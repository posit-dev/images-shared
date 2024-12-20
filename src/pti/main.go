package main

import (
	"github.com/pterm/pterm"
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

	cli := cmd.Cli()
	if err := cli.Run(os.Args); err != nil {
		slog.Error(err.Error())
	}
}
