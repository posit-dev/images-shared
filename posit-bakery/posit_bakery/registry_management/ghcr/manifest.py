import base64
import json
import logging
import os

import requests
from pydantic import ValidationError
from python_on_whales.components.buildx.imagetools.models import Manifest

from posit_bakery.registry_management.ghcr.clean import REGISTRY_PATTERN

log = logging.getLogger(__name__)


class GHCRManifestClient:
    """Read-only client for the GHCR registry v2 API (`ghcr.io`).

    Distinct from :class:`GHCRClient`, which talks to the GHCR Packages API
    (`api.github.com`): that API has no size field on a package version at all, while the
    registry v2 API's manifest response carries real per-layer sizes.
    """

    BASE_URL = "https://ghcr.io"

    def __init__(self, token: str | None = None) -> None:
        token = token or os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError(
                "A GitHub token with 'read:packages' scope is required, via the 'token' "
                "argument or the GITHUB_TOKEN environment variable."
            )
        credentials = base64.b64encode(token.encode()).decode()
        self._headers = {
            "Authorization": f"Bearer {credentials}",
            "Accept": "application/vnd.oci.image.manifest.v1+json",
        }

    def get_manifest(self, ref: str) -> Manifest | None:
        """Fetch the manifest for a `ghcr.io/<organization>/<package>:<tag>` reference.

        Returns `None` for anything that isn't a usable result -- a ref this client can't
        parse, a private repo without access (401), a tag that was never pushed (404), or a
        network hiccup -- so callers can treat "no manifest" uniformly with "couldn't measure".
        """
        match = REGISTRY_PATTERN.match(ref)
        if not match or ":" not in ref:
            log.debug(f"Not a recognized GHCR ref: '{ref}'")
            return None
        organization, package = match.group("organization"), match.group("package")
        tag = ref.rsplit(":", 1)[-1]

        url = f"{self.BASE_URL}/v2/{organization}/{package}/manifests/{tag}"
        try:
            response = requests.get(url, headers=self._headers, timeout=10)
            response.raise_for_status()
            return Manifest(**response.json())
        except (requests.RequestException, json.JSONDecodeError, ValidationError) as e:
            log.debug(f"Could not fetch GHCR manifest for '{ref}': {e}")
            return None
