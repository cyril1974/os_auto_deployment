# Debug: `match: { size: 7T }` — Installation Ignores Size Constraint, Installs on Wrong Disk

**Date:** 2026-04-09
**Symptom:** ISO built with `--storage-size=7T` installs onto `/dev/nvme0n1` (a small NVMe)
instead of the intended 7T HDD/SSD. No error is reported by Subiquity — installation
appears to complete normally but lands on the wrong disk.

---

## 1. Observed Behaviour

Generated `user-data` storage section:

```yaml
storage:
  config:
    - type: disk
      id: disk-main
      match:
        size: 7T          ← this key is silently ignored by Subiquity
      ptable: gpt
      wipe: superblock-recursive
      preserve: false
```

Expected: Subiquity selects the 7T drive.
Actual: Subiquity selects `/dev/nvme0n1` (first disk in enumeration order).

---

## 2. Root Cause

### `size` is not a valid Subiquity `match` key

Subiquity's disk selection engine (curtin `select_devices()`) only recognises the
following keys inside a `type: disk` → `match:` block:

| Key | Matches against |
|---|---|
| `serial` | udev `ID_SERIAL` |
| `model` | udev `ID_MODEL` |
| `path` | device path glob (e.g. `/dev/sda`, `/dev/nvme*`) |
| `id_path` | udev `ID_PATH` |
| `sysfs_businfo` | PCI/USB bus info string |

**`size` is not in this list.** When curtin encounters an unrecognised key in the
`match` dict, it silently ignores it. With no valid constraint remaining, the match
degenerates to "any disk" and curtin picks the first disk in enumeration order —
which is `/dev/nvme0n1` on most systems.

### Why the builder accepted `--storage-size=7T` without error

The original implementation of `--storage-size` in both the Go builder
(`build-iso-go/main.go`) and the shell builder (`build-ubuntu-autoinstall-iso.sh`)
blindly templated the flag key/value into the `match:` block:

```yaml
# what the template produced — WRONG
match:
  {{.StorageMatchKey}}: {{.StorageMatchValue}}
# → match: { size: 7T }
```

There was no validation that the key was actually supported by Subiquity. The builder
silently produced invalid YAML that Subiquity then silently ignored at install time.

---

## 3. Subiquity Log Evidence

When `match: { size: 7T }` is used, Subiquity's
`/var/log/installer/subiquity-server-debug.log` shows:

```
INFO  considering [Disk(path='/dev/nvme0n1', ...), Disk(path='/dev/sda', ...)]
INFO  disk /dev/nvme0n1 matches {}
INFO  selecting /dev/nvme0n1 for disk-main
```

Key observations:
- The `match` dict shown as `{}` — curtin stripped `size` as unrecognised.
- The **first** disk enumerated (`nvme0n1`) is selected without any size check.
- No warning or error about the unknown `size` key is emitted.

---

## 4. Fix Applied

`--storage-size=<val>` is reinterpreted to use `find_disk.sh` with a size hint rather
than embedding an invalid key in user-data.

### Build time

Both builders now treat `--storage-size=<val>` as a size hint for `find_disk.sh`:

```
--storage-size=7T
  → StorageMatchKey  = "serial"
  → StorageMatchValue = "__ID_SERIAL__"      (same as auto-detect mode)
  → FindDiskSizeHint  = "7T"                 (passed to find_disk.sh at boot)
  → FindDiskEnabled   = true                 (find_disk.sh IS copied to ISO)
```

The generated `user-data` now correctly uses `serial` as the match key:

```yaml
match:
  serial: __ID_SERIAL__     ← valid Subiquity key; patched at boot by find_disk.sh
```

### Boot time (early-commands)

The early-command that runs `find_disk.sh` now includes the size argument:

```yaml
early-commands:
  - |
    if [ -f /cdrom/autoinstall/scripts/find_disk.sh ]; then
        sh /cdrom/autoinstall/scripts/find_disk.sh --target-size=7T
    fi
```

### find_disk.sh — new `--target-size` parameter

`autoinstall/scripts/find_disk.sh` was extended to accept `--target-size=<val>`:

- Parses value + unit (T/G/M/K, decimal digits only, case-insensitive) → bytes.
- Adds a `size_matches_target()` check: passes when actual disk size is within ±10% of
  the target (tolerates marketing vs binary size differences and manufacturing variance).
- When `--target-size` is set: first qualifying disk wins (break on first match).
- When `--target-size` is absent: smallest empty disk wins (original behaviour).

Example for `--target-size=7T`:

```
7T = 7 × 1024^4 = 7,696,581,394,432 bytes
tolerance ±10%:
  lower = 6,926,923,255,089 bytes  (~6.3 TB)
  upper = 8,466,239,533,875 bytes  (~7.7 TB)

A 7.27 TB drive (7,997,006,036,992 bytes) → within range → selected
A 960 GB NVMe  (1,024,209,543,168 bytes)  → outside range → skipped
```

After the correct disk is found, its `ID_SERIAL` is written into
`/autoinstall.yaml` exactly as in auto-detect mode:

```
sed -i "s/__ID_SERIAL__/S6CKNT0W700868/g" /autoinstall.yaml
```

Subiquity then sees `match: { serial: S6CKNT0W700868 }` — a valid, exact match.

### Full corrected flow

```
Build time                          Boot time (early-commands)
──────────────────────────────      ──────────────────────────────────────────────
ISO contains:                       find_disk.sh --target-size=7T
  match:                              │
    serial: __ID_SERIAL__             ├─ sda  : 7.3T → within ±10% of 7T → candidate
  early-commands:                     ├─ nvme0n1: 953G → outside range → skipped
    find_disk.sh --target-size=7T     ├─ get ID_SERIAL of sda → S6CKNT0W700868
                                      └─ sed __ID_SERIAL__ → S6CKNT0W700868
                                                 ↓
                                    Subiquity reads: match: { serial: S6CKNT0W700868 }
                                    → correct 7T disk selected ✓
```

---

## 5. Files Changed

| File | Change |
|---|---|
| `autoinstall/scripts/find_disk.sh` | Added `--target-size=` parameter, `size_matches_target()`, size-filter mode |
| `autoinstall/build-iso-go/main.go` | `--storage-size` now sets `FindDiskSizeHint`; no longer writes `size:` to match block; `BuildConfig` gains `FindDiskSizeHint string`; template passes `--target-size` to find_disk.sh |
| `autoinstall/build-ubuntu-autoinstall-iso.sh` | Same logic; `FIND_DISK_SIZE_HINT` variable; early-command block builds `FIND_DISK_CMD` with optional `--target-size` |

---

## 6. How to Get the Correct Model or Serial (Alternative Approaches)

If size-based selection is not precise enough (e.g. two disks of the same size),
use serial or model instead:

```bash
# Get udev ID_SERIAL for all disks
for d in $(lsblk -nd -o NAME); do
    echo -n "/dev/$d  "
    udevadm info --query=property --name=/dev/$d | grep "^ID_SERIAL="
done

# Get udev ID_MODEL for all disks
for d in $(lsblk -nd -o NAME); do
    echo -n "/dev/$d  "
    udevadm info --query=property --name=/dev/$d | grep "^ID_MODEL="
done
```

Then build with the exact udev string:

```bash
# By serial (most precise — one specific physical disk)
sudo ./build-iso-go/build-iso ubuntu-24.04.2-live-server-amd64 --storage-serial=S6CKNT0W700868

# By model (works across identical disks in a fleet)
sudo ./build-iso-go/build-iso ubuntu-24.04.2-live-server-amd64 --storage-model=TOSHIBA_MG08ACA14TE
```

---

## 7. Key Takeaway

> Subiquity's `match:` block for `type: disk` only supports `serial`, `model`, `path`,
> `id_path`, and `sysfs_businfo`. Any other key (including `size`) is **silently ignored**
> and the match degenerates to "select any disk". No error or warning is produced.
> Always verify the generated `user-data` against the
> [Subiquity storage reference](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html#storage)
> when adding new match criteria.
