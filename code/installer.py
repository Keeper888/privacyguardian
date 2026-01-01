"""
PrivacyGuardian - Installer
============================
Sets up systemd service, iptables rules, and desktop integration.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple

from llm_endpoints import get_domains_for_iptables


class Installer:
    """Install/uninstall PrivacyGuardian system integration"""

    def __init__(self):
        self.project_dir = Path(__file__).parent.parent.absolute()
        self.user = os.environ.get("USER", "user")
        self.home = Path.home()

        # Paths
        self.systemd_user_dir = self.home / ".config" / "systemd" / "user"
        self.service_file = self.systemd_user_dir / "privacyguardian.service"
        self.autostart_dir = self.home / ".config" / "autostart"
        self.desktop_file = self.autostart_dir / "privacyguardian.desktop"

    def install(self) -> bool:
        """Full installation"""
        print("🛡️  Installing PrivacyGuardian...\n")

        steps = [
            ("Creating systemd service", self._create_systemd_service),
            ("Enabling service", self._enable_service),
            ("Creating desktop autostart", self._create_desktop_entry),
            ("Setting up notifications", self._setup_notifications),
        ]

        for name, func in steps:
            print(f"  → {name}...", end=" ", flush=True)
            try:
                success, msg = func()
                if success:
                    print("✓")
                else:
                    print(f"✗ ({msg})")
                    return False
            except Exception as e:
                print(f"✗ ({e})")
                return False

        print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                  ✓ Installation Complete!                        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  PrivacyGuardian will now start automatically on login.         ║
║                                                                  ║
║  Commands:                                                       ║
║    Start now:    systemctl --user start privacyguardian          ║
║    Stop:         systemctl --user stop privacyguardian           ║
║    Status:       systemctl --user status privacyguardian         ║
║    Logs:         journalctl --user -u privacyguardian -f         ║
║                                                                  ║
║  GUI Dashboard:  ./guardian gui                                  ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
        """)

        return True

    def uninstall(self) -> bool:
        """Remove all system integration"""
        print("🛡️  Uninstalling PrivacyGuardian...\n")

        # Stop service
        print("  → Stopping service...", end=" ", flush=True)
        subprocess.run(
            ["systemctl", "--user", "stop", "privacyguardian"],
            capture_output=True
        )
        print("✓")

        # Disable service
        print("  → Disabling service...", end=" ", flush=True)
        subprocess.run(
            ["systemctl", "--user", "disable", "privacyguardian"],
            capture_output=True
        )
        print("✓")

        # Remove files
        for path, name in [
            (self.service_file, "systemd service"),
            (self.desktop_file, "desktop entry"),
        ]:
            print(f"  → Removing {name}...", end=" ", flush=True)
            if path.exists():
                path.unlink()
            print("✓")

        # Reload systemd
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)

        print("\n✓ Uninstallation complete!")
        return True

    def _create_systemd_service(self) -> Tuple[bool, str]:
        """Create systemd user service file"""
        self.systemd_user_dir.mkdir(parents=True, exist_ok=True)

        # Find Python in venv
        venv_python = self.project_dir / "venv" / "bin" / "python"
        if not venv_python.exists():
            return False, "Virtual environment not found. Run ./guardian setup first."

        service_content = f"""[Unit]
Description=PrivacyGuardian - Universal LLM PII Protection
Documentation=https://github.com/Keeper888/privacyguardian
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={venv_python} {self.project_dir}/code/guardian_proxy.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
WorkingDirectory={self.project_dir}/code

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={self.home}/.privacyguardian

[Install]
WantedBy=default.target
"""

        self.service_file.write_text(service_content)
        return True, ""

    def _enable_service(self) -> Tuple[bool, str]:
        """Enable and start the systemd service"""
        # Reload daemon
        result = subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True, text=True
        )

        # Enable service
        result = subprocess.run(
            ["systemctl", "--user", "enable", "privacyguardian"],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            return False, result.stderr

        # Start service
        result = subprocess.run(
            ["systemctl", "--user", "start", "privacyguardian"],
            capture_output=True, text=True
        )

        # Enable lingering so service runs even when logged out
        subprocess.run(
            ["loginctl", "enable-linger", self.user],
            capture_output=True
        )

        return True, ""

    def _create_desktop_entry(self) -> Tuple[bool, str]:
        """Create desktop autostart entry for GUI notification"""
        self.autostart_dir.mkdir(parents=True, exist_ok=True)

        desktop_content = f"""[Desktop Entry]
Type=Application
Name=PrivacyGuardian
Comment=LLM PII Protection Proxy
Exec={self.project_dir}/guardian notify-startup
Icon=security-high
Terminal=false
Categories=Security;Network;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""

        self.desktop_file.write_text(desktop_content)
        return True, ""

    def _setup_notifications(self) -> Tuple[bool, str]:
        """Ensure notification dependencies are available"""
        # Check for notify-send
        if not shutil.which("notify-send"):
            return False, "notify-send not found. Install libnotify-bin."

        return True, ""

    def status(self) -> dict:
        """Get installation status"""
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "privacyguardian"],
            capture_output=True, text=True
        )
        service_active = result.stdout.strip() == "active"

        result = subprocess.run(
            ["systemctl", "--user", "is-enabled", "privacyguardian"],
            capture_output=True, text=True
        )
        service_enabled = result.stdout.strip() == "enabled"

        return {
            "service_installed": self.service_file.exists(),
            "service_enabled": service_enabled,
            "service_active": service_active,
            "desktop_entry": self.desktop_file.exists(),
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="PrivacyGuardian Installer")
    parser.add_argument("action", choices=["install", "uninstall", "status"],
                        help="Action to perform")
    args = parser.parse_args()

    installer = Installer()

    if args.action == "install":
        installer.install()
    elif args.action == "uninstall":
        installer.uninstall()
    elif args.action == "status":
        status = installer.status()
        print("PrivacyGuardian Status:")
        for key, value in status.items():
            icon = "✓" if value else "✗"
            print(f"  {icon} {key.replace('_', ' ').title()}: {value}")


if __name__ == "__main__":
    main()
