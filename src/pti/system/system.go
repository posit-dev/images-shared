package system

import (
	"fmt"
	"github.com/zcalusic/sysinfo"
	"log"
	"os/user"
	"pti/errors"
)

func RequireSudo() {
	current, err := user.Current()
	if err != nil {
		log.Fatal(err)
	}

	if current.Uid != "0" {
		log.Fatal("command must be run as root")
	}
}

func UpdateCACertificates() error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	switch si.OS.Vendor {
	case "ubuntu", "debian":
		s := NewSysCmd("update-ca-certificates", nil)
		if err := s.Execute(); err != nil {
			return fmt.Errorf("failed to update-ca-certificates: %w", err)
		}
	case "almalinux", "centos", "rockylinux", "rhel":
		s := NewSysCmd("update-ca-trust", nil)
		if err := s.Execute(); err != nil {
			return fmt.Errorf("failed to update-ca-trust: %w", err)
		}
	default:
		return &errors.UnsupportedOSError{Vendor: si.OS.Vendor, Version: si.OS.Version}
	}

	return nil
}
