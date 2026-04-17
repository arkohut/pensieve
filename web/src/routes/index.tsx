import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useCallback, useEffect, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Settings } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { Input } from '$/components/ui/input';
import { Skeleton } from '$/components/ui/skeleton';
import { Logo } from '$/components/common/Logo';
import { ErrorState } from '$/components/common/ErrorState';
import { PageHeader } from '$/components/common/PageHeader';
import { HitCard } from '$/components/search/HitCard';
import { FacetFilter } from '$/components/search/FacetFilter';
import { LibraryFilter } from '$/components/search/LibraryFilter';
import { TimeFilter } from '$/components/search/TimeFilter';
import { Figure } from '$/components/entity/Figure';
import { searchSchema, type SearchParams } from '$/lib/search-params';
import { useFacets, useSearch } from '$/lib/api/search';
import { cn } from '$/lib/utils';

export const Route = createFileRoute('/')({
  validateSearch: searchSchema,
  component: HomePage,
});

const LOADING_SKELETON = (
  <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
    {Array.from({ length: 8 }).map((_, i) => (
      <div key={i} className="overflow-hidden rounded-lg border border-gray-300 bg-white">
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
);

function HomePage() {
  const { t } = useTranslation();
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const [localQuery, setLocalQuery] = useState(search.q);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [isScrolled, setIsScrolled] = useState(false);
  const { data, isLoading, isError, error, refetch } = useSearch(search);

  useEffect(() => {
    function handleScroll() {
      const y = window.scrollY;
      setIsScrolled((prev) => {
        if (y > 100) return true;
        if (y < 20) return false;
        return prev;
      });
    }
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);
  const { data: facets } = useFacets({
    submitted_q: search.submitted_q,
    library_ids: search.library_ids,
    start: search.start,
    end: search.end,
  });
  const appFacet = facets?.find((f) => f.field_name === 'app_names');

  useEffect(() => {
    setLocalQuery(search.q);
  }, [search.q]);

  useEffect(() => {
    document.title = search.q ? `Pensieve - ${search.q}` : 'Pensieve';
  }, [search.q]);

  const toggleApp = useCallback(
    (name: string, checked: boolean) => {
      void navigate({
        search: (s: SearchParams) => ({
          ...s,
          app_names: checked
            ? [...s.app_names, name]
            : s.app_names.filter((x) => x !== name),
        }),
      });
    },
    [navigate],
  );

  const submitQuery = useCallback(() => {
    void navigate({
      search: (s: SearchParams) => ({
        ...s,
        q: localQuery,
        submitted_q: localQuery,
        app_names: [],
      }),
    });
  }, [navigate, localQuery]);

  const handleLibraryChange = useCallback(
    (ids: number[]) => {
      void navigate({ search: (s: SearchParams) => ({ ...s, library_ids: ids }) });
    },
    [navigate],
  );

  const handleTimeChange = useCallback(
    ({ start, end }: { start?: number; end?: number }) => {
      void navigate({ search: (s: SearchParams) => ({ ...s, start, end }) });
    },
    [navigate],
  );

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalQuery(e.target.value);
  }, []);

  const handleInputKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        submitQuery();
      }
    },
    [submitQuery],
  );

  const closeFigure = useCallback(() => setSelectedIndex(null), []);
  const showNextFigure = useCallback(() => {
    setSelectedIndex((index) => {
      if (index == null || !data?.hits.length) return index;
      return (index + 1) % data.hits.length;
    });
  }, [data?.hits.length]);
  const showPreviousFigure = useCallback(() => {
    setSelectedIndex((index) => {
      if (index == null || !data?.hits.length) return index;
      return (index - 1 + data.hits.length) % data.hits.length;
    });
  }, [data?.hits.length]);

  const filterButtons = (
    <>
      <LibraryFilter selectedLibraryIds={search.library_ids} onChange={handleLibraryChange} />
      <TimeFilter start={search.start} end={search.end} onChange={handleTimeChange} />
    </>
  );

  return (
    <div className="flex min-h-screen flex-col">
      <PageHeader
        right={
          <Link to="/config">
            <Button variant="ghost" size="icon" title={t('config.title')}>
              <Settings size={20} />
            </Button>
          </Link>
        }
      />

      <header className="mx-auto flex w-full max-w-screen-lg flex-col items-center justify-between px-4 py-4">
        <Logo size={128} withBorder hasGap className="mr-4" />
        <div className="mt-4 flex w-full p-2">
          <Input
            type="text"
            value={localQuery}
            onChange={handleInputChange}
            onKeyDown={handleInputKeyDown}
            placeholder={t('searchPlaceholder')}
            autoFocus
            className="w-full border-gray-500 text-lg"
          />
        </div>
        <div className="mt-2 flex w-full justify-start gap-2 px-2">{filterButtons}</div>
      </header>

      <div
        className={cn(
          'fixed inset-x-0 top-0 z-20 border-b bg-background shadow-sm transition-opacity duration-200',
          isScrolled ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
        aria-hidden={!isScrolled}
      >
        <div className="mx-auto flex max-w-screen-lg items-center gap-4 px-4 py-2">
          <Logo size={32} withBorder={false} hasGap={false} />
          <Input
            type="text"
            value={localQuery}
            onChange={handleInputChange}
            onKeyDown={handleInputKeyDown}
            placeholder={t('searchPlaceholder')}
            tabIndex={isScrolled ? 0 : -1}
            className="w-full border-gray-500"
          />
          <div className="flex flex-shrink-0 gap-2">{filterButtons}</div>
        </div>
      </div>

      <main className="flex-grow">
        <div className="mx-auto flex flex-col sm:flex-row">
          {appFacet && appFacet.counts.length > 0 && (
            <aside className="pr-4 sm:w-full md:w-1/5 lg:w-1/6 xl:w-[14.28%]">
              <FacetFilter facet={appFacet} selected={search.app_names} onToggle={toggleApp} />
            </aside>
          )}
          <div
            className={
              appFacet && appFacet.counts.length > 0 ? 'md:w-4/5 lg:w-5/6 xl:w-[85.72%]' : 'w-full'
            }
          >
            {isLoading ? (
              LOADING_SKELETON
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
                    <HitCard key={hit.document.id} hit={hit} onClick={() => setSelectedIndex(i)} />
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

      {data && selectedIndex != null && data.hits[selectedIndex] && (
        <Figure
          entity={data.hits[selectedIndex].document}
          onClose={closeFigure}
          onNext={showNextFigure}
          onPrevious={showPreviousFigure}
        />
      )}
    </div>
  );
}
