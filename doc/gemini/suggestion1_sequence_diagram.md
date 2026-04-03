# Suggestion 1: Dynamic Provisioning Sequence Flow

This sequence chart demonstrates the timeline and interaction between the different tiers when utilizing an **embedded HTTP Server** combined with a **vanilla generic ISO** instead of having to rebuild the ISO file.

```mermaid
sequenceDiagram
    autonumber
    actor Admin as DevOps/Admin
    participant CLI as Orchestrator / CLI
    participant HTTP as Embedded HTTP Server
    participant BMC as Target BMC
    participant Target as Physical Server
    
    Admin->>CLI: Start deployment (MAC, IPs, Disk Serial)
    CLI->>HTTP: Register target node config in memory/DB
    
    %% Boot sequence
    CLI->>BMC: Mount Vanilla ISO via Virtual Media
    CLI->>BMC: Push Power Cycle (Reboot) Command
    BMC-->>Target: Initiate Hardware Boot
    Target->>BMC: Boot from Network/Virtual CD-ROM
    
    %% Installer execution
    Target->>Target: Loads Subiquity Installer Image into RAM
    Note over Target, HTTP: Kernel boot parameters instruct Installer to fetch config via nocloud-net
    
    %% Calling home for dynamic YAML
    Target->>HTTP: HTTP GET /user-data?mac=XX:XX:XX
    HTTP->>HTTP: Lookup node via MAC &<br/>Render dynamic autoinstall.yaml
    HTTP-->>Target: HTTP 200 OK (Returns custom YAML)
    
    %% Local installation
    Target->>Target: Validate target Disk Serial
    Target->>Target: Partition Drives & Install Ubuntu OS
    
    %% Post installation
    Target->>BMC: Late-Command: Log new Host IP to SEL
    Target->>Target: Final Reboot into Target SSD
    Target-->>Admin: Server is successfully provisioned
```
