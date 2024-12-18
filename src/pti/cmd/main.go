package cmd

import (
	"github.com/pterm/pterm"
	"github.com/urfave/cli/v2"
	"log/slog"
	"pti/tools/drivers"
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

							versionFlag("Posit Pro Drivers version to install", drivers.DefaultVersion),
						},
						Action: driversInstall,
					},
					{
						Name:  "upgrade",
						Usage: "Remove and reinstall Posit Pro Drivers",
						Flags: []cli.Flag{
							versionFlag("Posit Pro Drivers version to install", drivers.DefaultVersion),
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
				Flags: []cli.Flag{
					versionFlag("Python version to use", ""),
				},
				Subcommands: []*cli.Command{
					{
						Name:  "install",
						Usage: "Install a Python version",
						Flags: []cli.Flag{
							packageFlag("Python package(s) to install"),
							packageFileFlag("Path to requirements file(s) to install"),
							defaultFlag("Symlink the installed Python version to /opt/python/default"),
							addToPathFlag("Symlink the installed Python version to /usr/local/bin/python<version>"),
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
									forceFlag("Force installation of Jupyter if it is already installed"),
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
						Action: RInstall,
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
						Action: RInstallPackages,
					},
				},
			},
			{
				Name:     "quarto",
				Usage:    "Install or manage Quarto",
				Category: "tools",
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
						Action: QuartoInstall,
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
						Action: QuartoInstallTinyTex,
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
						Action: QuartoUpdateTinyTex,
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
							&cli.StringFlag{
								Name:        "install-path",
								Usage:       "Path to install Tini",
								DefaultText: "/usr/bin/tini",
							},
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
							&cli.StringFlag{
								Name:        "install-path",
								Usage:       "Path to install Tini",
								DefaultText: "/usr/bin/wait-for-it",
							},
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
