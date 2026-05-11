import { createFileRoute, useNavigate, useRouter } from '@tanstack/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Home, Loader } from 'lucide-react';
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
  const router = useRouter();
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

      void navigate({ to: '/entities/$id', params: { id: String(targetId) } });
    },
    [navigate, queryClient],
  );

  const goToHome = useCallback(() => {
    // Prefer history.back so the home page's search params survive. Fall back
    // to a fresh navigate when the user landed directly on /entities/$id.
    if (router.history.length > 1) {
      router.history.back();
    } else {
      void navigate({ to: '/' });
    }
  }, [navigate, router.history]);

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        goToHome();
      } else if (e.key === 'ArrowLeft' && previousEntity) {
        goToEntity(previousEntity);
      } else if (e.key === 'ArrowRight' && nextEntity) {
        goToEntity(nextEntity);
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [goToEntity, goToHome, nextEntity, previousEntity]);

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

  const homeButton = (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="h-8 w-8 text-muted-foreground hover:text-foreground"
      onClick={goToHome}
      aria-label="Home"
      title="Home"
    >
      <Home size={18} />
    </Button>
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
                leftAction={homeButton}
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
        <div className="h-[180px] w-full border-t bg-muted/50 shadow-inner">
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
