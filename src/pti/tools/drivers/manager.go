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
	positDriversOdbcInstIniPath = "/opt/rstudio-drivers/odbcinst.ini.sample"
	odbcInstIniPath             = "/etc/odbcinst.ini"
	driversVersion              = "2024.03.0"
	driversPackageName          = "rstudio-drivers"
)

var proDriversUrl = "https://cdn.posit.co/drivers/7C152C12/installer/%s"

type ProDriversManager struct {
	*system.LocalSystem
	Version                string
	CopyExampleOdbcInstIni bool
}

func NewProDriversManager(l *system.LocalSystem, version string, copyExample bool) *ProDriversManager {
	if version == "" {
		version = driversVersion
	}
	return &ProDriversManager{
		LocalSystem:            l,
		Version:                version,
		CopyExampleOdbcInstIni: copyExample,
	}
}

func getProDriversUrl(l *system.LocalSystem, driversVersion string) (string, error) {
	var packageName string
	switch l.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based distribution")
		packageName = fmt.Sprintf("rstudio-drivers_%s_%s.deb", driversVersion, l.Arch)
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based distribution")
		packageName = fmt.Sprintf("rstudio-drivers-%s-1.el.%s.rpm", driversVersion, l.GetAltArchName())
	default:
		return "", fmt.Errorf("unsupported OS: %s %s", l.Vendor, l.Version)
	}
	slog.Debug("Using package name: " + packageName)
	return fmt.Sprintf(proDriversUrl, packageName), nil
}

func getProDriversDependencies(l *system.LocalSystem) ([]string, error) {
	var packages []string
	switch l.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based distribution")
		packages = []string{"unixodbc", "unixodbc-dev"}
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based distribution")
		packages = []string{"unixODBC", "unixODBC-devel"}
	default:
		return nil, fmt.Errorf("unsupported OS: %s %s", l.Vendor, l.Version)
	}
	slog.Debug("Using driver dependencies: " + strings.Join(packages, ", "))
	return packages, nil
}

func (m *ProDriversManager) Installed() (bool, error) {
	// TODO: Implement an "IsInstalled" method for PackageManager
	//       This will likely require some work with routing command outputs
	return false, fmt.Errorf("not implemented")
}

func (m *ProDriversManager) Install() error {
	slog.Info("Installing Posit Pro Drivers " + driversVersion)

	// Determine driver dependencies if possible and the Drivers package name
	downloadUrl, err := getProDriversUrl(m.LocalSystem, driversVersion)
	if err != nil {
		return fmt.Errorf("failed to determine Posit Pro Drivers download URL: %w", err)
	}
	driverDependencies, err := getProDriversDependencies(m.LocalSystem)
	if err != nil {
		return fmt.Errorf("failed to determine Posit Pro Drivers system dependencies: %w", err)
	}

	slog.Debug("Driver system dependencies to install: " + strings.Join(driverDependencies, ", "))
	slog.Debug("Driver download URL: " + downloadUrl)

	// Download and install the drivers
	downloadTmpDir, err := afero.TempDir(file.AppFs, "", "drivers")
	downloadPath := downloadTmpDir + "/drivers" + m.LocalSystem.PackageManager.GetPackageExtension()
	if err != nil {
		return fmt.Errorf("failed to create temporary download directory for driver package: %w", err)
	}
	defer file.AppFs.RemoveAll(downloadPath)

	slog.Debug("Downloading driver package to: " + downloadPath)
	if err := file.DownloadFile(downloadUrl, downloadPath); err != nil {
		return fmt.Errorf("failed to download pro drivers package from '%s': %w", downloadUrl, err)
	}
	// Install dependencies and then install local package
	if err := m.LocalSystem.PackageManager.Install(&syspkg.PackageList{Packages: driverDependencies, LocalPackages: []string{downloadPath}}); err != nil {
		return fmt.Errorf("failed to install pro drivers package located at '%s': %w", downloadPath, err)
	}
	defer m.LocalSystem.PackageManager.Clean()

	// Copy the odbcinst.ini.sample from the Posit Drivers package
	if m.CopyExampleOdbcInstIni {
		if err := m.CopyProDriversOdbcInstIni(); err != nil {
			return fmt.Errorf("failed to copy example odbcinst.ini file: %w", err)
		}
	}

	return nil
}

func (m *ProDriversManager) CopyProDriversOdbcInstIni() error {
	// Check if the Posit Pro Drivers odbcinst.ini.sample exists
	isFile, err := file.IsFile(positDriversOdbcInstIniPath)
	if err != nil {
		return fmt.Errorf("unable to check whether Posit Pro Drivers odbcinst.ini.sample exists at '%s': %w", positDriversOdbcInstIniPath, err)
	}
	if !isFile {
		slog.Error(fmt.Sprintf("Posit Pro Drivers odbcinst.ini.sample does not exist as expected at '%s'. An installation error may have occurred.", positDriversOdbcInstIniPath))
		return fmt.Errorf("odbcinst.ini.sample does not exist at '%s' as expected", positDriversOdbcInstIniPath)
	}

	isFile, err = file.IsFile(odbcInstIniPath)
	if err != nil {
		slog.Info("No odbcinst.ini detected, backup step will be skipped.")
	}

	// Backup original odbcinst.ini
	if isFile {
		slog.Info("Backing up original odbcinst.ini to " + fmt.Sprintf("%s.bak", odbcInstIniPath))
		if err := file.Move(odbcInstIniPath, fmt.Sprintf("%s.bak", odbcInstIniPath)); err != nil {
			slog.Error("Failed to backup odbcinst.ini, Pro Drivers odbcinst.ini.sample will not be copied.")
			return fmt.Errorf("unable to backup odbcinst.ini: %w", err)
		}
	}

	// Copy the odbcinst.ini.sample from the Posit Drivers package
	slog.Info("Copying Posit Pro Drivers odbcinst.ini.sample to " + odbcInstIniPath)
	if err := file.Copy(positDriversOdbcInstIniPath, odbcInstIniPath); err != nil {
		slog.Error(fmt.Sprintf("Failed to copy %s to %s. Original odbcinst.ini will be restored.", positDriversOdbcInstIniPath, odbcInstIniPath))
		err := file.Move(fmt.Sprintf("%s.bak", odbcInstIniPath), odbcInstIniPath)
		if err != nil {
			slog.Error("Failed to restore original odbcinst.ini.")
		}
		return fmt.Errorf("unable to copy Pro Drivers example ini file from %s to %s: %w", positDriversOdbcInstIniPath, odbcInstIniPath, err)
	}

	return nil
}

func (m *ProDriversManager) Update() error {
	err := m.Remove()
	if err != nil {
		slog.Error("Failed to remove Posit Pro Drivers: " + err.Error())
	}
	return m.Install()
}

func (m *ProDriversManager) Remove() error {
	err := m.LocalSystem.PackageManager.Remove(&syspkg.PackageList{Packages: []string{driversPackageName}})
	if err != nil {
		return fmt.Errorf("failed to uninstall %s: %w", driversPackageName, err)
	}
	return nil
}
