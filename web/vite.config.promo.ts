import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import path from 'node:path';

// Promo screenshot / future-Remotion site — independent static build, no TanStack Router.
//   - root: src/promo  → its index.html serves at `/` in dev and lands at dist-promo root.
//   - base: './'       → relative asset paths, so dist-promo/index.html opens from a file:// URL.
// PostCSS/Tailwind apply automatically: postcss.config.js is found by searching upward from
// root, and tailwind.config content globs (./src/**) resolve against the web/ cwd.
export default defineConfig({
  root: path.resolve(__dirname, 'src/promo'),
  base: './',
  plugins: [react()],
  resolve: {
    alias: { $: path.resolve(__dirname, './src') },
  },
  build: {
    outDir: path.resolve(__dirname, 'dist-promo'),
    emptyOutDir: true,
  },
});
