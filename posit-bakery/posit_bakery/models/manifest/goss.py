from pydantic import BaseModel


# TODO: Write custom validators as needed when performing the translation
# from the TOML document to the TargetBuild object
class ManifestGoss(BaseModel):
    deps: str = None  # defaults to version/deps
    path: str = None  # defaults to version/goss
    wait: int = 0
    command: str = "sleep infinity"
