#!/bin/bash
set -e

echo "[*] Running pre-build tests..."
go test ./... -v || { echo "[!] Tests failed — aborting build"; exit 1; }
echo "[+] Tests passed"

echo "[*] Building binary..."
go build -o build-iso .
echo "[+] Build complete: build-iso"
