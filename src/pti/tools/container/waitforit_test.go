package container

import (
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"pti/ptitest"
	"pti/system/file"
	"testing"
)

func Test_WaitForItManager_Installed(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	type args struct {
		installPath string
	}
	tests := []struct {
		name           string
		args           args
		setupFs        func(fs afero.Fs)
		want           bool
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "file exists",
			args: args{
				installPath: "/wait-for-it",
			},
			setupFs: func(fs afero.Fs) {
				err := afero.WriteFile(fs, "/wait-for-it", []byte("test"), 0755)
				require.NoError(err)
			},
			want:    true,
			wantErr: false,
		},
		{
			name: "path is directory",
			args: args{
				installPath: "/wait-for-it",
			},
			setupFs: func(fs afero.Fs) {
				err := fs.Mkdir("/wait-for-it", 0755)
				require.NoError(err)
			},
			want:           false,
			wantErr:        true,
			wantErrMessage: "'/wait-for-it' is not a file",
		},
		{
			name: "path does not exist",
			args: args{
				installPath: "/wait-for-it",
			},
			setupFs: func(fs afero.Fs) {},
			want:    false,
			wantErr: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			file.AppFs = afero.NewMemMapFs()
			t.Cleanup(ptitest.ResetAppFs)

			tt.setupFs(file.AppFs)

			w := NewWaitForItManager(tt.args.installPath)
			installed, err := w.Installed()
			if tt.wantErr {
				require.Error(err)
			} else {
				require.NoError(err)
				assert.Equal(tt.want, installed, "WaitForItManager.Installed() = %v, want %v", installed, tt.want)
			}
		})
	}
}

func Test_WaitForItManager_Install(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	const successResponse = "200 OK"

	type args struct {
		installPath string
	}
	tests := []struct {
		name           string
		args           args
		setupFs        func(fs afero.Fs)
		srv            *httptest.Server
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "already installed",
			args: args{
				installPath: "/wait-for-it",
			},
			setupFs: func(fs afero.Fs) {
				err := afero.WriteFile(fs, "/wait-for-it", []byte(successResponse), 0755)
				require.NoError(err)
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/wait-for-it/wait-for-it.sh" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/platform/wait-for-it/wait-for-it.sh")
				}
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr:        true,
			wantErrMessage: "wait-for-it is already installed",
		},
		{
			name: "success",
			args: args{
				installPath: "/wait-for-it",
			},
			setupFs: func(fs afero.Fs) {},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/wait-for-it/wait-for-it.sh" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/platform/wait-for-it/wait-for-it.sh")
				}
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr: false,
		},
		{
			name: "success with no installPath given",
			args: args{
				installPath: "",
			},
			setupFs: func(fs afero.Fs) {},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/wait-for-it/wait-for-it.sh" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/platform/wait-for-it/wait-for-it.sh")
				}
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr: false,
		},
		{
			name: "fail on bad response",
			args: args{
				installPath: "",
			},
			setupFs: func(fs afero.Fs) {},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/wait-for-it/wait-for-it.sh" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/platform/wait-for-it/wait-for-it.sh")
				}
				w.WriteHeader(http.StatusNotFound)
			})),
			wantErr:        true,
			wantErrMessage: "wait-for-it download failed",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldUrl := waitForItDownloadUrl
			file.AppFs = afero.NewMemMapFs()
			t.Cleanup(func() {
				waitForItDownloadUrl = oldUrl
				tt.srv.Close()
				ptitest.ResetAppFs()
			})

			tt.setupFs(file.AppFs)

			waitForItDownloadUrl = tt.srv.URL + "/platform/wait-for-it/wait-for-it.sh"

			w := NewWaitForItManager(tt.args.installPath)
			err := w.Install()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)

				installPath := tt.args.installPath
				if installPath == "" {
					installPath = "/usr/local/bin/wait-for-it"
				}

				exists, err := afero.Exists(file.AppFs, installPath)
				require.NoError(err, "File.Exists() error = %v", err)
				assert.True(exists, "%s file does not exist", installPath)

				contents, err := afero.ReadFile(file.AppFs, installPath)
				require.NoError(err, "ReadFile() error = %v", err)
				assert.Equal(successResponse, string(contents), "File contents = %v, want %v", string(contents), successResponse)

				fileInfo, err := file.AppFs.Stat(installPath)
				require.NoError(err, "Stat() error = %v", err)
				assert.True(fileInfo.Mode().IsRegular(), "File is not a regular file")
				assert.Equal(fs.FileMode(0755), fileInfo.Mode().Perm(), "File mode = %v, want %v", fileInfo.Mode(), 0755)
			}
		})
	}
}

func Test_WaitForItManager_Update(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	const successResponse = "200 OK"

	type args struct {
		arch        string
		installPath string
	}
	tests := []struct {
		name           string
		args           args
		srv            *httptest.Server
		setupFs        func(fs afero.Fs)
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "not installed",
			args: args{
				arch:        "amd64",
				installPath: "/wait-for-it",
			},
			setupFs: func(fs afero.Fs) {},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/wait-for-it/wait-for-it.sh" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/platform/wait-for-it/wait-for-it.sh")
				}
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr: false,
		},
		{
			name: "reinstall",
			args: args{
				arch:        "amd64",
				installPath: "/wait-for-it",
			},
			setupFs: func(fs afero.Fs) {
				err := afero.WriteFile(fs, "/wait-for-it", []byte("old wait-for-it"), 0755)
				require.NoError(err)
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/wait-for-it/wait-for-it.sh" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/platform/wait-for-it/wait-for-it.sh")
				}
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr: false,
		},
		{
			name: "path is directory",
			args: args{
				arch:        "amd64",
				installPath: "/wait-for-it",
			},
			setupFs: func(fs afero.Fs) {
				err := fs.MkdirAll("/wait-for-it", 0755)
				require.NoError(err)
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/wait-for-it/wait-for-it.sh" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/platform/wait-for-it/wait-for-it.sh")
				}
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr:        true,
			wantErrMessage: "'/wait-for-it' is not a file",
		},
		{
			name: "fail on bad response",
			args: args{
				arch:        "amd64",
				installPath: "/wait-for-it",
			},
			setupFs: func(fs afero.Fs) {},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/wait-for-it/wait-for-it.sh" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/platform/wait-for-it/wait-for-it.sh")
				}
				w.WriteHeader(http.StatusNotFound)
			})),
			wantErr:        true,
			wantErrMessage: "wait-for-it download failed",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldUrl := waitForItDownloadUrl
			file.AppFs = afero.NewMemMapFs()
			t.Cleanup(func() {
				waitForItDownloadUrl = oldUrl
				tt.srv.Close()
				ptitest.ResetAppFs()
			})

			tt.setupFs(file.AppFs)

			waitForItDownloadUrl = tt.srv.URL + "/platform/wait-for-it/wait-for-it.sh"

			w := NewWaitForItManager(tt.args.installPath)

			err := w.Update()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)

				exists, err := afero.Exists(file.AppFs, tt.args.installPath)
				require.NoError(err, "File.Exists() error = %v", err)
				assert.True(exists, "%s file does not exist", tt.args.installPath)

				contents, err := afero.ReadFile(file.AppFs, tt.args.installPath)
				require.NoError(err, "ReadFile() error = %v", err)
				assert.Equal(successResponse, string(contents), "File contents = %v, want %v", string(contents), successResponse)

				fileInfo, err := file.AppFs.Stat(tt.args.installPath)
				require.NoError(err, "Stat() error = %v", err)
				assert.True(fileInfo.Mode().IsRegular(), "File is not a regular file")
				assert.Equal(fs.FileMode(0755), fileInfo.Mode().Perm(), "File mode = %v, want %v", fileInfo.Mode(), 0755)
			}
		})
	}
}

func Test_WaitForIt_Remove(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	type fields struct {
		InstallPath string
	}
	tests := []struct {
		name           string
		fields         fields
		setupFs        func(fs afero.Fs)
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			fields: fields{
				InstallPath: "/wait-for-it",
			},
			setupFs: func(fs afero.Fs) {
				_, err := fs.Create("/wait-for-it")
				require.NoError(err)
			},
			wantErr: false,
		},
		{
			name: "fail on directory",
			fields: fields{
				InstallPath: "/wait-for-it",
			},
			setupFs: func(fs afero.Fs) {
				_ = fs.MkdirAll("/wait-for-it", 0755)
			},
			wantErr:        true,
			wantErrMessage: "'/wait-for-it' is not a file",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			file.AppFs = afero.NewMemMapFs()
			t.Cleanup(ptitest.ResetAppFs)

			tt.setupFs(file.AppFs)

			m := &TiniManager{
				InstallPath: tt.fields.InstallPath,
			}

			err := m.Remove()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)

				exists, err := afero.Exists(file.AppFs, tt.fields.InstallPath)
				require.NoError(err, "File.Exists() error = %v", err)
				assert.False(exists, "%s file still exists", tt.fields.InstallPath)
			}
		})
	}
}
