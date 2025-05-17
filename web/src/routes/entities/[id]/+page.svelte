<script lang="ts">
  import { onMount } from 'svelte';
  import { PUBLIC_API_ENDPOINT } from '$env/static/public';
  import EntityImage from '$lib/EntityImage.svelte';
  import EntityDetail from '$lib/EntityDetail.svelte';
  import ContextNavigationBar from '$lib/ContextNavigationBar.svelte';
  import { goto } from '$app/navigation';
  import { Home, Loader } from '@lucide/svelte';

  let entity: any = $state(null);
  let loading = $state(true); // 初始加载状态
  let navigating = $state(false); // 导航中状态，用于显示局部加载指示器
  let contextData: { prev: any[]; next: any[] } = $state({ prev: [], next: [] });
  const CONTEXT_SIZE = 12;

  // Add showDetails state and toggleDetails logic (like Figure)
  let showDetails = $state(true);

  function toggleDetails() {
    showDetails = !showDetails;
    localStorage.setItem('entityShowDetails', JSON.stringify(showDetails));
  }
  
  // Navigate back to home
  function goToHome() {
    goto('/');
  }
  
  // Navigate to previous entity
  function navigateToPrevious() {
    if (contextData.prev && contextData.prev.length > 0) {
      handleSelect(contextData.prev[contextData.prev.length - 1].id);
    }
  }
  
  // Navigate to next entity
  function navigateToNext() {
    if (contextData.next && contextData.next.length > 0) {
      handleSelect(contextData.next[0].id);
    }
  }
  
  // Handle keyboard navigation
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'ArrowLeft') {
      navigateToPrevious();
    } else if (event.key === 'ArrowRight') {
      navigateToNext();
    }
  }

  // English comment: Fetch entity detail by id from API when page loads
  onMount(() => {
    // Load details state from localStorage
    const savedState = localStorage.getItem('entityShowDetails');
    if (savedState !== null) {
      showDetails = JSON.parse(savedState);
    }
    
    // 初始加载实体
    const loadInitialEntity = async () => {
      const id = window.location.pathname.split('/').pop();
      const apiBase = typeof PUBLIC_API_ENDPOINT !== 'undefined' ? PUBLIC_API_ENDPOINT : window.location.origin;
      const res = await fetch(`${apiBase}/api/entities/${id}`);
      entity = await res.json();
      loading = false;
      if (entity && entity.library_id && entity.id) {
        fetchContext(entity.library_id, entity.id);
      }
    };
    
    loadInitialEntity();
    
    // Add keyboard event listener
    window.addEventListener('keydown', handleKeydown);
    
    // Clean up event listener on component unmount
    return () => {
      window.removeEventListener('keydown', handleKeydown);
    };
  });

  // English comment: Fetch context for the current entity
  async function fetchContext(libraryId: number, entityId: number) {
    try {
      const response = await fetch(
        `${PUBLIC_API_ENDPOINT}/api/libraries/${libraryId}/entities/${entityId}/context?prev=${CONTEXT_SIZE}&next=${CONTEXT_SIZE}`
      );
      if (response.ok) {
        contextData = await response.json();
      }
    } catch (error) {
      console.error('Error fetching entity context:', error);
    }
  }

  // Handle navigation to another entity in context bar (in-page update, no full reload)
  async function handleSelect(id: number) {
    // Update URL without page refresh
    const url = `/entities/${id}`;
    window.history.pushState({ id }, '', url);
    
    // 设置为导航状态而不是加载状态
    navigating = true;
    
    try {
      // Fetch new entity data
      const apiBase = typeof PUBLIC_API_ENDPOINT !== 'undefined' ? PUBLIC_API_ENDPOINT : window.location.origin;
      const res = await fetch(`${apiBase}/api/entities/${id}`);
      entity = await res.json();
      
      // Fetch new context
      if (entity && entity.library_id && entity.id) {
        const contextRes = await fetch(
          `${PUBLIC_API_ENDPOINT}/api/libraries/${entity.library_id}/entities/${entity.id}/context?prev=${CONTEXT_SIZE}&next=${CONTEXT_SIZE}`
        );
        if (contextRes.ok) {
          contextData = await contextRes.json();
        }
      }
    } catch (error) {
      console.error('Error navigating to entity:', error);
    } finally {
      navigating = false;
    }
  }
</script>

{#snippet HomeButton()}
  <button 
    class="p-2 rounded-full hover:bg-gray-100 flex items-center gap-2 text-indigo-600 mr-2"
    onclick={goToHome}
  >
    <Home size={18} class="text-indigo-600" />
  </button>
{/snippet}

{#if loading}
  <div class="fixed inset-0 bg-gray-600 bg-opacity-50 h-full w-full z-40 flex items-center justify-center">
    <Loader size={36} class="text-primary animate-spin" />
  </div>
{:else if entity}
  <div class="fixed inset-0 bg-gray-600 bg-opacity-50 h-full w-full z-40 flex flex-col">
    <!-- Main content area - the flex layout is important for proper sizing -->
    <div class="flex-grow flex flex-col">
      <!-- Main content modal with rounded top corners -->
      <div class="flex flex-col h-[calc(100vh-180px)] w-11/12 max-w-[95vw] mx-auto mt-6 rounded-t-md bg-white overflow-hidden relative">
        {#if navigating}
          <!-- 导航加载指示器 - 半透明覆盖，避免闪屏 -->
          <div class="absolute inset-0 flex items-center justify-center z-50">
            <div class="bg-white p-4 rounded-lg shadow-lg flex items-center justify-center">
              <Loader size={28} class="text-primary animate-spin" />
            </div>
          </div>
        {/if}
        
        <!-- Entity content - flex-grow to take all available space -->
        <div class="flex-grow overflow-hidden">
          <div class="h-full px-10 py-4">
            <div class="flex flex-col md:flex-row h-full">
              <EntityImage 
                {entity}
                {showDetails}
                {toggleDetails}
                LeftIcon={HomeButton}
              />
              
              {#if showDetails}
                <EntityDetail 
                  {entity}
                />
              {/if}
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Navigation bar at the bottom - full width of screen with increased height -->
    <div class="h-[180px] w-full bg-gray-50 shadow-inner border-t">
      <div class="mx-auto h-full py-3">
        <ContextNavigationBar 
          {entity} 
          {contextData}
          onSelectEntity={handleSelect}
        />
      </div>
    </div>
    
    <!-- Navigation buttons (hidden but accessible for keyboard nav) -->
    <div class="sr-only">
      <button onclick={navigateToPrevious}>Previous</button>
      <button onclick={navigateToNext}>Next</button>
    </div>
  </div>
{:else}
  <p>Entity not found.</p>
{/if} 