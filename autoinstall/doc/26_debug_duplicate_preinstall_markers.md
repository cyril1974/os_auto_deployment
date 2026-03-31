# Debug: Duplicate Package Pre-install Markers in SEL

## Symptom

During the automated OS installation on Ubuntu 24.04 targets, the forensic marker `0x0F` (**Package Pre-install Start**) was observed appearing **three times** in the BMC System Event Log (SEL).

**Log Evidence (BMC SEL/Monitoring Console):**
```text
[2026-03-31T07:39:04] [Info] Package Pre-install Start (Code : 0F)
[2026-03-31T07:39:05] [Info] Package Pre-install Start (Code : 0F)
[2026-03-31T07:39:06] [Info] Package Pre-install Start (Code : 0F)
... (54 seconds later)
[2026-03-31T07:39:41] [Info] Package Pre-install Complete (Code : 1F)
```
The duplication had a consistent **1-second interval** between entries, while subsequent markers like `0x1F` (Complete) and `0x01` (OS Start) were only logged once.

---

## Root Cause Analysis

### 1. Multi-Provider Trigger in Subiquity
The Ubuntu 24.04 installer (`subiquity`) and its underlying initialization engine (`cloud-init`) can process `autoinstall` configurations from multiple sources simultaneously if they are detected.

In our current ISO structure:
1.  **Direct Media Reference:** Specified via boot parameter `ds=nocloud;s=/cdrom/autoinstall/`.
2.  **Root Symlink:** A symlink at `/autoinstall.yaml` pointing to `/cdrom/autoinstall/user-data` (added for 24.04 compatibility).
3.  **Installer Refresh:** If the installer performing a self-update, it may re-read the configuration.

Each time a new configuration provider is initialized, the `early-commands` associated with that configuration are executed. On some hardware (Mitac G7/Node .49), this resulted in exactly three distinct executions of the initial shell commands before the installer settled on a final state.

### 2. Sequential Execution Overlap
Because the `Package Pre-install Start` call is the very first forensic command in the list, it is the most likely to be triggered during those early initialization phases. Subsequent commands (like `dpkg -i`) are often aborted or bypassed if a previous provider is already handling them, leading to a single `0x1F` (Complete) log at the end of the *actual* execution.

---

## Resolution: Idempotent IPMI Logging

To resolve this without removing the necessary compatibility symlinks, the `ipmi_start_logger.py` utility was updated to be **idempotent**.

### Implementation: Marker Lock System
A lock file mechanism was added to `ipmi_start_logger.py` to prevent any specific marker from being sent more than once per OS session.

**Technical Logic:**
1.  **Check for existing lock:** Before interacting with `/dev/ipmi0`, the script checks if `/tmp/ipmi_marker_XX.lock` exists.
2.  **Skip if locked:** If the file exists, it means the marker has already been recorded in the BMC SEL. The script exits silently with code `0`.
3.  **Send and Lock:** If not found, it performs the IPMI IOCTL. Upon success, it creates the `/tmp/` lock file.

**Code Snippet (`ipmi_start_logger.py`):**
```python
# Prevent duplicate logging of the same marker (Subiquity re-trigger bug)
marker_lock = f"/tmp/ipmi_marker_{marker:02x}.lock"
if os.path.exists(marker_lock):
    sys.exit(0)

# ... send command ...

if success:
    with open(marker_lock, 'w') as f:
        f.write(datetime.now().isoformat())
```

### Benefits
- ✅ **Clean Event Timeline:** Each deployment milestone now appears exactly once in the SEL.
- ✅ **Protocol Compliance:** Prevents visual clutter for operators monitoring large clusters.
- ✅ **Stability:** Does not rely on Subiquity internal state - purely managed via the forensic logging utility.

---

## Verification

After applying the fix, a new ISO was built and deployed. The logs confirmed that the `0x0F` marker now appears exactly once per run, regardless of how many times the `early-commands` are triggered by the installer layer.
