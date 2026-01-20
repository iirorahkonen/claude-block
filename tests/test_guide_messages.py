"""
Guide message tests for the block plugin.
"""
from tests.conftest import (
    create_block_file,
    make_edit_input,
    run_hook,
    is_blocked,
)


class TestGuideMessages:
    """Tests for guide message functionality."""

    def test_shows_global_guide_message_when_blocked(self, test_dir, hooks_dir):
        """Global guide message should be shown when blocked."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"guide": "This project is read-only for Claude."}')
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "This project is read-only for Claude." in stdout

    def test_shows_pattern_specific_guide_message(self, test_dir, hooks_dir):
        """Pattern-specific guide message should be shown."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": [{"pattern": "*.env*", "guide": "Environment files are sensitive!"}]}')
        input_json = make_edit_input(str(project_dir / ".env.local"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "Environment files are sensitive!" in stdout

    def test_pattern_specific_guide_takes_precedence_over_global(self, test_dir, hooks_dir):
        """Pattern-specific guide should take precedence over global guide."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '''
        {
            "blocked": [{"pattern": "*.secret", "guide": "Secret files protected"}, "*.other"],
            "guide": "General protection message"
        }
        ''')

        # Pattern-specific guide
        input_json = make_edit_input(str(project_dir / "api.secret"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)
        assert "Secret files protected" in stdout
        assert "General protection message" not in stdout

        # Falls back to global guide for pattern without specific guide
        input_json = make_edit_input(str(project_dir / "file.other"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)
        assert "General protection message" in stdout

    def test_allowed_list_with_pattern_guide_shows_global_guide_when_blocked(self, test_dir, hooks_dir):
        """Allowed list should show global guide when file is blocked."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '''
        {
            "allowed": [{"pattern": "*.test.ts", "guide": "Test files allowed"}],
            "guide": "Only test files can be edited"
        }
        ''')

        # Non-matching file should be blocked and show guide
        input_json = make_edit_input(str(project_dir / "app.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)
        assert "Only test files can be edited" in stdout

        # Matching file should be allowed
        input_json = make_edit_input(str(project_dir / "app.test.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

    def test_default_block_reason_when_no_guide(self, test_dir, hooks_dir):
        """Default block message should be shown when no guide specified."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{}')
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "BLOCKED" in stdout or "protected" in stdout
