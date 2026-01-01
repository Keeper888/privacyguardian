/*
 * PrivacyGuardian - Crypto Core
 * Ultra-fast PII tokenization engine in C
 * Uses XChaCha20-Poly1305 for encryption (via libsodium)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sodium.h>

#define TOKEN_PREFIX "◈PG:"
#define TOKEN_SUFFIX "◈"
#define MAX_PII_LENGTH 4096
#define NONCE_SIZE crypto_aead_xchacha20poly1305_ietf_NPUBBYTES
#define KEY_SIZE crypto_aead_xchacha20poly1305_ietf_KEYBYTES
#define TAG_SIZE crypto_aead_xchacha20poly1305_ietf_ABYTES

// Global encryption key (loaded from file or generated)
static unsigned char master_key[KEY_SIZE];
static int initialized = 0;

// Initialize the crypto system
int pg_init(const char *key_path) {
    if (sodium_init() < 0) {
        fprintf(stderr, "Failed to initialize libsodium\n");
        return -1;
    }

    FILE *kf = fopen(key_path, "rb");
    if (kf) {
        // Load existing key
        if (fread(master_key, 1, KEY_SIZE, kf) != KEY_SIZE) {
            fclose(kf);
            return -1;
        }
        fclose(kf);
    } else {
        // Generate new key
        crypto_aead_xchacha20poly1305_ietf_keygen(master_key);
        kf = fopen(key_path, "wb");
        if (kf) {
            fwrite(master_key, 1, KEY_SIZE, kf);
            fclose(kf);
            // Secure permissions
            chmod(key_path, 0600);
        }
    }

    initialized = 1;
    return 0;
}

// Encrypt a PII value and return a token
// Returns: base64-encoded encrypted token, caller must free()
char* pg_encrypt_pii(const char *plaintext, const char *pii_type) {
    if (!initialized || !plaintext) return NULL;

    size_t pt_len = strlen(plaintext);
    size_t type_len = pii_type ? strlen(pii_type) : 0;

    // Create payload: type|plaintext
    size_t payload_len = type_len + 1 + pt_len;
    unsigned char *payload = malloc(payload_len);
    if (pii_type) {
        memcpy(payload, pii_type, type_len);
    }
    payload[type_len] = '|';
    memcpy(payload + type_len + 1, plaintext, pt_len);

    // Allocate ciphertext buffer (nonce + ciphertext + tag)
    size_t ct_len = NONCE_SIZE + payload_len + TAG_SIZE;
    unsigned char *ciphertext = malloc(ct_len);

    // Generate random nonce
    randombytes_buf(ciphertext, NONCE_SIZE);

    // Encrypt
    unsigned long long actual_ct_len;
    crypto_aead_xchacha20poly1305_ietf_encrypt(
        ciphertext + NONCE_SIZE, &actual_ct_len,
        payload, payload_len,
        NULL, 0,  // no additional data
        NULL,
        ciphertext,  // nonce
        master_key
    );

    // Base64 encode
    size_t b64_len = sodium_base64_ENCODED_LEN(NONCE_SIZE + actual_ct_len,
                                                sodium_base64_VARIANT_URLSAFE_NO_PADDING);
    char *token = malloc(strlen(TOKEN_PREFIX) + b64_len + strlen(TOKEN_SUFFIX) + 1);

    strcpy(token, TOKEN_PREFIX);
    sodium_bin2base64(token + strlen(TOKEN_PREFIX), b64_len,
                      ciphertext, NONCE_SIZE + actual_ct_len,
                      sodium_base64_VARIANT_URLSAFE_NO_PADDING);
    strcat(token, TOKEN_SUFFIX);

    free(payload);
    free(ciphertext);

    return token;
}

// Decrypt a token back to plaintext
// Returns: decrypted value with type prefix, caller must free()
char* pg_decrypt_token(const char *token) {
    if (!initialized || !token) return NULL;

    // Strip prefix/suffix
    const char *start = token;
    if (strncmp(token, TOKEN_PREFIX, strlen(TOKEN_PREFIX)) == 0) {
        start = token + strlen(TOKEN_PREFIX);
    }

    size_t token_len = strlen(start);
    if (token_len > strlen(TOKEN_SUFFIX) &&
        strcmp(start + token_len - strlen(TOKEN_SUFFIX), TOKEN_SUFFIX) == 0) {
        token_len -= strlen(TOKEN_SUFFIX);
    }

    // Base64 decode
    size_t bin_maxlen = token_len;  // base64 decodes to smaller
    unsigned char *ciphertext = malloc(bin_maxlen);
    size_t bin_len;

    if (sodium_base642bin(ciphertext, bin_maxlen, start, token_len,
                          NULL, &bin_len, NULL,
                          sodium_base64_VARIANT_URLSAFE_NO_PADDING) != 0) {
        free(ciphertext);
        return NULL;
    }

    if (bin_len < NONCE_SIZE + TAG_SIZE) {
        free(ciphertext);
        return NULL;
    }

    // Decrypt
    size_t pt_maxlen = bin_len - NONCE_SIZE - TAG_SIZE;
    unsigned char *plaintext = malloc(pt_maxlen + 1);
    unsigned long long pt_len;

    if (crypto_aead_xchacha20poly1305_ietf_decrypt(
            plaintext, &pt_len,
            NULL,
            ciphertext + NONCE_SIZE, bin_len - NONCE_SIZE,
            NULL, 0,
            ciphertext,  // nonce
            master_key) != 0) {
        free(ciphertext);
        free(plaintext);
        return NULL;
    }

    plaintext[pt_len] = '\0';
    free(ciphertext);

    return (char*)plaintext;
}

// Python-callable wrapper functions (for ctypes/cffi)
// These use simple C strings for easy FFI

__attribute__((visibility("default")))
int privacy_guardian_init(const char *key_path) {
    return pg_init(key_path);
}

__attribute__((visibility("default")))
char* privacy_guardian_encrypt(const char *plaintext, const char *pii_type) {
    return pg_encrypt_pii(plaintext, pii_type);
}

__attribute__((visibility("default")))
char* privacy_guardian_decrypt(const char *token) {
    return pg_decrypt_token(token);
}

__attribute__((visibility("default")))
void privacy_guardian_free(char *ptr) {
    free(ptr);
}

// Test main
#ifdef PG_TEST_MAIN
int main() {
    if (pg_init("./pg_master.key") != 0) {
        printf("Init failed\n");
        return 1;
    }

    const char *test_data[] = {
        "john.doe@example.com",
        "555-123-4567",
        "4532-1234-5678-9012",
        "123-45-6789",
        "sk-ant-api03-xxxxxxxxxxxxx"
    };
    const char *test_types[] = {
        "EMAIL", "PHONE", "CREDIT_CARD", "SSN", "API_KEY"
    };

    printf("PrivacyGuardian Crypto Test\n");
    printf("===========================\n\n");

    for (int i = 0; i < 5; i++) {
        char *token = pg_encrypt_pii(test_data[i], test_types[i]);
        printf("Original [%s]: %s\n", test_types[i], test_data[i]);
        printf("Token: %s\n", token);

        char *decrypted = pg_decrypt_token(token);
        printf("Decrypted: %s\n\n", decrypted);

        free(token);
        free(decrypted);
    }

    return 0;
}
#endif
