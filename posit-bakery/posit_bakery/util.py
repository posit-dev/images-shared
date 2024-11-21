import os
from pathlib import Path
from shutil import which
from typing import Union

import git
from rich import print

from posit_bakery.error import BakeryFileNotFoundError


def find_bin(context: Union[str, bytes, os.PathLike], bin_name: str, bin_env_var: str):
    """Search for a binary as an env var, in the PATH, or in the project tools directory

    :param context: The project context to search for the binary in
    :param bin_name: The name of the binary to search for
    :param bin_env_var: The environment variable to search for
    """
    context = Path(context)
    if bin_env_var in os.environ:
        return os.environ[bin_env_var]
    elif which(bin_name) is not None:
        return None
    elif (context / "tools" / bin_name).is_file():
        return str(context / "tools" / bin_name)
    else:
        raise BakeryFileNotFoundError(
            f"Could not find {bin_name} in PATH or in project tools directory. "
            f"Either install {bin_name} or set the `{bin_env_var}` environment variable."
        )


def try_get_repo_url(context: Union[str, bytes, os.PathLike]) -> str:
    """Best guesses a repository URL for image labeling purposes based off the Git remote origin URL

    :param context: The repository root to check for a remote URL in
    :return: The guessed repository URL
    """
    url = "<REPLACE ME>"
    try:
        repo = git.Repo(context)
        # Use splitext since remotes should have `.git` as a suffix
        url = os.path.splitext(repo.remotes[0].config_reader.get("url"))[0]
        # If the URL is a git@ SSH URL, convert it to a https:// URL
        if url.startswith("git@"):
            url = url.removeprefix("git@")
            url = url.replace(":", "/")
        elif url.startswith("https://"):
            url = url.removeprefix("https://")
            url = url.split("@")[-1]
    except:  # noqa
        print("[bright_yellow][bold]WARNING:[/bold] Unable to determine repository name ")
    return url
