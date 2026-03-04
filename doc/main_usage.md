# OS Deployment Tool — Usage Guide

> **Module:** `os_deployment.main`
> **Entry Point:** `os-deploy` (CLI) / `python -m os_deployment.main`
> **Version:** 0.0.1
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
- [Workflow](#workflow)
- [Usage Examples](#usage-examples)
  - [Basic Usage](#basic-usage)
  - [Specifying BMC Credentials on CLI](#specifying-bmc-credentials-on-cli)
  - [Custom Config File](#custom-config-file)
  - [Skip Reboot](#skip-reboot)
  - [Show Version](#show-version)
- [Execution Flow Detail](#execution-flow-detail)
- [Error Handling](#error-handling)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [Troubleshooting](#troubleshooting)

---

## Overview

`os_deployment` is a CLI tool that automates the end-to-end process of deploying an operating system (Ubuntu) onto target servers via BMC (Baseboard Management Controller). The tool performs the following high-level operations:

1. **Load Configuration** — Reads server credentials and NFS settings from a JSON config file.
2. **Generate Custom Autoinstall ISO** — Executes a build script to create a custom Ubuntu autoinstall ISO.
3. **Deploy ISO to NFS Server** — Uploads the generated ISO to an NFS share.
4. **Mount ISO on Target Server** — Remotely mounts the ISO via BMC virtual media.
5. **Mount Utility Package** — Mounts additional utility images to the target server.
6. **Reboot to UEFI** — Reboots the target server to begin installation.
7. **Monitor Installation** — Monitors BMC event logs and manages automatic reboots during firmware/OS updates.

---

## Prerequisites

- **Python** >= 3.9, < 4.0
- **sudo** privileges (required for ISO build operations)
- **Network Access** to:
  - Target server's BMC IP
  - NFS server
- **NFS Server** configured and accessible
- **Autoinstall build script** located at `<project_root>/autoinstall/build-ubuntu-autoinstall-iso.sh`

---

## Installation

Using [Poetry](https://python-poetry.org/):

```bash
cd os_auto_deployment
poetry install
```

After installation, the CLI command `os-deploy` will be available in your Poetry environment.

Alternatively, run directly:

```bash
poetry run os-deploy --help
```

---

## Configuration

### config.json

The tool expects a JSON configuration file (default: `config.json` in the current working directory). This file provides NFS server information and BMC authentication credentials.

**Structure:**

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

**Fields:**

| Field                    | Type   | Description                                         |
| ------------------------ | ------ | --------------------------------------------------- |
| `nfs_server.ip`          | string | IP address of the NFS server                        |
| `nfs_server.path`        | string | Export path on the NFS server                       |
| `auth.<BMC_IP>.username` | string | Login username for the BMC at the specified IP      |
| `auth.<BMC_IP>.password` | string | Login password for the BMC at the specified IP      |

### Config Template

A template file is provided at `config.json.template`:

```json
{
  "nfs_server": {
    "ip": "192.168.1.100",
    "path": "/path/to/nfs/share"
  },
  "auth": {
    "192.168.1.50": {
      "username": "admin",
      "password": "your_password_here"
    }
  }
}
```

Copy and edit this template to create your own `config.json`.

---

## Command-Line Arguments

| Argument                    | Short | Required | Default        | Description                                                                                |
| --------------------------- | ----- | -------- | -------------- | ------------------------------------------------------------------------------------------ |
| `--bmcip`                   | `-B`  | **Yes**  | —              | BMC IP address of the target server                                                        |
| `--bmcuser`                 | `-BU` | No       | —              | BMC login username (if provided with `--bmcpasswd`, overrides config.json)                 |
| `--bmcpasswd`               | `-BP` | No       | —              | BMC login password (if provided with `--bmcuser`, overrides config.json)                   |
| `--nfsip`                   | `-N`  | **Yes**  | —              | NFS server IP (must be defined in config.json)                                             |
| `--os`                      | `-O`  | **Yes**  | —              | OS ISO name to deploy (Ubuntu only)                                                        |
| `--osuser`                  | `-OU` | No       | `admin`        | OS login username for the installed system                                                 |
| `--ospasswd`                | `-OP` | No       | `ubuntu`       | OS login password for the installed system                                                 |
| `--config`                  | `-c`  | No       | `config.json`  | Path to the JSON configuration file                                                        |
| `--no-reboot`               |       | No       | `False`        | Skip rebooting the target server after deployment                                          |
| `--version`                 | `-V`  | No       | —              | Show version information and exit                                                          |

> **Note:** If `--bmcuser` and `--bmcpasswd` are both provided along with `--bmcip`, the BMC credentials will be **added/updated** in the config.json file automatically.

---

## Workflow

```
┌─────────────────────────────────────────────┐
│  1. Parse CLI Arguments                     │
├─────────────────────────────────────────────┤
│  2. Load & Validate config.json             │
│     - Merge BMC credentials if provided     │
├─────────────────────────────────────────────┤
│  3. Generate Custom Autoinstall ISO         │
│     - Calls build-ubuntu-autoinstall-iso.sh │
│     - Requires sudo                         │
├─────────────────────────────────────────────┤
│  4. Deploy ISO to NFS Server                │
│     - Copy ISO to NFS export path           │
├─────────────────────────────────────────────┤
│  5. Authenticate with BMC                   │
│     - Detect product generation via Redfish │
├─────────────────────────────────────────────┤
│  6. Check Virtual Media Permission          │
│     - Verify outband & inband media access  │
├─────────────────────────────────────────────┤
│  7. Remote Mount ISO via BMC                │
├─────────────────────────────────────────────┤
│  8. Mount Utility Package                   │
├─────────────────────────────────────────────┤
│  9. Reboot to UEFI (unless --no-reboot)     │
├─────────────────────────────────────────────┤
│ 10. Monitor Event Log & Handle Reboots      │
│     - Track firmware update progress        │
│     - Re-mount media if lost                │
│     - Collect logs upon completion          │
└─────────────────────────────────────────────┘
```

---

## Usage Examples

### Basic Usage

```bash
os-deploy -B 10.99.236.49 -N 10.99.236.48 -O ubuntu-22.04.4-live-server-amd64.iso
```

This uses credentials from `config.json` for BMC IP `10.99.236.49`, mounts the ISO via NFS at `10.99.236.48`, and deploys the specified Ubuntu ISO.

### Specifying BMC Credentials on CLI

```bash
os-deploy \
  -B 10.99.236.49 \
  -BU admin \
  -BP MySecurePass \
  -N 10.99.236.48 \
  -O ubuntu-22.04.4-live-server-amd64.iso
```

When both `-BU` and `-BP` are provided, the credentials are written into `config.json` under the `auth` section for the given BMC IP.

### Custom Config File

```bash
os-deploy \
  -B 10.99.236.49 \
  -N 10.99.236.48 \
  -O ubuntu-22.04.4-live-server-amd64.iso \
  -c /path/to/my_config.json
```

### Skip Reboot

```bash
os-deploy \
  -B 10.99.236.49 \
  -N 10.99.236.48 \
  -O ubuntu-22.04.4-live-server-amd64.iso \
  --no-reboot
```

Useful for testing or when you want to manually control the reboot process.

### Show Version

```bash
os-deploy -V
```

Output:
```
MiTAC CUP Deploy Tool -- 0.0.1
Copyright (c) 2025 MiTAC Computing Technology Corporation
All rights reserved.
```

---

## Execution Flow Detail

### 1. Configuration Loading

- Validates the config path exists and is a valid string.
- Loads the JSON configuration.
- If BMC credentials (`--bmcuser` + `--bmcpasswd`) are provided on the CLI, they are **merged** into the config and written back to disk.
- If only `--bmcip` is provided without credentials, the tool expects the BMC IP to already exist in the config's `auth` section — otherwise it exits with an error.

### 2. ISO Generation

- Locates the build script at `<project_root>/autoinstall/build-ubuntu-autoinstall-iso.sh`.
- Executes the script with **sudo**: `sudo build-ubuntu-autoinstall-iso.sh <os_name> <os_user> <os_password>`.
- Parses the script output to extract the generated ISO file path.
- Converts any relative path to an absolute path.

### 3. NFS Deployment

- Reads the NFS server configuration from `config.json`.
- Retrieves NFS exports from the server.
- Deploys (copies) the ISO file to the configured NFS path.

### 4. BMC Authentication & Detection

- Retrieves authentication headers for Redfish API access.
- Detects the target server's product generation and model via Redfish.

### 5. Virtual Media Check

- Queries the BMC for virtual media permissions.
- Validates that both **outband** and **inband** virtual media are enabled.
- Exits with an error if permissions are insufficient.

### 6. Image Mounting & Reboot

- Mounts the ISO image remotely via the BMC's virtual media interface.
- Mounts additional utility packages.
- Sets boot device to UEFI and reboots the server (unless `--no-reboot` is set).

### 7. Monitoring

- Continuously polls BMC event logs for installation progress.
- Monitors for automatic server reboots and handles them.
- Re-mounts lost virtual media if detected.
- Tracks firmware update stages (BIOS, BMC, CPLD, SUP).
- Collects and saves logs upon completion.

---

## Error Handling

The tool exits with descriptive error messages in the following cases:

| Scenario                                    | Exit Message                                                             |
| ------------------------------------------- | ------------------------------------------------------------------------ |
| Config path is not a string                 | `Invalid configuration path: ...`                                        |
| Config file not found                       | `Configuration File (<path>) not found: ...`                             |
| BMC IP not in config (no CLI credentials)   | `BMC IP (<ip>) configuration not found in config.json`                   |
| Build script not found                      | `Build script not found: <path>`                                         |
| Build script execution fails                | `Failed to generate custom autoinstall ISO (exit code: <code>)`          |
| ISO path not found in script output         | `Failed to extract ISO path from build script output`                    |
| NFS configuration missing                   | `Get NFS Server Config Fail, Please configure NFS Server...`            |
| Virtual media not enabled                   | `No Virtual Media Permission, Please enter BMC to configure ...Abort`    |
| Remote mount fails                          | `Remote Mount Image <path> FAIL !! Exit`                                 |
| Reboot timeout                              | `Reboot Server Fail (TimeOut)`                                           |

---

## Project Structure

```
os_auto_deployment/
├── autoinstall/                    # Autoinstall ISO build scripts & resources
│   ├── build-ubuntu-autoinstall-iso.sh
│   └── doc/
├── config.json                     # Runtime configuration (not tracked in git)
├── config.json.template            # Configuration template
├── doc/                            # Documentation (this file)
│   └── main_usage.md
├── pyproject.toml                  # Poetry project definition
├── src/
│   └── os_deployment/
│       ├── __init__.py
│       ├── _version.py             # Version fallback for PyInstaller builds
│       ├── main.py                 # Main entry point (this document)
│       ├── test_function.py
│       └── lib/
│           ├── auth.py             # BMC authentication
│           ├── board_version.py    # Board version utilities
│           ├── config.py           # Config file loader
│           ├── constants.py        # Constants & API endpoint definitions
│           ├── generation.py       # Server generation detection
│           ├── monitor.py          # Monitoring utilities
│           ├── nfs.py              # NFS operations
│           ├── reboot.py           # Reboot & boot option management
│           ├── redfish.py          # Redfish API client
│           ├── remote_mount.py     # Remote virtual media mount
│           ├── state_manager.py    # Global state management
│           ├── utility_mount.py    # Utility image mount operations
│           └── utils.py            # Shared utility functions
└── tests/
```

---

## Dependencies

Defined in `pyproject.toml`:

| Package    | Version       | Purpose                         |
| ---------- | ------------- | ------------------------------- |
| `python`   | >= 3.9, < 4.0 | Runtime                         |
| `typer`    | ^0.9.0        | CLI framework                   |
| `requests` | ^2.32.3       | HTTP/Redfish API requests       |
| `aiohttp`  | ^3.11.18      | Async HTTP operations           |

**System dependencies:**
- `sudo` access (for ISO build script execution)
- NFS client utilities (for NFS mount operations)

---

## Troubleshooting

### Config file not found

```
Configuration File (config.json) not found
```

**Solution:** Ensure `config.json` exists in the current working directory, or specify a custom path with `-c /path/to/config.json`.

### BMC IP not in config

```
BMC IP (x.x.x.x) configuration not found in config.json
```

**Solution:** Either add the BMC IP and credentials to `config.json`, or supply them via CLI flags `-BU` and `-BP`.

### Build script not found

```
Build script not found: .../autoinstall/build-ubuntu-autoinstall-iso.sh
```

**Solution:** Ensure the `autoinstall/` directory exists at the project root with the required build script. The script is expected at `<project_root>/autoinstall/build-ubuntu-autoinstall-iso.sh`.

### Virtual Media Permission denied

```
No Virtual Media Permission, Please enter BMC to configure Virtual Media Permission ...Abort
```

**Solution:** Log into the BMC web interface and enable both Outband and Inband virtual media permissions.

### ISO generation failed

```
Failed to generate custom autoinstall ISO (exit code: X)
```

**Solution:** Check the stdout/stderr output printed above the error. Common causes include missing packages (the build script may require `xorriso`, `genisoimage`, etc.) or insufficient permissions.

---

*Document generated on 2026-03-02*
