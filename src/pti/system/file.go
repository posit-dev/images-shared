package system

import (
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"pti/errors"
)

func DownloadFile(filepath string, url string) error {
	slog.Debug("Downloading file from " + url + " to " + filepath)

	resp, err := http.Get(url)
	if err != nil {
		return fmt.Errorf(errors.RequestFailedErrorTpl, url, err)
	}
	defer resp.Body.Close()

	out, err := os.Create(filepath)
	if err != nil {
		return fmt.Errorf(errors.FileCreateErrorTpl, filepath, err)
	}
	defer out.Close()

	_, err = io.Copy(out, resp.Body)
	if err != nil {
		return fmt.Errorf(errors.RequestCopyFailedErrorTpl, filepath, err)
	}

	slog.Debug("Download complete")

	return nil
}

func MoveFile(oldFilePath, newFilePath string) error {
	slog.Debug("Moving file from " + oldFilePath + " to " + newFilePath)
	if err := os.Rename(oldFilePath, newFilePath); err != nil {
		return fmt.Errorf(errors.FileMoveErrorTpl, oldFilePath, newFilePath, err)
	}
	slog.Debug("Move complete")
	return nil
}

func CopyFile(oldFilePath, newFilePath string) error {
	slog.Debug("Copying file from " + oldFilePath + " to " + newFilePath)

	sourceFileStat, err := os.Stat(oldFilePath)
	if err != nil {
		return fmt.Errorf(errors.FileStatErrorTpl, oldFilePath, err)
	}

	if !sourceFileStat.Mode().IsRegular() {
		return fmt.Errorf("%s is not a regular file", oldFilePath)
	}

	source, err := os.Open(oldFilePath)
	if err != nil {
		return fmt.Errorf(errors.FileOpenErrorTpl, oldFilePath, err)
	}
	defer source.Close()

	destination, err := os.Create(newFilePath)
	if err != nil {
		return fmt.Errorf(errors.FileCreateErrorTpl, newFilePath, err)
	}
	defer destination.Close()
	_, err = io.Copy(destination, source)
	if err != nil {
		return fmt.Errorf(errors.FileCopyErrorTpl, oldFilePath, newFilePath, err)
	}

	slog.Debug("Copy complete")

	return nil
}

func IsPathExist(path string) (bool, error) {
	_, err := os.Stat(path)
	if err != nil {
		if os.IsNotExist(err) {
			slog.Debug("Path does not exist: " + path)
			return false, nil
		}
		return false, fmt.Errorf("unable to check if path %s exists: %w", path, err)
	}
	return true, nil
}
