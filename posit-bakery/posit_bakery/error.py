class BakeryError(Exception):
    pass


class BakeryTemplatingError(BakeryError):
    pass


class BakeryPlanError(BakeryError):
    pass


class BakeryBuildError(BakeryError):
    pass


class BakeryFileNotFoundError(BakeryError):
    pass


class BakeryGossError(BakeryError):
    def __init__(self, message, exit_code=1):
        self.exit_code = exit_code
        super().__init__(message)


class BakeryConfigError(BakeryError):
    pass
