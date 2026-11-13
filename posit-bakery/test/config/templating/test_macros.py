import shutil
import subprocess
import textwrap

import jinja2
import pytest
from ruamel.yaml import YAML
from jinja2 import PackageLoader, StrictUndefined

from posit_bakery.config.templating import jinja2_env
from posit_bakery.error import BakeryTemplateError


LINK_TOOLS = ("ls", "grep", "sort", "tail", "ln", "rm")


def run_link_script(tmp_path, template, opt_from, setup=None, on_path=()):
    """Render a macro and run its final RUN as a shell script against a fake /opt tree and /usr/local/bin.

    Shared by the Python and R link_to_path tests. PATH is restricted to the few tools the script needs so the host's
    own interpreters are not found; `on_path` names are created as executables elsewhere on that PATH.

    :param opt_from: The absolute directory in the script to redirect to ``tmp_path / "opt"``, e.g. "/opt/python".
    :param setup: Optional callable receiving ``(opt, local_bin)`` to populate the fake filesystem.
    :return: The completed process and the fake /usr/local/bin path.
    """
    rendered = (
        jinja2_env(loader=PackageLoader("posit_bakery.config.templating", "macros"), undefined=StrictUndefined)
        .from_string(template)
        .render()
    )
    script = rendered[rendered.rindex("RUN ") + 4 :].replace("\\\n", "\n")
    opt, local_bin, tools = tmp_path / "opt", tmp_path / "local-bin", tmp_path / "tools"
    for d in (opt, local_bin, tools):
        d.mkdir()
    if setup:
        setup(opt, local_bin)
    script = script.replace(opt_from, str(opt)).replace("/usr/local/bin", str(local_bin))
    for tool in LINK_TOOLS:
        found = shutil.which(tool)
        assert found, f"{tool} not found on host"
        (tools / tool).symlink_to(found)
    for name in on_path:
        (tools / name).touch(mode=0o755)
    result = subprocess.run(["/bin/sh", "-c", script], capture_output=True, text=True, env={"PATH": str(tools)})
    return result, local_bin


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
    @pytest.mark.parametrize(
        "repo,expected_url",
        [
            pytest.param("pro", "https://dl.posit.co/public/pro/setup.deb.sh", id="pro"),
            pytest.param("open", "https://dl.posit.co/public/open/setup.deb.sh", id="open"),
        ],
    )
    def test_setup_posit_repo(self, environment_with_macros, repo, expected_url):
        template = f'{{%- import "apt.j2" as apt -%}}\n{{{{ apt.setup_posit_repo("{repo}") }}}}\n'
        expected = f"bash -c \"$(curl -1fsSL '{expected_url}')\"\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_setup_posit_repo_with_codename(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "apt.j2" as apt -%}
            {{ apt.setup_posit_repo("pro", codename="noble") }}
            """
        )
        expected = textwrap.dedent(
            """\
            codename=noble bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')"
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "repo,expected_url",
        [
            pytest.param("pro", "https://dl.posit.co/public/pro/setup.deb.sh", id="pro"),
            pytest.param("open", "https://dl.posit.co/public/open/setup.deb.sh", id="open"),
        ],
    )
    def test_run_setup_posit_repo(self, environment_with_macros, repo, expected_url):
        template = f'{{%- import "apt.j2" as apt -%}}\n{{{{ apt.run_setup_posit_repo("{repo}") }}}}\n'
        expected = f"RUN bash -c \"$(curl -1fsSL '{expected_url}')\"\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_setup_posit_repo_with_codename(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "apt.j2" as apt -%}
            {{ apt.run_setup_posit_repo("pro", codename="noble") }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN codename=noble bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')"
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_setup_posit_repo_rejects_invalid(self, environment_with_macros):
        template = '{%- import "apt.j2" as apt -%}\n{{ apt.setup_posit_repo("foo") }}'
        with pytest.raises(Exception, match="Invalid repo"):
            environment_with_macros.from_string(template).render()

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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends"""
                ),
                id="update-noclean",
            ),
            pytest.param(
                False,
                False,
                textwrap.dedent(
                    """\
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends"""
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

    def test_install_packages_from_file_strips_comments(self, environment_with_macros, tmp_path):
        package_file = tmp_path / "packages.txt"
        package_file.write_text(
            textwrap.dedent("""\
                # Build tools
                curl  # inline comment

                  gnupg
                """)
        )
        template = '{%- import "apt.j2" as apt -%}\n{{ apt.install_packages_from_file(package_file, False, False) }}'
        rendered = environment_with_macros.from_string(template).render(package_file=str(package_file))
        command = rendered.replace("apt-get install", "echo")
        result = subprocess.run(["sh", "-c", command], capture_output=True, text=True, check=True)
        assert result.stdout == "-yqq --no-install-recommends curl gnupg\n"

        # All-comment file: install is skipped rather than run with no packages.
        package_file.write_text("# nothing\n\n")
        result = subprocess.run(["sh", "-c", command], capture_output=True, text=True, check=True)
        assert result.stdout == ""

        # Missing file still fails the command.
        package_file.unlink()
        assert subprocess.run(["sh", "-c", command], capture_output=True).returncode != 0

        # A directory at the path fails instead of silently installing nothing.
        package_file.mkdir()
        assert subprocess.run(["sh", "-c", command], capture_output=True).returncode != 0

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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
                    test -f /tmp/optional.txt && sed 's/#.*//' /tmp/optional.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
                    test -f /tmp/optional.txt && sed 's/#.*//' /tmp/optional.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends

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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends

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
                        test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
                        test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
                        test -f /tmp/optional.txt && sed 's/#.*//' /tmp/optional.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
                        test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
                        test -f /tmp/optional.txt && sed 's/#.*//' /tmp/optional.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
                        test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
                        test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r apt-get install -yqq --no-install-recommends && \\
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
        "clean,pro_repo,open_repo,expected",
        [
            pytest.param(
                True,
                True,
                False,
                textwrap.dedent(
                    """\
                    echo 'Acquire::Retries "3"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' > /etc/apt/apt.conf.d/99-retries && \\
                    apt-get update -yqq --fix-missing && \\
                    apt-get upgrade -yqq && \\
                    apt-get dist-upgrade -yqq && \\
                    apt-get autoremove -yqq --purge && \\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    apt-get install -yqq --no-install-recommends locales && \\
                    localedef -i en_US -f UTF-8 en_US.UTF-8 && \\
                    bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')" && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="pro-only-clean",
            ),
            pytest.param(
                False,
                True,
                False,
                textwrap.dedent(
                    """\
                    echo 'Acquire::Retries "3"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' > /etc/apt/apt.conf.d/99-retries && \\
                    apt-get update -yqq --fix-missing && \\
                    apt-get upgrade -yqq && \\
                    apt-get dist-upgrade -yqq && \\
                    apt-get autoremove -yqq --purge && \\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    apt-get install -yqq --no-install-recommends locales && \\
                    localedef -i en_US -f UTF-8 en_US.UTF-8 && \\
                    bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')"
                    """
                ),
                id="pro-only-noclean",
            ),
            pytest.param(
                True,
                True,
                True,
                textwrap.dedent(
                    """\
                    echo 'Acquire::Retries "3"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' > /etc/apt/apt.conf.d/99-retries && \\
                    apt-get update -yqq --fix-missing && \\
                    apt-get upgrade -yqq && \\
                    apt-get dist-upgrade -yqq && \\
                    apt-get autoremove -yqq --purge && \\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    apt-get install -yqq --no-install-recommends locales && \\
                    localedef -i en_US -f UTF-8 en_US.UTF-8 && \\
                    bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')" && \\
                    bash -c "$(curl -1fsSL 'https://dl.posit.co/public/open/setup.deb.sh')" && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="both-repos-clean",
            ),
            pytest.param(
                True,
                False,
                True,
                textwrap.dedent(
                    """\
                    echo 'Acquire::Retries "3"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' > /etc/apt/apt.conf.d/99-retries && \\
                    apt-get update -yqq --fix-missing && \\
                    apt-get upgrade -yqq && \\
                    apt-get dist-upgrade -yqq && \\
                    apt-get autoremove -yqq --purge && \\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    apt-get install -yqq --no-install-recommends locales && \\
                    localedef -i en_US -f UTF-8 en_US.UTF-8 && \\
                    bash -c "$(curl -1fsSL 'https://dl.posit.co/public/open/setup.deb.sh')" && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="open-only-clean",
            ),
            pytest.param(
                True,
                False,
                False,
                textwrap.dedent(
                    """\
                    echo 'Acquire::Retries "3"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' > /etc/apt/apt.conf.d/99-retries && \\
                    apt-get update -yqq --fix-missing && \\
                    apt-get upgrade -yqq && \\
                    apt-get dist-upgrade -yqq && \\
                    apt-get autoremove -yqq --purge && \\
                    apt-get install -yqq --no-install-recommends \\
                        curl \\
                        ca-certificates \\
                        gnupg \\
                        tar && \\
                    apt-get install -yqq --no-install-recommends locales && \\
                    localedef -i en_US -f UTF-8 en_US.UTF-8 && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*
                    """
                ),
                id="no-repos-clean",
            ),
        ],
    )
    def test_setup(self, environment_with_macros, clean, pro_repo, open_repo, expected):
        template = (
            '{%- import "apt.j2" as apt -%}\n'
            f"{{{{ apt.setup({clean}, pro_repo={pro_repo}, open_repo={open_repo}) }}}}\n"
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_setup(self, environment_with_macros):
        template = '{%- import "apt.j2" as apt -%}\n{{ apt.run_setup() }}\n'
        rendered = environment_with_macros.from_string(template).render()
        expected = textwrap.dedent(
            """\
            RUN echo 'Acquire::Retries "3"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' > /etc/apt/apt.conf.d/99-retries && \\
                apt-get update -yqq --fix-missing && \\
                apt-get upgrade -yqq && \\
                apt-get dist-upgrade -yqq && \\
                apt-get autoremove -yqq --purge && \\
                apt-get install -yqq --no-install-recommends \\
                    curl \\
                    ca-certificates \\
                    gnupg \\
                    tar && \\
                apt-get install -yqq --no-install-recommends locales && \\
                localedef -i en_US -f UTF-8 en_US.UTF-8 && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*
            ENV LANG=en_US.UTF-8
            ENV LANGUAGE=en_US:en
            ENV LC_ALL=en_US.UTF-8
            """
        )
        assert rendered == expected

    def test_run_setup_both_repos(self, environment_with_macros):
        template = '{%- import "apt.j2" as apt -%}\n{{ apt.run_setup(pro_repo=True, open_repo=True) }}\n'
        rendered = environment_with_macros.from_string(template).render()
        expected = textwrap.dedent(
            """\
            RUN echo 'Acquire::Retries "3"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' > /etc/apt/apt.conf.d/99-retries && \\
                apt-get update -yqq --fix-missing && \\
                apt-get upgrade -yqq && \\
                apt-get dist-upgrade -yqq && \\
                apt-get autoremove -yqq --purge && \\
                apt-get install -yqq --no-install-recommends \\
                    curl \\
                    ca-certificates \\
                    gnupg \\
                    tar && \\
                apt-get install -yqq --no-install-recommends locales && \\
                localedef -i en_US -f UTF-8 en_US.UTF-8 && \\
                bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')" && \\
                bash -c "$(curl -1fsSL 'https://dl.posit.co/public/open/setup.deb.sh')" && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*
            ENV LANG=en_US.UTF-8
            ENV LANGUAGE=en_US:en
            ENV LC_ALL=en_US.UTF-8
            """
        )
        assert rendered == expected

    def test_run_setup_with_codename(self, environment_with_macros):
        template = '{%- import "apt.j2" as apt -%}\n{{ apt.run_setup(codename="noble", pro_repo=True) }}\n'
        rendered = environment_with_macros.from_string(template).render()
        expected = textwrap.dedent(
            """\
            RUN echo 'Acquire::Retries "3"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' > /etc/apt/apt.conf.d/99-retries && \\
                apt-get update -yqq --fix-missing && \\
                apt-get upgrade -yqq && \\
                apt-get dist-upgrade -yqq && \\
                apt-get autoremove -yqq --purge && \\
                apt-get install -yqq --no-install-recommends \\
                    curl \\
                    ca-certificates \\
                    gnupg \\
                    tar && \\
                apt-get install -yqq --no-install-recommends locales && \\
                localedef -i en_US -f UTF-8 en_US.UTF-8 && \\
                codename=noble bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')" && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*
            ENV LANG=en_US.UTF-8
            ENV LANGUAGE=en_US:en
            ENV LC_ALL=en_US.UTF-8
            """
        )
        assert rendered == expected

    @pytest.mark.parametrize("locale", [False, None], ids=["false", "none"])
    def test_setup_locale_disabled(self, environment_with_macros, locale):
        template = f'{{%- import "apt.j2" as apt -%}}\n{{{{ apt.setup(locale={locale}) }}}}\n'
        rendered = environment_with_macros.from_string(template).render()
        expected = textwrap.dedent(
            """\
            echo 'Acquire::Retries "3"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' > /etc/apt/apt.conf.d/99-retries && \\
            apt-get update -yqq --fix-missing && \\
            apt-get upgrade -yqq && \\
            apt-get dist-upgrade -yqq && \\
            apt-get autoremove -yqq --purge && \\
            apt-get install -yqq --no-install-recommends \\
                curl \\
                ca-certificates \\
                gnupg \\
                tar && \\
            apt-get clean -yqq && \\
            rm -rf /var/lib/apt/lists/*
            """
        )
        assert rendered == expected

    @pytest.mark.parametrize("locale", [False, None], ids=["false", "none"])
    def test_run_setup_locale_disabled(self, environment_with_macros, locale):
        template = f'{{%- import "apt.j2" as apt -%}}\n{{{{ apt.run_setup(locale={locale}) }}}}\n'
        rendered = environment_with_macros.from_string(template).render()
        expected = textwrap.dedent(
            """\
            RUN echo 'Acquire::Retries "3"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' > /etc/apt/apt.conf.d/99-retries && \\
                apt-get update -yqq --fix-missing && \\
                apt-get upgrade -yqq && \\
                apt-get dist-upgrade -yqq && \\
                apt-get autoremove -yqq --purge && \\
                apt-get install -yqq --no-install-recommends \\
                    curl \\
                    ca-certificates \\
                    gnupg \\
                    tar && \\
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

    @pytest.mark.parametrize(
        "repo,expected_url",
        [
            pytest.param("pro", "https://dl.posit.co/public/pro/setup.rpm.sh", id="pro"),
            pytest.param("open", "https://dl.posit.co/public/open/setup.rpm.sh", id="open"),
        ],
    )
    def test_setup_posit_repo(self, environment_with_macros, repo, expected_url):
        template = f'{{%- import "dnf.j2" as dnf -%}}\n{{{{ dnf.setup_posit_repo("{repo}") }}}}\n'
        expected = f"bash -c \"$(curl -1fsSL '{expected_url}')\"\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "repo,expected_url",
        [
            pytest.param("pro", "https://dl.posit.co/public/pro/setup.rpm.sh", id="pro"),
            pytest.param("open", "https://dl.posit.co/public/open/setup.rpm.sh", id="open"),
        ],
    )
    def test_run_setup_posit_repo(self, environment_with_macros, repo, expected_url):
        template = f'{{%- import "dnf.j2" as dnf -%}}\n{{{{ dnf.run_setup_posit_repo("{repo}") }}}}\n'
        expected = f"RUN bash -c \"$(curl -1fsSL '{expected_url}')\"\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_setup_posit_repo_rejects_invalid(self, environment_with_macros):
        template = '{%- import "dnf.j2" as dnf -%}\n{{ dnf.setup_posit_repo("foo") }}'
        with pytest.raises(Exception, match="Invalid repo"):
            environment_with_macros.from_string(template).render()

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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r dnf install -yq && \\
                    dnf clean all -yq
                    """
                ),
                id="clean",
            ),
            pytest.param(
                False,
                textwrap.dedent(
                    """\
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r dnf install -yq
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r dnf install -yq && \\
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r dnf install -yq && \\
                    test -f /tmp/optional.txt && sed 's/#.*//' /tmp/optional.txt | xargs -r dnf install -yq && \\
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r dnf install -yq && \\
                    test -f /tmp/optional.txt && sed 's/#.*//' /tmp/optional.txt | xargs -r dnf install -yq && \\
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r dnf install -yq && \\
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
                    test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r dnf install -yq

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
                        test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r dnf install -yq && \\
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
                    RUN test -f /tmp/packages.txt && sed 's/#.*//' /tmp/packages.txt | xargs -r dnf install -yq && \\
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
                    dnf install -yq --allowerasing \\
                        curl \\
                        ca-certificates \\
                        findutils \\
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
                    dnf install -yq --allowerasing \\
                        curl \\
                        ca-certificates \\
                        findutils \\
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
        template = '{%- import "dnf.j2" as dnf -%}\n' + "{{ dnf.setup(" + str(clean) + ", pro_repo=True) }}\n"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_setup(self, environment_with_macros):
        template = '{%- import "dnf.j2" as dnf -%}\n{{ dnf.run_setup() }}\n'
        rendered = environment_with_macros.from_string(template).render()
        expected = textwrap.dedent(
            """\
            RUN dnf upgrade -yq && \\
                dnf install -yq --allowerasing \\
                    curl \\
                    ca-certificates \\
                    findutils \\
                    gnupg \\
                    tar && \\
                dnf clean all -yq
            """
        )
        assert rendered == expected


class TestGossMacros:
    def test_build_arg_env_var(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "goss.j2" as goss -%}
            {{ goss.build_arg_env_var("PYTHON_VERSION") }}
            """
        )
        expected = textwrap.dedent(
            """\
            {{ .Env.BUILD_ARG_PYTHON_VERSION }}
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize("binaries", ['["python", "pip"]', '"python, pip"'])
    def test_path_link_checks(self, environment_with_macros, binaries):
        template = textwrap.dedent(
            """\
            {%- import "goss.j2" as goss -%}
            command:{{ goss.path_link_checks(BINARIES, "/opt/python/3.14.10") }}
            """
        ).replace("BINARIES", binaries)
        expected = textwrap.dedent(
            """\
            command:
              python-on-path-is-newest:
                exec: test "$(readlink -f "$(command -v python)")" = "$(readlink -f /opt/python/3.14.10/bin/python)"
                exit-status: 0
              pip-on-path-is-newest:
                exec: test "$(readlink -f "$(command -v pip)")" = "$(readlink -f /opt/python/3.14.10/bin/pip)"
                exit-status: 0
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected
        parsed = YAML(typ="safe").load(rendered)
        assert set(parsed["command"]) == {"python-on-path-is-newest", "pip-on-path-is-newest"}

    def test_path_link_checks_single_string(self, environment_with_macros):
        template = (
            '{%- import "goss.j2" as goss -%}command:{{ goss.path_link_checks("python", "/opt/python/3.14.10") }}'
        )
        parsed = YAML(typ="safe").load(environment_with_macros.from_string(template).render())
        assert list(parsed["command"]) == ["python-on-path-is-newest"]

    def test_path_link_checks_empty_list_renders_no_entries(self, environment_with_macros):
        """An empty binary list yields a bare `command:` key (null), so callers should not pass one."""
        template = '{%- import "goss.j2" as goss -%}command:{{ goss.path_link_checks([], "/opt/python/3.14.10") }}'
        rendered = environment_with_macros.from_string(template).render()
        assert YAML(typ="safe").load(rendered) == {"command": None}

    @pytest.mark.parametrize(
        "link_to,expected_status",
        [
            pytest.param("3.14.10", 0, id="link-is-newest"),
            pytest.param("3.13.7", 1, id="link-is-older"),
            pytest.param(None, 1, id="link-missing"),
        ],
    )
    def test_path_link_checks_exec_runs(self, environment_with_macros, tmp_path, link_to, expected_status):
        """Run the generated exec line in sh with a temporary PATH."""
        template = '{%- import "goss.j2" as goss -%}command:{{ goss.path_link_checks("python", DIR) }}'.replace(
            "DIR", f'"{tmp_path}/opt/python/3.14.10"'
        )
        parsed = YAML(typ="safe").load(environment_with_macros.from_string(template).render())
        exec_line = parsed["command"]["python-on-path-is-newest"]["exec"]
        for version in ("3.14.10", "3.13.7"):
            (tmp_path / "opt" / "python" / version / "bin").mkdir(parents=True)
            (tmp_path / "opt" / "python" / version / "bin" / "python").touch(mode=0o755)
        path_dir = tmp_path / "path"
        path_dir.mkdir()
        readlink = shutil.which("readlink")
        assert readlink, "readlink not found on host"
        (path_dir / "readlink").symlink_to(readlink)
        if link_to:
            (path_dir / "python").symlink_to(tmp_path / "opt" / "python" / link_to / "bin" / "python")
        result = subprocess.run(["/bin/sh", "-c", exec_line], env={"PATH": str(path_dir)}, capture_output=True)
        assert result.returncode == expected_status, result.stderr

    def test_path_link_targets(self, environment_with_macros, tmp_path):
        template = '{%- import "goss.j2" as goss -%}command:{{ goss.path_link_targets(BINS, DIR) }}'.replace(
            "BINS", '["python", "pip"]'
        ).replace("DIR", f'"{tmp_path}/opt/python/3.14.10"')
        parsed = YAML(typ="safe").load(environment_with_macros.from_string(template).render())
        assert set(parsed["command"]) == {"python-link-targets-newest", "pip-link-targets-newest"}
        exec_line = parsed["command"]["python-link-targets-newest"]["exec"]
        assert parsed["command"]["python-link-targets-newest"]["exit-status"] == 0
        # Run against a fake /usr/local/bin by redirecting the path in the exec line.
        target = tmp_path / "opt" / "python" / "3.14.10" / "bin" / "python"
        for link, expected in (("good", 0), ("wrong", 1), ("missing", 1)):
            local_bin = tmp_path / link
            local_bin.mkdir()
            if link == "good":
                (local_bin / "python").symlink_to(target)
            elif link == "wrong":
                (local_bin / "python").symlink_to("/opt/python/3.13.7/bin/python")
            script = exec_line.replace("/usr/local/bin", str(local_bin))
            result = subprocess.run(["/bin/sh", "-c", script], env={"PATH": "/usr/bin:/bin"}, capture_output=True)
            assert result.returncode == expected, link


class TestPythonMacros:
    def test_declare_build_arg_default(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.declare_build_arg() }}
            """
        )
        expected = textwrap.dedent(
            """\
            ARG PYTHON_VERSION
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_declare_build_arg_alternate_name(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.declare_build_arg(name="MY_VERSION_OVERRIDE") }}
            """
        )
        expected = textwrap.dedent(
            """\
            ARG MY_VERSION_OVERRIDE
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_declare_build_arg_with_default(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.declare_build_arg(default="3.13.7") }}
            """
        )
        expected = textwrap.dedent(
            """\
            ARG PYTHON_VERSION=3.13.7
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_build_arg(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.build_arg() }}
            """
        )
        expected = textwrap.dedent(
            """\
            $PYTHON_VERSION
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_build_arg_alternate_name(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.build_arg("MY_VERSION_OVERRIDE") }}
            """
        )
        expected = textwrap.dedent(
            """\
            $MY_VERSION_OVERRIDE
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_build_stage(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.build_stage(["3.12.11", "3.11.9"]) }}
            """
        )
        expected = textwrap.dedent(
            """\
            FROM ghcr.io/astral-sh/uv:debian-slim AS python-builder

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
            FROM ghcr.io/astral-sh/uv:debian-slim AS python-builder

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

    def test_build_stage_with_build_arg(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.build_stage(python.build_arg(), prerun=python.declare_build_arg()) }}
            """
        )
        expected = textwrap.dedent(
            """\
            FROM ghcr.io/astral-sh/uv:debian-slim AS python-builder

            ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
            ENV UV_PYTHON_INSTALL_DIR=/opt/python
            ENV UV_PYTHON_PREFERENCE=only-managed

            ARG PYTHON_VERSION
            RUN uv python install $PYTHON_VERSION
            RUN mv /opt/python/cpython-$PYTHON_VERSION-linux-*/ /opt/python/$PYTHON_VERSION

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

    PYTHON_LINK_COPY = "COPY --from=python-builder /opt/python /opt/python\n\n"

    @staticmethod
    def _python_link_run(directory):
        return textwrap.dedent(
            f"""\
            RUN {{ if [ -L /usr/local/bin/python ] && [ ! -e /usr/local/bin/python ]; then rm /usr/local/bin/python; fi; [ -e /usr/local/bin/python ] || ln -s {directory}/bin/python /usr/local/bin/python; }} && \\
                {{ if [ -L /usr/local/bin/python3 ] && [ ! -e /usr/local/bin/python3 ]; then rm /usr/local/bin/python3; fi; [ -e /usr/local/bin/python3 ] || ln -s {directory}/bin/python3 /usr/local/bin/python3; }} && \\
                {{ if [ -L /usr/local/bin/pip ] && [ ! -e /usr/local/bin/pip ]; then rm /usr/local/bin/pip; fi; [ -e /usr/local/bin/pip ] || ln -s {directory}/bin/pip /usr/local/bin/pip; }} && \\
                {{ if [ -L /usr/local/bin/pip3 ] && [ ! -e /usr/local/bin/pip3 ]; then rm /usr/local/bin/pip3; fi; [ -e /usr/local/bin/pip3 ] || ln -s {directory}/bin/pip3 /usr/local/bin/pip3; }}"""
        )

    @pytest.mark.parametrize(
        "versions,directory",
        [
            pytest.param('["3.12.11", "3.13.7"]', "/opt/python/3.13.7", id="list"),
            pytest.param('["3.13.7", "3.9.20"]', "/opt/python/3.13.7", id="numeric-ordering"),
            pytest.param('"3.12.11,3.13.7"', "/opt/python/3.13.7", id="string"),
            pytest.param('["3.12.11"]', "/opt/python/3.12.11", id="single"),
            pytest.param('"${PYTHON_VERSION}"', "/opt/python/${PYTHON_VERSION}", id="placeholder"),
            pytest.param("python.build_arg()", "/opt/python/$PYTHON_VERSION", id="build-arg"),
        ],
    )
    def test_copy_from_build_stage_link_to_path_with_versions(self, environment_with_macros, versions, directory):
        template = (
            '{%- import "python.j2" as python -%}\n'
            "{{ python.copy_from_build_stage(versions=" + versions + ", link_to_path=True) }}"
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == self.PYTHON_LINK_COPY + self._python_link_run(directory)

    @pytest.mark.parametrize("versions", ["[]", "''"])
    def test_copy_from_build_stage_link_to_path_empty_versions_raises(self, environment_with_macros, versions):
        """An empty versions value is an error; it does not fall back to build-time detection."""
        template = (
            '{%- import "python.j2" as python -%}'
            "{{ python.copy_from_build_stage(versions=" + versions + ", link_to_path=True) }}"
        )
        with pytest.raises(BakeryTemplateError, match="maxVersion"):
            environment_with_macros.from_string(template).render()

    def test_copy_from_build_stage_versions_ignored_without_link(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.copy_from_build_stage(versions=["3.12.11", "3.13.7"]) }}"""
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == "COPY --from=python-builder /opt/python /opt/python"

    def test_copy_from_build_stage_link_to_path_detects_at_build_time(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.copy_from_build_stage(link_to_path=True) }}"""
        )
        expected = textwrap.dedent(
            """\
            COPY --from=python-builder /opt/python /opt/python

            RUN set -e; \\
                newest="$(ls /opt/python | grep -E '^[0-9]+\\.[0-9]+(\\.[0-9]+)?$' | sort -V | tail -n 1 || true)"; \\
                if [ -z "$newest" ]; then echo "link_to_path: no X.Y or X.Y.Z Python version found in /opt/python" >&2; exit 1; fi; \\
                for bin in python python3 pip pip3; do \\
                    if [ -L "/usr/local/bin/$bin" ] && [ ! -e "/usr/local/bin/$bin" ]; then rm "/usr/local/bin/$bin"; fi; \\
                    [ -e "/usr/local/bin/$bin" ] || ln -s "/opt/python/$newest/bin/$bin" "/usr/local/bin/$bin"; \\
                done"""
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @staticmethod
    def _run_detection_script(
        tmp_path,
        entries,
        existing_on_path=(),
        existing_in_local_bin=(),
        dangling_in_local_bin=(),
        valid_link_in_local_bin=None,
    ):
        """Run the rendered build-time detection script against a fake /opt/python and /usr/local/bin."""
        template = '{%- import "python.j2" as python -%}{{ python.copy_from_build_stage(link_to_path=True) }}'

        def setup(opt, local_bin):
            for name in existing_in_local_bin:
                (local_bin / name).touch()
            for name in dangling_in_local_bin:
                (local_bin / name).symlink_to("/nonexistent")
            for name, target in (valid_link_in_local_bin or {}).items():
                (local_bin / name).symlink_to(target)
            for entry in entries:
                (opt / entry / "bin").mkdir(parents=True)
                for name in ("python", "python3", "pip", "pip3"):
                    (opt / entry / "bin" / name).touch()

        return run_link_script(tmp_path, template, "/opt/python", setup, existing_on_path)

    def test_link_to_path_detection_picks_newest_release(self, tmp_path):
        result, local_bin = self._run_detection_script(tmp_path, ["3.9.20", "3.13.7", "3.14.0rc1", "3.12.11"])
        assert result.returncode == 0, result.stderr
        assert sorted(p.name for p in local_bin.iterdir()) == ["pip", "pip3", "python", "python3"]
        assert (local_bin / "python").readlink() == tmp_path / "opt" / "3.13.7" / "bin" / "python"

    @pytest.mark.parametrize(
        "entries,expected",
        [
            pytest.param(["3.11", "3.12"], "3.12", id="minor-only"),
            pytest.param(["3.9", "3.13"], "3.13", id="minor-only-numeric-ordering"),
            pytest.param(["3.12", "3.13.7"], "3.13.7", id="mixed-minor-and-patch"),
            pytest.param(["3.13.7", "3.13.7-dev", "default", "3.14.0rc1"], "3.13.7", id="ignores-non-release-names"),
        ],
    )
    def test_link_to_path_detection_accepts_minor_only_dirs(self, tmp_path, entries, expected):
        result, local_bin = self._run_detection_script(tmp_path, entries)
        assert result.returncode == 0, result.stderr
        assert (local_bin / "python").readlink() == tmp_path / "opt" / expected / "bin" / "python"

    def test_link_to_path_detection_keeps_existing_binary(self, tmp_path):
        result, local_bin = self._run_detection_script(tmp_path, ["3.13.7"], existing_in_local_bin=["python"])
        assert result.returncode == 0, result.stderr
        assert sorted(p.name for p in local_bin.iterdir()) == ["pip", "pip3", "python", "python3"]
        assert not (local_bin / "python").is_symlink()

    def test_link_to_path_detection_replaces_dangling_symlink(self, tmp_path):
        result, local_bin = self._run_detection_script(tmp_path, ["3.13.7"], dangling_in_local_bin=["python3"])
        assert result.returncode == 0, result.stderr
        assert (local_bin / "python3").readlink() == tmp_path / "opt" / "3.13.7" / "bin" / "python3"
        assert (local_bin / "python3").exists()

    def test_link_to_path_detection_keeps_valid_symlink(self, tmp_path):
        target = tmp_path / "other-python"
        target.touch()
        result, local_bin = self._run_detection_script(tmp_path, ["3.13.7"], valid_link_in_local_bin={"python": target})
        assert result.returncode == 0, result.stderr
        assert (local_bin / "python").readlink() == target

    def test_link_to_path_detection_shadows_binary_elsewhere_on_path(self, tmp_path):
        result, local_bin = self._run_detection_script(tmp_path, ["3.13.7"], existing_on_path=["python3"])
        assert result.returncode == 0, result.stderr
        assert (local_bin / "python3").readlink() == tmp_path / "opt" / "3.13.7" / "bin" / "python3"

    def test_link_to_path_detection_fails_without_match(self, tmp_path):
        result, local_bin = self._run_detection_script(tmp_path, ["3.14.0rc1"])
        assert result.returncode != 0
        assert "no X.Y or X.Y.Z Python version found" in result.stderr
        assert list(local_bin.iterdir()) == []

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

    def test_install_jupyterlab_workbench_default(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.install_jupyterlab_workbench("3.12.11") }}
            """
        )
        expected = textwrap.dedent(
            """\
            /opt/python/3.12.11/bin/python -m venv /opt/python/jupyter && \\
            /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \\
            /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade \\
                "jupyterlab" \\
                notebook \\
                "pwb_jupyterlab" && \\
            rm -rf /opt/python/jupyter/lib/python*/site-packages/jupyterlab/tests && \\
            rm -rf /opt/python/jupyter/lib/python*/site-packages/jupyterlab/galata && \\
            rm -rf /opt/python/jupyter/lib/python*/site-packages/tornado/test && \\
            rm -f /opt/python/jupyter/lib/python*/site-packages/jupyterlab/staging/yarn.lock && \\
            ln -s /opt/python/jupyter/bin/jupyter /usr/local/bin/jupyter
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_jupyterlab_workbench_version_pins(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.install_jupyterlab_workbench("3.12.11", jupyterlab_version_pin="<5", pwb_jupyterlab_version_pin="<2") }}
            """
        )
        expected = textwrap.dedent(
            """\
            /opt/python/3.12.11/bin/python -m venv /opt/python/jupyter && \\
            /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \\
            /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade \\
                "jupyterlab<5" \\
                notebook \\
                "pwb_jupyterlab<2" && \\
            rm -rf /opt/python/jupyter/lib/python*/site-packages/jupyterlab/tests && \\
            rm -rf /opt/python/jupyter/lib/python*/site-packages/jupyterlab/galata && \\
            rm -rf /opt/python/jupyter/lib/python*/site-packages/tornado/test && \\
            rm -f /opt/python/jupyter/lib/python*/site-packages/jupyterlab/staging/yarn.lock && \\
            ln -s /opt/python/jupyter/bin/jupyter /usr/local/bin/jupyter
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_jupyterlab_workbench_extra_packages(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.install_jupyterlab_workbench("3.12.11", extra_packages=["numpy", "pandas"]) }}
            """
        )
        expected = textwrap.dedent(
            """\
            /opt/python/3.12.11/bin/python -m venv /opt/python/jupyter && \\
            /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \\
            /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade \\
                "jupyterlab" \\
                notebook \\
                "pwb_jupyterlab" \\
                numpy \\
                pandas && \\
            rm -rf /opt/python/jupyter/lib/python*/site-packages/jupyterlab/tests && \\
            rm -rf /opt/python/jupyter/lib/python*/site-packages/jupyterlab/galata && \\
            rm -rf /opt/python/jupyter/lib/python*/site-packages/tornado/test && \\
            rm -f /opt/python/jupyter/lib/python*/site-packages/jupyterlab/staging/yarn.lock && \\
            ln -s /opt/python/jupyter/bin/jupyter /usr/local/bin/jupyter
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_jupyterlab_workbench_custom_venv_name(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.install_jupyterlab_workbench("3.12.11", jupyter_venv_name="lab") }}
            """
        )
        expected = textwrap.dedent(
            """\
            /opt/python/3.12.11/bin/python -m venv /opt/python/lab && \\
            /opt/python/lab/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \\
            /opt/python/lab/bin/pip install --no-cache-dir --upgrade \\
                "jupyterlab" \\
                notebook \\
                "pwb_jupyterlab" && \\
            rm -rf /opt/python/lab/lib/python*/site-packages/jupyterlab/tests && \\
            rm -rf /opt/python/lab/lib/python*/site-packages/jupyterlab/galata && \\
            rm -rf /opt/python/lab/lib/python*/site-packages/tornado/test && \\
            rm -f /opt/python/lab/lib/python*/site-packages/jupyterlab/staging/yarn.lock && \\
            ln -s /opt/python/lab/bin/jupyter /usr/local/bin/jupyter
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "strip_tests,strip_staging,expected",
        [
            pytest.param(
                True,
                True,
                textwrap.dedent(
                    """\
                    /opt/python/3.12.11/bin/python -m venv /opt/python/jupyter && \\
                    /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \\
                    /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade \\
                        "jupyterlab" \\
                        notebook \\
                        "pwb_jupyterlab" && \\
                    rm -rf /opt/python/jupyter/lib/python*/site-packages/jupyterlab/tests && \\
                    rm -rf /opt/python/jupyter/lib/python*/site-packages/jupyterlab/galata && \\
                    rm -rf /opt/python/jupyter/lib/python*/site-packages/tornado/test && \\
                    rm -f /opt/python/jupyter/lib/python*/site-packages/jupyterlab/staging/yarn.lock && \\
                    ln -s /opt/python/jupyter/bin/jupyter /usr/local/bin/jupyter
                    """
                ),
                id="strip-both",
            ),
            pytest.param(
                True,
                False,
                textwrap.dedent(
                    """\
                    /opt/python/3.12.11/bin/python -m venv /opt/python/jupyter && \\
                    /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \\
                    /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade \\
                        "jupyterlab" \\
                        notebook \\
                        "pwb_jupyterlab" && \\
                    rm -rf /opt/python/jupyter/lib/python*/site-packages/jupyterlab/tests && \\
                    rm -rf /opt/python/jupyter/lib/python*/site-packages/jupyterlab/galata && \\
                    rm -rf /opt/python/jupyter/lib/python*/site-packages/tornado/test && \\
                    ln -s /opt/python/jupyter/bin/jupyter /usr/local/bin/jupyter
                    """
                ),
                id="strip-tests-only",
            ),
            pytest.param(
                False,
                True,
                textwrap.dedent(
                    """\
                    /opt/python/3.12.11/bin/python -m venv /opt/python/jupyter && \\
                    /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \\
                    /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade \\
                        "jupyterlab" \\
                        notebook \\
                        "pwb_jupyterlab" && \\
                    rm -f /opt/python/jupyter/lib/python*/site-packages/jupyterlab/staging/yarn.lock && \\
                    ln -s /opt/python/jupyter/bin/jupyter /usr/local/bin/jupyter
                    """
                ),
                id="strip-staging-only",
            ),
            pytest.param(
                False,
                False,
                textwrap.dedent(
                    """\
                    /opt/python/3.12.11/bin/python -m venv /opt/python/jupyter && \\
                    /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \\
                    /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade \\
                        "jupyterlab" \\
                        notebook \\
                        "pwb_jupyterlab" && \\
                    ln -s /opt/python/jupyter/bin/jupyter /usr/local/bin/jupyter
                    """
                ),
                id="strip-neither",
            ),
        ],
    )
    def test_install_jupyterlab_workbench_strip_toggles(
        self, environment_with_macros, strip_tests, strip_staging, expected
    ):
        template = textwrap.dedent(
            f"""\
            {{%- import "python.j2" as python -%}}
            {{{{ python.install_jupyterlab_workbench("3.12.11", strip_tests={strip_tests}, strip_staging={strip_staging}) }}}}
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_install_jupyterlab_workbench_default(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.run_install_jupyterlab_workbench("3.12.11") }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN /opt/python/3.12.11/bin/python -m venv /opt/python/jupyter && \\
                /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \\
                /opt/python/jupyter/bin/pip install --no-cache-dir --upgrade \\
                    "jupyterlab" \\
                    notebook \\
                    "pwb_jupyterlab" && \\
                rm -rf /opt/python/jupyter/lib/python*/site-packages/jupyterlab/tests && \\
                rm -rf /opt/python/jupyter/lib/python*/site-packages/jupyterlab/galata && \\
                rm -rf /opt/python/jupyter/lib/python*/site-packages/tornado/test && \\
                rm -f /opt/python/jupyter/lib/python*/site-packages/jupyterlab/staging/yarn.lock && \\
                ln -s /opt/python/jupyter/bin/jupyter /usr/local/bin/jupyter
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_install_jupyterlab_workbench_passes_args_through(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "python.j2" as python -%}
            {{ python.run_install_jupyterlab_workbench("3.12.11", jupyter_venv_name="lab", jupyterlab_version_pin="<5", strip_tests=False, strip_staging=False) }}
            """
        )
        expected = textwrap.dedent(
            """\
            RUN /opt/python/3.12.11/bin/python -m venv /opt/python/lab && \\
                /opt/python/lab/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \\
                /opt/python/lab/bin/pip install --no-cache-dir --upgrade \\
                    "jupyterlab<5" \\
                    notebook \\
                    "pwb_jupyterlab" && \\
                ln -s /opt/python/lab/bin/jupyter /usr/local/bin/jupyter
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected


class TestQuartoMacros:
    def test_declare_build_arg_default(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.declare_build_arg() }}
            """
        )
        expected = textwrap.dedent(
            """\
            ARG QUARTO_VERSION
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_declare_build_arg_alternate_name(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.declare_build_arg(name="MY_VERSION_OVERRIDE") }}
            """
        )
        expected = textwrap.dedent(
            """\
            ARG MY_VERSION_OVERRIDE
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_declare_build_arg_with_default(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.declare_build_arg(default="1.8.26") }}
            """
        )
        expected = textwrap.dedent(
            """\
            ARG QUARTO_VERSION=1.8.26
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_build_arg(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.build_arg() }}
            """
        )
        expected = textwrap.dedent(
            """\
            $QUARTO_VERSION
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_build_arg_alternate_name(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.build_arg("MY_VERSION_OVERRIDE") }}
            """
        )
        expected = textwrap.dedent(
            """\
            $MY_VERSION_OVERRIDE
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_get_directory(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.get_directory("1.8.24") }}"""
        )
        expected = "/opt/quarto"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_get_version_directory(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.get_version_directory("1.8.24") }}"""
        )
        expected = "/opt/quarto"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_github_token_secret_mount(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.github_token_secret_mount() }}"""
        )
        expected = "--mount=type=secret,id=github_token,required=false"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    @pytest.mark.parametrize(
        "update_path,home_path,expected",
        [
            pytest.param(
                True,
                None,
                'GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" CI=true /opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt --update-path',
                id="with-update-path",
            ),
            pytest.param(
                False,
                None,
                'GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" CI=true /opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt',
                id="without-update-path",
            ),
            pytest.param(
                False,
                "/root",
                'GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" HOME="/root" CI=true /opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt && "/root"/.TinyTeX/bin/*/tlmgr conf texmf TEXMFVAR \'~/.texlive/texmf-var\'',
                id="with-home-path",
            ),
            pytest.param(
                True,
                "/root",
                'GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" HOME="/root" CI=true /opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt --update-path && "/root"/.TinyTeX/bin/*/tlmgr conf texmf TEXMFVAR \'~/.texlive/texmf-var\'',
                id="with-home-path-and-update-path",
            ),
        ],
    )
    def test_install_tinytex_command(self, environment_with_macros, update_path, home_path, expected):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.install_tinytex_command("/opt/quarto/1.8.24/bin/quarto", update_path, home_path) }}"""
        )
        rendered = environment_with_macros.from_string(template).render(update_path=update_path, home_path=home_path)
        assert rendered == expected

    @pytest.mark.parametrize(
        "with_tinytex,tinytex_update_path,tinytex_home_path,expected",
        [
            pytest.param(
                False,
                False,
                None,
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        quarto=1.8.24 && \\
                    apt-mark hold quarto && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*"""
                ),
                id="without-tinytex",
            ),
            pytest.param(
                False,
                True,
                None,
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        quarto=1.8.24 && \\
                    apt-mark hold quarto && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/*"""
                ),
                id="without-tinytex-update-path-no-effect",
            ),
            pytest.param(
                True,
                False,
                None,
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        quarto=1.8.24 \\
                        xz-utils && \\
                    apt-mark hold quarto && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/* && \\
                    GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" CI=true /opt/quarto/bin/quarto install tinytex --no-prompt"""
                ),
                id="with-tinytex",
            ),
            pytest.param(
                True,
                True,
                None,
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        quarto=1.8.24 \\
                        xz-utils && \\
                    apt-mark hold quarto && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/* && \\
                    GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" CI=true /opt/quarto/bin/quarto install tinytex --no-prompt --update-path"""
                ),
                id="with-tinytex-update-path",
            ),
            pytest.param(
                True,
                False,
                "/root",
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        quarto=1.8.24 \\
                        xz-utils && \\
                    apt-mark hold quarto && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/* && \\
                    GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" HOME="/root" CI=true /opt/quarto/bin/quarto install tinytex --no-prompt && "/root"/.TinyTeX/bin/*/tlmgr conf texmf TEXMFVAR '~/.texlive/texmf-var'"""
                ),
                id="with-tinytex-home-path",
            ),
            pytest.param(
                True,
                True,
                "/root",
                textwrap.dedent(
                    """\
                    apt-get update -yqq && \\
                    apt-get install -yqq --no-install-recommends \\
                        quarto=1.8.24 \\
                        xz-utils && \\
                    apt-mark hold quarto && \\
                    apt-get clean -yqq && \\
                    rm -rf /var/lib/apt/lists/* && \\
                    GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" HOME="/root" CI=true /opt/quarto/bin/quarto install tinytex --no-prompt --update-path && "/root"/.TinyTeX/bin/*/tlmgr conf texmf TEXMFVAR '~/.texlive/texmf-var'"""
                ),
                id="with-tinytex-home-path-update-path",
            ),
        ],
    )
    def test_install(self, environment_with_macros, with_tinytex, tinytex_update_path, tinytex_home_path, expected):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.install(version, with_tinytex, tinytex_update_path, tinytex_home_path) }}"""
        )
        rendered = environment_with_macros.from_string(template).render(
            version="1.8.24",
            with_tinytex=with_tinytex,
            tinytex_update_path=tinytex_update_path,
            tinytex_home_path=tinytex_home_path,
        )
        assert rendered == expected

    def test_install_rhel(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.install("1.8.24", os_family="rhel") }}"""
        )
        expected = textwrap.dedent(
            """\
            dnf install -yq \\
                quarto-1.8.24 \\
                'dnf-command(versionlock)' && \\
            dnf versionlock add quarto && \\
            dnf clean all -yq"""
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_rhel_with_tinytex(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.install("1.8.24", with_tinytex=True, os_family="rhel") }}"""
        )
        expected = textwrap.dedent(
            """\
            dnf install -yq \\
                quarto-1.8.24 \\
                'dnf-command(versionlock)' \\
                xz && \\
            dnf versionlock add quarto && \\
            dnf clean all -yq && \\
            GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" CI=true /opt/quarto/bin/quarto install tinytex --no-prompt"""
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_rejects_invalid_os_family(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.install("1.8.24", os_family="sles") }}"""
        )
        with pytest.raises(Exception, match="Unsupported os_family"):
            environment_with_macros.from_string(template).render()

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                (["1.8.24"], False, False, None),
                textwrap.dedent(
                    """\
                    RUN apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            quarto=1.8.24 && \\
                        apt-mark hold quarto && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/*"""
                ),
                id="single-version-no-tinytex",
            ),
            pytest.param(
                (["1.8.24"], True, False, None),
                textwrap.dedent(
                    """\
                    RUN --mount=type=secret,id=github_token,required=false apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            quarto=1.8.24 \\
                            xz-utils && \\
                        apt-mark hold quarto && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/* && \\
                        GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" CI=true /opt/quarto/bin/quarto install tinytex --no-prompt"""
                ),
                id="single-version-with-tinytex",
            ),
            pytest.param(
                (["1.8.24"], True, True, None),
                textwrap.dedent(
                    """\
                    RUN --mount=type=secret,id=github_token,required=false apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            quarto=1.8.24 \\
                            xz-utils && \\
                        apt-mark hold quarto && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/* && \\
                        GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" CI=true /opt/quarto/bin/quarto install tinytex --no-prompt --update-path"""
                ),
                id="single-version-with-tinytex-update-path",
            ),
            pytest.param(
                (["1.8.24"], True, False, "/root"),
                textwrap.dedent(
                    """\
                    RUN --mount=type=secret,id=github_token,required=false apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            quarto=1.8.24 \\
                            xz-utils && \\
                        apt-mark hold quarto && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/* && \\
                        GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" HOME="/root" CI=true /opt/quarto/bin/quarto install tinytex --no-prompt && "/root"/.TinyTeX/bin/*/tlmgr conf texmf TEXMFVAR '~/.texlive/texmf-var'"""
                ),
                id="single-version-with-tinytex-home-path",
            ),
            pytest.param(
                (["1.8.24"], True, True, "/root"),
                textwrap.dedent(
                    """\
                    RUN --mount=type=secret,id=github_token,required=false apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            quarto=1.8.24 \\
                            xz-utils && \\
                        apt-mark hold quarto && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/* && \\
                        GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" HOME="/root" CI=true /opt/quarto/bin/quarto install tinytex --no-prompt --update-path && "/root"/.TinyTeX/bin/*/tlmgr conf texmf TEXMFVAR '~/.texlive/texmf-var'"""
                ),
                id="single-version-with-tinytex-home-path-update-path",
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

    def test_run_install_rejects_multiple_versions(self, environment_with_macros):
        template = '{%- import "quarto.j2" as quarto -%}\n{{ quarto.run_install(["1.8.24", "1.7.8"]) }}'
        with pytest.raises(Exception, match="Only one Quarto version"):
            environment_with_macros.from_string(template).render()

    def test_symlink_version(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.symlink_version("1.8.24", "/opt/quarto/default") }}"""
        )
        expected = "ln -s /opt/quarto /opt/quarto/default"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_symlink_binary(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "quarto.j2" as quarto -%}
            {{ quarto.symlink_binary("1.8.24", "quarto", "/usr/local/bin/quarto") }}"""
        )
        expected = "ln -s /opt/quarto/bin/quarto /usr/local/bin/quarto"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected


class TestRMacros:
    def test_declare_build_arg_default(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.declare_build_arg() }}
            """
        )
        expected = textwrap.dedent(
            """\
            ARG R_VERSION
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_declare_build_arg_alternate_name(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.declare_build_arg(name="MY_VERSION_OVERRIDE") }}
            """
        )
        expected = textwrap.dedent(
            """\
            ARG MY_VERSION_OVERRIDE
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_declare_build_arg_with_default(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.declare_build_arg(default="4.4.0") }}
            """
        )
        expected = textwrap.dedent(
            """\
            ARG R_VERSION=4.4.0
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_build_arg(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.build_arg() }}
            """
        )
        expected = textwrap.dedent(
            """\
            $R_VERSION
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_build_arg_alternate_name(self, environment_with_macros):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{ r.build_arg("MY_VERSION_OVERRIDE") }}
            """
        )
        expected = textwrap.dedent(
            """\
            $MY_VERSION_OVERRIDE
            """
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

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
            apt-get update -yqq && \\
            apt-get install -yqq --no-install-recommends \\
                r-4.4.3 && \\
            apt-get clean -yqq && \\
            rm -rf /var/lib/apt/lists/*"""
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_rhel(self, environment_with_macros):
        template = '{%- import "r.j2" as r -%}\n{{ r.install("4.4.3", os_family="rhel") }}'
        expected = textwrap.dedent(
            """\
            dnf install -yq \\
                R-4.4.3 && \\
            dnf clean all -yq"""
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_install_rejects_invalid_os_family(self, environment_with_macros):
        template = '{%- import "r.j2" as r -%}\n{{ r.install("4.4.3", os_family="sles") }}'
        with pytest.raises(Exception, match="Unsupported os_family"):
            environment_with_macros.from_string(template).render()

    @pytest.mark.parametrize(
        "input,expected",
        [
            pytest.param(
                ["4.4.3"],
                textwrap.dedent(
                    """\
                    RUN apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            r-4.4.3 && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/*"""
                ),
                id="single-version",
            ),
            pytest.param(
                ["4.4.3", "4.3.3"],
                textwrap.dedent(
                    """\
                    RUN apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            r-4.4.3 && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/*
                    RUN apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            r-4.3.3 && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/*"""
                ),
                id="multiple-versions",
            ),
            pytest.param(
                "'4.4.3,4.3.3'",
                textwrap.dedent(
                    """\
                    RUN apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            r-4.4.3 && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/*
                    RUN apt-get update -yqq && \\
                        apt-get install -yqq --no-install-recommends \\
                            r-4.3.3 && \\
                        apt-get clean -yqq && \\
                        rm -rf /var/lib/apt/lists/*"""
                ),
                id="string-versions",
            ),
        ],
    )
    def test_run_install(self, environment_with_macros, input, expected):
        template = '{%- import "r.j2" as r -%}\n{{ r.run_install(' + str(input) + ") }}"
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_install_link_to_path_off_by_default(self, environment_with_macros):
        template = '{%- import "r.j2" as r -%}\n{{ r.run_install(["4.4.3", "4.5.0"]) }}'
        rendered = environment_with_macros.from_string(template).render()
        assert "ln -s" not in rendered

    @pytest.mark.parametrize(
        "versions,directory",
        [
            pytest.param('["4.4.3", "4.5.0"]', "/opt/R/4.5.0", id="list"),
            pytest.param('["4.5.0", "4.4.3"]', "/opt/R/4.5.0", id="list-reversed"),
            pytest.param('["4.9.0", "4.10.0"]', "/opt/R/4.10.0", id="numeric-ordering"),
            pytest.param('"4.4.3, 4.5.0"', "/opt/R/4.5.0", id="string"),
            pytest.param('["4.4.3"]', "/opt/R/4.4.3", id="single"),
            pytest.param("r.build_arg()", "/opt/R/$R_VERSION", id="build-arg-placeholder"),
        ],
    )
    def test_run_install_link_to_path(self, environment_with_macros, versions, directory):
        template = '{%- import "r.j2" as r -%}\n{{ r.run_install(' + versions + ", link_to_path=True) }}"
        rendered = environment_with_macros.from_string(template).render()
        expected_link = textwrap.dedent(
            f"""\
            RUN {{ if [ -L /usr/local/bin/R ] && [ ! -e /usr/local/bin/R ]; then rm /usr/local/bin/R; fi; [ -e /usr/local/bin/R ] || ln -s {directory}/bin/R /usr/local/bin/R; }} && \\
                {{ if [ -L /usr/local/bin/Rscript ] && [ ! -e /usr/local/bin/Rscript ]; then rm /usr/local/bin/Rscript; fi; [ -e /usr/local/bin/Rscript ] || ln -s {directory}/bin/Rscript /usr/local/bin/Rscript; }}"""
        )
        assert rendered.endswith("\n\n" + expected_link)
        assert rendered.count("ln -s") == 2

    @pytest.mark.parametrize("versions", ["[]", "''"])
    def test_run_install_link_to_path_empty_versions_raises(self, environment_with_macros, versions):
        template = '{%- import "r.j2" as r -%}{{ r.run_install(' + versions + ", link_to_path=True) }}"
        with pytest.raises(BakeryTemplateError, match="maxVersion"):
            environment_with_macros.from_string(template).render()

    def test_run_install_link_to_path_rhel(self, environment_with_macros):
        template = '{%- import "r.j2" as r -%}\n{{ r.run_install(["4.4.3"], os_family="rhel", link_to_path=True) }}'
        expected = textwrap.dedent(
            """\
            RUN dnf install -yq \\
                    R-4.4.3 && \\
                dnf clean all -yq

            RUN { if [ -L /usr/local/bin/R ] && [ ! -e /usr/local/bin/R ]; then rm /usr/local/bin/R; fi; [ -e /usr/local/bin/R ] || ln -s /opt/R/4.4.3/bin/R /usr/local/bin/R; } && \\
                { if [ -L /usr/local/bin/Rscript ] && [ ! -e /usr/local/bin/Rscript ]; then rm /usr/local/bin/Rscript; fi; [ -e /usr/local/bin/Rscript ] || ln -s /opt/R/4.4.3/bin/Rscript /usr/local/bin/Rscript; }"""
        )
        rendered = environment_with_macros.from_string(template).render()
        assert rendered == expected

    def test_run_install_rhel(self, environment_with_macros):
        template = '{%- import "r.j2" as r -%}\n{{ r.run_install(["4.4.3"], os_family="rhel") }}'
        expected = textwrap.dedent(
            """\
            RUN dnf install -yq \\
                    R-4.4.3 && \\
                dnf clean all -yq"""
        )
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

    @pytest.mark.parametrize(
        "_os,expected",
        [
            pytest.param(
                None,
                '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages(c("dplyr", "odbc"), repos="https://p3m.dev/cran/latest", clean = TRUE)\'',
                id="no-os",
            ),
            pytest.param(
                {"Name": "gentoo"},
                '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages(c("dplyr", "odbc"), repos="https://p3m.dev/cran/latest", clean = TRUE)\'',
                id="unsupported-os",
            ),
            pytest.param(
                {"Name": "ubuntu", "Codename": "jammy"},
                '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages(c("dplyr", "odbc"), repos="https://p3m.dev/cran/__linux__/jammy/latest", clean = TRUE)\'',
                id="ubuntu-jammy",
            ),
            pytest.param(
                {"Name": "ubuntu", "Codename": "noble"},
                '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages(c("dplyr", "odbc"), repos="https://p3m.dev/cran/__linux__/noble/latest", clean = TRUE)\'',
                id="ubuntu-noble",
            ),
            pytest.param(
                {"Name": "debian", "Codename": "bookworm"},
                '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages(c("dplyr", "odbc"), repos="https://p3m.dev/cran/__linux__/bookworm/latest", clean = TRUE)\'',
                id="debian-bookworm",
            ),
            pytest.param(
                {"Name": "debian", "Codename": "trixie"},
                '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages(c("dplyr", "odbc"), repos="https://p3m.dev/cran/__linux__/trixie/latest", clean = TRUE)\'',
                id="debian-trixie",
            ),
            pytest.param(
                {"Name": "rhel", "Version": "8"},
                '/opt/R/4.4.3/bin/R --vanilla -e \'install.packages(c("dplyr", "odbc"), repos="https://p3m.dev/cran/__linux__/rhel8/latest", clean = TRUE)\'',
                id="rhel-8",
            ),
        ],
    )
    def test_get_p3m_cran_repo_from_parent_template(self, environment_with_macros, _os, expected):
        template = textwrap.dedent(
            """\
            {%- import "r.j2" as r -%}
            {{- r.install_packages('4.4.3', packages=['dplyr', 'odbc'], _os=os_release) -}}"""
        )
        rendered = environment_with_macros.from_string(template).render(os_release=_os)
        assert rendered.strip() == expected.strip()

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


class TestLinkGuardShellLogic:
    """Run the versioned (`&&` chain) guard against a temp /usr/local/bin for each starting state."""

    @staticmethod
    def _run(tmp_path, setup, on_path=()):
        template = '{%- import "r.j2" as r -%}{{ r.run_install("4.4.3", link_to_path=True) }}'
        return run_link_script(tmp_path, template, "/opt/R", lambda opt, b: setup(b), on_path)

    @pytest.mark.parametrize(
        "template,opt_from,bins,version",
        [
            pytest.param(
                '{%- import "r.j2" as r -%}{{ r.run_install("4.4.3", link_to_path=True) }}',
                "/opt/R",
                ["R", "Rscript"],
                "4.4.3",
                id="r",
            ),
            pytest.param(
                '{%- import "python.j2" as python -%}{{ python.copy_from_build_stage("3.13.7", link_to_path=True) }}',
                "/opt/python",
                ["python", "python3", "pip", "pip3"],
                "3.13.7",
                id="python",
            ),
        ],
    )
    def test_binary_elsewhere_on_path_is_shadowed(self, tmp_path, template, opt_from, bins, version):
        result, local_bin = run_link_script(tmp_path, template, opt_from, on_path=bins)
        assert result.returncode == 0, result.stderr
        for name in bins:
            assert (local_bin / name).readlink() == tmp_path / "opt" / version / "bin" / name

    def test_nothing_present_creates_links(self, tmp_path):
        result, local_bin = self._run(tmp_path, lambda b: None)
        assert result.returncode == 0, result.stderr
        for name in ("R", "Rscript"):
            assert (local_bin / name).readlink() == tmp_path / "opt" / "4.4.3" / "bin" / name

    def test_valid_symlink_is_kept(self, tmp_path):
        target = tmp_path / "keep"
        target.touch()
        result, local_bin = self._run(tmp_path, lambda b: (b / "R").symlink_to(target))
        assert result.returncode == 0, result.stderr
        assert (local_bin / "R").readlink() == target
        assert (local_bin / "Rscript").readlink() == tmp_path / "opt" / "4.4.3" / "bin" / "Rscript"

    def test_real_file_is_kept(self, tmp_path):
        result, local_bin = self._run(tmp_path, lambda b: (b / "R").write_text("real"))
        assert result.returncode == 0, result.stderr
        assert not (local_bin / "R").is_symlink()
        assert (local_bin / "R").read_text() == "real"

    def test_dangling_symlink_is_replaced(self, tmp_path):
        result, local_bin = self._run(tmp_path, lambda b: (b / "R").symlink_to("/nonexistent"))
        assert result.returncode == 0, result.stderr
        assert (local_bin / "R").readlink() == tmp_path / "opt" / "4.4.3" / "bin" / "R"
