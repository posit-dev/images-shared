package drivers

import (
	"fmt"
	"log/slog"
	"pti/system/file"
)

const positDriversOdbcInstIniPath = "/opt/rstudio-drivers/odbcinst.ini.sample"

const systemOdbcInstIniPath = "/etc/odbcinst.ini"

func (m *Manager) CopyProDriversOdbcInstIni() error {
	// Check if the Posit Pro Drivers odbcinst.ini.sample exists
	isFile, err := file.IsFile(positDriversOdbcInstIniPath)
	if err != nil {
		return fmt.Errorf(
			"unable to check whether Posit Pro Drivers odbcinst.ini.sample exists at '%s': %w",
			positDriversOdbcInstIniPath,
			err,
		)
	}
	if !isFile {
		slog.Error(
			fmt.Sprintf(
				"Posit Pro Drivers odbcinst.ini.sample does not exist as expected at '%s'. "+
					"An installation error may have occurred.",
				positDriversOdbcInstIniPath,
			),
		)

		return fmt.Errorf(
			"odbcinst.ini.sample does not exist at '%s' as expected",
			positDriversOdbcInstIniPath,
		)
	}

	isFile, err = file.IsFile(systemOdbcInstIniPath)
	if err != nil {
		slog.Info("No odbcinst.ini detected, backup step will be skipped.")
	}

	// Backup original odbcinst.ini
	if isFile {
		slog.Info(
			"Backing up original odbcinst.ini to " + fmt.Sprintf("%s.bak", systemOdbcInstIniPath),
		)
		if err := file.Move(systemOdbcInstIniPath, fmt.Sprintf("%s.bak", systemOdbcInstIniPath)); err != nil {
			slog.Error(
				"Failed to backup odbcinst.ini, Pro Drivers odbcinst.ini.sample will not be copied.",
			)

			return fmt.Errorf("unable to backup odbcinst.ini: %w", err)
		}
	}

	// Copy the odbcinst.ini.sample from the Posit Drivers package
	slog.Info("Copying Posit Pro Drivers odbcinst.ini.sample to " + systemOdbcInstIniPath)
	if err := file.Copy(positDriversOdbcInstIniPath, systemOdbcInstIniPath); err != nil {
		slog.Error(
			fmt.Sprintf(
				"Failed to copy %s to %s. Original odbcinst.ini will be restored.",
				positDriversOdbcInstIniPath,
				systemOdbcInstIniPath,
			),
		)
		err := file.Move(fmt.Sprintf("%s.bak", systemOdbcInstIniPath), systemOdbcInstIniPath)
		if err != nil {
			slog.Error("Failed to restore original odbcinst.ini.")
		}

		return fmt.Errorf(
			"unable to copy Pro Drivers example ini file from %s to %s: %w",
			positDriversOdbcInstIniPath,
			systemOdbcInstIniPath,
			err,
		)
	}

	return nil
}
