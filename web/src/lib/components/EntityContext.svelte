<script lang="ts">
    import { run } from 'svelte/legacy';

    import { PUBLIC_API_ENDPOINT } from '$env/static/public';
    
    interface Props {
        libraryId: number;
        entityId: number;
        onSelect: (id: number) => void;
        currentImage: string;
    }

    let {
        libraryId,
        entityId,
        onSelect,
        currentImage
    }: Props = $props();
    
    interface Entity {
        id: number;
        filepath: string;
    }
    
    interface EntityContextData {
        prev: Entity[];
        next: Entity[];
    }
    
    let contextData: EntityContextData = $state({ prev: [], next: [] });
    const CONTEXT_SIZE = 12;
    
    async function fetchContext() {
        try {
            const response = await fetch(
                `${PUBLIC_API_ENDPOINT}/libraries/${libraryId}/entities/${entityId}/context?prev=${CONTEXT_SIZE}&next=${CONTEXT_SIZE}`
            );
            if (response.ok) {
                contextData = await response.json();
            }
        } catch (error) {
            console.error('Error fetching entity context:', error);
        }
    }
    
    run(() => {
        if (entityId && libraryId) {
            fetchContext();
        }
    });
</script>

<div class="absolute bottom-0 left-0 right-0 bg-black/50 backdrop-blur-sm p-4 transition-opacity opacity-0 group-hover:opacity-100">
    <div class="max-w-screen-xl mx-auto">
        <div class="flex items-center justify-center space-x-2 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-gray-400 scrollbar-track-transparent">
            {#each contextData.prev as entity}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <div 
                    class="flex-none w-24 h-24 rounded-lg overflow-hidden cursor-pointer opacity-70 hover:opacity-100 transition-opacity"
                    onclick={() => onSelect(entity.id)}
                >
                    <img
                        src={`${PUBLIC_API_ENDPOINT}/files/${entity.filepath}`}
                        alt=""
                        class="w-full h-full object-cover"
                    />
                </div>
            {/each}
            
            <!-- Current entity -->
            <div class="flex-none w-24 h-24 rounded-lg overflow-hidden border-2 border-white">
                <img
                    src={currentImage}
                    alt=""
                    class="w-full h-full object-cover"
                />
            </div>
            
            {#each contextData.next as entity}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <div 
                    class="flex-none w-24 h-24 rounded-lg overflow-hidden cursor-pointer opacity-70 hover:opacity-100 transition-opacity"
                    onclick={() => onSelect(entity.id)}
                >
                    <img
                        src={`${PUBLIC_API_ENDPOINT}/files/${entity.filepath}`}
                        alt=""
                        class="w-full h-full object-cover"
                    />
                </div>
            {/each}
        </div>
    </div>
</div>

<style>
    /* Add custom scrollbar styling */
    .scrollbar-thin::-webkit-scrollbar {
        height: 6px;
    }
    
    .scrollbar-thin::-webkit-scrollbar-track {
        background: transparent;
    }
    
    .scrollbar-thin::-webkit-scrollbar-thumb {
        background: rgba(156, 163, 175, 0.5);
        border-radius: 3px;
    }
    
    .scrollbar-thin::-webkit-scrollbar-thumb:hover {
        background: rgba(156, 163, 175, 0.8);
    }
</style> 