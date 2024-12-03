package syspkg

import (
	"bufio"
	"fmt"
	"pti/system/file"
)

type PackageList struct {
	Packages         []string
	PackageListFiles []*file.File
	LocalPackages    []*file.File
}

type SystemPackageManager interface {
	GetBin() string
	Install(list *PackageList) error
	Remove(list *PackageList) error
	Update() error
	Upgrade(fullUpgrade bool) error
	Clean() error
}

func packageListFileToSlice(f *file.File) ([]string, error) {
	if f == nil {
		return nil, fmt.Errorf("given package list file is nil")
	}

	fh, err := f.Open()
	if err != nil {
		return nil, fmt.Errorf("failed to open %s: %w", f.Path, err)
	}
	defer fh.Close()

	var lines []string
	scanner := bufio.NewScanner(fh)
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("error occurred while reading %s: %w", f.Path, err)
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
