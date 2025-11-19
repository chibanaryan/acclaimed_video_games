# Migration Documentation

This directory contains all documentation related to the Vue.js → Django + HTMX + Alpine.js migration.

## Files

### Planning & Assessment
- **MIGRATION_ASSESSMENT.md** - Initial assessment, dependency graph, and migration strategy
- **MIGRATION_PATTERNS.md** - Common patterns and best practices for migration
- **MIGRATION_QUICKSTART.md** - Quick reference guide for common migration tasks

### Beta Setup & Status
- **BETA_SETUP.md** - Step-by-step guide for setting up the beta directory
- **BETA_STATUS.md** - Current status and next steps for the beta migration
- **BETA_TESTING_GUIDE.md** - Guide for testing the beta version and confirming visual parity
- **BETA_WHAT_TO_CHECK.md** - Checklist of things to verify during migration

### Technical Guides
- **TEMPLATE_CACHING_GUIDE.md** - Django template caching issues and solutions

### Migration Reports
- **migration_reports/** - Individual component migration reports and notes

### Migration Tools
- **extract_vue_styles.py** - Script to extract styles, HTML structure, and component info from Vue components
- **README_EXTRACT_VUE_STYLES.md** - Documentation for the extraction script

## Migration Strategy

The migration follows a **leaf-to-root** approach:
1. Start with leaf components (no dependencies)
2. Work up to composition components
3. Finally migrate page-level components

All beta routes are under `/beta/` prefix to maintain the existing Vue.js site at root level.

