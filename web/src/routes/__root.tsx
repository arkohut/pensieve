import { createRootRouteWithContext, Outlet } from '@tanstack/react-router';
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools';
import type { QueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Github } from 'lucide-react';
import { LanguageSwitcher } from '$/components/common/LanguageSwitcher';

interface RouterContext {
  queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
});

function RootLayout() {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen bg-background">
      <div className="min-h-screen">
        <div className="mx-auto max-w-screen-2xl px-4 sm:px-6 lg:px-8">
          <div className="relative pb-16 pt-0">
            <Outlet />
          </div>
        </div>
        <footer className="mx-auto mt-8 w-full">
          <div className="container mx-auto">
            <div className="border-t border-slate-900/5 py-10 text-center">
              <p className="mt-2 text-sm leading-6 text-slate-500">{t('slogan')}</p>
              <p className="mt-2 text-sm leading-6 text-slate-500">{t('copyright')}</p>
              <div className="mt-2 flex items-center justify-center space-x-4 text-sm font-semibold leading-6 text-slate-700">
                <a
                  href="https://github.com/arkohut/pensieve"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="transition-colors hover:text-slate-900"
                  aria-label={t('github')}
                >
                  <Github size={16} />
                </a>
                <div className="h-4 w-px bg-slate-500/20" />
                <LanguageSwitcher />
              </div>
            </div>
          </div>
        </footer>
      </div>
      {import.meta.env.DEV && <TanStackRouterDevtools />}
    </div>
  );
}
