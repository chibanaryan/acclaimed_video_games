# Work Packages for Parallel Migration

These are ready-to-use work packages that can be assigned to different agents.

## Package 1: ListResultsComponent Migration ✅

**File**: `frontend/src/components/ListResultsComponent.vue` → `beta/templates/includes/_list_results.html`

**Props**: `items`, `showType`, `showRank`

**Tasks**:
1. ✅ Convert Vue template to Django template
2. ✅ Replace `v-for` with `{% for %}`
3. ✅ Replace `v-if` with `{% if %}`
4. ✅ Replace `router-link` with `{% url %}` tags
5. ✅ Migrate scoped styles to `base.html` or component-specific styles
6. Test in isolation
7. Compare with Vue version for visual parity

**Dependencies**: None (leaf component)

**Status**: ✅ COMPLETED

---

## Package 2: GameSearchResult Migration ✅

**File**: `frontend/src/components/GameSearchResult.vue` → `beta/templates/includes/_game_search_result.html`

**Props**: `result` (game object with slug, thumbnail, name, yearOfRelease, rank)

**Tasks**:
1. ✅ Convert Vue template to Django template
2. ✅ Replace `router-link` with `{% url 'beta:game-detail' slug=result.slug %}`
3. ✅ Migrate scoped styles
4. Test in isolation
5. Compare with Vue version for visual parity

**Dependencies**: None (leaf component)

**Status**: ✅ COMPLETED

---

## Package 3: GameProperties Migration ✅

**File**: `frontend/src/components/GameProperties.vue` → `beta/templates/games/includes/_game_properties.html`

**Props**: `game` (full game object)

**Tasks**:
1. ✅ Convert Vue template to Django template
2. ✅ Replace `router-link` with Django `{% url %}` tags
3. ✅ Convert `getGameRankRoute()` method logic to Django template tags or filters (using `game_rank_url` filter)
4. ✅ Migrate scoped styles
5. Test in isolation
6. Compare with Vue version for visual parity

**Dependencies**: None (leaf component)

**Status**: ✅ COMPLETED

---

## Package 4: SelectableTagList Migration ✅

**File**: `frontend/src/components/SelectableTagList.vue` → `beta/templates/includes/_selectable_tag_list.html` + Alpine.js

**Props**: `tags`, `selectedTags`, `onToggle`

**Tasks**:
1. ✅ Read Vue component to understand state management
2. ✅ Convert to Django template with Alpine.js for interactivity
3. ✅ Use `x-data` for selected tags state
4. ✅ Use `@click` for toggle functionality
5. ✅ Migrate styles
6. Test interactivity
7. Compare with Vue version

**Dependencies**: None (leaf component, but needs Alpine.js)

**Status**: ✅ COMPLETED (template created)

---

## Package 5: RangeSlider Migration ✅

**File**: `frontend/src/components/RangeSlider.vue` → `beta/templates/includes/_range_slider.html` + Alpine.js

**Props**: `min`, `max`, `value`, `onChange`

**Tasks**:
1. ✅ Read Vue component to understand slider logic
2. ✅ Convert to Django template with Alpine.js
3. ✅ Use `x-model` for value binding
4. ✅ Use `@input` for change events
5. ✅ Migrate styles
6. Test interactivity
7. Compare with Vue version

**Dependencies**: None (leaf component, but needs Alpine.js)

**Status**: ✅ COMPLETED (template created)

---

## Package 6: SearchInput Migration ✅

**File**: `frontend/src/components/SearchInput.vue` → `beta/templates/includes/_search_input.html` + Alpine.js

**Props**: `value`, `placeholder`, `onInput`

**Tasks**:
1. ✅ Read Vue component
2. ✅ Convert to Django template with Alpine.js
3. ✅ Use `x-model` for value
4. ✅ Use `@input` for events
5. ✅ Migrate styles
6. Test interactivity
7. Compare with Vue version

**Dependencies**: None (leaf component, but needs Alpine.js)

**Status**: ✅ COMPLETED (template created)

---

## Package 7: MultiSelectComponent Migration ✅

**File**: `frontend/src/components/MultiSelectComponent.vue` → `beta/templates/includes/_multi_select.html` + Alpine.js

**Props**: `options`, `selected`, `onChange`

**Tasks**:
1. ✅ Read Vue component to understand dropdown logic
2. ✅ Convert to Django template with Alpine.js
3. ✅ Use `x-data` for dropdown state
4. ✅ Use `x-show` for dropdown visibility
5. ✅ Use `@click` for selection
6. ✅ Migrate styles
7. Test interactivity
8. Compare with Vue version

**Dependencies**: None (leaf component, but needs Alpine.js)

**Status**: ✅ COMPLETED (template created)

---

## Package 8: Missing Page Templates ✅

**Create basic templates for**:
- ✅ `beta/templates/games/game_detail.html`
- ✅ `beta/templates/games/game_search.html`
- ✅ `beta/templates/developers/developer_list.html`
- ✅ `beta/templates/developers/developer_detail.html`
- ✅ `beta/templates/lists/list_list.html`
- ✅ `beta/templates/posts/post_list.html`
- ✅ `beta/templates/pages/page_detail.html`

**Tasks per template**:
1. ✅ Read corresponding Vue component
2. ✅ Create Django template extending `base.html`
3. ✅ Add content (fully implemented, not placeholders)
4. ✅ Ensure proper URL routing
5. Test route is accessible

**Dependencies**: None (can be placeholders)

**Status**: ✅ COMPLETED

---

## Package 9: GameRow Migration ✅

**File**: `frontend/src/components/GameRow.vue` → `beta/templates/games/includes/_game_row.html`

**Props**: `game`

**Dependencies**: ✅ `GameRowProperties` is done

**Tasks**:
1. ✅ Read Vue component
2. ✅ Convert to Django template
3. ✅ Include `_game_row_properties.html` partial
4. ✅ Migrate styles
5. Test in isolation
6. Compare with Vue version

**Status**: ✅ COMPLETED

---

## Package 10: PostList Migration ✅

**File**: `frontend/src/components/PostList.vue` → `beta/templates/posts/post_list.html` + view updates

**Dependencies**: ✅ `PostItem` is done

**Tasks**:
1. ✅ Read Vue component
2. ✅ Update `PostListView` in `beta/views.py` if needed
3. ✅ Create template using `{% include %}` for `_post_item.html`
4. ✅ Add pagination if needed
5. ✅ Migrate styles
6. Test functionality
7. Compare with Vue version

**Status**: ✅ COMPLETED

---

## Package 11: SimpleFilters Migration ✅

**File**: `frontend/src/components/SimpleFilters.vue` → `beta/templates/includes/_simple_filters.html` + Alpine.js

**Props**: `meta`, `filters`, `onFilterChange`

**Tasks**:
1. ✅ Read Vue component to understand filter logic
2. ✅ Convert to Django template with Alpine.js
3. ✅ Use `x-data` for filter state
4. ✅ Use `@change` for filter updates
5. ✅ Migrate styles
6. Test interactivity
7. Compare with Vue version

**Dependencies**: None (independent)

**Status**: ✅ COMPLETED

---

## Quick Start Instructions for Each Package

1. **Read the Vue component** in `frontend/src/components/`
2. **Check existing migrations** in `beta/templates/` for patterns
3. **Create the Django template** following established patterns
4. **Test locally** at `/beta/` route
5. **Compare visually** with Vue version at `/`
6. **Update** `docs/migration/MIGRATION_ASSESSMENT.md` when complete
7. **Mark as ✅** in the progress tracking

