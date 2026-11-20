"""
PrivacyGuardian - PII Detector
Fast regex-based PII detection with Presidio NLP layer for semantic PII.
"""

import re
import os
import hashlib
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
    SSH_KEY = "SSH_KEY"
    FILE_PATH = "FILE_PATH"
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

    # === SEMANTIC (detected by Presidio NLP) ===
    PERSON_NAME = "PERSON"
    LOCATION = "LOCATION"


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
    # New format: sk-proj-... / sk-svcacct-...
    # Old format: sk- followed by 32+ consecutive alphanumeric chars (no dashes)
    #   — dashes in Anthropic keys (sk-ant-...) naturally break this match
    PIIType.OPENAI_KEY: re.compile(
        r'\bsk-(?:proj|svcacct)-[A-Za-z0-9_-]{40,}\b'
        r'|\bsk-[A-Za-z0-9]{32,}\b'
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

    # SSH Public Keys
    PIIType.SSH_KEY: re.compile(
        r'\b(?:ssh-rsa|ssh-ed25519|ssh-dss|ecdsa-sha2-nistp(?:256|384|521))\s+[A-Za-z0-9+/]{20,}={0,2}(?:\s+\S+)?\b'
    ),

    # Sensitive file paths (SSH keys, credentials, secrets, env files)
    PIIType.FILE_PATH: re.compile(
        r'(?:'
        r'~|/home/[^/\s]+|/root|/Users/[^/\s]+'
        r'|[A-Za-z]:\\Users\\[^\\]+|%USERPROFILE%|%APPDATA%'
        r')'
        r'(?:[/\\][^\s,\'"<>]{1,80})*'
        r'[/\\](?:'
        r'\.ssh|\.aws|\.gnupg|\.pgp'
        r'|secrets?(?:\.md|\.txt|\.json|\.yaml|\.env)?'
        r'|credentials?(?:\.md|\.txt|\.json)?'
        r'|\.env(?:\.[a-z]+)?'
        r'|id_rsa|id_ed25519|id_ecdsa|id_dsa'
        r'|private[_-]?key'
        r'|[^\s/\\]*\.pem|[^\s/\\]*\.p12|[^\s/\\]*\.pfx'
        r')[^\s,\'"<>]*',
        re.IGNORECASE
    ),

    # Password patterns (in config/env files)
    PIIType.PASSWORD: re.compile(
        r'(?:password|passwd|pwd|secret|token)[\s]*[=:]\s*["\']?([^\s"\']{8,})["\']?',
        re.IGNORECASE
    ),

    # IPv4 Addresses — all valid addresses except loopback/unspecified/broadcast
    # Validates each octet is 0-255, excludes 127.x.x.x, 0.0.0.0, 255.255.255.255
    PIIType.IP_ADDRESS: re.compile(
        r'\b(?!'
        r'127\.\d+\.\d+\.\d+|'    # loopback
        r'0\.0\.0\.0|'             # unspecified
        r'255\.255\.255\.255'      # broadcast
        r')'
        r'(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}'
        r'(?:25[0-5]|2[0-4]\d|[01]?\d\d?)'
        r'\b'
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


class PresidioNLPDetector:
    """
    NLP-based PII detection using Microsoft Presidio + spaCy.
    Catches semantic PII that regex can't: names, addresses, organizations.
    Lazy-loaded so the proxy starts instantly even if spaCy model isn't downloaded.
    """

    # Map Presidio entity types to our PIIType enum
    ENTITY_MAP = {
        "PERSON": PIIType.PERSON_NAME,
        "LOCATION": PIIType.LOCATION,
        "GPE": PIIType.LOCATION,       # Geopolitical entity
        "LOC": PIIType.LOCATION,
    }

    def __init__(self):
        self._analyzer = None
        self._available = None  # None = not yet checked
        self._cache: dict = {}

    def _try_load(self) -> bool:
        """Attempt to load Presidio. Returns True if successful."""
        if self._available is not None:
            return self._available
        try:
            from presidio_analyzer import AnalyzerEngine
            self._analyzer = AnalyzerEngine()
            self._available = True
            print("[PrivacyGuardian] Presidio NLP detector loaded.")
        except Exception:
            self._available = False
            print("[PrivacyGuardian] Presidio not available — install presidio-analyzer + spacy model for NLP detection.")
        return self._available

    def detect(self, text: str) -> List[PIIMatch]:
        """Run Presidio NLP detection. Returns empty list if not available.
        Results are cached per string: agent requests resend the whole history every turn."""
        if not self._try_load():
            return []
        key = hashlib.sha256(text.encode("utf-8", "surrogatepass")).digest()
        if key in self._cache:
            return self._cache[key]
        result = self._analyze(text)
        if len(self._cache) > 4096:
            self._cache.clear()
        self._cache[key] = result
        return result

    def _analyze(self, text: str) -> List[PIIMatch]:
        try:
            results = self._analyzer.analyze(text=text, language="en")
            matches = []
            for r in results:
                pii_type = self.ENTITY_MAP.get(r.entity_type)
                if pii_type is None:
                    continue
                matches.append(PIIMatch(
                    pii_type=pii_type,
                    value=text[r.start:r.end],
                    start=r.start,
                    end=r.end,
                    confidence=r.score,
                ))
            return matches
        except Exception:
            return []


class PIIDetector:
    """
    PII detection: regex patterns (fast, high precision) +
    optional Presidio NLP layer (names, addresses, semantic context).
    """

    def __init__(self, custom_patterns: Optional[dict] = None, use_nlp: Optional[bool] = None):
        # NLP is slow on 100k-token agent requests and noisy on source code: opt-in via PG_NLP=1
        if use_nlp is None:
            use_nlp = os.environ.get("PG_NLP", "") == "1"
        self.patterns = PII_PATTERNS.copy()
        if custom_patterns:
            self.patterns.update(custom_patterns)
        self.nlp = PresidioNLPDetector() if use_nlp else None

    def detect(self, text: str) -> List[PIIMatch]:
        """Detect all PII in text — regex first, then NLP layer."""
        matches = []

        for pii_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
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
                    confidence=0.95,
                ))

        # NLP layer: adds names, addresses, anything regex misses
        if self.nlp:
            nlp_matches = self.nlp.detect(text)
            matches.extend(nlp_matches)

        # Sort by position and remove overlaps (regex wins over NLP on ties)
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


