package quarto

import (
	"fmt"
	"log/slog"
	"pti/system"
	"pti/system/file"
	"slices"

	"github.com/pterm/pterm"
	"github.com/spf13/afero"
)

const (
	DefaultInstallPath     = "/opt/quarto"
	defaultBinPath         = "/opt/quarto/bin/quarto"
	workbenchLibRoot       = "/lib/rstudio-server"
	workbenchQuartoPath    = workbenchLibRoot + "/bin/quarto"
	workbenchQuartoBinPath = workbenchLibRoot + "/bin/quarto/bin/quarto"
)

var (
	supportedArchitectures = []string{"amd64", "arm64"}
	downloadUrl            = "https://github.com/quarto-dev/quarto-cli/releases/download/v%s/quarto-%s-linux-%s.tar.gz"
)

type Manager struct {
	*system.LocalSystem
	Version                 string
	InstallationPath        string
	BinPath                 string
	IsWorkbenchInstallation bool
}

func workbenchInstalled() (bool, error) {
	workbenchExists, err := file.IsFile(workbenchQuartoBinPath)
	if err != nil {
		return false, fmt.Errorf(
			"failed to check for existing Workbench Quarto installation at '%s': %w",
			workbenchQuartoBinPath,
			err,
		)
	}

	return workbenchExists, nil
}

func NewManager(
	l *system.LocalSystem,
	version, installationPath string,
	useWorkbench bool,
) *Manager {
	var binPath string
	workbenchQuartoExists, err := workbenchInstalled()
	if err != nil {
		slog.Error("Failed to check for existing Workbench Quarto installation: " + err.Error())
		slog.Warn("Assuming Workbench Quarto installation does not exist.")
		workbenchQuartoExists = false
	}
	isWorkbenchInstallation := false
	switch {
	case workbenchQuartoExists && useWorkbench:
		slog.Info("Using Quarto from Workbench: " + workbenchQuartoPath)
		installationPath = workbenchQuartoPath
		binPath = workbenchQuartoBinPath
		isWorkbenchInstallation = true
	case installationPath == "":
		slog.Info("Using default Quarto installation path: " + DefaultInstallPath)
		installationPath = DefaultInstallPath
		binPath = defaultBinPath
	default:
		binPath = installationPath + "/bin/quarto"
	}

	return &Manager{
		LocalSystem:             l,
		Version:                 version,
		InstallationPath:        installationPath,
		BinPath:                 binPath,
		IsWorkbenchInstallation: isWorkbenchInstallation,
	}
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
		return false, fmt.Errorf(
			"failed to check for existing Quarto installation at '%s': %w",
			m.InstallationPath,
			err,
		)
	}

	return quartoBinExists, nil
}

func getDownloadUrl(quartoVersion, arch string) (string, error) {
	slog.Info("Fetching Quarto package " + quartoVersion)

	if !slices.Contains(supportedArchitectures, arch) {
		slog.Error("Quarto is only supported on amd64 and arm64 architectures")

		return "", fmt.Errorf("quarto is not supported on detected '%s' architecture", arch)
	}

	quartoDownloadUrl := fmt.Sprintf(downloadUrl, quartoVersion, quartoVersion, arch)

	slog.Debug("Download URL: " + quartoDownloadUrl)

	return quartoDownloadUrl, nil
}

//nolint:cyclop
func (m *Manager) Install(force bool) error {
	err := m.validate()
	if err != nil {
		return fmt.Errorf("quarto install failed: %w", err)
	}

	if m.IsWorkbenchInstallation {
		slog.Info("Workbench Quarto installation detected, skipping installation.")

		return nil
	}

	slog.Debug("Quarto version: " + m.Version)
	slog.Debug("Target Quarto installation path: " + m.InstallationPath)
	slog.Debug("Target Quarto binary path: " + m.BinPath)

	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check if quarto is installed: %w", err)
	}

	if !installed || force {
		err = file.InstallableDir(m.InstallationPath, !force)
		if err != nil {
			slog.Error("Quarto could not be installed on installation path " + m.InstallationPath)
			slog.Error("Use `--force` flag to attempt to install anyways.")

			return fmt.Errorf(
				"installation path '%s' is not installable: %w",
				m.InstallationPath,
				err,
			)
		}

		if installed {
			slog.Info("Removing existing Quarto installation")
			if err := file.AppFs.RemoveAll(m.InstallationPath); err != nil {
				return err
			}
		}

		s, _ := pterm.DefaultSpinner.Start("Downloading Quarto " + m.Version)

		url, err := getDownloadUrl(m.Version, m.LocalSystem.Arch)
		if err != nil {
			s.Fail("Download failed.")

			return fmt.Errorf("failed to determine quarto download URL: %w", err)
		}

		tmpDir, err := afero.TempDir(file.AppFs, "", "quarto")
		if err != nil {
			s.Fail("Download failed.")

			return fmt.Errorf("failed to create temporary directory for quarto download: %w", err)
		}
		downloadPath := tmpDir + "/quarto.tar.gz"
		defer file.AppFs.RemoveAll(tmpDir) //nolint:errcheck

		if err := file.DownloadFile(url, downloadPath); err != nil {
			s.Fail("Download failed.")

			return fmt.Errorf("quarto %s download failed: %w", m.Version, err)
		}
		s.Success("Download complete.")

		s, _ = pterm.DefaultSpinner.Start("Installing Quarto " + m.Version)

		if err := file.ExtractTarGz(downloadPath, tmpDir); err != nil {
			s.Fail("Installation failed.")

			return fmt.Errorf(
				"unable to extract quarto archive from '%s' to '%s': %w",
				downloadPath,
				tmpDir,
				err,
			)
		}

		extractDir := tmpDir + "/quarto-" + m.Version
		exists, err := file.IsDir(extractDir)
		if err != nil {
			s.Fail("Installation failed.")

			return fmt.Errorf("could not read quarto extract path '%s': %w", extractDir, err)
		}
		if !exists {
			s.Fail("Installation failed.")

			return fmt.Errorf("expected quarto extract path '%s' does not exist", extractDir)
		}

		slog.Info("Installing Quarto to " + m.InstallationPath)
		if err := file.Move(extractDir, m.InstallationPath); err != nil {
			s.Fail("Installation failed.")

			return fmt.Errorf(
				"failed to move quarto from '%s' to installation path '%s': %w",
				extractDir,
				m.InstallationPath,
				err,
			)
		}

		s.Success("Installation complete.")
	} else {
		slog.Info("Quarto is already installed")
	}

	return nil
}
