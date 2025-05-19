<script>
  import { ChevronLeft, ChevronRight, X } from '@lucide/svelte';
  import { _ } from 'svelte-i18n';
  import { goto } from '$app/navigation';
  import EntityImage from './EntityImage.svelte';
  import EntityDetail from './EntityDetail.svelte';

  /**
   * @typedef {Object} Props
   * @property {string} id
   * @property {number} library_id
   * @property {number} file_created_at
   * @property {number} folder_id
   * @property {any} image
   * @property {string} filepath
   * @property {string} title
   * @property {any} app_name
   * @property {Array<string>} [tags]
   * @property {Array<{key: string, source: string, value: any}>} [metadata_entries]
   * @property {any} onClose
   * @property {any} onNext
   * @property {any} onPrevious
   */

  /** @type {Props} */
  let {
    id,
    library_id,
    file_created_at,
    folder_id,
    image,
    filepath,
    tags = [],
    metadata_entries = [],
    onClose,
    onNext,
    onPrevious
  } = $props();

  let showDetails = $state(false);

  $effect(() => {
    const savedState = localStorage.getItem('figureShowDetails');
    showDetails = savedState ? JSON.parse(savedState) : false;
  });

  function toggleDetails() {
    showDetails = !showDetails;
    localStorage.setItem('figureShowDetails', JSON.stringify(showDetails));
  }

  // English comment: This function navigates to the entity detail page.
  function goToDetail() {
    goto(`/entities/${id}`);
  }

  // Create an entity object from the props to pass to the components
  const entity = $derived({
    id,
    library_id,
    file_created_at,
    folder_id,
    image,
    filepath,
    tags,
    metadata_entries
  });

  $inspect(entity);
</script>

<div
  class="fixed inset-0 bg-gray-600 bg-opacity-50 h-full w-full z-40 flex items-center justify-center"
  id="my-modal"
>
  <div
    class="relative mx-auto border w-11/12 max-w-[95vw] h-[95vh] shadow-lg rounded-md bg-white group"
  >
    <div class="absolute inset-0 px-10 py-4">
      <!-- Button container -->
      <div class="group absolute inset-x-0 h-full">
        <button
          class="absolute p-2 left-2 top-1/2 transform -translate-y-1/2 rounded-full hover:bg-gray-100 bg-white/80 border opacity-0 group-hover:opacity-100 flex z-[51] transition-all duration-200"
          onclick={onPrevious}
        >
          <ChevronLeft size={24} class="text-indigo-600" />
        </button>
        <button
          class="absolute p-2 right-2 top-1/2 transform -translate-y-1/2 rounded-full hover:bg-gray-100 bg-white/80 border opacity-0 group-hover:opacity-100 flex z-[51] transition-all duration-200"
          onclick={onNext}
        >
          <ChevronRight size={24} class="text-indigo-600" />
        </button>
      </div>

      <div class="flex flex-col md:flex-row h-full relative">
        <!-- Image container -->
        <EntityImage {entity} {showDetails} {toggleDetails} />

        <!-- Details container -->
        {#if showDetails}
          <EntityDetail {entity} />
        {/if}
      </div>

      <div class="absolute top-2 right-2 z-[52]">
        <button
          class="p-2 rounded-full hover:bg-gray-100 bg-white/80 opacity-0 group-hover:opacity-100 transition-all duration-200"
          onclick={onClose}
        >
          <X size={24} class="text-indigo-600" />
        </button>
      </div>
      <!-- English comment: Button to view entity details page, centered at the bottom with 2em spacing -->
      <div
        class="absolute left-1/2 transform -translate-x-1/2 bottom-8 z-[53] flex justify-center w-full pointer-events-none"
      >
        <button
          class="pointer-events-auto py-2 px-4 rounded-full hover:bg-indigo-100 bg-white/80 border border-indigo-200 text-indigo-700 font-semibold transition shadow-lg text-sm"
          onclick={goToDetail}
        >
          {$_('figure.viewContext')}
        </button>
      </div>
    </div>
  </div>
</div>
