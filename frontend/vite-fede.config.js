import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import replace from '@rollup/plugin-replace';
import { resolve } from 'path';
import path from 'path';
import { createFilter } from '@rollup/pluginutils';
import cssInjectedByJsPlugin from 'vite-plugin-css-injected-by-js';

function replaceVuePlugin() {
    const filter = createFilter(['**/*.js', '**/*.ts']);

    return {
        name: 'replace-vue-plugin',
        transform(code, id) {
            if (filter(id)) {
                // Replace 'Vue' with 'VueApp'
                const transformedCode = code.replace(/Vue/g, 'VueApp');
                return {
                    code: transformedCode,
                    map: null,
                };
            }
            return null;
        },
    };
}

export default async () => {
    return defineConfig({
        plugins: [
            vue(),
            replace({
                'process.env.NODE_ENV': JSON.stringify('production'),
                preventAssignment: true,
            }),
            replaceVuePlugin(),
            cssInjectedByJsPlugin({ styleId: 'embed-styles' }),
        ],

        build: {
            target: 'esnext',
            minify: false,
            cssCodeSplit: false,
            sourcemap: false,

            emptyOutDir: false,
            outDir: 'dist/bundle',

            lib: {
                entry: resolve(__dirname, 'src/subAppEntry.js'),
                name: 'index',
                fileName: 'index',
                formats: ['es'],
            },
        },

        resolve: {
            alias: [
                {
                    find: '@',
                    replacement: path.resolve(__dirname, 'src'),
                },
            ],
        },
    });
};
