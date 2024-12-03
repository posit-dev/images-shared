package file

import (
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
