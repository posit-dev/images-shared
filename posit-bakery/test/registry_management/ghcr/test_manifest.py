import base64
from unittest.mock import MagicMock, patch

import pytest
import requests

from posit_bakery.registry_management.ghcr.manifest import GHCRManifestClient

MANIFEST_JSON = {
    "mediaType": "application/vnd.oci.image.manifest.v1+json",
    "schemaVersion": 2,
    "layers": [{"digest": "sha256:a", "size": 100}, {"digest": "sha256:b", "size": 200}],
}


def _fake_response(status_code=200, json_body=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body if json_body is not None else MANIFEST_JSON
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(f"{status_code} error", response=response)
    return response


class TestInit:
    def test_uses_explicit_token(self):
        client = GHCRManifestClient(token="explicit-token")
        credentials = base64.b64encode(b"explicit-token").decode()
        assert client._headers["Authorization"] == f"Bearer {credentials}"

    def test_falls_back_to_github_token_env_var(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        client = GHCRManifestClient()
        credentials = base64.b64encode(b"env-token").decode()
        assert client._headers["Authorization"] == f"Bearer {credentials}"

    def test_raises_without_a_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(ValueError, match="GITHUB_TOKEN"):
            GHCRManifestClient()


class TestGetManifest:
    REF = "ghcr.io/posit-dev/connect/cache:2026.01.1-ubuntu-24.04-min-amd64"

    def test_parses_a_valid_manifest(self):
        client = GHCRManifestClient(token="fake-token")
        with patch(
            "posit_bakery.registry_management.ghcr.manifest.requests.get", return_value=_fake_response()
        ) as mock_get:
            manifest = client.get_manifest(self.REF)

        assert manifest is not None
        assert len(manifest.layers) == 2
        assert manifest.layers[0].size == 100

    def test_requests_the_correct_url_and_headers(self):
        client = GHCRManifestClient(token="fake-token")
        with patch(
            "posit_bakery.registry_management.ghcr.manifest.requests.get", return_value=_fake_response()
        ) as mock_get:
            client.get_manifest(self.REF)

        mock_get.assert_called_once()
        called_url = mock_get.call_args.args[0]
        called_headers = mock_get.call_args.kwargs["headers"]
        assert called_url == ("https://ghcr.io/v2/posit-dev/connect/cache/manifests/2026.01.1-ubuntu-24.04-min-amd64")
        credentials = base64.b64encode(b"fake-token").decode()
        assert called_headers["Authorization"] == f"Bearer {credentials}"

    def test_returns_none_on_401(self):
        client = GHCRManifestClient(token="fake-token")
        with patch(
            "posit_bakery.registry_management.ghcr.manifest.requests.get",
            return_value=_fake_response(status_code=401),
        ):
            assert client.get_manifest(self.REF) is None

    def test_returns_none_on_404(self):
        client = GHCRManifestClient(token="fake-token")
        with patch(
            "posit_bakery.registry_management.ghcr.manifest.requests.get",
            return_value=_fake_response(status_code=404),
        ):
            assert client.get_manifest(self.REF) is None

    def test_returns_none_on_connection_error(self):
        client = GHCRManifestClient(token="fake-token")
        with patch(
            "posit_bakery.registry_management.ghcr.manifest.requests.get",
            side_effect=requests.ConnectionError("boom"),
        ):
            assert client.get_manifest(self.REF) is None

    def test_returns_none_for_a_non_ghcr_ref_without_calling_requests(self):
        client = GHCRManifestClient(token="fake-token")
        with patch("posit_bakery.registry_management.ghcr.manifest.requests.get") as mock_get:
            assert client.get_manifest("docker.io/posit-dev/connect/cache:2026.01.1") is None
        mock_get.assert_not_called()

    def test_returns_none_for_a_ref_with_no_tag(self):
        client = GHCRManifestClient(token="fake-token")
        with patch("posit_bakery.registry_management.ghcr.manifest.requests.get") as mock_get:
            assert client.get_manifest("ghcr.io/posit-dev/connect/cache") is None
        mock_get.assert_not_called()
