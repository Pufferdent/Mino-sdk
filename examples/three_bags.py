"""Chance of walking three drawn boards, keeping S2 back-to-back throughout.

Each line is one bag of play. Hold is modelled properly (the queue's front two
pieces are the playable ones), and every line clear must be back-to-back
eligible or the route is rejected.
"""

from mino_sdk.opener import Bridge, KeepB2B, Node

BOARDS = [
    "v115@vhAAgH",                                                    # empty
    "v115@zgh0EewwBeg0Eeywwhg0AtEehlwhBtR4BeRpglwhAtR4CeRpglwhJeAgH",  # bag 1
    "v115@pgB8GeD8BeH8CeF8EeD8EeF8BeF8JeAgH",                          # bag 2
    "v115@fgA8IeA8IeC8FeD8CeF8DeG8BeH8CeD8JeAgH",                      # bag 3
]

nodes = [Node(f, ()) for f in BOARDS]          # colour is normalised away here
running = 1.0
for i, (start, end) in enumerate(zip(nodes, nodes[1:]), 1):
    bridge = Bridge(start, end, pieces=7, constraints=(KeepB2B(),))
    hits, total = bridge.odds()
    running *= hits / total
    print(f"bag {i}: clears={bridge.cleared_lines}  "
          f"{hits}/{total} = {hits / total:7.2%}   running {running:7.2%}")
