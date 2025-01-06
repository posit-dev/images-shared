package container

import (
	"fmt"
	"log/slog"
	"pti/system"
	"pti/system/syspkg"
)

func Bootstrap(l *system.LocalSystem) error {
	err := l.PackageManager.Update()
	defer l.PackageManager.Clean() //nolint:errcheck
	if err != nil {
		return fmt.Errorf("failed to update package manager: %w", err)
	}

	slog.Info("Installing and configuring ca-certificates")
	packages := &syspkg.PackageList{Packages: []string{"ca-certificates"}}

	if err := l.PackageManager.Install(packages); err != nil {
		return fmt.Errorf("failed to install ca-certificates: %w", err)
	}

	if err := l.UpdateCACertificates(); err != nil {
		return fmt.Errorf("failed to update CA certificates: %w", err)
	}

	if l.PackageManager.GetBin() == "dnf" {
		slog.Info("Installing EPEL repository")
		err = l.PackageManager.Install(&syspkg.PackageList{Packages: []string{"epel-release"}})
		if err != nil {
			return fmt.Errorf("failed to install epel-release: %w", err)
		}
	}

	return nil
}
