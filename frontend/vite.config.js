import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ command }) => {
    return {
        base: command === 'build' ? '/static/' : '/',
        plugins: [vue()],
        resolve: {
            extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json', '.vue'],
            alias: {
                '@': fileURLToPath(new URL('./src', import.meta.url))
            }
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
    };
});
