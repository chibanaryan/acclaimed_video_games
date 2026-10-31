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
venv/bin/python manage.py tailwind build
```

Use the venv's interpreter throughout: a bare `python3` is whatever the
shell finds first, not the Python and packages production runs.

### 3. Minify JavaScript files

```bash
./scripts/minify_js.sh
```

### 4. Fetch main

```bash
git fetch origin
```

So the review's `git diff origin/main` is against the real `main`. There is
no local `collectstatic` step: `staticfiles/` is gitignored and Heroku runs
it on every build, and CI's `production-install` job renders pages under the
manifest storage, which is what a local run used to catch.

### 5. Review the change

Every ticket's work gets a `/code-review` pass before it reaches `main`.
Pushing to `main` is the merge in this repo, so this step is the review
gate.

Invoke the `code-review` skill at `high`, naming the level so it does not
reuse whatever level was typed last. Review everything that will land on
`main`: the working-tree changes **and** any commits on this branch not yet
on `origin/main` (`git diff origin/main` covers both).

- **Answer every finding.** Fix it, or say in chat why it is a false
  positive or out of scope. Never drop one silently.
- **Re-review after fixing.** Run it again on the new diff, with no limit
  on rounds, until one comes back with nothing left to answer. Any code
  changed since the last round gets another, even a small fix made after
  the review. A finding already waived does not need answering twice.
- **Skip only when** the user explicitly says so ("commit without
  review"), or the diff touches no code or templates (DEVLOG or docs
  only). Say in chat that the review was skipped and why.
- **Report it.** The final message carries one line:
  "Reviewed at high: N findings, N fixed, N waived (reasons)".

### 6. Stage the change

```bash
git status --short
```

Read the list before staging: anything you did not mean to change (a
scratch file, a local database, a `.env`) stays out. Then stage tracked
changes and add new files by path:

```bash
git add -u
git add path/to/new_file.py
```

### 7. Commit with descriptive message

```bash
git commit -m "Your commit message here"
```

### 8. Push to main branch

Work happens on a branch (a Conductor worktree), so push its commit to
`main`:

```bash
git push origin HEAD:main
```

If the push is rejected because `main` moved meanwhile, rebase onto it,
re-run the tests, and push again:

```bash
git fetch origin && git rebase origin/main
venv/bin/pytest
git push origin HEAD:main
```

**STOP HERE** - Do NOT push to Heroku unless explicitly asked to deploy.

## Pre-commit Hook Handling

Pre-commit hooks will run tests and enforce code quality before allowing the commit.
They run after the review (step 5), so they test the reviewed and fixed code.

**If pre-commit hooks fail**: Fix issues immediately, do NOT skip or work around them:
- **Coverage failures**: Add tests or proper exclusions (not workarounds)
- **Linting failures**: Fix the code to comply with standards
- **Test failures**: Fix the failing tests or broken code

Commits will be blocked if any tests fail, coverage drops below 100%, or linting fails.
