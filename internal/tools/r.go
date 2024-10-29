package tools

import (
	"encoding/json"
	"fmt"
	"github.com/zcalusic/sysinfo"
	"log/slog"
	"net/http"
	"os"
	"posit-images-shared/internal/system"
	"strconv"
	"strings"
)

const rUrlRoot = "https://cdn.posit.co/r"
const rVersionsJsonUrl = rUrlRoot + "/versions.json"
const packageManagerUrl = "https://packagemanager.posit.co"

func InstallR(rVersion string, rPackages *[]string, rPackageFiles *[]string, setDefault bool, addToPath bool) error {
	rInstallationPath := fmt.Sprintf("/opt/R/%s", rVersion)
	rBinPath := fmt.Sprintf("%s/bin/R", rInstallationPath)

	slog.Debug("R version: " + rVersion)
	slog.Debug("R installation path: " + rInstallationPath)
	slog.Debug("R binary path: " + rBinPath)

	slog.Debug("Checking if R " + rVersion + " is installed")
	// Install R if not installed
	if _, err := os.Stat(rBinPath); os.IsNotExist(err) {
		slog.Info("Installing R version " + rVersion)

		validVersion, err := ValidateRVersion(rVersion)
		if err != nil {
			return err
		}
		if !validVersion {
			return fmt.Errorf("R version %s is not supported", rVersion)
		}

		downloadPath, err := FetchRPackage(rVersion)
		if err != nil {
			return err
		}

		if err := system.InstallLocalPackage(downloadPath); err != nil {
			return err
		}

		if err := os.Remove(downloadPath); err != nil {
			return err
		}
	} else {
		slog.Info("R version " + rVersion + " is already installed")
	}

	if len(*rPackages) > 0 {
		if err := installRPackages(rBinPath, rPackages); err != nil {
			return err
		}
	}

	if len(*rPackageFiles) > 0 {
		if err := installRPackagesFiles(rBinPath, rPackageFiles); err != nil {
			return err
		}
	}

	if setDefault {
		if err := SymlinkDefaultR(rInstallationPath); err != nil {
			return err
		}
	}

	if addToPath {
		if err := SymlinkVersionedRToPath(rInstallationPath, rVersion); err != nil {
			return err
		}
	}

	slog.Info("R " + rVersion + " installation finished")

	return nil
}

func InstallRPackages(rBinPath string, rPackages *[]string, rPackageFiles *[]string) error {
	slog.Debug("R binary path: " + rBinPath)

	exists, err := system.PathExists(rBinPath)
	if err != nil {
		return err
	}
	if !exists {
		return fmt.Errorf("R binary does not exist at path %s", rBinPath)
	}

	if len(*rPackages) > 0 {
		if err := installRPackages(rBinPath, rPackages); err != nil {
			return err
		}
	}

	if len(*rPackageFiles) > 0 {
		if err := installRPackagesFiles(rBinPath, rPackageFiles); err != nil {
			return err
		}
	}

	slog.Info("R package installation finished")

	return nil
}

func SymlinkDefaultR(rInstallationPath string) error {
	const defaultRPath = "/opt/R/default"

	slog.Info("Symlinking " + rInstallationPath + " to " + defaultRPath)

	if _, err := os.Lstat(defaultRPath); err == nil {
		slog.Debug("Removing existing symlink at " + defaultRPath)
		if err := os.Remove(defaultRPath); err != nil {
			return err
		}
	}

	if err := os.Symlink(rInstallationPath, defaultRPath); err != nil {
		return err
	}

	return nil
}

func SymlinkVersionedRToPath(rInstallationPath string, rVersion string) error {
	rBinPath := fmt.Sprintf("%s/bin/R", rInstallationPath)
	rScriptBinPath := fmt.Sprintf("%s/bin/Rscript", rInstallationPath)
	symlinkRPath := fmt.Sprintf("/usr/local/bin/R%s", rVersion)
	symlinkRScriptPath := fmt.Sprintf("/usr/local/bin/Rscript%s", rVersion)

	slog.Info("Symlinking " + rBinPath + " to " + symlinkRPath)

	if _, err := os.Lstat(symlinkRPath); err == nil {
		if err := os.Remove(symlinkRPath); err != nil {
			return err
		}
	}
	if err := os.Symlink(rBinPath, symlinkRPath); err != nil {
		return err
	}

	slog.Info("Symlinking " + rScriptBinPath + " to " + symlinkRScriptPath)

	if _, err := os.Lstat(symlinkRScriptPath); err == nil {
		if err := os.Remove(symlinkRScriptPath); err != nil {
			return err
		}
	}
	if err := os.Symlink(rScriptBinPath, symlinkRScriptPath); err != nil {
		return err
	}

	return nil
}

func ValidateRVersion(rVersion string) (bool, error) {
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
		if version == rVersion {
			slog.Debug("R version " + rVersion + " is supported")
			return true, nil
		}
	}

	return false, nil
}

func FetchRPackage(rVersion string) (string, error) {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	var downloadUrl string
	var downloadPath string

	slog.Info("Fetching R package for " + si.OS.Vendor + " " + si.OS.Version)
	switch strings.ToLower(si.OS.Vendor) {
	case "ubuntu":
		slog.Debug("Detected Ubuntu")
		osVersionClean := strings.Replace(si.OS.Version, ".", "", -1)
		osIdentifier := fmt.Sprintf("ubuntu-%s", osVersionClean)
		downloadUrl = fmt.Sprintf("%s/%s/pkgs/r-%s_1_%s.deb", rUrlRoot, osIdentifier, rVersion, si.OS.Architecture)
		downloadPath = fmt.Sprintf("/tmp/R-%s.deb", rVersion)
	case "debian":
		slog.Debug("Detected Debian")
		osIdentifier := fmt.Sprintf("debian-%s", si.OS.Version)
		downloadUrl = fmt.Sprintf("%s/%s/pkgs/r-%s_1_%s.deb", rUrlRoot, osIdentifier, rVersion, si.OS.Architecture)
		downloadPath = fmt.Sprintf("/tmp/R-%s.deb", rVersion)
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based OS")
		rhelVerison, err := strconv.Atoi(si.OS.Version)
		if err != nil {
			return "", err
		}

		var osIdentifier string
		if rhelVerison <= 8 {
			osIdentifier = fmt.Sprintf("centos-%s", si.OS.Version)
		} else {
			osIdentifier = fmt.Sprintf("rhel-%s", si.OS.Version)
		}

		var archIdentifier string
		if si.OS.Architecture == "amd64" {
			archIdentifier = "x86_64"
		} else {
			archIdentifier = si.OS.Architecture
		}

		downloadUrl = fmt.Sprintf("%s/%s/pkgs/R-%s-1-1.%s.rpm", rUrlRoot, osIdentifier, rVersion, archIdentifier)
		downloadPath = fmt.Sprintf("/tmp/R-%s.rpm", rVersion)
	case "fedora":
		slog.Debug("Detected Fedora")
		osIdentifier := fmt.Sprintf("fedora-%s", si.OS.Version)

		var archIdentifier string
		if si.OS.Architecture == "amd64" {
			archIdentifier = "x86_64"
		} else {
			archIdentifier = si.OS.Architecture
		}

		downloadUrl = fmt.Sprintf("%s/%s/pkgs/R-%s-1-1.%s.rpm", rUrlRoot, osIdentifier, rVersion, archIdentifier)
		downloadPath = fmt.Sprintf("/tmp/R-%s.deb", rVersion)
	default:
		return "", fmt.Errorf("unsupported OS: %s %s", si.OS.Vendor, si.OS.Version)
	}

	slog.Debug("Download URL: " + downloadUrl)
	slog.Debug("Destination Path: " + downloadPath)

	err := system.DownloadFile(downloadPath, downloadUrl)
	if err != nil {
		return "", err
	}
	return downloadPath, err
}

func GetPackageManagerCRANMirror() string {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	codeName := ""
	defaultCran := packageManagerUrl + "/cran/latest"

	slog.Info("Getting CRAN mirror for " + si.OS.Vendor + " " + si.OS.Version)

	switch strings.ToLower(si.OS.Vendor) {
	case "ubuntu":
		slog.Debug("Detected Ubuntu")
		switch si.OS.Version {
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
			slog.Warn("No pre-built binaries available for Ubuntu version " + si.OS.Version + ". Packages will be installed from source.")
			return defaultCran
		}
	case "debian":
		slog.Debug("Detected Debian")
		switch si.OS.Version {
		case "10":
			codeName = "bullseye"
			slog.Debug("Using code name " + codeName)
		case "11":
			codeName = "bookworm"
			slog.Debug("Using code name " + codeName)
		default:
			slog.Warn("No pre-built binaries available for Debian version " + si.OS.Version + ". Packages will be installed from source.")
			return defaultCran
		}
	case "centos", "rocky", "rhel":
		slog.Debug("Detected RHEL-based OS")
		switch si.OS.Version {
		case "7":
			codeName = "centos7"
			slog.Debug("Using code name " + codeName)
		case "8", "9":
			codeName = "rhel" + si.OS.Version
			slog.Debug("Using code name " + codeName)
		default:
			slog.Warn("No pre-built binaries available for " + si.OS.Vendor + " version " + si.OS.Version + ". Packages will be installed from source.")
			return defaultCran
		}
	default:
		slog.Warn("No pre-built binaries available for " + si.OS.Vendor + " version " + si.OS.Version + ". Packages will be installed from source.")
		return defaultCran
	}

	return fmt.Sprintf("%s/cran/__linux__/%s/latest", packageManagerUrl, codeName)
}

func installRPackages(rBin string, packages *[]string) error {
	cranRepo := GetPackageManagerCRANMirror()

	slog.Info("Using CRAN mirror: " + cranRepo)

	slog.Info("Installing R packages: " + strings.Join(*packages, ", "))

	quotedPackages := make([]string, len(*packages))
	for i, pkg := range *packages {
		quotedPackages[i] = fmt.Sprintf("\"%s\"", pkg)
	}
	packageList := "c(" + strings.Join(quotedPackages, ", ") + ")"
	args := []string{"--vanilla", "-e", fmt.Sprintf("install.packages(%s, repos = \"%s\", clean = TRUE)", packageList, cranRepo)}
	s := system.NewSysCmd(rBin, &args)
	return s.Execute()
}

func installRPackagesFiles(rBin string, packagesFiles *[]string) error {
	cranRepo := GetPackageManagerCRANMirror()

	slog.Info("Using CRAN mirror: " + cranRepo)

	slog.Debug("Installing R packages: " + strings.Join(*packagesFiles, ", "))

	for _, file := range *packagesFiles {
		slog.Debug("Installing R packages from file: " + file)
		args := []string{"--vanilla", "-e", fmt.Sprintf("install.packages(readLines(\"%s\"), repos = \"%s\", clean = TRUE)", file, cranRepo)}
		s := system.NewSysCmd(rBin, &args)
		if err := s.Execute(); err != nil {
			slog.Error(fmt.Sprintf("Error installing R packages from %s: %v", file, err))
		}
	}

	return nil
}
