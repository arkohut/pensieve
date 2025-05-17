<script lang="ts">
  import { marked } from 'marked';
  import { ScrollArea } from '$lib/components/ui/scroll-area';
  import OCRTable from '$lib/OCRTable.svelte';
  import CopyToClipboard from '$lib/components/CopyToClipboard.svelte';

  let {
    entity
  } = $props();

  // Process entity.metadata_entries and parse JSON values
  let processedMetadata = $derived(
    entity?.metadata_entries 
      ? entity.metadata_entries.map((entry: any) => {
          // Create a new object to avoid modifying the original
          const processed = { ...entry };
          
          // Parse JSON value if the data_type is JSON_DATA
          if (entry.data_type === 'json') {
            try {
              processed.value = JSON.parse(entry.value);
            } catch (error) {
              console.error(`Error parsing JSON for key ${entry.key}:`, error);
              // Keep original value if parsing fails
              processed.value = entry.value;
            }
          }
          
          return processed;
        })
      : []
  );

  // Process entity.metadata_entries
  let displayEntries = $derived(
    processedMetadata 
      ? [...processedMetadata]
        .filter((entry: any) =>
          entry.key !== 'timestamp' &&
          entry.key !== 'sequence' &&
          entry.key !== 'active_app' &&
          entry.key !== 'active_window')
        .sort((a: any, b: any) => {
          if (a.key === 'ocr_result') return 1;
          if (b.key === 'ocr_result') return -1;
          return 0;
        })
      : []
  );

  // Check if the data structure is valid for OCRTable
  function isValidOCRDataStructure(data: any): boolean {
    if (!Array.isArray(data)) return false;
    for (const item of data) {
      if (
        !item.hasOwnProperty('dt_boxes') ||
        !item.hasOwnProperty('rec_txt') ||
        !item.hasOwnProperty('score')
      ) {
        return false;
      }
      if (
        !Array.isArray(item.dt_boxes) ||
        typeof item.rec_txt !== 'string' ||
        typeof item.score !== 'number'
      ) {
        return false;
      }
    }
    return true;
  }
</script>

<ScrollArea class="mt-4 md:mt-0 md:ml-6 md:w-1/2 max-h-[calc(100vh-180px)] overflow-y-auto">
  {#if entity?.tags && entity.tags.length > 0}
    <div class="mb-4">
      <div class="uppercase tracking-wide text-sm text-indigo-600 font-bold">TAGS</div>
      <div class="text-gray-600">
        {#each entity.tags as tag}
          <span class="text-base text-gray-500 inline-block mr-2">
            {typeof tag === 'string' ? tag : tag.name}
          </span>
        {/each}
      </div>
    </div>
  {/if}
  
  <div class="uppercase tracking-wide text-sm text-indigo-600 font-bold">METADATA</div>
  <div class="mt-2 text-gray-600 pb-4">
    {#each displayEntries as entry}
      <div class="mb-2">
        <span class="font-bold flex items-center">
          {entry.key}
          <CopyToClipboard text={entry.value} />
        </span>
        {#if typeof entry.value === 'object'}
          {#if isValidOCRDataStructure(entry.value)}
            <OCRTable ocrData={entry.value} />
          {:else}
            <pre class="bg-gray-100 p-2 rounded overflow-y-auto max-h-80">
              {JSON.stringify(entry.value, null, 2)}
            </pre>
          {/if}
        {:else}
          <!-- Render markdown content -->
          <div class="prose">
            {@html marked(entry.value)}
          </div>
        {/if}
        <span class="text-sm text-gray-500">({entry.source})</span>
      </div>
    {/each}
  </div>
  
  <!-- Display app_name if present in metadata -->
  {#if entity?.metadata_entries?.some((entry: any) => entry.key === 'active_app')}
    <div class="uppercase tracking-wide text-sm text-indigo-600 font-bold mt-6">APP NAME</div>
    <div class="text-base text-gray-700 mb-4">
      {entity.metadata_entries.find((entry: any) => entry.key === 'active_app')?.value || 'unknown'}
    </div>
  {/if}
</ScrollArea> 