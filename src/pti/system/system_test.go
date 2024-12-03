package system

import (
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/zcalusic/sysinfo"
	"os/user"
	"testing"
)

type MockOSInfo struct {
	Vendor       string
	Version      string
	Architecture string
}

type MockSysInfo struct {
	OS MockOSInfo
}

func TestGetLocalSystem(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	tests := []struct {
		name      string
		sysInfo   MockSysInfo
		wantPmBin string
		wantErr   bool
	}{
		{
			name: "Test Ubuntu",
			sysInfo: MockSysInfo{
				OS: MockOSInfo{
					Vendor: "ubuntu",
				},
			},
			wantPmBin: "apt",
			wantErr:   false,
		},
		{
			name: "Test CentOS",
			sysInfo: MockSysInfo{
				OS: MockOSInfo{
					Vendor: "rockylinux",
				},
			},
			wantPmBin: "dnf",
			wantErr:   false,
		},
		{
			name: "Test Unsupported OS",
			sysInfo: MockSysInfo{
				OS: MockOSInfo{
					Vendor: "unsupported",
				},
			},
			wantPmBin: "",
			wantErr:   true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			old := sysInfo
			defer func() {
				sysInfo = old
			}()
			sysInfo = func() sysinfo.SysInfo {
				return sysinfo.SysInfo{
					OS: sysinfo.OS{
						Vendor:       tt.sysInfo.OS.Vendor,
						Version:      tt.sysInfo.OS.Version,
						Architecture: tt.sysInfo.OS.Architecture,
					},
				}
			}
			ls, err := GetLocalSystem()

			require.Equal(tt.wantErr, err != nil, "GetLocalSystem() error = %v, wantErr %v", err, tt.wantErr)
			if err == nil {
				assert.Equal(tt.wantPmBin, ls.PackageManager.GetBin(), "PackageManager.GetBin() = %v, want %v", ls.PackageManager.GetBin(), tt.wantPmBin)
			}
		})
	}
}

type MockUser struct {
	Uid string
}

func TestRequireSudo(t *testing.T) {
	tests := []struct {
		name        string
		currentUser MockUser
		wantErr     bool
	}{
		{
			name: "Test as user",
			currentUser: MockUser{
				Uid: "1000",
			},
			wantErr: true,
		},
		{
			name: "Test as root",
			currentUser: MockUser{
				Uid: "0",
			},
			wantErr: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			old := currentUser
			defer func() {
				currentUser = old
			}()
			currentUser = func() (*user.User, error) {
				return &user.User{
					Uid: tt.currentUser.Uid,
				}, nil
			}
			err := RequireSudo()
			if (err != nil) != tt.wantErr {
				t.Errorf("RequireSudo() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}
