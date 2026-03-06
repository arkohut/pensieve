<script lang="ts">
	import { Copy, Check } from '@lucide/svelte';

	let { text } = $props();

	let copied = $state(false);

	function normalizeText(value: unknown): string {
		return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
	}

	/**
	 * Copy text to clipboard and change icon
	 * @param {string} text
	 */
	function handleCopyClick(text: unknown) {
		navigator.clipboard
			.writeText(normalizeText(text))
			.then(() => {
				copied = true;
				setTimeout(() => {
					copied = false;
				}, 2000);
			})
			.catch((err) => {
				console.error('Failed to copy text: ', err);
			});
	}
</script>

<button class="ml-2 flex items-center" onclick={() => handleCopyClick(text)}>
	{#if copied}
		<Check size={20} />
	{:else}
		<Copy size={20} />
	{/if}
</button>
