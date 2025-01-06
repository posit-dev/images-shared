package r

import (
	"fmt"
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	command_mock "pti/mocks/pti/system/command"
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

	defaultSystem := &system.LocalSystem{}
	cranUrl := packageManagerUrl + "/cran/latest"

	const testRVersion = "4.4.2"
	const rBinPath = "/opt/R/4.4.2/bin/R"

	dplyrShinyInstallCall := expectedCall{
		name:           rBinPath,
		args:           []string{"--vanilla", "-e", "install.packages(c(\"dplyr\", \"shiny\"), repos = \"" + cranUrl + "\", clean = TRUE)"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	fileInstallCall := expectedCall{
		name:           rBinPath,
		args:           []string{"--vanilla", "-e", "install.packages(readLines(\"/tmp/r-packages.txt\"), repos = \"" + cranUrl + "\", clean = TRUE)"},
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
				LocalSystem:      defaultSystem,
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            rBinPath,
				Version:          testRVersion,
			},
			setupFs: fakeRInstallation,
			packages: &PackageList{
				Packages:     []string{"dplyr", "shiny"},
				PackageFiles: []string{"/tmp/r-packages.txt"},
			},
			expectedCalls: []expectedCall{
				dplyrShinyInstallCall,
				fileInstallCall,
			},
			wantErr: false,
		},
		{
			name: "not installed",
			manager: &Manager{
				LocalSystem:      defaultSystem,
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            rBinPath,
				Version:          testRVersion,
			},
			expectedCalls:  []expectedCall{},
			wantErr:        true,
			wantErrMessage: "r 4.4.2 is not installed",
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

			err := tt.manager.InstallPackages(tt.packages)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}

func Test_Manager_cranMirror(t *testing.T) {
	assert := assert.New(t)

	tests := []struct {
		name           string
		manager        *Manager
		expectedMirror string
	}{
		{
			name: "default",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{},
			},
			expectedMirror: packageManagerUrl + "/cran/latest",
		},
		{
			name: "ubuntu 22.04",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "Ubuntu",
					Version: "22.04",
				},
			},
			expectedMirror: packageManagerUrl + "/cran/__linux__/jammy/latest",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			assert.Equal(tt.expectedMirror, tt.manager.cranMirror())
		})
	}
}
