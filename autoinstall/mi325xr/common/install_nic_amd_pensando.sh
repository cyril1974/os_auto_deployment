#!/bin/bash
# =====================================
# install_amd_pensando.sh
# Detect and install AMD Pensando DSC driver
# =====================================

PCI_ID="1dd8:1002"
DRIVER_BUNDLE_NAME="ainic_bundle_1.117.5-a-38.tar.gz"
HOST_PKG_NAME="host_sw_pkg.tar.gz"
BASE_DIR="/opt/firstboot"
EXTRACTED_DIR="ainic_bundle_1.117.5-a-38"
HOST_SW_DIR="host_sw_pkg"
DRIVER_SW_DIR="ionic_driver/src"
DRIVER_PKG_NAME="drivers-linux.tar.xz"
PERFTEST_SW_DIR="drivers-linux/perftest"

# Detect NIC
if lspci -nn | grep -iq "$PCI_ID"; then
    echo "[✔] AMD Pensando NIC detected ($PCI_ID)"
else
    echo "[✖] AMD Pensando NIC not found ($PCI_ID)"
    exit 0
fi

# Check bundle file
if [ ! -f "$BASE_DIR/$DRIVER_BUNDLE_NAME" ]; then
    echo "[✖] Bundle tarball not found: $BASE_DIR/$DRIVER_BUNDLE_NAME"
    exit 1
fi

# Create working directory
mkdir -p "$BASE_DIR"

echo "[*] Extracting main bundle..."
tar -xzf "$BASE_DIR/$DRIVER_BUNDLE_NAME" -C "$BASE_DIR"

if [ $? -ne 0 ]; then
    echo "[✖] Failed to extract main bundle"
    exit 1
fi

# Check extracted directory
if [ ! -d "$BASE_DIR/$EXTRACTED_DIR" ]; then
    echo "[✖] Expected directory not found: $BASE_DIR/$EXTRACTED_DIR"
    exit 1
fi

echo "[✔] Main bundle extracted"

# Extract host_sw_pkg.tar.gz
HOST_PKG_PATH="$BASE_DIR/$EXTRACTED_DIR/$HOST_PKG_NAME"

if [ ! -f "$HOST_PKG_PATH" ]; then
    echo "[✖] host_sw_pkg.tar.gz not found in bundle"
    exit 1
fi

echo "[*] Extracting host_sw_pkg.tar.gz..."
tar -xzf "$HOST_PKG_PATH" -C "$BASE_DIR/$EXTRACTED_DIR"

if [ $? -ne 0 ]; then
    echo "[✖] Failed to extract host_sw_pkg.tar.gz"
    exit 1
fi

echo "[✔] host_sw_pkg extracted successfully"

# Install driver (placeholder)
echo "Installing AMD Pensando driver..."
cd "$BASE_DIR/$EXTRACTED_DIR/$HOST_SW_DIR"
bash install.sh -y

# Build perftest utility
echo "Building AMD Perftest utility..."
DRIVER_PKG_PATH="$BASE_DIR/$EXTRACTED_DIR/$HOST_SW_DIR/$DRIVER_SW_DIR/$DRIVER_PKG_NAME"
tar -xvf "$DRIVER_PKG_PATH" -C "$BASE_DIR/$EXTRACTED_DIR/$HOST_SW_DIR/$DRIVER_SW_DIR"
cd "$BASE_DIR/$EXTRACTED_DIR/$HOST_SW_DIR/$DRIVER_SW_DIR/$PERFTEST_SW_DIR"
bash autogen.sh
bash configure --prefix=`pwd` --enable-rocm --with-rocm=/opt/rocm
make
make install

echo "[✔] AMD Pensando driver installation step completed (replace with real commands)"
