# Building the `os-deploy` Standalone Binary with Nuitka

## Overview

`os-deploy` is distributed as a single self-contained executable compiled with
[Nuitka](https://nuitka.net/). The binary:

- Includes the Python interpreter, all source modules, and all runtime
  dependencies (`requests`, `urllib3`, `certifi`).
- Requires **no Python installation** on the target machine.
- Hides all source code — Python modules are compiled to native machine code,
  not stored as `.pyc` files or a ZIP archive.

```
Developer machine              Target machine
─────────────────              ──────────────
src/os_deployment/             os-deploy-0.9.2   ← single file, ~30 MB
build-cli.sh           ──►
pyproject.toml                 (no Python needed,
build-requirements.txt          no pip packages needed)
```

---

## How Nuitka Hides Source Code

| Method | Recoverability | Notes |
|--------|---------------|-------|
| Plain `.py` files | Trivial | Readable directly |
| `.pyc` bytecode (PyInstaller) | Easy — `uncompyle6` | ZIP archive inside ELF |
| Nuitka compiled binary | Hard — C machine code | Compiled via GCC, no bytecode |

Nuitka translates each Python module to a C source file and compiles it with
GCC. The final binary contains native machine code. There is no stored bytecode
and no embedded ZIP archive. Decompiling the result requires reverse-engineering
native binaries.

---

## Prerequisites

### System packages (Ubuntu/Debian)

```bash
apt install -y gcc patchelf python3-venv
```

| Package | Purpose |
|---------|---------|
| `gcc` | C compiler — Nuitka translates Python → C → binary |
| `patchelf` | Patches RPATH in the onefile binary for portability |
| `python3-venv` | Creates the isolated build virtualenv |

> **Note — Ubuntu 24.04+ / PEP 668**
>
> Ubuntu 24.04 and later mark the system Python as *externally managed*,
> blocking `pip install` system-wide:
> ```
> error: externally-managed-environment
> ```
> `build-cli.sh` handles this automatically by creating a local virtualenv
> (`.venv/`) and installing all build dependencies inside it.
> **You do not need to run `pip install` manually.**

### Python packages (managed automatically)

`build-cli.sh` creates `.venv/` and runs `pip install -r build-requirements.txt`
inside it on every invocation. No manual pip commands are needed.

[build-requirements.txt](../../build-requirements.txt) contains:

| Package | Version | Purpose |
|---------|---------|---------|
| `nuitka` | ≥ 2.0 | The compiler itself |
| `zstandard` | ≥ 0.21 | Compresses the onefile payload |
| `ordered-set` | ≥ 4.1 | Nuitka dependency ordering |
| `requests` | ≥ 2.32 | Runtime — bundled into binary |
| `urllib3` | ≥ 2.0 | Runtime — bundled into binary |
| `certifi` | ≥ 2024.0 | Runtime — TLS certificates bundled |

---

## Build Instructions

### Quick build

```bash
cd /path/to/os_auto_deployment
apt install -y gcc patchelf python3-venv   # one-time system setup
bash build-cli.sh
```

Output:
```
[+] System prerequisites satisfied (python3, gcc, patchelf)
[*] Creating virtualenv at .venv/ ...
[+] Virtualenv created
[*] Installing build dependencies into .venv/ ...
[+] Build dependencies installed
[*] os-deploy build — version 0.9.2
[*] Compiling with Nuitka (this takes 2–5 minutes on first build)...
[+] Build complete
[+] Binary  : dist/os-deploy-0.9.2
[+] Size    : 31M
```

### Build options

| Flag | Effect |
|------|--------|
| _(none)_ | Build binary into `dist/` (reuses `.venv/` if it exists) |
| `--clean` | Delete `dist/`, `build/nuitka/`, and `.venv/` before building |
| `--check` | Verify prerequisites and venv only, no build |

```bash
bash build-cli.sh --clean   # clean rebuild (re-creates venv too)
bash build-cli.sh --check   # verify environment only
```

### First build vs subsequent builds

Nuitka caches compiled C objects in `build/nuitka/`. The `.venv/` is reused
on subsequent runs so pip install is skipped. Only changed modules are
recompiled.

```
First build:   2–5 minutes  (creates venv, installs deps, compiles all modules)
Rebuild:       ~30 seconds  (reuses venv, only changed modules recompiled)
```

---

## Output

```
dist/
└── os-deploy-<version>    ← versioned binary (e.g. os-deploy-0.9.2)
```

The version is read automatically from `pyproject.toml` (`tool.poetry.version`).

---

## Deploying to a Target Machine

Copy the single binary to the target and run:

```bash
scp dist/os-deploy-0.9.2 user@target:/usr/local/bin/os-deploy
chmod +x /usr/local/bin/os-deploy

# Verify
os-deploy --version
os-deploy --help
```

No Python, no pip, no virtualenv required on the target machine.

---

## Usage (same as the Python entry point)

```bash
# Full deployment
os-deploy -B <bmc-ip> -N <nfs-ip> -O ubuntu-24.04-live-server-amd64

# Use pre-built ISO (skip generation)
os-deploy -B <bmc-ip> -N <nfs-ip> --iso /path/to/custom.iso

# Use Go ISO builder
os-deploy -B <bmc-ip> -N <nfs-ip> -O ubuntu-24.04-live-server-amd64 --gen-by-go

# Match target disk by model
os-deploy -B <bmc-ip> -N <nfs-ip> -O ubuntu-24.04-live-server-amd64 \
    --storage-model="SAMSUNG MZQL27T6HBLA*"

# Skip reboot
os-deploy -B <bmc-ip> -N <nfs-ip> -O ubuntu-24.04-live-server-amd64 --no-reboot
```

---

## Project File Reference

```
os_auto_deployment/
├── build-cli.sh              ← Nuitka build script (main entry)
├── build-requirements.txt    ← pip packages needed to build
├── pyproject.toml            ← version source (tool.poetry.version)
├── src/
│   └── os_deployment/
│       ├── main.py           ← CLI entry point
│       ├── _version.py       ← version string (bundled into binary)
│       └── lib/              ← modules compiled to native code
└── dist/
    └── os-deploy-<version>   ← produced binary
```

---

## Troubleshooting

### `error: externally-managed-environment` when running pip

Ubuntu 24.04+ (PEP 668) blocks system-wide `pip install`. `build-cli.sh`
handles this automatically via `.venv/` — **do not run pip manually**.
If you hit this error outside the build script:

```bash
# Option A — use the build script (recommended)
bash build-cli.sh

# Option B — create a venv manually
python3 -m venv .venv
.venv/bin/pip install -r build-requirements.txt
```

### `ModuleNotFoundError` at runtime for a lib module

Nuitka must be told to include packages explicitly. If a new sub-package is
added under `os_deployment/`, verify that `--include-package=os_deployment`
in `build-cli.sh` covers it (it does — it includes the entire package tree).

If a new **third-party** dependency is added to `pyproject.toml`, add a
corresponding `--include-package=<name>` line to `build-cli.sh` and
`build-requirements.txt`.

### Binary crashes on a different Linux distribution

The onefile binary uses `patchelf` to embed library paths. If the target system
has a significantly older glibc (e.g., building on Ubuntu 24.04, deploying on
Ubuntu 20.04), rebuild on the oldest target OS version or use a Docker container:

```bash
docker run --rm -v $(pwd):/work -w /work ubuntu:20.04 bash -c "
    apt update && apt install -y gcc patchelf python3 python3-pip &&
    pip3 install -r build-requirements.txt &&
    bash build-cli.sh
"
```

### `patchelf: not found`

```bash
apt install -y patchelf
```

### Build is slow / runs out of disk space

Nuitka's cache lives in `build/nuitka/`. This directory can reach 500 MB–1 GB
during compilation. Use `--clean` to remove it if disk space is constrained.
Subsequent clean builds take the same time as the first build.

### Version shows `unknown`

Ensure `pyproject.toml` exists and `tool.poetry.version` is set, or that
`src/os_deployment/_version.py` contains `__version__ = "x.y.z"`.
