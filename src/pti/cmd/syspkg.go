package cmd

import (
	"fmt"
	"github.com/urfave/cli/v2"
	"pti/system"
	"pti/system/syspkg"
)

func SysPkgUpdate(cCtx *cli.Context) error {
	err := system.RequireSudo()
	if err != nil {
		return err
	}

	l, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	return l.PackageManager.Update()
}

func SysPkgUpgrade(cCtx *cli.Context) error {
	err := system.RequireSudo()
	if err != nil {
		return err
	}

	l, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	err = l.PackageManager.Update()
	defer l.PackageManager.Clean()
	if err != nil {
		return fmt.Errorf("failed to update package manager: %w", err)
	}

	fullUpgrade := cCtx.Bool("dist")

	return l.PackageManager.Upgrade(fullUpgrade)
}

func SysPkgInstall(cCtx *cli.Context) error {
	err := system.RequireSudo()
	if err != nil {
		return err
	}

	l, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	err = l.PackageManager.Update()
	defer l.PackageManager.Clean()
	if err != nil {
		return fmt.Errorf("failed to update package manager: %w", err)
	}

	packages := cCtx.StringSlice("package")
	packageFiles := cCtx.StringSlice("packages-file")
	pkgList := &syspkg.PackageList{Packages: packages, PackageListFiles: packageFiles}

	return l.PackageManager.Install(pkgList)
}

func SysPkgUninstall(cCtx *cli.Context) error {
	err := system.RequireSudo()
	if err != nil {
		return err
	}

	l, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	packages := cCtx.StringSlice("package")
	pkgList := &syspkg.PackageList{Packages: packages}

	return l.PackageManager.Remove(pkgList)
}

func SysPkgClean(cCtx *cli.Context) error {
	err := system.RequireSudo()
	if err != nil {
		return err
	}

	l, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	return l.PackageManager.Clean()
}
