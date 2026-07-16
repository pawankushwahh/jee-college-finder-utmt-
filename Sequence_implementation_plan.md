# DIY Task Sequence

Here is a step-by-step guide designed for you to pick up one task at a time, review the code, and implement the fix yourself. They are ordered from the most straightforward (text replacements/UI tweaks) to the most complex (logic reviews).

## 1. Change "Target" and "Reach" to something more appropriate (Task 6)
**What to do:** Decide on new terminology (e.g., "Moderate", "Ambitious").
**Files to edit:**
- `app/jee_college_finder_utmt/recommender.py`: Update the dictionary keys in `CATEGORY_ORDER`, `FIT_LABELS`, `CATEGORY_BLURBS`, and the string returns in `_categorize`.
- `templates/jee_college_finder_utmt_templates/js/app.js`: Search for `"Target"` and `"Reach"` and replace them (especially in `SECTION_ORDER`, `byCat` tracking, and UI strings).
- `templates/jee_college_finder_utmt_templates/js/i18n.js`: Update all translations.
- `templates/jee_college_finder_utmt_templates/index.html`: Update the Welcome screen legend (`.dot--target`, `.dot--reach`).
- `templates/jee_college_finder_utmt_templates/css/style.css`: Update any CSS classes (e.g., `.tone-target`, `.dot--target`) if you decide to change the CSS class names as well.

## 2. Fix logic for "Safe" (Task 5)
**What to do:** Currently, a college is marked "Safe" if `rank <= opening`. This means your rank must be better than the absolute best person who got in last year. Decide if "Safe" should be more forgiving (e.g., rank is in the top 30% of the closing-opening gap).
**Files to edit:**
- `app/jee_college_finder_utmt/recommender.py`: Modify the `_categorize(rank, opening, closing)` function to reflect your new mathematical definition of "Safe".

## 3. Fix: Instis for "Reach" and "Safe" not showing (Task 10)
**What to do:** There is a bug where these categories don't appear in the results list. This is likely an issue with how the frontend slices the array of results to prevent freezing the browser, or how it toggles visibility.
**Files to edit:**
- `templates/jee_college_finder_utmt_templates/js/app.js`: Search for `const targets = recs.filter((r) => r.category === "Target");` and the `pool` slicing logic. Ensure that when it truncates results, it doesn't accidentally discard all the "Safe" and "Reach" items.

## 4. Ensure "Whole Picture" sliders show dots on both sides (Task 7)
**What to do:** The rank scale (ruler) sometimes has dots perfectly flush against the edge, making it hard to see. You need to add a mathematical buffer to the minimum and maximum scale values.
**Files to edit:**
- `templates/jee_college_finder_utmt_templates/js/app.js`: Locate the `renderRuler()` or `drawRuler()` logic. Find where `minRank` and `maxRank` are calculated and subtract/add a padding value (e.g., `minRank * 0.8` and `maxRank * 1.2`) so the dots sit comfortably within the line.

## 5. Move the filter below to be just above the college table (Task 8)
**What to do:** Move the filter panel from its current layout position to sit horizontally directly above the college result cards.
**Files to edit:**
- `templates/jee_college_finder_utmt_templates/index.html`: Cut the `<aside class="results-panel">` block and paste it inside the results container just before the `<ul class="college-list">`.
- `templates/jee_college_finder_utmt_templates/css/style.css`: Refactor the CSS grid/flexbox for `.results-layout` and `.results-panel` to ensure it looks good horizontally.

## 6. Add "State" filter separately (Task 9)
**What to do:** Add a standalone state filter for the results page so users can filter recommended colleges by their location.
**Files to edit:**
- `templates/jee_college_finder_utmt_templates/index.html`: Add a new `<select id="filter-state">` inside the `#panel-body` filter panel.
- `templates/jee_college_finder_utmt_templates/js/app.js`: Add an event listener for this dropdown and update the `applyFilters()` logic to hide college cards that don't match the selected state.

## 7. Review the algo and logic for all decisions & Create Flowchart (Tasks 2 & 11)
**What to do:** Sit down and map out exactly how a student's profile translates into a final list of colleges. 
**Files to edit:**
- `app/jee_college_finder_utmt/states.py`: Review `GOAL_TAG_WEIGHTS` and how interests map to specific branches.
- `app/jee_college_finder_utmt/recommender.py`: Review `_interest_score` and `_calculate_probability`.
- Draw out the flowchart using a tool like Whimsical, Excalidraw, or Mermaid.md to present to your superior.
