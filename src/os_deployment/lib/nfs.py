import subprocess
import shutil
import sys
import os
import tempfile
from pathlib import Path

def _ensure_showmount():
    """Make sure `showmount` is available, installing nfs-common if needed."""
    if shutil.which("showmount"):
        return

    print("'showmount' not found; installing nfs-common via apt…")
    try:
        # Update package lists
        subprocess.run(
            ["sudo", "apt-get", "update", "-y"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Install nfs-common non-interactively
        subprocess.run(
            ["sudo", "apt-get", "install", "-y", "nfs-common"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        sys.exit(f"❌ Failed to install nfs-common: {e}")
    
    # Verify installation
    if not shutil.which("showmount"):
        sys.exit("❌ Installation succeeded, but `showmount` still not found.")
    print("✅ `showmount` is now available.")



def get_nfs_exports(nfs_server: str) -> list[str]:
    """
    Returns the list of NFS export paths from a server by parsing `showmount -e`.
    Requires the `showmount` utility (from nfs-common) to be installed.
    """
    _ensure_showmount()

    cmd = ["showmount", "-e", nfs_server]
    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(f"Error running {' '.join(cmd)}:\n{e.output.strip()}")
        return []

    lines = output.splitlines()
    # Skip the header line ("Exports list on <server>:")
    exports = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        # field 0 is the path, rest are clients (we ignore)
        path = line.split()[0]
        exports.append(path)
    return exports

def drop_file_to_nfs(server: str, export_path: str, local_file: Path) -> str:
    """
    Mounts the NFS export `server:export_path`, copies `local_file` into
    the root of that export, then unmounts.
    """
    # 1. Validate local file
    if not local_file.is_file():
        sys.exit(f"Error: local file '{local_file}' does not exist")

    # 2. Construct mount source
    mount_src = f"{server}:{export_path}"

    # 3. Create a temporary mount point
    with tempfile.TemporaryDirectory(prefix="nfs_mount_") as mpoint_str:
        mpoint = Path(mpoint_str)
        # print(f"Mounting {mount_src} → {mpoint}")
        try:
            subprocess.run(
                ["mount", "-t", "nfs", mount_src, str(mpoint)],
                check=True
            )
        except subprocess.CalledProcessError as e:
            sys.exit(f"Error mounting NFS share: {e}")

        # 4. Copy the file
        dest = mpoint / local_file.name
        # print(f"Copying '{local_file}' → '{dest}'")
        try:
            shutil.copy2(local_file, dest)
        except Exception as e:
            # subprocess.run(["umount", str(mpoint)], check=False)
            sys.exit(f"Error copying file: {e}")

        # 5. Unmount
        # print(f"Unmounting {mpoint}")
        try:
            subprocess.run(["umount", str(mpoint)], check=True)
        except subprocess.CalledProcessError as e:
            sys.exit(f"Error unmounting NFS share: {e}")

    # print(f"File {local_file} dropped to NFS Server {server} successfully.")
    return f"nfs://{server}:{export_path}/{local_file.name}"