import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useCallback, useEffect, useMemo, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, Settings } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { Input } from '$/components/ui/input';
import { Skeleton } from '$/components/ui/skeleton';
import { ErrorState } from '$/components/common/ErrorState';
import { LanguageSwitcher } from '$/components/common/LanguageSwitcher';
import { Logo } from '$/components/common/Logo';
import { PageHeader } from '$/components/common/PageHeader';
import { ProcessingStatusPill } from '$/components/common/ProcessingStatusPill';
import { ThemeToggle } from '$/components/common/ThemeToggle';
import { HitViewerModal } from '$/components/entity/HitViewerModal';
import { HitCard } from '$/components/search/HitCard';
import { FacetFilter } from '$/components/search/FacetFilter';
import { LibraryFilter } from '$/components/search/LibraryFilter';
import { TimeFilter } from '$/components/search/TimeFilter';
import { DateBucketFilter } from '$/components/search/DateBucketFilter';
import { effectiveSearchParams, searchSchema, type SearchParams } from '$/lib/search-params';
import { useFacets, useSearch } from '$/lib/api/search';
import { groupHits } from '$/lib/group-hits';
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
  const [isScrolled, setIsScrolled] = useState(false);
  const openEntity = useCallback(
    (entityId: number) => {
      void navigate({
        search: (s: SearchParams) => ({ ...s, open: entityId }),
      });
    },
    [navigate],
  );

  const closeHitModal = useCallback(() => {
    // Replace so closing doesn't leave a "no-modal" entry behind a "modal-open"
    // entry — browser back after closing should return to whatever was there
    // before the user clicked into a hit, not re-open the modal.
    void navigate({
      search: (s: SearchParams) => ({ ...s, open: undefined }),
      replace: true,
    });
  }, [navigate]);
  // Apply the default 3-month window unless the user explicitly opted into
  // start=0 ("All time") or set start/end/date themselves. Recompute when the
  // URL changes so navigating fresh picks up a current window.
  // Strip `open` from the params that feed the search/facet queries and the
  // sessionStorage snapshot — it is purely a modal-visibility flag and must
  // not invalidate query caches or persist across navigations.
  const searchWithoutOpen = useMemo(() => {
    const { open: _open, ...rest } = search;
    return rest as SearchParams;
  }, [search]);
  const effective = useMemo(
    () => effectiveSearchParams(searchWithoutOpen),
    [searchWithoutOpen],
  );
  const { data, isLoading, isError, error, refetch, isFetching } = useSearch(effective);

  // Snapshot the home search so the entity page can restore it on Esc/Home.
  // sessionStorage is per-tab and clears with the tab, which matches the
  // intuition that the "previous home" only makes sense within this session.
  useEffect(() => {
    try {
      sessionStorage.setItem('memos:homeSearch', JSON.stringify(searchWithoutOpen));
    } catch {
      // Storage may be disabled (private mode quotas, etc). Falling back to
      // an unparameterized home is still a valid behavior.
    }
  }, [searchWithoutOpen]);

  // Also snapshot the ordered hit ids so the entity page can offer "next /
  // prev result" navigation across the current search session. Coerce to
  // numbers because the API returns ids as strings even though the type
  // declares number, and the entity route parses its param via Number().
  useEffect(() => {
    if (!data) return;
    try {
      sessionStorage.setItem(
        'memos:searchHitIds',
        JSON.stringify(data.hits.map((h) => Number(h.document.id))),
      );
    } catch {
      // Same trade-off as above — without storage, the entity page falls
      // back to plain temporal navigation.
    }
  }, [data]);

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
    submitted_q: effective.submitted_q,
    library_ids: effective.library_ids,
    start: effective.start,
    end: effective.end,
    date: effective.date,
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
          <Link to="/" aria-label="Pensieve home" className="flex items-center">
            <Logo size={40} withBorder={false} />
          </Link>
        }
        right={
          <div className="flex items-center gap-1">
            <ProcessingStatusPill />
            <LanguageSwitcher />
            <ThemeToggle />
            <Link to="/config">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                title={t('config.title')}
              >
                <Settings size={18} />
              </Button>
            </Link>
          </div>
        }
      />

      <header className="mx-auto w-full max-w-screen-xl px-6 pb-6 pt-12">
        <h1 className="font-display text-3xl font-normal tracking-tight text-foreground sm:text-[40px]">
          {t('slogan')}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {totalIndexed != null ? (
            <>
              <span className="font-mono text-[13px] tabular-nums text-brand">
                {totalIndexed.toLocaleString()}
              </span>{' '}
              {t('heroIndexedSuffix')}
            </>
          ) : (
            '—'
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
            <span
              aria-hidden
              className="pointer-events-none absolute inset-y-0 right-3 flex items-center"
            >
              <Loader2 className="animate-spin text-brand" size={16} />
            </span>
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
          <Link to="/" aria-label="Pensieve home" className="flex shrink-0 items-center">
            <Logo size={28} withBorder={false} />
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
              <span
                aria-hidden
                className="pointer-events-none absolute inset-y-0 right-3 flex items-center"
              >
                <Loader2 className="animate-spin text-brand" size={14} />
              </span>
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
                          found: data.found.toLocaleString(),
                          outOf: data.out_of.toLocaleString(),
                        })
                      : t('searchSummarySemantic', {
                          hits: data.hits.length.toLocaleString(),
                        })}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-x-5 gap-y-7 md:grid-cols-3 lg:grid-cols-4">
                  {groupHits(data.hits).map((group) => (
                    <HitCard
                      key={group.rep.document.id}
                      hit={group.rep}
                      stackCount={group.count}
                      onClick={() => openEntity(group.rep.document.id)}
                    />
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
      {search.open != null && (
        <HitViewerModal entityId={search.open} onClose={closeHitModal} />
      )}
    </div>
  );
}
