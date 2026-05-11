import { createRootRouteWithContext, Outlet } from '@tanstack/react-router';
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools';
import type { QueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Github } from 'lucide-react';
import { TopProgressBar } from '$/components/common/TopProgressBar';

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
      <TopProgressBar />
      <div className="min-h-screen">
        <div className="mx-auto max-w-screen-2xl px-4 sm:px-6 lg:px-8">
          <div className="relative pb-12 pt-0">
            <Outlet />
          </div>
        </div>
        <footer className="border-t border-border">
          <div className="mx-auto flex max-w-screen-xl items-center justify-between px-6 py-4 text-xs text-muted-foreground">
            <span>{t('copyright')}</span>
            <a
              href="https://github.com/arkohut/pensieve"
              target="_blank"
              rel="noopener noreferrer"
              className="transition-colors hover:text-foreground"
              aria-label={t('github')}
            >
              <Github size={14} />
            </a>
          </div>
        </footer>
      </div>
      {import.meta.env.DEV && <TanStackRouterDevtools />}
    </div>
  );
}
