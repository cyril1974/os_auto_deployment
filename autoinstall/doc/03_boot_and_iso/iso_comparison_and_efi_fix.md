# ISO Comparison: Original vs Custom — Boot Failure Root Cause Analysis

**Date:** 2026-02-25  
**Subject:** Deep comparison between the bootable original Ubuntu 18.04 Server ISO and the non-bootable custom autoinstall ISO, leading to the discovery and resolution of the EFI boot chain breakage.

---

## 1. Problem Statement

The custom autoinstall ISO (`ubuntu_18.04.6_server_amd64_autoinstall_*.iso`) produced a **solid black screen** when booted on a physical machine, while the original ISO (`ubuntu-18.04.6-server-amd64.iso`) booted successfully on the same machine.

Both ISOs were verified to have identical `xorriso` build parameters (via `-report_el_torito as_mkisofs`), yet only the original worked.

---

## 2. Comparison Methodology

Two ISOs were mounted and compared layer by layer:

| ISO | Path |
|-----|------|
| **Original** | `iso_repository/Ubuntu/ubuntu-18.04.6-server-amd64.iso` |
| **Custom** | `output_custom_iso/ubuntu_18.04.6_server_amd64_autoinstall_202602251419.iso` |

---

## 3. Comparison Results

### 3.1 File Size

| ISO | Size |
|-----|------|
| Original | 1,010,827,264 bytes (964 MB) |
| Custom | 1,028,653,056 bytes (981 MB) |

**Cause:** The custom ISO contains additional files (`/autoinstall/` directory, `/preseed.cfg`).

### 3.2 Boot Record (xorriso report)

Both ISOs report **identical** El Torito boot parameters:

```
Boot record  : El Torito , MBR isohybrid cyl-align-on GPT APM
-partition_cyl_align on
-partition_offset 0
-partition_hd_cyl 64
-partition_sec_hd 32
--mbr-force-bootable
-apm-block-size 2048
-iso_mbr_part_type 0x00
-c '/isolinux/boot.cat'
-b '/isolinux/isolinux.bin'
-no-emul-boot
-boot-load-size 4
-boot-info-table
-eltorito-alt-boot
-e '/boot/grub/efi.img'
-no-emul-boot
-boot-load-size 4800
-isohybrid-gpt-basdat
-isohybrid-apm-hfsplus
```

**Result:** ✅ Identical — not the cause.

### 3.3 MBR Bootstrap Code (first 432 bytes)

```
Original MBR bootstrap (432 bytes): identical to Custom
```

**Result:** ✅ Identical — not the cause.

### 3.4 MBR Partition Table

| Property | Original | Custom |
|----------|----------|--------|
| Partition 1 (ISO9660) | Start=0, End=1974271, 964MB, Boot=* | Start=0, End=2009087, 981MB, Boot=* |
| Partition 2 (EFI) | Start=1510808, 2.3MB, Type=EF | Start=8596, 2.3MB, Type=EF |
| Disk Identifier | 0x03aa559f | 0x7646f3c2 |

**Result:** ℹ️ Different sector offsets due to different ISO sizes. This is expected and normal.

### 3.5 Kernel and Initrd

| File | Original | Custom |
|------|----------|--------|
| `/install/vmlinuz` | 8,453,792 bytes (Sep 2021) | 8,453,792 bytes (Sep 2021) |
| `/install/initrd.gz` | 16,798,563 bytes (Sep 2021) | 16,798,563 bytes (Sep 2021) |

**Result:** ✅ Identical — not the cause.

### 3.6 EFI Boot Files (on ISO9660 filesystem)

| File | Original | Custom |
|------|----------|--------|
| `/EFI/BOOT/BOOTx64.EFI` | 955,656 bytes | 955,656 bytes |
| `/EFI/BOOT/grubx64.efi` | 1,456,000 bytes | 1,456,000 bytes |

**Result:** ✅ Identical — not the cause.

### 3.7 GRUB Config (`/boot/grub/grub.cfg` on ISO9660)

| Property | Original | Custom |
|----------|----------|--------|
| timeout | 30 | 0 |
| First menuentry | "Install Ubuntu Server" | "Auto Install Ubuntu Server" |
| Kernel params | `file=/cdrom/preseed/ubuntu-server.seed quiet ---` | `file=/cdrom/preseed.cfg auto=true priority=critical console=ttyS0,115200n8 --- quiet` |

**Result:** ℹ️ Intentionally different (this is the purpose of the customization).

### 3.8 ISOLINUX Config (`/isolinux/txt.cfg`)

| Property | Original | Custom |
|----------|----------|--------|
| append line | `file=/cdrom/preseed/ubuntu-server.seed vga=788 initrd=/install/initrd.gz quiet ---` | `file=/cdrom/preseed.cfg auto=true priority=critical initrd=/install/initrd.gz console=ttyS0,115200n8 quiet ---` |

**Result:** ℹ️ Intentionally different.

### 3.9 ISOLINUX timeout (`/isolinux/isolinux.cfg`)

| Property | Original | Custom |
|----------|----------|--------|
| timeout | 300 | 10 |

**Result:** ℹ️ Intentionally different.

### 3.10 Additional Files in Custom ISO

| File | Present in Original | Present in Custom |
|------|---------------------|-------------------|
| `/autoinstall/` (directory) | ❌ | ✅ |
| `/preseed.cfg` | ❌ | ✅ (2,172 bytes) |

**Result:** ℹ️ New files added intentionally. Harmless.

### 3.11 ⚠️ `boot/grub/efi.img` (THE CRITICAL DIFFERENCE)

| Property | Original | Custom (broken) |
|----------|----------|-----------------|
| File size | 2,457,600 bytes | 2,457,600 bytes |
| **MD5 checksum** | **e1fb948511b0b5a8dcea206a334d527f** | **e485e5d3df5828bb62869d0942c9bc23** |

**The checksums differed!**

#### Contents inside `efi.img`:

| File | Original | Custom (broken) |
|------|----------|-----------------|
| `/efi/boot/bootx64.efi` | ✅ (955,656 bytes) | ✅ (955,656 bytes, identical) |
| `/efi/boot/grubx64.efi` | ✅ (1,456,000 bytes) | ✅ (1,456,000 bytes, identical) |
| `/boot/grub/grub.cfg` | **❌ NOT PRESENT** | **✅ PRESENT (2,437 bytes)** |

**Result:** 🔴 **ROOT CAUSE FOUND** — The custom ISO had an extra `grub.cfg` injected into `efi.img` that the original does not have.

---

## 4. Root Cause: UEFI Boot Chain Breakdown

### 4.1 How the Original 18.04 UEFI Boot Chain Works

The `grubx64.efi` binary has an **embedded startup script** (extracted via `strings`):

```grub
# Step 1: Find the ISO filesystem
if [ -z "$prefix" -o ! -e "$prefix" ]; then
    if ! search --file --set=root /.disk/info; then
        search --file --set=root /.disk/mini-info
    fi
    set prefix=($root)/boot/grub
fi

# Step 2: Load partition modules, then the real grub.cfg
if [ -e $prefix/x86_64-efi/grub.cfg ]; then
    source $prefix/x86_64-efi/grub.cfg
elif [ -e $prefix/grub.cfg ]; then
    source $prefix/grub.cfg
else
    source $cmdpath/grub.cfg
fi
```

The `/boot/grub/x86_64-efi/grub.cfg` file (present in both ISOs, identical) contains:

```grub
insmod part_acorn
insmod part_amiga
... (partition driver modules)
insmod part_sunpc
configfile /boot/grub/grub.cfg    ← loads the REAL menu
```

#### Normal flow (Original ISO):
```
UEFI firmware
  → loads efi.img FAT partition
  → BOOTx64.EFI → grubx64.efi
  → embedded script runs:
      1. $prefix is empty → search --file --set=root /.disk/info
         → Finds ISO9660 filesystem → sets $root to ISO9660
      2. set prefix=($root)/boot/grub   → points to ISO9660
      3. $prefix/x86_64-efi/grub.cfg exists on ISO9660 → source it
      4. configfile /boot/grub/grub.cfg  → loads menu from ISO9660
  → Menu shows "Install Ubuntu Server"
  → linux /install/vmlinuz ...        ← found on ISO9660 ✅
```

### 4.2 What Went Wrong (Custom ISO with patched efi.img)

When we injected `/boot/grub/grub.cfg` into `efi.img`, the startup logic changed:

```
UEFI firmware
  → loads efi.img FAT partition
  → BOOTx64.EFI → grubx64.efi
  → embedded script runs:
      1. $prefix might initially point to the EFI FAT partition
         (before search runs, or if search fails/is slow)
      2. $prefix/grub.cfg EXISTS inside efi.img! → source it directly
         (skips x86_64-efi/grub.cfg and the search command entirely)
      3. grub.cfg tries: loadfont /boot/grub/font.pf2  → not on FAT → fails silently
      4. grub.cfg tries: linux /install/vmlinuz ...
         → $root still points to EFI FAT partition
         → /install/vmlinuz does NOT exist on the 2.3MB FAT partition
         → GRUB error → black screen ❌
```

The key insight: **the `elif [ -e $prefix/grub.cfg ]` check finds the injected grub.cfg on the EFI FAT partition BEFORE the `search` command can redirect `$root` to the ISO9660 filesystem.**

---

## 5. Resolution

### Action Taken
**Removed all `efi.img` patching for 18.04.** The build script now preserves the original `efi.img` byte-for-byte.

The patched `grub.cfg` on the ISO9660 filesystem (`/boot/grub/grub.cfg`) is sufficient — GRUB's embedded `search → configfile` chain naturally loads it from the correct filesystem.

### Verification After Fix

```
efi.img MD5 (Original): e1fb948511b0b5a8dcea206a334d527f
efi.img MD5 (Fixed):    e1fb948511b0b5a8dcea206a334d527f  ← IDENTICAL ✅
```

### Code Change

In `build-ubuntu-autoinstall-iso.sh`, the 18.04 branch now reads:

```bash
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
  echo "[*] 18.04 Legacy ISO: using original efi.img (no modification needed)"
```

---

## 6. Key Takeaway

When customizing Ubuntu ISOs, **never modify the internal `efi.img`** unless you fully understand the embedded GRUB startup script. The UEFI boot chain relies on `grubx64.efi`'s embedded `search` command to locate the correct filesystem at runtime. Injecting files into the EFI FAT partition can short-circuit this logic and cause GRUB to load configurations in the wrong filesystem context, leading to silent boot failures.

The correct approach is to **only modify files on the ISO9660 filesystem** (e.g., `/boot/grub/grub.cfg`, `/isolinux/txt.cfg`, `/preseed.cfg`) and let the original EFI boot chain discover them naturally.

---

## 7. Second Boot Failure: Black Screen Despite Identical efi.img (Round 2)

### 7.1 Symptom

After fixing the `efi.img` issue (Section 5), the rebuilt ISO still showed a **black screen** on the physical server when booted via BMC virtual media (NFS). The original ISO displayed the GRUB menu normally on the same machine.

### 7.2 Exhaustive Re-comparison

A second round of comparison confirmed:
- **`efi.img`**: ✅ Byte-identical (`e1fb948511b0b5a8dcea206a334d527f`)
- **All xorriso build parameters**: ✅ Identical (20+ flags match)
- **MBR bootstrap code**: ✅ Identical
- **Kernel, initrd, EFI binaries**: ✅ Identical
- **Boot catalog and El Torito entries**: ✅ Valid (LBAs point to correct locations)

### 7.3 QEMU Verification

Both ISOs were tested in QEMU under UEFI (OVMF) and BIOS modes:

| Mode | Original | Custom |
|------|----------|--------|
| **UEFI** | ✅ Boots, kernel loads | ✅ Boots, kernel loads, d-i starts |
| **BIOS** | ✅ Boots | ✅ Boots, "Detecting hardware..." |

**Conclusion: The ISO is structurally sound and boots correctly.** The failure was not in the ISO format.

### 7.4 Root Cause: Display/Console Settings

The black screen was caused by **two settings working together** that prevented any visible output on the BMC KVM console:

| Setting | Original | Custom (broken) | Effect |
|---------|----------|-----------------|--------|
| `set timeout=` | **30** | **0** | GRUB skips menu display entirely — user sees nothing |
| `console=` | *(none)* | **`ttyS0,115200n8` only** | Kernel and d-i output goes to serial port only, not video |
| `quiet` | yes | yes | Suppresses kernel boot messages |

The combined effect:
1. **GRUB timeout=0** → Menu never appears (instant boot to default entry)
2. **`console=ttyS0,115200n8`** → All kernel and installer output redirected to serial port
3. **No `console=tty0`** → Video/KVM console receives no output at all
4. **`quiet`** → Even if video were active, kernel messages would be suppressed

The user, viewing via BMC IPMI KVM (which is essentially a video console), saw nothing but a black screen.

### 7.5 Resolution

Three changes were made:

1. **GRUB timeout**: `0` → `5` (menu visible for 5 seconds)
2. **Dual console**: Added `console=tty0` before `console=ttyS0,115200n8`
   - `console=tty0` sends output to the video/KVM console
   - `console=ttyS0,115200n8` sends output to serial for logging
   - Both consoles are active simultaneously
3. **Removed `quiet`**: Boot messages now visible for debugging

#### Final GRUB configuration:
```grub
set timeout=5
menuentry "Auto Install Ubuntu Server" {
    set gfxpayload=keep
    linux   /install/vmlinuz file=/cdrom/preseed.cfg auto=true priority=critical console=tty0 console=ttyS0,115200n8 ---
    initrd  /install/initrd.gz
}
```

#### Final ISOLINUX configuration:
```
append  file=/cdrom/preseed.cfg auto=true priority=critical initrd=/install/initrd.gz console=tty0 console=ttyS0,115200n8  ---
```

### 7.6 Key Takeaway

When deploying via **BMC virtual media / IPMI KVM**:
- Always include `console=tty0` in kernel parameters to ensure the video console receives output
- Use `timeout >= 5` in GRUB to confirm the bootloader is working
- Avoid `quiet` during initial testing
- `console=ttyS0` alone redirects ALL output to serial, leaving the KVM video blank

---

## 8. Third Boot Issue: Kernel Boots but Installer Invisible (Round 3)

### 8.1 Symptom

After fixing the timeout and adding `console=tty0` (Section 7), the rebuilt ISO showed progress: the GRUB menu appeared, the kernel loaded, and hardware detection messages scrolled on the BMC KVM screen. However, the screen appeared to **hang after ~52 seconds** at the last kernel message:

```
[   52.852105] [drm] Initialized ast 0.1.0 20120228 for 0000:2b:00.0 on minor 0
```

The system showed kernel messages including:
- USB device enumeration (OpenBMC Virtual Keyboard, Mouse, Ethernet, Virtual Media Device)
- AST2500 DRM framebuffer initialization (`fb: switching to astdrmfb from EFI VGA`)
- Console switching to colour frame buffer device 128x48
- USB Mass Storage detected (virtual CDROM)

After these messages, **nothing more appeared for 30+ minutes**.

### 8.2 Analysis

The kernel was **not hung**. All hardware was detected successfully, including the BMC virtual media CDROM. The debian-installer (d-i) was actually running — but its ncurses TUI was being displayed on the **serial port** instead of the video console.

### 8.3 Root Cause: Linux `console=` Parameter Ordering

In Linux, when multiple `console=` parameters are specified on the kernel command line:

1. **ALL listed consoles** receive kernel log messages (`printk` output)
2. The **LAST `console=` parameter** becomes `/dev/console` — the **primary console**
3. User-space programs that open `/dev/console` (like the debian-installer) display their UI on the **primary console only**

Our previous configuration had:

```
console=tty0 console=ttyS0,115200n8
```

This meant:
| Console | Role | What it received |
|---------|------|-----------------|
| `tty0` (video/KVM) | Secondary | Kernel messages only |
| `ttyS0` (serial) | **Primary** (`/dev/console`) | Kernel messages **+ d-i TUI** |

The user, viewing via BMC IPMI KVM (video console), saw:
- ✅ Kernel boot messages (both consoles get these)
- ❌ Debian-installer TUI (went to serial only)
- Result: Screen appeared "frozen" after the last kernel message

### 8.4 Why the Original ISO Didn't Have This Problem

The original Ubuntu 18.04 ISO uses:

```
file=/cdrom/preseed/ubuntu-server.seed quiet ---
```

**No `console=` parameter at all.** Without explicit console parameters, the kernel defaults to `tty0` (video) as the only console. All output — kernel messages and d-i TUI — goes to video.

### 8.5 Resolution

Reversed the `console=` parameter order so `tty0` is **last** (= primary):

```diff
- console=tty0 console=ttyS0,115200n8
+ console=ttyS0,115200n8 console=tty0
```

| Console | Role | What it receives |
|---------|------|-----------------|
| `ttyS0` (serial) | Secondary | Kernel messages (for logging) |
| `tty0` (video/KVM) | **Primary** (`/dev/console`) | Kernel messages **+ d-i TUI** ✅ |

#### Final GRUB configuration:
```grub
set timeout=5
menuentry "Auto Install Ubuntu Server" {
    set gfxpayload=keep
    linux   /install/vmlinuz file=/cdrom/preseed.cfg auto=true priority=critical console=ttyS0,115200n8 console=tty0 ---
    initrd  /install/initrd.gz
}
```

#### Final ISOLINUX configuration:
```
append  file=/cdrom/preseed.cfg auto=true priority=critical initrd=/install/initrd.gz console=ttyS0,115200n8 console=tty0  ---
```

### 8.6 Key Takeaway: Linux Console Parameter Rules

```
console=<first> console=<second> console=<third>
         ↑                          ↑
      secondary                  PRIMARY (/dev/console)
      (kernel msgs only)         (kernel msgs + user-space UI)
```

**The LAST `console=` parameter wins.** When deploying via BMC/IPMI KVM:
- `console=tty0` must be **last** to make the video console primary
- `console=ttyS0` should be **first** (secondary) for serial log capture
- Omitting `console=tty0` entirely means only serial gets output
- Multiple consoles all receive `printk` messages, but only the last one gets `/dev/console`

### 8.7 Complete Boot Issue Timeline

| Round | Symptom | Root Cause | Fix |
|-------|---------|------------|-----|
| 1 | Total black screen | `efi.img` patched with extra `grub.cfg`, broke UEFI boot chain | Stop patching `efi.img` for 18.04 |
| 2 | Black screen (no GRUB menu) | `timeout=0` + `console=ttyS0` only | Set `timeout=5`, add `console=tty0` |
| 3 | Kernel boots then appears hung | `console=tty0` before `console=ttyS0` → d-i TUI on serial | Reverse order: `ttyS0` first, `tty0` last |
