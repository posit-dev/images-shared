package cmd

import (
	"log/slog"
	"pti/system"
	"pti/tools/r"

	"github.com/urfave/cli/v2"
)

//nolint:cyclop
func rInstall(cCtx *cli.Context) error {
	err := system.RequireSudo()
	if err != nil {
		return err
	}

	rVersion := cCtx.String("version")
	rPackages := cCtx.StringSlice("package")
	rPackagesFiles := cCtx.StringSlice("packages-file")
	setDefault := cCtx.Bool("default")
	addToPath := cCtx.Bool("add-to-path")

	l, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	m := r.NewManager(l, rVersion)
	err = m.Install()
	if err != nil {
		slog.Error("Failed to install R " + rVersion)

		return err
	}

	if len(rPackages) > 0 || len(rPackagesFiles) > 0 {
		list := &r.PackageList{Packages: rPackages, PackageFiles: rPackagesFiles}
		err = m.InstallPackages(list)
		if err != nil {
			slog.Error("Failed to install R packages: " + err.Error())
		}
	}

	if setDefault {
		err = m.MakeDefault()
		if err != nil {
			slog.Error("Failed to set R " + rVersion + " as default")
		}
	}

	if addToPath {
		err = m.AddToPath(true)
		if err != nil {
			slog.Error("Failed to add R " + rVersion + " to PATH")
		}
	}

	return nil
}

func rInstallPackages(cCtx *cli.Context) error {
	rVersion := cCtx.String("version")
	rPackages := cCtx.StringSlice("package")
	rPackagesFiles := cCtx.StringSlice("packages-file")

	l, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	m := r.NewManager(l, rVersion)
	list := &r.PackageList{Packages: rPackages, PackageFiles: rPackagesFiles}

	return m.InstallPackages(list)
}
