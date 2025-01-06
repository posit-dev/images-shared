package cmd

import (
	"pti/system"
	"pti/tools/drivers"

	"github.com/urfave/cli/v2"
)

func driversInstall(cCtx *cli.Context) error {
	err := system.RequireSudo()
	if err != nil {
		return err
	}

	localSystem, err := system.GetLocalSystem()
	if err != nil {
		return err
	}
	m := drivers.NewManager(localSystem, cCtx.String("version"))

	return m.Install()
}

func driversUpdate(cCtx *cli.Context) error {
	err := system.RequireSudo()
	if err != nil {
		return err
	}

	localSystem, err := system.GetLocalSystem()
	if err != nil {
		return err
	}
	m := drivers.NewManager(localSystem, cCtx.String("version"))

	return m.Update()
}

func driversRemove(cCtx *cli.Context) error {
	err := system.RequireSudo()
	if err != nil {
		return err
	}

	localSystem, err := system.GetLocalSystem()
	if err != nil {
		return err
	}
	m := drivers.NewManager(localSystem, cCtx.String("version"))

	return m.Remove()
}
