#!/bin/bash
# build-cli.sh — Build os-deploy standalone binary using Nuitka
#
# Produces a single self-contained executable at dist/os-deploy-<version>
# The binary includes the Python interpreter and all dependencies.
# Source code is compiled to native machine code — not recoverable.
#
# On Ubuntu 24.04+ (PEP 668), pip install is blocked system-wide.
# This script automatically creates and uses a local virtualenv (.venv/)
# so no system Python packages are modified.
#
# GLIBC COMPATIBILITY
#   By default the binary links against the host system's glibc, so it only
#   runs on systems with glibc >= host version.  Use --docker to build inside
#   an Ubuntu 22.04 container (glibc 2.35), producing a binary that runs on
#   any system with glibc >= 2.35 (Ubuntu 22.04+, Debian 12+, RHEL 9+).
#
# Usage:
#   bash build-cli.sh              # build on host (glibc = host version)
#   bash build-cli.sh --docker     # build in Ubuntu 22.04 container (glibc 2.35)
#   bash build-cli.sh --clean      # remove dist/, build/, .venv/ before building
#   bash build-cli.sh --check      # check prerequisites only, no build

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_ENTRY="${SCRIPT_DIR}/cli_entry.py"
PYPROJECT="${SCRIPT_DIR}/pyproject.toml"
DIST_DIR="${SCRIPT_DIR}/dist"
BUILD_DIR="${SCRIPT_DIR}/build/nuitka"
# VENV_DIR can be overridden by the caller (e.g. Docker sets it to /tmp/.venv-docker
# so the container never touches the host's .venv/ which has wrong interpreter paths).
VENV_DIR="${VENV_DIR:-${SCRIPT_DIR}/.venv}"
BINARY_NAME="os-deploy"

# ─── Helpers ──────────────────────────────────────────────────────────────────

info()  { echo "[*] $*"; }
ok()    { echo "[+] $*"; }
warn()  { echo "[!] $*"; }
die()   { echo "[ERROR] $*" >&2; exit 1; }

# ─── Parse arguments ──────────────────────────────────────────────────────────

DO_CLEAN=false
CHECK_ONLY=false
USE_DOCKER=false
for arg in "$@"; do
    case "$arg" in
        --clean)  DO_CLEAN=true ;;
        --check)  CHECK_ONLY=true ;;
        --docker) USE_DOCKER=true ;;
        *) die "Unknown argument: $arg (valid: --clean, --check, --docker)" ;;
    esac
done

# ─── Docker build path ────────────────────────────────────────────────────────
# When --docker is passed, build the image (if needed) then re-invoke this
# script inside a Ubuntu 22.04 container so the binary links against glibc
# 2.35 and runs on any system with glibc >= 2.35.

if [ "$USE_DOCKER" = "true" ]; then
    command -v docker >/dev/null 2>&1 || die "docker is not installed or not in PATH"

    DOCKER_IMAGE="os-deploy-builder"
    DOCKERFILE="${SCRIPT_DIR}/Dockerfile.build"

    [ -f "${DOCKERFILE}" ] || die "Dockerfile.build not found at ${DOCKERFILE}"

    # Build image only when Dockerfile changed or image doesn't exist
    if ! docker image inspect "${DOCKER_IMAGE}" >/dev/null 2>&1; then
        info "Building Docker image ${DOCKER_IMAGE} (Ubuntu 22.04 / glibc 2.35)..."
        docker build -f "${DOCKERFILE}" -t "${DOCKER_IMAGE}" "${SCRIPT_DIR}"
        ok "Docker image built: ${DOCKER_IMAGE}"
    else
        info "Reusing existing Docker image: ${DOCKER_IMAGE}"
    fi

    info "Running build inside Docker container..."
    # Pass through all original flags except --docker to avoid infinite recursion.
    INNER_ARGS=()
    for arg in "$@"; do
        [ "$arg" != "--docker" ] && INNER_ARGS+=("$arg")
    done

    docker run --rm \
        -v "${SCRIPT_DIR}:/workspace" \
        -w /workspace \
        -e VENV_DIR=/tmp/.venv-docker \
        "${DOCKER_IMAGE}" \
        bash build-cli.sh "${INNER_ARGS[@]}"

    ok "Docker build complete — binary is at dist/"
    exit 0
fi

# ─── System prerequisite check (before venv) ──────────────────────────────────

MISSING_SYS=()
command -v python3  >/dev/null 2>&1 || MISSING_SYS+=("python3")
command -v gcc      >/dev/null 2>&1 || MISSING_SYS+=("gcc")
command -v patchelf >/dev/null 2>&1 || MISSING_SYS+=("patchelf")

if [ ${#MISSING_SYS[@]} -gt 0 ]; then
    die "Missing system packages: ${MISSING_SYS[*]}\n\nFix with:\n  apt install -y ${MISSING_SYS[*]}"
fi

# python3-venv is required to create the virtualenv
python3 -m venv --help >/dev/null 2>&1 || \
    die "python3-venv is not installed.\n\nFix with:\n  apt install -y python3-venv"

ok "System prerequisites satisfied (python3, gcc, patchelf)"

# ─── Clean if requested ────────────────────────────────────────────────────────

if [ "$DO_CLEAN" = "true" ]; then
    info "Cleaning dist/, build/nuitka/, .venv/ ..."
    rm -rf "${DIST_DIR}" "${BUILD_DIR}" "${VENV_DIR}"
    ok "Clean done"
    info "Note: Go binary (autoinstall/build-iso-go/build-iso) is NOT removed by --clean."
    info "      To rebuild it, delete it manually or run autoinstall/build-iso-go/build.sh."
fi

# ─── Create / reuse virtualenv ────────────────────────────────────────────────

if [ ! -f "${VENV_DIR}/bin/python" ]; then
    info "Creating virtualenv at .venv/ ..."
    python3 -m venv "${VENV_DIR}"
    ok "Virtualenv created"
else
    info "Reusing existing virtualenv at .venv/"
fi

PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"

# ─── Install build dependencies into venv ────────────────────────────────────

info "Installing build dependencies into .venv/ ..."
"${PIP}" install --quiet --upgrade pip
"${PIP}" install --quiet -r "${SCRIPT_DIR}/build-requirements.txt"
ok "Build dependencies installed"

# Make os_deployment importable (src/ layout — not installed as a package)
export PYTHONPATH="${SCRIPT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

# ─── Read version from pyproject.toml ─────────────────────────────────────────

VERSION=$("${PYTHON}" -c "
import tomllib, pathlib
data = tomllib.load(open('${PYPROJECT}', 'rb'))
print(data['tool']['poetry']['version'])
" 2>/dev/null) || VERSION=$("${PYTHON}" -c "
import re, pathlib
text = pathlib.Path('${PYPROJECT}').read_text()
m = re.search(r'version\s*=\s*\"([^\"]+)\"', text)
print(m.group(1) if m else 'unknown')
")

OUTPUT_BINARY="${DIST_DIR}/${BINARY_NAME}-${VERSION}"

info "os-deploy build — version ${VERSION}"

# ─── Check-only mode ──────────────────────────────────────────────────────────

if [ "$CHECK_ONLY" = "true" ]; then
    info "Nuitka version: $("${PYTHON}" -m nuitka --version 2>&1 | head -1)"
    info "Check complete (--check mode, no build performed)"
    exit 0
fi

# ─── Build Go ISO builder binary ─────────────────────────────────────────────

GO_BUILD_DIR="${SCRIPT_DIR}/autoinstall/build-iso-go"
GO_BINARY="${GO_BUILD_DIR}/build-iso"

if command -v go >/dev/null 2>&1; then
    info "Building Go ISO builder (autoinstall/build-iso-go/build.sh)..."
    (cd "${GO_BUILD_DIR}" && bash build.sh)
    ok "Go binary built: ${GO_BINARY}"
else
    if [ -f "${GO_BINARY}" ]; then
        warn "go not found — using existing Go binary: ${GO_BINARY}"
    else
        die "'go' is not installed and no pre-built Go binary found at ${GO_BINARY}.\n\nFix with:\n  apt install -y golang  OR  snap install go --classic"
    fi
fi

# ─── Build ────────────────────────────────────────────────────────────────────

mkdir -p "${DIST_DIR}" "${BUILD_DIR}"

# Remove any stale Nuitka intermediate build directories from a previous run.
# These cause an AssertionError if Nuitka tries to write a .c file that already exists.
rm -rf "${DIST_DIR}"/*.build "${DIST_DIR}"/*.dist "${DIST_DIR}"/*.onefile-build

info "Compiling with Nuitka (this takes 2–5 minutes on first build)..."
info "Entry point : ${SRC_ENTRY}"
info "Output      : ${OUTPUT_BINARY}"

"${PYTHON}" -m nuitka \
    --onefile \
    --output-filename="${BINARY_NAME}" \
    --output-dir="${DIST_DIR}" \
    --remove-output \
    \
    --include-package=os_deployment \
    --include-package=requests \
    --include-package=urllib3 \
    --include-package=certifi \
    --include-package=tomli \
    \
    --include-data-files="${SCRIPT_DIR}/src/os_deployment/_version.py=os_deployment/_version.py" \
    --include-data-files="${GO_BINARY}=autoinstall/build-iso-go/build-iso" \
    \
    --nofollow-import-to=tkinter \
    --nofollow-import-to=matplotlib \
    --nofollow-import-to=numpy \
    --nofollow-import-to=scipy \
    --nofollow-import-to=pandas \
    \
    --company-name="MiTAC Computing Technology Corporation" \
    --product-name="os-deploy" \
    --product-version="${VERSION}" \
    --file-description="MiTAC CUP OS Auto-Deployment Tool" \
    \
    --assume-yes-for-downloads \
    --jobs="$(nproc)" \
    \
    "${SRC_ENTRY}"

# ─── Rename to versioned output ────────────────────────────────────────────────

if [ -f "${DIST_DIR}/${BINARY_NAME}" ]; then
    mv "${DIST_DIR}/${BINARY_NAME}" "${OUTPUT_BINARY}"
    chmod +x "${OUTPUT_BINARY}"
    SIZE=$(du -sh "${OUTPUT_BINARY}" | cut -f1)
    ok "Build complete"
    ok "Binary  : ${OUTPUT_BINARY}"
    ok "Size    : ${SIZE}"
    echo ""
    echo "  Run with:"
    echo "    ${OUTPUT_BINARY} --help"
    echo "    ${OUTPUT_BINARY} -B <bmc-ip> -N <nfs-ip> -O <os-name>"
else
    die "Build finished but output binary not found at ${DIST_DIR}/${BINARY_NAME}"
fi
