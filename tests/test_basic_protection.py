"""
Basic protection tests for the block plugin.
"""
from tests.conftest import (
    create_block_file,
    make_edit_input,
    run_hook,
    is_blocked,
)


class TestBasicProtection:
    """Tests for basic protection functionality."""

    def test_allows_operations_when_no_block_file_exists(self, test_dir, hooks_dir):
        """Operations should be allowed when no .block file exists."""
        project_dir = test_dir / "project" / "src"
        project_dir.mkdir(parents=True)
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert exit_code == 0
        assert not is_blocked(stdout)

    def test_blocks_operations_when_empty_block_file_exists(self, test_dir, hooks_dir):
        """Operations should be blocked when empty .block file exists."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)
        input_json = make_edit_input(str(src_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "BLOCKED" in stdout or "protected" in stdout

    def test_blocks_operations_when_block_contains_empty_json(self, test_dir, hooks_dir):
        """Operations should be blocked when .block contains empty JSON object."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{}')
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)
        input_json = make_edit_input(str(src_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "BLOCKED" in stdout or "protected" in stdout

    def test_blocks_nested_directory_when_parent_has_block(self, test_dir, hooks_dir):
        """Nested directories should be blocked when parent has .block."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        nested_dir = project_dir / "src" / "deep" / "nested"
        nested_dir.mkdir(parents=True)
        input_json = make_edit_input(str(nested_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
