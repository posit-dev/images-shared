package system

import (
	"bufio"
	"fmt"
	"github.com/zcalusic/sysinfo"
	"log/slog"
	"os"
	"strings"
)

func InstallLocalPackage(packagePath string) error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	switch si.OS.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based distribution, using apt")
		if err := updateApt(); err != nil {
			return err
		}
		if err := installLocalDebPackage(packagePath); err != nil {
			return err
		}
		if err := cleanApt(); err != nil {
			return err
		}
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based distribution, using yum")
		if err := installLocalRpmPackage(packagePath); err != nil {
			return err
		}
		if err := cleanYum(); err != nil {
			return err
		}
	default:
		return fmt.Errorf("unsupported OS: %s %s", si.OS.Vendor, si.OS.Version)
	}

	return nil
}

func ExtractTarGz(archivePath, destinationPath string, options *[]string) error {
	slog.Info("Extracting tar.gz file " + archivePath + " to " + destinationPath)

	args := []string{"-C", destinationPath, "-xvzf", archivePath}
	args = append(args, *options...)
	cmd := NewSysCmd("tar", &args)
	if err := cmd.Execute(); err != nil {
		return err
	}

	return nil
}

func InstallPackages(packages *[]string) error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	switch si.OS.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based distribution, using apt")
		if err := updateApt(); err != nil {
			return err
		}
		if err := installDebPackages(packages); err != nil {
			return err
		}
		if err := cleanApt(); err != nil {
			return err
		}
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based distribution, using yum")
		if err := installRpmPackages(packages); err != nil {
			return err
		}
		if err := cleanYum(); err != nil {
			return err
		}
	default:
		return fmt.Errorf("unsupported OS: %s %s", si.OS.Vendor, si.OS.Version)
	}

	return nil
}

func InstallPackagesFiles(packageFiles *[]string) error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	switch si.OS.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based distribution, using apt")
		if err := updateApt(); err != nil {
			return err
		}
		if err := installDebPackagesFiles(packageFiles); err != nil {
			return err
		}
		if err := cleanApt(); err != nil {
			return err
		}
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based distribution, using yum")
		if err := installRpmPackagesFiles(packageFiles); err != nil {
			return err
		}
		if err := cleanYum(); err != nil {
			return err
		}
	default:
		return fmt.Errorf("unsupported OS: %s %s", si.OS.Vendor, si.OS.Version)
	}

	return nil
}

func RemovePackages(packages *[]string) error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	switch si.OS.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based distribution, using apt")
		if err := removeDebPackages(packages); err != nil {
			return err
		}
		if err := cleanApt(); err != nil {
			return err
		}
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based distribution, using yum")
		if err := removeRpmPackages(packages); err != nil {
			return err
		}
		if err := cleanYum(); err != nil {
			return err
		}
	default:
		return fmt.Errorf("unsupported OS: %s %s", si.OS.Vendor, si.OS.Version)
	}

	return nil
}

func UpgradePackages(distUpgrade bool) error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	switch si.OS.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based distribution, using apt")
		if err := updateApt(); err != nil {
			return err
		}
		if err := upgradeApt(); err != nil {
			return err
		}
		if distUpgrade {
			if err := distUpgradeApt(); err != nil {
				return err
			}
		}
		if err := cleanApt(); err != nil {
			return err
		}
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based distribution, using yum")
		if distUpgrade {
			slog.Warn("yum does not support dist-upgrade, --dist will be ignored")
		}
		if err := upgradeYum(); err != nil {
			return err
		}
		if err := cleanYum(); err != nil {
			return err
		}
	default:
		return fmt.Errorf("unsupported OS: %s %s", si.OS.Vendor, si.OS.Version)
	}

	return nil
}

func UpdatePackageLists() error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	switch si.OS.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based distribution, using apt")
		if err := updateApt(); err != nil {
			return err
		}
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based distribution, using yum")
		slog.Warn("yum does not require updating package lists")
	default:
		return fmt.Errorf("unsupported OS: %s %s", si.OS.Vendor, si.OS.Version)
	}

	return nil
}

func CleanPackages() error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	switch si.OS.Vendor {
	case "ubuntu", "debian":
		slog.Debug("Detected Debian-based distribution, using apt")
		if err := cleanApt(); err != nil {
			return err
		}
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based distribution, using yum")
		if err := cleanYum(); err != nil {
			return err
		}
	default:
		return fmt.Errorf("unsupported OS: %s %s", si.OS.Vendor, si.OS.Version)
	}

	return nil
}

func updateApt() error {
	slog.Info("Updating package lists for apt")

	s := NewSysCmd("apt-get", &[]string{"update", "-q"})
	return s.Execute()
}

func upgradeApt() error {
	slog.Info("Upgrading installed packages for apt")

	s := NewSysCmd("apt-get", &[]string{"upgrade", "-y", "-q"})
	return s.Execute()
}

func distUpgradeApt() error {
	slog.Info("Running dist-upgrade for apt")

	s := NewSysCmd("apt-get", &[]string{"dist-upgrade", "-y", "-q"})
	return s.Execute()
}

func installLocalDebPackage(packagePath string) error {
	slog.Info("Installing local deb package: " + packagePath)

	args := []string{"install", "-y", "-q", packagePath}
	s := NewSysCmd("apt-get", &args)
	return s.Execute()
}

func installDebPackages(packages *[]string) error {
	slog.Info("Installing deb packages: " + strings.Join(*packages, ", "))

	args := append([]string{"install", "-y", "-q"}, *packages...)
	s := NewSysCmd("apt-get", &args)
	return s.Execute()
}

func installDebPackagesFiles(packagesFiles *[]string) error {
	slog.Info("Installing deb packages from file(s): " + strings.Join(*packagesFiles, ", "))

	for _, packagesFile := range *packagesFiles {
		slog.Info("Installing packages from file: " + packagesFile)

		fh, err := os.Open(packagesFile)
		if err != nil {
			return err
		}
		defer fh.Close()

		var lines []string
		scanner := bufio.NewScanner(fh)
		for scanner.Scan() {
			lines = append(lines, strings.TrimSpace(scanner.Text()))
		}
		if err := scanner.Err(); err != nil {
			return err
		}

		if err := installDebPackages(&lines); err != nil {
			return err
		}
	}
	return nil
}

func removeDebPackages(packages *[]string) error {
	slog.Info("Removing deb packages: " + strings.Join(*packages, ", "))

	args := append([]string{"remove", "-y", "-q"}, *packages...)
	s := NewSysCmd("apt-get", &args)
	return s.Execute()
}

func cleanApt() error {
	slog.Info("Cleaning up apt")

	s := NewSysCmd("apt-get", &[]string{"autoremove", "-y", "-q"})
	if err := s.Execute(); err != nil {
		return err
	}

	s = NewSysCmd("apt-get", &[]string{"clean", "-q"})
	if err := s.Execute(); err != nil {
		return err
	}

	s = NewSysCmd("rm", &[]string{"-rf", "/var/lib/apt/lists"})
	if err := s.Execute(); err != nil {
		return err
	}

	slog.Debug("Removing /var/lib/apt/lists")
	err := os.RemoveAll("/var/lib/apt/lists")
	if err != nil {
		if os.IsNotExist(err) {
			slog.Debug("/var/lib/apt/lists does not exist")
		} else {
			return err
		}
	}

	return nil
}

func upgradeYum() error {
	slog.Info("Upgrading installed packages for yum")

	s := NewSysCmd("yum", &[]string{"upgrade", "-y", "-q"})
	return s.Execute()
}

func installLocalRpmPackage(packagePath string) error {
	slog.Info("Installing local rpm package: " + packagePath)

	args := []string{"install", "-y", "-q", packagePath}
	s := NewSysCmd("yum", &args)
	return s.Execute()
}

func installRpmPackages(packages *[]string) error {
	slog.Info("Installing rpm packages: " + strings.Join(*packages, ", "))

	args := append([]string{"install", "-y", "-q"}, *packages...)
	s := NewSysCmd("yum", &args)
	return s.Execute()
}

func installRpmPackagesFiles(packagesFiles *[]string) error {
	slog.Info("Installing rpm packages from file(s): " + strings.Join(*packagesFiles, ", "))

	for _, packagesFile := range *packagesFiles {
		slog.Info("Installing packages from file: " + packagesFile)

		fh, err := os.Open(packagesFile)
		if err != nil {
			return err
		}
		defer fh.Close()

		var lines []string
		scanner := bufio.NewScanner(fh)
		for scanner.Scan() {
			lines = append(lines, scanner.Text())
		}
		if err := scanner.Err(); err != nil {
			return err
		}

		if err := installRpmPackages(&lines); err != nil {
			return err
		}
	}
	return nil
}

func removeRpmPackages(packages *[]string) error {
	slog.Info("Removing rpm packages: " + strings.Join(*packages, ", "))

	args := append([]string{"remove", "-y", "-q"}, *packages...)
	s := NewSysCmd("yum", &args)
	return s.Execute()
}

func cleanYum() error {
	slog.Info("Cleaning up yum")

	s := NewSysCmd("yum", &[]string{"autoremove", "-y", "-q"})
	if err := s.Execute(); err != nil {
		slog.Error(fmt.Sprintf("Failed to autoremove packages: %v", err))
	}

	s = NewSysCmd("yum", &[]string{"clean", "all"})
	if err := s.Execute(); err != nil {
		slog.Error(fmt.Sprintf("Failed to clean yum cache: %v", err))
	}

	return nil
}
