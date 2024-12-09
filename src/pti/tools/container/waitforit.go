package container

import (
	"fmt"
	"github.com/pterm/pterm"
	"github.com/spf13/afero"
	"log/slog"
	"pti/system/file"
)

var waitForItDownloadUrl = "https://cdn.posit.co/platform/wait-for-it/wait-for-it.sh"

func InstallWaitForIt(installPath string) error {
	s, _ := pterm.DefaultSpinner.Start("Downloading wait-for-it...")

	if installPath == "" {
		installPath = "/usr/local/bin/wait-for-it"
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
	downloadPath := downloadDir + "/wait-for-it"

	err = file.DownloadFile(waitForItDownloadUrl, downloadPath)
	if err != nil {
		s.Fail("Download failed.")
		return fmt.Errorf("wait-for-it download failed: %w", err)
	}
	s.Success("Download complete.")

	slog.Debug("Installing wait-for-it script to: " + installPath)
	if err := file.Move(downloadPath, installPath); err != nil {
		return fmt.Errorf("failed to install wait-for-it to '%s': %w", installPath, err)
	}
	slog.Debug("Setting permissions for wait-for-it script to 0755")
	if err := file.AppFs.Chmod(installPath, 0755); err != nil {
		return fmt.Errorf("failed to set permissions for %s to 0755: %w", installPath, err)
	}
	slog.Info("wait-for-it installed successfully to " + installPath)

	return nil
}
