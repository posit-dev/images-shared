package quarto

import (
	"fmt"
	"log/slog"
	"pti/system/command"
)

func (m *Manager) InstallPackage(name string, options []string) error {
	slog.Info(fmt.Sprintf("Installing Quarto %s add-on", name))

	args := []string{"install", name, "--no-prompt"}
	if len(options) > 0 {
		args = append(args, options...)
	}
	s := command.NewShellCommand(m.BinPath, args, nil, true)
	if err := s.Run(); err != nil {
		return fmt.Errorf("failed to install quarto %s tool: %w", name, err)
	}

	return nil
}

func (m *Manager) UpdatePackage(name string, options []string) error {
	slog.Info("Updating Quarto " + name + " tool")

	args := []string{"update", name, "--no-prompt"}
	if len(options) > 0 {
		args = append(args, options...)
	}

	s := command.NewShellCommand(m.BinPath, args, nil, true)
	if err := s.Run(); err != nil {
		return fmt.Errorf("failed to update quarto %s tool: %w", name, err)
	}

	return nil
}

func (m *Manager) RemovePackage(name string, options []string) error {
	slog.Info("Updating Quarto " + name + " tool")

	args := []string{"remove", name, "--no-prompt"}
	if len(options) > 0 {
		args = append(args, options...)
	}

	s := command.NewShellCommand(m.BinPath, args, nil, true)
	if err := s.Run(); err != nil {
		return fmt.Errorf("failed to remove quarto %s tool: %w", name, err)
	}

	return nil
}
