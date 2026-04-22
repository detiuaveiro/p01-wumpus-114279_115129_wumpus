import asyncio
import json
import os
import random
from collections import defaultdict
from typing import Any, Optional, Set, Tuple, Union

from agents.base_agent import BaseAgent


class ProbabilisticAgent(BaseAgent):
    """
    Probabilistic Wumpus agent using two overlapping maps:

    Movement map  – prefers unvisited cells, never locks out visited ones.
    Danger map    – degrades on breeze/stench neighbours; visited cells lock at 1.0 (safe).

    Final move score = movement_prob * danger_prob.
    """

    # movement map weights
    REVISIT_PENALTY  = 0.3   # visited cell — still reachable, just less preferred

    # danger map fixed levels (persistent, never change once set unless upgrading to safe)
    DANGER_SAFE      = 1.0   # visited cell — confirmed safe forever
    DANGER_UNKNOWN   = 1.0   # default for cells we know nothing about
    DANGER_NEAR      = 0.6   # neighbour of a breeze/stench cell — fixed, stays forever
    DANGER_SELF      = 0.8   # current cell when breeze/stench sensed — fixed, stays forever
    DANGER_DEADLY    = 0.0   # confirmed pit or wumpus — locked forever

    def __init__(self, server_uri: Optional[str] = None) -> None:
        if server_uri is None:
            server_uri = os.environ.get("WUMPUS_SERVER", "ws://localhost:8765")
        super().__init__(server_uri)

        # ── core memory ──────────────────────────────────────────────────────
        self.visited: Set[Tuple[int, int]] = set()

        # movement_map: (x,y) -> weight  (higher = more attractive to visit)
        self.movement_map: dict[Tuple[int, int], float] = defaultdict(lambda: 1.0)

        # danger_map: (x,y) -> probability of being SAFE  (1.0 = confirmed safe, 0.0 = deadly)
        self.danger_map: dict[Tuple[int, int], float] = defaultdict(lambda: 1.0)

        # cells we are certain contain a pit or the wumpus
        self.confirmed_deadly: Set[Tuple[int, int]] = set()

        # cells where breeze/stench was sensed — permanently marked DANGER_SELF
        self.danger_self_cells: Set[Tuple[int, int]] = set()

        # whether the wumpus is still alive
        self.wumpus_alive: bool = True

        # cells confirmed to be walls (score locked to 0, never entered)
        self.walls: Set[Tuple[int, int]] = set()

        # the direction chosen in the previous deliberate() call
        self._last_action: Optional[str] = None

        # last known position (for delta-based telemetry)
        self._last_pos: Optional[Tuple[int, int]] = None

    # ── helpers ──────────────────────────────────────────────────────────────

    def _pos(self) -> Optional[Tuple[int, int]]:
        """Return current (x, y) or None."""
        if not self.current_state:
            return None
        p = self.current_state.get("position")
        return tuple(p) if p else None

    @staticmethod
    def _neighbours(x: int, y: int) -> list[Tuple[int, int]]:
        return [(x, y + 1), (x, y - 1), (x + 1, y), (x - 1, y)]

    @staticmethod
    def _dir_to_delta(direction: str) -> Tuple[int, int]:
        return {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}[direction]

    @staticmethod
    def _direction(fx: int, fy: int, tx: int, ty: int) -> Optional[str]:
        dx, dy = tx - fx, ty - fy
        return {(0, 1): "N", (0, -1): "S", (1, 0): "E", (-1, 0): "W"}.get((dx, dy))

    # ── memory update (called once per tick before deliberate) ───────────────

    def update_memory(self) -> None:
        pos = self._pos()
        if pos is None:
            return

        x, y = pos
        percepts = self.current_state.get("percepts", {}) if self.current_state else {}

        # ── bump detection ────────────────────────────────────────────────
        if percepts.get("bump") and self._last_action in ("N", "S", "E", "W"):
            dx, dy = self._dir_to_delta(self._last_action)
            wall_cell = (x + dx, y + dy)
            self.walls.add(wall_cell)
            self.movement_map[wall_cell] = 0.0
            self.danger_map[wall_cell]   = 0.0

        # ── mark current cell as visited & confirmed safe ─────────────────
        # Visited cells are locked at DANGER_SAFE (1.0) forever — even if we
        # previously marked them as DANGER_SELF, surviving here confirms safety.
        self.visited.add(pos)
        self.movement_map[pos] = self.REVISIT_PENALTY
        self.danger_map[pos]   = self.DANGER_SAFE

        # ── process percepts ──────────────────────────────────────────────
        has_breeze = percepts.get("breeze", False)
        has_stench = percepts.get("stench", False)
        has_scream = percepts.get("scream", False)

        if has_scream:
            self.wumpus_alive = False
            # Wumpus is dead — restore DANGER_NEAR cells that were only dangerous
            # because of stench (we can't distinguish pit vs wumpus contributions
            # here, so we conservatively bump non-confirmed cells up toward unknown).
            for cell in list(self.danger_map):
                if cell not in self.visited and cell not in self.confirmed_deadly:
                    if self.danger_map[cell] == self.DANGER_NEAR:
                        self.danger_map[cell] = self.DANGER_UNKNOWN

        neighbours = self._neighbours(x, y)

        if has_breeze or has_stench:
            # Current cell: danger is nearby. Mark it persistently.
            self.danger_self_cells.add(pos)
            self.danger_map[pos] = self.DANGER_SELF

            # Neighbours: apply DANGER_NEAR only to unconfirmed, unvisited cells.
            # Never downgrade a visited (safe) cell or upgrade a deadly one.
            for nb in neighbours:
                if nb in self.visited:
                    continue
                if nb in self.confirmed_deadly:
                    continue
                if nb in self.walls:
                    continue
                if self.danger_map[nb] > self.DANGER_NEAR:
                    self.danger_map[nb] = self.DANGER_NEAR

            # ── certain-cell inference ────────────────────────────────────
            unvisited = [
                n for n in neighbours
                if n not in self.visited
                and n not in self.walls
                and n not in self.confirmed_deadly
            ]
            if len(unvisited) == 1:
                deadly = unvisited[0]
                self.danger_map[deadly] = self.DANGER_DEADLY
                self.confirmed_deadly.add(deadly)

        else:
            # No percept → unvisited neighbours are confirmed safe.
            for nb in neighbours:
                if nb not in self.visited and nb not in self.confirmed_deadly and nb not in self.walls:
                    self.danger_map[nb] = self.DANGER_SAFE

        # ── enforce permanent locks ───────────────────────────────────────
        # Order matters: deadly > danger_self > visited-safe.
        # A visited cell that was previously a danger_self keeps DANGER_SELF
        # only while it's the current cell — once we leave and return without
        # a percept, visiting it again locks it safe. But since we don't revisit
        # the lock loop here, danger_self cells retain their mark across ticks.
        for cell in self.confirmed_deadly:
            self.danger_map[cell] = self.DANGER_DEADLY
        # Re-apply DANGER_SELF for all cells where it was ever sensed,
        # UNLESS that cell is now confirmed deadly or a wall.
        for cell in self.danger_self_cells:
            if cell not in self.confirmed_deadly and cell not in self.walls:
                self.danger_map[cell] = self.DANGER_SELF

        self._last_pos = pos

    # ── scoring ───────────────────────────────────────────────────────────────

    def _is_current_cell_dangerous(self) -> bool:
        """True if the cell we're standing on was ever sensed as danger-adjacent."""
        pos = self._pos()
        if pos is None:
            return False
        return pos in self.danger_self_cells

    def _score(self, candidate: Tuple[int, int], standing_in_danger: bool) -> float:
        """
        Combined score for moving to a candidate cell.

        When standing_in_danger is True, visited safe cells are boosted above
        fresh unknowns so the agent prefers retreating to confirmed safety.

        Priority table
        ──────────────────────────────────────────────────────
        Standing in SAFE cell:
          fresh unknown (1.0 × 1.0 = 1.0)
          > revisited   (0.3 × 1.0 = 0.3)
          > danger-near (1.0 × 0.6 = 0.6)   ← wait, unknown > near > revisited
          Actually:
            unknown  = 1.0 × 1.0 = 1.0
            near     = 1.0 × 0.6 = 0.6
            revisited= 0.3 × 1.0 = 0.3
          So: unknown > near > revisited  ✓

        Standing in DANGER cell:
          revisited safe boosted to 1.0 movement weight so it beats fresh unknown:
            revisited_boosted = 1.0 × 1.0 = 1.0
            unknown           = 1.0 × 1.0 = 1.0   ← tie-break randomly? No —
          We give revisited a small extra edge via REVISIT_BOOST:
            revisited_boosted = 1.1 × 1.0 = 1.1
            unknown           = 1.0 × 1.0 = 1.0
            near              = 1.0 × 0.6 = 0.6
        """
        d = self.danger_map[candidate]

        if standing_in_danger and candidate in self.visited:
            # Boost visited-safe cells so they beat fresh unknowns
            m = 1.1
        else:
            m = self.movement_map[candidate]   # 1.0 for unknown, REVISIT_PENALTY for visited

        return m * d

    # ── deliberation ──────────────────────────────────────────────────────────

    async def deliberate(self) -> Optional[Union[str, Tuple[str, str]]]:
        pos = self._pos()
        if pos is None:
            return random.choice(["N", "S", "E", "W"])

        percepts = self.current_state.get("percepts", {}) if self.current_state else {}

        # ── win condition ─────────────────────────────────────────────────
        if percepts.get("glitter"):
            self._last_action = None
            return None

        x, y = pos
        neighbours = self._neighbours(x, y)
        in_danger = self._is_current_cell_dangerous()

        # ── shoot if we know where the wumpus is and it's alive ───────────
        if self.wumpus_alive:
            for nb in neighbours:
                if nb in self.confirmed_deadly:
                    direction = self._direction(x, y, *nb)
                    if direction:
                        self._last_action = "shoot"
                        return ("shoot", direction)

        # ── score every neighbour and pick the best ───────────────────────
        scored = []
        for nb in neighbours:
            if nb in self.walls:
                continue
            score = self._score(nb, in_danger)
            direction = self._direction(x, y, *nb)
            if direction and score > 0:
                scored.append((score, direction, nb))

        if not scored:
            if self.wumpus_alive:
                for nb in neighbours:
                    if nb in self.confirmed_deadly:
                        d = self._direction(x, y, *nb)
                        if d:
                            self._last_action = "shoot"
                            return ("shoot", d)
            choice = random.choice(["N", "S", "E", "W"])
            self._last_action = choice
            return choice

        best_score = max(s for s, _, _ in scored)
        best_moves = [(d, nb) for s, d, nb in scored if s == best_score]
        chosen_dir, _ = random.choice(best_moves)
        self._last_action = chosen_dir
        return chosen_dir

    # ── reset ─────────────────────────────────────────────────────────────────

    def reset_memory(self) -> None:
        self.visited.clear()
        self.movement_map.clear()
        self.danger_map.clear()
        self.confirmed_deadly.clear()
        self.danger_self_cells.clear()
        self.walls.clear()
        self.wumpus_alive = True
        self._last_action = None
        self._last_pos = None

    # ── telemetry ─────────────────────────────────────────────────────────────

    async def send_telemetry(self, websocket: Any) -> None:
        pos = self._pos()
        percepts = self.current_state.get("percepts", {}) if self.current_state else {}

        # Build per-direction probability payload for the UI
        current_probs = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}
        if pos:
            x, y = pos
            in_danger = self._is_current_cell_dangerous()
            for nb, label in zip(self._neighbours(x, y), ["N", "S", "E", "W"]):
                current_probs[label] = round(self._score(nb, in_danger), 4)

        # Serialise danger map for heatmap rendering (string keys for JSON)
        danger_export = {
            f"{cx},{cy}": round(v, 4)
            for (cx, cy), v in self.danger_map.items()
        }

        payload = {
            "action": "telemetry",
            "data": {
                "visited": [f"{cx},{cy}" for cx, cy in self.visited],
                "confirmed_deadly": [f"{cx},{cy}" for cx, cy in self.confirmed_deadly],
                "danger_self": [f"{cx},{cy}" for cx, cy in self.danger_self_cells],
                "walls": [f"{cx},{cy}" for cx, cy in self.walls],
                "percepts": percepts,
                "agent_pos": list(pos) if pos else None,
                "current_probs": current_probs,
                "danger_map": danger_export,
                "wumpus_alive": self.wumpus_alive,
            },
        }
        await websocket.send(json.dumps(payload))


if __name__ == "__main__":
    agent = ProbabilisticAgent()
    asyncio.run(agent.run())