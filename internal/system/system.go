package system

import (
	"fmt"
	"github.com/zcalusic/sysinfo"
	"log"
	"os/user"
)

func RequireSudo() {
	current, err := user.Current()
	if err != nil {
		log.Fatal(err)
	}

	if current.Uid != "0" {
		log.Fatal("This cmd must be run as root")
	}
}

func UpdateCACertificates() error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	switch si.OS.Vendor {
	case "ubuntu", "debian":
		s := NewSysCmd("update-ca-certificates", nil)
		return s.Execute()
	case "almalinux", "centos", "rockylinux", "rhel":
		s := NewSysCmd("update-ca-trust", nil)
		return s.Execute()
	default:
		return fmt.Errorf("unsupported OS: %s %s", si.OS.Vendor, si.OS.Version)
	}
}
