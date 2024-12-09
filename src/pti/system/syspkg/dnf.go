package syspkg

import (
	"fmt"
	"log/slog"
	"pti/system/command"
	"pti/system/file"
	"strings"
)

type DnfManager struct {
	binary         string
	installOpts    []string
	upgradeOpts    []string
	removeOpts     []string
	autoRemoveOpts []string
	cleanOpts      []string
}

func NewDnfManager() *DnfManager {
	return &DnfManager{
		binary:         "dnf",
		installOpts:    []string{"-y", "-q", "install"},
		upgradeOpts:    []string{"-y", "-q", "upgrade"},
		removeOpts:     []string{"-y", "-q", "remove"},
		autoRemoveOpts: []string{"-y", "-q", "autoremove"},
		cleanOpts:      []string{"-y", "-q", "clean", "all"},
	}
}

func (m *DnfManager) GetBin() string {
	return m.binary
}

func (m *DnfManager) Install(list *PackageList) error {
	packagesToInstall, err := list.GetPackages()
	if err != nil {
		return fmt.Errorf("error occurred while parsing packages to install: %w", err)
	}
	if len(packagesToInstall) > 0 {
		slog.Info("Installing packages: " + strings.Join(packagesToInstall[:], ", "))

		args := append(m.installOpts, packagesToInstall...)

		cmd := command.NewShellCommand(m.binary, args, nil, true)
		err = cmd.Run()
		if err != nil {
			return fmt.Errorf("failed to install packages '%v': %w", packagesToInstall, err)
		}
	}
	if len(list.LocalPackages) > 0 {
		for _, localPackagePath := range list.LocalPackages {
			slog.Info("Installing package " + localPackagePath)

			args := append(m.installOpts, localPackagePath)

			exist, err := file.IsPathExist(localPackagePath)
			if err != nil {
				return fmt.Errorf("failed to check if local package '%s' exists: %w", localPackagePath, err)
			}
			if !exist {
				return fmt.Errorf("local package '%s' does not exist", localPackagePath)
			}

			cmd := command.NewShellCommand(m.binary, args, nil, true)
			err = cmd.Run()
			if err != nil {
				return fmt.Errorf("failed to install local package '%s': %w", localPackagePath, err)
			}
		}
	}

	return nil
}

func (m *DnfManager) Remove(list *PackageList) error {
	packagesToRemove, err := list.GetPackages()
	if err != nil {
		return fmt.Errorf("error occurred while parsing packages to remove: %w", err)
	}

	if len(packagesToRemove) > 0 {
		slog.Info("Removing package(s): " + strings.Join(packagesToRemove[:], ", "))

		args := append(m.removeOpts, packagesToRemove...)

		cmd := command.NewShellCommand(m.binary, args, nil, true)
		err = cmd.Run()
		if err != nil {
			return fmt.Errorf("failed to remove packages '%v': %w", packagesToRemove, err)
		}
	}

	return nil
}

func (m *DnfManager) Update() error {
	slog.Debug("No update command required for dnf")
	return nil
}

func (m *DnfManager) Upgrade(fullUpgrade bool) error {
	slog.Info("Upgrading dnf packages")
	cmd := command.NewShellCommand(m.binary, m.upgradeOpts, nil, true)
	err := cmd.Run()
	if err != nil {
		return fmt.Errorf("dnf upgrade failed: %w", err)
	}

	if fullUpgrade {
		slog.Debug("No full upgrade command is configured for dnf")
	}

	return nil
}

func (m *DnfManager) Clean() error {
	slog.Info("Cleaning up dnf")

	cmd := command.NewShellCommand(m.binary, m.cleanOpts, nil, true)
	err := cmd.Run()
	if err != nil {
		slog.Error("dnf clean step failed: " + err.Error())
		return fmt.Errorf("dnf clean failed: %w", err)
	}

	err = m.autoRemove()
	if err != nil {
		slog.Error("dnf autoremove step failed: " + err.Error())
		return err
	}

	return nil
}

func (m *DnfManager) autoRemove() error {
	cmd := command.NewShellCommand(m.binary, m.autoRemoveOpts, nil, true)
	err := cmd.Run()
	if err != nil {
		return fmt.Errorf("dnf autoremove failed: %w", err)
	}

	return nil
}
