# Ubuntu Autoinstall ISO Builder - Workflow

## Build Process Flow

```mermaid
flowchart TD
    Start([Start Script]) --> CheckArgs{Arguments Valid?}
    CheckArgs -->|No| ShowHelp[Show Help & Exit]
    CheckArgs -->|Yes| CleanDirs[Clean Work & Output Directories]
    CleanDirs --> InstallPkgs[Install Required Packages]
    InstallPkgs --> CheckISO{ISO Exists?}
    CheckISO -->|No| Error1[Error: ISO Not Found]
    CheckISO -->|Yes| MountISO[Mount Original ISO]
    MountISO --> CopyISO[Copy ISO Contents to Workdir]
    CopyISO --> Unmount[Unmount Original ISO]
    Unmount --> CreateMeta[Create meta-data]
    CreateMeta --> HashPwd[Hash Password with mkpasswd]
    HashPwd --> GenSSH[Generate SSH Key Pair]
    GenSSH --> CreateUser[Create user-data Config]
    CreateUser --> PatchGRUB[Patch GRUB Configuration]
    PatchGRUB --> ExtractMBR[Extract MBR from Original ISO]
    ExtractMBR --> CreateEFI[Create EFI Boot Image]
    CreateEFI --> BuildISO[Build ISO with xorriso]
    BuildISO --> Done([ISO Created Successfully])
```

## Detailed Step-by-Step Workflow

### Phase 1: Initialization & Validation

```mermaid
sequenceDiagram
    participant User
    participant Script
    participant System

    User->>Script: Execute with parameters
    Script->>Script: Parse arguments
    alt No arguments or --help
        Script->>User: Display help
        Script->>Script: Exit
    else Valid arguments
        Script->>System: Check root privileges
        Script->>System: Clean directories
        Script->>System: Install packages
        Script->>System: Validate ISO exists
    end
```

**Steps:**
1. Parse command-line arguments (ISO path, username, password)
2. Validate ISO file exists
3. Clean previous build artifacts
4. Install required packages: `whois`, `genisoimage`, `xorriso`, `isolinux`, `mtools`

### Phase 2: ISO Extraction & Preparation

```mermaid
flowchart LR
    A[Mount ISO] --> B[Copy Contents]
    B --> C[Unmount ISO]
    C --> D[Modify Permissions]
    D --> E[Ready for Customization]
```

**Steps:**
1. Create mount point: `/mnt/ubuntuiso`
2. Mount original ISO read-only
3. Copy all contents to `./workdir_custom_iso/`
4. Unmount original ISO
5. Make workdir writable

### Phase 3: Autoinstall Configuration

```mermaid
flowchart TD
    A[Start Config] --> B[Create autoinstall Directory]
    B --> C[Generate meta-data]
    B --> D[Hash Password]
    D --> E[Generate SSH Keys]
    E --> F[Create user-data]
    F --> G[Configure Identity]
    F --> H[Configure SSH]
    F --> I[Configure late-commands]
    G --> J[Config Complete]
    H --> J
    I --> J
```

**Steps:**
1. Create `./workdir_custom_iso/autoinstall/` directory
2. Generate `meta-data` with instance ID and hostname
3. Hash password using `mkpasswd -m sha-512`
4. Generate ED25519 SSH key pair
5. Create `user-data` with:
   - Autoinstall version
   - User identity (hostname, username, password)
   - Locale and keyboard settings
   - SSH configuration
   - Late-commands for post-install setup

### Phase 4: GRUB Configuration

```mermaid
flowchart TD
    A[Locate grub.cfg] --> B[Backup Original]
    B --> C[Set Timeout to 0]
    C --> D[Add Auto Install Entry]
    D --> E[Add Search Command]
    E --> F[Remove Invalid Commands]
    F --> G[Save Modified Config]
```

**Steps:**
1. Locate `boot/grub/grub.cfg`
2. Create backup: `grub.cfg.orig`
3. Set GRUB timeout to 0 (auto-boot)
4. Replace "Try or Install" entry with "Auto Install" entry
5. Add `search --no-floppy --set=root --file /casper/vmlinuz`
6. Remove standalone `grub_platform` command
7. Save modified configuration

### Phase 5: EFI Boot Image Creation

```mermaid
flowchart LR
    A[Create 20MB Image] --> B[Format as FAT32]
    B --> C[Create Directories]
    C --> D[Copy EFI Bootloaders]
    C --> E[Copy GRUB Config]
    C --> F[Copy GRUB Modules]
    C --> G[Copy Fonts]
    D --> H[EFI Image Ready]
    E --> H
    F --> H
    G --> H
```

**Steps:**
1. Create 20MB empty file: `/tmp/efi.img`
2. Format as FAT32 filesystem
3. Create directory structure:
   - `/EFI/boot/`
   - `/boot/grub/`
4. Copy bootloaders: `bootx64.efi`, `grubx64.efi`, `mmx64.efi`
5. Copy `grub.cfg` to EFI partition
6. Copy GRUB modules: `x86_64-efi/`
7. Copy fonts directory

### Phase 6: ISO Building

```mermaid
flowchart TD
    A[Extract Volume ID] --> B[Extract MBR]
    B --> C[Configure xorriso]
    C --> D[Add ISO Filesystem]
    D --> E[Add Boot Catalog]
    E --> F[Add BIOS Boot]
    F --> G[Append EFI Partition]
    G --> H[Apply MBR]
    H --> I[Create GPT]
    I --> J[Write ISO File]
```

**Steps:**
1. Extract volume ID from original ISO
2. Extract MBR from original ISO (432 bytes)
3. Use `xorriso` with parameters:
   - `-r`: Rock Ridge extensions
   - `-V`: Volume ID
   - `-J -l`: Joliet extensions
   - `-b boot/grub/i386-pc/eltorito.img`: BIOS boot image
   - `-c boot.catalog`: Boot catalog
   - `-e --interval:appended_partition_2:all::`: UEFI boot from appended partition
   - `-append_partition 2 0xEF`: Append EFI partition
   - `--grub2-mbr`: Apply GRUB2 MBR
   - `-partition_offset 16`: Partition alignment
   - `-appended_part_as_gpt`: Create GPT partition table
4. Write output ISO to `./output_custom_iso/<name>_autoinstall.iso`

## Installation Workflow (Runtime)

```mermaid
flowchart TD
    A[Boot from ISO] --> B[UEFI Loads GRUB]
    B --> C[GRUB Auto-selects Autoinstall]
    C --> D[Load Kernel & Initrd]
    D --> E[Kernel Boots]
    E --> F[Cloud-Init Starts]
    F --> G[Read /cdrom/autoinstall/user-data]
    G --> H[Subiquity Installer]
    H --> I[Partition Disk]
    I --> J[Install Base System]
    J --> K[Configure Network]
    K --> L[Run late-commands]
    L --> M[Set Root Password]
    L --> N[Configure SSH]
    L --> O[Install Packages]
    L --> P[Configure Sudo]
    M --> Q[Reboot]
    N --> Q
    O --> Q
    P --> Q
    Q --> R[System Ready]
```

## Error Handling Flow

```mermaid
flowchart TD
    A[Error Detected] --> B{Error Type?}
    B -->|ISO Not Found| C[Exit with Error]
    B -->|Package Install Fail| D[Continue with Warning]
    B -->|GRUB Patch Fail| E[Log Warning]
    B -->|ISO Build Fail| F[Exit with Error]
    D --> G[Log to Console]
    E --> G
    G --> H[Continue Process]
    C --> I[Cleanup & Exit]
    F --> I
```

## Output Artifacts

```mermaid
graph LR
    A[Build Process] --> B[Custom ISO File]
    A --> C[SSH Private Key]
    A --> D[SSH Public Key]
    A --> E[Build Logs]
    B --> F[./output_custom_iso/]
    C --> G[~/.ssh/id_ed25519_*]
    D --> G
    E --> H[Console Output]
```
