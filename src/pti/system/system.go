package system

import (
	"fmt"
	"github.com/zcalusic/sysinfo"
	"os/user"
	"pti/system/syspkg"
)

type LocalSystem struct {
	Vendor         string
	Version        string
	Arch           string
	PackageManager syspkg.SystemPackageManager
}

var sysInfo = func() sysinfo.SysInfo {
	var si sysinfo.SysInfo
	si.GetSysInfo()
	return si
}

func GetLocalSystem() (*LocalSystem, error) {
	si := sysInfo()

	var pm *syspkg.SystemPackageManager
	pm = new(syspkg.SystemPackageManager)

	switch si.OS.Vendor {
	case "ubuntu", "debian":
		*pm = syspkg.NewAptManager()
	case "almalinux", "centos", "rockylinux", "rhel":
		*pm = syspkg.NewDnfManager()
	default:
		return nil, fmt.Errorf("unsupported OS: %s %s", si.OS.Vendor, si.OS.Version)
	}

	return &LocalSystem{
		Vendor:         si.OS.Vendor,
		Version:        si.OS.Version,
		Arch:           si.OS.Architecture,
		PackageManager: *pm,
	}, nil
}

var currentUser = func() (*user.User, error) {
	return user.Current()
}

func RequireSudo() error {
	current, err := currentUser()
	if err != nil {
		return fmt.Errorf("failed to get current user: %w", err)
	}

	if current.Uid != "0" {
		return fmt.Errorf("this command must be run as root")
	}

	return nil
}

func (l *LocalSystem) GetAltArchName() string {
	if l.Arch == "amd64" {
		return "x86_64"
	}

	return l.Arch
}
