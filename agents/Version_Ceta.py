import asyncio
import json
import os
import random
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



    def update_memory(self) -> None:
        """Track where we have been just to paint the UI blue."""
        # Isto será mais usado para atualizar as variáveis que temos em relação à memóra 

        if self.current_state:
            pos = self.current_state.get("position")
            self.map_name = self.current_state.get("map_name")

            if pos:
                self.visited.add(f"{pos[0]},{pos[1]}")

                percepts = self.current_state.get("percepts", {}) if self.current_state else {}

                active_percepts = [k.capitalize() for k, v in percepts.items() if v]
                percept_str = ", ".join(active_percepts) if active_percepts else "None"

                score = self.current_state.get("score", 0)
                arrows = self.current_state.get("arrows", 0)

                map_size: list[int] = list([self.current_state.get("width",0),self.current_state.get("height",0)]) # Inicialização do tamanho do mapa

                print(f"\n--- Agent at {pos[0],pos[1]} | Score: {score} | Arrows: {arrows} ---")
                print(f"Percepts: [{percept_str}]")

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

                    self.detected_Wumpus_cell = f"{pos[0],pos[1]}"


                elif percepts["breeze"] and percepts["stench"] and not self.Wumpus_detected:

                    print("\nSECOND CONDITION")

                    for (dx,dy) , _ in directions:
                        nx, ny = pos[0] + dx, pos[1] + dy

                        if 0 <= nx < map_size[0] and 0 <= ny < map_size[1] and f"{nx},{ny}" not in self.safe_cells:
                            self.Hole_positions[f"{nx},{ny}"] = self.Hole_positions.get(f"{nx},{ny}", 0) + 1
                            self.Wumpus_positions[f"{nx},{ny}"] = self.Wumpus_positions.get(f"{nx},{ny}",0) + 1

                    self.detected_Wumpus_cell = f"{pos[0],pos[1]}"



                elif percepts["bump"] and percepts["breeze"]:

                    print("\nTHIRD CONDITION")

                    for (dx,dy) , name in directions:

                        if self.last_action[1] == name:
                            nx , ny = pos[0] + dx , pos[1] + dy

                            self.Wall_positions.add(f"{nx},{ny}")

                            if 0 <= nx < map_size[0] and 0 <= ny < map_size[1] and f"{nx},{ny}" not in self.safe_cells:
                                self.Hole_positions[f"{nx},{ny}"] = self.Hole_positions.get(f"{nx},{ny}", 0) + 1




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

                    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

                    for dx, dy in directions:
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

                if self.current_state.get("termination_reason") == "GAME OVER: Wumpus!":
                    self.Wumpus_positions[self.last_visitedCell] = self.Wumpus_positions.get(self.last_visitedCell,0) + 100

                    for cells in self.Wumpus_positions:
                        if cells != self.last_visitedCell:
                            self.Wumpus_positions.pop(self.last_visitedCell, None)

                    self.safe_cells.remove(self.last_visitedCell)

                if self.current_state.get("termination_reason") == "GAME OVER: Pit!":
                    self.Hole_positions[self.last_visitedCell] = self.Hole_positions.get(self.last_visitedCell,0) + 100
                    self.safe_cells.remove(self.last_visitedCell)



    def get_risk(self, cell: str) -> float:
        return self.Hole_positions.get(cell, 0) + self.Wumpus_positions.get(cell, 0)

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

        directions = [
            ((1, 0), "E"),
            ((-1, 0), "W"),
            ((0, 1), "S"),
            ((0, -1), "N"),
        ]


        if self.current_state:
            pos = self.current_state.get("position")

            candidates = []

            for (dx, dy), name in directions:
                nx, ny = pos[0] + dx, pos[1] + dy
                cell = f"{nx},{ny}"

                if cell in self.Wall_positions:
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

        if self.current_state:

            if (self.current_state.get("map_name")  == self.map_name):

                self.safe_cells.clear()
                self.Wumpus_positions.clear()
                self.Hole_positions.clear()
                self.map_size.clear()
                self.Wall_positions.clear()

                self.Wumpus_detected = False

        self.last_action = None
        self.last_visitedCell = None

        self.probabilities = [0.25 , 0.25 , 0.25 , 0.25]

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
