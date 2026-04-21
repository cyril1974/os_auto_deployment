#!/bin/bash
# =====================================
# install_intel_e810.sh
# Detect and install Intel E810 (ICE) driver
# =====================================

PCI_IDS=("8086:1593" "8086:159B" "8086:159D")
DRIVER_TAR="/opt/firstboot/ice-2.4.5.tar.gz"
DRIVER_DIR="/opt/firstboot/ice-2.4.5"

NIC_FOUND=0
for id in "${PCI_IDS[@]}"; do
    if lspci -nn | grep -iq "$id"; then
        echo "[✔] Intel E810 NIC detected ($id)"
        NIC_FOUND=1
        break
    fi
done

if [ $NIC_FOUND -eq 0 ]; then
    echo "[✖] Intel E810 NIC not found (${PCI_IDS[*]})"
    exit 0
fi

# Extract driver
if [ -f "$DRIVER_TAR" ]; then
    mkdir -p "$DRIVER_DIR"
    tar -xzf "$DRIVER_TAR" -C "$DRIVER_DIR" --strip-components=1
    echo "Driver extracted to $DRIVER_DIR"
else
    echo "[✖] Driver tarball not found: $DRIVER_TAR"
    exit 1
fi

# Install driver
if [ -d "$DRIVER_DIR/src" ]; then
    cd "$DRIVER_DIR/src" || exit
    make -j$(nproc)
    make install -j$(nproc)
    cd - >/dev/null
    echo "[✔] Intel E810 driver installed successfully"
else
    echo "[✖] ICE src directory not found"
    exit 1
fi
