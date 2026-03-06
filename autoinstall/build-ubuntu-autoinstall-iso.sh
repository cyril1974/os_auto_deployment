#!/usr/bin/env bash
set -euo pipefail

# Help function
show_help() {
    cat << EOF
Ubuntu Autoinstall ISO Builder
===============================

USAGE:
    $0 <OS_NAME> [USERNAME] [PASSWORD]

PARAMETERS:
    OS_NAME     OS name to look up in file_list.json (required)
                Example: ubuntu-22.04.2-live-server-amd64
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
    $0 ubuntu-22.04.2-live-server-amd64

    # Specify custom username and password
    $0 ubuntu-22.04.2-live-server-amd64 myuser mypassword

    # Using different Ubuntu version
    $0 ubuntu-24.04.1-live-server-amd64 sysadmin SecurePass123

OUTPUT:
    - ISO file: ./output_custom_iso/ubuntu_22.04.2_live_server_amd64_autoinstall.iso
    - SSH private key: ~/.ssh/id_ed25519_<timestamp>_<random>
    - SSH public key: ~/.ssh/id_ed25519_<timestamp>_<random>.pub

REQUIREMENTS:
    - Root privileges (uses apt to install packages)
    - Packages: whois, genisoimage, xorriso, isolinux, mtools, jq
    - file_list.json in iso_repository/ directory

EOF
    exit 0
}

# Check for help flag or skip-install flag
SKIP_INSTALL=false
for arg in "$@"; do
    if [[ "$arg" == "--skip-install" ]]; then
        SKIP_INSTALL=true
        break
    fi
done

if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]] || [[ $# -eq 0 ]]; then
    show_help
fi


# Function to lookup ISO path from file_list.json
lookup_iso_path() {
    local os_name="$1"
    local json_file="./iso_repository/file_list.json"
    
    if [ ! -f "$json_file" ]; then
        echo "Error: file_list.json not found at $json_file" >&2
        exit 1
    fi
    
    # Use jq to find the OS_Path for the given OS_Name
    local iso_path=$(jq -r ".tree.Ubuntu[] | select(.OS_Name == \"$os_name\") | .OS_Path" "$json_file")
    
    if [ -z "$iso_path" ] || [ "$iso_path" == "null" ]; then
        echo "Error: OS name '$os_name' not found in file_list.json" >&2
        echo "Available OS names:" >&2
        jq -r '.tree.Ubuntu[].OS_Name' "$json_file" >&2
        exit 1
    fi
    
    # Prepend iso_repository/ to the path
    echo "./iso_repository/$iso_path"
}

# Check and install necessary packages only if missing
check_and_install_packages() {
    local missing_packages=()
    local required_packages=("whois" "genisoimage" "xorriso" "isolinux" "mtools" "jq")
    
    for pkg in "${required_packages[@]}"; do
        if ! command -v "$pkg" &> /dev/null && ! dpkg -l | grep -q "^ii  $pkg"; then
            missing_packages+=("$pkg")
        fi
    done
    
    if [ ${#missing_packages[@]} -gt 0 ]; then
        echo "[*] Installing missing packages: ${missing_packages[*]}"
        # Update package lists, ignoring repository errors (exit code 100)
        echo "[*] Running apt update (ignoring repository errors)..."
        sudo apt update 2>&1 | grep -v "does not have a stable CLI interface" || true
        # Install packages even if apt update had some errors
        echo "[*] Installing packages..."
        sudo apt -y install "${missing_packages[@]}" || echo "[!] Warning: apt install had errors, but continuing..."
    else
        echo "[*] All required packages are already installed"
    fi
}

# Detect Ubuntu codename from OS_NAME for downloading correct packages
# Maps version numbers to their Ubuntu codenames (archive repository names)
get_ubuntu_codename() {
    local os_name="$1"
    if [[ "$os_name" == *"25.04"* ]]; then
        echo "plucky"
    elif [[ "$os_name" == *"24.10"* ]]; then
        echo "oracular"
    elif [[ "$os_name" == *"24.04"* ]]; then
        echo "noble"
    elif [[ "$os_name" == *"23.10"* ]]; then
        echo "mantic"
    elif [[ "$os_name" == *"23.04"* ]]; then
        echo "lunar"
    elif [[ "$os_name" == *"22.10"* ]]; then
        echo "kinetic"
    elif [[ "$os_name" == *"22.04"* ]]; then
        echo "jammy"
    elif [[ "$os_name" == *"20.04"* ]]; then
        echo "focal"
    elif [[ "$os_name" == *"18.04"* ]]; then
        echo "bionic"
    else
        # Default to jammy if version cannot be determined
        echo "jammy"
    fi
}

# Download ipmitool and its dependencies for the target Ubuntu version.
# Packages are downloaded from the correct Ubuntu archive matching the target ISO's
# distribution, avoiding cross-version dependency issues.
# The .deb files are saved into the ISO work directory under /pool/extra/.
download_ipmitool_packages() {
    local workdir="$1"
    local codename="$2"
    local extra_pool="$workdir/pool/extra"
    local tmp_download
    tmp_download="$(mktemp -d)"

    echo "[*] Downloading ipmitool packages for Ubuntu ${codename}..."
    mkdir -p "$extra_pool"

    # ipmitool dependencies vary between Ubuntu versions due to ABI transitions:
    #   - Ubuntu 20.04 (focal): libsnmp35, libopenipmi0
    #   - Ubuntu 22.04 (jammy): libsnmp40, libopenipmi0
    #   - Ubuntu 24.04 (noble): libsnmp40t64, libopenipmi0t64, libfreeipmi17t64
    #
    # IMPORTANT: The build machine may run a different Ubuntu version than the target.
    # We must fully isolate apt from the host's dpkg status database, otherwise
    # apt will try to download the HOST's package versions from the TARGET's repo.
    # (e.g., trying to find plucky's ipmitool 1.8.19 in the jammy repo → fails)

    # Create a fully isolated temporary apt environment
    local apt_conf_dir
    apt_conf_dir="$(mktemp -d)"
    local apt_sources="$apt_conf_dir/sources.list"
    local apt_cache="$apt_conf_dir/cache"
    local apt_state="$apt_conf_dir/state"
    local apt_etc="$apt_conf_dir/etc"

    mkdir -p "$apt_cache/archives/partial" "$apt_state/lists/partial" "$apt_etc/apt.conf.d" "$apt_etc/preferences.d" "$apt_etc/trusted.gpg.d"

    # Create EMPTY dpkg status file — this is critical!
    # Without this, apt reads the HOST's /var/lib/dpkg/status and resolves
    # packages based on the host's installed versions, not the target's.
    touch "$apt_state/status"

    # Copy trusted GPG keys from the host system
    if [ -d /etc/apt/trusted.gpg.d ]; then
        cp /etc/apt/trusted.gpg.d/*.gpg "$apt_etc/trusted.gpg.d/" 2>/dev/null || true
    fi
    if [ -f /etc/apt/trusted.gpg ]; then
        cp /etc/apt/trusted.gpg "$apt_etc/" 2>/dev/null || true
    fi

    # Common apt options to fully isolate from host system
    local APT_OPTS=(
        -o Dir::Etc::sourcelist="$apt_sources"
        -o Dir::Etc::sourceparts="/dev/null"
        -o Dir::Cache="$apt_cache"
        -o Dir::State="$apt_state"
        -o Dir::State::status="$apt_state/status"
        -o Dir::Etc="$apt_etc"
    )

    # Set up sources for the target version (main + universe where ipmitool lives)
    cat > "$apt_sources" << APTEOF
deb [trusted=yes] http://archive.ubuntu.com/ubuntu ${codename} main universe
deb [trusted=yes] http://archive.ubuntu.com/ubuntu ${codename}-updates main universe
APTEOF

    # Download packages using the target version's repository
    echo "[*] Fetching package index for ${codename}..."
    if apt-get "${APT_OPTS[@]}" update 2>&1 | tail -3; then

        echo "[*] Downloading ipmitool and dependencies..."
        cd "$tmp_download"

        # Use -t to force resolution from the target codename's release
        apt-get "${APT_OPTS[@]}" -t "${codename}" download ipmitool 2>&1 || true

        # Resolve the actual dependency names for this target version
        local deps
        deps=$(apt-cache "${APT_OPTS[@]}" depends ipmitool 2>/dev/null \
               | grep -E '^\s*(Depends|PreDepends):' \
               | sed 's/.*: //' | tr -d ' ' | sort -u || true)

        if [ -n "$deps" ]; then
            echo "[*] Resolved dependencies for ${codename}: $deps"
            for dep in $deps; do
                # Skip virtual packages and packages already in the live installer base system
                case "$dep" in
                    libc6|libgcc*|debconf*|dpkg|bash|coreutils|install-info) continue ;;
                esac
                apt-get "${APT_OPTS[@]}" -t "${codename}" download "$dep" 2>/dev/null || true
            done
        fi
        cd - > /dev/null

        # Move all downloaded .deb files to the ISO pool
        local deb_count
        deb_count=$(find "$tmp_download" -name '*.deb' | wc -l)
        if [ "$deb_count" -gt 0 ]; then
            mv "$tmp_download"/*.deb "$extra_pool/"
            echo "[*] Bundled $deb_count ipmitool package(s) into ISO ($extra_pool/):"
            ls -la "$extra_pool/"*.deb | awk '{print "    " $NF " (" $5 " bytes)"}'
        else
            echo "[!] WARNING: Failed to download ipmitool packages for ${codename}"
            echo "[!] The early-commands ipmitool SEL write will not work."
        fi
    else
        echo "[!] WARNING: Failed to fetch package index for ${codename}"
        echo "[!] The early-commands ipmitool SEL write will not work."
    fi

    # Cleanup temporary directories
    rm -rf "$tmp_download" "$apt_conf_dir"
}

# Install packages if needed (requires root) and not skipped
if [ "$SKIP_INSTALL" = false ]; then
    if [ "$EUID" -eq 0 ]; then
        check_and_install_packages
    else
        echo "[*] Skipping package installation (not running as root)"
        echo "[*] Required packages: whois, genisoimage, xorriso, isolinux, mtools, jq"
    fi
else
    echo "[*] Skipping package installation (--skip-install flag set)"
fi


# Get OS name from first argument
OS_NAME="${1:-ubuntu-22.04.5-live-server-amd64}"
USERNAME="${2:-autoinstall}"
PASSWORD="${3:-ubuntu}"

# Detect if it's Ubuntu 18.04
IS_1804=false
if [[ "$OS_NAME" == *"18.04"* ]]; then
    IS_1804=true
    echo "[*] Detected Ubuntu 18.04 - Using Preseed automation"
else
    echo "[*] Detected Ubuntu 20.04+ - Using Autoinstall automation"
fi

# Lookup the actual ISO path
echo "[*] Looking up ISO path for OS: $OS_NAME"
ORIG_ISO=$(lookup_iso_path "$OS_NAME")
echo "[*] Found ISO: $ORIG_ISO"

WORKDIR="./workdir_custom_iso"
echo "[*] Cleaning work directory..."
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"
OUT_ISO_DIR="./output_custom_iso"
# Extract base filename and create autoinstall version with underscores
ISO_BASENAME=$(basename "$ORIG_ISO" .iso)
TIMESTAMP=$(date +%Y%m%d%H%M)
ISO_AUTOINSTALL="${ISO_BASENAME//-/_}_autoinstall_${TIMESTAMP}.iso"
OUT_ISO="${OUT_ISO_DIR}/${ISO_AUTOINSTALL}"

echo "[*] Clean Work directory and Output Folder"
rm -rf ${WORKDIR}
rm -rf ${OUT_ISO_DIR}
mkdir -p ${OUT_ISO_DIR}


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

# Download and bundle ipmitool packages for the target Ubuntu version (20.04+ only)
# Ubuntu 18.04 uses preseed which installs packages during normal apt phase
if [ "$IS_1804" != true ]; then
    UBUNTU_CODENAME=$(get_ubuntu_codename "$OS_NAME")
    echo "[*] Target Ubuntu codename: $UBUNTU_CODENAME"
    download_ipmitool_packages "$WORKDIR" "$UBUNTU_CODENAME"
fi

# Hash password for user-data
HASH_PASSWORD=$(mkpasswd -m sha-512 ${PASSWORD})
echo "[*] Hashed Password is ${HASH_PASSWORD}"

# Generate SSH KEY
RANDOM="133244577"
KEY_NAME="id_ed25519_$(date +%Y%m%d_%H%M%S)_$RANDOM"
ssh-keygen -t ed25519 -f ~/.ssh/${KEY_NAME} -C "admin@ubuntu-autoinstall" -N ""
PUB_KEY=$(cat ~/.ssh/${KEY_NAME}.pub)

echo "[*] Adding autoinstall cloud-init data..."
mkdir -p "$WORKDIR/autoinstall"

cat > "$WORKDIR/autoinstall/meta-data" << 'EOF'
instance-id: ubuntu-autoinstall-001
local-hostname: ubuntu-auto
EOF

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
  storage:
    layout:
      name: direct
  ssh:
    install-server: true
    authorized-keys:
      - ${PUB_KEY}
    allow-pw: true
  updates: security
  apt:
    fallback: offline-install
    geoip: false
  early-commands:
    # Load IPMI kernel modules for BMC communication
    - modprobe ipmi_devintf 2>/dev/null || true
    - modprobe ipmi_si 2>/dev/null || true
    - modprobe ipmi_msghandler 2>/dev/null || true
    - sleep 2
    # Install ipmitool from pre-bundled .deb files on ISO (no network needed)
    # Packages are version-matched for the target Ubuntu release during ISO build.
    - dpkg -i /cdrom/pool/extra/*.deb 2>/dev/null || true
    # Write SEL entry - OS Installation Starting
    # Uses Platform Event Message (NetFn=Sensor/Event 0x04, Cmd=0x02)
    # instead of Add SEL Entry (0x0a 0x44) to avoid duplicate SEL records.
    # Format: EvMRev(0x04) SensorType(0x1F) SensorNum(0x01) EventType(0x6f) EvData1 EvData2 EvData3
    # Event Data 0x01 = Installation starting marker
    - ipmitool raw 0x04 0x02 0x04 0x1F 0x01 0x6f 0x01 0xff 0xff 2>/dev/null || true
  late-commands:
    - echo 'root:${PASSWORD}' | chroot /target chpasswd
    - curtin in-target --target=/target -- sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
    - curtin in-target --target=/target -- sed -i 's/^#\\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
    - echo '${USERNAME} ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/${USERNAME}
    - chmod 440 /target/etc/sudoers.d/${USERNAME}
    # Ensure DNS resolution is available in the target chroot
    - cp /etc/resolv.conf /target/etc/resolv.conf
    # Use sh -c wrapper so || true is properly handled inside curtin in-target
    - curtin in-target --target=/target -- sh -c 'apt-get update || true'
    - curtin in-target --target=/target -- sh -c 'apt-get install -y vim curl net-tools ipmitool htop || true'
    # Write SEL entry - OS Installation Completed (Event Data 0x02)
    # Uses Platform Event Message to produce a single SEL entry per write
    - chroot /target ipmitool raw 0x04 0x02 0x04 0x1F 0x01 0x6f 0x02 0xff 0xff 2>/dev/null || true
EOF

if [ "$IS_1804" = true ]; then
  echo "[*] Adding Preseed configuration for Ubuntu 18.04 compatibility..."
  # Generate preseed.cfg (as a fallback or for legacy installer if present)
  cat > "$WORKDIR/preseed.cfg" << EOF
# Locale/Keyboard
d-i debian-installer/locale string en_US.UTF-8
d-i console-setup/ask_detect boolean false
d-i keyboard-configuration/xkb-keymap select us

# Network
d-i netcfg/choose_interface select auto
d-i netcfg/get_hostname string ubuntu-auto
d-i netcfg/get_domain string unassigned-domain

# Clock
d-i clock-setup/utc boolean true
d-i time/zone string UTC

# Partitioning (Atomic)
d-i partman-auto/method string regular
d-i partman-lvm/device_remove_lvm boolean true
d-i partman-md/device_remove_md boolean true
d-i partman-lvm/confirm boolean true
d-i partman-lvm/confirm_nooverwrite boolean true
d-i partman-auto/choose_recipe select atomic
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/choose_partition select finish
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true

# User/Root Setup
d-i passwd/user-fullname string ${USERNAME}
d-i passwd/username string ${USERNAME}
d-i passwd/user-password-password password ${PASSWORD}
d-i passwd/user-password-again password ${PASSWORD}
d-i user-setup/allow-password-weak boolean true
d-i user-setup/encrypt-home boolean false

# Repository
d-i apt-setup/use_mirror boolean false
d-i apt-setup/cdrom/set-first boolean false
d-i apt-setup/cdrom/set-next boolean false
d-i apt-setup/cdrom/set-failed boolean false
d-i apt-setup/restricted boolean true
d-i apt-setup/universe boolean true

# Packages
tasksel tasksel/first multiselect standard, server
d-i pkgsel/include string ssh openssh-server vim curl net-tools ipmitool htop
d-i pkgsel/upgrade select none
d-i pkgsel/update-policy select none

# Bootloader
d-i grub-installer/only_debian boolean true
d-i grub-installer/with_other_os boolean true

# Late commands (SSH config and Sudoers)
d-i preseed/late_command string \\
    in-target sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config; \\
    in-target sed -i 's/^#\\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config; \\
    echo '${USERNAME} ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/${USERNAME}; \\
    chmod 440 /target/etc/sudoers.d/${USERNAME}; \\
    echo "root:${PASSWORD}" | in-target chpasswd

# Finish
d-i finish-install/reboot_in_progress note
EOF
fi

export GRUB_CFG="$WORKDIR/boot/grub/grub.cfg"
echo "[*] GRUB Config Location :${GRUB_CFG}"
if [ ! -f "$GRUB_CFG" ]; then
  echo "Error: grub.cfg not found at $GRUB_CFG" >&2
  exit 1
fi

echo "[*] Patching GRUB configuration..."

# Backup original grub
cp "$GRUB_CFG" "${GRUB_CFG}.orig"

# This is a simple replace: you may want to fine-tune it for different ISO versions.
# Here we:
# 1. force timeout=0
# 2. change the main menuentry to have autoinstall args

# Ensure default & timeout
sed -i 's/^set timeout=.*/set timeout=5/' "$GRUB_CFG" || true
grep -q 'set default=' "$GRUB_CFG" || echo 'set default="0"' >> "$GRUB_CFG"

# Parameters for the linux line
if [ "$IS_1804" = true ]; then
  # For 18.04 Legacy ISO, use standard preseed parameters
  BOOT_PARAMS='file=/cdrom/preseed.cfg auto=true priority=critical console=ttyS0,115200n8 console=tty0 ---'
else
  BOOT_PARAMS='boot=casper autoinstall ds=nocloud;s=/cdrom/autoinstall/ console=ttyS0,115200n8 console=tty0 ---'
fi

python3 - <<PYEOF
import re, pathlib

path = pathlib.Path("$GRUB_CFG")
txt = path.read_text()

# Parameters for the linux line
# For GRUB, we need to escape the semicolon with a backslash
boot_params = "${BOOT_PARAMS}".replace(";", "\\\\;")

if "$IS_1804" == "true":
    pattern = r'(menuentry "(Try or Install |Install )?Ubuntu Server" {[^}]+linux\s+/install/vmlinuz)([^\n]*)(\n\s*initrd\s+/install/initrd.gz[^\n]*\n\s*})'
    repl = f'''menuentry "Auto Install Ubuntu Server" {{
    set gfxpayload=keep
    linux   /install/vmlinuz {boot_params}
    initrd  /install/initrd.gz
}}'''
else:
    pattern = r'(menuentry "(Try or Install |Install )?Ubuntu Server" {[^}]+linux\s+/casper/vmlinuz)([^\n]*)(\n\s*initrd\s+/casper/initrd[^\n]*\n\s*})'
    repl = f'''menuentry "Auto Install Ubuntu Server" {{
    set gfxpayload=keep
    search --no-floppy --set=root --file /casper/vmlinuz
    linux   /casper/vmlinuz {boot_params}
    initrd  /casper/initrd
}}'''

new_txt, n = re.subn(pattern, repl, txt, flags=re.MULTILINE | re.IGNORECASE)

if n == 0:
    print("WARNING: Did not find expected menuentry; grub.cfg not modified.", flush=True)
else:
    print(f"Patched {n} menuentry block(s).", flush=True)

# Remove standalone grub_platform command that causes error
new_txt = re.sub(r'^\s*grub_platform\s*$', '', new_txt, flags=re.MULTILINE)

path.write_text(new_txt)
PYEOF

# Patch ISOLINUX configuration for BIOS autoinstall
ISOLINUX_CFG_FILES=("./workdir_custom_iso/isolinux/txt.cfg" "./workdir_custom_iso/isolinux/adtxt.cfg")
for cfg in "${ISOLINUX_CFG_FILES[@]}"; do
    if [ -f "$cfg" ]; then
        echo "[*] Patching ISOLINUX configuration in $cfg..."
if [ "$IS_1804" = true ]; then
  # Legacy parameters for 18.04 BIOS boot
  BOOT_PARAMS='file=/cdrom/preseed.cfg auto=true priority=critical initrd=/install/initrd.gz console=ttyS0,115200n8 console=tty0'
else
  # For 20.04+ Autoinstall
  BOOT_PARAMS='boot=casper autoinstall ds=nocloud;s=/cdrom/autoinstall/ initrd=/casper/initrd console=ttyS0,115200n8 console=tty0'
fi

python3 - <<PYEOF
import re, pathlib
path = pathlib.Path("$cfg")
txt = path.read_text()

boot_params = "${BOOT_PARAMS}"

if "$IS_1804" == "true":
    pattern = r'(label\s+install\s+.*?kernel\s+/install/vmlinuz\s+append\s+)(.*?)(\s+---)'
else:
    pattern = r'(label\s+live\s+.*?kernel\s+/casper/vmlinuz\s+append\s+)(.*?)(\s+---)'

repl = rf'\1{boot_params} \3'

new_txt, n = re.subn(pattern, repl, txt, flags=re.DOTALL | re.IGNORECASE)

if n > 0:
    print(f"Patched {n} labels in $cfg.")
    path.write_text(new_txt)
else:
    # Generic fallback: search for ANY append line and inject
    pattern2 = r'(append\s+)(.*?)(\s+---)'
    repl2 = rf'\1{boot_params} \2 \3'
    new_txt2, n2 = re.subn(pattern2, repl2, txt, flags=re.IGNORECASE)
    if n2 > 0:
        print(f"Patched {n2} append lines in $cfg using generic pattern.")
        path.write_text(new_txt2)
PYEOF
    fi
done

echo "[*] Disabling interactive boot menu timeout for ISOLINUX..."
if [ -f "$WORKDIR/isolinux/isolinux.cfg" ]; then
    sed -i 's/^timeout.*/timeout 10/' "$WORKDIR/isolinux/isolinux.cfg" || true
    sed -i 's/^prompt.*/prompt 0/' "$WORKDIR/isolinux/isolinux.cfg" || true
fi

echo "[*] Rebuilding ISO..."

# Find the volume ID from original ISO (optional; can hardcode)
VOLID=$(isoinfo -d -i "$ORIG_ISO" | awk -F': ' '/Volume id:/ {print $2}')
VOLID=${VOLID:-UBUNTU_AUTOINSTALL}

if [ "$IS_1804" = true ]; then
  # IMPORTANT: Do NOT patch boot/grub/efi.img for 18.04!
  # The original efi.img contains only BOOTx64.EFI and grubx64.efi (no grub.cfg).
  # grubx64.efi has an embedded script that:
  #   1. search --file --set=root /.disk/info  (finds the ISO9660 filesystem)
  #   2. set prefix=($root)/boot/grub
  #   3. source $prefix/x86_64-efi/grub.cfg   (loads partition module loader)
  #   4. configfile /boot/grub/grub.cfg        (loads the real menu from ISO9660)
  # Adding grub.cfg inside efi.img breaks this chain because GRUB would load
  # the config in the EFI FAT partition context where /install/vmlinuz doesn't exist.
  # The patched grub.cfg on the ISO9660 filesystem (/boot/grub/grub.cfg) is sufficient.
  echo "[*] 18.04 Legacy ISO: using original efi.img (no modification needed)"

  echo "[*] Modification is ok"
  echo "[*] Generate customize ISO"

  # Extract the isohybrid MBR from the original 18.04 ISO (first 432 bytes = MBR bootstrap code)
  echo "[*] Extracting isohybrid MBR from original ISO..."
  MBR_FILE="/tmp/isohdpfx_1804.bin"
  dd if="$ORIG_ISO" bs=1 count=432 of="$MBR_FILE" 2>/dev/null
  echo "[*] MBR extracted to: $MBR_FILE"

  (
    cd "$WORKDIR"
    # Use the EXACT same xorriso parameters as the original 18.04 ISO reports
    # (obtained via: xorriso -indev ubuntu-18.04.6-server-amd64.iso -report_el_torito as_mkisofs)
    xorriso -as mkisofs \
      -r \
      -V "$VOLID" \
      -J -l \
      -isohybrid-mbr "$MBR_FILE" \
      -partition_cyl_align on \
      -partition_offset 0 \
      -partition_hd_cyl 64 \
      -partition_sec_hd 32 \
      --mbr-force-bootable \
      -apm-block-size 2048 \
      -iso_mbr_part_type 0x00 \
      -c isolinux/boot.cat \
      -b isolinux/isolinux.bin \
      -no-emul-boot \
      -boot-load-size 4 \
      -boot-info-table \
      -eltorito-alt-boot \
      -e boot/grub/efi.img \
      -no-emul-boot \
      -boot-load-size 4800 \
      -isohybrid-gpt-basdat \
      -isohybrid-apm-hfsplus \
      -o "../$OUT_ISO" .
  )

else
  # ---- 20.04+ Modern approach ----
  echo "[*] 20.04+ Modern ISO: building external EFI partition..."

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

  # Create EFI boot image for GPT partition with GRUB modules and config
  EFI_IMG="/tmp/efi.img"
  echo "[*] Creating EFI boot image (64MB)..."
  ( cd "$WORKDIR"
    dd if=/dev/zero of="$EFI_IMG" bs=1M count=64 2>/dev/null
    mkfs.vfat "$EFI_IMG" >/dev/null 2>&1
    mmd -i "$EFI_IMG" ::/EFI ::/EFI/BOOT ::/boot ::/boot/grub

    copy_file_robust() {
      local src_pattern="$1"
      local dest_path="$2"
      local found_file
      found_file=$(find . -iname "$src_pattern" 2>/dev/null | head -n 1)
      if [ -n "$found_file" ]; then
        echo "[*] Copying $found_file to $dest_path"
        mcopy -v -i "$EFI_IMG" "$found_file" "$dest_path"
      else
        echo "[!] Warning: $src_pattern not found"
      fi
    }

    copy_file_robust "bootx64.efi" "::/EFI/BOOT/bootx64.efi"
    copy_file_robust "grubx64.efi" "::/EFI/BOOT/grubx64.efi"
    copy_file_robust "mmx64.efi" "::/EFI/BOOT/mmx64.efi"

    if [ -d "boot/grub" ]; then
      echo "[*] Copying GRUB configuration and assets..."
      find boot/grub -maxdepth 1 -type f -exec mcopy -i "$EFI_IMG" {} ::/boot/grub/ \;
      if [ -f "boot/grub/grub.cfg" ]; then
        mcopy -i "$EFI_IMG" boot/grub/grub.cfg ::/EFI/BOOT/grub.cfg
      fi
    fi

    if [ -d "boot/grub/x86_64-efi" ]; then
      echo "[*] Copying GRUB modules..."
      mcopy -s -i "$EFI_IMG" boot/grub/x86_64-efi ::/boot/grub/
    fi

    if [ -d "boot/grub/fonts" ]; then
      echo "[*] Copying GRUB fonts directory..."
      mcopy -s -i "$EFI_IMG" boot/grub/fonts ::/boot/grub/
    fi
  )
  echo "[*] EFI boot image created: $EFI_IMG"

  echo "[*] Modification is ok"
  echo "[*] Generate customize ISO"

  # Find BIOS boot image
  BIOS_BOOT_IMG=""
  if [ -f "$WORKDIR/boot/grub/i386-pc/eltorito.img" ]; then
    BIOS_BOOT_IMG="boot/grub/i386-pc/eltorito.img"
  elif [ -f "$WORKDIR/isolinux/isolinux.bin" ]; then
    BIOS_BOOT_IMG="isolinux/isolinux.bin"
  fi

  echo "[*] Using BIOS boot image: $BIOS_BOOT_IMG"

  (
    cd "$WORKDIR"
    XORRISO_ARGS=(
      -as mkisofs
      -r
      -V "$VOLID"
      -J -l
      -c boot.catalog
      -no-emul-boot
      -boot-load-size 4
      -boot-info-table
      -eltorito-alt-boot
      -e --interval:appended_partition_2:all::
      -no-emul-boot
      -append_partition 2 0xEF "$EFI_IMG"
      --grub2-mbr "$MBR_FILE"
      -partition_offset 16
      -appended_part_as_gpt
      -iso_mbr_part_type a2a0d0ebe5b9334487c068b6b72699c7
      -o "../$OUT_ISO" .
    )

    if [ -n "$BIOS_BOOT_IMG" ]; then
      xorriso "${XORRISO_ARGS[@]:0:5}" -b "$BIOS_BOOT_IMG" "${XORRISO_ARGS[@]:5}"
    else
      xorriso "${XORRISO_ARGS[@]}"
    fi
  )

fi

echo "[*] Done. Autoinstall ISO created at: $OUT_ISO"
