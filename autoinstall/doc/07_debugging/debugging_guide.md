# Debugging & Troubleshooting Guide

## Common Issues & Solutions

### Issue 1: ISO Not Appearing in UEFI Boot Menu

**Symptoms:**
- ISO mounts successfully via BMC
- Shows as BLK device in UEFI shell
- Not listed in boot options

**Diagnosis:**
```bash
# Check partition table type
fdisk -l your_custom.iso

# Should show:
# Disklabel type: gpt  ← Must be GPT, not dos
```

**Root Cause:**
- Missing GPT partition table
- Missing EFI System partition

**Solution:**
Ensure xorriso command includes:
```bash
-append_partition 2 0xEF "$EFI_IMG"
--grub2-mbr "$MBR_FILE"
-appended_part_as_gpt
```

**Verification:**
```bash
# Check for GPT and EFI partition
fdisk -l custom.iso | grep -E "gpt|EFI System"
```

---

### Issue 2: GRUB Error - Can't Find Command 'grub_platform'

**Symptoms:**
```
error: can't find command 'grub_platform'.
```

**Diagnosis:**
```bash
# Check for standalone grub_platform command
grep -n "^grub_platform$" workdir_custom_iso/boot/grub/grub.cfg
```

**Root Cause:**
- Invalid standalone `grub_platform` command in grub.cfg
- Should be used in conditional, not standalone

**Solution:**
Remove the standalone command:
```python
new_txt = re.sub(r'^\s*grub_platform\s*$', '', new_txt, flags=re.MULTILINE)
```

**Verification:**
```bash
# Should return nothing
grep "^grub_platform$" workdir_custom_iso/boot/grub/grub.cfg
```

---

### Issue 3: Kernel Load Error - Invalid Sector Size

**Symptoms:**
```
error: invalid sector size 0.
error: you need to load the kernel first.
```

**Diagnosis:**
```bash
# Check if search command exists in grub.cfg
grep "search.*vmlinuz" workdir_custom_iso/boot/grub/grub.cfg
```

**Root Cause:**
- GRUB can't find ISO filesystem with kernel
- Missing search command to mount ISO

**Solution:**
Add search command before loading kernel:
```
search --no-floppy --set=root --file /casper/vmlinuz
linux   /casper/vmlinuz autoinstall ...
initrd  /casper/initrd
```

**Verification:**
```bash
# Check GRUB menu entry
grep -A 5 "Auto Install" workdir_custom_iso/boot/grub/grub.cfg
```

---

### Issue 4: Cloud-Init Crash - NoneType Error

**Symptoms:**
```
'NoneType' object has no attribute 'id'
```

**Diagnosis:**
```bash
# Check user-data structure
cat workdir_custom_iso/autoinstall/user-data | grep -A 20 "user-data:"
```

**Root Cause:**
- Nested `user-data` section inside `autoinstall`
- Invalid configuration structure

**Solution:**
Remove nested user-data section:
```yaml
autoinstall:
  version: 1
  identity: ...
  ssh: ...
  # Remove this entire section:
  # user-data:
  #   users: ...
```

**Verification:**
```bash
# Should not have nested user-data
! grep -q "^  user-data:" workdir_custom_iso/autoinstall/user-data
```

---

### Issue 5: Package Installation Failure

**Symptoms:**
```
Command ['systemd-run', ...] returned non-zero exit status 100.
```

**Diagnosis:**
```bash
# Check if packages are in autoinstall section
grep -A 10 "packages:" workdir_custom_iso/autoinstall/user-data
```

**Root Cause:**
- Network unavailable during early installation
- Package installation timing issues

**Solution:**
Move packages to late-commands:
```yaml
late-commands:
  - curtin in-target --target=/target -- apt-get update
  - curtin in-target --target=/target -- apt-get install -y vim curl || true
```

**Verification:**
```bash
# Packages should be in late-commands
grep "apt-get install" workdir_custom_iso/autoinstall/user-data
```

---

## Debugging Tools & Techniques

### During ISO Build

**Enable verbose output:**
```bash
# Add -x to script for debugging
bash -x ./build-ubuntu-autoinstall-iso.sh iso.iso user pass
```

**Check intermediate files:**
```bash
# Verify autoinstall config
cat workdir_custom_iso/autoinstall/user-data

# Check GRUB config
cat workdir_custom_iso/boot/grub/grub.cfg

# Verify EFI image contents
mdir -i /tmp/efi.img ::/
mdir -i /tmp/efi.img ::/boot/grub/
```

**Validate ISO structure:**
```bash
# Check ISO info
isoinfo -d -i output_custom_iso/*.iso

# Check partition table
fdisk -l output_custom_iso/*.iso

# Verify file type
file output_custom_iso/*.iso
```

### During Installation

**Access logs in live environment:**
```bash
# Switch to TTY2
# Press Alt+F2

# View main installer log
tail -f /var/log/installer/subiquity-server-debug.log

# View curtin log
tail -f /var/log/installer/curtin-install.log

# View cloud-init logs
tail -f /var/log/cloud-init.log
tail -f /var/log/cloud-init-output.log

# System journal
journalctl -f
```

**Search for errors:**
```bash
# Find errors in logs
grep -i error /var/log/installer/*.log
grep -i fail /var/log/installer/*.log

# Check crash reports
ls -la /var/crash/
cat /var/crash/*.crash
```

**Network debugging:**
```bash
# Check network status
ip addr
ip route
ping -c 3 8.8.8.8

# DNS resolution
cat /etc/resolv.conf
nslookup archive.ubuntu.com
```

### Post-Installation

**Verify configuration:**
```bash
# Check user creation
id username
id root

# Check sudo access
sudo -l -U username

# Check SSH configuration
grep PermitRootLogin /etc/ssh/sshd_config
grep PasswordAuthentication /etc/ssh/sshd_config

# Check installed packages
dpkg -l | grep -E "vim|curl|net-tools"
```

## Log File Reference

| Log File | Purpose | Key Information |
|----------|---------|-----------------|
| `/var/log/installer/subiquity-server-debug.log` | Main installer log | Configuration parsing, installation steps |
| `/var/log/installer/curtin-install.log` | Curtin backend log | Disk partitioning, package installation |
| `/var/log/cloud-init.log` | Cloud-init processing | User-data parsing, module execution |
| `/var/log/cloud-init-output.log` | Cloud-init command output | Script execution results |
| `/var/crash/*.crash` | Crash dumps | Python tracebacks, error details |

## Quick Diagnostic Commands

```bash
# Check ISO boot capability
file custom.iso | grep -i boot

# Verify GPT partition table
gdisk -l custom.iso 2>/dev/null | grep GPT

# Check EFI partition
fdisk -l custom.iso | grep "EFI System"

# Verify GRUB config syntax
grub-script-check workdir_custom_iso/boot/grub/grub.cfg

# Test password hash
echo 'password' | mkpasswd -m sha-512 -s

# Validate user-data YAML
python3 -c "import yaml; yaml.safe_load(open('workdir_custom_iso/autoinstall/user-data'))"
```

## Error Code Reference

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| 1 | ISO not found | Check ISO path |
| 2 | Missing dependencies | Run apt install |
| 100 | Package install fail | Check network, move to late-commands |
| 127 | Command not found | Install required packages |

## Recovery Procedures

### Failed Build Recovery
```bash
# Clean up and retry
rm -rf workdir_custom_iso output_custom_iso
./build-ubuntu-autoinstall-iso.sh iso.iso user pass
```

### Failed Installation Recovery
```bash
# From installation failure shell
# Copy logs for analysis
mkdir /tmp/logs
cp -r /var/log/installer /tmp/logs/
cp /var/log/cloud-init* /tmp/logs/

# Mount USB or network share to save logs
# Then reboot and retry
```

### Corrupted ISO Recovery
```bash
# Verify ISO integrity
md5sum custom.iso
sha256sum custom.iso

# Compare with build log checksums
# Rebuild if corrupted
```
