# apt_cache Persistence — Design Options

## Problem

The Go ISO builder downloads Ubuntu packages via `apt-get -d` into a
`apt_cache/<codename>/archives/` directory on the first run. On subsequent
runs it reuses the cached `.deb` files, which avoids re-downloading hundreds
of megabytes each time.

When the binary is built with `//go:embed` (see
`doc/09_asset_embedding/asset_embedding_options.md`), the runtime assets are
extracted to a temporary directory:

```
/tmp/build-iso-assets-xxx/
├── scripts/
│   ├── find_disk.sh
│   └── find_disk_1804.sh
├── startup.nsh
├── ipmi_start_logger.py
└── package_list
```

`scriptDir` is set to this temp dir. The old code placed the cache at:

```
/tmp/build-iso-assets-xxx/apt_cache/<codename>/archives/
```

Because `defer os.RemoveAll(assetsDir)` is called on exit, **the entire cache
is destroyed at the end of every run**. Every invocation re-downloads all
packages from scratch.

---

## Option A — Binary directory (next to the executable)

Place the cache next to the Go binary on disk:

```go
execPath, _ := os.Executable()
cacheDir := filepath.Join(filepath.Dir(execPath), "apt_cache")
```

**How it works:** The cache lives alongside the binary regardless of where it
is installed, so it survives temp-dir cleanup.

**Pros:**
- Simple; always co-located with the binary
- Works without any extra configuration

**Cons:**
- Fails when the binary is on a read-only filesystem (e.g. `/usr/local/bin/`)
- When run via Nuitka onefile, `os.Executable()` resolves to the onefile
  bootstrap path, not the bundled Go binary — the Go binary is never directly
  on disk
- Pollutes the install directory with runtime state
- Different users running the same binary get separate caches in unexpected
  locations

---

## Option B — XDG cache directory (selected) ✓

Use the [XDG Base Directory Specification] to place the cache at
`~/.cache/build-iso/apt_cache/`:

```go
cacheHome := os.Getenv("XDG_CACHE_HOME")
if cacheHome == "" {
    cacheHome = filepath.Join(os.Getenv("HOME"), ".cache")
}
cacheDir := filepath.Join(cacheHome, "build-iso", "apt_cache")
```

**How it works:**

```
First run:   ~/.cache/build-iso/apt_cache/jammy/archives/*.deb  ← downloaded
              
Binary exits: /tmp/build-iso-assets-xxx/ deleted (embed cleanup)
              ~/.cache/build-iso/apt_cache/  PRESERVED

Second run:  apt-get -d hits local cache, skips network download
```

**Pros:**
- Cache survives binary runs, OS reboots, and binary upgrades
- Follows Linux convention — users know where per-user cache lives
- Works equally for the standalone Go binary and the Nuitka `os-deploy` binary
- Respects `$XDG_CACHE_HOME` overrides (useful in CI: set a shared cache)
- No permission issues — always in the invoking user's home directory

**Cons:**
- Cache is per-user (two users building on the same machine each maintain their
  own cache); this is the expected XDG behaviour
- On minimal systems without a `$HOME` set, `filepath.Join("", ".cache", …)`
  produces a relative path — acceptable as an edge case

[XDG Base Directory Specification]: https://specifications.freedesktop.org/basedir-spec/latest/

---

## Option C — `--cache-dir` flag

Add an explicit CLI flag `--cache-dir=<path>`. The caller controls where
packages are cached.

**Pros:**
- Maximum flexibility for CI/shared-cache scenarios

**Cons:**
- Requires the caller to always supply the flag to get persistence
- Without the flag, behaviour is undefined (falls back to a default — which is
  the same problem we started with)
- Extra interface surface

---

## Decision: Option B

Option B was selected because it:

1. Requires **zero configuration** — the cache is always at a predictable,
   persistent, per-user location.
2. Follows an established Linux standard that users and CI pipelines already
   understand.
3. Works identically for the standalone Go binary and the Nuitka `os-deploy`
   binary.
4. Respects `$XDG_CACHE_HOME` for power users who want to redirect it.

---

## Implementation

### Files changed

| File | Change |
|------|--------|
| `autoinstall/build-iso-go/main.go` | Added `CacheDir` to `BuildConfig`; XDG resolution in `main()`; updated `downloadExtraPackages()` |

### `BuildConfig` — new field

```go
// CacheDir is the persistent apt package cache directory, stored under the
// XDG cache home (~/.cache/build-iso/apt_cache/) so it survives binary runs
// and is not destroyed when the embedded-assets temp dir is cleaned up.
CacheDir string
```

### `main()` — XDG resolution (replaces old `os.MkdirAll` for `apt_cache`)

```go
// Resolve persistent apt cache under XDG_CACHE_HOME (or ~/.cache/) so it
// survives runs even when scriptDir is a temporary embedded-assets directory.
cacheHome := os.Getenv("XDG_CACHE_HOME")
if cacheHome == "" {
    cacheHome = filepath.Join(os.Getenv("HOME"), ".cache")
}
cacheDir := filepath.Join(cacheHome, "build-iso", "apt_cache")
_ = os.MkdirAll(cacheDir, 0755)
```

`cacheDir` is then passed into `BuildConfig`:

```go
cfg := &BuildConfig{
    // ... other fields ...
    CacheDir: cacheDir,
}
```

### `downloadExtraPackages()` — use `cfg.CacheDir`

Before:
```go
// Anchor cache to scriptDir (autoinstall/) ...
persistentCache, _ := filepath.Abs(filepath.Join(cfg.ScriptDir, "apt_cache", cfg.Codename))
```

After:
```go
// Use the XDG-based cache dir so packages persist across runs.
// cfg.CacheDir is ~/.cache/build-iso/apt_cache/ (or $XDG_CACHE_HOME equivalent).
persistentCache, _ := filepath.Abs(filepath.Join(cfg.CacheDir, cfg.Codename))
```

### Cache layout on disk

```
~/.cache/build-iso/
└── apt_cache/
    ├── jammy/                     ← Ubuntu 22.04
    │   └── archives/
    │       ├── partial/
    │       └── *.deb
    └── bionic/                    ← Ubuntu 18.04
        └── archives/
            ├── partial/
            └── *.deb
```

### Overriding the cache location (CI example)

```bash
export XDG_CACHE_HOME=/mnt/shared/cache
./os-deploy -B 10.0.0.1 -N 10.0.0.2 -O ubuntu-22.04 ...
# cache written to /mnt/shared/cache/build-iso/apt_cache/
```

### Clearing the cache

```bash
rm -rf ~/.cache/build-iso/apt_cache/
```
