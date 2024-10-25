package system

import (
	"bufio"
	"fmt"
	"github.com/zcalusic/sysinfo"
	"log/slog"
	"os"
	"os/exec"
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
	cmd := exec.Command("tar", args...)
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
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

	cmd := exec.Command("apt-get", "update", "-q")
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
}

func upgradeApt() error {
	slog.Info("Upgrading installed packages for apt")

	cmd := exec.Command("apt-get", "upgrade", "-y", "-q")
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
}

func distUpgradeApt() error {
	slog.Info("Running dist-upgrade for apt")

	cmd := exec.Command("apt-get", "dist-upgrade", "-y", "-q")
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
}

func installLocalDebPackage(packagePath string) error {
	slog.Info("Installing local deb package: " + packagePath)

	args := []string{"install", "-y", "-q", packagePath}
	cmd := exec.Command("apt-get", args...)
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
}

func installDebPackages(packages *[]string) error {
	slog.Info("Installing deb packages: " + strings.Join(*packages, ", "))

	args := append([]string{"install", "-y", "-q"}, *packages...)
	cmd := exec.Command("apt-get", args...)
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
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
			lines = append(lines, scanner.Text())
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
	cmd := exec.Command("apt-get", args...)
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
}

func cleanApt() error {
	slog.Info("Cleaning up apt")

	cmd := exec.Command("apt-get", "autoremove", "-y", "-q")
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	cmd = exec.Command("apt-get", "clean", "-q")
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
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

	cmd := exec.Command("yum", "update", "-y", "-q")
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
}

func installLocalRpmPackage(packagePath string) error {
	slog.Info("Installing local rpm package: " + packagePath)

	args := []string{"install", "-y", "-q", packagePath}
	cmd := exec.Command("yum", args...)
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
}

func installRpmPackages(packages *[]string) error {
	slog.Info("Installing rpm packages: " + strings.Join(*packages, ", "))

	args := append([]string{"install", "-y", "-q"}, *packages...)
	cmd := exec.Command("yum", args...)
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
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
	cmd := exec.Command("yum", args...)
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
}

func cleanYum() error {
	slog.Info("Cleaning up yum")

	cmd := exec.Command("yum", "autoremove", "-y", "-q")
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	cmd = exec.Command("yum", "clean", "all")
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
}
