package cmd

import (
	"github.com/urfave/cli/v2"
	"pti/system"
	"pti/tools/quarto"
)

func QuartoInstall(cCtx *cli.Context) error {
	err := system.RequireSudo()
	if err != nil {
		return err
	}

	ignoreWorkbench := cCtx.Bool("ignore-workbench")
	quartoVersion := cCtx.String("version")
	force := cCtx.Bool("force")
	path := cCtx.String("path")

	l, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	m := quarto.NewManager(l, quartoVersion, path, ignoreWorkbench)

	return m.Install(force)
}

func QuartoInstallTinyTex(cCtx *cli.Context) error {
	path := cCtx.String("path")
	ignoreWorkbench := cCtx.Bool("ignore-workbench")
	addToPath := cCtx.Bool("add-to-path")

	l, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	m := quarto.NewManager(l, "", path, ignoreWorkbench)

	options := []string{}
	if addToPath {
		options = append(options, "--add-to-path")
	}

	return m.InstallPackage("tinytex", options)
}

func QuartoUpdateTinyTex(cCtx *cli.Context) error {
	path := cCtx.String("path")
	ignoreWorkbench := cCtx.Bool("ignore-workbench")

	l, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	m := quarto.NewManager(l, "", path, ignoreWorkbench)
	return m.UpdatePackage("tinytex", nil)
}
