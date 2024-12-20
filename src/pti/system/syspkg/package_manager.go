package syspkg

import (
	"bufio"
	"fmt"
	"pti/system/file"
)

type PackageList struct {
	Packages         []string
	PackageListFiles []string
	LocalPackages    []string
}

// TODO: Add an "IsInstalled" method for Package Managers

type SystemPackageManager interface {
	GetBin() string
	GetPackageExtension() string
	Install(list *PackageList) error
	Remove(list *PackageList) error
	Update() error
	Upgrade(fullUpgrade bool) error
	Clean() error
}

func packageListFileToSlice(path string) ([]string, error) {
	exists, err := file.IsPathExist(path)
	if err != nil {
		return nil, fmt.Errorf("failed to check if '%s' exists: %w", path, err)
	}
	if !exists {
		return nil, fmt.Errorf("file '%s' does not exist", path)
	}

	fh, err := file.Open(path)
	if err != nil {
		return nil, fmt.Errorf("failed to open '%s': %w", path, err)
	}
	defer fh.Close()

	var lines []string
	scanner := bufio.NewScanner(fh)
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("error occurred while reading %s: %w", path, err)
	}

	return lines, nil
}

func (l *PackageList) GetPackagesFromPackageListFiles() ([]string, error) {
	var pkg []string
	for _, f := range l.PackageListFiles {
		lines, err := packageListFileToSlice(f)
		if err != nil {
			return nil, err
		}
		pkg = append(pkg, lines...)
	}
	return pkg, nil
}

func (l *PackageList) GetPackages() ([]string, error) {
	pkg := l.Packages
	filePkg, err := l.GetPackagesFromPackageListFiles()
	if err != nil {
		return nil, err
	}
	pkg = append(pkg, filePkg...)

	return pkg, nil
}
