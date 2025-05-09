<script lang="ts">
	import { Copy, Check } from '@lucide/svelte';

	let { text } = $props();

	let copied = $state(false);

	/**
	 * Copy text to clipboard and change icon
	 * @param {string} text
	 */
	function handleCopyClick(text) {
		navigator.clipboard.writeText(text).then(() => {
			copied = true;
			setTimeout(() => {
				copied = false;
			}, 2000);
		}).catch(err => {
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