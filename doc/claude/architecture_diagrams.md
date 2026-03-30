# OS Auto Deployment - Architecture Diagrams

**Document Version:** 1.0
**Last Updated:** 2026-03-30
**Diagrams:** Mermaid.js

---

## Table of Contents

1. [High-Level System Architecture](#high-level-system-architecture)
2. [Deployment Workflow](#deployment-workflow)
3. [ISO Build Pipeline](#iso-build-pipeline)
4. [Component Interaction](#component-interaction)
5. [Network Architecture](#network-architecture)
6. [IPMI Forensic Flow](#ipmi-forensic-flow)
7. [State Machine Diagram](#state-machine-diagram)
8. [Class Diagram](#class-diagram)
9. [Data Flow Diagram](#data-flow-diagram)

---

## High-Level System Architecture

```mermaid
graph TB
    subgraph "Deployment Host"
        CLI[os-deploy CLI<br/>Python 3.9+]
        Builder[ISO Builder<br/>Bash Script]
        Config[config.json<br/>NFS + BMC Credentials]

        CLI -->|Load Config| Config
        CLI -->|Execute| Builder
        Builder -->|Generate| ISO[Custom ISO<br/>ubuntu_autoinstall.iso]
    end

    subgraph "Network Infrastructure"
        NFS[NFS Server<br/>192.168.1.100]
        Network[Management Network<br/>VLAN 10]

        ISO -->|Upload| NFS
    end

    subgraph "Target Server"
        BMC[BMC Redfish API<br/>192.168.1.50]
        VirtualMedia[Virtual Media<br/>Controller]
        Host[Host System<br/>x86_64 Server]
        IPMI[IPMI SEL<br/>Event Logs]

        BMC -->|Control| VirtualMedia
        VirtualMedia -->|Mount ISO| Host
        Host -->|Log Events| IPMI
        BMC -->|Read| IPMI
    end

    CLI -->|1. Authenticate| BMC
    CLI -->|2. Mount ISO| VirtualMedia
    CLI -->|3. Reboot| BMC
    CLI -->|4. Monitor| IPMI
    NFS -->|Provide ISO| VirtualMedia
    Host -->|5. Boot & Install| Ubuntu[Ubuntu Server<br/>Installed]

    style CLI fill:#4a90e2,color:#fff
    style Builder fill:#7b68ee,color:#fff
    style BMC fill:#e74c3c,color:#fff
    style Host fill:#27ae60,color:#fff
    style NFS fill:#f39c12,color:#fff
```

---

## Deployment Workflow

```mermaid
sequenceDiagram
    participant User
    participant CLI as os-deploy CLI
    participant Config as config.json
    participant Builder as ISO Builder
    participant NFS as NFS Server
    participant BMC as BMC (Redfish)
    participant VM as Virtual Media
    participant Server as Target Server
    participant IPMI as IPMI SEL

    User->>CLI: os-deploy -B 192.168.1.50 -N 192.168.1.100 -O ubuntu-24.04

    Note over CLI: Phase 1: Validation
    CLI->>Config: Load configuration
    Config-->>CLI: NFS + BMC credentials
    CLI->>BMC: GET /redfish/v1/SessionService
    BMC-->>CLI: 200 OK (Auth valid)
    CLI->>BMC: Check Virtual Media permissions
    BMC-->>CLI: Permissions OK

    Note over CLI,Builder: Phase 2: ISO Generation
    CLI->>Builder: sudo build-ubuntu-autoinstall-iso.sh ubuntu-24.04
    activate Builder
    Builder->>Builder: 1. Fetch base ISO
    Builder->>Builder: 2. Extract ISO contents
    Builder->>Builder: 3. Generate autoinstall config
    Builder->>Builder: 4. Bundle offline packages
    Builder->>Builder: 5. Patch GRUB config
    Builder->>Builder: 6. Create EFI partition
    Builder->>Builder: 7. Repack with xorriso
    Builder-->>CLI: /path/to/ubuntu_24_04_autoinstall.iso
    deactivate Builder

    Note over CLI,NFS: Phase 3: Deployment
    CLI->>NFS: Upload ISO via NFS mount
    NFS-->>CLI: nfs://192.168.1.100/share/ubuntu_24_04_autoinstall.iso

    CLI->>BMC: POST /VirtualMedia/Inband/Actions/InsertMedia
    BMC->>VM: Mount ISO from NFS
    VM-->>BMC: Mounted successfully
    BMC-->>CLI: Virtual media ready

    CLI->>BMC: PATCH /Systems/system (Set boot order: CD-ROM)
    CLI->>BMC: POST /Systems/system/Actions/ComputerSystem.Reset
    BMC->>Server: Power cycle

    Note over Server: Phase 4: Installation
    Server->>Server: UEFI/BIOS boot from virtual CD
    Server->>Server: GRUB loads kernel (autoinstall)
    Server->>Server: cloud-init reads /cdrom/autoinstall/user-data

    Server->>IPMI: Log marker 0x01 (Installation Start)
    Server->>Server: Subiquity: Partition disk
    Server->>Server: Subiquity: Install base system
    Server->>IPMI: Log marker 0x0F (Pre-install packages start)
    Server->>Server: Install dependencies
    Server->>IPMI: Log marker 0x1F (Pre-install complete)

    Server->>IPMI: Log marker 0x06 (Post-install start)
    Server->>Server: Install main packages (Docker, K8s)
    Server->>IPMI: Log marker 0x16 (Post-install complete)

    Server->>Server: Configure network
    Server->>IPMI: Log marker 0x03/0x13 (IP: 192.168.1.51)

    Server->>Server: Verify storage
    Server->>IPMI: Log marker 0x05 (Audit: OK)

    Server->>IPMI: Log marker 0xAA (Installation Complete)
    Server->>Server: Reboot to installed OS

    Note over CLI,IPMI: Phase 5: Monitoring
    loop Every 5 seconds
        CLI->>BMC: GET /LogServices/SEL/Entries
        BMC->>IPMI: Fetch new entries
        IPMI-->>BMC: Event logs
        BMC-->>CLI: JSON event data
        CLI->>CLI: Parse forensic markers
        CLI->>User: [10:00:00] OS Installation Start
        CLI->>User: [10:05:00] IP Address: 192.168.1.51
        CLI->>User: [10:20:00] Installation Complete
    end

    Note over CLI: Phase 6: Completion
    CLI->>User: ✓ Deployment Result: COMPLETED
    CLI->>User: Server IP Address: 192.168.1.51
    CLI->>User: Audit Result: OK
```

---

## ISO Build Pipeline

```mermaid
graph LR
    subgraph "Input"
        BaseISO[Base Ubuntu ISO<br/>ubuntu-24.04.1-live-server-amd64.iso]
        PackageList[package_list<br/>Optional packages]
        UserData[User Credentials<br/>username/password]
    end

    subgraph "Build Process"
        direction TB
        Extract[Extract ISO<br/>mount -o loop]
        GenConfig[Generate Config<br/>user-data<br/>meta-data]
        FetchPkg[Fetch Packages<br/>apt-get download]
        PatchGRUB[Patch GRUB<br/>Add autoinstall entry]
        CreateEFI[Create EFI Partition<br/>20MB FAT32]
        Repack[Repack ISO<br/>xorriso + GPT]

        Extract --> GenConfig
        GenConfig --> FetchPkg
        FetchPkg --> PatchGRUB
        PatchGRUB --> CreateEFI
        CreateEFI --> Repack
    end

    subgraph "Output"
        CustomISO[Custom Autoinstall ISO<br/>ubuntu_24_04_autoinstall.iso]
        Metadata[Metadata<br/>SSH keys<br/>Build ID]
    end

    BaseISO --> Extract
    PackageList --> FetchPkg
    UserData --> GenConfig
    Repack --> CustomISO
    Repack --> Metadata

    style Extract fill:#3498db,color:#fff
    style GenConfig fill:#9b59b6,color:#fff
    style FetchPkg fill:#e67e22,color:#fff
    style Repack fill:#27ae60,color:#fff
    style CustomISO fill:#2ecc71,color:#fff
```

### Detailed ISO Structure

```mermaid
graph TB
    MBR[MBR<br/>GRUB2 Bootloader<br/>432 bytes]
    GPT[GPT Partition Table]

    subgraph Part1["Partition 1: ISO 9660"]
        Casper[/casper/<br/>vmlinuz<br/>initrd]
        BootGRUB[/boot/grub/<br/>grub.cfg]
        Autoinstall[/autoinstall/<br/>user-data<br/>meta-data]
        PoolExtra[/pool/extra/<br/>*.deb packages<br/>Docker, K8s, tools]
    end

    subgraph Part2["Partition 2: EFI System - 20MB"]
        EFIBoot[/EFI/boot/<br/>bootx64.efi<br/>grubx64.efi]
        EFIModules[/boot/grub/<br/>x86_64-efi/<br/>fonts/]
    end

    subgraph Part3["Partition 3: Boot Catalog"]
        ElTorito[El Torito<br/>Boot Catalog<br/>300KB]
    end

    MBR --> GPT
    GPT --> Part1
    GPT --> Part2
    GPT --> Part3

    style MBR fill:#e74c3c,color:#fff
    style GPT fill:#3498db,color:#fff
    style Autoinstall fill:#f39c12,color:#000
    style PoolExtra fill:#9b59b6,color:#fff
    style EFIBoot fill:#27ae60,color:#fff
```

---

## Component Interaction

```mermaid
graph TB
    subgraph "Python Orchestrator"
        Main[main.py<br/>CLI Entry Point]

        subgraph "Library Modules"
            Auth[auth.py<br/>BMC Authentication]
            Utils[utils.py<br/>Redfish Helpers<br/>Event Parsing]
            RemoteMount[remote_mount.py<br/>Virtual Media]
            Reboot[reboot.py<br/>Boot Management]
            NFS[nfs.py<br/>NFS Operations]
            Generation[generation.py<br/>Hardware Detection]
            Constants[constants.py<br/>API Endpoints<br/>Event Mappings]
            Config[config.py<br/>JSON Loading]
            StateManager[state_manager.py<br/>Global State]
        end
    end

    Main --> Auth
    Main --> Utils
    Main --> RemoteMount
    Main --> Reboot
    Main --> NFS
    Main --> Generation

    Auth --> Constants
    Utils --> Constants
    RemoteMount --> Constants
    Reboot --> Constants
    Generation --> Constants

    Main --> Config
    Main --> StateManager
    Utils --> StateManager
    RemoteMount --> StateManager

    subgraph "External Systems"
        RedfishAPI[Redfish API<br/>BMC HTTPS]
        NFSAPI[NFS Server<br/>Mount/Upload]
        BashScript[build-ubuntu-autoinstall-iso.sh<br/>ISO Builder]
    end

    Utils --> RedfishAPI
    RemoteMount --> RedfishAPI
    Reboot --> RedfishAPI
    Generation --> RedfishAPI
    NFS --> NFSAPI
    Main --> BashScript

    style Main fill:#4a90e2,color:#fff
    style Auth fill:#e74c3c,color:#fff
    style Utils fill:#f39c12,color:#000
    style RemoteMount fill:#9b59b6,color:#fff
    style Constants fill:#27ae60,color:#fff
    style RedfishAPI fill:#e67e22,color:#fff
```

---

## Network Architecture

```mermaid
graph TB
    subgraph "Management Network (VLAN 10)"
        DeployHost[Deployment Host<br/>10.99.236.1]
        NFS[NFS Server<br/>10.99.236.100]
        BMC1[BMC 1<br/>10.99.236.50]
        BMC2[BMC 2<br/>10.99.236.51]
        BMC3[BMC 3<br/>10.99.236.52]
    end

    subgraph "Production Network (VLAN 20)"
        Server1[Server 1<br/>192.168.1.50]
        Server2[Server 2<br/>192.168.1.51]
        Server3[Server 3<br/>192.168.1.52]
    end

    subgraph "Storage Network (VLAN 30)"
        NFSData[NFS Storage<br/>172.16.1.100]
    end

    DeployHost -->|Redfish HTTPS| BMC1
    DeployHost -->|Redfish HTTPS| BMC2
    DeployHost -->|Redfish HTTPS| BMC3

    DeployHost -->|Upload ISO| NFS

    BMC1 -->|Mount Virtual Media| NFS
    BMC2 -->|Mount Virtual Media| NFS
    BMC3 -->|Mount Virtual Media| NFS

    BMC1 -.->|Control| Server1
    BMC2 -.->|Control| Server2
    BMC3 -.->|Control| Server3

    Server1 -->|Production Traffic| Internet[Internet]
    Server2 -->|Production Traffic| Internet
    Server3 -->|Production Traffic| Internet

    Server1 -->|Data Storage| NFSData
    Server2 -->|Data Storage| NFSData
    Server3 -->|Data Storage| NFSData

    style DeployHost fill:#4a90e2,color:#fff
    style NFS fill:#f39c12,color:#000
    style BMC1 fill:#e74c3c,color:#fff
    style BMC2 fill:#e74c3c,color:#fff
    style BMC3 fill:#e74c3c,color:#fff
    style Server1 fill:#27ae60,color:#fff
    style Server2 fill:#27ae60,color:#fff
    style Server3 fill:#27ae60,color:#fff
```

---

## IPMI Forensic Flow

```mermaid
graph TB
    subgraph "Target Server - Installation Process"
        Start[Boot from ISO]
        EarlyCmd[early-commands<br/>Disk Detection]
        Install[Install Base System]
        PreInstall[Pre-install Packages<br/>Dependencies]
        PostInstall[Post-install Packages<br/>Docker, K8s]
        Network[Configure Network]
        Audit[Storage Audit]
        Complete[Installation Complete]
        ErrorState[Installation Failed]

        Start --> EarlyCmd
        EarlyCmd --> Install
        Install --> PreInstall
        PreInstall --> PostInstall
        PostInstall --> Network
        Network --> Audit
        Audit --> Complete

        EarlyCmd -.->|Error| ErrorState
        Install -.->|Error| ErrorState
        PreInstall -.->|Error| ErrorState
        PostInstall -.->|Error| ErrorState
    end

    subgraph "IPMI SEL Markers"
        M01[0x01<br/>Installation Start]
        M0F[0x0F<br/>Pre-install Start]
        M1F[0x1F<br/>Pre-install Complete]
        M06[0x06<br/>Post-install Start]
        M16[0x16<br/>Post-install Complete]
        M03[0x03<br/>IP Part 1<br/>Octets 1-2]
        M13[0x13<br/>IP Part 2<br/>Octets 3-4]
        M05[0x05<br/>Storage Audit<br/>OK/ER]
        MAA[0xAA<br/>Installation Complete]
        MEE[0xEE<br/>Installation Failed]
    end

    Start --> M01
    Install --> M0F
    PreInstall --> M1F
    PostInstall --> M06
    PostInstall --> M16
    Network --> M03
    Network --> M13
    Audit --> M05
    Complete --> MAA
    ErrorState --> MEE

    subgraph "Monitoring Console"
        Poll[Poll SEL Every 5s]
        Parse[Parse Forensic Markers]
        Display[Display Progress]

        Poll --> Parse
        Parse --> Display
    end

    M01 -.->|Read| Poll
    M0F -.->|Read| Poll
    M1F -.->|Read| Poll
    M06 -.->|Read| Poll
    M16 -.->|Read| Poll
    M03 -.->|Read| Poll
    M13 -.->|Read| Poll
    M05 -.->|Read| Poll
    MAA -.->|Read| Poll
    MEE -.->|Read| Poll

    style M01 fill:#3498db,color:#fff
    style M0F fill:#9b59b6,color:#fff
    style M1F fill:#9b59b6,color:#fff
    style M06 fill:#e67e22,color:#fff
    style M16 fill:#e67e22,color:#fff
    style M03 fill:#f39c12,color:#000
    style M13 fill:#f39c12,color:#000
    style M05 fill:#1abc9c,color:#fff
    style MAA fill:#27ae60,color:#fff
    style MEE fill:#e74c3c,color:#fff
```

### IPMI Marker Timeline

```mermaid
gantt
    title Installation Timeline with IPMI Markers
    dateFormat HH:mm
    axisFormat %H:%M

    section Boot
    Server Boot           :done, boot, 10:00, 1m
    0x01 Start           :milestone, m01, 10:01, 0m

    section Base Install
    Disk Partitioning    :done, part, 10:01, 2m
    Base System Install  :done, base, 10:03, 5m

    section Pre-install
    0x0F Pre-start       :milestone, m0f, 10:08, 0m
    Dependencies Install :done, deps, 10:08, 3m
    0x1F Pre-complete    :milestone, m1f, 10:11, 0m

    section Post-install
    0x06 Post-start      :milestone, m06, 10:11, 0m
    Docker Install       :done, docker, 10:11, 4m
    Kubernetes Install   :done, k8s, 10:15, 5m
    0x16 Post-complete   :milestone, m16, 10:20, 0m

    section Network
    Network Config       :done, net, 10:20, 2m
    0x03 IP Part1        :milestone, m03, 10:22, 0m
    0x13 IP Part2        :milestone, m13, 10:22, 0m

    section Finalize
    Storage Audit        :done, audit, 10:22, 1m
    0x05 Audit Result    :milestone, m05, 10:23, 0m
    Final Cleanup        :done, clean, 10:23, 2m
    0xAA Complete        :milestone, maa, 10:25, 0m
    Reboot               :done, reboot, 10:25, 1m
```

---

## State Machine Diagram

```mermaid
stateDiagram-v2
    [*] --> Initializing

    Initializing --> ValidatingConfig: Load config.json
    ValidatingConfig --> AuthenticatingBMC: Config valid
    ValidatingConfig --> Failed: Config invalid

    AuthenticatingBMC --> CheckingPermissions: Auth successful
    AuthenticatingBMC --> Failed: Auth failed

    CheckingPermissions --> GeneratingISO: Permissions OK
    CheckingPermissions --> Failed: No VM permissions

    GeneratingISO --> DeployingToNFS: ISO generated
    GeneratingISO --> UsingPrebuiltISO: --iso provided
    GeneratingISO --> Failed: Build failed

    UsingPrebuiltISO --> DeployingToNFS: ISO validated

    DeployingToNFS --> MountingVirtualMedia: Upload complete
    DeployingToNFS --> Failed: NFS error

    MountingVirtualMedia --> Rebooting: Mounted successfully
    MountingVirtualMedia --> Failed: Mount failed

    Rebooting --> MonitoringInstallation: Server rebooting
    Rebooting --> Completed: --no-reboot flag

    MonitoringInstallation --> MonitoringInstallation: Polling SEL logs
    MonitoringInstallation --> Completed: 0xAA received
    MonitoringInstallation --> Failed: 0xEE received
    MonitoringInstallation --> Timeout: 2 hours elapsed

    Completed --> [*]
    Failed --> [*]
    Timeout --> [*]

    note right of ValidatingConfig
        Validate:
        - NFS config
        - BMC credentials
        - File paths
    end note

    note right of GeneratingISO
        Build ISO:
        - Fetch base ISO
        - Generate config
        - Bundle packages
        - Repack with xorriso
    end note

    note right of MonitoringInstallation
        Parse IPMI markers:
        - 0x01: Start
        - 0x0F/0x1F: Pre-install
        - 0x06/0x16: Post-install
        - 0x03/0x13: IP address
        - 0x05: Audit
        - 0xAA: Success
        - 0xEE: Failure
    end note
```

---

## Class Diagram

```mermaid
classDiagram
    class Main {
        +parse_arguments()
        +load_config()
        +validate_bmc_auth()
        +generate_iso()
        +deploy_to_nfs()
        +mount_virtual_media()
        +reboot_server()
        +monitor_installation()
        +main()
    }

    class Config {
        +load_config(path: str) dict
        +validate_schema(config: dict) bool
    }

    class Auth {
        +get_auth_header(target: str, config: dict) str
        -_encode_credentials(user: str, pass: str) str
    }

    class Utils {
        +redfish_get_request(cmd: str, bmc_ip: str, auth: str) Response
        +check_redfish_api(target: str, auth: str) bool
        +check_auth_valid(target: str, auth: str) dict
        +get_redfish_version(bmc_ip: str, auth: str) str
        +getSystemEventLog(bmc_ip: str, auth: str, from_ts: int) list
        +filter_custom_event(events: list, bmc_ip: str, auth: str) list
        +decode_event(message: str) str
        +formatted_time() str
    }

    class RemoteMount {
        +mount_image(mount_path: str, target: str, config: dict) str
        -_fetch_virtual_media(target: str, auth: str) Response
        -_get_candidate_mount_point(json_body: dict) list
        -_check_usable(target: str, auth: str, endpoint: str) str
        -exec_mount_image(path: str, target: str, auth: str, endpoint: str) bool
    }

    class Reboot {
        +reboot_cdrom(bmc_ip: str, config: dict) str
        +clear_postcode_log(bmc_ip: str, config: dict)
        +set_boot_cdrom(bmc_ip: str, auth: str)
    }

    class NFS {
        +get_nfs_exports(nfs_ip: str) list
        +drop_file_to_nfs(nfs_ip: str, nfs_path: str, iso_path: Path) str
        -_mount_nfs(nfs_ip: str, nfs_path: str) str
        -_copy_to_nfs(iso_path: Path, mount_point: str) str
    }

    class Generation {
        +get_generation_redfish(bmc_ip: str, auth: str) tuple
        -_detect_generation(system_info: dict) int
        -_detect_product_model(system_info: dict) str
    }

    class Constants {
        +VIRTUAL_MEDIA_API_DICT: dict
        +INBAND_MEDIA: dict
        +LOG_FETCH_API: dict
        +EventLogPrefix: dict
        +EventLogMessage: dict
        +REDFISH_TIMEOUT: int
        +PROCESS_TIMEOUT: int
    }

    class StateManager {
        +state: DeploymentState
    }

    class DeploymentState {
        +generation: int
        +product_model: str
        +redfish_version: str
        +log_save_path: str
    }

    Main --> Config
    Main --> Auth
    Main --> Utils
    Main --> RemoteMount
    Main --> Reboot
    Main --> NFS
    Main --> Generation
    Main --> StateManager

    Utils --> Constants
    RemoteMount --> Constants
    RemoteMount --> StateManager
    Reboot --> Constants
    Generation --> Constants

    StateManager --> DeploymentState
```

---

## Data Flow Diagram

```mermaid
graph TD
    subgraph "Level 0: Context Diagram"
        User[System Administrator] -->|Command Line Args| System[OS Auto Deployment]
        System -->|SSH Key| User
        System <-->|Redfish API| BMC[BMC Controller]
        System <-->|NFS Mount| NFS[NFS Server]
        System -->|Monitor| Console[Console Output]
    end
```

```mermaid
graph TB
    subgraph "Level 1: System Decomposition"
        A[User Input] --> B[Validation Process]
        B --> C[ISO Generation]
        C --> D[Deployment Process]
        D --> E[Installation Monitor]
        E --> F[Result Output]

        G[config.json] -.-> B
        H[Base Ubuntu ISO] -.-> C
        I[NFS Server] <-.-> D
        J[BMC Redfish API] <-.-> D
        J <-.-> E
        K[IPMI SEL Logs] -.-> E
    end
```

```mermaid
graph LR
    subgraph "Level 2: Detailed Data Flow"
        direction TB

        subgraph "Input Processing"
            IN1[CLI Arguments] --> Parse[Argument Parser]
            IN2[config.json] --> Parse
            Parse --> Valid{Valid?}
            Valid -->|Yes| Credentials[BMC Credentials]
            Valid -->|No| Error1[Error Exit]
        end

        subgraph "ISO Creation"
            Credentials --> ISOBuilder[ISO Builder]
            ISO_Repo[ISO Repository] --> ISOBuilder
            Pkg_List[package_list] --> ISOBuilder
            ISOBuilder --> Custom_ISO[Custom ISO File]
        end

        subgraph "Deployment"
            Custom_ISO --> NFS_Upload[NFS Upload]
            NFS_Upload --> NFS_Path[NFS ISO Path]
            NFS_Path --> VM_Mount[Virtual Media Mount]
            Credentials --> VM_Mount
            VM_Mount --> Boot[Set Boot Order]
            Boot --> Reboot_Cmd[Reboot Command]
        end

        subgraph "Monitoring"
            Reboot_Cmd --> Poll[Poll SEL Logs]
            Poll --> Fetch[Fetch Events]
            Fetch --> Filter[Filter Custom Events]
            Filter --> Decode[Decode Markers]
            Decode --> Check{Complete?}
            Check -->|0xAA| Success[Success Output]
            Check -->|0xEE| Failure[Failure Output]
            Check -->|Pending| Poll
            Check -->|Timeout| Timeout[Timeout Output]
        end

        Success --> Results[Deployment Results]
        Failure --> Results
        Timeout --> Results
        Results --> User_Output[Console Display]
    end

    style Parse fill:#4a90e2,color:#fff
    style ISOBuilder fill:#9b59b6,color:#fff
    style VM_Mount fill:#e74c3c,color:#fff
    style Poll fill:#f39c12,color:#000
    style Success fill:#27ae60,color:#fff
    style Failure fill:#e74c3c,color:#fff
```

---

## Hardware Generation Support

```mermaid
graph TB
    Detect[get_generation_redfish]
    Check{Redfish Version}
    Gen6[Generation 6<br/>EGS Platform]
    Gen7[Generation 7<br/>BHS Platform]

    Detect --> Check
    Check -->|"< 1.17.0"| Gen6
    Check -->|">= 1.17.0"| Gen7

    subgraph Gen6Config["Gen-6 Configuration"]
        API6[API Endpoints]
        VM6[/redfish/v1/Managers/bmc/<br/>VirtualMedia/Internal/]
        LOG6[/redfish/v1/Systems/system/<br/>LogServices/EventLog/Entries]
        PREFIX6[EventLogPrefix:<br/>0000020000000021000412006F]

        API6 --> VM6
        API6 --> LOG6
        API6 --> PREFIX6
    end

    subgraph Gen7Config["Gen-7 Configuration"]
        API7[API Endpoints]
        VM7[/redfish/v1/Managers/bmc/<br/>VirtualMedia/Inband/]
        LOG7[/redfish/v1/Managers/bmc/<br/>LogServices/SEL/Entries]
        PREFIX7[EventLogPrefix:<br/>210012006F]
        ADDITIONAL[AdditionalDataURI<br/>External forensic data]

        API7 --> VM7
        API7 --> LOG7
        API7 --> PREFIX7
        API7 --> ADDITIONAL
    end

    subgraph CommonOps["Common Operations"]
        Mount[Mount Virtual Media]
        Monitor[Monitor Installation]
        Parse[Parse IPMI Markers]
    end

    Gen6 --> Gen6Config
    Gen7 --> Gen7Config
    Gen6 --> CommonOps
    Gen7 --> CommonOps

    style Gen6 fill:#3498db,color:#fff
    style Gen7 fill:#9b59b6,color:#fff
    style Mount fill:#27ae60,color:#fff
    style Monitor fill:#f39c12,color:#000
    style Parse fill:#e67e22,color:#fff
```

---

## Error Handling Flow

```mermaid
graph TB
    Start[Start Deployment] --> LoadConfig[Load Config]

    LoadConfig -->|Success| ValidateCreds[Validate Credentials]
    LoadConfig -->|Fail| E1[ConfigError:<br/>Invalid JSON]

    ValidateCreds -->|Success| CheckPerms[Check VM Permissions]
    ValidateCreds -->|Fail| E2[AuthError:<br/>Invalid credentials]

    CheckPerms -->|Success| BuildISO[Build/Validate ISO]
    CheckPerms -->|Fail| E3[PermissionError:<br/>VM not enabled]

    BuildISO -->|Success| DeployNFS[Deploy to NFS]
    BuildISO -->|Fail| E4[BuildError:<br/>ISO generation failed]

    DeployNFS -->|Success| MountVM[Mount Virtual Media]
    DeployNFS -->|Fail| E5[NFSError:<br/>Upload failed]

    MountVM -->|Success| RebootSrv[Reboot Server]
    MountVM -->|Fail| E6[MountError:<br/>VM mount failed]

    RebootSrv -->|Success| Monitor[Monitor Installation]
    RebootSrv -->|Fail| E7[RebootError:<br/>Power control failed]

    Monitor -->|0xAA| Success[Deployment Complete]
    Monitor -->|0xEE| E8[InstallError:<br/>Installation failed]
    Monitor -->|Timeout| E9[TimeoutError:<br/>No response]

    E1 --> Cleanup[Cleanup Resources]
    E2 --> Cleanup
    E3 --> Cleanup
    E4 --> Cleanup
    E5 --> Cleanup
    E6 --> CleanupVM[Unmount Virtual Media]
    E7 --> CleanupVM
    E8 --> CleanupVM
    E9 --> CleanupVM

    CleanupVM --> Cleanup
    Cleanup --> LogError[Log Error Details]
    LogError --> Exit[Exit with Error Code]

    Success --> CleanupSuccess[Optional Cleanup]
    CleanupSuccess --> LogSuccess[Log Success]
    LogSuccess --> ExitSuccess[Exit with Code 0]

    style Success fill:#27ae60,color:#fff
    style E1 fill:#e74c3c,color:#fff
    style E2 fill:#e74c3c,color:#fff
    style E3 fill:#e74c3c,color:#fff
    style E4 fill:#e74c3c,color:#fff
    style E5 fill:#e74c3c,color:#fff
    style E6 fill:#e74c3c,color:#fff
    style E7 fill:#e74c3c,color:#fff
    style E8 fill:#e74c3c,color:#fff
    style E9 fill:#e74c3c,color:#fff
```

---

## Deployment Patterns

### Single Server Deployment

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant BMC as BMC<br/>192.168.1.50
    participant Server as Server 1

    User->>CLI: os-deploy -B 192.168.1.50 -N 192.168.1.100 -O ubuntu-24.04
    CLI->>BMC: Authenticate
    CLI->>BMC: Mount ISO
    CLI->>BMC: Reboot
    BMC->>Server: Power cycle
    Server->>Server: Install OS
    CLI->>BMC: Monitor progress
    BMC-->>CLI: Installation complete
    CLI-->>User: ✓ Deployment successful
```

### Parallel Deployment (Roadmap)

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant BMC1 as BMC 1
    participant BMC2 as BMC 2
    participant BMC3 as BMC 3
    participant Server1 as Server 1
    participant Server2 as Server 2
    participant Server3 as Server 3

    User->>CLI: Deploy to 192.168.1.{50..52}

    par Deploy Server 1
        CLI->>BMC1: Authenticate & Mount
        CLI->>BMC1: Reboot
        BMC1->>Server1: Install
    and Deploy Server 2
        CLI->>BMC2: Authenticate & Mount
        CLI->>BMC2: Reboot
        BMC2->>Server2: Install
    and Deploy Server 3
        CLI->>BMC3: Authenticate & Mount
        CLI->>BMC3: Reboot
        BMC3->>Server3: Install
    end

    par Monitor Server 1
        CLI->>BMC1: Poll SEL
        BMC1-->>CLI: 0xAA
    and Monitor Server 2
        CLI->>BMC2: Poll SEL
        BMC2-->>CLI: 0xAA
    and Monitor Server 3
        CLI->>BMC3: Poll SEL
        BMC3-->>CLI: 0xAA
    end

    CLI-->>User: ✓ All 3 servers deployed
```

---

## Summary

These diagrams provide a comprehensive visual representation of the OS Auto Deployment system architecture:

1. **High-Level Architecture** - Overall system components and relationships
2. **Deployment Workflow** - Complete sequence from user command to installed OS
3. **ISO Build Pipeline** - Custom ISO creation process
4. **Component Interaction** - Python module dependencies
5. **Network Architecture** - Multi-VLAN network topology
6. **IPMI Forensic Flow** - Installation monitoring with markers
7. **State Machine** - Deployment state transitions
8. **Class Diagram** - Code structure and relationships
9. **Data Flow** - Information flow through the system

These diagrams can be rendered in any Mermaid-compatible viewer or documentation platform.

---

**Document Information:**
- **Version:** 1.0
- **Last Updated:** 2026-03-30
- **Diagram Format:** Mermaid.js
- **License:** Copyright © 2025-2026 MiTAC Computing Technology Corporation
