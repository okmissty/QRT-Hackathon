#!/bin/python3
"""Heuristic Document Lego solver; assemble(encoded_pieces) returns integer rows.


Run: python3 bonus_document_lego_solution.py < input.txt
Uses only the standard library, with a small built-in vocabulary supplemented
by explicitly bounded words in the input. No external dictionary is assumed.
Horizontal word seams drive a beam search; local moves and component merges
repair layouts. Vertical joins require line-wrap evidence, not just geometry.
Unresolved fragments remain separate pages rather than forced into a layout.
This is a partial-credit heuristic, not an exact solver or a noise classifier.


SEARCH_SECONDS bounds search effort (not parsing/output). Increase it if the
judge permits more time. The input's true page count is never assumed.
"""


from __future__ import annotations


import heapq
import math
import os
import random
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass




SEARCH_SECONDS = 8.0
BEAM_WIDTH = 5
NEIGHBORS = 12
MAX_WIDTH = 60
MAX_HEIGHT = 14
WORD = re.compile(r"[a-z]+(?:'[a-z]+)*")
TAIL = re.compile(r"[a-z']+$")
HEAD = re.compile(r"^[a-z']+")


# A deliberately small, self-contained vocabulary, not a downloaded corpus.
COMMON_WORDS = frozenset("""
a about above across act action after again against age ago air all almost
alone along already also although always am among an and animal animals another
answer any anyone anything appear are area around art as ask asked at away
back bad ball base be became because become bed been before began begin behind
being believe below best better between big bird birds black blue board body
book books both box boy bring brought build building built business but buy by
call called came can cannot car care carry case cat cause center century certain
change changed children city class clear close cold color come common company
complete condition consider contain continue control could country course cut
dark day days deep develop did different direction do does dog doing done door
down draw drive during each early earth east easy eat education effect eight
either end energy enough even ever every everyone everything example experience
explain eye eyes face fact family far farm fast father feel feet few field
figure fill final find fine fire first fish five floor follow food foot for
force form found four free friend friends from front full game gave general
get girl give given go goes going gold good got government great green ground
group grow had half hand hands happen hard has have having he head hear heard
heart heat heavy help her here high him himself his history hold home hope
horse hot hour house how however human hundred i idea if important in include
information inside instead interest into is issue it its itself job join just
keep kind knew know known land language large last late later law lay lead
learn least leave left less let letter life light like line list little live
lived local long look looked lot love low machine made main make man many map
mark matter may me mean means measure men might mile million mind minute miss
model modern moment money month more morning most mother move movement much
music must my name named nation natural near nearly necessary need never new
next night no north not nothing now number object of off offer office often
old on once one only open or order other others our out outside over own page
paper part particular pass past pattern pay people per perhaps person picture
piece pieces place plan plant play point possible power present problem process
produce provide public pull purpose put question quite rain ran range rather
reach read ready real reason receive record red remain remember report require
research rest result return right river road rock room round rule run said same
saw say school science sea second see seem seen self sense sentence set several
shall shape she short should show side since simple simply small so social
some someone something sometimes son song soon sound south space speak special
speed spend stand start state stay step still stop story street strong student
study such sun support sure system table take taken talk teach team tell ten
term test text than that the their them themselves then there these they thing
things think third this those though thought thousand three through time times
to today together told too took top toward town tree trees true try turn turned
two type under understand until up upon us use used using usually value very
view voice wait walk want war warm was watch water way we week well went were
west what when where whether which while white who whole whom whose why wide
will wind window wish with within without woman women word words work working
world would write written wrong year years yes yet you young your yourself
able ability available beautiful beginning bicycle bicycles boat boats border
borders bottom bridge broken brown carefully character characters child circle
computer create created design developed discovery document documents engine
english especially event factory famous finally flight flower flowers forest
glass history industry invented invention journey king knowledge later library
longer material materials metal method middle mountain mountains museum narrow
nearly ocean original painted painting parents parts passenger passengers
pattern patterns pedal pedals period personal photograph planet plastic
popular position printed printing probably puzzle puzzles railway rectangle
rectangular road roads sail sailing sat scientist scientists ship ships slowly
sold space station steam stone straight structure surface technology television
themselves train travel traveled travelling unit units useful village wheel
wheels width wood wooden worker workers writing yellow yesterday
don't can't isn't wasn't aren't weren't it's that's there's i'm you're we're
they're i've you've we've they've didn't doesn't couldn't wouldn't shouldn't
""".split())


Layout = dict[int, tuple[int, int]]




@dataclass(frozen=True)
class Piece:
   rows: tuple[str, ...]


   @property
   def width(self) -> int:
       return len(self.rows[0])


   @property
   def height(self) -> int:
       return len(self.rows)




@dataclass(frozen=True)
class LineEvidence:
   value: float = 0.0
   hit: int = 0
   bounded: int = 0
   long_word: int = 0




@dataclass(frozen=True)
class Seam:
   value: float
   hits: int
   bounded: int
   long_word: int


   @property
   def tier(self) -> int:
       if self.hits >= 2:
           return 3
       if self.long_word:
           return 2
       return 1 if self.bounded else 0


   @property
   def score(self) -> float:
       return self.value + 8 * max(0, self.hits - 1) + self.long_word / 2




def combine(lines: list[LineEvidence]) -> Seam:
   return Seam(
       sum(line.value for line in lines),
       sum(line.hit for line in lines),
       sum(line.bounded for line in lines),
       max((line.long_word for line in lines), default=0),
   )




class Language:
   def __init__(self, pieces: list[Piece]) -> None:
       words = set(COMMON_WORDS)
       for piece in pieces:
           for row in piece.rows:
               for match in WORD.finditer(row.lower()):
                   # A cut edge does not establish a word boundary.
                   if 0 < match.start() and match.end() < len(row):
                       words.add(match.group())
       self.words = words
       self.fragments = {
           word[start:end]
           for word in words
           for start in range(len(word))
           for end in range(start + 2, len(word) + 1)
       }
       self.trigrams = {
           word[start:start + 3]
           for word in words for start in range(len(word) - 2)
       }
       self.cache: dict[tuple[str, str], LineEvidence] = {}


   def line(self, left: str, right: str) -> LineEvidence:
       left, right = left[-24:].lower(), right[:24].lower()
       key = left, right
       if key in self.cache:
           return self.cache[key]
       evidence = self._line(left, right)
       if len(self.cache) < 50000:
           self.cache[key] = evidence
       return evidence


   def _line(self, left: str, right: str) -> LineEvidence:
       tail, head = TAIL.search(left), HEAD.match(right)
       if tail is None or head is None:
           # Whitespace or punctuation alone is not evidence of adjacency.
           if left and right and left[-1] in ",;:!?" and right[0].isalpha():
               return LineEvidence(-0.5)
           return LineEvidence()
       word = tail.group() + head.group()
       bounded = tail.start() > 0 and head.end() < len(right)
       length = len(word)
       if word in self.words:
           if bounded:
               return LineEvidence(4 + min(length, 12), 1, 1,
                                   min(length, 12) if length >= 6 else 0)
           if length >= 4:
               return LineEvidence(1 + min(length, 12) / 2, 1)
           return LineEvidence(0.15)
       if not bounded and word in self.fragments:
           return LineEvidence(0.1 + 0.06 * min(length, 8))
       # Only n-grams crossing the new seam contribute.
       split = len(tail.group())
       grams = [word[i:i + 3]
                for i in range(max(0, split - 2), min(split, length - 2))]
       missing = sum(gram not in self.trigrams for gram in grams)
       penalty = 0.4 * missing / max(1, len(grams))
       return LineEvidence(-penalty - (1.0 if bounded else 0.1))




@dataclass(frozen=True)
class Candidate:
   left: int
   right: int
   dy: int
   seam: Seam
   ambiguity: int = 0


   @property
   def rank(self) -> tuple[int, float, float]:
       return (self.seam.tier,
               self.seam.score / (1 + math.log2(1 + self.ambiguity)),
               self.seam.score)




def candidates(pieces: list[Piece], language: Language,
              deadline: float) -> list[Candidate]:
   heaps: list[list[tuple[tuple[int, float, float], int, Candidate]]] = [
       [] for _ in range(2 * len(pieces))
   ]
   order = list(range(len(pieces)))
   random.Random(0).shuffle(order)
   serial = 0
   for left in order:
       if time.monotonic() >= deadline:
           break
       a = pieces[left]
       for right in order:
           if time.monotonic() >= deadline:
               break
           b = pieces[right]
           if left == right or a.width + b.width > MAX_WIDTH:
               continue
           offsets: dict[int, list[LineEvidence]] = defaultdict(list)
           for ar, arow in enumerate(a.rows):
               for br, brow in enumerate(b.rows):
                   offsets[ar - br].append(language.line(arow, brow))
           for dy, lines in offsets.items():
               if max(a.height, dy + b.height) - min(0, dy) > MAX_HEIGHT:
                   continue
               seam = combine(lines)
               if seam.score < 0.5:
                   continue
               edge = Candidate(left, right, dy, seam)
               entry = edge.rank, serial, edge
               serial += 1
               for bucket in (heaps[left], heaps[len(pieces) + right]):
                   if len(bucket) < NEIGHBORS:
                       heapq.heappush(bucket, entry)
                   elif entry[:2] > bucket[0][:2]:
                       heapq.heapreplace(bucket, entry)
   unique = {
       (edge.left, edge.right, edge.dy): edge
       for bucket in heaps for _, _, edge in bucket
   }
   sides: dict[tuple[int, bool], list[Candidate]] = defaultdict(list)
   for edge in unique.values():
       sides[edge.left, True].append(edge)
       sides[edge.right, False].append(edge)
   result = []
   for edge in unique.values():
       rivals = 0
       for left_side in (True, False):
           anchor = edge.left if left_side else edge.right
           offset = edge.dy if left_side else -edge.dy
           neighbor = edge.right if left_side else edge.left
           low, high = max(0, offset), min(
               pieces[anchor].height, offset + pieces[neighbor].height)
           count = 0
           for other in sides[anchor, left_side]:
               if other == edge or other.seam.tier != edge.seam.tier:
                   continue
               off = other.dy if left_side else -other.dy
               nbr = other.right if left_side else other.left
               if (max(low, off) < min(high, off + pieces[nbr].height)
                       and other.seam.score >= edge.seam.score * 0.9):
                   count += 1
           rivals = max(rivals, count)
       result.append(Candidate(edge.left, edge.right, edge.dy,
                               edge.seam, rivals))
   return sorted(result, key=lambda edge: edge.rank, reverse=True)




def bounds(layout: Layout, pieces: list[Piece]) -> tuple[int, int, int, int]:
   return (
       min(row for row, _ in layout.values()),
       min(col for _, col in layout.values()),
       max(row + pieces[i].height for i, (row, _) in layout.items()),
       max(col + pieces[i].width for i, (_, col) in layout.items()),
   )




def valid(layout: Layout, pieces: list[Piece]) -> bool:
   if not layout:
       return True
   top, left, bottom, right = bounds(layout, pieces)
   if bottom - top > MAX_HEIGHT or right - left > MAX_WIDTH:
       return False
   occupied: dict[int, int] = {}
   for i, (row, col) in layout.items():
       mask = ((1 << pieces[i].width) - 1) << (col - left)
       for r in range(row, row + pieces[i].height):
           if occupied.get(r, 0) & mask:
               return False
           occupied[r] = occupied.get(r, 0) | mask
   return True




def normalize(layout: Layout) -> Layout:
   if not layout:
       return {}
   top = min(row for row, _ in layout.values())
   left = min(col for _, col in layout.values())
   return {i: (row - top, col - left) for i, (row, col) in layout.items()}




def layout_score(layout: Layout, pieces: list[Piece],
                language: Language) -> float:
   grid: dict[int, dict[int, tuple[str, int]]] = defaultdict(dict)
   for i, (row, col) in layout.items():
       for dr, text in enumerate(pieces[i].rows):
           for dc, char in enumerate(text):
               grid[row + dr][col + dc] = char, i
   seams: dict[tuple[int, int], list[LineEvidence]] = defaultdict(list)
   full_rows: dict[int, str] = {}
   for row, cells in grid.items():
       columns = sorted(cells)
       start = 0
       while start < len(columns):
           end = start + 1
           while end < len(columns) and columns[end] == columns[end - 1] + 1:
               end += 1
           run = columns[start:end]
           text = ''.join(cells[col][0] for col in run)
           for k in range(1, len(run)):
               a, b = cells[run[k - 1]][1], cells[run[k]][1]
               if a != b:
                   seams[a, b].append(language.line(text[:k], text[k:]))
           start = end
       if columns[-1] - columns[0] + 1 == len(columns):
           full_rows[row] = ''.join(cells[col][0] for col in columns)
   score = sum(combine(lines).score for lines in seams.values())
   if not layout:
       return score
   _, left, _, right = bounds(layout, pieces)
   if 40 <= right - left <= MAX_WIDTH:
       for row, text in full_rows.items():
           following = full_rows.get(row + 1, "")
           # A guessed piece edge is not a page line ending. Require two
           # complete rows spanning a feasible page width before unhyphenating.
           if (len(text) == right - left == len(following)
                   and text.endswith("-")):
               a, b = grid[row][right - 1][1], grid[row + 1][left][1]
               if a != b:
                   score += language.line(text[:-1], following).value
   return score




def attach(edge: Candidate, anchor: int, position: tuple[int, int],
          pieces: list[Piece]) -> tuple[int, tuple[int, int]]:
   row, col = position
   if anchor == edge.left:
       return edge.right, (row + edge.dy, col + pieces[anchor].width)
   return edge.left, (row - edge.dy, col - pieces[edge.left].width)




def grow(seed: Candidate, available: set[int], pieces: list[Piece],
        language: Language, adjacency: list[list[Candidate]],
        deadline: float) -> tuple[float, Layout]:
   initial = {seed.left: (0, 0),
              seed.right: (seed.dy, pieces[seed.left].width)}
   beam = [(layout_score(initial, pieces, language), initial)]
   best = beam[0]
   while time.monotonic() < deadline:
       expanded: dict[tuple[tuple[int, tuple[int, int]], ...],
                      tuple[float, Layout]] = {}
       for score, layout in beam:
           proposals: set[tuple[int, tuple[int, int]]] = set()
           for anchor, position in layout.items():
               for edge in adjacency[anchor]:
                   i, pos = attach(edge, anchor, position, pieces)
                   if i in available and i not in layout:
                       proposals.add((i, pos))
           for i, pos in sorted(proposals):
               if time.monotonic() >= deadline:
                   break
               updated = dict(layout)
               updated[i] = pos
               if not valid(updated, pieces):
                   continue
               value = layout_score(updated, pieces, language)
               if value < score + 1.0:
                   continue
               updated = normalize(updated)
               key = tuple(sorted(updated.items()))
               expanded[key] = value, updated
       if not expanded:
           break
       beam = sorted(expanded.values(), key=lambda item: item[0],
                     reverse=True)[:BEAM_WIDTH]
       if beam[0][0] > best[0]:
           best = beam[0]
   return best




def improve(groups: list[Layout], edges: list[Candidate], pieces: list[Piece],
           language: Language, deadline: float) -> list[Layout]:
   scores = [layout_score(group, pieces, language) for group in groups]
   # Revisit whole-component joins, including supported vertical line wraps.
   while time.monotonic() < deadline:
       owner = {i: g for g, group in enumerate(groups) for i in group}
       proposals: set[tuple[int, int, int, int]] = set()
       for edge in edges:
           a, b = owner[edge.left], owner[edge.right]
           if a == b:
               continue
           _, target = attach(edge, edge.left, groups[a][edge.left], pieces)
           row, col = groups[b][edge.right]
           proposals.add((a, b, target[0] - row, target[1] - col))
       extents = [bounds(group, pieces) if group else None for group in groups]
       for a, ab in enumerate(extents):
           if ab is None or ab[3] - ab[1] < 40:
               continue
           for b, bb in enumerate(extents):
               if (a != b and bb is not None
                       and ab[3] - ab[1] == bb[3] - bb[1]
                       and ab[2] - ab[0] + bb[2] - bb[0] <= MAX_HEIGHT):
                   proposals.add((a, b, ab[2] - bb[0], ab[1] - bb[1]))
       best_gain, best = 1.0, None
       for a, b, dr, dc in sorted(proposals):
           if time.monotonic() >= deadline:
               break
           merged = dict(groups[a])
           merged.update({i: (r + dr, c + dc)
                          for i, (r, c) in groups[b].items()})
           if not valid(merged, pieces):
               continue
           score = layout_score(merged, pieces, language)
           gain = score - scores[a] - scores[b]
           if gain > best_gain:
               best_gain, best = gain, (a, b, merged, score)
       if best is None:
           break
       a, b, merged, score = best
       groups[a], groups[b] = normalize(merged), {}
       scores[a], scores[b] = score, 0.0


   # Remove and reinsert individual fragments, including into another page.
   for _ in range(2):
       changed = False
       for edge in edges:
           if time.monotonic() >= deadline:
               break
           for anchor in (edge.left, edge.right):
               owner = {i: g for g, group in enumerate(groups) for i in group}
               target_group = owner[anchor]
               i, pos = attach(edge, anchor, groups[target_group][anchor], pieces)
               source_group = owner[i]
               if groups[source_group][i] == pos and source_group == target_group:
                   continue
               source = {j: p for j, p in groups[source_group].items() if j != i}
               target = dict(source if source_group == target_group
                             else groups[target_group])
               target[i] = pos
               if not valid(target, pieces):
                   continue
               target_score = layout_score(target, pieces, language)
               source_score = (0.0 if source_group == target_group
                               else layout_score(source, pieces, language))
               old_score = scores[target_group]
               if source_group != target_group:
                   old_score += scores[source_group]
               if target_score + source_score > old_score + 1.0:
                   if source_group != target_group:
                       groups[source_group] = normalize(source)
                       scores[source_group] = source_score
                   groups[target_group] = normalize(target)
                   scores[target_group] = target_score
                   changed = True
       if not changed:
           break
   return [normalize(group) for group in groups if group]




def parse_pieces(encoded: list[str]) -> list[Piece]:
   result = []
   for i, text in enumerate(encoded):
       rows = tuple(text.replace("_", " ").split("|"))
       if (not rows[0] or any(len(row) != len(rows[0]) for row in rows)
               or any("\n" in row or "\r" in row for row in rows)):
           raise ValueError(f"piece {i} must be a nonempty rectangle")
       if len(rows) > MAX_HEIGHT or len(rows[0]) > MAX_WIDTH:
           raise ValueError(f"piece {i} exceeds the maximum page dimensions")
       result.append(Piece(rows))
   return result




def assemble(pieces: list[str]) -> list[list[int]]:
   """Return [piece, page, row, col] rows; ids follow input order."""
   parsed = parse_pieces(pieces)
   if not parsed:
       return []
   start = time.monotonic()
   deadline = start + SEARCH_SECONDS
   language = Language(parsed)
   edges = candidates(parsed, language, start + SEARCH_SECONDS * 0.4)
   adjacency: list[list[Candidate]] = [[] for _ in parsed]
   for edge in edges:
       adjacency[edge.left].append(edge)
       adjacency[edge.right].append(edge)
   available = set(range(len(parsed)))
   groups: list[Layout] = []
   grow_deadline = start + SEARCH_SECONDS * 0.8
   while time.monotonic() < grow_deadline:
       seeds = [edge for edge in edges if edge.seam.tier > 0
                and edge.left in available and edge.right in available][:3]
       if not seeds:
           break
       best_score, best_layout = -math.inf, {}
       for seed in seeds:
           # Reserve time for other page hypotheses instead of spending the
           # entire budget growing the first page.
           stop = min(grow_deadline, time.monotonic() + 0.15)
           score, layout = grow(seed, available, parsed, language, adjacency, stop)
           confidence = score / (1 + math.log2(1 + seed.ambiguity))
           if confidence > best_score:
               best_score, best_layout = confidence, layout
       groups.append(normalize(best_layout))
       available.difference_update(best_layout)
   groups.extend({i: (0, 0)} for i in sorted(available))
   groups = improve(groups, edges, parsed, language, deadline)
   return [[i, page, row, col]
           for page, group in enumerate(groups)
           for i, (row, col) in sorted(group.items())]




def main() -> None:
   count = int(sys.stdin.readline())
   if count < 0:
       raise ValueError("piece count cannot be negative")
   pieces = []
   for i in range(count):
       line = sys.stdin.readline()
       if not line:
           raise ValueError(f"missing piece {i}")
       pieces.append(line.rstrip("\r\n"))
   if sys.stdin.read().strip():
       raise ValueError("unexpected data after the pieces")
   output = ''.join(' '.join(map(str, row)) + '\n' for row in assemble(pieces))
   path = os.environ.get("OUTPUT_PATH")
   if path:
       with open(path, "w", encoding="utf-8") as stream:
           stream.write(output)
   else:
       sys.stdout.write(output)




if __name__ == '__main__':
   try:
       main()
   except ValueError as error:
       print(f"Invalid input: {error}", file=sys.stderr)
       sys.exit(2)
