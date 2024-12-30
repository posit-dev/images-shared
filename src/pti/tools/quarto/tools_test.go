package quarto

import (
	"fmt"
	command_mock "pti/mocks/pti/system/command"
	"pti/system"
	"pti/system/command"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func Test_Manager_InstallPackage(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	type expectedCall struct {
		bin            string
		args           []string
		envVars        []string
		inheritEnvVars bool
	}

	tests := []struct {
		name           string
		toolName       string
		options        []string
		expectedCall   expectedCall
		runErr         error
		wantErr        bool
		wantErrMessage string
	}{
		{
			name:     "normal",
			toolName: "testpkg",
			options:  nil,
			expectedCall: expectedCall{
				bin:            "quarto",
				args:           []string{"install", "testpkg", "--no-prompt"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			wantErr: false,
		},
		{
			name:     "normal with options",
			toolName: "testpkg",
			options:  []string{"--update-path"},
			expectedCall: expectedCall{
				bin:            "quarto",
				args:           []string{"install", "testpkg", "--no-prompt", "--update-path"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			wantErr: false,
		},
		{
			name:     "failed",
			toolName: "testpkg",
			options:  nil,
			expectedCall: expectedCall{
				bin:            "quarto",
				args:           []string{"install", "testpkg", "--no-prompt"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			runErr:         fmt.Errorf("runtime error"),
			wantErr:        true,
			wantErrMessage: "failed to install quarto testpkg tool",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			manager := &Manager{
				LocalSystem:             &system.LocalSystem{},
				Version:                 "1.6.39",
				InstallationPath:        DefaultInstallPath,
				BinPath:                 defaultBinPath,
				IsWorkbenchInstallation: false,
			}

			oldShellCommand := command.NewShellCommand
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				mockShellCommand := command_mock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(tt.runErr)

				assert.Contains(name, tt.expectedCall.bin)
				for _, arg := range tt.expectedCall.args {
					assert.Contains(args, arg)
				}
				assert.Equal(tt.expectedCall.envVars, envVars)
				assert.Equal(tt.expectedCall.inheritEnvVars, inheritEnvVars)

				return mockShellCommand
			}
			t.Cleanup(func() {
				command.NewShellCommand = oldShellCommand
			})

			err := manager.InstallPackage(tt.toolName, tt.options)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}

func Test_Manager_UpdatePackage(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	type expectedCall struct {
		bin            string
		args           []string
		envVars        []string
		inheritEnvVars bool
	}

	tests := []struct {
		name           string
		toolName       string
		options        []string
		expectedCall   expectedCall
		runErr         error
		wantErr        bool
		wantErrMessage string
	}{
		{
			name:     "normal",
			toolName: "testpkg",
			options:  nil,
			expectedCall: expectedCall{
				bin:            "quarto",
				args:           []string{"update", "testpkg", "--no-prompt"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			wantErr: false,
		},
		{
			name:     "normal with options",
			toolName: "testpkg",
			options:  []string{"--update-path"},
			expectedCall: expectedCall{
				bin:            "quarto",
				args:           []string{"update", "testpkg", "--no-prompt", "--update-path"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			wantErr: false,
		},
		{
			name:     "failed",
			toolName: "testpkg",
			options:  nil,
			expectedCall: expectedCall{
				bin:            "quarto",
				args:           []string{"update", "testpkg", "--no-prompt"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			runErr:         fmt.Errorf("runtime error"),
			wantErr:        true,
			wantErrMessage: "failed to update quarto testpkg tool",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			manager := &Manager{
				LocalSystem:             &system.LocalSystem{},
				Version:                 "1.6.39",
				InstallationPath:        DefaultInstallPath,
				BinPath:                 defaultBinPath,
				IsWorkbenchInstallation: false,
			}

			oldShellCommand := command.NewShellCommand
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				mockShellCommand := command_mock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(tt.runErr)

				assert.Contains(name, tt.expectedCall.bin)
				for _, arg := range tt.expectedCall.args {
					assert.Contains(args, arg)
				}
				assert.Equal(tt.expectedCall.envVars, envVars)
				assert.Equal(tt.expectedCall.inheritEnvVars, inheritEnvVars)

				return mockShellCommand
			}
			t.Cleanup(func() {
				command.NewShellCommand = oldShellCommand
			})

			err := manager.UpdatePackage(tt.toolName, tt.options)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}

func Test_Manager_RemovePackage(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	type expectedCall struct {
		bin            string
		args           []string
		envVars        []string
		inheritEnvVars bool
	}

	tests := []struct {
		name           string
		toolName       string
		options        []string
		expectedCall   expectedCall
		runErr         error
		wantErr        bool
		wantErrMessage string
	}{
		{
			name:     "normal",
			toolName: "testpkg",
			options:  nil,
			expectedCall: expectedCall{
				bin:            "quarto",
				args:           []string{"remove", "testpkg", "--no-prompt"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			wantErr: false,
		},
		{
			name:     "normal with options",
			toolName: "testpkg",
			options:  []string{"--remove-path"},
			expectedCall: expectedCall{
				bin:            "quarto",
				args:           []string{"remove", "testpkg", "--no-prompt", "--remove-path"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			wantErr: false,
		},
		{
			name:     "failed",
			toolName: "testpkg",
			options:  nil,
			expectedCall: expectedCall{
				bin:            "quarto",
				args:           []string{"remove", "testpkg", "--no-prompt"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			runErr:         fmt.Errorf("runtime error"),
			wantErr:        true,
			wantErrMessage: "failed to remove quarto testpkg tool",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			manager := &Manager{
				LocalSystem:             &system.LocalSystem{},
				Version:                 "1.6.39",
				InstallationPath:        DefaultInstallPath,
				BinPath:                 defaultBinPath,
				IsWorkbenchInstallation: false,
			}

			oldShellCommand := command.NewShellCommand
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				mockShellCommand := command_mock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(tt.runErr)

				assert.Contains(name, tt.expectedCall.bin)
				for _, arg := range tt.expectedCall.args {
					assert.Contains(args, arg)
				}
				assert.Equal(tt.expectedCall.envVars, envVars)
				assert.Equal(tt.expectedCall.inheritEnvVars, inheritEnvVars)

				return mockShellCommand
			}
			t.Cleanup(func() {
				command.NewShellCommand = oldShellCommand
			})

			err := manager.RemovePackage(tt.toolName, tt.options)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}
