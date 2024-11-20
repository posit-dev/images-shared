class BakeryError(Exception):
    """Base class for all Bakery exceptions"""
    pass


class BakeryTemplatingError(BakeryError):
    """Error for templating issues"""
    pass


class BakeryPlanError(BakeryError):
    """Error for bake plan issues"""
    pass


class BakeryBuildError(BakeryError):
    """Error for build issues"""
    def __init__(self, exit_code: int = 1) -> None:
        self.exit_code = exit_code
        super().__init__()


class BakeryFileNotFoundError(BakeryError):
    """Error for an expected file or directory not being found"""
    pass


class BakeryGossError(BakeryError):
    """Error for dgoss issues"""
    def __init__(self, message: str, exit_code: int = 1) -> None:
        self.exit_code = exit_code
        super().__init__(message)


class BakeryConfigError(BakeryError):
    """Error for config/manifest issues"""
    pass
