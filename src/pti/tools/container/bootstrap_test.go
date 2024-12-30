package container

import (
	"fmt"
	commandMock "pti/mocks/pti/system/command"
	syspkgMock "pti/mocks/pti/system/syspkg"
	"pti/ptitest"
	"pti/system"
	"pti/system/command"
	"pti/system/file"
	"pti/system/syspkg"
	"testing"

	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
)

func bootstrapPackageManagerMock(t *testing.T, localSystem *system.LocalSystem) {
	mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
	expectedPackages := []string{"ca-certificates"}
	switch localSystem.Vendor {
	case "ubuntu":
		mockPackageManager.EXPECT().GetBin().Return("apt-get")
	case "rockylinux":
		mockPackageManager.EXPECT().GetBin().Return("dnf")
		expectedPackages = append(expectedPackages, "epel-release")
	default:
		t.Fatalf("unsupported vendor: %s", localSystem.Vendor)
	}
	mockPackageManager.EXPECT().Update().Return(nil)
	mockPackageManager.EXPECT().
		Install(mock.AnythingOfType("*syspkg.PackageList")).
		RunAndReturn(func(l *syspkg.PackageList) error {
			assert.Contains(t, expectedPackages, l.Packages[0])
			return nil
		})
	mockPackageManager.EXPECT().Clean().Return(nil)
	localSystem.PackageManager = mockPackageManager
}

func Test_Bootstrap(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name                  string
		system                *system.LocalSystem
		expectedNewShellCalls []*ptitest.ShellCall
		pmSetup               func(t *testing.T, localSystem *system.LocalSystem)
		callErr               *ptitest.FakeShellCallError
		wantErr               bool
		wantErrMessage        string
	}{
		{
			name:   "success debian-based",
			system: ptitest.NewUbuntuSystem(),
			expectedNewShellCalls: []*ptitest.ShellCall{
				ptitest.CommonShellCalls["debCAUpdate"],
			},
			pmSetup: bootstrapPackageManagerMock,
			callErr: nil,
			wantErr: false,
		},
		{
			name:   "success rhel-based",
			system: ptitest.NewRockySystem(),
			expectedNewShellCalls: []*ptitest.ShellCall{
				ptitest.CommonShellCalls["rhelCAUpdate"],
			},
			pmSetup: bootstrapPackageManagerMock,
			callErr: nil,
			wantErr: false,
		},
		{
			name:   "failed install debian-based",
			system: ptitest.NewUbuntuSystem(),
			expectedNewShellCalls: []*ptitest.ShellCall{
				ptitest.CommonShellCalls["debCAUpdate"],
			},
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().Update().Return(nil)
				mockPackageManager.EXPECT().
					Install(&syspkg.PackageList{Packages: []string{"ca-certificates"}}).
					Return(fmt.Errorf("install error"))
				mockPackageManager.EXPECT().Clean().Return(nil)
				localSystem.PackageManager = mockPackageManager
			},
			callErr:        nil,
			wantErr:        true,
			wantErrMessage: "failed to install ca-certificates",
		},
		{
			name:   "failed install rhel-based",
			system: ptitest.NewRockySystem(),
			expectedNewShellCalls: []*ptitest.ShellCall{
				ptitest.CommonShellCalls["rhelCAUpdate"],
			},
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().Update().Return(nil)
				mockPackageManager.EXPECT().
					Install(&syspkg.PackageList{Packages: []string{"ca-certificates"}}).
					Return(fmt.Errorf("install error"))
				mockPackageManager.EXPECT().Clean().Return(nil)
				localSystem.PackageManager = mockPackageManager
			},
			callErr:        nil,
			wantErr:        true,
			wantErrMessage: "failed to install ca-certificates",
		},
		{
			name:   "failed update debian-based",
			system: ptitest.NewUbuntuSystem(),
			expectedNewShellCalls: []*ptitest.ShellCall{
				ptitest.CommonShellCalls["debCAUpdate"],
			},
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().Update().Return(nil)
				mockPackageManager.EXPECT().
					Install(&syspkg.PackageList{Packages: []string{"ca-certificates"}}).
					Return(nil)
				mockPackageManager.EXPECT().Clean().Return(nil)
				localSystem.PackageManager = mockPackageManager
			},
			callErr: &ptitest.FakeShellCallError{
				OnCall: 0,
				Err:    fmt.Errorf("update certs error"),
			},
			wantErr:        true,
			wantErrMessage: "failed to update CA certificates",
		},
		{
			name:   "failed update rhel-based",
			system: ptitest.NewRockySystem(),
			expectedNewShellCalls: []*ptitest.ShellCall{
				ptitest.CommonShellCalls["rhelCAUpdate"],
			},
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().Update().Return(nil)
				mockPackageManager.EXPECT().
					Install(&syspkg.PackageList{Packages: []string{"ca-certificates"}}).
					Return(nil)
				mockPackageManager.EXPECT().Clean().Return(nil)
				localSystem.PackageManager = mockPackageManager
			},
			callErr: &ptitest.FakeShellCallError{
				OnCall: 0,
				Err:    fmt.Errorf("update certs error"),
			},
			wantErr:        true,
			wantErrMessage: "failed to update CA certificates",
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

			// Setup package manager
			tt.pmSetup(t, tt.system)

			iShellCalls := 0
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				mockShellCommand := commandMock.NewMockShellCommandRunner(t)
				tt.expectedNewShellCalls[iShellCalls].Equal(t, name, args, envVars, inheritEnvVars)
				if tt.callErr != nil && tt.callErr.OnCall == iShellCalls {
					mockShellCommand.EXPECT().Run().Return(tt.callErr.Err)
				} else {
					mockShellCommand.EXPECT().Run().Return(nil)
				}
				iShellCalls++

				return mockShellCommand
			}

			// Run test
			err := Bootstrap(tt.system)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}
