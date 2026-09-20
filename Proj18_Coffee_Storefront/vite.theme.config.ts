import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The same app, built as the two plain files a Shopify theme serves from its assets folder. One script and one
// stylesheet with fixed names (the theme's layout refers to them), no code splitting, and the public folder (the
// favicon) copied alongside. Run with `npm run build:theme`, then push the theme folder.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'theme/assets',
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: 'src/main.tsx',
      output: {
        entryFileNames: 'coffee-storefront.js',
        assetFileNames: 'coffee-storefront.[ext]',
        inlineDynamicImports: true,
      },
    },
  },
});
