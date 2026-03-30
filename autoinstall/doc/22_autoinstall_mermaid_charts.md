# Autoinstall System — Mermaid Charts

---

## 1. System Architecture Overview

```mermaid
graph TB
    subgraph BUILD["Build Host"]
        PL[package_list]
        ISO_SRC["Original Ubuntu ISO<br/>from iso_repository/"]
        SCRIPT[build-ubuntu-autoinstall-iso.sh]
        APT_CACHE["apt_cache/<br/>persistent .deb cache"]
    end

    subgraph ISO_CONTENTS["Custom ISO Contents"]
        GRUB_CFG["boot/grub/grub.cfg<br/>patched for autoinstall"]
        USER_DATA["autoinstall/user-data<br/>cloud-init config"]
        META_DATA["autoinstall/meta-data"]
        FIND_DISK["autoinstall/scripts/find_disk.sh"]
        POOL["pool/extra/*.deb<br/>pre-bundled packages"]
        LOGGER["pool/extra/ipmi_start_logger.py"]
        EFI_IMG["EFI System Partition<br/>64MB FAT32"]
        DOCKER_ASC["autoinstall/docker.asc"]
        K8S_GPG["autoinstall/kubernetes.gpg"]
    end

    subgraph TARGET["Target Server"]
        BMC["BMC<br/>Virtual Media"]
        UEFI_FW[UEFI Firmware]
        GRUB2[GRUB2 Bootloader]
        KERNEL["Linux Kernel +<br/>Initrd / Casper"]
        SUBIQUITY[Subiquity Installer]
        CURTIN[Curtin Backend]
        DISK["Target Disk<br/>serial-matched"]
        IPMI_DEV["/dev/ipmi0<br/>BMC Interface"]
        SEL["BMC SEL<br/>System Event Log"]
    end

    PL --> SCRIPT
    ISO_SRC --> SCRIPT
    SCRIPT --> APT_CACHE
    APT_CACHE --> POOL
    SCRIPT --> ISO_CONTENTS
    ISO_CONTENTS --> OUT_ISO[Custom Autoinstall ISO]
    OUT_ISO --> BMC
    BMC --> UEFI_FW --> GRUB2 --> KERNEL
    KERNEL --> SUBIQUITY
    SUBIQUITY --> CURTIN --> DISK
    LOGGER --> IPMI_DEV --> SEL
```

---

## 2. Build Script — Step-by-Step Flow

```mermaid
flowchart TD
    START(["Start: build-ubuntu-autoinstall-iso.sh<br/>OS_NAME  USERNAME  PASSWORD"]) --> CHK_PKGS

    CHK_PKGS{Running as root?} -->|Yes| INST_PKGS["apt install:<br/>whois xorriso genisoimage<br/>isolinux mtools jq"]
    CHK_PKGS -->|No / --skip-install| SKIP_INST[Skip tool installation]
    INST_PKGS --> LOOKUP
    SKIP_INST --> LOOKUP

    LOOKUP["jq: lookup ISO path<br/>from iso_repository/file_list.json"] --> VER_CHK

    VER_CHK{Ubuntu 18.04?} -->|Yes| SET_1804["IS_1804=true<br/>Use preseed automation"]
    VER_CHK -->|No| SET_MODERN["IS_1804=false<br/>Use cloud-init autoinstall"]

    SET_1804 --> BUILD_ID
    SET_MODERN --> BUILD_ID

    BUILD_ID["Generate unique BUILD_ID<br/>WORKDIR + OUT_ISO_DIR"] --> MOUNT_ISO

    MOUNT_ISO["Mount original ISO<br/>→ loop mount /mnt/ubuntuiso"] --> RSYNC
    RSYNC["rsync ISO contents<br/>to WORKDIR/"] --> UMOUNT
    UMOUNT["umount /mnt/ubuntuiso"] --> PKG_DL_CHK

    PKG_DL_CHK{IS_1804?} -->|Yes| GEN_KEYS
    PKG_DL_CHK -->|No| CODENAME

    CODENAME["Detect Ubuntu codename<br/>jammy / noble / oracular..."] --> DL_PKGS

    DL_PKGS["download_extra_packages:<br/>• Isolated apt environment<br/>• Resolve full dep closure<br/>• Delta download vs cache<br/>• Copy .debs → pool/extra/"] --> DL_DOCKER

    DL_DOCKER{docker in<br/>package_list?} -->|Yes| ADD_DOCKER["Add Docker repo<br/>Bundle docker.asc GPG key"]
    DL_DOCKER -->|No| DL_K8S
    ADD_DOCKER --> DL_K8S

    DL_K8S{kube in<br/>package_list?} -->|Yes| ADD_K8S["Add k8s repo<br/>Bundle kubernetes.gpg"]
    DL_K8S -->|No| COPY_LOGGER
    ADD_K8S --> COPY_LOGGER

    COPY_LOGGER["Copy ipmi_start_logger.py<br/>→ pool/extra/"] --> GEN_KEYS

    GEN_KEYS["ssh-keygen -t ed25519<br/>Generate unique key pair"] --> HASH_PW
    HASH_PW["mkpasswd -m sha-512<br/>Hash PASSWORD"] --> GEN_CONFIG

    GEN_CONFIG["Write autoinstall/meta-data"] --> GEN_USERDATA
    GEN_CONFIG --> WRITE_FIND_DISK["Write autoinstall/scripts/find_disk.sh"]

    GEN_USERDATA["Write autoinstall/user-data<br/>#cloud-config<br/>autoinstall v1"] --> SYMLINK
    SYMLINK["Create /autoinstall.yaml symlink<br/>→ /cdrom/autoinstall/user-data<br/>24.04+ compatibility"] --> 1804_PRESEED

    1804_PRESEED{IS_1804?} -->|Yes| PRESEED["Write preseed.cfg<br/>d-i debian-installer config"] --> PATCH_GRUB
    1804_PRESEED -->|No| PATCH_GRUB

    PATCH_GRUB["Patch boot/grub/grub.cfg<br/>via Python regex:<br/>• Set timeout=5<br/>• Replace menuentry with autoinstall params<br/>• ds=nocloud;s=/cdrom/autoinstall/"] --> PATCH_ISOLINUX

    PATCH_ISOLINUX["Patch isolinux/txt.cfg<br/>isolinux/adtxt.cfg<br/>for BIOS boot"] --> REPACK

    REPACK{IS_1804?} -->|Yes| XORRISO_1804["xorriso 18.04 legacy:<br/>• isohybrid-mbr<br/>• BIOS + efi.img<br/>• No EFI partition mod"]
    REPACK -->|No| BUILD_EFI

    BUILD_EFI["Create 64MB EFI FAT image:<br/>• mmd EFI/BOOT boot/grub<br/>• mcopy bootx64.efi grubx64.efi<br/>• mcopy grub.cfg + modules"] --> XORRISO_MODERN

    XORRISO_MODERN["xorriso 20.04+:<br/>• GPT + MBR hybrid<br/>• append_partition 2 EFI<br/>• BIOS eltorito<br/>• UEFI EFI partition"] --> DONE

    XORRISO_1804 --> DONE
    DONE([Output: output_custom_iso/BUILD_ID/*.iso])
```

---

## 3. Target Boot & Installation Flow

```mermaid
sequenceDiagram
    autonumber
    participant BMC as BMC<br/>Virtual Media
    participant UEFI as UEFI / BIOS<br/>Firmware
    participant GRUB as GRUB2<br/>Bootloader
    participant K as Linux Kernel<br/>+ Casper initrd
    participant CI as Cloud-Init<br/>/ Subiquity
    participant EC as early-commands
    participant LC as late-commands
    participant IPMI as /dev/ipmi0<br/>BMC SEL
    participant DISK as Target Disk

    BMC->>UEFI: Mount ISO as virtual CD
    UEFI->>GRUB: Load EFI/BOOT/bootx64.efi → grubx64.efi
    Note over GRUB: Reads patched grub.cfg<br/>menuentry "Auto Install Ubuntu Server"
    GRUB->>K: Load /casper/vmlinuz + initrd<br/>params: autoinstall ds=nocloud&#59;s=/cdrom/autoinstall/
    K->>CI: Boot, hand off to cloud-init/subiquity

    Note over CI: Reads /cdrom/autoinstall/user-data<br/>version: 1 autoinstall config

    CI->>EC: Run early-commands

    EC->>EC: Source find_disk.sh<br/>find_empty_disk_serial()
    Note over EC: Scans all block devices:<br/>1. Partition check<br/>2. Filesystem signature check<br/>3. First 1MB data check<br/>4. Prefer smallest empty disk
    EC->>EC: sed -i replace __ID_SERIAL__<br/>in /autoinstall.yaml + runtime configs

    EC->>IPMI: modprobe ipmi_devintf/si/msghandler
    EC->>IPMI: 0x0F — Package Pre-install Start
    EC->>EC: dpkg -i /cdrom/pool/extra/*.deb
    EC->>IPMI: 0x1F — Package Pre-install Complete
    EC->>IPMI: 0x01 — OS Install Start

    CI->>CI: Subiquity runs partitioning<br/>GPT: 512MB EFI + remaining ext4<br/>matched by disk serial
    CI->>DISK: Format + mount /target
    CI->>CI: Install base system (debootstrap/curtin)

    CI->>LC: Run late-commands
    LC->>IPMI: 0x06 — Post-Install Start
    LC->>LC: chpasswd root<br/>PermitRootLogin yes<br/>PasswordAuthentication yes<br/>sudoers setup
    LC->>LC: cp resolv.conf → /target/etc/

    alt package_list provided (offline mode)
        LC->>LC: Copy .debs → /target/tmp/extra_pkg/<br/>Setup Docker/k8s keyrings if needed
        LC->>DISK: curtin in-target: apt install /tmp/extra_pkg/*.deb
    else no package_list (hybrid mode)
        LC->>LC: Try: apt-get install vim curl ipmitool htop
        alt Internet success
            LC->>DISK: Install from Ubuntu mirrors
        else Internet failure
            LC->>LC: Fallback: copy .debs from /cdrom/pool/extra/
            LC->>DISK: dpkg -i /tmp/extra_pkg/*.deb
        end
    end

    LC->>IPMI: 0x16 — Post-Install Complete
    LC->>LC: hostname -I → parse octets<br/>awk -F. eval o1 o2 o3 o4
    LC->>IPMI: 0x03 [octet1] [octet2] — IP Part 1
    LC->>IPMI: 0x13 [octet3] [octet4] — IP Part 2
    LC->>IPMI: 0xAA — OS Install Completed

    LC->>LC: Disk serial audit:<br/>lsblk → udevadm → compare __ID_SERIAL__
    alt Serial matches
        LC->>IPMI: 0x05 0x4F 0x4B — Verify OK
    else Serial mismatch
        LC->>IPMI: 0x05 0x45 0x52 — Verify ER (Error)
    end

    LC->>DISK: Copy ipmi_telemetry.log → /target/var/log/
    LC->>DISK: Copy install_disk_audit.log → /target/var/log/
    CI->>BMC: Signal reboot
```

---

## 4. IPMI SEL Telemetry Markers

```mermaid
stateDiagram-v2
    direction LR

    [*] --> BootStart : ISO boots on target

    BootStart --> PkgPreInstStart : early-commands begin
    note right of PkgPreInstStart
        Marker 0x0F
        Package Pre-install Start
        (binary-less Python logger)
    end note

    PkgPreInstStart --> PkgInstall : dpkg -i *.deb from ISO

    PkgInstall --> PkgPreInstDone
    note right of PkgPreInstDone
        Marker 0x1F
        Package Pre-install Complete
        (ipmitool now available)
    end note

    PkgPreInstDone --> OSInstStart
    note right of OSInstStart
        Marker 0x01
        OS Installation Start
    end note

    OSInstStart --> MainInstall : Subiquity partitions & installs

    MainInstall --> PostInstStart : late-commands begin
    note right of PostInstStart
        Marker 0x06
        Post-Install Start
    end note

    PostInstStart --> PackagesInstalled : user packages installed

    PackagesInstalled --> PostInstDone
    note right of PostInstDone
        Marker 0x16
        Post-Install Complete
    end note

    PostInstDone --> IP_P1
    note right of IP_P1
        Marker 0x03 [o1] [o2]
        IP Address Part 1
        e.g. 10.99
    end note

    IP_P1 --> IP_P2
    note right of IP_P2
        Marker 0x13 [o3] [o4]
        IP Address Part 2
        e.g. 236.106
    end note

    IP_P2 --> InstallComplete
    note right of InstallComplete
        Marker 0xAA
        OS Install Completed
    end note

    InstallComplete --> DiskVerify
    DiskVerify --> VerifyOK : Serial matches
    DiskVerify --> VerifyFail : Serial mismatch

    note right of VerifyOK
        Marker 0x05 0x4F 0x4B
        "OK"
    end note

    note right of VerifyFail
        Marker 0x05 0x45 0x52
        "ER" (Error)
    end note

    VerifyOK --> [*]
    VerifyFail --> [*]

    OSInstStart --> ErrorPath : Subiquity error
    note right of ErrorPath
        error-commands path
        0x03/0x13 log IP if available
        Marker 0xEE — ABORTED
    end note
    ErrorPath --> [*]
```

---

## 5. Disk Detection Algorithm (find_disk.sh)

```mermaid
flowchart TD
    START(["find_empty_disk_serial"]) --> LSBLK
    LSBLK["lsblk -nd --exclude 1,2,11<br/>List all non-loop block devices"] --> LOOP_DISK

    LOOP_DISK{For each disk<br/>device in list} --> CHK_BLOCK

    CHK_BLOCK{Is block<br/>device?} -->|No| NEXT_DISK[Skip]
    CHK_BLOCK -->|Yes| CHK_PARTS

    CHK_PARTS["lsblk -o TYPE: count 'part'"] --> HAS_PARTS{Has<br/>partitions?}
    HAS_PARTS -->|Yes| SKIP_PARTS["Skip: has partitions"]
    HAS_PARTS -->|No| CHK_FS

    CHK_FS["wipefs: check filesystem signatures"] --> HAS_FS{Has FS<br/>signatures?}
    HAS_FS -->|Yes| SKIP_FS["Skip: has filesystem"]
    HAS_FS -->|No| CHK_DATA

    CHK_DATA["dd if=device bs=1M count=1<br/>tr -d '\0' | wc -c"] --> HAS_DATA{Non-zero<br/>bytes in<br/>first 1MB?}
    HAS_DATA -->|Yes| SKIP_DATA["Skip: has data"]
    HAS_DATA -->|No| GET_SERIAL

    GET_SERIAL["udevadm info: get ID_SERIAL"] --> HAS_SERIAL{Serial<br/>found?}
    HAS_SERIAL -->|No| TRY_NVME["Try DEVPATH fallback:<br/>/sys/.../serial"]
    TRY_NVME --> HAS_SERIAL2{Serial<br/>found?}
    HAS_SERIAL2 -->|No| SKIP_NOSER["Skip: no serial"]
    HAS_SERIAL -->|Yes| CANDIDATE
    HAS_SERIAL2 -->|Yes| CANDIDATE

    CANDIDATE["Valid candidate:<br/>log size + serial"] --> SMALLEST{Smaller than<br/>current best?}
    SMALLEST -->|Yes| UPDATE["Update: min_size, target_serial,<br/>target_disk"]
    SMALLEST -->|No| NEXT_DISK2["Keep current best"]

    UPDATE --> NEXT_DISK
    NEXT_DISK --> LOOP_DISK
    SKIP_PARTS --> NEXT_DISK
    SKIP_FS --> NEXT_DISK
    SKIP_DATA --> NEXT_DISK
    SKIP_NOSER --> NEXT_DISK
    NEXT_DISK2 --> NEXT_DISK

    LOOP_DISK -->|All disks checked| RESULT

    RESULT{target_serial<br/>found?} -->|Yes| RETURN_SERIAL["Return serial string<br/>Exit 0"]
    RESULT -->|No| RETURN_ERR["Log ERROR to /dev/console<br/>Exit 1"]
```

---

## 6. Package Bundling — Offline vs Hybrid

```mermaid
flowchart TD
    subgraph BUILD_TIME["Build Time (build host)"]
        PL_CHK{package_list<br/>exists?} -->|Yes| READ_PL["Read package_list<br/>filter comments/blanks"]
        PL_CHK -->|No| DEFAULT_PKGS["Default packages:<br/>ipmitool grub-efi shim efibootmgr"]

        READ_PL --> DOCKER_CHK{docker<br/>in list?}
        DEFAULT_PKGS --> DOCKER_CHK

        DOCKER_CHK -->|Yes| ADD_DOCKER_REPO["Add Docker repo to apt sources<br/>Expand 'docker' → full package set<br/>Download docker.asc GPG key"]
        DOCKER_CHK -->|No| K8S_CHK
        ADD_DOCKER_REPO --> K8S_CHK

        K8S_CHK{kube<br/>in list?} -->|Yes| ADD_K8S_REPO["Add k8s stable/v1.35 repo<br/>Download kubernetes.gpg"]
        K8S_CHK -->|No| ISOLATED_APT
        ADD_K8S_REPO --> ISOLATED_APT

        ISOLATED_APT["Create isolated apt environment:<br/>• Empty dpkg status file<br/>• Target codename sources.list<br/>• Separate cache/state dirs<br/>• Copy host GPG keys"]

        ISOLATED_APT --> APT_UPDATE["apt update<br/>Target codename packages"]
        APT_UPDATE --> DEP_CLOSURE["apt install -s --reinstall<br/>Resolve full dependency closure"]
        DEP_CLOSURE --> DELTA_LOOP

        DELTA_LOOP{For each<br/>dep package} --> SKIP_BASE{Base system<br/>package?}
        SKIP_BASE -->|Yes| NEXT_PKG[Skip]
        SKIP_BASE -->|No| CHK_CACHE{In persistent<br/>apt_cache/?}
        CHK_CACHE -->|Yes| CACHE_HIT[Use cached .deb]
        CHK_CACHE -->|No| DOWNLOAD["apt-get download<br/>Move to cache"]
        CACHE_HIT --> COPY_POOL["cp → WORKDIR/pool/extra/"]
        DOWNLOAD --> COPY_POOL
        COPY_POOL --> NEXT_PKG --> DELTA_LOOP

        COPY_LOGGER_BLD["Copy ipmi_start_logger.py<br/>→ pool/extra/"] --> ISO_READY
        DELTA_LOOP -->|Done| COPY_LOGGER_BLD
    end

    ISO_READY["ISO packed with .debs in pool/extra/"] --> INSTALL_PHASE

    subgraph INSTALL_TIME["Install Time (target server — late-commands)"]
        INSTALL_PHASE{package_list<br/>was non-empty?}

        INSTALL_PHASE -->|Yes - Offline| OFFLINE["Copy .debs → /target/tmp/extra_pkg/<br/>Setup Docker/k8s keyrings<br/>curtin in-target: apt install .deb files"]

        INSTALL_PHASE -->|No - Hybrid| ONLINE_TRY["Try apt-get install<br/>from Ubuntu mirrors"]
        ONLINE_TRY --> ONLINE_OK{Success?}
        ONLINE_OK -->|Yes| ONLINE_DONE[Packages installed online]
        ONLINE_OK -->|No| FALLBACK["Fallback: copy .debs from /cdrom/pool/extra/<br/>curtin in-target: dpkg -i"]
    end
```

---

## 7. ISO Structure (20.04+ GPT Layout)

```mermaid
graph TB
    subgraph ISO["Custom ISO File — xorriso output"]
        subgraph GPT["GPT Partition Table"]
            P1["Partition 1: ISO 9660 filesystem<br/>Main content — variable size"]
            P2["Partition 2: EFI System Partition<br/>64MB FAT32 — appended"]
            P3["Boot Catalog — El Torito"]
        end

        subgraph ISO9660["ISO 9660 Filesystem"]
            subgraph BOOT_SEC["Boot"]
                MBR2["MBR bootstrap 432 bytes<br/>isohdpfx.bin — GRUB2"]
                GRUB_CFG_F["/boot/grub/grub.cfg<br/>patched: autoinstall params"]
                ELTORITO["/boot/grub/i386-pc/eltorito.img<br/>BIOS El Torito boot"]
            end

            subgraph CASPER["Casper — Live Environment"]
                VMLINUZ["/casper/vmlinuz — kernel"]
                INITRD["/casper/initrd — initial ramdisk"]
            end

            subgraph AI["Autoinstall Config"]
                UD["/autoinstall/user-data<br/>cloud-init autoinstall v1"]
                MD["/autoinstall/meta-data"]
                FD["/autoinstall/scripts/find_disk.sh"]
                YAML_LINK["/autoinstall.yaml — symlink<br/>24.04+ compatibility"]
            end

            subgraph EXTRA["Extra Packages"]
                DEBS["/pool/extra/*.deb<br/>pre-bundled packages + deps"]
                PYLOG["/pool/extra/ipmi_start_logger.py"]
                DKGPG["/autoinstall/docker.asc — optional"]
                K8SGPG["/autoinstall/kubernetes.gpg — optional"]
            end
        end

        subgraph EFIFAT["EFI FAT32 Partition — 64MB"]
            BOOTX64["/EFI/BOOT/bootx64.efi — UEFI shim"]
            GRUBX64["/EFI/BOOT/grubx64.efi — GRUB UEFI"]
            MMX64["/EFI/BOOT/mmx64.efi — MOK Manager"]
            EFI_GRUB["/EFI/BOOT/grub.cfg — copy of main grub.cfg"]
            GRUB_MODS["/boot/grub/x86_64-efi/ — GRUB modules"]
            FONTS["/boot/grub/fonts/"]
        end
    end

    P1 --- ISO9660
    P2 --- EFIFAT
```
