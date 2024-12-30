package container

import (
	"fmt"
	"log/slog"
	"pti/system"
	"pti/system/file"

	"github.com/pterm/pterm"
	"github.com/spf13/afero"
)

const (
	DefaultTiniPath = "/usr/local/bin/tini"
	tiniVersion     = "0.19.0"
)

var tiniDownloadUrl = "https://cdn.posit.co/platform/tini/v%s/tini-%s"

type TiniManager struct {
	*system.LocalSystem
	Version     string
	InstallPath string
}

func NewTiniManager(l *system.LocalSystem, version, installPath string) *TiniManager {
	if version == "" {
		version = tiniVersion
	}
	if installPath == "" {
		installPath = DefaultTiniPath
	}

	return &TiniManager{
		LocalSystem: l,
		Version:     version,
		InstallPath: installPath,
	}
}

func getTiniDownloadUrl(version, arch string) (string, error) {
	if version == "" {
		version = tiniVersion
	}
	if arch == "" {
		return "", fmt.Errorf("no system architecture provided for tini download")
	}

	return fmt.Sprintf(tiniDownloadUrl, version, arch), nil
}

func (m *TiniManager) Installed() (bool, error) {
	exists, err := file.IsPathExist(m.InstallPath)
	if err != nil {
		return false, fmt.Errorf(
			"failed to check for existing tini installation at '%s': %w",
			m.InstallPath,
			err,
		)
	}
	if exists {
		isFile, err := file.IsFile(m.InstallPath)
		if err != nil {
			return false, fmt.Errorf("failed to check if '%s' is a file: %w", m.InstallPath, err)
		}
		if !isFile {
			return false, fmt.Errorf("'%s' is not a file", m.InstallPath)
		}
	}

	return exists, nil
}

func (m *TiniManager) Install() error {
	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check for existing tini: %w", err)
	}
	if installed {
		slog.Info("tini is already installed")

		return fmt.Errorf("tini is already installed")
	}

	s, _ := pterm.DefaultSpinner.Start("Downloading tini...")

	downloadDir, err := afero.TempDir(file.AppFs, "", "pti")
	if err != nil {
		return fmt.Errorf("unable to create pti temporary directory for download: %w", err)
	}
	defer func() {
		err := file.AppFs.RemoveAll(downloadDir)
		if err != nil {
			slog.Warn("Failed to remove temporary directory '" + downloadDir + "': " + err.Error())
		}
	}()
	downloadPath := downloadDir + "/tini"

	downloadUrl, err := getTiniDownloadUrl("", m.LocalSystem.Arch)
	if err != nil {
		return fmt.Errorf("unable to determine tini download url: %w", err)
	}

	err = file.DownloadFile(downloadUrl, downloadPath)
	if err != nil {
		s.Fail("Download failed.")

		return fmt.Errorf("tini download failed: %w", err)
	}
	s.Success("Download complete.")

	// TODO: Implement checksum validation

	slog.Debug("Installing tini binary to: " + m.InstallPath)
	if err := file.Move(downloadPath, m.InstallPath); err != nil {
		return fmt.Errorf("failed to install tini to '%s': %w", m.InstallPath, err)
	}
	slog.Debug("Setting permissions for tini binary to 0755")
	if err := file.AppFs.Chmod(m.InstallPath, 0o755); err != nil {
		return fmt.Errorf("failed to set permissions for %s to 0755: %w", m.InstallPath, err)
	}
	slog.Info("tini installed successfully to " + m.InstallPath)

	return nil
}

func (m *TiniManager) Update() error {
	slog.Info("Updating tini")
	slog.Info("Checking for existing tini installation")
	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check for existing tini installation: %w", err)
	}

	if installed {
		slog.Info("Existing tini installation found")
		err := m.Remove()
		if err != nil {
			return fmt.Errorf("failed to remove existing tini installation: %w", err)
		}
	} else {
		slog.Info("tini is not installed")
	}

	return m.Install()
}

func (m *TiniManager) Remove() error {
	installed, err := m.Installed()
	if err != nil {
		return fmt.Errorf("failed to check for existing tini: %w", err)
	}
	if !installed {
		slog.Info("tini is not installed")

		return nil
	}

	slog.Info("Removing tini")
	err = file.AppFs.Remove(m.InstallPath)
	if err != nil {
		return fmt.Errorf("failed to remove tini from '%s': %w", m.InstallPath, err)
	}
	slog.Info("tini removed successfully from " + m.InstallPath)

	return nil
}
