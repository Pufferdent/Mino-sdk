from tetris_sdk.pieces import PieceType, get_piece_cells


def compute_topological_orderings(
    operations: list[tuple[PieceType, int, int, int]],
) -> list[list[tuple[PieceType, int, int, int]]]:
    n = len(operations)
    if n <= 1:
        return [list(operations)]

    piece_cells: list[list[tuple[int, int]]] = []
    for ptype, rot, col, row in operations:
        cells = get_piece_cells(ptype, rot, col, row, coord_system="sdk")
        piece_cells.append(cells)

    adj: list[list[int]] = [[] for _ in range(n)]
    indegree: list[int] = [0] * n

    for i in range(n):
        cells_i = piece_cells[i]
        cols_i = {c for _, c in cells_i}
        for j in range(n):
            if i == j:
                continue
            cells_j = piece_cells[j]
            common_cols = cols_i & {c for _, c in cells_j}
            for c in common_cols:
                min_row_i = min(r for r, col_ in cells_i if col_ == c)
                min_row_j = min(r for r, col_ in cells_j if col_ == c)
                if min_row_i < min_row_j:
                    adj[i].append(j)
                    indegree[j] += 1
                    break

    all_orders: list[list[tuple[PieceType, int, int, int]]] = []

    def backtrack(order, visited, indeg):
        if len(order) == n:
            all_orders.append([operations[idx] for idx in order])
            return
        for i in range(n):
            if not visited[i] and indeg[i] == 0:
                visited[i] = True
                order.append(i)
                for nb in adj[i]:
                    indeg[nb] -= 1
                backtrack(order, visited, indeg)
                order.pop()
                visited[i] = False
                for nb in adj[i]:
                    indeg[nb] += 1

    backtrack([], [False] * n, list(indegree))
    if not all_orders:
        all_orders.append(list(operations))
    return all_orders
