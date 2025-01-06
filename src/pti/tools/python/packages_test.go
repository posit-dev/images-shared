package python

import (
	"fmt"
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"pti/mocks/pti/system/command"
	"pti/ptitest"
	"pti/system"
	"pti/system/command"
	"pti/system/file"
	"testing"
)

func Test_Manager_InstallPackages(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	type expectedCall struct {
		name           string
		args           []string
		envVars        []string
		inheritEnvVars bool
	}

	numpyInstallCall := expectedCall{
		name:           "/opt/python/3.12.4/bin/python",
		args:           []string{"-m", "pip", "install", "numpy"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	pandasInstallCall := expectedCall{
		name:           "/opt/python/3.12.4/bin/python",
		args:           []string{"-m", "pip", "install", "pandas"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	requirementsFileInstallCall := expectedCall{
		name:           "/opt/python/3.12.4/bin/python",
		args:           []string{"-m", "pip", "install", "-r", "/tmp/requirements.txt"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	pipCleanCall := expectedCall{
		name:           "/opt/python/3.12.4/bin/python",
		args:           []string{"-m", "pip", "cache", "purge"},
		envVars:        nil,
		inheritEnvVars: true,
	}

	tests := []struct {
		name           string
		manager        *Manager
		setupFs        func(*testing.T, afero.Fs, string)
		packages       *PackageList
		expectedCalls  []expectedCall
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
					Arch:    "amd64",
				},
				InstallationPath: fmt.Sprintf(installPathTpl, "3.12.4"),
				PythonPath:       fmt.Sprintf(binPathTpl, "3.12.4"),
				PipPath:          fmt.Sprintf(pipPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			setupFs: fakePythonInstallation,
			packages: &PackageList{
				Packages:     []string{"numpy", "pandas"},
				PackageFiles: []string{"/tmp/requirements.txt"},
			},
			expectedCalls: []expectedCall{
				numpyInstallCall,
				pandasInstallCall,
				requirementsFileInstallCall,
				pipCleanCall,
			},
			wantErr: false,
		},
		{
			name: "not installed",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
					Arch:    "amd64",
				},
				InstallationPath: fmt.Sprintf(installPathTpl, "3.12.4"),
				PythonPath:       fmt.Sprintf(binPathTpl, "3.12.4"),
				PipPath:          fmt.Sprintf(pipPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			expectedCalls:  []expectedCall{},
			wantErr:        true,
			wantErrMessage: "python 3.12.4 is not installed",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldNSC := command.NewShellCommand
			file.AppFs = afero.NewMemMapFs()
			t.Cleanup(func() {
				command.NewShellCommand = oldNSC
				ptitest.ResetAppFs()
			})

			if tt.setupFs != nil {
				tt.setupFs(t, file.AppFs, tt.manager.Version)
			}

			shellCalls := 0
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				require.LessOrEqual(shellCalls, len(tt.expectedCalls)-1)
				assert.Equal(tt.expectedCalls[shellCalls].name, name)
				assert.Equal(tt.expectedCalls[shellCalls].args, args)
				assert.Equal(tt.expectedCalls[shellCalls].envVars, envVars)
				assert.Equal(tt.expectedCalls[shellCalls].inheritEnvVars, inheritEnvVars)
				shellCalls++

				mockShellCommand := command_mock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(nil)
				return mockShellCommand
			}

			err := tt.manager.InstallPackages(tt.packages, nil)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}

func Test_Manager_Clean(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		manager        *Manager
		runErr         error
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			manager: &Manager{
				PythonPath: "/opt/python/3.12.4/bin/python",
			},
			runErr:  nil,
			wantErr: false,
		},
		{
			name: "run error",
			manager: &Manager{
				PythonPath: "/opt/python/3.12.4/bin/python",
			},
			runErr:         fmt.Errorf("run error"),
			wantErr:        true,
			wantErrMessage: "failed to purge pip cache",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {

			oldNSC := command.NewShellCommand
			t.Cleanup(func() {
				command.NewShellCommand = oldNSC
			})
			command.NewShellCommand = func(name string, args []string, envVar []string, inheritEnvVars bool) command.ShellCommandRunner {
				assert.Equal(tt.manager.PythonPath, name)
				assert.Equal([]string{"-m", "pip", "cache", "purge"}, args)
				assert.Nil(envVar)
				assert.True(inheritEnvVars)

				shellCommand := command_mock.NewMockShellCommandRunner(t)
				shellCommand.EXPECT().Run().Return(tt.runErr)

				return shellCommand
			}

			err := tt.manager.Clean()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}

func Test_Manager_initCorePackages(t *testing.T) {
	assert := assert.New(t)

	type expectedCall struct {
		name           string
		args           []string
		envVars        []string
		inheritEnvVars bool
	}

	ensurePipCall := expectedCall{
		name:           "/opt/python/3.12.4/bin/python",
		args:           []string{"-m", "ensurepip", "--upgrade"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	pipInstallUpgradeCall := expectedCall{
		name:           "/opt/python/3.12.4/bin/python",
		args:           []string{"-m", "pip", "install", "pip", "--upgrade"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	setuptoolsInstallUpgradeCall := expectedCall{
		name:           "/opt/python/3.12.4/bin/python",
		args:           []string{"-m", "pip", "install", "setuptools", "--upgrade"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	cleanPipCall := expectedCall{
		name:           "/opt/python/3.12.4/bin/python",
		args:           []string{"-m", "pip", "cache", "purge"},
		envVars:        nil,
		inheritEnvVars: true,
	}

	tests := []struct {
		name          string
		manager       *Manager
		expectedCalls []expectedCall
	}{
		{
			name: "success",
			manager: &Manager{
				Version:    "3.12.4",
				PythonPath: "/opt/python/3.12.4/bin/python",
			},
			expectedCalls: []expectedCall{
				ensurePipCall,
				pipInstallUpgradeCall,
				setuptoolsInstallUpgradeCall,
				cleanPipCall,
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldNSC := command.NewShellCommand
			file.AppFs = afero.NewMemMapFs()
			t.Cleanup(func() {
				command.NewShellCommand = oldNSC
				ptitest.ResetAppFs()
			})
			fakePythonInstallation(t, file.AppFs, tt.manager.Version)

			shellCalls := 0
			command.NewShellCommand = func(name string, args []string, envVar []string, inheritEnvVars bool) command.ShellCommandRunner {
				assert.Equal(tt.expectedCalls[shellCalls].name, name)
				assert.Equal(tt.expectedCalls[shellCalls].args, args)
				assert.Equal(tt.expectedCalls[shellCalls].envVars, envVar)
				assert.Equal(tt.expectedCalls[shellCalls].inheritEnvVars, inheritEnvVars)
				shellCalls++

				shellCommand := command_mock.NewMockShellCommandRunner(t)
				shellCommand.EXPECT().Run().Return(nil)

				return shellCommand
			}

			err := tt.manager.initCorePackages()
			assert.NoError(err)
		})
	}
}

func Test_Manager_ensurePip(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	type expectedCall struct {
		name           string
		args           []string
		envVars        []string
		inheritEnvVars bool
	}

	ensurePipCall := expectedCall{
		name:           "/opt/python/3.12.4/bin/python",
		args:           []string{"-m", "ensurepip", "--upgrade"},
		envVars:        nil,
		inheritEnvVars: true,
	}

	tests := []struct {
		name           string
		manager        *Manager
		expectedCalls  []expectedCall
		runErr         error
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			manager: &Manager{
				Version:    "3.12.4",
				PythonPath: "/opt/python/3.12.4/bin/python",
			},
			expectedCalls: []expectedCall{ensurePipCall},
			runErr:        nil,
			wantErr:       false,
		},
		{
			name: "run error",
			manager: &Manager{
				Version:    "3.12.4",
				PythonPath: "/opt/python/3.12.4/bin/python",
			},
			expectedCalls:  []expectedCall{ensurePipCall},
			runErr:         fmt.Errorf("run error"),
			wantErr:        true,
			wantErrMessage: "ensurepip failed",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			shellCalls := 0
			oldNSC := command.NewShellCommand
			t.Cleanup(func() {
				command.NewShellCommand = oldNSC
			})
			command.NewShellCommand = func(name string, args []string, envVar []string, inheritEnvVars bool) command.ShellCommandRunner {
				assert.Equal(tt.expectedCalls[shellCalls].name, name)
				assert.Equal(tt.expectedCalls[shellCalls].args, args)
				assert.Equal(tt.expectedCalls[shellCalls].envVars, envVar)
				assert.Equal(tt.expectedCalls[shellCalls].inheritEnvVars, inheritEnvVars)
				shellCalls++

				shellCommand := command_mock.NewMockShellCommandRunner(t)
				shellCommand.EXPECT().Run().Return(tt.runErr)

				return shellCommand
			}

			err := tt.manager.ensurePip()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}
