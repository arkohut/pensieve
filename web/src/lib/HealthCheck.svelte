<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { toast } from 'svelte-sonner';
    import { _ } from 'svelte-i18n';

    // 传入API端点供健康检查使用
    export let apiEndpoint: string;
    // 重启状态
    export let servicesRestarting: boolean = false;
    // 回调函数，用于通知父组件健康检查状态变化
    export let onStatusChange: (restarting: boolean) => void = () => {};

    let healthCheckInterval: ReturnType<typeof setInterval> | null = null;
    let healthCheckAttempts = 0;
    const MAX_HEALTH_CHECK_ATTEMPTS = 60; // 最多尝试60次，总时长约为3分钟

    // 清除健康检查定时器
    function clearHealthCheck() {
        if (healthCheckInterval) {
            clearInterval(healthCheckInterval);
            healthCheckInterval = null;
        }
    }

    // 检查服务健康状态
    async function checkHealth() {
        try {
            const response = await fetch(`${apiEndpoint}/health`, { cache: 'no-store' });
            if (response.ok) {
                // 服务已恢复
                servicesRestarting = false;
                onStatusChange(false);
                clearHealthCheck();
                healthCheckAttempts = 0;
                toast.success($_('config.title'), {
                    description: $_('config.servicesRestarted')
                });
            } else {
                healthCheckAttempts++;
                if (healthCheckAttempts >= MAX_HEALTH_CHECK_ATTEMPTS) {
                    // 超过最大尝试次数，认为服务可能未能成功重启
                    servicesRestarting = false;
                    onStatusChange(false);
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
                servicesRestarting = false;
                onStatusChange(false);
                clearHealthCheck();
                toast.error($_('config.error'), {
                    description: $_('config.servicesRestartTimeout')
                });
            }
        }
    }

    // 开始健康检查
    export function startHealthCheck() {
        // 重置尝试次数
        healthCheckAttempts = 0;
        // 设置重启状态
        servicesRestarting = true;
        onStatusChange(true);
        
        // 延迟3秒后开始检查健康状态，因为服务需要一些时间来关闭和重启
        setTimeout(() => {
            // 每3秒检查一次健康状态
            healthCheckInterval = setInterval(checkHealth, 3000);
        }, 3000);
    }

    // 组件销毁时清除定时器
    onDestroy(() => {
        clearHealthCheck();
    });
</script>

{#if servicesRestarting}
    <div class="fixed inset-0 bg-black/70 flex flex-col items-center justify-center z-50">
        <div class="animate-spin rounded-full h-16 w-16 border-4 border-t-primary border-r-transparent border-b-primary border-l-transparent mb-4"></div>
        <h3 class="text-xl font-medium text-white mb-2">{$_('config.servicesRestartingTitle')}</h3>
        <p class="text-white text-center max-w-md">{$_('config.servicesRestartingMessage')}</p>
    </div>
{/if} 