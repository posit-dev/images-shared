package python

import (
	"errors"
	"fmt"
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
	"net/http"
	"net/http/httptest"
	"os"
	"path"
	command_mock "pti/mocks/pti/system/command"
	syspkg_mock "pti/mocks/pti/system/syspkg"
	"pti/system"
	"pti/system/command"
	"pti/system/file"
	"pti/system/syspkg"
	"regexp"
	"runtime"
	"testing"
)

const testVersionsJson = "versions.json"

var testdataPath string

func init() {
	_, testPath, _, _ := runtime.Caller(0)
	// The ".." may change depending on you folder structure
	testdataPath = path.Join(path.Dir(testPath), "testdata")
}

func newServerPythonCdn(t *testing.T, fs afero.Fs) *httptest.Server {
	require := require.New(t)
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		packagePat := regexp.MustCompile("/python/[a-z]+-[0-9]+/pkgs/python-3.[0-9]{1,2}.[0-9]{1,2}(_1_|-1-1.)(amd64|x86_64|arm64).(rpm|deb)")

		if r.URL.Path == "/python/versions.json" {
			versionsJsonData, err := afero.ReadFile(fs, "/"+testVersionsJson)
			require.NoError(err)

			w.WriteHeader(http.StatusOK)
			w.Write(versionsJsonData)
		} else if packagePat.Match([]byte(r.URL.Path)) {
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("200 OK"))
		}

		w.WriteHeader(http.StatusNotFound)
	}))
}

func fakePythonInstallation(t *testing.T, fs afero.Fs, version string) {
	require := require.New(t)

	err := fs.MkdirAll("/opt/python/"+version+"/bin", 0755)
	require.NoError(err)
	_, err = fs.Create("/opt/python/" + version + "/bin/python")
	require.NoError(err)
	_, err = fs.Create("/opt/python/" + version + "/bin/pip")
	require.NoError(err)
}

func Test_NewManager(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	ubuntuSystem := &system.LocalSystem{
		Vendor:         "ubuntu",
		Version:        "22.04",
		Arch:           "amd64",
		PackageManager: syspkg.NewAptManager(),
	}

	tests := []struct {
		name           string
		system         *system.LocalSystem
		version        string
		InstallOptions *InstallOptions
		want           *Manager
		wantErr        bool
		wantErrMessage string
	}{
		{
			name:           "no version",
			system:         ubuntuSystem,
			version:        "",
			InstallOptions: nil,
			want:           nil,
			wantErr:        true,
			wantErrMessage: "python version is required",
		},
		{
			name:           "default",
			system:         ubuntuSystem,
			version:        "3.12.4",
			InstallOptions: nil,
			want: &Manager{
				LocalSystem:      ubuntuSystem,
				Version:          "3.12.4",
				InstallationPath: "/opt/python/3.12.4",
				PythonPath:       "/opt/python/3.12.4/bin/python",
				PipPath:          "/opt/python/3.12.4/bin/pip",
				InstallOptions: &InstallOptions{
					SetDefault: false,
					AddKernel:  false,
					AddToPath:  false,
				},
			},
			wantErr: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := NewManager(tt.system, tt.version, tt.InstallOptions)
			assert.Equal(tt.want, got)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}

func Test_Manager_validVersion(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	tests := []struct {
		name           string
		version        string
		srv            func(*testing.T, afero.Fs) *httptest.Server
		want           bool
		wantErr        bool
		wantErrMessage string
	}{
		{
			name:    "validate",
			srv:     newServerPythonCdn,
			version: "3.12.4",
			want:    true,
			wantErr: false,
		},
		{
			name:    "invalid unsupported",
			srv:     newServerPythonCdn,
			version: "2.7.14",
			want:    false,
			wantErr: false,
		},
		{
			name:    "invalid major.minor",
			srv:     newServerPythonCdn,
			version: "3.12",
			want:    false,
			wantErr: false,
		},
		{
			name:    "invalid major-only",
			srv:     newServerPythonCdn,
			version: "3",
			want:    false,
			wantErr: false,
		},
		{
			name: "bad server response",
			srv: func(t *testing.T, fs afero.Fs) *httptest.Server {
				return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					w.WriteHeader(http.StatusInternalServerError)
				}))
			},
			version:        "3.12.4",
			want:           false,
			wantErr:        true,
			wantErrMessage: "could not fetch python version list",
		},
		{
			name: "bad json parse",
			srv: func(t *testing.T, fs afero.Fs) *httptest.Server {
				return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					w.WriteHeader(http.StatusOK)
					w.Write([]byte("{"))
				}))
			},
			version:        "3.12.4",
			want:           false,
			wantErr:        true,
			wantErrMessage: "error occurred while parsing support python versions",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fs := afero.NewMemMapFs()
			contents, err := afero.ReadFile(file.AppFs, testdataPath+"/"+testVersionsJson)
			require.NoError(err)
			err = afero.WriteFile(fs, "/"+testVersionsJson, contents, 0644)

			srv := tt.srv(t, fs)
			defer srv.Close()

			m := &Manager{Version: tt.version}

			versionsJsonUrl = srv.URL + "/python/versions.json"

			got, err := m.validVersion()
			assert.Equal(tt.want, got)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}

func Test_Manager_validate(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	tests := []struct {
		name           string
		manager        *Manager
		srv            func(*testing.T, afero.Fs) *httptest.Server
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "valid",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
					Arch:    "amd64",
				},
				InstallationPath: fmt.Sprintf(binPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			srv:     newServerPythonCdn,
			wantErr: false,
		},
		{
			name: "invalid version",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
					Arch:    "amd64",
				},
				InstallationPath: fmt.Sprintf(binPathTpl, "3.12.4"),
				Version:          "3.12",
			},
			srv:            newServerPythonCdn,
			wantErr:        true,
			wantErrMessage: "python version '3.12' is not supported",
		},
		{
			name: "no installation path",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
					Arch:    "amd64",
				},
				Version: "3.12.4",
			},
			srv:            newServerPythonCdn,
			wantErr:        true,
			wantErrMessage: "python installation path is required",
		},
		{
			name: "bad vendor",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "opensuse",
					Version: "13.2",
					Arch:    "amd64",
				},
				InstallationPath: fmt.Sprintf(binPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			srv:            newServerPythonCdn,
			wantErr:        true,
			wantErrMessage: "python is currently not supported for opensuse 13.2",
		},
		{
			name: "no arch",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
				},
				InstallationPath: fmt.Sprintf(binPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			srv:            newServerPythonCdn,
			wantErr:        true,
			wantErrMessage: "unable to detect system architecture",
		},
		{
			name: "bad arch",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
					Arch:    "arm64",
				},
				InstallationPath: fmt.Sprintf(binPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			srv:            newServerPythonCdn,
			wantErr:        true,
			wantErrMessage: "python is currently not supported on arm64",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fs := afero.NewMemMapFs()
			contents, err := afero.ReadFile(file.AppFs, testdataPath+"/"+testVersionsJson)
			require.NoError(err)
			err = afero.WriteFile(fs, "/"+testVersionsJson, contents, 0644)

			srv := tt.srv(t, fs)
			defer srv.Close()

			versionsJsonUrl = srv.URL + "/python/versions.json"

			err = tt.manager.validate()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}

func Test_Manager_downloadUrl(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		manager        *Manager
		want           string
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "ubuntu amd64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
					Arch:    "amd64",
				},
				Version: "3.12.4",
			},
			want: "https://cdn.posit.co/python/ubuntu-2204/pkgs/python-3.12.4_1_amd64.deb",
		},
		{
			name: "ubuntu arm64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
					Arch:    "arm64",
				},
				Version: "3.12.4",
			},
			want: "https://cdn.posit.co/python/ubuntu-2204/pkgs/python-3.12.4_1_arm64.deb",
		},
		{
			name: "debian amd64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "debian",
					Version: "12",
					Arch:    "amd64",
				},
				Version: "3.12.4",
			},
			want: "https://cdn.posit.co/python/debian-12/pkgs/python-3.12.4_1_amd64.deb",
		},
		{
			name: "debian arm64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "debian",
					Version: "12",
					Arch:    "arm64",
				},
				Version: "3.12.4",
			},
			want: "https://cdn.posit.co/python/debian-12/pkgs/python-3.12.4_1_arm64.deb",
		},
		{
			name: "rockylinux amd64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "rockylinux",
					Version: "8",
					Arch:    "amd64",
				},
				Version: "3.12.4",
			},
			want: "https://cdn.posit.co/python/centos-8/pkgs/python-3.12.4-1-1.x86_64.rpm",
		},
		{
			name: "rockylinux arm64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "rockylinux",
					Version: "8",
					Arch:    "arm64",
				},
				Version: "3.12.4",
			},
			want: "https://cdn.posit.co/python/centos-8/pkgs/python-3.12.4-1-1.arm64.rpm",
		},
		{
			name: "almalinux amd64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "almalinux",
					Version: "9",
					Arch:    "amd64",
				},
				Version: "3.12.4",
			},
			want: "https://cdn.posit.co/python/rhel-9/pkgs/python-3.12.4-1-1.x86_64.rpm",
		},
		{
			name: "almalinux arm64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "almalinux",
					Version: "9",
					Arch:    "arm64",
				},
				Version: "3.12.4",
			},
			want: "https://cdn.posit.co/python/rhel-9/pkgs/python-3.12.4-1-1.arm64.rpm",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := tt.manager.downloadUrl()
			assert.Equal(tt.want, got)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}

func Test_Manager_Install(t *testing.T) {
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
	pipCleanCall := expectedCall{
		name:           "/opt/python/3.12.4/bin/python",
		args:           []string{"-m", "pip", "cache", "purge"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	ipykernelInstallCall := expectedCall{
		name:           "/opt/python/3.12.4/bin/python",
		args:           []string{"-m", "pip", "install", "ipykernel", "--upgrade"},
		envVars:        nil,
		inheritEnvVars: true,
	}

	tests := []struct {
		name           string
		manager        *Manager
		srv            func(*testing.T, afero.Fs) *httptest.Server
		setupFs        func(*testing.T, string) afero.Fs
		setupPm        func(*Manager, afero.Fs)
		validateFs     func(*testing.T, afero.Fs)
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
				InstallOptions: &InstallOptions{
					SetDefault: false,
					AddKernel:  false,
					AddToPath:  false,
				},
			},
			srv: newServerPythonCdn,
			setupFs: func(t *testing.T, version string) afero.Fs {
				fs := afero.NewMemMapFs()
				return fs
			},
			setupPm: func(manager *Manager, fs afero.Fs) {
				mockPm := syspkg_mock.NewMockSystemPackageManager(t)
				mockPm.EXPECT().GetPackageExtension().Return(".deb")
				mockPm.EXPECT().Install(mock.AnythingOfType("*syspkg.PackageList")).RunAndReturn(
					func(list *syspkg.PackageList) error {
						assert.Contains(list.LocalPackages[0], "python.deb")
						fakePythonInstallation(t, fs, "3.12.4")
						return nil
					},
				)
				manager.LocalSystem.PackageManager = mockPm
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isFile, err := file.IsFile("/opt/python/3.12.4/bin/python")
				require.NoError(err)
				assert.True(isFile)

				isFile, err = file.IsFile("/opt/python/3.12.4/bin/pip")
				require.NoError(err)
				assert.True(isFile)
			},
			expectedCalls: []expectedCall{
				ensurePipCall,
				pipInstallUpgradeCall,
				setuptoolsInstallUpgradeCall,
				pipCleanCall,
			},
			wantErr: false,
		},
		{
			name: "installed",
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
				InstallOptions: &InstallOptions{
					SetDefault: false,
					AddKernel:  false,
					AddToPath:  false,
				},
			},
			srv: newServerPythonCdn,
			setupFs: func(t *testing.T, s string) afero.Fs {
				fs := afero.NewMemMapFs()
				fakePythonInstallation(t, fs, "3.12.4")
				return fs
			},
			setupPm: func(manager *Manager, fs afero.Fs) {
				mockPm := syspkg_mock.NewMockSystemPackageManager(t)
				manager.LocalSystem.PackageManager = mockPm
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isFile, err := file.IsFile("/opt/python/3.12.4/bin/python")
				require.NoError(err)
				assert.True(isFile)

				isFile, err = file.IsFile("/opt/python/3.12.4/bin/pip")
				require.NoError(err)
				assert.True(isFile)
			},
			expectedCalls: []expectedCall{},
			wantErr:       false,
		},
		{
			name: "add kernel",
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
				InstallOptions: &InstallOptions{
					SetDefault: false,
					AddKernel:  true,
					AddToPath:  false,
				},
			},
			srv: newServerPythonCdn,
			setupFs: func(t *testing.T, s string) afero.Fs {
				fs := afero.NewMemMapFs()
				return fs
			},
			setupPm: func(manager *Manager, fs afero.Fs) {
				mockPm := syspkg_mock.NewMockSystemPackageManager(t)
				mockPm.EXPECT().GetPackageExtension().Return(".deb")
				mockPm.EXPECT().Install(mock.AnythingOfType("*syspkg.PackageList")).RunAndReturn(
					func(list *syspkg.PackageList) error {
						assert.Contains(list.LocalPackages[0], "python.deb")
						fakePythonInstallation(t, fs, "3.12.4")
						return nil
					},
				)
				manager.LocalSystem.PackageManager = mockPm
			},
			expectedCalls: []expectedCall{
				ensurePipCall,
				pipInstallUpgradeCall,
				setuptoolsInstallUpgradeCall,
				pipCleanCall,
				ipykernelInstallCall,
				pipCleanCall,
				{
					name:           "/opt/python/3.12.4/bin/python",
					args:           []string{"-m", "ipykernel", "install", "--name", "py3.12.4", "--display-name", "Python 3.12.4"},
					envVars:        nil,
					inheritEnvVars: true,
				},
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isFile, err := file.IsFile("/opt/python/3.12.4/bin/python")
				require.NoError(err)
				assert.True(isFile)

				isFile, err = file.IsFile("/opt/python/3.12.4/bin/pip")
				require.NoError(err)
				assert.True(isFile)
			},
			wantErr: false,
		},
		{
			name: "set default",
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
				InstallOptions: &InstallOptions{
					SetDefault: true,
					AddKernel:  false,
					AddToPath:  false,
				},
			},
			srv: newServerPythonCdn,
			setupFs: func(t *testing.T, version string) afero.Fs {
				fs := afero.NewBasePathFs(afero.NewOsFs(), os.TempDir()+"/setdefault")
				err := fs.MkdirAll("/opt", 0755)
				require.NoError(err)
				err = fs.MkdirAll("/tmp", 0755)
				require.NoError(err)

				return fs
			},
			setupPm: func(manager *Manager, fs afero.Fs) {
				mockPm := syspkg_mock.NewMockSystemPackageManager(t)
				mockPm.EXPECT().GetPackageExtension().Return(".deb")
				mockPm.EXPECT().Install(mock.AnythingOfType("*syspkg.PackageList")).RunAndReturn(
					func(list *syspkg.PackageList) error {
						assert.Contains(list.LocalPackages[0], "python.deb")
						fakePythonInstallation(t, fs, "3.12.4")
						return nil
					},
				)
				manager.LocalSystem.PackageManager = mockPm
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isFile, err := file.IsFile("/opt/python/3.12.4/bin/python")
				require.NoError(err)
				assert.True(isFile)

				isFile, err = file.IsFile("/opt/python/3.12.4/bin/pip")
				require.NoError(err)
				assert.True(isFile)

				isSymlink, err := file.IsSymlink("/opt/python/default")
				require.NoError(err)
				assert.True(isSymlink)

				osFs := afero.NewOsFs()
				err = osFs.RemoveAll(os.TempDir() + "/setdefault")
				require.NoError(err)
			},
			expectedCalls: []expectedCall{
				ensurePipCall,
				pipInstallUpgradeCall,
				setuptoolsInstallUpgradeCall,
				pipCleanCall,
			},
			wantErr: false,
		},
		{
			name: "add to path",
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
				InstallOptions: &InstallOptions{
					SetDefault: false,
					AddKernel:  false,
					AddToPath:  true,
				},
			},
			srv: newServerPythonCdn,
			setupFs: func(t *testing.T, version string) afero.Fs {
				fs := afero.NewBasePathFs(afero.NewOsFs(), os.TempDir()+"/addpath")
				err := fs.MkdirAll("/usr/local/bin", 0755)
				require.NoError(err)
				err = fs.MkdirAll("/opt", 0755)
				require.NoError(err)
				err = fs.MkdirAll("/tmp", 0755)
				require.NoError(err)

				return fs
			},
			setupPm: func(manager *Manager, fs afero.Fs) {
				mockPm := syspkg_mock.NewMockSystemPackageManager(t)
				mockPm.EXPECT().GetPackageExtension().Return(".deb")
				mockPm.EXPECT().Install(mock.AnythingOfType("*syspkg.PackageList")).RunAndReturn(
					func(list *syspkg.PackageList) error {
						assert.Contains(list.LocalPackages[0], "python.deb")
						fakePythonInstallation(t, fs, "3.12.4")
						return nil
					},
				)
				manager.LocalSystem.PackageManager = mockPm
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isFile, err := file.IsFile("/opt/python/3.12.4/bin/python")
				require.NoError(err)
				assert.True(isFile)

				isFile, err = file.IsFile("/opt/python/3.12.4/bin/pip")
				require.NoError(err)
				assert.True(isFile)

				isSymlink, err := file.IsSymlink("/usr/local/bin/python3.12.4")
				require.NoError(err)
				assert.True(isSymlink)

				isSymlink, err = file.IsSymlink("/usr/local/bin/pip3.12.4")
				require.NoError(err)
				assert.True(isSymlink)

				osFs := afero.NewOsFs()
				err = osFs.RemoveAll(os.TempDir() + "/addpath")
				require.NoError(err)
			},
			expectedCalls: []expectedCall{
				ensurePipCall,
				pipInstallUpgradeCall,
				setuptoolsInstallUpgradeCall,
				pipCleanCall,
			},
			wantErr: false,
		},
		{
			name: "download error",
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
				InstallOptions: &InstallOptions{
					SetDefault: false,
					AddKernel:  false,
					AddToPath:  false,
				},
			},
			srv: func(t *testing.T, fs afero.Fs) *httptest.Server {
				return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					if r.URL.Path == "/python/versions.json" {
						versionsJsonData, err := afero.ReadFile(fs, "/"+testVersionsJson)
						require.NoError(err)

						w.WriteHeader(http.StatusOK)
						w.Write(versionsJsonData)
					}

					w.WriteHeader(http.StatusInternalServerError)
				}))
			},
			setupFs: func(t *testing.T, version string) afero.Fs {
				fs := afero.NewMemMapFs()
				return fs
			},
			setupPm: func(manager *Manager, fs afero.Fs) {
				mockPm := syspkg_mock.NewMockSystemPackageManager(t)
				mockPm.EXPECT().GetPackageExtension().Return(".deb")
				manager.LocalSystem.PackageManager = mockPm
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isFile, err := file.IsFile("/opt/python/3.12.4/bin/python")
				require.NoError(err)
				assert.False(isFile)

				isFile, err = file.IsFile("/opt/python/3.12.4/bin/pip")
				require.NoError(err)
				assert.False(isFile)
			},
			expectedCalls: []expectedCall{
				ensurePipCall,
				pipInstallUpgradeCall,
				setuptoolsInstallUpgradeCall,
				pipCleanCall,
			},
			wantErr:        true,
			wantErrMessage: "failed to download python 3.12.4 package",
		},
		{
			name: "install error",
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
				InstallOptions: &InstallOptions{
					SetDefault: false,
					AddKernel:  false,
					AddToPath:  false,
				},
			},
			srv: newServerPythonCdn,
			setupFs: func(t *testing.T, version string) afero.Fs {
				fs := afero.NewMemMapFs()
				return fs
			},
			setupPm: func(manager *Manager, fs afero.Fs) {
				mockPm := syspkg_mock.NewMockSystemPackageManager(t)
				mockPm.EXPECT().GetPackageExtension().Return(".deb")
				mockPm.EXPECT().Install(mock.AnythingOfType("*syspkg.PackageList")).Return(errors.New("install error"))
				manager.LocalSystem.PackageManager = mockPm
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isFile, err := file.IsFile("/opt/python/3.12.4/bin/python")
				require.NoError(err)
				assert.False(isFile)

				isFile, err = file.IsFile("/opt/python/3.12.4/bin/pip")
				require.NoError(err)
				assert.False(isFile)
			},
			expectedCalls: []expectedCall{
				ensurePipCall,
				pipInstallUpgradeCall,
				setuptoolsInstallUpgradeCall,
				pipCleanCall,
			},
			wantErr:        true,
			wantErrMessage: "failed to install python 3.12.4",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := file.AppFs
			file.AppFs = tt.setupFs(t, "3.12.4")
			defer func() {
				file.AppFs = oldFs
			}()

			contents, err := afero.ReadFile(oldFs, testdataPath+"/"+testVersionsJson)
			require.NoError(err)
			err = afero.WriteFile(file.AppFs, "/"+testVersionsJson, contents, 0644)

			srv := tt.srv(t, file.AppFs)
			defer srv.Close()

			versionsJsonUrl = srv.URL + "/python/versions.json"
			downloadUrl = srv.URL + "/python/%s/pkgs/%s"

			if tt.setupPm != nil {
				tt.setupPm(tt.manager, file.AppFs)
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

				mockShellCommand := command_mock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(nil)
				return mockShellCommand
			}
			defer func() {
				command.NewShellCommand = oldNSC
			}()

			err = tt.manager.Install()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
				tt.validateFs(t, file.AppFs)
			}
		})
	}
}

func Test_Manager_makeDefault(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tmpDir := os.TempDir() + "/makedefault"

	tests := []struct {
		name           string
		manager        *Manager
		setupFs        func(*testing.T, afero.Fs, string)
		validateFs     func(*testing.T, afero.Fs)
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "3.12.4"),
				PythonPath:       fmt.Sprintf(binPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				err := fs.MkdirAll("/opt/python", 0755)
				require.NoError(err)
				fakePythonInstallation(t, fs, "3.12.4")
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isSymlink, err := file.IsSymlink("/opt/python/default")
				require.NoError(err)
				assert.True(isSymlink)

				exists, err := file.IsPathExist("/opt/python/default/bin/python")
				require.NoError(err)
				assert.True(exists)

				exists, err = file.IsPathExist("/opt/python/default/bin/pip")
				require.NoError(err)
				assert.True(exists)
			},
			wantErr: false,
		},
		{
			name: "not installed",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "3.12.4"),
				PythonPath:       fmt.Sprintf(binPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				err := fs.MkdirAll("/opt/python", 0755)
				require.NoError(err)
			},
			validateFs:     nil,
			wantErr:        true,
			wantErrMessage: "python 3.12.4 is not installed",
		},
		{
			name: "remove existing default directory",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "3.12.4"),
				PythonPath:       fmt.Sprintf(binPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				err := fs.MkdirAll("/opt/python/default", 0755)
				require.NoError(err)
				_, err = fs.Create("/opt/python/default/testfile")
				require.NoError(err)
				fakePythonInstallation(t, fs, "3.12.4")
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isSymlink, err := file.IsSymlink("/opt/python/default")
				require.NoError(err)
				assert.True(isSymlink)

				exists, err := file.IsPathExist("/opt/python/default/bin/python")
				require.NoError(err)
				assert.True(exists)

				exists, err = file.IsPathExist("/opt/python/default/bin/pip")
				require.NoError(err)
				assert.True(exists)

				exists, err = file.IsPathExist("/opt/python/default/testfile")
				require.NoError(err)
				assert.False(exists)
			},
		},
		{
			name: "remove existing default symlink",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "3.12.4"),
				PythonPath:       fmt.Sprintf(binPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				fakePythonInstallation(t, fs, "3.11.7")
				fakePythonInstallation(t, fs, "3.12.4")
				sFs, ok := fs.(*afero.BasePathFs)
				require.True(ok)
				err := sFs.SymlinkIfPossible("/opt/python/3.11.7", "/opt/python/default")
				require.NoError(err)
				rl, err := sFs.ReadlinkIfPossible("/opt/python/default")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/python/3.11.7", rl)
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isSymlink, err := file.IsSymlink("/opt/python/default")
				require.NoError(err)
				assert.True(isSymlink)

				exists, err := file.IsPathExist("/opt/python/default/bin/python")
				require.NoError(err)
				assert.True(exists)

				exists, err = file.IsPathExist("/opt/python/default/bin/pip")
				require.NoError(err)
				assert.True(exists)

				sFs, ok := fs.(*afero.BasePathFs)
				require.True(ok)
				rl, err := sFs.ReadlinkIfPossible("/opt/python/default")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/python/3.12.4", rl)
			},
			wantErr: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := file.AppFs
			file.AppFs = afero.NewBasePathFs(afero.NewOsFs(), tmpDir)
			defer func() {
				file.AppFs = oldFs
				file.AppFs.RemoveAll(tmpDir)
			}()

			tt.setupFs(t, file.AppFs, "3.12.4")

			err := tt.manager.makeDefault()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
				if tt.validateFs != nil {
					tt.validateFs(t, file.AppFs)
				}
			}
		})
	}
}

func Test_Manager_addToPath(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tmpDir := os.TempDir() + "/addtopath"

	tests := []struct {
		name           string
		manager        *Manager
		setupFs        func(*testing.T, afero.Fs, string)
		validateFs     func(*testing.T, afero.Fs)
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "3.12.4"),
				PythonPath:       fmt.Sprintf(binPathTpl, "3.12.4"),
				PipPath:          fmt.Sprintf(pipPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				err := fs.MkdirAll("/usr/local/bin", 0755)
				require.NoError(err)
				fakePythonInstallation(t, fs, "3.12.4")
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isSymlink, err := file.IsSymlink("/usr/local/bin/python3.12.4")
				require.NoError(err)
				assert.True(isSymlink)

				rl, err := os.Readlink(tmpDir + "/usr/local/bin/python3.12.4")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/python/3.12.4/bin/python", rl)

				isSymlink, err = file.IsSymlink("/usr/local/bin/pip3.12.4")
				require.NoError(err)
				assert.True(isSymlink)

				rl, err = os.Readlink(tmpDir + "/usr/local/bin/pip3.12.4")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/python/3.12.4/bin/pip", rl)
			},
			wantErr: false,
		},
		{
			name: "not installed",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "3.12.4"),
				PythonPath:       fmt.Sprintf(binPathTpl, "3.12.4"),
				PipPath:          fmt.Sprintf(pipPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				err := fs.MkdirAll("/usr/local/bin", 0755)
				require.NoError(err)
			},
			validateFs:     nil,
			wantErr:        true,
			wantErrMessage: "python 3.12.4 is not installed",
		},
		{
			name: "symlinks replaced",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "3.12.4"),
				PythonPath:       fmt.Sprintf(binPathTpl, "3.12.4"),
				PipPath:          fmt.Sprintf(pipPathTpl, "3.12.4"),
				Version:          "3.12.4",
			},
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				fakePythonInstallation(t, fs, "3.12.3")
				fakePythonInstallation(t, fs, "3.12.4")
				err := fs.MkdirAll("/usr/local/bin", 0755)
				require.NoError(err)

				sFs, ok := fs.(*afero.BasePathFs)
				require.True(ok)
				err = sFs.SymlinkIfPossible("/opt/python/3.12.3/bin/python", "/usr/local/bin/python3.12.4")
				require.NoError(err)
				rl, err := sFs.ReadlinkIfPossible("/usr/local/bin/python3.12.4")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/python/3.12.3/bin/python", rl)

				err = sFs.SymlinkIfPossible("/opt/python/3.12.3/bin/pip", "/usr/local/bin/pip3.12.4")
				require.NoError(err)
				rl, err = sFs.ReadlinkIfPossible("/usr/local/bin/pip3.12.4")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/python/3.12.3/bin/pip", rl)
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isSymlink, err := file.IsSymlink("/usr/local/bin/python3.12.4")
				require.NoError(err)
				assert.True(isSymlink)

				rl, err := os.Readlink(tmpDir + "/usr/local/bin/python3.12.4")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/python/3.12.4/bin/python", rl)

				isSymlink, err = file.IsSymlink("/usr/local/bin/pip3.12.4")
				require.NoError(err)
				assert.True(isSymlink)

				rl, err = os.Readlink(tmpDir + "/usr/local/bin/pip3.12.4")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/python/3.12.4/bin/pip", rl)
			},
			wantErr: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := file.AppFs
			file.AppFs = afero.NewBasePathFs(afero.NewOsFs(), tmpDir)
			defer func() {
				file.AppFs = oldFs
				file.AppFs.RemoveAll(tmpDir)
			}()

			tt.setupFs(t, file.AppFs, "3.12.4")

			err := tt.manager.addToPath()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
				if tt.validateFs != nil {
					tt.validateFs(t, file.AppFs)
				}
			}
		})
	}
}
