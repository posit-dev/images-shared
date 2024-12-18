package drivers

import (
	"fmt"
	"github.com/spf13/afero"
	"log/slog"
	"pti/system"
	"pti/system/file"
	"pti/system/syspkg"
	"strings"
)

const (
	defaultVersion = "2024.03.0"
	packageName    = "rstudio-drivers"
)

var downloadUrl = "https://cdn.posit.co/drivers/7C152C12/installer/%s"

type Manager struct {
	*system.LocalSystem
	Version string
}

func NewManager(l *system.LocalSystem, version string) *Manager {
	if version == "" {
		version = defaultVersion
	}
	return &Manager{
		LocalSystem: l,
		Version:     version,
	}
}

func (m *Manager) downloadUrl() (string, error) {
	var packageName string
	switch m.LocalSystem.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based distribution")
		packageName = fmt.Sprintf("rstudio-drivers_%s_%s.deb", m.Version, m.LocalSystem.Arch)
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based distribution")
		packageName = fmt.Sprintf("rstudio-drivers-%s-1.el.%s.rpm", m.Version, m.LocalSystem.GetAltArchName())
	default:
		return "", fmt.Errorf("unsupported OS: %s %s", m.LocalSystem.Vendor, m.LocalSystem.Version)
	}
	slog.Debug("Using package name: " + packageName)
	return fmt.Sprintf(downloadUrl, packageName), nil
}

func (m *Manager) dependencies() (*syspkg.PackageList, error) {
	var packages []string
	switch m.LocalSystem.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based distribution")
		packages = []string{"unixodbc", "unixodbc-dev"}
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based distribution")
		packages = []string{"unixODBC", "unixODBC-devel"}
	default:
		return nil, fmt.Errorf("unsupported OS: %s %s", m.LocalSystem.Vendor, m.LocalSystem.Version)
	}
	slog.Debug("Using driver dependencies: " + strings.Join(packages, ", "))
	return &syspkg.PackageList{Packages: packages}, nil
}

func (m *Manager) Installed() (bool, error) {
	// TODO: Implement an "IsInstalled" method for PackageManager
	//       This will likely require some work with routing command outputs
	return false, fmt.Errorf("not implemented")
}

func (m *Manager) Install() error {
	slog.Info("Installing Posit Pro Drivers " + defaultVersion)

	// Determine driver dependencies if possible and the Drivers package name
	url, err := m.downloadUrl()
	if err != nil {
		return fmt.Errorf("failed to determine Posit Pro Drivers download URL: %w", err)
	}
	driverPackages, err := m.dependencies()
	if err != nil {
		return fmt.Errorf("failed to determine Posit Pro Drivers system dependencies: %w", err)
	}

	slog.Debug("Driver system dependencies to install: " + strings.Join(driverPackages.Packages, ", "))
	slog.Debug("Driver download URL: " + url)

	// Download and install the drivers
	downloadTmpDir, err := afero.TempDir(file.AppFs, "", "drivers")
	downloadPath := downloadTmpDir + "/drivers" + m.LocalSystem.PackageManager.GetPackageExtension()
	if err != nil {
		return fmt.Errorf("failed to create temporary download directory for driver package: %w", err)
	}
	defer file.AppFs.RemoveAll(downloadPath)

	slog.Debug("Downloading driver package to: " + downloadPath)
	if err := file.DownloadFile(url, downloadPath); err != nil {
		return fmt.Errorf("failed to download pro drivers package from '%s': %w", url, err)
	}
	driverPackages.LocalPackages = []string{downloadPath}
	// Install dependencies and then install local package
	if err := m.LocalSystem.PackageManager.Install(driverPackages); err != nil {
		return fmt.Errorf("failed to install pro drivers package located at '%s': %w", downloadPath, err)
	}
	defer m.LocalSystem.PackageManager.Clean()

	return nil
}

func (m *Manager) Update() error {
	err := m.Remove()
	if err != nil {
		slog.Error("Failed to remove Posit Pro Drivers: " + err.Error())
	}
	return m.Install()
}

func (m *Manager) Remove() error {
	err := m.LocalSystem.PackageManager.Remove(&syspkg.PackageList{Packages: []string{packageName}})
	if err != nil {
		return fmt.Errorf("failed to uninstall %s: %w", packageName, err)
	}
	return nil
}
