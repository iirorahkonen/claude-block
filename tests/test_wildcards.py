"""
Wildcard pattern tests for the block plugin.
"""
from tests.conftest import (
    create_block_file,
    make_edit_input,
    run_hook,
    is_blocked,
)


class TestWildcards:
    """Tests for wildcard pattern matching."""

    def test_single_asterisk_does_not_match_path_separator(self, test_dir, hooks_dir):
        """Single asterisk should not match path separator."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": ["src/*.ts"]}')
        deep_dir = project_dir / "src" / "deep"
        deep_dir.mkdir(parents=True)

        # Should match direct child
        input_json = make_edit_input(str(project_dir / "src" / "index.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Should NOT match nested file (single * doesn't cross directories)
        input_json = make_edit_input(str(deep_dir / "nested.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

    def test_double_asterisk_matches_path_separator(self, test_dir, hooks_dir):
        """Double asterisk should match path separator."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": ["src/**/*.ts"]}')
        nested_dir = project_dir / "src" / "deep" / "nested"
        nested_dir.mkdir(parents=True)

        # Should match nested file
        input_json = make_edit_input(str(nested_dir / "file.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

    def test_question_mark_matches_single_character(self, test_dir, hooks_dir):
        """Question mark should match single character."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": ["file?.txt"]}')

        # Should match file1.txt
        input_json = make_edit_input(str(project_dir / "file1.txt"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Should NOT match file12.txt
        input_json = make_edit_input(str(project_dir / "file12.txt"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

    def test_pattern_with_dots_works_correctly(self, test_dir, hooks_dir):
        """Patterns with dots should work correctly."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": ["*.config.ts"]}')

        # Should match
        input_json = make_edit_input(str(project_dir / "app.config.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Should NOT match (dots are literal)
        input_json = make_edit_input(str(project_dir / "appXconfigXts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0
