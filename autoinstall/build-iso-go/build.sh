#!/bin/bash
# build.sh — Build the build-iso Go binary.
#
# Assets from the parent autoinstall/ directory (ipmi_start_logger.py,
# package_list) are copied here before build so Go's //go:embed directive can
# include them, then removed afterwards.
# The scripts/ directory (startup.nsh, startup_mi325xr.nsh, find_disk*.sh,
# IpmiTool.efi, ipmicmdtoolX64.efi) is copied wholesale from the parent dir.
# The mi325xr/ directory is likewise copied for Mi325x platform support.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "${SCRIPT_DIR}")"

# ─── Stage assets for go:embed ────────────────────────────────────────────────

STAGED=()

# Copy individual asset files
for asset in ipmi_start_logger.py package_list; do
    src="${PARENT_DIR}/${asset}"
    dst="${SCRIPT_DIR}/${asset}"
    if [ -f "${src}" ] && [ ! -e "${dst}" ]; then
        cp "${src}" "${dst}"
        STAGED+=("${dst}")
    fi
done

# Copy scripts/ directory (go:embed does not follow symlinks to external paths)
if [ -d "${PARENT_DIR}/scripts" ] && [ ! -e "${SCRIPT_DIR}/scripts" ]; then
    cp -r "${PARENT_DIR}/scripts" "${SCRIPT_DIR}/scripts"
    STAGED+=("${SCRIPT_DIR}/scripts")
fi

# Copy mi325xr/ directory (platform-specific files for MiTAC Mi325x nodes)
if [ -d "${PARENT_DIR}/mi325xr" ] && [ ! -e "${SCRIPT_DIR}/mi325xr" ]; then
    cp -r "${PARENT_DIR}/mi325xr" "${SCRIPT_DIR}/mi325xr"
    STAGED+=("${SCRIPT_DIR}/mi325xr")
fi

cleanup() {
    for f in "${STAGED[@]}"; do
        rm -rf "${f}"
    done
}
trap cleanup EXIT

# ─── Test and build ───────────────────────────────────────────────────────────

echo "[*] Running pre-build tests..."
go test ./... -v || { echo "[!] Tests failed — aborting build"; exit 1; }
echo "[+] Tests passed"

echo "[*] Building binary..."
go build -o build-iso .
echo "[+] Build complete: build-iso"
