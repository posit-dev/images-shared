package container

import (
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"pti/system"
	"pti/system/file"
	"testing"
)

func Test_getTiniDownloadUrl(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	type args struct {
		version string
		arch    string
	}
	tests := []struct {
		name           string
		args           args
		want           string
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success with alternate version",
			args: args{
				version: "0.18.0",
				arch:    "amd64",
			},
			want:    "https://cdn.posit.co/platform/tini/v0.18.0/tini-amd64",
			wantErr: false,
		},
		{
			name: "success with default version",
			args: args{
				version: "",
				arch:    "amd64",
			},
			want:    "https://cdn.posit.co/platform/tini/v0.19.0/tini-amd64",
			wantErr: false,
		},
		{
			name: "fail with no arch given",
			args: args{
				version: "0.19.0",
				arch:    "",
			},
			want:           "",
			wantErr:        true,
			wantErrMessage: "no system architecture provided for tini download",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := getTiniDownloadUrl(tt.args.version, tt.args.arch)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}
			assert.Equal(tt.want, got)
		})
	}
}

func Test_InstallTini(t *testing.T) {
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
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			args: args{
				arch:        "amd64",
				installPath: "/tini",
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/tini/v0.19.0/tini-amd64" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/success.txt")
				}
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr: false,
		},
		{
			name: "fail with no arch given",
			args: args{
				arch:        "",
				installPath: "",
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/tini/v0.19.0/tini-amd64" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/success.txt")
				}
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr:        true,
			wantErrMessage: "unable to determine tini download url",
		},
		{
			name: "success with no installPath given",
			args: args{
				arch:        "amd64",
				installPath: "",
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/tini/v0.19.0/tini-amd64" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/success.txt")
				}
				w.WriteHeader(http.StatusOK)
				w.Write([]byte(successResponse))
			})),
			wantErr: false,
		},
		{
			name: "fail on bad response",
			args: args{
				arch:        "amd64",
				installPath: "",
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/tini/v0.19.0/tini-amd64" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/success.txt")
				}
				w.WriteHeader(http.StatusNotFound)
			})),
			wantErr:        true,
			wantErrMessage: "tini download failed",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := file.AppFs
			file.AppFs = afero.NewMemMapFs()
			defer func() {
				file.AppFs = oldFs
			}()

			oldUrl := tiniDownloadUrl
			tiniDownloadUrl = tt.srv.URL + "/platform/tini/v%s/tini-%s"
			defer func() {
				tiniDownloadUrl = oldUrl
				tt.srv.Close()
			}()

			err := InstallTini(&system.LocalSystem{Arch: tt.args.arch}, tt.args.installPath)
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)

				installPath := tt.args.installPath
				if installPath == "" {
					installPath = "/usr/local/bin/tini"
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
