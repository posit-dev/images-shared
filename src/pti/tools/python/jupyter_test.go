package python

import (
	"fmt"
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"pti/mocks/pti/system/command"
	"pti/system"
	"pti/system/command"
	"pti/system/file"
	"slices"
	"testing"
)

func Test_Manager_InstallJupyter4Workbench(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	type expectedCall struct {
		name           string
		args           []string
		envVars        []string
		inheritEnvVars bool
	}

	newVenvCalls := func(pythonPath, targetPath string) []expectedCall {
		return []expectedCall{
			{
				name:           pythonPath,
				args:           []string{"-m", "venv", targetPath},
				envVars:        nil,
				inheritEnvVars: true,
			},
		}
	}
	initCorePackagesCalls := func(pythonPath string) []expectedCall {
		return []expectedCall{
			{
				name:           pythonPath,
				args:           []string{"-m", "ensurepip", "--upgrade"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			{
				name:           pythonPath,
				args:           []string{"-m", "pip", "install", "pip", "--upgrade"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			{
				name:           pythonPath,
				args:           []string{"-m", "pip", "install", "setuptools", "--upgrade"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			{
				name:           pythonPath,
				args:           []string{"-m", "pip", "cache", "purge"},
				envVars:        nil,
				inheritEnvVars: true,
			},
		}
	}
	jupyterPackageInstallCalls := func(pythonPath string) []expectedCall {
		return []expectedCall{
			{
				name:           pythonPath,
				args:           []string{"-m", "pip", "install", "jupyterlab"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			{
				name:           pythonPath,
				args:           []string{"-m", "pip", "install", "notebook"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			{
				name:           pythonPath,
				args:           []string{"-m", "pip", "install", "pwb_jupyterlab"},
				envVars:        nil,
				inheritEnvVars: true,
			},
			{
				name:           pythonPath,
				args:           []string{"-m", "pip", "cache", "purge"},
				envVars:        nil,
				inheritEnvVars: true,
			},
		}
	}

	tests := []struct {
		name           string
		manager        *Manager
		jupyterPath    string
		force          bool
		setupFs        func(*testing.T, afero.Fs, string)
		expectedCalls  []expectedCall
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "default",
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
			jupyterPath: "",
			force:       false,
			setupFs:     fakePythonInstallation,
			expectedCalls: append(
				append(
					newVenvCalls(fmt.Sprintf(binPathTpl, "3.12.4"), defaultJupyterPath),
					initCorePackagesCalls(defaultJupyterPath+"/bin/python")...,
				),
				jupyterPackageInstallCalls(defaultJupyterPath+"/bin/python")...,
			),
			wantErr: false,
		},
		{
			name: "custom path",
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
			jupyterPath: "/opt/jupyter",
			force:       false,
			setupFs:     fakePythonInstallation,
			expectedCalls: append(
				append(
					newVenvCalls(fmt.Sprintf(binPathTpl, "3.12.4"), "/opt/jupyter"),
					initCorePackagesCalls("/opt/jupyter/bin/python")...,
				),
				jupyterPackageInstallCalls("/opt/jupyter/bin/python")...,
			),
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
			jupyterPath:    "",
			force:          false,
			expectedCalls:  []expectedCall{},
			wantErr:        true,
			wantErrMessage: "python 3.12.4 is not installed",
		},
		{
			name: "dirty path no force",
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
			jupyterPath: "",
			force:       false,
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				fakePythonInstallation(t, fs, "3.12.4")
				err := fs.MkdirAll(defaultJupyterPath, 0755)
				require.NoError(err)
			},
			expectedCalls: []expectedCall{},
			wantErr:       false,
		},
		{
			name: "dirty path force",
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
			jupyterPath: "",
			force:       true,
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				fakePythonInstallation(t, fs, "3.12.4")
				err := fs.MkdirAll(defaultJupyterPath, 0755)
				require.NoError(err)
			},
			expectedCalls: append(
				append(
					newVenvCalls(fmt.Sprintf(binPathTpl, "3.12.4"), defaultJupyterPath),
					initCorePackagesCalls(defaultJupyterPath+"/bin/python")...,
				),
				jupyterPackageInstallCalls(defaultJupyterPath+"/bin/python")...,
			),
			wantErr: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := file.AppFs
			file.AppFs = afero.NewMemMapFs()
			defer func() {
				file.AppFs = oldFs
			}()

			if tt.setupFs != nil {
				tt.setupFs(t, file.AppFs, tt.manager.Version)
			}

			shellCalls := 0
			oldNSC := command.NewShellCommand
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				require.LessOrEqual(shellCalls, len(tt.expectedCalls)-1)
				assert.Equal(tt.expectedCalls[shellCalls].name, name)
				assert.Equal(tt.expectedCalls[shellCalls].args, args)
				assert.Equal(tt.expectedCalls[shellCalls].envVars, envVars)
				assert.Equal(tt.expectedCalls[shellCalls].inheritEnvVars, inheritEnvVars)
				shellCalls++

				if slices.Contains(args, "venv") {
					p := tt.jupyterPath
					if p == "" {
						p = defaultJupyterPath
					}
					err := file.AppFs.Mkdir(p, 0755)
					require.NoError(err)
					_, err = file.AppFs.Create(p + "/bin/python")
					require.NoError(err)
				}

				mockShellCommand := command_mock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(nil)
				return mockShellCommand
			}
			defer func() {
				command.NewShellCommand = oldNSC
			}()

			err := tt.manager.InstallJupyter4Workbench(tt.jupyterPath, tt.force)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}

func Test_Manager_addJupyterKernel(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	type expectedCall struct {
		name           string
		args           []string
		envVars        []string
		inheritEnvVars bool
	}

	ipykernelInstallCall := expectedCall{
		name:           fmt.Sprintf(binPathTpl, "3.12.4"),
		args:           []string{"-m", "pip", "install", "ipykernel", "--upgrade"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	ipykernelRegisterCall := expectedCall{
		name:           fmt.Sprintf(binPathTpl, "3.12.4"),
		args:           []string{"-m", "ipykernel", "install", "--name", "py3.12.4", "--display-name", "Python 3.12.4"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	pipCleanCall := expectedCall{
		name:           fmt.Sprintf(binPathTpl, "3.12.4"),
		args:           []string{"-m", "pip", "cache", "purge"},
		envVars:        nil,
		inheritEnvVars: true,
	}

	tests := []struct {
		name           string
		manager        *Manager
		expectedCalls  []expectedCall
		runErr         error
		runErrOnCall   int
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			manager: &Manager{
				Version:    "3.12.4",
				PythonPath: fmt.Sprintf(binPathTpl, "3.12.4"),
				PipPath:    fmt.Sprintf(pipPathTpl, "3.12.4"),
			},
			expectedCalls: []expectedCall{
				ipykernelInstallCall,
				pipCleanCall,
				ipykernelRegisterCall,
			},
			runErrOnCall: -1,
			wantErr:      false,
		},
		{
			name: "install error",
			manager: &Manager{
				Version:    "3.12.4",
				PythonPath: fmt.Sprintf(binPathTpl, "3.12.4"),
				PipPath:    fmt.Sprintf(pipPathTpl, "3.12.4"),
			},
			expectedCalls: []expectedCall{
				ipykernelInstallCall,
				pipCleanCall,
			},
			runErr:         fmt.Errorf("run error"),
			runErrOnCall:   0,
			wantErr:        true,
			wantErrMessage: "failed to install ipykernel to python 3.12.4",
		},
		{
			name: "register error",
			manager: &Manager{
				Version:    "3.12.4",
				PythonPath: fmt.Sprintf(binPathTpl, "3.12.4"),
				PipPath:    fmt.Sprintf(pipPathTpl, "3.12.4"),
			},
			expectedCalls: []expectedCall{
				ipykernelInstallCall,
				pipCleanCall,
				ipykernelRegisterCall,
			},
			runErr:         fmt.Errorf("run error"),
			runErrOnCall:   2,
			wantErr:        true,
			wantErrMessage: "failed to register kernel for python 3.12.4",
		},
	}
	for _, tt := range tests {
		oldFs := file.AppFs
		file.AppFs = afero.NewMemMapFs()
		defer func() {
			file.AppFs = oldFs
		}()
		fakePythonInstallation(t, file.AppFs, "3.12.4")

		t.Run(tt.name, func(t *testing.T) {
			shellCalls := 0
			oldNSC := command.NewShellCommand
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				require.LessOrEqual(shellCalls, len(tt.expectedCalls)-1)
				assert.Equal(tt.expectedCalls[shellCalls].name, name)
				assert.Equal(tt.expectedCalls[shellCalls].args, args)
				assert.Equal(tt.expectedCalls[shellCalls].envVars, envVars)
				assert.Equal(tt.expectedCalls[shellCalls].inheritEnvVars, inheritEnvVars)

				mockShellCommand := command_mock.NewMockShellCommandRunner(t)
				if shellCalls == tt.runErrOnCall {
					mockShellCommand.EXPECT().Run().Return(tt.runErr)
				} else {
					mockShellCommand.EXPECT().Run().Return(nil)
				}
				shellCalls++
				return mockShellCommand
			}
			defer func() {
				command.NewShellCommand = oldNSC
			}()

			err := tt.manager.AddKernel()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}
