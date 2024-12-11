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
	pythonDownloadUrl     = "https://cdn.posit.co/python/%s/pkgs/python-%s_1_%s.deb"
	pythonVersionsJsonUrl = "https://cdn.posit.co/python/versions.json"
	pythonPathTpl         = "/opt/python/%s"
	pythonBinPathTpl      = "/opt/python/%s/bin/python"
	pipPathTpl            = "/opt/python/%s/bin/pip"
	jupyterPath           = "/opt/jupyter"
	defaultPythonPath     = "/opt/python/default"
)

type PythonInstallOptions struct {
	SetDefault bool
	AddKernel  bool
	AddToPath  bool
}

type PythonManager struct {
	*system.LocalSystem
	Version          string
	InstallationPath string
	PythonPath       string
	PipPath          string
	InstallOptions   *PythonInstallOptions
}

type PythonPackageList struct {
	Packages     []string
	PackageFiles []string
}

func NewPythonManager(l *system.LocalSystem, version string, installOptions *PythonInstallOptions) (*PythonManager, error) {
	if version == "" {
		return nil, fmt.Errorf("python version is required")
	}

	if installOptions == nil {
		installOptions = &PythonInstallOptions{
			SetDefault: false,
			AddKernel:  false,
			AddToPath:  false,
		}
	}

	installationPath := fmt.Sprintf(pythonPathTpl, version)
	pyPath := fmt.Sprintf(pythonBinPathTpl, version)
	pipPath := fmt.Sprintf(pipPathTpl, version)

	return &PythonManager{
		LocalSystem:      l,
		Version:          version,
		InstallationPath: installationPath,
		PythonPath:       pyPath,
		PipPath:          pipPath,
		InstallOptions:   installOptions,
	}, nil
}

func (m *PythonManager) validVersion() (bool, error) {
	type pythonVersionInfo struct {
		Versions []string `json:"python_versions"`
	}

	res, err := http.Get(pythonVersionsJsonUrl)
	if err != nil {
		return false, err
	}
	defer res.Body.Close()

	var pythonVersions pythonVersionInfo
	if err := json.NewDecoder(res.Body).Decode(&pythonVersions); err != nil {
		return false, err
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

func (m *PythonManager) downloadUrl() (string, error) {
	var downloadUrl string

	slog.Info("Fetching Python package URL for " + m.LocalSystem.Vendor + " " + m.LocalSystem.Version)

	switch m.LocalSystem.Vendor {
	case "ubuntu":
		slog.Debug("Detected Ubuntu")
		osVersionClean := strings.Replace(m.LocalSystem.Version, ".", "", -1)
		osIdentifier := fmt.Sprintf("ubuntu-%s", osVersionClean)
		downloadUrl = fmt.Sprintf(pythonDownloadUrl, osIdentifier, m.Version, m.LocalSystem.Arch)
	case "debian":
		slog.Debug("Detected Debian")
		osIdentifier := fmt.Sprintf("debian-%s", m.LocalSystem.Version)
		downloadUrl = fmt.Sprintf(pythonDownloadUrl, osIdentifier, m.Version, m.LocalSystem.Arch)
	case "almalinux", "centos", "rockylinux", "rhel":
		slog.Debug("Detected RHEL-based OS")
		rhelVersion, err := strconv.Atoi(m.LocalSystem.Version)
		if err != nil {
			return "", fmt.Errorf("could not cast RHEL version '%s' to int: %w", m.LocalSystem.Version, err)
		}

		var osIdentifier string
		if rhelVersion == 8 {
			osIdentifier = fmt.Sprintf("centos-%s", m.Version)
		} else {
			osIdentifier = fmt.Sprintf("rhel-%s", m.Version)
		}

		archIdentifier := m.LocalSystem.GetAltArchName()

		downloadUrl = fmt.Sprintf(pythonDownloadUrl, osIdentifier, m.Version, archIdentifier)
	default:
		return "", fmt.Errorf("unsupported OS '%s %s'", m.Vendor, m.Version)
	}

	return downloadUrl, nil
}

func (m *PythonManager) Installed() (bool, error) {
	slog.Info("Checking if Python " + m.Version + " is installed")
	slog.Debug("Checking for existence of path " + m.PythonPath)
	// TODO: This should check the Package Manager in the future instead or in addition to the install path
	isFile, err := file.IsFile(m.PythonPath)
	if err != nil {
		return false, fmt.Errorf("failed to check for existing python installation at '%s': %w", err)
	}
	return isFile, nil
}

func (m *PythonManager) Install() error {
	// Check if Python is already installed
	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if python %s is installed: %w", m.Version, err)
	}

	// Install Python if not installed
	if !installed {
		s, _ := pterm.DefaultSpinner.Start("Downloading python " + m.Version + "...")

		// Verify Python version is supported
		validVersion, err := m.validVersion()
		if err != nil {
			s.Fail("Download failed.")
			return err
		}
		if !validVersion {
			s.Fail("Download failed.")
			return fmt.Errorf("python version '%s' is not supported", m.Version)
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
		downloadUrl, err := m.downloadUrl()
		if err != nil {
			s.Fail("Download failed.")
			return fmt.Errorf("unable to determine download url for python %s on %s %s: %w", m.Version, m.LocalSystem.Vendor, m.LocalSystem.Version, err)
		}
		slog.Debug("Download URL: " + downloadUrl)
		err = file.DownloadFile(downloadUrl, downloadPath)
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
	} else {
		// Skip install if Python is already installed
		slog.Info("Python " + m.Version + " is already installed")
	}

	if err := m.initializePythonCoreTools(); err != nil {
		return fmt.Errorf("failed to initialize python core tools: %w", err)
	}

	if m.InstallOptions.AddKernel {
		if err := m.addJupyterKernel(); err != nil {
			slog.Error("Failed to add Jupyter kernel for Python " + m.Version)
			slog.Error(err.Error())
		}
	}

	if m.InstallOptions.SetDefault {
		if err := m.makeDefault(); err != nil {
			slog.Error("Failed to set Python %s as default Python version: %v", m.Version, err)
		}
	}

	if m.InstallOptions.AddToPath {
		if err := m.addToPath(); err != nil {
			slog.Error("Failed to add Python %s to PATH: %v", m.Version, err)
		}
	}

	slog.Info("Python " + m.Version + " installation finished")

	return nil
}

func (m *PythonManager) InstallPackages(packageList *PythonPackageList, options []string) error {
	slog.Debug("Python binary path: " + m.PythonPath)

	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if Python %s is installed: %w", m.Version, err)
	}
	if !installed {
		return fmt.Errorf("python %s is not installed", m.Version)
	}

	defer m.Clean()

	for _, name := range packageList.Packages {
		slog.Info("Installing Python package " + name)

		args := []string{"-m", "pip", "install", name}
		if len(options) > 0 {
			args = append(args, options...)
		}
		s := command.NewShellCommand(m.PythonPath, args, nil, true)
		if err := s.Run(); err != nil {
			return fmt.Errorf("failed to install Python package %s: %w", name, err)
		}
	}

	for _, requirementsFile := range packageList.PackageFiles {
		slog.Info("Installing Python requirements file " + requirementsFile)

		args := []string{"-m", "pip", "install", "-r", requirementsFile}
		if len(options) > 0 {
			args = append(args, options...)
		}
		s := command.NewShellCommand(m.PythonPath, args, nil, true)
		if err := s.Run(); err != nil {
			return fmt.Errorf("failed to install Python package %s: %w", requirementsFile, err)
		}
	}

	return nil
}

func (m *PythonManager) InstallJupyter4Workbench(path string, force bool) error {
	slog.Info("Installing Jupyter for Workbench using Python " + m.Version)
	slog.Debug("Python binary path: " + m.PythonPath)

	if path == "" {
		path = jupyterPath
	}
	pythonPath := jupyterPath + "/bin/python"
	pipPath := jupyterPath + "/bin/pip"

	// Check if Python is installed
	installed, err := m.Installed()
	if err != nil {
		return err
	}
	if !installed {
		return fmt.Errorf("python %s is not installed", m.Version)
	}

	// Remove existing Jupyter installation
	exists, err := file.IsPathExist(path)
	if err != nil {
		return fmt.Errorf("failed to check for existing Jupyter installation at '%s': %w", path, err)
	}
	if exists && force {
		slog.Info("Removing existing Jupyter installation")
		err := file.AppFs.RemoveAll(path)
		if err != nil {
			return err
		}
	} else {
		slog.Info("Jupyter is already installed, use `--force` to reinstall")
		return nil
	}

	// Create a new virtual environment for Jupyter
	slog.Info("Creating a new virtual environment for Jupyter")
	args := []string{"-m", "venv", path}
	s := command.NewShellCommand(m.PythonPath, args, nil, true)
	if err := s.Run(); err != nil {
		return fmt.Errorf("failed to create virtual environment for Jupyter: %w", err)
	}

	jupyterManager := &PythonManager{
		LocalSystem:      m.LocalSystem,
		Version:          m.Version,
		InstallationPath: path,
		PythonPath:       pythonPath,
		PipPath:          pipPath,
		InstallOptions:   &PythonInstallOptions{},
	}

	if err := jupyterManager.initializePythonCoreTools(); err != nil {
		return fmt.Errorf("failed to initialize jupyter virtual environment: %w", err)
	}

	jupyterPackageList := &PythonPackageList{
		Packages: []string{"jupyterlab", "notebook", "pwb_jupyterlab"},
	}
	err = jupyterManager.InstallPackages(jupyterPackageList, nil)
	if err != nil {
		return err
	}

	return nil
}

func (m *PythonManager) Clean() error {
	slog.Info("Purging pip cache")

	args := []string{"-m", "pip", "cache", "purge"}
	s := command.NewShellCommand(m.PythonPath, args, nil, true)
	err := s.Run()
	if err != nil {
		return fmt.Errorf("failed to purge pip cache: %w", err)
	}

	return nil
}

func (m *PythonManager) initializePythonCoreTools() error {
	err := m.ensurePip()
	if err != nil {
		return err
	}

	err = m.InstallPackages(&PythonPackageList{Packages: []string{"pip", "setuptools"}}, []string{"--upgrade"})
	if err != nil {
		return err
	}

	return nil
}

func (m *PythonManager) ensurePip() error {
	slog.Debug("Ensuring pip is installed")

	args := []string{"-m", "ensurepip", "--upgrade"}
	s := command.NewShellCommand(m.PythonPath, args, nil, true)
	if err := s.Run(); err != nil {
		return fmt.Errorf("ensurepip failed: %w", err)
	}

	return nil
}

func (m *PythonManager) makeDefault() error {
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

func (m *PythonManager) addToPath() error {
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

func (m *PythonManager) addJupyterKernel() error {
	slog.Info("Configuring IPython kernel for Python " + m.Version)

	err := m.InstallPackages(&PythonPackageList{Packages: []string{"ipykernel"}}, []string{"--upgrade"})
	if err != nil {
		return fmt.Errorf("failed to install ipykernel to python %s: %w", m.Version, err)
	}

	args := []string{"-m", "ipykernel", "install", "--name", fmt.Sprintf("py%s", m.Version), "--display-name", fmt.Sprintf("Python %s", m.Version)}
	s := command.NewShellCommand(m.PythonPath, args, nil, true)
	err = s.Run()
	if err != nil {
		return fmt.Errorf("failed to register kernel for python %s: %w", m.Version, err)
	}

	return nil
}
