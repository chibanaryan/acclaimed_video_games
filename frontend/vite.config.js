import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ command }) => ({
    base: command === 'build' ? '/static/' : '/',
    plugins: [vue()],
    resolve: {
        extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json', '.vue'],
        alias: {
            '@': fileURLToPath(new URL('./src', import.meta.url))
        }
    },
    ssgOptions: {
        formatting: 'minify',
        format: 'cjs',
        // Define which routes to pre-render during build
        async includedRoutes(paths, routes) {
            const dynamicRoutes = [];
            const apiUrl = process.env.VITE_SSG_API_URL || 'http://127.0.0.1:8000/api/';

            try {
                console.log('Fetching dynamic routes from:', apiUrl);

                // Fetch game slugs (limit to 10 for testing SSG)
                const gamesResponse = await fetch(`${apiUrl}games/?limit=10`);
                if (gamesResponse.ok) {
                    const gamesData = await gamesResponse.json();
                    gamesData.results.forEach(game => {
                        dynamicRoutes.push(`/game/${game.slug}/`);
                    });
                    console.log(`Added ${gamesData.results.length} game routes`);
                }

                // Fetch developer slugs (limit to 5 for testing SSG)
                const devsResponse = await fetch(`${apiUrl}developers/?limit=5`);
                if (devsResponse.ok) {
                    const devsData = await devsResponse.json();
                    devsData.results.forEach(dev => {
                        dynamicRoutes.push(`/developers/${dev.slug}/`);
                    });
                    console.log(`Added ${devsData.results.length} developer routes`);
                }
            } catch (error) {
                console.warn('Warning: Could not fetch dynamic routes from API:', error.message);
                console.warn('Make sure Django dev server is running at:', apiUrl);
            }

            // Include all static routes (those without dynamic parameters)
            const staticRoutes = paths.filter(p => !p.includes(':'));

            const allRoutes = [...staticRoutes, ...dynamicRoutes];
            console.log(`Total routes to pre-render: ${allRoutes.length}`);

            return allRoutes;
        },
    },
    test: {
        environment: 'jsdom',
        globals: true,
        setupFiles: './src/test/setup.js',
        coverage: {
            reporter: ['text', 'html'],
            provider: 'v8',
            thresholds: {
                statements: 95,
                branches: 95,
                functions: 95,
                lines: 95,
            },
        },
    }
}));
