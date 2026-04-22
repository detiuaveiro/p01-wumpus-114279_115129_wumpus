import asyncio
import json
import os
import random
from typing import Any, Optional, Set, Tuple, Union, Dict

from agents.base_agent import BaseAgent


class ProbabilisticAgent(BaseAgent):
    def __init__(self, server_uri: Optional[str] = None) -> None:
        if server_uri is None:
            server_uri = os.environ.get("WUMPUS_SERVER", "ws://localhost:8765")
        super().__init__(server_uri)

        self.reset_memory()

    # -------------------------
    # RESET
    # -------------------------
    def reset_memory(self) -> None:
        self.visited: Set[Tuple[int, int]] = set()
        self.safe_cells: Set[Tuple[int, int]] = set()
        self.visit_count: Dict[Tuple[int, int], int] = {}

        self.movement_map: Dict[Tuple[int, int], float] = {}
        self.danger_map: Dict[Tuple[int, int], float] = {}

        self.breeze_cells: Set[Tuple[int, int]] = set()
        self.stench_cells: Set[Tuple[int, int]] = set()

        self.walls: Set[Tuple[int, int]] = set()

        self.last_action: Optional[str] = None
        self.last_pos: Optional[Tuple[int, int]] = None

    # -------------------------
    # UTILS
    # -------------------------
    def neighbors(self, pos):
        x, y = pos
        return [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]

    def clamp(self, v):
        return max(0.0, min(1.0, v))

    # -------------------------
    # MEMORY UPDATE
    # -------------------------
    def update_memory(self) -> None:
        if not self.current_state:
            return

        percepts = self.current_state.get("percepts", {})
        pos_raw = self.current_state.get("position")
        if not pos_raw:
            return

        pos = tuple(pos_raw)

        # WALL (bump)
        if percepts.get("bump") and self.last_action and self.last_pos:
            x, y = self.last_pos
            wall_pos = {
                "N": (x,y+1),
                "S": (x,y-1),
                "E": (x+1,y),
                "W": (x-1,y)
            }[self.last_action]

            self.walls.add(wall_pos)
            self.movement_map[wall_pos] = 0.0
            self.danger_map[wall_pos] = 0.0

        # VISIT
        self.visited.add(pos)
        self.safe_cells.add(pos)

        self.visit_count[pos] = self.visit_count.get(pos, 0) + 1
        self.movement_map[pos] = 1 / (1 + self.visit_count[pos])
        self.danger_map[pos] = 1.0

        neigh = self.neighbors(pos)

        # POPULATE PERCEPTS
        if percepts.get("breeze"): self.breeze_cells.add(pos)
        if percepts.get("stench"): self.stench_cells.add(pos)

        # NO DANGER → SAFE
        if not percepts.get("breeze") and not percepts.get("stench"):
            for n in neigh:
                if n not in self.walls:
                    self.safe_cells.add(n)
                    self.danger_map[n] = 1.0
                    self.movement_map.setdefault(n, 1.0)

        # BREEZE / STENCH
        if percepts.get("breeze") or percepts.get("stench"):
            for n in neigh:
                if n not in self.safe_cells and n not in self.walls:
                    self.danger_map[n] = self.clamp(
                        self.danger_map.get(n, 0.5) - 0.3
                    )

                    # 🔥 NEAR-DANGER GRADIENT
                    for nn in self.neighbors(n):
                        if nn not in self.safe_cells and nn not in self.walls:
                            self.danger_map[nn] = self.clamp(
                                self.danger_map.get(nn, 0.5) - 0.05
                            )

        for n in neigh:
            if n not in self.walls:
                self.movement_map.setdefault(n, 1.0)
                self.danger_map.setdefault(n, 0.5)

        self.deduce_danger()

    # -------------------------
    # DEDUCTION
    # -------------------------
    def deduce_danger(self):
        for cell in self.breeze_cells:
            cands = [n for n in self.neighbors(cell)
                     if n not in self.safe_cells and n not in self.walls]
            if len(cands) == 1:
                self.danger_map[cands[0]] = 0.0

        for cell in self.stench_cells:
            cands = [n for n in self.neighbors(cell)
                     if n not in self.safe_cells and n not in self.walls]
            if len(cands) == 1:
                self.danger_map[cands[0]] = 0.0

    # -------------------------
    # CLASSIFICATION (SIMPLIFIED)
    # -------------------------
    def classify(self, cell):
        # We now only use this to filter out absolute dead ends.
        # Let the probability math handle everything else.
        if cell in self.walls:
            return 0

        if self.danger_map.get(cell, 0.5) <= 0.0:
            return 0  # known danger

        return 1  # viable move

    # -------------------------
    # DECISION
    # -------------------------
    async def deliberate(self):
        if not self.current_state:
            return None

        percepts = self.current_state.get("percepts", {})
        pos = tuple(self.current_state["position"])

        if percepts.get("glitter"):
            return None

        neigh = {
            "E": (pos[0]+1,pos[1]),
            "W": (pos[0]-1,pos[1]),
            "N": (pos[0],pos[1]+1),
            "S": (pos[0],pos[1]-1)
        }

        scored = []

        for d, cell in neigh.items():
            if not self.classify(cell): # Skip walls and known 0.0 dangers
                continue

            move_prob = self.movement_map.get(cell, 1.0)
            danger_prob = self.danger_map.get(cell, 0.5)

            score = move_prob * danger_prob
            scored.append((score, d))

        if not scored:
            return None

        # Find the highest score
        max_s = max(s for s, _ in scored)
        best_moves = [d for s, d in scored if s == max_s]

        # Break ties randomly
        choice = random.choice(best_moves)

        self.last_action = choice
        self.last_pos = pos

        return choice

    # -------------------------
    # TELEMETRY
    # -------------------------
    async def send_telemetry(self, websocket: Any):
        if not self.current_state:
            return

        percepts = self.current_state.get("percepts", {})
        pos = self.current_state.get("position")
        if not pos:
            return

        payload = {
            "action": "telemetry",
            "data": {
                "visited": [f"{x},{y}" for x,y in self.visited],
                "percepts": percepts,
                "agent_pos": pos
            }
        }

        await websocket.send(json.dumps(payload))


if __name__ == "__main__":
    agent = ProbabilisticAgent()
    asyncio.run(agent.run())
