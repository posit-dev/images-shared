package cmd

import (
	"github.com/urfave/cli/v2"
	"pti/system"
	container2 "pti/tools/container"
)

func ContainerInstallTini(cCtx *cli.Context) error {
	system.RequireSudo()

	installPath := cCtx.String("install-path")
	if installPath == "" {
		installPath = "/usr/bin/tini"
	}

	return container2.InstallTini(installPath)
}

func ContainerInstallWaitForIt(cCtx *cli.Context) error {
	system.RequireSudo()

	installPath := cCtx.String("install-path")
	if installPath == "" {
		installPath = "/usr/bin/wait-for-it"
	}

	return container2.InstallWaitForIt(installPath)
}
