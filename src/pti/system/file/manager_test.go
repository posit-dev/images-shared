package file

import (
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

func TestFile_IsPathExist(t *testing.T) {
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
			if got != tt.want {
				t.Errorf("File.IsPathExist() got = %v, want %v", got, tt.want)
			}
			if (err != nil) != tt.wantErr {
				t.Errorf("File.IsPathExist() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestFile_Stat(t *testing.T) {
	tmpDir := t.TempDir()
	tmpFileName := tmpDir + "/file"
	tmpFile, err := os.Create(tmpFileName)
	if err != nil {
		t.Fatal(err)
	}
	defer tmpFile.Close()

	file := &File{Path: tmpFileName}
	fileInfo, err := file.Stat()
	if err != nil {
		t.Fatalf("File.Stat() error = %v", err)
	}
	if "file" != fileInfo.Name() {
		t.Errorf("File.Stat().Name() = %v, want %v", fileInfo.Name(), "file")
	}
	if fileInfo.IsDir() {
		t.Errorf("File.Stat().IsDir() = %v, want %v", fileInfo.IsDir(), false)
	}
}

func TestFile_Create(t *testing.T) {
	tmpDir := t.TempDir()
	tmpFileName := tmpDir + "/file"
	file := &File{Path: tmpFileName}
	fh, err := file.Create()
	if err != nil {
		t.Fatalf("File.Create() error = %v", err)
	}
	if err := fh.Close(); err != nil {
		t.Fatalf("File.Create().Close() error = %v", err)
	}
}

func TestFile_Open(t *testing.T) {
	tmpDir := t.TempDir()
	tmpFileName := tmpDir + "/file"
	tmpFile, err := os.Create(tmpFileName)
	if err != nil {
		t.Fatal(err)
	}
	defer tmpFile.Close()

	file := &File{Path: tmpFileName}
	fh, err := file.Open()
	if err != nil {
		t.Fatalf("File.Open() error = %v", err)
	}
	if err := fh.Close(); err != nil {
		t.Fatalf("File.Open().Close() error = %v", err)
	}
}

func TestFile_MoveFile(t *testing.T) {
	tmpDir := t.TempDir()
	tmpFileName := tmpDir + "/file"
	tmpFile, err := os.Create(tmpFileName)
	if err != nil {
		t.Fatal(err)
	}
	defer tmpFile.Close()

	newTmpFileName := tmpDir + "/newfile"
	file := &File{Path: tmpFileName}
	if err := file.MoveFile(newTmpFileName); err != nil {
		t.Fatalf("File.MoveFile() error = %v", err)
	}
	if file.Path != newTmpFileName {
		t.Errorf("File.Path = %v, want %v", file.Path, newTmpFileName)
	}
	oldFile := &File{Path: tmpFileName}
	exists, err := oldFile.IsPathExist()
	if err != nil {
		t.Fatalf("File.IsPathExist() error = %v", err)
	}
	if exists {
		t.Errorf("File.MoveFile() old file exists")
	}
}

func TestFile_CopyFile(t *testing.T) {
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
	if err != nil {
		t.Fatalf("File.CopyFile() error = %v", err)
	}
	if newFile.Path != newTmpFileName {
		t.Errorf("File.Path = %v, want %v", newFile.Path, newTmpFileName)
	}
}

func TestFile_DownloadFile(t *testing.T) {
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
			if (err != nil) != tt.wantErr {
				t.Errorf("DownloadFile() error = %v, wantErr %v", err, tt.wantErr)
			}
			if file != nil && !tt.wantFile {
				t.Errorf("DownloadFile() returned File, want not exists")
			}
			if file != nil && file.Path != tt.fields.Path {
				t.Errorf("File.Path = %v, want %v", file.Path, tt.fields.Path)
			}
			if file != nil {
				fh, err := file.Open()
				if err != nil {
					t.Fatalf("File.Open() error = %v", err)
				}
				buf := make([]byte, 1024)
				n, err := fh.Read(buf)
				if err != nil {
					t.Fatalf("File.Read() error = %v", err)
				}
				if string(buf[:n]) != tt.fields.Contents {
					t.Errorf("File contents = %v, want %v", string(buf[:n]), tt.fields.Contents)
				}
			}
		})
	}
}
