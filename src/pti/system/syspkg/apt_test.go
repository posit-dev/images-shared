package syspkg

import (
	"fmt"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"os"
	commandMock "pti/mocks/pti/system/command"
	"pti/system/command"
	"pti/system/file"
	"testing"
)

func TestNewAptManager(t *testing.T) {
	assert := assert.New(t)

	m := NewAptManager()

	assert.Equal("apt", m.GetBin())
	assert.Contains(m.installOpts, "install")
	assert.Contains(m.updateOpts, "update")
	assert.Contains(m.upgradeOpts, "upgrade")
	assert.Contains(m.distUpgradeOpts, "dist-upgrade")
	assert.Contains(m.removeOpts, "remove")
	assert.Contains(m.autoRemoveOpts, "autoremove")
	assert.Contains(m.cleanOpts, "clean")
}

func TestAptManager_Install(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	d := os.TempDir()
	testPackageList := &file.File{
		Path: d + "/test_package_list.txt",
	}
	fh, err := os.Create(testPackageList.Path)
	require.Nil(err, "Create() error = %v, want nil", err)
	_, err = fh.WriteString("pkg3\npkg4\n")
	require.Nil(err, "WriteString() error = %v, want nil", err)
	defer fh.Close()

	tests := []struct {
		name                  string
		packageList           *PackageList
		expectedNewShellCalls int
		runErr                error
		wantErr               bool
	}{
		{
			name:                  "Empty package list",
			packageList:           &PackageList{},
			expectedNewShellCalls: 0,
			wantErr:               false,
		},
		{
			name:                  "Runtime error empty package list",
			packageList:           &PackageList{},
			expectedNewShellCalls: 0,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               false,
		},
		{
			name: "String packages",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
			},
			expectedNewShellCalls: 1,
			wantErr:               false,
		},
		{
			name: "Local packages",
			packageList: &PackageList{
				LocalPackages: []*file.File{
					{Path: "/tmp/pkg1.deb"},
					{Path: "/tmp/pkg2.deb"},
				},
			},
			expectedNewShellCalls: 2,
			wantErr:               false,
		},
		{
			name: "Runtime error local packages",
			packageList: &PackageList{
				LocalPackages: []*file.File{
					{Path: "/tmp/pkg1.deb"},
					{Path: "/tmp/pkg2.deb"},
				},
			},
			expectedNewShellCalls: 1,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               true,
		},
		{
			name: "String and local packages",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
				LocalPackages: []*file.File{
					{Path: "/tmp/pkg1.deb"},
					{Path: "/tmp/pkg2.deb"},
				},
			},
			expectedNewShellCalls: 3,
			wantErr:               false,
		},
		{
			name: "String, file lists, and local packages",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
				PackageListFiles: []*file.File{
					testPackageList,
				},
				LocalPackages: []*file.File{
					{Path: "/tmp/pkg1.deb"},
					{Path: "/tmp/pkg2.deb"},
				},
			},
			expectedNewShellCalls: 3,
			wantErr:               false,
		},
		{
			name: "Runtime error string, file lists, and local packages",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
				PackageListFiles: []*file.File{
					testPackageList,
				},
				LocalPackages: []*file.File{
					{Path: "/tmp/pkg1.deb"},
					{Path: "/tmp/pkg2.deb"},
				},
			},
			expectedNewShellCalls: 1,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               true,
		},
		{
			name: "File lists and local packages",
			packageList: &PackageList{
				PackageListFiles: []*file.File{
					testPackageList,
				},
				LocalPackages: []*file.File{
					{Path: "/tmp/pkg1.deb"},
					{Path: "/tmp/pkg2.deb"},
				},
			},
			expectedNewShellCalls: 3,
			wantErr:               false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			newShellCalls := 0
			m := NewAptManager()

			old := command.NewShellCommand
			defer func() {
				command.NewShellCommand = old
			}()
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				assert.Equal("apt", name, "binary name = %v, want binary apt", name)
				for _, arg := range m.installOpts {
					assert.Contains(args, arg, "args = %v, want contains %v", args, arg)
				}

				p, err := tt.packageList.GetPackages()
				require.Nil(err, "GetPackages() error = %v, want nil", err)

				if newShellCalls == 0 && len(p) > 0 {
					for _, pkg := range p {
						assert.Contains(args, pkg, "args = %v, want contains %v", args, pkg)
					}
				} else {
					var localPackageIndex int
					if len(p) == 0 {
						localPackageIndex = newShellCalls
					} else {
						localPackageIndex = newShellCalls - 1
					}
					assert.Contains(args, tt.packageList.LocalPackages[localPackageIndex].Path, "args = %v, want args %v", args)
				}
				newShellCalls++

				mockShellCommand := commandMock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(tt.runErr)
				return mockShellCommand
			}

			err := m.Install(tt.packageList)
			assert.Equal(tt.expectedNewShellCalls, newShellCalls, "newShellCalls = %v, want %v", newShellCalls, tt.expectedNewShellCalls)
			assert.Equal(tt.wantErr, err != nil, "Install() error = %v, wantErr %v", err, tt.wantErr)
		})
	}
}

func TestAptManager_Remove(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	d := os.TempDir()
	testPackageList := &file.File{
		Path: d + "/test_package_list.txt",
	}
	fh, err := os.Create(testPackageList.Path)
	require.Nil(err, "Create() error = %v, want nil", err)
	_, err = fh.WriteString("pkg3\npkg4\n")
	require.Nil(err, "WriteString() error = %v, want nil", err)
	defer fh.Close()

	tests := []struct {
		name                  string
		packageList           *PackageList
		expectedNewShellCalls int
		runErr                error
		wantErr               bool
	}{
		{
			name:                  "Empty package list",
			packageList:           &PackageList{},
			expectedNewShellCalls: 0,
			wantErr:               false,
		},
		{
			name:                  "Empty package runtime error",
			packageList:           &PackageList{},
			expectedNewShellCalls: 0,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               false,
		},
		{
			name: "String packages",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
			},
			expectedNewShellCalls: 1,
			wantErr:               false,
		},
		{
			name: "File list packages",
			packageList: &PackageList{
				PackageListFiles: []*file.File{
					testPackageList,
				},
			},
			expectedNewShellCalls: 1,
			wantErr:               false,
		},
		{
			name: "String and file list packages",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
				PackageListFiles: []*file.File{
					testPackageList,
				},
			},
			expectedNewShellCalls: 1,
			wantErr:               false,
		},
		{
			name: "Runtime error",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
				PackageListFiles: []*file.File{
					testPackageList,
				},
			},
			expectedNewShellCalls: 1,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			newShellCalls := 0
			m := NewAptManager()

			old := command.NewShellCommand
			defer func() {
				command.NewShellCommand = old
			}()
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				assert.Equal("apt", name, "binary name = %v, want binary apt", name)
				for _, arg := range m.removeOpts {
					assert.Contains(args, arg, "args = %v, want contains %v", args, arg)
				}

				p, err := tt.packageList.GetPackages()
				require.Nil(err, "GetPackages() error = %v, want nil", err)

				for _, pkg := range p {
					assert.Contains(args, pkg, "args = %v, want contains %v", args, pkg)
				}
				newShellCalls++

				mockShellCommand := commandMock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(tt.runErr)
				return mockShellCommand
			}

			err := m.Remove(tt.packageList)
			assert.Equal(tt.wantErr, err != nil, "Remove() error = %v, wantErr %v", err, tt.wantErr)
			assert.Equal(tt.expectedNewShellCalls, newShellCalls, "newShellCalls = %v, want %v", newShellCalls, tt.expectedNewShellCalls)
		})
	}
}

func TestAptManager_Update(t *testing.T) {
	assert := assert.New(t)

	tests := []struct {
		name    string
		runErr  error
		wantErr bool
	}{
		{
			name:    "No error",
			runErr:  nil,
			wantErr: false,
		},
		{
			name:    "Runtime error",
			runErr:  fmt.Errorf("runtime error"),
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			m := NewAptManager()

			newShellCalled := false
			old := command.NewShellCommand
			defer func() {
				command.NewShellCommand = old
			}()
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				newShellCalled = true

				assert.Equal("apt", name, "binary name = %v, want binary apt", name)
				for _, arg := range m.updateOpts {
					assert.Contains(args, arg, "args = %v, want contains %v", args, arg)
				}

				mockShellCommand := commandMock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(tt.runErr)
				return mockShellCommand
			}

			err := m.Update()
			assert.Equal(tt.wantErr, err != nil, "Update() error = %v, wantErr %v", err, tt.wantErr)
			assert.True(newShellCalled, "NewShellCommand() was not called")
		})
	}
}

func TestAptManager_Upgrade(t *testing.T) {
	assert := assert.New(t)

	tests := []struct {
		name                  string
		expectedNewShellCalls int
		fullUpgrade           bool
		runErr                error
		wantErr               bool
	}{
		{
			name:                  "No error",
			expectedNewShellCalls: 1,
			fullUpgrade:           false,
			runErr:                nil,
			wantErr:               false,
		},
		{
			name:                  "Runtime error",
			expectedNewShellCalls: 1,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               true,
		},
		{
			name:                  "With full upgrade",
			expectedNewShellCalls: 2,
			fullUpgrade:           true,
			runErr:                nil,
			wantErr:               false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			m := NewAptManager()

			newShellCalls := 0
			old := command.NewShellCommand
			defer func() {
				command.NewShellCommand = old
			}()
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				newShellCalls++

				assert.Equal("apt", name, "binary name = %v, want binary apt", name)

				var opts []string
				if newShellCalls == 2 && tt.fullUpgrade {
					opts = m.distUpgradeOpts
				} else {
					opts = m.upgradeOpts
				}
				for _, arg := range opts {
					assert.Contains(args, arg, "args = %v, want contains %v", args, arg)
				}

				mockShellCommand := commandMock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(tt.runErr)
				return mockShellCommand
			}

			err := m.Upgrade(tt.fullUpgrade)
			assert.Equal(tt.wantErr, err != nil, "Upgrade() error = %v, wantErr %v", err, tt.wantErr)
			assert.Equal(tt.expectedNewShellCalls, newShellCalls, "newShellCalls = %v, want 1", newShellCalls)
		})
	}
}

/*
func TestAptManager_Clean(t *testing.T) {
	assert := assert.New(t)

	tests := []struct {
		name    string
		runErr  error
		wantErr bool
	}{
		{
			name:    "No error",
			runErr:  nil,
			wantErr: false,
		},
		{
			name:    "Runtime error",
			runErr:  fmt.Errorf("runtime error"),
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			m := NewAptManager()

			newShellCalls := 0
			old := command.NewShellCommand
			defer func() {
				command.NewShellCommand = old
			}()
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				newShellCalls = true

				assert.Equal("apt", name, "binary name = %v, want binary apt", name)

				var opts []string
				switch newShellCalls {
				case 1:
					opts = m.cleanOpts
				case 2:
					opts = m.autoRemoveOpts
				}
				for _, arg := range opts {
					assert.Contains(args, arg, "args = %v, want contains %v", args, arg)
				}

				mockShellCommand := commandMock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(tt.runErr)
				return mockShellCommand
			}

			err := m.Clean()
			assert.Equal(tt.wantErr, err != nil, "Clean() error = %v, wantErr %v", err, tt.wantErr)
			assert.True(newShellCalled, "NewShellCommand() was not called")
		})
	}
}
*/
