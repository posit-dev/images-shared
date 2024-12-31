package ptitest

import (
	"github.com/spf13/afero"
	"pti/system/file"
)

func ResetAppFs() {
	// Reset the AppFs to the original filesystem
	file.AppFs = afero.NewOsFs()
}
