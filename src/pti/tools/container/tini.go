package container

import (
	"fmt"
	"github.com/pterm/pterm"
	"github.com/spf13/afero"
	"log/slog"
	"pti/system"
	"pti/system/file"
)

const tiniVersion = "0.19.0"

var tiniDownloadUrl = "https://cdn.posit.co/platform/tini/v%s/tini-%s"

func getTiniDownloadUrl(version, arch string) (string, error) {
	if version == "" {
		version = tiniVersion
	}
	if arch == "" {
		return "", fmt.Errorf("no system architecture provided for tini download")
	}
	return fmt.Sprintf(tiniDownloadUrl, version, arch), nil
}

func InstallTini(l *system.LocalSystem, installPath string) error {
	s, _ := pterm.DefaultSpinner.Start("Downloading tini...")

	if installPath == "" {
		installPath = "/usr/local/bin/tini"
	}

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

	downloadUrl, err := getTiniDownloadUrl("", l.Arch)
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

	slog.Debug("Installing tini binary to: " + installPath)
	if err := file.Move(downloadPath, installPath); err != nil {
		return fmt.Errorf("failed to install tini to '%s': %w", installPath, err)
	}
	slog.Debug("Setting permissions for tini binary to 0755")
	if err := file.AppFs.Chmod(installPath, 0755); err != nil {
		return fmt.Errorf("failed to set permissions for %s to 0755: %w", installPath, err)
	}
	slog.Info("tini installed successfully to " + installPath)

	return nil
}
