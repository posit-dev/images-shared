package file

import (
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"net/http"
	"net/http/httptest"
	"testing"
)

func Test_IsPathExist(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name    string
		setupFs func(fs afero.Fs) (string, error)
		want    bool
		wantErr bool
	}{
		{
			name: "path does not exist",
			setupFs: func(fs afero.Fs) (string, error) {
				tmpDir, err := afero.TempDir(fs, "", "")
				if err != nil {
					return "", err
				}
				return tmpDir + "/nonexistentfile", nil
			},
			want:    false,
			wantErr: false,
		},
		{
			name: "path exists",
			setupFs: func(fs afero.Fs) (string, error) {
				fh, err := afero.TempFile(fs, "", "testfile")
				if err != nil {
					return "", err
				}
				return fh.Name(), nil
			},
			want:    true,
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()

			oldFs := AppFs
			AppFs = afero.NewMemMapFs()
			defer func() {
				AppFs = oldFs
			}()

			fileName, err := tt.setupFs(AppFs)
			require.Nil(err, "setupFs() error = %v", err)

			got, err := IsPathExist(fileName)

			assert.Equal(tt.want, got)
			if tt.wantErr {
				assert.NotNil(err)
			} else {
				assert.Nil(err)
			}
		})
	}
}

func Test_Stat(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		setupFs        func(fs afero.Fs) (string, error)
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			setupFs: func(fs afero.Fs) (string, error) {
				fh, err := afero.TempFile(fs, "", "testfile")
				if err != nil {
					return "", err
				}
				_, err = fh.WriteString("test")
				if err != nil {
					return "", err
				}
				return fh.Name(), nil
			},
			wantErr: false,
		},
		{
			name: "path does not exist",
			setupFs: func(fs afero.Fs) (string, error) {
				tmpDir, err := afero.TempDir(fs, "", "")
				if err != nil {
					return "", err
				}
				return tmpDir + "/nonexistentfile", nil
			},
			wantErr:        true,
			wantErrMessage: "failed to stat file",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := AppFs
			AppFs = afero.NewMemMapFs()
			defer func() {
				AppFs = oldFs
			}()

			fileName, err := tt.setupFs(AppFs)
			require.Nil(err, "setupFs() error = %v", err)

			statFile, err := Stat(fileName)

			if tt.wantErr {
				assert.NotNil(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				assert.Nil(err)
				assert.Contains(fileName, statFile.Name())
				assert.False(statFile.IsDir())
			}
		})
	}
}

func Test_Create(t *testing.T) {
	require := require.New(t)

	oldFs := AppFs
	AppFs = afero.NewMemMapFs()
	defer func() {
		AppFs = oldFs
	}()

	tmpDir, err := afero.TempDir(AppFs, "", "create")
	require.NoError(err)
	tmpFileName := tmpDir + "/file"

	fh, err := Create(tmpFileName)

	require.NoError(err)
	_, err = fh.WriteString("test")
	require.NoError(err, "File.WriteString() error = %v", err)

	err = fh.Close()
	require.NoError(err, "File.Create().Close() error = %v", err)
}

func Test_Open(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	oldFs := AppFs
	AppFs = afero.NewMemMapFs()
	defer func() {
		AppFs = oldFs
	}()

	tmpFile, err := afero.TempFile(AppFs, "", "open")
	require.NoError(err)
	_, err = tmpFile.WriteString("test")
	require.NoError(err, "TempFile.WriteString() error = %v", err)
	defer tmpFile.Close()

	fh, err := Open(tmpFile.Name())
	require.NoError(err, "File.Open() error = %v", err)

	contents, err := afero.ReadFile(AppFs, fh.Name())
	require.NoError(err, "ReadFile() error = %v", err)
	assert.Equal("test", string(contents), "File contents = %v, want %v", string(contents), "test")
	assert.Equal(tmpFile.Name(), fh.Name(), "File.Name() = %v, want %v", fh.Name(), tmpFile.Name())
	err = fh.Close()
	require.NoError(err, "File.Open().Close() error = %v", err)
}

func Test_MoveFile(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	oldFs := AppFs
	AppFs = afero.NewMemMapFs()
	defer func() {
		AppFs = oldFs
	}()

	tmpDir, err := afero.TempDir(AppFs, "", "move")
	require.NoError(err)
	tmpFile, err := afero.TempFile(AppFs, tmpDir, "oldfile")
	require.NoError(err)
	tmpFileName := tmpFile.Name()
	_, err = tmpFile.WriteString("test")
	require.NoError(err, "TempFile.WriteString() error = %v", err)
	tmpFile.Close()

	destTmpFile := tmpDir + "/newfile"
	err = MoveFile(tmpFileName, destTmpFile)

	require.Nil(err, "File.MoveFile() error = %v", err)
	exists, err := IsPathExist(tmpFileName)
	require.Nil(err, "File.IsPathExist() error = %v", err)
	assert.False(exists, "File.MoveFile() old file exists")

	exists, err = IsPathExist(destTmpFile)
	require.Nil(err, "File.IsPathExist() error = %v", err)
	assert.True(exists, "File.MoveFile() new file does not exist")

	contents, err := afero.ReadFile(AppFs, destTmpFile)
	require.Nil(err, "ReadFile() error = %v", err)
	assert.Equal("test", string(contents), "File contents = %v, want %v", string(contents), "test")
}

func Test_CopyFile(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		setupFs        func(fs afero.Fs) (string, error)
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			setupFs: func(fs afero.Fs) (string, error) {
				tmpDir, err := afero.TempDir(fs, "", "copy")
				if err != nil {
					return "", err
				}
				tmpFile, err := afero.TempFile(fs, tmpDir, "oldfile")
				if err != nil {
					return "", err
				}
				_, err = tmpFile.WriteString("test")
				if err != nil {
					return "", err
				}
				return tmpFile.Name(), nil
			},
			wantErr: false,
		},
		{
			name: "source file does not exist",
			setupFs: func(fs afero.Fs) (string, error) {
				tmpDir, err := afero.TempDir(fs, "", "copy")
				if err != nil {
					return "", err
				}
				return tmpDir + "/nonexistentfile", nil
			},
			wantErr:        true,
			wantErrMessage: "failed to stat file",
		},
		{
			name: "source file is not a regular file",
			setupFs: func(fs afero.Fs) (string, error) {
				tmpDir, err := afero.TempDir(fs, "", "copy")
				if err != nil {
					return "", err
				}
				return tmpDir, nil
			},
			wantErr:        true,
			wantErrMessage: "is not a regular file",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := AppFs
			AppFs = afero.NewMemMapFs()
			defer func() {
				AppFs = oldFs
			}()

			fileName, err := tt.setupFs(AppFs)
			require.Nil(err, "setupFs() error = %v", err)

			destTmpDir, err := afero.TempDir(AppFs, "", "copy")
			require.Nil(err, "TempDir() error = %v", err)
			destTmpFile := destTmpDir + "/newfile"

			err = CopyFile(fileName, destTmpFile)

			if tt.wantErr {
				require.Error(err, "File.CopyFile() error = %v", err)
				require.ErrorContains(err, tt.wantErrMessage, "File.CopyFile() error message = %v, want %v", err.Error(), tt.wantErrMessage)
			} else {
				require.NoError(err, "File.CopyFile() error = %v", err)

				exists, err := IsPathExist(fileName)
				require.NoError(err, "File.IsPathExist() error = %v", err)
				assert.True(exists, "File.CopyFile() old file does not exist")

				exists, err = IsPathExist(destTmpFile)
				require.NoError(err, "File.IsPathExist() error = %v", err)
				assert.True(exists, "File.CopyFile() new file does not exist")

				contents, err := afero.ReadFile(AppFs, destTmpFile)
				require.Nil(err, "ReadFile() error = %v", err)
				assert.Equal("test", string(contents), "File contents = %v, want %v", string(contents), "test")
			}
		})
	}
}

func Test_MoveDir(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	createTestFile := func(fs afero.Fs, path, contents string) {
		fh, err := fs.Create(path)
		require.NoError(err, "Create() error = %v", err)
		_, err = fh.WriteString(contents)
		require.NoError(err, "WriteString() error = %v", err)
	}

	tests := []struct {
		name       string
		setupFs    func(fs afero.Fs, dir string)
		validateFs func(fs afero.Fs, src, dest string) error
	}{
		{
			name: "success",
			setupFs: func(fs afero.Fs, dir string) {
				createTestFile(fs, dir+"/file1", "test1")
				createTestFile(fs, dir+"/file2", "test2")
				err := fs.MkdirAll(dir+"/subdir", 0755)
				require.NoError(err, "MkdirAll() error = %v", err)
				createTestFile(fs, dir+"/subdir1/file3", "test3")
				err = fs.MkdirAll(dir+"/subdir1/subdir2", 0755)
				require.NoError(err, "MkdirAll() error = %v", err)
				createTestFile(fs, dir+"/subdir1/subdir2/file4", "test4")
			},
			validateFs: func(fs afero.Fs, src, dest string) error {
				_, err := fs.Stat(src)
				require.Error(err, "Stat() error = %v", err)
				exists, err := IsPathExist(src)
				require.NoError(err, "IsPathExist() error = %v", err)
				assert.False(exists, "source directory exists")

				_, err = fs.Stat(dest)
				require.NoError(err, "Stat() error = %v", err)
				exists, err = IsPathExist(dest)
				require.NoError(err, "IsPathExist() error = %v", err)
				assert.True(exists, "destination directory does not exist")

				contents, err := afero.ReadFile(fs, dest+"/file1")
				require.NoError(err, "ReadFile() error = %v", err)
				assert.Equal("test1", string(contents), "File contents = %v, want %v", string(contents), "test1")

				contents, err = afero.ReadFile(fs, dest+"/file2")
				require.NoError(err, "ReadFile() error = %v", err)
				assert.Equal("test2", string(contents), "File contents = %v, want %v", string(contents), "test2")

				contents, err = afero.ReadFile(fs, dest+"/subdir1/file3")
				require.NoError(err, "ReadFile() error = %v", err)
				assert.Equal("test3", string(contents), "File contents = %v, want %v", string(contents), "test3")

				contents, err = afero.ReadFile(fs, dest+"/subdir1/subdir2/file4")
				require.NoError(err, "ReadFile() error = %v", err)
				assert.Equal("test4", string(contents), "File contents = %v, want %v", string(contents), "test4")

				return nil
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := AppFs
			AppFs = afero.NewMemMapFs()
			defer func() {
				AppFs = oldFs
			}()

			srcDir, err := afero.TempDir(AppFs, "", "src")
			require.NoError(err, "TempDir() error = %v", err)
			destDir, err := afero.TempDir(AppFs, "", "dest")
			require.NoError(err, "TempDir() error = %v", err)

			tt.setupFs(AppFs, srcDir)

			err = MoveDir(srcDir, destDir)

			require.NoError(err, "File.MoveDir() error = %v", err)

			err = tt.validateFs(AppFs, srcDir, destDir)
			require.NoError(err, "validateFs() error = %v", err)
		})
	}
}

func Test_CopyDir(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	createTestFile := func(fs afero.Fs, path, contents string) {
		fh, err := fs.Create(path)
		require.NoError(err, "Create() error = %v", err)
		_, err = fh.WriteString(contents)
		require.NoError(err, "WriteString() error = %v", err)
	}

	tests := []struct {
		name       string
		setupFs    func(fs afero.Fs, dir string)
		validateFs func(fs afero.Fs, src, dest string) error
	}{
		{
			name: "success",
			setupFs: func(fs afero.Fs, dir string) {
				createTestFile(fs, dir+"/file1", "test1")
				createTestFile(fs, dir+"/file2", "test2")
				err := fs.MkdirAll(dir+"/subdir", 0755)
				require.NoError(err, "MkdirAll() error = %v", err)
				createTestFile(fs, dir+"/subdir1/file3", "test3")
				err = fs.MkdirAll(dir+"/subdir1/subdir2", 0755)
				require.NoError(err, "MkdirAll() error = %v", err)
				createTestFile(fs, dir+"/subdir1/subdir2/file4", "test4")
			},
			validateFs: func(fs afero.Fs, src, dest string) error {
				for _, path := range []string{dest, src} {
					_, err := fs.Stat(path)
					require.NoError(err, "Stat() error = %v", err)
					exists, err := IsPathExist(path)
					require.NoError(err, "IsPathExist() error = %v", err)
					assert.True(exists, "destination directory does not exist")

					contents, err := afero.ReadFile(fs, path+"/file1")
					require.NoError(err, "ReadFile() error = %v", err)
					assert.Equal("test1", string(contents), "File contents = %v, want %v", string(contents), "test1")

					contents, err = afero.ReadFile(fs, path+"/file2")
					require.NoError(err, "ReadFile() error = %v", err)
					assert.Equal("test2", string(contents), "File contents = %v, want %v", string(contents), "test2")

					contents, err = afero.ReadFile(fs, path+"/subdir1/file3")
					require.NoError(err, "ReadFile() error = %v", err)
					assert.Equal("test3", string(contents), "File contents = %v, want %v", string(contents), "test3")

					contents, err = afero.ReadFile(fs, path+"/subdir1/subdir2/file4")
					require.NoError(err, "ReadFile() error = %v", err)
					assert.Equal("test4", string(contents), "File contents = %v, want %v", string(contents), "test4")
				}

				return nil
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := AppFs
			AppFs = afero.NewMemMapFs()
			defer func() {
				AppFs = oldFs
			}()

			srcDir, err := afero.TempDir(AppFs, "", "src")
			require.NoError(err, "TempDir() error = %v", err)
			destDir, err := afero.TempDir(AppFs, "", "dest")
			require.NoError(err, "TempDir() error = %v", err)

			tt.setupFs(AppFs, srcDir)

			err = CopyDir(srcDir, destDir)

			require.NoError(err, "File.MoveDir() error = %v", err)

			err = tt.validateFs(AppFs, srcDir, destDir)
			require.NoError(err, "validateFs() error = %v", err)
		})
	}
}

func Test_DownloadFile(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tmpDir := t.TempDir()

	type fields struct {
		url      string
		path     string
		contents string
		srv      *httptest.Server
	}
	tests := []struct {
		name           string
		fields         fields
		wantFile       bool
		wantContents   string
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "successful request",
			fields: fields{
				url:      "/success.txt",
				path:     tmpDir + "/success.txt",
				contents: "200 OK",
				srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					if r.URL.Path != "/success.txt" {
						t.Errorf("Request URL = %v, want %v", r.URL.Path, "/success.txt")
					}
					w.WriteHeader(http.StatusOK)
					w.Write([]byte("200 OK"))
				})),
			},
			wantFile:     true,
			wantContents: "200 OK",
			wantErr:      false,
		},
		{
			name: "bad status code",
			fields: fields{
				url:  "/fail.txt",
				path: tmpDir + "/fail.txt",
				srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					if r.URL.Path != "/fail.txt" {
						t.Errorf("Request URL = %v, want %v", r.URL.Path, "/fail.txt")
					}
					w.WriteHeader(http.StatusNotFound)
				})),
			},
			wantFile:       false,
			wantErr:        true,
			wantErrMessage: "failed to download file with status",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := AppFs
			AppFs = afero.NewMemMapFs()
			defer func() {
				AppFs = oldFs
			}()

			err := DownloadFile(tt.fields.srv.URL+tt.fields.url, tt.fields.path)
			defer tt.fields.srv.Close()

			if tt.wantErr {
				require.Error(err, "File.DownloadFile() error = %v", err)
				assert.ErrorContains(err, "failed to download file", "File.DownloadFile() error message = %v, want %v", err.Error(), "failed to download file")
			} else {
				require.NoError(err, "File.DownloadFile() error = %v", err)

				exists, err := afero.Exists(AppFs, tt.fields.path)
				require.NoError(err, "File.Exists() error = %v", err)
				assert.True(exists, "File.DownloadFile() file does not exist")

				contents, err := afero.ReadFile(AppFs, tt.fields.path)
				require.NoError(err, "ReadFile() error = %v", err)
				assert.Equal(tt.wantContents, string(contents), "File contents = %v, want %v", string(contents), tt.wantContents)
			}
		})
	}
}
