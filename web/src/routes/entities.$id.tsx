import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Home, Loader } from 'lucide-react';
import { z } from 'zod';
import { Button } from '$/components/ui/button';
import { EntityImage } from '$/components/entity/EntityImage';
import { EntityDetail } from '$/components/entity/EntityDetail';
import { EntityViewerToolbar, type ViewerLayout } from '$/components/entity/EntityViewerToolbar';
import { ContextNavigationBar } from '$/components/entity/ContextNavigationBar';
import { ErrorState } from '$/components/common/ErrorState';
import {
  entityKeys,
  fetchEntityContext,
  preloadEntityImage,
  useEntity,
  useEntityContext,
} from '$/lib/api/entities';
import { useLibraries } from '$/lib/api/libraries';
import type { Entity } from '$/lib/api/types';

const entitySearchSchema = z.object({
  // 'hit' marks "I came from a search hit modal" — drives the back-to-search
  // button and the Esc/back behavior. Any other value is dropped.
  from: z.enum(['hit']).optional().catch(undefined),
});

export const Route = createFileRoute('/entities/$id')({
  validateSearch: entitySearchSchema,
  component: EntityPage,
});

function EntityPage() {
  const { t } = useTranslation();
  const { id } = Route.useParams();
  const search = Route.useSearch();
  const fromHit = search.from === 'hit';
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
  const isRecordLibrary = library?.kind !== 'static';
  const { data: contextData } = useEntityContext(
    isRecordLibrary ? entity?.library_id : undefined,
    isRecordLibrary ? entityId : 0,
  );
  const previousEntity = useMemo(() => contextData?.prev.at(-1), [contextData?.prev]);
  const nextEntity = useMemo(() => contextData?.next[0], [contextData?.next]);
  const adjacentEntities = useMemo(() => {
    if (!contextData) return [] as Entity[];
    return [...contextData.prev.slice(-3), ...contextData.next.slice(0, 3)];
  }, [contextData]);

  const goToEntity = useCallback(
    (target: Entity | number) => {
      const targetId = typeof target === 'number' ? target : target.id;

      if (typeof target !== 'number') {
        queryClient.setQueryData(entityKeys.detail(targetId), target);
      }

      // Replace so a long temporal walk doesn't pile up history — pressing
      // browser-back from here should land on whatever was before the entity
      // page (typically the hit modal that opened it).
      void navigate({
        to: '/entities/$id',
        params: { id: String(targetId) },
        search: (s) => s,
        replace: true,
      });
    },
    [navigate, queryClient],
  );

  const goBackOrHome = useCallback(() => {
    if (fromHit && window.history.length > 1) {
      window.history.back();
      return;
    }
    let homeSearch: Record<string, unknown> = {};
    try {
      const saved = sessionStorage.getItem('memos:homeSearch');
      if (saved) homeSearch = JSON.parse(saved);
    } catch {
      // Ignore storage failures; navigate to bare home below.
    }
    void navigate({ to: '/', search: homeSearch });
  }, [navigate, fromHit]);

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        goBackOrHome();
      } else if (e.key === 'ArrowLeft') {
        if (previousEntity) goToEntity(previousEntity);
      } else if (e.key === 'ArrowRight') {
        if (nextEntity) goToEntity(nextEntity);
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [goToEntity, goBackOrHome, nextEntity, previousEntity]);

  useEffect(() => {
    if (!contextData) return;
    for (const contextEntity of [...contextData.prev, ...contextData.next]) {
      queryClient.setQueryData(entityKeys.detail(contextEntity.id), contextEntity);
    }
  }, [contextData, queryClient]);

  useEffect(() => {
    for (const e of adjacentEntities) {
      preloadEntityImage(e);
      void queryClient.prefetchQuery({
        queryKey: entityKeys.context(e.library_id, e.id, 12),
        queryFn: ({ signal }) => fetchEntityContext(e.library_id, e.id, 12, signal),
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
      {fromHit ? (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground hover:text-foreground"
          onClick={goBackOrHome}
          aria-label={t('entityViewer.backToSearch')}
          title={t('entityViewer.backToSearchTitle')}
        >
          <ArrowLeft size={18} />
        </Button>
      ) : (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground hover:text-foreground"
          onClick={goBackOrHome}
          aria-label={t('entityViewer.home')}
          title={t('entityViewer.homeTitle')}
        >
          <Home size={18} />
        </Button>
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
