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

	// 用于返回主页面的函数，由父组件传入
	export let onBack: () => void;

	const apiEndpoint =
		(typeof PUBLIC_API_ENDPOINT !== 'undefined' ? PUBLIC_API_ENDPOINT : window.location.origin) + '/api';

	let config: any = null;
	let loading = true;
	let saving = false;
	let error: string | null = null;
	let changes: any = {};

	// 添加状态变量控制显示确认对话框
	let showRestartConfirm = false;
	
	// 服务重启中的状态
	let servicesRestarting = false;
	
	// 健康检查组件引用
	let healthCheckComponent: HealthCheck;

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

	let isInitialized = false; // 添加初始化标志

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
		if (!isInitialized) return; // 如果还没初始化完成，不保存状态
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

	onMount(async () => {
		loadCollapseStates();
		await fetchConfig();
		isInitialized = true; // 标记初始化完成
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

	// 显示重启确认对话框
	function handleRestartClick() {
		showRestartConfirm = true;
	}

	// 取消重启操作
	function cancelRestart() {
		showRestartConfirm = false;
	}

	// 处理服务重启状态变化
	function handleRestartStatusChange(restarting: boolean) {
		servicesRestarting = restarting;
	}

	// 执行实际的重启服务操作
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
		// 创建一个新对象以触发Svelte的响应式更新
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
</script>

<svelte:head>
	<title>Pensieve - {$_('config.title')}</title>
</svelte:head>

<div class="container mx-auto p-4 max-w-5xl">
	<!-- 健康检查组件 -->
	<HealthCheck 
		bind:this={healthCheckComponent} 
		{apiEndpoint} 
		bind:servicesRestarting 
		onStatusChange={handleRestartStatusChange} 
	/>

	<header class="flex justify-between items-center mb-8">
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
	</header>

	{#if error}
		<Alert variant="destructive" class="mb-4">
			<AlertDescription>{error}</AlertDescription>
		</Alert>
	{/if}

	<!-- 重启服务确认对话框 -->
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
											value={getConfigValue(['base_dir'])}
											on:change={(e) => handleChange(['base_dir'], e.currentTarget.value)}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{config.base_dir}
										</p>
									</div>

									<div>
										<Label for="screenshots-dir">{$_('config.general.screenshotsDir')}</Label>
										<Input
											id="screenshots-dir"
											value={getConfigValue(['screenshots_dir'])}
											on:change={(e) => handleChange(['screenshots_dir'], e.currentTarget.value)}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{config.screenshots_dir}
										</p>
									</div>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="database-path">{$_('config.general.databasePath')}</Label>
										<Input
											id="database-path"
											value={getConfigValue(['database_path'])}
											on:change={(e) => handleChange(['database_path'], e.currentTarget.value)}
										/>
										<p class="text-sm text-muted-foreground mt-1">
											{config.database_path}
										</p>
									</div>

									<div>
										<Label for="default-library">{$_('config.general.defaultLibrary')}</Label>
										<Input
											id="default-library"
											value={getConfigValue(['default_library'])}
											on:change={(e) => handleChange(['default_library'], e.currentTarget.value)}
										/>
									</div>
								</div>

								<div class="flex items-center space-x-2">
									<Checkbox
										id="facet-option"
										checked={getConfigValue(['facet'])}
										on:click={() => {
											handleChange(['facet'], !getConfigValue(['facet']));
										}}
									/>
									<Label for="facet-option">{$_('config.general.enableFacet')}</Label>
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
											value={getConfigValue(['server_host'])}
											on:change={(e) => handleChange(['server_host'], e.currentTarget.value)}
										/>
									</div>

									<div>
										<Label for="server-port">{$_('config.server.port')}</Label>
										<Input
											id="server-port"
											type="number"
											value={getConfigValue(['server_port'])}
											on:change={(e) => handleChange(['server_port'], parseInt(e.currentTarget.value))}
										/>
									</div>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="auth-username">{$_('config.server.username')}</Label>
										<Input
											id="auth-username"
											value={getConfigValue(['auth_username'])}
											on:change={(e) => handleChange(['auth_username'], e.currentTarget.value)}
										/>
									</div>

									<div>
										<Label for="auth-password">{$_('config.server.password')}</Label>
										<Input
											id="auth-password"
											type="password"
											value={getConfigValue(['auth_password']) === '********' ? '' : getConfigValue(['auth_password'])}
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
										type="number"
										value={getConfigValue(['record_interval'])}
										on:change={(e) => handleChange(['record_interval'], parseInt(e.currentTarget.value))}
									/>
									<p class="text-sm text-muted-foreground mt-1">
										{$_('config.record.intervalDescription')}
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
											type="number"
											value={getConfigValue(['watch', 'rate_window_size'])}
											on:change={(e) => handleChange(['watch', 'rate_window_size'], parseInt(e.currentTarget.value))}
										/>
									</div>

									<div>
										<Label for="sparsity-factor">{$_('config.watch.sparsityFactor')}</Label>
										<Input
											id="sparsity-factor"
											type="number"
											step="0.1"
											value={getConfigValue(['watch', 'sparsity_factor'])}
											on:change={(e) => handleChange(['watch', 'sparsity_factor'], parseFloat(e.currentTarget.value))}
										/>
									</div>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="processing-interval">{$_('config.watch.processingInterval')}</Label>
										<Input
											id="processing-interval"
											type="number"
											value={getConfigValue(['watch', 'processing_interval'])}
											on:change={(e) => handleChange(['watch', 'processing_interval'], parseInt(e.currentTarget.value))}
										/>
									</div>

									<div>
										<Label for="idle-timeout">{$_('config.watch.idleTimeout')}</Label>
										<Input
											id="idle-timeout"
											type="number"
											value={getConfigValue(['watch', 'idle_timeout'])}
											on:change={(e) => handleChange(['watch', 'idle_timeout'], parseInt(e.currentTarget.value))}
										/>
									</div>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="idle-process-start">{$_('config.watch.idleProcessStart')}</Label>
										<Input
											id="idle-process-start"
											type="time"
											value={getConfigValue(['watch', 'idle_process_interval'])?.[0] || "00:00"}
											on:change={(e) => {
												const currentInterval = getConfigValue(['watch', 'idle_process_interval']) || ["00:00", "07:00"];
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
											type="time"
											value={getConfigValue(['watch', 'idle_process_interval'])?.[1] || "07:00"}
											on:change={(e) => {
												const currentInterval = getConfigValue(['watch', 'idle_process_interval']) || ["00:00", "07:00"];
												handleChange(['watch', 'idle_process_interval'], [
													currentInterval[0],
													e.currentTarget.value
												]);
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
								<div class="flex items-center space-x-2">
									<Checkbox
										id="use-local-ocr"
										checked={getConfigValue(['ocr', 'use_local'])}
										on:click={() => {
											handleChange(['ocr', 'use_local'], !getConfigValue(['ocr', 'use_local']));
										}}
									/>
									<Label for="use-local-ocr">{$_('config.ocr.useLocal')}</Label>
								</div>

								<div class="flex items-center space-x-2">
									<Checkbox
										id="force-jpeg-ocr"
										checked={getConfigValue(['ocr', 'force_jpeg'])}
										on:click={() => {
											handleChange(['ocr', 'force_jpeg'], !getConfigValue(['ocr', 'force_jpeg']));
										}}
									/>
									<Label for="force-jpeg-ocr">{$_('config.ocr.forceJpeg')}</Label>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="ocr-endpoint">{$_('config.ocr.endpoint')}</Label>
										<Input
											id="ocr-endpoint"
											value={getConfigValue(['ocr', 'endpoint'])}
											disabled={getConfigValue(['ocr', 'use_local'])}
											on:change={(e) => handleChange(['ocr', 'endpoint'], e.currentTarget.value)}
										/>
									</div>

									<div>
										<Label for="ocr-token">{$_('config.ocr.token')}</Label>
										<Input
											id="ocr-token"
											type="password"
											value={getConfigValue(['ocr', 'token']) === '********' ? '' : getConfigValue(['ocr', 'token'])}
											placeholder="********"
											disabled={getConfigValue(['ocr', 'use_local'])}
											on:change={(e) => {
												if (e.currentTarget.value) {
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
										type="number"
										value={getConfigValue(['ocr', 'concurrency'])}
										on:change={(e) => handleChange(['ocr', 'concurrency'], parseInt(e.currentTarget.value))}
									/>
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
								<div>
									<Label for="model-name">{$_('config.vlm.modelName')}</Label>
									<Input
										id="model-name"
										value={getConfigValue(['vlm', 'modelname'])}
										on:change={(e) => handleChange(['vlm', 'modelname'], e.currentTarget.value)}
									/>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="vlm-endpoint">{$_('config.vlm.endpoint')}</Label>
										<Input
											id="vlm-endpoint"
											value={getConfigValue(['vlm', 'endpoint'])}
											on:change={(e) => handleChange(['vlm', 'endpoint'], e.currentTarget.value)}
										/>
									</div>

									<div>
										<Label for="vlm-token">{$_('config.vlm.token')}</Label>
										<Input
											id="vlm-token"
											type="password"
											value={getConfigValue(['vlm', 'token']) === '********' ? '' : getConfigValue(['vlm', 'token'])}
											placeholder="********"
											on:change={(e) => {
												if (e.currentTarget.value) {
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
										type="number"
										value={getConfigValue(['vlm', 'concurrency'])}
										on:change={(e) => handleChange(['vlm', 'concurrency'], parseInt(e.currentTarget.value))}
									/>
								</div>

								<div class="flex items-center space-x-2">
									<Checkbox
										id="force-jpeg-vlm"
										checked={getConfigValue(['vlm', 'force_jpeg'])}
										on:click={() => {
											handleChange(['vlm', 'force_jpeg'], !getConfigValue(['vlm', 'force_jpeg']));
										}}
									/>
									<Label for="force-jpeg-vlm">{$_('config.vlm.forceJpeg')}</Label>
								</div>

								<div>
									<Label for="vlm-prompt">{$_('config.vlm.prompt')}</Label>
									<Textarea
										id="vlm-prompt"
										rows={3}
										value={getConfigValue(['vlm', 'prompt'])}
										on:change={(e) => handleChange(['vlm', 'prompt'], e.currentTarget.value)}
									/>
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
								<div class="flex items-center space-x-2">
									<Checkbox
										id="use-local-embedding"
										checked={getConfigValue(['embedding', 'use_local'])}
										on:click={() => {
											handleChange(['embedding', 'use_local'], !getConfigValue(['embedding', 'use_local']));
										}}
									/>
									<Label for="use-local-embedding">{$_('config.embedding.useLocal')}</Label>
								</div>

								<div class="flex items-center space-x-2">
									<Checkbox
										id="use-modelscope"
										checked={getConfigValue(['embedding', 'use_modelscope'])}
										on:click={() => {
											handleChange(['embedding', 'use_modelscope'], !getConfigValue(['embedding', 'use_modelscope']));
										}}
									/>
									<Label for="use-modelscope">{$_('config.embedding.useModelscope')}</Label>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="embedding-model">{$_('config.embedding.model')}</Label>
										<Input
											id="embedding-model"
											value={getConfigValue(['embedding', 'model'])}
											on:change={(e) => handleChange(['embedding', 'model'], e.currentTarget.value)}
										/>
									</div>

									<div>
										<Label for="embedding-dimensions">{$_('config.embedding.dimensions')}</Label>
										<Input
											id="embedding-dimensions"
											type="number"
											value={getConfigValue(['embedding', 'num_dim'])}
											on:change={(e) => handleChange(['embedding', 'num_dim'], parseInt(e.currentTarget.value))}
										/>
									</div>
								</div>

								<div class="grid grid-cols-2 gap-4">
									<div>
										<Label for="embedding-endpoint">{$_('config.embedding.endpoint')}</Label>
										<Input
											id="embedding-endpoint"
											value={getConfigValue(['embedding', 'endpoint'])}
											disabled={getConfigValue(['embedding', 'use_local'])}
											on:change={(e) => handleChange(['embedding', 'endpoint'], e.currentTarget.value)}
										/>
									</div>

									<div>
										<Label for="embedding-token">{$_('config.embedding.token')}</Label>
										<Input
											id="embedding-token"
											type="password"
											value={getConfigValue(['embedding', 'token']) === '********' ? '' : getConfigValue(['embedding', 'token'])}
											placeholder="********"
											disabled={getConfigValue(['embedding', 'use_local'])}
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