from posit_bakery.config.tag import TagPattern, TagPatternFilter, default_tag_patterns


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
        rendered_tags = tag_pattern.render(Version="1.0", OS="ubuntu2204", Variant="min")
        assert rendered_tags == ["1.0-ubuntu2204-min"]

    def test_render_tag_pattern_multiple(self):
        tag_pattern = TagPattern(
            patterns=["{{ Version }}-{{ OS }}-{{ Variant }}", "{{ Variant }}"], only=[TagPatternFilter.ALL]
        )
        rendered_tags = tag_pattern.render(Version="1.0", OS="ubuntu2204", Variant="min")
        assert rendered_tags == ["1.0-ubuntu2204-min", "min"]

    def test_hash_tag_pattern(self):
        tag_pattern1 = TagPattern(patterns=["{{ Version }}-{{ OS }}-{{ Variant }}"], only=[TagPatternFilter.ALL])
        tag_pattern2 = TagPattern(patterns=["{{ Version }}-{{ OS }}-{{ Variant }}"], only=[TagPatternFilter.ALL])
        assert tag_pattern1 == tag_pattern2
        assert hash(tag_pattern1) == hash(tag_pattern2)


def test_default_tag_patterns():
    """Test that the default tag patterns are created correctly."""
    patterns = default_tag_patterns()
    version = "1.0"
    os = "ubuntu2204"
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
