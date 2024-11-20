package cmd

import (
	"github.com/urfave/cli/v2"
	"pti/system"
	"pti/tools"
)

func Bootstrap(cCtx *cli.Context) error {
	system.RequireSudo()

	return tools.Bootstrap()
}

func ContainerInstallTini(cCtx *cli.Context) error {
	system.RequireSudo()

	installPath := cCtx.String("install-path")
	if installPath == "" {
		installPath = "/usr/bin/tini"
	}

	return tools.InstallTini(installPath)
}

func ContainerInstallWaitForIt(cCtx *cli.Context) error {
	system.RequireSudo()

	installPath := cCtx.String("install-path")
	if installPath == "" {
		installPath = "/usr/bin/wait-for-it"
	}

	return tools.InstallWaitForIt(installPath)
}

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
