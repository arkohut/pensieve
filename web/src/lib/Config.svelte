<script lang="ts">
	import { onMount } from 'svelte';
	import { PUBLIC_API_ENDPOINT } from '$env/static/public';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '$lib/components/ui/card';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Save, RotateCw, ArrowLeft, ChevronUp, ChevronDown } from 'lucide-svelte';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { toast } from 'svelte-sonner';
	import { Textarea } from '$lib/components/ui/textarea';
	import { _ } from 'svelte-i18n';
	import HealthCheck from './HealthCheck.svelte';

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

	function toggleSection(section: keyof typeof sectionCollapsed) {
		sectionCollapsed[section] = !sectionCollapsed[section];
	}

	onMount(() => {
		fetchConfig();
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
		<Card class="mb-6">
			<CardHeader class="cursor-pointer" on:click={() => toggleSection('general')}>
				<div class="flex justify-between items-center">
					<CardTitle>{$_('config.general.title')}</CardTitle>
					<div>
						{#if sectionCollapsed.general}
							<ChevronDown size={20} />
						{:else}
							<ChevronUp size={20} />
						{/if}
					</div>
				</div>
				<CardDescription>
					{$_('config.general.description')}
				</CardDescription>
			</CardHeader>
			{#if !sectionCollapsed.general}
				<CardContent>
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
				</CardContent>
			{/if}
		</Card>

		<!-- Server Section -->
		<Card class="mb-6">
			<CardHeader class="cursor-pointer" on:click={() => toggleSection('serve')}>
				<div class="flex justify-between items-center">
					<CardTitle>{$_('config.server.title')}</CardTitle>
					<div>
						{#if sectionCollapsed.serve}
							<ChevronDown size={20} />
						{:else}
							<ChevronUp size={20} />
						{/if}
					</div>
				</div>
				<CardDescription>
					{$_('config.server.description')}
				</CardDescription>
			</CardHeader>
			{#if !sectionCollapsed.serve}
				<CardContent>
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
				</CardContent>
			{/if}
		</Card>

		<!-- Record Section -->
		<Card class="mb-6">
			<CardHeader class="cursor-pointer" on:click={() => toggleSection('record')}>
				<div class="flex justify-between items-center">
					<CardTitle>{$_('config.record.title')}</CardTitle>
					<div>
						{#if sectionCollapsed.record}
							<ChevronDown size={20} />
						{:else}
							<ChevronUp size={20} />
						{/if}
					</div>
				</div>
				<CardDescription>
					{$_('config.record.description')}
				</CardDescription>
			</CardHeader>
			{#if !sectionCollapsed.record}
				<CardContent>
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
				</CardContent>
			{/if}
		</Card>

		<!-- Watch Section -->
		<Card class="mb-6">
			<CardHeader class="cursor-pointer" on:click={() => toggleSection('watch')}>
				<div class="flex justify-between items-center">
					<CardTitle>{$_('config.watch.title')}</CardTitle>
					<div>
						{#if sectionCollapsed.watch}
							<ChevronDown size={20} />
						{:else}
							<ChevronUp size={20} />
						{/if}
					</div>
				</div>
				<CardDescription>
					{$_('config.watch.description')}
				</CardDescription>
			</CardHeader>
			{#if !sectionCollapsed.watch}
				<CardContent>
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
				</CardContent>
			{/if}
		</Card>

		<!-- OCR Section -->
		<Card class="mb-6">
			<CardHeader class="cursor-pointer" on:click={() => toggleSection('ocr')}>
				<div class="flex justify-between items-center">
					<CardTitle>{$_('config.ocr.title')}</CardTitle>
					<div>
						{#if sectionCollapsed.ocr}
							<ChevronDown size={20} />
						{:else}
							<ChevronUp size={20} />
						{/if}
					</div>
				</div>
				<CardDescription>
					{$_('config.ocr.description')}
				</CardDescription>
			</CardHeader>
			{#if !sectionCollapsed.ocr}
				<CardContent>
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
				</CardContent>
			{/if}
		</Card>

		<!-- VLM Section -->
		<Card class="mb-6">
			<CardHeader class="cursor-pointer" on:click={() => toggleSection('vlm')}>
				<div class="flex justify-between items-center">
					<CardTitle>{$_('config.vlm.title')}</CardTitle>
					<div>
						{#if sectionCollapsed.vlm}
							<ChevronDown size={20} />
						{:else}
							<ChevronUp size={20} />
						{/if}
					</div>
				</div>
				<CardDescription>
					{$_('config.vlm.description')}
				</CardDescription>
			</CardHeader>
			{#if !sectionCollapsed.vlm}
				<CardContent>
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
				</CardContent>
			{/if}
		</Card>

		<!-- Embedding Section -->
		<Card class="mb-6">
			<CardHeader class="cursor-pointer" on:click={() => toggleSection('embedding')}>
				<div class="flex justify-between items-center">
					<CardTitle>{$_('config.embedding.title')}</CardTitle>
					<div>
						{#if sectionCollapsed.embedding}
							<ChevronDown size={20} />
						{:else}
							<ChevronUp size={20} />
						{/if}
					</div>
				</div>
				<CardDescription>
					{$_('config.embedding.description')}
				</CardDescription>
			</CardHeader>
			{#if !sectionCollapsed.embedding}
				<CardContent>
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
				</CardContent>
			{/if}
		</Card>
	{/if}
</div> 