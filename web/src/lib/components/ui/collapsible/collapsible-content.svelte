<script lang="ts">
	import { Collapsible as CollapsiblePrimitive } from "bits-ui";
	import { slide } from "svelte/transition";
	import { cn } from "$lib/utils.js";

	type $$Props = CollapsiblePrimitive.ContentProps;

	let className: $$Props["class"] = undefined;
	export { className as class };
</script>

<CollapsiblePrimitive.Content
	transition={slide}
	class={cn(className)}
	{...$$restProps}
>
	<slot />
</CollapsiblePrimitive.Content>
