# OS Auto Deployment

Automatically deploy OS (Ubuntu) to target servers via BMC (Baseboard Management Controller).

## Quick Start

```bash
# Install dependencies
poetry install

# Run the tool
os-deploy -B <BMC_IP> -N <NFS_IP> -O <ISO_NAME>
```

## Documentation

- [Usage Guide](doc/main_usage.md) — Full CLI reference, configuration, workflow, and examples.

## License

Copyright © 2025 MiTAC Computing Technology Corporation. All rights reserved.
