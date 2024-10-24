package system

import (
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
)

func DownloadFile(filepath string, url string) error {
	slog.Debug("Downloading file from " + url + " to " + filepath)

	resp, err := http.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	out, err := os.Create(filepath)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, resp.Body)

	slog.Debug("Download complete")

	return err
}

func MoveFile(oldFilePath, newFilePath string) error {
	slog.Debug("Moving file from " + oldFilePath + " to " + newFilePath)
	if err := os.Rename(oldFilePath, newFilePath); err != nil {
		return err
	}
	slog.Debug("Move complete")
	return nil
}

func CopyFile(oldFilePath, newFilePath string) error {
	slog.Debug("Copying file from " + oldFilePath + " to " + newFilePath)

	sourceFileStat, err := os.Stat(oldFilePath)
	if err != nil {
		return err
	}

	if !sourceFileStat.Mode().IsRegular() {
		return fmt.Errorf("%s is not a regular file", oldFilePath)
	}

	source, err := os.Open(oldFilePath)
	if err != nil {
		return err
	}
	defer source.Close()

	destination, err := os.Create(newFilePath)
	if err != nil {
		return err
	}
	defer destination.Close()
	_, err = io.Copy(destination, source)

	slog.Debug("Copy complete")

	return err
}

func PathExists(path string) (bool, error) {
	_, err := os.Stat(path)
	if err == nil {
		return true, nil
	}
	if os.IsNotExist(err) {
		return false, nil
	}
	return false, err
}

func DirIsEmpty(path string) (bool, error) {
	f, err := os.Open(path)
	if err != nil {
		return false, err
	}
	defer f.Close()

	_, err = f.Readdirnames(1)

	if err == io.EOF {
		return true, nil
	}
	return false, err
}
