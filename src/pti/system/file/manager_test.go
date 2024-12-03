package file

import (
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

func TestFile_IsPathExist(t *testing.T) {
	assert := assert.New(t)

	tmpDir := t.TempDir()
	tmpFileName := tmpDir + "/file"
	tmpFile, err := os.Create(tmpFileName)
	if err != nil {
		t.Fatal(err)
	}
	defer tmpFile.Close()

	type fields struct {
		Path string
	}
	tests := []struct {
		name    string
		fields  fields
		want    bool
		wantErr bool
	}{
		{
			name: "Path does not exist",
			fields: fields{
				Path: "/tmp/nonexistent",
			},
			want:    false,
			wantErr: false,
		},
		{
			name: "Path exists",
			fields: fields{
				Path: tmpFileName,
			},
			want:    true,
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			f := &File{
				tt.fields.Path,
			}
			got, err := f.IsPathExist()

			assert.Equal(tt.want, got)
			assert.Equal(tt.wantErr, err != nil, "File.IsPathExist() error = %v, wantErr %v", err, tt.wantErr)
		})
	}
}

func TestFile_Stat(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tmpDir := t.TempDir()
	tmpFileName := tmpDir + "/file"
	tmpFile, err := os.Create(tmpFileName)
	require.Nil(err, "os.Create() error = %v", err)
	defer tmpFile.Close()

	file := &File{Path: tmpFileName}
	fileInfo, err := file.Stat()

	require.Nil(err)
	assert.Equal("file", fileInfo.Name())
	assert.False(fileInfo.IsDir())
}

func TestFile_Create(t *testing.T) {
	require := require.New(t)

	tmpDir := t.TempDir()
	tmpFileName := tmpDir + "/file"
	file := &File{Path: tmpFileName}
	fh, err := file.Create()

	require.Nil(err)
	err = fh.Close()
	require.Nil(err, "File.Create().Close() error = %v", err)
}

func TestFile_Open(t *testing.T) {
	require := require.New(t)

	tmpDir := t.TempDir()
	tmpFileName := tmpDir + "/file"
	tmpFile, err := os.Create(tmpFileName)
	if err != nil {
		t.Fatal(err)
	}
	defer tmpFile.Close()

	file := &File{Path: tmpFileName}
	fh, err := file.Open()

	require.Nil(err, "File.Open() error = %v", err)
	err = fh.Close()
	require.Nil(err, "File.Open().Close() error = %v", err)
}

func TestFile_MoveFile(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tmpDir := t.TempDir()
	tmpFileName := tmpDir + "/file"
	tmpFile, err := os.Create(tmpFileName)
	if err != nil {
		t.Fatal(err)
	}
	defer tmpFile.Close()

	newTmpFileName := tmpDir + "/newfile"
	file := &File{Path: tmpFileName}
	err = file.MoveFile(newTmpFileName)

	require.Nil(err, "File.MoveFile() error = %v", err)
	assert.Equal(newTmpFileName, file.Path, "File.Path = %v, want %v", file.Path, newTmpFileName)

	oldFile := &File{Path: tmpFileName}
	exists, err := oldFile.IsPathExist()
	require.Nil(err, "File.IsPathExist() error = %v", err)
	assert.False(exists, "File.MoveFile() old file exists")
}

func TestFile_CopyFile(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tmpDir := t.TempDir()
	tmpFileName := tmpDir + "/file"
	tmpFile, err := os.Create(tmpFileName)
	if err != nil {
		t.Fatal(err)
	}
	_, err = tmpFile.WriteString("test")
	if err != nil {
		return
	}
	defer tmpFile.Close()

	newTmpFileName := tmpDir + "/newfile"
	file := &File{Path: tmpFileName}
	newFile, err := file.CopyFile(newTmpFileName)

	require.Nil(err, "File.CopyFile() error = %v", err)
	assert.Equal(newTmpFileName, newFile.Path, "File.Path = %v, want %v", newFile.Path, newTmpFileName)
}

func TestFile_DownloadFile(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tmpDir := t.TempDir()

	type fields struct {
		Url      string
		Path     string
		Contents string
		Srv      *httptest.Server
	}
	tests := []struct {
		name         string
		fields       fields
		wantFile     bool
		wantContents string
		wantErr      bool
	}{
		{
			name: "Successful request",
			fields: fields{
				Url:      "/success.txt",
				Path:     tmpDir + "/success.txt",
				Contents: "200 OK",
				Srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
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
			name: "Unsuccessful request",
			fields: fields{
				Url:  "/fail.txt",
				Path: tmpDir + "/fail.txt",
				Srv: httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					if r.URL.Path != "/fail.txt" {
						t.Errorf("Request URL = %v, want %v", r.URL.Path, "/fail.txt")
					}
					w.WriteHeader(http.StatusNotFound)
				})),
			},
			wantFile:     false,
			wantContents: "",
			wantErr:      true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			file, err := DownloadFile(tt.fields.Srv.URL+tt.fields.Url, tt.fields.Path)
			defer tt.fields.Srv.Close()

			assert.Equal(tt.wantErr, err != nil, "DownloadFile() error = %v, wantErr %v", err, tt.wantErr)
			assert.Equal(tt.wantFile, file != nil, "DownloadFile() returned File, want not exists")

			if file != nil {
				assert.Equal(tt.fields.Path, file.Path, "File.Path = %v, want %v", file.Path, tt.fields.Path)

				fh, err := file.Open()
				require.Nil(err, "File.Open() error = %v", err)

				buf := make([]byte, 1024)
				n, err := fh.Read(buf)
				require.Nil(err, "File.Read() error = %v", err)

				assert.Equal(tt.wantContents, string(buf[:n]), "File contents = %v, want %v", string(buf[:n]), tt.wantContents)
			}
		})
	}
}
