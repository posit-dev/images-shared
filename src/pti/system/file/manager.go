package file

import (
	"archive/tar"
	"bufio"
	"compress/gzip"
	"fmt"
	"github.com/spf13/afero"
	"io"
	"log/slog"
	"net/http"
	"os"
	"strings"
)

var AppFs = afero.NewOsFs()

func IsPathExist(path string) (bool, error) {
	return afero.Exists(AppFs, path)
}

func Stat(path string) (os.FileInfo, error) {
	i, err := AppFs.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("failed to stat file %s: %w", path, err)
	}
	return i, nil
}

func Create(path string) (afero.File, error) {
	slog.Debug("Creating file: " + path)
	fh, err := AppFs.Create(path)
	if err != nil {
		return nil, fmt.Errorf("failed to create file %s: %w", path, err)
	}
	slog.Debug("File created")
	return fh, nil
}

func Open(path string) (afero.File, error) {
	fh, err := AppFs.Open(path)
	if err != nil {
		return nil, err
	}
	return fh, nil
}

func moveFile(src, dest string) error {
	slog.Debug("Moving file from " + src + " to " + dest)
	if err := AppFs.Rename(src, dest); err != nil {
		return fmt.Errorf("failed to move file: %w", err)
	}
	slog.Debug("Move complete")
	return nil
}

func copyFile(src, dest string) error {
	slog.Debug("Copying file from " + src + " to " + dest)

	sourceFileStat, err := AppFs.Stat(src)
	if err != nil {
		return fmt.Errorf("failed to stat file %s during copy: %w", src, err)
	}

	if !sourceFileStat.Mode().IsRegular() {
		return fmt.Errorf("%s is not a regular file", src)
	}

	sourceFh, err := Open(src)
	if err != nil {
		return fmt.Errorf("failed to open copy source file '%s': %w", src, err)
	}

	destinationFh, err := Create(dest)
	if err != nil {
		return fmt.Errorf("failed to create copy destination file '%s': %w", dest, err)
	}
	defer destinationFh.Close()

	_, err = io.Copy(destinationFh, sourceFh)
	if err != nil {
		return fmt.Errorf("failed to copy '%s' to '%s': %w", src, dest, err)
	}

	slog.Debug("Copy complete")

	return nil
}

func moveDir(src, dest string) error {
	src = strings.TrimSuffix(src, "/")
	dest = strings.TrimSuffix(dest, "/")

	slog.Debug("Moving directory from " + src + " to " + dest)
	err := afero.Walk(AppFs, src, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return fmt.Errorf("failed to walk directory '%s': %w", src, err)
		}
		relPath := strings.TrimPrefix(path, src)
		destPath := dest + "/" + relPath
		if info.IsDir() {
			err := AppFs.MkdirAll(destPath, info.Mode())
			if err != nil {
				return fmt.Errorf("failed to create directory '%s': %w", destPath, err)
			}
		} else {
			err := copyFile(path, destPath)
			if err != nil {
				return fmt.Errorf("failed to copy file '%s' to '%s': %w", path, destPath, err)
			}
		}
		return nil
	})
	if err != nil {
		return fmt.Errorf("failed to move directory '%s' to '%s': %w", src, dest, err)
	}
	err = AppFs.RemoveAll(src)
	if err != nil {
		return fmt.Errorf("failed to remove source directory '%s' after move: %w", src, err)
	}
	slog.Debug("Move complete")
	return nil
}

func copyDir(src, dest string) error {
	src = strings.TrimSuffix(src, "/")
	dest = strings.TrimSuffix(dest, "/")

	slog.Debug("Moving directory from " + src + " to " + dest)
	err := afero.Walk(AppFs, src, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return fmt.Errorf("failed to walk directory '%s': %w", src, err)
		}
		relPath := strings.TrimPrefix(path, src)
		destPath := dest + "/" + relPath
		if info.IsDir() {
			err := AppFs.MkdirAll(destPath, info.Mode())
			if err != nil {
				return fmt.Errorf("failed to create directory '%s': %w", destPath, err)
			}
		} else {
			err := copyFile(path, destPath)
			if err != nil {
				return fmt.Errorf("failed to copy file '%s' to '%s': %w", path, destPath, err)
			}
		}
		return nil
	})
	if err != nil {
		return fmt.Errorf("failed to move directory '%s' to '%s': %w", src, dest, err)
	}
	slog.Debug("Copy complete")
	return nil
}

func Copy(src, dest string) error {
	srcStat, err := Stat(src)
	if err != nil {
		return fmt.Errorf("failed to stat source file '%s': %w", src, err)
	}

	if srcStat.IsDir() {
		return copyDir(src, dest)
	} else {
		return copyFile(src, dest)
	}
}

func Move(src, dest string) error {
	srcStat, err := Stat(src)
	if err != nil {
		return fmt.Errorf("failed to stat source file '%s': %w", src, err)
	}

	if srcStat.IsDir() {
		return moveDir(src, dest)
	} else {
		return moveFile(src, dest)
	}
}

func DownloadFile(url string, filepath string) error {
	slog.Debug("Downloading file from " + url + " to " + filepath)

	request, _ := http.NewRequest(http.MethodGet, url, nil)
	client := &http.Client{}

	resp, err := client.Do(request)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("failed to download file with status '%s'", resp.Status)
	}

	newFh, err := Create(filepath)
	if err != nil {
		return fmt.Errorf("failed to save download to file '%s': %w", filepath, err)
	}
	defer newFh.Close()

	_, err = io.Copy(newFh, resp.Body)
	if err != nil {
		return err
	}

	slog.Debug("Download complete")

	return nil
}

func ExtractTarGz(archive, dest string) error {
	slog.Info("Extracting tar.gz file " + archive + " to " + dest)

	fh, err := Open(archive)
	if err != nil {
		return fmt.Errorf("failed to open %s for extraction: %w", archive, err)
	}
	defer fh.Close()
	reader := bufio.NewReader(fh)

	gzr, err := gzip.NewReader(reader)
	if err != nil {
		return fmt.Errorf("failed to create gzip reader for %s: %w", archive, err)
	}

	tr := tar.NewReader(gzr)
	for {
		header, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("failed to read tar header for %s: %w", archive, err)
		}

		target := dest + "/" + header.Name
		switch header.Typeflag {
		case tar.TypeDir:
			if err := AppFs.MkdirAll(target, os.FileMode(header.Mode)); err != nil {
				return fmt.Errorf("failed to create directory %s: %w", target, err)
			}
		case tar.TypeReg:
			fh, err := AppFs.OpenFile(target, os.O_CREATE|os.O_RDWR, os.FileMode(header.Mode))
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
