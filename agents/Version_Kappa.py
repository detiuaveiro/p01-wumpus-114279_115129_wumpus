import asyncio
import json
import os
import random
from collections import Counter, deque
from typing import Any, Optional, Set, Tuple, Union

from agents.base_agent import BaseAgent


class DummyAgent(BaseAgent):

    def __init__(self, server_uri: Optional[str] = None) -> None:

        """
        Args:
            server_uri: The URI of the simulation server.
        """

        if server_uri is None:
            server_uri = os.environ.get("WUMPUS_SERVER", "ws://localhost:8765")
        super().__init__(server_uri)

        self.visited: Set[str] = set() # Self visited não vai ser tão importante como safe cells
        self.safe_cells: Set[str] = set() # Safe cells, são célula seguras

        self.Wumpus_positions: dict[str,int] = dict() # Inicialização de posições possíveis do wumups
        self.Hole_positions: dict[str,int] = dict() # Inicialização das posições possíveis de buracos
        self.Wall_positions: Set[str] = set() # Iniciialização de posições de paredes


        self.map_size: Set[int] = set({0,0})

        self.last_action: tuple[str] = tuple()

        self.Wumpus_detected = False
        self.probabilities = [0.25, 0.25, 0.25, 0.25]

        self.detected_Wumpus_cell : str = None

        self.last_visitedCell = str()

        self.map_name = str()

        # Loop detection: keeps the last 10 positions visited.
        # If any single cell appears 3+ times the agent is considered stuck.
        self.position_history: deque = deque(maxlen=10)

        # When a loop escape is triggered the full BFS path is stored here.
        # deliberate() consumes one direction per turn until it is empty.
        self.escape_path: deque = deque()

        # Cells where the agent has actually died in a pit — confirmed deadly.
        # Persists across resets on the same map so the agent never re-targets them.
        self.confirmed_pits: Set[str] = set()

        # Cells where the agent has actually been killed by the Wumpus.
        # Persists across resets; cleared if the Wumpus is later killed (scream).
        self.confirmed_wumpus: Set[str] = set()

        # The cell where the gold was found in a previous run.
        # Persists across resets so the agent can beeline straight to it.
        # Cleared only on map change.
        self.confirmed_gold: Optional[str] = None

        # Committed path to the gold cell, consumed one step per turn.
        self.gold_path: deque = deque()




    def update_memory(self) -> None:
        """Track where we have been just to paint the UI blue."""
        # Isto será mais usado para atualizar as variáveis que temos em relação à memóra 



        if self.current_state:
            pos = self.current_state.get("position")

            print((self.current_state.get("map_name")  != self.map_name))

            current_map = self.current_state.get("map_name")

            if current_map != self.map_name:

                print("WE ARE RESSETING THE CELLS!")

                self.safe_cells.clear()
                self.Wumpus_positions.clear()
                self.Hole_positions.clear()
                self.map_size.clear()
                self.Wall_positions.clear()
                self.position_history.clear()
                self.escape_path.clear()
                self.confirmed_pits.clear()
                self.confirmed_wumpus.clear()
                self.confirmed_gold = None
                self.gold_path.clear()

                self.Wumpus_detected = False
            
            self.map_name = self.current_state.get("map_name")

            number_of_holes = 0 # Incrementamos isto, caso seja só 1 buraco então damos mais peso a esse para que o agente arrisque entre dois
                    # por exemplo no 2º mapa
            Last_hole_position = None

            if pos:
                self.visited.add(f"{pos[0]},{pos[1]}")
                self.position_history.append(f"{pos[0]},{pos[1]}")

                percepts = self.current_state.get("percepts", {}) if self.current_state else {}

                active_percepts = [k.capitalize() for k, v in percepts.items() if v]
                percept_str = ", ".join(active_percepts) if active_percepts else "None"

                score = self.current_state.get("score", 0)
                arrows = self.current_state.get("arrows", 0)

                map_size: list[int] = list([self.current_state.get("width",0),self.current_state.get("height",0)]) # Inicialização do tamanho do mapa


                print(f"\n--- Agent at {pos[0],pos[1]} | Score: {score} | Arrows: {arrows} ---")
                print(f"Percepts: [{percept_str}]")

                # Scream: arrow hit the Wumpus
                # The scream percept is received on the turn after a successful
                # shot. Mark the confirmed Wumpus cell as safe and unvisited so
                # the agent can now walk through it normally.
                if percepts.get("scream") and self.last_action and self.last_action[0] == "shoot":
                    print("[SCREAM] Arrow hit! Wumpus is dead.")
                    for wumpus_cell in list(self.Wumpus_positions.keys()):
                        self.safe_cells.add(wumpus_cell)
                        self.visited.discard(wumpus_cell)   # treat as unvisited — worth exploring
                    self.Wumpus_positions.clear()
                    self.Wumpus_detected = False
                    self.detected_Wumpus_cell = None

                directions = [
                    ((1, 0), "E"),
                    ((-1, 0), "W"),
                    ((0, 1), "S"),
                    ((0, -1), "N"),
                ]

                if percepts["breeze"] and percepts["stench"] and percepts["bump"] and not self.Wumpus_detected:

                    print("\nFIRST CONDITION")

                    for (dx,dy) , _ in directions:
                        nx, ny = pos[0] + dx, pos[1] + dy

                        if self.last_action[1] == name:
                            nx , ny = pos[0] + dx , pos[1] + dy

                            self.Wall_positions.add(f"{nx},{ny}")

                        if 0 <= nx < map_size[0] and 0 <= ny < map_size[1] and f"{nx},{ny}" not in self.safe_cells:
                            self.Hole_positions[f"{nx},{ny}"] = self.Hole_positions.get(f"{nx},{ny}", 0) + 1
                            self.Wumpus_positions[f"{nx},{ny}"] = self.Wumpus_positions.get(f"{nx},{ny}",0) + 1

                            Last_hole_position = f"{nx},{ny}"
                            number_of_holes += 1

                    if number_of_holes == 1 and Last_hole_position:
                        self.Hole_positions[Last_hole_position] += 100

                    self.detected_Wumpus_cell = f"{pos[0],pos[1]}"


                elif percepts["breeze"] and percepts["stench"] and not self.Wumpus_detected:

                    print("\nSECOND CONDITION")

                    for (dx,dy) , _ in directions:
                        nx, ny = pos[0] + dx, pos[1] + dy

                        if 0 <= nx < map_size[0] and 0 <= ny < map_size[1] and f"{nx},{ny}" not in (self.safe_cells and self.Wall_positions):
                            self.Hole_positions[f"{nx},{ny}"] = self.Hole_positions.get(f"{nx},{ny}", 0) + 1
                            self.Wumpus_positions[f"{nx},{ny}"] = self.Wumpus_positions.get(f"{nx},{ny}",0) + 1
                            
                            Last_hole_position = f"{nx},{ny}"
                            number_of_holes += 1

                    if number_of_holes == 1 and Last_hole_position:
                        self.Hole_positions[Last_hole_position] += 100

                    self.detected_Wumpus_cell = f"{pos[0],pos[1]}"



                elif percepts["bump"] and percepts["breeze"]:

                    print("\nTHIRD CONDITION")

                    for (dx,dy) , name in directions:

                        if self.last_action[1] == name:
                            nx , ny = pos[0] + dx , pos[1] + dy

                            self.Wall_positions.add(f"{nx},{ny}")

                            if 0 <= nx < map_size[0] and 0 <= ny < map_size[1] and f"{nx},{ny}" not in self.safe_cells:
                                self.Hole_positions[f"{nx},{ny}"] = self.Hole_positions.get(f"{nx},{ny}", 0) + 1

                                Last_hole_position = f"{nx},{ny}"
                                number_of_holes += 1

                    if number_of_holes == 1 and Last_hole_position:
                        self.Hole_positions[Last_hole_position] += 100



                elif percepts["bump"]:

                    print("\nFORTH CONDITION")

                    for (dx,dy) , name in directions:

                        if self.last_action[1] == name:
                            nx , ny = pos[0] + dx , pos[1] + dy

                            self.Wall_positions.add(f"{nx},{ny}")


                elif percepts["breeze"]:

                    print("\nFIFTH CONDITION")

                    for (dx,dy) , _ in directions:
                        nx, ny = pos[0] + dx, pos[1] + dy

                        if 0 <= nx < map_size[0] and 0 <= ny < map_size[1] and f"{nx},{ny}" not in self.safe_cells:
                            self.Hole_positions[f"{nx},{ny}"] = self.Hole_positions.get(f"{nx},{ny}", 0) + 1

                            Last_hole_position = f"{nx},{ny}"
                            number_of_holes += 1

                    if number_of_holes == 1 and Last_hole_position:
                        self.Hole_positions[Last_hole_position] += 100


                elif percepts["stench"] and (not self.Wumpus_detected):

                    print("\nSIXTH CONDITION")

                    for (dx,dy) , _ in directions:
                        nx, ny = pos[0] + dx, pos[1] + dy

                        if 0 <= nx < map_size[0] and 0 <= ny < map_size[1] and f"{nx},{ny}" not in self.safe_cells:
                           
                            self.Wumpus_positions[f"{nx},{ny}"] = self.Wumpus_positions.get(f"{nx},{ny}",0) + 1

                            if f"{nx},{ny}" in self.Hole_positions:
                                self.safe_cells.add(f"{nx},{ny}")
                                print("Taken from wumpus: ",nx,ny)

                    self.detected_Wumpus_cell = f"{pos[0],pos[1]}"


                elif not percepts["stench"] and not percepts["breeze"] and not percepts["bump"]:

                    print("\nSEVENTH CONDITION")

                    for (dx, dy) , _ in directions:
                        nx, ny = pos[0] + dx, pos[1] + dy

                        if 0 <= nx < map_size[0] and 0 <= ny < map_size[1] and f"{nx},{ny}" not in self.Wall_positions:
                            self.safe_cells.add(f"{nx},{ny}")

                self.safe_cells.add(f"{pos[0]},{pos[1]}")

                self.safe_cells -= self.Wall_positions

                for cell in self.safe_cells:
                    self.Wumpus_positions.pop(cell, None)
                    self.Hole_positions.pop(cell, None)

                for cell in self.Wall_positions:
                    self.Hole_positions.pop(cell, None)

                if len(self.Wumpus_positions) == 1:
                    self.Wumpus_detected = True


            self.last_visitedCell = f"{pos[0]},{pos[1]}"

            if not self.current_state.get("running"):
                print("Termination Reason: ",self.current_state.get("termination_reason"))

                termination = self.current_state.get("termination_reason") or ""

                # Record the gold cell when the agent wins so future runs can
                # beeline directly to it
                if "gold" in termination.lower() or "win" in termination.lower() or "grabbed" in termination.lower():
                    self.confirmed_gold = f"{pos[0]},{pos[1]}"
                    print(f"[GOLD] Gold location confirmed at {self.confirmed_gold} — will beeline next run.")

                if self.current_state.get("termination_reason") == "GAME OVER: Wumpus!":
                    confirmed_score = self.Wumpus_positions.get(self.last_visitedCell, 0) + 100
                    # Rebuild dict with only the confirmed Wumpus cell — avoids
                    # "dictionary changed size during iteration" from pop() inside a loop
                    self.Wumpus_positions = {self.last_visitedCell: confirmed_score}
                    self.Wumpus_detected = True
                    self.confirmed_wumpus.add(self.last_visitedCell)
                    self.safe_cells.discard(self.last_visitedCell)

                if self.current_state.get("termination_reason") == "GAME OVER: Pit!":
                    self.Hole_positions[self.last_visitedCell] = self.Hole_positions.get(self.last_visitedCell,0) + 100
                    # Record as confirmed pit so future BFS escape never targets it
                    self.confirmed_pits.add(self.last_visitedCell)
                    self.safe_cells.discard(self.last_visitedCell)



    def get_risk(self, cell: str) -> float:
        return self.Hole_positions.get(cell, 0) + self.Wumpus_positions.get(cell, 0)

    def _is_looping(self) -> bool:
        """Return True when any cell appears 3+ times in the recent position history."""
        # Need at least 6 entries so a single back-and-forth doesn't trigger this
        if len(self.position_history) < 6:
            return False
        counts = Counter(self.position_history)
        return any(v >= 3 for v in counts.values())

    def _is_confirmed_deadly(self, cell: str) -> bool:
        """
        True only for cells we are certain the agent cannot survive:
          - confirmed wall
          - cells where the agent has actually died in a pit (confirmed_pits)
          - the single pinpointed Wumpus cell (Wumpus_detected + exactly 1 candidate)
        Near-danger (high breeze / stench score) is suspected but NOT confirmed deadly.
        """
        if cell in self.Wall_positions:
            return True
        if cell in self.confirmed_pits:
            return True
        if self.Wumpus_detected and len(self.Wumpus_positions) == 1 and cell in self.Wumpus_positions:
            return True
        return False

    def _bfs_to_unknown(self, escape_mode: bool = False) -> Optional[deque]:
        """
        BFS from the current position toward the nearest unvisited cell.
        Returns the FULL sequence of directions as a deque, or None if no
        reachable target exists.

        Normal mode  — only walks through safe_cells | visited; targets safe_cells - visited.
        Escape mode  — walks through ANY cell that isn't confirmed deadly; targets any
                       unvisited, non-confirmed-deadly cell. Used when the agent is stuck
                       in a loop and needs to risk an unknown cell to break out.
        """
        if not self.current_state:
            return None

        pos = self.current_state.get("position")
        if not pos:
            return None

        start = (pos[0], pos[1])
        dir_map = [(1, 0, "E"), (-1, 0, "W"), (0, 1, "S"), (0, -1, "N")]

        if escape_mode:
            # Target: anything unvisited that we aren't certain will kill us
            targets = {
                f"{nx},{ny}"
                for nx in range(self.current_state.get("width", 20))
                for ny in range(self.current_state.get("height", 20))
                if f"{nx},{ny}" not in self.visited
                and not self._is_confirmed_deadly(f"{nx},{ny}")
            }
        else:
            # Target: known-safe cells not yet stepped on
            targets = self.safe_cells - self.visited

        if not targets:
            return None

        # BFS: each entry is (position, path_so_far_as_list_of_directions)
        queue: deque = deque()
        queue.append((start, []))
        seen: Set[Tuple[int, int]] = {start}

        while queue:
            (cx, cy), path = queue.popleft()
            cell = f"{cx},{cy}"

            # Found a target that isn't the starting cell — return the full path
            if cell in targets and (cx, cy) != start:
                return deque(path)

            for dx, dy, name in dir_map:
                nx, ny = cx + dx, cy + dy
                npos = (nx, ny)
                ncell = f"{nx},{ny}"

                if npos in seen or self._is_confirmed_deadly(ncell):
                    continue

                if escape_mode:
                    # Walk through anything that isn't confirmed deadly
                    can_traverse = True
                else:
                    # Walk only through cells we know are safe
                    can_traverse = ncell in self.safe_cells or ncell in self.visited

                if can_traverse:
                    seen.add(npos)
                    queue.append((npos, path + [name]))

        return None  # No reachable target found

    def _bfs_to_cell(self, target_cell: str, extra_blocked: Optional[Set[str]] = None) -> Optional[deque]:
        """
        BFS from the current position to a specific target cell.
        Avoids confirmed deadly cells plus anything in extra_blocked.
        Returns the full path as a deque of directions, or None if unreachable.
        """
        if not self.current_state:
            return None
        pos = self.current_state.get("position")
        if not pos:
            return None

        blocked = extra_blocked or set()
        start = (pos[0], pos[1])
        tx, ty = map(int, target_cell.split(","))
        target = (tx, ty)
        dir_map = [(1, 0, "E"), (-1, 0, "W"), (0, 1, "S"), (0, -1, "N")]

        queue: deque = deque()
        queue.append((start, []))
        seen: Set[Tuple[int, int]] = {start}

        while queue:
            (cx, cy), path = queue.popleft()

            if (cx, cy) == target and (cx, cy) != start:
                return deque(path)

            for dx, dy, name in dir_map:
                nx, ny = cx + dx, cy + dy
                npos = (nx, ny)
                ncell = f"{nx},{ny}"

                if npos in seen:
                    continue
                if self._is_confirmed_deadly(ncell):
                    continue
                if ncell in blocked:
                    continue

                seen.add(npos)
                queue.append((npos, path + [name]))

        return None

    async def deliberate(self) -> Optional[Union[str, Tuple[str, str]]]:
        """
        Completely ignore percepts and pick a random action.

        Returns:
            A random direction or a shoot action.
        """

        # Isto será usado para fazermos as ações do agente

        cell_options = [] # Opções de escolha para deslocar para uma célula segura
        dangerous_moves = [] # Opção de escolha para deslocar para uma célula perigosa

        print("Safe cells: ",self.safe_cells)
        print("Visited cells: ",self.visited)
        print("Wumpus cells: ",self.Wumpus_positions)
        print("Hole positions: ",self.Hole_positions)
        print("Wall Positions: ",self.Wall_positions)
        print("Confirmed pits: ",self.confirmed_pits)

        directions = [
            ((1, 0), "E"),
            ((-1, 0), "W"),
            ((0, 1), "S"),
            ((0, -1), "N"),
        ]

        dir_to_delta = {"E": (1, 0), "W": (-1, 0), "S": (0, 1), "N": (0, -1)}

        if self.current_state:
            pos = self.current_state.get("position")
            arrows = self.current_state.get("arrows", 0)

            # Gold beeline 
            # If we know where the gold is from a previous run, commit to the
            # shortest path there at the very start of the run.
            # Two paths are computed:
            #   safe_path  — avoids the Wumpus cell entirely
            #   direct_path — routes through/past the Wumpus cell
            # If the detour to avoid the Wumpus costs more than 10 extra steps
            # it's cheaper to shoot (10 pts) than to walk around, so we let the
            # existing shoot logic below handle alignment and firing, and we
            # follow the direct path instead.
            if self.confirmed_gold and pos:
                if not self.gold_path:
                    # Determine which cells to treat as blocked for the safe route
                    wumpus_blocked: Set[str] = set()
                    if self.Wumpus_detected and len(self.Wumpus_positions) == 1:
                        wumpus_blocked = set(self.Wumpus_positions.keys())

                    safe_path  = self._bfs_to_cell(self.confirmed_gold, extra_blocked=wumpus_blocked)
                    direct_path = self._bfs_to_cell(self.confirmed_gold, extra_blocked=set())

                    if safe_path and direct_path:
                        detour = len(safe_path) - len(direct_path)
                        if wumpus_blocked and detour > 10:
                            # Shooting is worth it — follow the direct path and let
                            # the shoot block below fire the arrow when aligned
                            print(f"[GOLD] Detour to avoid Wumpus is {detour} steps — cheaper to shoot. Following direct path.")
                            self.gold_path = direct_path
                        else:
                            print(f"[GOLD] Safe path to gold is {len(safe_path)} steps (detour={detour}). Committing.")
                            self.gold_path = safe_path
                    elif safe_path:
                        print(f"[GOLD] Only safe path available ({len(safe_path)} steps). Committing.")
                        self.gold_path = safe_path
                    elif direct_path:
                        print(f"[GOLD] Only direct path available ({len(direct_path)} steps) — Wumpus must be shot en route.")
                        self.gold_path = direct_path
                    else:
                        print("[GOLD] Gold is unreachable with current knowledge — falling back to exploration.")

                if self.gold_path:
                    next_dir = self.gold_path[0]
                    if next_dir in dir_to_delta:
                        ddx, ddy = dir_to_delta[next_dir]
                        next_cell = f"{pos[0]+ddx},{pos[1]+ddy}"
                        if self._is_confirmed_deadly(next_cell):
                            print(f"[GOLD] Next cell {next_cell} is confirmed deadly — replanning.")
                            self.gold_path.clear()
                        else:
                            self.gold_path.popleft()
                            print(f"[GOLD] Beelining to gold → {next_dir} ({len(self.gold_path)} steps remaining).")
                            self.last_action = ("move", next_dir)
                            return next_dir
                    else:
                        self.gold_path.clear()

            # Wumpus shot
            # If the Wumpus position is confirmed and we have arrows, check
            # whether we are aligned (same row or column) and shoot immediately.
            # We never waste the arrow on a guess — only fire when Wumpus_detected
            # is True and there is exactly one candidate cell.
            if self.Wumpus_detected and len(self.Wumpus_positions) == 1 and arrows > 0 and pos:
                wx, wy = map(int, next(iter(self.Wumpus_positions)).split(","))
                px, py = pos[0], pos[1]
                shoot_dir = None

                if wx == px and wy < py:   # Wumpus is directly North
                    shoot_dir = "N"
                elif wx == px and wy > py: # Wumpus is directly South
                    shoot_dir = "S"
                elif wy == py and wx > px: # Wumpus is directly East
                    shoot_dir = "E"
                elif wy == py and wx < px: # Wumpus is directly West
                    shoot_dir = "W"

                if shoot_dir:
                    print(f"[SHOOT] Wumpus confirmed at {wx},{wy} — firing arrow {shoot_dir}!")
                    self.escape_path.clear()  # cancel any pending escape; shot changes the board state
                    self.last_action = ("shoot", shoot_dir)
                    return ("shoot", shoot_dir)
                else:
                    print(f"[SHOOT] Wumpus confirmed at {wx},{wy} but not aligned with {px},{py} — navigating to line up.")


            # Committed escape path 
            # If a BFS escape path is in progress, consume it one step at a time.
            # Before each step, validate the next cell hasn't become confirmed
            # deadly since the path was built (e.g. we just learned it's a pit).
            if self.escape_path:
                next_dir = self.escape_path[0]
                if pos and next_dir in dir_to_delta:
                    ddx, ddy = dir_to_delta[next_dir]
                    next_cell = f"{pos[0]+ddx},{pos[1]+ddy}"
                    if self._is_confirmed_deadly(next_cell):
                        print(f"[LOOP ESCAPE] Next cell {next_cell} is now confirmed deadly — aborting path, replanning.")
                        self.escape_path.clear()
                    else:
                        self.escape_path.popleft()
                        print(f"[LOOP ESCAPE] Following committed path → {next_dir} ({len(self.escape_path)} steps remaining).")
                        self.last_action = ("move", next_dir)
                        return next_dir
                else:
                    self.escape_path.clear()  # malformed entry, discard


            # Loop detection 
            if self._is_looping():
                print("\n[LOOP DETECTED] Building BFS escape path.")

                # Stage 1: safe cells only, no risk
                path = self._bfs_to_unknown(escape_mode=False)
                if path:
                    print(f"[LOOP ESCAPE] Safe path found ({len(path)} steps).")
                else:
                    # Stage 2: allow unknown/risky cells; only confirmed deadly blocked
                    print("[LOOP ESCAPE] No safe path; trying risky BFS.")
                    path = self._bfs_to_unknown(escape_mode=True)
                    if path:
                        print(f"[LOOP ESCAPE] Risky path found ({len(path)} steps, may cross unknown cells).")

                if path:
                    self.position_history.clear()  # prevents re-triggering mid-path
                    self.escape_path = path
                    next_dir = self.escape_path.popleft()
                    print(f"[LOOP ESCAPE] Starting escape → {next_dir} ({len(self.escape_path)} steps remaining).")
                    self.last_action = ("move", next_dir)
                    return next_dir
                else:
                    print("[LOOP ESCAPE] Completely surrounded by confirmed deadly cells; falling back to normal logic.")

            candidates = []

            for (dx, dy), name in directions:
                nx, ny = pos[0] + dx, pos[1] + dy
                cell = f"{nx},{ny}"

                # Skip walls and anything we know for certain is fatal
                if self._is_confirmed_deadly(cell):
                    continue

                risk = self.get_risk(cell)

                if cell in self.safe_cells and cell not in self.visited:
                    priority = 0
                elif cell in self.safe_cells:
                    priority = 1
                else:
                    priority = 2

                candidates.append((cell, name, priority, risk))


            if candidates:
                candidates.sort(key=lambda x: (x[2], x[3]))

                best_priority = candidates[0][2]
                best_candidates = [c for c in candidates if c[2] == best_priority]

                min_risk = min(c[3] for c in best_candidates)
                best_moves = [c for c in best_candidates if c[3] == min_risk]

                print("Best moves: ",best_moves)

                cell_to_move, direction, _, risk = random.choice(best_moves)

                print(f"Moving {direction} to {cell_to_move} (risk={risk})")

                self.last_action = ("move", direction)
                return direction



    def reset_memory(self) -> None:
        """Clears the set of visited tiles."""
        self.visited.clear()

        self.last_action = None
        self.last_visitedCell = None

        self.probabilities = [0.25 , 0.25 , 0.25 , 0.25]

        self.position_history.clear()
        self.escape_path.clear()
        self.gold_path.clear()  # rebuilt fresh each run from confirmed_gold

        # confirmed_pits and confirmed_wumpus are intentionally NOT cleared here.
        # They persist across resets so the agent remembers where dangers are.
        # Repopulate Wumpus_positions from confirmed_wumpus so the new run
        # treats those cells as dangerous from the start, even if the Wumpus
        # was killed last run (it respawns).
        for cell in self.confirmed_wumpus:
            self.Wumpus_positions[cell] = max(self.Wumpus_positions.get(cell, 0), 100)
            self.safe_cells.discard(cell)
        if self.confirmed_wumpus:
            self.Wumpus_detected = True

    async def send_telemetry(self, websocket: Any) -> None:
        """
        Send basic telemetry so the UI renders the explored path.

        Args:
            websocket: The websocket connection to the server.
        """
        percepts = self.current_state.get("percepts", {}) if self.current_state else {}
        payload = {
            "action": "telemetry",
            "data": {
                "visited": list(self.visited),
                "percepts": percepts,
                "agent_pos": self.current_state.get("position") if self.current_state else None,
                "current_probs": {  "N": self.probabilities[0],
                                    "S": self.probabilities[1],
                                    "E": self.probabilities[2],
                                    "W": self.probabilities[3],},
            },
        }
        await websocket.send(json.dumps(payload))


if __name__ == "__main__":
    agent = DummyAgent()
    asyncio.run(agent.run())