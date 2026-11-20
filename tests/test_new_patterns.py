"""
PrivacyGuardian - Tests for new patterns and fixes
====================================================
Covers: public IPs, SSH keys, file paths, OpenAI key disambiguation,
        (streaming is covered in test_courier.py).
"""

import sys
sys.path.insert(0, 'code')

import pytest
from pii_detector import PIIDetector, PIIType

TOKEN_CHAR = '\u25c8'


@pytest.fixture
def detector():
    return PIIDetector(use_nlp=False)


# =============================================================================
# IP ADDRESS
# =============================================================================

class TestIPAddress:
    def test_public_ip_detected(self, detector):
        matches = detector.detect("server at 46.224.103.207")
        assert any(m.pii_type == PIIType.IP_ADDRESS for m in matches)

    def test_private_ip_still_detected(self, detector):
        matches = detector.detect("device at 192.168.50.158")
        assert any(m.pii_type == PIIType.IP_ADDRESS for m in matches)

    def test_loopback_not_detected(self, detector):
        matches = detector.detect("127.0.0.1")
        assert not any(m.pii_type == PIIType.IP_ADDRESS for m in matches)

    def test_unspecified_not_detected(self, detector):
        matches = detector.detect("0.0.0.0")
        assert not any(m.pii_type == PIIType.IP_ADDRESS for m in matches)

    def test_broadcast_not_detected(self, detector):
        matches = detector.detect("255.255.255.255")
        assert not any(m.pii_type == PIIType.IP_ADDRESS for m in matches)

    def test_vpn_ip_detected(self, detector):
        matches = detector.detect("VPN: 10.66.66.1")
        assert any(m.pii_type == PIIType.IP_ADDRESS for m in matches)


# =============================================================================
# SSH PUBLIC KEYS
# =============================================================================

class TestSSHKey:
    def test_rsa_public_key(self, detector):
        text = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7example user@host"
        matches = detector.detect(text)
        assert any(m.pii_type == PIIType.SSH_KEY for m in matches)

    def test_ed25519_public_key(self, detector):
        text = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOexample user@host"
        matches = detector.detect(text)
        assert any(m.pii_type == PIIType.SSH_KEY for m in matches)

    def test_ecdsa_public_key(self, detector):
        text = "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYexample user@host"
        matches = detector.detect(text)
        assert any(m.pii_type == PIIType.SSH_KEY for m in matches)

    def test_private_key_pem_still_detected(self, detector):
        text = "-----BEGIN OPENSSH PRIVATE KEY-----\nAAAA\n-----END OPENSSH PRIVATE KEY-----"
        matches = detector.detect(text)
        assert any(m.pii_type == PIIType.PRIVATE_KEY for m in matches)


# =============================================================================
# FILE PATHS
# =============================================================================

class TestFilePath:
    def test_ssh_dir_unix(self, detector):
        matches = detector.detect("key is at ~/.ssh/hetzner")
        assert any(m.pii_type == PIIType.FILE_PATH for m in matches)

    def test_secrets_md(self, detector):
        matches = detector.detect("check ~/.claude/secrets.md")
        assert any(m.pii_type == PIIType.FILE_PATH for m in matches)

    def test_env_file(self, detector):
        matches = detector.detect("load ~/.env.production")
        assert any(m.pii_type == PIIType.FILE_PATH for m in matches)

    def test_aws_credentials(self, detector):
        matches = detector.detect("credentials in ~/.aws/credentials")
        assert any(m.pii_type == PIIType.FILE_PATH for m in matches)

    def test_pem_file(self, detector):
        matches = detector.detect("cert at /home/user/server.pem")
        assert any(m.pii_type == PIIType.FILE_PATH for m in matches)

    def test_id_rsa(self, detector):
        matches = detector.detect("/root/.ssh/id_rsa")
        assert any(m.pii_type == PIIType.FILE_PATH for m in matches)


# =============================================================================
# OPENAI KEY DISAMBIGUATION
# =============================================================================

class TestOpenAIKey:
    def test_new_format_proj(self, detector):
        key = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqr"
        matches = detector.detect(key)
        assert any(m.pii_type == PIIType.OPENAI_KEY for m in matches)

    def test_old_format(self, detector):
        key = "sk-" + "T3Blbk" + "FJabcdefghijklmnopqrstuvwxyz1234567890abcdef"  # split: fake key, keeps secret scanners quiet
        matches = detector.detect(key)
        assert any(m.pii_type == PIIType.OPENAI_KEY for m in matches)

    def test_anthropic_not_classified_as_openai(self, detector):
        key = "sk-ant-api03-ABCDEFGHIJKLMNOPabcdefghijklmnop"
        matches = detector.detect(key)
        assert not any(m.pii_type == PIIType.OPENAI_KEY for m in matches), \
            "Anthropic key must not be classified as OPENAI_KEY"
        assert any(m.pii_type == PIIType.API_KEY for m in matches), \
            "Anthropic key must still be detected as API_KEY"

    def test_stripe_not_classified_as_openai(self, detector):
        key = "sk_live_abcdefghijklmnopqrstuvwx"
        matches = detector.detect(key)
        assert not any(m.pii_type == PIIType.OPENAI_KEY for m in matches)
        assert any(m.pii_type == PIIType.STRIPE_KEY for m in matches)
