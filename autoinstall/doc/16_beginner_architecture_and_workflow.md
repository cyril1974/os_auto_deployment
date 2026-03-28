# Beginner Guide: Autoinstall Architecture & Workflow

## What this project does (in plain words)

The `autoinstall/` tooling takes an original Ubuntu Server ISO and produces a **new custom ISO** that installs Ubuntu automatically with no manual installer steps.

This is especially useful for remote provisioning through **BMC virtual media** where keyboard/screen access is limited.

---

## Big picture architecture

Think of the system as 3 layers:

1. **Input layer**
   - Source ISO selected by `OS_NAME` from `iso_repository/file_list.json`
   - Operator-provided username/password

2. **Build layer (script)**
   - Extract original ISO into a writable work directory
   - Inject unattended install config (`autoinstall/user-data`, `autoinstall/meta-data`)
   - Patch boot menus (GRUB + ISOLINUX)
   - Rebuild a hybrid BIOS/UEFI ISO

3. **Runtime install layer (target server)**
   - Server boots from the custom ISO via BMC
   - Kernel starts with autoinstall parameters
   - cloud-init/subiquity/curtin install OS and run post-install tasks

---

## Core components

### 1) Main build script

- File: `build-ubuntu-autoinstall-iso.sh`
- Responsibilities:
  - Validate arguments
  - Locate source ISO from JSON
  - Prepare work/output directories
  - Build unattended install configuration
  - Patch bootloader configs
  - Repack final ISO

### 2) Working directories and outputs

- `./workdir_custom_iso/` → temporary extracted and modified ISO tree
- `./output_custom_iso/` → final generated autoinstall ISO

### 3) Injected unattended config

- `autoinstall/meta-data`
- `autoinstall/user-data`

For Ubuntu 20.04+, cloud-init autoinstall is used.
For Ubuntu 18.04, the script additionally generates `preseed.cfg` for legacy installer flow.

---

## Workflow (step-by-step)

## Phase 1: Start and validate

- Parse: `OS_NAME [USERNAME] [PASSWORD]`
- Optional: `--skip-install`
- Ensure required packages are available (`xorriso`, `mtools`, `jq`, etc.)

## Phase 2: Resolve source ISO

- Read `iso_repository/file_list.json`
- Match `OS_NAME` to `OS_Path`
- Exit early if name/path is not found

## Phase 3: Prepare ISO workspace

- Remove old work/output folders
- Mount source ISO at `/mnt/ubuntuiso`
- Copy contents into `workdir_custom_iso`
- Unmount source ISO

## Phase 4: Create unattended install data

- Hash password with SHA-512 (`mkpasswd -m sha-512`)
- Generate SSH keypair and embed public key in `user-data`
- Set identity (hostname, username, password)
- Configure SSH + package behavior
- Add early and late commands (including IPMI SEL writes)

## Phase 5: Patch boot configuration

- Edit `boot/grub/grub.cfg`:
  - set default/timeout
  - replace menu entry with Auto Install entry
  - inject correct kernel args for autoinstall/preseed
- Patch BIOS boot menus in ISOLINUX (`txt.cfg`, `adtxt.cfg` when present)

## Phase 6: Rebuild final ISO

Two paths are used:

- **Ubuntu 18.04 path**
  - Keeps legacy EFI image behavior
  - Uses legacy xorriso options compatible with 18.04 boot chain

- **Ubuntu 20.04+ path**
  - Builds external FAT EFI image
  - Copies EFI binaries, GRUB assets/modules/fonts
  - Uses xorriso with appended EFI partition + GPT/MBR hybrid metadata

Output is written to `./output_custom_iso/<name>_autoinstall_<timestamp>.iso`.

---

## Runtime install flow on target server

1. BMC mounts custom ISO as virtual media
2. Firmware boots (UEFI or BIOS)
3. GRUB/ISOLINUX autoselects unattended entry
4. Kernel + initrd boot with autoinstall (or preseed) parameters
5. cloud-init/subiquity perform automated install
6. late-commands finalize root password, SSH, sudo, package setup
7. System reboots into installed OS

---

## Common beginner pitfalls

- `OS_NAME` mismatch in `file_list.json`
- Source ISO path missing/inaccessible
- Missing required build packages
- Boot menu not patched because unexpected upstream config layout
- Environment cannot mount loop devices (container limitations)
- 18.04 behavior differs from modern autoinstall flow

---

## Where to read next

- `01_architecture.md` for full architecture diagrams
- `02_workflow.md` for phase diagrams
- `04_debugging_guide.md` for troubleshooting commands/logs
- `17_day1_operator_cheat_sheet.md` for practical day-1 operations
