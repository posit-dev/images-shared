import pytest

from posit_bakery.config.image.posit_product.resolvers import ReleaseBranchResolver, UrlFetchResolver

RELEASES = [
    {"branch": "apple-blossom", "version": "2026.04.0"},
    {"branch": "blue-mistflower", "version": "2026.09.0"},
]


class TestReleaseBranchResolver:
    @pytest.mark.parametrize(
        "release_branch,expected",
        [
            pytest.param("latest", RELEASES[0], id="latest-is-first"),
            pytest.param("blue-mistflower", RELEASES[1], id="by-branch"),
            pytest.param("2026.09.0", RELEASES[1], id="by-version"),
            pytest.param("missing", None, id="no-match"),
        ],
    )
    def test_resolve(self, release_branch, expected):
        resolver = ReleaseBranchResolver()
        resolver.set_metadata({"release_branch": release_branch})
        assert resolver.resolve(RELEASES) == expected

    def test_latest_with_empty_list(self):
        resolver = ReleaseBranchResolver()
        resolver.set_metadata({"release_branch": "latest"})
        assert resolver.resolve([]) is None


class TestUrlFetchResolver:
    def test_resolve_fetches_json(self, mocker):
        mock_session = mocker.patch("posit_bakery.config.image.posit_product.resolvers.cached_session")
        mock_session.return_value.get.return_value.json.return_value = {"a": 1}

        assert UrlFetchResolver().resolve("https://example.com/x.json") == {"a": 1}
        mock_session.return_value.get.assert_called_once_with("https://example.com/x.json")
        mock_session.return_value.get.return_value.raise_for_status.assert_called_once()
