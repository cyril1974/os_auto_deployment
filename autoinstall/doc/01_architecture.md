# Ubuntu Autoinstall ISO Builder - Architecture

## Overview

The Ubuntu Autoinstall ISO Builder creates a custom Ubuntu Server ISO that performs fully automated installations via BMC virtual media. The system uses cloud-init's autoinstall feature with a hybrid UEFI/BIOS bootable ISO.

## System Architecture

```mermaid
graph TB
    A[Original Ubuntu ISO] --> B[build-ubuntu-autoinstall-iso.sh]
    B --> C[Extract & Mount ISO]
    C --> D[Create Autoinstall Config]
    C --> E[Patch GRUB Config]
    C --> F[Create EFI Boot Image]
    D --> G[user-data]
    D --> H[meta-data]
    E --> I[Modified grub.cfg]
    F --> J[20MB EFI Partition]
    G --> K[Repack ISO with xorriso]
    H --> K
    I --> K
    J --> K
    K --> L[Custom Autoinstall ISO]
    L --> M[GPT Partition Table]
    M --> N[Partition 1: ISO Data]
    M --> O[Partition 2: EFI System]
    M --> P[Partition 3: Boot Catalog]
```

## Component Architecture

### 1. ISO Structure

```
Custom ISO
├── Boot Components
│   ├── MBR (Master Boot Record)
│   │   └── GRUB2 bootloader (432 bytes from isohdpfx.bin)
│   ├── GPT Partition Table
│   │   ├── Partition 1: ISO 9660 filesystem (1.8GB)
│   │   ├── Partition 2: EFI System Partition (20MB FAT32)
│   │   └── Partition 3: Boot catalog (300KB)
│   └── El Torito Boot Catalog
│       ├── BIOS boot: boot/grub/i386-pc/eltorito.img
│       └── UEFI boot: EFI partition (appended)
│
├── Main Filesystem (ISO 9660)
│   ├── /casper/
│   │   ├── vmlinuz (kernel)
│   │   └── initrd (initial ramdisk)
│   ├── /boot/grub/
│   │   ├── grub.cfg (modified with autoinstall entry)
│   │   ├── i386-pc/ (BIOS GRUB modules)
│   │   └── x86_64-efi/ (UEFI GRUB modules)
│   └── /autoinstall/
│       ├── user-data (cloud-init autoinstall config)
│       └── meta-data (instance metadata)
│
└── EFI System Partition (20MB FAT32)
    ├── /EFI/boot/
    │   ├── bootx64.efi (UEFI bootloader)
    │   ├── grubx64.efi (GRUB UEFI)
    │   └── mmx64.efi (MOK Manager)
    └── /boot/grub/
        ├── grub.cfg (copy of main grub.cfg)
        ├── x86_64-efi/ (GRUB modules)
        └── fonts/ (GRUB fonts)
```

### 2. Boot Flow Architecture

```mermaid
sequenceDiagram
    participant BMC as BMC Virtual Media
    participant UEFI as UEFI Firmware
    participant MBR as MBR/GPT
    participant GRUB as GRUB Bootloader
    participant Kernel as Linux Kernel
    participant CloudInit as Cloud-Init
    participant Installer as Subiquity Installer

    BMC->>UEFI: Mount ISO as virtual CD/DVD
    UEFI->>MBR: Read partition table
    MBR->>UEFI: Return GPT with EFI partition
    UEFI->>GRUB: Load EFI/boot/bootx64.efi
    GRUB->>GRUB: Load modules from EFI partition
    GRUB->>GRUB: Read grub.cfg
    GRUB->>GRUB: Search for ISO filesystem
    GRUB->>Kernel: Load /casper/vmlinuz
    GRUB->>Kernel: Load /casper/initrd
    Kernel->>CloudInit: Boot with autoinstall parameter
    CloudInit->>CloudInit: Read /cdrom/autoinstall/user-data
    CloudInit->>Installer: Configure subiquity
    Installer->>Installer: Automated installation
    Installer->>CloudInit: Run late-commands
    CloudInit->>CloudInit: Configure system
```

### 3. Data Flow

```mermaid
flowchart LR
    A[User Credentials] --> B[build script]
    C[Original ISO] --> B
    B --> D[Hash Password]
    B --> E[Generate SSH Keys]
    B --> F[Create user-data]
    D --> F
    E --> F
    F --> G[Embed in ISO]
    B --> H[Patch GRUB]
    H --> G
    B --> I[Create EFI Image]
    I --> G
    G --> J[Custom ISO]
    J --> K[Boot Process]
    K --> L[Cloud-Init]
    L --> M[Automated Install]
```

## Key Technologies

### Build Tools
- **xorriso**: ISO creation with hybrid boot support
- **mtools**: FAT filesystem manipulation for EFI partition
- **mkpasswd**: Password hashing (SHA-512)
- **ssh-keygen**: SSH key pair generation

### Boot Technologies
- **GRUB2**: Bootloader for both BIOS and UEFI
- **El Torito**: CD/DVD boot standard
- **GPT**: GUID Partition Table for UEFI
- **MBR**: Master Boot Record for BIOS compatibility

### Installation Technologies
- **Cloud-Init**: Configuration management
- **Subiquity**: Ubuntu Server installer
- **Curtin**: Installation backend
- **Autoinstall**: Automated installation schema

## Security Considerations

1. **Password Storage**: Passwords hashed with SHA-512 before embedding
2. **SSH Keys**: Unique ED25519 keys generated per build
3. **Root Access**: Enabled by default (configurable)
4. **Network Security**: No network configuration by default
5. **Package Installation**: Deferred to late-commands to prevent failures

## Scalability

- **Parallel Builds**: Script can run multiple instances with different ISOs
- **Customization**: Easy to modify user-data for different configurations
- **Version Support**: Works with Ubuntu 22.04+ Server ISOs
- **Multi-Architecture**: Supports x86_64 (amd64) architecture
