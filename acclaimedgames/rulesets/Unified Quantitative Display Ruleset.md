# Unified Quantitative Display Ruleset

A comprehensive ruleset for producing visual displays of quantitative information whose primary goal is to **enlighten**: make accurate comparisons, reveal patterns/relationships, and support sound judgments. Design and aesthetics are always subordinate to evidence, perception, comprehension, and use.

---

## Table of contents

- [[#1. Purpose, mission, and success criteria]]
  - [[#1.1 Graphical excellence]]
  - [[#1.2 Graphical integrity]]
  - [[#1.3 Aesthetics subordinate to communication]]
  - [[#1.4 Complexity and skepticism about rules]]
- [[#2. Workflow and decision sequence]]
  - [[#2.1 Clarify the communication problem before designing]]
  - [[#2.2 Choose table, text, or graphic based on the job-to-be-done]]
  - [[#2.3 Identify the primary relationship type and comparisons]]
  - [[#2.4 Design for comparison and layered reading]]
  - [[#2.5 Verify and refine before delivery]]
- [[#3. Truthfulness, evidence, and data preparation]]
  - [[#3.1 Show data variation, not design variation]]
  - [[#3.2 Lie factor and dimensional integrity]]
  - [[#3.3 Scale, units, context, and sources]]
  - [[#3.4 Monetary values across time and across countries]]
  - [[#3.5 Derived measures and internal consistency checks]]
- [[#4. Economy of ink and attention]]
  - [[#4.1 Data-ink and data-ink ratio]]
  - [[#4.2 Non-data-ink, redundant data-ink, and when redundancy helps]]
  - [[#4.3 Editing and redesign as a core workflow]]
  - [[#4.4 Avoiding chartjunk, ducks, and computer debris]]
  - [[#4.5 Avoiding optical noise, moiré, and vibration]]
- [[#5. High-information design and viewing architecture]]
  - [[#5.1 Data density and large data matrices]]
  - [[#5.2 Small multiples]]
  - [[#5.3 Layers, hierarchy, and multiple viewing paths]]
  - [[#5.4 Multiple viewing depths and lines of sight]]
  - [[#5.5 Avoiding puzzle graphics]]
- [[#6. Choosing the right format: sentence, text-table, table, semi-graphic, graphic]]
  - [[#6.1 Format choice factors]]
  - [[#6.2 Format rules by use case]]
  - [[#6.3 Table vs graph rules of thumb]]
  - [[#6.4 Practice-derived selection patterns]]
  - [[#6.5 Pie charts and part-to-whole displays]]
- [[#7. Table design and table-graphics]]
  - [[#7.1 Supertables and table craft]]
  - [[#7.2 Reduce non-data and structure for scanning]]
  - [[#7.3 Align, format, and label numbers for effortless reading]]
  - [[#7.4 Order, group, summarize, and place derived measures to support comparison]]
  - [[#7.5 Emphasis and highlighting]]
  - [[#7.6 Table design practice patterns]]
  - [[#7.7 Table-graphics and table lens displays]]
- [[#8. Graph design: general rules]]
  - [[#8.1 Choose the correct graph form for the relationship]]
  - [[#8.2 Scales, axes, and reference structure]]
  - [[#8.3 Managing many series and variables]]
  - [[#8.4 Graph design practice patterns]]
- [[#9. Core quantitative graphic forms and redesign patterns]]
  - [[#9.1 Time-series]]
  - [[#9.2 Relational graphics and scatterplots]]
  - [[#9.3 Distributions: histograms, frequency polygons, stem-and-leaf, rugplots, box plots]]
  - [[#9.4 Part-to-whole and contribution]]
  - [[#9.5 Deviation from baseline or target]]
  - [[#9.6 Mean plus range over time]]
  - [[#9.7 Maps]]
  - [[#9.8 Multivariate encodings and glyphs]]
- [[#10. Annotation, labeling, titles, and integrated text]]
  - [[#10.1 Direct labeling, data-based labels, and legends]]
  - [[#10.2 Titles, messages, and required context]]
  - [[#10.3 Friendly data graphics]]
  - [[#10.4 Integrating words, numbers, and pictures]]
- [[#11. Aesthetics and technique]]
  - [[#11.1 Line weight and orthogonal structure]]
  - [[#11.2 Shape, aspect ratio, and horizontality]]
  - [[#11.3 Color, gray scales, and contrast]]
  - [[#11.4 Typography]]
- [[#12. Production workflow and QA]]
  - [[#12.1 Quantitative checks]]
  - [[#12.2 Perceptual and usability checks]]
  - [[#12.3 Publication checks]]

---

## 1. Purpose, mission, and success criteria

### 1.1 Graphical excellence
A display is excellent when it:
- **Gives the viewer the greatest number of ideas** in the shortest time, with the least ink, in the smallest space.
- **Reveals data**: comparisons, contrasts, differences, variation, change; and also **outliers** and exceptions.
- **Encourages comparison** (within, between, and across panels).
- **Shows multivariate data** (not just one number at a time).
- **Is integrated with words and numbers**: labels, explanations, and evidence live with the graphic.
- **Serves the content**: design is choice in service of evidence, not an end in itself.

### 1.2 Graphical integrity
A display has integrity when it:
- Represents quantities **proportionally** (what is shown matches the data).
- Uses **consistent scales and clear units**.
- Provides **context** needed to interpret magnitudes and changes.
- Avoids any design move that **overstates**, **understates**, or **confuses** the evidence.

### 1.3 Aesthetics subordinate to communication
- Produce **visual displays of quantitative information** whose primary goal is to **enlighten**—i.e., make accurate comparisons, reveal patterns/relationships, and support sound judgments.
- Treat aesthetics as subordinate to communication:
  - Visual styling is acceptable only insofar as it **improves perception, comprehension, and use**.
  - Design remains in service of evidence and the viewer’s tasks; decoration is never an end.

### 1.4 Complexity and skepticism about rules
- Prefer **clarity of complex truth** over decorative simplification. Aim to give visual access to the subtle and difficult; avoid “complicating the simple.”
- Apply principles **skeptically and flexibly**: violating a principle is acceptable if it yields a more truthful, graceful display.

---

## 2. Workflow and decision sequence

### 2.1 Clarify the communication problem before designing
- Identify:
  - The audience’s **task** (lookup exact values vs. detect patterns; persuade vs. analyze; novice vs. statistically fluent).
  - The **message** (what matters most) and what comparisons must be effortless.
  - The **relationship types** present (often more than one) and which is primary.

### 2.2 Choose table, text, or graphic based on the job-to-be-done
- Decide early whether the display is primarily for:
  - **Lookup** (typically a table or text-table, sometimes a dense table-graphic), or
  - **Pattern/relationship perception** (typically a graph, often with supporting tabular detail if exact values also matter).
- Choose the format family early (sentence, text-table, table, semi-graphic, graphic) so the rest of the design work optimizes the right reading task rather than decorating a misfit format. (See §6.)

### 2.3 Identify the primary relationship type and comparisons
- Classify what you must show (often more than one; pick the primary):
  - Time-series change
  - Nominal/ranked comparison
  - Part-to-whole contribution
  - Distribution shape
  - Correlation between variables
  - Deviation from a baseline/target

### 2.4 Design for comparison and layered reading
- Make the data and the intended comparisons visually dominant.
- Demote supporting structure (axes, grid lines, legends, borders) so it never competes with the data.
- Design to **encourage comparison**:
  - comparisons within one view,
  - comparisons between views/panels,
  - comparisons across panels in a multi-panel layout.
- Use **layering and separation** (weight, tone, spacing, alignment) so the viewer can read complex information without decoding a puzzle.

### 2.5 Verify and refine before delivery
- Verification and refinement are mandatory:
  - Perform the quantitative, perceptual/usability, and publication checks in §12.
  - Iterate until the display’s encodings, context, and emphasis reliably support the intended reading tasks.

---

## 3. Truthfulness, evidence, and data preparation

### 3.1 Show data variation, not design variation
- **Design variation ≠ data variation.** Avoid ornamental changes (shading, perspective, icon size, 3D forms) that visually change more than the underlying data.
- Prefer encodings where the eye reads **differences in the data**, not differences in the decoration.

### 3.2 Lie factor and dimensional integrity
**Lie factor**
- Lie factor = *(size of effect shown in the graphic) / (size of effect in the data)*.
- Target lie factor ≈ **1.0**.
- Any substantial departure is a design failure unless explicitly justified and explained.

**Dimensional integrity**
- The **number of visual dimensions** used to represent magnitudes must **not exceed** the number of dimensions in the data.
- **Do not use area/volume** (2D/3D) to represent 1D quantities unless the mapping is explicitly correct and perceptually unambiguous.
- Avoid perspective, foreshortening, and 3D objects for quantitative magnitude—these multiply ambiguity and lie factors.

### 3.3 Scale, units, context, and sources
- Always show **units** and measurement definitions.
- Provide **context** sufficient for interpretation:
  - baseline conditions,
  - comparative references,
  - denominators,
  - population size,
  - exposure,
  - other context required to interpret magnitudes and changes.
- Always include required context that preserves interpretability later:
  - **Time frame / as-of date**.
  - **Units and currency** (including scale, e.g., “$ in thousands,” where not otherwise obvious).
- Label **data sources** and key transformation choices (deflation, smoothing, standardization, exclusions).

### 3.4 Monetary values across time and across countries
- When comparing monetary values from different years, **adjust for inflation** (constant dollars) or the comparison is distorted.
- Use an inflation index to convert values to a common base year (“constant dollars”), and state the basis in the display.
- If values are **not** inflation-adjusted:
  - explicitly label them as **current dollars**,
  - and avoid implying real (inflation-adjusted) change.
- When comparing money values from different countries:
  - convert to a **common currency**,
  - then adjust for inflation as appropriate.
- Make time-series **comparable across time**:
  - consistent sampling windows,
  - same units,
  - comparable denominators.

### 3.5 Derived measures and internal consistency checks
- Prefer derived measures that simplify the intended relationship and reduce mental arithmetic at the moment of reading:
  - For contribution/part-to-whole arguments, add **% of total** and often **cumulative %** to make dominance obvious.
  - For comparisons against targets, include **variance** and **% of quota/budget** adjacent to the base measures.
  - For ranking/comparison, sort by the key measure and add summary columns that enable fast judgment.
- For part-to-whole data:
  - verify that component percentages sum to ~100% (accounting for rounding),
  - fix the data or explain discrepancies to avoid undermining trust.

---

## 4. Economy of ink and attention

### 4.1 Data-ink and data-ink ratio
- **Data-ink** is ink that represents the data; everything else must justify itself.
- Data-ink ratio:
  - Data-ink ratio = *(data-ink) / (total ink)*.
- Maximize the ratio **without losing information**.

### 4.2 Non-data-ink, redundant data-ink, and when redundancy helps
- **Erase non-data-ink**:
  - decorative borders,
  - heavy frames,
  - gratuitous gridlines,
  - background shading,
  - unnecessary symbols,
  - legends and framing that exist only because the software defaulted to them.
- **Erase redundant data-ink** when it repeats the same information unnecessarily.
- But do **not** erase redundancy that improves readability, continuity, or comparison.

Redundancy is acceptable (even desirable) when it supports the viewer’s reading:
- **Cyclical time**: repeat parts of cycles so the eye can track without “teleporting.”
- **Maps that wrap**: repeated context can aid continuity across boundaries.

Rule:
- Keep redundancy only when it **adds reading power**, not decoration.

### 4.3 Editing and redesign as a core workflow
Treat graphical design like writing:
- Iteratively **edit**: prune, simplify, tighten, re-balance.
- Redesign is critical labor:
  - **sift, combine, construct, expunge, correct, test**.

### 4.4 Avoiding chartjunk, ducks, and computer debris
- Avoid chartjunk: decorative structures that are not data.
- Do not embed data in a “duck” (architecture/ornament that overwhelms content).
- Avoid fake 3D, perspective, and cosmetic effects that do not encode additional truthful variables.
- Do not accept software defaults; they often maximize non-data-ink (heavy frames, default gridlines, cluttered legends, thick strokes).
- Rebuild the graphic to serve the data and reading task, not the tool’s template.

### 4.5 Avoiding optical noise, moiré, and vibration
- Avoid patterns and grid treatments that produce **vibration**, optical shimmer, or distracting textures.
- Beware heavy/doubled grid lines and dense intersections that create optical white-dot artifacts.

---

## 5. High-information design and viewing architecture

### 5.1 Data density and large data matrices
**Data density**
- Data density = *(number of data entries) / (area of graphic)*.

Rules:
- Prefer **large data matrices** and **high density** when the subject warrants it.
- If a display is overcrowded:
  - do **data reduction** (averaging, smoothing, clustering) *before* plotting,
  - rather than using chartjunk or oversized canvases.
- High-density displays increase credibility and give context; low-information designs invite suspicion (“what’s missing?”).

### 5.2 Small multiples
Rules:
- Use repeated, consistent frames to compare changes across:
  - time,
  - groups,
  - categories,
  - scenarios.
- Keep scales, encodings, and layout consistent across panels.
- Small multiples enable both:
  - **overall pattern** reading, and
  - **local detail** reading.

Sampling variability:
- When variability from sampling matters, show it directly (e.g., multiple realizations/distributions).
- Small multiples can display sampling variability without heavy explanation.

Managing many series and variables:
- When too many categories/series would clutter a single graph:
  - split into a **series of small graphs** (small multiples) rather than forcing everything into one plot.
  - group series into meaningful subsets (e.g., product families) and keep each subset to a manageable count per graph.
- Use a consistent structure across small multiples:
  - same scale,
  - same axis placement,
  - consistent typography and reference structure,
  to support quick comparison.

### 5.3 Layers, hierarchy, and multiple viewing paths
Design for structured reading:
- A good display supports multiple paths:
  - **across**,
  - **down**,
  - **within**,
  without clutter.
- Organize complex information **hierarchically**, so the viewer can “peel back” layers rather than decode a puzzle.
- Use **layering and separation**:
  - separate elements by weight, tone, spacing, and alignment so each layer can be read cleanly.

### 5.4 Multiple viewing depths and lines of sight
Multiple viewing depths:
- Build graphics that work at:
  1) a distance (overall structure),
  2) close inspection (fine detail),
  3) implicit structure behind the marks (e.g., a dense underlying grid).

Multiple viewing angles / lines of sight:
- Create distinct, stable lines of sight (often horizontal/vertical) so the eye can track each aspect without confusion.

### 5.5 Avoiding puzzle graphics
Rule:
- If understanding requires constant legend-decoding and verbal translation, it’s a failure of design.
- The viewer should quickly move from initial decoding to direct seeing.

---

## 6. Choosing the right format: sentence, text-table, table, semi-graphic, graphic

### 6.1 Format choice factors
Choose format by:
- Amount of data and comparisons required,
- Need for precise values,
- Labeling burden and ordering logic,
- Structure of the story (sequence and grouping).

### 6.2 Format rules by use case
Rules:
- **Sentence**:
  - OK for very few numbers,
  - collapses with more than ~2 numbers.
- **Text-table**:
  - better than sentences for small labeled sets,
  - keeps numbers in reading flow.
- **Table**:
  - best for exact values and dense local comparisons,
  - can carry very large datasets.
- **Semi-graphic**:
  - wordy displays close to text,
  - good for complex, heavily labeled evidence.
- **Graphic**:
  - best for patterns, relationships, comparisons over large/complex data.

### 6.3 Table vs graph rules of thumb
Use a **table** when:
- Users need exact numbers (reference/lookup).
- There are very few values and a graph adds no perceptual advantage (e.g., four ranked items).
- The audience is uncomfortable with statistical graphics and a simple table better matches their literacy.

Use a **graph** when:
- Users need to see the overall pattern:
  - trend,
  - distribution shape,
  - correlation.
- The primary message is relative contribution or change.

### 6.4 Practice-derived selection patterns
These patterns come from practice-answer rationales; treat them as concrete decision templates.

- Lookup vs. pattern:
  - If the reader “just wants to know” exact values by category (e.g., departmental expenses/headcount), use a table.
  - If the reader needs to **see how relationships change**, use a graph.
- Combined relationships:
  - When you must show both **part-to-whole** and **time-series** across several categories, the typical encoding (e.g., stacked bars) may become too complex.
  - Consider a **multi-series line graph** to show trends and relative contributions more clearly, then highlight the most important series (e.g., thicker line).
- Distribution comparison:
  - If the audience is statistically fluent, a small table of summary statistics (median/mean/std. dev.) can suffice for a distribution.
  - Otherwise use a distribution graph.
  - For one distribution: histogram or frequency polygon.
  - For comparing two distributions: two **frequency polygons** (two lines) often support shape comparison better than two histograms.
- Small ranked sets:
  - If the key message is a ranking of only a handful of values (e.g., four), a table can communicate most efficiently; sort by the measure.
- Correlation with a before/after intervention:
  - Use a scatter plot for correlation.
  - Use color to separate periods (pre/post).
  - Use ordered intensity (e.g., darker over time) if you must also show progression within a period.
- Skewed contribution stories:
  - For a striking part-to-whole story (e.g., top decile contributes most), use a bar display and ensure labels clearly distinguish “donor groups” from “% of total contributed.”
  - Use a title that states the key takeaway so the graph reinforces it.

### 6.5 Pie charts and part-to-whole displays
- A table is nearly always better than a pie chart.
- Pie charts should **never** be used for serious quantitative comparison because:
  - low data density,
  - weak ordering along a visual dimension,
  - angle/area comparisons are harder than position/length.

---

## 7. Table design and table-graphics

### 7.1 Supertables and table craft
- A dense, well-structured table can outperform “a hundred little bar charts.”
- Use ordering and grouping so the table reads like organized paragraphs:
  - rows/sections grouped by meaning,
  - horizontal rules used sparingly to create “data paragraphs,”
  - ordering chosen to tell an analytic story (not alphabetical by default).

### 7.2 Reduce non-data and structure for scanning
- Prefer **white space** and alignment over heavy grids:
  - eliminate full cell grids,
  - keep at most a light rule separating headers from the body when needed.
- Avoid decorative styling that competes with the data:
  - don’t use heavy borders,
  - don’t use dark fills,
  - don’t use excessive bold in headers.

### 7.3 Align, format, and label numbers for effortless reading
Make numeric formatting unambiguous and consistent:
- Include **% signs** for percentages.
- Indicate the **unit of measure** for currencies (and scale, e.g., “$ in thousands”) where not otherwise obvious.
- Use consistent precision; avoid fluctuating decimal places that slow scanning (e.g., for rates/points).
- Use commas (digit grouping) in large numbers to improve readability.

Align headers with the data they describe:
- Header alignment should preview the alignment of values beneath (e.g., right-aligned numeric columns).

### 7.4 Order, group, summarize, and place derived measures to support comparison
Placement and adjacency:
- Put the most-used comparison column(s) adjacent to row labels.
  - Example pattern: place the key performance metric immediately to the right of names.
- Place **derived measures** to the right of the base measures they depend on.
  - Example pattern: variance and % of quota should follow bookings and quota columns.

Summaries:
- Add summary measures that enable “overall” judgments (totals, averages, etc.) when that’s part of the task.

Ordering:
- Sort rows by the key measure to reveal rank order and support comparison.

Dominance and contribution:
- Use **% of total** (and sometimes **cumulative %**) when it helps reveal dominance and supports a Pareto argument.

### 7.5 Emphasis and highlighting
- Use bolding/highlighting to support a specific task:
  - For lookup tables, it can be appropriate to make the primary lookup field (e.g., lender name) stand out, but avoid unnecessary emphasis elsewhere.
- Never use “highlight everything else” as a way to de-emphasize something unnecessary—remove unnecessary information instead.

### 7.6 Table design practice patterns
Use these as reusable design patterns.

- Sales rep performance table pattern:
  - Remove the grid; use minimal rules.
  - Add column summaries / totals.
  - Sort reps by bookings; include bookings as % of total bookings.
  - Keep bookings next to names; derived columns to the right.
- Mortgage rates lookup table pattern:
  - Arrange the table for lookup by the dimension users care about (e.g., lender first).
  - Use white space (or a blank column) to separate right-aligned numbers from left-aligned text when needed.
  - Avoid repeating group labels in every row; show them once per group and at the start of a new page/section containing that group.
- Transaction-level expense table → analytical summary pattern:
  - If transaction-level detail is not required, remove it and summarize to the level needed (e.g., quarter × expense type).
  - Avoid heavy vertical rules that fight the needed horizontal scanning between category and value columns.
  - Use a legible font; avoid decorative fonts that reduce readability.
  - Place a “total” column adjacent to the expense type column if totals matter more than the quarterly breakdown (bring the most important comparisons closer).
- Product dominance (Pareto) table pattern:
  - Include % of total and cumulative % columns for revenue and profit to make dominance obvious.
  - Sort products so the dominant items appear first.
  - Add a prominent message above/within the table that states the key finding.
  - Include the time period covered in the title so the table stays interpretable later.
- Regional performance reference table pattern (VP of Sales use case):
  - Put all measures for each region in a single row to support fast lookup.
  - This also enables easy across-region comparison of any single measure because each measure is in its own column.
  - Add regional % of total measures (e.g., % of total revenue) to support relative-performance judgments.
  - Add per-product % of total revenue measures to compare product mix by region.
  - Add derived measures that the reader can’t (or shouldn’t have to) compute mentally in the moment (profit, avg revenue per salesperson, avg order size).

### 7.7 Table-graphics and table lens displays

**Convert scaffolding into data-bearing structure**
- Convert “graphical scaffolding” into data-bearing structure:
  - **data-based coordinate lines** → **data-based labels**.
- Prefer **range labels** (actual min/max) over “round-number” labels when using data-based frames.
- Use **double-functioning labels**:
  - labels that both identify and encode an ordering,
  - avoid arbitrary ordering (e.g., alphabetical) when a meaningful sequence exists.

**Range-frames**
- Replace passive frames with **range-frames**:
  - Frame endpoints correspond to realized **min/max** (data-based), not arbitrary round limits.
  - Range-frames increase information with almost no added ink.

**Quartile plots**
- Upgrade range-frames to **quartile plots**:
  - show min/max plus median and quartiles along both axes.
  - Often better than a plain scatterplot because it adds marginal distribution info.

**Dot-dash plots and rugplot integrations**
- Add marginal distributions via **dot-dash plots** / **rugplots**:
  - show marginal distributions and the bivariate distribution together.
  - use the frame’s ink as data (dashes/dots) rather than decoration.
- Use rug marks on axes to show marginal distributions and to connect sequences of projections.

**Table lens displays**
- Use a table lens display to show relationships among several quantitative variables across many categorical items as aligned micro bar charts.
- Sort the categorical items by one featured variable (e.g., descending), then scan other variables for similar or opposite patterns to infer positive/negative correlations.
- Table lens displays can be easier to understand than scatter plots for audiences unfamiliar with correlation plots; they work even for only two variables.
- When showing ranked items in a table-lens (or any ranked table), ensure the visual order reads naturally (largest at top) to support quick scanning.
- Construction principles (tool-agnostic):
  - Use a consistent baseline and scale per variable.
  - Remove nonessential chart elements (axes lines, heavy borders).
  - Align rows precisely so patterns are visually comparable across variables.

---

## 8. Graph design: general rules

### 8.1 Choose the correct graph form for the relationship
- Use a graph when the job is pattern/relationship perception (trend, distribution shape, correlation), not when the job is simple value lookup.
- Don’t use a scatter plot (correlation display) when the goal is to show change through time with a small set of time points; use a time-series form instead.
- Don’t connect values with lines when the horizontal axis is nominal or ordinal (categories with no meaningful interval spacing).
  - Connecting is meaningful on an interval scale, not on nominal/ordinal.
- Avoid 3D forms and perspective for quantitative magnitudes; use 2D only.

### 8.2 Scales, axes, and reference structure
- Remove or mute unnecessary reference structure:
  - eliminate grid lines unless they materially improve value reading; if kept, make them subtle.
  - visually mute axis lines and scale labels so they support rather than compete with the data.
- Use tick marks and labels only as needed; too many reduce readability.
- Avoid unnecessary decimal places on axes; they reduce efficiency and imply false precision.
- When subtle change matters:
  - A zero-based scale can preserve consistency but may hide small variation.
  - Provide an additional view with a tighter scale (starting just below the minimum) to reveal the pattern; present both for completeness.

### 8.3 Managing many series and variables
- When too many categories/series would clutter a single graph:
  - Split into a **series of small graphs** (small multiples) rather than forcing everything into one plot.
  - Group series into meaningful subsets (e.g., product families) and keep each subset to a manageable count per graph.
- Use a consistent structure across small multiples (same scale, same axis placement) to support quick comparison.

### 8.4 Graph design practice patterns

- Multi-metric quarterly performance pattern:
  - Use multiple line graphs arranged vertically (small multiples) with the same time axis; one measure per graph (e.g., revenue, guests, revenue/guest).
  - Remove legends, grid lines; mute axes; consistent font; add date/currency.
  - If points are used to encode individual values, size them so they’re easily distinguishable.
  - If changes are small, add a second set of graphs with tighter scales; show both.
- Many-product time series pattern:
  - Put time on the X axis; one line per product; use 2D only.
  - Break into multiple graphs (e.g., three panels) with a few lines each; reduce tick clutter; remove decimals; remove grid; avoid rotated labels.
- Two-time-point market-share change pattern:
  - Replace multiple pie charts with either:
    - A line graph with one line per company connecting the two time points, or
    - A bar chart showing the change (difference) from period A to period B.
  - Arrange time points left-to-right; keep decorative imagery separate from the graph.
  - Use the title to state the main story (e.g., gains by top vendors came at expense of smaller rivals).
- Mean + range over time pattern:
  - Encode the mean trend as a line; encode the min/max as simple range boxes; highlight the mean; mute the rest; remove unnecessary tick marks.

---

## 9. Core quantitative graphic forms and redesign patterns

### 9.1 Time-series
- Time-series are central for showing change.
- Use time-series to show the **data**, not decoration:
  - minimal non-data-ink,
  - direct labeling where possible,
  - avoid needless markers at every point unless they encode data.
- Causality caution:
  - Time itself is rarely a causal variable; a time plot is not a causal explanation.
  - If causal mechanisms matter, annotate events, interventions, and context; don’t let “time trend” substitute for explanation.

### 9.2 Relational graphics and scatterplots
Relational graphics:
- Relational graphics are central to analysis and causal reasoning.
- Use relational graphics to confront causal hypotheses with evidence (without pretending the plot alone proves causality).

Scatterplot redesign patterns:
- Redesign the default scatterplot using table-graphic patterns:
  - **range-frames**,
  - **quartile plots**,
  - marginal distributions via **dot-dash plots / rugplots** (see §7.7 for construction rules).
- For multivariate sequences, connect related views so the eye can follow transformations:
  - use fringe dashes and linked sequences of bivariate scatters to trace the same observation through multiple projections.
- Outliers/strangers:
  - Identify unusual points (outliers, “strangers”) by observation number/name so they can be investigated.

Correlation with a before/after intervention:
- Use a scatter plot for correlation; use color to separate periods (pre/post).
- Use ordered intensity (e.g., darker over time) if you must also show progression within a period.

### 9.3 Distributions: histograms, frequency polygons, stem-and-leaf, rugplots, box plots

Distribution choice rules:
- If the audience is statistically fluent, a small table of summary statistics (median/mean/std. dev.) can suffice for a distribution.
- Otherwise use a distribution graph.
- For one distribution:
  - histogram, or
  - frequency polygon.
- For comparing two distributions:
  - two **frequency polygons** (two lines) often support shape comparison better than two histograms.

Histogram/bar redesign patterns:
- Remove enclosing boxes and heavy axes (erase frames).
- Replace heavy ticks and axes with a **white grid** when appropriate:
  - erase parts of data measures to create clean reference lines,
  - tie numeric labels directly to the reference lines,
  - potentially eliminate tick marks entirely.
- Baselines can often be erased; if kept, keep them **thin**.
- Watch for optical artifacts at intersections of thick bars and baselines.

Stem-and-leaf:
- Use digits as marks: the data themselves form the distribution.
- “The simplest meaningful mark is a digit.” Favor designs where **every element carries information**.

Rugplots:
- Use rug marks on axes to show marginal distributions and to connect sequences of projections.

Box plots / quartile displays:
- Use quartile/median information explicitly.
- Consider **variable-width notched box plots**:
  - box width encodes group size (e.g., proportional to √n),
  - notches reflect uncertainty around medians,
  - use log scales when warranted and label them clearly.

Box plot conventions:
- **3-value** box plot: lowest, median, highest.
- **5-value** box plot: lowest, 25th percentile, median, 75th percentile, highest.

Box plot styling principles:
- Remove chart borders and legends that add no information.
- Reduce or eliminate grid lines; keep reference structure subtle.
- Use neutral, light fills for boxes; avoid shadows and 3D effects.
- Make the median mark distinct (e.g., darker/thicker) without overpowering the display.
- Set the quantitative scale with slight padding beyond min/max so the whiskers aren’t cramped.

### 9.4 Part-to-whole and contribution
Rules for part-to-whole communication:
- For contribution/part-to-whole arguments:
  - add **% of total** and often **cumulative %** to make dominance obvious.
- For part-to-whole data integrity:
  - verify components sum to ~100% (accounting for rounding),
  - fix the data or explain discrepancies.

Skewed contribution stories:
- For a striking part-to-whole story (e.g., top decile contributes most):
  - use a bar display,
  - ensure labels clearly distinguish “donor groups” from “% of total contributed.”

### 9.5 Deviation from baseline or target
Rules for target/baseline comparison:
- For comparisons against targets:
  - include **variance** and **% of quota/budget** adjacent to the base measures,
  - so the display encodes the deviation directly rather than requiring mental computation.

### 9.6 Mean plus range over time
Mean + range over time:
- Encode the mean trend as a line.
- Encode the min/max as simple range boxes.
- Highlight the mean; mute the rest.
- Remove unnecessary tick marks.

### 9.7 Maps
- Use maps to show data with geographic context.
- Prefer designs that preserve data density and local detail:
  - dot maps can carry massive detail and support macro/micro reading.
- Avoid “puzzle maps” where decoding depends on complex color legends.

### 9.8 Multivariate encodings and glyphs
- Multivariate glyphs can work if they remain legible at small sizes and don’t become puzzles.
- Avoid bilateral symmetry that wastes space without adding information:
  - symmetry can be redundant; consider half-faces or asymmetrical designs if adding variables.
- Even when using glyphs, keep the underlying structure clear (e.g., the base scatterplot still matters).

---

## 10. Annotation, labeling, titles, and integrated text

### 10.1 Direct labeling, data-based labels, and legends
- Prefer **labels placed on the graphic** to legends that force eye-darting.
- If a legend is required:
  - keep it visually subdued (no heavy borders, no oversized text).
- Make labels and coordinate references **data-based** where possible:
  - integrate labels with the scale and with data-bearing structures.
- Align axis titles with the scale labels they describe; use consistent typography.
- Use small, precise, modest text; avoid clutter but do not under-label.

### 10.2 Titles, messages, and required context
Titles:
- Titles should not be generic.
- Where possible, state the key message so the graph is immediately interpretable (especially for skewed contribution and market-share stories).

Context that must be present on or with the display:
- Time frame / as-of date.
- Units and currency (including scale where relevant).
- Sources and key transformation choices when needed to interpret the numbers.

Text guidance by purpose:
- For explanatory communication:
  - label outliers,
  - add equations,
  - include small tables in the plotting field when useful,
  - use text to support interpretation of technically complex evidence.
- For exploratory analysis:
  - use words primarily to instruct how to read a technically complex design—not to tell the viewer what to conclude.

Contrast and legibility:
- Maintain readable contrast for text and data.
- Avoid dark backgrounds with low-contrast labels that reduce legibility.

### 10.3 Friendly data graphics
A friendly data graphic:
- Spells words out; avoids cryptic abbreviations.
- Keeps words left-to-right; avoids rotated axis labels.
- Uses small explanatory messages directly on the graphic.
- Avoids elaborate shadings/cross-hatching; minimizes legends via direct labeling.
- Chooses colors mindful of color-deficient viewers:
  - avoid red/green as the only essential contrast,
  - blue is generally distinguishable.
- Avoids chartjunk; attracts curiosity rather than repels.
- Uses clear, modest typography; prefers **serif**, mixed case; avoids all-caps and clotted lettering.

### 10.4 Integrating words, numbers, and pictures
- Words on graphics are often **data-ink**.
- Data graphics are **paragraphs about data**; treat them like paragraphs:
  - integrate words, numbers, tables, and pictures in one flow,
  - avoid artificial separation caused by production conventions,
  - repeat graphics near where they are discussed if necessary, even at reduced size.

---

## 11. Aesthetics and technique

### 11.1 Line weight and orthogonal structure
- Prefer **thin lines**; thick drafting-pen linework is clumsy.
- Use **orthogonal intersections** of lines with different weights:
  - heavier lines should represent data measures,
  - lighter lines can support structure; weight differences imply meaning differences.
- Avoid constant-thickness “all lines equal” design; it dilutes structure and hierarchy.

### 11.2 Shape, aspect ratio, and horizontality
General rule:
- Graphics should tend toward **horizontal** shapes: longer than tall.

Reasons:
- **Horizon analogy**: the eye is practiced at detecting deviations from a horizon; time-series benefit from horizontal stretch.
- **Labeling** is easier left-to-right on horizontal fields.
- Many causal displays put “cause” on x-axis and “effect” on y-axis; horizontal elaboration supports causal reading.
- Wiggly curves and scatter often need to be wider than tall; smooth curves can tolerate taller shapes.

Aspect ratio guidance:
- Don’t treat golden ratio as law; aesthetic “rules” are uncertain.
- If data suggest a shape, follow that.
- Otherwise, aim for a graphic **about 50% wider than tall** (aspect ratio ≈ **1.5**).

### 11.3 Color, gray scales, and contrast
- Color often lacks an inherent perceptual ordering; complex color schemes can become verbal decoding puzzles.
- For ordered magnitude, **gray scales** often communicate hierarchy better than color.
- If using color:
  - ensure interpretability for color-deficient viewers,
  - avoid red/green as the only essential contrast,
  - keep the palette calm and non-vibrating.
- Maintain readable contrast for text and data; avoid dark backgrounds with low-contrast labels.

### 11.4 Typography
- Use typography that reads like good prose: clear, precise, modest.
- Prefer **serif** type, mixed case; avoid all caps for text.
- Match the typography of the graphic to surrounding text; avoid stylistic mismatch between figure and page.
- Use a legible font; avoid decorative fonts that reduce readability.

---

## 12. Production workflow and QA

### 12.1 Quantitative checks
Before shipping a graphic:
- **Lie factor** near 1.0.
- Dimensional integrity:
  - no extra visual dimensions for 1D quantities,
  - avoid area/volume and 3D unless explicitly correct and unambiguous.
- Data-ink ratio improved relative to a reasonable baseline.
- Data density appropriate to the question; if low-density, justify.
- Part-to-whole internal consistency where relevant:
  - component percentages sum to ~100% (accounting for rounding) or discrepancies are explained.

### 12.2 Perceptual and usability checks
- Can a viewer read it without constant legend decoding?
  - If not, you’ve made a puzzle.
- Are words readable left-to-right, without rotation?
- Any moiré/vibration or optical artifacts?
- Does the display support both macro and micro readings?
- Encodings match the relationship:
  - don’t connect nominal/ordinal categories with lines,
  - don’t use a correlation chart form for time-series change,
  - don’t use 3D or perspective for quantitative magnitudes.
- Units, time frames, and definitions are explicit.
- Visual emphasis matches analytic importance.
- The display cannot be misread due to scale or labeling choices.
- Reference structure supports rather than competes with data:
  - grid lines are absent unless materially helpful, and if present are subtle,
  - axes and scale labels are visually muted,
  - decimals are not used unnecessarily on axes.

### 12.3 Publication checks
- Labels, units, sources, and key transformations present.
- Caption and explanation integrated with the display (not an afterthought).
- If referenced repeatedly, consider reprinting the graphic near each discussion point (even at reduced size), rather than forcing repeated searching.
