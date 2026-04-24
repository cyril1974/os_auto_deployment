#!/bin/bash
# =====================================
# install_broadcom.sh
# Detect and install Broadcom N2200G/P1400G driver
# =====================================

PCI_ID="14e4:1760"
DRIVER_TAR="/opt/firstboot/bcm_236.1.155.0c.tar.gz"
DRIVER_DIR="/opt/firstboot/bcm_236.1.155.0c"

# Detect NIC
if lspci -nn | grep -iq "$PCI_ID"; then
    echo "[✔] Broadcom NIC detected ($PCI_ID)"
else
    echo "[✖] Broadcom NIC not found ($PCI_ID)"
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
INSTALL_SCRIPT="$DRIVER_DIR/utils/nic_wizard/nic_wizard"
if [ -f "$INSTALL_SCRIPT" ]; then
    cd "$(dirname "$INSTALL_SCRIPT")" || exit
    ./nic_wizard installer install -v -f -g -N
    echo "blacklist bnxt_en" | tee /etc/modprobe.d/blacklist-bnxt.conf
    update-initramfs -c -k $(uname -r)
    cd - >/dev/null
    echo "[✔] Broadcom driver installed successfully"
else
    echo "[✖] Broadcom install script not found"
    exit 1
fi
