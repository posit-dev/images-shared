package system

import (
	"fmt"
	"pti/system/command"
)

func (l *LocalSystem) UpdateCACertificates() error {
	var updateBin string

	switch l.Vendor {
	case "ubuntu", "debian":
		updateBin = "update-ca-certificates"
	case "almalinux", "centos", "rockylinux", "rhel":
		updateBin = "update-ca-trust"
	default:
		return fmt.Errorf("unsupported OS: %s %s", l.Vendor, l.Version)
	}

	s := command.NewShellCommand(updateBin, nil, nil, true)
	err := s.Run()
	if err != nil {
		return fmt.Errorf("failed to update CA certificates: %w", err)
	}

	return nil
}
