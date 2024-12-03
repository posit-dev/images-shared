package command

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"os/signal"
	"syscall"
)

type ShellCommandExecutor interface {
	Start() error
	Wait() error
	String() string
}

type ShellCommandContexter interface {
	Done() <-chan struct{}
	Err() error
}

type ShellCommandRunner interface {
	Run() error
	String() string
	GetName() string
	GetArgs() []string
	GetEnvVars() []string
	GetInheritEnvVars() bool
	GetContext() ShellCommandContexter
	GetExecutor() ShellCommandExecutor
}

type ShellCommand struct {
	Name           string
	Args           []string
	EnvVars        []string
	InheritEnvVars bool
	Ctx            ShellCommandContexter
	Cmd            ShellCommandExecutor
}

var NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) ShellCommandRunner {
	ctx, _ := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)

	cmd := exec.CommandContext(ctx, name, args...)

	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	cmd.Cancel = func() error {
		slog.Info("Interrupt signal received, cancelling command")
		err := cmd.Process.Signal(syscall.SIGTERM)
		if err != nil {
			slog.Error("Failed to cancel command: " + err.Error())
		}
		return err
	}
	cmd.Env = envVars
	if inheritEnvVars {
		cmd.Env = append(cmd.Env, os.Environ()...)
	}
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	return &ShellCommand{
		Name:           name,
		Args:           args,
		EnvVars:        envVars,
		InheritEnvVars: inheritEnvVars,
		Ctx:            ctx,
		Cmd:            cmd,
	}
}

func (s *ShellCommand) Run() error {
	slog.Debug(fmt.Sprintf("Environment variables: %v", s.EnvVars))
	slog.Debug("Running cmd: " + s.String())
	if err := s.Cmd.Start(); err != nil {
		return fmt.Errorf("failed to start command '%s': %w", s.String(), err)
	}

	err := s.Cmd.Wait()
	select {
	case <-s.Ctx.Done():
		slog.Debug("Command was interrupted")
		return s.Ctx.Err()
	default:
		if err != nil {
			return fmt.Errorf("command '%s' failed: %w", s.String(), err)
		}
		slog.Debug("Command finished successfully")
		return nil
	}
}

func (s *ShellCommand) String() string {
	return s.Cmd.String()
}

func (s *ShellCommand) GetName() string {
	return s.Name
}

func (s *ShellCommand) GetArgs() []string {
	return s.Args
}

func (s *ShellCommand) GetEnvVars() []string {
	return s.EnvVars
}

func (s *ShellCommand) GetInheritEnvVars() bool {
	return s.InheritEnvVars
}

func (s *ShellCommand) GetContext() ShellCommandContexter {
	return s.Ctx
}

func (s *ShellCommand) GetExecutor() ShellCommandExecutor {
	return s.Cmd
}
