<script lang="ts">
	import { goto } from '$app/navigation';
	import Config from '$lib/Config.svelte';

	function handleBack() {
		goto('/');
	}
</script>

<Config onBack={handleBack} /> 