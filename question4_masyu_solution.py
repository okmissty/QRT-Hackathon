#!/bin/python3
import os
import random
import sys
import time


#
# Complete the 'solve' function below.
#
# The function is expected to return a STRING_ARRAY.
# The function accepts STRING_ARRAY grid as parameter.
#


def solve(grid):
   rows, cols = len(grid), len(grid[0])
   stride = cols + 2
   board = '#' * stride + ''.join('#' + row + '#' for row in grid) + '#' * stride


   north, east, south, west = -stride, 1, stride, -1
   directions = (north, east, south, west)
   shapes = {
       frozenset((north, east)): 'L',
       frozenset((north, west)): 'J',
       frozenset((south, east)): 'F',
       frozenset((south, west)): '7',
       frozenset((east, west)): '-',
       frozenset((north, south)): '|',
   }


   pearls = {p for p, cell in enumerate(board) if cell in 'BW'}


   def distance(a, b):
       return abs(a // stride - b // stride) + abs(a % stride - b % stride)


   def starting_directions(p):
       if board[p] == 'B':
           return [
               d for d in directions
               if board[p + d] not in '#B' and board[p + 2 * d] != '#'
           ]
       return [
           d for d in directions
           if board[p + d] != '#' and board[p - d] != '#'
       ]


   order = sorted(
       pearls,
       key=lambda p: (len(starting_directions(p)), board[p] != 'B', p),
   )
   start = order[0]
   home = {p: distance(p, start) for p in pearls}
   remaining = pearls - {start}
   path = [start]
   visited = {start}
   best = None


   begin = time.monotonic()
   deadline = begin + 9.15
   calls = 0
   sys.setrecursionlimit(max(sys.getrecursionlimit(), rows * cols + 100))


   top = min(p // stride for p in pearls)
   bottom = max(p // stride for p in pearls)
   left = min(p % stride for p in pearls)
   right = max(p % stride for p in pearls)


   min_height = max(1, bottom - top)
   min_width = max(1, right - left)
   lower = max(2 * (min_height + min_width), 2 * max(home.values()), len(pearls))
   lower += lower % 2


   def valid_loop(loop):
       size = len(loop)
       turns = [
           loop[i - 1] + loop[(i + 1) % size] != 2 * p
           for i, p in enumerate(loop)
       ]
       for i, p in enumerate(loop):
           previous_turn = turns[i - 1]
           next_turn = turns[(i + 1) % size]
           if board[p] == 'B' and (not turns[i] or previous_turn or next_turn):
               return False
           if board[p] == 'W' and (turns[i] or not (previous_turn or next_turn)):
               return False
       return True


   # Try a few rectangles to get a cheap first solution.
   for a in range(top, max(0, top - 3), -1):
       for b in range(bottom, min(rows, bottom + 2) + 1):
           for x in range(left, max(0, left - 3), -1):
               for y in range(right, min(cols, right + 2) + 1):
                   size = 2 * (b - a + y - x)
                   if a == b or x == y or (best and size >= len(best)):
                       continue
                   perimeter = (
                       [a * stride + c for c in range(x, y)]
                       + [r * stride + y for r in range(a, b)]
                       + [b * stride + c for c in range(y, x, -1)]
                       + [r * stride + x for r in range(b, a, -1)]
                   )
                   if pearls.issubset(perimeter) and valid_loop(perimeter):
                       best = perimeter


   class Found(Exception):
       pass


   class Budget(Exception):
       pass


   found = None
   node_cap = float('inf')
   rng = random.Random(0x5EED)
   noise = False


   def search(limit):
       nonlocal found, calls
       calls += 1
       if calls % 16 == 0:
           if time.monotonic() >= deadline:
               raise TimeoutError
           if calls >= node_cap:
               raise Budget


       p = path[-1]
       used = len(path) - 1
       slack = limit - used


       # Prune any path that cannot close within the current length limit.
       if max(distance(p, start), len(remaining) + 1) > slack:
           return
       far, far_q = 0, None
       for q in remaining:
           b = distance(p, q) + home[q]
           if b > far:
               far, far_q = b, q
       if far > slack:
           return
       if far_q is not None:
           # Pair bound: both pearls must be visited, in one order or the other.
           d1, h1 = distance(p, far_q), home[far_q]
           for r in remaining:
               if r == far_q:
                   continue
               d2 = distance(far_q, r)
               if min(d1 + d2 + home[r], distance(p, r) + d2 + h1) > slack:
                   return


       previous = path[-2] if used else None
       choices = directions if used else starting_directions(start)
       candidates = []


       for d in choices:
           q = p + d
           if board[q] == '#' or (q in visited and q != start):
               continue


           if used:
               turn = d != p - previous
               if board[p] == 'W' and turn:
                   continue
               if board[p] == 'B' and not turn:
                   continue
               if turn and (board[previous] == 'B' or board[q] == 'B'):
                   continue


               # A white pearl needs a turn on at least one side.
               if used >= 3 and board[previous] == 'W' and not turn:
                   straight_before_white = path[-4] + previous == 2 * path[-3]
                   if straight_before_white:
                       continue


           if q == start:
               if used >= 3 and not remaining and valid_loop(path):
                   found = path.copy()
                   raise Found
               continue


           nearest = min(
               (distance(q, pearl) for pearl in remaining),
               default=distance(q, start),
           )
           candidates.append((nearest, rng.random() if noise else 0, q))


       for _, _, q in sorted(candidates):
           is_pearl = q in remaining
           if is_pearl:
               remaining.remove(q)
           visited.add(q)
           path.append(q)


           search(limit)


           path.pop()
           visited.remove(q)
           if is_pearl:
               remaining.add(q)


   def reset():
       path[:] = [start]
       visited.clear()
       visited.add(start)
       remaining.clear()
       remaining.update(pearls - {start})


   def set_start(s):
       # A loop passes through every pearl, so any pearl works as the start
       # and infeasibility proofs carry over between starts.
       nonlocal start, home
       start = s
       home = {p: distance(p, s) for p in pearls}
       reset()


   timed_out = False
   proven = lower - 2
   if not best or len(best) > lower:
       cap = min(rows * cols - rows * cols % 2, lower + 2 * (rows + cols))


       # Phase 1 (feasibility): find any loop.  Try a ladder of coarse length
       # limits (tight to loose) per start pearl, rotating starts and
       # randomizing move order between budgeted restarts.  Exhausting a
       # limit proves no loop of that length or less exists.
       if not best:
           deadline = begin + 9.1
           fb_budget = 50_000
           attempt = 0
           try:
               while True:
                   set_start(order[attempt % len(order)])
                   span = cap - proven
                   tiers = sorted(
                       {proven + (span * i // 4) // 2 * 2 for i in range(1, 5)}
                       | {cap}
                   )
                   for limit in tiers:
                       if limit <= proven:
                           continue
                       reset()
                       node_cap = calls + fb_budget
                       try:
                           search(limit)
                           proven = limit  # exhausted: infeasible
                       except Budget:
                           pass
                   if proven >= cap:
                       if cap >= rows * cols - 1:
                           break  # no loop at all (cannot happen)
                       cap = rows * cols - rows * cols % 2
                   attempt += 1
                   noise = True
                   if attempt % len(order) == 0:
                       fb_budget += fb_budget // 2
           except Found:
               best = found
           except TimeoutError:
               timed_out = True


       # Phase 2 (improvement): iterative deepening with a node budget per
       # length limit.  Limits that cannot be exhausted cheaply are skipped
       # and retried with a larger budget (and a different start pearl) on
       # the next sweep.  Once `proven == len(best) - 2`, best is optimal.
       now = time.monotonic()
       deadline = (begin + 0.9) if now < begin + 0.3 else min(begin + 8.8, now + 2.0)
       budget = 20_000
       sweep = 0
       noise = False
       try:
           while best and proven < len(best) - 2:
               set_start(order[sweep % len(order)])
               improved = False
               limit = proven + 2
               while limit <= len(best) - 2:
                   reset()
                   node_cap = calls + budget
                   try:
                       search(limit)
                       proven = limit  # exhausted: infeasible
                   except Budget:
                       pass
                   except Found:
                       best = found
                       improved = True
                       break
                   limit += 2
               if not improved:
                   sweep += 1
                   budget *= 2
                   noise = True
       except TimeoutError:
           timed_out = True


   print(
       f"grid={rows}x{cols}, pearls={len(pearls)}, "
       f"timed_out={timed_out}, best_length={len(best) if best else 0}, "
       f"search_calls={calls}, elapsed={time.monotonic() - begin:.2f}s",
       file=sys.stderr,
   )


   output = [list('.' * cols) for _ in grid]
   if best:
       for i, p in enumerate(best):
           before = best[i - 1] - p
           after = best[(i + 1) % len(best)] - p
           output[p // stride - 1][p % stride - 1] = shapes[frozenset((before, after))]


   return [''.join(row) for row in output]


if __name__ == '__main__':
   fptr = open(os.environ['OUTPUT_PATH'], 'w')


   grid_count = int(input().strip())


   grid = []


   for _ in range(grid_count):
       grid_item = input()
       grid.append(grid_item)


   result = solve(grid)


   fptr.write('\n'.join(result))
   fptr.write('\n')


   fptr.close()
