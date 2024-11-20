package main

import (
	"github.com/pterm/pterm"
	"github.com/urfave/cli/v2"
	"log"
	"log/slog"
	"os"
	"pti/cmd"
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
				Action: cmd.Init,
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
							&cli.StringFlag{
								Name:        "version",
								Aliases:     []string{"V"},
								Usage:       "Posit Pro Drivers version to install",
								DefaultText: cmd.DefaultProDriverVersion,
							},
						},
						Action: cmd.ProDriversInstall,
					},
				},
			},
			{
				Name:     "python",
				Usage:    "Install or manage Python versions",
				Category: "tools",
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
						Action: cmd.PythonInstall,
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
						Action: cmd.PythonInstallPackages,
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
						Action: cmd.PythonInstallJupyter,
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
						Action: cmd.PythonAddJupyterKernel,
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
						Action: cmd.RInstall,
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
						Action: cmd.RInstallPackages,
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
						Action: cmd.QuartoInstall,
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
						Action: cmd.QuartoInstallTinyTex,
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
						Action: cmd.QuartoUpdateTinyTex,
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
						Action: cmd.ContainerInstallTini,
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
						Action: cmd.ContainerInstallWaitForIt,
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
						Action: cmd.SysPkgUpdate,
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
						Action: cmd.SysPkgUpgrade,
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
						Action: cmd.SysPkgInstall,
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
						Action: cmd.SysPkgUninstall,
					},
					{
						Name:   "clean",
						Usage:  "Clean up package caches",
						Action: cmd.SysPkgClean,
					},
				},
			},
		},
	}
	if err := app.Run(os.Args); err != nil {
		log.Fatal(err)
	}
}
