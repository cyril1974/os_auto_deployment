package main

import (
	"embed"
	"io/fs"
	"os"
	"path/filepath"
)

// embeddedAssets bundles all runtime assets that the ISO builder needs from
// the autoinstall/ directory. They are compiled into the binary at build time
// so the binary is self-contained regardless of where it is invoked from
// (direct execution, Nuitka onefile, CI pipeline, etc.).
//
// Embedded files:
//   - scripts/find_disk.sh       — serial auto-detection script (copied into ISO)
//   - scripts/find_disk_1804.sh  — same for Ubuntu 18.04
//   - startup.nsh                — UEFI startup script (copied into ISO EFI image)
//   - ipmi_start_logger.py       — IPMI SEL logger (copied into ISO pool/extra/)
//   - package_list               — offline package list read at startup

//go:embed scripts startup.nsh ipmi_start_logger.py package_list
var embeddedAssets embed.FS

// extractEmbeddedAssets writes all embedded assets to a temporary directory
// and returns its path. The caller is responsible for removing the directory
// when done (typically via defer os.RemoveAll(dir)).
//
// Directory layout mirrors the autoinstall/ source tree so that all existing
// scriptDir-relative path logic in main.go works unchanged:
//
//	<tmpdir>/
//	├── scripts/
//	│   ├── find_disk.sh
//	│   └── find_disk_1804.sh
//	├── startup.nsh
//	├── ipmi_start_logger.py
//	└── package_list
func extractEmbeddedAssets() (string, error) {
	tmpDir, err := os.MkdirTemp("", "build-iso-assets-*")
	if err != nil {
		return "", err
	}

	err = fs.WalkDir(embeddedAssets, ".", func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		dest := filepath.Join(tmpDir, path)
		if d.IsDir() {
			return os.MkdirAll(dest, 0755)
		}
		data, err := embeddedAssets.ReadFile(path)
		if err != nil {
			return err
		}
		if err := os.WriteFile(dest, data, 0755); err != nil {
			return err
		}
		return nil
	})
	if err != nil {
		os.RemoveAll(tmpDir)
		return "", err
	}
	return tmpDir, nil
}
