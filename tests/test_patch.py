from reviewer_selector.patch import Patch


def test_patch_extracts_file_paths(sample_diff: str):
    patch = Patch(sample_diff)
    files = patch.get_changed_files()
    assert list(files) == ["locales/en/messages.ftl"]


def test_patch_handles_multiple_files(sample_diff_multiple_files: str):
    patch = Patch(sample_diff_multiple_files)
    files = patch.get_changed_files()
    assert "file1.py" in files
    assert "dir/file2.js" in files


def test_patch_empty_diff():
    patch = Patch("")
    files = patch.get_changed_files()
    assert files == []
