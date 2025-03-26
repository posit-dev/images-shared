from pydantic import BaseModel, ConfigDict


class ManifestGoss(BaseModel):
    model_config = ConfigDict(frozen=True)

    deps: str | bool | None = None  # defaults to version/deps
    path: str | None = None  # defaults to version/goss
    wait: int = 0
    command: str = "sleep infinity"
