import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		adapter: adapter({
			pages: '../memos/static',
			assets: '../memos/static',
			precompress: false,
			strict: true,
			fallback: 'app.html' // may differ from host to host
		})
	}
};

export default config;
