package tools

import (
	"encoding/json"
	"fmt"
	"github.com/pterm/pterm"
	"github.com/spf13/afero"
	"log/slog"
	"net/http"
	"pti/system"
	"pti/system/command"
	"pti/system/file"
	"pti/system/syspkg"
	"strconv"
	"strings"
)

const (
	rDownloadUrl      = "https://cdn.posit.co/r/%s/pkgs/r-%s_1_%s.deb"
	rVersionsJsonUrl  = "https://cdn.posit.co/r/versions.json"
	packageManagerUrl = "https://p3m.dev"
	rPathTpl          = "/opt/R/%s"
	rBinPathTpl       = "/opt/R/%s/bin/R"
	rScriptBinPathTpl = "/opt/R/%s/bin/Rscript"
	defaultRPath      = "/opt/R/default"
)

type RInstallOptions struct {
	SetDefault bool
	AddToPath  bool
}

type RManager struct {
	*system.LocalSystem
	Version          string
	InstallationPath string
	RPath            string
	RscriptPath      string
	InstallOptions   *RInstallOptions
}

type RPackageList struct {
	Packages     []string
	PackageFiles []string
}

func NewRManager(l *system.LocalSystem, version string, installOptions *RInstallOptions) (*RManager, error) {
	if version == "" {
		return nil, fmt.Errorf("r version is required")
	}

	if installOptions == nil {
		installOptions = &RInstallOptions{
			SetDefault: false,
			AddToPath:  false,
		}
	}

	rInstallationPath := fmt.Sprintf(rPathTpl, version)
	rBinPath := fmt.Sprintf(rBinPathTpl, rInstallationPath)
	rScriptBinPath := fmt.Sprintf(rScriptBinPathTpl, rInstallationPath)

	return &RManager{
		LocalSystem:      l,
		Version:          version,
		InstallationPath: rInstallationPath,
		RPath:            rBinPath,
		RscriptPath:      rScriptBinPath,
		InstallOptions:   installOptions,
	}, nil
}

func (m *RManager) validVersion() (bool, error) {
	type rVersionInfo struct {
		Versions []string `json:"r_versions"`
	}

	res, err := http.Get(rVersionsJsonUrl)
	if err != nil {
		return false, err
	}
	defer res.Body.Close()

	var rVersions rVersionInfo
	if err := json.NewDecoder(res.Body).Decode(&rVersions); err != nil {
		return false, err
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

func (m *RManager) downloadUrl() (string, error) {
	var downloadUrl string

	slog.Info("Fetching R package URL for " + m.LocalSystem.Vendor + " " + m.LocalSystem.Version)
	switch strings.ToLower(m.LocalSystem.Vendor) {
	case "ubuntu":
		slog.Debug("Detected Ubuntu")
		osVersionClean := strings.Replace(m.LocalSystem.Version, ".", "", -1)
		osIdentifier := fmt.Sprintf("ubuntu-%s", osVersionClean)
		downloadUrl = fmt.Sprintf(rDownloadUrl, osIdentifier, m.Version, m.LocalSystem.Arch)
	case "debian":
		slog.Debug("Detected Debian")
		osIdentifier := fmt.Sprintf("debian-%s", m.LocalSystem.Version)
		downloadUrl = fmt.Sprintf(rDownloadUrl, osIdentifier, m.Version, m.LocalSystem.Arch)
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based OS")
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

		downloadUrl = fmt.Sprintf(rDownloadUrl, osIdentifier, m.Version, archIdentifier)
	case "fedora":
		slog.Debug("Detected Fedora")
		osIdentifier := fmt.Sprintf("fedora-%s", m.LocalSystem.Version)

		archIdentifier := m.LocalSystem.GetAltArchName()

		downloadUrl = fmt.Sprintf(rDownloadUrl, osIdentifier, m.Version, archIdentifier)
	default:
		return "", fmt.Errorf("unsupported OS: %s %s", m.LocalSystem.Vendor, m.LocalSystem.Version)
	}

	slog.Debug("Download URL: " + downloadUrl)

	return downloadUrl, nil
}

func (m *RManager) Installed() (bool, error) {
	slog.Info("Checking if R " + m.Version + " is installed")
	slog.Debug("Checking for existence of path " + m.RPath)
	// TODO: This should check the Package Manager in the future instead or in addition to the install path
	isFile, err := file.IsFile(m.RPath)
	if err != nil {
		return false, fmt.Errorf("failed to check for existing python installation at '%s': %w", err)
	}
	return isFile, nil
}

func (m *RManager) Install() error {
	// Check if R is already installed
	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if R %s is installed: %w", m.Version, err)
	}

	// Install R if not installed
	if !installed {
		s, _ := pterm.DefaultSpinner.Start("Downloading R " + m.Version + "...")

		// Verify R version is supported
		validVersion, err := m.validVersion()
		if err != nil {
			s.Fail("Download failed.")
			return err
		}
		if !validVersion {
			s.Fail("Download failed.")
			return fmt.Errorf("R version %s is not supported", m.Version)
		}

		// Create temporary directory for download
		tmpDir, err := afero.TempDir(file.AppFs, "", "r")
		if err != nil {
			s.Fail("Download failed.")
			return fmt.Errorf("unable to create temporary directory for R download: %w", err)
		}
		downloadPath := tmpDir + "/r" + m.LocalSystem.PackageManager.GetPackageExtension()
		defer file.AppFs.RemoveAll(tmpDir)

		// Download R package
		slog.Debug("Downloading package to " + downloadPath)
		downloadUrl, err := m.downloadUrl()
		if err != nil {
			s.Fail("Download failed.")
			return fmt.Errorf("unable to determine download url for R %s on %s %s: %w", m.Version, m.LocalSystem.Vendor, m.LocalSystem.Version, err)
		}
		slog.Debug("Downloading R package from " + downloadUrl)
		err = file.DownloadFile(downloadUrl, downloadPath)
		if err != nil {
			s.Fail("Download failed.")
			return fmt.Errorf("failed to download R %s package: %w", m.Version, err)
		}
		s.Success("Download complete.")

		s, _ = pterm.DefaultSpinner.Start("Installing R " + m.Version + "...")

		// Install R package
		pkgList := &syspkg.PackageList{LocalPackages: []string{downloadPath}}
		if err := m.LocalSystem.PackageManager.Install(pkgList); err != nil {
			s.Fail("Installation failed.")
			return fmt.Errorf("failed to install R %s: %w", m.Version, err)
		}
		s.Success("Installation complete.")
	} else {
		slog.Info("R " + m.Version + " is already installed")
	}

	if m.InstallOptions.SetDefault {
		if err := m.makeDefault(); err != nil {
			slog.Error("Failed to set R %s as default: %v", m.Version, err)
		}
	}

	if m.InstallOptions.AddToPath {
		if err := m.addToPath(); err != nil {
			slog.Error("Failed to add R %s to PATH: %v", m.Version, err)
		}
	}

	slog.Info("R " + m.Version + " installation finished")
	return nil
}

func (m *RManager) InstallPackages(packageList *RPackageList) error {
	slog.Debug("R binary path: " + m.RPath)

	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if R %s is installed: %w", m.Version, err)
	}
	if !installed {
		return fmt.Errorf("R %s is not installed", m.Version)
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

func (m *RManager) cranMirror() string {
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

func (m *RManager) makeDefault() error {
	exists, err := file.IsPathExist(defaultRPath)
	if err != nil {
		return fmt.Errorf("failed to check for existing default R installation at '%s': %w", defaultRPath, err)
	}
	if exists {
		err = file.AppFs.RemoveAll(defaultRPath)
		if err != nil {
			return fmt.Errorf("failed to remove existing default R installation at '%s': %w", defaultRPath, err)
		}
	}

	if err := file.CreateSymlink(m.InstallationPath, defaultRPath); err != nil {
		return fmt.Errorf("failed to create symlink for default R installation: %w", err)
	}

	return nil
}

func (m *RManager) addToPath() error {
	slog.Info("Adding R " + m.Version + " to PATH")
	versionedRTarget := "/usr/local/bin/R"
	versionedRscriptTarget := "/usr/local/bin/Rscript"
	if !m.InstallOptions.SetDefault {
		versionedRTarget += m.Version
		versionedRscriptTarget += m.Version
	}

	exists, err := file.IsPathExist(versionedRTarget)
	if err != nil {
		return fmt.Errorf("failed to check for existing python symlink: %w", err)
	}
	if exists {
		err = file.AppFs.RemoveAll(versionedRTarget)
		if err != nil {
			return fmt.Errorf("failed to remove existing python symlink: %w", err)
		}
	}
	if err := file.CreateSymlink(m.RPath, versionedRTarget); err != nil {
		return fmt.Errorf("failed to symlink python to path '%s': %w", versionedRTarget, err)
	}

	exists, err = file.IsPathExist(versionedRscriptTarget)
	if err != nil {
		return fmt.Errorf("failed to check for existing python symlink: %w", err)
	}
	if exists {
		err = file.AppFs.RemoveAll(versionedRscriptTarget)
		if err != nil {
			return fmt.Errorf("failed to remove existing python symlink: %w", err)
		}
	}
	if err := file.CreateSymlink(m.RscriptPath, versionedRscriptTarget); err != nil {
		return fmt.Errorf("failed to symlink pip to path '%s': %w", versionedRscriptTarget, err)
	}

	return nil
}
