# build-iso-go

A Go rewrite of `../build-ubuntu-autoinstall-iso.sh`.

Produces the same custom Ubuntu autoinstall ISO as the shell script — fully unattended, IPMI SEL telemetry, offline package bundling, Ubuntu 18.04 preseed and Ubuntu 20.04+ autoinstall support.

---

## Directory Layout

```
autoinstall/
├── build-ubuntu-autoinstall-iso.sh   ← original shell script
├── build-iso-go/                     ← this Go program
│   ├── main.go
│   ├── go.mod
│   └── README.md
├── iso_repository/                   ← ISO files + file_list.json
│   └── file_list.json
├── scripts/
│   ├── find_disk.sh                  ← required for 20.04+
│   └── find_disk_1804.sh             ← required for 18.04
├── ipmi_start_logger.py              ← bundled into ISO at build time
├── startup.nsh                       ← bundled into EFI image
├── package_list                      ← optional offline package list
├── apt_cache/                        ← persistent .deb download cache
└── output_custom_iso/                ← built ISOs are saved here
```

> **Important:** The binary must be run from the `autoinstall/` directory so that relative paths (`./iso_repository/`, `./output_custom_iso/`, `./apt_cache/`) resolve correctly.

---

## Build

```bash
cd autoinstall/build-iso-go
go build -o build-iso .
```

Requires Go 1.21+. No external Go dependencies — stdlib only.

---

## Usage

```bash
# Run from the autoinstall/ directory
cd autoinstall/

# Basic (defaults: user=mitac, password=ubuntu)
sudo ./build-iso-go/build-iso ubuntu-22.04.5-live-server-amd64

# Custom username and password
sudo ./build-iso-go/build-iso ubuntu-24.04.2-live-server-amd64 myuser MyPass123

# Skip apt package installation check (faster, if tools already installed)
sudo ./build-iso-go/build-iso ubuntu-24.04.2-live-server-amd64 --skip-install
```

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `OS_NAME` | *(required)* | Must match an `OS_Name` entry in `iso_repository/file_list.json` |
| `USERNAME` | `mitac` | Username created on the installed system |
| `PASSWORD` | `ubuntu` | Password for both user and root |
| `--skip-install` | false | Skip checking / installing host tool dependencies |

### Output

```
autoinstall/output_custom_iso/<BUILD_ID>/
└── ubuntu_24_04_2_live_server_amd64_autoinstall_<TIMESTAMP>.iso
```

A unique `BUILD_ID` (datetime + random suffix) is generated per run to support parallel builds.

---

## How It Works

### Phase 1 — Dependency Check
Verifies that `whois`, `genisoimage`, `xorriso`, `isolinux`, `mtools`, `jq` are installed. Installs missing packages via `apt` if running as root.

### Phase 2 — ISO Lookup & Mount
Reads `iso_repository/file_list.json` to resolve the ISO file path by `OS_Name`. Mounts the original ISO via loop device and copies its contents into a temporary work directory.

### Phase 3 — Codename Detection
Determines the Ubuntu release codename using three methods in order:
1. Read `/.disk/info` from the ISO
2. Check the single subdirectory name under `/dists/`
3. Fall back to version string matching (e.g. `24.04` → `noble`)

### Phase 4 — Offline Package Bundling
Creates an isolated apt environment (empty dpkg status, separate state/cache dirs) pointing at the **target** Ubuntu archive — not the host's. Downloads the full dependency closure for packages listed in `package_list` (or the default set: `ipmitool grub-efi-amd64-signed shim-signed efibootmgr`) and copies `.deb` files into `pool/extra/` on the ISO. Downloaded packages are cached in `apt_cache/<codename>/` for reuse on subsequent builds.

Special handling:
- **Docker**: expands the `docker` slug to the full package set and bundles the Docker GPG key
- **Kubernetes**: adds the k8s v1.35 stable repo and bundles the Kubernetes GPG key

### Phase 5 — SSH Key Generation
Generates a fresh `ed25519` key pair in `~/.ssh/` with a timestamped name. The public key is embedded in `autoinstall/user-data` for immediate SSH access after installation.

### Phase 6 — Cloud-Init / Preseed Generation

**Ubuntu 20.04+ (autoinstall):** Writes `autoinstall/user-data` and `autoinstall/meta-data` into the ISO work directory. The `user-data` file uses the `nocloud` data source with:
- GPT partition layout with 512 MB EFI + remaining root
- Disk matched by `__ID_SERIAL__` (patched at boot by `find_disk.sh`)
- `early-commands`: load IPMI modules, run `find_disk.sh`, install bundled `.deb` files, log IPMI SEL events
- `late-commands`: configure SSH, sudoers, install packages, log IP address and completion to SEL, verify disk serial

**Ubuntu 18.04 (preseed):** Writes `preseed.cfg` with equivalent functionality using the Debian Installer preseed format. Disk detection runs via `partman/early_command` using `find_disk_1804.sh`.

### Phase 7 — GRUB & ISOLINUX Patching
Patches `boot/grub/grub.cfg` and `isolinux/txt.cfg` / `isolinux/adtxt.cfg` to:
- Set `timeout=5` and `default=0`
- Replace the default "Try or Install" menu entry with `Auto Install Ubuntu Server`
- Inject the correct kernel boot parameters (`autoinstall ds=nocloud` for 20.04+, `file=/cdrom/preseed.cfg` for 18.04)
- Add `video=1024x768 console=ttyS0,115200n8 console=tty0` for serial console support

### Phase 8 — ISO Rebuild

**Ubuntu 18.04:** Uses `xorriso -as mkisofs` with isohybrid MBR extracted from the original ISO. The original `boot/grub/efi.img` is left unmodified (patching it would break GRUB's boot chain on 18.04).

**Ubuntu 20.04+:** Builds a fresh 64 MB FAT32 EFI partition image (`efi.img`) containing:
- `EFI/BOOT/bootx64.efi`, `grubx64.efi`, `mmx64.efi`
- GRUB modules, fonts, and patched `grub.cfg`
- `startup.nsh` for UEFI Shell auto-execution

Then calls `xorriso` with GPT + hybrid MBR for dual BIOS/UEFI boot.

---

## Comparison: Go vs Shell

| Aspect | Shell script | Go binary |
|---|---|---|
| **Lines of code** | ~1,253 | ~1,394 |
| **JSON parsing** | `jq` (external) | `encoding/json` (stdlib) |
| **Regex patching** | `sed`, `python3 -c` | `regexp` (stdlib) |
| **Templating** | here-docs (`<< EOF`) | `text/template` (stdlib) |
| **Exit on error** | `set -euo pipefail` | `fatalf()` helper |
| **Cleanup on exit** | `trap cleanup EXIT` | `defer os.RemoveAll()` |
| **External deps** | bash, jq, python3, sed | **zero** Go deps (stdlib only) |
| **Parallel builds** | Separate processes | Native goroutines (future) |
| **Cross-compile** | No | `GOOS=linux go build` |
| **Testability** | Difficult | Functions are unit-testable |
| **Error messages** | String output | Structured with line context |

---

## Required Host Tools

These system binaries must be present (the program installs them automatically if root):

| Tool | Used for |
|---|---|
| `xorriso` | Rebuilding the ISO |
| `genisoimage` | ISO volume ID detection |
| `mtools` / `mmd` / `mcopy` | Building the EFI FAT image |
| `mkfs.vfat` | Formatting the EFI image |
| `rsync` | Copying ISO contents to work dir |
| `mount` / `umount` | Mounting the source ISO |
| `ssh-keygen` | Generating the deployment key pair |
| `mkpasswd` | Hashing the user password (SHA-512) |
| `apt-get` | Downloading offline packages |
| `dd` | Extracting MBR from original ISO |

---

## IPMI SEL Event Markers

The installed OS logs progress events to the BMC System Event Log via `ipmi_start_logger.py`:

| Marker | Event |
|---|---|
| `0x0F` | Package pre-install start |
| `0x1F` | Package pre-install complete |
| `0x01` | OS installation start |
| `0x06` | Post-install (late-commands) start |
| `0x16` | Post-install complete |
| `0x03` + `0x13` | IP address (two-part: octets 1.2 and 3.4) |
| `0xAA` | Installation fully complete |
| `0x05 0x4F 0x4B` | Disk serial verification: OK |
| `0x05 0x45 0x52` | Disk serial verification: ERROR |
| `0xEE` | Installation aborted / failed |
