<script lang="ts">
  import { PUBLIC_API_ENDPOINT } from '$env/static/public';
  import { goto } from '$app/navigation';
  import * as Tooltip from "$lib/components/ui/tooltip";
  import { onMount } from 'svelte';

  // Define interface for metadata entries
  interface EntityMetadata {
    key: string;
    value: string;
    source?: string;
    data_type?: string;
  }

  // Props
  let { 
    entity, 
    contextData = { prev: [], next: [] },
    onSelectEntity
  } = $props();

  // Handle entity selection with URL update
  function handleEntitySelect(id: number, e: Event) {
    e.preventDefault(); // Prevent default navigation
    
    // Update the URL without a full page reload
    goto(`/entities/${id}`, { replaceState: false, noScroll: true });
    
    // Call the passed function to update entity data
    onSelectEntity(id);
  }

  // Format date to readable string
  function formatDate(dateStr: string): string {
    if (!dateStr) return '';
    try {
      const utcDate = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z';
      const date = new Date(utcDate);
      console.log(date);
      return date.toLocaleString(undefined, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      });
    } catch (e) {
      try {
        const date = new Date(dateStr);
        return date.toLocaleString(undefined, {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          hour12: false
        });
      } catch (innerError) {
        return dateStr;
      }
    }
  }
  
  // 滚动容器引用
  let scrollContainerRef: HTMLElement;
  
  // 鼠标滚轮处理
  function handleWheel(e: WheelEvent) {
    // 检查是否是鼠标滚轮事件 (而非触摸板)
    // 触摸板通常产生的是具有惯性的平滑滚动，而鼠标滚轮产生的是离散的滚动
    if (Math.abs(e.deltaY) >= 10 && e.deltaMode === 0) {  // 判断是否可能是鼠标滚轮
      e.preventDefault(); // 阻止默认的垂直滚动
      // 将垂直滚动转换为水平滚动
      scrollContainerRef.scrollLeft += e.deltaY;
    }
    // 不处理触摸板事件，让它保持原始行为
  }
  
  onMount(() => {
    // 添加鼠标滚轮事件监听
    if (scrollContainerRef) {
      scrollContainerRef.addEventListener('wheel', handleWheel, { passive: false });
      
      // 清理函数
      return () => {
        scrollContainerRef.removeEventListener('wheel', handleWheel);
      };
    }
  });

  const apiEndpoint = (typeof PUBLIC_API_ENDPOINT !== 'undefined' ? PUBLIC_API_ENDPOINT : window.location.origin) + '/api';
</script>

<!-- Context navigation bar - full width with proper scrolling -->
<div class="h-full w-full flex items-center">
  <div class="w-full px-2 overflow-x-auto" bind:this={scrollContainerRef}>
    <div class="flex items-center justify-start gap-3 min-w-max pb-2">
      <Tooltip.Provider delayDuration={0}>
        {#each contextData.prev as contextEntity}
          <!-- Click to navigate to the selected entity's detail page -->
          <div class="flex-none w-24 h-24">
            <Tooltip.Root>
              <Tooltip.Trigger class="w-full h-full">
                <a 
                  href={`/entities/${contextEntity.id}`}
                  class="block w-full h-full rounded-lg overflow-hidden cursor-pointer opacity-70 hover:opacity-100 transition-opacity"
                  onclick={(e) => handleEntitySelect(contextEntity.id, e)}
                >
                  <img
                    src={`${apiEndpoint}/thumbnails/${contextEntity.filepath.replace(/^\/+/, '')}`}
                    alt=""
                    class="w-full h-full object-cover"
                  />
                </a>
              </Tooltip.Trigger>
              <Tooltip.Content>
                {contextEntity.metadata_entries?.find((entry: EntityMetadata) => entry.key === 'screen_name')?.value || ''} {contextEntity.metadata_entries?.find((entry: EntityMetadata) => entry.key === 'active_app')?.value || ''} {formatDate(contextEntity.file_created_at)}
              </Tooltip.Content>
            </Tooltip.Root>
          </div>
        {/each}
        
        <!-- Current entity -->
        <div class="flex-none w-28 h-28 rounded-lg overflow-hidden border-2 border-indigo-500 shadow-md">
          <Tooltip.Root>
            <Tooltip.Trigger class="w-full h-full">
              <img
                src={entity.image || `${apiEndpoint}/thumbnails/${entity.filepath.replace(/^\/+/, '')}`}
                alt=""
                class="w-full h-full object-cover"
              />
            </Tooltip.Trigger>
            <Tooltip.Content>
              {entity.metadata_entries?.find((entry: EntityMetadata) => entry.key === 'screen_name')?.value || ''} {entity.metadata_entries?.find((entry: EntityMetadata) => entry.key === 'active_app')?.value || ''} {formatDate(entity.file_created_at)}
            </Tooltip.Content>
          </Tooltip.Root>
        </div>
        
        {#each contextData.next as contextEntity}
          <!-- Click to navigate to the selected entity's detail page -->
          <div class="flex-none w-24 h-24">
            <Tooltip.Root>
              <Tooltip.Trigger class="w-full h-full">
                <a 
                  href={`/entities/${contextEntity.id}`}
                  class="flex-none w-full h-full rounded-lg overflow-hidden cursor-pointer opacity-70 hover:opacity-100 transition-opacity"
                  onclick={(e) => handleEntitySelect(contextEntity.id, e)}
                >
                  <img
                    src={`${apiEndpoint}/thumbnails/${contextEntity.filepath.replace(/^\/+/, '')}`}
                    alt=""
                    class="w-full h-full object-cover"
                  />
                </a>
              </Tooltip.Trigger>
              <Tooltip.Content>
                {contextEntity.metadata_entries?.find((entry: EntityMetadata) => entry.key === 'screen_name')?.value || ''} {contextEntity.metadata_entries?.find((entry: EntityMetadata) => entry.key === 'active_app')?.value || ''} {formatDate(contextEntity.file_created_at)}
              </Tooltip.Content>
            </Tooltip.Root>
          </div>
        {/each}
      </Tooltip.Provider>
    </div>
  </div>
</div> 