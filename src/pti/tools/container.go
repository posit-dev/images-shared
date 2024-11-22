package tools

import (
	"fmt"
	"log/slog"
	"os"
	"pti/errors"
	"pti/system"
)

const tiniDownloadUrl = "https://cdn.posit.co/platform/tini/v0.19.0/tini-amd64"
const waitForItDownloadUrl = "https://cdn.posit.co/platform/wait-for-it/wait-for-it.sh"

func Bootstrap() error {
	if err := system.InstallPackages(&[]string{"ca-certificates"}); err != nil {
		return err
	}
	if err := system.UpdateCACertificates(); err != nil {
		return err
	}
	return nil
}

func InstallTini(installPath string) error {
	downloadPath := "/tmp/tini"
	slog.Info("Downloading tini...")
	err := DownloadTiniBinary(downloadPath)
	if err != nil {
		return fmt.Errorf(errors.ToolDownloadFailedErrorTpl, "tini", err)
	}
	slog.Info("Download complete.")

	// TODO: Implement checksum validation

	slog.Debug("Installing tini binary to: " + installPath)
	if err := system.MoveFile(downloadPath, installPath); err != nil {
		return fmt.Errorf(errors.ToolInstallFailedErrorTpl, "tini", err)
	}
	slog.Debug("Setting permissions for tini binary to 0755")
	if err := os.Chmod(installPath, 0755); err != nil {
		return fmt.Errorf(errors.ToolSetPermissionsFailedErrorTpl, "tini", "0755", err)
	}
	slog.Info("tini installed successfully to " + installPath)

	return nil
}

func InstallWaitForIt(installPath string) error {
	downloadPath := "/tmp/wait-for-it.sh"

	slog.Info("Downloading wait-for-it.sh...")
	err := DownloadWaitForItScript(downloadPath)
	if err != nil {
		return fmt.Errorf(errors.ToolDownloadFailedErrorTpl, "wait-for-it.sh", err)
	}

	slog.Debug("Installing wait-for-it script to: " + installPath)
	if err := system.MoveFile(downloadPath, installPath); err != nil {
		return fmt.Errorf(errors.ToolInstallFailedErrorTpl, "wait-for-it.sh", err)
	}
	slog.Debug("Setting permissions for wait-for-it script to 0755")
	if err := os.Chmod(installPath, 0755); err != nil {
		return fmt.Errorf(errors.ToolSetPermissionsFailedErrorTpl, "wait-for-it.sh", "0755", err)
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
