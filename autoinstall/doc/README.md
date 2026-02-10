# Ubuntu Autoinstall ISO Builder - Documentation

## Documentation Structure

This directory contains comprehensive documentation for the Ubuntu Autoinstall ISO Builder project.

### Documents

1. **[Architecture](01_architecture.md)** - System architecture, component structure, and technology stack
2. **[Workflow](02_workflow.md)** - Build process flow, installation workflow, and error handling
3. **[Development Progress](03_development_progress.md)** - Project timeline, bug fixes, and feature status
4. **[Debugging Guide](04_debugging_guide.md)** - Troubleshooting, common issues, and solutions

## Quick Links

### For Users
- **Getting Started**: See main [README.md](../README.md) (if exists) or run `./build-ubuntu-autoinstall-iso.sh --help`
- **Common Issues**: [Debugging Guide - Common Issues](04_debugging_guide.md#common-issues--solutions)
- **Installation Logs**: [Debugging Guide - Log Files](04_debugging_guide.md#log-file-reference)

### For Developers
- **System Design**: [Architecture - Overview](01_architecture.md#overview)
- **Build Process**: [Workflow - Build Process](02_workflow.md#build-process-flow)
- **Known Issues**: [Development Progress - Known Limitations](03_development_progress.md#known-limitations)

### For Troubleshooting
- **Boot Issues**: [Debugging Guide - Issue 1 & 2](04_debugging_guide.md#issue-1-iso-not-appearing-in-uefi-boot-menu)
- **Installation Errors**: [Debugging Guide - Issue 4 & 5](04_debugging_guide.md#issue-4-cloud-init-crash---nonetype-error)
- **Diagnostic Commands**: [Debugging Guide - Quick Diagnostics](04_debugging_guide.md#quick-diagnostic-commands)

## Project Overview

The Ubuntu Autoinstall ISO Builder creates custom Ubuntu Server ISOs for fully automated installations via BMC virtual media. The system uses cloud-init's autoinstall feature with hybrid UEFI/BIOS boot support.

### Key Features
- ✅ GPT partition table for UEFI compatibility
- ✅ Hybrid BIOS/UEFI boot support
- ✅ Automated installation with no user interaction
- ✅ SSH server with key-based authentication
- ✅ Configurable user credentials
- ✅ Root access enabled
- ✅ Sudo configuration
- ✅ Optional package installation

### Technology Stack
- **Build**: bash, xorriso, mtools, mkpasswd
- **Boot**: GRUB2, El Torito, GPT/MBR
- **Install**: cloud-init, subiquity, curtin

## Document Conventions

### Diagrams
- Mermaid diagrams for visual representation
- Flowcharts for processes
- Sequence diagrams for interactions

### Code Blocks
- Bash commands with syntax highlighting
- Configuration examples
- Log output samples

### Status Indicators
- ✅ Complete/Working
- ⚠️ Warning/Caution
- ❌ Error/Failed
- 🔧 In Progress

## Contributing to Documentation

When updating documentation:
1. Keep diagrams up-to-date with code changes
2. Add new issues to debugging guide
3. Update progress tracking
4. Include examples and verification steps

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-10 | Initial documentation release |

## Support

For issues or questions:
1. Check [Debugging Guide](04_debugging_guide.md)
2. Review [Development Progress](03_development_progress.md) for known issues
3. Examine log files during installation
4. Create detailed bug report with logs
