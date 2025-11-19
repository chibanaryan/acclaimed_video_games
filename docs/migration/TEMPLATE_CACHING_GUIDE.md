# Django Template Caching Guide

## Why Templates Get Cached

Django caches templates at multiple levels:

1. **Template Loader Cache** - Django caches compiled templates in memory
2. **Browser Cache** - Your browser caches the HTML response
3. **Python Bytecode Cache** - `__pycache__` files can affect imports
4. **Django's Cached Template Loader** - If enabled, aggressively caches templates

## When Hard Refresh Isn't Enough

A hard refresh (Cmd+Shift+R / Ctrl+Shift+R) only clears:
- ✅ Browser cache
- ✅ CSS/JS cache

It does NOT clear:
- ❌ Django's in-memory template cache
- ❌ Django's compiled template cache
- ❌ Python's import cache

## When to Restart the Server

**Restart Django server when:**
- Template files are changed (`.html` files)
- Template tags/filters are modified
- Template context processors change
- You see old content despite hard refresh
- Template includes/extends aren't updating

**Hard refresh is enough for:**
- CSS changes (if loaded from static files)
- JavaScript changes (if loaded from static files)
- Image changes
- Content changes that come from the database (not templates)

## How to Avoid Template Caching Issues

### 1. Check Your Template Loaders

In `settings.py`, make sure you're using the filesystem loader (not cached loader) in development:

```python
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [...],
        'APP_DIRS': True,
        'OPTIONS': {
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
            # Don't use cached loader in development!
            # 'loaders': [
            #     ('django.template.loaders.cached.Loader', [
            #         'django.template.loaders.filesystem.Loader',
            #         'django.template.loaders.app_directories.Loader',
            #     ]),
            # ],
        },
    },
]
```

### 2. Development Best Practices

**Option A: Auto-restart on template changes (Recommended)**

Use a file watcher that restarts Django when templates change:

```bash
# Using watchdog (install: pip install watchdog)
watchmedo auto-restart --patterns="*.html" --recursive --directory=beta/templates -- python manage.py runserver

# Or use django-extensions (already installed)
python manage.py runserver_plus --reloader
```

**Option B: Manual restart workflow**

1. Make template changes
2. Save file
3. **Always restart server** after template changes:
   ```bash
   # Stop: Ctrl+C
   # Start: python manage.py runserver
   ```
4. Then hard refresh browser

**Option C: Clear Python cache**

If templates still don't update, clear Python's bytecode cache:

```bash
find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null
find . -name "*.pyc" -delete
python manage.py runserver
```

### 3. Check if Templates Are Being Cached

To verify Django is finding your templates:

```bash
python manage.py shell
```

```python
from django.template.loader import get_template
t = get_template('base.html')
print(t.origin)  # Should show the file path
```

### 4. Development Settings

Make sure `DEBUG=True` in development (it should auto-reload, but sometimes doesn't catch template changes immediately).

### 5. Quick Restart Script

Create a script to quickly restart:

```bash
#!/bin/bash
# restart-django.sh
pkill -f "manage.py runserver"
sleep 1
python manage.py runserver
```

## Why This Happened

In your case, the template file had the correct content, but Django was serving a cached version. This can happen when:
- The server has been running for a long time
- Multiple template files were changed
- Django's auto-reload didn't catch the changes
- There's a race condition in template loading

## Recommended Workflow

1. **Make template changes**
2. **Save the file**
3. **Restart Django server** (Ctrl+C, then `python manage.py runserver`)
4. **Hard refresh browser** (Cmd+Shift+R / Ctrl+Shift+R)

This ensures both Django's cache and browser cache are cleared.

## Alternative: Use Django's Auto-Reload

Django's development server should auto-reload on template changes, but it's not 100% reliable. If you want to force it:

1. Touch the template file: `touch beta/templates/base.html`
2. Or make a small change (add/remove a space) and save again
3. Django should detect the file change and reload

But the most reliable method is still: **restart the server after template changes**.

