package cmd

import (
	"github.com/urfave/cli/v2"
	"pti/system"
	"pti/tools/container"
)

func ContainerInstallTini(cCtx *cli.Context) error {
	installPath := cCtx.String("path")

	l, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	m := container.NewTiniManager(l, "", installPath)
	return m.Install()
}

func ContainerInstallWaitForIt(cCtx *cli.Context) error {
	installPath := cCtx.String("path")

	m := container.NewWaitForItManager(installPath)
	return m.Install()
}
