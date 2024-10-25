package tools

import (
	"github.com/pterm/pterm"
	"log/slog"
	"os"
	"posit-images-shared/internal/system"
)

const tiniDownloadUrl = "https://cdn.posit.co/platform/tini/v0.19.0/tini-amd64"
const waitForItDownloadUrl = "https://cdn.posit.co/platform/wait-for-it/wait-for-it.sh"

func Bootstrap() error {
	if err := system.InstallPackages(&[]string{"ca-certificates"}); err != nil {
		slog.Error("Failed to install ca-certificates", err)
		return err
	}
	if err := system.UpdateCACertificates(); err != nil {
		slog.Error("Failed to update CA certificates", err)
		return err
	}
	return nil
}

func InstallTini(installPath string) error {
	downloadPath := "/tmp/tini"
	s, _ := pterm.DefaultSpinner.Start("Downloading tini...")
	err := DownloadTiniBinary(downloadPath)
	if err != nil {
		s.Fail("Download failed.")
		return err
	}
	s.Success("Download complete.")

	slog.Debug("Installing tini binary to: " + installPath)
	if err := system.MoveFile(downloadPath, installPath); err != nil {
		return err
	}
	slog.Debug("Setting permissions for tini binary to 0755")
	if err := os.Chmod(installPath, 0755); err != nil {
		return err
	}
	slog.Info("tini installed successfully to " + installPath)

	return nil
}

func InstallWaitForIt(installPath string) error {
	downloadPath := "/tmp/wait-for-it.sh"
	err := DownloadWaitForItScript(downloadPath)
	if err != nil {
		return err
	}
	slog.Debug("Installing wait-for-it script to: " + installPath)
	if err := system.MoveFile(downloadPath, installPath); err != nil {
		return err
	}
	slog.Debug("Setting permissions for wait-for-it script to 0755")
	if err := os.Chmod(installPath, 0755); err != nil {
		return err
	}
	slog.Info("wait-for-it installed successfully to " + installPath)

	return nil
}

func DownloadTiniBinary(targetPath string) error {
	slog.Debug("Downloading tini to: " + targetPath)
	if err := system.DownloadFile(targetPath, tiniDownloadUrl); err != nil {
		return err
	}
	return nil
}

func DownloadWaitForItScript(targetPath string) error {
	slog.Debug("Downloading wait-for-it script to: " + targetPath)
	if err := system.DownloadFile(targetPath, waitForItDownloadUrl); err != nil {
		return err
	}
	return nil
}
