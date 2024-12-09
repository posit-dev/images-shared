package container

import (
	"fmt"
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	commandMock "pti/mocks/pti/system/command"
	"pti/system"
	"pti/system/command"
	"pti/system/file"
	"pti/system/syspkg"
	"testing"
)

func Test_Bootstrap(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	// Define systems to test against
	debSystem := system.LocalSystem{
		Vendor:         "ubuntu",
		Version:        "22.04",
		Arch:           "amd64",
		PackageManager: syspkg.NewAptManager(),
	}
	rhelSystem := system.LocalSystem{
		Vendor:         "rockylinux",
		Version:        "8",
		Arch:           "amd64",
		PackageManager: syspkg.NewDnfManager(),
	}

	// Define calls
	type shellCall struct {
		binary         string
		containsArgs   []string
		envVars        []string
		inheritEnvVars bool
	}

	debCAInstall := shellCall{
		binary:         "apt",
		containsArgs:   []string{"install", "-y", "-q", "ca-certificates"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	debCAUpdate := shellCall{
		binary:         "update-ca-certificates",
		containsArgs:   []string{},
		envVars:        nil,
		inheritEnvVars: true,
	}
	debClean := shellCall{
		binary:         "apt",
		containsArgs:   []string{"clean", "-q"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	debAutoRemove := shellCall{
		binary:         "apt",
		containsArgs:   []string{"autoremove", "-y", "-q"},
		envVars:        nil,
		inheritEnvVars: true,
	}

	rhelCAInstall := shellCall{
		binary:         "dnf",
		containsArgs:   []string{"-y", "-q", "install", "ca-certificates"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	rhelCAUpdate := shellCall{
		binary:         "update-ca-trust",
		containsArgs:   []string{},
		envVars:        nil,
		inheritEnvVars: true,
	}
	rhelClean := shellCall{
		binary:         "dnf",
		containsArgs:   []string{"-y", "-q", "clean", "all"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	rhelAutoRemove := shellCall{
		binary:         "dnf",
		containsArgs:   []string{"-y", "-q", "autoremove"},
		envVars:        nil,
		inheritEnvVars: true,
	}

	tests := []struct {
		name                  string
		system                system.LocalSystem
		expectedNewShellCalls []shellCall
		runErr                error
		runErrOnCall          int
		wantErr               bool
		wantErrMessage        string
	}{
		{
			name:   "success debian-based",
			system: debSystem,
			expectedNewShellCalls: []shellCall{
				debCAInstall,
				debCAUpdate,
				debClean,
				debAutoRemove,
			},
			runErr:       nil,
			runErrOnCall: 0,
			wantErr:      false,
		},
		{
			name:   "success rhel-based",
			system: rhelSystem,
			expectedNewShellCalls: []shellCall{
				rhelCAInstall,
				rhelCAUpdate,
				rhelClean,
				rhelAutoRemove,
			},
			runErr:       nil,
			runErrOnCall: 0,
			wantErr:      false,
		},
		{
			name:   "failed install debian-based",
			system: debSystem,
			expectedNewShellCalls: []shellCall{
				debCAInstall,
			},
			runErr:         fmt.Errorf("install error"),
			runErrOnCall:   1,
			wantErr:        true,
			wantErrMessage: "failed to install ca-certificates",
		},
		{
			name:   "failed install rhel-based",
			system: rhelSystem,
			expectedNewShellCalls: []shellCall{
				rhelCAInstall,
			},
			runErr:         fmt.Errorf("install error"),
			runErrOnCall:   1,
			wantErr:        true,
			wantErrMessage: "failed to install ca-certificates",
		},
		{
			name:   "failed update debian-based",
			system: debSystem,
			expectedNewShellCalls: []shellCall{
				debCAInstall,
				debCAUpdate,
				debClean,
				debAutoRemove,
			},
			runErr:         fmt.Errorf("update error"),
			runErrOnCall:   2,
			wantErr:        true,
			wantErrMessage: "failed to update CA certificates",
		},
		{
			name:   "failed update rhel-based",
			system: rhelSystem,
			expectedNewShellCalls: []shellCall{
				rhelCAInstall,
				rhelCAUpdate,
				rhelClean,
				rhelAutoRemove,
			},
			runErr:         fmt.Errorf("update error"),
			runErrOnCall:   2,
			wantErr:        true,
			wantErrMessage: "failed to update CA certificates",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := file.AppFs
			file.AppFs = afero.NewMemMapFs()
			defer func() {
				file.AppFs = oldFs
			}()

			newShellCalls := 0
			oldNSC := command.NewShellCommand
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				assert.Equal(tt.expectedNewShellCalls[newShellCalls].binary, name)
				for _, arg := range tt.expectedNewShellCalls[newShellCalls].containsArgs {
					assert.Contains(args, arg)
				}
				assert.Equal(tt.expectedNewShellCalls[newShellCalls].envVars, envVars)
				assert.Equal(tt.expectedNewShellCalls[newShellCalls].inheritEnvVars, inheritEnvVars)

				newShellCalls++
				mockShellCommand := commandMock.NewMockShellCommandRunner(t)

				if newShellCalls == tt.runErrOnCall {
					mockShellCommand.EXPECT().Run().Return(tt.runErr)
				} else {
					mockShellCommand.EXPECT().Run().Return(nil)
				}
				return mockShellCommand
			}
			defer func() {
				command.NewShellCommand = oldNSC
			}()

			// Run test
			err := Bootstrap(&tt.system)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}

			assert.Equal(len(tt.expectedNewShellCalls), len(tt.expectedNewShellCalls))
		})
	}
}
