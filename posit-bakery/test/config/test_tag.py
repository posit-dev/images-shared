import pytest

from posit_bakery.config.tag import TagPattern, TagPatternFilter, default_matrix_tag_patterns, default_tag_patterns

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestTagPattern:
    def test_create_tag_pattern_default(self):
        tag_pattern = TagPattern(patterns=["{{ Version }}-{{ OS }}-{{ Variant }}"])
        assert tag_pattern.only == [TagPatternFilter.ALL]

    def test_create_tag_pattern_single(self):
        TagPattern(patterns=["{{ Variant }}"], only=["latest", "primaryOS"])

    def test_create_tag_pattern_multiple(self):
        TagPattern(patterns=["{{ Version }}-{{ OS }}", "{{ Variant }}"], only=["all", "latest"])

    def test_render_tag_pattern_single(self):
        tag_pattern = TagPattern(patterns=["{{ Version }}-{{ OS }}-{{ Variant }}"], only=[TagPatternFilter.ALL])
        rendered_tags = tag_pattern.render(Version="1.0", OS="ubuntu-22.04", Variant="min")
        assert rendered_tags == ["1.0-ubuntu-22.04-min"]

    def test_render_tag_pattern_multiple(self):
        tag_pattern = TagPattern(
            patterns=["{{ Version }}-{{ OS }}-{{ Variant }}", "{{ Variant }}"], only=[TagPatternFilter.ALL]
        )
        rendered_tags = tag_pattern.render(Version="1.0", OS="ubuntu-22.04", Variant="min")
        assert rendered_tags == ["1.0-ubuntu-22.04-min", "min"]

    def test_hash_tag_pattern(self):
        tag_pattern1 = TagPattern(patterns=["{{ Version }}-{{ OS }}-{{ Variant }}"], only=[TagPatternFilter.ALL])
        tag_pattern2 = TagPattern(patterns=["{{ Version }}-{{ OS }}-{{ Variant }}"], only=[TagPatternFilter.ALL])
        assert tag_pattern1 == tag_pattern2
        assert hash(tag_pattern1) == hash(tag_pattern2)


def test_default_tag_patterns():
    """Test that the default tag patterns are created correctly."""
    patterns = default_tag_patterns()
    version = "1.0"
    os = "ubuntu-22.04"
    variant = "min"
    expected_tags = [
        f"{version}-{os}-{variant}",
        f"{version}-{variant}",
        f"{version}-{os}",
        version,
        f"{os}-{variant}",
        os,
        variant,
        "latest",
    ]
    rendered_tags = []
    for pattern in patterns:
        rendered_tags.extend(pattern.render(Version=version, OS=os, Variant=variant))
    for tag in expected_tags:
        assert tag in rendered_tags


def test_default_matrix_tag_patterns():
    """Test that the default matrix tag patterns are created correctly."""
    patterns = default_matrix_tag_patterns()
    version = "R4.3.3-python3.11.15"
    os = "ubuntu2404"
    variant = "min"
    expected_tags = [
        f"{version}-{os}-{variant}",
        f"{version}-{variant}",
        f"{version}-{os}",
        version,
        f"{os}-{variant}",
        os,
        variant,
        "latest",
    ]
    rendered_tags = []
    for pattern in patterns:
        rendered_tags.extend(pattern.render(Version=version, OS=os, Variant=variant))
    for tag in expected_tags:
        assert tag in rendered_tags


def test_default_matrix_tag_patterns_includes_latest_filter():
    """Matrix tag patterns now include LATEST-filtered entries matching default_tag_patterns()."""
    matrix_patterns = default_matrix_tag_patterns()
    default_patterns = default_tag_patterns()

    matrix_latest = [p for p in matrix_patterns if TagPatternFilter.LATEST in p.only]
    default_latest = [p for p in default_patterns if TagPatternFilter.LATEST in p.only]

    # Same set of LATEST-filtered patterns; order-insensitive.
    assert sorted([(tuple(p.patterns), tuple(p.only)) for p in matrix_latest]) == sorted(
        [(tuple(p.patterns), tuple(p.only)) for p in default_latest]
    )
    assert len(matrix_latest) == 4


def test_default_matrix_tag_patterns_no_strip_metadata():
    """Test that default matrix tag patterns do not include stripMetadata patterns.

    The stripMetadata filter strips from the last hyphen onward, which breaks composite
    matrix version names like "R4.3.3-python3.11.15" by collapsing them to "R4.3.3".
    """
    patterns = default_matrix_tag_patterns()
    for pattern in patterns:
        for p in pattern.patterns:
            assert "stripMetadata" not in p, f"Matrix tag pattern should not use stripMetadata: {p}"


def test_default_matrix_tag_patterns_no_tag_collisions():
    """Test that matrix tag patterns do not produce colliding tags across different matrix combinations.

    This reproduces the bug where stripMetadata caused "R4.3.3-python3.11.15" and
    "R4.3.3-python3.12.13" to both produce the tag "R4.3.3".

    Checks that different versions within the same OS produce unique tags. Cross-OS overlap
    (e.g., the PRIMARY_OS pattern producing "R4.3.3-python3.11.15" for both OSes) is expected
    and handled by tag pattern filters at the ImageTarget level. LATEST- and LATEST_PATCH-filtered
    patterns are similarly filter-handled (only applied to specific rows), so they are excluded here.
    """
    patterns = [
        p
        for p in default_matrix_tag_patterns()
        if TagPatternFilter.LATEST not in p.only and TagPatternFilter.LATEST_PATCH not in p.only
    ]
    versions = ["R4.3.3-python3.11.15", "R4.3.3-python3.12.13", "R4.3.3-python3.13.12"]
    os_values = ["ubuntu2404", "ubuntu2204"]

    for os in os_values:
        tags_by_version = {}
        for version in versions:
            tags = []
            for pattern in patterns:
                tags.extend(pattern.render(Version=version, OS=os, Variant="min"))
            tags_by_version[version] = set(tags)

        # Verify no two different versions within the same OS share any tags
        version_list = list(tags_by_version.keys())
        for i, v1 in enumerate(version_list):
            for v2 in version_list[i + 1 :]:
                overlap = tags_by_version[v1] & tags_by_version[v2]
                assert not overlap, f"Tag collision for OS {os} between {v1} and {v2}: {overlap}"


def test_default_matrix_tag_patterns_includes_strip_patch_under_latest_patch_filter():
    """Matrix tag patterns include stripPatch variants gated by LATEST_PATCH."""
    patterns = default_matrix_tag_patterns()
    strip_patch_patterns = [p for p in patterns if any("stripPatch" in pat for pat in p.patterns)]
    # One per OS/Variant combination: ALL-equivalent, PRIMARY_OS, PRIMARY_VARIANT, both-primary.
    assert len(strip_patch_patterns) == 4
    for pattern in strip_patch_patterns:
        assert TagPatternFilter.LATEST_PATCH in pattern.only, (
            f"stripPatch pattern must be gated by LATEST_PATCH: {pattern.patterns} only={pattern.only}"
        )


def test_default_matrix_tag_patterns_strip_patch_renders_minor_tags():
    """stripPatch-filtered tag patterns produce minor-only tags from composite matrix versions."""
    patterns = [p for p in default_matrix_tag_patterns() if TagPatternFilter.LATEST_PATCH in p.only]
    version = "R4.3.3-python3.11.15"
    os = "ubuntu2404"
    variant = "min"

    rendered_tags = []
    for pattern in patterns:
        rendered_tags.extend(pattern.render(Version=version, OS=os, Variant=variant))

    expected = {
        f"R4.3-python3.11-{os}-{variant}",
        f"R4.3-python3.11-{variant}",
        f"R4.3-python3.11-{os}",
        "R4.3-python3.11",
    }
    assert expected.issubset(set(rendered_tags))
