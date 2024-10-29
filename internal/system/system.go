package system

import (
	"fmt"
	"github.com/zcalusic/sysinfo"
	"log"
	"log/slog"
	"os"
	"os/exec"
	"os/user"
)

func RunCommand(command string, args *[]string, envVars *[]string) error {
	if args == nil {
		args = &[]string{}
	}
	cmd := exec.Command(command, *args...)
	cmd.Env = os.Environ()
	if envVars != nil {
		cmd.Env = append(cmd.Env, *envVars...)
	}
	// TODO: Consider a way to suppress output
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	slog.Debug(fmt.Sprintf("Environment variables: %v", cmd.Env))
	slog.Debug("Running command: " + cmd.String())
	if err := cmd.Run(); err != nil {
		return err
	}
	return nil
}

func RequireSudo() {
	current, err := user.Current()
	if err != nil {
		log.Fatal(err)
	}

	if current.Uid != "0" {
		log.Fatal("This command must be run as root")
	}
}

func UpdateCACertificates() error {
	var si sysinfo.SysInfo
	si.GetSysInfo()

	switch si.OS.Vendor {
	case "ubuntu", "debian":
		if err := RunCommand("update-ca-certificates", nil, nil); err != nil {
			return err
		}
	case "almalinux", "centos", "rockylinux", "rhel":
		if err := RunCommand("update-ca-trust", nil, nil); err != nil {
			return err
		}
	}

	return nil
}
