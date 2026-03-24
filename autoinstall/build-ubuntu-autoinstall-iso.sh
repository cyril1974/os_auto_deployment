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
    USERNAME    Username for the installed system (default: mitac)
    PASSWORD    Password for both user and root (default: MiTAC00123)

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
    # Basic usage with defaults (user: mitac, password: MiTAC00123)
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

# Check for package_list for offline installation
PACKAGE_LIST_FILE="$(dirname "$0")/package_list"
OFFLINE_PACKAGES=""
if [ -f "$PACKAGE_LIST_FILE" ]; then
    echo "[*] Found package_list file. Reading packages for offline installation..."
    # Read packages, ignoring comments and empty lines
    OFFLINE_PACKAGES=$(grep -v '^#' "$PACKAGE_LIST_FILE" | grep -v '^\s*$' | tr '\n' ' ' | xargs)
    # Ensure critical tools are always included if requested (ipmitool, docker, kube tools)
    for pkg in "ipmitool" "docker" "kubelet" "kubeadm" "kubectl"; do
        if [[ " $OFFLINE_PACKAGES " != *" $pkg "* ]]; then
            if [[ "$pkg" == "ipmitool" ]]; then
                # Mandatory fallback for ipmitool
                OFFLINE_PACKAGES="$OFFLINE_PACKAGES ipmitool"
            fi
        fi
    done
    OFFLINE_PACKAGES=$(echo "$OFFLINE_PACKAGES" | xargs) # Trim leading/trailing spaces
    echo "[*] Online package download DISABLED. Following list will be bundled for offline install: $OFFLINE_PACKAGES"
fi

# GPT partition table for UEFI boot compatibility
EFI_GUID="c12a7328-f81f-11d2-ba4b-00a0c93ec93b" # EFI System Partition (ESP)

# Cache directory for persistent package storage
CACHE_DIR="./apt_cache"
mkdir -p "$CACHE_DIR"


# Function to lookup ISO path from file_list.json
lookup_iso_path() {
    local os_name="$1"
    local json_file="./iso_repository/file_list.json"
    
    if [ ! -f "$json_file" ]; then
        echo "Error: file_list.json not found at $json_file" >&2
        exit 1
    fi
    
    # Use jq to find the OS_Path for the given OS_Name
    local iso_path
    iso_path=$(jq -r ".tree.Ubuntu[] | select(.OS_Name == \"$os_name\") | .OS_Path" "$json_file")
    
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

# Download packages for the target Ubuntu version to be bundled into the ISO.
# Packages (from package_list or default ipmitool) are downloaded along with their
# dependencies from the correct Ubuntu archive matching the target ISO's codename.
download_extra_packages() {
    local workdir="$1"
    local codename="$2"
    local extra_pool="$workdir/pool/extra"
    local tmp_download
    tmp_download=$(mktemp -d)

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
    local apt_state="$apt_conf_dir/state"
    local apt_etc="$apt_conf_dir/etc"

    # Define persistent cache location (Ensure absolute path as we will cd shortly)
    local persistent_cache
    persistent_cache="$(realpath "${CACHE_DIR}")/${codename}"
    mkdir -p "$persistent_cache/archives/partial"

    mkdir -p "$apt_state/lists/partial" "$apt_etc/apt.conf.d" "$apt_etc/preferences.d" "$apt_etc/trusted.gpg.d"

    # Create EMPTY dpkg status file — this is critical!
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
        -o Dir::Cache="$persistent_cache"
        -o Dir::State="$apt_state"
        -o Dir::State::status="$apt_state/status"
        -o Dir::Etc="$apt_etc"
        -o Acquire::AllowInsecureRepositories=true
        -o Acquire::AllowDowngradeToInsecureRepositories=true
    )

    # Set up sources for the target version (main + universe)
    cat > "$apt_sources" << APTEOF
deb [trusted=yes] http://archive.ubuntu.com/ubuntu ${codename} main universe
deb [trusted=yes] http://archive.ubuntu.com/ubuntu ${codename}-updates main universe
APTEOF

    # Use the provided OFFLINE_PACKAGES if set, otherwise fallback to default mandatory ipmitool
    local pkgs_to_download="${OFFLINE_PACKAGES:-ipmitool}"

    # Create the autoinstall directory early for GPG key storage
    mkdir -p "$workdir/autoinstall"

    # Add Docker repository if docker is requested in package_list
    if echo "$pkgs_to_download" | grep -q "docker"; then
        echo "[*] Adding Docker repository for bundling..."
        echo "deb [arch=amd64 trusted=yes] https://download.docker.com/linux/ubuntu ${codename} stable" >> "$apt_sources"
        # Expand 'docker' slug to the full package set requested by user
        pkgs_to_download="${pkgs_to_download/docker/docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin}"
        # Bundle Docker GPG key into the ISO autoinstall folder for late-command availability
        echo "[*] Bundling Docker GPG key into ISO..."
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o "$workdir/autoinstall/docker.asc" || true
    fi

    # Add Kubernetes repository if any k8s pkg is requested
    if echo "$pkgs_to_download" | grep -q "kube"; then
        echo "[*] Adding Kubernetes repository for bundling (stable v1.35)..."
        echo "deb [arch=amd64 trusted=yes] https://pkgs.k8s.io/core:/stable:/v1.35/deb/ /" >> "$apt_sources"
        # Bundle Kubernetes GPG key into the ISO autoinstall folder for late-command availability
        echo "[*] Bundling Kubernetes GPG key into ISO..."
        curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.35/deb/Release.key | gpg --dearmor -o "$workdir/autoinstall/kubernetes.gpg" || true
    fi

    echo "[*] Fetching package index for ${codename}..."
    if apt-get "${APT_OPTS[@]}" update 2>&1 | tail -3; then

        echo "[*] Delta Download: Checking cache for requested packages in ${codename}..."
        cd "$tmp_download"

        # Determine the full dependency closure (recursive)
        local all_needed
        all_needed=$(apt-get "${APT_OPTS[@]}" -s install --reinstall $pkgs_to_download | grep '^Inst' | awk '{print $2}' | sort -u || true)

        if [ -z "$all_needed" ]; then
            echo "[!] WARNING: No packages identified for download."
        fi

        for pkg in $all_needed; do
            # Skip common base packages and core libraries already present on the ISO.
            case "$pkg" in
                libc6|libgcc*|debconf*|dpkg|bash|coreutils|install-info|libstdc++*|init-system-helpers|base-files|netbase|libsystemd*|systemd*|libudev*|udev*|libpam*|libnss*|libdbus*|dbus*|libk5*|libssl*|libcrypt*|libzstd*|libuuid*|libblkid*|libmount*|libselinux*|util-linux|mount|login|passwd) continue ;;
            esac
            
            # Check if this package (matching the name) is already in the persistent cache.
            # We look for the ${pkg}_ prefix to be specific.
            if ls "$persistent_cache/archives/${pkg}"_*.deb >/dev/null 2>&1; then
                echo "    + Found $pkg in cache, skipping download."
                continue
            fi

            # apt-get download puts files in CWD ($tmp_download), not in Dir::Cache.
            # We must explicitly move them to the persistent cache archives.
            if apt-get "${APT_OPTS[@]}" -t "${codename}" download "$pkg" 2>/dev/null; then
                mv ./*.deb "$persistent_cache/archives/" 2>/dev/null || true
            fi
        done
        cd - > /dev/null

        # Move files from cache archives to the ISO extra pool
        local deb_count=0
        for pkg_name in $all_needed; do
             # Check if specific package exists in archives (ignoring extension case/version)
             # We use find to be precise about matching the package name prefix.
             find "$persistent_cache/archives/" -maxdepth 1 -name "${pkg_name}_*.deb" -exec cp {} "$extra_pool/" \; 2>/dev/null && deb_count=$((deb_count + 1)) || true
        done
        
        if [ "$deb_count" -gt 0 ]; then
             echo "[*] Bundled $deb_count package(s) into ISO ($extra_pool/)."
        fi

        # Also bundle the binary-less Python IPMI logger into the ISO
        if [ -f "${BASE_DIR}/autoinstall/ipmi_start_logger.py" ]; then
            cp "${BASE_DIR}/autoinstall/ipmi_start_logger.py" "$extra_pool/"
            chmod +x "$extra_pool/ipmi_start_logger.py"
        fi
    else
        echo "[!] WARNING: Failed to fetch package index for ${codename}"
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
# Default user and password (modified per user request)
USERNAME="${2:-mitac}"
PASSWORD="${3:-MiTAC00123}"

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
    download_extra_packages "$WORKDIR" "$UBUNTU_CODENAME"
fi

# Hash password for user-data
HASH_PASSWORD=$(mkpasswd -m sha-512 ${PASSWORD})
echo "[*] Hashed Password is ${HASH_PASSWORD}"

# Create the scripts directory for bundling logic helpers
mkdir -p "$WORKDIR/autoinstall/scripts"

# Write the find_empty_disk_serial function to a standalone script on the ISO
cat > "$WORKDIR/autoinstall/scripts/find_disk.sh" << 'EOF'
#!/bin/sh
find_empty_disk_serial() {
    local min_size=0
    local target_serial=""
    local target_disk=""
    
    echo "[!] INFO: Starting automated disk detection (Prefer SMALLEST empty)..." > /dev/console
    
    # Get all disk devices (sh-compatible)
    for disk in $(lsblk -nd -o NAME --exclude 1,2,11 2>/dev/null); do
        device="/dev/$disk"
        [ -b "$device" ] || continue

        # 1. Partition Check
        partition_count=$(lsblk -nk -o TYPE "$device" 2>/dev/null | grep -c "part")
        if [ "$partition_count" -gt 0 ]; then
            echo "    [-] Skipping $device: Contains $partition_count partition(s)" > /dev/console
            continue
        fi

        # 2. Filesystem Signature Check
        signatures=$(wipefs "$device" 2>/dev/null | grep -v "^offset")
        if [ -n "$signatures" ]; then
            echo "    [-] Skipping $device: Contains filesystem signatures" > /dev/console
            continue
        fi

        # 3. Data Check (First 1MB)
        # Use portable tr to check for non-zero bytes (Dash compatible)
        empty_bytes=$(dd if="$device" bs=1M count=1 2>/dev/null | tr -d '\0' | wc -c)
        if [ "$empty_bytes" -gt 0 ]; then
            echo "    [-] Skipping $device: Contains non-zero data in first 1MB" > /dev/console
            continue
        fi

        # 4. Success - Candidate Found
        size=$(lsblk -ndb -o SIZE "$device" 2>/dev/null)
        serial=$(udevadm info --query=property --name="$device" 2>/dev/null | grep "^ID_SERIAL=" | cut -d'=' -f2)
        
        if [ -z "$serial" ]; then
            # Try DEVPATH fallback for some NVMe controllers
            sys_path=$(udevadm info --query=property --name="$device" 2>/dev/null | grep "^DEVPATH=" | cut -d'=' -f2)
            serial=$(cat "/sys${sys_path}/../serial" 2>/dev/null || cat "/sys${sys_path}/device/serial" 2>/dev/null)
        fi

        if [ -n "$serial" ]; then
            human_size="$((size/1024/1024/1024))GB"
            echo "    [*] Valid Candidate: $device ($human_size, Serial: $serial)" > /dev/console
            
            # Implementation of SMALLEST logic to avoid large data drives
            if [ "$min_size" -eq 0 ] || [ "$size" -lt "$min_size" ]; then
                min_size="$size"
                target_serial="$serial"
                target_disk="$device"
            fi
        else
            echo "    [!] Warning: $device is empty but has no accessible serial. Skipping." > /dev/console
        fi
    done

    if [ -n "$target_serial" ]; then
        echo "[+] Final Selection: $target_disk ($((min_size/1024/1024/1024))GB, Serial: $target_serial)" > /dev/console
        echo "$target_serial"
        return 0
    fi
    
    echo "[!] ERROR: No empty storage devices detected." > /dev/console
    return 1
}
EOF
chmod +x "$WORKDIR/autoinstall/scripts/find_disk.sh"

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
    config:
      - type: disk
        id: disk-main
        match:
          serial: __ID_SERIAL__
        ptable: gpt
        wipe: superblock-recursive
        preserve: false
      - type: partition
        id: partition-efi
        device: disk-main
        size: 512M
        flag: boot
        partition_type: ${EFI_GUID}
        grub_device: true
        number: 1
        preserve: false
      - type: format
        id: format-efi
        volume: partition-efi
        fstype: vfat
        preserve: false
      - type: partition
        id: partition-root
        device: disk-main
        size: -1
        number: 2
        preserve: false
      - type: format
        id: format-root
        volume: partition-root
        fstype: ext4
        preserve: false
      - type: mount
        id: mount-root
        device: format-root
        path: /
      - type: mount
        id: mount-efi
        device: format-efi
        path: /boot/efi
  ssh:
    install-server: true
    authorized-keys:
      - ${PUB_KEY}
    allow-pw: true
  updates: security
  refresh-installer:
    update: no
  apt:
    fallback: offline-install
    geoip: true
    preserve_sources_list: false
    primary:
      - arches: [default]
        uri: http://archive.ubuntu.com/ubuntu
  early-commands:
    # 1. Source and execute find_disk logic safely (if it exists)
    - |
      #!/bin/sh
      if [ -f /cdrom/autoinstall/scripts/find_disk.sh ]; then
          . /cdrom/autoinstall/scripts/find_disk.sh
          serial=\$(find_empty_disk_serial)
          if [ \$? -eq 0 ]; then
              # Update the serial in the configuration files
              # In Ubuntu 24.04, subiquity use cloud.autoinstall.yaml
              for cfg in /autoinstall.yaml /run/subiquity/autoinstall.yaml /run/subiquity/cloud.autoinstall.yaml /tmp/autoinstall.yaml; do
                  if [ -f "\$cfg" ]; then
                      sed -i "s/__ID_SERIAL__/\${serial}/g" "\$cfg"
                  fi
              done
          else
              echo "[!] WARNING: No empty storage device found. Bypassing detection."
          fi
      else
          echo "[!] WARNING: find_disk.sh not found. Proceeding with default config."
      fi

    # Load IPMI kernel modules for BMC communication
    - modprobe ipmi_devintf 2>/dev/null || true
    - modprobe ipmi_si 2>/dev/null || true
    - modprobe ipmi_msghandler 2>/dev/null || true
    - sleep 2
    # Log START INSTALL immediately using Python (Binary-less)
    # This ensures OOB telemetry works BEFORE ipmitool is even installed.
    - python3 /cdrom/pool/extra/ipmi_start_logger.py || true
    # Install ipmitool from pre-bundled .deb files on ISO (no network needed)
    # Packages are version-matched for the target Ubuntu release during ISO build.
    - dpkg -i /cdrom/pool/extra/*.deb 2>/dev/null || true
    # Write SEL entry - OS Installation Starting
    # Uses Add SEL Entry (NetFn=Storage 0x0a, Cmd=0x44) to directly write to the SEL.
    # MiTAC BMC prohibits using BMC Generator ID (0x20); we use software ID (0x21).
    # 16-byte format: RecordID[2] RecType Timestamp[4] GenID[2] EvMRev SensorType SensorNum EventType EvData1 EvData2 EvData3
    # RecordID=0x0000(auto) RecType=0x02(SystemEvent) Timestamp=0x00000000(auto)
    # GenID=0x2100(SWid=0x01) EvMRev=0x04 SensorType=0x12(SystemEvent) SensorNum=0x00
    # EventType=0x6f(sensor-specific,assertion) EvData1=0x01(Starting) EvData2=0xff EvData3=0xff
    - ipmitool raw 0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x01 0x00 0x00 2>/dev/null || true
  late-commands:
    - echo 'root:${PASSWORD}' | chroot /target chpasswd
    - curtin in-target --target=/target -- sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
    - curtin in-target --target=/target -- sed -i 's/^#\\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
    - echo '${USERNAME} ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/${USERNAME}
    - chmod 440 /target/etc/sudoers.d/${USERNAME}
    # Ensure DNS resolution is available in the target chroot (in case of local proxy)
    - cp /etc/resolv.conf /target/etc/resolv.conf
    # Package installation (Offline if package_list provided, else Hybrid)
    - |
      if [ -n "${OFFLINE_PACKAGES}" ]; then
          echo "[*] Installing specified packages offline: ${OFFLINE_PACKAGES}"
          # Preparation of target-side environment
          mkdir -p /target/tmp/extra_pkg
          cp -r /cdrom/pool/extra/*.deb /target/tmp/extra_pkg/ 2>/dev/null || true

          # If Docker is being installed, setup the keyring and list file
          if echo "${OFFLINE_PACKAGES}" | grep -q "docker"; then
              echo "[*] Setting up Docker keyring and sources..."
              mkdir -p /target/etc/apt/keyrings
              cp /cdrom/autoinstall/docker.asc /target/etc/apt/keyrings/docker.asc 2>/dev/null || true
              chmod a+r /target/etc/apt/keyrings/docker.asc
              # Get arch and distro from inside the target (Must be escaped to prevent builder-side expansion)
              arch=\$(chroot /target dpkg --print-architecture)
              distro=\$(chroot /target bash -c '. /etc/os-release && echo \$VERSION_CODENAME')
              echo "deb [arch=\$arch signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \$distro stable" > /target/etc/apt/sources.list.d/docker.list
          fi

          # If Kubernetes is being installed, setup the keyring and list file
          if echo "${OFFLINE_PACKAGES}" | grep -q "kube"; then
              echo "[*] Setting up Kubernetes keyring and sources..."
              mkdir -p /target/etc/apt/keyrings
              cp /cdrom/autoinstall/kubernetes.gpg /target/etc/apt/keyrings/kubernetes-apt-keyring.gpg 2>/dev/null || true
              chmod a+r /target/etc/apt/keyrings/kubernetes-apt-keyring.gpg
              arch=\$(chroot /target dpkg --print-architecture)
              echo "deb [arch=\$arch signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.35/deb/ /" > /target/etc/apt/sources.list.d/kubernetes.list
          fi

          # Standard installation via curtin in-target (ensures proper mount points like /proc)
          curtin in-target --target=/target -- sh -c 'apt-get install -y /tmp/extra_pkg/*.deb || dpkg -i /tmp/extra_pkg/*.deb || true'
          rm -rf /target/tmp/extra_pkg
      else
          echo "[*] Attempting to install default packages from Internet mirrors..."
          if apt-get update && curtin in-target --target=/target -- apt-get install -y vim curl net-tools ipmitool htop; then
              echo "[+] Success: Packages installed from Internet mirrors."
          else
              echo "[-] Warning: Internet installation failed. Falling back to local CDROM pool..."
              mkdir -p /target/tmp/extra_pkg
              cp -r /cdrom/pool/extra/*.deb /target/tmp/extra_pkg/ 2>/dev/null || true
              curtin in-target --target=/target -- sh -c 'apt-get install -y /tmp/extra_pkg/*.deb || dpkg -i /tmp/extra_pkg/*.deb || true'
              rm -rf /target/tmp/extra_pkg
          fi
      fi
    # Log IP Address to SEL (Two-part entry for Mitac/Intel BMC compatibility)
    - |
      curtin in-target --target=/target -- sh -c '
        IP=\$(hostname -I | awk "{print \$1}")
        if [ -n "\$IP" ]; then
            # Split IP into 4 octets
            o1=\$(echo \$IP | cut -d. -f1)
            o2=\$(echo \$IP | cut -d. -f2)
            o3=\$(echo \$IP | cut -d. -f3)
            o4=\$(echo \$IP | cut -d. -f4)
            
            # Convert to hex bytes
            h1=\$(printf "0x%02x" \$o1)
            h2=\$(printf "0x%02x" \$o2)
            h3=\$(printf "0x%02x" \$o3)
            h4=\$(printf "0x%02x" \$o4)
            
            # Part 1: IP Octets 1.2 (192.168)
            ipmitool raw 0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x01 \$h1 \$h2 2>/dev/null || true
            sleep 1
            # Part 2: IP Octets 3.4 (236.120)
            ipmitool raw 0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x02 \$h3 \$h4 2>/dev/null || true
            echo "[+] IP \$IP logged to SEL."
        fi
      '
    # Write SEL entry - OS Installation Completed
    # Uses curtin in-target to ensure /dev/ipmi0 is accessible.
    - sleep 1
    - curtin in-target --target=/target -- sh -c 'ipmitool raw 0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x02 0x00 0x00 || true'
    - sleep 1
    
    # Verification: Ensure root is on the correct serial and log outcome to SEL
    - |
      curtin in-target --target=/target -- sh -c '
        # Detect actual root device serial (identifying the parent disk of / partition)
        root_dev=\$(lsblk -no PKNAME \$(findmnt -nvo SOURCE /) | head -n 1)
        [ -z "\$root_dev" ] && root_dev=\$(lsblk -no NAME \$(findmnt -nvo SOURCE /) | head -n 1)
        actual_serial=\$(udevadm info --query=property --name=/dev/\$root_dev 2>/dev/null | grep "^ID_SERIAL=" | cut -d"=" -f2)
        expected_serial="__ID_SERIAL__"
        
        echo "--- Installation Audit ---" >> /var/log/install_disk_audit.log
        echo "Expected Serial: \$expected_serial" >> /var/log/install_disk_audit.log
        echo "Actual Root Serial: \$actual_serial" >> /var/log/install_disk_audit.log
        
        if [ "\$actual_serial" = "\$expected_serial" ]; then
            echo "[+] VERIFICATION SUCCESS: OS installed on correct disk (\$actual_serial)"
            echo "Result: SUCCESS" >> /var/log/install_disk_audit.log
            # Log SUCCESS (ASCII "OK") to SEL EvData2/3
            ipmitool raw 0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x02 0x4f 0x4b 2>/dev/null || true
        else
            echo "[!] VERIFICATION FAILED: OS installed on WRONG disk!"
            echo "[!] Actual: \$actual_serial"
            echo "Result: FAILURE (Target Mismatch)" >> /var/log/install_disk_audit.log
            # Log FAILURE (ASCII "ER" for Error) to SEL EvData2/3
            ipmitool raw 0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x02 0x45 0x52 2>/dev/null || true
        fi
      '
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
    # 18.04 Legacy
    pattern = r'(menuentry\s+[\'"](?:Try or Install |Install )?Ubuntu Server[\'"]\s+{[^}]+linux\s+/install/(?:hwe-)?vmlinuz)([^\n]*)(\n\s*initrd\s+/install/(?:hwe-)?initrd\.gz[^\n]*\n\s*})'
    repl = f'''menuentry "Auto Install Ubuntu Server" {{
    set gfxpayload=keep
    linux   /install/vmlinuz {boot_params}
    initrd  /install/initrd.gz
}}'''
else:
    # 20.04 - 24.10 Autoinstall
    # Match menuentry with either ' or " quotes, and handle possible hwe-vmlinuz
    pattern = r'(menuentry\s+[\'"](?:Try or Install |Install )?Ubuntu Server[\'"]\s+{[^}]+linux\s+/casper/(?:hwe-)?vmlinuz)([^\n]*)(\n\s*initrd\s+/casper/(?:hwe-)?initrd[^\n]*\n\s*})'
    # Also attempt a more generic match if the specific one fails
    generic_pattern = r'(menuentry\s+[\'"]Ubuntu[\'"]\s+{[^}]+linux\s+/casper/[^\n]+)([^\n]*)(\n\s*initrd\s+/casper/[^\n]+[^\n]*\n\s*})'
    
    repl = f'''menuentry "Auto Install Ubuntu Server" {{
    set gfxpayload=keep
    search --no-floppy --set=root --file /casper/vmlinuz
    linux   /casper/vmlinuz {boot_params}
    initrd  /casper/initrd
}}'''

new_txt, n = re.subn(pattern, repl, txt, flags=re.MULTILINE | re.IGNORECASE)

if n == 0:
    # Try the generic pattern if the specific one failed
    new_txt, n = re.subn(r'(menuentry\s+[\'"][^"]*Ubuntu[^"]*[\'"]\s+{[^}]+linux\s+/(?:casper|install)/[^\s]+)([^\n]*)(\n\s*initrd\s+/(?:casper|install)/[^\n]+[^\n]*\n\s*})', repl, txt, flags=re.MULTILINE | re.IGNORECASE)

if n == 0:
    print("WARNING: Did not find expected menuentry; grub.cfg not modified.", flush=True)
else:
    print(f"Patched {n} menuentry block(s) in grub.cfg.", flush=True)

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
