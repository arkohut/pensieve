<script lang="ts">
	import { Collapsible as CollapsiblePrimitive } from "bits-ui";
	import { cn } from "$lib/utils.js";

	type $$Props = CollapsiblePrimitive.Props;

	let className: $$Props["class"] = undefined;
	export let open: $$Props["open"] = undefined;
	export { className as class };
</script>

<CollapsiblePrimitive.Root
	bind:open
	class={cn(className)}
	{...$$restProps}
>
	<slot />
</CollapsiblePrimitive.Root> 