package python

import (
	"encoding/json"
	"fmt"
	"github.com/pterm/pterm"
	"github.com/spf13/afero"
	"log/slog"
	"net/http"
	"pti/system"
	"pti/system/file"
	"pti/system/syspkg"
	"slices"
	"strconv"
	"strings"
)

const (
	installPathTpl     = "/opt/python/%s"
	binPathTpl         = "/opt/python/%s/bin/python"
	pipPathTpl         = "/opt/python/%s/bin/pip"
	defaultJupyterPath = "/opt/python/jupyter"
	defaultPythonPath  = "/opt/python/default"
)

var supportedArchitectures = []string{"amd64"}
var supportedVendors = []string{"ubuntu", "debian", "almalinux", "centos", "rockylinux", "rhel"}
var downloadUrl = "https://cdn.posit.co/python/%s/pkgs/%s"
var versionsJsonUrl = "https://cdn.posit.co/python/versions.json"

type Manager struct {
	*system.LocalSystem
	Version          string
	InstallationPath string
	PythonPath       string
	PipPath          string
}

func NewManager(l *system.LocalSystem, version string) (*Manager, error) {
	if version == "" {
		return nil, fmt.Errorf("python version is required")
	}

	installationPath := fmt.Sprintf(installPathTpl, version)
	pyPath := fmt.Sprintf(binPathTpl, version)
	pipPath := fmt.Sprintf(pipPathTpl, version)

	return &Manager{
		LocalSystem:      l,
		Version:          version,
		InstallationPath: installationPath,
		PythonPath:       pyPath,
		PipPath:          pipPath,
	}, nil
}

func (m *Manager) validVersion() (bool, error) {
	type pythonVersionInfo struct {
		Versions []string `json:"python_versions"`
	}

	res, err := http.Get(versionsJsonUrl)
	if err != nil {
		return false, fmt.Errorf("could not fetch python version list from '%s': %w", versionsJsonUrl, err)
	}
	if res.StatusCode != http.StatusOK {
		return false, fmt.Errorf("could not fetch python version list from '%s': unexpected status code %s", versionsJsonUrl, res.Status)
	}
	defer res.Body.Close()

	var pythonVersions pythonVersionInfo
	if err := json.NewDecoder(res.Body).Decode(&pythonVersions); err != nil {
		return false, fmt.Errorf("error occurred while parsing support python versions: %w", err)
	}

	slog.Debug("Supported Python versions: " + strings.Join(pythonVersions.Versions, ", "))
	for _, version := range pythonVersions.Versions {
		if version == m.Version {
			slog.Debug("Python version " + m.Version + " is supported")
			return true, nil
		}
	}

	return false, nil
}

func (m *Manager) validate() error {
	if m.Version == "" {
		return fmt.Errorf("python version is required")
	}
	isValidVersion, err := m.validVersion()
	if err != nil {
		return fmt.Errorf("failed to validate python version: %w", err)
	}
	if !isValidVersion {
		return fmt.Errorf("python version '%s' is not supported", m.Version)
	}
	if m.InstallationPath == "" {
		return fmt.Errorf("python installation path is required")
	}
	if !slices.Contains(supportedVendors, m.LocalSystem.Vendor) {
		return fmt.Errorf("python is currently not supported for %s %s", m.LocalSystem.Vendor, m.LocalSystem.Version)
	}
	if m.LocalSystem.Arch == "" {
		return fmt.Errorf("unable to detect system architecture")
	}
	if !slices.Contains(supportedArchitectures, m.LocalSystem.Arch) {
		return fmt.Errorf("python is currently not supported on %s", m.LocalSystem.Arch)
	}
	return nil
}

func (m *Manager) downloadUrl() (string, error) {
	var url string

	slog.Info("Fetching Python package URL for " + m.LocalSystem.Vendor + " " + m.LocalSystem.Version)

	switch m.LocalSystem.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected " + m.LocalSystem.Vendor)
		osVersionClean := strings.Replace(m.LocalSystem.Version, ".", "", -1)
		osIdentifier := fmt.Sprintf("%s-%s", m.LocalSystem.Vendor, osVersionClean)
		packageName := fmt.Sprintf("python-%s_1_%s.deb", m.Version, m.LocalSystem.Arch)
		url = fmt.Sprintf(downloadUrl, osIdentifier, packageName)
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based OS")
		rhelVersion, err := strconv.Atoi(m.LocalSystem.Version)
		if err != nil {
			return "", fmt.Errorf("could not cast RHEL version '%s' to int: %w", m.LocalSystem.Version, err)
		}

		var osIdentifier string
		if rhelVersion == 8 {
			osIdentifier = fmt.Sprintf("centos-%s", m.LocalSystem.Version)
		} else {
			osIdentifier = fmt.Sprintf("rhel-%s", m.LocalSystem.Version)
		}

		archIdentifier := m.LocalSystem.GetAltArchName()

		packageName := fmt.Sprintf("python-%s-1-1.%s.rpm", m.Version, archIdentifier)
		url = fmt.Sprintf(downloadUrl, osIdentifier, packageName)
	default:
		return "", fmt.Errorf("unsupported OS '%s %s'", m.LocalSystem.Vendor, m.LocalSystem.Version)
	}

	return url, nil
}

func (m *Manager) Installed() (bool, error) {
	slog.Info("Checking if Python " + m.Version + " is installed")
	slog.Debug("Checking for existence of path " + m.PythonPath)
	// TODO: This should check the Package Manager in the future instead or in addition to the install path
	isFile, err := file.IsFile(m.PythonPath)
	if err != nil {
		return false, fmt.Errorf("failed to check for existing python installation at '%s': %w", m.InstallationPath, err)
	}
	return isFile, nil
}

func (m *Manager) Install() error {
	// Check if Python is already installed
	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if python %s is installed: %w", m.Version, err)
	}

	// Install Python if not installed
	if !installed {
		s, _ := pterm.DefaultSpinner.Start("Downloading python " + m.Version + "...")

		// Verify Python version is supported
		err = m.validate()
		if err != nil {
			s.Fail("Download failed.")
			return err
		}

		// Create temporary directory for download
		tmpDir, err := afero.TempDir(file.AppFs, "", "python")
		if err != nil {
			s.Fail("Download failed.")
			return fmt.Errorf("unable to create temporary directory for python download: %w", err)
		}
		downloadPath := tmpDir + "/python" + m.LocalSystem.PackageManager.GetPackageExtension()
		defer file.AppFs.RemoveAll(tmpDir)

		// Download Python package
		slog.Debug("Downloading package to " + downloadPath)
		url, err := m.downloadUrl()
		if err != nil {
			s.Fail("Download failed.")
			return fmt.Errorf("unable to determine download url for python %s on %s %s: %w", m.Version, m.LocalSystem.Vendor, m.LocalSystem.Version, err)
		}
		slog.Debug("Download URL: " + url)
		err = file.DownloadFile(url, downloadPath)
		if err != nil {
			s.Fail("Download failed.")
			return fmt.Errorf("failed to download python %s package: %w", m.Version, err)
		}
		s.Success("Download complete.")

		s, _ = pterm.DefaultSpinner.Start("Installing python " + m.Version + "...")

		// Install Python package
		pkgList := &syspkg.PackageList{LocalPackages: []string{downloadPath}}
		if err := m.LocalSystem.PackageManager.Install(pkgList); err != nil {
			s.Fail("Installation failed.")
			return fmt.Errorf("failed to install python %s: %w", m.Version, err)
		}
		s.Success("Installation complete.")

		slog.Info("Ensuring pip and setuptools are installed and upgraded")
		if err := m.initCorePackages(); err != nil {
			return fmt.Errorf("failed to initialize python core tools: %w", err)
		}
	} else {
		// Skip install if Python is already installed
		slog.Info("Python " + m.Version + " is already installed")
	}

	slog.Info("Python " + m.Version + " installation finished")

	return nil
}

func (m *Manager) makeDefault() error {
	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if python %s is installed: %w", m.Version, err)
	}
	if !installed {
		return fmt.Errorf("python %s is not installed", m.Version)
	}

	exists, err := file.IsPathExist(defaultPythonPath)
	if err != nil {
		return fmt.Errorf("failed to check for default python symlink at '%s': %w", defaultPythonPath, err)
	}
	if exists {
		err = file.AppFs.RemoveAll(defaultPythonPath)
		if err != nil {
			return fmt.Errorf("failed to remove existing default python symlink at '%s': %w", defaultPythonPath, err)
		}
	}

	if err := file.CreateSymlink(m.InstallationPath, defaultPythonPath); err != nil {
		return fmt.Errorf("failed to create python default symlink: %w", err)
	}

	return nil
}

func (m *Manager) addToPath() error {
	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if python %s is installed: %w", m.Version, err)
	}
	if !installed {
		return fmt.Errorf("python %s is not installed", m.Version)
	}

	slog.Info("Adding Python " + m.Version + " to PATH")
	versionedPythonTarget := "/usr/local/bin/python" + m.Version
	versionedPipTarget := "/usr/local/bin/pip" + m.Version

	exists, err := file.IsPathExist(versionedPythonTarget)
	if err != nil {
		return fmt.Errorf("failed to check for existing python symlink: %w", err)
	}
	if exists {
		err = file.AppFs.RemoveAll(versionedPythonTarget)
		if err != nil {
			return fmt.Errorf("failed to remove existing python symlink: %w", err)
		}
	}
	if err := file.CreateSymlink(m.PythonPath, versionedPythonTarget); err != nil {
		return fmt.Errorf("failed to symlink python to path '%s': %w", versionedPythonTarget, err)
	}

	exists, err = file.IsPathExist(versionedPipTarget)
	if err != nil {
		return fmt.Errorf("failed to check for existing python symlink: %w", err)
	}
	if exists {
		err = file.AppFs.RemoveAll(versionedPipTarget)
		if err != nil {
			return fmt.Errorf("failed to remove existing python symlink: %w", err)
		}
	}
	if err := file.CreateSymlink(m.PipPath, versionedPipTarget); err != nil {
		return fmt.Errorf("failed to symlink pip to path '%s': %w", versionedPipTarget, err)
	}

	return nil
}
