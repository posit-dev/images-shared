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
    def test_setup_posit_cloudsmith(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "apt.j2" as apt -%}
            {{ apt.setup_posit_cloudsmith() }}
            """
        )
        expected = textwrap.dedent(
            """\
            bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')"
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_setup_posit_cloudsmith(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "apt.j2" as apt -%}
            {{ apt.run_setup_posit_cloudsmith() }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')"
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_clean_command(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "apt.j2" as apt -%}
            {{ apt.clean_command() }}
            """
        )
        expected = textwrap.dedent(
            """\
            apt-get clean -yqq && \\
            rm -rf /var/lib/apt/lists/*
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "clean,expected",
        [
            pytest.param(
                True,
                textwrap.dedent(
                    """\
                    apt-get update -yqq --fix-missing && \\
                    apt-get upgrade -yqq && \\
                    apt-get dist-upgrade -yqq && \\
                    apt-get autoremove -yqq --purge && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*"""
                ),
                id="clean-true",
            ),
            pytest.param(
                False,
                textwrap.dedent(
                    """\
                    apt-get update -yqq --fix-missing && \\
                    apt-get upgrade -yqq && \\
                    apt-get dist-upgrade -yqq && \\
                    apt-get autoremove -yqq --purge"""
                ),
                id="clean-false",
            ),
        ],
    )
    def test_update_upgrade(self, environment_with_macros, clean, expected):
        template = '{%- import "apt.j2" as apt -%}\n{{ apt.update_upgrade(' + str(clean) + ") }}"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_update_upgrade(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "apt.j2" as apt -%}
            {{ apt.run_update_upgrade() }}
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

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                ("'ca-certificates'", True, True),
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        ca-certificates && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*"""
                ),
                id="single-string-update-clean",
            ),
            pytest.param(
                ("'ca-certificates,git,g++'", True, True),
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        ca-certificates \\
                        git \\
                        g++ && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*"""
                ),
                id="delimited-string-update-clean",
            ),
            pytest.param(
                (["ca-certificates"], True, True),
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        ca-certificates && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*"""
                ),
                id="single-array-update-clean",
            ),
            pytest.param(
                (["ca-certificates", "git", "g++"], True, True),
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        ca-certificates \\
                        git \\
                        g++ && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*"""
                ),
                id="multi-array-update-clean",
            ),
            pytest.param(
                ("'ca-certificates'", False, True),
                textwrap.dedent(
                    """\
                    apt-get install -yqq --no-install-recommends \\
                        ca-certificates && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*"""
                ),
                id="single-string-noupdate-clean",
            ),
            pytest.param(
                ("'ca-certificates'", True, False),
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        ca-certificates"""
                ),
                id="single-string-update-noclean",
            ),
            pytest.param(
                ("'ca-certificates'", False, False),
                textwrap.dedent(
                    """\
                    apt-get install -yqq --no-install-recommends \\
                        ca-certificates"""
                ),
                id="single-string-noupdate-noclean",
            ),
        ],
    )
    def test_install_packages_from_list(self, environment_with_macros, input, expected):
        template = (
            '{%- import "apt.j2" as apt -%}\n'
            "{{ apt.install_packages_from_list(" + ", ".join([str(i) for i in input]) + ") }}"
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "update,clean,expected",
        [
            pytest.param(
                True,
                True,
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*"""
                ),
                id="update-clean",
            ),
            pytest.param(
                False,
                True,
                textwrap.dedent(
                    """\
                    xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*"""
                ),
                id="noupdate-clean",
            ),
            pytest.param(
                True,
                False,
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends"""
                ),
                id="update-noclean",
            ),
            pytest.param(
                False,
                False,
                textwrap.dedent(
                    """\
                    xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends"""
                ),
                id="noupdate-noclean",
            ),
        ],
    )
    def test_install_packages_from_file(self, environment_with_macros, update, clean, expected):
        template = (
            '{%- import "apt.j2" as apt -%}\n'
            "{{ apt.install_packages_from_file(package_file, " + f"{str(update)}, {str(clean)}" + ") }}"
        )
        rendered = environment_with_macros.from_string(template).render(package_file="/tmp/packages.txt")
        assert rendered == expected

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], "'/tmp/packages.txt'", True, True),
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="packages-singlefile-update-clean",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], "'/tmp/packages.txt, /tmp/optional.txt'", True, True),
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                    xargs -a /tmp/optional.txt apt-get install -yqq --no-install-recommends && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="packages-multistringfile-update-clean",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], ["/tmp/packages.txt", "/tmp/optional.txt"], True, True),
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                    xargs -a /tmp/optional.txt apt-get install -yqq --no-install-recommends && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="packages-multistringfile-update-clean",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], None, True, True),
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="packages-nofile-update-clean",
            ),
            pytest.param(
                (None, "'/tmp/packages.txt'", True, True),
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="nopackages-file-update-clean",
            ),
            pytest.param(
                (None, "'/tmp/packages.txt'", True, True),
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="packages-nofile-update-clean",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], "'/tmp/packages.txt'", False, True),
                textwrap.dedent(
                    """\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="packages-singlefile-noupdate-clean",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], "'/tmp/packages.txt'", True, False),
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends

                    """
                ),
                id="packages-singlefile-update-noclean",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], "'/tmp/packages.txt'", False, False),
                textwrap.dedent(
                    """\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends

                    """
                ),
                id="packages-singlefile-noupdate-noclean",
            ),
        ],
    )
    def test_install(self, environment_with_macros, input, expected):
        template = '{%- import "apt.j2" as apt -%}\n{{ apt.install(' + ", ".join([str(i) for i in input]) + ") }}\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], "'/tmp/packages.txt'"),
                textwrap.dedent(
                    """\
                    RUN apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            curl \\
                            ca-certificates \\
                            gnupg \\
                            tar && \\
                        xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="packages-singlefile",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], "'/tmp/packages.txt, /tmp/optional.txt'"),
                textwrap.dedent(
                    """\
                    RUN apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            curl \\
                            ca-certificates \\
                            gnupg \\
                            tar && \\
                        xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                        xargs -a /tmp/optional.txt apt-get install -yqq --no-install-recommends && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="packages-multistringfile",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], ["/tmp/packages.txt", "/tmp/optional.txt"]),
                textwrap.dedent(
                    """\
                    RUN apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            curl \\
                            ca-certificates \\
                            gnupg \\
                            tar && \\
                        xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                        xargs -a /tmp/optional.txt apt-get install -yqq --no-install-recommends && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="packages-multistringfile",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], None),
                textwrap.dedent(
                    """\
                    RUN apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            curl \\
                            ca-certificates \\
                            gnupg \\
                            tar && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="packages-nofile",
            ),
            pytest.param(
                (None, "'/tmp/packages.txt'"),
                textwrap.dedent(
                    """\
                    RUN apt-get update -yqq && \\
                        xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="nopackages-file",
            ),
            pytest.param(
                (None, "'/tmp/packages.txt'"),
                textwrap.dedent(
                    """\
                    RUN apt-get update -yqq && \\
                        xargs -a /tmp/packages.txt apt-get install -yqq --no-install-recommends && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="packages-nofile",
            ),
        ],
    )
    def test_run_install(self, environment_with_macros, input, expected):
        template = '{%- import "apt.j2" as apt -%}\n{{ apt.run_install(' + ", ".join([str(i) for i in input]) + ") }}\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "clean,expected",
        [
            pytest.param(
                True,
                textwrap.dedent(
                    """\
                    apt-get update -yqq --fix-missing && \\
                    apt-get upgrade -yqq && \\
                    apt-get dist-upgrade -yqq && \\
                    apt-get autoremove -yqq --purge && \\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')" && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="clean",
            ),
            pytest.param(
                False,
                textwrap.dedent(
                    """\
                    apt-get update -yqq --fix-missing && \\
                    apt-get upgrade -yqq && \\
                    apt-get dist-upgrade -yqq && \\
                    apt-get autoremove -yqq --purge && \\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')"
                    """
                ),
                id="noclean",
            ),
        ],
    )
    def test_setup(self, environment_with_macros, clean, expected):
        template = '{%- import "apt.j2" as apt -%}\n' + "{{ apt.setup(" + str(clean) + ") }}\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_setup(self, environment_with_macros):
        template = '{%- import "apt.j2" as apt -%}\n{{ apt.run_setup() }}\n'
        rendered = environment_with_macros.from_string(template).render()
        expected = textwrap.dedent(
            """\
            RUN apt-get update -yqq --fix-missing && \\
                apt-get upgrade -yqq && \\
                apt-get dist-upgrade -yqq && \\
                apt-get autoremove -yqq --purge && \\
                apt-get install -yqq --no-install-recommends \\
                    curl \\
                    ca-certificates \\
                    gnupg \\
                    tar && \\
                bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')" && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*
            """
        )
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

    def test_dnf_install_packages_from_list_single_string_input(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "dnf.j2" as dnf -%}
            {{ dnf.install_packages_from_list("ca-certificates") }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN dnf install -yq \\
                    ca-certificates && \\
                dnf clean all -yq
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_dnf_install_packages_from_list_multi_string_input(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "dnf.j2" as dnf -%}
            {{ dnf.install_packages_from_list("ca-certificates, git, g++") }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN dnf install -yq \\
                    ca-certificates \\
                    git \\
                    g++ && \\
                dnf clean all -yq
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_dnf_install_packages_from_list_list_input(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "dnf.j2" as dnf -%}
            {{ dnf.install_packages_from_list(["ca-certificates", "git", "g++"]) }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN dnf install -yq \\
                    ca-certificates \\
                    git \\
                    g++ && \\
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
            RUN /opt/python/cpython-3.13.7-linux-x86_64-gnu/bin/pip install --no-cache-dir --upgrade \\
                numpy \\
                pandas \\
                -r /tmp/requirements.txt
            RUN /opt/python/cpython-3.12.11-linux-x86_64-gnu/bin/pip install --no-cache-dir --upgrade \\
                numpy \\
                pandas \\
                -r /tmp/requirements.txt
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
            RUN mkdir -p /opt/quarto/1.8.24 && \\
                curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1
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
            RUN mkdir -p /opt/quarto/1.8.24 && \\
                curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1 && \\
                /opt/quarto/1.8.24/bin/quarto install tinytex
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected


class TestRMacros:
    @pytest.mark.parametrize(
        "r_versions",
        [
            "['4.4.3', '4.3.3']",
            "'4.4.3, 4.3.3'",
        ],
    )
    def test_install(self, environment_with_macros, r_versions):
        template = '{%- import "r.j2" as r -%}\n' + "{{ r.install(" + r_versions + ") }}\n"
        expected = textwrap.dedent(
            """\
            RUN RUN_UNATTENDED=1 R_VERSION=4.4.3 bash -c "$(curl -L https://rstd.io/r-install)"
            RUN RUN_UNATTENDED=1 R_VERSION=4.3.3 bash -c "$(curl -L https://rstd.io/r-install)"
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "r_versions",
        [
            "['4.4.3', '4.3.3']",
            "'4.4.3, 4.3.3'",
        ],
    )
    def test_install_packages(self, environment_with_macros, r_versions):
        template = (
            '{%- import "r.j2" as r -%}\n'
            + "{{ r.install_packages("
            + r_versions
            + ", ['dplyr', 'ggplot2'], '/tmp/packages.txt') }}\n"
        )
        expected = textwrap.dedent(
            """\
            RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(c(\"dplyr\", \"ggplot2\", readLines(\"/tmp/packages.txt\")), repos=\"https://p3m.dev/cran/latest\", clean = TRUE)'
            RUN /opt/R/4.3.3/bin/R --vanilla -e 'install.packages(c(\"dplyr\", \"ggplot2\", readLines(\"/tmp/packages.txt\")), repos=\"https://p3m.dev/cran/latest\", clean = TRUE)'
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_packages_from_string(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.install_packages("4.4.3", "dplyr, ggplot2") }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(c(\"dplyr\", \"ggplot2\"), repos=\"https://p3m.dev/cran/latest\", clean = TRUE)'
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_packages_from_file(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.install_packages("4.4.3", package_list_file="/tmp/packages.txt") }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(c(readLines(\"/tmp/packages.txt\")), repos=\"https://p3m.dev/cran/latest\", clean = TRUE)'
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected
