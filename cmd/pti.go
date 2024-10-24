package main

import (
	"fmt"
	"github.com/pterm/pterm"
	"github.com/urfave/cli/v2"
	"log"
	"log/slog"
	"os"
	"posit-images-shared/internal/system"
	"posit-images-shared/internal/tools"
	"runtime"
)

func main() {
	if runtime.GOOS != "linux" {
		log.Fatal("pti is only supported on Linux")
	}

	logger := slog.New(pterm.NewSlogHandler(&pterm.DefaultLogger))
	slog.SetDefault(logger)

	app := &cli.App{
		Name:        "pti",
		Usage:       "Posit Tools Installer",
		Description: "Install and manage third-party tools related to Posit products",
		Flags: []cli.Flag{
			&cli.BoolFlag{
				Name:    "debug",
				Aliases: []string{"d"},
				Usage:   "Enable debug mode",
				Action: func(c *cli.Context, debugMode bool) error {
					if debugMode {
						pterm.DefaultLogger.Level = pterm.LogLevelDebug
					}
					return nil
				},
			},
		},
		Commands: []*cli.Command{
			{
				Name:  "pro-drivers",
				Usage: "Install or manage Posit Pro Drivers",
				Subcommands: []*cli.Command{
					{
						Name:  "install",
						Usage: "Install Posit Pro Drivers",
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:        "version",
								Aliases:     []string{"V"},
								Usage:       "Posit Pro Drivers version to install",
								DefaultText: "2024.03.0",
							},
						},
						Action: func(cCtx *cli.Context) error {
							system.RequireSudo()

							driverVersion := cCtx.String("version")
							if driverVersion == "" {
								driverVersion = "2024.03.0"
							}

							return tools.InstallProDrivers(driverVersion)
						},
					},
				},
			},
			{
				Name:  "python",
				Usage: "Install or manage Python versions",
				Subcommands: []*cli.Command{
					{
						Name:  "install",
						Usage: "Install a Python version",
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:     "version",
								Aliases:  []string{"V"},
								Usage:    "Python version to install",
								Required: true,
							},
							&cli.StringSliceFlag{
								Name:     "package",
								Aliases:  []string{"p"},
								Usage:    "Python package(s) to install",
								Category: "Package installation:",
							},
							&cli.StringSliceFlag{
								Name:     "requirements-file",
								Aliases:  []string{"r"},
								Usage:    "Path to requirements file(s) to install",
								Category: "Package installation:",
							},
							&cli.BoolFlag{
								Name:    "default",
								Aliases: []string{"D"},
								Usage:   "Symlink the installed Python version to /opt/python/default",
							},
							&cli.BoolFlag{
								Name:    "add-to-path",
								Aliases: []string{"P"},
								Usage:   "Add the installed Python version to the PATH",
							},
							&cli.BoolFlag{
								Name:    "add-jupyter-kernel",
								Aliases: []string{"k"},
								Usage:   "Install a Jupyter kernel for the Python version",
							},
						},
						Action: func(cCtx *cli.Context) error {
							system.RequireSudo()

							pythonVersion := cCtx.String("version")
							pythonPackages := cCtx.StringSlice("package")
							pythonRequirementFiles := cCtx.StringSlice("requirements-file")
							setDefault := cCtx.Bool("default")
							addToPath := cCtx.Bool("add-to-path")
							addJupyterKernel := cCtx.Bool("add-jupyter-kernel")

							return tools.InstallPython(pythonVersion, &pythonPackages, &pythonRequirementFiles, setDefault, addToPath, addJupyterKernel)
						},
					},
					{
						Name:  "install-packages",
						Usage: "Install Python packages",
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:    "version",
								Aliases: []string{"V"},
								Usage:   "Python version to install",
							},
							&cli.StringFlag{
								Name:  "python-path",
								Usage: "Path to Python installation, assumes /opt/python/<version>/bin/python if not provided",
							},
							&cli.StringSliceFlag{
								Name:    "package",
								Aliases: []string{"p"},
								Usage:   "Python package(s) to install",
							},
							&cli.StringSliceFlag{
								Name:    "requirements-file",
								Aliases: []string{"r"},
								Usage:   "Path to requirements file(s) to install",
							},
						},
						Action: func(cCtx *cli.Context) error {
							pythonVersion := cCtx.String("version")

							pythonPath := cCtx.String("python-path")
							if pythonPath == "" {
								if pythonVersion == "" {
									return fmt.Errorf("Python version or path must be provided")
								}

								pythonPath := "/opt/python/" + pythonVersion + "/bin/python" // Assume pythonPath if not given
								slog.Info("Assuming Python binary path " + pythonPath)
							}
							// Check that binary exists
							exists, err := system.PathExists(pythonPath)
							if err != nil {
								return err
							}
							if !exists {
								return fmt.Errorf("Python binary does not exist at path %s", pythonPath)
							}

							pythonPackages := cCtx.StringSlice("package")
							pythonRequirementFiles := cCtx.StringSlice("requirements-file")

							return tools.InstallPythonPackages(pythonPath, &pythonPackages, &pythonRequirementFiles)
						},
					},
					{
						Name:  "install-jupyter",
						Usage: "Install Jupyter 4 for use with Workbench",
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:    "version",
								Aliases: []string{"V"},
								Usage:   "Python version to use for Jupyter environment",
							},
							&cli.StringFlag{
								Name:  "python-path",
								Usage: "Path to Python installation to create environment from, assumes /opt/python/<version>/bin/python if not provided",
							},
							&cli.StringFlag{
								Name:        "jupyter-path",
								Usage:       "Path to install Jupyter to",
								DefaultText: "/opt/python/jupyter",
							},
							&cli.BoolFlag{
								Name:    "force",
								Aliases: []string{"f"},
								Usage:   "Force installation of Jupyter to <jupyter-path>, even if the path is not empty",
							},
						},
						Action: func(cCtx *cli.Context) error {
							pythonVersion := cCtx.String("version")

							pythonPath := cCtx.String("python-path")
							if pythonPath == "" {
								if pythonVersion == "" {
									return fmt.Errorf("Python version or path must be provided")
								}

								pythonPath := "/opt/python/" + pythonVersion + "/bin/python" // Assume pythonPath if not given
								slog.Info("Assuming Python binary path " + pythonPath)
							}
							// Check that binary exists
							exists, err := system.PathExists(pythonPath)
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
						},
					},
					{
						Name:  "add-jupyter-kernel",
						Usage: "Add a Jupyter kernel for a Python version",
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:    "version",
								Aliases: []string{"V"},
								Usage:   "Python version to use for Jupyter environment",
							},
							&cli.StringFlag{
								Name:  "python-path",
								Usage: "Path to Python installation to add, assumes /opt/python/<version>/bin/python if not provided",
							},
							&cli.StringFlag{
								Name:  "machine-name",
								Usage: "Machine readable name for the kernel",
							},
							&cli.StringFlag{
								Name:  "display-name",
								Usage: "Display name for the kernel",
							},
						},
						Action: func(cCtx *cli.Context) error {
							pythonVersion := cCtx.String("version")

							machineName := cCtx.String("machine-name")
							displayName := cCtx.String("display-name")

							pythonPath := cCtx.String("python-path")
							if pythonPath == "" {
								if pythonVersion == "" {
									return fmt.Errorf("Python version or path must be provided")
								}

								pythonPath := "/opt/python/" + pythonVersion + "/bin/python" // Assume pythonPath if not given
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
							exists, err := system.PathExists(pythonPath)
							if err != nil {
								return err
							}
							if !exists {
								return fmt.Errorf("Python binary does not exist at path %s", pythonPath)
							}

							return tools.ConfigureIPythonKernel(pythonPath, machineName, displayName)
						},
					},
				},
			},
			{
				Name:  "r",
				Usage: "Install or manage R versions",
				Subcommands: []*cli.Command{
					{
						Name:  "install",
						Usage: "Install a R version",
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:     "version",
								Aliases:  []string{"V"},
								Usage:    "Python version to install",
								Required: true,
							},
							&cli.StringSliceFlag{
								Name:    "package",
								Aliases: []string{"p"},
								Usage:   "Python package(s) to install",
							},
							&cli.StringSliceFlag{
								Name:    "packages-file",
								Aliases: []string{"f"},
								Usage:   "Path to requirements file(s) to install",
							},
							&cli.BoolFlag{
								Name:    "default",
								Aliases: []string{"D"},
								Usage:   "Symlink the installed R version to /opt/R/default",
							},
							&cli.BoolFlag{
								Name:    "add-to-path",
								Aliases: []string{"P"},
								Usage:   "Add the installed R version to the PATH",
							},
						},
						Action: func(cCtx *cli.Context) error {
							system.RequireSudo()

							rVersion := cCtx.String("version")
							rPackages := cCtx.StringSlice("package")
							rPackagesFiles := cCtx.StringSlice("packages-file")
							setDefault := cCtx.Bool("set-default")
							addToPath := cCtx.Bool("add-to-path")

							return tools.InstallR(rVersion, &rPackages, &rPackagesFiles, setDefault, addToPath)
						},
					},
					{
						Name:  "install-packages",
						Usage: "Install Python packages",
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:    "version",
								Aliases: []string{"V"},
								Usage:   "Python version to install",
							},
							&cli.StringFlag{
								Name:  "r-path",
								Usage: "Path to R installation",
							},
							&cli.StringSliceFlag{
								Name:    "package",
								Aliases: []string{"p"},
								Usage:   "Python package(s) to install",
							},
							&cli.StringSliceFlag{
								Name:    "packages-file",
								Aliases: []string{"f"},
								Usage:   "Path to requirements file(s) to install",
							},
						},
						Action: func(cCtx *cli.Context) error {
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
							exists, err := system.PathExists(rPath)
							if err != nil {
								return err
							}
							if !exists {
								return fmt.Errorf("R binary does not exist at path %s", rPath)
							}

							rPackages := cCtx.StringSlice("package")
							rPackagesFiles := cCtx.StringSlice("packages-file")

							return tools.InstallRPackages(rPath, &rPackages, &rPackagesFiles)
						},
					},
				},
			},
			{
				Name:  "quarto",
				Usage: "Install or manage Quarto",
				Subcommands: []*cli.Command{
					{
						Name:  "install",
						Usage: "Install Quarto",
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:    "version",
								Aliases: []string{"V"},
								Usage:   "Quarto version to install",
							},
							&cli.BoolFlag{
								Name:  "install-tinytex",
								Usage: "Install Quarto TinyTeX",
							},
							&cli.BoolFlag{
								Name:  "add-path-tinytex",
								Usage: "Add Quarto TinyTeX to PATH",
							},
							&cli.BoolFlag{
								Name:    "force",
								Aliases: []string{"f"},
								Usage:   "Force installation of Quarto if it is already installed or is present in Posit Workbench",
							},
						},
						Action: func(cCtx *cli.Context) error {
							system.RequireSudo()

							quartoVersion := cCtx.String("version")
							force := cCtx.Bool("force")
							workbenchQuartoExists, err := system.PathExists("/opt/posit-workbench/quarto")
							if err != nil {
								return err
							}
							if quartoVersion == "" && (!workbenchQuartoExists && force) {
								return fmt.Errorf("Quarto version must be provided")
							}

							installTinyTex := cCtx.Bool("install-tinytex")
							addPathTinyTex := cCtx.Bool("add-path-tinytex")

							return tools.InstallQuarto(quartoVersion, installTinyTex, addPathTinyTex, force)
						},
					},
					{
						Name:  "install-tinytex",
						Usage: "Install Quarto TinyTeX",
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:  "quarto-path",
								Usage: "Path to Quarto installation",
							},
							&cli.BoolFlag{
								Name:  "add-path-tinytex",
								Usage: "Add Quarto TinyTeX to PATH",
							},
						},
						Action: func(cCtx *cli.Context) error {
							quartoPath := cCtx.String("quarto-path")
							if quartoPath == "" {
								quartoPath = "/opt/quarto/bin/quarto"

								exists, err := system.PathExists(quartoPath)
								if err != nil {
									return err
								}
								if !exists {
									slog.Debug("Quarto binary does not exist at path %s", quartoPath)
								}

								workbenchQuartoBinPath := tools.WorkbenchQuartoPath + "/bin/quarto"

								exists, err = system.PathExists(workbenchQuartoBinPath)
								if err != nil {
									return err
								}
								if !exists {
									return fmt.Errorf("Could not find Quarto binary at %s or %s", quartoPath, workbenchQuartoBinPath)
								}
							}

							var options []string
							addToPath := cCtx.Bool("add-path-tinytex")
							if addToPath {
								options = append(options, "--update-path")
							}

							return tools.InstallQuartoTool(quartoPath, "tinytex", &options)
						},
					},
					{
						Name:  "update-tinytex",
						Usage: "Update Quarto TinyTeX",
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:  "quarto-path",
								Usage: "Path to Quarto installation",
							},
						},
						Action: func(cCtx *cli.Context) error {
							quartoPath := cCtx.String("quarto-path")
							if quartoPath == "" {
								quartoPath = "/opt/quarto/bin/quarto"
							}

							exists, err := system.PathExists(quartoPath)
							if err != nil {
								return err
							}
							if !exists {
								return fmt.Errorf("Quarto binary does not exist at path %s", quartoPath)
							}

							return tools.UpdateQuartoTool(quartoPath, "tinytex", &[]string{})
						},
					},
				},
			},
			{
				Name:  "container",
				Usage: "Install or manage optional container-specific tooling",
				Subcommands: []*cli.Command{
					{
						Name:  "install-tini",
						Usage: "Install Tini",
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:        "install-path",
								Usage:       "Path to install Tini",
								DefaultText: "/usr/bin/tini",
							},
						},
						Action: func(cCtx *cli.Context) error {
							system.RequireSudo()

							installPath := cCtx.String("install-path")
							if installPath == "" {
								installPath = "/usr/bin/tini"
							}

							return tools.InstallTini(installPath)
						},
					},
					{
						Name:  "install-wait-for-it",
						Usage: "Install Wait-for-it",
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:        "install-path",
								Usage:       "Path to install Tini",
								DefaultText: "/usr/bin/wait-for-it",
							},
						},
						Action: func(cCtx *cli.Context) error {
							system.RequireSudo()

							installPath := cCtx.String("install-path")
							if installPath == "" {
								installPath = "/usr/bin/wait-for-it"
							}

							return tools.InstallWaitForIt(installPath)
						},
					},
					{
						Name:  "syspkg",
						Usage: "Manage system package installations",
						Subcommands: []*cli.Command{
							{
								Name:  "update",
								Usage: "Update package lists",
								Action: func(context *cli.Context) error {
									return system.UpdatePackageLists()
								},
							},
							{
								Name:  "upgrade",
								Usage: "Upgrade installed packages",
								Flags: []cli.Flag{
									&cli.BoolFlag{
										Name:  "dist",
										Usage: "Run dist-upgrade on Debian-based systems",
									},
								},
								Action: func(context *cli.Context) error {
									return system.UpgradePackages(context.Bool("dist"))
								},
							},
							{
								Name:  "install",
								Usage: "Install system packages",
								Flags: []cli.Flag{
									&cli.StringSliceFlag{
										Name:    "package",
										Aliases: []string{"p"},
										Usage:   "Package(s) to install",
									},
									&cli.StringSliceFlag{
										Name:    "packages-file",
										Aliases: []string{"f"},
										Usage:   "Path to file containing package names to install",
									},
								},
								Action: func(context *cli.Context) error {
									if len(context.StringSlice("package")) > 0 {
										return system.InstallPackages(context.StringSlice("package"))
									}
									if len(context.StringSlice("packages-file")) > 0 {
										return system.InstallPackagesFiles(context.StringSlice("packages-file"))
									}
									return nil
								},
							},
							{
								Name:  "clean",
								Usage: "Clean up package caches",
								Action: func(context *cli.Context) error {
									return system.CleanPackages()
								},
							},
						},
					},
				},
			},
		},
	}
	if err := app.Run(os.Args); err != nil {
		log.Fatal(err)
	}
}
