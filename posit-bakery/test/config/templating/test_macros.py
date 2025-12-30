import textwrap

import jinja2
import pytest
from jinja2 import PackageLoader, StrictUndefined

from posit_bakery.config.templating import jinja2_env


@pytest.fixture
def environment_with_macros():
    return jinja2_env(
        loader=PackageLoader("posit_bakery.config.templating", "macros"),
        autoescape=jinja2.select_autoescape(
            default_for_string=False,
            default=False,
        ),
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
    def test_clean_command(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "dnf.j2" as dnf -%}
            {{ dnf.clean_command() }}
            """
        )
        expected = textwrap.dedent(
            """\
            dnf clean all -yq
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_setup_posit_cloudsmith(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "dnf.j2" as dnf -%}
            {{ dnf.setup_posit_cloudsmith() }}
            """
        )
        expected = textwrap.dedent(
            """\
            bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.rpm.sh')"
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_setup_posit_cloudsmith(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "dnf.j2" as dnf -%}
            {{ dnf.run_setup_posit_cloudsmith() }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.rpm.sh')"
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
                    dnf upgrade -yq && \\
                    dnf clean all -yq
                    """
                ),
                id="clean-true",
            ),
            pytest.param(
                False,
                textwrap.dedent(
                    """\
                    dnf upgrade -yq
                    """
                ),
                id="clean-false",
            ),
        ],
    )
    def test_update_upgrade(self, environment_with_macros, clean, expected):
        template = '{%- import "dnf.j2" as dnf -%}\n{{ dnf.update_upgrade(' + str(clean) + ") }}\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_update_upgrade(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "dnf.j2" as dnf -%}
            {{ dnf.run_update_upgrade() }}
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

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                ("'ca-certificates'", True),
                textwrap.dedent(
                    """\
                    dnf install -yq \\
                        ca-certificates && \\
                    dnf clean all -yq
                    """
                ),
                id="single-string-clean",
            ),
            pytest.param(
                ("'ca-certificates,git,g++'", True),
                textwrap.dedent(
                    """\
                    dnf install -yq \\
                        ca-certificates \\
                        git \\
                        g++ && \\
                    dnf clean all -yq
                    """
                ),
                id="delimited-string-clean",
            ),
            pytest.param(
                (["ca-certificates"], True),
                textwrap.dedent(
                    """\
                    dnf install -yq \\
                        ca-certificates && \\
                    dnf clean all -yq
                    """
                ),
                id="single-array-clean",
            ),
            pytest.param(
                (["ca-certificates", "git", "g++"], True),
                textwrap.dedent(
                    """\
                    dnf install -yq \\
                        ca-certificates \\
                        git \\
                        g++ && \\
                    dnf clean all -yq
                    """
                ),
                id="multi-array-clean",
            ),
            pytest.param(
                ("'ca-certificates'", False),
                textwrap.dedent(
                    """\
                    dnf install -yq \\
                        ca-certificates
                    """
                ),
                id="single-string-noclean",
            ),
        ],
    )
    def test_install_packages_from_list(self, environment_with_macros, input, expected):
        template = (
            '{%- import "dnf.j2" as dnf -%}\n'
            "{{ dnf.install_packages_from_list(" + ", ".join([str(i) for i in input]) + ") }}\n"
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
                    xargs -a /tmp/packages.txt dnf install -yq && \\
                    dnf clean all -yq
                    """
                ),
                id="clean",
            ),
            pytest.param(
                False,
                textwrap.dedent(
                    """\
                    xargs -a /tmp/packages.txt dnf install -yq
                    """
                ),
                id="noclean",
            ),
        ],
    )
    def test_install_packages_from_file(self, environment_with_macros, clean, expected):
        template = (
            '{%- import "dnf.j2" as dnf -%}\n'
            "{{ dnf.install_packages_from_file(package_file, " + f"{str(clean)}" + ") }}\n"
        )
        rendered = environment_with_macros.from_string(template).render(package_file="/tmp/packages.txt")
        assert rendered == expected

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], "'/tmp/packages.txt'", True),
                textwrap.dedent(
                    """\
                    dnf install -yq \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    xargs -a /tmp/packages.txt dnf install -yq && \\
                    dnf clean all -yq
                    """
                ),
                id="packages-singlefile-clean",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], "'/tmp/packages.txt, /tmp/optional.txt'", True),
                textwrap.dedent(
                    """\
                    dnf install -yq \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    xargs -a /tmp/packages.txt dnf install -yq && \\
                    xargs -a /tmp/optional.txt dnf install -yq && \\
                    dnf clean all -yq
                    """
                ),
                id="packages-multistringfile-clean",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], ["/tmp/packages.txt", "/tmp/optional.txt"], True),
                textwrap.dedent(
                    """\
                    dnf install -yq \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    xargs -a /tmp/packages.txt dnf install -yq && \\
                    xargs -a /tmp/optional.txt dnf install -yq && \\
                    dnf clean all -yq
                    """
                ),
                id="packages-multilistfile-clean",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], None, True),
                textwrap.dedent(
                    """\
                    dnf install -yq \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    dnf clean all -yq
                    """
                ),
                id="packages-nofile-clean",
            ),
            pytest.param(
                (None, "'/tmp/packages.txt'", True),
                textwrap.dedent(
                    """\
                    xargs -a /tmp/packages.txt dnf install -yq && \\
                    dnf clean all -yq
                    """
                ),
                id="nopackages-file-clean",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], "'/tmp/packages.txt'", False),
                textwrap.dedent(
                    """\
                    dnf install -yq \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    xargs -a /tmp/packages.txt dnf install -yq

                    """
                ),
                id="packages-singlefile-noclean",
            ),
        ],
    )
    def test_install(self, environment_with_macros, input, expected):
        template = '{%- import "dnf.j2" as dnf -%}\n{{ dnf.install(' + ", ".join([str(i) for i in input]) + ") }}\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], "'/tmp/packages.txt'"),
                textwrap.dedent(
                    """\
                    RUN dnf install -yq \\
                            curl \\
                            ca-certificates \\
                            gnupg \\
                            tar && \\
                        xargs -a /tmp/packages.txt dnf install -yq && \\
                        dnf clean all -yq
                    """
                ),
                id="packages-singlefile",
            ),
            pytest.param(
                (["curl", "ca-certificates", "gnupg", "tar"], None),
                textwrap.dedent(
                    """\
                    RUN dnf install -yq \\
                            curl \\
                            ca-certificates \\
                            gnupg \\
                            tar && \\
                        dnf clean all -yq
                    """
                ),
                id="packages-nofile",
            ),
            pytest.param(
                (None, "'/tmp/packages.txt'"),
                textwrap.dedent(
                    """\
                    RUN xargs -a /tmp/packages.txt dnf install -yq && \\
                        dnf clean all -yq
                    """
                ),
                id="nopackages-file",
            ),
        ],
    )
    def test_run_install(self, environment_with_macros, input, expected):
        template = '{%- import "dnf.j2" as dnf -%}\n{{ dnf.run_install(' + ", ".join([str(i) for i in input]) + ") }}\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "clean,expected",
        [
            pytest.param(
                True,
                textwrap.dedent(
                    """\
                    dnf upgrade -yq && \\
                    dnf install -yq \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.rpm.sh')" && \\
                    dnf clean all -yq
                    """
                ),
                id="clean",
            ),
            pytest.param(
                False,
                textwrap.dedent(
                    """\
                    dnf upgrade -yq && \\
                    dnf install -yq \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.rpm.sh')"
                    """
                ),
                id="noclean",
            ),
        ],
    )
    def test_setup(self, environment_with_macros, clean, expected):
        template = '{%- import "dnf.j2" as dnf -%}\n' + "{{ dnf.setup(" + str(clean) + ") }}\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_setup(self, environment_with_macros):
        template = '{%- import "dnf.j2" as dnf -%}\n{{ dnf.run_setup() }}\n'
        rendered = environment_with_macros.from_string(template).render()
        expected = textwrap.dedent(
            """\
            RUN dnf upgrade -yq && \\
                dnf install -yq \\
                    curl \\
                    ca-certificates \\
                    gnupg \\
                    tar && \\
                bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.rpm.sh')" && \\
                dnf clean all -yq
            """
        )
        assert rendered == expected


class TestPythonMacros:
    def test_build_stage(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.build_stage(["3.12.11", "3.11.9"]) }}
            """
        )
        expected = textwrap.dedent(
            """\
            FROM ghcr.io/astral-sh/uv:bookworm-slim AS python-builder

            ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
            ENV UV_PYTHON_INSTALL_DIR=/opt/python
            ENV UV_PYTHON_PREFERENCE=only-managed
            RUN uv python install 3.12.11 3.11.9
            RUN mv /opt/python/cpython-3.12.11-linux-*/ /opt/python/3.12.11 && \\
                mv /opt/python/cpython-3.11.9-linux-*/ /opt/python/3.11.9

            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_build_stage_string_input(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.build_stage("3.12.11, 3.11.9") }}
            """
        )
        expected = textwrap.dedent(
            """\
            FROM ghcr.io/astral-sh/uv:bookworm-slim AS python-builder

            ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
            ENV UV_PYTHON_INSTALL_DIR=/opt/python
            ENV UV_PYTHON_PREFERENCE=only-managed
            RUN uv python install 3.12.11 3.11.9
            RUN mv /opt/python/cpython-3.12.11-linux-*/ /opt/python/3.12.11 && \\
                mv /opt/python/cpython-3.11.9-linux-*/ /opt/python/3.11.9

            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_get_version_directory(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.get_version_directory("3.12.11") }}"""
        )
        expected = "/opt/python/3.12.11"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_copy_from_build_stage(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.copy_from_build_stage() }}"""
        )
        expected = "COPY --from=python-builder /opt/python /opt/python"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "python_version,break_system_packages,expected",
        [
            pytest.param(
                "3.12.11",
                True,
                "/opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages",
                id="with-break-system-packages",
            ),
            pytest.param(
                "3.12.11",
                False,
                "/opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade",
                id="without-break-system-packages",
            ),
        ],
    )
    def test_pip_install_command(self, environment_with_macros, python_version, break_system_packages, expected):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.pip_install_command(python_version, break_system_packages) }}"""
        )
        rendered = environment_with_macros.from_string(template).render(
            python_version=python_version, break_system_packages=break_system_packages
        )
        assert rendered == expected

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                ("'3.12.11'", ["numpy", "pandas"], None, True),
                textwrap.dedent(
                    """\
                    /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                        numpy \\
                        pandas"""
                ),
                id="only-packages-list",
            ),
            pytest.param(
                ("'3.12.11'", "'numpy,pandas'", None, True),
                textwrap.dedent(
                    """\
                    /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                        numpy \\
                        pandas"""
                ),
                id="only-packages-string",
            ),
            pytest.param(
                ("'3.12.11'", None, ["/tmp/requirements.txt"], True),
                textwrap.dedent(
                    """\
                    /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                        -r /tmp/requirements.txt && \\
                    rm -f /tmp/requirements.txt"""
                ),
                id="only-requirements-list-clean",
            ),
            pytest.param(
                ("'3.12.11'", None, "'/tmp/requirements.txt'", True),
                textwrap.dedent(
                    """\
                    /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                        -r /tmp/requirements.txt && \\
                    rm -f /tmp/requirements.txt"""
                ),
                id="only-requirements-string-clean",
            ),
            pytest.param(
                ("'3.12.11'", None, ["/tmp/requirements.txt"], False),
                textwrap.dedent(
                    """\
                    /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                        -r /tmp/requirements.txt"""
                ),
                id="only-requirements-list-noclean",
            ),
            pytest.param(
                ("'3.12.11'", ["numpy", "pandas"], ["/tmp/requirements.txt"], True),
                textwrap.dedent(
                    """\
                    /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                        numpy \\
                        pandas \\
                        -r /tmp/requirements.txt && \\
                    rm -f /tmp/requirements.txt"""
                ),
                id="packages-and-requirements-clean",
            ),
            pytest.param(
                ("'3.12.11'", ["numpy", "pandas"], ["/tmp/requirements.txt", "/tmp/dev-requirements.txt"], True),
                textwrap.dedent(
                    """\
                    /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                        numpy \\
                        pandas \\
                        -r /tmp/requirements.txt \\
                        -r /tmp/dev-requirements.txt && \\
                    rm -f /tmp/requirements.txt /tmp/dev-requirements.txt"""
                ),
                id="packages-and-multiple-requirements-clean",
            ),
            pytest.param(
                ("'3.12.11'", ["numpy", "pandas"], ["/tmp/requirements.txt"], False),
                textwrap.dedent(
                    """\
                    /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                        numpy \\
                        pandas \\
                        -r /tmp/requirements.txt"""
                ),
                id="packages-and-requirements-noclean",
            ),
        ],
    )
    def test_install_packages(self, environment_with_macros, input, expected):
        template = (
            '{%- import "python.j2" as python -%}\n'
            "{{ python.install_packages(" + ", ".join([str(i) for i in input]) + ") }}"
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                (["3.12.11", "3.11.9"], ["numpy", "pandas"], None, True),
                textwrap.dedent(
                    """\
                    RUN /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                            numpy \\
                            pandas
                    RUN /opt/python/3.11.9/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                            numpy \\
                            pandas"""
                ),
                id="multi-version-packages",
            ),
            pytest.param(
                ("'3.12.11,3.11.9'", ["numpy", "pandas"], None, True),
                textwrap.dedent(
                    """\
                    RUN /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                            numpy \\
                            pandas
                    RUN /opt/python/3.11.9/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                            numpy \\
                            pandas"""
                ),
                id="string-version-packages",
            ),
            pytest.param(
                (["3.12.11", "3.11.9"], None, "'/tmp/requirements.txt'", True),
                textwrap.dedent(
                    """\
                    RUN /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                            -r /tmp/requirements.txt && \\
                        rm -f /tmp/requirements.txt
                    RUN /opt/python/3.11.9/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                            -r /tmp/requirements.txt && \\
                        rm -f /tmp/requirements.txt"""
                ),
                id="multi-version-requirements-clean",
            ),
            pytest.param(
                (["3.12.11", "3.11.9"], ["numpy", "pandas"], "'/tmp/requirements.txt'", True),
                textwrap.dedent(
                    """\
                    RUN /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                            numpy \\
                            pandas \\
                            -r /tmp/requirements.txt && \\
                        rm -f /tmp/requirements.txt
                    RUN /opt/python/3.11.9/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                            numpy \\
                            pandas \\
                            -r /tmp/requirements.txt && \\
                        rm -f /tmp/requirements.txt"""
                ),
                id="multi-version-packages-requirements-clean",
            ),
            pytest.param(
                (["3.12.11", "3.11.9"], ["numpy", "pandas"], "'/tmp/requirements.txt'", False),
                textwrap.dedent(
                    """\
                    RUN /opt/python/3.12.11/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                            numpy \\
                            pandas \\
                            -r /tmp/requirements.txt
                    RUN /opt/python/3.11.9/bin/pip install --no-cache-dir --upgrade --break-system-packages \\
                            numpy \\
                            pandas \\
                            -r /tmp/requirements.txt"""
                ),
                id="multi-version-packages-requirements-noclean",
            ),
        ],
    )
    def test_run_install_packages(self, environment_with_macros, input, expected):
        template = (
            '{%- import "python.j2" as python -%}\n'
            "{{ python.run_install_packages(" + ", ".join([str(i) for i in input]) + ") }}"
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_symlink_version(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.symlink_version("3.12.11", "/opt/python/default") }}"""
        )
        expected = "ln -s /opt/python/3.12.11 /opt/python/default"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_symlink_binary(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.symlink_binary("3.12.11", "python", "/usr/local/bin/python3.12") }}"""
        )
        expected = "ln -s /opt/python/3.12.11/bin/python /usr/local/bin/python3.12"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_symlink_binaries(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            RUN {{ python.symlink_version("3.12.11", "/opt/python/default") }} && \\
                {{ python.symlink_binary("3.12.11", "python", "/usr/local/bin/python3.12") }} && \\
                {{ python.symlink_binary("3.12.11", "pip", "/usr/local/bin/pip3.12") }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN ln -s /opt/python/3.12.11 /opt/python/default && \\
                ln -s /opt/python/3.12.11/bin/python /usr/local/bin/python3.12 && \\
                ln -s /opt/python/3.12.11/bin/pip /usr/local/bin/pip3.12
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected


class TestQuartoMacros:
    def test_get_version_directory(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.get_version_directory("1.8.24") }}"""
        )
        expected = "/opt/quarto/1.8.24"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "update_path,expected",
        [
            pytest.param(
                True,
                "/opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt --quiet --update-path",
                id="with-update-path",
            ),
            pytest.param(
                False,
                "/opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt --quiet",
                id="without-update-path",
            ),
        ],
    )
    def test_install_tinytex_command(self, environment_with_macros, update_path, expected):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.install_tinytex_command("/opt/quarto/1.8.24/bin/quarto", update_path) }}"""
        )
        rendered = environment_with_macros.from_string(template).render(update_path=update_path)
        assert rendered == expected

    @pytest.mark.parametrize(
        "with_tinytex,tinytex_update_path,expected",
        [
            pytest.param(
                False,
                False,
                textwrap.dedent(
                    """\
                    mkdir -p /opt/quarto/1.8.24 && \\
                    curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1"""
                ),
                id="without-tinytex",
            ),
            pytest.param(
                False,
                True,
                textwrap.dedent(
                    """\
                    mkdir -p /opt/quarto/1.8.24 && \\
                    curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1"""
                ),
                id="without-tinytex-update-path-no-effect",
            ),
            pytest.param(
                True,
                False,
                textwrap.dedent(
                    """\
                    mkdir -p /opt/quarto/1.8.24 && \\
                    curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1 && \\
                    /opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt --quiet"""
                ),
                id="with-tinytex",
            ),
            pytest.param(
                True,
                True,
                textwrap.dedent(
                    """\
                    mkdir -p /opt/quarto/1.8.24 && \\
                    curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1 && \\
                    /opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt --quiet --update-path"""
                ),
                id="with-tinytex-update-path",
            ),
        ],
    )
    def test_install(self, environment_with_macros, with_tinytex, tinytex_update_path, expected):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.install(version, with_tinytex, tinytex_update_path) }}"""
        )
        rendered = environment_with_macros.from_string(template).render(
            version="1.8.24", with_tinytex=with_tinytex, tinytex_update_path=tinytex_update_path
        )
        assert rendered == expected

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                (["1.8.24"], False, False),
                textwrap.dedent(
                    """\
                    RUN mkdir -p /opt/quarto/1.8.24 && \\
                        curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1"""
                ),
                id="single-version-no-tinytex",
            ),
            pytest.param(
                (["1.8.24", "1.7.8"], False, False),
                textwrap.dedent(
                    """\
                    RUN mkdir -p /opt/quarto/1.8.24 && \\
                        curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1
                    RUN mkdir -p /opt/quarto/1.7.8 && \\
                        curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.7.8/quarto-1.7.8-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.7.8" --strip-components=1"""
                ),
                id="multiple-versions-no-tinytex",
            ),
            pytest.param(
                ("1.8.24,1.7.8", False, False),
                textwrap.dedent(
                    """\
                    RUN mkdir -p /opt/quarto/1.8.24 && \\
                        curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1
                    RUN mkdir -p /opt/quarto/1.7.8 && \\
                        curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.7.8/quarto-1.7.8-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.7.8" --strip-components=1"""
                ),
                id="string-versions-no-tinytex",
            ),
            pytest.param(
                (["1.8.24"], True, False),
                textwrap.dedent(
                    """\
                    RUN mkdir -p /opt/quarto/1.8.24 && \\
                        curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1 && \\
                        /opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt --quiet"""
                ),
                id="single-version-with-tinytex",
            ),
            pytest.param(
                (["1.8.24", "1.7.8"], True, False),
                textwrap.dedent(
                    """\
                    RUN mkdir -p /opt/quarto/1.8.24 && \\
                        curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1 && \\
                        /opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt --quiet
                    RUN mkdir -p /opt/quarto/1.7.8 && \\
                        curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.7.8/quarto-1.7.8-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.7.8" --strip-components=1 && \\
                        /opt/quarto/1.7.8/bin/quarto install tinytex --no-prompt --quiet"""
                ),
                id="multiple-versions-with-tinytex",
            ),
            pytest.param(
                (["1.8.24"], True, True),
                textwrap.dedent(
                    """\
                    RUN mkdir -p /opt/quarto/1.8.24 && \\
                        curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1 && \\
                        /opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt --quiet --update-path"""
                ),
                id="single-version-with-tinytex-update-path",
            ),
            pytest.param(
                (["1.8.24", "1.7.8"], True, True),
                textwrap.dedent(
                    """\
                    RUN mkdir -p /opt/quarto/1.8.24 && \\
                        curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1 && \\
                        /opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt --quiet --update-path
                    RUN mkdir -p /opt/quarto/1.7.8 && \\
                        curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.7.8/quarto-1.7.8-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.7.8" --strip-components=1 && \\
                        /opt/quarto/1.7.8/bin/quarto install tinytex --no-prompt --quiet --update-path"""
                ),
                id="multiple-versions-with-tinytex-update-path",
            ),
        ],
    )
    def test_run_install(self, environment_with_macros, input, expected):
        template = (
            '{%- import "quarto.j2" as quarto -%}\n'
            "{{ quarto.run_install(" + ", ".join([repr(i) for i in input]) + ") }}"
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_symlink_version(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.symlink_version("1.8.24", "/opt/quarto/default") }}"""
        )
        expected = "ln -s /opt/quarto/1.8.24 /opt/quarto/default"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_symlink_binary(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.symlink_binary("1.8.24", "quarto", "/usr/local/bin/quarto") }}"""
        )
        expected = "ln -s /opt/quarto/1.8.24/bin/quarto /usr/local/bin/quarto"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected


class TestRMacros:
    def test_get_version_directory(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.get_version_directory("4.4.3") }}"""
        )
        expected = "/opt/R/4.4.3"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install(self, environment_with_macros):
        template = '{%- import "r.j2" as r -%}\n{{ r.install("4.4.3") }}'
        expected = textwrap.dedent(
            """\
            RUN_UNATTENDED=1 R_VERSION=4.4.3 bash -c "$(curl -fsSL https://rstd.io/r-install)" && \\
            find . -type f -name '[rR]-4.4.3.*\.(deb|rpm)' -delete"""
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                ["4.4.3"],
                textwrap.dedent(
                    """\
                    RUN RUN_UNATTENDED=1 R_VERSION=4.4.3 bash -c "$(curl -fsSL https://rstd.io/r-install)" && \\
                        find . -type f -name '[rR]-4.4.3.*\.(deb|rpm)' -delete"""
                ),
                id="single-version",
            ),
            pytest.param(
                ["4.4.3", "4.3.3"],
                textwrap.dedent(
                    """\
                    RUN RUN_UNATTENDED=1 R_VERSION=4.4.3 bash -c "$(curl -fsSL https://rstd.io/r-install)" && \\
                        find . -type f -name '[rR]-4.4.3.*\.(deb|rpm)' -delete
                    RUN RUN_UNATTENDED=1 R_VERSION=4.3.3 bash -c "$(curl -fsSL https://rstd.io/r-install)" && \\
                        find . -type f -name '[rR]-4.3.3.*\.(deb|rpm)' -delete"""
                ),
                id="multiple-versions",
            ),
            pytest.param(
                "'4.4.3,4.3.3'",
                textwrap.dedent(
                    """\
                    RUN RUN_UNATTENDED=1 R_VERSION=4.4.3 bash -c "$(curl -fsSL https://rstd.io/r-install)" && \\
                        find . -type f -name '[rR]-4.4.3.*\.(deb|rpm)' -delete
                    RUN RUN_UNATTENDED=1 R_VERSION=4.3.3 bash -c "$(curl -fsSL https://rstd.io/r-install)" && \\
                        find . -type f -name '[rR]-4.3.3.*\.(deb|rpm)' -delete"""
                ),
                id="string-versions",
            ),
        ],
    )
    def test_run_install(self, environment_with_macros, input, expected):
        template = '{%- import "r.j2" as r -%}\n{{ r.run_install(' + str(input) + ") }}"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "_os,expected",
        [
            pytest.param(
                None,
                "https://p3m.dev/cran/latest",
                id="no-os",
            ),
            pytest.param(
                {"Name": "gentoo"},
                "https://p3m.dev/cran/latest",
                id="unsupported-os",
            ),
            pytest.param(
                {"Name": "ubuntu", "Codename": "jammy"},
                "https://p3m.dev/cran/__linux__/jammy/latest",
                id="ubuntu-jammy",
            ),
            pytest.param(
                {"Name": "ubuntu", "Codename": "noble"},
                "https://p3m.dev/cran/__linux__/noble/latest",
                id="ubuntu-noble",
            ),
            pytest.param(
                {"Name": "debian", "Codename": "bookworm"},
                "https://p3m.dev/cran/__linux__/bookworm/latest",
                id="debian-bookworm",
            ),
            pytest.param(
                {"Name": "debian", "Codename": "trixie"},
                "https://p3m.dev/cran/__linux__/trixie/latest",
                id="debian-trixie",
            ),
            pytest.param(
                {"Name": "rhel", "Version": "8"},
                "https://p3m.dev/cran/__linux__/rhel8/latest",
                id="rhel-8",
            ),
        ],
    )
    def test_get_p3m_cran_repo(self, environment_with_macros, _os, expected):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.get_p3m_cran_repo(os_release) }}"""
        )
        rendered = environment_with_macros.from_string(template).render(os_release=_os)
        assert rendered == expected

    def test_r_expression(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.r_expression("4.4.3", 'install.packages("dplyr", repos="https://p3m.dev/cran/latest", clean = TRUE)') }}"""
        )
        expected = '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages("dplyr", repos="https://p3m.dev/cran/latest", clean = TRUE)\''
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                ("'4.4.3'", ["dplyr"], None),
                '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages(c("dplyr"), repos="https://p3m.dev/cran/latest", clean = TRUE)\'',
                id="single-package-list",
            ),
            pytest.param(
                ("'4.4.3'", "'dplyr'", None),
                '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages(c("dplyr"), repos="https://p3m.dev/cran/latest", clean = TRUE)\'',
                id="single-package-string",
            ),
            pytest.param(
                ("'4.4.3'", ["dplyr", "ggplot2"], None),
                '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages(c("dplyr", "ggplot2"), repos="https://p3m.dev/cran/latest", clean = TRUE)\'',
                id="multi-package-list",
            ),
            pytest.param(
                ("'4.4.3'", "'dplyr,ggplot2'", None),
                '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages(c("dplyr", "ggplot2"), repos="https://p3m.dev/cran/latest", clean = TRUE)\'',
                id="multi-package-string",
            ),
        ],
    )
    def test_install_packages_from_list(self, environment_with_macros, input, expected):
        template = (
            '{%- import "r.j2" as r -%}\n{{ r.install_packages_from_list(' + ", ".join([str(i) for i in input]) + ") }}"
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_packages_from_file(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.install_packages_from_file("4.4.3", "/tmp/packages.txt") }}"""
        )
        expected = '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)\''
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                ("'4.4.3'", ["dplyr", "ggplot2"], None, None, True),
                textwrap.dedent(
                    """\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(c("dplyr", "ggplot2"), repos="https://p3m.dev/cran/latest", clean = TRUE)'

                    """
                ),
                id="only-packages-list",
            ),
            pytest.param(
                ("'4.4.3'", None, ["/tmp/packages.txt"], None, True),
                textwrap.dedent(
                    """\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                    rm -f /tmp/packages.txt
                    """
                ),
                id="single-file-list-clean",
            ),
            pytest.param(
                ("'4.4.3'", None, "'/tmp/packages.txt'", None, True),
                textwrap.dedent(
                    """\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                    rm -f /tmp/packages.txt
                    """
                ),
                id="single-file-string-clean",
            ),
            pytest.param(
                ("'4.4.3'", None, "'/tmp/packages.txt'", None, False),
                textwrap.dedent(
                    """\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)'
                    """
                ),
                id="single-file-string-noclean",
            ),
            pytest.param(
                ("'4.4.3'", None, ["/tmp/packages.txt", "/tmp/extra.txt"], None, True),
                textwrap.dedent(
                    """\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/extra.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                    rm -f /tmp/packages.txt /tmp/extra.txt
                    """
                ),
                id="multi-file-list-clean",
            ),
            pytest.param(
                ("'4.4.3'", None, "'/tmp/packages.txt,/tmp/extra.txt'", None, True),
                textwrap.dedent(
                    """\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/extra.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                    rm -f /tmp/packages.txt /tmp/extra.txt
                    """
                ),
                id="multi-file-string-clean",
            ),
            pytest.param(
                ("'4.4.3'", None, ["/tmp/packages.txt", "/tmp/extra.txt"], None, False),
                textwrap.dedent(
                    """\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/extra.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)'
                    """
                ),
                id="multi-file-list-noclean",
            ),
            pytest.param(
                ("'4.4.3'", None, "'/tmp/packages.txt,/tmp/extra.txt'", None, False),
                textwrap.dedent(
                    """\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/extra.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)'
                    """
                ),
                id="multi-file-string-noclean",
            ),
            pytest.param(
                ("'4.4.3'", ["dplyr", "ggplot"], ["/tmp/packages.txt"], None, True),
                textwrap.dedent(
                    """\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(c("dplyr", "ggplot"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                    rm -f /tmp/packages.txt
                    """
                ),
                id="packages-and-file-list-clean",
            ),
            pytest.param(
                ("'4.4.3'", ["dplyr", "ggplot"], ["/tmp/packages.txt"], None, False),
                textwrap.dedent(
                    """\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(c("dplyr", "ggplot"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                    /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)'
                    """
                ),
                id="packages-and-file-list-noclean",
            ),
        ],
    )
    def test_install_packages(self, environment_with_macros, input, expected):
        template = '{%- import "r.j2" as r -%}\n{{ r.install_packages(' + ", ".join([str(i) for i in input]) + ") }}\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                ("'4.4.3'", ["dplyr", "ggplot2"], None, None),
                textwrap.dedent(
                    """\
                    RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(c("dplyr", "ggplot2"), repos="https://p3m.dev/cran/latest", clean = TRUE)'
                    """
                ),
                id="only-packages-list",
            ),
            pytest.param(
                ("'4.4.3,4.3.3'", ["dplyr", "ggplot2"], None, None),
                textwrap.dedent(
                    """\
                    RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(c("dplyr", "ggplot2"), repos="https://p3m.dev/cran/latest", clean = TRUE)'

                    RUN /opt/R/4.3.3/bin/R --vanilla -e 'install.packages(c("dplyr", "ggplot2"), repos="https://p3m.dev/cran/latest", clean = TRUE)'
                    """
                ),
                id="multi-version-string-packages-list",
            ),
            pytest.param(
                (["4.4.3", "4.3.3"], ["dplyr", "ggplot2"], None, None),
                textwrap.dedent(
                    """\
                    RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(c("dplyr", "ggplot2"), repos="https://p3m.dev/cran/latest", clean = TRUE)'

                    RUN /opt/R/4.3.3/bin/R --vanilla -e 'install.packages(c("dplyr", "ggplot2"), repos="https://p3m.dev/cran/latest", clean = TRUE)'
                    """
                ),
                id="multi-version-list-packages-list",
            ),
            pytest.param(
                ("'4.4.3'", None, ["/tmp/packages.txt"], None),
                textwrap.dedent(
                    """\
                    RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                        rm -f /tmp/packages.txt"""
                ),
                id="single-file-list",
            ),
            pytest.param(
                ("'4.4.3'", None, "'/tmp/packages.txt'", None),
                textwrap.dedent(
                    """\
                    RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                        rm -f /tmp/packages.txt"""
                ),
                id="single-file-string",
            ),
            pytest.param(
                ("'4.4.3'", None, ["/tmp/packages.txt", "/tmp/extra.txt"], None),
                textwrap.dedent(
                    """\
                    RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                        /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/extra.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                        rm -f /tmp/packages.txt /tmp/extra.txt"""
                ),
                id="multi-file-list",
            ),
            pytest.param(
                (["4.4.3", "4.3.3"], None, ["/tmp/packages.txt", "/tmp/extra.txt"], None),
                textwrap.dedent(
                    """\
                    RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                        /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/extra.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                        rm -f /tmp/packages.txt /tmp/extra.txt
                    RUN /opt/R/4.3.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                        /opt/R/4.3.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/extra.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                        rm -f /tmp/packages.txt /tmp/extra.txt"""
                ),
                id="multi-version-multi-file-list",
            ),
            pytest.param(
                ("'4.4.3'", None, "'/tmp/packages.txt,/tmp/extra.txt'", None),
                textwrap.dedent(
                    """\
                    RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                        /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/extra.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                        rm -f /tmp/packages.txt /tmp/extra.txt"""
                ),
                id="multi-file-string",
            ),
            pytest.param(
                ("'4.4.3'", ["dplyr", "ggplot"], ["/tmp/packages.txt"], None),
                textwrap.dedent(
                    """\
                    RUN /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(c("dplyr", "ggplot"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                        /opt/R/4.4.3/bin/R --vanilla -e 'install.packages(readLines("/tmp/packages.txt"), repos="https://p3m.dev/cran/latest", clean = TRUE)' && \\
                        rm -f /tmp/packages.txt"""
                ),
                id="packages-and-file-list",
            ),
        ],
    )
    def test_run_install_packages(self, environment_with_macros, input, expected):
        template = (
            '{%- import "r.j2" as r -%}\n{{ r.run_install_packages(' + ", ".join([str(i) for i in input]) + ") }}"
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_symlink_version(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.symlink_version("4.4.3", "/opt/R/default") }}"""
        )
        expected = "ln -s /opt/R/4.4.3 /opt/R/default"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_symlink_binary(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.symlink_binary("4.4.3", "R", "/usr/local/bin/R") }}"""
        )
        expected = "ln -s /opt/R/4.4.3/bin/R /usr/local/bin/R"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected


class TestWaitForItMacros:
    def test_install(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "wait-for-it.j2" as waitforit -%}
            {{ waitforit.install() }}"""
        )
        expected = textwrap.dedent(
            """\
            curl -fsSL -o /usr/local/bin/wait-for-it.sh https://raw.githubusercontent.com/rstudio/wait-for-it/master/wait-for-it.sh && \\
            chmod +x /usr/local/bin/wait-for-it.sh"""
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_install(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "wait-for-it.j2" as waitforit -%}
            {{ waitforit.run_install() }}"""
        )
        expected = textwrap.dedent(
            """\
            RUN curl -fsSL -o /usr/local/bin/wait-for-it.sh https://raw.githubusercontent.com/rstudio/wait-for-it/master/wait-for-it.sh && \\
                chmod +x /usr/local/bin/wait-for-it.sh"""
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected
