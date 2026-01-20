"""
Blocked pattern tests for the block plugin.
"""
from tests.conftest import (
    create_block_file,
    make_edit_input,
    run_hook,
    is_blocked,
)


class TestBlockedPatterns:
    """Tests for blocked list patterns."""

    def test_blocked_list_blocks_matching_file(self, test_dir, hooks_dir):
        """Blocked list should block matching files."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": ["*.secret"]}')
        input_json = make_edit_input(str(project_dir / "config.secret"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "BLOCKED" in stdout or "blocked pattern" in stdout

    def test_blocked_list_allows_non_matching_file(self, test_dir, hooks_dir):
        """Blocked list should allow non-matching files."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": ["*.secret"]}')
        input_json = make_edit_input(str(project_dir / "config.json"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert exit_code == 0
        assert not is_blocked(stdout)

    def test_blocked_list_blocks_nested_directory_with_double_asterisk(self, test_dir, hooks_dir):
        """Blocked list with ** should block nested directories."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": ["node_modules/**/*"]}')
        nested_dir = project_dir / "node_modules" / "package" / "dist"
        nested_dir.mkdir(parents=True)
        input_json = make_edit_input(str(nested_dir / "index.js"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_blocked_list_multiple_patterns_all_work(self, test_dir, hooks_dir):
        """Multiple blocked patterns should all work."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": ["*.lock", "*.env", "dist/**"]}')

        # Test .lock file
        input_json = make_edit_input(str(project_dir / "yarn.lock"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Test .env file
        input_json = make_edit_input(str(project_dir / "app.env"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Test dist directory
        dist_dir = project_dir / "dist"
        dist_dir.mkdir(parents=True)
        input_json = make_edit_input(str(dist_dir / "bundle.js"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Non-blocked file should be allowed
        input_json = make_edit_input(str(project_dir / "src" / "index.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

    def test_empty_blocked_array_allows_all(self, test_dir, hooks_dir):
        """Empty blocked array should allow everything."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": []}')
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert exit_code == 0
        assert not is_blocked(stdout)
