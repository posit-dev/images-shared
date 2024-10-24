package system

import (
	"log"
	"os/user"
)

func RequireSudo() {
	current, err := user.Current()
	if err != nil {
		log.Fatal(err)
	}

	if current.Uid != "0" {
		log.Fatal("This command must be run as root")
	}
}
