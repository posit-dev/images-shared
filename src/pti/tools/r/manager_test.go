package r

import (
	"fmt"
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
	"net/http"
	"net/http/httptest"
	"os"
	"path"
	syspkg_mock "pti/mocks/pti/system/syspkg"
	"pti/ptitest"
	"pti/system"
	"pti/system/file"
	"pti/system/syspkg"
	"regexp"
	"runtime"
	"strings"
	"testing"
)

const testVersionsJson = "versions.json"

var testdataPath string

func init() {
	_, testPath, _, _ := runtime.Caller(0)
	// The ".." may change depending on you folder structure
	testdataPath = path.Join(path.Dir(testPath), "testdata")
}

func newServerRCdn(t *testing.T, fs afero.Fs) *httptest.Server {
	require := require.New(t)
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		packagePat := regexp.MustCompile("/r/[a-z]+-[0-9]+/pkgs/r-[3-5].[0-9].[0-9](_1_|-1-1.)(amd64|x86_64|arm64).(rpm|deb)")

		if r.URL.Path == "/r/versions.json" {
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

func fakeRInstallation(t *testing.T, fs afero.Fs, version string) {
	require := require.New(t)

	err := fs.MkdirAll("/opt/R/"+version+"/bin", 0755)
	require.NoError(err)
	_, err = fs.Create("/opt/R/" + version + "/bin/R")
	require.NoError(err)
	_, err = fs.Create("/opt/R/" + version + "/bin/Rscript")
	require.NoError(err)
}

func Test_NewManager(t *testing.T) {
	assert := assert.New(t)

	ubuntuSystem := system.LocalSystem{
		Vendor:  "ubuntu",
		Version: "22.04",
		Arch:    "amd64",
	}

	tests := []struct {
		name    string
		version string
		want    *Manager
	}{
		{
			name:    "default",
			version: "4.4.2",
			want: &Manager{
				LocalSystem:      &ubuntuSystem,
				Version:          "4.4.2",
				InstallationPath: "/opt/R/4.4.2",
				RPath:            "/opt/R/4.4.2/bin/R",
				RscriptPath:      "/opt/R/4.4.2/bin/Rscript",
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := NewManager(&ubuntuSystem, tt.version)
			assert.Equal(tt.want, got)
		})
	}
}

func Test_validVersion(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

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
			srv:     newServerRCdn,
			version: "4.4.2",
			want:    true,
			wantErr: false,
		},
		{
			name:    "invalid unsupported",
			srv:     newServerRCdn,
			version: "2.1.0",
			want:    false,
			wantErr: false,
		},
		{
			name:    "invalid major.minor",
			srv:     newServerRCdn,
			version: "4.2",
			want:    false,
			wantErr: false,
		},
		{
			name:    "invalid major-only",
			srv:     newServerRCdn,
			version: "4",
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
			version:        "4.4.2",
			want:           false,
			wantErr:        true,
			wantErrMessage: "could not fetch r version list with status code 500",
		},
		{
			name: "bad json parse",
			srv: func(t *testing.T, fs afero.Fs) *httptest.Server {
				return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					w.WriteHeader(http.StatusOK)
					w.Write([]byte("{"))
				}))
			},
			version:        "4.4.2",
			want:           false,
			wantErr:        true,
			wantErrMessage: "error occurred while parsing supported r versions",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fs := afero.NewMemMapFs()
			contents, err := afero.ReadFile(file.AppFs, testdataPath+"/"+testVersionsJson)
			require.NoError(err)
			err = afero.WriteFile(fs, "/"+testVersionsJson, contents, 0644)

			srv := tt.srv(t, fs)
			t.Cleanup(srv.Close)

			m := &Manager{Version: tt.version}

			versionsJsonUrl = srv.URL + "/r/versions.json"

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
				InstallationPath: fmt.Sprintf(binPathTpl, "4.4.2"),
				Version:          "4.4.2",
			},
			srv:     newServerRCdn,
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
				InstallationPath: fmt.Sprintf(binPathTpl, "4.4.2"),
				Version:          "4.2",
			},
			srv:            newServerRCdn,
			wantErr:        true,
			wantErrMessage: "r version '4.2' is not supported",
		},
		{
			name: "no installation path",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
					Arch:    "amd64",
				},
				Version: "4.4.2",
			},
			srv:            newServerRCdn,
			wantErr:        true,
			wantErrMessage: "r installation path is required",
		},
		{
			name: "bad vendor",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "opensuse",
					Version: "13.2",
					Arch:    "amd64",
				},
				InstallationPath: fmt.Sprintf(binPathTpl, "4.4.2"),
				Version:          "4.4.2",
			},
			srv:            newServerRCdn,
			wantErr:        true,
			wantErrMessage: "r is currently not supported for opensuse 13.2",
		},
		{
			name: "no arch",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
				},
				InstallationPath: fmt.Sprintf(binPathTpl, "4.4.2"),
				Version:          "4.4.2",
			},
			srv:            newServerRCdn,
			wantErr:        true,
			wantErrMessage: "unable to detect system architecture",
		},
		{
			name: "bad arch",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
					Arch:    "i386",
				},
				InstallationPath: fmt.Sprintf(binPathTpl, "4.4.2"),
				Version:          "4.4.2",
			},
			srv:            newServerRCdn,
			wantErr:        true,
			wantErrMessage: "r is currently not supported on i386",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fs := afero.NewMemMapFs()
			contents, err := afero.ReadFile(file.AppFs, testdataPath+"/"+testVersionsJson)
			require.NoError(err)
			err = afero.WriteFile(fs, "/"+testVersionsJson, contents, 0644)

			srv := tt.srv(t, fs)
			t.Cleanup(srv.Close)

			versionsJsonUrl = srv.URL + "/r/versions.json"

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
				Version: "4.4.2",
			},
			want: "https://cdn.posit.co/r/ubuntu-2204/pkgs/r-4.4.2_1_amd64.deb",
		},
		{
			name: "ubuntu arm64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "ubuntu",
					Version: "22.04",
					Arch:    "arm64",
				},
				Version: "4.4.2",
			},
			want: "https://cdn.posit.co/r/ubuntu-2204/pkgs/r-4.4.2_1_arm64.deb",
		},
		{
			name: "debian amd64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "debian",
					Version: "12",
					Arch:    "amd64",
				},
				Version: "4.4.2",
			},
			want: "https://cdn.posit.co/r/debian-12/pkgs/r-4.4.2_1_amd64.deb",
		},
		{
			name: "debian arm64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "debian",
					Version: "12",
					Arch:    "arm64",
				},
				Version: "4.4.2",
			},
			want: "https://cdn.posit.co/r/debian-12/pkgs/r-4.4.2_1_arm64.deb",
		},
		{
			name: "rockylinux amd64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "rockylinux",
					Version: "8",
					Arch:    "amd64",
				},
				Version: "4.4.2",
			},
			want: "https://cdn.posit.co/r/centos-8/pkgs/R-4.4.2-1-1.x86_64.rpm",
		},
		{
			name: "rockylinux arm64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "rockylinux",
					Version: "8",
					Arch:    "arm64",
				},
				Version: "4.4.2",
			},
			want: "https://cdn.posit.co/r/centos-8/pkgs/R-4.4.2-1-1.arm64.rpm",
		},
		{
			name: "almalinux amd64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "almalinux",
					Version: "9",
					Arch:    "amd64",
				},
				Version: "4.4.2",
			},
			want: "https://cdn.posit.co/r/rhel-9/pkgs/R-4.4.2-1-1.x86_64.rpm",
		},
		{
			name: "almalinux arm64",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:  "almalinux",
					Version: "9",
					Arch:    "arm64",
				},
				Version: "4.4.2",
			},
			want: "https://cdn.posit.co/r/rhel-9/pkgs/R-4.4.2-1-1.arm64.rpm",
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

func Test_Manager_Installed(t *testing.T) {
	assert := assert.New(t)

	tests := []struct {
		name    string
		manager *Manager
		setupFs func(*testing.T, afero.Fs, string)
		want    bool
	}{
		{
			name: "installed",
			manager: &Manager{
				Version:          "4.4.2",
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
			},
			setupFs: fakeRInstallation,
			want:    true,
		},
		{
			name: "not installed",
			manager: &Manager{
				Version:          "4.4.2",
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
			},
			setupFs: nil,
			want:    false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			file.AppFs = afero.NewMemMapFs()
			t.Cleanup(ptitest.ResetAppFs)

			if tt.setupFs != nil {
				tt.setupFs(t, file.AppFs, tt.manager.Version)
			}

			got, err := tt.manager.Installed()
			assert.Equal(tt.want, got)
			assert.NoError(err)
		})
	}
}

func Test_Manager_Install(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		manager        *Manager
		setupFs        func(*testing.T, afero.Fs, string)
		srv            func(*testing.T, afero.Fs) *httptest.Server
		wantDownload   bool
		wantInstall    bool
		installErr     error
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "install",
			manager: &Manager{
				LocalSystem:      ptitest.NewUbuntuSystem(),
				Version:          "4.4.2",
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
			},
			setupFs:      nil,
			srv:          newServerRCdn,
			wantDownload: true,
			wantInstall:  true,
			installErr:   nil,
			wantErr:      false,
		},
		{
			name: "already installed",
			manager: &Manager{
				LocalSystem:      ptitest.NewUbuntuSystem(),
				Version:          "4.4.2",
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
			},
			setupFs:      fakeRInstallation,
			srv:          newServerRCdn,
			wantDownload: false,
			wantInstall:  false,
			installErr:   nil,
			wantErr:      false,
		},
		{
			name: "invalid version",
			manager: &Manager{
				LocalSystem:      ptitest.NewUbuntuSystem(),
				Version:          "2.1.3",
				InstallationPath: fmt.Sprintf(installPathTpl, "2.1.3"),
				RPath:            fmt.Sprintf(binPathTpl, "2.1.3"),
			},
			setupFs:        nil,
			srv:            newServerRCdn,
			wantDownload:   false,
			wantInstall:    false,
			installErr:     nil,
			wantErr:        true,
			wantErrMessage: "r version '2.1.3' is not supported",
		},
		{
			name: "bad download url",
			manager: &Manager{
				LocalSystem:      ptitest.NewUbuntuSystem(),
				Version:          "4.4.2",
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
			},
			setupFs: nil,
			srv: func(t *testing.T, fs afero.Fs) *httptest.Server {
				return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					if r.URL.Path == "/r/versions.json" {
						versionsJsonData, err := afero.ReadFile(fs, "/"+testVersionsJson)
						require.NoError(err)

						w.WriteHeader(http.StatusOK)
						w.Write(versionsJsonData)
					} else {
						w.WriteHeader(http.StatusNotFound)
					}
				}))
			},
			wantDownload:   true,
			wantInstall:    false,
			installErr:     nil,
			wantErr:        true,
			wantErrMessage: "failed to download r 4.4.2 package",
		},
		{
			name: "install error",
			manager: &Manager{
				LocalSystem:      ptitest.NewUbuntuSystem(),
				Version:          "4.4.2",
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
			},
			setupFs:        nil,
			srv:            newServerRCdn,
			wantDownload:   true,
			wantInstall:    true,
			installErr:     fmt.Errorf("install error"),
			wantErr:        true,
			wantErrMessage: "failed to install r 4.4.2",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			contents, err := afero.ReadFile(file.AppFs, testdataPath+"/"+testVersionsJson)
			require.NoError(err)

			file.AppFs = afero.NewMemMapFs()

			srv := tt.srv(t, file.AppFs)
			oldJsonUrl := versionsJsonUrl
			versionsJsonUrl = srv.URL + "/r/versions.json"
			oldDownloadUrl := downloadUrl
			downloadUrl = srv.URL + "/r/%s/pkgs/%s"

			t.Cleanup(func() {
				ptitest.ResetAppFs()
				versionsJsonUrl = oldJsonUrl
				downloadUrl = oldDownloadUrl
				srv.Close()
			})

			err = afero.WriteFile(file.AppFs, "/"+testVersionsJson, contents, 0644)

			if tt.setupFs != nil {
				tt.setupFs(t, file.AppFs, tt.manager.Version)
			}

			mockPm := syspkg_mock.NewMockSystemPackageManager(t)
			if tt.wantDownload {
				mockPm.EXPECT().GetPackageExtension().RunAndReturn(func() string {
					switch tt.manager.LocalSystem.Vendor {
					case "ubuntu":
						return ".deb"
					case "rockylinux":
						return ".rpm"
					default:
						t.Errorf("unsupported vendor: %s", tt.manager.LocalSystem.Vendor)
						return ""
					}
				})
			}
			if tt.wantInstall {
				mockPm.EXPECT().Update().Return(nil)
				mockPm.EXPECT().Install(mock.AnythingOfType("*syspkg.PackageList")).RunAndReturn(func(list *syspkg.PackageList) error {
					switch tt.manager.LocalSystem.Vendor {
					case "ubuntu":
						assert.Contains(list.LocalPackages[0], "r.deb")
					case "rockylinux":
						assert.Contains(list.LocalPackages[0], "r.rpm")
					default:
						t.Errorf("unsupported vendor: %s", tt.manager.LocalSystem.Vendor)
					}
					fakeRInstallation(t, file.AppFs, "4.4.2")
					return tt.installErr
				})
				mockPm.EXPECT().Clean().Return(nil)
			}
			tt.manager.LocalSystem.PackageManager = mockPm

			err = tt.manager.Install()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}

func Test_Manager_makeDefault(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tmpDir := os.TempDir()
	if !strings.HasSuffix(tmpDir, "/") {
		tmpDir += "/"
	}
	tmpDir += "r_makedefault"

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
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
				Version:          "4.4.2",
			},
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				err := fs.MkdirAll("/opt/R", 0755)
				require.NoError(err)
				fakeRInstallation(t, fs, "4.4.2")
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isSymlink, err := file.IsSymlink("/opt/R/default")
				require.NoError(err)
				assert.True(isSymlink)

				exists, err := file.IsPathExist("/opt/R/default/bin/R")
				require.NoError(err)
				assert.True(exists)

				exists, err = file.IsPathExist("/opt/R/default/bin/Rscript")
				require.NoError(err)
				assert.True(exists)
			},
			wantErr: false,
		},
		{
			name: "not installed",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
				Version:          "4.4.2",
			},
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				err := fs.MkdirAll("/opt/R", 0755)
				require.NoError(err)
			},
			validateFs:     nil,
			wantErr:        true,
			wantErrMessage: "r 4.4.2 is not installed",
		},
		{
			name: "remove existing default directory",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
				Version:          "4.4.2",
			},
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				err := fs.MkdirAll("/opt/R/default", 0755)
				require.NoError(err)
				_, err = fs.Create("/opt/R/default/testfile")
				require.NoError(err)
				fakeRInstallation(t, fs, "4.4.2")
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isSymlink, err := file.IsSymlink("/opt/R/default")
				require.NoError(err)
				assert.True(isSymlink)

				exists, err := file.IsPathExist("/opt/R/default/bin/R")
				require.NoError(err)
				assert.True(exists)

				exists, err = file.IsPathExist("/opt/R/default/bin/Rscript")
				require.NoError(err)
				assert.True(exists)

				exists, err = file.IsPathExist("/opt/R/default/testfile")
				require.NoError(err)
				assert.False(exists)
			},
		},
		{
			name: "remove existing default symlink",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
				Version:          "4.4.2",
			},
			setupFs: func(t *testing.T, fs afero.Fs, s string) {
				fakeRInstallation(t, fs, "4.2.3")
				fakeRInstallation(t, fs, "4.4.2")
				sFs, ok := fs.(*afero.BasePathFs)
				require.True(ok)
				err := sFs.SymlinkIfPossible("/opt/R/4.2.3", "/opt/R/default")
				require.NoError(err)
				rl, err := sFs.ReadlinkIfPossible("/opt/R/default")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/R/4.2.3", rl)
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isSymlink, err := file.IsSymlink("/opt/R/default")
				require.NoError(err)
				assert.True(isSymlink)

				exists, err := file.IsPathExist("/opt/R/default/bin/R")
				require.NoError(err)
				assert.True(exists)

				exists, err = file.IsPathExist("/opt/R/default/bin/Rscript")
				require.NoError(err)
				assert.True(exists)

				sFs, ok := fs.(*afero.BasePathFs)
				require.True(ok)
				rl, err := sFs.ReadlinkIfPossible("/opt/R/default")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/R/4.4.2", rl)
			},
			wantErr: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			file.AppFs = afero.NewBasePathFs(afero.NewOsFs(), tmpDir)
			t.Cleanup(func() {
				ptitest.ResetAppFs()
				file.AppFs.RemoveAll(tmpDir)
			})

			tt.setupFs(t, file.AppFs, "4.4.2")

			err := tt.manager.MakeDefault()
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

	tmpDir := os.TempDir()
	if !strings.HasSuffix(tmpDir, "/") {
		tmpDir += "/"
	}
	tmpDir += "r_addtopath"

	tests := []struct {
		name           string
		manager        *Manager
		setupFs        func(*testing.T, afero.Fs)
		validateFs     func(*testing.T, afero.Fs)
		appendVersion  bool
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
				RscriptPath:      fmt.Sprintf(rScriptBinPathTpl, "4.4.2"),
				Version:          "4.4.2",
			},
			setupFs: func(t *testing.T, fs afero.Fs) {
				err := fs.MkdirAll("/usr/local/bin", 0755)
				require.NoError(err)
				fakeRInstallation(t, fs, "4.4.2")
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isSymlink, err := file.IsSymlink("/usr/local/bin/R4.4.2")
				require.NoError(err)
				assert.True(isSymlink)

				rl, err := os.Readlink(tmpDir + "/usr/local/bin/R4.4.2")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/R/4.4.2/bin/R", rl)

				isSymlink, err = file.IsSymlink("/usr/local/bin/Rscript4.4.2")
				require.NoError(err)
				assert.True(isSymlink)

				rl, err = os.Readlink(tmpDir + "/usr/local/bin/Rscript4.4.2")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/R/4.4.2/bin/Rscript", rl)
			},
			appendVersion: true,
			wantErr:       false,
		},
		{
			name: "success no append version",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
				RscriptPath:      fmt.Sprintf(rScriptBinPathTpl, "4.4.2"),
				Version:          "4.4.2",
			},
			setupFs: func(t *testing.T, fs afero.Fs) {
				err := fs.MkdirAll("/usr/local/bin", 0755)
				require.NoError(err)
				fakeRInstallation(t, fs, "4.4.2")
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isSymlink, err := file.IsSymlink("/usr/local/bin/R")
				require.NoError(err)
				assert.True(isSymlink)

				rl, err := os.Readlink(tmpDir + "/usr/local/bin/R")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/R/4.4.2/bin/R", rl)

				isSymlink, err = file.IsSymlink("/usr/local/bin/Rscript")
				require.NoError(err)
				assert.True(isSymlink)

				rl, err = os.Readlink(tmpDir + "/usr/local/bin/Rscript")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/R/4.4.2/bin/Rscript", rl)
			},
			appendVersion: false,
			wantErr:       false,
		},
		{
			name: "not installed",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
				RscriptPath:      fmt.Sprintf(rScriptBinPathTpl, "4.4.2"),
				Version:          "4.4.2",
			},
			setupFs: func(t *testing.T, fs afero.Fs) {
				err := fs.MkdirAll("/usr/local/bin", 0755)
				require.NoError(err)
			},
			validateFs:     nil,
			appendVersion:  true,
			wantErr:        true,
			wantErrMessage: "r 4.4.2 is not installed",
		},
		{
			name: "symlinks replaced",
			manager: &Manager{
				InstallationPath: fmt.Sprintf(installPathTpl, "4.4.2"),
				RPath:            fmt.Sprintf(binPathTpl, "4.4.2"),
				RscriptPath:      fmt.Sprintf(rScriptBinPathTpl, "4.4.2"),
				Version:          "3.12.4",
			},
			setupFs: func(t *testing.T, fs afero.Fs) {
				fakeRInstallation(t, fs, "4.2.3")
				fakeRInstallation(t, fs, "4.4.2")
				err := fs.MkdirAll("/usr/local/bin", 0755)
				require.NoError(err)

				sFs, ok := fs.(*afero.BasePathFs)
				require.True(ok)
				err = sFs.SymlinkIfPossible("/opt/R/4.2.3/bin/R", "/usr/local/bin/R")
				require.NoError(err)
				rl, err := sFs.ReadlinkIfPossible("/usr/local/bin/R")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/R/4.2.3/bin/R", rl)

				err = sFs.SymlinkIfPossible("/opt/R/4.2.3/bin/Rscript", "/usr/local/bin/Rscript")
				require.NoError(err)
				rl, err = sFs.ReadlinkIfPossible("/usr/local/bin/Rscript")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/R/4.2.3/bin/Rscript", rl)
			},
			validateFs: func(t *testing.T, fs afero.Fs) {
				isSymlink, err := file.IsSymlink("/usr/local/bin/R")
				require.NoError(err)
				assert.True(isSymlink)

				rl, err := os.Readlink(tmpDir + "/usr/local/bin/R")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/R/4.4.2/bin/R", rl)

				isSymlink, err = file.IsSymlink("/usr/local/bin/Rscript")
				require.NoError(err)
				assert.True(isSymlink)

				rl, err = os.Readlink(tmpDir + "/usr/local/bin/Rscript")
				require.NoError(err)
				assert.Equal(tmpDir+"/opt/R/4.4.2/bin/Rscript", rl)
			},
			appendVersion: false,
			wantErr:       false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			file.AppFs = afero.NewBasePathFs(afero.NewOsFs(), tmpDir)
			t.Cleanup(func() {
				ptitest.ResetAppFs()
				file.AppFs.RemoveAll(tmpDir)
			})

			tt.setupFs(t, file.AppFs)

			err := tt.manager.AddToPath(tt.appendVersion)
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

func Test_Manager_Remove(t *testing.T) {
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
				LocalSystem: &system.LocalSystem{},
				Version:     "4.4.2",
			},
			runErr:  nil,
			wantErr: false,
		},
		{
			name: "failed to remove",
			manager: &Manager{
				LocalSystem: &system.LocalSystem{},
				Version:     "4.4.2",
			},
			runErr:         fmt.Errorf("remove error"),
			wantErr:        true,
			wantErrMessage: "failed to remove r 4.4.2",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mockPm := syspkg_mock.NewMockSystemPackageManager(t)
			mockPm.EXPECT().Remove(mock.AnythingOfType("*syspkg.PackageList")).RunAndReturn(func(list *syspkg.PackageList) error {
				assert.Contains(list.Packages, "r-4.4.2")
				return tt.runErr
			})
			tt.manager.LocalSystem.PackageManager = mockPm

			err := tt.manager.Remove()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
		})
	}
}
