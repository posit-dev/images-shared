package quarto

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"path"
	commandMock "pti/mocks/pti/system/command"
	"pti/ptitest"
	"pti/system"
	"pti/system/command"
	"pti/system/file"
	"pti/system/syspkg"
	"runtime"
	"testing"

	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

const testTarGz = "test_quarto.tar.gz"

var testdataPath string

func init() {
	_, testPath, _, _ := runtime.Caller(0)
	// The ".." may change depending on you folder structure
	testdataPath = path.Join(path.Dir(testPath), "testdata")
}

func validateQuartoManager(t *testing.T, want *Manager, got *Manager) {
	assert := assert.New(t)
	assert.Equal(want, got)
}

func Test_workbenchInstalled(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	tests := []struct {
		name           string
		setupFs        func(afero.Fs)
		want           bool
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "workbench quarto bin exists",
			setupFs: func(fs afero.Fs) {
				err := fs.MkdirAll(workbenchQuartoPath, 0o755)
				require.NoError(err)
				err = afero.WriteFile(fs, workbenchQuartoBinPath, []byte{}, 0o644)
				require.NoError(err)
			},
			want:    true,
			wantErr: false,
		},
		{
			name:    "workbench does not exist",
			setupFs: func(fs afero.Fs) {},
			want:    false,
			wantErr: false,
		},
		{
			name: "workbench quarto bin not a file",
			setupFs: func(fs afero.Fs) {
				err := fs.MkdirAll(workbenchQuartoBinPath, 0o755)
				require.NoError(err)
			},
			want:    false,
			wantErr: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			file.AppFs = afero.NewMemMapFs()
			t.Cleanup(ptitest.ResetAppFs)

			tt.setupFs(file.AppFs)

			got, err := workbenchInstalled()
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

func Test_NewManager(t *testing.T) {
	require := require.New(t)

	ubuntuSystem := &system.LocalSystem{
		Vendor:         "ubuntu",
		Version:        "22.04",
		Arch:           "amd64",
		PackageManager: syspkg.NewAptManager(),
	}

	tests := []struct {
		name         string
		setupFs      func(afero.Fs) string
		localSys     *system.LocalSystem
		version      string
		useWorkbench bool
		validator    func(*testing.T, *Manager, *Manager)
		want         *Manager
	}{
		{
			name:         "default",
			setupFs:      func(fs afero.Fs) string { return "" },
			localSys:     ubuntuSystem,
			version:      "1.6.39",
			useWorkbench: true,
			validator:    validateQuartoManager,
			want: &Manager{
				LocalSystem:             ubuntuSystem,
				Version:                 "1.6.39",
				InstallationPath:        DefaultInstallPath,
				BinPath:                 defaultBinPath,
				IsWorkbenchInstallation: false,
			},
		},
		{
			name: "workbench default",
			setupFs: func(fs afero.Fs) string {
				err := fs.MkdirAll(workbenchQuartoPath, 0o755)
				require.NoError(err)
				err = afero.WriteFile(fs, workbenchQuartoBinPath, []byte{}, 0o644)
				require.NoError(err)
				return ""
			},
			localSys:     ubuntuSystem,
			version:      "1.6.39",
			useWorkbench: true,
			validator:    validateQuartoManager,
			want: &Manager{
				LocalSystem:             ubuntuSystem,
				Version:                 "1.6.39",
				InstallationPath:        workbenchQuartoPath,
				BinPath:                 workbenchQuartoBinPath,
				IsWorkbenchInstallation: true,
			},
		},
		{
			name: "workbench ignored with useWorkbench false",
			setupFs: func(fs afero.Fs) string {
				err := fs.MkdirAll(workbenchQuartoPath, 0o755)
				require.NoError(err)
				err = afero.WriteFile(fs, workbenchQuartoBinPath, []byte{}, 0o644)
				require.NoError(err)
				return ""
			},
			localSys:     ubuntuSystem,
			version:      "1.6.39",
			useWorkbench: false,
			validator:    validateQuartoManager,
			want: &Manager{
				LocalSystem:             ubuntuSystem,
				Version:                 "1.6.39",
				InstallationPath:        DefaultInstallPath,
				BinPath:                 defaultBinPath,
				IsWorkbenchInstallation: false,
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			file.AppFs = afero.NewMemMapFs()
			t.Cleanup(ptitest.ResetAppFs)

			path := tt.setupFs(file.AppFs)

			got := NewManager(tt.localSys, tt.version, path, tt.useWorkbench)
			tt.validator(t, tt.want, got)
		})
	}
}

func Test_Manager_validate(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	testNew := NewManager(&system.LocalSystem{}, "1.6.39", "", true)

	tests := []struct {
		name           string
		manager        *Manager
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "validate",
			manager: &Manager{
				Version:          "1.6.39",
				InstallationPath: DefaultInstallPath,
			},
			wantErr: false,
		},
		{
			name:    "default NewManager is validate",
			manager: testNew,
			wantErr: false,
		},
		{
			name: "empty version",
			manager: &Manager{
				Version:          "",
				InstallationPath: DefaultInstallPath,
			},
			wantErr:        true,
			wantErrMessage: "quarto version is required",
		},
		{
			name: "empty installation path",
			manager: &Manager{
				Version:          "1.6.39",
				InstallationPath: "",
			},
			wantErr:        true,
			wantErrMessage: "quarto installation path is required",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			file.AppFs = afero.NewMemMapFs()
			t.Cleanup(ptitest.ResetAppFs)

			err := tt.manager.validate()
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
	require := require.New(t)

	tests := []struct {
		name           string
		setupFs        func(afero.Fs)
		manager        *Manager
		want           bool
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "quarto bin exists",
			setupFs: func(fs afero.Fs) {
				err := fs.MkdirAll(DefaultInstallPath, 0o755)
				require.NoError(err)
				err = afero.WriteFile(fs, defaultBinPath, []byte{}, 0o644)
				require.NoError(err)
			},
			manager: &Manager{
				Version:          "1.6.39",
				InstallationPath: DefaultInstallPath,
				BinPath:          defaultBinPath,
			},
			want:    true,
			wantErr: false,
		},
		{
			name:    "quarto bin does not exist",
			setupFs: func(fs afero.Fs) {},
			manager: &Manager{
				Version:          "1.6.39",
				InstallationPath: DefaultInstallPath,
				BinPath:          defaultBinPath,
			},
			want:    false,
			wantErr: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			file.AppFs = afero.NewMemMapFs()
			t.Cleanup(ptitest.ResetAppFs)

			tt.setupFs(file.AppFs)

			got, err := tt.manager.Installed()
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

func Test_getDownloadUrl(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		version        string
		arch           string
		want           string
		wantErr        bool
		wantErrMessage string
	}{
		{
			name:    "validate amd64",
			version: "1.6.39",
			arch:    "amd64",
			want:    fmt.Sprintf(downloadUrl, "1.6.39", "1.6.39", "amd64"),
			wantErr: false,
		},
		{
			name:    "validate arm64",
			version: "1.6.39",
			arch:    "arm64",
			want:    fmt.Sprintf(downloadUrl, "1.6.39", "1.6.39", "arm64"),
			wantErr: false,
		},
		{
			name:           "invalid arch",
			version:        "1.6.39",
			arch:           "i386",
			want:           "",
			wantErr:        true,
			wantErrMessage: "quarto is not supported on detected 'i386' architecture",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := getDownloadUrl(tt.version, tt.arch)
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

func validateTestQuartoInstallation(t *testing.T, path, version string) {
	assert := assert.New(t)
	require := require.New(t)

	isDir, err := file.IsDir(path)
	require.NoError(err)
	require.True(isDir)

	isFile, err := file.IsFile(path + "/bin/quarto")
	assert.NoError(err)
	assert.True(isFile)

	contents, err := afero.ReadFile(file.AppFs, path+"/bin/quarto")
	assert.NoError(err)
	assert.Contains(string(contents), "testbin")

	isFile, err = file.IsFile(path + "/share/version")
	assert.NoError(err)
	assert.True(isFile)

	contents, err = afero.ReadFile(file.AppFs, path+"/share/version")
	assert.NoError(err)
	assert.Contains(string(contents), version)
}

func newServerQuartoTestTarGz(t *testing.T, fs afero.Fs, version, arch string) *httptest.Server {
	require := require.New(t)
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		expectedPath := fmt.Sprintf(
			"/quarto-dev/quarto-cli/releases/download/v%s/quarto-%s-linux-%s.tar.gz",
			version,
			version,
			arch,
		)
		if r.URL.Path != expectedPath {
			t.Errorf("Request URL = %v, want %v", r.URL.Path, expectedPath)
		}

		tarContents, err := afero.ReadFile(fs, "/"+testTarGz)
		require.NoError(err)

		w.WriteHeader(http.StatusOK)
		w.Write(tarContents)
	}))
}

func Test_Manager_Install(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	type expectedCall struct {
		bin            string
		args           []string
		envVars        []string
		inheritEnvVars bool
	}

	ubuntuSystem := &system.LocalSystem{
		Vendor:         "ubuntu",
		Version:        "22.04",
		Arch:           "amd64",
		PackageManager: syspkg.NewAptManager(),
	}
	defaultManager := &Manager{
		LocalSystem:             ubuntuSystem,
		Version:                 "1.6.39",
		InstallationPath:        DefaultInstallPath,
		BinPath:                 defaultBinPath,
		IsWorkbenchInstallation: false,
	}

	tests := []struct {
		name           string
		setupFs        func(afero.Fs)
		srv            func(*testing.T, afero.Fs, string, string) *httptest.Server
		fsValidator    func(*testing.T, string, string)
		manager        *Manager
		force          bool
		expectedCalls  []expectedCall
		wantErr        bool
		wantErrMessage string
	}{
		{
			name:          "install default",
			setupFs:       func(fs afero.Fs) {},
			srv:           newServerQuartoTestTarGz,
			fsValidator:   validateTestQuartoInstallation,
			manager:       defaultManager,
			force:         false,
			expectedCalls: []expectedCall{},
			wantErr:       false,
		},
		{
			name:        "install custom path",
			setupFs:     func(fs afero.Fs) {},
			srv:         newServerQuartoTestTarGz,
			fsValidator: validateTestQuartoInstallation,
			manager: &Manager{
				LocalSystem:             ubuntuSystem,
				Version:                 "1.6.39",
				InstallationPath:        "/tmp/quarto",
				BinPath:                 "/tmp/quarto/bin/quarto",
				IsWorkbenchInstallation: false,
			},
			force:         false,
			expectedCalls: []expectedCall{},
			wantErr:       false,
		},
		{
			name: "no changes installed without force",
			setupFs: func(fs afero.Fs) {
				err := fs.MkdirAll(DefaultInstallPath, 0o755)
				require.NoError(err)
				err = afero.WriteFile(fs, defaultBinPath, []byte("testbin-old"), 0o644)
				require.NoError(err)
			},
			srv: newServerQuartoTestTarGz,
			fsValidator: func(t *testing.T, path string, version string) {
				isDir, err := file.IsDir(path)
				require.NoError(err)
				require.True(isDir)

				isFile, err := file.IsFile(path + "/bin/quarto")
				assert.NoError(err)
				assert.True(isFile)

				contents, err := afero.ReadFile(file.AppFs, path+"/bin/quarto")
				assert.NoError(err)
				assert.Contains(string(contents), "testbin-old")

				isFile, err = file.IsFile(path + "/share/version")
				assert.NoError(err)
				assert.False(isFile)
			},
			manager:       defaultManager,
			force:         false,
			expectedCalls: []expectedCall{},
			wantErr:       false,
		},
		{
			name: "force reinstall",
			setupFs: func(fs afero.Fs) {
				err := fs.MkdirAll(DefaultInstallPath, 0o755)
				require.NoError(err)
				err = afero.WriteFile(fs, defaultBinPath, []byte("testbin"), 0o644)
				require.NoError(err)
			},
			fsValidator: validateTestQuartoInstallation,
			srv:         newServerQuartoTestTarGz,
			manager: &Manager{
				LocalSystem:             ubuntuSystem,
				Version:                 "1.6.39",
				InstallationPath:        DefaultInstallPath,
				BinPath:                 defaultBinPath,
				IsWorkbenchInstallation: false,
			},
			force:         true,
			expectedCalls: []expectedCall{},
			wantErr:       false,
		},
		{
			name: "install dirty path not installable",
			setupFs: func(fs afero.Fs) {
				err := fs.MkdirAll(DefaultInstallPath, 0o755)
				require.NoError(err)
				err = afero.WriteFile(
					fs,
					DefaultInstallPath+"/share/version",
					[]byte("test"),
					0o644,
				)
				require.NoError(err)
				err = afero.WriteFile(
					fs,
					DefaultInstallPath+"/bin/somelibrary",
					[]byte("test"),
					0o644,
				)
				require.NoError(err)
			},
			fsValidator: nil,
			srv:         newServerQuartoTestTarGz,
			manager: &Manager{
				LocalSystem:             ubuntuSystem,
				Version:                 "1.6.39",
				InstallationPath:        DefaultInstallPath,
				BinPath:                 defaultBinPath,
				IsWorkbenchInstallation: false,
			},
			force:          false,
			expectedCalls:  []expectedCall{},
			wantErr:        true,
			wantErrMessage: "installation path '/opt/quarto' is not installable",
		},
		{
			name: "install dirty path force",
			setupFs: func(fs afero.Fs) {
				err := fs.MkdirAll(DefaultInstallPath, 0o755)
				require.NoError(err)
				err = afero.WriteFile(fs, DefaultInstallPath+"testfile", []byte("testbin"), 0o644)
				require.NoError(err)
			},
			fsValidator: validateTestQuartoInstallation,
			srv:         newServerQuartoTestTarGz,
			manager: &Manager{
				LocalSystem:             ubuntuSystem,
				Version:                 "1.6.39",
				InstallationPath:        DefaultInstallPath,
				BinPath:                 defaultBinPath,
				IsWorkbenchInstallation: false,
			},
			force:         true,
			expectedCalls: []expectedCall{},
			wantErr:       false,
		},
		{
			name:    "bad response",
			setupFs: func(fs afero.Fs) {},
			srv: func(t *testing.T, fs afero.Fs, version string, arch string) *httptest.Server {
				return httptest.NewServer(
					http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
						w.WriteHeader(http.StatusInternalServerError)
					}),
				)
			},
			manager:        defaultManager,
			force:          false,
			expectedCalls:  []expectedCall{},
			wantErr:        true,
			wantErrMessage: "quarto 1.6.39 download failed",
		},
		{
			name:    "bad arch",
			setupFs: func(fs afero.Fs) {},
			srv:     newServerQuartoTestTarGz,
			manager: &Manager{
				LocalSystem: &system.LocalSystem{
					Vendor:         "ubuntu",
					Version:        "22.04",
					Arch:           "i386",
					PackageManager: syspkg.NewAptManager(),
				},
				Version:                 "1.6.39",
				InstallationPath:        DefaultInstallPath,
				BinPath:                 defaultBinPath,
				IsWorkbenchInstallation: false,
			},
			force:          false,
			expectedCalls:  []expectedCall{},
			wantErr:        true,
			wantErrMessage: "failed to determine quarto download URL",
		},
		{
			name:    "extract failed",
			setupFs: func(fs afero.Fs) {},
			srv: func(t *testing.T, fs afero.Fs, version string, arch string) *httptest.Server {
				return httptest.NewServer(
					http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
						w.WriteHeader(http.StatusOK)
						w.Write([]byte("not a tar"))
					}),
				)
			},
			manager: &Manager{
				LocalSystem:             ubuntuSystem,
				Version:                 "1.6.39",
				InstallationPath:        DefaultInstallPath,
				BinPath:                 defaultBinPath,
				IsWorkbenchInstallation: false,
			},
			force:          false,
			expectedCalls:  []expectedCall{},
			wantErr:        true,
			wantErrMessage: "unable to extract quarto archive",
		},
		{
			name:    "unable to extract quarto archive",
			setupFs: func(fs afero.Fs) {},
			srv:     newServerQuartoTestTarGz,
			manager: &Manager{
				LocalSystem:             ubuntuSystem,
				Version:                 "1.4.538",
				InstallationPath:        DefaultInstallPath,
				BinPath:                 defaultBinPath,
				IsWorkbenchInstallation: false,
			},
			force:          false,
			expectedCalls:  []expectedCall{},
			wantErr:        true,
			wantErrMessage: "does not exist",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			contents, err := afero.ReadFile(file.AppFs, testdataPath+"/"+testTarGz)
			require.NoError(err)

			file.AppFs = afero.NewMemMapFs()

			tt.setupFs(file.AppFs)
			server := tt.srv(t, file.AppFs, tt.manager.Version, tt.manager.LocalSystem.Arch)

			oldURL := downloadUrl
			downloadUrl = server.URL + "/quarto-dev/quarto-cli/releases/download/v%s/quarto-%s-linux-%s.tar.gz"

			oldShellCommand := command.NewShellCommand

			t.Cleanup(func() {
				command.NewShellCommand = oldShellCommand
				server.Close()
				downloadUrl = oldURL
				ptitest.ResetAppFs()
			})

			err = afero.WriteFile(file.AppFs, "/"+testTarGz, contents, 0o644)
			require.NoError(err)

			newShellCalls := 0
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				mockShellCommand := commandMock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(nil)

				assert.Contains(name, tt.expectedCalls[newShellCalls].bin)
				for _, arg := range tt.expectedCalls[newShellCalls].args {
					assert.Contains(args, arg)
				}
				assert.Equal(tt.expectedCalls[newShellCalls].envVars, envVars)
				assert.Equal(tt.expectedCalls[newShellCalls].inheritEnvVars, inheritEnvVars)

				newShellCalls++
				require.LessOrEqual(newShellCalls, len(tt.expectedCalls))
				return mockShellCommand
			}

			err = tt.manager.Install(tt.force)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)

				tt.fsValidator(t, tt.manager.InstallationPath, tt.manager.Version)
			}
		})
	}
}
