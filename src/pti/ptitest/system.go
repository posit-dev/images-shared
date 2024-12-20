package ptitest

import "pti/system"

func NewUbuntuSystem() *system.LocalSystem {
	return &system.LocalSystem{
		Vendor:  "ubuntu",
		Version: "22.04",
		Arch:    "amd64",
	}
}

func NewRockySystem() *system.LocalSystem {
	return &system.LocalSystem{
		Vendor:  "rockylinux",
		Version: "8",
		Arch:    "amd64",
	}
}
