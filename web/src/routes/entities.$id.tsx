import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Home, Loader } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { EntityImage } from '$/components/entity/EntityImage';
import { EntityDetail } from '$/components/entity/EntityDetail';
import { EntityViewerToolbar, type ViewerLayout } from '$/components/entity/EntityViewerToolbar';
import { ContextNavigationBar } from '$/components/entity/ContextNavigationBar';
import { ErrorState } from '$/components/common/ErrorState';
import {
  entityFileUrl,
  entityKeys,
  fetchEntityContext,
  useEntity,
  useEntityContext,
} from '$/lib/api/entities';
import { useLibraries } from '$/lib/api/libraries';
import type { Entity } from '$/lib/api/types';

export const Route = createFileRoute('/entities/$id')({
  component: EntityPage,
});

function EntityPage() {
  const { id } = Route.useParams();
  const entityId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [layout, setLayoutState] = useState<ViewerLayout>(() => {
    if (typeof window === 'undefined') return 'both';
    const saved = localStorage.getItem('entityViewerLayout');
    return saved === 'image' || saved === 'details' ? saved : 'both';
  });
  const showImage = layout !== 'details';
  const showDetails = layout !== 'image';

  function setLayout(next: ViewerLayout) {
    setLayoutState(next);
    localStorage.setItem('entityViewerLayout', next);
  }

  const { data: entity, isLoading, isError, error, refetch } = useEntity(entityId);
  const { data: libraries } = useLibraries();
  const library = libraries?.find((l) => l.id === entity?.library_id);

  // Read the search hit list captured by HomePage so we can offer
  // "previous / next result" navigation when the user opened this entity
  // from a search. The list is plain ids — when an id lands here we know
  // it's part of the active search session.
  const [searchHitIds, setSearchHitIds] = useState<number[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const raw = sessionStorage.getItem('memos:searchHitIds');
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  });
  useEffect(() => {
    // Refresh on entity change in case the storage was updated mid-session.
    try {
      const raw = sessionStorage.getItem('memos:searchHitIds');
      setSearchHitIds(raw ? JSON.parse(raw) : []);
    } catch {
      setSearchHitIds([]);
    }
  }, [entityId]);

  // Anchor sticks at the last hit visited so the indicator stays put even
  // when the user temporarily wanders into a temporal neighbor that wasn't
  // in the search results. Pressing ←/→ pulls them back onto hits land.
  const [anchorIndex, setAnchorIndex] = useState<number | null>(null);
  useEffect(() => {
    if (searchHitIds.length === 0) {
      setAnchorIndex(null);
      return;
    }
    const idx = searchHitIds.indexOf(entityId);
    if (idx >= 0) setAnchorIndex(idx);
    // else: keep the previous anchor so the session indicator stays visible.
  }, [entityId, searchHitIds]);

  const searchNav = useMemo(() => {
    if (searchHitIds.length === 0 || anchorIndex === null) return null;
    const onHit = searchHitIds[anchorIndex] === entityId;
    return {
      index: anchorIndex,
      total: searchHitIds.length,
      onHit,
      prevId: anchorIndex > 0 ? searchHitIds[anchorIndex - 1] : null,
      nextId:
        anchorIndex < searchHitIds.length - 1 ? searchHitIds[anchorIndex + 1] : null,
    };
  }, [searchHitIds, anchorIndex, entityId]);

  // Treat libraries with unknown kind as 'record' to stay backward-compatible
  // until everyone is on a server that exposes the field.
  const isRecordLibrary = library?.kind !== 'static';
  const { data: contextData } = useEntityContext(
    isRecordLibrary ? entity?.library_id : undefined,
    isRecordLibrary ? entityId : 0,
  );
  const previousEntity = useMemo(() => contextData?.prev.at(-1), [contextData?.prev]);
  const nextEntity = useMemo(() => contextData?.next[0], [contextData?.next]);
  const adjacentEntities = useMemo(
    () => [previousEntity, nextEntity].filter((item): item is Entity => Boolean(item)),
    [nextEntity, previousEntity],
  );

  const goToEntity = useCallback(
    (target: Entity | number) => {
      const targetId = typeof target === 'number' ? target : target.id;

      if (typeof target !== 'number') {
        queryClient.setQueryData(entityKeys.detail(targetId), target);
      }

      // Replace instead of push: entity-to-entity navigation should not
      // accumulate history, so a later Esc / Home reliably lands on the
      // place the user came from (typically the home page) rather than
      // unwinding through each entity they visited.
      void navigate({
        to: '/entities/$id',
        params: { id: String(targetId) },
        replace: true,
      });
    },
    [navigate, queryClient],
  );

  const goToHome = useCallback(() => {
    // Restore the home search params snapshotted by HomePage so the user lands
    // back on their previous query / filters. Falls back to a bare home when
    // there's no snapshot (direct visit to /entities/$id, fresh tab, etc).
    let homeSearch: Record<string, unknown> = {};
    try {
      const saved = sessionStorage.getItem('memos:homeSearch');
      if (saved) homeSearch = JSON.parse(saved);
    } catch {
      // Ignore storage failures; navigate to bare home below.
    }
    void navigate({ to: '/', search: homeSearch });
  }, [navigate]);

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        goToHome();
      } else if (e.key === 'ArrowLeft') {
        // Search context wins over temporal: the most common use is stepping
        // through the result list the user just clicked into.
        if (searchNav?.prevId != null) {
          goToEntity(searchNav.prevId);
        } else if (previousEntity) {
          goToEntity(previousEntity);
        }
      } else if (e.key === 'ArrowRight') {
        if (searchNav?.nextId != null) {
          goToEntity(searchNav.nextId);
        } else if (nextEntity) {
          goToEntity(nextEntity);
        }
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [goToEntity, goToHome, nextEntity, previousEntity, searchNav]);

  useEffect(() => {
    if (!contextData) return;

    for (const contextEntity of [...contextData.prev, ...contextData.next]) {
      queryClient.setQueryData(entityKeys.detail(contextEntity.id), contextEntity);
    }
  }, [contextData, queryClient]);

  useEffect(() => {
    for (const adjacentEntity of adjacentEntities) {
      const image = document.createElement('img');
      image.decoding = 'async';
      image.src = entityFileUrl(adjacentEntity);
      void image.decode().catch(() => undefined);

      void queryClient.prefetchQuery({
        queryKey: entityKeys.context(adjacentEntity.library_id, adjacentEntity.id, 12),
        queryFn: ({ signal }) =>
          fetchEntityContext(adjacentEntity.library_id, adjacentEntity.id, 12, signal),
      });
    }
  }, [adjacentEntities, queryClient]);

  if (isLoading) {
    return (
      <div className="fixed inset-0 z-40 flex h-full w-full items-center justify-center bg-black/50">
        <Loader size={36} className="animate-spin text-primary" />
      </div>
    );
  }
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />;
  if (!entity) return <p className="p-4">Entity not found.</p>;

  const leftCluster = (
    <div className="flex items-center gap-1">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-muted-foreground hover:text-foreground"
        onClick={goToHome}
        aria-label="Home"
        title="Home (Esc)"
      >
        <Home size={18} />
      </Button>
      {searchNav && (
        <div
          className={`ml-1 flex items-center gap-1 border-l border-border pl-2 ${
            searchNav.onHit ? '' : 'opacity-60'
          }`}
          title={
            searchNav.onHit
              ? 'Position within search results'
              : 'Off search results — ← / → return to the list'
          }
        >
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            disabled={searchNav.prevId == null}
            onClick={() => searchNav.prevId != null && goToEntity(searchNav.prevId)}
            aria-label="Previous result"
            title="Previous result (←)"
          >
            <ChevronLeft size={16} />
          </Button>
          <span className="min-w-[3.5rem] text-center font-mono text-[11px] tabular-nums text-muted-foreground">
            <span className={searchNav.onHit ? 'text-foreground' : ''}>
              {searchNav.index + 1}
            </span>
            <span className="mx-1 opacity-50">/</span>
            {searchNav.total}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            disabled={searchNav.nextId == null}
            onClick={() => searchNav.nextId != null && goToEntity(searchNav.nextId)}
            aria-label="Next result"
            title="Next result (→)"
          >
            <ChevronRight size={16} />
          </Button>
        </div>
      )}
    </div>
  );

  const showContext = isRecordLibrary && !!contextData;
  const viewerHeight = showContext ? 'h-[calc(100vh-180px)]' : 'h-[calc(100vh-48px)]';

  return (
    <div className="fixed inset-0 z-40 flex h-full w-full flex-col bg-black/50">
      <div className="flex flex-grow flex-col">
        <div
          className={`relative mx-auto mt-6 flex ${viewerHeight} w-11/12 max-w-[95vw] flex-col overflow-hidden rounded-t-md bg-background`}
        >
          <div className="flex flex-grow flex-col overflow-hidden">
            <div className="flex h-full flex-col overflow-y-auto px-4 py-4 sm:px-6 lg:overflow-hidden lg:px-10">
              <EntityViewerToolbar
                entity={entity}
                layout={layout}
                onLayoutChange={setLayout}
                leftAction={leftCluster}
              />
              <div className="mt-3 flex min-h-0 flex-1 flex-col gap-4 lg:flex-row">
                {showImage && (
                  <EntityImage
                    entity={entity}
                    showIdentifier={showDetails}
                    className={showDetails ? 'lg:w-1/2' : 'lg:flex-1'}
                  />
                )}
                {showDetails && (
                  <EntityDetail
                    entity={entity}
                    className={showImage ? 'lg:ml-6 lg:w-1/2' : 'lg:flex-1'}
                  />
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {showContext && (
        <div className="h-[180px] w-full border-t border-border bg-background">
          <div className="mx-auto h-full py-3">
            <ContextNavigationBar
              entity={entity}
              contextData={contextData}
              onSelectEntity={goToEntity}
            />
          </div>
        </div>
      )}
    </div>
  );
}
