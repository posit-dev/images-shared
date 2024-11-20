package cmd

import (
	"github.com/urfave/cli/v2"
	"pti/system"
	"pti/tools"
)

func ContainerInstallTini(cCtx *cli.Context) error {
	system.RequireSudo()

	installPath := cCtx.String("install-path")
	if installPath == "" {
		installPath = "/usr/bin/tini"
	}

	return tools.InstallTini(installPath)
}

func ContainerInstallWaitForIt(cCtx *cli.Context) error {
	system.RequireSudo()

	installPath := cCtx.String("install-path")
	if installPath == "" {
		installPath = "/usr/bin/wait-for-it"
	}

	return tools.InstallWaitForIt(installPath)
}
