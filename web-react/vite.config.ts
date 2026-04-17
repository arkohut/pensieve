import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import { TanStackRouterVite } from '@tanstack/router-plugin/vite';
import path from 'node:path';

const vendorChunks = [
  {
    name: 'react-vendor',
    packages: ['/react/', '/react-dom/', '/scheduler/'],
  },
  {
    name: 'tanstack-vendor',
    packages: ['/@tanstack/'],
  },
  {
    name: 'i18n-vendor',
    packages: ['/i18next/', '/react-i18next/'],
  },
  {
    name: 'ui-vendor',
    packages: ['/@radix-ui/', '/lucide-react/', '/sonner/', '/next-themes/'],
  },
] as const;

export default defineConfig({
  plugins: [TanStackRouterVite({ target: 'react', autoCodeSplitting: true }), react()],
  resolve: {
    alias: { $: path.resolve(__dirname, './src') },
  },
  build: {
    outDir: '../memos/static',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('/node_modules/')) return;

          for (const chunk of vendorChunks) {
            if (chunk.packages.some((packageName) => id.includes(packageName))) {
              return chunk.name;
            }
          }
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8839', changeOrigin: true },
    },
  },
});
