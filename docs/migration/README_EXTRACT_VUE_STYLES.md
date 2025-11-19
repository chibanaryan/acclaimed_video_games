# Vue Component Style Extractor

This script helps extract styles, HTML structure, and component information from Vue.js components to aid in migration to Django + HTMX + Alpine.js.

## Features

- Extracts HTML template structure
- Extracts all style blocks (CSS, SASS, scoped, global)
- Converts SASS to CSS automatically
- Identifies component dependencies
- Extracts props, data, computed properties, and methods
- Generates migration reports with Django template examples
- Creates side-by-side comparison guides

## Usage

### Extract a Single Component

```bash
python docs/migration/extract_vue_styles.py GameRow
```

This will create a migration report at `docs/migration/migration_reports/GameRow_migration.md`

### Extract All Components

```bash
python docs/migration/extract_vue_styles.py --all
```

This will generate migration reports for all Vue components found in `frontend/src/components/`

### List All Components

```bash
python docs/migration/extract_vue_styles.py --list
```

This will list all Vue component files found.

## Output

The script generates markdown reports in the `migration_reports/` directory. Each report includes:

1. **Component Information**
   - File path
   - Dependencies (other components used)
   - Props, data properties, computed properties, methods

2. **HTML Structure**
   - Cleaned HTML structure (Vue directives removed for structure analysis)
   - Original template code

3. **Styles**
   - All style blocks with language and scoped information
   - Combined CSS (SASS converted to CSS)

4. **Migration Notes**
   - HTML structure matching guide
   - Style migration guide
   - Component dependency information

5. **Django Template Example**
   - Ready-to-use Django template code

6. **Testing Checklist**
   - Visual parity verification checklist

## Example Output

For `GameRow.vue`, the script will generate:

- `migration_reports/GameRow_migration.md` containing:
  - HTML structure extracted from template
  - All styles (SASS converted to CSS)
  - Migration notes
  - Django template example

## Integration with Migration Process

1. **Before migrating a component**:
   ```bash
   python docs/migration/extract_vue_styles.py ComponentName
   ```

2. **Review the migration report**:
   - Check HTML structure
   - Review styles
   - Note dependencies

3. **Migrate the component**:
   - Use the HTML structure as reference
   - Copy styles to Django template
   - Follow migration notes

4. **Test for visual parity**:
   - Use the testing checklist
   - Compare side-by-side with Vue version

## Tips

- Start with leaf components (no dependencies) - they're easier to migrate
- Use `--list` to see all components and plan migration order
- Use `--all` to generate reports for all components at once
- Review dependencies to understand migration order
- The SASS to CSS conversion is basic - review converted CSS for accuracy

## Requirements

- Python 3.6+
- No external dependencies (uses only standard library)

## Notes

- The SASS to CSS conversion handles basic nesting and indentation
- Complex SASS features may need manual review
- Scoped styles are identified but you'll need to make selectors specific in Django templates
- Component dependencies are extracted from import statements

