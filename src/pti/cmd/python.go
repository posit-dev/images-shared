package cmd

import (
	"github.com/urfave/cli/v2"
	"pti/system"
	"pti/tools/python"
)

func pythonInstall(cCtx *cli.Context) error {
	err := system.RequireSudo()
	if err != nil {
		return err
	}

	localSystem, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	pythonVersion := cCtx.String("version")
	pythonPackages := cCtx.StringSlice("package")
	pythonRequirementFiles := cCtx.StringSlice("requirements-file")
	setDefault := cCtx.Bool("default")
	addToPath := cCtx.Bool("add-to-path")
	addJupyterKernel := cCtx.Bool("add-jupyter-kernel")

	m, err := python.NewManager(localSystem, pythonVersion)
	if err != nil {
		return err
	}
	err = m.Install()
	if err != nil {
		return err
	}

	if len(pythonPackages) > 0 || len(pythonRequirementFiles) > 0 {
		list := &python.PackageList{Packages: pythonPackages, PackageFiles: pythonRequirementFiles}
		err = m.InstallPackages(list, nil)
		if err != nil {
			return err
		}
	}

	if setDefault {
		err = m.MakeDefault()
		if err != nil {
			return err
		}
	}

	if addToPath {
		err = m.AddToPath()
		if err != nil {
			return err
		}
	}

	if addJupyterKernel {
		err = m.AddKernel()
		if err != nil {
			return err
		}
	}

	return nil
}

func pythonInstallPackages(cCtx *cli.Context) error {
	localSystem, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	pythonVersion := cCtx.String("version")

	m, err := python.NewManager(localSystem, pythonVersion)
	if err != nil {
		return err
	}

	pythonPackages := cCtx.StringSlice("package")
	pythonRequirementFiles := cCtx.StringSlice("requirements-file")
	list := &python.PackageList{Packages: pythonPackages, PackageFiles: pythonRequirementFiles}

	return m.InstallPackages(list, nil)
}

func pythonInstallJupyter(cCtx *cli.Context) error {
	localSystem, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	pythonVersion := cCtx.String("version")
	m, err := python.NewManager(localSystem, pythonVersion)
	if err != nil {
		return err
	}

	jupyterPath := cCtx.String("path")
	force := cCtx.Bool("force")

	return m.InstallJupyter4Workbench(jupyterPath, force)
}

func pythonAddKernel(cCtx *cli.Context) error {
	localSystem, err := system.GetLocalSystem()
	if err != nil {
		return err
	}

	pythonVersion := cCtx.String("version")
	m, err := python.NewManager(localSystem, pythonVersion)
	if err != nil {
		return err
	}

	return m.AddKernel()
}
