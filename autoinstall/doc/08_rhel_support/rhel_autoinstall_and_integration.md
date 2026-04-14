# RHEL Automated Installation — Principle, Workflow, and Go Builder Integration

---

## 1. Overview

Red Hat Enterprise Linux (RHEL), and its binary-compatible derivatives (Rocky Linux,
AlmaLinux, CentOS Stream), use **Kickstart** as their unattended-installation technology.
Kickstart is the RHEL equivalent of Ubuntu's Subiquity autoinstall — it is a plain-text
answer file that pre-answers every question the Anaconda installer would otherwise ask.

| Technology | Ubuntu | RHEL / Rocky / Alma |
|---|---|---|
| Installer | Subiquity | Anaconda |
| Answer file | `user-data` (cloud-init YAML) | `ks.cfg` (Kickstart) |
| Format | YAML | INI-like with `%sections` |
| Boot parameter | `autoinstall ds=nocloud` | `inst.ks=<location>` |
| Pre-install hook | `early-commands:` | `%pre` section |
| Post-install hook | `late-commands:` | `%post` section |
| Offline packages | `.deb` via `dpkg -i` | `.rpm` via `rpm -i` or `%packages` |

---

## 2. Kickstart File Structure

A Kickstart file (`ks.cfg`) has four functional areas:

```
# ── 1. Installation commands ─────────────────────────────────────────
lang en_US.UTF-8
keyboard us
timezone UTC --utc
network --bootproto=dhcp --hostname=rhel-auto
rootpw --iscrypted <sha512-hash>
user --name=sysadmin --password=<hash> --iscrypted --groups=wheel
sshkey --username=sysadmin "<public-key>"
selinux --disabled
firewall --disabled
services --enabled=sshd
reboot

# ── 2. Disk and partition layout ─────────────────────────────────────
# (see Section 3 — disk selection)
ignoredisk --only-use=sda
clearpart --all --initlabel --drives=sda
part /boot/efi --fstype=efi   --size=512  --ondrive=sda
part /boot     --fstype=xfs   --size=1024 --ondrive=sda
part /         --fstype=xfs   --size=-1   --grow --ondrive=sda

# ── 3. Package selection ──────────────────────────────────────────────
%packages --ignoremissing
@core
ipmitool
openssh-server
%end

# ── 4. Pre/Post scripts ───────────────────────────────────────────────
%pre --interpreter=/bin/bash --log=/tmp/ks-pre.log
# runs BEFORE partitioning, in the live installer env
%end

%post --interpreter=/bin/bash --log=/var/log/ks-post.log
# runs AFTER first boot inside the installed OS (chroot)
%end
```

---

## 3. Disk Selection

### 3a. Static — `ignoredisk` (known disk name)

The simplest method. The operator specifies the target device name at ISO build time:

```
ignoredisk --only-use=sda
clearpart  --all --initlabel --drives=sda
```

**Limitation:** device names (`sda`, `nvme0n1`) are assigned by the kernel and can shift
between boots.  Reliable only on single-disk systems or when the target slot is fixed.

### 3b. Static — `inst.ks.device` / `ignoredisk --only-use=<model>` by udev property

Anaconda (RHEL 8+) supports device matching by WWN, path, or model in some contexts, but
`ignoredisk` itself only accepts device names — not serial numbers.

### 3c. Dynamic — `%pre` script (equivalent to `find_disk.sh`)

The most reliable method for multi-disk servers.  A `%pre` script runs before partitioning
while the full installer environment is available.  It probes disks and writes the chosen
device into a second Kickstart snippet that the main file `%include`s:

```kickstart
%include /tmp/ks-disk.cfg     ← written by %pre

%pre --interpreter=/bin/bash
#!/bin/bash

# ---- find the smallest empty disk (mirrors find_disk.sh logic) ----
target=""
min_size=0

for disk in $(lsblk -nd -o NAME --exclude 1,2,11 2>/dev/null); do
    dev="/dev/$disk"
    [ -b "$dev" ] || continue

    # skip if partitioned
    parts=$(lsblk -n -o TYPE "$dev" 2>/dev/null | grep -c "part")
    [ "$parts" -gt 0 ] && continue

    # skip if filesystem signatures present
    sigs=$(wipefs "$dev" 2>/dev/null | grep -v "^offset")
    [ -n "$sigs" ] && continue

    # skip if first 1 MB has > 512 non-zero bytes
    nz=$(dd if="$dev" bs=1M count=1 2>/dev/null | tr -d '\0' | wc -c)
    [ "$nz" -gt 512 ] && continue

    size=$(lsblk -ndb -o SIZE "$dev" 2>/dev/null)
    if [ "$min_size" -eq 0 ] || [ "$size" -lt "$min_size" ]; then
        min_size=$size
        target=$disk
    fi
done

if [ -z "$target" ]; then
    echo "[!] ERROR: No empty disk found" >> /dev/console
    exit 1
fi

# Write the disk selection snippet
cat > /tmp/ks-disk.cfg << EOF
ignoredisk --only-use=${target}
clearpart  --all --initlabel --drives=${target}
part /boot/efi --fstype=efi  --size=512  --ondrive=${target}
part /boot     --fstype=xfs  --size=1024 --ondrive=${target}
part /         --fstype=xfs  --size=-1   --grow --ondrive=${target}
EOF
echo "[+] Target disk: ${target}" >> /dev/console
%end
```

> **Note:** In Anaconda's `%pre` environment, `lsblk`, `wipefs`, `blkid`, `dd`, and `udevadm`
> are available — the same tools used in `find_disk.sh`.

### 3d. Static-by-serial — `inst.ks.device` not applicable; use `%pre` with serial lookup

When a serial number is known at build time (equivalent to `--storage-serial` in the
Go builder), embed it directly in a `%pre` script:

```bash
# resolve device name from known serial at install time
target=$(lsblk -nd -o NAME 2>/dev/null | while read d; do
    s=$(udevadm info --query=property --name=/dev/$d 2>/dev/null | grep "^ID_SERIAL=" | cut -d= -f2)
    [ "$s" = "S3EVNX0K123456" ] && echo "$d" && break
done)
```

---

## 4. How Anaconda Finds the Kickstart File

The `inst.ks=` kernel boot parameter tells Anaconda where to load the Kickstart file from.

| Location | Boot parameter |
|---|---|
| On the ISO/CDROM | `inst.ks=cdrom:/ks.cfg` |
| HTTP server | `inst.ks=http://192.168.1.10/ks.cfg` |
| NFS share | `inst.ks=nfs:192.168.1.10:/exports/ks.cfg` |
| Embedded in initrd | `inst.ks=file:/ks.cfg` |

For the BMC virtual-media deployment model used in this project, **`inst.ks=cdrom:/ks.cfg`**
is the correct choice — the Kickstart file is placed at the root of the rebuilt ISO.

---

## 5. Boot Parameter Injection

RHEL ISOs use the same GRUB2 / ISOLINUX dual-boot layout as Ubuntu.

**GRUB entry (`boot/grub2/grub.cfg` or `EFI/BOOT/grub.cfg`):**

```
menuentry 'Auto Install RHEL' {
    linuxefi  /images/pxeboot/vmlinuz \
        inst.stage2=cdrom \
        inst.ks=cdrom:/ks.cfg \
        console=ttyS0,115200n8 console=tty0 \
        video=1024x768 quiet
    initrdefi /images/pxeboot/initrd.img
}
```

**ISOLINUX entry (`isolinux/isolinux.cfg`):**

```
label autoinstall
  menu label ^Auto Install RHEL
  kernel vmlinuz
  append initrd=initrd.img \
    inst.stage2=cdrom \
    inst.ks=cdrom:/ks.cfg \
    console=ttyS0,115200n8 console=tty0 \
    video=1024x768 quiet
```

Key differences from Ubuntu:
- Kernel is at `images/pxeboot/vmlinuz` (not `casper/vmlinuz`)
- `inst.stage2=cdrom` tells Anaconda to load installer components from the disc
- No `ds=nocloud` — Kickstart is fully self-contained

---

## 6. Offline Package Bundling

RHEL's `%packages` section names RPM packages.  Anaconda resolves them from the disc's
`BaseOS` and `AppStream` repositories (`repodata/` trees on the ISO).

For packages **not** on the original ISO, two approaches exist:

### 6a. Bundle extra RPMs on the ISO

Copy additional `.rpm` files into a custom directory (e.g. `/extra-rpms/`) and install
them in `%post`:

```bash
%post
rpm -i --nodeps /mnt/source/extra-rpms/*.rpm 2>/dev/null || true
%end
```

### 6b. Create an additional local repo on the ISO

Add a `[extra]` repo entry pointing at the bundled directory, then list packages normally
in `%packages`.  Requires generating a `repodata/` index with `createrepo_c`.

---

## 7. IPMI SEL Telemetry in RHEL

The same `ipmi_start_logger.py` binary-less logger used for Ubuntu can be embedded in the
RHEL ISO and called from `%pre` and `%post`:

```bash
%pre
modprobe ipmi_devintf ipmi_si ipmi_msghandler 2>/dev/null || true
sleep 2
python3 /run/install/repo/extra-rpms/ipmi_start_logger.py 0x01 || true
%end

%post
python3 /mnt/source/extra-rpms/ipmi_start_logger.py 0xAA || true
%end
```

> **CDROM path in `%pre`:** the installer disc is mounted at `/run/install/repo` in RHEL 8/9.
> In `%post` (chroot) it is accessible at `/mnt/source` or via `--nochroot`.

---

## 8. Integration Plan for the Go ISO Builder

The Go builder (`autoinstall/build-iso-go/main.go`) requires the following additions to
support RHEL-family ISOs.

### 8.1 Codename / Distro Detection

Extend `getUbuntuCodename()` (or add `detectDistro()`) to recognise RHEL-family ISOs:

| Detection method | Path on ISO | Content |
|---|---|---|
| `.treeinfo` | `/.treeinfo` | `[release]` section with `name` and `version` |
| `media.repo` | `/media.repo` | `[InstallMedia]` section |
| `BaseOS` repo presence | `/BaseOS/repodata/` | exists on RHEL 8/9 |

```go
// Pseudo-code
func detectDistro(workDir string) (family, version string) {
    if fileExists(workDir + "/.treeinfo") {
        // parse [release] name/version
    }
    if dirExists(workDir + "/BaseOS") {
        family = "rhel"
    }
    if dirExists(workDir + "/casper") {
        family = "ubuntu"
    }
}
```

### 8.2 Kickstart File Generation

Add a `writeKickstartFiles(cfg BuildConfig, workDir string)` function parallel to
`writeCloudInitFiles()`.  The Kickstart template mirrors the user-data template:

```
%include /tmp/ks-disk.cfg       ← disk selection written by %pre

lang en_US.UTF-8
keyboard us
timezone UTC --utc
rootpw --iscrypted {{.HashedPassword}}
user --name={{.Username}} --password={{.HashedPassword}} --iscrypted --groups=wheel
sshkey --username={{.Username}} "{{.SSHPubKey}}"
selinux --disabled
firewall --disabled
services --enabled=sshd
reboot --eject

%packages --ignoremissing
@core
ipmitool
%end

%pre --interpreter=/bin/bash
{{- if .FindDiskEnabled}}
# dynamic disk detection (mirrors find_disk.sh)
...
{{- else}}
# static disk selection
cat > /tmp/ks-disk.cfg << EOF
ignoredisk --only-use=$(lsblk -nd -o NAME 2>/dev/null | while read d; do
    s=$(udevadm info --query=property --name=/dev/$d 2>/dev/null | grep "^ID_SERIAL=" | cut -d= -f2)
    [ "$s" = "{{.StorageMatchValue}}" ] && echo "$d" && break
done)
...
EOF
{{- end}}

# IPMI markers
modprobe ipmi_devintf ipmi_si ipmi_msghandler 2>/dev/null || true
sleep 2
python3 /run/install/repo/extra-rpms/ipmi_start_logger.py 0x01 || true
%end

%post --interpreter=/bin/bash
python3 /mnt/source/extra-rpms/ipmi_start_logger.py 0xAA || true
%end
```

### 8.3 GRUB and ISOLINUX Patching

The existing `patchGrub()` and `patchIsolinux()` functions need RHEL-aware paths and
parameters.

| Item | Ubuntu | RHEL 8/9 |
|---|---|---|
| GRUB config path | `boot/grub/grub.cfg` | `EFI/BOOT/grub.cfg` + `boot/grub2/grub.cfg` |
| Kernel path | `casper/vmlinuz` | `images/pxeboot/vmlinuz` |
| Initrd path | `casper/initrd` | `images/pxeboot/initrd.img` |
| Autoinstall param | `autoinstall ds=nocloud` | `inst.ks=cdrom:/ks.cfg inst.stage2=cdrom` |
| ISOLINUX config | `isolinux/txt.cfg` | `isolinux/isolinux.cfg` |

Suggested refactor: add a `DistroFamily string` field to `BuildConfig` and branch on it
inside the existing patch functions rather than duplicating them.

### 8.4 Offline Package Bundling

The existing `downloadExtraPackages()` downloads `.deb` files using an isolated `apt`
environment.  For RHEL a parallel `downloadExtraPackagesRpm()` is needed:

1. Use `dnf download --resolve --destdir=<pool/extra>` with a RHEL or Rocky repo pointed
   at the target version.
2. Copy `.rpm` files into `extra-rpms/` on the ISO.
3. In `%post`, install with `rpm -i --nodeps /mnt/source/extra-rpms/*.rpm`.

> The host machine running the builder must have `dnf` installed, or a container with the
> target RHEL version is needed for accurate dependency resolution.

### 8.5 `file_list.json` Extension

Add RHEL/Rocky entries alongside Ubuntu:

```json
{
  "tree": {
    "Ubuntu": [...],
    "RHEL": [
      {
        "OS_Name": "rhel-9.4-x86_64",
        "OS_Path": "rhel-9.4-x86_64-dvd.iso",
        "OS_Family": "rhel",
        "OS_Version": "9.4"
      }
    ],
    "Rocky": [
      {
        "OS_Name": "rocky-9.4-x86_64",
        "OS_Path": "Rocky-9.4-x86_64-dvd.iso",
        "OS_Family": "rhel",
        "OS_Version": "9.4"
      }
    ]
  }
}
```

### 8.6 `BuildConfig` Additions

```go
type BuildConfig struct {
    // ... existing fields ...
    DistroFamily string  // "ubuntu" | "rhel"
    DistroVersion string // "9.4", "8.10", etc.
}
```

### 8.7 EFI Image

RHEL 8/9 ISOs ship a pre-built `images/efiboot.img`.  Unlike Ubuntu 20.04+ where the Go
builder reconstructs `efi.img` from scratch, for RHEL the safest approach is to **reuse
the original `images/efiboot.img`** and only patch the GRUB config inside it via `mtools`:

```bash
mcopy -i images/efiboot.img ::EFI/BOOT/grub.cfg /tmp/grub.cfg
# edit /tmp/grub.cfg
mcopy -o -i images/efiboot.img /tmp/grub.cfg ::EFI/BOOT/grub.cfg
```

This mirrors the Go builder's existing Ubuntu 18.04 EFI strategy.

---

## 9. Comparison: Ubuntu Autoinstall vs RHEL Kickstart

| Aspect | Ubuntu Subiquity | RHEL Anaconda / Kickstart |
|---|---|---|
| Answer file location on ISO | `autoinstall/user-data` | `/ks.cfg` (root of ISO) |
| Boot trigger | `autoinstall ds=nocloud` kernel param | `inst.ks=cdrom:/ks.cfg` kernel param |
| Disk match by serial | `match: { serial: <val> }` in YAML | `%pre` script → resolve device name → `ignoredisk` |
| Dynamic disk detection | `find_disk.sh` via `early-commands` | `%pre` script writing `/tmp/ks-disk.cfg` |
| Pre-install hook | `early-commands:` list in YAML | `%pre` section |
| Post-install hook | `late-commands:` list in YAML | `%post` section (chroot by default) |
| Package format | `.deb` (apt) | `.rpm` (dnf/rpm) |
| Offline packages | `dpkg -i /cdrom/pool/extra/*.deb` | `rpm -i /mnt/source/extra-rpms/*.rpm` |
| Password hashing | `mkpasswd -m sha-512` | `openssl passwd -6` or `python3 -c "crypt..."` |
| SSH key injection | `authorized-keys:` in YAML | `sshkey --username=<user> "<pubkey>"` |
| IPMI logger path (`%pre`) | `/cdrom/pool/extra/` | `/run/install/repo/extra-rpms/` |
| IPMI logger path (`%post`) | `/cdrom/pool/extra/` | `/mnt/source/extra-rpms/` (nochroot) |

---

## 10. Minimum Viable Kickstart File (copy-paste reference)

```kickstart
# ks.cfg — minimal RHEL 9 autoinstall with dynamic disk detection
# Generated by build-iso-go

%include /tmp/ks-disk.cfg

lang en_US.UTF-8
keyboard us
timezone UTC --utc
network --bootproto=dhcp --onboot=yes
rootpw --iscrypted $6$rounds=4096$salt$hash...
user --name=sysadmin --password=$6$rounds=4096$salt$hash... --iscrypted --groups=wheel
selinux --disabled
firewall --disabled
services --enabled=sshd
reboot --eject

%packages --ignoremissing
@^minimal-environment
ipmitool
net-tools
curl
%end

%pre --interpreter=/bin/bash --log=/tmp/ks-pre.log
modprobe ipmi_devintf ipmi_si ipmi_msghandler 2>/dev/null || true
sleep 2
python3 /run/install/repo/extra-rpms/ipmi_start_logger.py 0x01 2>/dev/null || true

target=""
min_size=0
for disk in $(lsblk -nd -o NAME --exclude 1,2,11 2>/dev/null); do
    dev="/dev/$disk"
    [ -b "$dev" ] || continue
    parts=$(lsblk -n -o TYPE "$dev" 2>/dev/null | grep -c "part")
    [ "$parts" -gt 0 ] && continue
    sigs=$(wipefs "$dev" 2>/dev/null | grep -v "^offset")
    [ -n "$sigs" ] && continue
    nz=$(dd if="$dev" bs=1M count=1 2>/dev/null | tr -d '\0' | wc -c)
    [ "$nz" -gt 512 ] && continue
    size=$(lsblk -ndb -o SIZE "$dev" 2>/dev/null)
    if [ "$min_size" -eq 0 ] || [ "$size" -lt "$min_size" ]; then
        min_size=$size
        target=$disk
    fi
done

if [ -z "$target" ]; then
    echo "[!] No empty disk found" >> /dev/console
    python3 /run/install/repo/extra-rpms/ipmi_start_logger.py 0xEE 2>/dev/null || true
    exit 1
fi

echo "[+] Target disk: $target ($(( min_size / 1024 / 1024 / 1024 ))GB)" >> /dev/console
cat > /tmp/ks-disk.cfg << EOF
ignoredisk --only-use=${target}
clearpart  --all --initlabel --drives=${target}
part /boot/efi --fstype=efi  --size=512  --ondrive=${target} --fsoptions="umask=0077"
part /boot     --fstype=xfs  --size=1024 --ondrive=${target}
part /         --fstype=xfs  --size=-1   --grow --ondrive=${target}
EOF
%end

%post --nochroot --interpreter=/bin/bash --log=/mnt/sysimage/var/log/ks-post.log
python3 /mnt/source/extra-rpms/ipmi_start_logger.py 0xAA 2>/dev/null || true
%end
```

---

## 11. Implementation Checklist for Go Builder RHEL Support

- [ ] Add `DistroFamily` / `DistroVersion` to `BuildConfig`
- [ ] Implement `detectDistro()` using `.treeinfo` and directory layout probing
- [ ] Add `writeKickstartFile()` with Go template parallel to `writeCloudInitFiles()`
- [ ] Extend `patchGrub()` and `patchIsolinux()` to branch on `DistroFamily`
- [ ] Add RHEL kernel/initrd paths (`images/pxeboot/vmlinuz`, `images/pxeboot/initrd.img`)
- [ ] Add `downloadExtraPackagesRpm()` using `dnf download --resolve`
- [ ] Handle `images/efiboot.img` patching via `mtools` (reuse original EFI image)
- [ ] Add `openssl passwd -6` (or Python `crypt`) for SHA-512 password hashing without `mkpasswd`
- [ ] Extend `file_list.json` schema with `OS_Family` field
- [ ] Add RHEL ISO entries to `iso_repository/file_list.json`
- [ ] Test with Rocky Linux 9.x (freely available, binary-compatible with RHEL 9)
