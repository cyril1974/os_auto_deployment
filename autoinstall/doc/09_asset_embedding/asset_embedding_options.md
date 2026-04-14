# ISO Builder Asset Embedding — Design Options

## Problem

When `os-deploy` runs as a Nuitka onefile binary, it extracts to a temporary
directory such as `/tmp/onefile_xxx/`. The Go ISO builder binary is bundled
inside and extracts to:

```
/tmp/onefile_xxx/autoinstall/build-iso-go/build-iso
```

The Go binary determines its asset directory (`scriptDir`) relative to itself:

```go
binaryDir := filepath.Dir(os.Args[0])   // .../autoinstall/build-iso-go/
scriptDir  := filepath.Dir(binaryDir)   // .../autoinstall/
```

It then looks for these assets under `scriptDir`:

| Asset | Path relative to scriptDir | Used for |
|-------|---------------------------|---------|
| `scripts/find_disk.sh` | `scripts/find_disk.sh` | Copied into ISO for serial auto-detection at boot |
| `scripts/find_disk_1804.sh` | `scripts/find_disk_1804.sh` | Same, Ubuntu 18.04 variant |
| `startup.nsh` | `startup.nsh` | Copied into ISO EFI image for UEFI boot |
| `ipmi_start_logger.py` | `ipmi_start_logger.py` | Copied into ISO pool for IPMI SEL logging |
| `package_list` | `package_list` | Read at startup for offline package bundling |

Since none of these are present in the Nuitka extraction temp dir, the
ISO builder silently skips them (or fatals for required files like
`find_disk.sh`), producing an ISO that is missing key components.

---

## Option 1 — Bundle as Nuitka data files

Add `--include-data-dir` / `--include-data-files` entries to `build-cli.sh`
so Nuitka extracts the files alongside the Go binary at the correct paths.

```bash
# In build-cli.sh, added to the Nuitka invocation:
--include-data-dir="${SCRIPT_DIR}/autoinstall/scripts=autoinstall/scripts" \
--include-data-files="${SCRIPT_DIR}/autoinstall/startup.nsh=autoinstall/startup.nsh" \
--include-data-files="${SCRIPT_DIR}/autoinstall/package_list=autoinstall/package_list" \
--include-data-files="${SCRIPT_DIR}/autoinstall/ipmi_start_logger.py=autoinstall/ipmi_start_logger.py" \
```

**How it works:** Nuitka places these files in the extraction temp dir under
`autoinstall/`, exactly where `scriptDir` resolves to.

**Pros:**
- Zero code changes to `main.go`
- Fast to add

**Cons:**
- Any new asset file added to `autoinstall/` must be manually added to `build-cli.sh`
- The Go binary is NOT self-contained — it only works when called from the
  Nuitka binary or when run from a correctly structured `autoinstall/` directory

---

## Option 2 — Go `//go:embed` (selected) ✓

Use Go's built-in `embed` package to compile the asset files directly into the
Go binary at build time. At runtime, the binary extracts them to a temp
directory before use.

```go
import "embed"

//go:embed scripts startup.nsh ipmi_start_logger.py
var embeddedAssets embed.FS

// package_list is optional — embedded only if present
//go:embed package_list
var embeddedPackageList []byte
```

**How it works:**

```
go build  →  build-iso  (contains scripts/, startup.nsh, etc. inside the binary)
                │
                ▼  at runtime
          extractEmbeddedAssets()
                │
                ▼
          /tmp/build-iso-assets-xxx/
          ├── scripts/
          │   ├── find_disk.sh
          │   └── find_disk_1804.sh
          ├── startup.nsh
          └── ipmi_start_logger.py
                │
                ▼
          scriptDir = /tmp/build-iso-assets-xxx/
          (existing asset path logic unchanged)
```

**Pros:**
- Go binary is fully self-contained regardless of how/where it is invoked
- Works correctly from: Nuitka onefile, direct execution, any working directory
- `build-cli.sh` does not need updating when assets change
- No dependency on surrounding directory structure

**Cons:**
- ~100–200 KB increase in Go binary size (scripts are small)
- Slightly more complex startup code (temp dir extraction)
- Optional `package_list` requires careful handling (embed directive fails if
  file is absent — solved by making it part of the embedded FS with a default
  empty fallback)

---

## Option 3 — `--script-dir` flag on the Go binary

Add a `--script-dir=<path>` argument. `main.py` passes the actual
`autoinstall/` path when calling the Go binary. For the Nuitka case,
`main.py` derives the path from `__file__`.

**Pros:**
- Simple argument change
- No file bundling needed

**Cons:**
- Does not solve the core problem: the asset files are still not present in the
  Nuitka extraction temp dir
- Breaks standalone Go binary usage unless the flag is always supplied
- Makes `os-deploy` responsible for knowing where assets live on disk

---

## Decision: Option 2

Option 2 was selected because the Go binary becomes **fully self-contained**:
the same binary works identically whether invoked from the Nuitka binary,
called directly, or run from a CI pipeline — without requiring any surrounding
directory structure.

### Implementation plan

1. Create `embed.go` in `autoinstall/build-iso-go/` containing the embed
   directives and the `extractEmbeddedAssets()` function.
2. Add a `package_list.default` empty fallback so the embed directive is always
   satisfied.
3. Call `extractEmbeddedAssets()` at startup in `main()`, set `scriptDir` to
   the extraction temp dir, defer cleanup.
4. The `//go:embed package_list` directive is conditional: if the real
   `package_list` file exists it is embedded; otherwise the empty fallback is
   used (handled via embed FS, not raw bytes).
5. Rebuild with `build.sh` — tests run before binary is produced.
