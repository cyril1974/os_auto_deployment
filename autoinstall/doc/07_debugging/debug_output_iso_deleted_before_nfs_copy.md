# Bug: Output ISO Deleted Before NFS Copy

## Symptom

After the Go ISO builder finishes successfully, `main.py` reports:

```
Custom ISO generated:
  Path: /tmp/build-iso-assets-XXXXXXXX/output_custom_iso/<BUILD_ID>/<name>_autoinstall_<ts>.iso
Error: local file '/tmp/build-iso-assets-XXXXXXXX/output_custom_iso/...' does not exist
[...] Deploy ... to NFS Server (10.x.x.x) ...
```

The ISO is reported as created, then immediately reported as missing. The NFS
copy fails because the file no longer exists on disk.

---

## Root Cause

The issue was introduced when `//go:embed` asset bundling was added
(see `doc/09_asset_embedding/asset_embedding_options.md`).

Before `//go:embed`, `scriptDir` pointed to the `autoinstall/` checkout
directory on disk — a stable, persistent location.

After `//go:embed`, `scriptDir` is set to a **temporary extraction directory**:

```go
assetsDir, err := extractEmbeddedAssets()   // → /tmp/build-iso-assets-XXXXXXXX/
// ...
defer os.RemoveAll(assetsDir)               // deleted on exit
scriptDir := assetsDir
```

`workDir` and `outISODir` were both anchored to `scriptDir`:

```go
workDir,   _ = filepath.Abs(filepath.Join(scriptDir, "workdir_custom_iso",  buildID))
outISODir, _ = filepath.Abs(filepath.Join(scriptDir, "output_custom_iso",   buildID))
```

This placed the output ISO inside the temp dir:

```
/tmp/build-iso-assets-XXXXXXXX/
├── scripts/          ← embedded assets (needed only during build)
├── startup.nsh
├── ipmi_start_logger.py
├── package_list
├── workdir_custom_iso/<BUILD_ID>/   ← ISO workspace (deleted intentionally)
└── output_custom_iso/<BUILD_ID>/
    └── ubuntu_22.04.5_..._autoinstall_....iso   ← OUTPUT ISO (deleted too!)
```

Execution order on exit:

```
1. defer workDir cleanup  → /tmp/build-iso-assets-XXXXXXXX/workdir_custom_iso/ deleted  ✓ intended
2. defer assetsDir cleanup → /tmp/build-iso-assets-XXXXXXXX/ deleted (including output ISO)  ✗ BUG
3. main.py attempts to read the ISO → file not found
```

---

## Fix

Anchor `workDir` and `outISODir` to the **current working directory** instead
of `scriptDir`. The current working directory is stable and never cleaned up
by the Go binary.

### Change in `autoinstall/build-iso-go/main.go`

Before:
```go
// Build ID and directories — all anchored to scriptDir (autoinstall/)
rand.Seed(time.Now().UnixNano())
buildID := fmt.Sprintf("%s_%04d", time.Now().Format("20060102150405"), rand.Intn(9999))
workDir,  _ := filepath.Abs(filepath.Join(scriptDir, "workdir_custom_iso", buildID))
outISODir, _ := filepath.Abs(filepath.Join(scriptDir, "output_custom_iso", buildID))
```

After:
```go
// Build ID and directories — anchored to the current working directory, NOT
// scriptDir. scriptDir now points to the embedded-assets temp dir which is
// deleted on exit; placing workDir/outISODir there would destroy the output
// ISO before the caller (main.py / NFS copy) can use it.
rand.Seed(time.Now().UnixNano())
buildID := fmt.Sprintf("%s_%04d", time.Now().Format("20060102150405"), rand.Intn(9999))
cwd, _ := os.Getwd()
workDir,  _ := filepath.Abs(filepath.Join(cwd, "workdir_custom_iso", buildID))
outISODir, _ := filepath.Abs(filepath.Join(cwd, "output_custom_iso", buildID))
```

---

## Directory Layout After Fix

```
/tmp/build-iso-assets-XXXXXXXX/     ← deleted on exit (embed assets only)
    scripts/
    startup.nsh
    ipmi_start_logger.py
    package_list

<cwd>/                              ← current working directory (stable)
    workdir_custom_iso/<BUILD_ID>/  ← ISO workspace, deleted on exit ✓
    output_custom_iso/<BUILD_ID>/
        ubuntu_22.04.5_..._autoinstall_....iso  ← OUTPUT ISO preserved ✓

~/.cache/build-iso/apt_cache/       ← apt cache (XDG, persistent)
```

---

## Verification Steps

1. Run `bash autoinstall/build-iso-go/build.sh` — all tests pass, binary built.
2. Run `bash build-cli.sh` — Nuitka `os-deploy` binary rebuilt.
3. Execute a full ISO build; confirm the ISO path reported under
   `Custom ISO generated:` exists in `<cwd>/output_custom_iso/` after the
   binary exits.

---

## Related

- `doc/09_asset_embedding/asset_embedding_options.md` — describes the
  `//go:embed` design that introduced `scriptDir` as a temp dir
- `doc/10_apt_cache/apt_cache_persistence_options.md` — describes the same
  class of problem for `apt_cache/`, fixed by using `~/.cache/build-iso/`
