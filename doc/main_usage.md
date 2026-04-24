# OS Deployment Tool — Usage Guide

> **Module:** `os_deployment.main`
> **Entry Point:** `os-deploy` (CLI) / `python -m os_deployment.main`
> **Author:** Cyril Chang
> **Copyright:** © 2025 MiTAC Computing Technology Corporation

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [config.json](#configjson)
  - [Config Template](#config-template)
- [Command-Line Arguments](#command-line-arguments)
  - [Required Arguments](#required-arguments)
  - [ISO Generation Options](#iso-generation-options)
  - [Storage Matching Options](#storage-matching-options)
  - [Platform Options](#platform-options)
  - [Deployment Control](#deployment-control)
- [Workflow](#workflow)
  - [Full Deployment Flow](#full-deployment-flow)
  - [ISO-Only Flow (--gen-iso-only)](#iso-only-flow---gen-iso-only)
- [Usage Examples](#usage-examples)
- [Execution Flow Detail](#execution-flow-detail)
- [Error Handling](#error-handling)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [Troubleshooting](#troubleshooting)

---

## Overview

`os_deployment` is a CLI tool that automates the end-to-end process of deploying Ubuntu onto target servers via BMC (Baseboard Management Controller). It can also operate in ISO-only mode to generate a custom autoinstall ISO without performing any network deployment.

**Full deployment** performs:

1. Generate custom autoinstall ISO (or use pre-built)
2. Deploy ISO to NFS server
3. Validate Redfish API & BMC authentication
4. Mount ISO via BMC virtual media
5. Set boot device to CD-ROM + reboot
6. Monitor BMC event log until installation completes

**ISO-only mode** (`--gen-iso-only`):

1. Generate custom autoinstall ISO
2. Print the ISO path and exit — no BMC or NFS access required

---

## Prerequisites

- **Python** >= 3.9, < 4.0
- **sudo** privileges (required for ISO build operations)
- **Network access** to BMC IP and NFS server *(not required in `--gen-iso-only` mode)*
- **Go ISO builder** binary at `autoinstall/build-iso-go/build-iso`
  (run `bash build.sh` inside `autoinstall/build-iso-go/` to compile)

---

## Installation

Using [Poetry](https://python-poetry.org/):

```bash
cd os_auto_deployment
poetry install
```

After installation, the CLI command `os-deploy` is available in the Poetry environment:

```bash
poetry run os-deploy --help
```

---

## Configuration

### config.json

The tool expects a JSON configuration file (default: `config.json` in the current working directory).

```json
{
    "nfs_server": {
        "ip": "<NFS_SERVER_IP>",
        "path": "<NFS_SHARE_PATH>"
    },
    "auth": {
        "<BMC_IP>": {
            "username": "<BMC_USERNAME>",
            "password": "<BMC_PASSWORD>"
        }
    }
}
```

| Field | Type | Description |
|---|---|---|
| `nfs_server.ip` | string | IP address of the NFS server |
| `nfs_server.path` | string | Export path on the NFS server |
| `auth.<BMC_IP>.username` | string | BMC login username |
| `auth.<BMC_IP>.password` | string | BMC login password |

### Config Template

Copy and edit the template:

```bash
cp config.json.template config.json
```

---

## Command-Line Arguments

### Required Arguments

| Argument | Short | Required | Default | Description |
|---|---|---|---|---|
| `--bmcip` | `-B` | Yes* | — | BMC IP of the target server (*not required with `--gen-iso-only`) |
| `--nfsip` | `-N` | Yes* | — | NFS server IP (*not required with `--gen-iso-only`) |
| `--os` | `-O` | Yes** | — | OS ISO name to look up in `file_list.json` (**required unless `--iso` is provided) |
| `--iso-repo-dir` | — | Yes** | — | Path to ISO repository containing `file_list.json` (**required when `-O` is used) |

### Authentication Options

| Argument | Short | Required | Default | Description |
|---|---|---|---|---|
| `--bmcuser` | `-BU` | No | — | BMC login username (overrides config.json when combined with `--bmcpasswd`) |
| `--bmcpasswd` | `-BP` | No | — | BMC login password |
| `--osuser` | `-OU` | No | `autoinstall` | Username for the installed OS |
| `--ospasswd` | `-OP` | No | `ubuntu` | Password for the installed OS (also applied to root) |
| `--config` | `-c` | No | `config.json` | Path to the JSON config file |

### ISO Generation Options

| Argument | Required | Default | Description |
|---|---|---|---|
| `--iso` | No | — | Path to a pre-built ISO. Skips ISO generation entirely and uses this file for deployment. Mutually exclusive with `--gen-iso-only`. |
| `--gen-iso-only` | No | `False` | Generate the custom ISO and print its path, then exit. Skips NFS deployment, remote mount, and reboot. `-B` and `-N` are not required in this mode. |
| `--gen-by-sh` | No | `False` | Use the legacy shell script builder (`build-ubuntu-autoinstall-iso.sh`) instead of the default Go builder. |
| `--package-list` | No | — | Path to a custom `package_list` file to override the embedded package list in the Go builder. |

### Storage Matching Options

Only one of the following may be specified. If more than one is provided, the first in argument order is used and the rest are ignored with a warning.

| Argument | Description |
|---|---|
| `--storage-serial=VALUE` | Match target disk by serial number. Embeds directly in `user-data`; disables `find_disk.sh`. |
| `--storage-model=VALUE` | Match target disk by model name. Embeds directly in `user-data`; disables `find_disk.sh`. |
| `--storage-size=VALUE` | Match target disk by size (e.g. `7T`, `960G`). Enables `find_disk.sh` at boot with `--target-size`. Serial is resolved at boot time. |

When none of the above is set, `find_disk.sh` runs at boot and selects the smallest empty disk automatically.

### Platform Options

| Argument | Required | Default | Description |
|---|---|---|---|
| `--hostname=NAME` | No | `ubuntu-auto` | Hostname written into `user-data` / preseed for the installed system. |
| `--mi325x-support` | No | `False` | Apply MiTAC Mi325x platform late-commands: GRUB kernel parameters (`amd_iommu=on iommu=pt pci=realloc=off`), `GRUB_RECORDFAIL_TIMEOUT=0`, and `update-grub`. Requires `--mi325x-node`. |
| `--mi325x-node=NODE` | Conditional | — | Target node identifier. Required when `--mi325x-support` is set. Format: `node_<integer>` e.g. `node_1`, `node_2`. |

### Deployment Control

| Argument | Short | Default | Description |
|---|---|---|---|
| `--no-reboot` | — | `False` | Skip rebooting the target server after deployment. Useful for testing. |
| `--version` | `-V` | — | Show version information and exit. |

---

## Workflow

### Full Deployment Flow

```
┌─────────────────────────────────────────────────────┐
│  1. Parse & Validate CLI Arguments                  │
├─────────────────────────────────────────────────────┤
│  2. Load & Validate config.json                     │
│     - Merge BMC credentials if -BU/-BP provided     │
├─────────────────────────────────────────────────────┤
│  3. Validate Redfish API & BMC Authentication       │
│     - Detect Redfish support                        │
│     - Validate BMC login credentials                │
├─────────────────────────────────────────────────────┤
│  4. Generate Custom Autoinstall ISO                 │
│     - Go builder (default) or shell builder         │
│     - Embeds: hostname, credentials, storage match, │
│       platform options, offline packages            │
│  OR: Use pre-built ISO (--iso)                      │
├─────────────────────────────────────────────────────┤
│  5. Deploy ISO to NFS Server                        │
│     - Copy ISO to NFS export path                   │
├─────────────────────────────────────────────────────┤
│  6. Detect Product Generation                       │
│     - Query Redfish for model and generation        │
├─────────────────────────────────────────────────────┤
│  7. Remote Mount ISO via BMC Virtual Media          │
│     - Gen 6/7: standard Redfish VirtualMedia        │
│     - Gen 8: EnableRMedia + polling RedirectionStatus│
├─────────────────────────────────────────────────────┤
│  8. Set Boot Device to CD-ROM + Reboot              │
│     - Gen 8: ETag / If-Match PATCH required         │
│     (skipped if --no-reboot)                        │
├─────────────────────────────────────────────────────┤
│  9. Monitor Installation                            │
│     - Poll BMC event log for progress               │
│     - Handle automatic reboots                      │
│     - Re-mount media if lost                        │
│     - Collect logs on completion                    │
└─────────────────────────────────────────────────────┘
```

### ISO-Only Flow (`--gen-iso-only`)

```
┌─────────────────────────────────────────────────────┐
│  1. Parse & Validate CLI Arguments                  │
│     (-B and -N not required)                        │
├─────────────────────────────────────────────────────┤
│  2. Load config.json                                │
├─────────────────────────────────────────────────────┤
│  3. Generate Custom Autoinstall ISO                 │
├─────────────────────────────────────────────────────┤
│  4. Print ISO path and exit                         │
└─────────────────────────────────────────────────────┘
```

---

## Usage Examples

### Basic Full Deployment

```bash
os-deploy \
  -B 10.99.236.49 \
  -N 10.99.236.48 \
  -O ubuntu-24.04.2-live-server-amd64 \
  --iso-repo-dir=/data/iso_repo
```

### Generate ISO Only (no BMC/NFS needed)

```bash
os-deploy \
  --gen-iso-only \
  -O ubuntu-24.04.2-live-server-amd64 \
  --iso-repo-dir=/data/iso_repo \
  --hostname=node01
```

The generated ISO path is printed to stdout. Use `--iso` in a subsequent deployment step to skip re-generation:

```bash
os-deploy \
  -B 10.99.236.49 \
  -N 10.99.236.48 \
  --iso=/path/to/generated.iso
```

### Mi325x Platform Deployment

```bash
os-deploy \
  -B 10.99.236.49 \
  -N 10.99.236.48 \
  -O ubuntu-24.04.2-live-server-amd64 \
  --iso-repo-dir=/data/iso_repo \
  --hostname=mi325xr-node1 \
  --mi325x-support \
  --mi325x-node=node_1
```

### ISO-Only for Mi325x Node

```bash
os-deploy \
  --gen-iso-only \
  -O ubuntu-24.04.2-live-server-amd64 \
  --iso-repo-dir=/data/iso_repo \
  --hostname=mi325xr-node3 \
  --mi325x-support \
  --mi325x-node=node_3
```

### Custom Package List

```bash
os-deploy \
  --gen-iso-only \
  -O ubuntu-24.04.2-live-server-amd64 \
  --iso-repo-dir=/data/iso_repo \
  --package-list=/data/package_list_mi325xr
```

### Match Disk by Serial Number

```bash
os-deploy \
  -B 10.99.236.49 \
  -N 10.99.236.48 \
  -O ubuntu-24.04.2-live-server-amd64 \
  --iso-repo-dir=/data/iso_repo \
  --storage-serial=S6CKNT0W700868
```

### Match Disk by Size

```bash
os-deploy \
  -B 10.99.236.49 \
  -N 10.99.236.48 \
  -O ubuntu-24.04.2-live-server-amd64 \
  --iso-repo-dir=/data/iso_repo \
  --storage-size=7T
```

### BMC Credentials on CLI

```bash
os-deploy \
  -B 10.99.236.49 \
  -BU admin \
  -BP MySecurePass \
  -N 10.99.236.48 \
  -O ubuntu-24.04.2-live-server-amd64 \
  --iso-repo-dir=/data/iso_repo
```

When both `-BU` and `-BP` are provided, credentials are written into `config.json` under the `auth` section for that BMC IP.

### Skip Reboot

```bash
os-deploy \
  -B 10.99.236.49 \
  -N 10.99.236.48 \
  -O ubuntu-24.04.2-live-server-amd64 \
  --iso-repo-dir=/data/iso_repo \
  --no-reboot
```

### Show Version

```bash
os-deploy -V
```

---

## Execution Flow Detail

### ISO Generation

The Go builder (`autoinstall/build-iso-go/build-iso`) is used by default. It embeds:

- Hostname, username, password (hashed), SSH public key
- Storage match key/value or `find_disk.sh` size hint
- Offline package list (embedded or from `--package-list`)
- Mi325x platform files (`mi325xr/common/` + `mi325xr/node_x/`) when `--mi325x-support` is set
- IPMI SEL logger script

The legacy shell builder (`--gen-by-sh`) calls `build-ubuntu-autoinstall-iso.sh` instead.

### Gen 8 BMC Compatibility

The tool handles MiTAC Mi325x (Gen 8) BMC differences automatically:

| Operation | Gen 6/7 | Gen 8 |
|---|---|---|
| Virtual media enable | Not needed | POST `AMIVirtualMedia.EnableRMedia` first |
| Mount confirmation | Synchronous | Poll `Oem.Ami.RedirectionStatus` up to 60s |
| Boot PATCH | No special headers | Requires `If-Match: <ETag>` header |
| Boot mode | — | `BootSourceOverrideMode: UEFI` required |

---

## Error Handling

| Scenario | Exit Message |
|---|---|
| `--gen-iso-only` + `--iso` together | `--gen-iso-only and --iso are mutually exclusive` |
| `-B` missing in full deployment mode | `-B/--bmcip is required (omit only with --gen-iso-only)` |
| `-N` missing in full deployment mode | `-N/--nfsip is required (omit only with --gen-iso-only)` |
| `-O` missing and `--iso` not provided | `-O/--os is required when --iso is not provided` |
| `--iso-repo-dir` missing with `-O` | `--iso-repo-dir is required when -O/--os is specified` |
| `--mi325x-node` missing with `--mi325x-support` | `--mi325x-node is required when --mi325x-support is set` |
| Invalid `--mi325x-node` format | `invalid --mi325x-node value: ... Expected format: node_<integer>` |
| Config file not found | `Configuration File (<path>) not found` |
| BMC IP not in config | `BMC IP (<ip>) configuration not found in config.json` |
| Pre-built ISO not found | `Pre-built ISO not found: <path>` |
| Build script not found | `Build script not found: <path>` |
| ISO generation failed | `Failed to generate custom autoinstall ISO (exit code: <N>)` |
| NFS config missing | `Get NFS Server Config Fail, Please configure NFS Server...` |
| Remote mount failed | `Remote Mount Image <path> FAIL !! Exit` |
| Reboot timeout | `Reboot Server Fail (TimeOut)` |

---

## Project Structure

```
os_auto_deployment/
├── autoinstall/
│   ├── build-iso-go/           # Go ISO builder source
│   │   ├── main.go             # Builder entry point + user-data template
│   │   ├── embed.go            # Embedded asset extraction
│   │   ├── build.sh            # Compile script
│   │   └── build-iso           # Compiled binary (not in git)
│   ├── mi325xr/                # Mi325x platform files
│   │   ├── common/             # Shared across all nodes
│   │   └── node_1/ … node_4/  # Per-node files (netplan, network tests)
│   ├── scripts/                # find_disk.sh variants
│   ├── package_list            # Default offline package list
│   └── package_list_mi325xr   # Mi325x-specific package list
├── config.json                 # Runtime config (not in git)
├── config.json.template
├── doc/
│   ├── main_usage.md           # This document
│   ├── 09_distribution/
│   └── 11_platform_compatibility/
│       └── mi325x_gen8_compatibility.md
├── pyproject.toml
└── src/os_deployment/
    ├── main.py                 # CLI entry point
    └── lib/
        ├── auth.py             # BMC authentication
        ├── config.py           # Config loader
        ├── generation.py       # Server generation detection
        ├── nfs.py              # NFS operations
        ├── reboot.py           # Reboot & boot option management
        ├── remote_mount.py     # BMC virtual media mount
        ├── state_manager.py    # Global state
        └── utils.py            # Shared utilities
```

---

## Dependencies

Defined in `pyproject.toml`:

| Package | Version | Purpose |
|---|---|---|
| `python` | >= 3.9, < 4.0 | Runtime |
| `requests` | ^2.32.3 | HTTP / Redfish API |
| `aiohttp` | ^3.11.18 | Async HTTP |

**System dependencies:**
- `sudo` access (ISO build requires root for `apt` and ISO operations)
- Go 1.21+ (to compile `build-iso-go/build-iso` from source)
- `xorriso`, `genisoimage`, `mtools`, `isolinux` (used by ISO builder at runtime)

---

## Troubleshooting

### BMC IP not in config

```
BMC IP (x.x.x.x) configuration not found in config.json
```

Add credentials to `config.json` or supply `-BU` / `-BP` on the CLI.

### Build script not found

```
Build script not found: .../autoinstall/build-iso-go/build-iso
```

Compile the Go builder first:

```bash
cd autoinstall/build-iso-go
bash build.sh
```

### Virtual media permission denied

```
No Virtual Media Permission, Please enter BMC to configure Virtual Media Permission ...Abort
```

Log into the BMC web interface and enable Outband and Inband virtual media.

### ISO generation failed

```
Failed to generate custom autoinstall ISO (exit code: X)
```

Check the stdout output above the error. Common causes: missing packages (`xorriso`, `genisoimage`), insufficient permissions, or invalid `--os` name.

### Unmet dependencies on installed system

If `apt install` fails after OS deployment with version conflict errors, the offline packages installed from the ISO are from an older snapshot. Run on the target:

```bash
apt --fix-broken install -y
apt update && apt full-upgrade -y
```

---

*Last updated: 2026-04-21*