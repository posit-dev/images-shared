package container

import (
	"fmt"
	"github.com/pterm/pterm"
	"github.com/spf13/afero"
	"log/slog"
	"pti/system/file"
)

var waitForItDownloadUrl = "https://cdn.posit.co/platform/wait-for-it/wait-for-it.sh"

type WaitForItManager struct {
	InstallPath string
}

func NewWaitForItManager(installPath string) *WaitForItManager {
	if installPath == "" {
		installPath = "/usr/local/bin/wait-for-it"
	}
	return &WaitForItManager{
		InstallPath: installPath,
	}
}

func (w *WaitForItManager) Installed() (bool, error) {
	exists, err := file.IsPathExist(w.InstallPath)
	if err != nil {
		return false, fmt.Errorf("failed to check for existing wait-for-it installation at '%s': %w", w.InstallPath, err)
	}
	if exists {
		isFile, err := file.IsFile(w.InstallPath)
		if err != nil {
			return false, fmt.Errorf("failed to check if '%s' is a file: %w", w.InstallPath, err)
		}
		if !isFile {
			return false, fmt.Errorf("'%s' is not a file", w.InstallPath)
		}
	}
	return exists, nil
}

func (w *WaitForItManager) Install() error {
	installed, err := w.Installed()
	if err != nil {
		return err
	}
	if installed {
		slog.Warn("wait-for-it is installed")
		return fmt.Errorf("wait-for-it is already installed")
	}

	s, _ := pterm.DefaultSpinner.Start("Downloading wait-for-it...")

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

	slog.Debug("Installing wait-for-it script to: " + w.InstallPath)
	if err := file.Move(downloadPath, w.InstallPath); err != nil {
		return fmt.Errorf("failed to install wait-for-it to '%s': %w", w.InstallPath, err)
	}
	slog.Debug("Setting permissions for wait-for-it script to 0755")
	if err := file.AppFs.Chmod(w.InstallPath, 0755); err != nil {
		return fmt.Errorf("failed to set permissions for %s to 0755: %w", w.InstallPath, err)
	}
	slog.Info("wait-for-it installed successfully to " + w.InstallPath)

	return nil
}

func (w *WaitForItManager) Update() error {
	slog.Info("Updating wait-for-it")
	slog.Info("Checking for existing wait-for-it installation")
	installed, err := w.Installed()
	if err != nil {
		return err
	}

	if installed {
		slog.Info("Existing wait-for-it installation found")
		err := w.Remove()
		if err != nil {
			return fmt.Errorf("failed to remove existing wait-for-it: %w", err)
		}
	} else {
		slog.Info("wait-for-it is not installed")
	}

	return w.Install()
}

func (w *WaitForItManager) Remove() error {
	installed, err := w.Installed()
	if err != nil {
		return err
	}
	if !installed {
		slog.Warn("wait-for-it is not installed")
		return nil
	}

	slog.Info("Removing wait-for-it")
	err = file.AppFs.Remove(w.InstallPath)
	if err != nil {
		return fmt.Errorf("failed to remove wait-for-it from '%s': %w", w.InstallPath, err)
	}
	slog.Info("wait-for-it removed successfully from " + w.InstallPath)

	return nil
}

func (w *WaitForItManager) InstallPackage() error {
	return fmt.Errorf("wait-for-it does not utilize subpackage installation")
}

func (w *WaitForItManager) RemovePackage() error {
	return fmt.Errorf("wait-for-it does not utilize subpackage installation")
}
