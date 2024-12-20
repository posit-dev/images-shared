package r

import (
	"fmt"
	"log/slog"
	"pti/system/command"
	"strings"
)

type PackageList struct {
	Packages     []string
	PackageFiles []string
}

func (m *Manager) InstallPackages(packageList *PackageList) error {
	slog.Debug("R binary path: " + m.RPath)

	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if R %s is installed: %w", m.Version, err)
	}
	if !installed {
		return fmt.Errorf("r %s is not installed", m.Version)
	}

	cranRepo := m.cranMirror()

	slog.Info("Using CRAN mirror: " + cranRepo)

	if len(packageList.Packages) > 0 {

		slog.Info("Installing R packages: " + strings.Join(packageList.Packages, ", "))

		quotedPackages := make([]string, len(packageList.Packages))
		for i, pkg := range packageList.Packages {
			quotedPackages[i] = fmt.Sprintf("\"%s\"", pkg)
		}
		wrappedList := "c(" + strings.Join(quotedPackages, ", ") + ")"
		args := []string{"--vanilla", "-e", fmt.Sprintf("install.packages(%s, repos = \"%s\", clean = TRUE)", wrappedList, cranRepo)}
		s := command.NewShellCommand(m.RPath, args, nil, true)
		err = s.Run()
		if err != nil {
			return fmt.Errorf("failed to install R packages: %w", err)
		}
	}

	if len(packageList.PackageFiles) > 0 {
		slog.Debug("Installing R packages: " + strings.Join(packageList.PackageFiles, ", "))

		for _, packageListFile := range packageList.PackageFiles {
			slog.Debug("Installing R packages from file: " + packageListFile)
			args := []string{"--vanilla", "-e", fmt.Sprintf("install.packages(readLines(\"%s\"), repos = \"%s\", clean = TRUE)", packageListFile, cranRepo)}
			s := command.NewShellCommand(m.RPath, args, nil, true)
			if err := s.Run(); err != nil {
				slog.Error(fmt.Sprintf("Error installing R packages from %s: %v", packageListFile, err))
			}
		}
	}

	return nil
}

func (m *Manager) cranMirror() string {
	codeName := ""
	defaultCran := packageManagerUrl + "/cran/latest"

	slog.Info("Getting CRAN mirror for " + m.LocalSystem.Vendor + " " + m.LocalSystem.Version)

	switch strings.ToLower(m.LocalSystem.Vendor) {
	case "ubuntu":
		slog.Debug("Detected Ubuntu")
		switch m.LocalSystem.Version {
		case "20.04":
			codeName = "focal"
			slog.Debug("Using code name " + codeName)
		case "22.04":
			codeName = "jammy"
			slog.Debug("Using code name " + codeName)
		case "24.04":
			codeName = "noble"
			slog.Debug("Using code name " + codeName)
		default:
			slog.Warn(fmt.Sprintf("No pre-built binaries available for %s %s. Packages will be installed from source.", m.LocalSystem.Vendor, m.LocalSystem.Version))
			return defaultCran
		}
	case "debian":
		slog.Debug("Detected Debian")
		switch m.LocalSystem.Version {
		case "10":
			codeName = "bullseye"
			slog.Debug("Using code name " + codeName)
		case "11":
			codeName = "bookworm"
			slog.Debug("Using code name " + codeName)
		default:
			slog.Warn(fmt.Sprintf("No pre-built binaries available for %s %s. Packages will be installed from source.", m.LocalSystem.Vendor, m.LocalSystem.Version))
			return defaultCran
		}
	case "centos", "rocky", "rhel":
		slog.Debug("Detected RHEL-based OS")
		switch m.LocalSystem.Version {
		case "7":
			codeName = "centos7"
			slog.Debug("Using code name " + codeName)
		case "8", "9":
			codeName = "rhel" + m.LocalSystem.Version
			slog.Debug("Using code name " + codeName)
		default:
			slog.Warn(fmt.Sprintf("No pre-built binaries available for %s %s. Packages will be installed from source.", m.LocalSystem.Vendor, m.LocalSystem.Version))
			return defaultCran
		}
	default:
		slog.Warn(fmt.Sprintf("No pre-built binaries available for %s %s. Packages will be installed from source.", m.LocalSystem.Vendor, m.LocalSystem.Version))
		return defaultCran
	}

	return fmt.Sprintf("%s/cran/__linux__/%s/latest", packageManagerUrl, codeName)
}
