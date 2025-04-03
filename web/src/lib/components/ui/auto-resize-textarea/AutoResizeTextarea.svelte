<script lang="ts">
	import { onMount } from 'svelte';

	export let value: string = '';
	export let id: string | undefined = undefined;
	export let placeholder: string | undefined = undefined;
	export let disabled: boolean = false;
	export let minRows: number = 3;
	export let className: string = '';

	let textareaElement: HTMLTextAreaElement;

	// 添加自动调整文本区域高度的函数
	function adjustTextareaHeight(textarea: HTMLTextAreaElement) {
		// 设置最小高度（基于行数）
		const lineHeight = 24; // 假设每行高度为24px
		const minHeight = lineHeight * minRows;
		
		// 重置高度以获取实际内容高度
		textarea.style.height = 'auto';
		
		// 计算新高度（内容高度和最小高度中的较大值）
		const newHeight = Math.max(textarea.scrollHeight, minHeight);
		
		// 设置新高度
		textarea.style.height = newHeight + 'px';
	}

	// 监听值的变化
	$: if (textareaElement && value !== undefined) {
		setTimeout(() => adjustTextareaHeight(textareaElement), 0);
	}

	// 组件挂载时初始化
	onMount(() => {
		if (textareaElement) {
			adjustTextareaHeight(textareaElement);
		}
	});
</script>

<textarea
	bind:this={textareaElement}
	{id}
	{placeholder}
	{disabled}
	bind:value
	class="resize-none overflow-hidden w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 {className}"
	on:input={(e) => {
		adjustTextareaHeight(e.currentTarget);
	}}
	{...$$restProps}
/> 