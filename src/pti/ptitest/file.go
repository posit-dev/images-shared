package ptitest

import (
	"pti/system/file"

	"github.com/spf13/afero"
)

func ResetAppFs() {
	// Reset the AppFs to the original filesystem
	file.AppFs = afero.NewOsFs()
}
