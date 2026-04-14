package main

import (
	"bytes"
	"fmt"
	"os/exec"
	"strings"
	"testing"
	"text/template"
)

// ─── Template data struct (mirrors the anonymous struct in writeCloudInitFiles) ─

type userDataTmplData struct {
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
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

func renderTemplate(t *testing.T, data userDataTmplData) string {
	t.Helper()
	tmpl, err := template.New("userdata").Parse(userDataTmpl)
	if err != nil {
		t.Fatalf("template parse failed: %v", err)
	}
	var buf bytes.Buffer
	if err := tmpl.Execute(&buf, data); err != nil {
		t.Fatalf("template execute failed: %v", err)
	}
	return buf.String()
}

// defaultData returns a fully populated data struct for the default (auto-detect) mode.
func defaultData() userDataTmplData {
	return userDataTmplData{
		Username:          "mitac",
		Password:          "ubuntu",
		HashPassword:      "$6$rounds=4096$salt$hashedpassword",
		PubKey:            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA test@autoinstall",
		EFIGUID:           efiGUID,
		OfflinePackages:   "ipmitool curl vim",
		StorageMatchKey:   "serial",
		StorageMatchValue: "__ID_SERIAL__",
		FindDiskEnabled:   true,
		FindDiskSizeHint:  "",
	}
}

// validateYAML calls python3 to parse the rendered YAML, returning any error.
func validateYAML(content string) error {
	cmd := exec.Command("python3", "-c", "import yaml,sys; yaml.safe_load(sys.stdin)")
	cmd.Stdin = strings.NewReader(content)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("yaml parse error: %v\n%s", err, out)
	}
	return nil
}

// lineIndex returns the 0-based index of the first line containing needle, or -1.
func lineIndex(content, needle string) int {
	for i, line := range strings.Split(content, "\n") {
		if strings.Contains(line, needle) {
			return i
		}
	}
	return -1
}

// ─── Tests ────────────────────────────────────────────────────────────────────

// TestUserData_NoTabs ensures no TAB characters appear anywhere in the rendered
// user-data. YAML forbids tabs as indentation and Subiquity will crash if present.
func TestUserData_NoTabs(t *testing.T) {
	for _, name := range []string{"default", "serial", "model", "size-hint"} {
		data := defaultData()
		switch name {
		case "serial":
			data.StorageMatchKey = "serial"
			data.StorageMatchValue = "S6CKNT0W700868"
			data.FindDiskEnabled = false
		case "model":
			data.StorageMatchKey = "model"
			data.StorageMatchValue = "SAMSUNG_MZQL27T6HBLA"
			data.FindDiskEnabled = false
		case "size-hint":
			data.FindDiskSizeHint = "7T"
		}
		t.Run(name, func(t *testing.T) {
			out := renderTemplate(t, data)
			for i, line := range strings.Split(out, "\n") {
				if strings.Contains(line, "\t") {
					t.Errorf("TAB character found at line %d: %q", i+1, line)
				}
			}
		})
	}
}

// TestUserData_YAMLValid checks that the rendered user-data is valid YAML for
// all four storage modes using python3's yaml.safe_load.
func TestUserData_YAMLValid(t *testing.T) {
	cases := []struct {
		name string
		data userDataTmplData
	}{
		{
			"default (auto-detect)",
			defaultData(),
		},
		{
			"explicit serial",
			func() userDataTmplData {
				d := defaultData()
				d.StorageMatchKey = "serial"
				d.StorageMatchValue = "S6CKNT0W700868"
				d.FindDiskEnabled = false
				return d
			}(),
		},
		{
			"model match",
			func() userDataTmplData {
				d := defaultData()
				d.StorageMatchKey = "model"
				d.StorageMatchValue = "SAMSUNG_MZQL27T6HBLA"
				d.FindDiskEnabled = false
				return d
			}(),
		},
		{
			"size hint",
			func() userDataTmplData {
				d := defaultData()
				d.FindDiskSizeHint = "7T"
				return d
			}(),
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			out := renderTemplate(t, tc.data)
			if err := validateYAML(out); err != nil {
				t.Errorf("YAML validation failed: %v\n--- rendered output ---\n%s", err, out)
			}
		})
	}
}

// TestUserData_DefaultMode verifies the auto-detect storage config:
//   - match key is "serial", value is "__ID_SERIAL__"
//   - find_disk.sh is present in early-commands without --target-size
//   - serial verification block is present in late-commands
func TestUserData_DefaultMode(t *testing.T) {
	out := renderTemplate(t, defaultData())

	if !strings.Contains(out, `serial: "__ID_SERIAL__"`) {
		t.Error("expected 'serial: \"__ID_SERIAL__\"' in storage match")
	}
	if !strings.Contains(out, "find_disk.sh") {
		t.Error("expected find_disk.sh in early-commands")
	}
	if strings.Contains(out, "--target-size") {
		t.Error("unexpected --target-size in early-commands (no size hint set)")
	}
	if !strings.Contains(out, `expected_serial="__ID_SERIAL__"`) {
		t.Error("expected serial verification with __ID_SERIAL__ in late-commands")
	}
}

// TestUserData_ExplicitSerial verifies --storage-serial mode:
//   - match key is "serial", value is the provided serial
//   - find_disk.sh is NOT present in early-commands
//   - serial verification uses the provided serial value
func TestUserData_ExplicitSerial(t *testing.T) {
	d := defaultData()
	d.StorageMatchKey = "serial"
	d.StorageMatchValue = "S6CKNT0W700868"
	d.FindDiskEnabled = false
	out := renderTemplate(t, d)

	if !strings.Contains(out, `serial: "S6CKNT0W700868"`) {
		t.Error("expected 'serial: \"S6CKNT0W700868\"' in storage match")
	}
	if strings.Contains(out, "find_disk.sh") {
		t.Error("find_disk.sh must NOT appear when explicit serial is set")
	}
	if !strings.Contains(out, `expected_serial="S6CKNT0W700868"`) {
		t.Error("expected serial verification with explicit serial value")
	}
}

// TestUserData_ModelMatch verifies --storage-model mode:
//   - match key is "model", value is the provided model
//   - find_disk.sh is NOT present in early-commands
//   - serial verification block is NOT present (model match can't verify by serial)
func TestUserData_ModelMatch(t *testing.T) {
	d := defaultData()
	d.StorageMatchKey = "model"
	d.StorageMatchValue = "SAMSUNG_MZQL27T6HBLA"
	d.FindDiskEnabled = false
	out := renderTemplate(t, d)

	if !strings.Contains(out, `model: "SAMSUNG_MZQL27T6HBLA"`) {
		t.Error("expected 'model: \"SAMSUNG_MZQL27T6HBLA\"' in storage match")
	}
	if strings.Contains(out, "find_disk.sh") {
		t.Error("find_disk.sh must NOT appear when model match is set")
	}
	if strings.Contains(out, "ID_SERIAL") {
		t.Error("serial verification must NOT appear for model match mode")
	}
}

// TestUserData_SizeHint verifies --storage-size mode:
//   - match key is still "serial" with "__ID_SERIAL__" placeholder
//   - find_disk.sh IS present in early-commands with --target-size=7T
//   - serial verification uses __ID_SERIAL__ (patched at boot)
func TestUserData_SizeHint(t *testing.T) {
	d := defaultData()
	d.FindDiskSizeHint = "7T"
	out := renderTemplate(t, d)

	if !strings.Contains(out, `serial: "__ID_SERIAL__"`) {
		t.Error("expected 'serial: \"__ID_SERIAL__\"' in storage match for size-hint mode")
	}
	if !strings.Contains(out, "find_disk.sh --target-size=7T") {
		t.Error("expected 'find_disk.sh --target-size=7T' in early-commands")
	}
	if !strings.Contains(out, `expected_serial="__ID_SERIAL__"`) {
		t.Error("expected serial verification with __ID_SERIAL__ in late-commands")
	}
}

// TestUserData_0xaaBeforeVerify checks that the 0xaa (Installation Complete) IPMI
// marker appears BEFORE the serial verification block in late-commands.
// This ordering ensures the SEL records completion before the disk audit runs.
func TestUserData_0xaaBeforeVerify(t *testing.T) {
	out := renderTemplate(t, defaultData())

	lateStart := strings.Index(out, "late-commands:")
	if lateStart == -1 {
		t.Fatal("late-commands section not found")
	}
	late := out[lateStart:]

	aaIdx := lineIndex(late, "0xaa")
	verifyIdx := lineIndex(late, "ID_SERIAL")

	if aaIdx == -1 {
		t.Fatal("0xaa marker not found in late-commands")
	}
	if verifyIdx == -1 {
		t.Fatal("serial verification (ID_SERIAL) not found in late-commands")
	}
	if aaIdx >= verifyIdx {
		t.Errorf("0xaa (line %d) must appear BEFORE serial verification (line %d)", aaIdx+1, verifyIdx+1)
	}
}

// TestUserData_IPMIMarkers checks that all required IPMI SEL markers are present
// in the correct sections of the generated user-data.
func TestUserData_IPMIMarkers(t *testing.T) {
	out := renderTemplate(t, defaultData())

	earlyEnd := strings.Index(out, "error-commands:")
	lateStart := strings.Index(out, "late-commands:")
	if earlyEnd == -1 || lateStart == -1 {
		t.Fatal("could not locate early-commands or late-commands sections")
	}
	early := out[:earlyEnd]
	late := out[lateStart:]

	earlyMarkers := []string{"0x0F", "0x1F", "0x01"}
	for _, m := range earlyMarkers {
		if !strings.Contains(early, m) {
			t.Errorf("IPMI marker %s missing from early-commands", m)
		}
	}

	lateMarkers := []string{"0x06", "0x16", "0x03", "0x13", "0xaa"}
	for _, m := range lateMarkers {
		if !strings.Contains(late, m) {
			t.Errorf("IPMI marker %s missing from late-commands", m)
		}
	}
}

// TestUserData_SSHConfig checks SSH is configured with install-server, allow-pw,
// and an authorized key.
func TestUserData_SSHConfig(t *testing.T) {
	out := renderTemplate(t, defaultData())

	checks := []struct{ label, needle string }{
		{"install-server: true", "install-server: true"},
		{"allow-pw: true", "allow-pw: true"},
		{"authorized-keys entry", "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA"},
	}
	for _, c := range checks {
		if !strings.Contains(out, c.needle) {
			t.Errorf("SSH config: %s not found", c.label)
		}
	}
}

// TestUserData_StorageLayout checks the partition layout:
//   - EFI partition 512M with boot flag
//   - root partition filling remaining space (size: -1)
//   - EFI formatted as vfat, root as ext4
//   - both partitions mounted at /boot/efi and /
func TestUserData_StorageLayout(t *testing.T) {
	out := renderTemplate(t, defaultData())

	checks := []struct{ label, needle string }{
		{"GPT partition table", "ptable: gpt"},
		{"superblock-recursive wipe", "wipe: superblock-recursive"},
		{"EFI partition 512M", "size: 512M"},
		{"EFI boot flag", "flag: boot"},
		{"EFI vfat format", "fstype: vfat"},
		{"root partition size -1", "size: -1"},
		{"root ext4 format", "fstype: ext4"},
		{"root mount /", "path: /"},
		{"EFI mount /boot/efi", "path: /boot/efi"},
	}
	for _, c := range checks {
		if !strings.Contains(out, c.needle) {
			t.Errorf("storage layout: %s (%q) not found", c.label, c.needle)
		}
	}
}
