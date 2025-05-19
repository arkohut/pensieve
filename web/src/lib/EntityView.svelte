<script lang="ts">
  import EntityImage from './EntityImage.svelte';
  import EntityDetail from './EntityDetail.svelte';

  // Props in a single $props() call
  let { entity, showDetails = true, toggleDetails } = $props();

  $inspect(entity);
</script>

<div class="flex flex-col md:flex-row h-full relative">
  <!-- Left: Image and basic info -->
  <EntityImage 
    {entity}
    {showDetails}
    {toggleDetails}
  />
  
  <!-- Right: Details, tags, metadata -->
  {#if showDetails}
    <EntityDetail 
      {entity}
    />
  {/if}
</div> 