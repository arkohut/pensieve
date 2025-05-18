<script lang="ts">
  import { PUBLIC_API_ENDPOINT } from '$env/static/public';
  import { IndentIncrease, Library, Folder, Hash, FileClock } from '@lucide/svelte';
  import LucideIcon from './components/LucideIcon.svelte';
  import { translateAppName } from './utils';

  let {
    entity,
    showDetails = false,
    toggleDetails,
    LeftIcon = null,
  } = $props();

  // Compute title and app_name from entity if not explicitly provided
  let displayTitle = $derived(entity ? getEntityTitle(entity) : 'unknown');
  let displayAppName = $derived(entity ? getAppName(entity) : 'unknown');
  
  // API基础路径
  const apiEndpoint = (typeof PUBLIC_API_ENDPOINT !== 'undefined' ? PUBLIC_API_ENDPOINT : window.location.origin) + '/api';
  
  // 生成视频URL (如果路径存在)
  let videoUrl = $derived(entity?.filepath ? `${apiEndpoint}/files/video/${entity.filepath.replace(/^\/+/, '')}` : null);

  // Helper to extract the entity title from metadata_entries or fallback to filename
  function getEntityTitle(document: any): string {
    if (!document) return '';
    if (document.metadata_entries && 
      document.metadata_entries.some((entry: any) => entry.key === 'active_window')) {
      return document.metadata_entries.find((entry: any) => entry.key === 'active_window').value;
    }
    return document.filepath ? document.filepath.split('/').pop() : '';
  }

  // Helper to extract the app name from metadata_entries or fallback to 'unknown'
  function getAppName(document: any): string {
    if (!document) return 'unknown';
    if (document.metadata_entries && document.metadata_entries.some((entry: any) => entry.key === 'active_app')) {
      return document.metadata_entries.find((entry: any) => entry.key === 'active_app').value;
    } else {
      return "unknown";
    }
  }

  $inspect(entity);
</script>

<div class="flex-none {showDetails ? 'w-full md:w-1/2' : 'w-full'} flex flex-col h-full">
  <div class="mb-2 relative z-[52]">
    <div class="flex items-center text-lg leading-tight font-medium text-black w-full">
      <div class="flex items-center justify-between w-full">
        <!-- Left part - for the icon button -->
        <div class="flex-none">
          {#if LeftIcon}
            {@render LeftIcon()}
          {/if}
        </div>
        
        <!-- Center part - for the title -->
        <div class="flex-1 flex items-center justify-center min-w-0">
          <div class="flex items-center space-x-2 min-w-0">
            <LucideIcon name={translateAppName(displayAppName) || 'Image'} size={24} />
            <p class="truncate max-w-[500px]">{displayTitle}</p>
            {#if !showDetails}
            <span class="inline-flex items-center text-sm text-gray-500 font-mono pl-4">
              <FileClock size={16} class="mr-1 text-gray-500" />
              {entity?.file_created_at ? new Date(entity.file_created_at).toLocaleString() : ''}
            </span>
            {/if}
          </div>
        </div>
        
        <!-- Right part - for the toggle button -->
        <button
          class="p-2 hover:bg-gray-100 rounded-full transition-colors flex-none"
          onclick={toggleDetails}
        >
          <IndentIncrease 
            size={24} 
            class={showDetails ? 'text-indigo-600' : 'text-gray-400'} 
          />
        </button>
      </div>
    </div>
  </div>

  {#if showDetails}
    <div class="mb-2 mr-2 pb-2 border-b border-gray-300">
      <span class="mt-1 text-sm leading-tight font-medium text-gray-500 font-mono">
        <span class="inline-flex mr-4">
          <Library
            size={16}
            class="uppercase tracking-wide text-sm text-indigo-600 font-bold mr-1"
          />
          {entity?.library_id || ''}
        </span>

        <span class="inline-flex mr-4">
          <Folder
            size={16}
            class="uppercase tracking-wide text-sm text-indigo-600 font-bold mr-1"
          />
          {entity?.folder_id || ''}
        </span>

        <span class="inline-flex mr-4">
          <Hash
            size={16}
            class="uppercase tracking-wide text-sm text-indigo-600 font-bold mr-1"
          />
          {entity?.id || ''}
        </span>

        <span class="inline-flex mr-4">
          <FileClock
            size={16}
            class="uppercase tracking-wide text-sm text-indigo-600 font-bold mr-1 font-mono"
          />
          {entity?.file_created_at ? new Date(entity.file_created_at).toLocaleString() : ''}
        </span>
      </span>

      <div>
        <span class="mt-1 text-xs leading-tight font-xs text-gray-500 font-mono">
          {entity?.filepath || ''}
        </span>
      </div>
    </div>
  {/if}

  <div class="relative flex-1 overflow-hidden flex items-center justify-center {showDetails ? 'mr-2' : ''}">
    <!-- 直接使用视频链接，不需要条件判断 -->
    <a href={videoUrl} target="_blank" rel="noopener noreferrer" class="block w-full h-full flex items-center justify-center">
      <img
        class="h-full object-contain rounded-lg drop-shadow-md"
        src={entity?.image || (entity?.filepath ? `${apiEndpoint}/files/${entity.filepath.replace(/^\/+/,'')}` : '')}
        alt={displayTitle}
      />
    </a>
  </div>
</div> 