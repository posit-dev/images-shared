package syspkg

import (
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"pti/system/file"
	"testing"
)

func TestPackageListFileToSlice(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	tests := []struct {
		name           string
		contents       string
		createFile     bool
		want           []string
		wantErr        bool
		wantErrMessage string
	}{
		{
			name:       "empty file",
			contents:   "",
			createFile: true,
			want:       nil,
			wantErr:    false,
		},
		{
			name:       "single line",
			contents:   "line1",
			createFile: true,
			want:       []string{"line1"},
			wantErr:    false,
		},
		{
			name:       "multiple lines",
			contents:   "line1\nline2\nline3",
			createFile: true,
			want:       []string{"line1", "line2", "line3"},
			wantErr:    false,
		},
		{
			name:           "file does not exist",
			createFile:     false,
			wantErr:        true,
			wantErrMessage: "does not exist",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := file.AppFs
			file.AppFs = afero.NewMemMapFs()
			defer func() {
				file.AppFs = oldFs
			}()

			tmpDir, err := afero.TempDir(file.AppFs, "", "package_list_to_slice")
			f := tmpDir + "/file.txt"
			if tt.createFile {
				fh, err := file.AppFs.Create(f)
				require.Nil(err, "os.Create() error = %v", err)

				_, err = fh.WriteString(tt.contents)
				require.Nil(err, "f.WriteString() error = %v", err)
				defer fh.Close()
			}

			got, err := packageListFileToSlice(f)
			if tt.wantErr {
				require.NotNil(err, "packageListFileToSlice() error = %v", err)
				assert.ErrorContains(err, tt.wantErrMessage, "packageListFileToSlice() error message = %v, want %v", err.Error(), tt.wantErrMessage)
			} else {
				assert.Nil(err, "packageListFileToSlice() error = %v", err)
				assert.Equal(tt.want, got, "packageListFileToSlice() got = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestPackageList_GetPackagesFromPackageListFiles(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	tests := []struct {
		name                    string
		packageListFileContents []string
		want                    []string
	}{
		{
			name:                    "No files",
			packageListFileContents: []string{},
			want:                    nil,
		},
		{
			name: "Single file, single line",
			packageListFileContents: []string{
				"line1",
			},
			want: []string{"line1"},
		},
		{
			name: "Single file, multiple lines",
			packageListFileContents: []string{
				"line1\nline2\nline3",
			},
			want: []string{"line1", "line2", "line3"},
		},
		{
			name: "Multiple files, some empty",
			packageListFileContents: []string{
				"line1",
				"",
				"line2\nline3",
			},
			want: []string{"line1", "line2", "line3"},
		},
		{
			name: "Multiple files, single line",
			packageListFileContents: []string{
				"line1",
				"line2",
				"line3",
			},
			want: []string{"line1", "line2", "line3"},
		},
		{
			name: "Multiple files, multiple lines",
			packageListFileContents: []string{
				"line1\nline2",
				"line3\nline4\nline5",
				"line6",
				"line7\nline8\nline9\nline10",
			},
			want: []string{"line1", "line2", "line3", "line4", "line5", "line6", "line7", "line8", "line9", "line10"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := file.AppFs
			file.AppFs = afero.NewMemMapFs()
			defer func() {
				file.AppFs = oldFs
			}()

			tmpDir, err := afero.TempDir(file.AppFs, "", "get_packages_from_package_lists")
			require.NoError(err, "afero.TempDir() error = %v", err)

			l := PackageList{
				PackageListFiles: []string{},
			}
			for _, line := range tt.packageListFileContents {
				f, err := afero.TempFile(file.AppFs, tmpDir, "file*.txt")
				require.NoError(err, "os.Create() error = %v", err)

				_, err = f.WriteString(line)
				require.Nil(err, "f.WriteString() error = %v", err)
				defer f.Close()

				l.PackageListFiles = append(l.PackageListFiles, f.Name())
			}

			got, err := l.GetPackagesFromPackageListFiles()
			require.Nil(err, "PackageList.GetPackagesFromPackageListFiles() error = %v", err)
			assert.Equal(tt.want, got, "PackageList.GetPackagesFromPackageListFiles() got = %v, want %v", got, tt.want)
		})
	}
}

func TestPackageList_GetPackages(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	tests := []struct {
		name                    string
		packagesDirectList      []string
		packageListFileContents []string
		want                    []string
	}{
		{
			name:                    "No packages or files",
			packagesDirectList:      []string{},
			packageListFileContents: []string{},
			want:                    []string{},
		},
		{
			name:                    "One package, no files",
			packagesDirectList:      []string{"package1"},
			packageListFileContents: []string{},
			want:                    []string{"package1"},
		},
		{
			name:                    "Multiple packages, no files",
			packagesDirectList:      []string{"package1", "package2", "package3"},
			packageListFileContents: []string{},
			want:                    []string{"package1", "package2", "package3"},
		},
		{
			name:               "No packages, single file, single line",
			packagesDirectList: []string{},
			packageListFileContents: []string{
				"line1",
			},
			want: []string{"line1"},
		},
		{
			name:               "One package and single file, single line",
			packagesDirectList: []string{"package1"},
			packageListFileContents: []string{
				"line1",
			},
			want: []string{"package1", "line1"},
		},
		{
			name:               "Multiple packages and single file, single line",
			packagesDirectList: []string{"package1", "package2", "package3"},
			packageListFileContents: []string{
				"line1",
			},
			want: []string{"package1", "package2", "package3", "line1"},
		},
		{
			name:               "No packages and single file, multiple lines",
			packagesDirectList: []string{},
			packageListFileContents: []string{
				"line1\nline2\nline3",
			},
			want: []string{"line1", "line2", "line3"},
		},
		{
			name:               "One package and single file, multiple lines",
			packagesDirectList: []string{"package1"},
			packageListFileContents: []string{
				"line1\nline2\nline3",
			},
			want: []string{"package1", "line1", "line2", "line3"},
		},
		{
			name:               "Multiple packages and single file, multiple lines",
			packagesDirectList: []string{"package1", "package2", "package3"},
			packageListFileContents: []string{
				"line1\nline2\nline3",
			},
			want: []string{"package1", "package2", "package3", "line1", "line2", "line3"},
		},
		{
			name:               "No packages and multiple files, some empty",
			packagesDirectList: []string{},
			packageListFileContents: []string{
				"line1",
				"",
				"line2\nline3",
			},
			want: []string{"line1", "line2", "line3"},
		},
		{
			name:               "One package and multiple files, single line",
			packagesDirectList: []string{"package1"},
			packageListFileContents: []string{
				"line1",
				"line2",
				"line3",
			},
			want: []string{"package1", "line1", "line2", "line3"},
		},
		{
			name:               "Multiple packages and multiple files, multiple lines",
			packagesDirectList: []string{"package1", "package2", "package3"},
			packageListFileContents: []string{
				"line1\nline2",
				"line3\nline4\nline5",
				"line6",
				"line7\nline8\nline9\nline10",
			},
			want: []string{
				"package1",
				"package2",
				"package3",
				"line1",
				"line2",
				"line3",
				"line4",
				"line5",
				"line6",
				"line7",
				"line8",
				"line9",
				"line10",
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			oldFs := file.AppFs
			file.AppFs = afero.NewMemMapFs()
			defer func() {
				file.AppFs = oldFs
			}()

			tmpDir, err := afero.TempDir(file.AppFs, "", "get_packages_from_package_lists")
			require.NoError(err, "afero.TempDir() error = %v", err)

			l := PackageList{
				Packages:         tt.packagesDirectList,
				PackageListFiles: []string{},
			}

			for _, line := range tt.packageListFileContents {
				f, err := afero.TempFile(file.AppFs, tmpDir, "file*.txt")
				require.NoError(err, "os.Create() error = %v", err)

				_, err = f.WriteString(line)
				require.Nil(err, "f.WriteString() error = %v", err)
				defer f.Close()

				l.PackageListFiles = append(l.PackageListFiles, f.Name())
			}

			got, err := l.GetPackages()
			require.NoError(err, "PackageList.GetPackages() error = %v", err)
			assert.Equal(tt.want, got, "PackageList.GetPackages() got = %v, want %v", got, tt.want)
		})
	}
}
