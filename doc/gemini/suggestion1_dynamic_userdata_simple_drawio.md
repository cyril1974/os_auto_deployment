# Suggestion 1: Dynamic User-Data Architecture (Simplified)
## Draw.io Compatible Diagram

**Goal:** Use one generic ISO for all servers. Instead of baking config into the ISO, serve each node's `autoinstall.yaml` dynamically over HTTP at boot time.

### Current vs. Proposed

| | Current | Proposed |
|---|---|---|
| ISO | Rebuilt for every node | One ISO reused for all nodes |
| `autoinstall.yaml` | Embedded inside ISO | Served over HTTP at boot time |
| Node identity | Baked into ISO at build time | Looked up by MAC address at runtime |

---

### How to Import into Draw.io

1. Open [app.diagrams.net](https://app.diagrams.net/)
2. Click **Extras** > **Edit Diagram**
3. Paste the Mermaid code below and click **OK**

---

```mermaid
flowchart TD
    classDef user   fill:#f8cecc,stroke:#b85450,stroke-width:2px;
    classDef host   fill:#dae8fc,stroke:#6c8ebf,stroke-width:2px;
    classDef new    fill:#cce5ff,stroke:#004085,stroke-width:2px,font-weight:bold;
    classDef config fill:#fff2cc,stroke:#d6b656,stroke-width:2px;
    classDef bmc    fill:#d5e8d4,stroke:#82b366,stroke-width:2px;
    classDef hw     fill:#e1d5e7,stroke:#9673a6,stroke-width:2px;

    User([Admin]):::user

    subgraph Host ["Host System"]
        Builder["Build Script\nBuilds ONE generic ISO"]:::host
        GenISO[("Generic Ubuntu ISO\nreused for ALL nodes")]:::new
        NFS["NFS Server"]:::host
        CLI["os-deploy CLI\nRedfish / IPMI"]:::host
        HTTPSrv["HTTP User-Data Server\n:8080\nnew component"]:::new
        NodeConfigs[("Per-Node YAML Config\nnode_AA:BB:CC.yaml\n───────────────\ndisk_serial: WD-XXX\nhostname: node-01\nip: 192.168.1.10")]:::config
    end

    subgraph Target ["Target Server"]
        BMC{"BMC\nRedfish / IPMI"}:::bmc
        Installer["Subiquity Installer\nin RAM"]:::hw
        SSD[("Target SSD")]:::hw
    end

    %% Setup (one-time)
    User        -->|"1. Build once"| Builder
    Builder     -->|"2. Output"| GenISO
    GenISO      -.->|"hosted on"| NFS
    User        -->|"3. Write config\nper node"| NodeConfigs
    NodeConfigs -.->|"loaded by"| HTTPSrv

    %% Deploy
    User        -->|"4. Run os-deploy"| CLI
    CLI         -->|"5. Mount ISO\nvia Virtual Media"| BMC
    CLI         -->|"6. Reboot server"| BMC
    CLI         -->|"7. Start HTTP server"| HTTPSrv
    NFS        <-->|"8. Stream ISO"| BMC

    %% Install
    BMC         -->|"9. Boot from ISO"| Installer
    Installer   -->|"10. GET /user-data\n?mac=AA:BB:CC"| HTTPSrv
    HTTPSrv     -->|"11. Return node-specific\nautoinstall.yaml"| Installer
    Installer   -->|"12. Install OS"| SSD
    Installer   -->|"13. Log completion\nto SEL"| BMC
```

---

### Key Points

- **Step 1–2:** Run the build script once per Ubuntu version — the same ISO is used for every server.
- **Step 3:** The only per-node setup is a small YAML file (disk serial, hostname, IP), stored on the host.
- **Step 10–11:** At boot, the installer asks the HTTP server for its config using its MAC address. The HTTP server returns the correct `autoinstall.yaml` for that node.
- **No new infrastructure needed** — the HTTP server runs inside the existing `os-deploy` process.
