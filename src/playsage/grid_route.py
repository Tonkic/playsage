"""Bounded simple-path search for the observed Cyber Healer grid rules."""

import itertools
from dataclasses import dataclass, field

Cell = tuple[int, int]
DIRECTIONS = {"w": (-1, 0), "s": (1, 0), "a": (0, -1), "d": (0, 1)}


@dataclass(frozen=True)
class Board:
    rows: int
    columns: int
    blocked: frozenset[Cell]
    targets: frozenset[Cell]
    end: Cell
    ports: dict[Cell, str] = field(default_factory=dict)
    rotations: frozenset[Cell] = frozenset()
    ordered_targets: tuple[Cell, ...] = ()
    forced: dict[Cell, str] = field(default_factory=dict)
    teleports: dict[Cell, Cell] = field(default_factory=dict)

    def contains(self, cell):
        return 0 <= cell[0] < self.rows and 0 <= cell[1] < self.columns

    def allows(self, source, target, turns=0):
        delta = (target[0] - source[0], target[1] - source[1])
        reverse = {value: key for key, value in DIRECTIONS.items()}
        if delta not in reverse:
            return False
        key = reverse[delta]
        opposite = {"w": "s", "s": "w", "a": "d", "d": "a"}
        clockwise = {"w": "d", "d": "s", "s": "a", "a": "w"}
        if source in self.forced and key != self.forced[source]:
            return False
        if target in self.forced and opposite[key] == self.forced[target]:
            return False

        def rotated(cell):
            ports = self.ports.get(cell, "wsad")
            for _ in range(turns % 4):
                ports = "".join(clockwise[port] for port in ports)
            return ports

        return key in rotated(source) and opposite[key] in rotated(target)

    def validate(self, prefix):
        cells = (
            self.blocked
            | self.targets
            | {self.end}
            | set(prefix)
            | set(self.ports)
            | self.rotations
            | set(self.forced)
            | set(self.teleports)
            | set(self.teleports.values())
        )
        if not prefix or any(not self.contains(cell) for cell in cells):
            raise ValueError("invalid board coordinates or empty prefix")
        if self.blocked & (self.targets | {self.end} | set(prefix)):
            raise ValueError("blocked cell overlaps route/objective")
        if len(prefix) != len(set(prefix)):
            raise ValueError("prefix revisits a cell")
        if self.ordered_targets:
            if set(self.ordered_targets) != self.targets or len(self.ordered_targets) != len(
                self.targets
            ):
                raise ValueError("ordered targets must enumerate every target exactly once")
            collected = tuple(cell for cell in prefix if cell in self.targets)
            if collected != self.ordered_targets[: len(collected)]:
                raise ValueError("prefix violates target order")
        if self.end in prefix[:-1]:
            raise ValueError("prefix already crossed the end")
        if any(not ports or set(ports) - set(DIRECTIONS) for ports in self.ports.values()):
            raise ValueError("invalid directional ports")
        if any(key not in DIRECTIONS for key in self.forced.values()):
            raise ValueError("invalid quick-channel direction")
        if set(self.forced) & (
            self.blocked | self.targets | self.rotations | set(self.ports) | {self.end}
        ):
            raise ValueError("quick channel overlaps another special tile")
        if prefix[-1] in self.forced:
            raise ValueError("prefix must end after automatic movement settles")
        if any(a == b or self.teleports.get(b) != a for a, b in self.teleports.items()):
            raise ValueError("teleports must be distinct symmetric pairs")
        if set(self.teleports) & (
            self.blocked | self.targets | self.rotations | set(self.ports)
            | set(self.forced) | {self.end, prefix[0]}
        ):
            raise ValueError("teleport overlaps another special tile or start")
        if prefix[-1] in self.teleports and (
            len(prefix) < 2 or prefix[-2] != self.teleports[prefix[-1]]
        ):
            raise ValueError("prefix must end after teleport settles")
        if self.rotations & (self.blocked | set(self.ports) | self.targets | {self.end}):
            raise ValueError("rotation cell overlaps another special tile")
        turns = int(prefix[0] in self.rotations)
        for index, (a, b) in enumerate(itertools.pairwise(prefix)):
            must_jump = a in self.teleports and (
                index == 0 or prefix[index - 1] != self.teleports[a]
            )
            if must_jump:
                if b != self.teleports[a]:
                    raise ValueError("prefix skips required teleport")
            elif not self.allows(a, b, turns):
                raise ValueError("prefix violates directional ports")
            turns += b in self.rotations


def solve(board: Board, prefix: list[Cell], max_nodes=200_000):
    """Return a legal continuation; fail closed on search exhaustion."""
    board.validate(prefix)
    seen = set(prefix)
    route = list(prefix)
    nodes = 0

    def visit():
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise RuntimeError("search budget exhausted")
        here = route[-1]
        turns = len(board.rotations & seen)
        if here == board.end:
            return board.targets <= seen
        # Every outstanding objective must remain reachable without crossing the route.
        # With rotations, use an optimistic over-approximation here: current ports
        # may open later. Exact candidate edges below always enforce every constraint.
        reachable, pending = {here}, [here]
        while pending:
            r, c = pending.pop()
            neighbors = [(r + dr, c + dc) for dr, dc in DIRECTIONS.values()]
            if (r, c) in board.teleports:
                neighbors.append(board.teleports[r, c])
            for nxt in neighbors:
                if (
                    board.contains(nxt)
                    and nxt not in board.blocked
                    and nxt not in seen
                    and nxt not in reachable
                    and (board.rotations or board.teleports.get((r, c)) == nxt
                         or board.allows((r, c), nxt, turns))
                ):
                    reachable.add(nxt)
                    pending.append(nxt)
        if not (board.targets - seen | {board.end}) <= reachable:
            return False
        options = []
        for key, (dr, dc) in DIRECTIONS.items():
            nxt = (here[0] + dr, here[1] + dc)
            if (
                board.contains(nxt)
                and nxt not in board.blocked
                and nxt not in seen
                and board.allows(here, nxt, turns)
            ):
                if nxt == board.end and not board.targets <= seen | {nxt}:
                    continue
                if (
                    board.ordered_targets
                    and nxt in board.targets
                    and nxt != board.ordered_targets[len(board.targets & seen)]
                ):
                    continue
                traversed = [nxt]
                if nxt in board.teleports:
                    destination = board.teleports[nxt]
                    if destination in seen:
                        continue
                    traversed.append(destination)
                options.append((nxt not in board.targets, key, traversed))
        for _, key, traversed in sorted(options):
            seen.update(traversed)
            route.extend(traversed)
            if visit():
                return True
            del route[-len(traversed):]
            seen.difference_update(traversed)
        return False

    if not visit():
        raise ValueError("no route collects all data before the end")
    return route


def keys_for(route):
    reverse = {delta: key for key, delta in DIRECTIONS.items()}
    return [reverse[(b[0] - a[0], b[1] - a[1])] for a, b in itertools.pairwise(route)]


def actions_for(board, route, prefix_length):
    """One key enters a channel chain; automatic edges receive no extra keys."""
    board.validate(route)
    index = prefix_length - 1
    if not 0 <= index < len(route) or route[index] in board.forced:
        raise ValueError("action prefix must end at a settled cell")
    while index < len(route) - 1:
        key = keys_for(route[index : index + 2])[0]
        end = index + 1
        while route[end] in board.forced or (
            route[end] in board.teleports and route[end - 1] != board.teleports[route[end]]
        ):
            end += 1
        yield key, route[index + 1 : end + 1]
        index = end


def advance(board: Board, prefix: list[Cell], key: str) -> list[Cell]:
    """Predict one key plus automatic movement, using the existing board contract.

    Pure and bounded by board area. An illegal/unknown move raises instead of
    claiming that the real game necessarily stayed still.
    """
    board.validate(prefix)
    if key not in DIRECTIONS:
        raise ValueError("unsupported grid action")
    if prefix[-1] == board.end:
        raise ValueError("cannot predict input after the end")
    route = list(prefix)
    seen = set(route)
    for _ in range(board.rows * board.columns):
        here = route[-1]
        dr, dc = DIRECTIONS[key]
        nxt = (here[0] + dr, here[1] + dc)
        turns = len(board.rotations & seen)
        if (not board.contains(nxt) or nxt in board.blocked or nxt in seen
                or not board.allows(here, nxt, turns)):
            raise ValueError("action violates grid geometry or directional rules")
        if nxt == board.end and not board.targets <= seen | {nxt}:
            raise ValueError("action reaches end before collecting targets")
        if (board.ordered_targets and nxt in board.targets
                and nxt != board.ordered_targets[len(board.targets & seen)]):
            raise ValueError("action violates target order")
        route.append(nxt)
        seen.add(nxt)
        if nxt in board.teleports:
            destination = board.teleports[nxt]
            if destination in seen:
                raise ValueError("teleport revisits a cell")
            route.append(destination)
            board.validate(route)
            return route
        if nxt not in board.forced:
            board.validate(route)
            return route
        key = board.forced[nxt]
    raise ValueError("automatic movement budget exhausted")
