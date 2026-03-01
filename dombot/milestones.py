from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass
class PhaseState:
    name: str
    retry_budget: int
    attempts: int = 0


class MilestoneTracker:
    """Lightweight milestone tracker for run diagnostics.

    Tracks phase progression and budget pressure without hard-failing runs.
    """

    def __init__(self, task: str):
        self.task = task
        self.phases = self._build_phases(task)
        self.current_idx = 0
        self.phase_revisits = 0
        self.milestone_violations = 0
        self.total_steps_observed = 0

    def _build_phases(self, task: str) -> list[PhaseState]:
        text = task.lower()
        # Composite shopping/cart tasks
        if "search for" in text and "add" in text and "cart" in text:
            phase_count = 1 + len(re.findall(r"\bthen\b", text))
            phases: list[PhaseState] = []
            for i in range(phase_count):
                phases.append(PhaseState(name=f"SELECT_{i+1}", retry_budget=4))
            phases.append(PhaseState(name="CART", retry_budget=3))
            phases.append(PhaseState(name="EXTRACT", retry_budget=2))
            return phases
        # Generic fallback
        return [
            PhaseState(name="SEARCH", retry_budget=4),
            PhaseState(name="SELECT", retry_budget=4),
            PhaseState(name="CART", retry_budget=3),
            PhaseState(name="EXTRACT", retry_budget=2),
        ]

    def _classify_phase(self, action_blob: str) -> str:
        s = action_blob.lower()
        if any(k in s for k in ("extract", "done", "result")):
            return "EXTRACT"
        if any(k in s for k in ("add to cart", "view cart", "cart")):
            return "CART"
        if any(k in s for k in ("click", "options", "product", "result")):
            return "SELECT"
        return "SEARCH"

    def observe_step(self, model_output: Any) -> None:
        self.total_steps_observed += 1
        blob = ""
        try:
            if model_output and getattr(model_output, "action", None):
                for action in model_output.action:
                    blob += str(action.model_dump(exclude_unset=True))
        except Exception:
            blob = str(model_output or "")

        phase_name = self._classify_phase(blob)
        if not self.phases:
            return

        # map SELECT_x family to SELECT for comparison
        cur_phase = self.phases[self.current_idx].name
        cur_family = "SELECT" if cur_phase.startswith("SELECT_") else cur_phase

        if phase_name == cur_family:
            self.phases[self.current_idx].attempts += 1
        else:
            # advance if phase seems forward
            order = ["SEARCH", "SELECT", "CART", "EXTRACT"]
            try:
                cur_pos = order.index(cur_family)
                next_pos = order.index(phase_name)
            except ValueError:
                cur_pos = 0
                next_pos = 0
            if next_pos >= cur_pos:
                # advance to first matching family from current index onward
                moved = False
                for i in range(self.current_idx, len(self.phases)):
                    fam = "SELECT" if self.phases[i].name.startswith("SELECT_") else self.phases[i].name
                    if fam == phase_name:
                        self.current_idx = i
                        self.phases[i].attempts += 1
                        moved = True
                        break
                if not moved:
                    self.phases[self.current_idx].attempts += 1
            else:
                # backtracking signal
                self.phase_revisits += 1
                self.milestone_violations += 1
                self.phases[self.current_idx].attempts += 1

        # budget check
        st = self.phases[self.current_idx]
        if st.attempts > st.retry_budget:
            self.milestone_violations += 1

    def snapshot(self) -> dict[str, int]:
        return {
            "milestone_violations": int(self.milestone_violations),
            "phase_revisits": int(self.phase_revisits),
            "milestone_steps_observed": int(self.total_steps_observed),
        }
