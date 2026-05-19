import asyncio
import json
import os
import random
from collections import Counter, deque
from typing import Any, Optional, Set, Tuple, Union

from agents.base_agent import BaseAgent


class DummyAgent(BaseAgent):

    def __init__(self, server_uri: Optional[str] = None) -> None:

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

        # Loop detection: guarda as últimas 10 posições visitadas.
        # Se alguma célula aparecer 3+ vezes, o agente é considerado preso.
        self.position_history: deque = deque(maxlen=10)

        # Quando uma escapatória do loop é detetada, o caminho completo do BFS é armazenado aqui.
        # deliberate() consome uma direção por turno até que todo o caminho seja percorrido.
        self.escape_path: deque = deque()

        # Cells onde o agente tem a certeza de que há um buraco.
        # Persiste mesmo após reset_memory() para que o agente nunca mais arrisque entrar nessas células.
        self.confirmed_pits: Set[str] = set()




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

                        if f"{nx},{ny}" in self.Wumpus_positions:
                            self.safe_cells.add(f"{nx},{ny}")
                            print("Taken from Holes: ",nx,ny)

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

                if self.current_state.get("termination_reason") == "GAME OVER: Wumpus!":
                    confirmed_score = self.Wumpus_positions.get(self.last_visitedCell, 0) + 100
                    # Reconstroi o dict apenas com a célula do Wumpus confirmada — evita o erro de 
                    # "dictionary changed size during iteration" from pop() inside a loop
                    self.Wumpus_positions = {self.last_visitedCell: confirmed_score}
                    self.Wumpus_detected = True
                    self.safe_cells.discard(self.last_visitedCell)

                if self.current_state.get("termination_reason") == "GAME OVER: Pit!":
                    self.Hole_positions[self.last_visitedCell] = self.Hole_positions.get(self.last_visitedCell,0) + 100
                    # Guarda a célula onde o agente morreu como um buraco confirmado para nunca mais arriscar entrar nela.
                    self.confirmed_pits.add(self.last_visitedCell)
                    self.safe_cells.discard(self.last_visitedCell)



    def get_risk(self, cell: str) -> float:
        return self.Hole_positions.get(cell, 0) + self.Wumpus_positions.get(cell, 0)

    def _is_looping(self) -> bool:
        """Return True quando o agente parece estar preso em um loop, baseado no histórico recente de posições visitadas."""
        # Necessita de pelo menos 6 entradas para evitar falsos positivos de loops no início do jogo.
        if len(self.position_history) < 6:
            return False
        counts = Counter(self.position_history)
        return any(v >= 3 for v in counts.values())

    def _is_confirmed_deadly(self, cell: str) -> bool:
        """
        Verdade apenas se a célula for uma parede, um buraco confirmado (onde o agente já morreu) 
        ou uma posição de Wumpus confirmada (se o Wumpus foi detectado e só resta uma posição possível).
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
        BFS desde a posição atual até a célula desconhecida mais próxima.
        Retorna o caminho completo como uma deque, ou None se não houver
        alvo alcançável.

        Normal mode  — apenas caminha por células que sabemos serem seguras, visando outras células seguras não visitadas.
        Escape mode  — caminha por qualquer célula que não seja confirmadamente mortal; 
                       visa qualquer célula não visitada e não confirmadamente mortal.
        """
        if not self.current_state:
            return None

        pos = self.current_state.get("position")
        if not pos:
            return None

        start = (pos[0], pos[1])
        dir_map = [(1, 0, "E"), (-1, 0, "W"), (0, 1, "S"), (0, -1, "N")]

        if escape_mode:
            # Target: qualquer célula que não seja confirmadamente mortal e que ainda não tenhamos visitado
            targets = {
                f"{nx},{ny}"
                for nx in range(self.current_state.get("width", 20))
                for ny in range(self.current_state.get("height", 20))
                if f"{nx},{ny}" not in self.visited
                and not self._is_confirmed_deadly(f"{nx},{ny}")
            }
        else:
            # Target: células seguras que ainda não visitamos
            targets = self.safe_cells - self.visited

        if not targets:
            return None

        # BFS: cada entrada é (position, path_so_far_as_list_of_directions)
        queue: deque = deque()
        queue.append((start, []))
        seen: Set[Tuple[int, int]] = {start}

        while queue:
            (cx, cy), path = queue.popleft()
            cell = f"{cx},{cy}"

            # Encontramos um alvo, retorna o caminho completo.
            if cell in targets and (cx, cy) != start:
                return deque(path)

            for dx, dy, name in dir_map:
                nx, ny = cx + dx, cy + dy
                npos = (nx, ny)
                ncell = f"{nx},{ny}"

                if npos in seen or self._is_confirmed_deadly(ncell):
                    continue

                if escape_mode:
                    # Caminha por qualquer célula que não seja confirmadamente mortal, mesmo que não saibamos se é segura ou perigosa.
                    can_traverse = True
                else:
                    # Caminha apenas por células que sabemos serem seguras.
                    can_traverse = ncell in self.safe_cells or ncell in self.visited

                if can_traverse:
                    seen.add(npos)
                    queue.append((npos, path + [name]))

        return None  # Nenhum caminho encontrado

    async def deliberate(self) -> Optional[Union[str, Tuple[str, str]]]:
        """
        Ignora percepções e escolhe uma ação aleatória.

        Retorna:
            uma direção ("N", "S", "E", "W") para mover, ou
            um tuple ("shoot", direção) para atirar, ou
            None para fazer nada.
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

            # Se um caminho do BFS estiver em progresso, corre-o um passo de cada vez.
            # Antes de andar o próximo passo, verifica se a próxima célula do caminho se tornou perigosa 
            # (ex: o agente morreu e resetou, ou descobriu um buraco que antes era desconhecido).
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
                    self.escape_path.clear()  # entrada inválida, discardar

            # Loop detection 
            if self._is_looping():
                print("\n[LOOP DETECTED] Building BFS escape path.")

                # Stage 1: células seguras apenas, evitando qualquer célula que não tenhamos certeza de que é segura
                path = self._bfs_to_unknown(escape_mode=False)
                if path:
                    print(f"[LOOP ESCAPE] Safe path found ({len(path)} steps).")
                else:
                    # Stage 2: permitir atravessar células que não sabemos se são seguras, 
                    # mas que também não são confirmadamente mortais (ex: células que nunca visitamos e que não estão na lista de células seguras).
                    print("[LOOP ESCAPE] No safe path; trying risky BFS.")
                    path = self._bfs_to_unknown(escape_mode=True)
                    if path:
                        print(f"[LOOP ESCAPE] Risky path found ({len(path)} steps, may cross unknown cells).")

                if path:
                    self.position_history.clear()  # previne reaparição do loop enquanto seguimos este caminho
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
        """Limpa a memória do agente, exceto por informações que ele tem certeza absoluta (ex: buracos confirmados onde ele já morreu)."""
        self.visited.clear()

        self.last_action = None
        self.last_visitedCell = None

        self.probabilities = [0.25 , 0.25 , 0.25 , 0.25]

        self.position_history.clear()
        self.escape_path.clear()
        # Note: confirmed_pits não é limpo de propósito.
        # O agente tem certeza absoluta de que essas células são perigosas porque ele já morreu nelas, 
        # então não faz sentido esquecer isso.

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