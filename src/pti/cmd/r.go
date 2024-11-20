package cmd

import (
	"fmt"
	"github.com/urfave/cli/v2"
	"log/slog"
	"pti/system"
	"pti/tools"
)

func RInstall(cCtx *cli.Context) error {
	system.RequireSudo()

	rVersion := cCtx.String("version")
	rPackages := cCtx.StringSlice("package")
	rPackagesFiles := cCtx.StringSlice("packages-file")
	setDefault := cCtx.Bool("set-default")
	addToPath := cCtx.Bool("add-to-path")

	return tools.InstallR(rVersion, &rPackages, &rPackagesFiles, setDefault, addToPath)
}

func RInstallPackages(cCtx *cli.Context) error {
	rVersion := cCtx.String("version")

	rPath := cCtx.String("r-path")
	// Assume rPath if not given
	if rPath == "" {
		if rVersion == "" {
			return fmt.Errorf("R version or path must be provided")
		}

		rPath = "/opt/R/" + rVersion + "/bin/R"
		slog.Info("Assuming R binary path " + rPath)
	}

	// Check that binary exists
	exists, err := system.IsPathExist(rPath)
	if err != nil {
		return err
	}
	if !exists {
		return fmt.Errorf("R binary does not exist at path %s", rPath)
	}

	rPackages := cCtx.StringSlice("package")
	rPackagesFiles := cCtx.StringSlice("packages-file")

	return tools.InstallRPackages(rPath, &rPackages, &rPackagesFiles)
}
