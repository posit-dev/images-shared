import pytest

from posit_bakery.config.dirdiff import FileDiff, diff_directories, read_directory_tree, render_markdown


class TestReadDirectoryTree:
    def test_reads_nested_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello\n")
        nested = tmp_path / "sub"
        nested.mkdir()
        (nested / "b.txt").write_text("world\n")

        tree = read_directory_tree(tmp_path)

        assert tree == {
            "a.txt": b"hello\n",
            "sub/b.txt": b"world\n",
        }

    def test_reads_binary_file(self, tmp_path):
        (tmp_path / "bin.dat").write_bytes(b"\x00\x01\x02")

        tree = read_directory_tree(tmp_path)

        assert tree == {"bin.dat": b"\x00\x01\x02"}

    def test_empty_directory(self, tmp_path):
        assert read_directory_tree(tmp_path) == {}

    def test_nonexistent_path_raises_file_not_found_error(self, tmp_path):
        missing = tmp_path / "does-not-exist"

        with pytest.raises(FileNotFoundError):
            read_directory_tree(missing)


class TestDiffDirectories:
    def test_identical_trees_produce_no_diffs(self):
        tree = {"a.txt": b"hello\n"}
        assert diff_directories(tree, dict(tree)) == []

    def test_added_file(self):
        old = {}
        new = {"a.txt": b"hello\n"}

        result = diff_directories(old, new)

        assert len(result) == 1
        assert result[0].path == "a.txt"
        assert result[0].status == "added"
        assert "+hello" in result[0].diff_text

    def test_removed_file(self):
        old = {"a.txt": b"hello\n"}
        new = {}

        result = diff_directories(old, new)

        assert len(result) == 1
        assert result[0].path == "a.txt"
        assert result[0].status == "removed"
        assert "-hello" in result[0].diff_text

    def test_modified_text_file(self):
        old = {"a.txt": b"line one\nline two\n"}
        new = {"a.txt": b"line one\nline TWO\n"}

        result = diff_directories(old, new)

        assert len(result) == 1
        assert result[0].status == "modified"
        assert "-line two" in result[0].diff_text
        assert "+line TWO" in result[0].diff_text

    def test_binary_file_changed(self):
        old = {"bin.dat": b"\x00\x01"}
        new = {"bin.dat": b"\x00\x02"}

        result = diff_directories(old, new)

        assert len(result) == 1
        assert result[0].status == "binary"
        assert result[0].diff_text is None

    def test_unchanged_file_omitted_alongside_changed_one(self):
        old = {"same.txt": b"unchanged\n", "changed.txt": b"before\n"}
        new = {"same.txt": b"unchanged\n", "changed.txt": b"after\n"}

        result = diff_directories(old, new)

        assert [fd.path for fd in result] == ["changed.txt"]


class TestRenderMarkdown:
    def test_no_diffs_renders_no_differences_message(self):
        markdown = render_markdown("connect", [])

        assert "<details open>" in markdown
        assert "<summary><code>connect</code></summary>" in markdown
        assert "No differences from previous edition" in markdown

    def test_full_diff_renders_nested_details_per_file(self):
        file_diffs = [
            FileDiff(path="Containerfile", status="modified", diff_text="--- a/Containerfile\n+++ b/Containerfile\n"),
        ]

        markdown = render_markdown("connect", file_diffs)

        assert markdown.count("<details open>") == 2  # image-level + one file-level
        assert "<summary><code>Containerfile</code></summary>" in markdown
        assert "```diff" in markdown

    def test_binary_file_shows_placeholder_not_diff_fence(self):
        file_diffs = [FileDiff(path="image.png", status="binary", diff_text=None)]

        markdown = render_markdown("connect", file_diffs)

        assert "_Binary file changed._" in markdown
        assert "```diff" not in markdown

    def test_oversized_diff_falls_back_to_flat_list(self):
        file_diffs = [
            FileDiff(path="big.txt", status="modified", diff_text="+" + ("x" * 500)),
        ]

        markdown = render_markdown("connect", file_diffs, max_chars=50)

        assert "Diff too large to display in full" in markdown
        assert "`big.txt` (modified)" in markdown
        assert "```diff" not in markdown

    def test_diff_text_with_backtick_fence_uses_wider_fence(self):
        # The diffed file's own content happens to contain a fenced code block
        # (e.g. a README with an embedded ```python example). A hardcoded
        # triple-backtick wrapper would close early on that content and
        # corrupt the rest of the rendered comment.
        diff_text = (
            "--- a/README.md\n+++ b/README.md\n@@ -1,2 +1,4 @@\n existing line\n+```python\n+print('hi')\n+```\n"
        )
        file_diffs = [FileDiff(path="README.md", status="modified", diff_text=diff_text)]

        markdown = render_markdown("connect", file_diffs)

        # The embedded ``` fence survives unbroken inside the wider wrapper.
        assert diff_text in markdown
        # The wrapping fence is longer (4 backticks) than the embedded run (3).
        assert "````diff" in markdown
        assert markdown.count("````") == 2  # opening + closing fence only

    def test_multiple_files_render_as_separate_nested_sections(self):
        file_diffs = [
            FileDiff(
                path="Containerfile",
                status="modified",
                diff_text="--- a/Containerfile\n+++ b/Containerfile\n@@ -1 +1 @@\n-old\n+new\n",
            ),
            FileDiff(
                path="deps/packages.txt",
                status="added",
                diff_text="--- a/deps/packages.txt\n+++ b/deps/packages.txt\n@@ -0,0 +1 @@\n+new-package\n",
            ),
        ]

        markdown = render_markdown("connect", file_diffs)

        assert markdown.count("<details open>") == 3  # image-level + 2 file-level
        assert "<summary><code>Containerfile</code></summary>" in markdown
        assert "<summary><code>deps/packages.txt</code></summary>" in markdown
        assert markdown.count("```diff") == 2
