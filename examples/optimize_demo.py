"""The diagram optimizer, minimally: score = lines sent * 0.8 + B2B clears * 1.

Three drawn boards a bag apart, with a fork: from the first stack the player
may build toward the drawn second board or its mirror, and each continues to
its own third board. You write one function saying what a route is worth; the
optimizer attributes every queue to the best playable way through and reports
the expected score under optimal play.

Run:  PYTHONPATH=. .venv/bin/python examples/optimize_demo.py
"""

from tetris_sdk.opener import Diagram, Node

BOARDS = {
    "start": "v115@vhAAgH",
    "bag1":  "v115@zgh0EewwBeg0Eeywwhg0AtEehlwhBtR4BeRpglwhAtR4CeRpglwhJeAgH",
    "bag2":  "v115@pgB8GeD8BeH8CeF8EeD8EeF8BeF8JeAgH",
    "bag3":  "v115@fgA8IeA8IeC8FeD8CeF8DeG8BeH8CeD8JeAgH",
}


def score(route):
    """The whole SPI: lines sent * 0.8 + B2B clears * 1.    """
    return route.attack() * 0.8 + route.b2b() * 1.0


d = Diagram()
start, bag1, bag2, bag3 = (Node(BOARDS[k], ()) for k in BOARDS)
bag1m, bag2m, bag3m = bag1.mirrored(), bag2.mirrored(), bag3.mirrored()

d.line(start, bag1)           # the fork: open with the drawn first board...
d.line(start, bag1m)          # ...or its mirror, whichever the queue favors
d.line(bag1, bag2)
d.line(bag2, bag3)
d.line(bag1m, bag2m)
d.line(bag2m, bag3m)

value = d.optimize(start, score)
print(f"expected score, playing optimally: {value:.3f}\n")

names = {start: "start", bag1: "bag1", bag1m: "bag1'", bag2: "bag2",
         bag2m: "bag2'", bag3: "bag3", bag3m: "bag3'"}
for (node, leftover), (worth, choices) in d.explain(start, score).items():
    print(f"{names[node]:6} (leftover {leftover or '-'}):  value {worth:.3f}")
    for c in choices:
        print(f"    -> {names[c.line.end]:6}  score {c.score:4.1f}  "
              f"saves {c.saved or '-'}  playable {c.playable}/{c.total}  "
              f"future {c.future:.3f}")
