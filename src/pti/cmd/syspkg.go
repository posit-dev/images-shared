package cmd

import (
	"github.com/urfave/cli/v2"
	"pti/system"
)

func SysPkgUpdate(context *cli.Context) error {
	return system.UpdatePackageLists()
}

func SysPkgUpgrade(context *cli.Context) error {
	return system.UpgradePackages(context.Bool("dist"))
}

func SysPkgInstall(context *cli.Context) error {
	packages := context.StringSlice("package")
	if len(packages) > 0 {
		return system.InstallPackages(&packages)
	}
	packageFiles := context.StringSlice("packages-file")
	if len(packageFiles) > 0 {
		return system.InstallPackagesFiles(&packageFiles)
	}
	return nil
}

func SysPkgUninstall(cCtx *cli.Context) error {
	packages := cCtx.StringSlice("package")
	if len(packages) > 0 {
		return system.RemovePackages(&packages)
	}
	return nil
}

func SysPkgClean(context *cli.Context) error {
	return system.CleanPackages()
}
