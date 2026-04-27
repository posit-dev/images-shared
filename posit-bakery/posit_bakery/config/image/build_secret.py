from typing import Annotated

from pydantic import Field

from posit_bakery.config.shared import BakeryYAMLModel


class BuildSecret(BakeryYAMLModel):
    """A build secret passed to `docker buildx build` via `--secret id=<id>,env=<envVar>`.

    The secret is then available in the Containerfile by adding
    `--mount=type=secret,id=<id>` to a `RUN` instruction. The mounted file contains
    the value of the environment variable named by `envVar` at build time.
    """

    id: Annotated[
        str,
        Field(
            min_length=1,
            pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$",
            description="Secret ID referenced by `RUN --mount=type=secret,id=<id>` in the Containerfile. "
            "Restricted to alphanumerics, underscores, dots, and hyphens to prevent CLI argument injection.",
        ),
    ]
    envVar: Annotated[
        str,
        Field(
            min_length=1,
            pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
            description="Name of the environment variable whose value is mounted as the secret at build time. "
            "Must be a valid POSIX environment variable name.",
        ),
    ]

    def as_cli_option(self) -> str:
        """Return the value for docker's `--secret` flag, e.g. `id=github_token,env=GITHUB_TOKEN`."""
        return f"id={self.id},env={self.envVar}"

    def as_bake_json(self) -> dict[str, str]:
        """Return the per-target `secret` entry for a Docker Bake JSON plan.

        See https://docs.docker.com/build/bake/reference/#targetsecret for the schema.
        """
        return {"type": "env", "id": self.id, "env": self.envVar}
