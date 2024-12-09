package container

import (
	"fmt"
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	commandMock "pti/mocks/pti/system/command"
	syspkgMock "pti/mocks/pti/system/syspkg"
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
		Vendor:  "ubuntu",
		Version: "22.04",
		Arch:    "amd64",
	}
	rhelSystem := system.LocalSystem{
		Vendor:  "rockylinux",
		Version: "8",
		Arch:    "amd64",
	}

	// Define calls
	type shellCall struct {
		binary         string
		containsArgs   []string
		envVars        []string
		inheritEnvVars bool
	}

	debCAUpdate := shellCall{
		binary:         "update-ca-certificates",
		containsArgs:   []string{},
		envVars:        nil,
		inheritEnvVars: true,
	}
	rhelCAUpdate := shellCall{
		binary:         "update-ca-trust",
		containsArgs:   []string{},
		envVars:        nil,
		inheritEnvVars: true,
	}

	tests := []struct {
		name                 string
		system               system.LocalSystem
		expectedNewShellCall *shellCall
		pmSetup              func(t *testing.T, localSystem *system.LocalSystem)
		shellRunErr          error
		wantErr              bool
		wantErrMessage       string
	}{
		{
			name:                 "success debian-based",
			system:               debSystem,
			expectedNewShellCall: &debCAUpdate,
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().Install(&syspkg.PackageList{Packages: []string{"ca-certificates"}}).Return(nil)
				mockPackageManager.EXPECT().Clean().Return(nil)
				localSystem.PackageManager = mockPackageManager
			},
			shellRunErr: nil,
			wantErr:     false,
		},
		{
			name:                 "success rhel-based",
			system:               rhelSystem,
			expectedNewShellCall: &rhelCAUpdate,
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().Install(&syspkg.PackageList{Packages: []string{"ca-certificates"}}).Return(nil)
				mockPackageManager.EXPECT().Clean().Return(nil)
				localSystem.PackageManager = mockPackageManager
			},
			shellRunErr: nil,
			wantErr:     false,
		},
		{
			name:                 "failed install debian-based",
			system:               debSystem,
			expectedNewShellCall: &debCAUpdate,
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().Install(&syspkg.PackageList{Packages: []string{"ca-certificates"}}).Return(fmt.Errorf("install error"))
				localSystem.PackageManager = mockPackageManager
			},
			shellRunErr:    nil,
			wantErr:        true,
			wantErrMessage: "failed to install ca-certificates",
		},
		{
			name:                 "failed install rhel-based",
			system:               rhelSystem,
			expectedNewShellCall: nil,
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().Install(&syspkg.PackageList{Packages: []string{"ca-certificates"}}).Return(fmt.Errorf("install error"))
				localSystem.PackageManager = mockPackageManager
			},
			shellRunErr:    nil,
			wantErr:        true,
			wantErrMessage: "failed to install ca-certificates",
		},
		{
			name:                 "failed update debian-based",
			system:               debSystem,
			expectedNewShellCall: &debCAUpdate,
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().Install(&syspkg.PackageList{Packages: []string{"ca-certificates"}}).Return(nil)
				mockPackageManager.EXPECT().Clean().Return(nil)
				localSystem.PackageManager = mockPackageManager
			},
			shellRunErr:    fmt.Errorf("update error"),
			wantErr:        true,
			wantErrMessage: "failed to update CA certificates",
		},
		{
			name:                 "failed update rhel-based",
			system:               rhelSystem,
			expectedNewShellCall: &rhelCAUpdate,
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().Install(&syspkg.PackageList{Packages: []string{"ca-certificates"}}).Return(nil)
				mockPackageManager.EXPECT().Clean().Return(nil)
				localSystem.PackageManager = mockPackageManager
			},
			shellRunErr:    fmt.Errorf("update error"),
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

			// Setup package manager
			tt.pmSetup(t, &tt.system)

			oldNSC := command.NewShellCommand
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				mockShellCommand := commandMock.NewMockShellCommandRunner(t)
				if tt.expectedNewShellCall != nil {
					if tt.shellRunErr != nil {
						mockShellCommand.EXPECT().Run().Return(tt.shellRunErr)
					} else {
						mockShellCommand.EXPECT().Run().Return(nil)
					}
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
		})
	}
}
