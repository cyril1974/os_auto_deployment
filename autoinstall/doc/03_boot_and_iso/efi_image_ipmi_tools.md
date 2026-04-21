# EFI Image: IPMI Tool Embedding

**Date:** 2026-04-21  
**Commit:** `eef1212`  
**Files Changed:**

| File | Change |
|---|---|
| `autoinstall/build-iso-go/main.go` | Modified — `buildISO()` now copies both EFI tools into the EFI image root |
| `autoinstall/scripts/IpmiTool.efi` | New — UEFI-native IPMI utility |
| `autoinstall/scripts/ipmicmdtoolX64.efi` | New — Alternative UEFI IPMI command tool (x64) |

---

## Background

When the server boots from the custom autoinstall ISO via UEFI, the `startup.nsh` script runs inside the UEFI Shell environment. Having IPMI tools available as UEFI-native `.efi` executables (in the same location as `startup.nsh`) allows direct BMC communication from within the UEFI Shell before the OS installer takes over — useful for pre-install diagnostics, boot-phase telemetry, or manual BMC queries via KVM.

---

## What Changed

### `autoinstall/scripts/` — New EFI tool files

Two UEFI-native EFI executables are now tracked in the repository under `autoinstall/scripts/`:

| File | Description |
|---|---|
| `IpmiTool.efi` | UEFI Shell IPMI utility (15 KB) |
| `ipmicmdtoolX64.efi` | UEFI Shell IPMI command tool, x64 (137 KB) |

These files are embedded into the self-contained `build-iso-go` binary at compile time via the existing `//go:embed scripts` directive in `embed.go` — no changes to the embed directive were needed.

### `autoinstall/build-iso-go/main.go` — `buildISO()` function

In the Ubuntu 20.04+ EFI image creation path (inside the `else` branch of the `cfg.Is1804` check), the following logic was added **immediately after** the `startup.nsh` copy block:

```go
ipmiToolEfi := filepath.Join(cfg.ScriptDir, "scripts/IpmiTool.efi")
if fileExists(ipmiToolEfi) {
    logf("Copying IpmiTool.efi to EFI image root...")
    run("mcopy", "-i", efiImg, ipmiToolEfi, "::/IpmiTool.efi")
} else {
    warnf("IpmiTool.efi not found at %s", ipmiToolEfi)
}
ipmiCmdToolEfi := filepath.Join(cfg.ScriptDir, "scripts/ipmicmdtoolX64.efi")
if fileExists(ipmiCmdToolEfi) {
    logf("Copying ipmicmdtoolX64.efi to EFI image root...")
    run("mcopy", "-i", efiImg, ipmiCmdToolEfi, "::/ipmicmdtoolX64.efi")
} else {
    warnf("ipmicmdtoolX64.efi not found at %s", ipmiCmdToolEfi)
}
```

**Design decisions:**
- Follows the exact same pattern as the existing `startup.nsh` copy (non-fatal `warnf` on missing file, `mcopy -i <efiImg>` to EFI root `::/<filename>`).
- Resolves the source path from `cfg.ScriptDir` — which points to the extracted embedded-assets temp directory — so it works correctly when the binary is invoked from any working directory.
- Only applies to the 20.04+ path; no changes are made to the 18.04 legacy ISO path.

---

## Resulting EFI Image Layout

After the ISO build, the EFI image root (`::/ `) will contain:

```
::/
├── EFI/
│   └── BOOT/
│       ├── bootx64.efi
│       ├── grubx64.efi
│       ├── mmx64.efi
│       └── grub.cfg
├── boot/
│   └── grub/
│       └── (grub modules, fonts, grub.cfg)
├── startup.nsh          ← existing
├── IpmiTool.efi         ← NEW
└── ipmicmdtoolX64.efi   ← NEW
```

---

## Usage from UEFI Shell

Once the server boots to the UEFI Shell via the autoinstall ISO, the tools are accessible from the drive root:

```shell
# Navigate to the ISO filesystem (e.g. fs0:)
fs0:

# Run IPMI tool
IpmiTool.efi <args>

# Run alternative IPMI command tool
ipmicmdtoolX64.efi <args>
```

The exact command syntax depends on each tool's own help output (invoke with no arguments or `/?`).

---

## Notes

- The `scripts/` directory is already embedded at compile time via `//go:embed scripts` in `embed.go`. No rebuild of `embed.go` is required.
- The warning path (`warnf`) is non-fatal — a missing EFI file will print a warning but will not abort the ISO build.
- This change only affects the **EFI image** (`/tmp/efi.img`). The main ISO filesystem is unchanged.
