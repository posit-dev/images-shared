package container

import (
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"pti/system/file"
	"testing"
)

func Test_InstallWaitForIt(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	const successResponse = "200 OK"

	type args struct {
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
				installPath: "/wait-for-it",
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/wait-for-it/wait-for-it.sh" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/success.txt")
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
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/wait-for-it/wait-for-it.sh" {
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
				installPath: "",
			},
			srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/platform/wait-for-it/wait-for-it.sh" {
					t.Errorf("Request URL = %v, want %v", r.URL.Path, "/success.txt")
				}
				w.WriteHeader(http.StatusNotFound)
			})),
			wantErr:        true,
			wantErrMessage: "wait-for-it download failed",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := file.AppFs
			file.AppFs = afero.NewMemMapFs()
			defer func() {
				file.AppFs = oldFs
			}()

			oldUrl := waitForItDownloadUrl
			waitForItDownloadUrl = tt.srv.URL + "/platform/wait-for-it/wait-for-it.sh"
			defer func() {
				waitForItDownloadUrl = oldUrl
				tt.srv.Close()
			}()

			err := InstallWaitForIt(tt.args.installPath)
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
