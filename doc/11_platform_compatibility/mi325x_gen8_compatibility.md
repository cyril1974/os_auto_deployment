# Mi325x (Gen 8) Platform Compatibility Adjustments

This document records every Redfish behaviour difference discovered on the
MiTAC Mi325x (BMC generation 8) and the corresponding code changes made to
`remote_mount.py` and `reboot.py`.

---

## Platform Overview

| Attribute | Value |
|-----------|-------|
| Platform | MiTAC Mi325x |
| BMC Generation | 8 |
| BMC Firmware | AMI-based |
| Redfish Base URL | `https://<bmc-ip>/redfish/v1` |
| Systems endpoint | `/redfish/v1/Systems/Self` |
| Managers endpoint | `/redfish/v1/Managers/Self` |

---

## 1. Virtual Media — Remote Media Must Be Explicitly Enabled

### Symptom

On Gen 6/7, `GET /redfish/v1/Managers/Self/VirtualMedia` (or the equivalent
path) immediately returns populated `Members`. On Gen 8, `Members` is empty
until the AMI OEM action is called to enable remote media.

### Root Cause

Gen 8 BMC ships with remote media in a disabled state. It must be activated
via an AMI OEM Redfish action before the standard `VirtualMedia` collection
becomes usable.

### Resolution

Added `_enable_rmedia_gen8()` in `remote_mount.py`, called from
`_fetch_virtual_media()` before the normal GET when `gen == '8'`.

**Enable endpoint:**
```
POST /redfish/v1/Managers/Self/Actions/Oem/AMIVirtualMedia.EnableRMedia
Content-Type: application/json

{"RMediaState": "Enable"}
```

**Pre-check (avoid redundant enables):**

Before sending the POST, the function GETs
`/redfish/v1/Managers/Self/VirtualMedia` and inspects `Members`. If
`Members` is already non-empty, the POST is skipped and a message is printed:

```
[Gen8] Remote media already enabled (1 member(s) present), skipping EnableRMedia.
```

After the POST, a **5-second sleep** is inserted to allow the BMC to
initialise the virtual media collection before the subsequent GET.

**Files changed:** `src/os_deployment/lib/remote_mount.py`

---

## 2. Virtual Media — Mount Point Selection Filter

### Symptom

On Gen 6/7, only entries whose `@odata.id` contains `"WebISO"` are valid
ISO mount points. All other members (e.g. floppy, USB) must be excluded.
On Gen 8, all `Members` entries are valid and should be considered.

### Resolution

Updated `_get_candidate_mount_point()` to apply the `"WebISO"` filter only
for Gen 6 and 7:

```python
return [
    m.get("@odata.id") for m in members
    if gen not in ('6', '7') or "WebISO" in (m.get("@odata.id") or "")
]
```

**Files changed:** `src/os_deployment/lib/remote_mount.py`

---

## 3. Virtual Media — InsertMedia Payload Difference

### Symptom

On Gen 6/7, the `InsertMedia` POST body requires `UserName` and `Password`
fields. On Gen 8, sending these fields causes the request to fail.

### Resolution

`exec_mount_image()` now builds the payload conditionally:

```python
# Gen 8 — no UserName / Password
if gen == '8':
    data = {"Image": mount_path, "WriteProtected": True,
            "TransferProtocolType": "NFS", "Inserted": True}
# Gen 6/7
else:
    data = {"Image": mount_path, "UserName": "", "Password": "",
            "WriteProtected": True, "TransferProtocolType": "NFS", "Inserted": True}
```

**Files changed:** `src/os_deployment/lib/remote_mount.py`

---

## 4. Virtual Media — Redirection Status Polling After Mount

### Symptom

On Gen 6/7, a successful `InsertMedia` POST (HTTP 200/202/204) is sufficient
confirmation that the ISO is mounted. On Gen 8, the POST returns success
immediately but the actual media redirection is asynchronous — the ISO is not
usable until the BMC reports it has started.

### Resolution

After `exec_mount_image()` succeeds on Gen 8, `mount_image()` polls
`GET <endpoint>` (e.g. `/redfish/v1/Managers/Self/VirtualMedia/CD1`) every
3 seconds for up to 60 seconds, checking:

```
response["Oem"]["Ami"]["RedirectionStatus"]
```

| Condition | Action |
|-----------|--------|
| Value contains `"Started"` | Print success message, return mount point |
| 60 s timeout reached | `sys.exit` with last seen `RedirectionStatus` value |

**Example success response field:**
```json
"RedirectionStatus": "Redirection Started With Media Boost"
```

**Console output:**
```
⏳ Mount starting — waiting for redirection on /redfish/v1/Managers/Self/VirtualMedia/CD1 ...
✅ Mount started: Redirection Started With Media Boost
```

**Files changed:** `src/os_deployment/lib/remote_mount.py`

---

## 5. Boot Order — ETag Required for PATCH

### Symptom

On Gen 6/7, `PATCH /redfish/v1/Systems/system` (boot override) succeeds
with a standard `Content-Type: application/json` request.

On Gen 8, the same PATCH to `/redfish/v1/Systems/Self` returns:

```
HTTP 412 Precondition Failed
"The request to /redfish/v1/Systems/Self cannot be completed because
 the If-Match precondition failed"
```

### Root Cause

Gen 8 BMC enforces optimistic concurrency control on `Systems/Self`. Every
PATCH must include an `If-Match` header whose value matches the current
`ETag` returned by a prior GET on the same resource.

### Resolution

Added `_fetch_etag_gen8()` in `reboot.py`. When `gen == '8'`,
`_set_boot_cdrom()` performs a two-step flow:

**Step 1 — Fetch current ETag:**
```
GET /redfish/v1/Systems/Self
→ response header:  ETag: "1776395333"
```

The ETag is read verbatim from the response header (quotes included), as
the server requires an exact string match.

**Step 2 — PATCH with If-Match:**
```
PATCH /redfish/v1/Systems/Self
If-Match: "1776395333"
Content-Type: application/json

{
  "Boot": {
    "BootSourceOverrideTarget": "UefiShell",
    "BootSourceOverrideEnabled": "Once",
    "BootSourceOverrideMode": "UEFI"
  }
}
```

Note: Gen 8 also requires `"BootSourceOverrideMode": "UEFI"` in the boot
payload. Gen 6/7 omit this field.

**Files changed:** `src/os_deployment/lib/reboot.py`

---

## Summary Table

| # | Area | Gen 6/7 Behaviour | Gen 8 Behaviour | Code Location |
|---|------|--------------------|-----------------|---------------|
| 1 | VirtualMedia enable | Not required | Must POST `EnableRMedia` first | `remote_mount._enable_rmedia_gen8` |
| 2 | Mount point filter | `"WebISO"` entries only | All `Members` entries | `remote_mount._get_candidate_mount_point` |
| 3 | InsertMedia payload | Requires `UserName`/`Password` | Must omit `UserName`/`Password` | `remote_mount.exec_mount_image` |
| 4 | Mount confirmation | HTTP 2xx is sufficient | Poll `RedirectionStatus` until `"Started"` | `remote_mount.mount_image` |
| 5 | Boot PATCH | No `If-Match` needed | Must GET ETag first, send `If-Match` | `reboot._fetch_etag_gen8`, `reboot._set_boot_cdrom` |
| 5 | Boot payload | No `BootSourceOverrideMode` | Requires `"BootSourceOverrideMode": "UEFI"` | `reboot._set_boot_cdrom` |

---

## Related Files

| File | Changes |
|------|---------|
| `src/os_deployment/lib/remote_mount.py` | Items 1–4 |
| `src/os_deployment/lib/reboot.py` | Item 5 |
