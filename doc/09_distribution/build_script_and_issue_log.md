# Build Script Reference and Issue Log

This document covers the current state of the `os-deploy` build system,
known issues encountered during development and deployment, and the
resolution for each.

---

## 1. Build System Overview

### 1.1 Components

```
os_auto_deployment/
├── build-cli.sh              ← Main Nuitka build script
├── build-requirements.txt    ← pip packages required to build
├── Dockerfile.build          ← Ubuntu 22.04 container for glibc-compatible builds
├── cli_entry.py              ← Nuitka entry point (imports os_deployment.main)
├── pyproject.toml            ← Version source
├── src/os_deployment/        ← Python source (compiled to native code)
├── autoinstall/build-iso-go/ ← Go ISO builder (embedded into binary)
│   ├── main.go
│   ├── embed.go
│   ├── build.sh              ← Go build script (runs go test + go build)
│   └── go.mod / go.sum
└── dist/
    └── os-deploy-<version>   ← Produced standalone binary
```

### 1.2 Build Flow

```
bash build-cli.sh [--docker] [--clean] [--check]
        │
        ├─ (--docker) ──► docker run ubuntu:22.04 bash build-cli.sh
        │
        ├─ Check system prerequisites (python3, gcc, patchelf)
        ├─ Create / reuse .venv/  (or /tmp/.venv-docker inside container)
        ├─ pip install -r build-requirements.txt
        │
        ├─ Go build (autoinstall/build-iso-go/build.sh)
        │   ├─ Stage embed assets (scripts/, startup.nsh, etc.)
        │   ├─ go test ./...        ← must pass before build
        │   └─ go build -o build-iso
        │
        └─ Nuitka onefile compilation
            ├─ --include-package=os_deployment,requests,urllib3,certifi,tomli
            ├─ --include-data-files=build-iso=autoinstall/build-iso-go/build-iso
            └─ Output: dist/os-deploy  →  renamed to  dist/os-deploy-<version>
```

### 1.3 Build Options

| Flag | Effect |
|------|--------|
| _(none)_ | Build on host system (glibc = host version) |
| `--docker` | Build inside Ubuntu 22.04 container (glibc ≥ 2.34 compatible) |
| `--clean` | Remove `dist/`, `build/nuitka/`, `.venv/` before building |
| `--check` | Verify prerequisites only, no build |

### 1.4 Go Build Script (`autoinstall/build-iso-go/build.sh`)

The Go binary cannot use `//go:embed` on files outside the package directory.
Since the assets (`scripts/`, `startup.nsh`, etc.) live in the parent
`autoinstall/` directory, `build.sh` stages them before the build:

```bash
# Stage assets into build-iso-go/ for go:embed
for asset in startup.nsh ipmi_start_logger.py package_list; do
    cp autoinstall/$asset  build-iso-go/$asset   # copied in
done
cp -r autoinstall/scripts  build-iso-go/scripts  # copied in

go test ./...        # must pass before build proceeds
go build -o build-iso .

# Cleanup: trap EXIT removes all staged files
```

### 1.5 Embedded Assets and Runtime Paths

At runtime the `build-iso` binary:
1. Extracts embedded assets to `/tmp/build-iso-assets-XXXXXXXX/` (`scriptDir`)
2. Writes work files to `<cwd>/workdir_custom_iso/<BUILD_ID>/`
3. Writes output ISO to `<cwd>/output_custom_iso/<BUILD_ID>/`
4. Stores apt package cache at `~/.cache/build-iso/apt_cache/<codename>/`
5. Cleans up `/tmp/build-iso-assets-XXXXXXXX/` on exit

```
/tmp/build-iso-assets-XXXXXXXX/   ← deleted on exit (embed assets only)
<cwd>/workdir_custom_iso/<id>/    ← ISO workspace, deleted on exit
<cwd>/output_custom_iso/<id>/     ← output ISO  ← PRESERVED
~/.cache/build-iso/apt_cache/     ← apt package cache  ← PRESERVED
```

---

## 2. Issue Log

### Issue 1 — glibc Version Mismatch on Target Server

**Date:** 2026-04-15
**Symptom:**

```
./os-deploy-1.0.0: /lib/x86_64-linux-gnu/libm.so.6: version `GLIBC_2.38'
    not found (required by ./os-deploy-1.0.0)
./os-deploy-1.0.0: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.38'
    not found (required by ./os-deploy-1.0.0)
```

**Root Cause:**

Nuitka compiles Python to C and links against the host system's glibc.
The build host was Ubuntu 25.04 (glibc 2.41). The target server had an
older glibc that did not have `GLIBC_2.38` symbols.

**Resolution:**

Added `Dockerfile.build` based on Ubuntu 22.04 (glibc 2.35) and a
`--docker` flag to `build-cli.sh`. Building inside the container
produces a binary that requires glibc ≥ **2.34**, compatible with
Ubuntu 22.04+, Debian 12+, and RHEL 9+.

```bash
# Build glibc-compatible binary
bash build-cli.sh --docker
```

The container image is tagged `os-deploy-builder` and reused on
subsequent runs. `VENV_DIR=/tmp/.venv-docker` is passed to prevent
the container from trying to reuse the host `.venv/` which contains
hard-coded host paths.

**Files changed:** `Dockerfile.build` (new), `build-cli.sh`

---

### Issue 2 — `ModuleNotFoundError: No module named 'tomllib'`

**Date:** 2026-04-16
**Symptom:**

```
Traceback (most recent call last):
  File ".../cli_entry.py", line 7, in <module>
  File ".../os_deployment/main.py", line 5, in <module>
ModuleNotFoundError: No module named 'tomllib'
```

**Root Cause:**

`tomllib` was added to the Python standard library in **Python 3.11**.
The Docker build image uses Ubuntu 22.04 / **Python 3.10**, which does
not have it. The binary was compiled with Python 3.10 (inside the
container) and crashed on startup because `import tomllib` failed.

**Resolution:**

Changed `main.py` to use a try/except import chain:

```python
try:
    import tomllib          # Python 3.11+ stdlib
except ImportError:
    try:
        import tomli as tomllib  # backport for Python <= 3.10
    except ImportError:
        tomllib = None
```

Added `tomli>=2.0; python_version < "3.11"` to `build-requirements.txt`
and `--include-package=tomli` to `build-cli.sh` so Nuitka bundles the
backport when building on Python 3.10.

**Files changed:** `src/os_deployment/main.py`, `build-requirements.txt`,
`build-cli.sh`

---

### Issue 3 — `exec: "mkpasswd": executable file not found in $PATH`

**Date:** 2026-04-16
**Symptom:**

```
[ERROR] failed to hash password: exec: "mkpasswd": executable file not found in $PATH
```

**Root Cause:**

`build-iso` called `mkpasswd -m sha-512 <password>` (from the `whois`
system package) to produce the SHA-512 crypt password hash for
`user-data`. `mkpasswd` is not installed on the target build server.

**Resolution:**

Replaced the external process call with a pure-Go SHA-512 crypt
implementation via `github.com/GehirnInc/crypt`. This produces
identical `$6$...` hashes to `mkpasswd -m sha-512` with no external
binary dependency.

Before:
```go
hashOut, err := outputOf("mkpasswd", "-m", "sha-512", password)
```

After:
```go
hashOut, err := crypt.New(crypt.SHA512).Generate([]byte(password), nil)
```

**Files changed:** `autoinstall/build-iso-go/main.go`, `go.mod`,
`go.sum`

---

### Issue 4 — Output ISO Deleted Before NFS Copy

**Date:** 2026-04-14
**Symptom:**

```
Custom ISO generated:
  Path: /tmp/build-iso-assets-XXXXXXXX/output_custom_iso/.../ubuntu_*.iso
Error: local file '...' does not exist
```

**Root Cause:**

After embedding assets with `//go:embed`, `scriptDir` pointed to the
extracted temp dir `/tmp/build-iso-assets-XXXXXXXX/`. Both `workDir`
and `outISODir` were anchored inside `scriptDir`, so `defer
os.RemoveAll(assetsDir)` wiped the output ISO before `main.py` could
copy it to NFS.

**Resolution:**

Anchored `workDir` and `outISODir` to `os.Getwd()` (the directory the
binary is invoked from), which is never cleaned up by the binary.

**Files changed:** `autoinstall/build-iso-go/main.go`
(see [debug_output_iso_deleted_before_nfs_copy.md](../../autoinstall/doc/07_debugging/debug_output_iso_deleted_before_nfs_copy.md))

---

### Issue 5 — `pool/extra` Contains No `.deb` Files

**Date:** 2026-04-14
**Symptom:**

ISO built successfully, but `pool/extra/` only contained
`ipmi_start_logger.py`. All 187 packages were missing.

**Root Cause:**

`apt-get download` downloaded `.deb` files to `/tmp/apt-download-xxx/`
(a tmpfs mount). The code used `os.Rename` to move them to
`~/.cache/build-iso/apt_cache/` (on ext4). `os.Rename` cannot cross
filesystem boundaries — it returns `EXDEV` — and the error was silently
discarded (`_ = os.Rename(...)`). Every `.deb` was then deleted by
`defer os.RemoveAll(tmpDir)`.

**Resolution:**

Replaced `os.Rename` with `copyFile` (uses `io.Copy`, works across any
filesystem) followed by `os.Remove` on success.

**Files changed:** `autoinstall/build-iso-go/main.go`
(see [debug_pool_extra_packages_missing.md](../../autoinstall/doc/07_debugging/debug_pool_extra_packages_missing.md))

---

### Issue 6 — Duplicate Progress Bar Printed

**Date:** 2026-04-14
**Symptom:**

Two progress bars appeared in terminal output during package download:

```
Progress: |████████████████████████████████████████| 100.0% Complete

Progress: |                                        | 100.0% Complete
```

**Root Cause:**

`downloadExtraPackages` had a redundant `fmt.Printf` after the loop
that was intended to finalise the bar at 100%. However, `printProgress`
ends with `\n`, leaving the cursor on a new blank line. The `\r` in the
redundant print moved to column 0 of that blank line rather than
overwriting the existing bar, causing a second line to appear.

Since both branches inside the loop (`[cached]` and `[downloading]`)
always call `printProgress(i+1, total, ...)`, the last iteration already
shows 100%. The post-loop print was always redundant.

**Resolution:**

Removed the three lines:
```go
if total > 0 {
    fmt.Printf("\rProgress: |%s| 100.0%% Complete\n", strings.Repeat("█", 40))
}
```

**Files changed:** `autoinstall/build-iso-go/main.go`
(see [debug_duplicate_progress_bar.md](../../autoinstall/doc/07_debugging/debug_duplicate_progress_bar.md))

---

### Issue 7 — apt_cache Destroyed on Every Run

**Date:** 2026-04-14
**Symptom:**

All packages re-downloaded from the internet on every ISO build run.

**Root Cause:**

Before `//go:embed` was added, `scriptDir` was the `autoinstall/`
checkout directory — stable across runs. After embedding, `scriptDir`
was set to `/tmp/build-iso-assets-XXXXXXXX/`, which is wiped by `defer
os.RemoveAll(assetsDir)` on exit. The apt cache at
`scriptDir/apt_cache/` was destroyed with it.

**Resolution:**

Moved the apt cache to the XDG cache directory:
`~/.cache/build-iso/apt_cache/<codename>/`. This path is stable,
per-user, and never cleaned up by the binary. `$XDG_CACHE_HOME` is
respected for CI / shared-cache overrides.

**Files changed:** `autoinstall/build-iso-go/main.go`
(see [apt_cache_persistence_options.md](../../autoinstall/doc/10_apt_cache/apt_cache_persistence_options.md))

---

### Issue 8 — `go:embed` Cannot Follow Symlinks

**Date:** 2026-04-14
**Symptom (during build):**

```
pattern scripts: cannot embed irregular file scripts
pattern ipmi_start_logger.py: no matching files found
```

**Root Cause:**

`//go:embed` rejects symlinks that point outside the package directory.
The `scripts -> ../scripts/` symlink in `build-iso-go/` was flagged as
an "irregular file". The other assets (`startup.nsh`, `package_list`,
`ipmi_start_logger.py`) did not exist inside the package directory at
all.

**Resolution:**

`build.sh` copies the assets into `build-iso-go/` before the build and
removes them afterwards via `trap cleanup EXIT`. The `.gitignore` for
`build-iso-go/` lists all staged files so they are never committed.

**Files changed:** `autoinstall/build-iso-go/build.sh`,
`autoinstall/build-iso-go/.gitignore`
(see [asset_embedding_options.md](../../autoinstall/doc/09_asset_embedding/asset_embedding_options.md))

---

## 3. Build Script Quick Reference

```bash
# Standard build (host glibc — only for dev/test on same OS)
bash build-cli.sh

# Production build — compatible with Ubuntu 22.04+ (glibc ≥ 2.34)
bash build-cli.sh --docker

# Clean rebuild (forces fresh venv and Nuitka cache)
bash build-cli.sh --docker --clean

# Verify prerequisites only
bash build-cli.sh --check

# Rebuild Docker image after Dockerfile.build changes
docker rmi os-deploy-builder
bash build-cli.sh --docker
```

---

## 4. Compatibility Matrix

| Build method | Min target glibc | Min target OS |
|---|---|---|
| `bash build-cli.sh` (Ubuntu 25.04 host) | 2.41 | Ubuntu 25.04 only |
| `bash build-cli.sh --docker` | 2.34 | Ubuntu 22.04+, Debian 12+, RHEL 9+ |

---

## 5. Related Documents

| Document | Topic |
|----------|-------|
| [nuitka_build.md](nuitka_build.md) | Nuitka compilation overview and troubleshooting |
| [asset_embedding_options.md](../../autoinstall/doc/09_asset_embedding/asset_embedding_options.md) | `//go:embed` design and implementation |
| [apt_cache_persistence_options.md](../../autoinstall/doc/10_apt_cache/apt_cache_persistence_options.md) | XDG apt cache design |
| [debug_output_iso_deleted_before_nfs_copy.md](../../autoinstall/doc/07_debugging/debug_output_iso_deleted_before_nfs_copy.md) | Issue 4 details |
| [debug_pool_extra_packages_missing.md](../../autoinstall/doc/07_debugging/debug_pool_extra_packages_missing.md) | Issue 5 details |
| [debug_duplicate_progress_bar.md](../../autoinstall/doc/07_debugging/debug_duplicate_progress_bar.md) | Issue 6 details |
