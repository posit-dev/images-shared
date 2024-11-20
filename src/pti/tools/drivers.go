package tools

import (
	"fmt"
	"github.com/zcalusic/sysinfo"
	"log/slog"
	"os"
	"pti/system"
	"strings"
)

const proDriversUrl = "https://cdn.posit.co/drivers/7C152C12/installer"

func InstallProDrivers(driversVersion string) error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	slog.Info("Installing Posit Pro Drivers " + driversVersion)

	// Determine driver dependencies if possible and the Drivers package name
	var driverDependencies []string
	var packageName string
	var downloadUrl string
	switch si.OS.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based distribution")
		driverDependencies = []string{"unixodbc", "unixodbc-dev"}
		packageName = fmt.Sprintf("rstudio-drivers_%s_%s.deb", driversVersion, si.OS.Architecture)
		downloadUrl = fmt.Sprintf("%s/%s", proDriversUrl, packageName)
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based distribution")
		driverDependencies = []string{"unixODBC", "unixODBC-devel"}

		architecture := si.OS.Architecture
		if si.OS.Architecture == "amd64" {
			architecture = "x86_64"
		}

		packageName = fmt.Sprintf("rstudio-drivers-%s-1.el.%s.rpm", driversVersion, architecture)
		downloadUrl = fmt.Sprintf("%s/%s", proDriversUrl, packageName)
	default:
		return fmt.Errorf("unsupported OS: %s %s", si.OS.Vendor, si.OS.Version)
	}

	slog.Debug("Driver system dependencies to install: " + strings.Join(driverDependencies, ", "))
	slog.Debug("Driver download URL: " + downloadUrl)

	// Install the driver dependencies
	if err := system.InstallPackages(&driverDependencies); err != nil {
		return err
	}

	// Download and install the drivers
	downloadPath := fmt.Sprintf("/tmp/%s", packageName)
	slog.Debug("Downloading driver package to: " + downloadPath)
	if err := system.DownloadFile(downloadPath, downloadUrl); err != nil {
		return err
	}
	if err := system.InstallLocalPackage(downloadPath); err != nil {
		return err
	}

	// Clean up the downloaded package
	if err := os.Remove(downloadPath); err != nil {
		return err
	}

	// Copy the odbcinst.ini.sample from the Posit Drivers package
	if err := CopyProDriversOdbcInstIni(); err != nil {
		return err
	}

	return nil
}

func CopyProDriversOdbcInstIni() error {
	const positDriversOdbcInstIniPath = "/opt/rstudio-drivers/odbcinst.ini.sample"
	const odbcInstIniPath = "/etc/odbcinst.ini"

	// Backup original odbcinst.ini
	slog.Info("Backing up original odbcinst.ini to " + fmt.Sprintf("%s.bak", odbcInstIniPath))
	if err := system.MoveFile(odbcInstIniPath, fmt.Sprintf("%s.bak", odbcInstIniPath)); err != nil {
		return err
	}

	// Copy the odbcinst.ini.sample from the Posit Drivers package
	slog.Info("Copying Posit Pro Drivers odbcinst.ini.sample to " + odbcInstIniPath)
	if err := system.CopyFile(positDriversOdbcInstIniPath, odbcInstIniPath); err != nil {
		return err
	}

	return nil
}
