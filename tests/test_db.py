"""Unit tests for db/db.py — runs without a live MongoDB connection."""

from __future__ import annotations

from unittest.mock import call

import pytest

from db.db import (
    OptimalPath,
    StepData,
    _action_signature,
    _recompute_optimal_path,
    query_context,
    store_step,
    store_trace,
)


# ---------------------------------------------------------------------------
# TestActionSignature
# ---------------------------------------------------------------------------

class TestActionSignature:
    def test_without_value(self):
        step = StepData(action="click", target="button")
        assert _action_signature(step) == "click:button"

    def test_with_value(self):
        step = StepData(action="type", target="search_input", value="macbook")
        assert _action_signature(step) == "type:search_input:macbook"

    def test_empty_string_value_treated_as_no_value(self):
        step = StepData(action="click", target="link", value="")
        assert _action_signature(step) == "click:link"

    def test_none_value(self):
        step = StepData(action="click", target="link", value=None)
        assert _action_signature(step) == "click:link"


# ---------------------------------------------------------------------------
# TestRecomputeOptimalPath
# ---------------------------------------------------------------------------

class TestRecomputeOptimalPath:
    def _make_doc(self, run_count, success_count, step_counts):
        return {
            "task": "t",
            "domain": "d",
            "run_count": run_count,
            "_success_count": success_count,
            "_step_counts": step_counts,
        }

    def test_zero_runs_skips(self, mock_collection):
        mock_collection.find_one.return_value = self._make_doc(0, 0, {})
        _recompute_optimal_path(mock_collection, "t", "d")
        mock_collection.update_one.assert_not_called()

    def test_no_doc_skips(self, mock_collection):
        mock_collection.find_one.return_value = None
        _recompute_optimal_path(mock_collection, "t", "d")
        mock_collection.update_one.assert_not_called()

    def test_confidence_formula(self, mock_collection):
        # 8 runs, 6 successes → success_rate=0.75, volume_factor=0.8
        # confidence = 0.75*0.7 + 0.8*0.3 = 0.525 + 0.24 = 0.765
        mock_collection.find_one.return_value = self._make_doc(8, 6, {
            "click:btn": {"attempts": 6, "successes": 6},
        })
        _recompute_optimal_path(mock_collection, "t", "d")
        update_call = mock_collection.update_one.call_args
        confidence = update_call[0][1]["$set"]["confidence"]
        assert confidence == 0.765

    def test_confidence_capped_at_099(self, mock_collection):
        mock_collection.find_one.return_value = self._make_doc(100, 100, {
            "click:btn": {"attempts": 100, "successes": 100},
        })
        _recompute_optimal_path(mock_collection, "t", "d")
        update_call = mock_collection.update_one.call_args
        confidence = update_call[0][1]["$set"]["confidence"]
        assert confidence == 0.99

    def test_optimal_actions_thresholds(self, mock_collection):
        # success_count=10
        # step A: 8 attempts (freq 80%), 90% success → included
        # step B: 3 attempts (freq 30%), 100% success → excluded (freq < 50%)
        # step C: 7 attempts (freq 70%), 50% success → excluded (rate < 70%)
        mock_collection.find_one.return_value = self._make_doc(10, 10, {
            "click:a": {"attempts": 8, "successes": 7},   # freq=80%, rate=87.5%
            "click:b": {"attempts": 3, "successes": 3},   # freq=30%, rate=100%
            "click:c": {"attempts": 7, "successes": 3},   # freq=70%, rate=42.9%
        })
        _recompute_optimal_path(mock_collection, "t", "d")
        update_call = mock_collection.update_one.call_args
        optimal = update_call[0][1]["$set"]["optimal_actions"]
        assert "click:a" in optimal
        assert "click:b" not in optimal
        assert "click:c" not in optimal

    def test_step_traces_sorted_by_success_rate_then_attempts(self, mock_collection):
        mock_collection.find_one.return_value = self._make_doc(10, 10, {
            "click:low": {"attempts": 5, "successes": 2},   # rate=0.4
            "click:high": {"attempts": 5, "successes": 5},  # rate=1.0
            "click:mid": {"attempts": 10, "successes": 7},  # rate=0.7
        })
        _recompute_optimal_path(mock_collection, "t", "d")
        update_call = mock_collection.update_one.call_args
        traces = update_call[0][1]["$set"]["step_traces"]
        sigs = [t["action_signature"] for t in traces]
        assert sigs == ["click:high", "click:mid", "click:low"]

    def test_empty_step_counts(self, mock_collection):
        mock_collection.find_one.return_value = self._make_doc(5, 3, {})
        _recompute_optimal_path(mock_collection, "t", "d")
        update_call = mock_collection.update_one.call_args
        set_doc = update_call[0][1]["$set"]
        assert set_doc["optimal_actions"] == []
        assert set_doc["step_traces"] == []
        # confidence still computed: 3/5*0.7 + 0.5*0.3 = 0.42+0.15 = 0.57
        assert set_doc["confidence"] == 0.57


# ---------------------------------------------------------------------------
# TestStoreStep
# ---------------------------------------------------------------------------

class TestStoreStep:
    def test_upsert_structure(self, mock_collection, mock_embed):
        step = StepData(action="click", target="btn", success=True)
        store_step("buy macbook", "walmart.com", step)

        mock_collection.update_one.assert_called_once()
        args = mock_collection.update_one.call_args
        filt, update = args[0]
        assert filt == {"task": "buy macbook", "domain": "walmart.com"}
        assert update["$setOnInsert"]["task"] == "buy macbook"
        assert update["$inc"]["_step_counts.click:btn.attempts"] == 1
        assert update["$inc"]["_step_counts.click:btn.successes"] == 1
        assert args[1]["upsert"] is True

    def test_failure_does_not_increment_successes(self, mock_collection, mock_embed):
        step = StepData(action="click", target="btn", success=False)
        store_step("buy macbook", "walmart.com", step)

        args = mock_collection.update_one.call_args
        update = args[0][1]
        assert update["$inc"]["_step_counts.click:btn.successes"] == 0
        assert update["$inc"]["_step_counts.click:btn.attempts"] == 1

    def test_embeds_task(self, mock_collection, mock_embed):
        store_step("buy macbook", "walmart.com", StepData("click", "btn"))
        mock_embed.assert_called_once_with("buy macbook")


# ---------------------------------------------------------------------------
# TestStoreTrace
# ---------------------------------------------------------------------------

class TestStoreTrace:
    def test_successful_trace(self, mock_collection, mock_embed):
        mock_collection.find_one.return_value = {
            "task": "t", "domain": "d",
            "run_count": 1, "_success_count": 1,
            "confidence": 0.99,
            "_step_counts": {"click:btn": {"attempts": 1, "successes": 1}},
        }
        trace = [StepData("click", "btn", success=True)]
        store_trace("t", "d", trace, success=True)

        # update_one calls: upsert, inc, recompute, history push
        assert mock_collection.update_one.call_count >= 2
        inc_call = mock_collection.update_one.call_args_list[1]
        inc_ops = inc_call[0][1]["$inc"]
        assert inc_ops["run_count"] == 1
        assert inc_ops["_success_count"] == 1
        assert inc_ops["_step_counts.click:btn.attempts"] == 1

    def test_failed_trace_only_increments_run_count(self, mock_collection, mock_embed):
        mock_collection.find_one.return_value = {
            "task": "t", "domain": "d",
            "run_count": 1, "_success_count": 0,
            "confidence": 0.0,
            "_step_counts": {},
        }
        trace = [StepData("click", "btn", success=False)]
        store_trace("t", "d", trace, success=False)

        inc_call = mock_collection.update_one.call_args_list[1]
        inc_ops = inc_call[0][1]["$inc"]
        assert inc_ops == {"run_count": 1}

    def test_embed_called_once(self, mock_collection, mock_embed):
        mock_collection.find_one.return_value = {
            "task": "t", "domain": "d",
            "run_count": 1, "_success_count": 1,
            "confidence": 0.99,
            "_step_counts": {},
        }
        store_trace("t", "d", [StepData("click", "btn")], success=True)
        mock_embed.assert_called_once_with("t")

    def test_recompute_called(self, mock_collection, mock_embed):
        mock_collection.find_one.return_value = {
            "task": "t", "domain": "d",
            "run_count": 1, "_success_count": 1,
            "confidence": 0.99,
            "_step_counts": {},
        }
        store_trace("t", "d", [StepData("click", "btn")], success=True)
        # find_one is called by _recompute_optimal_path and then again for event data
        assert mock_collection.find_one.call_count == 2


# ---------------------------------------------------------------------------
# TestQueryContext
# ---------------------------------------------------------------------------

class TestQueryContext:
    def test_pipeline_structure(self, mock_collection, mock_embed):
        mock_collection.aggregate.return_value = iter([])
        result = query_context("buy macbook", "walmart.com")

        mock_collection.aggregate.assert_called_once()
        pipeline = mock_collection.aggregate.call_args[0][0]

        # First stage must be $vectorSearch with domain filter
        vs = pipeline[0]["$vectorSearch"]
        assert vs["queryVector"] == [0.1] * 1536
        assert vs["filter"] == {"domain": "walmart.com"}

        # No separate $match stage for domain
        stage_keys = [list(s.keys())[0] for s in pipeline]
        assert "$match" not in stage_keys

        assert result is None

    def test_result_unpacked_to_optimal_path(self, mock_collection, mock_embed):
        mock_collection.aggregate.return_value = iter([{
            "task": "buy macbook",
            "domain": "walmart.com",
            "confidence": 0.94,
            "run_count": 500,
            "optimal_actions": ["search", "click"],
            "step_traces": [{"action_signature": "click:btn"}],
        }])
        result = query_context("buy macbook", "walmart.com")

        assert isinstance(result, OptimalPath)
        assert result.task == "buy macbook"
        assert result.confidence == 0.94
        assert result.optimal_actions == ["search", "click"]

    def test_missing_fields_use_defaults(self, mock_collection, mock_embed):
        mock_collection.aggregate.return_value = iter([{
            "task": "t",
            "domain": "d",
        }])
        result = query_context("t", "d")

        assert result.confidence == 0.0
        assert result.run_count == 0
        assert result.optimal_actions == []
        assert result.step_traces == []


# ---------------------------------------------------------------------------
# TestInputValidation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_empty_task_raises(self, mock_collection, mock_embed):
        with pytest.raises(ValueError, match="task"):
            query_context("", "walmart.com")
        with pytest.raises(ValueError, match="task"):
            store_step("", "walmart.com", StepData("click", "btn"))
        with pytest.raises(ValueError, match="task"):
            store_trace("", "walmart.com", [StepData("click", "btn")], True)

    def test_whitespace_task_raises(self, mock_collection, mock_embed):
        with pytest.raises(ValueError, match="task"):
            query_context("   ", "walmart.com")

    def test_empty_domain_raises(self, mock_collection, mock_embed):
        with pytest.raises(ValueError, match="domain"):
            query_context("buy macbook", "")
        with pytest.raises(ValueError, match="domain"):
            query_context("buy macbook", "   ")

    def test_empty_step_fields_raise(self, mock_collection, mock_embed):
        with pytest.raises(ValueError, match="action"):
            store_step("t", "d", StepData(action="", target="btn"))
        with pytest.raises(ValueError, match="target"):
            store_step("t", "d", StepData(action="click", target=""))

    def test_empty_trace_list_raises(self, mock_collection, mock_embed):
        with pytest.raises(ValueError, match="trace"):
            store_trace("t", "d", [], True)
