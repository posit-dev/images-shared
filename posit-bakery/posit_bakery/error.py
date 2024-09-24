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
    pass
