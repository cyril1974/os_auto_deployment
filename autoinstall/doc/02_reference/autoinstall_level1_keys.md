# Ubuntu Autoinstall — Level-1 Key Complete Reference
> `autoinstall.yaml` top-level keys | Ubuntu 20.04 LTS and later (Subiquity installer)  
> Source: [Canonical Autoinstall Reference](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html)

---

## Overview

The autoinstall file is YAML. The single root key is `autoinstall:`, under which all level-1 keys are placed. <br>
**Unrecognized keys are ignored in version 1** but will cause a fatal validation error in future versions.

```yaml
#cloud-config          ← required header when delivering via cloud-init
autoinstall:
  version: 1           ← REQUIRED
  <key>: <value>
  ...
```

> **NOTE (24.04+):** Starting with Ubuntu 24.04 Noble, any unrecognized key under `autoinstall:` causes a runtime validation error. On earlier ISOs, they are silently ignored.

---

## All Level-1 Keys at a Glance

| Key | Type | Required | Interactive | Purpose |
|-----|------|----------|-------------|---------|
| [`version`](#1-version) | integer | **Yes** | No | Schema version (must be `1`) |
| [`interactive-sections`](#2-interactive-sections) | list | No | — | Pause installer at specified screens |
| [`early-commands`](#3-early-commands) | command list | No | No | Run before device probing |
| [`locale`](#4-locale) | string | No | Yes | System locale |
| [`refresh-installer`](#5-refresh-installer) | mapping | No | Yes | Auto-update Subiquity before install |
| [`keyboard`](#6-keyboard) | mapping | No | Yes | Keyboard layout settings |
| [`source`](#7-source) | mapping | No | Yes | Installation source / variant |
| [`network`](#8-network) | mapping | No | Yes | Netplan network configuration |
| [`proxy`](#9-proxy) | URL/null | No | Yes | HTTP proxy for apt and snapd |
| [`apt`](#10-apt) | mapping | No | Yes | APT mirror and source configuration |
| [`storage`](#11-storage) | mapping | No | Yes | Disk layout and partitioning |
| [`identity`](#12-identity) | mapping | No* | Yes | Initial user and hostname |
| [`active-directory`](#13-active-directory) | mapping | No | Yes | Join AD domain |
| [`ubuntu-pro`](#14-ubuntu-pro) | mapping | No | Yes | Ubuntu Pro subscription token |
| [`ssh`](#15-ssh) | mapping | No | Yes | OpenSSH server configuration |
| [`codecs`](#16-codecs) | mapping | No | No | Restricted codec packages |
| [`drivers`](#17-drivers) | mapping | No | Yes | Third-party driver installation |
| [`oem`](#18-oem) | mapping | No | No | OEM meta-package installation |
| [`snaps`](#19-snaps) | list | No | No | Snap packages to install |
| [`packages`](#20-packages) | list | No | No | Apt packages to install |
| [`timezone`](#21-timezone) | string | No | Yes | System timezone |
| [`updates`](#22-updates) | string | No | No | Which updates to apply post-install |
| [`reporting`](#23-reporting) | mapping | No | No | Installation progress reporting |
| [`error-commands`](#24-error-commands) | command list | No | No | Run on fatal installer error |
| [`late-commands`](#25-late-commands) | command list | No | No | Run after installation, before reboot |
| [`user-data`](#26-user-data) | mapping | No | No | cloud-init user-data for first boot |
| [`shutdown`](#27-shutdown) | string | No | No | Action after install completes |
| [`debconf-selections`](#28-debconf-selections) | string | No | No | Preseed debconf values |
| [`swap`](#29-swap) | mapping | No | No | Swap file size |

> \* `identity` is **required** unless `user-data` is present instead.

---

## 1. version

| | |
|---|---|
| **Type** | integer |
| **Required** | **Yes** |
| **Default** | none |
| **Interactive** | No |

A future-proofing schema version field. Currently must always be `1`.

```yaml
autoinstall:
  version: 1
```

---

## 2. interactive-sections

| | |
|---|---|
| **Type** | list of strings |
| **Required** | No |
| **Default** | `[]` (fully unattended) |
| **Interactive** | — |

A list of configuration keys whose corresponding installer screens should still be shown to the user. Any provided value for that section becomes the screen's default. Use `"*"` to make the installer ask all questions (useful for default-override mode).

> **NOTE:** If any interactive sections are defined, the `reporting` key is ignored.

**Valid section names** (those that have corresponding UI screens):
`locale`, `keyboard`, `source`, `network`, `proxy`, `apt`, `storage`, `identity`, `active-directory`, `ubuntu-pro`, `ssh`, `drivers`, `timezone`, `updates`

```yaml
autoinstall:
  version: 1
  interactive-sections:
    - network        # pause on the network screen
    - storage        # pause on the storage screen
  identity:
    username: ubuntu
    password: $6$...

# Pause on ALL screens (use autoinstall only for defaults)
autoinstall:
  version: 1
  interactive-sections:
    - "*"
```

---

## 3. early-commands

| | |
|---|---|
| **Type** | list of strings or lists |
| **Required** | No |
| **Default** | no commands |
| **Interactive** | No |

Shell commands run immediately after the installer starts, **before** block and network devices are probed. The autoinstall config is available at `/autoinstall.yaml` and is **re-read** after these commands finish, allowing dynamic configuration replacement.

Each command can be:
- A **string** → executed via `sh -c`
- A **list** → executed directly (no shell)

Any command returning non-zero aborts the installation.

```yaml
autoinstall:
  early-commands:
    # Wait for a signal file before proceeding (manual inspection mode)
    - while [ ! -f /run/finish-early ]; do sleep 1; done

    # Fetch a remote autoinstall config and replace the current one
    - wget -O /autoinstall.yaml http://config-server.local/autoinstall.yaml

    # Load a kernel module before device probing
    - modprobe megaraid_sas

    # Using list form (no shell expansion)
    - [sh, -c, "echo nameserver 8.8.8.8 > /etc/resolv.conf"]
```

---

## 4. locale

| | |
|---|---|
| **Type** | string |
| **Required** | No |
| **Default** | `en_US.UTF-8` |
| **Interactive** | Yes |

The locale to configure in the installed system. Sets language, number format, date format, and character encoding.

```yaml
autoinstall:
  locale: en_US.UTF-8    # default

autoinstall:
  locale: zh_TW.UTF-8    # Traditional Chinese (Taiwan)

autoinstall:
  locale: ja_JP.UTF-8    # Japanese

autoinstall:
  locale: de_DE.UTF-8    # German
```

---

## 5. refresh-installer

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | `update: false` |
| **Interactive** | Yes |

Controls whether Subiquity (the installer) updates itself from a snap channel before proceeding with installation.

### Sub-keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `update` | boolean | `false` | Whether to auto-update the installer |
| `channel` | string | `stable/ubuntu-$REL` | Snap channel to check for updates |

```yaml
autoinstall:
  refresh-installer:
    update: true
    channel: latest/stable     # latest stable release

autoinstall:
  refresh-installer:
    update: true
    channel: latest/edge       # latest development build

autoinstall:
  refresh-installer:
    update: false              # skip update (default)
```

---

## 6. keyboard

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | US English (`layout: us`) |
| **Interactive** | Yes |

Keyboard layout settings. Maps to `/etc/default/keyboard` in the installed system.

### Sub-keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `layout` | string | `us` | XKB layout code (maps to `XKBLAYOUT`) |
| `variant` | string | `""` | XKB variant (maps to `XKBVARIANT`) |
| `toggle` | string/null | `null` | Layout toggle shortcut (`grp:` option in `XKBOPTIONS`) |

### toggle values

`caps_toggle`, `toggle`, `rctrl_toggle`, `rshift_toggle`, `rwin_toggle`, `menu_toggle`, `alt_shift_toggle`, `ctrl_shift_toggle`, `ctrl_alt_toggle`, `alt_caps_toggle`, `lctrl_lshift_toggle`, `lalt_toggle`, `lctrl_toggle`, `lshift_toggle`, `lwin_toggle`, `sclk_toggle`

```yaml
autoinstall:
  keyboard:
    layout: us               # US English (default)

autoinstall:
  keyboard:
    layout: gb               # British English

autoinstall:
  keyboard:
    layout: "us,tw"          # US + Traditional Chinese
    variant: ","
    toggle: alt_shift_toggle

autoinstall:
  keyboard:
    layout: de               # German
    variant: nodeadkeys
```

---

## 7. source

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | ISO default source |
| **Interactive** | Yes |

Selects which installation variant (package set) to install.

### Sub-keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `id` | string | ISO default | Installation source ID (see table below) |
| `search_drivers` | boolean | `true` | Whether to search for third-party drivers |

### Source IDs by flavour

| Flavour | Minimal ID | Standard ID |
|---------|-----------|-------------|
| Ubuntu Server | `ubuntu-server-minimal` | `ubuntu-server` *(default)* |
| Ubuntu Desktop | `ubuntu-desktop-minimal` *(default)* | `ubuntu-desktop` |
| Ubuntu Budgie | `ubuntu-budgie-desktop-minimal` | `ubuntu-budgie-desktop` |
| Ubuntu Cinnamon | `ubuntucinnamon-desktop-minimal` | `ubuntucinnamon-desktop` |
| Edubuntu | `edubuntu-desktop-minimal` | `edubuntu-desktop` |
| Ubuntu MATE | `ubuntu-mate-desktop-minimal` | `ubuntu-mate-desktop` |
| Ubuntu Studio | — | `ubuntustudio-desktop` |
| Xubuntu | `xubuntu-desktop-minimal` | `xubuntu-desktop` |

> **TIP:** Always verify the correct ID for your ISO in `casper/install-sources.yaml` on the installation media, as values may change between releases.

```yaml
autoinstall:
  source:
    id: ubuntu-server-minimal     # minimal server install

autoinstall:
  source:
    id: ubuntu-server             # full server install
    search_drivers: false         # skip third-party driver search
```

---

## 8. network

| | |
|---|---|
| **Type** | mapping (Netplan format) |
| **Required** | No |
| **Default** | DHCP on `eth*` / `en*` interfaces |
| **Interactive** | Yes |

Network configuration in [Netplan](https://netplan.io/reference) format. Applied both during installation and in the installed system.

```yaml
autoinstall:
  network:
    version: 2
    ethernets:
      enp0s3:
        dhcp4: true              # DHCP IPv4

autoinstall:
  network:
    version: 2
    ethernets:
      enp0s3:
        addresses: [192.168.1.100/24]
        gateway4: 192.168.1.1
        nameservers:
          addresses: [8.8.8.8, 1.1.1.1]

autoinstall:
  network:
    version: 2
    ethernets:
      enp0s3:
        dhcp6: true              # DHCP IPv6

autoinstall:
  network:
    version: 2
    bonds:
      bond0:
        interfaces: [enp0s3, enp0s8]
        parameters:
          mode: active-backup
        dhcp4: true
```

---

## 9. proxy

| | |
|---|---|
| **Type** | URL string or `null` |
| **Required** | No |
| **Default** | no proxy |
| **Interactive** | Yes |

HTTP proxy configured for apt and snapd both during and after installation.

> **NOTE:** This setting is currently not honored during GeoIP lookups.

```yaml
autoinstall:
  proxy: http://proxy.corp.local:3128

autoinstall:
  proxy: http://user:password@proxy.corp.local:3128

autoinstall:
  proxy: null        # explicitly no proxy
```

---

## 10. apt

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | Ubuntu archive with geoip mirror selection |
| **Interactive** | Yes |

APT configuration used during installation and in the installed system. Follows the curtin APT Source format with Subiquity extensions.

### Sub-keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `mirror-selection.primary` | list | country + archive | Ordered list of candidate mirrors |
| `fallback` | string | `offline-install` | Action when no mirror reachable: `abort`, `offline-install`, `continue-anyway` |
| `geoip` | boolean | `true` | Use IP geolocation to pick closest mirror |
| `preserve_sources_list` | boolean | `false` | Keep existing `/etc/apt/sources.list` |
| `sources` | mapping | — | Additional APT sources / PPAs |
| `disable_components` | list | — | Remove archive components (e.g. `multiverse`) |

```yaml
autoinstall:
  apt:
    mirror-selection:
      primary:
        - country-mirror          # auto-select by geolocation
        - uri: http://archive.ubuntu.com/ubuntu
    fallback: abort
    geoip: true

# Use internal mirror only
autoinstall:
  apt:
    mirror-selection:
      primary:
        - uri: http://apt-mirror.corp.local/ubuntu
    fallback: abort
    geoip: false

# Add a PPA
autoinstall:
  apt:
    sources:
      my-ppa:
        source: "ppa:deadsnakes/ppa"
```

---

## 11. storage

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | `lvm` layout on single-disk systems |
| **Interactive** | Yes |

Disk layout and partitioning. Supports a simple `layout:` shorthand or full `config:` object list. See the dedicated **Storage Configuration Reference** for full documentation.

### layout: shorthand sub-keys

| Key | Values | Description |
|-----|--------|-------------|
| `name` | `lvm`, `direct`, `zfs`, `hybrid` | Predefined layout |
| `match` | match spec | Which disk to use |
| `ptable` | `gpt`, `msdos` | Partition table type |
| `password` | string | LUKS passphrase (lvm only) |
| `sizing-policy` | `scaled`, `all` | LVM root LV sizing strategy |
| `encrypted` | boolean | TPM-backed encryption (hybrid only) |
| `reset-partition` | boolean / size | Create OEM reset partition |
| `reset-partition-only` | boolean | Only create reset partition, skip OS install |

```yaml
autoinstall:
  storage:
    layout:
      name: lvm                  # LVM layout (default)

autoinstall:
  storage:
    layout:
      name: lvm
      password: MyLUKSpass       # encrypted LVM

autoinstall:
  storage:
    layout:
      name: direct
      match:
        ssd: true                # install to SSD

autoinstall:
  storage:
    layout:
      name: zfs                  # ZFS root

autoinstall:
  storage:
    swap:
      size: 0                    # disable swap file
    config:
      - type: disk
        id: disk0
        ...                      # full custom config
```

---

## 12. identity

| | |
|---|---|
| **Type** | mapping |
| **Required** | **Yes*** |
| **Default** | none |
| **Interactive** | Yes |

Configures the initial user account and system hostname. Required unless `user-data` is provided.

> \* Optional only when the `user-data` key is present.

### Sub-keys

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `username` | string | **Yes** | Login name for the initial user |
| `password` | string | **Yes** | Encrypted password (sha-512 hash) |
| `hostname` | string | **Yes** | System hostname |
| `realname` | string | No | Full display name for the user |
| `groups` | list or mapping | No | Additional groups for the user |

### groups syntax

```yaml
groups: [adm, sudo, docker]             # override (list form)
groups:
  override: [adm, sudo, docker]         # replace default groups
groups:
  append: [docker, libvirt]             # add to default groups
```

### Password generation

```bash
# Generate sha-512 hash
mkpasswd --method=sha-512 'MyPassword'
openssl passwd -6 'MyPassword'
python3 -c "import crypt; print(crypt.crypt('MyPassword', crypt.mksalt(crypt.METHOD_SHA512)))"
```

```yaml
autoinstall:
  identity:
    realname: Ubuntu Admin
    username: ubuntu
    password: '$6$xyz...$hashedpassword'
    hostname: my-server

autoinstall:
  identity:
    username: sysadmin
    password: '$6$xyz...$hashedpassword'
    hostname: prod-node-01
    groups:
      append: [docker, libvirt]
```

---

## 13. active-directory

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | not configured |
| **Interactive** | Yes |

Join the installed system to a Microsoft Active Directory domain. The domain account password is prompted at runtime (not stored in the config file).

### Sub-keys

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `admin-name` | string | **Yes** | AD account with join privilege |
| `domain-name` | string | **Yes** | AD domain FQDN |

```yaml
autoinstall:
  active-directory:
    admin-name: administrator
    domain-name: corp.example.com
```

---

## 14. ubuntu-pro

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | not attached |
| **Interactive** | Yes |

Attach the installed system to an Ubuntu Pro (formerly UA) subscription for access to ESM, Livepatch, FIPS, and other enterprise features.

### Sub-keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `token` | string | none | Ubuntu Pro contract token |

```yaml
autoinstall:
  ubuntu-pro:
    token: C1NWcZTHLteJXGVMM6YhvHDpGrhyy7
```

> **NOTE:** Keep contract tokens out of version control. Use `early-commands` to fetch the token from a secrets manager at runtime.

---

## 15. ssh

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | no SSH server |
| **Interactive** | Yes |

Configure the OpenSSH server in the installed system.

### Sub-keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `install-server` | boolean | `false` | Install `openssh-server` |
| `authorized-keys` | list of strings | `[]` | SSH public keys for the initial user |
| `allow-pw` | boolean | `true` if no keys, else `false` | Allow password authentication |

```yaml
# Key-only SSH (recommended for servers)
autoinstall:
  ssh:
    install-server: true
    authorized-keys:
      - ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... user@workstation
      - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... backup-key
    allow-pw: false

# Password SSH (less secure)
autoinstall:
  ssh:
    install-server: true
    allow-pw: true

# No SSH server (default)
autoinstall:
  ssh:
    install-server: false
```

---

## 16. codecs

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | `install: false` |
| **Interactive** | No |

Install restricted multimedia codecs from the multiverse repository (`ubuntu-restricted-addons` package).

### Sub-keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `install` | boolean | `false` | Whether to install restricted codecs |

```yaml
autoinstall:
  codecs:
    install: true     # install mp3, aac, h264, etc. codecs

autoinstall:
  codecs:
    install: false    # default, no restricted codecs
```

---

## 17. drivers

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | `install: false` |
| **Interactive** | Yes |

Control third-party driver installation (GPU drivers, Wi-Fi firmware, etc.) as identified by `ubuntu-drivers`.

### Sub-keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `install` | boolean | `false` | Install recommended third-party drivers |

> **NOTE:** `search_drivers` under `source:` must be `true` (the default) for this section to have any effect.

```yaml
autoinstall:
  drivers:
    install: true      # install NVIDIA/AMD/Wi-Fi drivers if detected

autoinstall:
  drivers:
    install: false     # default, skip third-party drivers
```

---

## 18. oem

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | `install: auto` |
| **Interactive** | No |

Control installation of OEM meta-packages (used for OEM system provisioning workflows).

### Sub-keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `install` | boolean or `auto` | `auto` | `true` force install, `false` skip, `auto` detect |

```yaml
autoinstall:
  oem:
    install: auto      # default: install only if OEM packages found

autoinstall:
  oem:
    install: false     # never install OEM packages
```

---

## 19. snaps

| | |
|---|---|
| **Type** | list of mappings |
| **Required** | No |
| **Default** | no extra snaps |
| **Interactive** | No |

Snap packages to install in the target system.

### Per-snap fields

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `name` | string | **Required** | Snap package name |
| `channel` | string | `stable` | Snap channel (`stable`, `beta`, `edge`, `candidate`) |
| `classic` | boolean | `false` | Install in classic (unconfined) mode |

```yaml
autoinstall:
  snaps:
    - name: microk8s
      channel: 1.28/stable
      classic: false

    - name: kubectl
      channel: stable
      classic: true

    - name: code
      channel: stable
      classic: true

    - name: yq
      channel: stable
```

---

## 20. packages

| | |
|---|---|
| **Type** | list of strings |
| **Required** | No |
| **Default** | no extra packages |
| **Interactive** | No |

APT packages to install in the target system after the base installation. Installed via `curtin in-target -- apt-get install`.

```yaml
autoinstall:
  packages:
    - vim
    - git
    - curl
    - htop
    - build-essential
    - python3-pip
    - docker.io
    - nfs-common
```

---

## 21. timezone

| | |
|---|---|
| **Type** | string |
| **Required** | No |
| **Default** | `geoip` (auto-detect) or `UTC` |
| **Interactive** | Yes |

System timezone for the installed system. Use `geoip` as the value to automatically determine the timezone based on IP geolocation.

Uses standard tz database names (`Area/City` format).

```yaml
autoinstall:
  timezone: UTC                    # UTC (safe default for servers)

autoinstall:
  timezone: Asia/Taipei            # Taiwan

autoinstall:
  timezone: America/New_York       # US Eastern

autoinstall:
  timezone: Europe/London          # UK

autoinstall:
  timezone: geoip                  # auto-detect from IP
```

---

## 22. updates

| | |
|---|---|
| **Type** | string |
| **Required** | No |
| **Default** | `security` |
| **Interactive** | No |

Which package updates to apply during installation.

| Value | Behavior |
|-------|---------|
| `security` | Apply security updates only (default) |
| `all` | Apply all available updates |
| `none` | Do not apply any updates |

```yaml
autoinstall:
  updates: security    # default

autoinstall:
  updates: all         # apply all updates (longer install time)

autoinstall:
  updates: none        # skip updates (fastest, least secure)
```

---

## 23. reporting

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | print to console only |
| **Interactive** | No |

Installation progress reporting endpoints. Ignored if any `interactive-sections` are defined.

Supports multiple named reporters, each with a `type` and type-specific configuration.

### Reporter types

| Type | Description |
|------|-------------|
| `print` | Write to stdout/console (default) |
| `webhook` | POST JSON progress events to a URL |
| `rs` | Reporting service endpoint |

```yaml
autoinstall:
  reporting:
    hook:
      type: webhook
      endpoint: http://install-monitor.corp.local:8080/progress

    console:
      type: print
```

---

## 24. error-commands

| | |
|---|---|
| **Type** | command list |
| **Required** | No |
| **Default** | no commands |
| **Interactive** | No |

Shell commands to run when a fatal error occurs during installation. Non-zero exit codes from these commands are **ignored**. Used to collect diagnostic information or send alerts.

```yaml
autoinstall:
  error-commands:
    # Upload install logs to a remote server
    - tar czf /tmp/install-logs.tgz /var/log/installer
    - curl -F "file=@/tmp/install-logs.tgz" http://log-server.corp.local/upload

    # Send failure alert
    - >-
      curl -s -X POST http://alerts.corp.local/hook
      -H 'Content-Type: application/json'
      -d '{"text":"Autoinstall FAILED on node $(hostname)"}'
```

---

## 25. late-commands

| | |
|---|---|
| **Type** | command list |
| **Required** | No |
| **Default** | no commands |
| **Interactive** | No |

Shell commands run **after** the installation completes but **before** the first reboot. The installed system is mounted at `/target`. Use `curtin in-target -- <cmd>` to run commands inside the target chroot.

```yaml
autoinstall:
  late-commands:
    # Run commands inside the installed system (chroot)
    - curtin in-target -- apt-get install -y vim git

    # Modify files in the installed system directly
    - echo "ubuntu ALL=(ALL) NOPASSWD:ALL" >> /target/etc/sudoers.d/ubuntu

    # Copy files into the installed system
    - cp /cdrom/corp-ca.crt /target/usr/local/share/ca-certificates/
    - curtin in-target -- update-ca-certificates

    # Run an external post-install script
    - wget -O /target/root/postinstall.sh http://config-server.local/postinstall.sh
    - curtin in-target -- bash /root/postinstall.sh

    # Disable cloud-init on subsequent boots
    - touch /target/etc/cloud/cloud-init.disabled

    # Enable a systemd service
    - curtin in-target -- systemctl enable myservice
```

---

## 26. user-data

| | |
|---|---|
| **Type** | mapping (cloud-init user-data) |
| **Required** | No |
| **Default** | none |
| **Interactive** | No |

Cloud-init user-data configuration applied on the **first boot** of the installed system (not during installation). When this key is present, the `identity` key becomes optional.

```yaml
autoinstall:
  user-data:
    runcmd:
      - echo "First boot complete" >> /var/log/firstboot.log
    write_files:
      - path: /etc/motd
        content: |
          Welcome to the auto-installed server.
    package_update: true
    packages:
      - vim
```

---

## 27. shutdown

| | |
|---|---|
| **Type** | string |
| **Required** | No |
| **Default** | `reboot` |
| **Interactive** | No |

Action to perform after installation completes.

| Value | Behavior |
|-------|---------|
| `reboot` | Reboot into the installed system (default) |
| `poweroff` | Power off the machine after install |

```yaml
autoinstall:
  shutdown: reboot      # default

autoinstall:
  shutdown: poweroff    # useful for imaging workflows
```

---

## 28. debconf-selections

| | |
|---|---|
| **Type** | string (multiline) |
| **Required** | No |
| **Default** | none |
| **Interactive** | No |

Preseed-style `debconf` answers applied to the target system. Uses the same format as `debconf-set-selections`. Applied via `debconf-set-selections` in the target system during installation.

```yaml
autoinstall:
  debconf-selections: |
    locales locales/default_environment_locale select en_US.UTF-8
    locales locales/locales_to_be_generated multiselect en_US.UTF-8 UTF-8
    tzdata tzdata/Areas select Asia
    tzdata tzdata/Zones/Asia select Taipei
    tasksel tasksel/first multiselect standard, ssh-server
```

---

## 29. swap

| | |
|---|---|
| **Type** | mapping |
| **Required** | No |
| **Default** | auto-sized swap file |
| **Interactive** | No |

Controls swap file creation in the installed system. This is separate from swap partitions configured under `storage:`.

### Sub-keys

| Key | Type | Description |
|-----|------|-------------|
| `size` | integer or `0` | Swap file size in bytes; `0` = disable swap file |

```yaml
autoinstall:
  swap:
    size: 0              # disable swap file (use partition swap instead)

autoinstall:
  swap:
    size: 4294967296     # 4 GiB swap file (in bytes)
```

> **NOTE:** If you configure a swap partition in `storage:`, set `swap: { size: 0 }` to avoid also creating a swap file.

---

## Complete Minimal Example

```yaml
#cloud-config
autoinstall:
  version: 1
  locale: en_US.UTF-8
  keyboard:
    layout: us
  identity:
    hostname: ubuntu-server
    username: ubuntu
    password: '$6$xyz...$hashedpassword'
  ssh:
    install-server: true
    authorized-keys:
      - ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... user@host
    allow-pw: false
  storage:
    layout:
      name: lvm
  packages:
    - vim
    - curl
  late-commands:
    - echo "Installation complete" >> /target/var/log/autoinstall.log
  shutdown: reboot
```

## Complete Full-Featured Example

```yaml
#cloud-config
autoinstall:
  version: 1

  # ── System Locale & Input ────────────────────────────────────────────────
  locale: en_US.UTF-8
  timezone: Asia/Taipei
  keyboard:
    layout: us

  # ── Installer behavior ───────────────────────────────────────────────────
  refresh-installer:
    update: true
    channel: latest/stable

  # ── Source ───────────────────────────────────────────────────────────────
  source:
    id: ubuntu-server
    search_drivers: false

  # ── Network ──────────────────────────────────────────────────────────────
  network:
    version: 2
    ethernets:
      enp0s3:
        dhcp4: true

  # ── Proxy & APT ──────────────────────────────────────────────────────────
  proxy: null
  apt:
    mirror-selection:
      primary:
        - country-mirror
        - uri: http://archive.ubuntu.com/ubuntu
    fallback: abort
    geoip: true

  # ── Storage ──────────────────────────────────────────────────────────────
  storage:
    layout:
      name: lvm
      sizing-policy: all
  swap:
    size: 0

  # ── User ─────────────────────────────────────────────────────────────────
  identity:
    realname: Admin User
    username: ubuntu
    password: '$6$rounds=4096$...$hashedpassword'
    hostname: prod-server-01
    groups:
      append: [docker]

  # ── SSH ──────────────────────────────────────────────────────────────────
  ssh:
    install-server: true
    authorized-keys:
      - ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... admin@jumphost
    allow-pw: false

  # ── Packages & Snaps ─────────────────────────────────────────────────────
  packages:
    - vim
    - git
    - curl
    - htop
    - build-essential
  snaps:
    - name: yq
      channel: stable

  # ── Drivers & Codecs ─────────────────────────────────────────────────────
  drivers:
    install: false
  codecs:
    install: false

  # ── Updates ──────────────────────────────────────────────────────────────
  updates: security

  # ── Hooks ────────────────────────────────────────────────────────────────
  early-commands:
    - echo "Starting autoinstall" | tee /dev/console

  late-commands:
    - curtin in-target -- apt-get autoremove -y
    - echo "Install done $(date)" >> /target/var/log/autoinstall.log

  error-commands:
    - tar czf /tmp/logs.tgz /var/log/installer
    - curl -F "file=@/tmp/logs.tgz" http://log-server.local/upload || true

  # ── Reporting ─────────────────────────────────────────────────────────────
  reporting:
    console:
      type: print

  # ── Post-boot Cloud-init ──────────────────────────────────────────────────
  user-data:
    runcmd:
      - systemctl enable --now docker || true

  # ── Shutdown ─────────────────────────────────────────────────────────────
  shutdown: reboot
```

---

*Reference: [Ubuntu Autoinstall Configuration Reference](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html) | Ubuntu 20.04 LTS and later*
