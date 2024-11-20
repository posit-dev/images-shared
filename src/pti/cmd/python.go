package cmd

import (
	"fmt"
	"github.com/urfave/cli/v2"
	"log/slog"
	"pti/system"
	"pti/tools"
)

func PythonInstall(cCtx *cli.Context) error {
	system.RequireSudo()

	pythonVersion := cCtx.String("version")
	pythonPackages := cCtx.StringSlice("package")
	pythonRequirementFiles := cCtx.StringSlice("requirements-file")
	setDefault := cCtx.Bool("default")
	addToPath := cCtx.Bool("add-to-path")
	addJupyterKernel := cCtx.Bool("add-jupyter-kernel")

	return tools.InstallPython(pythonVersion, &pythonPackages, &pythonRequirementFiles, setDefault, addToPath, addJupyterKernel)
}

func PythonInstallPackages(cCtx *cli.Context) error {
	pythonVersion := cCtx.String("version")

	pythonPath := cCtx.String("python-path")
	if pythonPath == "" {
		if pythonVersion == "" {
			return fmt.Errorf("Python version or path must be provided")
		}

		pythonPath = "/opt/python/" + pythonVersion + "/bin/python3" // Assume pythonPath if not given
		slog.Info("Assuming Python binary path " + pythonPath)
	}
	// Check that binary exists
	exists, err := system.IsPathExist(pythonPath)
	if err != nil {
		return err
	}
	if !exists {
		return fmt.Errorf("Python binary does not exist at path %s", pythonPath)
	}

	pythonPackages := cCtx.StringSlice("package")
	pythonRequirementFiles := cCtx.StringSlice("requirements-file")

	return tools.InstallPythonPackages(pythonPath, &pythonPackages, &pythonRequirementFiles)
}

func PythonInstallJupyter(cCtx *cli.Context) error {
	pythonVersion := cCtx.String("version")

	pythonPath := cCtx.String("python-path")
	if pythonPath == "" {
		if pythonVersion == "" {
			return fmt.Errorf("Python version or path must be provided")
		}

		pythonPath = "/opt/python/" + pythonVersion + "/bin/python3" // Assume pythonPath if not given
		slog.Info("Assuming Python binary path " + pythonPath)
	}
	// Check that binary exists
	exists, err := system.IsPathExist(pythonPath)
	if err != nil {
		return err
	}
	if !exists {
		return fmt.Errorf("Python binary does not exist at path %s", pythonPath)
	}

	jupyterPath := cCtx.String("jupyter-path")
	if jupyterPath == "" {
		jupyterPath = "/opt/python/jupyter"
	}

	force := cCtx.Bool("force")

	return tools.InstallJupyter4Workbench(pythonPath, jupyterPath, force)
}

func PythonAddJupyterKernel(cCtx *cli.Context) error {
	pythonVersion := cCtx.String("version")

	machineName := cCtx.String("machine-name")
	displayName := cCtx.String("display-name")

	pythonPath := cCtx.String("python-path")
	if pythonPath == "" {
		if pythonVersion == "" {
			return fmt.Errorf("Python version or path must be provided")
		}

		pythonPath = "/opt/python/" + pythonVersion + "/bin/python3" // Assume pythonPath if not given
		slog.Info("Assuming Python binary path " + pythonPath)
	} else {
		if machineName == "" && pythonVersion == "" {
			return fmt.Errorf("Machine name must be provided if only providing python path")
		} else if machineName == "" {
			machineName = "py" + pythonVersion
		}

		if displayName == "" && pythonVersion == "" {
			return fmt.Errorf("Display name must be provided if only providing python path")
		} else if displayName == "" {
			displayName = "Python " + pythonVersion
		}
	}

	// Check that binary exists
	exists, err := system.IsPathExist(pythonPath)
	if err != nil {
		return err
	}
	if !exists {
		return fmt.Errorf("Python binary does not exist at path %s", pythonPath)
	}

	return tools.ConfigureIPythonKernel(pythonPath, machineName, displayName)
}
