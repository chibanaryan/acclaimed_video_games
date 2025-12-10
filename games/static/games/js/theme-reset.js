/**
 * Theme Reset Utility
 *
 * Run this in browser console if theme issues persist:
 *
 * To reset theme:
 *   resetTheme()
 *
 * To view current theme status:
 *   checkTheme()
 */

function resetTheme() {
    console.group('🎨 Theme Reset');

    // Remove all theme-related keys
    const themeKeys = ['theme', 'admin-theme', 'theme-preference'];
    const removed = [];

    themeKeys.forEach(key => {
        if (localStorage.getItem(key)) {
            removed.push(key + ': ' + localStorage.getItem(key));
            localStorage.removeItem(key);
        }
    });

    if (removed.length > 0) {
        console.log('Removed stale theme values:');
        removed.forEach(item => console.log('  -', item));
    } else {
        console.log('No stale theme values found');
    }

    // Set fresh theme based on system preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const newTheme = prefersDark ? 'forest' : 'lofi';

    localStorage.setItem('theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);

    console.log('✅ Theme reset to:', newTheme);
    console.log('🔄 Reload page to see changes');
    console.groupEnd();

    return newTheme;
}

function checkTheme() {
    console.group('🎨 Theme Status');

    // Check localStorage
    console.log('LocalStorage:');
    ['theme', 'admin-theme', 'theme-preference'].forEach(key => {
        const value = localStorage.getItem(key);
        if (value) {
            const isValid = value === 'lofi' || value === 'forest';
            console.log(`  ${key}: "${value}" ${isValid ? '✅' : '❌ INVALID'}`);
        }
    });

    // Check current document theme
    const currentTheme = document.documentElement.getAttribute('data-theme');
    console.log('\nCurrent document theme:', currentTheme);

    // Check system preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    console.log('System preference:', prefersDark ? 'dark (forest)' : 'light (lofi)');

    // Available themes
    console.log('\nValid themes:');
    console.log('  - lofi (light theme)');
    console.log('  - forest (dark theme)');

    console.groupEnd();
}

// Make functions available globally
window.resetTheme = resetTheme;
window.checkTheme = checkTheme;

console.info('🎨 Theme utilities loaded. Run checkTheme() or resetTheme() in console if needed.');
