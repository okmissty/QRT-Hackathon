#!/bin/python3

import os
import random
import time
from bisect import bisect_right


#
# Complete the 'pack_squares' function below.
#
# The function is expected to return a 2D_INTEGER_ARRAY.
# The function accepts INTEGER_ARRAY squares as parameter.
#

def _pack(sorted_items, W, policy, limit, rnd=None, p=0.0):
    # sorted_items is sorted by square side length:
    #   [(side_length, original_input_index), ...]
    #
    # keys stores just the side lengths so bisect_right can quickly find the
    # largest remaining square that fits in a skyline gap.
    keys = [s for s, _ in sorted_items]
    items = list(sorted_items)

    # Skyline segments. Each segment is:
    #   [y_start, segment_width, filled_height]
    #
    # x increases downward and y increases to the right. A segment says that
    # from y_start to y_start + segment_width, the current packed height is
    # filled_height.
    segs = [[0, W, 0]]
    out = []
    H = 0

    while items:
        # Find the lowest skyline segment. This is the gap we try to fill next.
        bi = 0
        bh = segs[0][2]
        for i in range(1, len(segs)):
            if segs[i][2] < bh:
                bh = segs[i][2]
                bi = i

        y, g, h = segs[bi]

        # k is the number of remaining squares with side length <= gap width.
        k = bisect_right(keys, g)

        if k == 0:  # nothing fits: raise gap to lower neighbour
            lh = segs[bi - 1][2] if bi > 0 else 1 << 60
            rh = segs[bi + 1][2] if bi + 1 < len(segs) else 1 << 60
            if lh <= rh:
                segs[bi - 1][1] += g
                del segs[bi]
                if lh == rh:
                    segs[bi - 1][1] += segs[bi][1]
                    del segs[bi]
            else:
                segs[bi + 1][0] = y
                segs[bi + 1][1] += g
                del segs[bi]
            continue

        # Greedy default: choose the largest square that fits the gap.
        j = k - 1

        # For policies 2 and 3, look for two squares that exactly fill the gap.
        # If found, place the larger one now; this leaves an exact leftover gap
        # for the smaller one, which often reduces wasted area.
        if policy >= 2 and keys[j] != g and j > 0:
            lo = 0
            hi = j
            while lo < hi:
                t = keys[lo] + keys[hi]
                if t == g:
                    j = hi
                    break
                if t < g:
                    lo += 1
                else:
                    hi -= 1

        # During the randomized phase, sometimes choose a different square that
        # still fits. The seed in pack_squares makes this reproducible.
        if rnd is not None and rnd.random() < p:
            j = rnd.randint(0, k - 1) if rnd.random() < 0.3 else rnd.randint(max(0, k - 4), k - 1)

        s, idx = items[j]
        del items[j]
        del keys[j]

        lh = segs[bi - 1][2] if bi > 0 else 1 << 60
        rh = segs[bi + 1][2] if bi + 1 < len(segs) else 1 << 60

        # Decide whether to place the square against the left or right edge of
        # the current gap. Different policies explore different alignments.
        left = True
        if policy % 2 == 1 and rh > lh:
            left = False
        if rnd is not None and rnd.random() < p:
            left = not left

        nh = h + s
        if nh > H:
            H = nh
            if H * W >= limit:
                return None

        if s == g:
            # The square exactly fills the gap width.
            out.append((idx, h, y))
            segs[bi][2] = nh
            if bi + 1 < len(segs) and segs[bi + 1][2] == nh:
                segs[bi][1] += segs[bi + 1][1]
                del segs[bi + 1]
            if bi > 0 and segs[bi - 1][2] == nh:
                segs[bi - 1][1] += segs[bi][1]
                del segs[bi]

        elif left:
            # Place on the left side of the gap and leave the unused part to
            # the right at the old height.
            out.append((idx, h, y))
            if bi > 0 and segs[bi - 1][2] == nh:
                segs[bi - 1][1] += s
                segs[bi][0] = y + s
                segs[bi][1] = g - s
            else:
                segs[bi][0] = y + s
                segs[bi][1] = g - s
                segs.insert(bi, [y, s, nh])

        else:
            # Place on the right side of the gap and leave the unused part to
            # the left at the old height.
            out.append((idx, h, y + g - s))
            segs[bi][1] = g - s
            if bi + 1 < len(segs) and segs[bi + 1][2] == nh:
                segs[bi + 1][0] = y + g - s
                segs[bi + 1][1] += s
            else:
                segs.insert(bi + 1, [y + g - s, s, nh])

    return H, out


def pack_squares(squares):
    BUDGET = 2.5  # seconds; lower this if you hit the time limit
    t0 = time.time()
    n = len(squares)
    if n == 0:
        return []

    # m is the largest side, S is the total square area, and total is the sum
    # of side lengths. total is a guaranteed upper bound for a strip width.
    m = max(squares)
    S = sum(s * s for s in squares)
    total = sum(squares)
    items = sorted((s, i) for i, s in enumerate(squares))
    best = [m * total + 1, None]

    # Candidate widths are sorted by their theoretical lower-bound area:
    #   width * max(largest_side, ceil(total_area / width))
    cands = []
    L = None
    W = m
    while W <= total:
        hb = max(m, -(-S // W))
        lb = W * hb
        if L is None or lb < L:
            L = lb
        cands.append((lb, W))
        if hb == m and lb > 2 * L:
            break
        W += 1
    cands.sort()

    # Deterministic pass over four policies. If we reach the lower bound L,
    # this test case cannot be improved according to the scorer's bound.
    done = False
    for pol in (3, 2, 1, 0):
        for lb, W in cands:
            if lb >= best[0]:
                break
            r = _pack(items, W, pol, best[0])
            if r and W * r[0] < best[0]:
                best[0] = W * r[0]
                best[1] = r[1]
            if best[0] == L or time.time() - t0 > BUDGET:
                done = True
                break
        if done:
            break

    # Randomized pass. The fixed seed keeps the result deterministic while
    # still exploring some non-greedy choices.
    rnd = random.Random(12345)
    while best[0] > L and time.time() - t0 < BUDGET:
        live = [W for lb, W in cands if lb < best[0]]
        if not live:
            break
        for W in live:
            r = _pack(items, W, rnd.randint(0, 3), best[0], rnd, rnd.choice((0.03, 0.1, 0.25)))
            if r and W * r[0] < best[0]:
                best[0] = W * r[0]
                best[1] = r[1]
            if time.time() - t0 > BUDGET:
                break

    res = [None] * n
    for idx, x, y in best[1]:
        res[idx] = [x, y]
    return res


if __name__ == '__main__':
    fptr = open(os.environ['OUTPUT_PATH'], 'w')

    squares_count = int(input().strip())

    squares = []

    for _ in range(squares_count):
        squares_item = int(input().strip())
        squares.append(squares_item)

    result = pack_squares(squares)

    fptr.write('\n'.join([' '.join(map(str, x)) for x in result]))
    fptr.write('\n')

    fptr.close()
