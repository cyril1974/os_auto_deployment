# Build Script Modification Summary

## Changes Made to `build-ubuntu-autoinstall-iso.sh`

### Overview
Modified the script to accept an **OS name** instead of an ISO file path. The script now looks up the actual ISO path from `file_list.json`.

### Key Changes

#### 1. New Function: `lookup_iso_path()`
```bash
lookup_iso_path() {
    local os_name="$1"
    local json_file="./iso_repository/file_list.json"
    
    # Use jq to find the OS_Path for the given OS_Name
    local iso_path=$(jq -r ".ISO_Repository.Ubuntu[] | select(.OS_Name == \"$os_name\") | .OS_Path" "$json_file")
    
    # Returns: ./iso_repository/Ubuntu/ubuntu-22.04.2-live-server-amd64.iso
}
```

#### 2. Updated Parameters
**Before:**
- `$1` = ISO file path
- `$2` = Username
- `$3` = Password

**After:**
- `$1` = OS name (e.g., `ubuntu-22.04.2-live-server-amd64`)
- `$2` = Username
- `$3` = Password

#### 3. New Dependency
Added `jq` package for JSON parsing:
```bash
apt -y install whois genisoimage xorriso isolinux mtools jq
```

### Usage Examples

#### Old Way (ISO Path):
```bash
./build-ubuntu-autoinstall-iso.sh /path/to/ubuntu-22.04.2-live-server-amd64.iso admin ubuntu
```

#### New Way (OS Name):
```bash
# Basic usage
./build-ubuntu-autoinstall-iso.sh ubuntu-22.04.2-live-server-amd64

# With custom credentials
./build-ubuntu-autoinstall-iso.sh ubuntu-22.04.2-live-server-amd64 myuser mypassword

# Different Ubuntu version
./build-ubuntu-autoinstall-iso.sh ubuntu-24.04.1-live-server-amd64 sysadmin SecurePass123
```

### Error Handling

If OS name not found, the script will:
1. Display error message
2. List all available OS names from file_list.json
3. Exit with error code 1

**Example:**
```bash
$ ./build-ubuntu-autoinstall-iso.sh ubuntu-99.99
Error: OS name 'ubuntu-99.99' not found in file_list.json
Available OS names:
ubuntu-20.04.6-live-server-amd64
ubuntu-22.04.2-live-server-amd64
ubuntu-22.04.3-live-server-amd64
ubuntu-24.04.1-live-server-amd64
...
```

### Integration with os_deployment

This change integrates with the main `os_deployment` tool where users specify:
- `-O, --os` parameter with the OS name
- Script automatically looks up the ISO path
- Generates custom autoinstall ISO

### File Structure Required
```
autoinstall/
├── build-ubuntu-autoinstall-iso.sh
├── iso_repository/
│   ├── file_list.json
│   └── Ubuntu/
│       ├── ubuntu-22.04.2-live-server-amd64.iso
│       ├── ubuntu-24.04.1-live-server-amd64.iso
│       └── ...
└── output_custom_iso/
    └── (generated ISOs)
```

### Benefits
1. ✅ Simpler command-line interface
2. ✅ No need to remember full ISO paths
3. ✅ Centralized ISO management via file_list.json
4. ✅ Easier integration with automation tools
5. ✅ Consistent naming across the project
