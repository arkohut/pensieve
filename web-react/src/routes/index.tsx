import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Settings } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { Input } from '$/components/ui/input';
import { Logo } from '$/components/common/Logo';
import { ErrorState } from '$/components/common/ErrorState';
import { searchSchema, type SearchParams } from '$/lib/search-params';
import { useSearch } from '$/lib/api/search';

export const Route = createFileRoute('/')({
  validateSearch: searchSchema,
  component: HomePage,
});

function HomePage() {
  const { t } = useTranslation();
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const [localQuery, setLocalQuery] = useState(search.q);
  const { data, isLoading, isError, error, refetch } = useSearch(search);

  useEffect(() => {
    document.title = search.q ? `Pensieve - ${search.q}` : 'Pensieve';
  }, [search.q]);

  function submitQuery() {
    void navigate({
      search: (s: SearchParams) => ({
        ...s,
        q: localQuery,
        submitted_q: localQuery,
        app_names: [],
      }),
    });
  }

  return (
    <div className="flex min-h-screen flex-col">
      <div className="w-full border-b">
        <div className="mx-auto flex max-w-screen-lg items-center justify-between py-2">
          <div />
          <Link to="/config">
            <Button variant="ghost" size="icon" title={t('config.title')}>
              <Settings size={20} />
            </Button>
          </Link>
        </div>
      </div>

      <header className="sticky top-0 z-10">
        <div className="mx-auto flex max-w-screen-lg flex-col items-center justify-between p-4">
          <Logo size={128} withBorder hasGap className="mr-4" />
          <div className="mt-4 flex w-full p-2">
            <Input
              type="text"
              value={localQuery}
              onChange={(e) => setLocalQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  submitQuery();
                }
              }}
              placeholder={t('searchPlaceholder')}
              autoFocus
              className="w-full border-gray-500 text-lg"
            />
          </div>
        </div>
      </header>

      <main className="flex-grow">
        <div className="mx-auto flex flex-col sm:flex-row">
          <div className="w-full">
            {isLoading && <p className="p-4 text-center">{t('loading')}</p>}
            {isError && <ErrorState error={error} onRetry={() => void refetch()} />}
            {data && data.hits.length === 0 && (
              <div className="flex min-h-[200px] items-center justify-center">
                <p>{t('noResults')}</p>
              </div>
            )}
            {data && data.hits.length > 0 && (
              <pre className="p-4 text-xs">
                {JSON.stringify(data.hits.slice(0, 3), null, 2)}
              </pre>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
