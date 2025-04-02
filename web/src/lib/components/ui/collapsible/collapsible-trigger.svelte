<script lang="ts">
	import { Collapsible as CollapsiblePrimitive } from "bits-ui";
	import { cn } from "$lib/utils.js";

	type $$Props = CollapsiblePrimitive.TriggerProps;

	let className: $$Props["class"] = undefined;
	export { className as class };
</script>

<CollapsiblePrimitive.Trigger
	class={cn(className)}
	{...$$restProps}
>
	<slot />
</CollapsiblePrimitive.Trigger> 