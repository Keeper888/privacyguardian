"""
PrivacyGuardian - PII Detector
Fast regex-based PII detection with optional tiny LLM validation
"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum


class PIIType(Enum):
    # === PERSONAL IDENTIFIERS ===
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    SSN = "SSN"
    PASSPORT = "PASSPORT"
    DRIVERS_LICENSE = "DRV_LIC"
    DATE_OF_BIRTH = "DOB"

    # === FINANCIAL ===
    CREDIT_CARD = "CREDIT_CARD"
    BANK_ACCOUNT = "BANK_ACCT"
    IBAN = "IBAN"
    ROUTING_NUMBER = "ROUTING"
    TAX_ID = "TAX_ID"
    VAT_NUMBER = "VAT"

    # === HEALTH / HIPAA ===
    MEDICAL_RECORD = "MRN"
    HEALTH_INSURANCE = "HEALTH_INS"
    DEA_NUMBER = "DEA"
    NPI = "NPI"
    ICD_CODE = "ICD"
    NDC_CODE = "NDC"

    # === LEGAL ===
    CASE_NUMBER = "CASE_NUM"
    BAR_NUMBER = "BAR_NUM"
    COURT_DOCKET = "DOCKET"

    # === BUSINESS / COMMERCIAL ===
    EIN = "EIN"
    DUNS_NUMBER = "DUNS"

    # === TECHNICAL / SECRETS ===
    API_KEY = "API_KEY"
    AWS_KEY = "AWS_KEY"
    PRIVATE_KEY = "PRIVATE_KEY"
    PASSWORD = "PASSWORD"
    IP_ADDRESS = "IP_ADDRESS"
    MAC_ADDRESS = "MAC_ADDRESS"
    JWT_TOKEN = "JWT_TOKEN"
    GITHUB_TOKEN = "GITHUB_TOKEN"
    SLACK_TOKEN = "SLACK_TOKEN"
    DATABASE_URL = "DATABASE_URL"
    SECRET = "SECRET"
    OPENAI_KEY = "OPENAI_KEY"
    GOOGLE_KEY = "GOOGLE_KEY"
    STRIPE_KEY = "STRIPE_KEY"


@dataclass
class PIIMatch:
    pii_type: PIIType
    value: str
    start: int
    end: int
    confidence: float


# Compiled regex patterns for speed
PII_PATTERNS = {
    # =========================================================================
    # PERSONAL IDENTIFIERS
    # =========================================================================

    # Email addresses
    PIIType.EMAIL: re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    ),

    # Phone numbers (US/International formats)
    PIIType.PHONE: re.compile(
        r'(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'
    ),

    # Social Security Numbers (US)
    PIIType.SSN: re.compile(
        r'\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b'
    ),

    # Passport Numbers (with context to avoid false positives)
    PIIType.PASSPORT: re.compile(
        r'\b(?:passport)[#:\s]*([A-Z]{1,2}[0-9]{6,9}|[0-9]{9})\b',
        re.IGNORECASE
    ),

    # Driver's License (common US state formats)
    PIIType.DRIVERS_LICENSE: re.compile(
        r'\b(?:DL|D\.?L\.?|License)[#:\s]*([A-Z]?[0-9]{5,12})\b',
        re.IGNORECASE
    ),

    # Date of Birth patterns
    PIIType.DATE_OF_BIRTH: re.compile(
        r'\b(?:DOB|D\.?O\.?B\.?|birth\s*date|date\s*of\s*birth)[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b',
        re.IGNORECASE
    ),

    # =========================================================================
    # FINANCIAL
    # =========================================================================

    # Credit Card Numbers (major brands, with/without separators)
    PIIType.CREDIT_CARD: re.compile(
        r'\b(?:'
        r'4[0-9]{3}[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}|'  # Visa (16 digits)
        r'4[0-9]{12}(?:[0-9]{3})?|'                               # Visa (no separators)
        r'5[1-5][0-9]{2}[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}|'  # MasterCard
        r'5[1-5][0-9]{14}|'                                       # MasterCard (no separators)
        r'3[47][0-9]{2}[-\s]?[0-9]{6}[-\s]?[0-9]{5}|'            # AmEx
        r'3[47][0-9]{13}|'                                        # AmEx (no separators)
        r'6(?:011|5[0-9]{2})[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}|'  # Discover
        r'6(?:011|5[0-9]{2})[0-9]{12}'                            # Discover (no separators)
        r')\b'
    ),

    # Bank Account Numbers (with context)
    PIIType.BANK_ACCOUNT: re.compile(
        r'\b(?:account|acct)[#:\s]*([0-9]{8,17})\b',
        re.IGNORECASE
    ),

    # IBAN (International Bank Account Number)
    PIIType.IBAN: re.compile(
        r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}(?:[A-Z0-9]{0,16})?\b'
    ),

    # Routing Numbers (US ABA)
    PIIType.ROUTING_NUMBER: re.compile(
        r'\b(?:routing|ABA)[#:\s]*([0-9]{9})\b',
        re.IGNORECASE
    ),

    # Tax ID / TIN (with context)
    PIIType.TAX_ID: re.compile(
        r'\b(?:tax\s*id|TIN|taxpayer)[#:\s]*([0-9]{2}[-\s]?[0-9]{7})\b',
        re.IGNORECASE
    ),

    # VAT Numbers (EU format)
    PIIType.VAT_NUMBER: re.compile(
        r'\b(?:VAT)[#:\s]*([A-Z]{2}[A-Z0-9]{8,12})\b',
        re.IGNORECASE
    ),

    # =========================================================================
    # HEALTH / HIPAA
    # =========================================================================

    # Medical Record Number (MRN) - with context
    PIIType.MEDICAL_RECORD: re.compile(
        r'\b(?:MRN|medical\s*record|patient\s*(?:id|number))[#:\s]*([A-Z0-9]{6,15})\b',
        re.IGNORECASE
    ),

    # Health Insurance ID (with context)
    PIIType.HEALTH_INSURANCE: re.compile(
        r'\b(?:member\s*id|insurance\s*id|policy\s*(?:number|#)|subscriber\s*id)[#:\s]*([A-Z0-9]{6,20})\b',
        re.IGNORECASE
    ),

    # DEA Number (Drug Enforcement Administration) - specific format
    PIIType.DEA_NUMBER: re.compile(
        r'\b(?:DEA[#:\s]*)?([A-Z][A-Z9][0-9]{7})\b'
    ),

    # NPI (National Provider Identifier) - 10 digits with context
    PIIType.NPI: re.compile(
        r'\b(?:NPI)[#:\s]*([0-9]{10})\b',
        re.IGNORECASE
    ),

    # ICD-10 Diagnosis Codes
    PIIType.ICD_CODE: re.compile(
        r'\b(?:ICD[-\s]?10?|diagnosis)[:\s]*([A-Z][0-9]{2}(?:\.[0-9A-Z]{1,4})?)\b',
        re.IGNORECASE
    ),

    # NDC (National Drug Code)
    PIIType.NDC_CODE: re.compile(
        r'\b(?:NDC)[#:\s]*([0-9]{4,5}[-\s]?[0-9]{3,4}[-\s]?[0-9]{1,2})\b'
    ),

    # =========================================================================
    # LEGAL
    # =========================================================================

    # Case Numbers (court cases)
    PIIType.CASE_NUMBER: re.compile(
        r'\b(?:case|docket)[#:\s]*(\d{1,2}[-:](?:cv|cr|mc)[-:]\d{3,6}(?:[-:][A-Z]{2,4})?)\b',
        re.IGNORECASE
    ),

    # Attorney Bar Numbers
    PIIType.BAR_NUMBER: re.compile(
        r'\b(?:bar|attorney)[#:\s]*([A-Z]{0,2}[0-9]{5,8})\b',
        re.IGNORECASE
    ),

    # Court Docket Numbers
    PIIType.COURT_DOCKET: re.compile(
        r'\b(?:docket)[#:\s]*([0-9]{2}[-][A-Z]{2,4}[-][0-9]{3,7})\b',
        re.IGNORECASE
    ),

    # =========================================================================
    # BUSINESS / COMMERCIAL
    # =========================================================================

    # EIN (Employer Identification Number)
    PIIType.EIN: re.compile(
        r'\b(?:EIN|employer\s*id)[#:\s]*([0-9]{2}[-\s]?[0-9]{7})\b',
        re.IGNORECASE
    ),

    # DUNS Number (9 digits)
    PIIType.DUNS_NUMBER: re.compile(
        r'\b(?:DUNS|D-U-N-S)[#:\s]*([0-9]{2}[-\s]?[0-9]{3}[-\s]?[0-9]{4})\b',
        re.IGNORECASE
    ),

    # =========================================================================
    # TECHNICAL / SECRETS
    # =========================================================================

    # Anthropic API Keys
    PIIType.API_KEY: re.compile(
        r'\bsk-ant-(?:api\d{2}-)?[A-Za-z0-9_-]{20,}\b'
    ),

    # OpenAI API Keys
    PIIType.OPENAI_KEY: re.compile(
        r'\bsk-[A-Za-z0-9]{32,}(?:-[A-Za-z0-9]+)?\b'
    ),

    # Google API Keys
    PIIType.GOOGLE_KEY: re.compile(
        r'\bAIza[A-Za-z0-9_-]{35}\b'
    ),

    # Stripe API Keys
    PIIType.STRIPE_KEY: re.compile(
        r'\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{24,}\b'
    ),

    # AWS Access Keys
    PIIType.AWS_KEY: re.compile(
        r'\b(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}\b'
    ),

    # Private Keys (PEM format)
    PIIType.PRIVATE_KEY: re.compile(
        r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
        re.MULTILINE
    ),

    # Password patterns (in config/env files)
    PIIType.PASSWORD: re.compile(
        r'(?:password|passwd|pwd|secret|token)[\s]*[=:]\s*["\']?([^\s"\']{8,})["\']?',
        re.IGNORECASE
    ),

    # IPv4 Addresses (private ranges)
    PIIType.IP_ADDRESS: re.compile(
        r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|'
        r'172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|'
        r'192\.168\.\d{1,3}\.\d{1,3})\b'
    ),

    # MAC Addresses
    PIIType.MAC_ADDRESS: re.compile(
        r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b'
    ),

    # JWT Tokens
    PIIType.JWT_TOKEN: re.compile(
        r'\beyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b'
    ),

    # GitHub Tokens (all types)
    PIIType.GITHUB_TOKEN: re.compile(
        r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b'
    ),

    # Slack Tokens
    PIIType.SLACK_TOKEN: re.compile(
        r'\bxox[baprs]-[A-Za-z0-9-]{10,}\b'
    ),

    # Database URLs with credentials
    PIIType.DATABASE_URL: re.compile(
        r'(?:postgres|mysql|mongodb|redis|mssql|oracle)(?:ql)?://[^:]+:[^@]+@[^\s]+',
        re.IGNORECASE
    ),

    # Generic secrets (env var style)
    PIIType.SECRET: re.compile(
        r'(?:^|\s)(?:SECRET|TOKEN|KEY|APIKEY|API_KEY|AUTH|CREDENTIAL)[_A-Z]*\s*[=:]\s*["\']?([A-Za-z0-9_\-/+=]{16,})["\']?',
        re.IGNORECASE | re.MULTILINE
    ),
}


class PIIDetector:
    """Fast PII detection using compiled regex patterns"""

    def __init__(self, custom_patterns: Optional[dict] = None):
        self.patterns = PII_PATTERNS.copy()
        if custom_patterns:
            self.patterns.update(custom_patterns)

    def detect(self, text: str) -> List[PIIMatch]:
        """Detect all PII in text, returns list of matches"""
        matches = []

        for pii_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                # Handle groups vs full match
                if match.groups():
                    value = match.group(1)
                    start = match.start(1)
                    end = match.end(1)
                else:
                    value = match.group(0)
                    start = match.start()
                    end = match.end()

                matches.append(PIIMatch(
                    pii_type=pii_type,
                    value=value,
                    start=start,
                    end=end,
                    confidence=0.95  # High confidence for regex matches
                ))

        # Sort by position (start) and remove overlaps
        matches.sort(key=lambda m: (m.start, -m.end))
        return self._remove_overlaps(matches)

    def _remove_overlaps(self, matches: List[PIIMatch]) -> List[PIIMatch]:
        """Remove overlapping matches, keep longer/higher priority ones"""
        if not matches:
            return matches

        result = []
        last_end = -1

        for match in matches:
            if match.start >= last_end:
                result.append(match)
                last_end = match.end

        return result

    def detect_and_mask(self, text: str) -> Tuple[str, List[PIIMatch]]:
        """Detect PII and return masked text + matches for encryption"""
        matches = self.detect(text)

        if not matches:
            return text, []

        # Build masked text (replace from end to preserve positions)
        masked = text
        for match in reversed(matches):
            placeholder = f"[{match.pii_type.value}]"
            masked = masked[:match.start] + placeholder + masked[match.end:]

        return masked, matches


# Optional: Tiny LLM validator for edge cases
class TinyLLMValidator:
    """
    Optional validator using a tiny local LLM (like TinyLlama or Phi-2)
    Only called for low-confidence detections or edge cases
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path

    def load(self):
        """Lazy load the model only when needed"""
        if self.model is not None:
            return

        try:
            # Try llama-cpp-python for minimal overhead
            from llama_cpp import Llama
            if self.model_path:
                self.model = Llama(
                    model_path=self.model_path,
                    n_ctx=512,      # Small context
                    n_threads=2,    # Minimal CPU usage
                    n_gpu_layers=0, # CPU only for minimal impact
                    verbose=False
                )
        except ImportError:
            print("Note: llama-cpp-python not installed, using regex-only mode")

    def validate(self, text: str, suspected_pii: str, pii_type: str) -> float:
        """
        Ask tiny LLM to validate if suspected text is actually PII
        Returns confidence score 0.0 - 1.0
        """
        if self.model is None:
            return 0.5  # Neutral if no model

        prompt = f"""Is this text personally identifiable information (PII) of type {pii_type}?
Text: "{suspected_pii}"
Answer only YES or NO:"""

        try:
            response = self.model(prompt, max_tokens=5, temperature=0)
            answer = response['choices'][0]['text'].strip().upper()
            return 0.95 if 'YES' in answer else 0.1
        except Exception:
            return 0.5


# Test
if __name__ == "__main__":
    detector = PIIDetector()

    test_text = """
    === PERSONAL ===
    Contact John at john.doe@example.com or call 555-123-4567.
    His SSN is 123-45-6789.
    DOB: 03/15/1985
    License: DL# A1234567

    === FINANCIAL ===
    Credit card: 4532-1234-5678-9012
    Bank account# 12345678901234
    IBAN: DE89370400440532013000
    Routing: 021000021
    EIN: 12-3456789
    Tax ID: 12-3456789

    === HEALTH (HIPAA) ===
    Patient ID: PAT123456
    MRN: MRN123456789
    Member ID: XYZ123456789
    DEA: AB1234567
    NPI: 1234567890
    ICD-10: J45.20
    NDC: 12345-6789-01

    === LEGAL ===
    Case# 23-cv-12345
    Bar# 123456
    Docket# 23-CV-001234

    === TECHNICAL ===
    API key: sk-ant-api03-abcdefghijklmnop123456
    OpenAI: sk-abcdefghijklmnopqrstuvwxyz123456
    Stripe: sk_live_abcdefghijklmnopqrstuvwx
    AWS: AKIAIOSFODNN7EXAMPLE
    Database: postgres://user:secretpass123@localhost:5432/mydb
    JWT: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U
    """

    print("=== PII Detection Test ===\n")
    matches = detector.detect(test_text)

    # Group by category
    categories = {
        "Personal": ["EMAIL", "PHONE", "SSN", "PASSPORT", "DRV_LIC", "DOB"],
        "Financial": ["CREDIT_CARD", "BANK_ACCT", "IBAN", "ROUTING", "TAX_ID", "VAT", "EIN"],
        "Health": ["MRN", "HEALTH_INS", "DEA", "NPI", "ICD", "NDC"],
        "Legal": ["CASE_NUM", "BAR_NUM", "DOCKET"],
        "Technical": ["API_KEY", "OPENAI_KEY", "GOOGLE_KEY", "STRIPE_KEY", "AWS_KEY",
                     "PRIVATE_KEY", "PASSWORD", "IP_ADDRESS", "MAC_ADDRESS",
                     "JWT_TOKEN", "GITHUB_TOKEN", "SLACK_TOKEN", "DATABASE_URL", "SECRET"],
    }

    for cat, types in categories.items():
        cat_matches = [m for m in matches if m.pii_type.value in types]
        if cat_matches:
            print(f"\n--- {cat} ---")
            for m in cat_matches:
                print(f"  [{m.pii_type.value}] '{m.value[:40]}...' " if len(m.value) > 40
                      else f"  [{m.pii_type.value}] '{m.value}'")

    print(f"\n=== Summary: {len(matches)} items detected ===\n")
