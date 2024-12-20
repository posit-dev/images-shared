package cmd

import (
	"github.com/urfave/cli/v2"
	"pti/system"
	"pti/tools/container"
)

func bootstrap(cCtx *cli.Context) error {
	err := system.RequireSudo()
	if err != nil {
		return err
	}

	localSystem, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	return container.Bootstrap(localSystem)
}
