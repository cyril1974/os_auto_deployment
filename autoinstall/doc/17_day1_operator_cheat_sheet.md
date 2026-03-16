# Day-1 Operator Cheat Sheet (Autoinstall ISO)

This guide is for first-time operators who need to generate and use an unattended Ubuntu install ISO quickly.

## 0) Pre-flight checklist

- Confirm you are in repo root:
  ```bash
  pwd
  ```
- Ensure source ISO inventory file exists:
  ```bash
  test -f iso_repository/file_list.json && echo OK
  ```
- Verify your target OS name is present:
  ```bash
  jq -r '.tree.Ubuntu[].OS_Name' iso_repository/file_list.json
  ```

---

## 1) Build one autoinstall ISO

## Basic build

```bash
cd autoinstall
bash ./build-ubuntu-autoinstall-iso.sh ubuntu-22.04.5-live-server-amd64 admin ubuntu
```

## Build without auto-installing dependencies

```bash
cd autoinstall
bash ./build-ubuntu-autoinstall-iso.sh ubuntu-22.04.5-live-server-amd64 admin ubuntu --skip-install
```

## Help

```bash
cd autoinstall
bash ./build-ubuntu-autoinstall-iso.sh --help
```

---

## 2) Verify output artifacts

```bash
cd autoinstall
ls -lh output_custom_iso/
```

Expected:
- New ISO named similar to:
  `ubuntu_22.04.5_live_server_amd64_autoinstall_<timestamp>.iso`

Also generated:
- SSH keys under `~/.ssh/id_ed25519_<timestamp>_<random>[.pub]`

---

## 3) Quick sanity checks before mounting in BMC

## Check GRUB config was patched in workdir

```bash
cd autoinstall
rg -n "Auto Install Ubuntu Server|autoinstall|ds=nocloud|preseed" workdir_custom_iso/boot/grub/grub.cfg
```

## Check cloud-init files exist (20.04+)

```bash
cd autoinstall
ls -l workdir_custom_iso/autoinstall/{user-data,meta-data}
```

## Check preseed exists (18.04 build)

```bash
cd autoinstall
test -f workdir_custom_iso/preseed.cfg && echo "preseed present"
```

---

## 4) BMC deployment flow (operator runbook)

1. Upload/mount generated ISO as virtual CD/DVD in BMC
2. Set one-time boot to virtual media (UEFI preferred unless environment requires BIOS)
3. Boot target server
4. Wait for unattended install to complete and automatic reboot
5. Log in with configured username/password or SSH key

---

## 5) First-login validation on target host

After installation:

```bash
# identity
hostnamectl
whoami

# ssh server
sudo systemctl status ssh --no-pager

# network
ip a
ip r

# optional packages expected by late-commands
dpkg -l | rg "vim|curl|net-tools|ipmitool|htop"

# sudo policy check
sudo -l
```

---

## 6) Fast troubleshooting

## Build-time issues

- **"OS name not found"**
  - Check exact string in `iso_repository/file_list.json`
- **"Original ISO not found"**
  - Validate resolved `OS_Path` points to a real file
- **Missing packages/tools**
  - Re-run without `--skip-install`, or install manually

## Boot/install-time issues

- **Drops into interactive menu**
  - Re-check patched GRUB/ISOLINUX entries in `workdir_custom_iso`
- **Autoinstall not detected**
  - Verify kernel args include `autoinstall ds=nocloud;s=/cdrom/autoinstall/`
- **18.04 does not behave like 22.04+**
  - Expected: 18.04 follows preseed compatibility path

## Log locations to inspect (installer environment)

- `/var/log/syslog`
- `/var/log/installer/subiquity-server-debug.log*`
- `/var/log/installer/subiquity-client-debug.log*`

---

## 7) Recommended day-1 defaults

- Start with Ubuntu 22.04 LTS image
- Keep username simple (e.g., `admin`)
- Use temporary password for provisioning only, rotate after install
- Prefer key-based SSH once first boot is confirmed
- Validate on one test node before rolling out to full fleet

---

## 8) Related docs

- `01_architecture.md`
- `02_workflow.md`
- `04_debugging_guide.md`
- `16_beginner_architecture_and_workflow.md`
