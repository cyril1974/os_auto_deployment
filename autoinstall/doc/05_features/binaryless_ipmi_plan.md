# Implementation Plan: Binary-less IPMI RAW Utility

**Goal**: Replace the dependency on the `ipmitool` binary with a lightweight Python-based "IOCTL wrapper" during the Ubuntu autoinstall process.

---

## Phase 1: Development of `ipmi_raw_lite.py`
Create a standalone Python 3 script that uses the Linux kernel's IPMI `ioctl` interface.

### Key Technical Requirements:
1.  **No External Dependencies**: Must use only standard libraries (`os`, `struct`, `fcntl`, `sys`).
2.  **CLI Compatibility**: Should accept arguments in a format similar to `ipmitool raw` (e.g., `python3 ipmi_raw_lite.py 0x0a 0x44 0x01 0x02 0x03`).
3.  **IOCTL Targeting**:
    -   Target Device: `/dev/ipmi0`.
    -   Address Type: `IPMI_SYSTEM_INTERFACE_ADDR_TYPE` (0x0c).
    -   IOCTL Code: `IPMICTL_SEND_COMMAND` (0x8028690d).

### Success Criteria:
-   Successfully writes an "OS Installation Starting" (Marker 0x01) SEL entry to the BMC.
-   Handles non-hex inputs gracefully.

---

## Phase 2: ISO Builder Integration
Modify the `build-ubuntu-autoinstall-iso.sh` script to incorporate the new utility.

### Step 1: Embedding the Script
-   Inject the `ipmi_raw_lite.py` into the custom ISO's `/usr/local/bin/`.
-   Ensure it has execution permissions (`chmod +x`).

### Step 2: Refactoring `early-commands` and `late-commands`
-   Search for all instances of `ipmitool raw ...`.
-   Replace them with `python3 /usr/local/bin/ipmi_raw_lite.py ...`.
-   **Note**: Retain the `modprobe ipmi_si ipmi_devintf` calls as the Python script still requires the kernel drivers.

---

## Phase 3: Transition & Cleanup
Once the Python utility is verified:

1.  **Dependency Removal**: Update the `OFFLINE_PACKAGES` list in the builder script to remove `ipmitool` and `freeipmi-common`.
2.  **Fallback Logic (Optional)**: If Python is unavailable (e.g., safe mode), keep a minimal binary fallback or log a clear error.
3.  **Documentation Update**: Update `doc/01_architecture_and_flow.md` and `autoinstall/doc/17_sel_logging_commands.md` to reflect the tool change.

---

## Phase 4: Verification & Testing
1.  **Baseline Test**: Prove the Python script can communicate on node 10.99.236.85.
2.  **Integration Test**: Build a "Lite" ISO and perform a full autoinstall.
3.  **Log Audit**: Verify the BMC SEL for markers `0x01` (Start), `0x01/0x02` (IP), and `0x02` (Completed).

---

## Timeline & Risks
-   **Timeline**: 1-2 days for development and testing.
-   **Risk (Architecture)**: 64-bit vs 32-bit `struct` packing differences for the `ioctl` buffer. (Must be tested on target hardware).
-   **Risk (Environment)**: Requires `python3` to be present in the installer environment (default on Ubuntu Live ISOs).
