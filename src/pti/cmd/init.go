package cmd

import (
	"github.com/urfave/cli/v2"
	"pti/system"
	"pti/tools"
)

func Init(cCtx *cli.Context) error {
	system.RequireSudo()

	return tools.Bootstrap()
}
