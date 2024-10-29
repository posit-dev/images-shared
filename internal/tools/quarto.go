package tools

import (
	"fmt"
	"github.com/zcalusic/sysinfo"
	"log/slog"
	"os"
	"posit-images-shared/internal/system"
)

const quartoDownloadUrlRoot = "https://github.com/quarto-dev/quarto-cli/releases/download"
const WorkbenchQuartoPath = "/lib/rstudio-server/bin/quarto"

func InstallQuarto(quartoVersion string, installTinyTeX, addPathTinyTeX, force bool) error {
	quartoInstallationPath := "/opt/quarto"
	quartoBinPath := fmt.Sprintf("%s/bin/quarto", quartoInstallationPath)

	slog.Debug("Quarto version: " + quartoVersion)

	workbenchQuartoExists, err := system.PathExists(WorkbenchQuartoPath)
	if err != nil {
		return err
	}
	slog.Debug("Workbench Quarto exists: " + fmt.Sprintf("%t", workbenchQuartoExists))
	quartoBinPathExists, err := system.PathExists(quartoBinPath)
	if err != nil {
		return err
	}
	slog.Debug("Quarto binary path already exists: " + fmt.Sprintf("%t", quartoBinPathExists))

	if workbenchQuartoExists && !force {
		slog.Warn("Quarto is already installed via Workbench. Use the `--force` flag to install a standalone version.")
		quartoInstallationPath = WorkbenchQuartoPath
		quartoBinPath = fmt.Sprintf("%s/bin/quarto", quartoInstallationPath)
		slog.Info("Using Quarto from Workbench: " + quartoBinPath)
	}

	slog.Debug("Target Quarto installation path: " + quartoInstallationPath)
	slog.Debug("Target Quarto binary path: " + quartoBinPath)

	if !quartoBinPathExists || force {
		slog.Info("Installing Quarto")

		if quartoBinPathExists {
			slog.Info("Removing existing Quarto installation")
			if err := os.RemoveAll(quartoInstallationPath); err != nil {
				return err
			}
		}

		downloadPath, err := FetchQuartoPackage(quartoVersion)
		if err != nil {
			return err
		}

		if err := system.ExtractTarGz(downloadPath, quartoInstallationPath, &[]string{"--strip-components", "1"}); err != nil {
			return err
		}

		if err := os.Remove(downloadPath); err != nil {
			return err
		}
	} else {
		slog.Info("Quarto is already installed")
	}

	if installTinyTeX {
		var options []string
		if addPathTinyTeX {
			options = append(options, "--update-path")
		}
		if err := InstallQuartoTool(quartoBinPath, "tinytex", &options); err != nil {
			return err
		}
	}

	return nil
}

func FetchQuartoPackage(quartoVersion string) (string, error) {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	slog.Info("Fetching Quarto package " + quartoVersion)

	if si.OS.Architecture != "amd64" && si.OS.Architecture != "arm64" {
		return "", fmt.Errorf("Quarto is only supported on amd64 and arm64 architectures")
	}

	quartoDownloadUrl := fmt.Sprintf("%s/v%s/quarto-%s-linux-%s.tar.gz", quartoDownloadUrlRoot, quartoVersion, quartoVersion, si.OS.Architecture)
	quartoDownloadPath := fmt.Sprintf("/tmp/quarto-%s.tar.gz", quartoVersion)

	slog.Debug("Download URL: " + quartoDownloadUrl)
	slog.Debug("Destination Path: " + quartoDownloadPath)

	err := system.DownloadFile(quartoDownloadPath, quartoDownloadUrl)
	if err != nil {
		return "", err
	}

	return quartoDownloadPath, nil
}

func InstallQuartoTool(quartoBinPath string, toolName string, options *[]string) error {
	slog.Info("Installing Quarto TinyTeX add-on")

	args := []string{"install", toolName, "--no-prompt"}
	if len(*options) > 0 {
		args = append(args, *options...)
	}
	if err := system.RunCommand(quartoBinPath, &args, nil); err != nil {
		return err
	}

	return nil
}

func UpdateQuartoTool(quartoBinPath, toolName string, options *[]string) error {
	slog.Info("Updating Quarto " + toolName + " tool")

	args := []string{"update", toolName, "--no-prompt"}
	if len(*options) > 0 {
		args = append(args, *options...)
	}
	if err := system.RunCommand(quartoBinPath, &args, nil); err != nil {
		return err
	}

	return nil
}
