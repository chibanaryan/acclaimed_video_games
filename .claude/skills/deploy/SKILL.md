---
name: deploy
description: Deploy to Heroku production. Use when asked to deploy, push to production, or push to Heroku.
---

# Complete Deployment Workflow

Use this workflow when making changes that need to be deployed to production.

**Production URL:** https://www.acclaimedvideogames.com/

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

### 2. Build Tailwind CSS for production

```bash
python3 manage.py tailwind build
```

### 3. Collect static files

```bash
python3 manage.py collectstatic --noinput
```

### 4. Stage all changes

```bash
git add -A
```

### 5. Commit with descriptive message

```bash
git commit -m "Your commit message here"
```

### 6. Push to main branch

```bash
git push origin main
```

### 7. Deploy to Heroku

```bash
git push heroku main
```

## Pre-commit Hook Handling

Pre-commit hooks will run tests and enforce code quality before allowing the commit.

**If pre-commit hooks fail**: Fix issues immediately, do NOT skip or work around them:
- **Coverage failures**: Add tests or proper exclusions (not workarounds)
- **Linting failures**: Fix the code to comply with standards
- **Test failures**: Fix the failing tests or broken code

Commits will be blocked if any tests fail, coverage drops below 95%, or linting fails.
