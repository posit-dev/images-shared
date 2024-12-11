package tools

type ToolManager interface {
	Installed() (bool, error)
	Install() error
	Update() error
	Remove() error
}
