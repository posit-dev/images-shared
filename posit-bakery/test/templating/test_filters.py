from posit_bakery.templating import filters


def test_tag_safe():
    assert filters.tag_safe("2024.09.1+394.pro7") == "2024.09.1-394.pro7"


def test_clean_version():
    assert filters.clean_version("2024.09.1+394.pro7") == "2024.09.1"


def test_condense():
    assert filters.condense("Ubuntu 22.04") == "ubuntu2204"
    assert filters.condense("Rocky Linux 8") == "rockylinux8"


def test_regex_replace():
    assert filters.regex_replace("2024.09.1+394.pro7", r"\+", "-") == "2024.09.1-394.pro7"


def test_jinja2_env():
    env = filters.jinja2_env(autoescape=True)
    assert env.filters["tag_safe"] == filters.tag_safe
    assert env.filters["clean_version"] == filters.clean_version
    assert env.filters["condense"] == filters.condense
    assert env.filters["regex_replace"] == filters.regex_replace
    assert env.autoescape is True


def test_render_template():
    template = "{{ '2024.09.1+394.pro7' | clean_version }}"
    assert filters.render_template(template) == "2024.09.1"
    template = "{{ '2024.09.1+394.pro7' | tag_safe }}"
    assert filters.render_template(template) == "2024.09.1-394.pro7"
    template = "{{ 'Ubuntu 22.04' | condense }}"
    assert filters.render_template(template) == "ubuntu2204"
    template = "{{ '2024.09.1+394.pro7' | regex_replace('[+|-].*', '') }}"
    assert filters.render_template(template) == "2024.09.1"
