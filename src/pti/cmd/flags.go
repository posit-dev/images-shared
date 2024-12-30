package cmd

import "github.com/urfave/cli/v2"

const categoryPackage = "Package installation: "

func versionFlag(usage, defaultText string) *cli.StringFlag {
	f := &cli.StringFlag{
		Name:    "version",
		Aliases: []string{"V"},
		Usage:   usage,
	}
	if defaultText != "" {
		f.DefaultText = defaultText
	}

	return f
}

func packageFlag(usage string) *cli.StringSliceFlag {
	return &cli.StringSliceFlag{
		Name:     "package",
		Aliases:  []string{"p"},
		Usage:    usage,
		Category: categoryPackage,
	}
}

func packageFileFlag(usage string) *cli.StringSliceFlag {
	return &cli.StringSliceFlag{
		Name:     "package-list-file",
		Aliases:  []string{"r"},
		Usage:    usage,
		Category: categoryPackage,
	}
}

func defaultFlag(usage string) *cli.BoolFlag {
	return &cli.BoolFlag{
		Name:    "default",
		Aliases: []string{"D"},
		Usage:   usage,
	}
}

func addToPathFlag(usage string) *cli.BoolFlag {
	return &cli.BoolFlag{
		Name:    "add-to-path",
		Aliases: []string{"P"},
		Usage:   usage,
	}
}

func forceFlag(usage string) *cli.BoolFlag {
	return &cli.BoolFlag{
		Name:    "force",
		Aliases: []string{"f"},
		Usage:   usage,
	}
}

func pathFlag(usage, defaultText string) *cli.StringFlag {
	f := &cli.StringFlag{
		Name:  "path",
		Usage: usage,
	}
	if defaultText != "" {
		f.DefaultText = defaultText
	}

	return f
}
