"""
PrivacyGuardian - Basic Tests
=============================
5 essential tests that verify core functionality works.
"""

import sys
sys.path.insert(0, 'code')

import pytest


# =============================================================================
# TEST 1: Email Detection
# =============================================================================
# WHY: Emails are the #1 most common PII. If this doesn't work, nothing works.

def test_email_detection():
    """Verify the system detects email addresses"""
    from pii_detector import PIIDetector

    detector = PIIDetector()

    # Test with a clear email
    text = "Contact me at john@example.com for more info"
    matches = detector.detect(text)

    # Should find exactly 1 email
    email_matches = [m for m in matches if m.pii_type.value == "EMAIL"]
    assert len(email_matches) == 1, "Should detect exactly 1 email"
    assert "john@example.com" in email_matches[0].value


# =============================================================================
# TEST 2: Phone Number Detection
# =============================================================================
# WHY: Phone numbers have many formats (555-123-4567, (555) 123-4567, etc.)
#      Need to make sure common formats are caught.

def test_phone_detection():
    """Verify the system detects phone numbers in various formats"""
    from pii_detector import PIIDetector

    detector = PIIDetector()

    # Test different phone formats
    test_cases = [
        "Call me at 555-123-4567",
        "Phone: (555) 123-4567",
        "Reach me at 555.123.4567",
    ]

    for text in test_cases:
        matches = detector.detect(text)
        phone_matches = [m for m in matches if m.pii_type.value == "PHONE"]
        assert len(phone_matches) >= 1, f"Should detect phone in: {text}"


# =============================================================================
# TEST 3: LLM Provider Detection
# =============================================================================
# WHY: The proxy needs to know which API it's talking to (OpenAI vs Anthropic)
#      so it can parse the request correctly. Wrong provider = broken parsing.

def test_provider_detection():
    """Verify correct LLM provider is identified from domain"""
    from llm_endpoints import get_provider_for_domain

    # Test known providers
    assert get_provider_for_domain("api.anthropic.com").name == "Anthropic"
    assert get_provider_for_domain("api.openai.com").name == "OpenAI"
    assert get_provider_for_domain("api.mistral.ai").name == "Mistral AI"

    # Test unknown domain returns None
    assert get_provider_for_domain("random-site.com") is None


# =============================================================================
# TEST 4: Token Format Validity
# =============================================================================
# WHY: Tokens must have a specific format so they can be detected and decrypted
#      later. Wrong format = data loss.

def test_token_format():
    """Verify tokens are created with correct format"""
    from guardian_proxy import PrivacyGuardianProxy

    proxy = PrivacyGuardianProxy()

    # Protect some text with an email
    original = "My email is test@example.com"
    protected = proxy.protect_text(original)

    # Token should have correct format
    import re
    token_pattern = r'◈PG:[A-Z_]+_[a-f0-9]+◈'
    tokens_found = re.findall(token_pattern, protected)

    assert len(tokens_found) == 1, f"Should create exactly 1 token, got: {protected}"
    assert "test@example.com" not in protected, "Original email should be replaced"


# =============================================================================
# TEST 5: Round-Trip Protection
# =============================================================================
# WHY: The whole point is: protect -> send to AI -> unprotect -> get original.
#      If unprotect doesn't restore the original, the tool is useless.

def test_round_trip():
    """Verify protect then unprotect returns original content"""
    from guardian_proxy import PrivacyGuardianProxy

    proxy = PrivacyGuardianProxy()

    original = "Email: user@test.org, Phone: 555-867-5309"

    # Protect (encrypt)
    protected = proxy.protect_text(original)

    # Should be different (tokens inserted)
    assert protected != original, "Protected text should differ from original"

    # Unprotect (decrypt)
    restored = proxy.unprotect_text(protected)

    # Should get original back
    assert restored == original, f"Round-trip failed.\nOriginal: {original}\nRestored: {restored}"


# =============================================================================
# Run with: pytest tests/test_basic.py -v
# =============================================================================
