package container

import (
	"fmt"
	"pti/system"
	"pti/system/syspkg"
)

func Bootstrap(l *system.LocalSystem) error {
	packages := &syspkg.PackageList{Packages: []string{"ca-certificates"}}

	if err := l.PackageManager.Install(packages); err != nil {
		return fmt.Errorf("failed to install ca-certificates: %w", err)
	}
	defer l.PackageManager.Clean()

	if err := l.UpdateCACertificates(); err != nil {
		return fmt.Errorf("failed to update CA certificates: %w", err)
	}

	return nil
}
