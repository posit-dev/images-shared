package r

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"pti/system"
	"pti/system/file"
	"pti/system/syspkg"
	"slices"
	"strconv"
	"strings"

	"github.com/pterm/pterm"
	"github.com/spf13/afero"
)

const (
	packageManagerUrl = "https://p3m.dev"
	installPathTpl    = "/opt/R/%s"
	binPathTpl        = "/opt/R/%s/bin/R"
	rScriptBinPathTpl = "/opt/R/%s/bin/Rscript"
	defaultRPath      = "/opt/R/default"
)

var (
	supportedArchitectures = []string{"amd64", "arm64"}
	supportedVendors       = []string{
		"ubuntu",
		"debian",
		"almalinux",
		"centos",
		"rockylinux",
		"rhel",
	}
	downloadUrl     = "https://cdn.posit.co/r/%s/pkgs/%s"
	versionsJsonUrl = "https://cdn.posit.co/r/versions.json"
)

type Manager struct {
	*system.LocalSystem
	Version          string
	InstallationPath string
	RPath            string
	RscriptPath      string
}

func NewManager(l *system.LocalSystem, version string) *Manager {
	rInstallationPath := fmt.Sprintf(installPathTpl, version)
	rBinPath := fmt.Sprintf(binPathTpl, version)
	rScriptBinPath := fmt.Sprintf(rScriptBinPathTpl, version)

	return &Manager{
		LocalSystem:      l,
		Version:          version,
		InstallationPath: rInstallationPath,
		RPath:            rBinPath,
		RscriptPath:      rScriptBinPath,
	}
}

func (m *Manager) validVersion() (bool, error) {
	type rVersionInfo struct {
		Versions []string `json:"r_versions"`
	}

	res, err := http.Get(versionsJsonUrl) //nolint:gosec
	if err != nil {
		return false, err
	}
	if res.StatusCode != http.StatusOK {
		return false, fmt.Errorf(
			"could not fetch r version list with status code %d",
			res.StatusCode,
		)
	}
	defer res.Body.Close()

	var rVersions rVersionInfo
	if err := json.NewDecoder(res.Body).Decode(&rVersions); err != nil {
		return false, fmt.Errorf("error occurred while parsing supported r versions: %w", err)
	}

	slog.Debug("Supported R versions: " + strings.Join(rVersions.Versions, ", "))

	for _, version := range rVersions.Versions {
		if version == m.Version {
			slog.Debug("R version " + m.Version + " is supported")

			return true, nil
		}
	}

	return false, nil
}

func (m *Manager) validate() error {
	if m.Version == "" {
		return fmt.Errorf("r version is required")
	}
	isValidVersion, err := m.validVersion()
	if err != nil {
		return fmt.Errorf("failed to validate r version: %w", err)
	}
	if !isValidVersion {
		return fmt.Errorf("r version '%s' is not supported", m.Version)
	}
	if m.InstallationPath == "" {
		return fmt.Errorf("r installation path is required")
	}
	if !slices.Contains(supportedVendors, m.LocalSystem.Vendor) {
		return fmt.Errorf(
			"r is currently not supported for %s %s",
			m.LocalSystem.Vendor,
			m.LocalSystem.Version,
		)
	}
	if m.LocalSystem.Arch == "" {
		return fmt.Errorf("unable to detect system architecture")
	}
	if !slices.Contains(supportedArchitectures, m.LocalSystem.Arch) {
		return fmt.Errorf("r is currently not supported on %s", m.LocalSystem.Arch)
	}

	return nil
}

func (m *Manager) downloadUrl() (string, error) {
	var url string

	slog.Info("Fetching R package URL for " + m.LocalSystem.Vendor + " " + m.LocalSystem.Version)
	switch strings.ToLower(m.LocalSystem.Vendor) {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based OS: " + m.LocalSystem.Vendor)
		osVersionClean := strings.ReplaceAll(m.LocalSystem.Version, ".", "")
		osIdentifier := fmt.Sprintf("%s-%s", m.LocalSystem.Vendor, osVersionClean)
		packageName := fmt.Sprintf("r-%s_1_%s.deb", m.Version, m.LocalSystem.Arch)
		url = fmt.Sprintf(downloadUrl, osIdentifier, packageName)
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based OS: " + m.LocalSystem.Vendor)
		rhelVerison, err := strconv.Atoi(m.LocalSystem.Version)
		if err != nil {
			return "", fmt.Errorf("failed to cast RHEL version to int: %w", err)
		}

		var osIdentifier string
		if rhelVerison <= 8 {
			osIdentifier = fmt.Sprintf("centos-%s", m.LocalSystem.Version)
		} else {
			osIdentifier = fmt.Sprintf("rhel-%s", m.LocalSystem.Version)
		}

		archIdentifier := m.LocalSystem.GetAltArchName()
		packageName := fmt.Sprintf("R-%s-1-1.%s.rpm", m.Version, archIdentifier)
		url = fmt.Sprintf(downloadUrl, osIdentifier, packageName)
	default:
		return "", fmt.Errorf("unsupported OS: %s %s", m.LocalSystem.Vendor, m.LocalSystem.Version)
	}

	slog.Debug("Download URL: " + url)

	return url, nil
}

func (m *Manager) Installed() (bool, error) {
	slog.Info("Checking if R " + m.Version + " is installed")
	slog.Debug("Checking for existence of path " + m.RPath)
	// TODO: This should check the Package Manager in the future instead or in addition to the install path
	isFile, err := file.IsFile(m.RPath)
	if err != nil {
		return false, fmt.Errorf(
			"failed to check for existing r installation at '%s': %w",
			m.RPath,
			err,
		)
	}

	return isFile, nil
}

func (m *Manager) Install() error {
	err := m.validate()
	if err != nil {
		return fmt.Errorf("r install failed validation: %w", err)
	}

	// Check if R is already installed
	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if R %s is installed: %w", m.Version, err)
	}

	// Install R if not installed
	if !installed {
		s, _ := pterm.DefaultSpinner.Start("Downloading R " + m.Version + "...")

		// Create temporary directory for download
		tmpDir, err := afero.TempDir(file.AppFs, "", "r")
		if err != nil {
			s.Fail("Download failed.")

			return fmt.Errorf("unable to create temporary directory for r download: %w", err)
		}
		downloadPath := tmpDir + "/r" + m.LocalSystem.PackageManager.GetPackageExtension()
		defer file.AppFs.RemoveAll(tmpDir) //nolint:errcheck

		// Download R package
		slog.Debug("Downloading package to " + downloadPath)
		url, err := m.downloadUrl()
		if err != nil {
			s.Fail("Download failed.")

			return fmt.Errorf(
				"unable to determine download url for r %s on %s %s: %w",
				m.Version,
				m.LocalSystem.Vendor,
				m.LocalSystem.Version,
				err,
			)
		}
		slog.Debug("Downloading R package from " + url)
		err = file.DownloadFile(url, downloadPath)
		if err != nil {
			s.Fail("Download failed.")

			return fmt.Errorf("failed to download r %s package: %w", m.Version, err)
		}
		s.Success("Download complete.")

		s, _ = pterm.DefaultSpinner.Start("Installing R " + m.Version + "...")

		// Update package manager
		if err := m.LocalSystem.PackageManager.Update(); err != nil {
			slog.Error("Failed to update package manager")
			slog.Warn("Continuing with installation...")
		}
		defer m.LocalSystem.PackageManager.Clean() //nolint:errcheck

		// Install R package
		pkgList := &syspkg.PackageList{LocalPackages: []string{downloadPath}}
		if err := m.LocalSystem.PackageManager.Install(pkgList); err != nil {
			s.Fail("Installation failed.")

			return fmt.Errorf("failed to install r %s: %w", m.Version, err)
		}
		s.Success("Installation complete.")
	} else {
		slog.Info("R " + m.Version + " is already installed")
	}

	slog.Info("R " + m.Version + " installation finished")

	return nil
}

func (m *Manager) MakeDefault() error {
	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if r %s is installed: %w", m.Version, err)
	}
	if !installed {
		return fmt.Errorf("r %s is not installed", m.Version)
	}

	exists, err := file.IsPathExist(defaultRPath)
	if err != nil {
		return fmt.Errorf(
			"failed to check for existing default R installation at '%s': %w",
			defaultRPath,
			err,
		)
	}
	if exists {
		err = file.AppFs.RemoveAll(defaultRPath)
		if err != nil {
			return fmt.Errorf(
				"failed to remove existing default R installation at '%s': %w",
				defaultRPath,
				err,
			)
		}
	}

	if err := file.CreateSymlink(m.InstallationPath, defaultRPath); err != nil {
		return fmt.Errorf("failed to create symlink for default R installation: %w", err)
	}

	return nil
}

//nolint:cyclop
func (m *Manager) AddToPath(appendVersion bool) error {
	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if r %s is installed: %w", m.Version, err)
	}
	if !installed {
		return fmt.Errorf("r %s is not installed", m.Version)
	}

	slog.Info("Adding R " + m.Version + " to PATH")
	rTarget := "/usr/local/bin/R"
	rscriptTarget := "/usr/local/bin/Rscript"
	if appendVersion {
		rTarget += m.Version
		rscriptTarget += m.Version
	}

	exists, err := file.IsPathExist(rTarget)
	if err != nil {
		return fmt.Errorf("failed to check for existing python symlink: %w", err)
	}
	if exists {
		err = file.AppFs.RemoveAll(rTarget)
		if err != nil {
			return fmt.Errorf("failed to remove existing python symlink: %w", err)
		}
	}
	if err := file.CreateSymlink(m.RPath, rTarget); err != nil {
		return fmt.Errorf("failed to symlink python to path '%s': %w", rTarget, err)
	}

	exists, err = file.IsPathExist(rscriptTarget)
	if err != nil {
		return fmt.Errorf("failed to check for existing python symlink: %w", err)
	}
	if exists {
		err = file.AppFs.RemoveAll(rscriptTarget)
		if err != nil {
			return fmt.Errorf("failed to remove existing python symlink: %w", err)
		}
	}
	if err := file.CreateSymlink(m.RscriptPath, rscriptTarget); err != nil {
		return fmt.Errorf("failed to symlink pip to path '%s': %w", rscriptTarget, err)
	}

	return nil
}

func (m *Manager) Update() error {
	return fmt.Errorf("not implemented")
}

func (m *Manager) Remove() error {
	l := &syspkg.PackageList{Packages: []string{"r-" + m.Version}}
	if err := m.LocalSystem.PackageManager.Remove(l); err != nil {
		return fmt.Errorf("failed to remove r %s: %w", m.Version, err)
	}

	return nil
}
