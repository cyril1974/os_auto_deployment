#!/usr/bin/env bash
set -euo pipefail

# Help function
show_help() {
    cat << EOF
Ubuntu Autoinstall ISO Builder
===============================

USAGE:
    $0 <ISO_PATH> [USERNAME] [PASSWORD]

PARAMETERS:
    ISO_PATH    Path to the original Ubuntu Server ISO file (required)
    USERNAME    Username for the installed system (default: admin)
    PASSWORD    Password for both user and root (default: ubuntu)

DESCRIPTION:
    This script creates a custom Ubuntu autoinstall ISO that will automatically
    install Ubuntu Server with the specified user credentials and configuration.

    The output ISO will be created in ./output_custom_iso/ with the filename
    based on the input ISO name with dashes replaced by underscores and
    '_autoinstall' suffix added.

FEATURES:
    - GPT partition table for UEFI boot compatibility
    - Automatic installation with no user interaction
    - SSH server enabled with password authentication
    - Root login enabled
    - Sudo access configured for the user
    - Optional package installation (vim, curl, net-tools, ipmitool, htop)

EXAMPLES:
    # Basic usage with defaults (user: admin, password: ubuntu)
    $0 ubuntu-22.04.2-live-server-amd64.iso

    # Specify custom username and password
    $0 ubuntu-22.04.2-live-server-amd64.iso myuser mypassword

    # Using full path to ISO
    $0 /path/to/ubuntu-22.04.2-live-server-amd64.iso sysadmin SecurePass123

OUTPUT:
    - ISO file: ./output_custom_iso/ubuntu_22.04.2_live_server_amd64_autoinstall.iso
    - SSH private key: ~/.ssh/id_ed25519_<timestamp>_<random>
    - SSH public key: ~/.ssh/id_ed25519_<timestamp>_<random>.pub

REQUIREMENTS:
    - Root privileges (uses apt to install packages)
    - Packages: whois, genisoimage, xorriso, isolinux, mtools

EOF
    exit 0
}

# Check for help flag
if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]] || [[ $# -eq 0 ]]; then
    show_help
fi


ORIG_ISO="${1:-/iso/ubuntu-22.04.5-live-server-amd64.iso}"
# WORKDIR="${2:-/tmp/ubuntuiso}"
WORKDIR="./workdir_custom_iso"
# OUT_ISO="${3:-/iso/ubuntu-22.04.5-autoinstall.iso}"
OUT_ISO_DIR="./output_custom_iso"
# Extract base filename and create autoinstall version with underscores
ISO_BASENAME=$(basename "$ORIG_ISO" .iso)
ISO_AUTOINSTALL="${ISO_BASENAME//-/_}_autoinstall.iso"
OUT_ISO="${OUT_ISO_DIR}/${ISO_AUTOINSTALL}"
USERNAME="${2:-admin}"
PASSWORD="${3:-ubuntu}"

echo "[*] Clean Work directory and Output Folder"
rm -rf ${WORKDIR}
rm -rf ${OUT_ISO_DIR}

echo "[*] Install Necessary Package ..."
apt update
apt -y install whois genisoimage xorriso isolinux mtools
if [ ! -f "$ORIG_ISO" ]; then
  echo "Original ISO not found: $ORIG_ISO" >&2
  exit 1
fi

echo "[*] Preparing work directories..."
mkdir -p "$WORKDIR" /mnt/ubuntuiso

echo "[*] Mounting original ISO..."
# umount /mnt/ubuntuiso
mount -o loop "$ORIG_ISO" /mnt/ubuntuiso

echo "[*] Copying ISO contents..."
rsync -a /mnt/ubuntuiso/ "$WORKDIR/"
umount /mnt/ubuntuiso

echo "[*] Adding autoinstall cloud-init data..."
mkdir -p "$WORKDIR/autoinstall"

cat > "$WORKDIR/autoinstall/meta-data" << 'EOF'
instance-id: ubuntu-autoinstall-001
local-hostname: ubuntu-auto
EOF

# Hash password for user-data
HASH_PASSWORD=$(mkpasswd -m sha-512 ${PASSWORD})
echo "[*] Hashed Password is ${HASH_PASSWORD}"

# Generate SSH KEY
RANDOM="133244577"
KEY_NAME="id_ed25519_$(date +%Y%m%d_%H%M%S)_$RANDOM"
ssh-keygen -t ed25519 -f ~/.ssh/${KEY_NAME} -C "admin@ubuntu-autoinstall" -N ""
PUB_KEY=$(cat ~/.ssh/${KEY_NAME}.pub)


cat > "$WORKDIR/autoinstall/user-data" << EOF
#cloud-config
autoinstall:
  version: 1
  identity:
    hostname: ubuntu-auto
    username: ${USERNAME}
    password: "${HASH_PASSWORD}"
  locale: en_US.UTF-8
  keyboard:
    layout: us
  ssh:
    install-server: true
    authorized-keys:
      - ${PUB_KEY}
    allow-pw: true
  late-commands:
    - echo 'root:${PASSWORD}' | chroot /target chpasswd
    - curtin in-target --target=/target -- sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
    - curtin in-target --target=/target -- sed -i 's/^#\\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
    - echo '${USERNAME} ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/${USERNAME}
    - chmod 440 /target/etc/sudoers.d/${USERNAME}
    - curtin in-target --target=/target -- apt-get update
    - curtin in-target --target=/target -- apt-get install -y vim curl net-tools ipmitool htop || true
EOF

export GRUB_CFG="$WORKDIR/boot/grub/grub.cfg"
echo "[*] GRUB Config Location :${GRUB_CFG}"
if [ ! -f "$GRUB_CFG" ]; then
  echo "Error: grub.cfg not found at $GRUB_CFG" >&2
  exit 1
fi

echo "[*] Patching GRUB configuration for autoinstall..."

# Backup original grub
cp "$GRUB_CFG" "${GRUB_CFG}.orig"

# This is a simple replace: you may want to fine-tune it for different ISO versions.
# Here we:
# 1. force timeout=0
# 2. change the main menuentry to have autoinstall args

# Ensure default & timeout
sed -i 's/^set timeout=.*/set timeout=0/' "$GRUB_CFG" || true
grep -q 'set default=' "$GRUB_CFG" || echo 'set default="0"' >> "$GRUB_CFG"

# Replace the "Try or Install Ubuntu Server" entry with autoinstall version
# This is a very targeted approach; adjust the pattern if Canonical changes the text.
python3 - <<PYEOF
import re, pathlib

path = pathlib.Path("$GRUB_CFG")
txt = path.read_text()

pattern = r'(menuentry "Try or Install Ubuntu Server" {[^}]+linux\s+/casper/vmlinuz)([^\n]*)(\n\s*initrd\s+/casper/initrd[^\n]*\n\s*})'
repl = r'''menuentry "Auto Install Ubuntu Server" {
    set gfxpayload=keep
    search --no-floppy --set=root --file /casper/vmlinuz
    linux   /casper/vmlinuz autoinstall ds=nocloud\\;s=/cdrom/autoinstall/ --- quiet
    initrd  /casper/initrd
}'''
new_txt, n = re.subn(pattern, repl, txt, flags=re.MULTILINE)

if n == 0:
    print("WARNING: Did not find expected menuentry; grub.cfg not modified.", flush=True)
else:
    print(f"Patched {n} menuentry block(s).", flush=True)

# Remove standalone grub_platform command that causes error
new_txt = re.sub(r'^\s*grub_platform\s*$', '', new_txt, flags=re.MULTILINE)

path.write_text(new_txt)
PYEOF

echo "[*] Rebuilding ISO..."

# Find the volume ID from original ISO (optional; can hardcode)
VOLID=$(isoinfo -d -i "$ORIG_ISO" | awk -F': ' '/Volume id:/ {print $2}')
VOLID=${VOLID:-UBUNTU_AUTOINSTALL}

# Extract MBR from original ISO for hybrid boot compatibility
echo "[*] Extracting MBR from original ISO..."
MBR_FILE="/tmp/isohdpfx.bin"
dd if="$ORIG_ISO" bs=1 count=432 of="$MBR_FILE" 2>/dev/null

# Try to use system isolinux MBR if available, otherwise use extracted one
if [ -f "/usr/lib/ISOLINUX/isohdpfx.bin" ]; then
  MBR_FILE="/usr/lib/ISOLINUX/isohdpfx.bin"
elif [ -f "/usr/lib/syslinux/isohdpfx.bin" ]; then
  MBR_FILE="/usr/lib/syslinux/isohdpfx.bin"
fi
echo "[*] Using MBR file: $MBR_FILE"

echo "[*] Creating EFI boot image..."
# Create EFI boot image for GPT partition with GRUB modules and config
EFI_IMG="/tmp/efi.img"
( cd "$WORKDIR" && \
  dd if=/dev/zero of="$EFI_IMG" bs=1M count=20 2>/dev/null && \
  mkfs.vfat "$EFI_IMG" >/dev/null 2>&1 && \
  mmd -i "$EFI_IMG" ::/EFI ::/EFI/boot ::/boot ::/boot/grub && \
  mcopy -i "$EFI_IMG" EFI/boot/bootx64.efi ::/EFI/boot/ && \
  mcopy -i "$EFI_IMG" EFI/boot/grubx64.efi ::/EFI/boot/ && \
  mcopy -i "$EFI_IMG" EFI/boot/mmx64.efi ::/EFI/boot/ && \
  mcopy -i "$EFI_IMG" boot/grub/grub.cfg ::/boot/grub/ && \
  mcopy -s -i "$EFI_IMG" boot/grub/x86_64-efi ::/boot/grub/ && \
  mcopy -s -i "$EFI_IMG" boot/grub/fonts ::/boot/grub/ 2>/dev/null
)
echo "[*] EFI boot image created: $EFI_IMG"

echo "[*] Modification is ok"
echo "[*] Generate customize ISO"

(
  cd "$WORKDIR"

  xorriso -as mkisofs \
    -r \
    -V "$VOLID" \
    -J -l \
    -b boot/grub/i386-pc/eltorito.img \
    -c boot.catalog \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    -eltorito-alt-boot \
    -e --interval:appended_partition_2:all:: \
    -no-emul-boot \
    -append_partition 2 0xEF "$EFI_IMG" \
    --grub2-mbr "$MBR_FILE" \
    -partition_offset 16 \
    -appended_part_as_gpt \
    -iso_mbr_part_type a2a0d0ebe5b9334487c068b6b72699c7 \
    -o "../$OUT_ISO" .
)

echo "[*] Done. Autoinstall ISO created at: $OUT_ISO"
# sed -n '1,80p' "$WORKDIR/autoinstall/user-data"
# sed -n '1,40p' "$WORKDIR/boot/grub/grub.cfg"
