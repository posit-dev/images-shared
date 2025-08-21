import jinja2
import pytest

from posit_bakery.config.templating.render import jinja2_env


pytestmark = [
    pytest.mark.unit,
]


class TestJinja2Env:
    def test_jinja2_env_creates_environment(self):
        """Test that jinja2_env creates a Jinja2 environment with custom filters."""
        env = jinja2_env()
        assert isinstance(env, jinja2.Environment)
        assert "tagSafe" in env.filters.keys()
        assert "stripMetadata" in env.filters.keys()
        assert "condense" in env.filters.keys()
        assert "regexReplace" in env.filters.keys()

    def test_tagSafe_filter(self):
        """Test the tagSafe filter."""
        env = jinja2_env()
        assert env.from_string("{{ 'valid-tag' | tagSafe }}").render() == "valid-tag"
        assert env.from_string("{{ 'invalid tag!' | tagSafe }}").render() == "invalid-tag"
        assert env.from_string("{{ 'another@invalid#tag' | tagSafe }}").render() == "another-invalid-tag"
        assert env.from_string("{{ '2025.05.1+513.pro3' | tagSafe }}").render() == "2025.05.1-513.pro3"
        assert env.from_string("{{ '2025.04.1-8' | tagSafe }}").render() == "2025.04.1-8"
        assert env.from_string("{{ '2025.05.0' | tagSafe }}").render() == "2025.05.0"

    def test_stripMetadata_filter(self):
        """Test the stripMetadata filter."""
        env = jinja2_env()
        assert env.from_string("{{ 'item-version+metadata' | stripMetadata }}").render() == "item-version"
        assert env.from_string("{{ 'release-2023-extra' | stripMetadata }}").render() == "release-2023"
        assert env.from_string("{{ '2025.05.1+513.pro3' | stripMetadata }}").render() == "2025.05.1"
        assert env.from_string("{{ '2025.04.1-8' | stripMetadata }}").render() == "2025.04.1"
        assert env.from_string("{{ '2025.05.0' | stripMetadata }}").render() == "2025.05.0"

    def test_condense_filter(self):
        """Test the condense filter."""
        env = jinja2_env()
        assert env.from_string("{{ 'Test String' | condense }}").render() == "TestString"
        assert env.from_string("{{ 'another-test.String' | condense }}").render() == "anothertestString"

    def test_regexReplace_filter(self):
        """Test the regexReplace filter."""
        env = jinja2_env()
        assert env.from_string("{{ 'hello world' | regexReplace('world', 'there') }}").render() == "hello there"
        assert env.from_string("{{ 'foo-bar-baz' | regexReplace('-', '_') }}").render() == "foo_bar_baz"
        assert env.from_string(r"{{ '123-456-789' | regexReplace('\d', 'X') }}").render() == "XXX-XXX-XXX"


def test_render_template():
    """Test the render_template function."""
    template = "{{ 'example-tag' | tagSafe }} {{ 'version+metadata' | stripMetadata }}"
    rendered = jinja2_env().from_string(template).render()
    assert rendered == "example-tag version"

    template = "{{ 'Test String' | condense }} {{ 'foo-bar-baz' | regexReplace('-', '_') }}"
    rendered = jinja2_env().from_string(template).render()
    assert rendered == "TestString foo_bar_baz"
