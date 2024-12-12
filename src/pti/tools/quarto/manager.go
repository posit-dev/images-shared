package quarto

import (
	"fmt"
	"github.com/spf13/afero"
	"log/slog"
	"pti/system"
	"pti/system/command"
	"pti/system/file"
	"strings"
)

const (
	defaultInstallPath     = "/opt/quarto"
	defaultBinPath         = "/opt/quarto/bin/quarto"
	workbenchLibRoot       = "/lib/rstudio-server"
	workbenchQuartoPath    = workbenchLibRoot + "/bin/quarto"
	workbenchQuartoBinPath = workbenchLibRoot + "/bin/quarto/bin/quarto"
)

var downloadUrl = "https://github.com/quarto-dev/quarto-cli/releases/download/v%s/quarto-%s-linux-%s.tar.gz"

type InstallOptions struct {
	InstallTinyTeX bool
	AddPathTinyTeX bool
	Force          bool
}

type Manager struct {
	*system.LocalSystem
	Version                 string
	InstallationPath        string
	BinPath                 string
	IsWorkbenchInstallation bool
	InstallOptions          *InstallOptions
}

func NewManager(l *system.LocalSystem, version, installationPath string, installOptions *InstallOptions) (*Manager, error) {
	if version == "" {
		return nil, fmt.Errorf("quarto version is required")
	}

	if installOptions == nil {
		installOptions = &InstallOptions{
			InstallTinyTeX: false,
			AddPathTinyTeX: false,
			Force:          false,
		}
	}

	binPath := ""
	isWorkbenchInstallation := false
	if installationPath == "" {
		workbenchExists, err := file.IsFile(workbenchQuartoBinPath)
		if err != nil {
			slog.Warn(fmt.Sprintf("Failed to check for Workbench Quarto: %s", err.Error()))
		}
		if workbenchExists && !installOptions.Force {
			slog.Info("Using Quarto from Workbench: " + workbenchQuartoPath)
			isWorkbenchInstallation = true
			installationPath = workbenchQuartoPath
			binPath = workbenchQuartoBinPath
		} else {
			slog.Info("Using default Quarto installation path: " + defaultInstallPath)
			installationPath = defaultInstallPath
			binPath = defaultBinPath
		}
	} else {
		binPath = installationPath + "/bin/quarto"

		slog.Info("Using custom Quarto installation path: " + installationPath)
		if strings.HasPrefix(installationPath, workbenchLibRoot) && !installOptions.Force {
			slog.Warn("Quarto installation path is within Workbench lib path " + workbenchLibRoot + ".")
			slog.Warn("Assuming Workbench Quarto installation at " + workbenchQuartoPath + " should be used.")
			isWorkbenchInstallation = true
			installationPath = workbenchQuartoPath
			binPath = workbenchQuartoBinPath
		} else if strings.HasPrefix(installationPath, workbenchLibRoot) && installOptions.Force {
			slog.Warn("This appears to be a Workbench path, but --force was used.")
			slog.Warn("Forcing use of custom Quarto installation path: " + installationPath)
		}
	}

	err := file.InstallableDir(installationPath, true)
	if !isWorkbenchInstallation && err != nil && !installOptions.Force {
		slog.Error("Quarto installation path is not installable: " + installationPath)
		slog.Error("Use --force to override!")
		return nil, fmt.Errorf("installation path '%s' is not installable: %w", installationPath, err)
	}

	return &Manager{
		LocalSystem:             l,
		Version:                 version,
		InstallationPath:        installationPath,
		BinPath:                 binPath,
		IsWorkbenchInstallation: isWorkbenchInstallation,
		InstallOptions:          installOptions,
	}, nil
}

func (m *Manager) validate() error {
	if m.Version == "" {
		return fmt.Errorf("quarto version is required")
	}
	if m.InstallationPath == "" {
		return fmt.Errorf("quarto installation path is required")
	}
	return nil
}

func (m *Manager) Installed() (bool, error) {
	quartoBinExists, err := file.IsFile(m.BinPath)
	if err != nil {
		return false, fmt.Errorf("failed to check for existing Quarto installation at '%s': %w", m.InstallationPath, err)
	}
	return quartoBinExists, nil
}

func getDownloadUrl(quartoVersion, arch string) (string, error) {
	slog.Info("Fetching Quarto package " + quartoVersion)

	if arch != "amd64" && arch != "arm64" {
		slog.Error("Quarto is only supported on amd64 and arm64 architectures")
		return "", fmt.Errorf("quarto is not supported on detected '%s' architecture", arch)
	}

	quartoDownloadUrl := fmt.Sprintf(downloadUrl, quartoVersion, quartoVersion, arch)

	slog.Debug("Download URL: " + quartoDownloadUrl)

	return quartoDownloadUrl, nil
}

func (m *Manager) Install() error {
	err := m.validate()
	if err != nil {
		return fmt.Errorf("quarto install failed: %w", err)
	}

	slog.Debug("Quarto version: " + m.Version)
	slog.Debug("Target Quarto installation path: " + m.InstallationPath)
	slog.Debug("Target Quarto binary path: " + m.BinPath)

	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if Quarto is installed: %w", err)
	}

	if !m.IsWorkbenchInstallation && (!installed || m.InstallOptions.Force) {
		slog.Info("Installing Quarto")

		if installed {
			slog.Info("Removing existing Quarto installation")
			if err := file.AppFs.RemoveAll(m.InstallationPath); err != nil {
				return err
			}
		}

		downloadUrl, err := getDownloadUrl(m.Version, m.LocalSystem.Arch)
		if err != nil {
			return fmt.Errorf("failed to determine quarto download URL: %w", err)
		}

		tmpDir, err := afero.TempDir(file.AppFs, "", "quarto")
		if err != nil {
			return fmt.Errorf("failed to create temporary directory for quarto download: %w", err)
		}
		downloadPath := tmpDir + "/quarto.tar.gz"
		defer file.AppFs.RemoveAll(tmpDir)

		if err := file.DownloadFile(downloadUrl, downloadPath); err != nil {
			return fmt.Errorf("quarto %s download failed: %w", m.Version, err)
		}

		if err := file.ExtractTarGz(downloadPath, tmpDir); err != nil {
			return fmt.Errorf("unable to extract quarto archive from '%s' to '%s': %w", downloadPath, tmpDir, err)
		}

		extractDir := tmpDir + "/quarto-" + m.Version
		exists, err := file.IsDir(extractDir)
		if err != nil {
			return fmt.Errorf("could not read quarto extract path '%s': %w", extractDir, err)
		}
		if !exists {
			return fmt.Errorf("expected quarto extract path '%s' does not exist", extractDir)
		}

		if err := file.Move(extractDir, m.InstallationPath); err != nil {
			return fmt.Errorf("failed to move quarto from '%s' to installation path '%s': %w", extractDir, m.InstallationPath, err)
		}
	} else {
		slog.Info("Quarto is already installed")
	}

	if m.InstallOptions.InstallTinyTeX {
		var options []string
		if m.InstallOptions.AddPathTinyTeX {
			options = append(options, "--update-path")
		}
		if err := m.InstallPackage("tinytex", options); err != nil {
			return err
		}
	}

	return nil
}

func (m *Manager) InstallPackage(name string, options []string) error {
	slog.Info(fmt.Sprintf("Installing Quarto %s add-on", name))

	args := []string{"install", name, "--no-prompt"}
	if len(options) > 0 {
		args = append(args, options...)
	}
	s := command.NewShellCommand(m.BinPath, args, nil, true)
	if err := s.Run(); err != nil {
		return fmt.Errorf("failed to install quarto %s tool: %w", name, err)
	}

	return nil
}

func (m *Manager) UpdatePackage(name string, options []string) error {
	slog.Info("Updating Quarto " + name + " tool")

	args := []string{"update", name, "--no-prompt"}
	if len(options) > 0 {
		args = append(args, options...)
	}

	s := command.NewShellCommand(m.BinPath, args, nil, true)
	if err := s.Run(); err != nil {
		return fmt.Errorf("failed to update quarto %s tool: %w", name, err)
	}

	return nil
}

func (m *Manager) RemovePackage(name string, options []string) error {
	slog.Info("Updating Quarto " + name + " tool")

	args := []string{"remove", name, "--no-prompt"}
	if len(options) > 0 {
		args = append(args, options...)
	}

	s := command.NewShellCommand(m.BinPath, args, nil, true)
	if err := s.Run(); err != nil {
		return fmt.Errorf("failed to remove quarto %s tool: %w", name, err)
	}

	return nil
}
