package system

import (
	"github.com/zcalusic/sysinfo"
	"log"
	"os/exec"
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

func UpdateCACertificates() error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	switch si.OS.Vendor {
	case "ubuntu", "debian":
		if err := exec.Command("update-ca-certificates").Run(); err != nil {
			return err
		}
	case "almalinux", "centos", "rockylinux", "rhel":
		if err := exec.Command("update-ca-trust").Run(); err != nil {
			return err
		}
	}

	return nil
}
