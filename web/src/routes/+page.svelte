<script lang="ts">
	import Figure from '$lib/Figure.svelte';
	import TimeFilter from '$lib/components/TimeFilter.svelte';
	import LibraryFilter from '$lib/components/LibraryFilter.svelte';
	import { Input } from '$lib/components/ui/input';
	import { PUBLIC_API_ENDPOINT } from '$env/static/public';
	import FacetFilter from '$lib/components/FacetFilter.svelte';
	import { formatDistanceToNow } from 'date-fns';
	import Logo from '$lib/components/Logo.svelte';
	import { onMount } from 'svelte';
	import { translateAppName } from '$lib/utils';
	import LucideIcon from '$lib/components/LucideIcon.svelte';
	import LanguageSwitcher from '$lib/LanguageSwitcher.svelte';
	import { _ } from 'svelte-i18n';
	import { Github } from 'lucide-svelte';
	import { Skeleton } from '$lib/components/ui/skeleton';

	let searchString = '';
	let isLoading = false;
	let showModal = false;
	let selectedImage = 0;

	let startTimestamp: number | null = null;
	let endTimestamp: number | null = null;

	let selectedLibraries: number[] = [];
	let searchResult: SearchResult | null = null;

	interface FacetCount {
		value: string;
		count: number;
	}

	interface Facet {
		field_name: string;
		counts: FacetCount[];
	}

	interface SearchResult {
		hits: any[];
		facet_counts: Facet[];
		found: number;
		out_of: number;
		search_time_ms: number;
	}

	let selectedAppNames: Record<string, boolean> = {};
	let selectedDates: Record<string, boolean> = {};

	const apiEndpoint =
		(typeof PUBLIC_API_ENDPOINT !== 'undefined' ? PUBLIC_API_ENDPOINT : window.location.origin) + '/api';

	let facetCounts: Facet[] | null = null;

	let isScrolled = false;
	let headerElement: HTMLElement;

	let currentAbortController: AbortController | null = null;

	let debounceTimer: ReturnType<typeof setTimeout>;

	// 添加一个计算属性来生成输入框的类名
	$: inputClasses = `w-full p-2 transition-all duration-300 ${
		!isScrolled ? 'mt-4' : ''
	}`;

	onMount(() => {
		const handleScroll = () => {
			if (window.scrollY > 100) {
				isScrolled = true;
			} else if (isScrolled && window.scrollY < 20) {
				isScrolled = false;
			}
		};

		window.addEventListener('scroll', handleScroll);

		return () => {
			window.removeEventListener('scroll', handleScroll);
		};
	});

	interface SearchParams {
		query: string;
		start: number | null;
		end: number | null;
		selectedLibraries: number[];
		selectedAppNames: string[];
		selectedDates: string[];
	}

	function buildSearchUrl(params: SearchParams): string {
		const searchParams = new URLSearchParams();
		searchParams.append('q', params.query);

		if (params.start != null && params.start > 0) {
			searchParams.append('start', Math.floor(params.start / 1000).toString());
		}
		if (params.end != null && params.end > 0) {
			searchParams.append('end', Math.floor(params.end / 1000).toString());
		}
		if (params.selectedLibraries.length > 0) {
			searchParams.append('library_ids', params.selectedLibraries.join(','));
		}
		if (params.selectedAppNames.length > 0) {
			searchParams.append('app_names', params.selectedAppNames.join(','));
		}
		if (params.selectedDates.length > 0) {
			searchParams.append('created_dates', params.selectedDates.join(','));
		}

		return `${apiEndpoint}/search?${searchParams.toString()}`;
	}

	async function searchItems(
		query: string,
		start: number | null,
		end: number | null,
		selectedLibraries: number[],
		selectedAppNames: string[],
		selectedDates: string[],
		updateFacets: boolean = false
	) {
		// Cancel any ongoing request
		if (currentAbortController) {
			currentAbortController.abort();
		}
		
		// Create new abort controller for this request
		currentAbortController = new AbortController();
		isLoading = true;

		try {
			const url = buildSearchUrl({
				query,
				start,
				end,
				selectedLibraries,
				selectedAppNames,
				selectedDates
			});
			const response = await fetch(url, {
				signal: currentAbortController.signal
			});
			if (!response.ok) {
				throw new Error('Network response was not ok');
			}
			const result = await response.json();
			if (updateFacets) {
				facetCounts = result.facet_counts;
				selectedAppNames = Object.fromEntries(
					result.facet_counts
						.find((f) => f.field_name === 'app_names')
						?.counts.map((t) => [t.value, false]) || []
				);
				selectedDates = Object.fromEntries(
					result.facet_counts
						.find((f) => f.field_name === 'created_date')
						?.counts.map((d) => [d.value, false]) || []
				);
			}
			searchResult = {
				...result,
				facet_counts: updateFacets ? result.facet_counts : facetCounts
				// Add other properties as needed
			};
			console.log(searchResult);
		} catch (error) {
			// Only log error if it's not an abort error
			if (error instanceof Error && error.name !== 'AbortError') {
				console.error('Search error:', error);
			}
		} finally {
			isLoading = false;
			if (currentAbortController) {
				currentAbortController = null;
			}
		}
	}

	function handleFiltersChange() {
		// Clear any existing timer
		if (debounceTimer) {
			clearTimeout(debounceTimer);
		}

		// Set a new timer
		debounceTimer = setTimeout(() => {
			if (!isLoading) {
				searchItems(
					searchString,
					startTimestamp,
					endTimestamp,
					selectedLibraries,
					Object.keys(selectedAppNames).filter((app_name) => selectedAppNames[app_name]),
					Object.keys(selectedDates).filter((date) => selectedDates[date]),
					false
				);
			}
		}, 300);
	}

	$: [startTimestamp, endTimestamp], handleFiltersChange();
	$: selectedLibraries, handleFiltersChange();

	function handleAppNameChange(app_name: string, checked: boolean) {
		selectedAppNames[app_name] = checked;
		handleFiltersChange();
	}

	function handleDateChange(date: string, checked: boolean) {
		selectedDates[date] = checked;
		handleFiltersChange();
	}

	/**
	 * @param {string} path
	 */
	function filename(path: string): string {
		let splits = path.split('/');
		return splits[splits.length - 1];
	}

	/**
	 * @param {number} index
	 */
	function openModal(index: number) {
		showModal = true;
		selectedImage = index;
		disableScroll();
	}

	function closeModal() {
		showModal = false;
		enableScroll();
	}

	/**
	 * @param {{ key: string; }} event
	 */
	function handleKeydown(event: KeyboardEvent) {
		if (showModal && searchResult) {
			if (event.key === 'Escape') {
				closeModal();
			} else if (event.key === 'ArrowRight') {
				selectedImage = (selectedImage + 1) % searchResult.hits.length;
			} else if (event.key === 'ArrowLeft') {
				selectedImage = (selectedImage - 1 + searchResult.hits.length) % searchResult.hits.length;
			}
		}
	}

	const disableScroll = () => {
		document.body.style.overflow = 'hidden';
	};

	const enableScroll = () => {
		document.body.style.overflow = '';
	};

	function handleEnterPress(event: KeyboardEvent) {
		if (event.key === 'Enter' && !isLoading) {
			event.preventDefault();
			selectedAppNames = {};
			searchItems(
				searchString,
				startTimestamp,
				endTimestamp,
				selectedLibraries,
				Object.keys(selectedAppNames).filter((tag) => selectedAppNames[tag]),
				Object.keys(selectedDates).filter((date) => selectedDates[date]),
				true
			);
		}
	}

	// Add this function near the top of the <script> section
	function getEntityTitle(document: any): string {
		if (document.metadata_entries && 
			document.metadata_entries.some((entry: any) => entry.key === 'active_window')) {
			return document.metadata_entries.find((entry: any) => entry.key === 'active_window').value;
		}
		return filename(document.filepath);
	}

	function getAppName(document: any): string {
		if (document.metadata_entries && document.metadata_entries.some((entry: any) => entry.key === 'active_app')) {
			return document.metadata_entries.find((entry: any) => entry.key === 'active_app').value;
		} else {
			return "unknown";
		}
	}

</script>

<svelte:head>
	<title>Pensieve {searchString ? `- ${searchString}` : ''}</title>
</svelte:head>

<svelte:window on:keydown={handleKeydown} />

<!-- 添加一个最外层的容器来管理整体布局 -->
<div class="min-h-screen flex flex-col">
	<!-- Header 部分 -->
	<header
		class="sticky top-0 z-10 transition-all duration-300"
		bind:this={headerElement}
	>
		<div class="mx-auto max-w-screen-lg flex items-center justify-between p-4 transition-all duration-300"
			 class:flex-col={!isScrolled}
			 class:flex-row={isScrolled}
		>
			<Logo size={isScrolled ? 32 : 128} withBorder={!isScrolled} hasGap={!isScrolled} class_="transition-transform duration-300 ease-in-out mr-4" />
			<div class="flex {inputClasses}">
				<Input
					type="text"
					class="w-full text-lg border-gray-500"
					bind:value={searchString}
					placeholder={$_('searchPlaceholder')}
					on:keydown={handleEnterPress}
					autofocus
				/>
			</div>
			<div class="mx-auto max-w-screen-lg">
				<div class="flex space-x-2" class:mt-4={!isScrolled} class:ml-4={isScrolled}>
					<LibraryFilter bind:selectedLibraryIds={selectedLibraries} />
					<TimeFilter bind:start={startTimestamp} bind:end={endTimestamp} />
				</div>
			</div>
		</div>
	</header>

	<!-- 添加一个动态调整高度的空白区域 -->
	<div style="height: {isScrolled ? '100px' : '0px'}"></div>

	<!-- 主要内容区域 -->
	<main class="flex-grow">
		<div class="mx-auto flex flex-col sm:flex-row">
			<!-- 左侧面板 -->
			{#if searchResult && searchResult.facet_counts && searchResult.facet_counts.length > 0}
				<div class="xl:w-1/7 lg:w-1/6 md:w-1/5 sm:w-full pr-4">
					{#each searchResult.facet_counts as facet}
						{#if facet.field_name === 'app_names' || facet.field_name === 'created_date'}
							<FacetFilter
								{facet}
								selectedItems={facet.field_name === 'app_names' ? selectedAppNames : selectedDates}
								onItemChange={facet.field_name === 'app_names' ? handleAppNameChange : handleDateChange}
							/>
						{/if}
					{/each}
				</div>
			{/if}

			<!-- 右侧面板 -->
			<div class="{searchResult && searchResult.facet_counts && searchResult.facet_counts.length > 0 ? 'xl:w-6/7 lg:w-5/6 md:w-4/5' : 'w-full'}">
				{#if isLoading}
					<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
						{#each Array(8) as _}
							<div class="bg-white rounded-lg overflow-hidden border border-gray-300">
								<div class="px-4 pt-4">
									<Skeleton class="h-4 w-3/4 mb-2" />
									<Skeleton class="h-4 w-1/2" />
									<Skeleton class="h-3 w-1/4 mt-2" />
								</div>
								<div class="px-4 pt-4 pb-4">
									<Skeleton class="w-full h-48" />
								</div>
							</div>
						{/each}
					</div>
				{:else if searchResult && searchResult.hits.length > 0}
					{#if searchResult['search_time_ms'] > 0}
						<p class="search-summary mb-4 text-center">
							{$_('searchSummary', { values: {
								found: searchResult['found'].toLocaleString(),
								outOf: searchResult['out_of'].toLocaleString(),
								time: searchResult['search_time_ms']
							}})}
						</p>
					{/if}
					<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
						{#each searchResult.hits as hit, index}
							<!-- svelte-ignore a11y-click-events-have-key-events -->
							<!-- svelte-ignore a11y-no-static-element-interactions -->
							<div
								class="bg-white rounded-lg overflow-hidden border border-gray-300 relative"
								on:click={() => openModal(index)}
							>
								<div class="px-4 pt-4">
									<h2 class="line-clamp-2 h-12">
										{getEntityTitle(hit.document)}
									</h2>
									<p class="text-gray-700 text-xs">
										{formatDistanceToNow(new Date(hit.document.file_created_at * 1000), {
											addSuffix: true
										})}
									</p>
								</div>
								<figure class="px-4 pt-4 mb-4 relative">
									<img
										class="w-full h-48 object-cover"
										src={`${apiEndpoint}/thumbnails/${hit.document.filepath.replace(/^\/+/, '')}`}
										alt=""
									/>
									{#if getAppName(hit.document) !== "unknown"}
										<div
											class="absolute bottom-2 left-6 bg-white bg-opacity-75 px-2 py-1 rounded-full text-xs font-semibold border border-gray-200 flex items-center space-x-2"
										>
											<LucideIcon name={translateAppName(getAppName(hit.document)) || "Hexagon"} size={16} />
											<span>{getAppName(hit.document)}</span>
										</div>
									{/if}
								</figure>
							</div>
						{/each}
					</div>
				{:else if searchResult}
					<div class="flex justify-center items-center min-h-[200px]">
						<p>{$_('noResults')}</p>
					</div>
				{:else}
					<div class="flex justify-center items-center min-h-[200px]">
						<p></p>
					</div>
				{/if}
			</div>
		</div>
	</main>

	<!-- Footer -->
	<footer class="w-full mx-auto mt-8">
		<div class="container mx-auto">
			<div class="border-t border-slate-900/5 py-10 text-center">
				<p class="mt-2 text-sm leading-6 text-slate-500">{$_('slogan')}</p>
				<p class="mt-2 text-sm leading-6 text-slate-500">{$_('copyright')}</p>
				<div class="mt-2 flex justify-center items-center space-x-4 text-sm font-semibold leading-6 text-slate-700">
					<a href="https://github.com/arkohut/memos" 
					   target="_blank" 
					   rel="noopener noreferrer"
					   class="hover:text-slate-900 transition-colors">
						<Github size={16} />
					</a>
					<div class="h-4 w-px bg-slate-500/20" />
					<LanguageSwitcher />
				</div>
			</div>
		</div>
	</footer>
</div>

{#if searchResult && searchResult.hits.length && showModal}
	<Figure
		id={searchResult.hits[selectedImage].document.id}
		library_id={searchResult.hits[selectedImage].document.library_id}
		folder_id={searchResult.hits[selectedImage].document.folder_id}
		image={`${apiEndpoint}/files/${searchResult.hits[selectedImage].document.filepath.replace(/^\/+/, '')}`}
		video={`${apiEndpoint}/files/video/${searchResult.hits[selectedImage].document.filepath.replace(/^\/+/, '')}`}
		created_at={searchResult.hits[selectedImage].document.file_created_at * 1000}
		filepath={searchResult.hits[selectedImage].document.filepath}
		title={getEntityTitle(searchResult.hits[selectedImage].document)}
		app_name={getAppName(searchResult.hits[selectedImage].document)}
		tags={searchResult.hits[selectedImage].document.tags}
		metadata_entries={searchResult.hits[selectedImage].document.metadata_entries}
		onClose={closeModal}
		onNext={() => searchResult && openModal((selectedImage + 1) % searchResult.hits.length)}
		onPrevious={() =>
			searchResult &&
			openModal((selectedImage - 1 + searchResult.hits.length) % searchResult.hits.length)}
	/>
{/if}
