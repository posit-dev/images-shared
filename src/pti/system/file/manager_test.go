package file

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path"
	"runtime"
	"testing"

	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

const testTarGz = "test.tar.gz"

var testdataPath string

func init() {
	_, testPath, _, _ := runtime.Caller(0)
	// The ".." may change depending on you folder structure
	testdataPath = path.Join(path.Dir(testPath), "testdata")
}

func resetAppFs() {
	AppFs = afero.NewOsFs()
}

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

func Test_IsDir(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name      string
		setupFs   func(fs afero.Fs) (testPath string, err error)
		useMemMap bool
		want      bool
		wantErr   bool
	}{
		{
			name: "path does not exist",
			setupFs: func(fs afero.Fs) (string, error) {
				tmpDir, err := afero.TempDir(fs, "", "")
				if err != nil {
					return "", err
				}
				return tmpDir + "/nonexistentdir", nil
			},
			want:    false,
			wantErr: false,
		},
		{
			name: "path exists",
			setupFs: func(fs afero.Fs) (string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", err
				}
				return tmpDir, nil
			},
			want:    true,
			wantErr: false,
		},
		{
			name: "path is file",
			setupFs: func(fs afero.Fs) (string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				tmpFile := tmpDir + "/testfile"
				err = afero.WriteFile(fs, tmpFile, []byte("test"), 0o644)
				if err != nil {
					return "", err
				}
				return tmpFile, nil
			},
			want:    false,
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Cleanup(resetAppFs)
			AppFs = afero.NewMemMapFs()

			testPath, err := tt.setupFs(AppFs)
			require.NoError(err, "setupFs() error = %v", err)

			require.NoError(err, "setupFs() error = %v", err)

			got, err := IsDir(testPath)

			assert.Equal(tt.want, got)
			if tt.wantErr {
				assert.NotNil(err)
			} else {
				assert.Nil(err)
			}
		})
	}
}

func Test_IsDir_Symlink(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		setupFs        func(fs afero.OsFs) (testPath string, tmpDir string, err error)
		want           bool
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "path is symlink to directory",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				tmpSrcDir := tmpDir + "/srcdir"
				err = fs.Mkdir(tmpSrcDir, 0o755)
				if err != nil {
					return "", tmpDir, err
				}
				tmpSymlink := tmpDir + "/symlink"
				err = fs.SymlinkIfPossible(tmpSrcDir, tmpSymlink)
				if err != nil {
					return "", tmpDir, err
				}
				return tmpSymlink, tmpDir, nil
			},
			want:    false,
			wantErr: false,
		},
		{
			name: "path is symlink to file",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				tmpFile := tmpDir + "/testfile"
				err = afero.WriteFile(fs, tmpFile, []byte("test"), 0o644)
				if err != nil {
					return "", tmpDir, err
				}
				tmpSymlink := tmpDir + "/symlink"
				err = fs.SymlinkIfPossible(tmpFile, tmpSymlink)
				if err != nil {
					return "", tmpDir, err
				}
				return tmpSymlink, tmpDir, nil
			},
			want:    false,
			wantErr: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			testPath, tmpDir, err := tt.setupFs(*AppFs.(*afero.OsFs))
			t.Cleanup(func() {
				AppFs.RemoveAll(tmpDir)
				resetAppFs()
			})

			require.NoError(err, "setupFs() error = %v", err)

			got, err := IsDir(testPath)

			assert.Equal(tt.want, got)
			if tt.wantErr {
				assert.NotNil(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				assert.Nil(err)
			}
		})
	}
}

func Test_IsFile(t *testing.T) {
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
				tmpDir, err := afero.TempDir(fs, "", "")
				if err != nil {
					return "", err
				}
				fh, err := fs.Create(tmpDir + "/testfile")
				if err != nil {
					return "", err
				}
				defer fh.Close()
				return fh.Name(), nil
			},
			want:    true,
			wantErr: false,
		},
		{
			name: "path is directory",
			setupFs: func(fs afero.Fs) (string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", err
				}
				return tmpDir, nil
			},
			want:    false,
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			AppFs = afero.NewMemMapFs()
			t.Cleanup(resetAppFs)

			fileName, err := tt.setupFs(AppFs)
			require.Nil(err, "setupFs() error = %v", err)

			got, err := IsFile(fileName)

			assert.Equal(tt.want, got)
			if tt.wantErr {
				assert.NotNil(err)
			} else {
				assert.Nil(err)
			}
		})
	}
}

func Test_IsFile_Symlink(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name    string
		setupFs func(fs afero.OsFs) (testPath string, tmpDir string, err error)
		want    bool
		wantErr bool
	}{
		{
			name: "path is symlink to directory",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				tmpSymlink := tmpDir + "/symlink"
				err = fs.SymlinkIfPossible(tmpDir, tmpSymlink)
				if err != nil {
					return "", tmpDir, err
				}
				return tmpSymlink, tmpDir, nil
			},
			want:    false,
			wantErr: false,
		},
		{
			name: "path is symlink to file",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				tmpFile := tmpDir + "/testfile"
				err = afero.WriteFile(fs, tmpFile, []byte("test"), 0o644)
				if err != nil {
					return "", tmpDir, err
				}
				tmpSymlink := tmpDir + "/symlink"
				err = fs.SymlinkIfPossible(tmpFile, tmpSymlink)
				if err != nil {
					return "", tmpDir, err
				}
				return tmpSymlink, tmpDir, nil
			},
			want:    false,
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fileName, tmpDir, err := tt.setupFs(*AppFs.(*afero.OsFs))
			t.Cleanup(func() {
				AppFs.RemoveAll(tmpDir)
				resetAppFs()
			})

			require.NoError(err, "setupFs() error = %v", err)

			got, err := IsFile(fileName)

			assert.Equal(tt.want, got)
			if tt.wantErr {
				assert.NotNil(err)
			} else {
				assert.Nil(err)
			}
		})
	}
}

func Test_IsSymlink(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name    string
		setupFs func(fs afero.OsFs) (testPath string, tmpDir string, err error)
		want    bool
		wantErr bool
	}{
		{
			name: "path is directory",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				return tmpDir, tmpDir, nil
			},
			want:    false,
			wantErr: false,
		},
		{
			name: "path is file",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				tmpFile := tmpDir + "/testfile"
				err = afero.WriteFile(fs, tmpFile, []byte("test"), 0o644)
				if err != nil {
					return "", tmpDir, err
				}
				return tmpFile, tmpDir, nil
			},
			want:    false,
			wantErr: false,
		},
		{
			name: "path is symlink to directory",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				tmpSymlink := tmpDir + "/symlink"
				err = fs.SymlinkIfPossible(tmpDir, tmpSymlink)
				if err != nil {
					return "", tmpDir, err
				}
				return tmpSymlink, tmpDir, nil
			},
			want:    true,
			wantErr: false,
		},
		{
			name: "path is symlink to file",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				tmpFile := tmpDir + "/testfile"
				err = afero.WriteFile(fs, tmpFile, []byte("test"), 0o644)
				if err != nil {
					return "", tmpDir, err
				}
				tmpSymlink := tmpDir + "/symlink"
				err = fs.SymlinkIfPossible(tmpFile, tmpSymlink)
				if err != nil {
					return "", tmpDir, err
				}
				return tmpSymlink, tmpDir, nil
			},
			want:    true,
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fileName, tmpDir, err := tt.setupFs(*AppFs.(*afero.OsFs))
			t.Cleanup(func() {
				AppFs.RemoveAll(tmpDir)
				resetAppFs()
			})

			require.NoError(err, "setupFs() error = %v", err)

			got, err := IsSymlink(fileName)

			assert.Equal(tt.want, got)
			if tt.wantErr {
				assert.Error(err)
			} else {
				assert.NoError(err)
			}
		})
	}
}

func Test_CreateSymlink(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		setupFs        func(fs afero.OsFs) (src string, tmpDir string, err error)
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "src does not exist",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				return tmpDir + "/doesnotexist", tmpDir, nil
			},
			wantErr:        true,
			wantErrMessage: "does not exist",
		},
		{
			name: "path is directory",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				err = fs.Mkdir(tmpDir+"/test", 0o755)
				if err != nil {
					return "", tmpDir, err
				}
				return tmpDir + "/test", tmpDir, nil
			},
			wantErr: false,
		},
		{
			name: "path is file",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				tmpFile := tmpDir + "/testfile"
				err = afero.WriteFile(fs, tmpFile, []byte("test"), 0o644)
				if err != nil {
					return "", tmpDir, err
				}
				return tmpFile, tmpDir, nil
			},
			wantErr: false,
		},
		{
			name: "normal file exists at target",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				tmpFile := tmpDir + "/testfile"
				err = afero.WriteFile(fs, tmpFile, []byte("test"), 0o644)
				if err != nil {
					return "", tmpDir, err
				}
				tmpFile = tmpDir + "/symlink"
				err = afero.WriteFile(fs, tmpFile, []byte("test"), 0o644)
				if err != nil {
					return "", tmpDir, err
				}
				return tmpFile, tmpDir, nil
			},
			wantErr:        true,
			wantErrMessage: "failed to create symlink",
		},
		{
			name: "symlink exists",
			setupFs: func(fs afero.OsFs) (string, string, error) {
				tmpDir, err := afero.TempDir(fs, "", "testdir")
				if err != nil {
					return "", tmpDir, err
				}
				tmpFile := tmpDir + "/testfile"
				err = afero.WriteFile(fs, tmpFile, []byte("test"), 0o644)
				if err != nil {
					return "", tmpDir, err
				}
				err = CreateSymlink(tmpFile, tmpDir+"/symlink")
				if err != nil {
					return "", tmpDir, err
				}
				return tmpFile, tmpDir, nil
			},
			wantErr:        true,
			wantErrMessage: "failed to create symlink",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			src, tmpDir, err := tt.setupFs(*AppFs.(*afero.OsFs))
			t.Cleanup(func() {
				AppFs.RemoveAll(tmpDir)
				resetAppFs()
			})

			require.NoError(err, "setupFs() error = %v", err)

			err = CreateSymlink(src, tmpDir+"/symlink")

			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)

				isSymlink, err := IsSymlink(tmpDir + "/symlink")
				require.NoError(err, "IsSymlink() error = %v", err)
				assert.True(isSymlink, "IsSymlink() = %v, want %v", isSymlink, true)

				truePath, err := os.Readlink(tmpDir + "/symlink")
				require.NoError(err, "Readlink() error = %v", err)
				assert.Equal(src, truePath, "Readlink() = %v, want %v", truePath, src)
			}
		})
	}
}

func Test_InstallableDir(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		setupFs        func(fs afero.Fs) string
		setEmpty       bool
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "installable empty dir",
			setupFs: func(fs afero.Fs) string {
				tmpDir, err := afero.TempDir(fs, "", "installable")
				require.NoError(err)
				return tmpDir
			},
			setEmpty: true,
			wantErr:  false,
		},
		{
			name: "installable empty dir empty agnostic",
			setupFs: func(fs afero.Fs) string {
				tmpDir, err := afero.TempDir(fs, "", "installable")
				require.NoError(err)
				return tmpDir
			},
			setEmpty: false,
			wantErr:  false,
		},
		{
			name: "not empty dir",
			setupFs: func(fs afero.Fs) string {
				tmpDir, err := afero.TempDir(fs, "", "installable")
				require.NoError(err)
				tmpFile := tmpDir + "/testfile"
				err = afero.WriteFile(fs, tmpFile, []byte("test"), 0o644)
				require.NoError(err)
				return tmpDir
			},
			setEmpty:       true,
			wantErr:        true,
			wantErrMessage: "is not empty",
		},
		{
			name: "not empty dir empty agnostic",
			setupFs: func(fs afero.Fs) string {
				tmpDir, err := afero.TempDir(fs, "", "installable")
				require.NoError(err)
				tmpFile := tmpDir + "/testfile"
				err = afero.WriteFile(fs, tmpFile, []byte("test"), 0o644)
				require.NoError(err)
				return tmpDir
			},
			setEmpty: false,
			wantErr:  false,
		},
		{
			name: "path does not exist",
			setupFs: func(fs afero.Fs) string {
				tmpDir, err := afero.TempDir(fs, "", "installable")
				require.NoError(err)
				return tmpDir + "doesnotexist"
			},
			setEmpty: false,
			wantErr:  false,
		},
		{
			name: "path is file",
			setupFs: func(fs afero.Fs) string {
				tmpDir, err := afero.TempDir(fs, "", "installable")
				require.NoError(err)
				tmpFile := tmpDir + "/testfile"
				err = afero.WriteFile(fs, tmpFile, []byte("test"), 0o644)
				require.NoError(err)
				return tmpFile
			},
			setEmpty:       false,
			wantErr:        true,
			wantErrMessage: "is not a directory",
		},
		{
			name: "no path given",
			setupFs: func(fs afero.Fs) string {
				return ""
			},
			setEmpty:       false,
			wantErr:        true,
			wantErrMessage: "installation path is required",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			AppFs = afero.NewMemMapFs()
			t.Cleanup(resetAppFs)

			p := tt.setupFs(AppFs)

			err := InstallableDir(p, tt.setEmpty)

			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
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
			AppFs = afero.NewMemMapFs()
			t.Cleanup(resetAppFs)

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

	AppFs = afero.NewMemMapFs()
	t.Cleanup(resetAppFs)

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

	AppFs = afero.NewMemMapFs()
	t.Cleanup(resetAppFs)

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

func Test_moveFile(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	AppFs = afero.NewMemMapFs()
	t.Cleanup(resetAppFs)

	tmpDir, err := afero.TempDir(AppFs, "", "move")
	require.NoError(err)
	tmpFile, err := afero.TempFile(AppFs, tmpDir, "oldfile")
	require.NoError(err)
	tmpFileName := tmpFile.Name()
	_, err = tmpFile.WriteString("test")
	require.NoError(err, "TempFile.WriteString() error = %v", err)
	tmpFile.Close()

	destTmpFile := tmpDir + "/newfile"
	err = moveFile(tmpFileName, destTmpFile)

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

func Test_copyFile(t *testing.T) {
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
			AppFs = afero.NewMemMapFs()
			t.Cleanup(resetAppFs)

			fileName, err := tt.setupFs(AppFs)
			require.Nil(err, "setupFs() error = %v", err)

			destTmpDir, err := afero.TempDir(AppFs, "", "copy")
			require.Nil(err, "TempDir() error = %v", err)
			destTmpFile := destTmpDir + "/newfile"

			err = copyFile(fileName, destTmpFile)

			if tt.wantErr {
				require.Error(err, "File.CopyFile() error = %v", err)
				require.ErrorContains(
					err,
					tt.wantErrMessage,
					"File.CopyFile() error message = %v, want %v",
					err.Error(),
					tt.wantErrMessage,
				)
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

func Test_moveDir(t *testing.T) {
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
				err := fs.MkdirAll(dir+"/subdir", 0o755)
				require.NoError(err, "MkdirAll() error = %v", err)
				createTestFile(fs, dir+"/subdir1/file3", "test3")
				err = fs.MkdirAll(dir+"/subdir1/subdir2", 0o755)
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
				assert.Equal(
					"test1",
					string(contents),
					"File contents = %v, want %v",
					string(contents),
					"test1",
				)

				contents, err = afero.ReadFile(fs, dest+"/file2")
				require.NoError(err, "ReadFile() error = %v", err)
				assert.Equal(
					"test2",
					string(contents),
					"File contents = %v, want %v",
					string(contents),
					"test2",
				)

				contents, err = afero.ReadFile(fs, dest+"/subdir1/file3")
				require.NoError(err, "ReadFile() error = %v", err)
				assert.Equal(
					"test3",
					string(contents),
					"File contents = %v, want %v",
					string(contents),
					"test3",
				)

				contents, err = afero.ReadFile(fs, dest+"/subdir1/subdir2/file4")
				require.NoError(err, "ReadFile() error = %v", err)
				assert.Equal(
					"test4",
					string(contents),
					"File contents = %v, want %v",
					string(contents),
					"test4",
				)

				return nil
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			AppFs = afero.NewMemMapFs()
			t.Cleanup(resetAppFs)

			srcDir, err := afero.TempDir(AppFs, "", "src")
			require.NoError(err, "TempDir() error = %v", err)
			destDir, err := afero.TempDir(AppFs, "", "dest")
			require.NoError(err, "TempDir() error = %v", err)

			tt.setupFs(AppFs, srcDir)

			err = moveDir(srcDir, destDir)

			require.NoError(err, "File.MoveDir() error = %v", err)

			err = tt.validateFs(AppFs, srcDir, destDir)
			require.NoError(err, "validateFs() error = %v", err)
		})
	}
}

func Test_copyDir(t *testing.T) {
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
				err := fs.MkdirAll(dir+"/subdir", 0o755)
				require.NoError(err, "MkdirAll() error = %v", err)
				createTestFile(fs, dir+"/subdir1/file3", "test3")
				err = fs.MkdirAll(dir+"/subdir1/subdir2", 0o755)
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
					assert.Equal(
						"test1",
						string(contents),
						"File contents = %v, want %v",
						string(contents),
						"test1",
					)

					contents, err = afero.ReadFile(fs, path+"/file2")
					require.NoError(err, "ReadFile() error = %v", err)
					assert.Equal(
						"test2",
						string(contents),
						"File contents = %v, want %v",
						string(contents),
						"test2",
					)

					contents, err = afero.ReadFile(fs, path+"/subdir1/file3")
					require.NoError(err, "ReadFile() error = %v", err)
					assert.Equal(
						"test3",
						string(contents),
						"File contents = %v, want %v",
						string(contents),
						"test3",
					)

					contents, err = afero.ReadFile(fs, path+"/subdir1/subdir2/file4")
					require.NoError(err, "ReadFile() error = %v", err)
					assert.Equal(
						"test4",
						string(contents),
						"File contents = %v, want %v",
						string(contents),
						"test4",
					)
				}

				return nil
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			AppFs = afero.NewMemMapFs()
			t.Cleanup(resetAppFs)

			srcDir, err := afero.TempDir(AppFs, "", "src")
			require.NoError(err, "TempDir() error = %v", err)
			destDir, err := afero.TempDir(AppFs, "", "dest")
			require.NoError(err, "TempDir() error = %v", err)

			tt.setupFs(AppFs, srcDir)

			err = copyDir(srcDir, destDir)

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
				srv: httptest.NewServer(
					http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
						if r.URL.Path != "/success.txt" {
							t.Errorf("Request URL = %v, want %v", r.URL.Path, "/success.txt")
						}
						w.WriteHeader(http.StatusOK)
						w.Write([]byte("200 OK"))
					}),
				),
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
				srv: httptest.NewServer(
					http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
						if r.URL.Path != "/fail.txt" {
							t.Errorf("Request URL = %v, want %v", r.URL.Path, "/fail.txt")
						}
						w.WriteHeader(http.StatusNotFound)
					}),
				),
			},
			wantFile:       false,
			wantErr:        true,
			wantErrMessage: "failed to download file with status",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			AppFs = afero.NewMemMapFs()
			t.Cleanup(resetAppFs)

			err := DownloadFile(tt.fields.srv.URL+tt.fields.url, tt.fields.path)
			defer tt.fields.srv.Close()

			if tt.wantErr {
				require.Error(err, "File.DownloadFile() error = %v", err)
				assert.ErrorContains(
					err,
					"failed to download file",
					"File.DownloadFile() error message = %v, want %v",
					err.Error(),
					"failed to download file",
				)
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

func Test_ExtractTarGz(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	fileStructure := []struct {
		path     string
		contents string
		isDir    bool
	}{
		{
			path:  "/test_targz",
			isDir: true,
		},
		{
			path:     "/test_targz/file1",
			contents: "test1",
			isDir:    false,
		},
		{
			path:  "/test_targz/subdir1",
			isDir: true,
		},
		{
			path:     "/test_targz/subdir1/file2",
			contents: "test2",
			isDir:    false,
		},
		{
			path:     "/test_targz/subdir1/file3",
			contents: "test3",
			isDir:    false,
		},
		{
			path:  "/test_targz/subdir1/subdir3",
			isDir: true,
		},
		{
			path:     "/test_targz/subdir1/subdir3/file4",
			contents: "test4",
			isDir:    false,
		},
		{
			path:  "/test_targz/subdir2",
			isDir: true,
		},
		{
			path:     "/test_targz/subdir2/file5",
			contents: "test5",
			isDir:    false,
		},
	}
	contents, err := afero.ReadFile(AppFs, testdataPath+"/"+testTarGz)
	require.NoError(err)

	AppFs = afero.NewMemMapFs()
	t.Cleanup(resetAppFs)

	err = afero.WriteFile(AppFs, "/"+testTarGz, contents, 0o644)
	require.NoError(err)

	err = ExtractTarGz("/"+testTarGz, "/")
	require.NoError(err)

	exists, err := IsPathExist("/" + testTarGz)
	require.NoError(err)
	assert.True(exists, "%s file does not exist", testTarGz)

	for _, entry := range fileStructure {
		if entry.isDir {
			isDir, err := IsDir(entry.path)
			assert.NoError(err)
			assert.True(isDir, "%s is not a directory", entry.path)
		} else {
			contents, err := afero.ReadFile(AppFs, entry.path)
			assert.NoError(err)
			assert.Contains(string(contents), entry.contents, "File contents = %v, want %v", string(contents), entry.contents)
		}
	}
}
