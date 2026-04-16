import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Settings } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { Input } from '$/components/ui/input';
import { Skeleton } from '$/components/ui/skeleton';
import { Logo } from '$/components/common/Logo';
import { ErrorState } from '$/components/common/ErrorState';
import { HitCard } from '$/components/search/HitCard';
import { TimeFilter } from '$/components/search/TimeFilter';
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
  const [, setSelectedIndex] = useState<number | null>(null);
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
          <div className="mt-2 flex w-full justify-start gap-2 px-2">
            <TimeFilter
              start={search.start}
              end={search.end}
              onChange={({ start, end }) =>
                void navigate({ search: (s: SearchParams) => ({ ...s, start, end }) })
              }
            />
          </div>
        </div>
      </header>

      <main className="flex-grow">
        <div className="mx-auto flex flex-col sm:flex-row">
          <div className="w-full">
            {isLoading ? (
              <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div
                    key={i}
                    className="overflow-hidden rounded-lg border border-gray-300 bg-white"
                  >
                    <div className="px-4 pt-4">
                      <Skeleton className="mb-2 h-4 w-3/4" />
                      <Skeleton className="h-4 w-1/2" />
                      <Skeleton className="mt-2 h-3 w-1/4" />
                    </div>
                    <div className="px-4 pb-4 pt-4">
                      <Skeleton className="h-48 w-full" />
                    </div>
                  </div>
                ))}
              </div>
            ) : isError ? (
              <ErrorState error={error} onRetry={() => void refetch()} />
            ) : data && data.hits.length > 0 ? (
              <>
                {data.search_time_ms > 0 && (
                  <p className="search-summary mb-4 text-center">
                    {t('searchSummary', {
                      found: data.found.toLocaleString(),
                      outOf: data.out_of.toLocaleString(),
                      time: data.search_time_ms,
                    })}
                  </p>
                )}
                <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
                  {data.hits.map((hit, i) => (
                    <HitCard
                      key={hit.document.id}
                      hit={hit}
                      onClick={() => setSelectedIndex(i)}
                    />
                  ))}
                </div>
              </>
            ) : data ? (
              <div className="flex min-h-[200px] items-center justify-center">
                <p>{t('noResults')}</p>
              </div>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}
