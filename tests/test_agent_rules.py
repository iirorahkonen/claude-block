"""
Tests for agent-specific blocking rules.

Covers:
- should_apply_to_agent decision logic
- Agent config parsing from .block files
- Agent config merging (same-directory and hierarchical)
- Agent resolution from tool_use_id + transcripts
- End-to-end hook invocation with agent context
- Parallel subagent scenarios
"""
import importlib.util
import json
from pathlib import Path

from tests.conftest import (
    create_agent_tracking_file,
    create_agent_transcript,
    create_block_file,
    get_block_reason,
    is_blocked,
    make_bash_input_with_agent,
    make_edit_input_with_agent,
    run_hook,
)

# Import functions under test via importlib to avoid polluting sys.path
# (adding hooks/ to sys.path causes pytest to collect test_* functions
# from protect_directories.py)
_spec = importlib.util.spec_from_file_location(
    "protect_directories",
    str(Path(__file__).parent.parent / "hooks" / "protect_directories.py"),
)
assert _spec is not None and _spec.loader is not None, "Failed to load protect_directories.py"
_pd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pd)

_config_has_agent_rules = _pd._config_has_agent_rules
_create_empty_config = _pd._create_empty_config
get_lock_file_config = _pd.get_lock_file_config
merge_configs = _pd.merge_configs
_merge_hierarchical_configs = _pd._merge_hierarchical_configs
resolve_agent_type = _pd.resolve_agent_type
should_apply_to_agent = _pd.should_apply_to_agent


# ---------------------------------------------------------------------------
# TestShouldApplyToAgent — unit tests for the decision function
# ---------------------------------------------------------------------------

class TestShouldApplyToAgent:
    """Unit tests for should_apply_to_agent()."""

    def test_no_agent_keys_applies_to_main(self):
        """No agent keys → applies to main agent."""
        config = _create_empty_config()
        assert should_apply_to_agent(config, None) is True

    def test_no_agent_keys_applies_to_any_subagent(self):
        """No agent keys → applies to any subagent."""
        config = _create_empty_config()
        assert should_apply_to_agent(config, "Explore") is True
        assert should_apply_to_agent(config, "code-reviewer") is True

    def test_agents_list_exempts_main(self):
        """agents: ["Explore"] → does NOT apply to main agent (agents key targets subagents only)."""
        config = _create_empty_config(agents=["Explore"], has_agents_key=True)
        assert should_apply_to_agent(config, None) is False

    def test_agents_list_applies_to_listed_subagent(self):
        """agents: ["Explore"] → applies to Explore subagent."""
        config = _create_empty_config(agents=["Explore"], has_agents_key=True)
        assert should_apply_to_agent(config, "Explore") is True

    def test_agents_list_does_not_apply_to_other_subagent(self):
        """agents: ["Explore"] → does NOT apply to other subagent types."""
        config = _create_empty_config(agents=["Explore"], has_agents_key=True)
        assert should_apply_to_agent(config, "code-reviewer") is False

    def test_disable_main_does_not_apply_to_main(self):
        """disable_main_agent: true → does NOT apply to main agent."""
        config = _create_empty_config(disable_main_agent=True, has_disable_main_agent_key=True)
        assert should_apply_to_agent(config, None) is False

    def test_disable_main_applies_to_all_subagents(self):
        """disable_main_agent: true → applies to all subagents."""
        config = _create_empty_config(disable_main_agent=True, has_disable_main_agent_key=True)
        assert should_apply_to_agent(config, "Explore") is True
        assert should_apply_to_agent(config, "code-reviewer") is True

    def test_agents_plus_disable_main_does_not_apply_to_main(self):
        """agents: ["Explore"] + disable_main_agent: true → does NOT apply to main."""
        config = _create_empty_config(
            agents=["Explore"], has_agents_key=True,
            disable_main_agent=True, has_disable_main_agent_key=True,
        )
        assert should_apply_to_agent(config, None) is False

    def test_agents_plus_disable_main_applies_to_listed(self):
        """agents: ["Explore"] + disable_main_agent: true → applies to Explore."""
        config = _create_empty_config(
            agents=["Explore"], has_agents_key=True,
            disable_main_agent=True, has_disable_main_agent_key=True,
        )
        assert should_apply_to_agent(config, "Explore") is True

    def test_agents_plus_disable_main_does_not_apply_to_other(self):
        """agents: ["Explore"] + disable_main_agent: true → does NOT apply to other subagents."""
        config = _create_empty_config(
            agents=["Explore"], has_agents_key=True,
            disable_main_agent=True, has_disable_main_agent_key=True,
        )
        assert should_apply_to_agent(config, "Plan") is False

    def test_empty_agents_list_exempts_main(self):
        """agents: [] → does NOT apply to main agent (agents key targets subagents only)."""
        config = _create_empty_config(agents=[], has_agents_key=True)
        assert should_apply_to_agent(config, None) is False

    def test_empty_agents_list_does_not_apply_to_subagent(self):
        """agents: [] → does NOT apply to any subagent."""
        config = _create_empty_config(agents=[], has_agents_key=True)
        assert should_apply_to_agent(config, "Explore") is False

    def test_empty_agents_plus_disable_main_applies_to_nobody(self):
        """agents: [] + disable_main_agent: true → does NOT apply to anyone."""
        config = _create_empty_config(
            agents=[], has_agents_key=True,
            disable_main_agent=True, has_disable_main_agent_key=True,
        )
        assert should_apply_to_agent(config, None) is False
        assert should_apply_to_agent(config, "Explore") is False

    def test_multiple_agent_types_in_list(self):
        """Multiple agent types in list → all listed types match."""
        config = _create_empty_config(
            agents=["Explore", "code-reviewer", "Plan"], has_agents_key=True,
        )
        assert should_apply_to_agent(config, "Explore") is True
        assert should_apply_to_agent(config, "code-reviewer") is True
        assert should_apply_to_agent(config, "Plan") is True
        assert should_apply_to_agent(config, "other-agent") is False


# ---------------------------------------------------------------------------
# TestAgentConfigParsing — parsing new keys from .block files
# ---------------------------------------------------------------------------

class TestAgentConfigParsing:
    """Tests for parsing agent keys from .block files."""

    def test_block_with_agents_key(self, tmp_path):
        """.block with agents key → parsed as list."""
        block_file = create_block_file(tmp_path, json.dumps({"agents": ["Explore"]}))
        config = get_lock_file_config(str(block_file))
        assert config["agents"] == ["Explore"]
        assert config["has_agents_key"] is True

    def test_block_without_agents_key(self, tmp_path):
        """.block without agents key → agents is None (not empty list)."""
        block_file = create_block_file(tmp_path, json.dumps({"blocked": ["*.log"]}))
        config = get_lock_file_config(str(block_file))
        assert config["agents"] is None
        assert config["has_agents_key"] is False

    def test_block_with_disable_main_agent(self, tmp_path):
        """.block with disable_main_agent: true → parsed correctly."""
        block_file = create_block_file(tmp_path, json.dumps({"disable_main_agent": True}))
        config = get_lock_file_config(str(block_file))
        assert config["disable_main_agent"] is True
        assert config["has_disable_main_agent_key"] is True

    def test_block_without_disable_main_agent(self, tmp_path):
        """.block without disable_main_agent → defaults to False."""
        block_file = create_block_file(tmp_path, json.dumps({"blocked": ["*.log"]}))
        config = get_lock_file_config(str(block_file))
        assert config["disable_main_agent"] is False
        assert config["has_disable_main_agent_key"] is False

    def test_block_with_agents_and_blocked_patterns(self, tmp_path):
        """.block with agents + standard blocked patterns → both parsed."""
        content = json.dumps({"blocked": ["*.config"], "agents": ["Explore"]})
        block_file = create_block_file(tmp_path, content)
        config = get_lock_file_config(str(block_file))
        assert config["blocked"] == ["*.config"]
        assert config["agents"] == ["Explore"]

    def test_block_with_agents_and_allowed_patterns(self, tmp_path):
        """.block with agents + allowed patterns → both parsed."""
        content = json.dumps({"allowed": ["docs/**"], "agents": ["Explore"]})
        block_file = create_block_file(tmp_path, content)
        config = get_lock_file_config(str(block_file))
        assert config["allowed"] == ["docs/**"]
        assert config["agents"] == ["Explore"]

    def test_empty_block_file_defaults(self, tmp_path):
        """Empty .block (block all) → agent fields default to None/False."""
        block_file = create_block_file(tmp_path)
        config = get_lock_file_config(str(block_file))
        assert config["agents"] is None
        assert config["disable_main_agent"] is False

    def test_block_with_only_agents_key(self, tmp_path):
        """.block with only agents key (no patterns) → still valid config."""
        block_file = create_block_file(tmp_path, json.dumps({"agents": ["Explore"]}))
        config = get_lock_file_config(str(block_file))
        assert config["agents"] == ["Explore"]
        assert config["is_empty"] is True  # No patterns = empty (block all)


# ---------------------------------------------------------------------------
# TestAgentConfigMerge — same-directory .block + .block.local merge
# ---------------------------------------------------------------------------

class TestAgentConfigMerge:
    """Tests for agent field merging between .block and .block.local."""

    def test_main_has_agents_local_doesnt(self, tmp_path):
        """Main has agents, local doesn't → main's agents preserved."""
        main_config = _create_empty_config(
            blocked=["*.log"], is_empty=False, has_blocked_key=True,
            agents=["Explore"], has_agents_key=True,
        )
        local_config = _create_empty_config(
            blocked=["*.tmp"], is_empty=False, has_blocked_key=True,
        )
        merged = merge_configs(main_config, local_config)
        assert merged["agents"] == ["Explore"]
        assert merged["has_agents_key"] is True

    def test_local_has_agents_main_doesnt(self, tmp_path):
        """Local has agents, main doesn't → local's agents used."""
        main_config = _create_empty_config(
            blocked=["*.log"], is_empty=False, has_blocked_key=True,
        )
        local_config = _create_empty_config(
            blocked=["*.tmp"], is_empty=False, has_blocked_key=True,
            agents=["code-reviewer"], has_agents_key=True,
        )
        merged = merge_configs(main_config, local_config)
        assert merged["agents"] == ["code-reviewer"]
        assert merged["has_agents_key"] is True

    def test_both_have_agents_local_overrides(self):
        """Both have agents → local overrides main."""
        main_config = _create_empty_config(
            blocked=["*.log"], is_empty=False, has_blocked_key=True,
            agents=["Explore"], has_agents_key=True,
        )
        local_config = _create_empty_config(
            blocked=["*.tmp"], is_empty=False, has_blocked_key=True,
            agents=["Plan"], has_agents_key=True,
        )
        merged = merge_configs(main_config, local_config)
        assert merged["agents"] == ["Plan"]

    def test_main_has_disable_local_doesnt(self):
        """Main has disable_main_agent, local doesn't → main's value preserved."""
        main_config = _create_empty_config(
            blocked=["*.log"], is_empty=False, has_blocked_key=True,
            disable_main_agent=True, has_disable_main_agent_key=True,
        )
        local_config = _create_empty_config(
            blocked=["*.tmp"], is_empty=False, has_blocked_key=True,
        )
        merged = merge_configs(main_config, local_config)
        assert merged["disable_main_agent"] is True
        assert merged["has_disable_main_agent_key"] is True

    def test_local_disable_overrides_main(self):
        """Local has disable_main_agent: true, main has false → local wins."""
        main_config = _create_empty_config(
            blocked=["*.log"], is_empty=False, has_blocked_key=True,
            disable_main_agent=False, has_disable_main_agent_key=True,
        )
        local_config = _create_empty_config(
            blocked=["*.tmp"], is_empty=False, has_blocked_key=True,
            disable_main_agent=True, has_disable_main_agent_key=True,
        )
        merged = merge_configs(main_config, local_config)
        assert merged["disable_main_agent"] is True

    def test_agent_fields_merge_with_existing_fields(self):
        """Agent fields merge correctly alongside existing blocked/allowed/guide merging."""
        main_config = _create_empty_config(
            blocked=["*.log"], is_empty=False, has_blocked_key=True,
            guide="Main guide",
            agents=["Explore"], has_agents_key=True,
            disable_main_agent=True, has_disable_main_agent_key=True,
        )
        local_config = _create_empty_config(
            blocked=["*.tmp"], is_empty=False, has_blocked_key=True,
            guide="Local guide",
        )
        merged = merge_configs(main_config, local_config)
        assert "*.log" in merged["blocked"]
        assert "*.tmp" in merged["blocked"]
        assert merged["guide"] == "Local guide"
        assert merged["agents"] == ["Explore"]
        assert merged["disable_main_agent"] is True


# ---------------------------------------------------------------------------
# TestAgentConfigHierarchical — child + parent directory merge
# ---------------------------------------------------------------------------

class TestAgentConfigHierarchical:
    """Tests for agent field merging in hierarchical (parent/child) configs."""

    def test_child_has_agents_parent_doesnt(self):
        """Child has agents, parent doesn't → child's agents used."""
        child = _create_empty_config(
            blocked=["*.log"], is_empty=False, has_blocked_key=True,
            agents=["Explore"], has_agents_key=True,
        )
        parent = _create_empty_config(
            blocked=["*.tmp"], is_empty=False, has_blocked_key=True,
        )
        merged = _merge_hierarchical_configs(child, parent)
        assert merged["agents"] == ["Explore"]
        assert merged["has_agents_key"] is True

    def test_parent_has_agents_child_doesnt(self):
        """Parent has agents, child doesn't → parent's agents inherited."""
        child = _create_empty_config(
            blocked=["*.log"], is_empty=False, has_blocked_key=True,
        )
        parent = _create_empty_config(
            blocked=["*.tmp"], is_empty=False, has_blocked_key=True,
            agents=["Explore"], has_agents_key=True,
        )
        merged = _merge_hierarchical_configs(child, parent)
        assert merged["agents"] == ["Explore"]
        assert merged["has_agents_key"] is True

    def test_both_have_agents_child_overrides(self):
        """Both have agents → child overrides parent."""
        child = _create_empty_config(
            blocked=["*.log"], is_empty=False, has_blocked_key=True,
            agents=["Plan"], has_agents_key=True,
        )
        parent = _create_empty_config(
            blocked=["*.tmp"], is_empty=False, has_blocked_key=True,
            agents=["Explore"], has_agents_key=True,
        )
        merged = _merge_hierarchical_configs(child, parent)
        assert merged["agents"] == ["Plan"]

    def test_child_has_disable_parent_doesnt(self):
        """Child has disable_main_agent, parent doesn't → child's value used."""
        child = _create_empty_config(
            blocked=["*.log"], is_empty=False, has_blocked_key=True,
            disable_main_agent=True, has_disable_main_agent_key=True,
        )
        parent = _create_empty_config(
            blocked=["*.tmp"], is_empty=False, has_blocked_key=True,
        )
        merged = _merge_hierarchical_configs(child, parent)
        assert merged["disable_main_agent"] is True
        assert merged["has_disable_main_agent_key"] is True

    def test_parent_has_disable_child_doesnt(self):
        """Parent has disable_main_agent, child doesn't → parent's value inherited."""
        child = _create_empty_config(
            blocked=["*.log"], is_empty=False, has_blocked_key=True,
        )
        parent = _create_empty_config(
            blocked=["*.tmp"], is_empty=False, has_blocked_key=True,
            disable_main_agent=True, has_disable_main_agent_key=True,
        )
        merged = _merge_hierarchical_configs(child, parent)
        assert merged["disable_main_agent"] is True
        assert merged["has_disable_main_agent_key"] is True

    def test_agent_fields_merge_with_hierarchical_patterns(self):
        """Agent fields merge correctly with hierarchical pattern inheritance."""
        child = _create_empty_config(
            blocked=["*.log"], is_empty=False, has_blocked_key=True,
            agents=["Explore"], has_agents_key=True,
        )
        parent = _create_empty_config(
            blocked=["*.tmp"], is_empty=False, has_blocked_key=True,
            disable_main_agent=True, has_disable_main_agent_key=True,
        )
        merged = _merge_hierarchical_configs(child, parent)
        # Child's agents, parent's disable_main_agent
        assert merged["agents"] == ["Explore"]
        assert merged["disable_main_agent"] is True
        # Blocked patterns combined
        assert "*.log" in merged["blocked"]
        assert "*.tmp" in merged["blocked"]


# ---------------------------------------------------------------------------
# TestAgentResolution — resolving agent type from tool_use_id + transcripts
# ---------------------------------------------------------------------------

class TestAgentResolution:
    """Tests for resolve_agent_type()."""

    def test_no_tracking_file_returns_none(self, tmp_path):
        """No tracking file → returns None (main agent)."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        result = resolve_agent_type({
            "tool_use_id": "tu_123",
            "transcript_path": str(transcript),
        })
        assert result is None

    def test_empty_tracking_file_returns_none(self, tmp_path):
        """Empty tracking file → returns None."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        create_agent_tracking_file(tmp_path, {})
        result = resolve_agent_type({
            "tool_use_id": "tu_123",
            "transcript_path": str(transcript),
        })
        assert result is None

    def test_tool_use_id_found_in_subagent(self, tmp_path):
        """tool_use_id found in subagent transcript → returns correct agent_type."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        create_agent_tracking_file(tmp_path, {"agent_abc": "Explore"})
        create_agent_transcript(tmp_path, "agent_abc", ["tu_123", "tu_456"])
        result = resolve_agent_type({
            "tool_use_id": "tu_123",
            "transcript_path": str(transcript),
        })
        assert result == "Explore"

    def test_tool_use_id_not_found_returns_none(self, tmp_path):
        """tool_use_id not in any transcript → returns None (main agent)."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        create_agent_tracking_file(tmp_path, {"agent_abc": "Explore"})
        create_agent_transcript(tmp_path, "agent_abc", ["tu_999"])
        result = resolve_agent_type({
            "tool_use_id": "tu_123",
            "transcript_path": str(transcript),
        })
        assert result is None

    def test_multiple_subagents_first_match(self, tmp_path):
        """Multiple subagents active, tool_use_id in first → returns first agent's type."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        # Dict insertion order (guaranteed in Python 3.7+) determines iteration order
        create_agent_tracking_file(tmp_path, {
            "agent_abc": "Explore",
            "agent_def": "Plan",
        })
        create_agent_transcript(tmp_path, "agent_abc", ["tu_123"])
        create_agent_transcript(tmp_path, "agent_def", ["tu_456"])
        result = resolve_agent_type({
            "tool_use_id": "tu_123",
            "transcript_path": str(transcript),
        })
        assert result == "Explore"

    def test_multiple_subagents_second_match(self, tmp_path):
        """Multiple subagents active, tool_use_id in second → returns second agent's type."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        # Dict insertion order (guaranteed in Python 3.7+) determines iteration order
        create_agent_tracking_file(tmp_path, {
            "agent_abc": "Explore",
            "agent_def": "Plan",
        })
        create_agent_transcript(tmp_path, "agent_abc", ["tu_111"])
        create_agent_transcript(tmp_path, "agent_def", ["tu_123"])
        result = resolve_agent_type({
            "tool_use_id": "tu_123",
            "transcript_path": str(transcript),
        })
        assert result == "Plan"

    def test_tracking_file_but_transcript_missing(self, tmp_path):
        """Tracking file has agent but transcript file missing → returns None."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        create_agent_tracking_file(tmp_path, {"agent_abc": "Explore"})
        # Don't create the transcript file
        result = resolve_agent_type({
            "tool_use_id": "tu_123",
            "transcript_path": str(transcript),
        })
        assert result is None

    def test_invalid_json_in_tracking_file(self, tmp_path):
        """Invalid JSON in tracking file → returns None."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        subagents_dir = tmp_path / "subagents"
        subagents_dir.mkdir(parents=True, exist_ok=True)
        (subagents_dir / ".agent_types.json").write_text("not json{{{")
        result = resolve_agent_type({
            "tool_use_id": "tu_123",
            "transcript_path": str(transcript),
        })
        assert result is None

    def test_missing_tool_use_id(self, tmp_path):
        """Missing tool_use_id in input → returns None."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        result = resolve_agent_type({
            "transcript_path": str(transcript),
        })
        assert result is None

    def test_missing_transcript_path(self):
        """Missing transcript_path in input → returns None."""
        result = resolve_agent_type({
            "tool_use_id": "tu_123",
        })
        assert result is None


# ---------------------------------------------------------------------------
# TestAgentRulesEndToEnd — full hook invocation with simulated agent context
# ---------------------------------------------------------------------------

class TestAgentRulesEndToEnd:
    """End-to-end tests running the actual hook with agent context."""

    def test_no_agent_keys_blocks_main(self, tmp_path, hooks_dir):
        """No agent keys in .block → blocks main agent (backward compat)."""
        protected = tmp_path / "protected"
        create_block_file(protected)
        target = str(protected / "file.txt")
        # No tool_use_id/transcript_path = main agent
        input_json = make_edit_input_with_agent(target)
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

    def test_no_agent_keys_blocks_subagent(self, tmp_path, hooks_dir):
        """No agent keys in .block → blocks subagent (backward compat)."""
        protected = tmp_path / "protected"
        create_block_file(protected)
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        create_agent_tracking_file(tmp_path, {"agent_abc": "Explore"})
        create_agent_transcript(tmp_path, "agent_abc", ["tu_123"])
        target = str(protected / "file.txt")
        input_json = make_edit_input_with_agent(target, "tu_123", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

    def test_agents_list_blocks_listed_subagent(self, tmp_path, hooks_dir):
        """agents: ["Explore"] + .block blocks all → blocks Explore subagent."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({"agents": ["Explore"]}))
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        create_agent_tracking_file(tmp_path, {"agent_abc": "Explore"})
        create_agent_transcript(tmp_path, "agent_abc", ["tu_123"])
        target = str(protected / "file.txt")
        input_json = make_edit_input_with_agent(target, "tu_123", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

    def test_agents_list_allows_unlisted_subagent(self, tmp_path, hooks_dir):
        """agents: ["Explore"] + .block blocks all → allows non-Explore subagent."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({"agents": ["Explore"]}))
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        create_agent_tracking_file(tmp_path, {"agent_def": "Plan"})
        create_agent_transcript(tmp_path, "agent_def", ["tu_456"])
        target = str(protected / "file.txt")
        input_json = make_edit_input_with_agent(target, "tu_456", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert not is_blocked(stdout)

    def test_agents_list_allows_main(self, tmp_path, hooks_dir):
        """agents: ["Explore"] + .block → allows main agent (agents key targets subagents only)."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({"agents": ["Explore"]}))
        target = str(protected / "file.txt")
        input_json = make_edit_input_with_agent(target)
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert not is_blocked(stdout)

    def test_disable_main_allows_main(self, tmp_path, hooks_dir):
        """disable_main_agent: true + .block blocks all → allows main agent."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({"disable_main_agent": True}))
        target = str(protected / "file.txt")
        input_json = make_edit_input_with_agent(target)
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert not is_blocked(stdout)

    def test_disable_main_blocks_subagent(self, tmp_path, hooks_dir):
        """disable_main_agent: true + .block blocks all → blocks any subagent."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({"disable_main_agent": True}))
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        create_agent_tracking_file(tmp_path, {"agent_abc": "Explore"})
        create_agent_transcript(tmp_path, "agent_abc", ["tu_123"])
        target = str(protected / "file.txt")
        input_json = make_edit_input_with_agent(target, "tu_123", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

    def test_agents_plus_disable_main_combined(self, tmp_path, hooks_dir):
        """agents: ["Explore"] + disable_main_agent: true → allows main, blocks Explore, allows other."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({
            "agents": ["Explore"],
            "disable_main_agent": True,
        }))
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()

        # Main agent → allowed
        target = str(protected / "file.txt")
        input_json = make_edit_input_with_agent(target)
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert not is_blocked(stdout)

        # Explore → blocked
        create_agent_tracking_file(tmp_path, {"agent_abc": "Explore"})
        create_agent_transcript(tmp_path, "agent_abc", ["tu_explore"])
        input_json = make_edit_input_with_agent(target, "tu_explore", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Plan → allowed
        create_agent_tracking_file(tmp_path, {"agent_def": "Plan"})
        create_agent_transcript(tmp_path, "agent_def", ["tu_plan"])
        input_json = make_edit_input_with_agent(target, "tu_plan", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert not is_blocked(stdout)

    def test_agents_with_blocked_patterns(self, tmp_path, hooks_dir):
        """agents with blocked patterns → Explore blocked on matching, allowed on non-matching."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({
            "blocked": ["*.config"],
            "agents": ["Explore"],
        }))
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        create_agent_tracking_file(tmp_path, {"agent_abc": "Explore"})
        create_agent_transcript(tmp_path, "agent_abc", ["tu_cfg", "tu_txt"])

        # Matching pattern → blocked
        target_cfg = str(protected / "app.config")
        input_json = make_edit_input_with_agent(target_cfg, "tu_cfg", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Non-matching pattern → allowed
        target_txt = str(protected / "readme.txt")
        input_json = make_edit_input_with_agent(target_txt, "tu_txt", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert not is_blocked(stdout)

    def test_agents_with_allowed_patterns(self, tmp_path, hooks_dir):
        """agents with allowed patterns → Explore allowed on matching, blocked on non-matching."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({
            "allowed": ["docs/**"],
            "agents": ["Explore"],
        }))
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        create_agent_tracking_file(tmp_path, {"agent_abc": "Explore"})
        create_agent_transcript(tmp_path, "agent_abc", ["tu_docs", "tu_src"])

        # Matching allowed pattern → allowed
        docs_dir = protected / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        target_docs = str(docs_dir / "readme.md")
        input_json = make_edit_input_with_agent(target_docs, "tu_docs", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert not is_blocked(stdout)

        # Non-matching → blocked
        target_src = str(protected / "main.py")
        input_json = make_edit_input_with_agent(target_src, "tu_src", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

    def test_guide_messages_with_agent_rules(self, tmp_path, hooks_dir):
        """Guide messages work with agent-scoped rules."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({
            "agents": ["Explore"],
            "guide": "Protected from Explore agents",
        }))
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        create_agent_tracking_file(tmp_path, {"agent_abc": "Explore"})
        create_agent_transcript(tmp_path, "agent_abc", ["tu_123"])
        target = str(protected / "file.txt")
        input_json = make_edit_input_with_agent(target, "tu_123", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)
        assert "Protected from Explore agents" in get_block_reason(stdout)

    def test_marker_file_protection_ignores_agent_rules(self, tmp_path, hooks_dir):
        """Marker file protection still works regardless of agent rules."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({
            "disable_main_agent": True,  # would exempt main
        }))
        target = str(protected / ".block")
        input_json = make_edit_input_with_agent(target)
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)
        assert ".block" in get_block_reason(stdout)

    def test_bash_with_agent_rules(self, tmp_path, hooks_dir):
        """Bash command detection works with agent-scoped rules."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({"agents": ["Explore"]}))
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()
        create_agent_tracking_file(tmp_path, {"agent_abc": "Explore"})
        create_agent_transcript(tmp_path, "agent_abc", ["tu_bash"])
        target = str(protected / "file.txt")
        input_json = make_bash_input_with_agent(f"rm {target}", "tu_bash", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)


# ---------------------------------------------------------------------------
# TestAgentRulesParallelSubagents — parallel agent scenarios
# ---------------------------------------------------------------------------

class TestAgentRulesParallelSubagents:
    """Tests for parallel subagent scenarios."""

    def test_two_parallel_explore_both_blocked(self, tmp_path, hooks_dir):
        """Two parallel Explore agents → both correctly blocked by agents: ["Explore"]."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({"agents": ["Explore"]}))
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()

        create_agent_tracking_file(tmp_path, {
            "agent_1": "Explore",
            "agent_2": "Explore",
        })
        create_agent_transcript(tmp_path, "agent_1", ["tu_a1"])
        create_agent_transcript(tmp_path, "agent_2", ["tu_a2"])

        target = str(protected / "file.txt")

        # First Explore agent
        input_json = make_edit_input_with_agent(target, "tu_a1", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Second Explore agent
        input_json = make_edit_input_with_agent(target, "tu_a2", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

    def test_explore_plus_plan_only_explore_blocked(self, tmp_path, hooks_dir):
        """Explore + Plan parallel → only Explore blocked by agents: ["Explore"]."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({"agents": ["Explore"]}))
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()

        create_agent_tracking_file(tmp_path, {
            "agent_explore": "Explore",
            "agent_plan": "Plan",
        })
        create_agent_transcript(tmp_path, "agent_explore", ["tu_explore"])
        create_agent_transcript(tmp_path, "agent_plan", ["tu_plan"])

        target = str(protected / "file.txt")

        # Explore → blocked
        input_json = make_edit_input_with_agent(target, "tu_explore", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Plan → allowed
        input_json = make_edit_input_with_agent(target, "tu_plan", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert not is_blocked(stdout)

    def test_two_different_types_resolved_correctly(self, tmp_path, hooks_dir):
        """Two different agent types parallel → each resolved to correct type."""
        protected = tmp_path / "protected"
        create_block_file(protected, json.dumps({"agents": ["Explore", "code-reviewer"]}))
        transcript = tmp_path / "transcript.jsonl"
        transcript.touch()

        create_agent_tracking_file(tmp_path, {
            "agent_explore": "Explore",
            "agent_plan": "Plan",
        })
        create_agent_transcript(tmp_path, "agent_explore", ["tu_explore"])
        create_agent_transcript(tmp_path, "agent_plan", ["tu_plan"])

        target = str(protected / "file.txt")

        # Explore → blocked (in list)
        input_json = make_edit_input_with_agent(target, "tu_explore", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Plan → allowed (not in list)
        input_json = make_edit_input_with_agent(target, "tu_plan", str(transcript))
        code, stdout, _ = run_hook(hooks_dir, input_json)
        assert not is_blocked(stdout)
