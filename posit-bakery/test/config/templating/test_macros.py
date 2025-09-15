import textwrap

import pytest
from jinja2 import PackageLoader, StrictUndefined

from posit_bakery.config.templating import jinja2_env


@pytest.fixture
def environment_with_macros():
    return jinja2_env(
        loader=PackageLoader("posit_bakery.config.templating", "macros"),
        autoescape=True,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def test_import_all_macros_no_errors(environment_with_macros):
    """Test that all macro files can be imported without errors."""
    template = textwrap.dedent(
        """\
        {%- import "apt.j2" as apt -%}
        {%- import "dnf.j2" as dnf -%}
        {%- import "python.j2" as python -%}
        {%- import "quarto.j2" as quarto -%}
        {%- import "r.j2" as r -%}
        """
    )
    environment_with_macros.from_string(template).render()


class TestAptMacros:
    def test_apt_update_upgrade(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "apt.j2" as apt -%}
            {{ apt.update_upgrade() }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN apt-get update -yqq --fix-missing && \\
                apt-get upgrade -yqq && \\
                apt-get dist-upgrade -yqq && \\
                apt-get autoremove -yqq --purge && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_packages_from_list(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "apt.j2" as apt -%}
            {{ apt.install_packages_from_list(["ca-certificates", "git", "g++"]) }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN apt-get update -yqq && \\
                apt-get install -yqq --no-install-recommends ca-certificates git g++ && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_packages_from_file(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "apt.j2" as apt -%}
            {{ apt.install_packages_from_file(package_file) }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN apt-get update -yqq && \\
                xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*
            """
        )
        rendered = environment_with_macros.from_string(template).render(package_file="/tmp/packages.txt")
        assert rendered == expected

    def test_setup(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "apt.j2" as apt -%}
            {{ apt.setup() }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN apt-get update -yqq --fix-missing && \\
                apt-get upgrade -yqq && \\
                apt-get dist-upgrade -yqq && \\
                apt-get install -yqq --no-install-recommends \\
                    curl \\
                    ca-certificates \\
                    epel-release \\
                    gnupg \\
                    tar && \\
                apt-get autoremove -yqq --purge && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected


class TestDnfMacros:
    def test_dnf_update_upgrade(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "dnf.j2" as dnf -%}
            {{ dnf.update_upgrade() }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN dnf upgrade -yq && \\
                dnf clean all -yq
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_dnf_install_packages_from_list(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "dnf.j2" as dnf -%}
            {{ dnf.install_packages_from_list(["ca-certificates", "git", "g++"]) }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN dnf install -yq ca-certificates git g++ && \\
                dnf clean all -yq
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_dnf_install_packages_from_file(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "dnf.j2" as dnf -%}
            {{ dnf.install_packages_from_file(package_file) }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN xargs -a /tmp/packages.txt dnf install -yq && \\
                dnf clean all -yq
            """
        )
        rendered = environment_with_macros.from_string(template).render(package_file="/tmp/packages.txt")
        assert rendered == expected

    def test_setup(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "dnf.j2" as dnf -%}
            {{ dnf.setup() }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN dnf upgrade -yq && \\
                dnf install -yq \\
                    curl \\
                    ca-certificates \\
                    gnupg \\
                    tar && \\
                dnf clean all -yq
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected


class TestPythonMacros:
    def test_build(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.build(["3.13.7", "3.12.11"]) }}
            """
        )
        expected = textwrap.dedent(
            """\
            FROM ghcr.io/astral-sh/uv:bookworm-slim AS python-builder
            ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

            ENV UV_PYTHON_INSTALL_DIR=/opt/python

            ENV UV_PYTHON_PREFERENCE=only-managed

            RUN uv python install 3.13.7 3.12.11
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_from_build_stage(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.install_from_build_stage() }}
            """
        )
        expected = textwrap.dedent(
            """\
            COPY --from=python-builder /opt/python /opt/python
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_packages(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.install_packages(["3.13.7", "3.12.11"], ["numpy", "pandas"], "/tmp/requirements.txt") }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN /opt/python/cpython-3.13.7-linux-x86_64-gnu/bin/pip install --no-cache-dir --upgrade numpy pandas -r /tmp/requirements.txt && \\
                /opt/python/cpython-3.12.11-linux-x86_64-gnu/bin/pip install --no-cache-dir --upgrade numpy pandas -r /tmp/requirements.txt
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected


class TestQuartoMacros:
    def test_install(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.install("1.8.24") }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_with_tinytex(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.install("1.8.24", True) }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1 && \\
                /opt/quarto/1.8.24/bin/quarto install tinytex
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected


class TestRMacros:
    def test_install(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.install(["4.4.3", "4.3.3"]) }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN RUN_UNATTENDED=1 R_VERSION=4.4.3 bash -c "$(curl -L https://rstd.io/r-install)" && \\
                RUN_UNATTENDED=1 R_VERSION=4.3.3 bash -c "$(curl -L https://rstd.io/r-install)"
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_packages(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.install_packages(["4.4.3", "4.3.3"], ["dplyr", "ggplot2"], "/tmp/packages.txt") }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(c(\"dplyr\", \"ggplot2\", readLines(\"/tmp/packages.txt\")), repos=\"https://p3m.dev/cran/latest\", clean = TRUE)' && \\
                /opt/R/4.3.3/bin/R --vanilla -e 'install.packages(c(\"dplyr\", \"ggplot2\", readLines(\"/tmp/packages.txt\")), repos=\"https://p3m.dev/cran/latest\", clean = TRUE)'
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected
