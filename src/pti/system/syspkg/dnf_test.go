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

func TestNewDnfManager(t *testing.T) {
	assert := assert.New(t)

	m := NewDnfManager()

	assert.Equal("dnf", m.GetBin())
	assert.Contains(m.installOpts, "install")
	assert.Contains(m.upgradeOpts, "upgrade")
	assert.Contains(m.removeOpts, "remove")
	assert.Contains(m.autoRemoveOpts, "autoremove")
	assert.Contains(m.cleanOpts, "clean")
}

func TestDnfManager_Install(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name                  string
		packageList           *PackageList
		setupFs               func(tmpDir string, list *PackageList) error
		expectedNewShellCalls int
		runErr                error
		wantErr               bool
		wantErrMessage        string
	}{
		{
			name:        "no packages",
			packageList: &PackageList{},
			setupFs: func(tmpDir string, list *PackageList) error {
				return nil
			},
			expectedNewShellCalls: 0,
			wantErr:               false,
		},
		{
			name:        "runtime error not reached on empty package list",
			packageList: &PackageList{},
			setupFs: func(tmpDir string, list *PackageList) error {
				return nil
			},
			expectedNewShellCalls: 0,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               false,
		},
		{
			name: "string package list",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				return nil
			},
			expectedNewShellCalls: 1,
			wantErr:               false,
		},
		{
			name: "string package list runtime error",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				return nil
			},
			expectedNewShellCalls: 1,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               true,
			wantErrMessage:        "failed to install packages",
		},
		{
			name: "local packages list",
			packageList: &PackageList{
				LocalPackages: []*file.File{
					{Path: "pkg1.rpm"},
					{Path: "pkg2.rpm"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				for _, pkg := range list.LocalPackages {
					newPath := tmpDir + "/" + pkg.Path
					_, err := os.Create(newPath)
					if err != nil {
						return err
					}
					pkg.Path = newPath
				}
				return nil
			},
			expectedNewShellCalls: 2,
			wantErr:               false,
		},
		{
			name: "local packages list runtime error",
			packageList: &PackageList{
				LocalPackages: []*file.File{
					{Path: "pkg1.rpm"},
					{Path: "pkg2.rpm"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				for _, pkg := range list.LocalPackages {
					newPath := tmpDir + "/" + pkg.Path
					_, err := os.Create(newPath)
					if err != nil {
						return err
					}
					pkg.Path = newPath
				}
				return nil
			},
			expectedNewShellCalls: 1,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               true,
			wantErrMessage:        "failed to install local package",
		},
		{
			name: "local packages package does not exist",
			packageList: &PackageList{
				LocalPackages: []*file.File{
					{Path: "pkg1.rpm"},
					{Path: "pkg2.rpm"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				return nil
			},
			expectedNewShellCalls: 0,
			runErr:                nil,
			wantErr:               true,
			wantErrMessage:        "does not exist",
		},
		{
			name: "string and local packages list",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
				LocalPackages: []*file.File{
					{Path: "pkg1.rpm"},
					{Path: "pkg2.rpm"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				for _, pkg := range list.LocalPackages {
					newPath := tmpDir + "/" + pkg.Path
					_, err := os.Create(newPath)
					if err != nil {
						return err
					}
					pkg.Path = newPath
				}
				return nil
			},
			expectedNewShellCalls: 3,
			wantErr:               false,
		},
		{
			name: "string, file lists, and local packages",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
				PackageListFiles: []*file.File{
					{Path: "test_package_list.txt"},
				},
				LocalPackages: []*file.File{
					{Path: "pkg1.rpm"},
					{Path: "pkg2.rpm"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				newPath := tmpDir + "/" + list.PackageListFiles[0].Path

				fh, err := os.Create(newPath)
				if err != nil {
					return err
				}

				_, err = fh.WriteString("pkg3\npkg4\n")
				if err != nil {
					return err
				}
				defer fh.Close()

				list.PackageListFiles[0].Path = newPath

				for _, pkg := range list.LocalPackages {
					newPath := tmpDir + "/" + pkg.Path
					_, err := os.Create(newPath)
					if err != nil {
						return err
					}
					pkg.Path = newPath
				}
				return nil
			},
			expectedNewShellCalls: 3,
			wantErr:               false,
		},
		{
			name: "string, file lists, and local packages with runtime error",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
				PackageListFiles: []*file.File{
					{Path: "test_package_list.txt"},
				},
				LocalPackages: []*file.File{
					{Path: "pkg1.rpm"},
					{Path: "pkg2.rpm"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				newPath := tmpDir + "/" + list.PackageListFiles[0].Path

				fh, err := os.Create(newPath)
				if err != nil {
					return err
				}

				_, err = fh.WriteString("pkg3\npkg4\n")
				if err != nil {
					return err
				}
				defer fh.Close()

				list.PackageListFiles[0].Path = newPath

				for _, pkg := range list.LocalPackages {
					newPath := tmpDir + "/" + pkg.Path
					_, err := os.Create(newPath)
					if err != nil {
						return err
					}
					pkg.Path = newPath
				}
				return nil
			},
			expectedNewShellCalls: 1,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               true,
			wantErrMessage:        "failed to install packages",
		},
		{
			name: "file lists and local packages",
			packageList: &PackageList{
				PackageListFiles: []*file.File{
					{Path: "test_package_list.txt"},
				},
				LocalPackages: []*file.File{
					{Path: "pkg1.rpm"},
					{Path: "pkg2.rpm"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				newPath := tmpDir + "/" + list.PackageListFiles[0].Path

				fh, err := os.Create(newPath)
				if err != nil {
					return err
				}

				_, err = fh.WriteString("pkg3\npkg4\n")
				if err != nil {
					return err
				}
				defer fh.Close()

				list.PackageListFiles[0].Path = newPath

				for _, pkg := range list.LocalPackages {
					newPath := tmpDir + "/" + pkg.Path
					_, err := os.Create(newPath)
					if err != nil {
						return err
					}
					pkg.Path = newPath
				}
				return nil
			},
			expectedNewShellCalls: 3,
			wantErr:               false,
		},
		{
			name: "file lists",
			packageList: &PackageList{
				PackageListFiles: []*file.File{
					{Path: "test_package_list.txt"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				newPath := tmpDir + "/" + list.PackageListFiles[0].Path

				fh, err := os.Create(newPath)
				if err != nil {
					return err
				}

				_, err = fh.WriteString("pkg3\npkg4\n")
				if err != nil {
					return err
				}
				defer fh.Close()

				list.PackageListFiles[0].Path = newPath

				return nil
			},
			expectedNewShellCalls: 1,
			wantErr:               false,
		},
		{
			name: "file list does not exist",
			packageList: &PackageList{
				PackageListFiles: []*file.File{
					{Path: "nonexistent.txt"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				list.PackageListFiles[0].Path = tmpDir + "/" + list.PackageListFiles[0].Path
				return nil
			},
			expectedNewShellCalls: 0,
			wantErr:               true,
			wantErrMessage:        "error occurred while parsing packages to install",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			newShellCalls := 0
			m := NewDnfManager()

			d := t.TempDir()
			err := tt.setupFs(d, tt.packageList)
			require.Nil(err, "setupFs() error = %v, want nil", err)

			old := command.NewShellCommand
			defer func() {
				command.NewShellCommand = old
			}()
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				assert.Equal("dnf", name, "binary name = %v, want binary dnf", name)
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

			err = m.Install(tt.packageList)
			assert.Equal(tt.expectedNewShellCalls, newShellCalls, "newShellCalls = %v, want %v", newShellCalls, tt.expectedNewShellCalls)
			if tt.wantErr {
				assert.ErrorContains(err, tt.wantErrMessage, "Install() error = %v, wantErr %v", err, tt.wantErr)
			} else {
				assert.NoError(err, "Install() error = %v, want nil", err)
			}
		})
	}
}

func TestDnfManager_Remove(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name                  string
		packageList           *PackageList
		setupFs               func(tmpDir string, list *PackageList) error
		expectedNewShellCalls int
		runErr                error
		wantErr               bool
		wantErrMessage        string
	}{
		{
			name:        "no packages",
			packageList: &PackageList{},
			setupFs: func(tmpDir string, list *PackageList) error {
				return nil
			},
			expectedNewShellCalls: 0,
			wantErr:               false,
		},
		{
			name:        "empty package runtime error not reached",
			packageList: &PackageList{},
			setupFs: func(tmpDir string, list *PackageList) error {
				return nil
			},
			expectedNewShellCalls: 0,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               false,
		},
		{
			name: "string packages",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				return nil
			},
			expectedNewShellCalls: 1,
			wantErr:               false,
		},
		{
			name: "file list packages",
			packageList: &PackageList{
				PackageListFiles: []*file.File{
					{Path: "test_package_list.txt"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				newPath := tmpDir + "/" + list.PackageListFiles[0].Path
				fh, err := os.Create(newPath)
				if err != nil {
					return err
				}
				_, err = fh.WriteString("pkg3\npkg4\n")
				if err != nil {
					return err
				}
				defer fh.Close()
				list.PackageListFiles[0].Path = newPath
				return nil
			},
			expectedNewShellCalls: 1,
			wantErr:               false,
		},
		{
			name: "file list does not exist",
			packageList: &PackageList{
				PackageListFiles: []*file.File{
					{Path: "nonexistent.txt"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				list.PackageListFiles[0].Path = tmpDir + "/" + list.PackageListFiles[0].Path
				return nil
			},
			expectedNewShellCalls: 0,
			wantErr:               true,
			wantErrMessage:        "error occurred while parsing packages to remove",
		},
		{
			name: "string and file list packages",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
				PackageListFiles: []*file.File{
					{Path: "test_package_list.txt"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				newPath := tmpDir + "/" + list.PackageListFiles[0].Path
				fh, err := os.Create(newPath)
				if err != nil {
					return err
				}
				_, err = fh.WriteString("pkg3\npkg4\n")
				if err != nil {
					return err
				}
				defer fh.Close()
				list.PackageListFiles[0].Path = newPath
				return nil
			},
			expectedNewShellCalls: 1,
			wantErr:               false,
		},
		{
			name: "runtime error",
			packageList: &PackageList{
				Packages: []string{"pkg1", "pkg2"},
				PackageListFiles: []*file.File{
					{Path: "test_package_list.txt"},
				},
			},
			setupFs: func(tmpDir string, list *PackageList) error {
				newPath := tmpDir + "/" + list.PackageListFiles[0].Path
				fh, err := os.Create(newPath)
				if err != nil {
					return err
				}
				_, err = fh.WriteString("pkg3\npkg4\n")
				if err != nil {
					return err
				}
				defer fh.Close()
				list.PackageListFiles[0].Path = newPath
				return nil
			},
			expectedNewShellCalls: 1,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               true,
			wantErrMessage:        "failed to remove packages",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			newShellCalls := 0
			m := NewDnfManager()

			d := t.TempDir()
			err := tt.setupFs(d, tt.packageList)
			require.Nil(err, "setupFs() error = %v, want nil", err)

			old := command.NewShellCommand
			defer func() {
				command.NewShellCommand = old
			}()
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				assert.Equal("dnf", name, "binary name = %v, want binary dnf", name)
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

			err = m.Remove(tt.packageList)
			if tt.wantErr {
				assert.ErrorContains(err, tt.wantErrMessage, "Remove() error = %v, wantErr %v", err, tt.wantErr)
			} else {
				assert.NoError(err, "Remove() error = %v, want nil", err)
			}
			assert.Equal(tt.expectedNewShellCalls, newShellCalls, "newShellCalls = %v, want %v", newShellCalls, tt.expectedNewShellCalls)
		})
	}
}

func TestDnfManager_Update(t *testing.T) {
	assert := assert.New(t)

	assert.Nil(NewDnfManager().Update())
}

func TestDnfManager_Upgrade(t *testing.T) {
	assert := assert.New(t)

	tests := []struct {
		name                  string
		expectedNewShellCalls int
		fullUpgrade           bool
		runErrOnCall          int
		runErr                error
		wantErr               bool
		wantErrMessage        string
	}{
		{
			name:                  "success",
			expectedNewShellCalls: 1,
			runErrOnCall:          0,
			fullUpgrade:           false,
			runErr:                nil,
			wantErr:               false,
		},
		{
			name:                  "upgrade runtime error",
			expectedNewShellCalls: 1,
			runErrOnCall:          1,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               true,
			wantErrMessage:        "dnf upgrade failed",
		},
		{
			name:                  "success with full upgrade flag does nothing",
			expectedNewShellCalls: 1,
			fullUpgrade:           true,
			runErr:                nil,
			wantErr:               false,
		},
		{
			name:                  "full upgrade runtime error not reached",
			expectedNewShellCalls: 1,
			runErrOnCall:          2,
			fullUpgrade:           true,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			m := NewDnfManager()

			newShellCalls := 0
			old := command.NewShellCommand
			defer func() {
				command.NewShellCommand = old
			}()
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				newShellCalls++

				assert.Equal("dnf", name, "binary name = %v, want binary dnf", name)

				opts := m.upgradeOpts
				for _, arg := range opts {
					assert.Contains(args, arg, "args = %v, want contains %v", args, arg)
				}

				mockShellCommand := commandMock.NewMockShellCommandRunner(t)
				if newShellCalls == tt.runErrOnCall {
					mockShellCommand.EXPECT().Run().Return(tt.runErr)
				} else {
					mockShellCommand.EXPECT().Run().Return(nil)
				}
				return mockShellCommand
			}

			err := m.Upgrade(tt.fullUpgrade)
			if tt.wantErr {
				assert.ErrorContains(err, tt.wantErrMessage, "Upgrade() error = %v, wantErr %v", err, tt.wantErr)
			} else {
				assert.NoError(err, "Upgrade() error = %v, want nil", err)
			}
			assert.Equal(tt.expectedNewShellCalls, newShellCalls, "newShellCalls = %v, want 1", newShellCalls)
		})
	}
}

func TestDnfManager_Clean(t *testing.T) {
	assert := assert.New(t)

	tests := []struct {
		name                  string
		expectedNewShellCalls int
		runErrOnCall          int
		runErr                error
		wantErr               bool
		wantErrMessage        string
	}{
		{
			name:                  "No error",
			expectedNewShellCalls: 2,
			runErrOnCall:          0,
			runErr:                nil,
			wantErr:               false,
		},
		{
			name:                  "Runtime error on clean",
			expectedNewShellCalls: 1,
			runErrOnCall:          1,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               true,
			wantErrMessage:        "dnf clean failed",
		},
		{
			name:                  "Runtime error on autoremove",
			expectedNewShellCalls: 2,
			runErrOnCall:          2,
			runErr:                fmt.Errorf("runtime error"),
			wantErr:               true,
			wantErrMessage:        "dnf autoremove failed",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			m := NewDnfManager()

			newShellCalls := 0
			oldNSC := command.NewShellCommand
			defer func() {
				command.NewShellCommand = oldNSC
			}()

			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				newShellCalls++

				assert.Equal("dnf", name, "binary name = %v, want binary dnf", name)

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
				if newShellCalls == tt.runErrOnCall {
					mockShellCommand.EXPECT().Run().Return(tt.runErr)
				} else {
					mockShellCommand.EXPECT().Run().Return(nil)
				}
				return mockShellCommand
			}

			err := m.Clean()
			if tt.wantErr {
				assert.ErrorContains(err, tt.wantErrMessage, "Clean() error = %v, wantErr %v", err, tt.wantErr)
			} else {
				assert.NoError(err, "Clean() error = %v, want nil", err)
			}
			assert.Equal(tt.expectedNewShellCalls, newShellCalls, "newShellCalls = %v, want %v", newShellCalls, tt.expectedNewShellCalls)
		})
	}
}

func TestDnfManager_autoRemove(t *testing.T) {
	assert := assert.New(t)

	tests := []struct {
		name           string
		runErr         error
		wantErr        bool
		wantErrMessage string
	}{
		{
			name:    "No error",
			runErr:  nil,
			wantErr: false,
		},
		{
			name:           "Runtime error",
			runErr:         fmt.Errorf("runtime error"),
			wantErr:        true,
			wantErrMessage: "dnf autoremove failed",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			m := NewDnfManager()

			newShellCalled := false
			old := command.NewShellCommand
			defer func() {
				command.NewShellCommand = old
			}()
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				newShellCalled = true

				assert.Equal("dnf", name, "binary name = %v, want binary dnf", name)
				for _, arg := range m.autoRemoveOpts {
					assert.Contains(args, arg, "args = %v, want contains %v", args, arg)
				}

				mockShellCommand := commandMock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(tt.runErr)
				return mockShellCommand
			}

			err := m.autoRemove()
			if tt.wantErr {
				assert.ErrorContains(err, tt.wantErrMessage, "autoRemove() error = %v, wantErr %v", err, tt.wantErr)
			} else {
				assert.NoError(err, "autoRemove() error = %v, want nil", err)
			}
			assert.True(newShellCalled, "NewShellCommand() was not called")
		})
	}
}
