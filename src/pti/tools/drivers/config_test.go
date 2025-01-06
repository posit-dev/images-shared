package drivers

import (
	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"pti/ptitest"
	"pti/system"
	"pti/system/file"
	"testing"
)

func Test_CopyProDriversOdbcInstIni(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name           string
		setupFs        func(fs afero.Fs)
		validateFs     func(fs afero.Fs)
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "success",
			setupFs: func(fs afero.Fs) {
				fh, err := fs.Create(systemOdbcInstIniPath)
				require.NoError(err)
				_, err = fh.WriteString("original definition")
				require.NoError(err)

				fh, err = fs.Create(positDriversOdbcInstIniPath)
				require.NoError(err)
				_, err = fh.WriteString("new definition")
				require.NoError(err)
			},
			validateFs: func(fs afero.Fs) {
				exists, err := afero.Exists(file.AppFs, systemOdbcInstIniPath)
				require.NoError(err)
				assert.True(exists)

				exists, err = afero.Exists(file.AppFs, positDriversOdbcInstIniPath)
				require.NoError(err)
				assert.True(exists)

				exists, err = afero.Exists(file.AppFs, systemOdbcInstIniPath+".bak")
				require.NoError(err)
				assert.True(exists)

				// Check that the odbcinst.ini file was updated
				contents, err := afero.ReadFile(file.AppFs, systemOdbcInstIniPath)
				require.NoError(err)
				assert.Equal("new definition", string(contents))

				// Check that the odbcinst.ini.bak file was saved
				contents, err = afero.ReadFile(file.AppFs, systemOdbcInstIniPath+".bak")
				require.NoError(err)
				assert.Equal("original definition", string(contents))
			},
			wantErr: false,
		},
		{
			name: "success no backup odbcinst.ini",
			setupFs: func(fs afero.Fs) {
				fh, err := fs.Create(positDriversOdbcInstIniPath)
				require.NoError(err)
				_, err = fh.WriteString("new definition")
				require.NoError(err)
			},
			validateFs: func(fs afero.Fs) {
				exists, err := afero.Exists(file.AppFs, systemOdbcInstIniPath)
				require.NoError(err)
				assert.True(exists)

				exists, err = afero.Exists(file.AppFs, positDriversOdbcInstIniPath)
				require.NoError(err)
				assert.True(exists)

				exists, err = afero.Exists(file.AppFs, systemOdbcInstIniPath+".bak")
				require.NoError(err)
				assert.False(exists)

				// Check that the odbcinst.ini file was updated
				contents, err := afero.ReadFile(file.AppFs, systemOdbcInstIniPath)
				require.NoError(err)
				assert.Equal("new definition", string(contents))
			},
			wantErr: false,
		},
		{
			name: "failed no odbcinst.ini.sample",
			setupFs: func(fs afero.Fs) {
				fh, err := fs.Create(systemOdbcInstIniPath)
				require.NoError(err)
				_, err = fh.WriteString("original definition")
				require.NoError(err)
			},
			validateFs: func(fs afero.Fs) {
				exists, err := afero.Exists(file.AppFs, systemOdbcInstIniPath)
				require.NoError(err)
				assert.True(exists)

				exists, err = afero.Exists(file.AppFs, systemOdbcInstIniPath+".bak")
				require.NoError(err)
				assert.False(exists)

				// Check that the odbcinst.ini file was updated
				contents, err := afero.ReadFile(file.AppFs, systemOdbcInstIniPath)
				require.NoError(err)
				assert.Equal("original definition", string(contents))
			},
			wantErr:        true,
			wantErrMessage: "odbcinst.ini.sample does not exist",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			file.AppFs = afero.NewMemMapFs()
			t.Cleanup(ptitest.ResetAppFs)

			tt.setupFs(file.AppFs)

			m := NewManager(&system.LocalSystem{}, "")

			err := m.CopyProDriversOdbcInstIni()
			if tt.wantErr {
				require.Error(err)
				assert.ErrorContains(err, tt.wantErrMessage)
			} else {
				require.NoError(err)
			}

			tt.validateFs(file.AppFs)
		})
	}
}
