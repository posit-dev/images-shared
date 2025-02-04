class BakeryError(Exception):
    """Base class for all Bakery exceptions"""

    def __init__(self, message: str = None, parent: Exception = None) -> None:
        super().__init__(message)
        self.parent = parent


class BakeryConfigError(BakeryError):
    """Error for config/manifest issues"""

    pass


class BakeryImageNotFoundError(BakeryConfigError):
    """Error for an expected image not being found"""

    pass


class BakeryBadImageError(BakeryConfigError):
    """Error for an image being malformed or invalid"""

    pass


class BakeryTemplatingError(BakeryError):
    """Error for template rendering issues"""

    pass


class BakeryDockerError(BakeryError):
    """Error for Docker issues"""

    pass


class BakeryPlanError(BakeryDockerError):
    """Error for bake plan issues"""

    pass


class BakeryBuildError(BakeryDockerError):
    """Error for build issues"""

    def __init__(self, message: str = None, stdout: bytes = None, stderr: bytes = None, exit_code: int = 1) -> None:
        super().__init__(message, None)
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class BakeryFileError(BakeryError):
    """Generic error for file/directory issues"""

    pass


class BakeryFileNotFoundError(BakeryFileError):
    """Error for an expected file not being found"""

    pass


class BakeryBadContextError(BakeryFileError):
    """Error for an expected context being malformed or invalid"""

    pass


class BakeryContextDirectoryNotFoundError(BakeryFileError):
    """Error for an expected context directory not being found"""

    pass


class BakeryConfigNotFoundError(BakeryFileError):
    """Error for an expected config file not being found"""

    pass


class BakeryContainerfileNotFoundError(BakeryFileError):
    """Error for an expected Containerfile not being found"""

    pass


class BakeryToolError(BakeryError):
    """Generic error for external tool issues"""

    pass


class BakeryToolNotFoundError(BakeryToolError):
    """Error for an expected tool not being found"""

    def __init__(self, message: str = None, tool_name: str = None) -> None:
        super().__init__(message, None)
        self.tool_name = tool_name


class BakeryGossError(BakeryToolError):
    """Error for dgoss issues"""

    def __init__(self, message: str = None, stdout: bytes = None, stderr: bytes = None, exit_code: int = 1) -> None:
        super().__init__(message, None)
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
