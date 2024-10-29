package system

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"os/signal"
	"syscall"
)

type SysCmd struct {
	Name           string
	Args           *[]string
	EnvVars        *[]string
	InheritEnvVars bool
	cmd            *exec.Cmd
}

func NewSysCmd(name string, args *[]string) *SysCmd {
	return &SysCmd{
		Name:           name,
		Args:           args,
		EnvVars:        nil,
		InheritEnvVars: true,
		cmd:            nil,
	}
}

func (s *SysCmd) Execute() error {
	ctx, _ := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)

	if s.Args == nil {
		s.Args = &[]string{}
	}
	if s.EnvVars == nil {
		s.EnvVars = &[]string{}
	}

	s.cmd = exec.CommandContext(ctx, s.Name, *s.Args...)
	s.cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	s.cmd.Cancel = func() error {
		return s.cmd.Process.Signal(syscall.SIGINT)
	}
	s.cmd.Env = *s.EnvVars
	if s.InheritEnvVars {
		s.cmd.Env = append(s.cmd.Env, os.Environ()...)
	}

	// TODO: Consider a way to suppress output
	s.cmd.Stdout = os.Stdout
	s.cmd.Stderr = os.Stderr

	slog.Debug(fmt.Sprintf("Environment variables: %v", s.cmd.Env))
	slog.Debug("Running cmd: " + s.cmd.String())
	if err := s.cmd.Start(); err != nil {
		return err
	}

	err := s.cmd.Wait()
	select {
	case <-ctx.Done():
		slog.Debug("Command was interrupted")
		return ctx.Err()
	default:
		if err != nil {
			return err
		}
		slog.Debug("Command finished successfully")
		return nil
	}
}
