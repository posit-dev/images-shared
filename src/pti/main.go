package main

import (
	"log"
	"log/slog"
	"os"
	"pti/cmd"
	"runtime"

	"github.com/pterm/pterm"
)

func main() {
	if runtime.GOOS != "linux" {
		log.Fatal("pti is only supported on Linux")
	}

	logger := slog.New(pterm.NewSlogHandler(&pterm.DefaultLogger))
	slog.SetDefault(logger)

	cli := cmd.Cli()
	if err := cli.Run(os.Args); err != nil {
		slog.Error(err.Error())
	}
}
