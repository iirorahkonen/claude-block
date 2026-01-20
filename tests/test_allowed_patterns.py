"""
Allowed pattern tests for the block plugin.
"""
from tests.conftest import (
    create_block_file,
    make_edit_input,
    run_hook,
    is_blocked,
)


class TestAllowedPatterns:
    """Tests for allowed list patterns."""

    def test_allowed_list_allows_matching_file(self, test_dir, hooks_dir):
        """Allowed list should allow matching files."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": ["*.txt"]}')
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert exit_code == 0
        assert not is_blocked(stdout)

    def test_allowed_list_blocks_non_matching_file(self, test_dir, hooks_dir):
        """Allowed list should block non-matching files."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": ["*.txt"]}')
        input_json = make_edit_input(str(project_dir / "file.js"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "BLOCKED" in stdout or "not in the allowed list" in stdout

    def test_allowed_list_allows_nested_matching_file_with_double_asterisk(self, test_dir, hooks_dir):
        """Allowed list with ** should allow nested matching files."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": ["src/**/*.ts"]}')
        deep_dir = project_dir / "src" / "deep"
        deep_dir.mkdir(parents=True)
        input_json = make_edit_input(str(deep_dir / "file.ts"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert exit_code == 0
        assert not is_blocked(stdout)

    def test_allowed_list_blocks_file_outside_allowed_pattern(self, test_dir, hooks_dir):
        """Allowed list should block files outside allowed patterns."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": ["src/**/*.ts"]}')
        lib_dir = project_dir / "lib"
        lib_dir.mkdir(parents=True)
        input_json = make_edit_input(str(lib_dir / "file.ts"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_allowed_list_allows_multiple_patterns(self, test_dir, hooks_dir):
        """Allowed list should allow multiple patterns."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": ["*.md", "*.txt", "docs/**/*"]}')
        docs_dir = project_dir / "docs" / "guide"
        docs_dir.mkdir(parents=True)

        # Test .md file
        input_json = make_edit_input(str(project_dir / "README.md"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

        # Test .txt file
        input_json = make_edit_input(str(project_dir / "notes.txt"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

        # Test docs subdirectory
        input_json = make_edit_input(str(docs_dir / "intro.html"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

    def test_empty_allowed_array_treated_as_block_all(self, test_dir, hooks_dir):
        """Empty allowed array should behave like block all."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": []}')
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
