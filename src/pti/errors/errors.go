package errors

import "fmt"

// Generic errors

var FileCreateErrorTpl = "failed to create file %s: %w"
var FileOpenErrorTpl = "failed to open %s: %w"
var FileStatErrorTpl = "failed to stat %s: %w"
var FileReadErrorTpl = "failed to read %s: %w"
var FileRemoveErrorTpl = "failed to remove %s: %w"
var FileMoveErrorTpl = "failed to move file from %s to %s: %w"
var FileCopyErrorTpl = "failed to copy file from %s to %s: %w"
var OSVersionParseErrorTpl = "failed to parse OS version %s: %w"

// Request errors

var RequestFailedErrorTpl = "request to %s failed: %w"
var RequestCopyFailedErrorTpl = "failed to copy data to %s: %w"

// System package errors

var SystemUpdateErrorTpl = "failed to update system package manager: %w"
var SystemUpgradeErrorTpl = "failed to upgrade system package manager: %w"
var SystemLocalPackageInstallErrorTpl = "failed to install %s: %w"
var SystemPackageInstallErrorTpl = "failed to install package(s): %w"
var SystemCleanErrorTpl = "failed to clean system package manager: %w"
var SystemPackageAutoremoveErrorTpl = "failed to autoremove system packages: %w"
var SystemPackageRemoveErrorTpl = "failed to remove package(s): %w"

// Symlink errors

var RemoveExistingSymlinkErrorTpl = "failed to remove existing symlink at %s: %w"
var CreateSymlinkErrorTpl = "failed to create symlink from %s to %s: %w"

// Tool errors

var ToolDownloadFailedErrorTpl = "failed to download %s: %w"
var ToolDependencyInstallFailedErrorTpl = "failed to install %s dependencies: %w"
var ToolInstallFailedErrorTpl = "failed to install %s: %w"
var ToolUpdateFailedErrorTpl = "failed to update %s: %w"
var ToolSetPermissionsFailedErrorTpl = "failed to set permissions on %s to %s: %w"
var ToolInstallerRemovalFailedErrorTpl = "failed to remove installer file(s) for %s: %w"
var ToolRemovalFailedErrorTpl = "failed to remove %s from %s: %w"
var ToolPackageInstallationErrorTpl = "failed to install packages to %s: %w"
var ToolPackageFileInstallationErrorTpl = "failed to install packages from %s to %s: %w"

type UnsupportedOSError struct {
	Vendor  string
	Version string
}

func (e *UnsupportedOSError) Error() string {
	return fmt.Sprintf("unsupported os %s %s", e.Vendor, e.Version)
}

type UnsupportedVersionError struct {
	Pkg     string
	Version string
}

func (e *UnsupportedVersionError) Error() string {
	return fmt.Sprintf("unsupported version %s for %s", e.Version, e.Pkg)
}

type BinaryDoesNotExistError struct {
	Pkg  string
	Path string
}

func (e *BinaryDoesNotExistError) Error() string {
	return fmt.Sprintf("binary %s does not exist at %s", e.Pkg, e.Path)
}

type AlreadyExistsError struct {
	Pkg  string
	Path string
}

func (e *AlreadyExistsError) Error() string {
	return fmt.Sprintf("%s already exists at %s, use --force to reinstall", e.Pkg, e.Path)
}
