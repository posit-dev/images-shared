package tools

type ToolManager interface {
	Installed() (bool, error)
	Install() error
	Update() error
	Remove() error
}

type ToolPackageManager interface {
	InstallPackage(string, []string) error
	UpdatePackage(string, []string) error
	RemovePackage(string, []string) error
}
