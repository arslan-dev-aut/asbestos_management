import { defineConfig, createFilter } from 'vite';
import vue from '@vitejs/plugin-vue';
import replace from '@rollup/plugin-replace';
import cssInjectedByJsPlugin from 'vite-plugin-css-injected-by-js';
import path from 'path';

function replaceVuePlugin() {
  const filter = createFilter(['**/*.js', '**/*.ts']);

  return {
    name: 'replace-vue-plugin',
    transform(code, id) {
      if (filter(id) && !id.includes('ScriptAllocate.js')) {
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

// https://vitejs.dev/config/
export default () => {
  return defineConfig({
    plugins: [
      replace({
        'process.env.NODE_ENV': JSON.stringify('production'),
        preventAssignment: true,
      }),
      vue(),
      cssInjectedByJsPlugin(),
      replaceVuePlugin(),
    ],

    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
  });
};
