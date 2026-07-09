# DIY Task Sequence & Discussion Log

This document serves as a complete record of the remaining tasks and the discussions/fixes we have applied so far.

---

## 1. DIY Task Sequence

Here is the step-by-step guide designed for you to pick up one task at a time, review the code, and implement the fix yourself. 

### 1. Change "Target" and "Reach" to something more appropriate (Task 6)
**What to do:** Decide on new terminology (e.g., "Moderate", "Ambitious").
**Files to edit:**
- `app/disha/recommender.py`: Update the dictionary keys in `CATEGORY_ORDER`, `FIT_LABELS`, `CATEGORY_BLURBS`, and the string returns in `_categorize`.
- `templates/disha_templates/js/app.js`: Search for `"Target"` and `"Reach"` and replace them (especially in `SECTION_ORDER`, `byCat` tracking, and UI strings).
- `templates/disha_templates/js/i18n.js`: Update all translations.
- `templates/disha_templates/index.html`: Update the Welcome screen legend (`.dot--target`, `.dot--reach`).
- `templates/disha_templates/css/style.css`: Update any CSS classes (e.g., `.tone-target`, `.dot--target`) if you decide to change the CSS class names as well.

### 2. Fix logic for "Safe" (Task 5)
*(✅ Completed - See Discussion section below)*

### 3. Fix: Instis for "Reach" and "Safe" not showing (Task 10)
*(✅ Completed - See Discussion section below)*

### 4. Ensure "Whole Picture" sliders show dots on both sides (Task 7)
**What to do:** The rank scale (ruler) sometimes has dots perfectly flush against the edge, making it hard to see. You need to add a mathematical buffer to the minimum and maximum scale values.
**Files to edit:**
- `templates/disha_templates/js/app.js`: Locate the `renderRuler()` or `drawRuler()` logic. Find where `minRank` and `maxRank` are calculated and subtract/add a padding value (e.g., `minRank * 0.8` and `maxRank * 1.2`) so the dots sit comfortably within the line.

### 5. Move the filter below to be just above the college table (Task 8)
**What to do:** Move the filter panel from its current layout position to sit horizontally directly above the college result cards.
**Files to edit:**
- `templates/disha_templates/index.html`: Cut the `<aside class="results-panel">` block and paste it inside the results container just before the `<ul class="college-list">`.
- `templates/disha_templates/css/style.css`: Refactor the CSS grid/flexbox for `.results-layout` and `.results-panel` to ensure it looks good horizontally.

### 6. Add "State" filter separately (Task 9)
**What to do:** Add a standalone state filter for the results page so users can filter recommended colleges by their location.
**Files to edit:**
- `templates/disha_templates/index.html`: Add a new `<select id="filter-state">` inside the `#panel-body` filter panel.
- `templates/disha_templates/js/app.js`: Add an event listener for this dropdown and update the `applyFilters()` logic to hide college cards that don't match the selected state.

### 7. Review the algo and logic for all decisions & Create Flowchart (Tasks 2 & 11)
**What to do:** Sit down and map out exactly how a student's profile translates into a final list of colleges. 
**Files to edit:**
- `app/disha/states.py`: Review `GOAL_TAG_WEIGHTS` and how interests map to specific branches.
- `app/disha/recommender.py`: Review `_interest_score` and `_calculate_probability`.
- Draw out the flowchart using a tool like Whimsical, Excalidraw, or Mermaid.md to present to your superior.

---

## 2. Completed Fixes & Discussions

### Task 5: Fix logic for "Safe"
**Discussion:** The previous logic required a student's rank to be strictly better than the absolute best person who got in last year (`rank <= opening`). This was far too conservative.
**Resolution:** We updated `app/disha/recommender.py` to use a 25% threshold on the opening-closing gap: `safe_threshold = opening + 0.25 * (closing - opening)`. This makes the "Safe" bucket much more realistic and forgiving.

### Task 10: Instis for "Reach" and "Safe" not showing
**Discussion:** It was suspected that the frontend `app.js` was improperly slicing the array. However, the root cause was discovered in the backend (`app/disha/recommender.py`). The code sorted all colleges by category (Target -> Reach -> Safe) and then blindly truncated the list to 60 items (`max_results`). If a student had 100 Target matches, all Reach and Safe matches were completely discarded before reaching the frontend!
**Resolution:** We updated `app/disha/recommender.py` to distribute the `max_results` quota proportionally: up to 25% of slots are reserved for Reach, 25% are reserved for Safe, and the rest for Target. This guarantees a balanced mix.

### Task 7 (Investigation): "Whole Picture" Ruler Logic
We reviewed how `renderRuler()` plots the dots and answered your specific questions:
1. **Which dataset is passed?** It receives `data.recommendations` from the backend API, which is the truncated top-matches list (capped by `max_results`), not every single mathematically eligible college in India.
2. **Is any filtering applied?** No frontend UI filtering (like the State filter) is applied to the ruler. It plots the entire payload sent by the backend so the student sees the "Whole Picture".
3. **Does it display all matching colleges or a subset?** A subset. It plots exactly the subset returned by the backend to prevent cluttering the view and freezing the browser.
4. **Why do nearly all dots appear on one side?** Dots are plotted by *Closing Rank*. A lower rank is on the left, a higher rank is on the right. 
   - **Target / Safe** colleges have closing ranks *higher (easier)* than your rank, so they plot to the right. 
   - **Reach** colleges have closing ranks *lower (harder)* than your rank, so they plot to the left. 
   - Because the truncation bug (Task 10) was dropping all "Reach" colleges, 100% of the dots were Target/Safe colleges, meaning 100% plotted to the right. With the bug fixed, you will now naturally see dots on both sides.

### Task 7 (Follow-up): Why are there left-side dots (Reach) for NITs but none for IITs?
**Discussion:** In the UI, a student with a Mains rank of ~33k sees many Reach dots, but for their Advanced rank of ~1.2k, they see zero Reach dots. Why?
**Resolution:** This is mathematically expected based on how "Reach" is defined and how ranks work at the very top:
1. **The "Reach" Window is Proportional:** In `recommender.py`, a college is considered a "Reach" if your rank is up to 25% higher than its closing rank (`if rank > closing * (1 + 0.25): return None`).
   - **For NIT Rank (33,232):** 25% is a massive window. A college is a Reach if its closing rank is between 26,585 and 33,231. That 6,600-rank window contains dozens of programs!
   - **For IIT Rank (1,212):** 25% is tiny. A college is only a Reach if its closing rank is between 970 and 1,211. That is a microscopic window of just 241 ranks.
2. **Density of Programs:** There are simply very few IIT programs that happen to close exactly in that narrow 970–1,211 window (especially with branch filters applied).
3. **Proof the Sorting Works:** When limiting results to `max_results`, the backend sorts them by `closing_rank` ascending. IIT closing ranks (~1,000) are much smaller than NIT closing ranks (~30,000), so IITs are placed at the very front. If there had been even one IIT program in that 970–1,211 window, it would have been prioritized. The fact that none are showing means the dataset has exactly *zero* IIT programs matching your criteria in that 240-rank gap.

### Task 7 (Follow-up 2): Should we increase the 25% "Reach" margin for IITs?
**Discussion:** Since a 25% margin at rank 1,200 often yields 0 Reach options, should we bump the percentage for IITs so more dots appear on the left?
**Resolution:** We decided to **keep it at 25%**. 
1. **Volatility scales with rank:** At rank 1,000, cutoffs are extremely rigid; a 250-rank jump is massive and highly unlikely. At rank 30,000, cutoffs are volatile, and a 7,500-rank jump is very possible. The 25% rule perfectly mimics this real-world behavior.
2. **Avoiding False Hope:** If we bumped the margin to 50% for IITs, we would tell a Rank 1,200 student that an IIT closing at Rank 600 is a "Reach". In reality, that is impossible and gives false hope. Keeping it at 25% ensures the system remains honest and data-driven.

