"""
PrivacyGuardian Native Crypto - Python bindings for libpgcrypto.so
Uses XChaCha20-Poly1305 via libsodium for fast, secure encryption.
"""

import ctypes
from ctypes import c_char_p, c_int, c_void_p
from pathlib import Path
import os


class CryptoNative:
    """Python wrapper for the C crypto library (libpgcrypto.so)"""

    def __init__(self, lib_path: str = None, key_path: str = None):
        """
        Initialize the native crypto library.

        Args:
            lib_path: Path to libpgcrypto.so (auto-detected if None)
            key_path: Path to master key file (default: ~/.privacyguardian/pg_master.key)
        """
        if lib_path is None:
            # Look for library in common locations
            search_paths = [
                Path(__file__).parent.parent / "build" / "libpgcrypto.so",
                Path("/usr/local/lib/libpgcrypto.so"),
                Path("/usr/lib/libpgcrypto.so"),
            ]
            for path in search_paths:
                if path.exists():
                    lib_path = str(path)
                    break
            else:
                raise FileNotFoundError(
                    "libpgcrypto.so not found. Run 'make' to build it."
                )

        # Load the library
        self._lib = ctypes.CDLL(lib_path)

        # Define function signatures - use c_void_p for returned pointers
        self._lib.privacy_guardian_init.argtypes = [c_char_p]
        self._lib.privacy_guardian_init.restype = c_int

        self._lib.privacy_guardian_encrypt.argtypes = [c_char_p, c_char_p]
        self._lib.privacy_guardian_encrypt.restype = c_void_p

        self._lib.privacy_guardian_decrypt.argtypes = [c_char_p]
        self._lib.privacy_guardian_decrypt.restype = c_void_p

        self._lib.privacy_guardian_free.argtypes = [c_void_p]
        self._lib.privacy_guardian_free.restype = None

        # Initialize with key path
        if key_path is None:
            key_dir = Path.home() / ".privacyguardian"
            key_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(key_dir, 0o700)
            key_path = str(key_dir / "pg_master.key")

        result = self._lib.privacy_guardian_init(key_path.encode('utf-8'))
        if result != 0:
            raise RuntimeError("Failed to initialize crypto library")

        self._initialized = True

    def encrypt(self, plaintext: str, pii_type: str = None) -> str:
        """
        Encrypt a PII value and return a token.

        Args:
            plaintext: The sensitive value to encrypt
            pii_type: Type of PII (e.g., "EMAIL", "PHONE") - stored in token

        Returns:
            Encrypted token string (e.g., "◈PG:abc123...◈")
        """
        if not self._initialized:
            raise RuntimeError("Crypto library not initialized")

        pii_type_bytes = pii_type.encode('utf-8') if pii_type else None

        result_ptr = self._lib.privacy_guardian_encrypt(
            plaintext.encode('utf-8'),
            pii_type_bytes
        )

        if not result_ptr:
            raise RuntimeError("Encryption failed")

        # Copy the result before freeing
        result = ctypes.string_at(result_ptr).decode('utf-8')
        self._lib.privacy_guardian_free(result_ptr)

        return result

    def decrypt(self, token: str) -> str:
        """
        Decrypt a token back to the original value.

        Args:
            token: The encrypted token (e.g., "◈PG:abc123...◈")

        Returns:
            Original plaintext with type prefix (e.g., "EMAIL|user@example.com")
        """
        if not self._initialized:
            raise RuntimeError("Crypto library not initialized")

        result_ptr = self._lib.privacy_guardian_decrypt(token.encode('utf-8'))

        if not result_ptr:
            return None  # Decryption failed (invalid token)

        # Copy the result before freeing
        result = ctypes.string_at(result_ptr).decode('utf-8')
        self._lib.privacy_guardian_free(result_ptr)

        return result

    def decrypt_value_only(self, token: str) -> str:
        """
        Decrypt a token and return only the value (without type prefix).

        Args:
            token: The encrypted token

        Returns:
            Original plaintext value only
        """
        result = self.decrypt(token)
        if result and '|' in result:
            return result.split('|', 1)[1]
        return result


# Global instance (lazy loaded)
_crypto_instance = None


def get_crypto() -> CryptoNative:
    """Get the global crypto instance (creates it on first call)."""
    global _crypto_instance
    if _crypto_instance is None:
        _crypto_instance = CryptoNative()
    return _crypto_instance
