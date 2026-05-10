import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useCallback, useEffect, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, Settings } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { Input } from '$/components/ui/input';
import { Skeleton } from '$/components/ui/skeleton';
import { ErrorState } from '$/components/common/ErrorState';
import { PageHeader } from '$/components/common/PageHeader';
import { HitCard } from '$/components/search/HitCard';
import { FacetFilter } from '$/components/search/FacetFilter';
import { LibraryFilter } from '$/components/search/LibraryFilter';
import { TimeFilter } from '$/components/search/TimeFilter';
import { DateBucketFilter } from '$/components/search/DateBucketFilter';
import { Figure } from '$/components/entity/Figure';
import { searchSchema, type SearchParams } from '$/lib/search-params';
import { useFacets, useSearch } from '$/lib/api/search';
import { cn } from '$/lib/utils';

export const Route = createFileRoute('/')({
  validateSearch: searchSchema,
  component: HomePage,
});

const LOADING_SKELETON = (
  <div className="grid grid-cols-2 gap-x-5 gap-y-7 md:grid-cols-3 lg:grid-cols-4">
    {Array.from({ length: 8 }).map((_, i) => (
      <div key={i}>
        <Skeleton className="aspect-[16/10] w-full rounded-md" />
        <div className="mt-2.5 flex items-center gap-3">
          <Skeleton className="h-3.5 flex-1" />
          <Skeleton className="h-3 w-12" />
        </div>
        <Skeleton className="mt-1.5 h-3 w-1/2" />
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
  const { data, isLoading, isError, error, refetch, isFetching } = useSearch(search);

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
  const { data: facetData, isFetching: isFacetFetching } = useFacets({
    submitted_q: search.submitted_q,
    library_ids: search.library_ids,
    start: search.start,
    end: search.end,
    date: search.date,
  });
  // Surface in-flight queries on the input (spinner) and on stale results
  // (faded grid). isLoading covers the very first fetch; isFetching covers
  // every refetch including the ones that keep prior data via placeholderData.
  const isQuerying = isFetching || isFacetFetching;
  const isStale = !isLoading && isFetching && !!data;
  const appFacet = facetData?.facets.find((f) => f.field_name === 'app_names');
  const dateBuckets = facetData?.dateBuckets ?? [];
  const bucketUnit = facetData?.bucketUnit ?? null;
  const hasAppFacet = !!appFacet && appFacet.counts.length > 0;
  const hasDateBuckets = dateBuckets.length > 0 && bucketUnit !== null;
  const hasSidebar = hasAppFacet || hasDateBuckets;

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

  // TimeFilter and the date facet are mutually exclusive temporal filters —
  // setting one clears the other so the displayed range always matches the
  // effective range (no UI mismatch like "Last month" + date=2026-05-09).
  const handleTimeChange = useCallback(
    ({ start, end }: { start?: number; end?: number }) => {
      void navigate({ search: (s: SearchParams) => ({ ...s, start, end, date: undefined }) });
    },
    [navigate],
  );

  const handleDateBucketChange = useCallback(
    (date: string | undefined) => {
      void navigate({
        search: (s: SearchParams) => ({ ...s, date, start: undefined, end: undefined }),
      });
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

  const totalIndexed = data?.out_of;

  return (
    <div className="flex min-h-screen flex-col">
      <PageHeader
        maxWidth="max-w-screen-xl"
        left={
          <Link to="/" className="flex items-baseline gap-3">
            <span className="text-base font-semibold tracking-tight">
              Pensieve<span className="text-brand">.</span>
            </span>
            <span className="hidden font-mono text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground sm:inline">
              / a private archive of your screen
            </span>
          </Link>
        }
        right={
          <Link to="/config">
            <Button variant="ghost" size="icon" title={t('config.title')}>
              <Settings size={18} />
            </Button>
          </Link>
        }
      />

      <header className="mx-auto w-full max-w-screen-xl px-6 pb-6 pt-12">
        <div className="flex items-center gap-2 font-mono text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground">
          <span className="relative inline-flex h-1.5 w-1.5">
            <span className="absolute inset-0 animate-ping rounded-full bg-brand/40" />
            <span className="relative inline-block h-1.5 w-1.5 rounded-full bg-brand" />
          </span>
          <span>live · capturing</span>
        </div>

        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-foreground sm:text-[36px]">
          <span className="text-brand">
            {totalIndexed != null ? totalIndexed.toLocaleString() : '—'}
          </span>{' '}
          memories indexed.
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          你电脑的私人记忆库
          {totalIndexed != null && (
            <>
              {' '}
              ——{' '}
              <span className="font-mono text-[13px] tabular-nums">
                {totalIndexed.toLocaleString()}
              </span>{' '}
              张截图，覆盖所有应用与所有屏幕。
            </>
          )}
        </p>

        <div className="relative mt-7 max-w-2xl">
          <Input
            type="text"
            value={localQuery}
            onChange={handleInputChange}
            onKeyDown={handleInputKeyDown}
            placeholder={t('searchPlaceholder')}
            autoFocus
            className="h-11 w-full border-border pr-10 text-[15px]"
          />
          {isQuerying && (
            <Loader2
              aria-hidden
              className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-brand"
              size={16}
            />
          )}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">{filterButtons}</div>
      </header>

      <div
        className={cn(
          'fixed inset-x-0 top-0 z-20 border-b bg-background/85 backdrop-blur transition-opacity duration-200',
          isScrolled ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
        aria-hidden={!isScrolled}
      >
        <div className="mx-auto flex max-w-screen-xl items-center gap-4 px-6 py-2.5">
          <Link to="/" className="shrink-0 text-sm font-semibold tracking-tight">
            Pensieve<span className="text-brand">.</span>
          </Link>
          <div className="relative min-w-0 flex-1">
            <Input
              type="text"
              value={localQuery}
              onChange={handleInputChange}
              onKeyDown={handleInputKeyDown}
              placeholder={t('searchPlaceholder')}
              tabIndex={isScrolled ? 0 : -1}
              className="h-9 w-full border-border pr-10"
            />
            {isQuerying && (
              <Loader2
                aria-hidden
                className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-brand"
                size={14}
              />
            )}
          </div>
          <div className="flex flex-shrink-0 gap-2">{filterButtons}</div>
        </div>
      </div>

      <main className="mx-auto w-full max-w-screen-xl flex-grow px-6 pb-16">
        <div className="flex flex-col sm:flex-row sm:gap-8">
          {hasSidebar && (
            <aside className="pb-6 sm:w-full md:w-56 md:flex-shrink-0">
              {hasDateBuckets && bucketUnit && (
                <DateBucketFilter
                  buckets={dateBuckets}
                  unit={bucketUnit}
                  selected={search.date}
                  onToggle={handleDateBucketChange}
                />
              )}
              {hasAppFacet && (
                <FacetFilter facet={appFacet} selected={search.app_names} onToggle={toggleApp} />
              )}
            </aside>
          )}
          <div className="min-w-0 flex-1">
            {isLoading ? (
              LOADING_SKELETON
            ) : isError ? (
              <ErrorState error={error} onRetry={() => void refetch()} />
            ) : data && data.hits.length > 0 ? (
              <div
                className={cn(
                  'transition-opacity duration-150',
                  isStale && 'pointer-events-none opacity-60',
                )}
                aria-busy={isStale}
              >
                <div className="mb-5 flex items-baseline justify-between border-b border-border pb-3 font-mono text-[11.5px] uppercase tracking-[0.08em] text-muted-foreground">
                  <span>
                    {data.found > 0
                      ? t('searchSummary', {
                          found:
                            // Server caps very broad counts at 10000 (returns 10001
                            // as the sentinel to avoid scanning hundreds of
                            // thousands of FTS rows. Render that as '10,000+'.
                            data.found > 10000
                              ? `${(10000).toLocaleString()}+`
                              : data.found.toLocaleString(),
                          outOf: data.out_of.toLocaleString(),
                        })
                      : t('searchSummarySemantic', {
                          hits: data.hits.length.toLocaleString(),
                        })}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-x-5 gap-y-7 md:grid-cols-3 lg:grid-cols-4">
                  {data.hits.map((hit, i) => (
                    <HitCard key={hit.document.id} hit={hit} onClick={() => setSelectedIndex(i)} />
                  ))}
                </div>
              </div>
            ) : data ? (
              <div className="flex min-h-[200px] items-center justify-center">
                <p className="text-sm text-muted-foreground">{t('noResults')}</p>
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
