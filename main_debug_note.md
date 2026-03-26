# Debug Note: Forensic IP Reporting and Payload Reconstruction

## Issue: Incorrect IP Address Reporting (10.99.236.0 vs 10.99.236.106)

**Date:** 2026-03-26
**Symptoms:** The forensic monitor reported `10.99.236.0` for a node whose actual IP was `10.99.236.106`. The Part 2 IP marker (Code `0x13`) showed `EC00` in the BMC SEL, indicating the 4th octet was incorrectly captured as `0`.

### Debugging Steps

1.  **Target Access:**
    - Logged into the target node `root@10.99.236.106` (password: `ubuntu`).
2.  **IP Identification:**
    - Ran `hostname -I`. Output included multiple IP addresses: `10.99.236.106 192.168.90.134 172.17.0.1`.
3.  **Command Validation:**
    - Tested the original parsing logic: `IP=$(hostname -I | awk '{print $1}')` and `o4=$(echo $IP | cut -d. -f4)`.
    - Identified a potential race condition or field-split issue where `hostname -I` output could be inconsistent or include trailing characters that confused `cut`.
    - Also discovered that if the subshell expanded `awk "{print \$1}"` incorrectly during the ISO build process (due to escaping issues in `cat << EOF`), the resulting `IP` variable could contain multiple addresses, further breaking `cut`.
4.  **Payload Analysis (`main.py`):**
    - Reviewed the Gen-7 reconstruction logic: `eventMessage = eventMessage_raw + item["SENSOR_DATA"][-4:]`.
    - Realized that slicing `[-4:]` (taking only the 2 data bytes) would result in a misaligned `StatusCode` lookup ([index -6:-4]) if the marker itself was not present in the base `Message`.

### Root Causes

- **Parsing Fragility:** Using `cut` on a variable that might contain multiple space-separated IPs is prone to failure if the field index is not strictly controlled.
- **Payload Truncation:** Concatenating only the data portion of `SENSOR_DATA` without the marker byte broke index-based forensic decoding on modern firmware.

### Solutions Implemented

1.  **Robust Shell Extraction:**
    - Switched to `eval $(echo "$IP" | awk -F. '{printf "o1=%s; o2=%s; o3=%s; o4=%s", $1, $2, $3, $4}')`.
    - This approach forces a strict field split on dots for Exactly one IP address, ensuring Octet 4 is always isolated correctly.
    - Added `printf` error handling to default octets to `0x00` rather than empty strings.
2.  **Full Payload Reconstruction:**
    - Updated `main.py` to use the **full 6-character `SENSOR_DATA`** (Marker + Byte1 + Byte2).
    - This ensures `eventMessage` always contains the marker at the offset expected by the `StatusCode` parser.
3.  **Escaping Fix:**
    - Ensured that `awk` field variables (`$1`, etc.) in the `autoinstall` heredoc are correctly escaped for both the ISO-generation bash shell and the target's installation shell.

---
**Verification:**
- Re-run the IP parsing logic on the target node confirms correct hex conversion (`0x6a` for `106`).
- Monitoring engine now correctly handles appended payloads without truncating the marker.
