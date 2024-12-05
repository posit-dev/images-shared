package command_test

import (
	"context"
	"fmt"
	"github.com/stretchr/testify/assert"
	commandMock "pti/mocks/pti/system/command"
	"pti/system/command"
	"strings"
	"testing"
)

func TestNewShellCommand(t *testing.T) {
	assert := assert.New(t)

	type args struct {
		name           string
		args           []string
		envVars        []string
		inheritEnvVars bool
	}
	testArgs := args{
		name:           "ls",
		args:           []string{"-l"},
		envVars:        []string{"PATH=/usr/bin"},
		inheritEnvVars: true,
	}
	shellCmd := command.NewShellCommand(testArgs.name, testArgs.args, testArgs.envVars, testArgs.inheritEnvVars)

	assert.Equal(testArgs.name, shellCmd.GetName())
	assert.Equal(testArgs.args, shellCmd.GetArgs())
	assert.Equal(testArgs.envVars, shellCmd.GetEnvVars())
	assert.Equal(testArgs.inheritEnvVars, shellCmd.GetInheritEnvVars())
	assert.NotNil(shellCmd.GetContext())
	assert.NotNil(shellCmd.GetExecutor())
	assert.IsType(&command.ShellCommand{}, shellCmd)
	expectedCommand := strings.TrimSpace(testArgs.name + " " + strings.Join(testArgs.args[:], " "))
	if !strings.HasSuffix(shellCmd.String(), expectedCommand) {
		t.Errorf("Command string = %s, want suffix %s", shellCmd.String(), expectedCommand)
	}
}

func TestShellCommand_Run(t *testing.T) {
	assert := assert.New(t)

	type executorSetup struct {
		start error
		wait  error
		str   string
	}
	type contextSetup struct {
		ctx context.Context
	}
	type fields struct {
		Name           string
		Args           []string
		EnvVars        []string
		InheritEnvVars bool
		ctxSetup       contextSetup
		cmdSetup       executorSetup
		ctxSetupFunc   func(*testing.T, contextSetup) command.ShellCommandContexter
		cmdSetupFunc   func(*testing.T, executorSetup) command.ShellCommandExecutor
	}
	tests := []struct {
		name           string
		fields         fields
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			fields: fields{
				Name: "ls",
				Args: []string{"-l"},
				cmdSetup: executorSetup{
					start: nil,
					wait:  nil,
					str:   "ls -l",
				},
				ctxSetup: contextSetup{
					ctx: context.Background(),
				},
				cmdSetupFunc: func(t *testing.T, setup executorSetup) command.ShellCommandExecutor {
					mockExecutor := commandMock.NewMockShellCommandExecutor(t)
					mockExecutor.EXPECT().Start().Return(setup.start)
					mockExecutor.EXPECT().Wait().Return(setup.wait)
					mockExecutor.On("String").Return("ls -l")
					return mockExecutor
				},
				ctxSetupFunc: func(t *testing.T, setup contextSetup) command.ShellCommandContexter {
					mockContext := commandMock.NewMockShellCommandContexter(t)
					mockContext.EXPECT().Done().Return(setup.ctx.Done())
					return mockContext
				},
			},
			wantErr: false,
		},
		{
			name: "failed to start",
			fields: fields{
				Name: "ls",
				Args: []string{"-l"},
				cmdSetup: executorSetup{
					start: fmt.Errorf("generic error"),
				},
				cmdSetupFunc: func(tc *testing.T, setup executorSetup) command.ShellCommandExecutor {
					mockExecutor := commandMock.NewMockShellCommandExecutor(t)
					mockExecutor.EXPECT().Start().Return(setup.start)
					mockExecutor.EXPECT().String().Return("ls -l")
					return mockExecutor
				},
				ctxSetupFunc: func(t *testing.T, setup contextSetup) command.ShellCommandContexter {
					mockContext := commandMock.NewMockShellCommandContexter(t)
					return mockContext
				},
			},
			wantErr:        true,
			wantErrMessage: "failed to start command 'ls -l'",
		},
		{
			name: "failed execution",
			fields: fields{
				Name: "ls",
				Args: []string{"-l"},
				cmdSetup: executorSetup{
					start: nil,
					wait:  fmt.Errorf("runtime error"),
				},
				ctxSetup: contextSetup{
					ctx: context.Background(),
				},
				cmdSetupFunc: func(t *testing.T, setup executorSetup) command.ShellCommandExecutor {
					mockExecutor := commandMock.NewMockShellCommandExecutor(t)
					mockExecutor.EXPECT().Start().Return(setup.start)
					mockExecutor.EXPECT().Wait().Return(setup.wait)
					mockExecutor.EXPECT().String().Return("ls -l")
					return mockExecutor
				},
				ctxSetupFunc: func(t *testing.T, setup contextSetup) command.ShellCommandContexter {
					mockContext := commandMock.NewMockShellCommandContexter(t)
					mockContext.EXPECT().Done().Return(setup.ctx.Done())
					return mockContext
				},
			},
			wantErr:        true,
			wantErrMessage: "command 'ls -l' failed",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			shellCmd := &command.ShellCommand{
				Name:           tt.fields.Name,
				Args:           tt.fields.Args,
				EnvVars:        tt.fields.EnvVars,
				InheritEnvVars: tt.fields.InheritEnvVars,
				Ctx:            tt.fields.ctxSetupFunc(t, tt.fields.ctxSetup),
				Cmd:            tt.fields.cmdSetupFunc(t, tt.fields.cmdSetup),
			}

			err := shellCmd.Run()
			if tt.wantErr {
				assert.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				assert.NoError(err)
			}
		})
	}
}
