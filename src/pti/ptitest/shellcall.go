package ptitest

import (
	"github.com/stretchr/testify/assert"
	"testing"
)

type FakeShellCallError struct {
	OnCall int
	Err    error
}

type ShellCall struct {
	Binary         string
	ContainsArgs   []string
	EnvVars        []string
	InheritEnvVars bool
}

func (s *ShellCall) Equal(t *testing.T, name string, args []string, envVars []string, inheritEnvVars bool) {
	assert := assert.New(t)
	assert.Equal(s.Binary, name)
	for _, arg := range s.ContainsArgs {
		assert.Contains(args, arg)
	}
	for _, v := range s.EnvVars {
		assert.Contains(envVars, v)
	}
	assert.Equal(s.InheritEnvVars, inheritEnvVars)
}

var CommonShellCalls = map[string]*ShellCall{
	"aptUpdate": {
		Binary:         "apt-get",
		ContainsArgs:   []string{"update", "-q"},
		EnvVars:        nil,
		InheritEnvVars: true,
	},
	"aptClean": {
		Binary:         "apt-get",
		ContainsArgs:   []string{"clean", "-q"},
		EnvVars:        nil,
		InheritEnvVars: true,
	},
	"debCAUpdate": {
		Binary:         "update-ca-certificates",
		ContainsArgs:   []string{},
		EnvVars:        nil,
		InheritEnvVars: true,
	},
	"dnfClean": {
		Binary:         "dnf",
		ContainsArgs:   []string{"clean", "all"},
		EnvVars:        nil,
		InheritEnvVars: true,
	},
	"rhelCAUpdate": {
		Binary:         "update-ca-trust",
		ContainsArgs:   []string{},
		EnvVars:        nil,
		InheritEnvVars: true,
	},
}
