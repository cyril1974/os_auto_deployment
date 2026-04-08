# Suggestion 1: Decouple Node Configs from ISO (Dynamic User-Data)
## Draw.io Compatible Architecture Diagram

This diagram illustrates the proposed architecture for **Suggestion 1**: replacing per-node custom ISOs with a single generic ISO + a dynamic HTTP user-data server hosted in the Python Orchestration tier.

### Key Changes vs. Current Architecture

| | Current | Proposed |
|---|---|---|
| ISO | Re-built per node (embeds `autoinstall.yaml` + disk serial) | Single generic ISO, reused for all nodes |
| `autoinstall.yaml` | Baked into ISO at build time | Served dynamically over HTTP at boot time |
| Node identity | Encoded in ISO filename / build step | Resolved at runtime via MAC address or BMC IP |
| Config store | Implicit (one ISO = one config) | Explicit YAML inventory files per node |

---

### How to Import into Draw.io

1. Open [Draw.io / Diagrams.net](https://app.diagrams.net/).
2. In the toolbar, click **Extras** > **Edit Diagram** (or `+` > **Advanced** > **Mermaid...**).
3. Copy the Mermaid code block below (excluding the triple backticks) and paste it into the dialog.
4. Click **OK** / **Insert** to render.

---

```mermaid
flowchart TD
    %% Style Definitions
    classDef user     fill:#f8cecc,stroke:#b85450,stroke-width:2px;
    classDef host     fill:#dae8fc,stroke:#6c8ebf,stroke-width:2px;
    classDef httpSrv  fill:#cce5ff,stroke:#004085,stroke-width:2px,font-weight:bold;
    classDef config   fill:#fff2cc,stroke:#d6b656,stroke-width:2px;
    classDef external fill:#f5f5f5,stroke:#666666,stroke-width:2px;
    classDef bmc      fill:#d5e8d4,stroke:#82b366,stroke-width:2px;
    classDef hw       fill:#e1d5e7,stroke:#9673a6,stroke-width:2px;
    classDef new      fill:#d5e8d4,stroke:#00897b,stroke-width:3px,font-weight:bold;

    User([DevOps / Admin User]):::user

    subgraph Host ["Tier 1 & Tier 2 — Host System"]
        direction TB

        Builder["Builder Script (Bash)\nBuilds ONE generic ISO\n(no node-specific config)"]:::host
        GenISO[("Generic Ubuntu ISO\n(nocloud-net enabled)\nReused for ALL nodes")]:::new
        NFS["NFS Server\nHosts Generic ISO"]:::host

        subgraph Orchestrator ["Python Orchestrator (os-deploy CLI)"]
            direction TB
            CLI["Orchestrator CLI\nRedfish / IPMI Control"]:::host
            HTTPSrv["HTTP User-Data Server\n(lightweight, built-in)\nListens on :8080"]:::httpSrv
        end

        NodeConfigs[("Node Config Store\nper-node YAML files\nkeyed by MAC / BMC IP\n\nnode_AA:BB:CC:DD:EE:FF.yaml\n  disk_serial: WD-XXXXX\n  hostname: node-01\n  ip: 192.168.1.10")]:::config
    end

    UbuntuMirror[("Ubuntu APT Mirrors\n(External)")]:::external

    subgraph Target ["Tier 3 — Target Physical Server"]
        direction TB
        BMC{"Target BMC\n(Redfish / IPMI)"}:::bmc
        RAMDisk["RAM Disk\n(Subiquity Auto-Installer)\nqueries HTTP for user-data"]:::hw
        SSD[("Target SSD\n(New OS Destination)")]:::hw
    end

    %% Build Phase
    User         -->|"1. Run build script\n(once per Ubuntu version)"| Builder
    Builder     <-->|"2. Fetch offline packages"| UbuntuMirror
    Builder      -->|"3. Produce single\ngeneric ISO"| GenISO
    GenISO      -.->|"Hosted via"| NFS

    %% Config Preparation
    User         -->|"4. Maintain per-node\nYAML config files"| NodeConfigs
    NodeConfigs -.->|"Loaded by"| HTTPSrv

    %% Deployment Phase
    User         -->|"5. Run os-deploy\n-B <BMC_IP>"| CLI
    CLI          -->|"6. Mount generic ISO\nvia Virtual Media"| BMC
    CLI          -->|"7. Set boot order\n& hard reboot"| BMC
    CLI          -->|"8. Start HTTP\nuser-data server"| HTTPSrv
    NFS         <-->|"9. Stream ISO\nover network"| BMC

    %% Boot & Install Phase
    BMC          -->|"10. Boot from\nnetwork CDROM"| RAMDisk
    RAMDisk      -->|"11. Query user-data\nGET /user-data?mac=AA:BB:CC\nor ?bmc=10.x.x.x"| HTTPSrv
    HTTPSrv      -->|"12. Serve node-specific\nautoinstall.yaml\n(disk serial, hostname, IP)"| RAMDisk
    RAMDisk      -->|"13. Auto-partition\n& install OS"| SSD
    RAMDisk      -->|"14. Log completion\nevent to SEL"| BMC
    RAMDisk      -->|"15. Reboot to\nnew OS"| SSD
```

---

### Architecture Notes

- **Steps 1–3** only need to run once per Ubuntu release — the same generic ISO is reused for every node in the cluster.
- **Step 4** is the only per-node preparation: a small YAML file with `disk_serial`, `hostname`, `ip`, etc., keyed by MAC address or BMC IP.
- **Steps 11–12** are the core of the proposal: Subiquity's `nocloud-net` data source fetches `user-data` from the HTTP server at boot time. The server identifies the node by its MAC address or BMC IP from the HTTP request and returns the correct `autoinstall.yaml`.
- The HTTP user-data server runs inside the existing Python Orchestrator process — no new infrastructure is required.
