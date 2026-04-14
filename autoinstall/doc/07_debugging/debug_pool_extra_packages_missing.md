# Bug: Offline Packages Missing from ISO pool/extra

## Symptom

The generated autoinstall ISO contains `pool/extra/ipmi_start_logger.py` but
no `.deb` package files, even though the build log reports downloading
packages successfully:

```
[*] Downloading 187 package(s) for jammy...
Progress: |████████████████████████████████████████| 100.0% Complete
```

Inspecting the ISO confirms the empty pool:

```bash
mount -o loop ubuntu_22.04.5_live_server_amd64_autoinstall_*.iso /mnt
ls /mnt/pool/extra/
# ipmi_start_logger.py       ← only this file, no .deb files
```

The persistent apt cache directory is also empty after the build:

```
~/.cache/build-iso/apt_cache/jammy/
├── pkgcache.bin
├── srcpkgcache.bin
└── archives/
    └── partial/           ← no .deb files
```

---

## Debug Steps

### 1. Inspect the generated ISO

```bash
sshpass -p 'mitac' ssh root@10.99.236.62 '
  mkdir -p /tmp/iso_inspect
  mount -o loop /home/cyril/nfs/ubuntu_22.04.5_live_server_amd64_autoinstall_202604141049.iso /tmp/iso_inspect
  ls /tmp/iso_inspect/pool/extra/
  ls /tmp/iso_inspect/pool/extra/ | wc -l
  umount /tmp/iso_inspect
'
```

Result: only `ipmi_start_logger.py` — zero `.deb` files.

### 2. Check the persistent apt cache

```bash
find ~/.cache/build-iso/apt_cache/jammy -type f
ls -la ~/.cache/build-iso/apt_cache/jammy/archives/
```

Result: cache directory exists with `pkgcache.bin` and `srcpkgcache.bin`
(written by `apt-get update`) but **no `.deb` files** in `archives/`.

### 3. Identify the download-to-cache code path

In `downloadExtraPackages()` (`main.go`):

```go
// Download to tmpDir (set as cmd.Dir)
cmd := exec.Command("apt-get", dlArgs...)
cmd.Dir = tmpDir
_ = cmd.Run()

// Move downloaded .deb to persistent cache
debs, _ := filepath.Glob(filepath.Join(tmpDir, "*.deb"))
for _, deb := range debs {
    dest := filepath.Join(persistentCache, "archives", filepath.Base(deb))
    _ = os.Rename(deb, dest)    // ← error silently discarded
}
```

`tmpDir` is created by `os.MkdirTemp("", "apt-download-*")` → `/tmp/apt-download-xxx/`

`persistentCache` = `~/.cache/build-iso/apt_cache/jammy` → `/root/.cache/...` (root filesystem)

### 4. Check filesystem boundaries

```bash
df /tmp ~/.cache
findmnt /tmp
```

Result:

```
Filesystem      Mounted on
tmpfs           /tmp           ← tmpfs (separate virtual filesystem)
/dev/vda2       /              ← ext4 root filesystem
```

`/tmp` and `~/.cache` are on **different filesystems**.

### 5. Confirm os.Rename fails across filesystems

`os.Rename` (which calls the `rename(2)` syscall) is a directory-entry
rearrangement within a single filesystem. When source and destination are on
different filesystems, the kernel returns `EXDEV` ("Invalid cross-device
link"). Because the error was silently discarded (`_ = os.Rename(...)`), the
`.deb` file was never moved to the cache.

After `downloadExtraPackages` returns, `defer os.RemoveAll(tmpDir)` deleted
every downloaded `.deb` still sitting in `/tmp/apt-download-xxx/`. The
persistent cache remained empty and nothing was ever copied into `pool/extra`.

---

## Root Cause

`os.Rename` fails with `EXDEV` when moving files across filesystem boundaries
(`/tmp` tmpfs → root ext4). The error was silently ignored, so every
downloaded `.deb` was left in the temporary download directory and deleted
when the function returned via `defer os.RemoveAll(tmpDir)`. As a result:

- The persistent cache (`~/.cache/build-iso/apt_cache/`) stayed empty
- The "copy from cache to ISO extra pool" loop found no files and copied nothing
- `pool/extra/` in the ISO contained only `ipmi_start_logger.py`

---

## Resolution

Replaced `os.Rename` with `copyFile` (which uses `io.Copy` across any
filesystem) followed by `os.Remove` to clean up the source.

### Change in `autoinstall/build-iso-go/main.go`

Before:
```go
// Move downloaded .deb to persistent cache
debs, _ := filepath.Glob(filepath.Join(tmpDir, "*.deb"))
for _, deb := range debs {
    dest := filepath.Join(persistentCache, "archives", filepath.Base(deb))
    _ = os.Rename(deb, dest)
}
```

After:
```go
// Move downloaded .deb to persistent cache.
// os.Rename fails across filesystem boundaries (e.g. /tmp on tmpfs →
// ~/.cache on ext4) with EXDEV. Use copy+remove so it always works.
debs, _ := filepath.Glob(filepath.Join(tmpDir, "*.deb"))
for _, deb := range debs {
    dest := filepath.Join(persistentCache, "archives", filepath.Base(deb))
    if err := copyFile(deb, dest); err == nil {
        _ = os.Remove(deb)
    }
}
```

`copyFile` reads the source and writes the destination using `io.Copy`,
which works regardless of whether source and destination are on the same
filesystem. The source is only removed on successful copy; a failed copy
leaves the original intact (and it will be cleaned up by `defer
os.RemoveAll(tmpDir)` as before).

---

## Expected Behaviour After Fix

First run — packages downloaded and cached:

```
[*] Downloading 187 package(s) for jammy...
Progress: |████████████████████████████████████████| 100.0% Complete
```

Cache populated:
```
~/.cache/build-iso/apt_cache/jammy/archives/
├── containerd.io_1.7.x_amd64.deb
├── docker-ce_27.x_amd64.deb
├── ...
└── (187 .deb files)
```

ISO pool populated:
```
pool/extra/
├── containerd.io_1.7.x_amd64.deb
├── docker-ce_27.x_amd64.deb
├── ipmi_start_logger.py
└── ...
```

Subsequent runs — all packages resolved from cache (no re-download):
```
Progress: |████████████████████████████████████████| 100.0% Complete  [cached]
```

---

## Related

- `doc/10_apt_cache/apt_cache_persistence_options.md` — describes why
  `~/.cache/build-iso/` was chosen as the cache location (XDG Option B)
- `doc/09_asset_embedding/asset_embedding_options.md` — explains why
  `scriptDir` is now a temp dir, which necessitated the XDG cache change
