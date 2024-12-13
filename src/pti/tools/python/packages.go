package python

import (
	"fmt"
	"log/slog"
	"pti/system/command"
)

type PackageList struct {
	Packages     []string
	PackageFiles []string
}

func (m *Manager) InstallPackages(packageList *PackageList, options []string) error {
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
			return fmt.Errorf("failed to install python package %s: %w", name, err)
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
			return fmt.Errorf("failed to install python requirements file %s: %w", requirementsFile, err)
		}
	}

	return nil
}

func (m *Manager) Clean() error {
	slog.Info("Purging pip cache")

	args := []string{"-m", "pip", "cache", "purge"}
	s := command.NewShellCommand(m.PythonPath, args, nil, true)
	err := s.Run()
	if err != nil {
		return fmt.Errorf("failed to purge pip cache: %w", err)
	}

	return nil
}

func (m *Manager) initCorePackages() error {
	err := m.ensurePip()
	if err != nil {
		return err
	}

	err = m.InstallPackages(&PackageList{Packages: []string{"pip", "setuptools"}}, []string{"--upgrade"})
	if err != nil {
		return err
	}

	return nil
}

func (m *Manager) ensurePip() error {
	slog.Debug("Ensuring pip is installed")

	args := []string{"-m", "ensurepip", "--upgrade"}
	s := command.NewShellCommand(m.PythonPath, args, nil, true)
	if err := s.Run(); err != nil {
		return fmt.Errorf("ensurepip failed: %w", err)
	}

	return nil
}
