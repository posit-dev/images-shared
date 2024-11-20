package cmd

import (
	"github.com/urfave/cli/v2"
	"pti/system"
	"pti/tools"
)

const DefaultProDriverVersion = "2024.03.0"

func ProDriversInstall(cCtx *cli.Context) error {
	system.RequireSudo()

	driverVersion := cCtx.String("version")
	if driverVersion == "" {
		driverVersion = DefaultProDriverVersion
	}

	return tools.InstallProDrivers(driverVersion)
}
