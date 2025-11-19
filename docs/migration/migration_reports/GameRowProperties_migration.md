# Migration Report: GameRowProperties

## Component Information

- **File**: `frontend/src/components/GameRowProperties.vue`
- **Dependencies**: None
- **Props**: game, showRank, default
- **Data Properties**: None
- **Computed Properties**: None
- **Methods**: None

## HTML Structure

```html
<div 
        class="py-0">
        <label class="has-text-weight-medium is-size-6">
            All time rank:
        </label>
        <span class="has-text-weight-medium is-size-6">
            {{ value }}
        </span>
    </div>
    <div class="py-0">
        <label class="has-text-weight-medium is-size-6">
            Developer{{ value }}:
        </label>
        <span 
            
            class="is-size-6">
            <router-link 
                
                class="is-size-6">
                {{ value }}
            </router-link><template >,
```

## Original Template

```vue
<template>
<div v-if="showRank"
        class="py-0">
        <label class="has-text-weight-medium is-size-6">
            All time rank:
        </label>
        <span class="has-text-weight-medium is-size-6">
            {{ game.rank }}
        </span>
    </div>
    <div class="py-0">
        <label class="has-text-weight-medium is-size-6">
            Developer{{ game.developers.length == 1 ? '' : 's' }}:
        </label>
        <span v-for="developer, i in game.developers"
            :key="developer.id"
            class="is-size-6">
            <router-link :to="{ name: 'developer-alias-redirect', params: { id: developer.id } }"
                :key="developer.id"
                class="is-size-6">
                {{ developer.name }}
            </router-link><template v-if="i < (game.developers.length - 1)">,
</template>
```

## Styles

### Style Blocks


### Combined CSS (for Django template)

```css

```

## Migration Notes

### HTML Structure Matching

1. Copy the HTML structure exactly
2. Replace Vue directives:
   - `v-if` → Django template `if` tag
   - `v-for` → Django template `for` tag
   - `v-show` → Alpine.js `x-show`
   - `v-model` → Alpine.js `x-model` or HTML `name` attribute
   - `:key` → Remove (not needed in Django)
   - `@click` → Alpine.js `@click` or HTML `onclick`
   - `router-link` → Django `url` template tag

### Style Migration

1. Copy all styles to Django template
2. Convert SASS to CSS if needed
3. Handle scoped styles (make selectors specific)
4. Test side-by-side with Vue version

### Component Dependencies

No component dependencies (leaf component - good starting point)

## Django Template Example

```django
{% extends 'beta/base.html' %}

{% block title %}GameRowProperties - Acclaimed Games{% endblock %}

{% block content %}
<style>

</style>

<div 
        class="py-0">
        <label class="has-text-weight-medium is-size-6">
            All time rank:
        </label>
        <span class="has-text-weight-medium is-size-6">
            {{ value }}
        </span>
    </div>
    <div class="py-0">
        <label class="has-text-weight-medium is-size-6">
            Developer{{ value }}:
        </label>
        <span 
            
            class="is-size-6">
            <router-link 
                
                class="is-size-6">
                {{ value }}
            </router-link><template >,
{% endblock %}
```

## Testing Checklist

- [ ] HTML structure matches exactly
- [ ] All styles copied and converted
- [ ] Colors match exactly (use color picker)
- [ ] Fonts match exactly (inspect computed styles)
- [ ] Spacing matches exactly (measure with DevTools)
- [ ] Responsive behavior matches
- [ ] Hover states work
- [ ] Side-by-side comparison with Vue version
