package cmd

import (
	"fmt"
	"github.com/urfave/cli/v2"
	"log/slog"
	"pti/system"
	"pti/tools"
)

func QuartoInstall(cCtx *cli.Context) error {
	system.RequireSudo()

	quartoVersion := cCtx.String("version")
	force := cCtx.Bool("force")
	workbenchQuartoExists, err := system.IsPathExist("/opt/posit-workbench/quarto")
	if err != nil {
		return err
	}
	if quartoVersion == "" && (!workbenchQuartoExists && force) {
		return fmt.Errorf("Quarto version must be provided")
	}

	installTinyTex := cCtx.Bool("install-tinytex")
	addPathTinyTex := cCtx.Bool("add-path-tinytex")

	return tools.InstallQuarto(quartoVersion, installTinyTex, addPathTinyTex, force)
}

func QuartoInstallTinyTex(cCtx *cli.Context) error {
	quartoPath := cCtx.String("quarto-path")
	if quartoPath == "" {
		quartoPath = "/opt/quarto/bin/quarto"

		exists, err := system.IsPathExist(quartoPath)
		if err != nil {
			return err
		}
		if !exists {
			slog.Debug("Quarto binary does not exist at path %s", quartoPath)
		}

		workbenchQuartoBinPath := tools.WorkbenchQuartoPath + "/bin/quarto"

		exists, err = system.IsPathExist(workbenchQuartoBinPath)
		if err != nil {
			return err
		}
		if !exists {
			return fmt.Errorf("Could not find Quarto binary at %s or %s", quartoPath, workbenchQuartoBinPath)
		}
	}

	var options []string
	addToPath := cCtx.Bool("add-path-tinytex")
	if addToPath {
		options = append(options, "--update-path")
	}

	return tools.InstallQuartoTool(quartoPath, "tinytex", &options)
}

func QuartoUpdateTinyTex(cCtx *cli.Context) error {
	quartoPath := cCtx.String("quarto-path")
	if quartoPath == "" {
		quartoPath = "/opt/quarto/bin/quarto"
	}

	exists, err := system.IsPathExist(quartoPath)
	if err != nil {
		return err
	}
	if !exists {
		return fmt.Errorf("Quarto binary does not exist at path %s", quartoPath)
	}

	return tools.UpdateQuartoTool(quartoPath, "tinytex", &[]string{})
}
