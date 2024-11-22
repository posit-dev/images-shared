package tools

import (
	"encoding/json"
	"fmt"
	"github.com/zcalusic/sysinfo"
	"log/slog"
	"net/http"
	"os"
	"pti/errors"
	"pti/system"
	"strconv"
	"strings"
)

const pythonUrlRoot = "https://cdn.posit.co/python"
const pythonVersionsJsonUrl = pythonUrlRoot + "/versions.json"

func InstallPython(pythonVersion string, pythonPackages *[]string, pythonRequirementsFiles *[]string, setDefault bool, addKernel bool, addToPath bool) error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	pythonInstallationPath := fmt.Sprintf("/opt/python/%s", pythonVersion)
	pythonBinPath := fmt.Sprintf("%s/bin/python", pythonInstallationPath)

	slog.Debug("Python version: " + pythonVersion)
	slog.Debug("Python installation path: " + pythonInstallationPath)
	slog.Debug("Python binary path: " + pythonBinPath)

	// Install Python if not installed
	if _, err := os.Stat(pythonBinPath); os.IsNotExist(err) {
		slog.Info("Installing Python " + pythonVersion)

		validVersion, err := validatePythonVersion(pythonVersion)
		if err != nil {
			return err
		}
		if !validVersion {
			return &errors.UnsupportedVersionError{Pkg: "python", Version: pythonVersion}
		}

		downloadPath, err := FetchPythonPackage(pythonVersion)
		if err != nil {
			return err
		}

		if err := system.InstallLocalPackage(downloadPath); err != nil {
			return fmt.Errorf(errors.ToolInstallFailedErrorTpl, "python", err)
		}

		if err := os.Remove(downloadPath); err != nil {
			return fmt.Errorf(errors.ToolInstallerRemovalFailedErrorTpl, "python", err)
		}
	} else {
		slog.Info("Python " + pythonVersion + " is already installed")
	}

	if err := PythonCoreModuleSetup(pythonBinPath); err != nil {
		return err
	}

	if len(*pythonPackages) > 0 {
		if err := installPythonPackages(pythonBinPath, pythonPackages, nil); err != nil {
			return err
		}
	}

	if len(*pythonRequirementsFiles) > 0 {
		if err := installPythonPackagesFromFile(pythonBinPath, pythonRequirementsFiles, nil); err != nil {
			return err
		}
	}

	if addKernel {
		machineName := fmt.Sprintf("py%s", pythonVersion)
		displayName := fmt.Sprintf("Python %s", pythonVersion)
		if err := ConfigureIPythonKernel(pythonBinPath, machineName, displayName); err != nil {
			return err
		}
	}

	if setDefault {
		if err := symlinkDefaultPython(pythonInstallationPath); err != nil {
			return err
		}
	}

	if addToPath {
		if err := symlinkVersionedPythonToPath(pythonInstallationPath, pythonVersion); err != nil {
			return err
		}
	}

	slog.Info("Python " + pythonVersion + " installation finished")

	return nil
}

func InstallPythonPackages(pythonBinPath string, pythonPackages *[]string, pythonRequirementsFiles *[]string) error {
	slog.Debug("Python binary path: " + pythonBinPath)

	exists, err := system.IsPathExist(pythonBinPath)
	if err != nil {
		return err
	}
	if !exists {
		return &errors.BinaryDoesNotExistError{Pkg: "python", Path: pythonBinPath}
	}

	if len(*pythonPackages) > 0 {
		if err := installPythonPackages(pythonBinPath, pythonPackages, nil); err != nil {
			return err
		}
	}

	if len(*pythonRequirementsFiles) > 0 {
		if err := installPythonPackagesFromFile(pythonBinPath, pythonRequirementsFiles, nil); err != nil {
			return err
		}
	}

	return nil
}

func InstallJupyter4Workbench(pythonBinPath, jupyterPath string, force bool) error {
	slog.Debug("Python binary path: " + pythonBinPath)
	jupyterPythonBinPath := jupyterPath + "/bin/python"

	// Check if Python is installed
	exists, err := system.IsPathExist(pythonBinPath)
	if err != nil {
		return err
	}
	if !exists {
		return &errors.BinaryDoesNotExistError{Pkg: "python", Path: pythonBinPath}
	}

	// Remove existing Jupyter installation
	if _, err := os.Lstat(jupyterPath); err == nil {
		if force {
			slog.Info("Removing existing Jupyter installation")
			err := os.RemoveAll(jupyterPath)
			if err != nil {
				return fmt.Errorf("failed to remove jupyter installation at %s: %w", jupyterPath, err)
			}
		} else {
			return &errors.AlreadyExistsError{Pkg: "jupyter", Path: jupyterPath}
		}
	}

	// Create a new virtual environment for Jupyter
	slog.Info("Creating a new virtual environment for Jupyter")
	args := []string{"-m", "venv", jupyterPath}
	s := system.NewSysCmd(pythonBinPath, &args)
	if err := s.Execute(); err != nil {
		return fmt.Errorf("failed to create virtual environment for jupyter: %w", err)
	}

	if err := PythonCoreModuleSetup(jupyterPythonBinPath); err != nil {
		return err
	}

	if err := installPythonPackages(jupyterPythonBinPath, &[]string{"jupyterlab", "notebook", "pwb_jupyterlab"}, nil); err != nil {
		return fmt.Errorf("failed to install jupyerlab: %w", err)
	}

	return nil
}

func validatePythonVersion(pythonVersion string) (bool, error) {
	type pythonVersionInfo struct {
		Versions []string `json:"python_versions"`
	}

	res, err := http.Get(pythonVersionsJsonUrl)
	if err != nil {
		return false, fmt.Errorf("failed to fetch python versions from %s: %w", pythonVersionsJsonUrl, err)
	}
	defer res.Body.Close()

	var pythonVersions pythonVersionInfo
	if err := json.NewDecoder(res.Body).Decode(&pythonVersions); err != nil {
		return false, fmt.Errorf("failed to unmarshal valid python versions: %w", err)
	}

	slog.Debug("Supported Python versions: " + strings.Join(pythonVersions.Versions, ", "))
	for _, version := range pythonVersions.Versions {
		if version == pythonVersion {
			slog.Debug("Python version " + pythonVersion + " is supported")
			return true, nil
		}
	}

	return false, nil
}

func symlinkDefaultPython(pythonInstallationPath string) error {
	const defaultPythonPath = "/opt/python/default"
	if _, err := os.Lstat(defaultPythonPath); err == nil {
		if err := os.Remove(defaultPythonPath); err != nil {
			return fmt.Errorf(errors.RemoveExistingSymlinkErrorTpl, defaultPythonPath, err)
		}
	}
	if err := os.Symlink(pythonInstallationPath, defaultPythonPath); err != nil {
		return fmt.Errorf(errors.CreateSymlinkErrorTpl, pythonInstallationPath, defaultPythonPath, err)
	}
	return nil
}

func symlinkVersionedPythonToPath(pythonInstallationPath string, pythonVersion string) error {
	pythonBinPath := pythonInstallationPath + "/bin/python"
	pipBinPath := pythonInstallationPath + "/bin/pip"
	symlinkPythonPath := fmt.Sprintf("/usr/local/bin/python%s", pythonVersion)
	symlinkPipPath := fmt.Sprintf("/usr/local/bin/pip%s", pythonVersion)

	slog.Info("Symlinking " + pythonBinPath + " to " + symlinkPythonPath)

	if _, err := os.Lstat(symlinkPythonPath); err == nil {
		slog.Debug("Removing existing symlink: " + symlinkPythonPath)
		if err := os.Remove(symlinkPythonPath); err != nil {
			return fmt.Errorf(errors.RemoveExistingSymlinkErrorTpl, symlinkPythonPath, err)
		}
	}
	if err := os.Symlink(pythonBinPath, symlinkPythonPath); err != nil {
		return fmt.Errorf(errors.CreateSymlinkErrorTpl, pythonBinPath, symlinkPythonPath, err)
	}

	slog.Info("Symlinking " + pipBinPath + " to " + symlinkPipPath)
	if _, err := os.Lstat(symlinkPipPath); err == nil {
		slog.Debug("Removing existing symlink: " + symlinkPipPath)
		if err := os.Remove(symlinkPipPath); err != nil {
			return fmt.Errorf(errors.RemoveExistingSymlinkErrorTpl, symlinkPipPath, err)
		}
	}
	if err := os.Symlink(pipBinPath, symlinkPipPath); err != nil {
		return fmt.Errorf(errors.CreateSymlinkErrorTpl, pipBinPath, symlinkPipPath, err)
	}

	return nil
}

func FetchPythonPackage(pythonVersion string) (string, error) {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	var downloadUrl string
	var downloadPath string

	slog.Info("Fetching Python package for " + si.OS.Vendor + " " + si.OS.Version)

	switch strings.ToLower(si.OS.Vendor) {
	case "ubuntu":
		slog.Debug("Detected Ubuntu")
		osVersionClean := strings.Replace(si.OS.Version, ".", "", -1)
		osIdentifier := fmt.Sprintf("ubuntu-%s", osVersionClean)
		downloadUrl = fmt.Sprintf("%s/%s/pkgs/python-%s_1_%s.deb", pythonUrlRoot, osIdentifier, pythonVersion, si.OS.Architecture)
		downloadPath = fmt.Sprintf("/tmp/python-%s.deb", pythonVersion)
	case "debian":
		slog.Debug("Detected Debian")
		osIdentifier := fmt.Sprintf("debian-%s", si.OS.Version)
		downloadUrl = fmt.Sprintf("%s/%s/pkgs/python-%s_1_%s.deb", pythonUrlRoot, osIdentifier, pythonVersion, si.OS.Architecture)
		downloadPath = fmt.Sprintf("/tmp/python-%s.deb", pythonVersion)
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based OS")
		rhelVersion, err := strconv.Atoi(si.OS.Version)
		if err != nil {
			return "", fmt.Errorf("failed to parse OS version: %w", err)
		}

		var osIdentifier string
		if rhelVersion == 8 {
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

		downloadUrl = fmt.Sprintf("%s/%s/pkgs/python-%s-1-1.%s.rpm", pythonUrlRoot, osIdentifier, pythonVersion, archIdentifier)
		downloadPath = fmt.Sprintf("/tmp/python-%s.rpm", pythonVersion)
	default:
		return "", &errors.UnsupportedOSError{Vendor: si.OS.Vendor, Version: si.OS.Version}
	}

	slog.Debug("Download URL: " + downloadUrl)
	slog.Debug("Destination Path: " + downloadPath)

	err := system.DownloadFile(downloadPath, downloadUrl)
	if err != nil {
		return "", fmt.Errorf(errors.ToolDownloadFailedErrorTpl, "python", err)
	}

	return downloadPath, err
}

func installPythonPackages(pythonBin string, packages *[]string, installOptions *[]string) error {
	slog.Info("Installing Python package(s): " + strings.Join(*packages, ", "))

	args := []string{"-m", "pip", "install"}
	if installOptions != nil {
		args = append(args, *installOptions...)
	}
	args = append(args, *packages...)
	s := system.NewSysCmd(pythonBin, &args)
	if err := s.Execute(); err != nil {
		return fmt.Errorf("failed to install packages to %s: %w", pythonBin, err)
	}

	if err := PurgePipCache(pythonBin); err != nil {
		return err
	}

	return nil
}

func installPythonPackagesFromFile(pythonBin string, requirementsFiles *[]string, installOptions *[]string) error {
	slog.Info("Installing Python packages from requirements file(s): " + strings.Join(*requirementsFiles, ", "))

	args := []string{"-m", "pip", "install"}
	if installOptions != nil {
		args = append(args, *installOptions...)
	}
	for _, requirementsFile := range *requirementsFiles {
		args = append(args, "-r", requirementsFile)
	}
	s := system.NewSysCmd(pythonBin, &args)
	if err := s.Execute(); err != nil {
		return fmt.Errorf("failed to install requirements files to %s: %w", pythonBin, err)
	}

	if err := PurgePipCache(pythonBin); err != nil {
		return err
	}

	return nil
}

func EnsurePip(pythonBin string) error {
	slog.Debug("Ensuring pip is installed")

	args := []string{"-m", "ensurepip", "--upgrade"}
	s := system.NewSysCmd(pythonBin, &args)
	if err := s.Execute(); err != nil {
		return fmt.Errorf("%s ensurepip failed: %w", pythonBin, err)
	}

	return nil
}

func PurgePipCache(pythonBin string) error {
	slog.Info("Purging pip cache")

	args := []string{"-m", "pip", "cache", "purge"}
	s := system.NewSysCmd(pythonBin, &args)
	if err := s.Execute(); err != nil {
		return fmt.Errorf("failed to purge pip cache for %s: %w", pythonBin, err)
	}

	return nil
}

func PythonCoreModuleSetup(pythonBin string) error {
	err := EnsurePip(pythonBin)
	if err != nil {
		return err
	}

	err = installPythonPackages(pythonBin, &[]string{"pip", "setuptools"}, &[]string{"--upgrade"})
	if err != nil {
		return fmt.Errorf("failed to install pip and setuptools to %s: %w", pythonBin, err)
	}

	err = PurgePipCache(pythonBin)
	if err != nil {
		return err
	}

	return nil
}

func ConfigureIPythonKernel(pythonBin, machineName, displayName string) error {
	slog.Info("Configuring IPython kernel for Python " + pythonBin)

	err := installPythonPackages(pythonBin, &[]string{"ipykernel"}, &[]string{"--upgrade"})
	if err != nil {
		return fmt.Errorf("failed to install ipykernel to %s: %w", pythonBin, err)
	}

	args := []string{"-m", "ipykernel", "install", "--name", machineName, "--display-name", displayName}
	s := system.NewSysCmd(pythonBin, &args)
	if err := s.Execute(); err != nil {
		return fmt.Errorf("failed to configure IPython kernel for %s: %w", pythonBin, err)
	}

	return nil
}
