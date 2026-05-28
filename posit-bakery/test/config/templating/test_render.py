import jinja2
import pytest

from posit_bakery.config.templating.render import jinja2_env, normalize_rendered_output


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
        assert "stripPatch" in env.filters.keys()
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

    def test_stripPatch_filter(self):
        """Test the stripPatch filter — drops the patch component from MAJOR.MINOR.PATCH groups."""
        env = jinja2_env()
        # Simple 3-component versions reduce to MAJOR.MINOR.
        assert env.from_string("{{ '3.12.3' | stripPatch }}").render() == "3.12"
        assert env.from_string("{{ '4.3.3' | stripPatch }}").render() == "4.3"
        # Composite matrix names — both version segments get stripped.
        assert env.from_string("{{ 'python3.12.3-R4.3.3' | stripPatch }}").render() == "python3.12-R4.3"
        assert env.from_string("{{ 'R4.3.3-python3.11.15' | stripPatch }}").render() == "R4.3-python3.11"
        # 2-component versions are untouched (no patch to strip).
        assert env.from_string("{{ '2026.04' | stripPatch }}").render() == "2026.04"
        # 4+ component versions collapse fully to MAJOR.MINOR, not partially.
        assert env.from_string("{{ '1.2.3.4' | stripPatch }}").render() == "1.2"
        assert env.from_string("{{ '1.2.3.4.5' | stripPatch }}").render() == "1.2"
        # Strings without version-like sequences are untouched.
        assert env.from_string("{{ 'standard-min' | stripPatch }}").render() == "standard-min"

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


class TestNormalizeRenderedOutput:
    def test_strips_trailing_spaces(self):
        assert normalize_rendered_output("foo  \nbar\n") == "foo\nbar\n"

    def test_strips_trailing_tabs(self):
        assert normalize_rendered_output("foo\t\nbar\n") == "foo\nbar\n"

    def test_strips_mixed_trailing_whitespace(self):
        assert normalize_rendered_output("foo \t \nbar\n") == "foo\nbar\n"

    def test_strips_whitespace_only_lines(self):
        assert normalize_rendered_output("a\n  \nb\n") == "a\n\nb\n"

    def test_collapses_multiple_trailing_newlines(self):
        assert normalize_rendered_output("foo\n\n\n") == "foo\n"

    def test_adds_missing_trailing_newline(self):
        assert normalize_rendered_output("foo\nbar") == "foo\nbar\n"

    def test_preserves_single_trailing_newline(self):
        assert normalize_rendered_output("foo\nbar\n") == "foo\nbar\n"

    def test_empty_input_stays_empty(self):
        assert normalize_rendered_output("") == ""

    def test_preserves_interior_blank_lines(self):
        assert normalize_rendered_output("a\n\nb\n") == "a\n\nb\n"

    def test_does_not_touch_leading_whitespace(self):
        assert normalize_rendered_output("    indented\n") == "    indented\n"
