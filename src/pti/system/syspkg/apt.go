package syspkg

import (
	"fmt"
	"github.com/spf13/afero"
	"log/slog"
	"pti/system/command"
	"pti/system/file"
	"strings"
)

type AptManager struct {
	binary          string
	installOpts     []string
	updateOpts      []string
	upgradeOpts     []string
	distUpgradeOpts []string
	removeOpts      []string
	autoRemoveOpts  []string
	cleanOpts       []string
}

func NewAptManager() *AptManager {
	return &AptManager{
		binary:          "apt-get",
		installOpts:     []string{"install", "-y", "-q"},
		updateOpts:      []string{"update", "-q"},
		upgradeOpts:     []string{"upgrade", "-y", "-q"},
		distUpgradeOpts: []string{"dist-upgrade", "-y", "-q"},
		removeOpts:      []string{"remove", "-y", "-q"},
		autoRemoveOpts:  []string{"autoremove", "-y", "-q"},
		cleanOpts:       []string{"clean", "-q"},
	}
}

func (m *AptManager) GetBin() string {
	return m.binary
}

func (m *AptManager) GetPackageExtension() string {
	return ".deb"
}

func (m *AptManager) Install(list *PackageList) error {
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

func (m *AptManager) Remove(list *PackageList) error {
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

func (m *AptManager) Update() error {
	slog.Info("Updating apt")
	cmd := command.NewShellCommand(m.binary, m.updateOpts, nil, true)
	err := cmd.Run()
	if err != nil {
		return fmt.Errorf("apt update failed: %w", err)
	}
	return nil
}

func (m *AptManager) Upgrade(fullUpgrade bool) error {
	slog.Info("Upgrading apt packages")
	cmd := command.NewShellCommand(m.binary, m.upgradeOpts, nil, true)
	err := cmd.Run()
	if err != nil {
		return fmt.Errorf("apt upgrade failed: %w", err)
	}

	if fullUpgrade {
		cmd := command.NewShellCommand(m.binary, m.distUpgradeOpts, nil, true)
		err := cmd.Run()
		if err != nil {
			return fmt.Errorf("apt dist-upgrade failed: %w", err)
		}
	}

	return nil
}

func (m *AptManager) Clean() error {
	slog.Info("Cleaning up apt")

	cmd := command.NewShellCommand(m.binary, m.cleanOpts, nil, true)
	err := cmd.Run()
	if err != nil {
		slog.Error("apt clean step failed: " + err.Error())
		return fmt.Errorf("apt clean failed: %w", err)
	}

	err = m.autoRemove()
	if err != nil {
		slog.Error("apt autoremove step failed: " + err.Error())
		return err
	}

	err = m.removePackageListCache()
	if err != nil {
		slog.Error("failed to remove apt lists (/var/lib/apt/lists) from file system: " + err.Error())
		return err
	}

	return nil
}

func (m *AptManager) autoRemove() error {
	cmd := command.NewShellCommand(m.binary, m.autoRemoveOpts, nil, true)
	err := cmd.Run()
	if err != nil {
		return fmt.Errorf("apt autoremove failed: %w", err)
	}

	return nil
}

func (m *AptManager) removePackageListCache() error {
	slog.Debug("Removing /var/lib/apt/lists")

	exists, err := afero.DirExists(file.AppFs, "/var/lib/apt/lists")
	if err != nil {
		return fmt.Errorf("failed to check if /var/lib/apt/lists exists: %w", err)
	}
	if !exists {
		slog.Debug("/var/lib/apt/lists does not exist")
		return nil
	}

	err = file.AppFs.RemoveAll("/var/lib/apt/lists")
	if err != nil {
		return fmt.Errorf("failed to remove /var/lib/apt/lists: %w", err)
	}

	return nil
}
