from posit_bakery.templating import filters


def test_tag_safe():
    """Test the tag_safe filter to ensure it replaces '+' with '-'"""
    assert filters.tag_safe("2024.09.1+394.pro7") == "2024.09.1-394.pro7"


def test_clean_version():
    """Test the clean_version filter to ensure it strips the build metadata"""
    assert filters.clean_version("2024.09.1+394.pro7") == "2024.09.1"
    assert filters.clean_version("2024.08.2-9") == "2024.08.2"


def test_condense():
    """Test the condense filter to ensure it converts a string to lowercase and removes whitespace"""
    assert filters.condense("Ubuntu 22.04") == "ubuntu2204"
    assert filters.condense("Rocky Linux 8") == "rockylinux8"


def test_regex_replace():
    """Test the generic regex replace filter"""
    assert filters.regex_replace("2024.09.1+394.pro7", r"\+", "-") == "2024.09.1-394.pro7"


def test_jinja2_env():
    """Test the custom Jinja2 environment auto-setup"""
    env = filters.jinja2_env(autoescape=True)
    assert env.filters["tag_safe"] == filters.tag_safe
    assert env.filters["clean_version"] == filters.clean_version
    assert env.filters["condense"] == filters.condense
    assert env.filters["regex_replace"] == filters.regex_replace
    assert env.autoescape is True


def test_render_template():
    """Test rendering some generic template strings for expected behaviors"""
    template = "{{ '2024.09.1+394.pro7' | clean_version }}"
    assert filters.render_template(template) == "2024.09.1"
    template = "{{ '2024.09.1+394.pro7' | tag_safe }}"
    assert filters.render_template(template) == "2024.09.1-394.pro7"
    template = "{{ 'Ubuntu 22.04' | condense }}"
    assert filters.render_template(template) == "ubuntu2204"
    template = "{{ '2024.09.1+394.pro7' | regex_replace('[+|-].*', '') }}"
    assert filters.render_template(template) == "2024.09.1"
