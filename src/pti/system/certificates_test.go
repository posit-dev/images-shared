package system

import (
	"fmt"
	"github.com/stretchr/testify/assert"
	commandMock "pti/mocks/pti/system/command"
	"pti/system/command"
	"testing"
)

func Test_UpdateCACertificates(t *testing.T) {
	assert := assert.New(t)

	tests := []struct {
		name           string
		localSystem    LocalSystem
		wantBin        string
		runErr         error
		wantErr        bool
		wantErrMessage string
	}{
		{
			name: "Test ubuntu",
			localSystem: LocalSystem{
				Vendor: "ubuntu",
			},
			wantBin: "update-ca-certificates",
			runErr:  nil,
			wantErr: false,
		},
		{
			name: "Test rockylinux",
			localSystem: LocalSystem{
				Vendor: "rockylinux",
			},
			wantBin: "update-ca-trust",
			runErr:  nil,
			wantErr: false,
		},
		{
			name: "Test unsupported os",
			localSystem: LocalSystem{
				Vendor: "unsupported",
			},
			wantBin:        "",
			runErr:         nil,
			wantErr:        true,
			wantErrMessage: "unsupported OS",
		},
		{
			name: "Test run error",
			localSystem: LocalSystem{
				Vendor: "ubuntu",
			},
			wantBin:        "update-ca-certificates",
			runErr:         fmt.Errorf("command failed"),
			wantErr:        true,
			wantErrMessage: "failed to update CA certificates",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			old := command.NewShellCommand
			defer func() {
				command.NewShellCommand = old
			}()
			command.NewShellCommand = func(name string, args []string, envVars []string, inheritEnvVars bool) command.ShellCommandRunner {
				assert.Equal(tt.wantBin, name, "binary name = %v, want binary %v", name, tt.wantBin)

				mockShellCommand := commandMock.NewMockShellCommandRunner(t)
				mockShellCommand.EXPECT().Run().Return(tt.runErr)
				return mockShellCommand
			}

			err := tt.localSystem.UpdateCACertificates()
			if tt.wantErr {
				assert.Error(err, "UpdateCACertificates() error = %v, wantErr %v", err, tt.wantErr)
				assert.ErrorContains(err, tt.wantErrMessage, "UpdateCACertificates() error = %v, wantErrMessage %v", err, tt.wantErrMessage)
			} else {
				assert.NoError(err, "UpdateCACertificates() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}
