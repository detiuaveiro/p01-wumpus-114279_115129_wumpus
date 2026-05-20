[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/iMKcprNB)
# <img src="frontend/favicon.svg" alt="logo" width="128" height="128" align="middle"> SI2 - Wumpus

## Introduction
In this README we are explicity going to explain our agent, as well as the fundamentals of our project and how we tackled them into our solution.

## Game Rules

The simulation follows the standard Wumpus World logic with additional features:
- **Percepts**: At each step, the agent receives a set of percepts:
  - `stench`: The Wumpus is in an adjacent cell.
  - `breeze`: A pit is in an adjacent cell.
  - `glitter`: Gold is in the current cell.
  - `bump`: The agent walked into an obstacle or the edge of the map.
  - `scream`: The Wumpus was killed by an arrow.
- **Actions**: The agent can perform the following actions:
  - `move`: Move one cell in a direction ('N', 'S', 'E', 'W').
  - `shoot`: Fire an arrow in a direction ('N', 'S', 'E', 'W').
- **World State**: The world is a grid of cells which can contain floors, obstacles, pits, the Wumpus, or gold. If teleportation is enabled, the grid is toroidal (wrapping around edges).
- **Scoring**:
  - -1 for each move.
  - -10 for shooting an arrow.
  - -1000 for dying (falling in a pit or being eaten by the Wumpus).
  - +1000 for achieving the objective (finding gold, reaching target, or exploring the room).


## Project Structure
### Agent Initialization
Our agent is similar to the ones taught in class, following a Sense-Think-Act architecture.
To start the agent, simply run:
```
python3 -m agents.final_agent
```
When the agent is initialized, the following variables are updated whenever we restart the simulation without changing the map:

- self.last_visited : Last visited cells
- self.position_history : History of the last 10 positions where our agent has been
- self.escape_path : BFS path used to escape loops
- self.gold_path.clear : Path to the gold

When the map is restarted, all other variables related to the map context are reset.

### Memory Update
Memory is only updated when the agent is present on the map.
When this happens, we store the map information, namely its height and width. In addition, we analyze its percepts and, according to a hierarchy of activated sensors/percepts, we update the agent’s memory.

Depending on the percepts, we update what may be adjacent to the agent.

- stench : Any cell adjacent to the agent is considered a possible Wumpus location
- bump : The cell the agent attempted to move into is considered a wall
- breeze : Any cell adjacent to the agent is considered a possible pit location
- scream : We remove the existence of the Wumpus from all of its possible positions

Whenever we detect a percept, we update the dictionary corresponding to the nature of the cell associated with that percept.
For example, when detecting breeze, we evaluate all adjacent cells as possible pit locations. If those positions do not yet exist, we assign them a weight of +1. If a possible pit position already exists in that cell, then we increment its weight by +1. The same logic applies to the Wumpus.

After processing the conditions related to the percepts detected by our agent, we mark the current cell as safe and store it as the last visited cell.

However, not all cells can be considered pits or Wumpus locations. If the agent’s directions combined with the target cell exceed the world boundaries, then that position is ignored.

After adding or updating cells, we verify whether the agent has already visited any of them. If so, we consider those cells safe rather than pits/Wumpus locations, removing them from the corresponding dictionaries. We also remove every cell contained in the safe cells set or visited cells set.

Finally, we verify whether the agent was terminated by the Wumpus or by a pit. If it was terminated by a pit, we assign a large weight to the indices corresponding to our last position and add the confirmed pit/Wumpus to a Set. If termination occurred due to detecting gold, then we store the gold cell.

### Decision Making
In this section, the agent applies algorithms ranging from simple approaches to Breadth-First Search algorithms, depending on the cells that still need to be visited.

As an additional note, at the beginning we print all Sets in order to track the agent’s memory in case there is any incorrect information.

Regarding the conditions activated to ensure the agent’s safety, if we already know the location of the gold, then a Breadth-First Search algorithm is applied. This algorithm calculates both the safe path and the direct path. If the safe detour costs more than 10 steps, the agent follows the direct route and shoots the Wumpus.

If we are aligned with the Wumpus and know that we must reach the gold, we shoot regardless of whether the Wumpus is adjacent, as long as it is in the same row or column as the agent.

If we encounter a dangerous path and want to backtrack in order to explore cells that, despite being dangerous, are likely candidates, we apply an algorithm that backtracks to the last cell that originated a branch.

Also, to prevent the agent from becoming trapped in cyclic movement patterns, the implementation maintains a history of the last visited positions. If the same cell appears repeatedly, the agent activates a BFS-based escape strategy that first searches for safe unexplored cells and, if necessary, allows controlled traversal through uncertain cells.

After all these cases, if none of them are activated, we proceed with a normal solution in which the agent explores every safe cell before choosing the cell that presents the least danger.
Each suspected pit or Wumpus position is associated with a weight representing how many percepts support that hypothesis. Cells with lower accumulated risk are prioritized during exploration.

## Analysis of the Results
With maps that contain few obstacles and have a well-defined path, the agent can solve them in 1 or 2 attempts, especially when it is uncertain between two cells. However, after exploring the safe path, it is able to consistently complete the route every subsequent time.

In maps where, for example, the Wumpus blocks the path, the agent requires several attempts because the route to the gold is considered more dangerous due to the number of cells classified as pits that are, in reality, safe. However, once the agent detects that shooting the Wumpus is necessary in order to reach the target cell, it will always perform that shooting action regardless of the distance.

Unlike a purely reactive agent, our implementation preserves confirmed information between simulation resets on the same map. This allows the agent to progressively improve its performance after each attempt.

## Conclusion

Overall, the agent combines probabilistic reasoning, memory persistence, and BFS-based pathfinding to progressively improve its performance across attempts. While uncertainty in early exploration may lead to risky decisions, the agent becomes increasingly efficient as more information about the environment is confirmed.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
