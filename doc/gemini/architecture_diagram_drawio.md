# OS Auto Deployment - Architecture Diagram (Draw.io Compatible)

The following diagram represents the core architecture and workflow of the OS Auto Deployment tool. 

It is provided using **Mermaid JS**, which is fully supported and natively editable in **Draw.io**.

### How to use this in Draw.io / Diagrams.net:
1. Open up [Draw.io / Diagrams.net](https://app.diagrams.net/).
2. In the top toolbar, go to **Arrange** > **Insert** > **Advanced** > **Mermaid...** (or click the `+` icon in the toolbar > **Advanced** > **Mermaid...**).
3. Copy the plain text content from the code block below (excluding the backticks ````mermaid ````) and paste it into the dialog box.
4. Click **Insert**. Draw.io will automatically parse the code and render a fully editable, styled diagram with native shapes and routing!

```mermaid
flowchart TD
    %% Defined Styles for Draw.io parsing
    classDef user fill:#f8cecc,stroke:#b85450,stroke-width:2px;
    classDef host fill:#dae8fc,stroke:#6c8ebf,stroke-width:2px;
    classDef external fill:#fff2cc,stroke:#d6b656,stroke-width:2px;
    classDef bmc fill:#d5e8d4,stroke:#82b366,stroke-width:2px;
    classDef hw fill:#e1d5e7,stroke:#9673a6,stroke-width:2px;

    User([DevOps/Admin User]):::user
    
    subgraph Host ["Tier 1 & Tier 2 (Host System)"]
        direction TB
        Builder["Builder Script\n(Bash)"]:::host
        ISO[("Custom Ubuntu ISO\n(w/ autoinstall.yaml)")]:::host
        CLI["Orchestrator CLI\n(os-deploy Python)"]:::host
        NFS["NFS Server / Share"]:::host
    end

    UbuntuMirror[("Ubuntu APT Mirrors\n(External Dependency)")]:::external

    subgraph Target ["Tier 3 (Target Physical Server)"]
        direction TB
        BMC{"Target BMC\n(Redfish/IPMI Endpoint)"}:::bmc
        RAMDisk["RAM Disk\n(Subiquity Auto-Installer)"]:::hw
        SSD[("Target SSD\n(New OS Destination)")]:::hw
    end

    %% Step-by-Step Connections
    User -->|1. Run Build Scripts| Builder
    Builder <-->|2. Fetch Offline Dependencies| UbuntuMirror
    Builder -->|3. Generate & Embed Package| ISO
    ISO -.->|Hosted via| NFS
    
    User -->|4. Run os-deploy| CLI
    CLI -->|5. Mount ISO via Virtual Media| BMC
    CLI -->|6. Set Boot Mode & Hard Reboot| BMC
    NFS <-->|7. Serve ISO over Network| BMC
    
    BMC -->|8. Boot from Network CDROM| RAMDisk
    RAMDisk -->|9. Pre-Install: Log Start Event to SEL| BMC
    RAMDisk -->|10. Auto-Partition & Install OS| SSD
    RAMDisk -->|11. Post-Install: Log Assigned IP to SEL| BMC
    RAMDisk -->|12. Auto Reboot to New OS| SSD

```
