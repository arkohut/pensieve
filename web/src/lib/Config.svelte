<script lang="ts">
	import { onMount } from 'svelte';
	import { PUBLIC_API_ENDPOINT } from '$env/static/public';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Save, RotateCw, ArrowLeft, ChevronUp, ChevronDown } from 'lucide-svelte';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { toast } from 'svelte-sonner';
	import { Textarea } from '$lib/components/ui/textarea';
	import { _ } from 'svelte-i18n';
	import HealthCheck from './HealthCheck.svelte';
	import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "$lib/components/ui/collapsible";

	export let onBack: () => void;

	const apiEndpoint =
		(typeof PUBLIC_API_ENDPOINT !== 'undefined' ? PUBLIC_API_ENDPOINT : window.location.origin) + '/api';

	let config: any = null;
	let loading = true;
	let saving = false;
	let error: string | null = null;
	let changes: any = {};

	let showRestartConfirm = false;
	
	let servicesRestarting = false;
	
	let healthCheckComponent: HealthCheck;

	let uiState = {
		inputsDisabled: {
			ocr: false,
			embedding: false
			// You can add more features to track here
		},
		pluginDisabled: {
			ocr: false,
			vlm: false
		}
	};

	// Section collapse state
	let sectionCollapsed = {
		general: false,
		serve: false,
		record: false,
		watch: false,
		ocr: false,
		vlm: false,
		embedding: false
	};

	let isInitialized = false;

	let isScrolled = false;

	function handleScroll() {
		if (window.scrollY > 100) {
			isScrolled = true;
		} else if (isScrolled && window.scrollY < 20) {
			isScrolled = false;
		}
	}

	// Load collapse states from localStorage
	function loadCollapseStates() {
		try {
			const savedStates = localStorage.getItem('configSectionStates');
			if (savedStates) {
				const parsedStates = JSON.parse(savedStates);
				sectionCollapsed = { ...parsedStates };
				console.log('Loaded states:', sectionCollapsed);
			}
		} catch (error) {
			console.error('Error loading collapse states:', error);
		}
	}

	// Save collapse states to localStorage
	function saveCollapseStates() {
		if (!isInitialized) return;
		try {
			localStorage.setItem('configSectionStates', JSON.stringify(sectionCollapsed));
			console.log('Saved states:', JSON.stringify(sectionCollapsed));
		} catch (error) {
			console.error('Error saving collapse states:', error);
		}
	}

	// Use Svelte's reactive statement to watch for state changes
	$: if (sectionCollapsed) {
		saveCollapseStates();
	}

	onMount(() => {
		loadCollapseStates();
		fetchConfig().then(() => {
			isInitialized = true;
		});

		window.addEventListener('scroll', handleScroll);
		
		return () => {
			window.removeEventListener('scroll', handleScroll);
		};
	});

	async function fetchConfig() {
		loading = true;
		error = null;
		try {
			const response = await fetch(`${apiEndpoint}/config`);
			if (!response.ok) {
				throw new Error(`Error fetching config: ${response.status} ${response.statusText}`);
			}
			config = await response.json();
			changes = {}; // Reset changes when loading new config
			
			if (config && config.ocr) {
				uiState.inputsDisabled.ocr = config.ocr.use_local;
				uiState.pluginDisabled.ocr = !config.ocr.enabled;
			}
			
			if (config && config.embedding) {
				uiState.inputsDisabled.embedding = config.embedding.use_local;
			}
			
			if (config && config.vlm) {
				uiState.pluginDisabled.vlm = !config.vlm.enabled;
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unknown error fetching configuration';
			console.error(error);
		} finally {
			loading = false;
		}
	}

	async function saveConfig() {
		if (Object.keys(changes).length === 0) {
			toast.message($_('config.title'), {
				description: $_('config.noChanges')
			});
			return;
		}

		saving = true;
		try {
			const response = await fetch(`${apiEndpoint}/config`, {
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(changes)
			});

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || `Error: ${response.status} ${response.statusText}`);
			}

			const result = await response.json();
			console.log('Save result:', result);

			// Check if any services need to be restarted
			const restartRequired = result.restart_required;
			if (Object.values(restartRequired).some((required) => required)) {
				toast.success($_('config.title'), {
					description: $_('config.savedSuccessfully')
				});
				
				if (restartRequired.serve) {
					healthCheckComponent.startHealthCheck();
				}
			} else {
				toast.success($_('config.title'), {
					description: $_('config.savedSuccessfully')
				});
			}

			// Refresh config to get updated values
			await fetchConfig();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unknown error saving configuration';
			console.error(error);
			toast.error($_('config.error'), {
				description: error
			});
		} finally {
			saving = false;
		}
	}

	function handleRestartClick() {
		showRestartConfirm = true;
	}

	function cancelRestart() {
		showRestartConfirm = false;
	}
	
	function handleRestartStatusChange(restarting: boolean) {
		servicesRestarting = restarting;
	}

	async function confirmRestart() {
		showRestartConfirm = false;
		saving = true;
		
		const restartData = {
			serve: true,
			watch: true,
			record: true
		};

		if (restartData.serve) {
			healthCheckComponent.startHealthCheck();
		}
		
		try {
			const response = await fetch(`${apiEndpoint}/config/restart`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(restartData)
			});

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || `Error: ${response.status} ${response.statusText}`);
			}

			toast.success($_('config.title'), {
				description: $_('config.servicesRestarting')
			});
			
			if (!restartData.serve) {
				healthCheckComponent.startHealthCheck();
			}
			
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unknown error restarting services';
			console.error(error);
			toast.error($_('config.error'), {
				description: error
			});
			servicesRestarting = false;
		} finally {
			saving = false;
		}
	}

	function handleChange(path: string[], value: any) {
		// Create nested path in changes object
		let current = changes;
		const lastKey = path[path.length - 1];
		
		// Build the nested structure
		for (let i = 0; i < path.length - 1; i++) {
			const key = path[i];
			if (!current[key]) {
				current[key] = {};
			}
			current = current[key];
		}
		
		// Set the value
		current[lastKey] = value;
		// Create a new object to trigger Svelte's reactive update
		changes = { ...changes };
		console.log("Changes updated:", changes);
	}

	function getConfigValue(path: string[]) {
		if (!config) return null;
		
		let current = config;
		for (const key of path) {
			if (current === undefined || current === null || !current.hasOwnProperty(key)) {
				return null;
			}
			current = current[key];
		}
		return current;
	}

	// Get the effective config value, prioritizing user changes
	function getEffectiveConfigValue(path: string[]) {
		// OCR-related debugging
		const isOcrPath = path[0] === 'ocr';
		const isOcrUseLocal = isOcrPath && path[1] === 'use_local';
		
		// First check if the value exists in user changes
		let changedValue = undefined;
		let current = changes;
		
		for (const key of path) {
			if (current === undefined || current === null || !current.hasOwnProperty(key)) {
				changedValue = undefined;
				break;
			}
			current = current[key];
			changedValue = current;
		}
		
		// If the value exists in user changes, return it
		if (changedValue !== undefined) {
			return changedValue;
		}
		
		// Otherwise return the original config value
		const originalValue = getConfigValue(path);

		return originalValue;
	}

	// Handle changes to the use_local checkbox type and update the UI state
	function handleUseLocalChange(feature: 'ocr' | 'embedding', newValue: boolean) {		
		// Update the config
		handleChange([feature, 'use_local'], newValue);
		
		// Update the UI state
		uiState.inputsDisabled[feature] = newValue;
	}

	// Handle changes to the enabled checkbox
	function handlePluginEnabledChange(plugin: 'ocr' | 'vlm', newValue: boolean) {
		// Update the config
		handleChange([plugin, 'enabled'], newValue);
		
		// Update the UI state
		uiState.pluginDisabled[plugin] = !newValue;
	}

	let textareaElement: HTMLTextAreaElement;
	
	// Add a function to automatically adjust the height of the textarea
	function adjustTextareaHeight(textarea: HTMLTextAreaElement) {
		// Set the minimum height (3 rows)
		const minHeight = 24 * 3; // Assuming each row is 24px tall
		
		// Reset height to get the actual content height
		textarea.style.height = 'auto';
		
		// Calculate the new height (the larger of the content height and the minimum height)
		const newHeight = Math.max(textarea.scrollHeight, minHeight);
		
		// Set the new height
		textarea.style.height = newHeight + 'px';
	}

	// 监听配置加载和文本区域挂载
	$: if (config && textareaElement) {
		setTimeout(() => adjustTextareaHeight(textareaElement), 0);
	}

	// 监听OCR设置的变化
	$: if (changes && changes.ocr) {
		if ('use_local' in changes.ocr) {
			
			// 检查DOM元素的状态
			setTimeout(() => {
				const endpointInput = document.getElementById('ocr-endpoint') as HTMLInputElement;
				const tokenInput = document.getElementById('ocr-token') as HTMLInputElement;
				if (endpointInput) {
				}
				if (tokenInput) {
				}
			}, 0);
		}
	}
</script>

<svelte:head>
	<title>Pensieve - {$_('config.title')}</title>
</svelte:head>

<div class="container mx-auto p-4 pt-0 max-w-5xl">
	<!-- 健康检查组件 -->
	<HealthCheck 
		bind:this={healthCheckComponent} 
		{apiEndpoint} 
		bind:servicesRestarting 
		onStatusChange={handleRestartStatusChange} 
	/>

	<header
		class="sticky top-0 z-10 transition-all duration-300 bg-white mb-4 border rounded-b-lg"
	>
		<div 
			class="flex items-center justify-between p-4 transition-all duration-300"
			class:shadow-md={isScrolled}
		>
			<div class="flex items-center">
				<Button variant="ghost" on:click={onBack} class="mr-4">
					<ArrowLeft size={18} class="mr-2" />
					{$_('back')}
				</Button>
				<h1 class="text-3xl font-bold">{$_('config.title')}</h1>
			</div>
			<div class="flex space-x-2">
				<Button variant="outline" on:click={handleRestartClick} disabled={saving || servicesRestarting}>
					<RotateCw size={18} class="mr-2" />
					{$_('config.restartServices')}
				</Button>
				<Button variant="default" on:click={saveConfig} disabled={saving || servicesRestarting || Object.keys(changes).length === 0}>
					<Save size={18} class="mr-2" />
					{$_('config.saveButton')}
				</Button>
			</div>
		</div>
	</header>

	{#if error}
		<Alert variant="destructive" class="mb-4">
			<AlertDescription>{error}</AlertDescription>
		</Alert>
	{/if}

	{#if showRestartConfirm}
		<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
			<div class="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
				<h3 class="text-lg font-medium mb-2">{$_('config.restartConfirmTitle')}</h3>
				<p class="text-gray-600 mb-4">{$_('config.restartConfirmMessage')}</p>
				<div class="flex justify-end space-x-2">
					<Button variant="outline" on:click={cancelRestart}>
						{$_('config.cancel')}
					</Button>
					<Button variant="destructive" on:click={confirmRestart}>
						{$_('config.confirm')}
					</Button>
				</div>
			</div>
		</div>
	{/if}

	{#if loading}
		<div class="flex justify-center items-center h-64">
			<div class="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
		</div>
	{:else if config}
		<!-- OCR Section -->
		<div class="mb-6">
			<Collapsible bind:open={sectionCollapsed.ocr}>
				<div class="border rounded-lg bg-white">
					<CollapsibleTrigger class="w-full">
						<div class="flex items-center justify-between p-4">
							<div class="space-y-1 text-left">
								<h3 class="text-lg font-semibold">{$_('config.ocr.title')}</h3>
								<p class="text-sm text-muted-foreground">{$_('config.ocr.description')}</p>
							</div>
							<Button variant="ghost" size="icon" class="hover:bg-transparent">
								{#if !sectionCollapsed.ocr}
									<ChevronDown size={20} />
								{:else}
									<ChevronUp size={20} />
								{/if}
							</Button>
						</div>
					</CollapsibleTrigger>
					<CollapsibleContent>
						<div class="p-4 pt-0">
							<div class="grid gap-4">
								<div class="flex items-start space-x-2">
									<Checkbox
										id="enable-ocr"
										checked={getEffectiveConfigValue(['ocr', 'enabled'])}
										on:click={() => {
											handlePluginEnabledChange('ocr', !getEffectiveConfigValue(['ocr', 'enabled']));
										}}
									/>
									<div class="space-y-1 leading-none">
										<Label for="enable-ocr">{$_('config.ocr.enabled', { default: 'Enable OCR Plugin' })}</Label>
										<p class="text-sm text-muted-foreground">
											{$_('config.ocr.enabledDesc', { default: 'Whether to enable the OCR plugin. Disable to save memory.' })}
										</p>
									</div>
								</div>

								<div class="flex items-start space-x-2">
									<Checkbox
										id="use-local-ocr"
										checked={getEffectiveConfigValue(['ocr', 'use_local'])}
										disabled={uiState.pluginDisabled.ocr}
										on:click={() => {
											if (!uiState.pluginDisabled.ocr) {
												handleUseLocalChange('ocr', !getEffectiveConfigValue(['ocr', 'use_local']));
											}
										}}
									/>
									<div class="space-y-1 leading-none">
										<Label for="use-local-ocr">
											<span class={uiState.pluginDisabled.ocr ? "text-muted-foreground" : ""}>
												{$_('config.ocr.useLocal')}
											</span>
										</Label>
									</div>
								</div>

								<div class="flex items-start space-x-2">
									<Checkbox
										id="force-jpeg-ocr"
										checked={getEffectiveConfigValue(['ocr', 'force_jpeg'])}
										disabled={uiState.pluginDisabled.ocr}
										on:click={() => {
											if (!uiState.pluginDisabled.ocr) {
												handleChange(['ocr', 'force_jpeg'], !getEffectiveConfigValue(['ocr', 'force_jpeg']));
											}
										}}
									/>
									<div class="space-y-1 leading-none">
										<Label for="force-jpeg-ocr">
											<span class={uiState.pluginDisabled.ocr ? "text-muted-foreground" : ""}>
												{$_('config.ocr.forceJpeg')}
											</span>
										</Label>
										<p class="text-sm text-muted-foreground">
											{$_('config.ocr.forceJpegDesc')}
										</p>
									</div>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="ocr-endpoint">{$_('config.ocr.endpoint')}</Label>
										<Input
											id="ocr-endpoint"
											class="font-mono"
											value={getEffectiveConfigValue(['ocr', 'endpoint'])}
											disabled={uiState.inputsDisabled.ocr || uiState.pluginDisabled.ocr}
											on:change={(e) => {
												if (!uiState.inputsDisabled.ocr && !uiState.pluginDisabled.ocr) {
													handleChange(['ocr', 'endpoint'], e.currentTarget.value);
												}
											}}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.ocr.endpointDesc')}
										</p>
									</div>

									<div>
										<Label for="ocr-token">{$_('config.ocr.token')}</Label>
										<Input
											id="ocr-token"
											class="font-mono"
											type="password"
											value={getEffectiveConfigValue(['ocr', 'token']) === '********' ? '' : getEffectiveConfigValue(['ocr', 'token'])}
											placeholder="********"
											disabled={uiState.inputsDisabled.ocr || uiState.pluginDisabled.ocr}
											on:change={(e) => {
												if (e.currentTarget.value && !uiState.inputsDisabled.ocr && !uiState.pluginDisabled.ocr) {
													handleChange(['ocr', 'token'], e.currentTarget.value);
												}
											}}
										/>
									</div>
								</div>

								<div>
									<Label for="ocr-concurrency">{$_('config.ocr.concurrency')}</Label>
									<Input
										id="ocr-concurrency"
										class="font-mono"
										type="number"
										value={getEffectiveConfigValue(['ocr', 'concurrency'])}
										disabled={uiState.pluginDisabled.ocr}
										on:change={(e) => {
											if (!uiState.pluginDisabled.ocr) {
												handleChange(['ocr', 'concurrency'], parseInt(e.currentTarget.value));
											}
										}}
									/>
									<p class="text-sm text-muted-foreground mt-1">
										{$_('config.ocr.concurrencyDesc')}
									</p>
								</div>
							</div>
						</div>
					</CollapsibleContent>
				</div>
			</Collapsible>
		</div>

		<!-- VLM Section -->
		<div class="mb-6">
			<Collapsible bind:open={sectionCollapsed.vlm}>
				<div class="border rounded-lg bg-white">
					<CollapsibleTrigger class="w-full">
						<div class="flex items-center justify-between p-4">
							<div class="space-y-1 text-left">
								<h3 class="text-lg font-semibold">{$_('config.vlm.title')}</h3>
								<p class="text-sm text-muted-foreground">{$_('config.vlm.description')}</p>
							</div>
							<Button variant="ghost" size="icon" class="hover:bg-transparent">
								{#if !sectionCollapsed.vlm}
									<ChevronDown size={20} />
								{:else}
									<ChevronUp size={20} />
								{/if}
							</Button>
						</div>
					</CollapsibleTrigger>
					<CollapsibleContent>
						<div class="p-4 pt-0">
							<div class="grid gap-4">
								<div class="flex items-start space-x-2 mb-4">
									<Checkbox
										id="enable-vlm"
										checked={getEffectiveConfigValue(['vlm', 'enabled'])}
										on:click={() => {
											handlePluginEnabledChange('vlm', !getEffectiveConfigValue(['vlm', 'enabled']));
										}}
									/>
									<div class="space-y-1 leading-none">
										<Label for="enable-vlm">{$_('config.vlm.enabled', { default: 'Enable VLM Plugin' })}</Label>
										<p class="text-sm text-muted-foreground">
											{$_('config.vlm.enabledDesc', { default: 'Whether to enable the VLM plugin. Disable to save memory.' })}
										</p>
									</div>
								</div>

								<div>
									<Label for="model-name">{$_('config.vlm.modelName')}</Label>
									<Input
										id="model-name"
										class="font-mono"
										value={getEffectiveConfigValue(['vlm', 'modelname'])}
										disabled={uiState.pluginDisabled.vlm}
										on:change={(e) => {
											if (!uiState.pluginDisabled.vlm) {
												handleChange(['vlm', 'modelname'], e.currentTarget.value);
											}
										}}
									/>
									<p class="text-sm text-muted-foreground mt-1">
										{$_('config.vlm.modelNameDesc')}
									</p>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="vlm-endpoint">{$_('config.vlm.endpoint')}</Label>
										<Input
											id="vlm-endpoint"
											class="font-mono"
											value={getEffectiveConfigValue(['vlm', 'endpoint'])}
											disabled={uiState.pluginDisabled.vlm}
											on:change={(e) => {
												if (!uiState.pluginDisabled.vlm) {
													handleChange(['vlm', 'endpoint'], e.currentTarget.value);
												}
											}}
										/>
									</div>

									<div>
										<Label for="vlm-token">{$_('config.vlm.token')}</Label>
										<Input
											id="vlm-token"
											class="font-mono"
											type="password"
											value={getEffectiveConfigValue(['vlm', 'token']) === '********' ? '' : getEffectiveConfigValue(['vlm', 'token'])}
											placeholder="********"
											disabled={uiState.pluginDisabled.vlm}
											on:change={(e) => {
												if (e.currentTarget.value && !uiState.pluginDisabled.vlm) {
													handleChange(['vlm', 'token'], e.currentTarget.value);
												}
											}}
										/>
									</div>
								</div>

								<div>
									<Label for="vlm-concurrency">{$_('config.vlm.concurrency')}</Label>
									<Input
										id="vlm-concurrency"
										class="font-mono"
										type="number"
										value={getEffectiveConfigValue(['vlm', 'concurrency'])}
										disabled={uiState.pluginDisabled.vlm}
										on:change={(e) => {
											if (!uiState.pluginDisabled.vlm) {
												handleChange(['vlm', 'concurrency'], parseInt(e.currentTarget.value));
											}
										}}
									/>
									<p class="text-sm text-muted-foreground mt-1">
										{$_('config.vlm.concurrencyDesc')}
									</p>
								</div>

								<div class="flex items-start space-x-2">
									<Checkbox
										id="force-jpeg-vlm"
										checked={getEffectiveConfigValue(['vlm', 'force_jpeg'])}
										disabled={uiState.pluginDisabled.vlm}
										on:click={() => {
											if (!uiState.pluginDisabled.vlm) {
												handleChange(['vlm', 'force_jpeg'], !getEffectiveConfigValue(['vlm', 'force_jpeg']));
											}
										}}
									/>
									<div class="space-y-1 leading-none">
										<Label for="force-jpeg-vlm">
											<span class={uiState.pluginDisabled.vlm ? "text-muted-foreground" : ""}>
												{$_('config.vlm.forceJpeg')}
											</span>
										</Label>
										<p class="text-sm text-muted-foreground">
											{$_('config.vlm.forceJpegDesc')}
										</p>
									</div>
								</div>

								<div>
									<Label for="vlm-prompt">{$_('config.vlm.prompt')}</Label>
									<div class="relative">
										<textarea
											bind:this={textareaElement}
											id="vlm-prompt"
											class="font-mono resize-none overflow-hidden w-full min-h-[72px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
											value={getEffectiveConfigValue(['vlm', 'prompt'])}
											disabled={uiState.pluginDisabled.vlm}
											on:input={(e) => {
												if (!uiState.pluginDisabled.vlm) {
													handleChange(['vlm', 'prompt'], e.currentTarget.value);
													adjustTextareaHeight(e.currentTarget);
												}
											}}
										/>
									</div>
									<p class="text-sm text-muted-foreground mt-1">
										{$_('config.vlm.promptDesc')}
									</p>
								</div>
							</div>
						</div>
					</CollapsibleContent>
				</div>
			</Collapsible>
		</div>

		<!-- Record Section -->
		<div class="mb-6">
			<Collapsible bind:open={sectionCollapsed.record}>
				<div class="border rounded-lg bg-white">
					<CollapsibleTrigger class="w-full">
						<div class="flex items-center justify-between p-4">
							<div class="space-y-1 text-left">
								<h3 class="text-lg font-semibold">{$_('config.record.title')}</h3>
								<p class="text-sm text-muted-foreground">{$_('config.record.description')}</p>
							</div>
							<Button variant="ghost" size="icon" class="hover:bg-transparent">
								{#if !sectionCollapsed.record}
									<ChevronDown size={20} />
								{:else}
									<ChevronUp size={20} />
								{/if}
							</Button>
						</div>
					</CollapsibleTrigger>
					<CollapsibleContent>
						<div class="p-4 pt-0">
							<div class="grid gap-4">
								<div>
									<Label for="record-interval">{$_('config.record.interval')}</Label>
									<Input
										id="record-interval"
										class="font-mono"
										type="number"
										value={getEffectiveConfigValue(['record_interval'])}
										on:change={(e) => handleChange(['record_interval'], parseInt(e.currentTarget.value))}
									/>
									<p class="text-sm text-muted-foreground mt-1">
										{$_('config.record.intervalDesc')}
									</p>
								</div>
							</div>
						</div>
					</CollapsibleContent>
				</div>
			</Collapsible>
		</div>


		<!-- Watch Section -->
		<div class="mb-6">
			<Collapsible bind:open={sectionCollapsed.watch}>
				<div class="border rounded-lg bg-white">
					<CollapsibleTrigger class="w-full">
						<div class="flex items-center justify-between p-4">
							<div class="space-y-1 text-left">
								<h3 class="text-lg font-semibold">{$_('config.watch.title')}</h3>
								<p class="text-sm text-muted-foreground">{$_('config.watch.description')}</p>
							</div>
							<Button variant="ghost" size="icon" class="hover:bg-transparent">
								{#if !sectionCollapsed.watch}
									<ChevronDown size={20} />
								{:else}
									<ChevronUp size={20} />
								{/if}
							</Button>
						</div>
					</CollapsibleTrigger>
					<CollapsibleContent>
						<div class="p-4 pt-0">
							<div class="grid gap-4">
								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="rate-window-size">{$_('config.watch.rateWindowSize')}</Label>
										<Input
											id="rate-window-size"
											class="font-mono"
											type="number"
											value={getEffectiveConfigValue(['watch', 'rate_window_size'])}
											on:change={(e) => handleChange(['watch', 'rate_window_size'], parseInt(e.currentTarget.value))}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.watch.rateWindowSizeDesc')}
										</p>
									</div>

									<div>
										<Label for="sparsity-factor">{$_('config.watch.sparsityFactor')}</Label>
										<Input
											id="sparsity-factor"
											class="font-mono"
											type="number"
											step="0.1"
											value={getEffectiveConfigValue(['watch', 'sparsity_factor'])}
											on:change={(e) => handleChange(['watch', 'sparsity_factor'], parseFloat(e.currentTarget.value))}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.watch.sparsityFactorDesc')}
										</p>
									</div>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="processing-interval">{$_('config.watch.processingInterval')}</Label>
										<Input
											id="processing-interval"
											class="font-mono"
											type="number"
											value={getEffectiveConfigValue(['watch', 'processing_interval'])}
											on:change={(e) => handleChange(['watch', 'processing_interval'], parseInt(e.currentTarget.value))}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.watch.processingIntervalDesc')}
										</p>
									</div>

									<div>
										<Label for="idle-timeout">{$_('config.watch.idleTimeout')}</Label>
										<Input
											id="idle-timeout"
											class="font-mono"
											type="number"
											value={getEffectiveConfigValue(['watch', 'idle_timeout'])}
											on:change={(e) => handleChange(['watch', 'idle_timeout'], parseInt(e.currentTarget.value))}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.watch.idleTimeoutDesc')}
										</p>
									</div>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="idle-process-start">{$_('config.watch.idleProcessStart')}</Label>
										<Input
											id="idle-process-start"
											class="font-mono"
											type="time"
											value={getEffectiveConfigValue(['watch', 'idle_process_interval'])?.[0] || "00:00"}
											on:change={(e) => {
												const currentInterval = getEffectiveConfigValue(['watch', 'idle_process_interval']) || ["00:00", "07:00"];
												handleChange(['watch', 'idle_process_interval'], [
													e.currentTarget.value,
													currentInterval[1]
												]);
											}}
										/>
									</div>

									<div>
										<Label for="idle-process-end">{$_('config.watch.idleProcessEnd')}</Label>
										<Input
											id="idle-process-end"
											class="font-mono"
											type="time"
											value={getEffectiveConfigValue(['watch', 'idle_process_interval'])?.[1] || "07:00"}
											on:change={(e) => {
												const currentInterval = getEffectiveConfigValue(['watch', 'idle_process_interval']) || ["00:00", "07:00"];
												handleChange(['watch', 'idle_process_interval'], [
													currentInterval[0],
													e.currentTarget.value
												]);
											}}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.watch.idleProcessDesc')}
										</p>
									</div>
								</div>
							</div>
						</div>
					</CollapsibleContent>
				</div>
			</Collapsible>
		</div>

		<!-- General Section -->
		<div class="mb-6">
			<Collapsible bind:open={sectionCollapsed.general}>
				<div class="border rounded-lg bg-white">
					<CollapsibleTrigger class="w-full">
						<div class="flex items-center justify-between p-4">
							<div class="space-y-1 text-left">
								<h3 class="text-lg font-semibold">{$_('config.general.title')}</h3>
								<p class="text-sm text-muted-foreground">{$_('config.general.description')}</p>
							</div>
							<Button variant="ghost" size="icon" class="hover:bg-transparent">
								{#if !sectionCollapsed.general}
									<ChevronDown size={20} />
								{:else}
									<ChevronUp size={20} />
								{/if}
							</Button>
						</div>
					</CollapsibleTrigger>
					<CollapsibleContent>
						<div class="p-4 pt-0">
							<div class="grid gap-4">
								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="base-dir">{$_('config.general.baseDir')}</Label>
										<Input
											id="base-dir"
											class="font-mono"
											value={getEffectiveConfigValue(['base_dir'])}
											on:change={(e) => handleChange(['base_dir'], e.currentTarget.value)}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.general.baseDirDesc')}
										</p>
									</div>

									<div>
										<Label for="screenshots-dir">{$_('config.general.screenshotsDir')}</Label>
										<Input
											id="screenshots-dir"
											class="font-mono"
											value={getEffectiveConfigValue(['screenshots_dir'])}
											on:change={(e) => handleChange(['screenshots_dir'], e.currentTarget.value)}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.general.screenshotsDirDesc')}
										</p>
									</div>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="database-path">{$_('config.general.databasePath')}</Label>
										<Input
											id="database-path"
											class="font-mono"
											value={getEffectiveConfigValue(['database_path'])}
											on:change={(e) => handleChange(['database_path'], e.currentTarget.value)}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.general.databasePathDesc')}
										</p>
									</div>

									<div>
										<Label for="default-library">{$_('config.general.defaultLibrary')}</Label>
										<Input
											id="default-library"
											class="font-mono"
											value={getEffectiveConfigValue(['default_library'])}
											on:change={(e) => handleChange(['default_library'], e.currentTarget.value)}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.general.defaultLibraryDesc')}
										</p>
									</div>
								</div>

								<div class="flex items-start space-x-2">
									<Checkbox
										id="facet-option"
										checked={getEffectiveConfigValue(['facet'])}
										on:click={() => {
											handleChange(['facet'], !getEffectiveConfigValue(['facet']));
										}}
									/>
									<div class="space-y-1 leading-none">
										<Label for="facet-option">{$_('config.general.enableFacet')}</Label>
										<p class="text-sm text-muted-foreground">
											{$_('config.general.enableFacetDesc')}
										</p>
									</div>
								</div>

								<div class="space-y-3">
									<h4 class="text-sm font-medium">{$_('config.general.defaultPlugins')}</h4>
									<div class="flex items-center space-x-2">
										<Checkbox
											id="builtin-ocr"
											checked={getEffectiveConfigValue(['default_plugins'])?.includes('builtin_ocr')}
											on:click={() => {
												const plugins = new Set(getEffectiveConfigValue(['default_plugins']) || []);
												if (plugins.has('builtin_ocr')) {
													plugins.delete('builtin_ocr');
												} else {
													plugins.add('builtin_ocr');
												}
												handleChange(['default_plugins'], Array.from(plugins));
											}}
										/>
										<Label for="builtin-ocr">Builtin OCR</Label>
									</div>
									<div class="flex items-center space-x-2">
										<Checkbox
											id="builtin-vlm"
											checked={getEffectiveConfigValue(['default_plugins'])?.includes('builtin_vlm')}
											on:click={() => {
												const plugins = new Set(getEffectiveConfigValue(['default_plugins']) || []);
												if (plugins.has('builtin_vlm')) {
													plugins.delete('builtin_vlm');
												} else {
													plugins.add('builtin_vlm');
												}
												handleChange(['default_plugins'], Array.from(plugins));
											}}
										/>
										<Label for="builtin-vlm">Builtin VLM</Label>
									</div>
									<p class="text-sm text-muted-foreground">
										{$_('config.general.defaultPluginsDesc')}
									</p>
								</div>
							</div>
						</div>
					</CollapsibleContent>
				</div>
			</Collapsible>
		</div>

		<!-- Server Section -->
		<div class="mb-6">
			<Collapsible bind:open={sectionCollapsed.serve}>
				<div class="border rounded-lg bg-white">
					<CollapsibleTrigger class="w-full">
						<div class="flex items-center justify-between p-4">
							<div class="space-y-1 text-left">
								<h3 class="text-lg font-semibold">{$_('config.server.title')}</h3>
								<p class="text-sm text-muted-foreground">{$_('config.server.description')}</p>
							</div>
							<Button variant="ghost" size="icon" class="hover:bg-transparent">
								{#if !sectionCollapsed.serve}
									<ChevronDown size={20} />
								{:else}
									<ChevronUp size={20} />
								{/if}
							</Button>
						</div>
					</CollapsibleTrigger>
					<CollapsibleContent>
						<div class="p-4 pt-0">
							<div class="grid gap-4">
								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="server-host">{$_('config.server.host')}</Label>
										<Input
											id="server-host"
											class="font-mono"
											value={getEffectiveConfigValue(['server_host'])}
											on:change={(e) => handleChange(['server_host'], e.currentTarget.value)}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.server.hostDesc')}
										</p>
									</div>

									<div>
										<Label for="server-port">{$_('config.server.port')}</Label>
										<Input
											id="server-port"
											class="font-mono"
											type="number"
											value={getEffectiveConfigValue(['server_port'])}
											on:change={(e) => handleChange(['server_port'], parseInt(e.currentTarget.value))}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.server.portDesc')}
										</p>
									</div>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="auth-username">{$_('config.server.username')}</Label>
										<Input
											id="auth-username"
											class="font-mono"
											value={getEffectiveConfigValue(['auth_username'])}
											on:change={(e) => handleChange(['auth_username'], e.currentTarget.value)}
										/>
									</div>

									<div>
										<Label for="auth-password">{$_('config.server.password')}</Label>
										<Input
											id="auth-password"
											class="font-mono"
											type="password"
											value={getEffectiveConfigValue(['auth_password']) === '********' ? '' : getEffectiveConfigValue(['auth_password'])}
											placeholder="********"
											on:change={(e) => {
												if (e.currentTarget.value) {
													handleChange(['auth_password'], e.currentTarget.value);
												}
											}}
										/>
									</div>
								</div>
							</div>
						</div>
					</CollapsibleContent>
				</div>
			</Collapsible>
		</div>

		<!-- Embedding Section -->
		<div class="mb-6">
			<Collapsible bind:open={sectionCollapsed.embedding}>
				<div class="border rounded-lg bg-white">
					<CollapsibleTrigger class="w-full">
						<div class="flex items-center justify-between p-4">
							<div class="space-y-1 text-left">
								<h3 class="text-lg font-semibold">{$_('config.embedding.title')}</h3>
								<p class="text-sm text-muted-foreground">{$_('config.embedding.description')}</p>
							</div>
							<Button variant="ghost" size="icon" class="hover:bg-transparent">
								{#if !sectionCollapsed.embedding}
									<ChevronDown size={20} />
								{:else}
									<ChevronUp size={20} />
								{/if}
							</Button>
						</div>
					</CollapsibleTrigger>
					<CollapsibleContent>
						<div class="p-4 pt-0">
							<div class="grid gap-4">								
								<Alert variant="destructive" class="bg-amber-50 border-amber-200 text-amber-700">
									<AlertDescription>
										{$_('config.embedding.changeWarningPrefix', { default: 'Changing the embedding model or dimensions requires restarting services and reindexing. After changes, run ' })}
										<code class="bg-amber-100 px-1 py-0.5 rounded font-mono text-amber-800">memos reindex --force</code>
									</AlertDescription>
								</Alert>

								<div class="grid gap-4">
									<div class="flex items-start space-x-2">
										<Checkbox
											id="use-local-embedding"
											checked={getEffectiveConfigValue(['embedding', 'use_local'])}
											on:click={() => {
												handleUseLocalChange('embedding', !getEffectiveConfigValue(['embedding', 'use_local']));
											}}
										/>
										<div class="space-y-1 leading-none">
											<Label for="use-local-embedding">{$_('config.embedding.useLocal')}</Label>
										</div>
									</div>

									<div class="flex items-start space-x-2">
										<Checkbox
											id="use-modelscope"
											checked={getEffectiveConfigValue(['embedding', 'use_modelscope'])}
											on:click={() => {
												handleChange(['embedding', 'use_modelscope'], !getEffectiveConfigValue(['embedding', 'use_modelscope']));
											}}
										/>
										<div class="space-y-1 leading-none">
											<Label for="use-modelscope">{$_('config.embedding.useModelscope')}</Label>
											<p class="text-sm text-muted-foreground">
												{$_('config.embedding.useModelScopeDesc')}
											</p>
										</div>
									</div>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="embedding-model">{$_('config.embedding.model')}</Label>
										<Input
											id="embedding-model"
											class="font-mono"
											value={getEffectiveConfigValue(['embedding', 'model'])}
											on:change={(e) => handleChange(['embedding', 'model'], e.currentTarget.value)}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.embedding.modelDesc')}
										</p>
									</div>

									<div>
										<Label for="embedding-dimensions">{$_('config.embedding.dimensions')}</Label>
										<Input
											id="embedding-dimensions"
											class="font-mono"
											type="number"
											value={getEffectiveConfigValue(['embedding', 'num_dim'])}
											on:change={(e) => handleChange(['embedding', 'num_dim'], parseInt(e.currentTarget.value))}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.embedding.dimensionsDesc')}
										</p>
									</div>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="embedding-endpoint">{$_('config.embedding.endpoint')}</Label>
										<Input
											id="embedding-endpoint"
											class="font-mono"
											value={getEffectiveConfigValue(['embedding', 'endpoint'])}
											disabled={uiState.inputsDisabled.embedding}
											on:change={(e) => handleChange(['embedding', 'endpoint'], e.currentTarget.value)}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{$_('config.embedding.endpointDesc')}
										</p>
									</div>

									<div>
										<Label for="embedding-token">{$_('config.embedding.token')}</Label>
										<Input
											id="embedding-token"
											class="font-mono"
											type="password"
											value={getEffectiveConfigValue(['embedding', 'token']) === '********' ? '' : getEffectiveConfigValue(['embedding', 'token'])}
											placeholder="********"
											disabled={uiState.inputsDisabled.embedding}
											on:change={(e) => {
												if (e.currentTarget.value) {
													handleChange(['embedding', 'token'], e.currentTarget.value);
												}
											}}
										/>
									</div>
								</div>
							</div>
						</div>
					</CollapsibleContent>
				</div>
			</Collapsible>
		</div>
	{/if}
</div> 