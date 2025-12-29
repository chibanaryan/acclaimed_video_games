---
name: commit
description: Commit and push changes to git. Use when asked to commit, push, or save changes to the repository.
---

# Commit and Push Workflow

Use this workflow to save changes to the repository WITHOUT deploying to production.

## Steps

### 1. Update DEVLOG.md (if warranted)

**When to Update:**
- Bug fixes that resolve user-reported issues or known problems
- Performance improvements or optimizations
- New features or functionality additions
- Significant refactoring or architectural changes
- API or database schema modifications
- Deployment issues or critical fixes

**When NOT to Update:**
- Minor style or formatting changes
- Documentation-only updates (unless substantive)
- Test-only commits with no production changes
- Dependency version bumps without notable behavior changes

**Format Guidelines:**
- Keep entries concise - 8 bullet points maximum per day
- Use brief, imperative language (e.g., "Fix double-load on first search character")
- Group changes by date (one date header per day of work)
- Include affected components/features for context
- Example:
  ```
  ## 2025-11-22
  - Fixed double-load on first search character in developer list (debounce trailing edge)
  ```

### 2. Build Tailwind CSS for production

```bash
python3 manage.py tailwind build
```

### 3. Minify JavaScript files

```bash
./scripts/minify_js.sh
```

### 4. Collect static files

```bash
python3 manage.py collectstatic --noinput
```

### 5. Stage all changes

```bash
git add -A
```

### 6. Commit with descriptive message

```bash
git commit -m "Your commit message here"
```

### 7. Push to main branch

```bash
git push origin main
```

**STOP HERE** - Do NOT push to Heroku unless explicitly asked to deploy.

## Pre-commit Hook Handling

Pre-commit hooks will run tests and enforce code quality before allowing the commit.

**If pre-commit hooks fail**: Fix issues immediately, do NOT skip or work around them:
- **Coverage failures**: Add tests or proper exclusions (not workarounds)
- **Linting failures**: Fix the code to comply with standards
- **Test failures**: Fix the failing tests or broken code

Commits will be blocked if any tests fail, coverage drops below 95%, or linting fails.
