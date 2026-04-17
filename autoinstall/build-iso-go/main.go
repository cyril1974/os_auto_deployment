package main

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"text/template"
	"time"

	"github.com/GehirnInc/crypt"
	_ "github.com/GehirnInc/crypt/sha512_crypt"
)

// ─── Constants ───────────────────────────────────────────────────────────────

const efiGUID = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"

// ─── Data structures ─────────────────────────────────────────────────────────

// FileList mirrors the structure of iso_repository/file_list.json
type FileList struct {
	Tree struct {
		Ubuntu []struct {
			OSName string `json:"OS_Name"`
			OSPath string `json:"OS_Path"`
		} `json:"Ubuntu"`
	} `json:"tree"`
}

// BuildConfig holds all parameters for one ISO build run
type BuildConfig struct {
	OSName          string
	Username        string
	Password        string
	HashPassword    string
	PubKey          string
	KeyName         string
	Is1804          bool
	Codename        string
	OrigISO         string
	WorkDir         string
	OutISODir       string
	OutISO          string
	BuildID         string
	ScriptDir       string
	OfflinePackages string
	Timestamp       string
	// Storage match: serial or model provided by user.
	// When set, disk=>match uses this key/value and find_disk.sh is disabled.
	StorageMatchKey   string // "serial" or "model"
	StorageMatchValue string // the value provided by the user
	// FindDiskSizeHint: when --storage-size=<val> is provided, find_disk.sh is
	// called with --target-size=<val> to locate the disk by size and resolve its serial.
	// StorageMatchKey remains "serial" and StorageMatchValue "__ID_SERIAL__" in this mode.
	FindDiskSizeHint string
	// CacheDir is the persistent apt package cache directory, stored under the
	// XDG cache home (~/.cache/build-iso/apt_cache/) so it survives binary runs
	// and is not destroyed when the embedded-assets temp dir is cleaned up.
	CacheDir string
	// Hostname is the system hostname written into user-data / preseed.
	// Defaults to "ubuntu-auto" when not specified.
	Hostname string
	// Mi325xSupport adds GRUB kernel parameters (amd_iommu=on iommu=pt pci=realloc=off)
	// and GRUB_RECORDFAIL_TIMEOUT=0 required for MiTAC Mi325x platform stability.
	Mi325xSupport bool
	// Mi325xNode identifies the target node (e.g. node_1, node_2).
	// Required when Mi325xSupport is true. Format: node_<integer>.
	Mi325xNode string
}

// ─── Help ─────────────────────────────────────────────────────────────────────

func showHelp() {
	fmt.Print(`Ubuntu Autoinstall ISO Builder (Go version)
============================================

USAGE:
    build-iso <OS_NAME> [USERNAME] [PASSWORD] [OPTIONS]

PARAMETERS:
    OS_NAME     OS name to look up in file_list.json (required)
                Example: ubuntu-22.04.2-live-server-amd64
    USERNAME    Username for the installed system (default: mitac)
    PASSWORD    Password for both user and root  (default: ubuntu)

OPTIONS:
    --skip-install              Skip checking/installing host tool dependencies

    --iso-repo-dir=<path>       Path to the ISO repository directory containing file_list.json
                                and the ISO files. Overrides the default location:
                                <script-dir>/iso_repository/
                                e.g. --iso-repo-dir=/data/iso_repo

    --storage-serial=<value>    Match target disk by serial number (embedded directly in user-data)
                                e.g. --storage-serial=S6CKNT0W700868
    --storage-model=<value>     Match target disk by model name (embedded directly in user-data)
                                e.g. --storage-model=SAMSUNG_MZQL27T6HBLA

    --hostname=<value>          Hostname for the installed system (default: ubuntu-auto)
                                e.g. --hostname=node01

    --mi325x-support            Apply MiTAC Mi325x platform GRUB adjustments in late-commands:
                                  - amd_iommu=on iommu=pt pci=realloc=off kernel parameters
                                  - GRUB_RECORDFAIL_TIMEOUT=0
                                  - update-grub
                                  Requires --mi325x-node.

    --mi325x-node=<value>       Target node identifier. Required when --mi325x-support is set.
                                Format: node_<integer>  e.g. node_1  node_2  node_10

    --storage-size=<value>      Find disk by size at boot via find_disk.sh, then match by serial.
                                find_disk.sh is called with --target-size=<value> (±10% tolerance).
                                user-data uses serial: __ID_SERIAL__ — patched at boot with the
                                resolved serial of the size-matching disk.
                                e.g. --storage-size=7T   --storage-size=960G

    NOTE: Only ONE of --storage-serial / --storage-model / --storage-size may be
    used. If more than one is provided, the first one found in argument order is
    used and the others are ignored with a warning.

    --storage-serial / --storage-model:
      - disk=>match set to the given key/value directly in user-data.
      - find_disk.sh is DISABLED (not copied to ISO).

    --storage-size:
      - disk=>match uses serial: __ID_SERIAL__ (same as auto-detect mode).
      - find_disk.sh IS copied and runs at boot with --target-size=<value>.
      - Disk whose size is within ±10% of <value> is selected; its serial patches __ID_SERIAL__.

    When NO storage option is set (default):
      - disk=>match uses serial: __ID_SERIAL__ as a placeholder.
      - find_disk.sh runs at boot and selects the smallest empty disk.

DESCRIPTION:
    Creates a custom Ubuntu autoinstall ISO that will automatically
    install Ubuntu Server with the specified credentials.

    Output ISO: ./output_custom_iso/<BUILD_ID>/<name>_autoinstall_<ts>.iso

FEATURES:
    - GPT partition table for UEFI boot compatibility
    - Fully unattended installation
    - SSH server enabled with password auth + auto-generated key
    - Root login enabled
    - IPMI SEL telemetry during install
    - Offline package bundling via package_list file
    - Ubuntu 18.04 preseed support

REQUIREMENTS:
    - Root privileges
    - Packages: whois, genisoimage, xorriso, isolinux, mtools, jq
    - iso_repository/file_list.json

`)
	os.Exit(0)
}

// ─── Utilities ────────────────────────────────────────────────────────────────

func logf(format string, args ...any) {
	fmt.Printf("[*] "+format+"\n", args...)
}

func warnf(format string, args ...any) {
	fmt.Printf("[!] "+format+"\n", args...)
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "[ERROR] "+format+"\n", args...)
	os.Exit(1)
}

// run executes a command, streaming its output, and fatal-exits on error.
func run(name string, args ...string) {
	cmd := exec.Command(name, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		fatalf("command failed: %s %s: %v", name, strings.Join(args, " "), err)
	}
}

// runSilent runs a command discarding output. Returns error without exiting.
func runSilent(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	return cmd.Run()
}

// outputOf runs a command and returns its trimmed stdout.
func outputOf(name string, args ...string) (string, error) {
	out, err := exec.Command(name, args...).Output()
	return strings.TrimSpace(string(out)), err
}

// fileExists returns true if the path exists and is a regular file.
func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

// dirExists returns true if the path exists and is a directory.
func dirExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}

// copyFile copies src to dst preserving permissions.
func copyFile(src, dst string) error {
	data, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	info, err := os.Stat(src)
	if err != nil {
		return err
	}
	return os.WriteFile(dst, data, info.Mode())
}

// ─── Package check ────────────────────────────────────────────────────────────

func checkAndInstallPackages(skip bool) {
	if skip {
		logf("Skipping package installation (--skip-install flag set)")
		return
	}
	if os.Geteuid() != 0 {
		logf("Skipping package installation (not running as root)")
		logf("Required packages: whois, genisoimage, xorriso, isolinux, mtools, jq")
		return
	}

	required := []string{"whois", "genisoimage", "xorriso", "isolinux", "mtools", "jq"}
	var missing []string
	for _, pkg := range required {
		if runSilent("command", "-v", pkg) != nil {
			if runSilent("dpkg", "-l", pkg) != nil {
				missing = append(missing, pkg)
			}
		}
	}

	if len(missing) == 0 {
		logf("All required packages are already installed")
		return
	}

	logf("Installing missing packages: %s", strings.Join(missing, " "))
	logf("Running apt update (ignoring repository errors)...")
	_ = runSilent("apt", "update")
	logf("Installing packages...")
	args := append([]string{"-y", "install"}, missing...)
	if err := runSilent("apt", args...); err != nil {
		warnf("apt install had errors, but continuing...")
	}
}

// ─── ISO path lookup ─────────────────────────────────────────────────────────

// lookupISOPath finds the ISO file for osName using file_list.json.
// isoRepoDir is the directory that contains both file_list.json and the ISO files.
// When empty, it defaults to <scriptDir>/iso_repository/.
func lookupISOPath(osName, scriptDir, isoRepoDir string) string {
	if isoRepoDir == "" {
		isoRepoDir = filepath.Join(scriptDir, "iso_repository")
	}

	jsonFile := filepath.Join(isoRepoDir, "file_list.json")
	data, err := os.ReadFile(jsonFile)
	if err != nil {
		fatalf("file_list.json not found at %s", jsonFile)
	}

	var fl FileList
	if err := json.Unmarshal(data, &fl); err != nil {
		fatalf("failed to parse file_list.json: %v", err)
	}

	for _, entry := range fl.Tree.Ubuntu {
		if entry.OSName == osName {
			return filepath.Join(isoRepoDir, entry.OSPath)
		}
	}

	fmt.Fprintf(os.Stderr, "Error: OS name '%s' not found in file_list.json\nAvailable:\n", osName)
	for _, entry := range fl.Tree.Ubuntu {
		fmt.Fprintf(os.Stderr, "  %s\n", entry.OSName)
	}
	os.Exit(1)
	return ""
}

// ─── Offline packages ────────────────────────────────────────────────────────

func readOfflinePackages(scriptDir string) string {
	pkgFile := filepath.Join(scriptDir, "package_list")
	if !fileExists(pkgFile) {
		return ""
	}

	logf("Found package_list file. Reading packages for offline installation...")
	data, err := os.ReadFile(pkgFile)
	if err != nil {
		return ""
	}

	var pkgs []string
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		pkgs = append(pkgs, line)
	}

	// Ensure ipmitool is always present
	hasipmitool := false
	for _, p := range pkgs {
		if p == "ipmitool" {
			hasipmitool = true
			break
		}
	}
	if !hasipmitool {
		pkgs = append(pkgs, "ipmitool")
	}

	result := strings.Join(pkgs, " ")
	logf("Offline packages: %s", result)
	return result
}

// ─── Codename detection ──────────────────────────────────────────────────────

func getUbuntuCodename(workDir, osName string) string {
	// Method 1: .disk/info
	diskInfo := filepath.Join(workDir, ".disk/info")
	if fileExists(diskInfo) {
		data, _ := os.ReadFile(diskInfo)
		re := regexp.MustCompile(`"([^"]+)"`)
		m := re.FindStringSubmatch(string(data))
		if len(m) > 1 {
			parts := strings.Fields(m[1])
			if len(parts) > 0 {
				codename := strings.ToLower(parts[0])
				logf("Detected codename from .disk/info: %s", codename)
				return codename
			}
		}
	}

	// Method 2: /dists directory
	distsDir := filepath.Join(workDir, "dists")
	if dirExists(distsDir) {
		entries, _ := os.ReadDir(distsDir)
		var dirs []string
		for _, e := range entries {
			if e.IsDir() {
				dirs = append(dirs, e.Name())
			}
		}
		if len(dirs) == 1 {
			logf("Detected codename from /dists directory: %s", dirs[0])
			return dirs[0]
		}
	}

	// Method 3: version-based fallback
	logf("Using fallback version-based codename detection from OS_NAME")
	versionMap := []struct{ ver, name string }{
		{"25.10", "questing"},
		{"25.04", "plucky"},
		{"24.10", "oracular"},
		{"24.04", "noble"},
		{"23.10", "mantic"},
		{"23.04", "lunar"},
		{"22.10", "kinetic"},
		{"22.04", "jammy"},
		{"20.04", "focal"},
		{"18.04", "bionic"},
	}
	for _, v := range versionMap {
		if strings.Contains(osName, v.ver) {
			return v.name
		}
	}

	warnf("Could not determine Ubuntu version, defaulting to jammy")
	return "jammy"
}

// ─── Mi325x platform files ───────────────────────────────────────────────────

// copyMi325xrFiles copies platform-specific files into pool/mi325xr/ inside the ISO.
// It merges two source directories:
//   - <scriptDir>/mi325xr/common/   — files shared by all Mi325x nodes
//   - <scriptDir>/mi325xr/<node>/   — files specific to the target node (optional)
func copyMi325xrFiles(cfg *BuildConfig) {
	destDir := filepath.Join(cfg.WorkDir, "pool/mi325xr")
	if err := os.MkdirAll(destDir, 0755); err != nil {
		fatalf("failed to create pool/mi325xr dir: %v", err)
	}

	sources := []string{
		filepath.Join(cfg.ScriptDir, "mi325xr", "common"),
		filepath.Join(cfg.ScriptDir, "mi325xr", cfg.Mi325xNode),
	}

	for _, src := range sources {
		if !dirExists(src) {
			warnf("mi325xr source directory not found, skipping: %s", src)
			continue
		}
		entries, err := os.ReadDir(src)
		if err != nil {
			warnf("failed to read mi325xr source directory %s: %v", src, err)
			continue
		}
		for _, e := range entries {
			if e.IsDir() {
				continue
			}
			srcFile := filepath.Join(src, e.Name())
			dstFile := filepath.Join(destDir, e.Name())
			if err := copyFile(srcFile, dstFile); err != nil {
				fatalf("failed to copy mi325xr file %s: %v", srcFile, err)
			}
			logf("Mi325x: bundled %s → pool/mi325xr/%s", srcFile, e.Name())
		}
	}
}

// ─── Download extra packages ─────────────────────────────────────────────────

func downloadExtraPackages(cfg *BuildConfig) {
	extraPool := filepath.Join(cfg.WorkDir, "pool/extra")
	if err := os.MkdirAll(extraPool, 0755); err != nil {
		fatalf("failed to create extra pool dir: %v", err)
	}

	logf("Downloading packages for Ubuntu %s...", cfg.Codename)
	logf("Package cache: %s", filepath.Join(cfg.CacheDir, cfg.Codename))

	tmpDir, _ := os.MkdirTemp("", "apt-download-*")
	aptConfDir, _ := os.MkdirTemp("", "apt-conf-*")
	defer os.RemoveAll(tmpDir)
	defer os.RemoveAll(aptConfDir)

	// Use the XDG-based cache dir so packages persist across runs.
	// cfg.CacheDir is ~/.cache/build-iso/apt_cache/ (or $XDG_CACHE_HOME equivalent).
	persistentCache, _ := filepath.Abs(filepath.Join(cfg.CacheDir, cfg.Codename))
	_ = os.MkdirAll(filepath.Join(persistentCache, "archives/partial"), 0755)

	aptState := filepath.Join(aptConfDir, "state")
	aptEtc := filepath.Join(aptConfDir, "etc")
	_ = os.MkdirAll(filepath.Join(aptState, "lists/partial"), 0755)
	_ = os.MkdirAll(filepath.Join(aptEtc, "apt.conf.d"), 0755)
	_ = os.MkdirAll(filepath.Join(aptEtc, "preferences.d"), 0755)
	_ = os.MkdirAll(filepath.Join(aptEtc, "trusted.gpg.d"), 0755)
	// Empty dpkg status (critical: isolates from host)
	_ = os.WriteFile(filepath.Join(aptState, "status"), []byte{}, 0644)

	// Copy GPG keys from host
	if dirExists("/etc/apt/trusted.gpg.d") {
		entries, _ := os.ReadDir("/etc/apt/trusted.gpg.d")
		for _, e := range entries {
			if strings.HasSuffix(e.Name(), ".gpg") {
				_ = copyFile(
					filepath.Join("/etc/apt/trusted.gpg.d", e.Name()),
					filepath.Join(aptEtc, "trusted.gpg.d", e.Name()),
				)
			}
		}
	}
	if fileExists("/etc/apt/trusted.gpg") {
		_ = copyFile("/etc/apt/trusted.gpg", filepath.Join(aptEtc, "trusted.gpg"))
	}

	aptSources := filepath.Join(aptConfDir, "sources.list")
	sourceContent := fmt.Sprintf(
		"deb [trusted=yes] http://archive.ubuntu.com/ubuntu %s main universe\n"+
			"deb [trusted=yes] http://archive.ubuntu.com/ubuntu %s-updates main universe\n",
		cfg.Codename, cfg.Codename,
	)

	pkgsToDownload := cfg.OfflinePackages
	if pkgsToDownload == "" {
		pkgsToDownload = "ipmitool grub-efi-amd64-signed shim-signed efibootmgr"
	}

	autoinstallDir := filepath.Join(cfg.WorkDir, "autoinstall")
	_ = os.MkdirAll(autoinstallDir, 0755)

	// Docker repository
	if strings.Contains(pkgsToDownload, "docker") {
		logf("Adding Docker repository for bundling...")
		sourceContent += fmt.Sprintf(
			"deb [arch=amd64 trusted=yes] https://download.docker.com/linux/ubuntu %s stable\n",
			cfg.Codename,
		)
		pkgsToDownload = strings.ReplaceAll(pkgsToDownload, "docker",
			"docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin")
		logf("Bundling Docker GPG key into ISO...")
		runSilent("curl", "-fsSL", "https://download.docker.com/linux/ubuntu/gpg",
			"-o", filepath.Join(autoinstallDir, "docker.asc"))
	}

	// Kubernetes repository
	if strings.Contains(pkgsToDownload, "kube") {
		logf("Adding Kubernetes repository for bundling...")
		logf("Bundling Kubernetes GPG key into ISO...")
		kubeGPG := filepath.Join(autoinstallDir, "kubernetes.gpg")
		runSilent("bash", "-c",
			fmt.Sprintf("curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.35/deb/Release.key | gpg --dearmor -o %s", kubeGPG))
		_ = copyFile(kubeGPG, filepath.Join(aptEtc, "trusted.gpg.d", "kubernetes.gpg"))
		sourceContent += "deb [arch=amd64 trusted=yes] https://pkgs.k8s.io/core:/stable:/v1.35/deb/ /\n"
	}

	_ = os.WriteFile(aptSources, []byte(sourceContent), 0644)

	aptOpts := []string{
		"-o", "Dir::Etc::sourcelist=" + aptSources,
		"-o", "Dir::Etc::sourceparts=/dev/null",
		"-o", "Dir::Cache=" + persistentCache,
		"-o", "Dir::State=" + aptState,
		"-o", "Dir::State::status=" + filepath.Join(aptState, "status"),
		"-o", "Dir::Etc=" + aptEtc,
		"-o", "Acquire::AllowInsecureRepositories=true",
		"-o", "Acquire::AllowDowngradeToInsecureRepositories=true",
	}

	logf("Fetching package index for %s...", cfg.Codename)
	updateArgs := append(append([]string{}, aptOpts...), "update")
	if err := runSilent("apt-get", updateArgs...); err != nil {
		warnf("Failed to fetch package index for %s", cfg.Codename)
		return
	}

	logf("Resolving package dependency closure for %s...", cfg.Codename)

	// Determine full dependency closure
	simArgs := append(append([]string{}, aptOpts...),
		"-s", "install", "--reinstall")
	simArgs = append(simArgs, strings.Fields(pkgsToDownload)...)
	simOutput, _ := exec.Command("apt-get", simArgs...).Output()

	var allNeeded []string
	seen := map[string]bool{}
	for _, line := range strings.Split(string(simOutput), "\n") {
		if strings.HasPrefix(line, "Inst ") {
			parts := strings.Fields(line)
			if len(parts) >= 2 && !seen[parts[1]] {
				seen[parts[1]] = true
				allNeeded = append(allNeeded, parts[1])
			}
		}
	}

	// Filter out base packages already on the ISO
	basePackages := map[string]bool{
		"libc6": true, "debconf": true, "dpkg": true, "bash": true,
		"coreutils": true, "install-info": true, "base-files": true,
		"netbase": true, "login": true, "passwd": true, "mount": true,
		"util-linux": true,
	}
	var filtered []string
	for _, pkg := range allNeeded {
		skip := false
		for base := range basePackages {
			if pkg == base || strings.HasPrefix(pkg, "libgcc") ||
				strings.HasPrefix(pkg, "libstdc++") ||
				strings.HasPrefix(pkg, "libpam") ||
				strings.HasPrefix(pkg, "libnss") ||
				strings.HasPrefix(pkg, "libdbus") ||
				strings.HasPrefix(pkg, "libsystemd") ||
				strings.HasPrefix(pkg, "systemd") ||
				strings.HasPrefix(pkg, "libudev") ||
				strings.HasPrefix(pkg, "udev") ||
				strings.HasPrefix(pkg, "libk5") ||
				strings.HasPrefix(pkg, "libssl") ||
				strings.HasPrefix(pkg, "libcrypt") ||
				strings.HasPrefix(pkg, "libzstd") ||
				strings.HasPrefix(pkg, "libuuid") ||
				strings.HasPrefix(pkg, "libblkid") ||
				strings.HasPrefix(pkg, "libmount") ||
				strings.HasPrefix(pkg, "libselinux") {
				skip = true
				break
			}
			if pkg == base {
				skip = true
				break
			}
		}
		if !skip {
			filtered = append(filtered, pkg)
		}
	}

	logf("Downloading %d package(s) for %s...", len(filtered), cfg.Codename)
	total := len(filtered)
	for i, pkg := range filtered {
		// Check persistent cache first
		glob := filepath.Join(persistentCache, "archives", pkg+"_*.deb")
		matches, _ := filepath.Glob(glob)
		if len(matches) > 0 {
			printProgress(i+1, total, pkg+" [cached]")
			continue
		}
		printProgress(i+1, total, pkg+" [downloading]")

		dlArgs := append(append([]string{}, aptOpts...),
			"-t", cfg.Codename, "download", pkg)
		cmd := exec.Command("apt-get", dlArgs...)
		cmd.Dir = tmpDir
		_ = cmd.Run()

		// Move downloaded .deb to persistent cache.
		// os.Rename fails across filesystem boundaries (e.g. /tmp on tmpfs →
		// ~/.cache on ext4) with EXDEV. Use copy+remove so it always works.
		debs, _ := filepath.Glob(filepath.Join(tmpDir, "*.deb"))
		for _, deb := range debs {
			dest := filepath.Join(persistentCache, "archives", filepath.Base(deb))
			if err := copyFile(deb, dest); err == nil {
				_ = os.Remove(deb)
			}
		}
	}

	// Copy from cache to ISO extra pool
	copied := 0
	for _, pkg := range allNeeded {
		glob := filepath.Join(persistentCache, "archives", pkg+"_*.deb")
		matches, _ := filepath.Glob(glob)
		for _, m := range matches {
			_ = copyFile(m, filepath.Join(extraPool, filepath.Base(m)))
			copied++
		}
	}
	if copied > 0 {
		logf("Bundled %d package(s) into ISO (%s/)", copied, extraPool)
	}

	// Bundle IPMI logger script
	loggerSrc := filepath.Join(cfg.ScriptDir, "ipmi_start_logger.py")
	if fileExists(loggerSrc) {
		dst := filepath.Join(extraPool, "ipmi_start_logger.py")
		_ = copyFile(loggerSrc, dst)
		_ = os.Chmod(dst, 0755)
	}
}

func printProgress(cur, total int, label string) {
	pct := float64(cur) * 100.0 / float64(total)
	filled := int(pct * 40 / 100)
	bar := strings.Repeat("█", filled) + strings.Repeat("-", 40-filled)
	if cur > 1 {
		fmt.Printf("\033[1A\033[2K")
	}
	fmt.Printf("Progress: |%s| %5.1f%% Complete\n", bar, pct)
}

// ─── SSH key generation ──────────────────────────────────────────────────────

func generateSSHKey(cfg *BuildConfig) {
	homeDir, _ := os.UserHomeDir()
	sshDir := filepath.Join(homeDir, ".ssh")
	_ = os.MkdirAll(sshDir, 0700)

	ts := time.Now().Format("20060102_150405")
	randSuffix := fmt.Sprintf("%d", rand.Intn(9999))
	cfg.KeyName = fmt.Sprintf("id_ed25519_%s_%s", ts, randSuffix)
	keyPath := filepath.Join(sshDir, cfg.KeyName)

	run("ssh-keygen", "-t", "ed25519", "-f", keyPath,
		"-C", "admin@ubuntu-autoinstall", "-N", "")

	pubKeyBytes, err := os.ReadFile(keyPath + ".pub")
	if err != nil {
		fatalf("failed to read public key: %v", err)
	}
	cfg.PubKey = strings.TrimSpace(string(pubKeyBytes))
}

// ─── GRUB config patching ────────────────────────────────────────────────────

func patchGrubConfig(cfg *BuildConfig, bootParams string) {
	grubCfg := filepath.Join(cfg.WorkDir, "boot/grub/grub.cfg")
	if !fileExists(grubCfg) {
		fatalf("grub.cfg not found at %s", grubCfg)
	}

	// Backup
	_ = copyFile(grubCfg, grubCfg+".orig")

	data, _ := os.ReadFile(grubCfg)
	txt := string(data)

	// Force timeout=5
	reTimeout := regexp.MustCompile(`(?m)^set timeout=.*`)
	txt = reTimeout.ReplaceAllString(txt, "set timeout=5")
	if !strings.Contains(txt, "set default=") {
		txt += "\nset default=\"0\"\n"
	}

	// Escape semicolons for GRUB
	grubParams := strings.ReplaceAll(bootParams, ";", "\\;")

	var newEntry string
	if cfg.Is1804 {
		newEntry = fmt.Sprintf(`menuentry "Auto Install Ubuntu Server" {
    set gfxpayload=keep
    linux   /install/vmlinuz %s
    initrd  /install/initrd.gz
}`, grubParams)
		re := regexp.MustCompile(`(?mis)(menuentry\s+['"](?:Try or Install |Install )?Ubuntu Server['"]\s+\{[^}]+linux\s+/install/(?:hwe-)?vmlinuz)([^\n]*)(\n\s*initrd\s+/install/(?:hwe-)?initrd\.gz[^\n]*\n\s*\})`)
		replaced := re.ReplaceAllString(txt, newEntry)
		if replaced == txt {
			warnf("Did not find expected 18.04 menuentry; grub.cfg not modified.")
		} else {
			txt = replaced
			logf("Patched grub.cfg (18.04 legacy)")
		}
	} else {
		newEntry = fmt.Sprintf(`menuentry "Auto Install Ubuntu Server" {
    set gfxpayload=keep
    search --no-floppy --set=root --file /casper/vmlinuz
    linux   /casper/vmlinuz %s
    initrd  /casper/initrd
}`, grubParams)
		re := regexp.MustCompile(`(?mis)(menuentry\s+['"](?:Try or Install |Install )?Ubuntu Server['"]\s+\{[^}]+linux\s+/casper/(?:hwe-)?vmlinuz)([^\n]*)(\n\s*initrd\s+/casper/(?:hwe-)?initrd[^\n]*\n\s*\})`)
		replaced := re.ReplaceAllString(txt, newEntry)
		if replaced == txt {
			// Generic fallback
			re2 := regexp.MustCompile(`(?mis)(menuentry\s+['"][^"]*Ubuntu[^"]*['"]\s+\{[^}]+linux\s+/(?:casper|install)/[^\s]+)([^\n]*)(\n\s*initrd\s+/(?:casper|install)/[^\n]+[^\n]*\n\s*\})`)
			replaced = re2.ReplaceAllString(txt, newEntry)
		}
		if replaced == txt {
			warnf("Did not find expected menuentry; grub.cfg not modified.")
		} else {
			txt = replaced
			logf("Patched grub.cfg (20.04+)")
		}
	}

	// Remove standalone grub_platform commands
	rePlatform := regexp.MustCompile(`(?m)^\s*grub_platform\s*$`)
	txt = rePlatform.ReplaceAllString(txt, "")

	_ = os.WriteFile(grubCfg, []byte(txt), 0644)
}

// ─── ISOLINUX config patching ────────────────────────────────────────────────

func patchISOLinuxConfig(cfg *BuildConfig, bootParams string) {
	cfgFiles := []string{
		filepath.Join(cfg.WorkDir, "isolinux/txt.cfg"),
		filepath.Join(cfg.WorkDir, "isolinux/adtxt.cfg"),
	}

	for _, cfgFile := range cfgFiles {
		if !fileExists(cfgFile) {
			continue
		}
		logf("Patching ISOLINUX configuration in %s...", cfgFile)
		data, _ := os.ReadFile(cfgFile)
		txt := string(data)

		var re *regexp.Regexp
		if cfg.Is1804 {
			re = regexp.MustCompile(`(?is)(label\s+install\s+.*?kernel\s+/install/vmlinuz\s+append\s+)(.*?)(\s+---)`)
		} else {
			re = regexp.MustCompile(`(?is)(label\s+live\s+.*?kernel\s+/casper/vmlinuz\s+append\s+)(.*?)(\s+---)`)
		}

		replaced := re.ReplaceAllString(txt, "${1}"+bootParams+" ${3}")
		if replaced == txt {
			// Generic fallback
			re2 := regexp.MustCompile(`(?i)(append\s+)(.*?)(\s+---)`)
			replaced = re2.ReplaceAllString(txt, "${1}"+bootParams+" ${2} ${3}")
		}
		_ = os.WriteFile(cfgFile, []byte(replaced), 0644)
	}

	// Set ISOLINUX timeout
	isoLinuxCfg := filepath.Join(cfg.WorkDir, "isolinux/isolinux.cfg")
	if fileExists(isoLinuxCfg) {
		logf("Disabling interactive boot menu timeout for ISOLINUX...")
		data, _ := os.ReadFile(isoLinuxCfg)
		txt := string(data)
		txt = regexp.MustCompile(`(?m)^timeout.*`).ReplaceAllString(txt, "timeout 10")
		txt = regexp.MustCompile(`(?m)^prompt.*`).ReplaceAllString(txt, "prompt 0")
		_ = os.WriteFile(isoLinuxCfg, []byte(txt), 0644)
	}
}

// ─── User-data template ──────────────────────────────────────────────────────

const userDataTmpl = `#cloud-config
autoinstall:
  version: 1
  identity:
    hostname: {{.Hostname}}
    username: {{.Username}}
    password: "{{.HashPassword}}"
  locale: en_US.UTF-8
  keyboard:
    layout: us
  storage:
    config:
      - type: disk
        id: disk-main
        match:
          {{.StorageMatchKey}}: "{{.StorageMatchValue}}"
        ptable: gpt
        wipe: superblock-recursive
        preserve: false
		grub_device: true

      - type: partition
        id: partition-efi
        device: disk-main
        size: 512M
        flag: boot
        partition_type: {{.EFIGUID}}
        grub_device: true
        number: 1
        preserve: false

      - type: format
        id: format-efi
        volume: partition-efi
        fstype: vfat
        preserve: false

      - type: mount
        id: mount-efi
        device: format-efi
        path: /boot/efi		
      
	  # SWAP Partition
      - id: swap_partition
        type: partition
        size: 8GB
        device: disk-main
        flag: swap

      - id: swap_format
        type: format
        fstype: swap
        volume: swap_partition

      - id: swap_mount
        path: none
        type: mount
        device: swap_format

	   # Root Partition (BTRFS)
      - id: root_partition
        type: partition
        size: -1
        device: disk-main

      - id: root_format
        type: format
        fstype: btrfs
        volume: root_partition

      - id: root_mount
        type: mount
        path: /
        device: root_format
	
  ssh:
    install-server: true
    authorized-keys:
      - {{.PubKey}}
    allow-pw: true
  updates: security
  refresh-installer:
    update: no
  apt:
    fallback: offline-install
    geoip: false
    preserve_sources_list: false
    primary:
      - arches: [default]
        uri: http://archive.ubuntu.com/ubuntu
  early-commands:
    - systemctl stop multipathd 2>/dev/null || true
    - systemctl mask multipathd 2>/dev/null || true
    - modprobe ipmi_devintf 2>/dev/null || true
    - modprobe ipmi_si 2>/dev/null || true
    - modprobe ipmi_msghandler 2>/dev/null || true
    - sleep 2
    - python3 /cdrom/pool/extra/ipmi_start_logger.py 0x0F || true
{{- if .FindDiskEnabled}}
    - |
      if [ -f /cdrom/autoinstall/scripts/find_disk.sh ]; then
          sh /cdrom/autoinstall/scripts/find_disk.sh{{if .FindDiskSizeHint}} --target-size={{.FindDiskSizeHint}}{{end}}
      else
          echo "[!] WARNING: find_disk.sh not found. Proceeding with default config." > /dev/console
      fi
{{- end}}
    - dpkg -i /cdrom/pool/extra/*.deb 2>/dev/null || true
    - python3 /cdrom/pool/extra/ipmi_start_logger.py 0x1F || true
    - sleep 2
    - python3 /cdrom/pool/extra/ipmi_start_logger.py 0x01 || true
  error-commands:
    - modprobe ipmi_devintf 2>/dev/null || true
    - modprobe ipmi_si 2>/dev/null || true
    - sleep 1
    - |
      IP=$(hostname -I | awk '{print $1}')
      if [ -n "$IP" ]; then
          eval $(echo "$IP" | awk -F. '{printf "o1=%s; o2=%s; o3=%s; o4=%s", $1, $2, $3, $4}')
          h1=$(printf "0x%02x" "$o1" 2>/dev/null || echo "0x00")
          h2=$(printf "0x%02x" "$o2" 2>/dev/null || echo "0x00")
          h3=$(printf "0x%02x" "$o3" 2>/dev/null || echo "0x00")
          h4=$(printf "0x%02x" "$o4" 2>/dev/null || echo "0x00")
          python3 /cdrom/pool/extra/ipmi_start_logger.py 0x03 "$h1" "$h2" 2>/dev/null || true
          sleep 2
          python3 /cdrom/pool/extra/ipmi_start_logger.py 0x13 "$h3" "$h4" 2>/dev/null || true
      fi
    - python3 /cdrom/pool/extra/ipmi_start_logger.py 0xEE || true
  late-commands:
    - python3 /cdrom/pool/extra/ipmi_start_logger.py 0x06 2>/dev/null || true
    - sleep 1
    - echo 'root:{{.Password}}' | chroot /target chpasswd
    - curtin in-target --target=/target -- sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
    - curtin in-target --target=/target -- sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
    - echo '{{.Username}} ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/{{.Username}}
    - chmod 440 /target/etc/sudoers.d/{{.Username}}
    
{{- if .Mi325xSupport}}
    # Add home folder and users
    - curtin in-target --target=/target -- groupadd -g 1003 mctadmins
{{- if ne .Username "mctadmin"}}
    - curtin in-target --target=/target -- useradd -u 1002 -g 1003 -m -d /home/mctadmin -s /bin/bash mctadmin
    - curtin in-target --target=/target -- usermod --password '$6$qP4pkN8TukYjIBGC$XTiUGY58xYSSwspzxJCu4W9g/JFUg59F4U4zs9xqIaZWV3X0LwK.hND85WtOCI5kcfAXiNu7V2bEFoPzeotGU1' mctadmin
    - curtin in-target --target=/target -- usermod -aG sudo,video,render,mctadmins mctadmin
{{- end}}
{{- if ne .Username "mctkube"}}
    - curtin in-target --target=/target -- useradd -u 1001 -g 1003 -m -d /home/mctkube -s /bin/bash mctkube
    - curtin in-target --target=/target -- usermod --password '$6$qP4pkN8TukYjIBGC$XTiUGY58xYSSwspzxJCu4W9g/JFUg59F4U4zs9xqIaZWV3X0LwK.hND85WtOCI5kcfAXiNu7V2bEFoPzeotGU1' mctkube
    - curtin in-target --target=/target -- usermod -aG sudo,video,render,mctadmins mctkube
{{- end}}
    - |
      curtin in-target --target=/target -- sh -c '
      echo "ADD_EXTRA_GROUPS=1" | tee -a /etc/adduser.conf
      echo "EXTRA_GROUPS=\"video render docker\"" | tee -a /etc/adduser.conf
      '
	# Update System configuration
	- cp /cdrom/pool/mi325xr/setup_routing_mi325.sh /target/usr/local/bin/setup_routing_mi3xx.sh
	- mkdir -p /target/var/spool/cron/crontabs
	- cp /cdrom/pool/mi325xr/crontabs /target/var/spool/cron/crontabs/root
    - |
      # Update crontab configuration
      curtin in-target --target=/target -- sh -c '
      chmod +x /usr/local/bin/setup_routing_mi3xx.sh
      chmod 600 /var/spool/cron/crontabs/root
      chown root:crontab /var/spool/cron/crontabs/root
      '
	# Passwordless SSH keys
	- mkdir -p /target/home/mctadmin/.ssh
	- chmod 700 /target/home/mctadmin/.ssh
	- mkdir -p /target/home/mctkube/.ssh
    - chmod 700 /target/home/mctkube/.ssh
    - cp /cdrom/pool/mi325xr/hosts /target/tmp/hosts
	- cp /cdrom/pool/mi325xr/id_rsa /target/home/mctadmin/.ssh/id_rsa
	- cp /cdrom/pool/mi325xr/id_rsa.pub /target/home/mctadmin/.ssh/id_rsa.pub
	- cp /cdrom/pool/mi325xr/id_rsa /target/home/mctkube/.ssh/id_rsa
	- cp /cdrom/pool/mi325xr/id_rsa.pub /target/home/mctkube/.ssh/id_rsa.pub
	- |
      curtin in-target --target=/target -- sh -c '
	  cat /tmp/hosts >> /etc/hosts
	  chown mctadmin:mctadmins -R /home/mctadmin/.ssh
	  chmod 600 /home/mctadmin/.ssh/*
	  chown mctkube:mctadmins -R /home/mctkube/.ssh
      chmod 600 -R /home/mctkube/.ssh/* 
	  '

	# Update eths naming
	- cp /cdrom/pool/mi325xr/70-amdgpu.rules /target/etc/udev/rules.d/70-amdgpu.rules
	- cp /cdrom/pool/mi325xr/99-network-naming.rules /target/etc/udev/rules.d/99-network-naming.rules
	- |
      curtin in-target --target=/target -- sh -c '
      udevadm control --reload
      udevadm trigger --subsystem-match=net
      '
    
	# Disable ACS
	- cp /cdrom/pool/mi325xr/disable_acs.service /target/etc/systemd/system/disable_acs.service
	- cp /cdrom/pool/mi325xr/disable_acs /target/usr/local/bin/disable_acs
    - |
      curtin in-target --target=/target -- sh -c '
      chmod +x /usr/local/bin/disable_acs
      systemctl daemon-reload
      systemctl enable disable_acs.service
      '

	# Others
	- cp /cdrom/pool/mi325xr/env.sh /target/etc/profile.d/env.sh   
	- |
      curtin in-target --target=/target -- sh -c '
      chmod +x /etc/profile.d/env.sh
      '

{{- end}}

	- cp /etc/resolv.conf /target/etc/resolv.conf
    - |
      if [ -n "{{.OfflinePackages}}" ]; then
          mkdir -p /target/tmp/extra_pkg
          cp -r /cdrom/pool/extra/*.deb /target/tmp/extra_pkg/ 2>/dev/null || true
          curtin in-target --target=/target -- sh -c 'apt-get install -y /tmp/extra_pkg/*.deb || dpkg -i /tmp/extra_pkg/*.deb || true'
          rm -rf /target/tmp/extra_pkg
      else
          if apt-get update && curtin in-target --target=/target -- apt-get install -y vim curl net-tools ipmitool htop; then
              echo "[+] Packages installed from mirrors."
          else
              mkdir -p /target/tmp/extra_pkg
              cp -r /cdrom/pool/extra/*.deb /target/tmp/extra_pkg/ 2>/dev/null || true
              curtin in-target --target=/target -- sh -c 'apt-get install -y /tmp/extra_pkg/*.deb || dpkg -i /tmp/extra_pkg/*.deb || true'
              rm -rf /target/tmp/extra_pkg
          fi
      fi
    - sleep 1
    - python3 /cdrom/pool/extra/ipmi_start_logger.py 0x16 2>/dev/null || true
    - sleep 1
    - |
      HOST_IP=$(hostname -I | awk '{print $1}')
      if [ -n "$HOST_IP" ]; then
          eval $(echo "$HOST_IP" | awk -F. '{printf "o1=%s; o2=%s; o3=%s; o4=%s", $1, $2, $3, $4}')
          h1=$(printf "0x%02x" "$o1" 2>/dev/null || echo "0x00")
          h2=$(printf "0x%02x" "$o2" 2>/dev/null || echo "0x00")
          h3=$(printf "0x%02x" "$o3" 2>/dev/null || echo "0x00")
          h4=$(printf "0x%02x" "$o4" 2>/dev/null || echo "0x00")
          python3 /cdrom/pool/extra/ipmi_start_logger.py 0x03 "$h1" "$h2" 2>/dev/null || true
          sleep 2
          python3 /cdrom/pool/extra/ipmi_start_logger.py 0x13 "$h3" "$h4" 2>/dev/null || true
      else
          python3 /cdrom/pool/extra/ipmi_start_logger.py 0x03 0x00 0x00 2>/dev/null || true
          sleep 2
          python3 /cdrom/pool/extra/ipmi_start_logger.py 0x13 0x00 0x00 2>/dev/null || true
      fi
    - sleep 1
    - python3 /cdrom/pool/extra/ipmi_start_logger.py 0xaa 2>/dev/null || true
    - sleep 1
{{- if eq .StorageMatchKey "serial"}}
    - |
      curtin in-target --target=/target -- sh -c '
        root_dev=$(lsblk -no PKNAME $(findmnt -nvo SOURCE /) | head -n 1)
        [ -z "$root_dev" ] && root_dev=$(lsblk -no NAME $(findmnt -nvo SOURCE /) | head -n 1)
        actual_serial=$(udevadm info --query=property --name=/dev/$root_dev 2>/dev/null | grep "^ID_SERIAL=" | cut -d"=" -f2)
        expected_serial="{{.StorageMatchValue}}"
        echo "--- Installation Audit ---" >> /var/log/install_disk_audit.log
        echo "Expected Serial: $expected_serial" >> /var/log/install_disk_audit.log
        echo "Actual Root Serial: $actual_serial" >> /var/log/install_disk_audit.log
        if [ "$actual_serial" = "$expected_serial" ]; then
            python3 /cdrom/pool/extra/ipmi_start_logger.py 0x05 0x4f 0x4b 2>/dev/null || true
        else
            python3 /cdrom/pool/extra/ipmi_start_logger.py 0x05 0x45 0x52 2>/dev/null || true
        fi
      '
{{- end}}
{{- if .Mi325xSupport}}
    # Mi325x platform: configure GRUB kernel parameters and record-fail timeout
    - curtin in-target --target=/target -- sh -c "sed -i 's/GRUB_CMDLINE_LINUX=\"\"/GRUB_CMDLINE_LINUX=\"amd_iommu=on iommu=pt pci=realloc=off\"/' /etc/default/grub"
    - curtin in-target -- bash -c 'echo "GRUB_RECORDFAIL_TIMEOUT=0" >> /etc/default/grub'
    - curtin in-target --target=/target -- update-grub
{{- end}}
    - cp /var/log/ipmi_telemetry.log /target/var/log/ipmi_telemetry.log 2>/dev/null || true
    - cp /var/log/install_disk_audit.log /target/var/log/install_disk_audit.log 2>/dev/null || true
`

// ─── Preseed template (Ubuntu 18.04) ─────────────────────────────────────────

const preseedTmpl = `# Locale/Keyboard
d-i debian-installer/locale string en_US.UTF-8
d-i console-setup/ask_detect boolean false
d-i keyboard-configuration/xkb-keymap select us

# Network
d-i netcfg/choose_interface select auto
d-i netcfg/get_hostname string {{.Hostname}}
d-i netcfg/get_domain string unassigned-domain

d-i anna/choose_modules string network-console
d-i network-console/password password {{.Password}}
d-i network-console/password-again password {{.Password}}
d-i network-console/start boolean false

# Clock
d-i clock-setup/utc boolean true
d-i time/zone string UTC

d-i preseed/early_command string \
    modprobe ipmi_devintf 2>/dev/null || true; \
    modprobe ipmi_si 2>/dev/null || true; \
    modprobe ipmi_msghandler 2>/dev/null || true; \
    sleep 2; \
    python3 /cdrom/pool/extra/ipmi_start_logger.py 0x0F 2>/dev/null || true; \
    dpkg -i /cdrom/pool/extra/*.deb 2>/dev/null || true; \
    python3 /cdrom/pool/extra/ipmi_start_logger.py 0x1F 2>/dev/null || true; \
    sleep 2; \
    python3 /cdrom/pool/extra/ipmi_start_logger.py 0x01 2>/dev/null || true

d-i partman/early_command string \
    sh /cdrom/find_disk_1804.sh; \
    disk=$(cat /tmp/find_disk_1804.result 2>/dev/null); \
    if [ -n "$disk" ]; then \
        echo "$disk" > /tmp/install_target_disk; \
        . /usr/share/debconf/confmodule; \
        db_set partman-auto/disk "$disk"; \
        db_set grub-installer/bootdev "$disk"; \
    else \
        python3 /cdrom/pool/extra/ipmi_start_logger.py 0xEE 2>/dev/null || true; \
        exit 1; \
    fi

d-i partman-auto/method string regular
d-i partman-lvm/device_remove_lvm boolean true
d-i partman-md/device_remove_md boolean true
d-i partman-lvm/confirm boolean true
d-i partman-lvm/confirm_nooverwrite boolean true
d-i partman-auto/choose_recipe select atomic
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/choose_partition select finish
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true

d-i passwd/user-fullname string {{.Username}}
d-i passwd/username string {{.Username}}
d-i passwd/user-password password {{.Password}}
d-i passwd/user-password-again password {{.Password}}
d-i passwd/root-password password {{.Password}}
d-i passwd/root-password-again password {{.Password}}
d-i passwd/root-login boolean true
d-i user-setup/allow-password-weak boolean true
d-i user-setup/encrypt-home boolean false

d-i apt-setup/use_mirror boolean false
d-i apt-setup/cdrom/set-first boolean true
d-i apt-setup/cdrom/set-next boolean false
d-i apt-setup/cdrom/set-failed boolean false
d-i apt-setup/restricted boolean true
d-i apt-setup/universe boolean true

tasksel tasksel/first multiselect standard, server
d-i pkgsel/include string openssh-server
d-i pkgsel/upgrade select none
d-i pkgsel/update-policy select none

d-i grub-installer/only_debian boolean true
d-i grub-installer/with_other_os boolean true

d-i preseed/late_command string \
    python3 /cdrom/pool/extra/ipmi_start_logger.py 0x06 2>/dev/null || true; \
    sleep 1; \
    in-target sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config; \
    in-target sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config; \
    echo '{{.Username}} ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/{{.Username}}; \
    chmod 440 /target/etc/sudoers.d/{{.Username}}; \
    echo "root:{{.Password}}" | in-target chpasswd; \
    if ls /cdrom/pool/extra/*.deb >/dev/null 2>&1; then \
        mkdir -p /target/tmp/extra_pkg; \
        cp /cdrom/pool/extra/*.deb /target/tmp/extra_pkg/; \
        in-target sh -c 'dpkg -i /tmp/extra_pkg/*.deb || apt-get install -y -f'; \
        rm -rf /target/tmp/extra_pkg; \
    fi; \
    sleep 1; \
    python3 /cdrom/pool/extra/ipmi_start_logger.py 0x16 2>/dev/null || true; \
    sleep 1; \
    HOST_IP=$(hostname -I | awk '{print $1}'); \
    if [ -n "$HOST_IP" ]; then \
        eval $(echo "$HOST_IP" | awk -F. '{printf "o1=%s; o2=%s; o3=%s; o4=%s", $1, $2, $3, $4}'); \
        h1=$(printf "0x%02x" "$o1" 2>/dev/null || echo "0x00"); \
        h2=$(printf "0x%02x" "$o2" 2>/dev/null || echo "0x00"); \
        h3=$(printf "0x%02x" "$o3" 2>/dev/null || echo "0x00"); \
        h4=$(printf "0x%02x" "$o4" 2>/dev/null || echo "0x00"); \
        python3 /cdrom/pool/extra/ipmi_start_logger.py 0x03 "$h1" "$h2" 2>/dev/null || true; \
        sleep 2; \
        python3 /cdrom/pool/extra/ipmi_start_logger.py 0x13 "$h3" "$h4" 2>/dev/null || true; \
    else \
        python3 /cdrom/pool/extra/ipmi_start_logger.py 0x03 0x00 0x00 2>/dev/null || true; \
        sleep 2; \
        python3 /cdrom/pool/extra/ipmi_start_logger.py 0x13 0x00 0x00 2>/dev/null || true; \
    fi; \
    sleep 1; \
    python3 /cdrom/pool/extra/ipmi_start_logger.py 0xaa 2>/dev/null || true; \
    sleep 1; \
    expected_disk=$(cat /tmp/install_target_disk 2>/dev/null); \
    root_dev=$(lsblk -no PKNAME $(findmnt -nvo SOURCE /) 2>/dev/null | head -n 1); \
    [ -z "$root_dev" ] && root_dev=$(lsblk -no NAME $(findmnt -nvo SOURCE /) 2>/dev/null | head -n 1); \
    actual_disk="/dev/$root_dev"; \
    if [ "$actual_disk" = "$expected_disk" ]; then \
        python3 /cdrom/pool/extra/ipmi_start_logger.py 0x05 0x4f 0x4b 2>/dev/null || true; \
    else \
        python3 /cdrom/pool/extra/ipmi_start_logger.py 0x05 0x45 0x52 2>/dev/null || true; \
    fi; \
    cp /var/log/ipmi_telemetry.log /target/var/log/ipmi_telemetry.log 2>/dev/null || true

d-i finish-install/reboot_in_progress note
`

// ─── Write cloud-init / preseed files ────────────────────────────────────────

func writeCloudInitFiles(cfg *BuildConfig) {
	autoinstallDir := filepath.Join(cfg.WorkDir, "autoinstall")
	_ = os.MkdirAll(autoinstallDir, 0755)

	metaData := fmt.Sprintf("instance-id: ubuntu-autoinstall-001\nlocal-hostname: %s\n", cfg.Hostname)
	_ = os.WriteFile(filepath.Join(autoinstallDir, "meta-data"), []byte(metaData), 0644)

	// Symlink for Ubuntu 24.04+ compatibility
	symlinkPath := filepath.Join(cfg.WorkDir, "autoinstall.yaml")
	if _, err := os.Lstat(symlinkPath); os.IsNotExist(err) {
		_ = os.Symlink("/cdrom/autoinstall/user-data", symlinkPath)
		logf("Created symlink: /autoinstall.yaml -> /cdrom/autoinstall/user-data")
	}

	tmplData := struct {
		Hostname          string
		Username          string
		Password          string
		HashPassword      string
		PubKey            string
		EFIGUID           string
		OfflinePackages   string
		StorageMatchKey   string
		StorageMatchValue string
		FindDiskEnabled   bool
		FindDiskSizeHint  string
		Mi325xSupport     bool
		Mi325xNode        string
	}{
		Hostname:          cfg.Hostname,
		Username:          cfg.Username,
		Password:          cfg.Password,
		HashPassword:      cfg.HashPassword,
		PubKey:            cfg.PubKey,
		EFIGUID:           efiGUID,
		OfflinePackages:   cfg.OfflinePackages,
		StorageMatchKey:   cfg.StorageMatchKey,
		StorageMatchValue: cfg.StorageMatchValue,
		FindDiskEnabled:   cfg.StorageMatchValue == "__ID_SERIAL__",
		FindDiskSizeHint:  cfg.FindDiskSizeHint,
		Mi325xSupport:     cfg.Mi325xSupport,
		Mi325xNode:        cfg.Mi325xNode,
	}

	t := template.Must(template.New("userdata").Parse(userDataTmpl))
	f, err := os.Create(filepath.Join(autoinstallDir, "user-data"))
	if err != nil {
		fatalf("failed to create user-data: %v", err)
	}
	defer f.Close()
	_ = t.Execute(f, tmplData)
}

func writePreseedFile(cfg *BuildConfig) {
	tmplData := struct {
		Hostname string
		Username string
		Password string
	}{
		Hostname: cfg.Hostname,
		Username: cfg.Username,
		Password: cfg.Password,
	}

	t := template.Must(template.New("preseed").Parse(preseedTmpl))
	f, err := os.Create(filepath.Join(cfg.WorkDir, "preseed.cfg"))
	if err != nil {
		fatalf("failed to create preseed.cfg: %v", err)
	}
	defer f.Close()
	_ = t.Execute(f, tmplData)
}

// sanitizeVolID makes a string safe for use as an ISO 9660 volume identifier:
// uppercase, only A-Z 0-9 _ allowed (spaces and dots → _), max 32 characters.
func sanitizeVolID(s string) string {
	s = strings.ToUpper(s)
	var b strings.Builder
	for _, r := range s {
		if (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '_' {
			b.WriteRune(r)
		} else {
			b.WriteRune('_')
		}
	}
	result := b.String()
	if len(result) > 32 {
		result = result[:32]
	}
	return result
}

// ─── ISO rebuild ─────────────────────────────────────────────────────────────

func buildISO(cfg *BuildConfig) {
	// Get volume ID from original ISO and sanitize for ISO 9660 compliance:
	// uppercase, max 32 chars, only A-Z 0-9 _ allowed (spaces → _).
	rawVolID, _ := outputOf("bash", "-c",
		fmt.Sprintf(`isoinfo -d -i "%s" | awk -F': ' '/Volume id:/ {print $2}'`, cfg.OrigISO))
	if rawVolID == "" {
		rawVolID = "UBUNTU_AUTOINSTALL"
	}
	volID := sanitizeVolID(rawVolID)
	logf("Volume ID: %s (raw: %s)", volID, rawVolID)

	if cfg.Is1804 {
		logf("18.04 Legacy ISO: using original efi.img (no modification needed)")
		mbrFile := "/tmp/isohdpfx_1804.bin"
		run("dd", "if="+cfg.OrigISO, "bs=1", "count=432", "of="+mbrFile)
		logf("MBR extracted to: %s", mbrFile)

		logf("Rebuilding ISO (18.04 legacy)...")
		cmd := exec.Command("xorriso",
			"-as", "mkisofs",
			"-r", "-V", volID, "-J", "-l",
			"-isohybrid-mbr", mbrFile,
			"-partition_cyl_align", "on",
			"-partition_offset", "0",
			"-partition_hd_cyl", "64",
			"-partition_sec_hd", "32",
			"--mbr-force-bootable",
			"-apm-block-size", "2048",
			"-iso_mbr_part_type", "0x00",
			"-c", "isolinux/boot.cat",
			"-b", "isolinux/isolinux.bin",
			"-no-emul-boot",
			"-boot-load-size", "4",
			"-boot-info-table",
			"-eltorito-alt-boot",
			"-e", "boot/grub/efi.img",
			"-no-emul-boot",
			"-boot-load-size", "4800",
			"-isohybrid-gpt-basdat",
			"-isohybrid-apm-hfsplus",
			"-o", cfg.OutISO,
			".",
		)
		cmd.Dir = cfg.WorkDir
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			fatalf("xorriso failed: %v", err)
		}

	} else {
		logf("20.04+ Modern ISO: building external EFI partition...")

		mbrFile := "/tmp/isohdpfx.bin"
		run("dd", "if="+cfg.OrigISO, "bs=1", "count=432", "of="+mbrFile)

		for _, candidate := range []string{
			"/usr/lib/ISOLINUX/isohdpfx.bin",
			"/usr/lib/syslinux/isohdpfx.bin",
		} {
			if fileExists(candidate) {
				mbrFile = candidate
				break
			}
		}
		logf("Using MBR file: %s", mbrFile)

		efiImg := "/tmp/efi.img"
		logf("Creating EFI boot image (64MB)...")
		run("dd", "if=/dev/zero", "of="+efiImg, "bs=1M", "count=64")
		run("mkfs.vfat", efiImg)
		run("mmd", "-i", efiImg, "::/EFI", "::/EFI/BOOT", "::/boot", "::/boot/grub")

		copyToEFI := func(pattern, dest string) {
			out, _ := exec.Command("find", cfg.WorkDir, "-iname", pattern).Output()
			found := strings.TrimSpace(string(out))
			if found != "" {
				first := strings.Split(found, "\n")[0]
				run("mcopy", "-v", "-i", efiImg, first, dest)
			} else {
				warnf("%s not found", pattern)
			}
		}
		copyToEFI("bootx64.efi", "::/EFI/BOOT/bootx64.efi")
		copyToEFI("grubx64.efi", "::/EFI/BOOT/grubx64.efi")
		copyToEFI("mmx64.efi", "::/EFI/BOOT/mmx64.efi")

		grubDir := filepath.Join(cfg.WorkDir, "boot/grub")
		if dirExists(grubDir) {
			logf("Copying GRUB configuration and assets...")
			entries, _ := os.ReadDir(grubDir)
			for _, e := range entries {
				if !e.IsDir() {
					run("mcopy", "-i", efiImg,
						filepath.Join(grubDir, e.Name()), "::/boot/grub/")
				}
			}
			grubCfg := filepath.Join(grubDir, "grub.cfg")
			if fileExists(grubCfg) {
				run("mcopy", "-i", efiImg, grubCfg, "::/EFI/BOOT/grub.cfg")
			}
		}
		efiModDir := filepath.Join(cfg.WorkDir, "boot/grub/x86_64-efi")
		if dirExists(efiModDir) {
			logf("Copying GRUB modules...")
			run("mcopy", "-s", "-i", efiImg, efiModDir, "::/boot/grub/")
		}
		fontsDir := filepath.Join(cfg.WorkDir, "boot/grub/fonts")
		if dirExists(fontsDir) {
			logf("Copying GRUB fonts directory...")
			run("mcopy", "-s", "-i", efiImg, fontsDir, "::/boot/grub/")
		}
		startupNsh := filepath.Join(cfg.ScriptDir, "startup.nsh")
		if fileExists(startupNsh) {
			logf("Copying startup.nsh to EFI image root...")
			run("mcopy", "-i", efiImg, startupNsh, "::/startup.nsh")
		} else {
			warnf("startup.nsh not found at %s", startupNsh)
		}
		logf("EFI boot image created: %s", efiImg)

		// Find BIOS boot image
		biosBootImg := ""
		for _, candidate := range []string{
			filepath.Join(cfg.WorkDir, "boot/grub/i386-pc/eltorito.img"),
			filepath.Join(cfg.WorkDir, "isolinux/isolinux.bin"),
		} {
			if fileExists(candidate) {
				// Make relative to WorkDir
				rel, _ := filepath.Rel(cfg.WorkDir, candidate)
				biosBootImg = rel
				break
			}
		}
		logf("Using BIOS boot image: %s", biosBootImg)

		logf("Rebuilding ISO (20.04+)...")

		// Build xorriso args matching the shell script argument order exactly.
		// When a BIOS boot image is present, -b must come right after -V <volID>
		// (before -J -l), matching: ${XORRISO_ARGS[@]:0:5} -b BIOS ${XORRISO_ARGS[@]:5}
		// Inserting -b anywhere else (e.g. after -boot-info-table) causes:
		//   "Cannot apply boot image patching outside of ISO 9660 filesystem"
		//   "Cannot refer by GRUB2 MBR to data outside of ISO 9660 filesystem"
		prefix := []string{"-as", "mkisofs", "-r", "-V", volID} // indices 0-4
		suffix := []string{
			"-J", "-l",
			"-c", "boot.catalog",
			"-no-emul-boot",
			"-boot-load-size", "4",
			"-boot-info-table",
			"-eltorito-alt-boot",
			"-e", "--interval:appended_partition_2:all::",
			"-no-emul-boot",
			"-append_partition", "2", "0xEF", efiImg,
			"--grub2-mbr", mbrFile,
			"-partition_offset", "16",
			"-appended_part_as_gpt",
			"-iso_mbr_part_type", "a2a0d0ebe5b9334487c068b6b72699c7",
			"-o", cfg.OutISO,
			".",
		}

		var xorrisoArgs []string
		if biosBootImg != "" {
			// -b <biosBootImg> inserted between prefix and suffix
			xorrisoArgs = append(prefix, append([]string{"-b", biosBootImg}, suffix...)...)
		} else {
			xorrisoArgs = append(prefix, suffix...)
		}

		cmd := exec.Command("xorriso", xorrisoArgs...)
		cmd.Dir = cfg.WorkDir
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			fatalf("xorriso failed: %v", err)
		}
	}
}

// ─── Main ─────────────────────────────────────────────────────────────────────

func main() {
	// Argument parsing
	if len(os.Args) < 2 ||
		os.Args[1] == "-h" || os.Args[1] == "--help" {
		showHelp()
	}

	skipInstall := false
	isoRepoDir := ""
	hostname := "ubuntu-auto"
	mi325xSupport := false
	mi325xNode := ""
	var positional []string

	// Storage match: collect all three flags in argv order, then resolve.
	type storageFlag struct{ key, value string }
	var storageFlags []storageFlag

	for _, arg := range os.Args[1:] {
		switch {
		case arg == "--skip-install":
			skipInstall = true
		case arg == "--mi325x-support":
			mi325xSupport = true
		case strings.HasPrefix(arg, "--mi325x-node="):
			mi325xNode = strings.TrimPrefix(arg, "--mi325x-node=")
		case strings.HasPrefix(arg, "--iso-repo-dir="):
			isoRepoDir = strings.TrimPrefix(arg, "--iso-repo-dir=")
		case strings.HasPrefix(arg, "--hostname="):
			hostname = strings.TrimPrefix(arg, "--hostname=")
		case strings.HasPrefix(arg, "--storage-serial="):
			storageFlags = append(storageFlags, storageFlag{"serial", strings.TrimPrefix(arg, "--storage-serial=")})
		case strings.HasPrefix(arg, "--storage-model="):
			storageFlags = append(storageFlags, storageFlag{"model", strings.TrimPrefix(arg, "--storage-model=")})
		case strings.HasPrefix(arg, "--storage-size="):
			storageFlags = append(storageFlags, storageFlag{"size", strings.TrimPrefix(arg, "--storage-size=")})
		default:
			positional = append(positional, arg)
		}
	}

	// Only one storage flag is allowed — first in argv order wins; warn about the rest.
	// --storage-size is handled differently: find_disk.sh resolves the serial at boot.
	var storageMatchKey, storageMatchValue, findDiskSizeHint string
	if len(storageFlags) > 0 {
		first := storageFlags[0]
		if first.key == "size" {
			findDiskSizeHint = first.value
			logf("Storage size hint: %s — find_disk.sh will locate disk by size and resolve serial at boot", first.value)
		} else {
			storageMatchKey = first.key
			storageMatchValue = first.value
			logf("Storage match: --storage-%s=%s (will be used)", storageMatchKey, storageMatchValue)
		}
		for _, extra := range storageFlags[1:] {
			warnf("Ignoring extra storage flag: --storage-%s=%s (only one storage match allowed)", extra.key, extra.value)
		}
	}

	osName := positional[0]
	username := "mitac"
	password := "ubuntu"
	if len(positional) >= 2 {
		username = positional[1]
	}
	if len(positional) >= 3 {
		password = positional[2]
	}

	// Extract embedded assets (scripts/, startup.nsh, ipmi_start_logger.py,
	// package_list) to a temp directory. This makes the binary self-contained:
	// it works correctly regardless of the working directory or how it is invoked
	// (direct execution, Nuitka onefile, CI pipeline, etc.).
	assetsDir, err := extractEmbeddedAssets()
	if err != nil {
		fatalf("failed to extract embedded assets: %v", err)
	}
	defer func() {
		logf("Cleaning up embedded assets: %s", assetsDir)
		_ = os.RemoveAll(assetsDir)
	}()
	scriptDir := assetsDir

	// Read offline packages
	offlinePkgs := readOfflinePackages(scriptDir)

	// Check / install required packages
	checkAndInstallPackages(skipInstall)

	// Detect Ubuntu variant
	is1804 := strings.Contains(osName, "18.04")
	if is1804 {
		logf("Detected Ubuntu 18.04 - Using Preseed automation")
	} else {
		logf("Detected Ubuntu 20.04+ - Using Autoinstall automation")
	}

	// Lookup ISO path
	if isoRepoDir != "" {
		logf("ISO repository: %s (--iso-repo-dir)", isoRepoDir)
	} else {
		logf("ISO repository: %s/iso_repository/ (default)", scriptDir)
	}
	logf("Looking up ISO path for OS: %s", osName)
	origISO := lookupISOPath(osName, scriptDir, isoRepoDir)
	logf("Found ISO: %s", origISO)
	if !fileExists(origISO) {
		fatalf("Original ISO not found: %s", origISO)
	}

	// Build ID and directories — anchored to the current working directory, NOT
	// scriptDir. scriptDir now points to the embedded-assets temp dir which is
	// deleted on exit; placing workDir/outISODir there would destroy the output
	// ISO before the caller (main.py / NFS copy) can use it.
	rand.Seed(time.Now().UnixNano())
	buildID := fmt.Sprintf("%s_%04d", time.Now().Format("20060102150405"), rand.Intn(9999))
	cwd, _ := os.Getwd()
	workDir, _ := filepath.Abs(filepath.Join(cwd, "workdir_custom_iso", buildID))
	outISODir, _ := filepath.Abs(filepath.Join(cwd, "output_custom_iso", buildID))

	// Resolve persistent apt cache under XDG_CACHE_HOME (or ~/.cache/) so it
	// survives runs even when scriptDir is a temporary embedded-assets directory.
	cacheHome := os.Getenv("XDG_CACHE_HOME")
	if cacheHome == "" {
		cacheHome = filepath.Join(os.Getenv("HOME"), ".cache")
	}
	cacheDir := filepath.Join(cacheHome, "build-iso", "apt_cache")
	_ = os.MkdirAll(cacheDir, 0755)

	isoBasename := strings.TrimSuffix(filepath.Base(origISO), ".iso")
	ts := time.Now().Format("200601021504")
	isoAutoinstall := strings.ReplaceAll(isoBasename, "-", "_") + "_autoinstall_" + ts + ".iso"
	outISO := filepath.Join(outISODir, isoAutoinstall)

	logf("Initializing unique build environment: %s", buildID)
	_ = os.MkdirAll(workDir, 0755)
	_ = os.MkdirAll(outISODir, 0755)

	// Cleanup workdir on exit
	defer func() {
		if dirExists(workDir) {
			logf("Cleaning up work directory: %s", workDir)
			_ = os.RemoveAll(workDir)
		}
	}()

	// Default storage match: placeholder serial replaced at boot by find_disk.sh.
	// --storage-serial/model sets key+value directly (find_disk disabled).
	// --storage-size sets findDiskSizeHint; find_disk.sh runs with --target-size at boot.
	// No flag: find_disk.sh picks the smallest empty disk.
	if storageMatchKey == "" {
		storageMatchKey = "serial"
		storageMatchValue = "__ID_SERIAL__"
		if findDiskSizeHint != "" {
			logf("Storage match: size hint %s — find_disk.sh will locate disk by size and patch serial", findDiskSizeHint)
		} else {
			logf("Storage match: not specified — using find_disk.sh auto-detection at boot")
		}
	}

	// Validate --mi325x-node when --mi325x-support is set.
	reNode := regexp.MustCompile(`^node_[1-9][0-9]*$`)
	if mi325xSupport {
		if mi325xNode == "" {
			fatalf("--mi325x-node is required when --mi325x-support is set\n" +
				"  Usage: --mi325x-node=node_1  (node_1, node_2, ... node_N)")
		}
		if !reNode.MatchString(mi325xNode) {
			fatalf("invalid --mi325x-node value: %q\n"+
				"  Expected format: node_<integer>  e.g. node_1, node_2, node_10", mi325xNode)
		}
	} else if mi325xNode != "" {
		warnf("--mi325x-node=%s ignored (only used when --mi325x-support is set)", mi325xNode)
	}

	logf("Hostname: %s", hostname)
	if mi325xSupport {
		logf("Mi325x support: enabled (GRUB kernel params will be applied in late-commands)")
		logf("Mi325x node: %s", mi325xNode)
	}

	cfg := &BuildConfig{
		OSName:            osName,
		Username:          username,
		Password:          password,
		Hostname:          hostname,
		Mi325xSupport:     mi325xSupport,
		Mi325xNode:        mi325xNode,
		Is1804:            is1804,
		OrigISO:           origISO,
		WorkDir:           workDir,
		OutISODir:         outISODir,
		OutISO:            outISO,
		BuildID:           buildID,
		ScriptDir:         scriptDir,
		OfflinePackages:   offlinePkgs,
		Timestamp:         ts,
		StorageMatchKey:   storageMatchKey,
		StorageMatchValue: storageMatchValue,
		FindDiskSizeHint:  findDiskSizeHint,
		CacheDir:          cacheDir,
	}

	// Mount and copy ISO contents
	logf("Preparing work directories...")
	_ = os.MkdirAll("/mnt/ubuntuiso", 0755)
	logf("Mounting original ISO...")
	run("mount", "-o", "loop", origISO, "/mnt/ubuntuiso")
	logf("Copying ISO contents...")
	run("rsync", "-a", "/mnt/ubuntuiso/", workDir+"/")
	run("umount", "/mnt/ubuntuiso")

	// Detect codename
	cfg.Codename = getUbuntuCodename(workDir, osName)
	logf("Target Ubuntu codename: %s", cfg.Codename)

	// Download and bundle extra packages
	downloadExtraPackages(cfg)

	// Copy Mi325x platform files into pool/mi325xr/
	if cfg.Mi325xSupport {
		logf("Bundling Mi325x platform files (node: %s)...", cfg.Mi325xNode)
		copyMi325xrFiles(cfg)
	}

	// Hash password using SHA-512 crypt (same format as mkpasswd -m sha-512).
	// Implemented natively in Go — no dependency on the external mkpasswd binary.
	hashOut, err := crypt.New(crypt.SHA512).Generate([]byte(password), nil)
	if err != nil {
		fatalf("failed to hash password: %v", err)
	}
	cfg.HashPassword = hashOut
	logf("Password hashed successfully")

	// Copy helper scripts
	scriptsDir := filepath.Join(workDir, "autoinstall/scripts")
	_ = os.MkdirAll(scriptsDir, 0755)

	findDiskSrc := filepath.Join(scriptDir, "scripts/find_disk.sh")
	if cfg.StorageMatchValue == "__ID_SERIAL__" {
		// Auto-detection mode: copy find_disk.sh so it can patch the serial at boot.
		if fileExists(findDiskSrc) {
			logf("Copying find_disk.sh to ISO (auto-detection mode)...")
			dst := filepath.Join(scriptsDir, "find_disk.sh")
			_ = copyFile(findDiskSrc, dst)
			_ = os.Chmod(dst, 0755)
		} else if !is1804 {
			fatalf("find_disk.sh not found at %s", findDiskSrc)
		}
	} else {
		// Manual storage match: disk identity is already set in user-data.
		// find_disk.sh is not needed and must not run (it would try to overwrite the match).
		logf("Skipping find_disk.sh (storage match set to %s=%s)", cfg.StorageMatchKey, cfg.StorageMatchValue)
	}

	if is1804 {
		findDisk1804Src := filepath.Join(scriptDir, "scripts/find_disk_1804.sh")
		if fileExists(findDisk1804Src) {
			logf("Copying find_disk_1804.sh to ISO...")
			dst := filepath.Join(workDir, "find_disk_1804.sh")
			_ = copyFile(findDisk1804Src, dst)
			_ = os.Chmod(dst, 0755)
		} else {
			fatalf("find_disk_1804.sh not found at %s", findDisk1804Src)
		}
	}

	// Generate SSH key
	generateSSHKey(cfg)

	// Write cloud-init / preseed files
	logf("Adding autoinstall cloud-init data...")
	writeCloudInitFiles(cfg)

	if is1804 {
		logf("Adding Preseed configuration for Ubuntu 18.04 compatibility...")
		writePreseedFile(cfg)
	}

	// Patch GRUB
	logf("Patching GRUB configuration...")
	var bootParams string
	if is1804 {
		bootParams = "file=/cdrom/preseed.cfg auto=true priority=critical video=1024x768 console=ttyS0,115200n8 console=tty0 ---"
	} else {
		bootParams = "boot=casper autoinstall ds=nocloud;s=/cdrom/autoinstall/ video=1024x768 console=ttyS0,115200n8 console=tty0 ---"
	}
	patchGrubConfig(cfg, bootParams)

	// Patch ISOLINUX
	var isoLinuxParams string
	if is1804 {
		isoLinuxParams = "file=/cdrom/preseed.cfg auto=true priority=critical initrd=/install/initrd.gz video=1024x768 console=ttyS0,115200n8 console=tty0"
	} else {
		isoLinuxParams = "boot=casper autoinstall ds=nocloud;s=/cdrom/autoinstall/ initrd=/casper/initrd video=1024x768 console=ttyS0,115200n8 console=tty0"
	}
	patchISOLinuxConfig(cfg, isoLinuxParams)

	// Rebuild ISO
	logf("Rebuilding ISO...")
	buildISO(cfg)

	logf("Done. Autoinstall ISO created at: %s", outISO)
	logf("Work directory will be removed on exit.")
}
