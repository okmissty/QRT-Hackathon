# QRT Hackathon

This repository archives our team submissions for the CompSoc x QRT two-hour
coding competition, run in partnership with OpenAI. The challenges were a mix
of optimisation, logic, search, and heuristic reconstruction problems designed
by QRT with help from an LLM.

Team: **Math is Fun**

## Solution Files

| Challenge | File | Language | Entry Point |
| --- | --- | --- | --- |
| Question 1: Square Packing++ | `question1_solution.py` | Python 3 | `pack_squares(squares)` |
| Question 2: Word Search Generation | `question2_word_search_solution.cpp` | C++17 | `generate_grid(required_words, forbidden_words)` |
| Question 3: Black Box | `question3_black_box_solution.py` | Python 3 | `probe(t)` |
| Question 4: Masyu | `question4_masyu_solution.py` | Python 3 | `solve(grid)` |
| Bonus: Document Lego | `bonus_document_lego_solution.py` | Python 3 | `assemble(pieces)` |

## Notes

- The files keep the HackerRank-style wrappers used during the competition.
- Python solutions write to `OUTPUT_PATH` when run through the platform.
- Question 2 is included as the recovered C++ solution from the shared team
  document.
- Explanation text files and generated artifacts have been removed so the repo
  stays focused on the final source submissions.

## Local Checks

```bash
python -m py_compile question1_solution.py question3_black_box_solution.py question4_masyu_solution.py bonus_document_lego_solution.py
```

When a C++ compiler is available:

```bash
g++ -std=c++17 -O2 -Wall -Wextra -pedantic question2_word_search_solution.cpp -o question2_word_search_solution
```
