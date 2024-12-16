package python

import (
	"fmt"
	"log/slog"
	"pti/system/command"
	"pti/system/file"
)

func (m *Manager) InstallJupyter4Workbench(path string, force bool) error {
	slog.Info("Installing Jupyter for Workbench using Python " + m.Version)
	slog.Debug("Python binary path: " + m.PythonPath)

	if path == "" {
		path = defaultJupyterPath
	}
	pythonPath := defaultJupyterPath + "/bin/python"
	pipPath := defaultJupyterPath + "/bin/pip"

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
		slog.Info("Removing existing Jupyter installation at " + path)
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

	jupyterManager := &Manager{
		LocalSystem:      m.LocalSystem,
		Version:          m.Version,
		InstallationPath: path,
		PythonPath:       pythonPath,
		PipPath:          pipPath,
	}

	if err := jupyterManager.initCorePackages(); err != nil {
		return fmt.Errorf("failed to initialize jupyter virtual environment: %w", err)
	}

	jupyterPackageList := &PackageList{
		Packages: []string{"jupyterlab", "notebook", "pwb_jupyterlab"},
	}
	err = jupyterManager.InstallPackages(jupyterPackageList, nil)
	if err != nil {
		return err
	}

	return nil
}

func (m *Manager) addJupyterKernel() error {
	slog.Info("Configuring IPython kernel for Python " + m.Version)

	err := m.InstallPackages(&PackageList{Packages: []string{"ipykernel"}}, []string{"--upgrade"})
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
