# Suggestion 1: Dynamic User-Data — Easy Read Version
## Draw.io Compatible Diagram

> **Analogy:** Think of this like a **restaurant kitchen**.
> - The **generic ISO** is a blank meal kit — the same box shipped to every table.
> - The **per-node YAML config** is the customer's order slip — unique per table.
> - The **HTTP User-Data Server** is the waiter who reads the order slip and tells the kitchen exactly how to prepare the meal.
> - Without this proposal, the kitchen had to pre-pack a custom box for every single table before service even started.

---

### How to Import into Draw.io

1. Open [app.diagrams.net](https://app.diagrams.net/)
2. Click **Extras** > **Edit Diagram**
3. Paste the Mermaid code below and click **OK**

---

```mermaid
flowchart TD
    classDef person  fill:#f8cecc,stroke:#b85450,stroke-width:2px;
    classDef prep    fill:#dae8fc,stroke:#6c8ebf,stroke-width:2px;
    classDef new     fill:#cce5ff,stroke:#004085,stroke-width:2px,font-weight:bold;
    classDef config  fill:#fff2cc,stroke:#d6b656,stroke-width:2px;
    classDef server  fill:#d5e8d4,stroke:#82b366,stroke-width:2px;
    classDef result  fill:#d5e8d4,stroke:#00897b,stroke-width:3px,font-weight:bold;

    Admin(["👤 Admin"]):::person

    subgraph Prepare ["🖥️  Preparation  —  done ONCE, reused forever"]
        ISO[("💿 One Universal\nInstall Disc\nsame disc for every server")]:::new
        FileServer["📂 File Server\nholds the install disc"]:::prep
        OrderBook[("📋 Server Order Book\none config file per server\n───────────────────\nserver-A.yaml\n  which hard disk to use\n  hostname\n  IP address")]:::config
    end

    subgraph DeployTool ["🛠️  Deployment Tool  —  runs on Admin's machine"]
        Tool["▶ os-deploy\nremote control tool"]:::prep
        Waiter["🧾 Config Waiter\nserves the right config\nwhen a server asks for it\n(new component)"]:::new
    end

    subgraph NewServer ["🖧  New Server  —  being installed"]
        RemoteCtrl["🔌 Remote Controller\n(built into every server)\nreceives commands\neven when OS is not installed"]:::server
        Installer["⚙️ Auto Installer\nruns from disc in memory\nasks Waiter for instructions"]:::server
        Disk[("💾 Hard Disk\nOS will be installed here")]:::server
    end

    Done(["✅ Server Ready\nhostname & IP assigned\nOS installed"]):::result

    %% Prepare phase
    Admin       -->|"1️⃣  Build install disc\n(one-time per Ubuntu version)"| ISO
    ISO         -.->|"stored on"| FileServer
    Admin       -->|"2️⃣  Fill in order book\none entry per server"| OrderBook
    OrderBook   -.->|"read by"| Waiter

    %% Deploy phase
    Admin       -->|"3️⃣  Run os-deploy\nfor target server"| Tool
    Tool        -->|"4️⃣  Insert install disc\ninto server remotely"| RemoteCtrl
    Tool        -->|"5️⃣  Power cycle\nthe server"| RemoteCtrl
    Tool        -->|"6️⃣  Start Config Waiter\nready to answer"| Waiter
    FileServer <-->|"7️⃣  Stream disc\nover network"| RemoteCtrl

    %% Install phase
    RemoteCtrl  -->|"8️⃣  Server boots\nfrom install disc"| Installer
    Installer   -->|"9️⃣  Ask: what are\nmy instructions?\n(sends own MAC address)"| Waiter
    Waiter      -->|"🔟  Here is your\ncustom install plan\n(hostname, disk, IP)"| Installer
    Installer   -->|"1️⃣1️⃣  Format disk\n& install OS"| Disk
    Disk        -->|"1️⃣2️⃣  Reboot into\nnew OS"| Done
```

---

### What Each Part Does (Plain Language)

| Component | What it is | Plain English |
|---|---|---|
| **One Universal Install Disc** | Generic Ubuntu ISO | Like a blank USB stick with Ubuntu — same one used for every server |
| **File Server** | NFS share | A shared folder on the network that holds the install disc |
| **Server Order Book** | Per-node YAML config files | A notebook with one page per server — what disk to use, what hostname, what IP |
| **os-deploy** | Python CLI tool | The remote control that operates the server even before an OS is installed |
| **Config Waiter** | Embedded HTTP server | Sits and waits for a server to ask "what should I do?" — answers with the right install plan |
| **Remote Controller** | BMC (IPMI/Redfish) | A tiny independent chip in every server that lets you power it on/off and insert a virtual disc remotely |
| **Auto Installer** | Ubuntu Subiquity | The install wizard that runs automatically from the disc, no human clicking needed |
| **Hard Disk** | Target SSD/HDD | Where the final OS gets written |

---

### Why This Is Better Than Before

```
BEFORE                              AFTER
──────────────────────────────      ──────────────────────────────
Build custom disc for server A      Build ONE disc  (done once)
Build custom disc for server B           │
Build custom disc for server C           │
        │                                ▼
        ▼                          Write one config file per server
Boot server A from its disc              │
Boot server B from its disc              ▼
Boot server C from its disc        Boot ALL servers from same disc
                                   Each server fetches its own plan
```

- **Before:** 10 servers = 10 ISO builds, 10 different disc files, lots of storage
- **After:** 10 servers = 1 ISO build, 10 small YAML files (each ~10 lines)
