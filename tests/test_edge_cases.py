"""
Edge case tests for the block plugin.
"""
from tests.conftest import (
    create_block_file,
    make_edit_input,
    make_write_input,
    make_bash_input,
    run_hook,
    is_blocked,
)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_empty_input_gracefully(self, hooks_dir):
        """Should handle empty input gracefully."""
        exit_code, stdout, stderr = run_hook(hooks_dir, "")
        assert exit_code == 0

    def test_handles_malformed_json_input_gracefully(self, hooks_dir):
        """Should handle malformed JSON input gracefully."""
        exit_code, stdout, stderr = run_hook(hooks_dir, "not json")
        assert exit_code == 0

    def test_handles_missing_tool_name_gracefully(self, hooks_dir):
        """Should handle missing tool_name gracefully."""
        exit_code, stdout, stderr = run_hook(hooks_dir, "{}")
        assert exit_code == 0

    def test_handles_paths_with_spaces(self, test_dir, hooks_dir):
        """Should handle paths with spaces."""
        project_dir = test_dir / "my project"
        create_block_file(project_dir)
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_closest_block_file_takes_precedence(self, test_dir, hooks_dir):
        """Closest .block file should take precedence."""
        # Parent directory blocks everything
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        # Child directory allows .txt files
        src_dir = project_dir / "src"
        create_block_file(src_dir, '{"allowed": ["*.txt"]}')

        # File in child directory should follow child's rules
        input_json = make_edit_input(str(src_dir / "notes.txt"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

        # Non-allowed file should be blocked
        input_json = make_edit_input(str(src_dir / "code.js"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)


class TestPathPatterns:
    """Tests for path pattern relative to .block directory."""

    def test_patterns_are_relative_to_block_directory_root_level(self, test_dir, hooks_dir):
        """Patterns should be relative to .block directory at root level."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": ["src/**"]}')
        components_dir = project_dir / "src" / "components"
        components_dir.mkdir(parents=True)

        # File in src/ should be blocked
        input_json = make_edit_input(str(project_dir / "src" / "index.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # File in src/components/ should be blocked
        input_json = make_edit_input(str(components_dir / "Button.tsx"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # File outside src/ should be allowed
        input_json = make_edit_input(str(project_dir / "README.md"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

    def test_patterns_are_relative_to_block_directory_nested_level(self, test_dir, hooks_dir):
        """Patterns should be relative to .block directory at nested level."""
        project_dir = test_dir / "project"
        src_dir = project_dir / "src"
        components_dir = src_dir / "components"
        components_dir.mkdir(parents=True)
        create_block_file(src_dir, '{"blocked": ["components/**"]}')

        # File in components/ should be blocked (relative to src/)
        input_json = make_edit_input(str(components_dir / "Button.tsx"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # File directly in src/ should be allowed
        input_json = make_edit_input(str(src_dir / "index.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

    def test_direct_file_pattern_works_at_any_level(self, test_dir, hooks_dir):
        """Direct file pattern should work at any level."""
        project_dir = test_dir / "project"
        nested_dir = project_dir / "deep" / "nested" / "dir"
        nested_dir.mkdir(parents=True)
        create_block_file(project_dir, '{"blocked": ["**config.json"]}')

        # config.json at root should be blocked
        input_json = make_edit_input(str(project_dir / "config.json"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # config.json in nested dir should be blocked
        input_json = make_edit_input(str(nested_dir / "config.json"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # other.json should be allowed
        input_json = make_edit_input(str(project_dir / "other.json"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

    def test_allowed_pattern_with_explicit_path_works_correctly(self, test_dir, hooks_dir):
        """Allowed pattern with explicit path should work correctly."""
        project_dir = test_dir / "project"
        auth_dir = project_dir / "src" / "features" / "auth"
        dashboard_dir = project_dir / "src" / "features" / "dashboard"
        auth_dir.mkdir(parents=True)
        dashboard_dir.mkdir(parents=True)
        create_block_file(project_dir, '{"allowed": ["src/features/auth/**"]}')

        # File in auth feature should be allowed
        input_json = make_edit_input(str(auth_dir / "login.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

        # File in dashboard feature should be blocked
        input_json = make_edit_input(str(dashboard_dir / "index.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

    def test_multiple_directory_levels_with_different_configs(self, test_dir, hooks_dir):
        """Multiple directory levels with different configs should work."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": ["src/**"]}')
        # src: block generated files
        src_dir = project_dir / "src"
        generated_dir = src_dir / "generated"
        generated_dir.mkdir(parents=True)
        create_block_file(src_dir, '{"blocked": ["generated/**"]}')

        # File in src/ follows src's rules (which blocks generated/)
        input_json = make_edit_input(str(src_dir / "index.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

        # Generated file is blocked by src's .block
        input_json = make_edit_input(str(generated_dir / "types.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)


class TestProtectionGuarantees:
    """Tests to verify protection guarantees."""

    def test_hook_block_decision_prevents_file_modification(self, test_dir, hooks_dir):
        """Hook block decision should prevent file modification."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        project_dir.mkdir(exist_ok=True)
        existing_file = project_dir / "existing.txt"
        existing_file.write_text("original content")

        input_json = make_edit_input(str(existing_file))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        # Hook must output JSON block decision
        assert is_blocked(stdout)

        # File content must be unchanged (hook runs BEFORE tool execution)
        assert existing_file.read_text() == "original content"

    def test_blocked_write_operation_never_creates_file(self, test_dir, hooks_dir):
        """Blocked Write operation should never create file."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)

        new_file = project_dir / "new-file.txt"
        input_json = make_write_input(str(new_file))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        # File must NOT exist (hook prevents creation)
        assert not new_file.exists()

    def test_blocked_bash_rm_never_deletes_file(self, test_dir, hooks_dir):
        """Blocked Bash rm should never delete file."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        project_dir.mkdir(exist_ok=True)
        keep_file = project_dir / "keep.txt"
        keep_file.write_text("protected")

        input_json = make_bash_input(f"rm {keep_file}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        # File must still exist
        assert keep_file.exists()

    def test_allowed_operations_proceed_normally(self, test_dir, hooks_dir):
        """Allowed operations should proceed normally."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": ["*.txt"]}')
        project_dir.mkdir(exist_ok=True)

        input_json = make_edit_input(str(project_dir / "allowed.txt"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        # Hook allows with exit code 0
        assert exit_code == 0
        assert not is_blocked(stdout)
