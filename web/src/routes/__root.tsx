import { createRootRouteWithContext, Outlet } from '@tanstack/react-router';
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools';
import type { QueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Github } from 'lucide-react';
import { LanguageSwitcher } from '$/components/common/LanguageSwitcher';
import { ThemeToggle } from '$/components/common/ThemeToggle';

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
            <div className="border-t py-10 text-center">
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{t('slogan')}</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{t('copyright')}</p>
              <div className="mt-2 flex items-center justify-center space-x-4 text-sm font-semibold leading-6 text-foreground">
                <a
                  href="https://github.com/arkohut/pensieve"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="transition-colors hover:text-primary"
                  aria-label={t('github')}
                >
                  <Github size={16} />
                </a>
                <div className="h-4 w-px bg-border" />
                <LanguageSwitcher />
                <div className="h-4 w-px bg-border" />
                <ThemeToggle />
              </div>
            </div>
          </div>
        </footer>
      </div>
      {import.meta.env.DEV && <TanStackRouterDevtools />}
    </div>
  );
}
