HEX_DIRECTIONS = [
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
]


def hex_neighbors(q, r):
    for dq, dr in HEX_DIRECTIONS:
        yield q + dq, r + dr


def hex_distance(aq, ar, bq, br):
    return (
        abs(aq - bq)
        + abs(aq + ar - bq - br)
        + abs(ar - br)
    ) // 2