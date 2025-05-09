<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { toast } from 'svelte-sonner';
    import { _ } from 'svelte-i18n';

    interface Props {
        apiEndpoint: string;
        onStatusChange: () => void;
    }

    let { apiEndpoint, onStatusChange = () => {} }: Props = $props();

    let isRestarting = $state(true);
    let healthCheckInterval: ReturnType<typeof setInterval> | null = null;
    let healthCheckAttempts = $state(0);
    const MAX_HEALTH_CHECK_ATTEMPTS = 60;

    function clearHealthCheck() {
        if (healthCheckInterval) {
            clearInterval(healthCheckInterval);
            healthCheckInterval = null;
        }
    }

    async function checkHealth() {
        try {
            const response = await fetch(`${apiEndpoint}/health`, { cache: 'no-store' });
            if (response.ok) {
                isRestarting = false;
                onStatusChange();
                clearHealthCheck();
                healthCheckAttempts = 0;
                toast.success($_('config.title'), {
                    description: $_('config.servicesRestarted')
                });
            } else {
                healthCheckAttempts++;
                if (healthCheckAttempts >= MAX_HEALTH_CHECK_ATTEMPTS) {
                    // 超过最大尝试次数，认为服务可能未能成功重启
                    isRestarting = false;
                    onStatusChange();
                    clearHealthCheck();
                    toast.error($_('config.error'), {
                        description: $_('config.servicesRestartTimeout')
                    });
                }
            }
        } catch (err) {
            // 请求失败表示服务可能仍在重启中，继续等待
            healthCheckAttempts++;
            if (healthCheckAttempts >= MAX_HEALTH_CHECK_ATTEMPTS) {
                isRestarting = false;
                onStatusChange();
                clearHealthCheck();
                toast.error($_('config.error'), {
                    description: $_('config.servicesRestartTimeout')
                });
            }
        }
    }

    // 开始健康检查
    export function startHealthCheck() {
        healthCheckAttempts = 0;
        isRestarting = true;
     
        // 延迟 1 秒后开始检查健康状态，因为服务需要一些时间来关闭和重启
        setTimeout(() => {
            healthCheckInterval = setInterval(checkHealth, 1000);
        }, 1000);
    }

    // 组件挂载时自动开始健康检查
    onMount(() => {
        startHealthCheck();
    });

    // 组件销毁时清除定时器
    onDestroy(() => {
        clearHealthCheck();
    });
</script>

{#if isRestarting}
    <div class="fixed inset-0 bg-black/70 flex flex-col items-center justify-center z-50">
        <div class="animate-spin rounded-full h-16 w-16 border-4 border-t-primary border-r-transparent border-b-primary border-l-transparent mb-4"></div>
        <h3 class="text-xl font-medium text-white mb-2">{$_('config.servicesRestartingTitle')}</h3>
        <p class="text-white text-center max-w-md">{$_('config.servicesRestartingMessage')}</p>
    </div>
{/if} 