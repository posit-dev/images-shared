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
	"strings"

	"github.com/spf13/afero"
)

// AppFs is the global file system object
var AppFs = afero.NewOsFs()

// hasSymlinkSupport checks if the file system supports symlinks.
// Currently, we only use the OsFs and BasePathFs file system which supports symlinks and the
// MemMapFs for tests which does not support symlinks.
func hasSymlinkSupport() (afero.Symlinker, bool) {
	_, ok := AppFs.(*afero.OsFs)
	if ok {
		return AppFs.(*afero.OsFs), true
	}
	_, ok = AppFs.(*afero.BasePathFs)
	if ok {
		return AppFs.(*afero.BasePathFs), true
	}

	return nil, false
}

// IsPathExist checks if a path exists.
// Returns true if the path exists, false otherwise.
// The check is symlink naive and will return true for symlinks.
func IsPathExist(path string) (bool, error) {
	return afero.Exists(AppFs, path)
}

// IsDir checks if a path is a directory.
// Returns true if the path is a directory, false otherwise.
// The check is symlink aware and will return false for symlinks.
func IsDir(path string) (bool, error) {
	exists, err := IsPathExist(path)
	if err != nil {
		return false, err
	}
	if !exists {
		return false, nil
	}

	var fileInfo os.FileInfo
	t, ok := hasSymlinkSupport()
	if ok {
		fileInfo, _, err = t.LstatIfPossible(path)
	} else {
		fileInfo, err = AppFs.Stat(path)
	}
	if err != nil {
		return false, fmt.Errorf("failed to stat file %s: %w", path, err)
	}

	if fileInfo.Mode().Type() == os.ModeSymlink {
		return false, nil
	}
	if fileInfo.IsDir() {
		return true, nil
	}

	return false, nil
}

// IsFile checks if a path is a file
// Returns true if the path is a file, false otherwise.
// The check is symlink aware and will return false for symlinks.
func IsFile(path string) (bool, error) {
	exists, err := IsPathExist(path)
	if err != nil {
		return false, err
	}
	if !exists {
		return false, nil
	}

	var fileInfo os.FileInfo
	t, ok := hasSymlinkSupport()
	if ok {
		fileInfo, _, err = t.LstatIfPossible(path)
	} else {
		fileInfo, err = AppFs.Stat(path)
	}
	if err != nil {
		return false, fmt.Errorf("failed to stat file %s: %w", path, err)
	}

	if fileInfo.IsDir() {
		return false, nil
	}
	if fileInfo.Mode().IsRegular() {
		return true, nil
	}

	return false, nil
}

// IsSymlink checks if a path is a symlink.
// Returns true if the path is a symlink, false otherwise.
func IsSymlink(path string) (bool, error) {
	exists, err := IsPathExist(path)
	if err != nil {
		return false, err
	}
	if !exists {
		return false, nil
	}

	var fileInfo os.FileInfo
	t, ok := hasSymlinkSupport()
	if ok {
		fileInfo, _, err = t.LstatIfPossible(path)
	} else {
		fileInfo, err = AppFs.Stat(path)
	}
	if err != nil {
		return false, fmt.Errorf("failed to stat file %s: %w", path, err)
	}

	if fileInfo.Mode().Type() == os.ModeSymlink {
		return true, nil
	}

	return false, nil
}

// CreateSymlink creates a symlink from src to dest.
// Returns an error if the symlink could not be created.
func CreateSymlink(oldName, newName string) error {
	slog.Debug("Creating symlink from " + oldName + " to " + newName)
	t, ok := hasSymlinkSupport()
	if ok {
		exists, err := IsPathExist(oldName)
		if err != nil {
			return fmt.Errorf("failed to check if source path '%s' exists: %w", oldName, err)
		}
		if !exists {
			return fmt.Errorf("source path '%s' does not exist", oldName)
		}

		err = t.SymlinkIfPossible(oldName, newName)
		if err != nil {
			return fmt.Errorf(
				"failed to create symlink from '%s' to '%s': %w",
				oldName,
				newName,
				err,
			)
		}
	} else {
		return fmt.Errorf("symlinks are not supported on this file system")
	}

	return nil
}

// InstallableDir checks if a directory is usable for installing a tool.
// To be installable, one of the following must be true about the directory:
//  1. Does not exist
//  2. Exists and is a directory, if empty is true the directory must be empty
func InstallableDir(path string, empty bool) error {
	if path == "" {
		return fmt.Errorf("installation path is required")
	}

	exists, err := IsPathExist(path)
	if err != nil {
		return fmt.Errorf("failed to check if installation path '%s' exists: %w", path, err)
	}
	if exists {
		isDir, err := IsDir(path)
		if err != nil {
			return fmt.Errorf(
				"failed to check if installation path '%s' is a directory: %w",
				path,
				err,
			)
		}
		if !isDir {
			return fmt.Errorf("installation path '%s' is not a directory", path)
		}

		isEmpty, err := afero.IsEmpty(AppFs, path)
		if err != nil {
			return fmt.Errorf("failed to check if installation path '%s' is empty: %w", path, err)
		}
		if !isEmpty && empty {
			return fmt.Errorf("installation path '%s' is not empty", path)
		}
	}

	return nil
}

// Stat returns the FileInfo structure describing the file at the given path.
// Returns an error if the file does not exist or if an error occurred during
// the stat operation. Symlinks are followed in Afero's default implementation.
func Stat(path string) (os.FileInfo, error) {
	i, err := AppFs.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("failed to stat file %s: %w", path, err)
	}

	return i, nil
}

// Create creates a file at the given path.
// Returns the file handle and an error if the file could not be created.
func Create(path string) (afero.File, error) {
	slog.Debug("Creating file: " + path)
	fh, err := AppFs.Create(path)
	if err != nil {
		return nil, fmt.Errorf("failed to create file %s: %w", path, err)
	}
	slog.Debug("File created")

	return fh, nil
}

// Open opens a file at the given path.
// Returns the file handle and an error if the file could not be opened.
func Open(path string) (afero.File, error) {
	fh, err := AppFs.Open(path)
	if err != nil {
		return nil, err
	}

	return fh, nil
}

// moveFile moves a single file from src to dest.
// Returns an error if the file could not be moved.
func moveFile(src, dest string) error {
	slog.Debug("Moving file from " + src + " to " + dest)
	if err := AppFs.Rename(src, dest); err != nil {
		return fmt.Errorf("failed to move file: %w", err)
	}
	slog.Debug("Move complete")

	return nil
}

// copyFile copies a single file from src to dest.
// Returns an error if the file could not be copied.
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

// moveDir moves a directory recursively from src to dest.
// Returns an error if the directory or any of its elements could not be moved.
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

// copyDir copies a directory recursively from src to dest.
// Returns an error if the directory or any of its elements could not be copied.
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

// Copy copies a file or directory from src to dest.
// Returns an error if the file or directory could not be copied.
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

// Move moves a file or directory from src to dest.
// Returns an error if the file or directory could not be moved.
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

// DownloadFile downloads a file from a URL and saves it to the given filepath.
// Returns an error if the file could not be downloaded or saved.
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

// ExtractTarGz extracts a tar.gz archive to the given destination.
// Returns an error if the archive could not be extracted.
//
//nolint:cyclop
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
		// FIXME: This is a low security risk for decompression attacks and potential filemode conversion overflow
		switch header.Typeflag {
		case tar.TypeDir:
			//nolint:gosec
			if err := AppFs.MkdirAll(target, os.FileMode(header.Mode)); err != nil {
				return fmt.Errorf("failed to create directory %s: %w", target, err)
			}
		case tar.TypeReg:
			//nolint:gosec
			fh, err := AppFs.OpenFile(target, os.O_CREATE|os.O_RDWR, os.FileMode(header.Mode))
			if err != nil {
				return fmt.Errorf("failed to create file %s: %w", target, err)
			}
			defer fh.Close()
			//nolint:gosec
			if _, err := io.Copy(fh, tr); err != nil {
				return fmt.Errorf("failed to copy file %s: %w", target, err)
			}
		}
	}

	return nil
}
