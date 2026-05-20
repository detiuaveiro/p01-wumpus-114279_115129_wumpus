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
            server_uri: URI do servidor de simulação.
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

        # Deteção de loops: guarda as últimas 10 posições. Se uma repetir 3+ vezes, o agente está preso.
        self.position_history: deque = deque(maxlen=10)

        # Caminho BFS para escapar de loops. Executado passo a passo no deliberate().
        self.escape_path: deque = deque()

        # Buracos confirmados (onde o agente morreu). Persiste entre resets no mesmo mapa.
        self.confirmed_pits: Set[str] = set()

        # Células do Wumpus confirmadas. Persiste entre resets; limpo se o Wumpus for morto.
        self.confirmed_wumpus: Set[str] = set()

        # Localização do ouro de tentativas anteriores. Persiste para ir direto ao alvo.
        self.confirmed_gold: Optional[str] = None

        # Caminho para o ouro, executado um passo por turno.
        self.gold_path: deque = deque()


    def update_memory(self) -> None:
        """Tracks the current position to update the UI."""
        # Isto será mais usado para atualizar as variáveis que temos em relação à memóra 

        if self.current_state:
            pos = self.current_state.get("position")

            print((self.current_state.get("map_name")  != self.map_name))

            current_map = self.current_state.get("map_name")

            if current_map != self.map_name:

                print("Reseting Cells!")

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

                # Grito: a flecha acertou no Wumpus. Marca a célula do Wumpus como segura e não visitada.
                if percepts.get("scream") and self.last_action and self.last_action[0] == "shoot":
                    print("[SCREAM] Arrow hit! Wumpus is dead.")
                    for wumpus_cell in list(self.Wumpus_positions.keys()):
                        self.safe_cells.add(wumpus_cell)
                        self.visited.discard(wumpus_cell)   # Tratar como não visitada (explorar)
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

                # Guarda a célula do ouro ao ganhar para ir direto na próxima tentativa.
                if "gold" in termination.lower() or "win" in termination.lower() or "grabbed" in termination.lower():
                    self.confirmed_gold = f"{pos[0]},{pos[1]}"
                    print(f"[GOLD] Gold location confirmed at {self.confirmed_gold} - will beeline next run.")

                if self.current_state.get("termination_reason") == "GAME OVER: Wumpus!":
                    confirmed_score = self.Wumpus_positions.get(self.last_visitedCell, 0) + 100
                    # Reconstrói o dicionário só com a célula confirmada do Wumpus (evita erros de iteração).
                    self.Wumpus_positions = {self.last_visitedCell: confirmed_score}
                    self.Wumpus_detected = True
                    self.confirmed_wumpus.add(self.last_visitedCell)
                    self.safe_cells.discard(self.last_visitedCell)

                if self.current_state.get("termination_reason") == "GAME OVER: Pit!":
                    self.Hole_positions[self.last_visitedCell] = self.Hole_positions.get(self.last_visitedCell,0) + 100
                    # Regista como poço confirmado para o BFS o ignorar no futuro.
                    self.confirmed_pits.add(self.last_visitedCell)
                    self.safe_cells.discard(self.last_visitedCell)


    def get_risk(self, cell: str) -> float:
        return self.Hole_positions.get(cell, 0) + self.Wumpus_positions.get(cell, 0)

    def _is_looping(self) -> bool:
        """Retorna True se alguma célula aparecer 3+ vezes no histórico recente."""
        # Requer pelo menos 6 entradas para evitar falsos positivos num vai-e-vem.
        if len(self.position_history) < 6:
            return False
        counts = Counter(self.position_history)
        return any(v >= 3 for v in counts.values())

    def _is_confirmed_deadly(self, cell: str) -> bool:
        """
        Verdadeiro apenas para células com morte certa (paredes, poços confirmados ou Wumpus exato).
        Perigo suspeito não é confirmado como mortal.
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
        Busca BFS para a célula não visitada mais próxima. Retorna o caminho completo.
        normal_mode: caminha apenas por células seguras/visitadas.
        escape_mode: arrisca células desconhecidas, evitando apenas as de morte certa.
        """
        if not self.current_state:
            return None

        pos = self.current_state.get("position")
        if not pos:
            return None

        start = (pos[0], pos[1])
        dir_map = [(1, 0, "E"), (-1, 0, "W"), (0, 1, "S"), (0, -1, "N")]

        if escape_mode:
            # Alvo: qualquer célula não visitada sem morte certa.
            targets = {
                f"{nx},{ny}"
                for nx in range(self.current_state.get("width", 20))
                for ny in range(self.current_state.get("height", 20))
                if f"{nx},{ny}" not in self.visited
                and not self._is_confirmed_deadly(f"{nx},{ny}")
            }
        else:
            # Alvo: células seguras não visitadas.
            targets = self.safe_cells - self.visited

        if not targets:
            return None

        # BFS: cada entrada é (posição, caminho_ate_agora).
        queue: deque = deque()
        queue.append((start, []))
        seen: Set[Tuple[int, int]] = {start}

        while queue:
            (cx, cy), path = queue.popleft()
            cell = f"{cx},{cy}"

            # Encontrou um alvo válido - retorna o caminho completo.
            if cell in targets and (cx, cy) != start:
                return deque(path)

            for dx, dy, name in dir_map:
                nx, ny = cx + dx, cy + dy
                npos = (nx, ny)
                ncell = f"{nx},{ny}"

                if npos in seen or self._is_confirmed_deadly(ncell):
                    continue

                if escape_mode:
                    # Pode atravessar tudo que não for morte certa.
                    can_traverse = True
                else:
                    # Caminha apenas por células seguras.
                    can_traverse = ncell in self.safe_cells or ncell in self.visited

                if can_traverse:
                    seen.add(npos)
                    queue.append((npos, path + [name]))

        return None  # Nenhum alvo alcançável.

    def _bfs_to_cell(self, target_cell: str, extra_blocked: Optional[Set[str]] = None) -> Optional[deque]:
        """
        Busca BFS para uma célula específica, evitando mortes certas e bloqueios extra.
        Retorna o caminho ou None se inalcançável.
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
        Decide a próxima ação (movimento ou disparo).
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

            # Rota direta ao Ouro: calcula caminho seguro e caminho direto. Se o desvio seguro custar >10 passos, é melhor seguir a direito e disparar contra o Wumpus.
            if self.confirmed_gold and pos:
                if not self.gold_path:
                    # Determina células bloqueadas para a rota segura.
                    wumpus_blocked: Set[str] = set()
                    if self.Wumpus_detected and len(self.Wumpus_positions) == 1:
                        wumpus_blocked = set(self.Wumpus_positions.keys())

                    safe_path  = self._bfs_to_cell(self.confirmed_gold, extra_blocked=wumpus_blocked)
                    direct_path = self._bfs_to_cell(self.confirmed_gold, extra_blocked=set())

                    if safe_path and direct_path:
                        detour = len(safe_path) - len(direct_path)
                        if wumpus_blocked and detour > 10:
                            # Vale a pena disparar: segue rota direta e dispara quando alinhado.
                            print(f"[GOLD] Detour to avoid Wumpus is {detour} steps - cheaper to shoot. Following direct path.")
                            self.gold_path = direct_path
                        else:
                            print(f"[GOLD] Safe path to gold is {len(safe_path)} steps (detour={detour}). Committing.")
                            self.gold_path = safe_path
                    elif safe_path:
                        print(f"[GOLD] Only safe path available ({len(safe_path)} steps). Committing.")
                        self.gold_path = safe_path
                    elif direct_path:
                        print(f"[GOLD] Only direct path available ({len(direct_path)} steps) - Wumpus must be shot en route.")
                        self.gold_path = direct_path
                    else:
                        print("[GOLD] Gold is unreachable with current knowledge - falling back to exploration.")

                if self.gold_path:
                    next_dir = self.gold_path[0]
                    if next_dir in dir_to_delta:
                        ddx, ddy = dir_to_delta[next_dir]
                        next_cell = f"{pos[0]+ddx},{pos[1]+ddy}"
                        if self._is_confirmed_deadly(next_cell):
                            print(f"[GOLD] Next cell {next_cell} is confirmed deadly - replanning.")
                            self.gold_path.clear()
                        else:
                            self.gold_path.popleft()
                            print(f"[GOLD] Beelining to gold → {next_dir} ({len(self.gold_path)} steps remaining).")
                            self.last_action = ("move", next_dir)
                            return next_dir
                    else:
                        self.gold_path.clear()

            # Disparo no Wumpus: se posição confirmada, alinhada e com flechas, dispara. Nunca desperdiça flechas em palpites.
            if self.Wumpus_detected and len(self.Wumpus_positions) == 1 and arrows > 0 and pos:
                wx, wy = map(int, next(iter(self.Wumpus_positions)).split(","))
                px, py = pos[0], pos[1]
                shoot_dir = None

                if wx == px and wy < py:   # Wumpus diretamente a Norte
                    shoot_dir = "N"
                elif wx == px and wy > py: # Wumpus diretamente a Sul
                    shoot_dir = "S"
                elif wy == py and wx > px: # Wumpus diretamente a Este
                    shoot_dir = "E"
                elif wy == py and wx < px: # Wumpus diretamente a Oeste
                    shoot_dir = "W"

                if shoot_dir:
                    print(f"[SHOOT] Wumpus confirmed at {wx},{wy} - firing arrow {shoot_dir}!")
                    self.escape_path.clear()  # Cancela fuga pendente; o disparo altera o estado do tabuleiro.
                    self.last_action = ("shoot", shoot_dir)
                    return ("shoot", shoot_dir)
                else:
                    print(f"[SHOOT] Wumpus confirmed at {wx},{wy} but not aligned with {px},{py} - navigating to line up.")


            # Caminho de fuga comprometido: consumido passo a passo, validando se a próxima célula não se tornou mortal entretanto.
            if self.escape_path:
                next_dir = self.escape_path[0]
                if pos and next_dir in dir_to_delta:
                    ddx, ddy = dir_to_delta[next_dir]
                    next_cell = f"{pos[0]+ddx},{pos[1]+ddy}"
                    if self._is_confirmed_deadly(next_cell):
                        print(f"[LOOP ESCAPE] Next cell {next_cell} is now confirmed deadly - aborting path, replanning.")
                        self.escape_path.clear()
                    else:
                        self.escape_path.popleft()
                        print(f"[LOOP ESCAPE] Following committed path → {next_dir} ({len(self.escape_path)} steps remaining).")
                        self.last_action = ("move", next_dir)
                        return next_dir
                else:
                    self.escape_path.clear()  # Entrada inválida, descarta.


            # Deteção de ciclo 
            if self._is_looping():
                print("\n[LOOP DETECTED] Building BFS escape path.")

                # Fase 1: apenas células seguras (sem risco).
                path = self._bfs_to_unknown(escape_mode=False)
                if path:
                    print(f"[LOOP ESCAPE] Safe path found ({len(path)} steps).")
                else:
                    # Fase 2: permite células de risco, evitando apenas morte certa.
                    print("[LOOP ESCAPE] No safe path; trying risky BFS.")
                    path = self._bfs_to_unknown(escape_mode=True)
                    if path:
                        print(f"[LOOP ESCAPE] Risky path found ({len(path)} steps, may cross unknown cells).")

                if path:
                    self.position_history.clear()  # Evita reativar a fuga a meio do caminho.
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

                # Ignora paredes e células com morte certa.
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
        self.gold_path.clear()  # Reconstruído a cada tentativa a partir do ouro confirmado.

        # Poços e Wumpus não são limpos para manter a memória dos perigos entre reinícios.
        for cell in self.confirmed_wumpus:
            self.Wumpus_positions[cell] = max(self.Wumpus_positions.get(cell, 0), 100)
            self.safe_cells.discard(cell)
        if self.confirmed_wumpus:
            self.Wumpus_detected = True

    async def send_telemetry(self, websocket: Any) -> None:
        """
        Pass the current percepts to the UI to update the tags panel.

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