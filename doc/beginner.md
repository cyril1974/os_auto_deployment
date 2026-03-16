# Beginner's Guide to This Codebase

## What this project does (high-level)

This repository is a CLI tool that automates Ubuntu OS deployment to physical servers through BMC/Redfish.

At a high level, it does the following:

1. Loads configuration and credentials.
2. Builds a custom Ubuntu autoinstall ISO (or uses a pre-built ISO).
3. Uploads the ISO to an NFS share.
4. Mounts the ISO to the target server via BMC virtual media.
5. Reboots the server to boot from virtual media.
6. Monitors Redfish event logs during installation/update.

---

## Overall structure

Focus on these three areas first:

- `src/os_deployment/`: Main Python application logic.
- `autoinstall/`: Bash scripts and assets for generating autoinstall ISOs.
- `doc/` and `autoinstall/doc/`: Usage and architecture documentation.

Key entry points:

- CLI command: `os-deploy` (defined by Poetry script entry).
- Main orchestrator: `src/os_deployment/main.py`.

---

## Execution flow in `main.py`

`main.py` is the orchestrator. It performs the end-to-end workflow:

1. Parse CLI arguments (BMC/NFS/OS/config/reboot options).
2. Validate and load `config.json`.
3. Validate BMC authentication.
4. Generate custom ISO (or accept `--iso`).
5. Copy ISO to NFS export.
6. Detect platform generation via Redfish.
7. Check virtual media permissions.
8. Mount remote image through Redfish virtual media.
9. Set boot device and reboot.
10. Monitor event logs and deployment state.

---

## Important modules to understand

A practical reading order for beginners:

1. `lib/config.py` - load configuration JSON.
2. `lib/auth.py` - build Basic auth header.
3. `lib/nfs.py` - NFS export query and file copy to NFS.
4. `lib/remote_mount.py` - virtual media discovery and mount action.
5. `lib/reboot.py` - set one-time boot target and reboot handling.
6. `lib/utils.py` - shared Redfish/API helpers and log parsing.
7. `lib/constants.py` - endpoint maps, timeout values, and event code mappings.
8. `lib/generation.py` + `lib/state_manager.py` - model generation detection and global state.

---

## Critical things a newcomer should know

- This is not just a Python-only utility; it depends heavily on system/network environment:
  - reachable BMC,
  - reachable NFS server,
  - sudo privileges,
  - Redfish availability.
- ISO generation is shell-based and depends on host packages/tools.
- Operational behavior depends on server generation/model (different endpoint usage and flows).
- Configuration quality is crucial: wrong BMC credentials or NFS path will stop the workflow early.

---

## Suggested next learning steps

1. Read `doc/main_usage.md` first to understand CLI usage and workflow.
2. Read `src/os_deployment/main.py` top to bottom once, only tracking call order.
3. Deep-dive into `lib/` modules in the reading order above.
4. Study `autoinstall/build-ubuntu-autoinstall-iso.sh` to understand ISO build mechanics.
5. Use `autoinstall/doc/` (architecture/workflow/debugging) for troubleshooting mindset.

---

## Quick start (developer perspective)

```bash
poetry install
poetry run os-deploy --help
```

Example:

```bash
os-deploy -B <BMC_IP> -N <NFS_IP> -O <ISO_NAME>
```

Use `config.json.template` to create your own configuration file before running real deployments.
