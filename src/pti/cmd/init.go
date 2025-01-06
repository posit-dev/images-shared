package cmd

import (
	"pti/system"
	"pti/tools/container"

	"github.com/urfave/cli/v2"
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
