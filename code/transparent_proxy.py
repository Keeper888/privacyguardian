"""
PrivacyGuardian - Transparent HTTPS Proxy
==========================================
Intercepts ALL traffic to LLM APIs at the network level.
No app configuration needed - it just works.

Uses iptables + local CA certificate for HTTPS interception.
"""

import os
from pathlib import Path
from typing import Tuple
from datetime import datetime, timedelta

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from llm_endpoints import get_domains_for_iptables


class CertificateAuthority:
    """
    Local Certificate Authority for HTTPS interception.
    Generates a root CA and signs certificates for LLM domains on-the-fly.
    """

    def __init__(self, ca_dir: str = "~/.privacyguardian/ca"):
        self.ca_dir = Path(ca_dir).expanduser()
        self.ca_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.ca_dir, 0o700)

        self.ca_key_file = self.ca_dir / "privacyguardian-ca.key"
        self.ca_cert_file = self.ca_dir / "privacyguardian-ca.crt"
        self.certs_dir = self.ca_dir / "certs"
        self.certs_dir.mkdir(exist_ok=True)

        self._init_ca()

    def _init_ca(self):
        """Initialize or load the CA certificate"""
        if self.ca_key_file.exists() and self.ca_cert_file.exists():
            # Load existing CA
            with open(self.ca_key_file, "rb") as f:
                self.ca_key = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
            with open(self.ca_cert_file, "rb") as f:
                self.ca_cert = x509.load_pem_x509_certificate(
                    f.read(), default_backend()
                )
        else:
            # Generate new CA
            self._generate_ca()

    def _generate_ca(self):
        """Generate a new CA certificate"""
        print("🔐 Generating PrivacyGuardian CA certificate...")

        # Generate CA private key
        self.ca_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )

        # CA certificate subject
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Local"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PrivacyGuardian"),
            x509.NameAttribute(NameOID.COMMON_NAME, "PrivacyGuardian Local CA"),
        ])

        # Build CA certificate
        self.ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(self.ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=3650))  # 10 years
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=0),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(self.ca_key, hashes.SHA256(), default_backend())
        )

        # Save CA key
        with open(self.ca_key_file, "wb") as f:
            f.write(self.ca_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        os.chmod(self.ca_key_file, 0o600)

        # Save CA certificate
        with open(self.ca_cert_file, "wb") as f:
            f.write(self.ca_cert.public_bytes(serialization.Encoding.PEM))

        print(f"✓ CA certificate saved to: {self.ca_cert_file}")

    def get_cert_for_domain(self, domain: str) -> Tuple[str, str]:
        """
        Get or generate a certificate for a domain.
        Returns: (cert_path, key_path)
        """
        # Sanitize domain name for filename
        safe_domain = domain.replace(".", "_").replace("*", "wildcard")
        cert_file = self.certs_dir / f"{safe_domain}.crt"
        key_file = self.certs_dir / f"{safe_domain}.key"

        if cert_file.exists() and key_file.exists():
            return str(cert_file), str(key_file)

        # Generate new certificate for domain
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, domain),
        ])

        # Build certificate
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self.ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName(domain),
                    x509.DNSName(f"*.{domain}"),
                ]),
                critical=False,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
            .sign(self.ca_key, hashes.SHA256(), default_backend())
        )

        # Save certificate
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        # Save key
        with open(key_file, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        os.chmod(key_file, 0o600)

        return str(cert_file), str(key_file)

    def get_ca_cert_path(self) -> str:
        """Get path to CA certificate for installation"""
        return str(self.ca_cert_file)


class IPTablesManager:
    """
    Manage iptables rules for transparent traffic interception.
    Redirects traffic to LLM API IPs through the local proxy.
    """

    CHAIN_NAME = "PRIVACYGUARDIAN"

    def __init__(self, proxy_port: int = 8443):
        self.proxy_port = proxy_port
        self.domains = get_domains_for_iptables()

    def _run_iptables(self, *args, check: bool = True) -> bool:
        """Run iptables command"""
        import subprocess
        cmd = ["sudo", "iptables"] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"iptables error: {result.stderr}")
            return False
        return result.returncode == 0

    def _resolve_domain(self, domain: str) -> list:
        """Resolve domain to IP addresses"""
        import subprocess
        result = subprocess.run(
            ["dig", "+short", domain],
            capture_output=True, text=True
        )
        ips = [ip.strip() for ip in result.stdout.strip().split('\n') if ip.strip()]
        # Filter only valid IPs (not CNAMEs)
        return [ip for ip in ips if all(c.isdigit() or c == '.' for c in ip)]

    def install_rules(self) -> bool:
        """Install iptables rules for LLM traffic interception"""
        print("🔧 Setting up iptables rules for LLM traffic interception...\n")

        # Create custom chain
        self._run_iptables("-t", "nat", "-N", self.CHAIN_NAME, check=False)

        # Flush existing rules in our chain
        self._run_iptables("-t", "nat", "-F", self.CHAIN_NAME)

        # Resolve all LLM domains and add redirect rules
        for domain in self.domains:
            ips = self._resolve_domain(domain)
            for ip in ips:
                print(f"  → {domain} ({ip})")
                self._run_iptables(
                    "-t", "nat", "-A", self.CHAIN_NAME,
                    "-p", "tcp", "-d", ip, "--dport", "443",
                    "-j", "REDIRECT", "--to-port", str(self.proxy_port)
                )

        # Link our chain to OUTPUT
        # First remove any existing link
        self._run_iptables(
            "-t", "nat", "-D", "OUTPUT",
            "-j", self.CHAIN_NAME,
            check=False
        )
        # Add the link
        self._run_iptables(
            "-t", "nat", "-A", "OUTPUT",
            "-j", self.CHAIN_NAME
        )

        print(f"\n✓ iptables rules installed. All LLM traffic redirected to port {self.proxy_port}")
        return True

    def remove_rules(self) -> bool:
        """Remove iptables rules"""
        print("🔧 Removing iptables rules...")

        # Remove link from OUTPUT
        self._run_iptables(
            "-t", "nat", "-D", "OUTPUT",
            "-j", self.CHAIN_NAME,
            check=False
        )

        # Flush and delete our chain
        self._run_iptables("-t", "nat", "-F", self.CHAIN_NAME, check=False)
        self._run_iptables("-t", "nat", "-X", self.CHAIN_NAME, check=False)

        print("✓ iptables rules removed")
        return True

    def status(self) -> dict:
        """Get iptables rules status"""
        import subprocess
        result = subprocess.run(
            ["sudo", "iptables", "-t", "nat", "-L", self.CHAIN_NAME, "-n", "-v"],
            capture_output=True, text=True
        )
        return {
            "installed": result.returncode == 0,
            "rules": result.stdout if result.returncode == 0 else None
        }


def install_ca_certificate():
    """Install CA certificate system-wide"""
    ca = CertificateAuthority()
    ca_path = ca.get_ca_cert_path()

    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║              🔐 CA Certificate Installation                       ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  To enable transparent HTTPS interception, you need to trust    ║
║  the PrivacyGuardian CA certificate.                            ║
║                                                                  ║
║  Certificate location:                                           ║
║  {ca_path:<50}          ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")

    print("Installing CA certificate system-wide...\n")

    import subprocess

    # Copy to system CA store
    dest = "/usr/local/share/ca-certificates/privacyguardian-ca.crt"

    result = subprocess.run(
        ["sudo", "cp", ca_path, dest],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"Error copying certificate: {result.stderr}")
        return False

    # Update CA certificates
    result = subprocess.run(
        ["sudo", "update-ca-certificates"],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        print("✓ CA certificate installed system-wide")
        print("\nBrowsers may need manual import:")
        print(f"  Firefox: Settings → Privacy → Certificates → Import → {ca_path}")
        print("  Chrome: Settings → Privacy → Security → Manage certificates → Import")
        return True
    else:
        print(f"Error updating certificates: {result.stderr}")
        return False


def generate_iptables_script() -> str:
    """Generate a standalone iptables setup script"""
    domains = get_domains_for_iptables()

    script = """#!/bin/bash
# PrivacyGuardian - iptables setup script
# Redirects LLM API traffic through the local proxy

PROXY_PORT=8443
CHAIN_NAME="PRIVACYGUARDIAN"

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

case "$1" in
    install)
        echo "Installing iptables rules for LLM traffic interception..."

        # Create chain
        iptables -t nat -N $CHAIN_NAME 2>/dev/null || true
        iptables -t nat -F $CHAIN_NAME

        # Add rules for each LLM API
"""

    for domain in domains:
        script += f"""
        # {domain}
        for ip in $(dig +short {domain} | grep -E '^[0-9.]+$'); do
            iptables -t nat -A $CHAIN_NAME -p tcp -d $ip --dport 443 -j REDIRECT --to-port $PROXY_PORT
            echo "  → {domain} ($ip)"
        done
"""

    script += """
        # Link to OUTPUT chain
        iptables -t nat -D OUTPUT -j $CHAIN_NAME 2>/dev/null || true
        iptables -t nat -A OUTPUT -j $CHAIN_NAME

        echo "✓ iptables rules installed"
        ;;

    remove)
        echo "Removing iptables rules..."
        iptables -t nat -D OUTPUT -j $CHAIN_NAME 2>/dev/null || true
        iptables -t nat -F $CHAIN_NAME 2>/dev/null || true
        iptables -t nat -X $CHAIN_NAME 2>/dev/null || true
        echo "✓ iptables rules removed"
        ;;

    status)
        echo "PrivacyGuardian iptables rules:"
        iptables -t nat -L $CHAIN_NAME -n -v 2>/dev/null || echo "Not installed"
        ;;

    *)
        echo "Usage: $0 {install|remove|status}"
        exit 1
        ;;
esac
"""
    return script


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python transparent_proxy.py [install-ca|install-iptables|remove-iptables|status|generate-script]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "install-ca":
        install_ca_certificate()

    elif cmd == "install-iptables":
        mgr = IPTablesManager()
        mgr.install_rules()

    elif cmd == "remove-iptables":
        mgr = IPTablesManager()
        mgr.remove_rules()

    elif cmd == "status":
        mgr = IPTablesManager()
        status = mgr.status()
        print("iptables status:", "installed" if status["installed"] else "not installed")
        if status["rules"]:
            print(status["rules"])

    elif cmd == "generate-script":
        script = generate_iptables_script()
        script_path = Path(__file__).parent.parent / "iptables-setup.sh"
        script_path.write_text(script)
        os.chmod(script_path, 0o755)
        print(f"✓ Script generated: {script_path}")

    else:
        print(f"Unknown command: {cmd}")
