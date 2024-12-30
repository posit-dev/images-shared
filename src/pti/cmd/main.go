package cmd

import (
	"log/slog"
	"pti/tools/container"
	"pti/tools/drivers"
	"pti/tools/quarto"

	"github.com/pterm/pterm"
	"github.com/urfave/cli/v2"
)

func Cli() *cli.App {
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
						slog.Info("Debug mode enabled")
						pterm.DefaultLogger.Level = pterm.LogLevelDebug
					}

					return nil
				},
			},
		},
		Commands: []*cli.Command{
			{
				Name:   "init",
				Usage:  "Initialize environment with necessary tools and packages",
				Action: bootstrap,
			},
			{
				Name:     "pro-drivers",
				Usage:    "Install or manage Posit Pro Drivers",
				Category: "tools",
				Subcommands: []*cli.Command{
					{
						Name:  "install",
						Usage: "Install Posit Pro Drivers",
						Flags: []cli.Flag{
							versionFlag(
								"Posit Pro Drivers version to install",
								drivers.DefaultVersion,
							),
						},
						Action: driversInstall,
					},
					{
						Name:  "upgrade",
						Usage: "Remove and reinstall Posit Pro Drivers",
						Flags: []cli.Flag{
							versionFlag(
								"Posit Pro Drivers version to install",
								drivers.DefaultVersion,
							),
						},
						Action: driversUpdate,
					},
					{
						Name:   "remove",
						Usage:  "Remove Posit Pro Drivers",
						Flags:  []cli.Flag{},
						Action: driversRemove,
					},
				},
			},
			{
				Name:     "python",
				Usage:    "Install or manage Python versions",
				Category: "tools",
				Flags:    []cli.Flag{},
				Subcommands: []*cli.Command{
					{
						Name:  "install",
						Usage: "Install a Python version",
						Flags: []cli.Flag{
							versionFlag("Python version to install", ""),
							packageFlag("Python package(s) to install"),
							packageFileFlag("Path to requirements file(s) to install"),
							defaultFlag(
								"Symlink the installed Python version to /opt/python/default",
							),
							addToPathFlag(
								"Symlink the installed Python version to /usr/local/bin/python<version>",
							),
							&cli.BoolFlag{
								Name:    "add-jupyter-kernel",
								Aliases: []string{"k"},
								Usage:   "Install a Jupyter kernel for the Python version",
							},
						},
						Action: pythonInstall,
					},
					{
						Name:  "packages",
						Usage: "Manage Python packages",
						Flags: []cli.Flag{},
						Subcommands: []*cli.Command{
							{
								Name:  "install",
								Usage: "Install Python packages",
								Flags: []cli.Flag{
									versionFlag("Python version to use", ""),
									packageFlag("Python package(s) to install"),
									packageFileFlag("Path to requirements file(s) to install"),
								},
								Action: pythonInstallPackages,
							},
						},
					},
					{
						Name:  "jupyter",
						Usage: "Install or manage Jupyter and its kernels",
						Flags: []cli.Flag{
							versionFlag("Python version to use", ""),
						},
						Subcommands: []*cli.Command{
							{
								Name:  "install",
								Usage: "Install Jupyter 4 for use with Workbench",
								Flags: []cli.Flag{
									&cli.StringFlag{
										Name:        "path",
										Usage:       "Path to install Jupyter to",
										DefaultText: "/opt/python/jupyter",
									},
									forceFlag(
										"Force installation of Jupyter if it is already installed",
									),
								},
								Action: pythonInstallJupyter,
							},
							{
								Name:   "add-kernel",
								Usage:  "Add a Jupyter kernel for a Python version",
								Flags:  []cli.Flag{},
								Action: pythonAddKernel,
							},
						},
					},
				},
			},
			{
				Name:     "r",
				Usage:    "Install or manage R versions",
				Category: "tools",
				Subcommands: []*cli.Command{
					{
						Name:  "install",
						Usage: "Install a R version",
						Flags: []cli.Flag{
							versionFlag("R version to install", ""),
							packageFlag("R package(s) to install"),
							packageFileFlag("Path to package list file(s) to install"),
							defaultFlag("Symlink the installed R version to /opt/R/default"),
							addToPathFlag(
								"Symlink the installed R version to /usr/local/bin/R<version>",
							),
						},
						Action: rInstall,
					},
					{
						Name:  "packages",
						Usage: "Install R packages",
						Flags: []cli.Flag{
							versionFlag("R version to use", ""),
						},
						Subcommands: []*cli.Command{
							{
								Name:  "install",
								Usage: "Install R packages",
								Flags: []cli.Flag{
									packageFlag("R package(s) to install"),
									packageFileFlag("Path to package list file(s) to install"),
								},
								Action: rInstallPackages,
							},
						},
					},
				},
			},
			{
				Name:  "quarto",
				Usage: "Install or manage Quarto",
				Flags: []cli.Flag{
					&cli.BoolFlag{
						Name:  "ignore-workbench",
						Usage: "Disable auto-selection of Workbench Quarto if it exists",
					},
				},
				Category: "tools",
				Subcommands: []*cli.Command{
					{
						Name:  "install",
						Usage: "Install Quarto",
						Flags: []cli.Flag{
							versionFlag("Quarto version to install", ""),
							forceFlag("Force installation of Quarto if it is already installed"),
							pathFlag("Path to install Quarto to", quarto.DefaultInstallPath),
						},
						Action: QuartoInstall,
					},
					{
						Name:  "tinytex",
						Usage: "Manage Quarto TinyTeX tool",
						Flags: []cli.Flag{
							pathFlag("Path to Quarto installation", quarto.DefaultInstallPath),
						},
						Subcommands: []*cli.Command{
							{
								Name:  "install",
								Usage: "Install Quarto TinyTeX",
								Flags: []cli.Flag{
									addToPathFlag("Add Quarto TinyTeX to PATH"),
								},
								Action: QuartoInstallTinyTex,
							},
							{
								Name:   "update",
								Usage:  "Update Quarto TinyTeX",
								Action: QuartoUpdateTinyTex,
							},
						},
					},
				},
			},
			{
				Name:     "tini",
				Usage:    "Install or manage tini init tool for containers",
				Category: "container",
				Subcommands: []*cli.Command{
					{
						Name:  "install",
						Usage: "Install tini",
						Flags: []cli.Flag{
							pathFlag("Path to install Tini to", container.DefaultTiniPath),
						},
						Action: ContainerInstallTini,
					},
				},
			},
			{
				Name:     "wait-for-it",
				Usage:    "Install or manage wait-for-it helper script for containers",
				Category: "container",
				Subcommands: []*cli.Command{
					{
						Name:  "install",
						Usage: "Install wait-for-it script",
						Flags: []cli.Flag{
							pathFlag(
								"Path to install wait-for-it to",
								container.DefaultWaitForItPath,
							),
						},
						Action: ContainerInstallWaitForIt,
					},
				},
			},
			{
				Name:     "syspkg",
				Usage:    "Manage system package installations",
				Category: "container",
				Subcommands: []*cli.Command{
					{
						Name:   "update",
						Usage:  "Update package lists",
						Action: SysPkgUpdate,
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
						Action: SysPkgUpgrade,
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
						Action: SysPkgInstall,
					},
					{
						Name:  "uninstall",
						Usage: "Uninstall system packages",
						Flags: []cli.Flag{
							&cli.StringSliceFlag{
								Name:    "package",
								Aliases: []string{"p"},
								Usage:   "Package(s) to install",
							},
						},
						Action: SysPkgUninstall,
					},
					{
						Name:   "clean",
						Usage:  "Clean up package caches",
						Action: SysPkgClean,
					},
				},
			},
		},
	}

	return app
}
