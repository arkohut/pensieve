<script lang="ts">
  import { Checkbox } from '$lib/components/ui/checkbox';
  import { Label } from '$lib/components/ui/label';

  interface Props {
    facet: { field_name: string; counts: { value: string; count: number }[] };
    selectedItems: Record<string, boolean>;
    onItemChange: (item: string, checked: boolean) => void;
  }

  let { facet, selectedItems, onItemChange }: Props = $props();

  let title = $derived(facet.field_name === 'app_names' ? 'App Names' : 'Created Date');
</script>

<div class="mb-4">
  <h3 class="text-lg font-semibold mb-2">{title}</h3>
  {#each facet.counts as item}
    <div class="mb-2 items-top flex space-x-2">
      <Checkbox
        id={`${facet.field_name}-${item.value}`}
        checked={selectedItems[item.value] || false}
        onCheckedChange={(checked) => onItemChange(item.value, checked)}
      />
      <Label for={`${facet.field_name}-${item.value}`} class="flex items-center text-sm">
        {item.value} ({item.count})
      </Label>
    </div>
  {/each}
</div>
