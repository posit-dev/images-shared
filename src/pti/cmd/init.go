package cmd

import (
	"github.com/urfave/cli/v2"
	"pti/system"
	"pti/tools/container"
)

func Init(cCtx *cli.Context) error {
	system.RequireSudo()

	return container.Bootstrap()
}
