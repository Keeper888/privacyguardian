# PrivacyGuardian Makefile

CC = gcc
CFLAGS = -O3 -fPIC -Wall -Wextra
LDFLAGS = -shared
LIBS = -lsodium

SRC_DIR = src
BUILD_DIR = build

.PHONY: all clean install deps test

all: $(BUILD_DIR)/libpgcrypto.so

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/libpgcrypto.so: $(SRC_DIR)/crypto_core.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $< $(LIBS)

# Build test binary
test-crypto: $(SRC_DIR)/crypto_core.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -DPG_TEST_MAIN -o $(BUILD_DIR)/test_crypto $< $(LIBS)
	./$(BUILD_DIR)/test_crypto

# Install system dependencies
deps:
	@echo "Installing system dependencies..."
	sudo apt-get update
	sudo apt-get install -y libsodium-dev python3-pip python3-venv
	@echo "Creating Python virtual environment..."
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

# Quick install (assumes deps are met)
install:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

# Test PII detector
test-pii:
	python3 $(SRC_DIR)/pii_detector.py

# Run the proxy
run:
	./venv/bin/python $(SRC_DIR)/guardian_proxy.py

clean:
	rm -rf $(BUILD_DIR) venv __pycache__ code/__pycache__
	rm -rf ~/.privacyguardian/vault.db
