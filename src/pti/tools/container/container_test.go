package container

import (
	"fmt"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"pti/system"
	"pti/system/syspkg"
	"testing"
)

func TestBootstrap(t *testing.T) {
	require := require.New(t)
	assert := assert.New(t)

	// Define systems to test against
	debSystem := system.LocalSystem{
		Vendor:         "ubuntu",
		Version:        "22.04",
		Arch:           "amd64",
		PackageManager: syspkg.NewAptManager(),
	}
	rhelSystem := system.LocalSystem{
		Vendor:         "rocklinux",
		Version:        "8",
		Arch:           "amd64",
		PackageManager: syspkg.NewDnfManager(),
	}

	// Define calls
	type shellCall struct {
		binary         string
		containsArgs   []string
		envVars        []string
		inheritEnvVars bool
	}

	debCAInstall := shellCall{
		binary:         "apt",
		containsArgs:   []string{"install", "-y", "-q", "ca-certificates"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	debCAUpdate := shellCall{
		binary:         "update-ca-certificates",
		containsArgs:   []string{},
		envVars:        nil,
		inheritEnvVars: true,
	}

	rhelCAInstall := shellCall{
		binary:         "dnf",
		containsArgs:   []string{"-y", "-q", "install", "ca-certificates"},
		envVars:        nil,
		inheritEnvVars: true,
	}
	rhelCAUpdate := shellCall{
		binary:         "update-ca-trust",
		containsArgs:   []string{},
		envVars:        nil,
		inheritEnvVars: true,
	}

	tests := []struct {
		name                  string
		system                system.LocalSystem
		expectedNewShellCalls []shellCall
		runErr                error
		runErrOnCall          int
		wantErr               bool
		wantErrMessage        string
	}{
		{
			name:   "success debian-based",
			system: debSystem,
			expectedNewShellCalls: []shellCall{
				debCAInstall,
				debCAUpdate,
			},
			runErr:       nil,
			runErrOnCall: 0,
			wantErr:      false,
		},
		{
			name:   "success rhel-based",
			system: rhelSystem,
			expectedNewShellCalls: []shellCall{
				rhelCAInstall,
				rhelCAUpdate,
			},
			runErr:       nil,
			runErrOnCall: 0,
			wantErr:      false,
		},
		{
			name:   "failed install debian-based",
			system: debSystem,
			expectedNewShellCalls: []shellCall{
				debCAInstall,
			},
			runErr:         fmt.Errorf("install error"),
			runErrOnCall:   1,
			wantErr:        true,
			wantErrMessage: "failed to install ca-certificates",
		},
		{
			name:   "failed install rhel-based",
			system: rhelSystem,
			expectedNewShellCalls: []shellCall{
				rhelCAInstall,
			},
			runErr:         fmt.Errorf("install error"),
			runErrOnCall:   1,
			wantErr:        true,
			wantErrMessage: "failed to install ca-certificates",
		},
		{
			name:   "failed update debian-based",
			system: debSystem,
			expectedNewShellCalls: []shellCall{
				debCAInstall,
				debCAUpdate,
			},
			runErr:         fmt.Errorf("update error"),
			runErrOnCall:   2,
			wantErr:        true,
			wantErrMessage: "failed to update CA certificates",
		},
		{
			name:   "failed update rhel-based",
			system: rhelSystem,
			expectedNewShellCalls: []shellCall{
				rhelCAInstall,
				rhelCAUpdate,
			},
			runErr:         fmt.Errorf("update error"),
			runErrOnCall:   2,
			wantErr:        true,
			wantErrMessage: "failed to update CA certificates",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {

		})
	}
}
