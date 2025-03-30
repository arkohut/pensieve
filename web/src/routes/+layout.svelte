<script lang="ts">
	import '../i18n';
	import '../app.css';
	import { _ } from 'svelte-i18n';
	import LanguageSwitcher from '$lib/LanguageSwitcher.svelte';
	import { Github } from 'lucide-svelte';
</script>

<svelte:head>
	<title>Pensieve</title>
</svelte:head>

<div class="min-h-screen bg-gradient">
	<div class="min-h-screen">
		<div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
			<div class="relative pt-6 pb-16">
				<slot />
			</div>
		</div>
		
		<!-- Footer -->
		<footer class="w-full mx-auto mt-8">
			<div class="container mx-auto">
				<div class="border-t border-slate-900/5 py-10 text-center">
					<p class="mt-2 text-sm leading-6 text-slate-500">{$_('slogan')}</p>
					<p class="mt-2 text-sm leading-6 text-slate-500">{$_('copyright')}</p>
					<div class="mt-2 flex justify-center items-center space-x-4 text-sm font-semibold leading-6 text-slate-700">
						<a href="https://github.com/arkohut/memos" 
						   target="_blank" 
						   rel="noopener noreferrer"
						   class="hover:text-slate-900 transition-colors">
							<Github size={16} />
						</a>
						<div class="h-4 w-px bg-slate-500/20" />
						<LanguageSwitcher />
					</div>
				</div>
			</div>
		</footer>
	</div>
</div>
