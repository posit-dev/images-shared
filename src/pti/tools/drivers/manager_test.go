package drivers

import (
	"fmt"
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
	"net/http"
	"net/http/httptest"
	syspkgMock "pti/mocks/pti/system/syspkg"
	"pti/system"
	"pti/system/file"
	"pti/system/syspkg"
	"regexp"
	"testing"
)

func Test_getProDriversUrl(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		l              *system.LocalSystem
		driversVersion string
		want           string
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "ubuntu amd64",
			l: &system.LocalSystem{
				Vendor:  "ubuntu",
				Version: "22.04",
				Arch:    "amd64",
			},
			driversVersion: "2024.03.0",
			want:           "https://cdn.posit.co/drivers/7C152C12/installer/rstudio-drivers_2024.03.0_amd64.deb",
			wantErr:        false,
		},
		{
			name: "ubuntu arm64",
			l: &system.LocalSystem{
				Vendor:  "ubuntu",
				Version: "22.04",
				Arch:    "arm64",
			},
			driversVersion: "2024.03.0",
			want:           "https://cdn.posit.co/drivers/7C152C12/installer/rstudio-drivers_2024.03.0_arm64.deb",
			wantErr:        false,
		},
		{
			name: "rockylinux amd64",
			l: &system.LocalSystem{
				Vendor:  "rockylinux",
				Version: "8",
				Arch:    "amd64",
			},
			driversVersion: "2024.03.0",
			want:           "https://cdn.posit.co/drivers/7C152C12/installer/rstudio-drivers-2024.03.0-1.el.x86_64.rpm",
			wantErr:        false,
		},
		{
			name: "rockylinux arm64",
			l: &system.LocalSystem{
				Vendor:  "rockylinux",
				Version: "8",
				Arch:    "arm64",
			},
			driversVersion: "2024.03.0",
			want:           "https://cdn.posit.co/drivers/7C152C12/installer/rstudio-drivers-2024.03.0-1.el.arm64.rpm",
			wantErr:        false,
		},
		{
			name: "unsupported",
			l: &system.LocalSystem{
				Vendor:  "unsupported",
				Version: "1.2.3",
				Arch:    "amd64",
			},
			driversVersion: "2024.03.0",
			want:           "",
			wantErr:        true,
			wantErrMessage: "unsupported OS: unsupported 1.2.3",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := getProDriversUrl(tt.l, tt.driversVersion)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
				assert.Equal(tt.want, got)
			}
		})
	}
}

func Test_getProDriversDependencies(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		l              *system.LocalSystem
		want           []string
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "ubuntu",
			l: &system.LocalSystem{
				Vendor:  "ubuntu",
				Version: "22.04",
				Arch:    "amd64",
			},
			want: []string{"unixodbc", "unixodbc-dev"},
		},
		{
			name: "rockylinux",
			l: &system.LocalSystem{
				Vendor:  "rockylinux",
				Version: "8",
				Arch:    "amd64",
			},
			want: []string{"unixODBC", "unixODBC-devel"},
		},
		{
			name: "unsupported",
			l: &system.LocalSystem{
				Vendor:  "unsupported",
				Version: "1.2.3",
				Arch:    "amd64",
			},
			want:           nil,
			wantErr:        true,
			wantErrMessage: "unsupported OS: unsupported 1.2.3",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := getProDriversDependencies(tt.l)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
				assert.Equal(tt.want, got)
			}
		})
	}
}

func Test_InstallProDrivers(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	const successResponse = "200 OK"
	urlPat := regexp.MustCompile("/drivers/7C152C12/installer/.*")

	// Define systems to test against
	debDependencies := &syspkg.PackageList{Packages: []string{"unixodbc", "unixodbc-dev"}}
	debSystem := system.LocalSystem{
		Vendor:  "ubuntu",
		Version: "22.04",
		Arch:    "amd64",
	}
	rhelDependencies := &syspkg.PackageList{Packages: []string{"unixODBC", "unixODBC-devel"}}
	rhelSystem := system.LocalSystem{
		Vendor:  "rockylinux",
		Version: "8",
		Arch:    "amd64",
	}

	type args struct {
		l              *system.LocalSystem
		driversVersion string
	}
	tests := []struct {
		name           string
		args           args
		pmSetup        func(t *testing.T, localSystem *system.LocalSystem)
		srv            *httptest.Server
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success ubuntu",
			args: args{
				l:              &debSystem,
				driversVersion: "2024.03.0",
			},
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().GetPackageExtension().Return(".deb")
				mockPackageManager.EXPECT().
					Install(mock.AnythingOfType("*syspkg.PackageList")).
					RunAndReturn(func(list *syspkg.PackageList) error {
						if len(list.Packages) == 2 {
							assert.Equal(debDependencies.Packages, list.Packages)
						} else if len(list.LocalPackages) == 1 {
							assert.Contains(list.LocalPackages[0], "drivers.deb")
						} else {
							t.Errorf("unexpected package list arguments: %v", list)
						}
						return nil
					})
				mockPackageManager.EXPECT().Clean().Return(nil)
				localSystem.PackageManager = mockPackageManager
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				assert.Regexp(urlPat, r.URL.Path)
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr: false,
		},
		{
			name: "success rockylinux",
			args: args{
				l:              &rhelSystem,
				driversVersion: "2024.03.0",
			},
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().GetPackageExtension().Return(".rpm")
				mockPackageManager.EXPECT().
					Install(mock.AnythingOfType("*syspkg.PackageList")).
					RunAndReturn(func(list *syspkg.PackageList) error {
						if len(list.Packages) == 2 && len(list.LocalPackages) == 1 {
							assert.Equal(rhelDependencies.Packages, list.Packages)
							assert.Contains(list.LocalPackages[0], "drivers.rpm")
						} else {
							t.Errorf("unexpected package list arguments: %v", list)
						}
						return nil
					})
				mockPackageManager.EXPECT().Clean().Return(nil)
				localSystem.PackageManager = mockPackageManager
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				assert.Regexp(urlPat, r.URL.Path)
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr: false,
		},
		{
			name: "unsupported OS",
			args: args{
				l:              &system.LocalSystem{Vendor: "unsupported", Version: "1.2.3", Arch: "amd64"},
				driversVersion: "2024.03.0",
			},
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				localSystem.PackageManager = mockPackageManager
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				assert.Regexp(urlPat, r.URL.Path)
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr:        true,
			wantErrMessage: "failed to determine Posit Pro Drivers download URL",
		},
		{
			name: "failed download",
			args: args{
				l:              &debSystem,
				driversVersion: "2024.03.0",
			},
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().GetPackageExtension().Return(".deb")
				localSystem.PackageManager = mockPackageManager
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				assert.Regexp(urlPat, r.URL.Path)
				w.WriteHeader(http.StatusNotFound)
			})),
			wantErr:        true,
			wantErrMessage: "failed to download pro drivers package from",
		},
		{
			name: "failed install",
			args: args{
				l:              &debSystem,
				driversVersion: "2024.03.0",
			},
			pmSetup: func(t *testing.T, localSystem *system.LocalSystem) {
				mockPackageManager := syspkgMock.NewMockSystemPackageManager(t)
				mockPackageManager.EXPECT().GetPackageExtension().Return(".deb")
				mockPackageManager.EXPECT().Install(mock.AnythingOfType("*syspkg.PackageList")).Return(fmt.Errorf("install error"))
				localSystem.PackageManager = mockPackageManager
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				assert.Regexp(urlPat, r.URL.Path)
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr:        true,
			wantErrMessage: "failed to install pro drivers package",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := file.AppFs
			file.AppFs = afero.NewMemMapFs()
			defer func() {
				file.AppFs = oldFs
			}()

			fh, err := file.AppFs.Create(odbcInstIniPath)
			require.NoError(err)
			_, err = fh.WriteString("original definition")
			require.NoError(err)
			fh, err = file.AppFs.Create(positDriversOdbcInstIniPath)
			require.NoError(err)
			_, err = fh.WriteString("new definition")
			require.NoError(err)

			oldUrl := proDriversUrl
			proDriversUrl = tt.srv.URL + "/drivers/7C152C12/installer/%s"
			defer func() {
				proDriversUrl = oldUrl
				tt.srv.Close()
			}()

			tt.pmSetup(t, tt.args.l)

			m := NewProDriversManager(tt.args.l, tt.args.driversVersion, true)

			err = m.Install()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)

				exists, err := afero.Exists(file.AppFs, odbcInstIniPath)
				require.NoError(err)
				assert.True(exists)

				exists, err = afero.Exists(file.AppFs, positDriversOdbcInstIniPath)
				require.NoError(err)
				assert.True(exists)

				exists, err = afero.Exists(file.AppFs, odbcInstIniPath+".bak")
				require.NoError(err)
				assert.True(exists)

				// Check that the odbcinst.ini file was updated
				contents, err := afero.ReadFile(file.AppFs, odbcInstIniPath)
				require.NoError(err)
				assert.Equal("new definition", string(contents))

				// Check that the odbcinst.ini.bak file was saved
				contents, err = afero.ReadFile(file.AppFs, odbcInstIniPath+".bak")
				require.NoError(err)
				assert.Equal("original definition", string(contents))
			}
		})
	}
}

func Test_CopyProDriversOdbcInstIni(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		setupFs        func(fs afero.Fs)
		validateFs     func(fs afero.Fs)
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			setupFs: func(fs afero.Fs) {
				fh, err := fs.Create(odbcInstIniPath)
				require.NoError(err)
				_, err = fh.WriteString("original definition")
				require.NoError(err)

				fh, err = fs.Create(positDriversOdbcInstIniPath)
				require.NoError(err)
				_, err = fh.WriteString("new definition")
				require.NoError(err)
			},
			validateFs: func(fs afero.Fs) {
				exists, err := afero.Exists(file.AppFs, odbcInstIniPath)
				require.NoError(err)
				assert.True(exists)

				exists, err = afero.Exists(file.AppFs, positDriversOdbcInstIniPath)
				require.NoError(err)
				assert.True(exists)

				exists, err = afero.Exists(file.AppFs, odbcInstIniPath+".bak")
				require.NoError(err)
				assert.True(exists)

				// Check that the odbcinst.ini file was updated
				contents, err := afero.ReadFile(file.AppFs, odbcInstIniPath)
				require.NoError(err)
				assert.Equal("new definition", string(contents))

				// Check that the odbcinst.ini.bak file was saved
				contents, err = afero.ReadFile(file.AppFs, odbcInstIniPath+".bak")
				require.NoError(err)
				assert.Equal("original definition", string(contents))
			},
			wantErr: false,
		},
		{
			name: "success no backup odbcinst.ini",
			setupFs: func(fs afero.Fs) {
				fh, err := fs.Create(positDriversOdbcInstIniPath)
				require.NoError(err)
				_, err = fh.WriteString("new definition")
				require.NoError(err)
			},
			validateFs: func(fs afero.Fs) {
				exists, err := afero.Exists(file.AppFs, odbcInstIniPath)
				require.NoError(err)
				assert.True(exists)

				exists, err = afero.Exists(file.AppFs, positDriversOdbcInstIniPath)
				require.NoError(err)
				assert.True(exists)

				exists, err = afero.Exists(file.AppFs, odbcInstIniPath+".bak")
				require.NoError(err)
				assert.False(exists)

				// Check that the odbcinst.ini file was updated
				contents, err := afero.ReadFile(file.AppFs, odbcInstIniPath)
				require.NoError(err)
				assert.Equal("new definition", string(contents))
			},
			wantErr: false,
		},
		{
			name: "failed no odbcinst.ini.sample",
			setupFs: func(fs afero.Fs) {
				fh, err := fs.Create(odbcInstIniPath)
				require.NoError(err)
				_, err = fh.WriteString("original definition")
				require.NoError(err)
			},
			validateFs: func(fs afero.Fs) {
				exists, err := afero.Exists(file.AppFs, odbcInstIniPath)
				require.NoError(err)
				assert.True(exists)

				exists, err = afero.Exists(file.AppFs, odbcInstIniPath+".bak")
				require.NoError(err)
				assert.False(exists)

				// Check that the odbcinst.ini file was updated
				contents, err := afero.ReadFile(file.AppFs, odbcInstIniPath)
				require.NoError(err)
				assert.Equal("original definition", string(contents))
			},
			wantErr:        true,
			wantErrMessage: "odbcinst.ini.sample does not exist",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := file.AppFs
			file.AppFs = afero.NewMemMapFs()
			defer func() {
				file.AppFs = oldFs
			}()

			tt.setupFs(file.AppFs)

			m := NewProDriversManager(&system.LocalSystem{}, "", false)

			err := m.CopyProDriversOdbcInstIni()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}

			tt.validateFs(file.AppFs)
		})
	}
}
