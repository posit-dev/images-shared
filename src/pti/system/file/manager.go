package file

import (
	"archive/tar"
	"bufio"
	"compress/gzip"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
)

type Manager interface {
	IsPathExist() (bool, error)
	Stat() (os.FileInfo, error)
	Create() error
	Open() (*os.File, error)
	ChangePermissions(perm os.FileMode) error
	MoveFile(newFilePath string) error
	CopyFile(newFilePath string) (*File, error)
	Download(url string, filepath string) (*File, error)
	ExtractTarGz(destinationPath string) error
}

type File struct {
	Path string
}

func (f *File) IsPathExist() (bool, error) {
	_, err := os.Stat(f.Path)
	if err != nil {
		if os.IsNotExist(err) {
			slog.Debug("Path does not exist: " + f.Path)
			return false, nil
		}
		return false, err
	}
	return true, nil
}

func (f *File) Stat() (os.FileInfo, error) {
	i, err := os.Stat(f.Path)
	if err != nil {
		return nil, fmt.Errorf("failed to stat file %s: %w", f.Path, err)
	}
	return i, nil
}

func (f *File) Create() (*os.File, error) {
	slog.Debug("Creating file: " + f.Path)
	fh, err := os.Create(f.Path)
	if err != nil {
		return nil, fmt.Errorf("failed to create file %s: %w", f.Path, err)
	}
	slog.Debug("File created")
	return fh, nil
}

func (f *File) Open() (*os.File, error) {
	fh, err := os.Open(f.Path)
	if err != nil {
		return nil, err
	}
	return fh, nil
}

func (f *File) MoveFile(newFilePath string) error {
	slog.Debug("Moving file from " + f.Path + " to " + newFilePath)
	if err := os.Rename(f.Path, newFilePath); err != nil {
		return err
	}
	f.Path = newFilePath
	slog.Debug("Move complete")
	return nil
}

func (f *File) CopyFile(newFilePath string) (*File, error) {
	slog.Debug("Copying file from " + f.Path + " to " + newFilePath)

	sourceFileStat, err := os.Stat(f.Path)
	if err != nil {
		return nil, err
	}

	if !sourceFileStat.Mode().IsRegular() {
		return nil, fmt.Errorf("%s is not a regular file", f.Path)
	}

	sourceFh, err := f.Open()
	if err != nil {
		return nil, err
	}

	destination := &File{Path: newFilePath}
	destinationFh, err := destination.Create()
	if err != nil {
		return nil, err
	}
	defer destinationFh.Close()
	_, err = io.Copy(destinationFh, sourceFh)

	slog.Debug("Copy complete")

	return destination, err
}

func DownloadFile(url string, filepath string) (*File, error) {
	slog.Debug("Downloading file from " + url + " to " + filepath)

	request, _ := http.NewRequest(http.MethodGet, url, nil)
	client := &http.Client{}

	resp, err := client.Do(request)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to download file: %s", resp.Status)
	}

	newFile := &File{Path: filepath}
	newFh, err := newFile.Create()
	if err != nil {
		return nil, err
	}
	defer newFh.Close()

	_, err = io.Copy(newFh, resp.Body)
	if err != nil {
		return nil, err
	}

	slog.Debug("Download complete")

	return newFile, nil
}

func (f *File) ExtractTarGz(destinationPath string) error {
	slog.Info("Extracting tar.gz file " + f.Path + " to " + destinationPath)

	fh, err := f.Open()
	if err != nil {
		return fmt.Errorf("failed to open %s for extraction: %w", f.Path, err)
	}
	defer fh.Close()
	reader := bufio.NewReader(fh)

	gzr, err := gzip.NewReader(reader)
	if err != nil {
		return fmt.Errorf("failed to create gzip reader for %s: %w", f.Path, err)
	}

	tr := tar.NewReader(gzr)
	for {
		header, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("failed to read tar header for %s: %w", f.Path, err)
		}

		target := destinationPath + "/" + header.Name
		switch header.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(target, os.FileMode(header.Mode)); err != nil {
				return fmt.Errorf("failed to create directory %s: %w", target, err)
			}
		case tar.TypeReg:
			fh, err := os.OpenFile(target, os.O_CREATE|os.O_RDWR, os.FileMode(header.Mode))
			if err != nil {
				return fmt.Errorf("failed to create file %s: %w", target, err)
			}
			defer fh.Close()
			if _, err := io.Copy(fh, tr); err != nil {
				return fmt.Errorf("failed to copy file %s: %w", target, err)
			}
		}
	}

	return nil
}
