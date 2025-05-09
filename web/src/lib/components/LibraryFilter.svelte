<script lang="ts">
	import { onMount } from 'svelte';
	import { _ } from 'svelte-i18n';

	import { Button } from '$lib/components/ui/button/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Popover from '$lib/components/ui/popover/index.js';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import { PUBLIC_API_ENDPOINT } from '$env/static/public';

	const apiEndpoint =
		(typeof PUBLIC_API_ENDPOINT !== 'undefined' ? PUBLIC_API_ENDPOINT : window.location.origin) + '/api';

	async function fetchLibraries() {
		try {
			const response = await fetch(`${apiEndpoint}/libraries`);
			if (!response.ok) {
				throw new Error('Failed to fetch libraries');
			}
			const libraries = await response.json();
			return libraries;
		} catch (error) {
			console.error('Error fetching libraries:', error);
			return [];
		}
	}

	let { selectedLibraryIds = $bindable([]) } = $props();

	function addLibraryId(id: string) {
		selectedLibraryIds = libraries.length === selectedLibraryIds.length + 1 ? [] : [...selectedLibraryIds, id];
	}
	
	function removeLibraryId(id: string) {
		selectedLibraryIds = selectedLibraryIds.filter((i) => i !== id);
	}

	let libraries: { id: number; name: string }[] = $state([]);
	let allSelected = $derived(selectedLibraryIds.length === 0);
	let displayName = $derived(selectedLibraryIds.length > 0 ? selectedLibraryIds.map((id) => libraries.find(lib => lib.id === id)?.name).join(', ') : $_('libraryFilter.all'));

	async function toggleSelectAll() {
		selectedLibraryIds = [];
	}

	// Fetch libraries when the component is mounted
	onMount(async () => {
		libraries = await fetchLibraries();
	});

	$inspect(selectedLibraryIds);
</script>

<div>
	<Popover.Root>
		<Popover.Trigger>
			<Button
				class="border p-2 text-xs font-medium focus:outline-none"
				size="sm"
				variant="outline">
				{displayName}
			</Button>
		</Popover.Trigger>
		<Popover.Content class="w-56 mt-1 p-1" align="start" side="bottom">
			<div class="px-2 py-1.5 text-sm font-semibold">
				<Label class="text-sm font-semibold">{$_('libraryFilter.repositoryFilter')}</Label>
			</div>
			<Separator class="my-1" />
			<div class="px-2 py-1.5">
				<div class="mb-2 items-top flex space-x-2">
						<Checkbox id="all-selected" bind:checked={allSelected} disabled={allSelected} onCheckedChange={toggleSelectAll} />
						<Label for="all-selected" class="flex items-center text-sm">{$_('libraryFilter.selectAll')}</Label>
				</div>
				{#each libraries as library (library.id)}
					{@const checked = selectedLibraryIds.includes(library.id)}
					<div class="mb-2 items-top flex space-x-2">
						<Checkbox
							id={`library-${library.id}`}
							name="library-select"
							value={library.id}
							{checked}
							onCheckedChange={(v) => {
								if (v) {
								  addLibraryId(library.id);
								} else {
								  removeLibraryId(library.id);
								}
							}}
						/>
						<Label for={`library-${library.id}`} class="flex items-center text-sm">{library.name}#{library.id}</Label>
					</div>
				{/each}
			</div>
		</Popover.Content>
	</Popover.Root>
</div>
