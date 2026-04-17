import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Home, Loader } from 'lucide-react';
import { EntityImage } from '$/components/entity/EntityImage';
import { EntityDetail } from '$/components/entity/EntityDetail';
import { ContextNavigationBar } from '$/components/entity/ContextNavigationBar';
import { ErrorState } from '$/components/common/ErrorState';
import {
  entityFileUrl,
  entityKeys,
  fetchEntityContext,
  useEntity,
  useEntityContext,
} from '$/lib/api/entities';
import type { Entity } from '$/lib/api/types';

export const Route = createFileRoute('/entities/$id')({
  component: EntityPage,
});

function EntityPage() {
  const { id } = Route.useParams();
  const entityId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [showDetails, setShowDetails] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    const saved = localStorage.getItem('entityShowDetails');
    return saved !== null ? JSON.parse(saved) : true;
  });

  const { data: entity, isLoading, isError, error, refetch } = useEntity(entityId);
  const { data: contextData } = useEntityContext(entity?.library_id, entityId);
  const previousEntity = useMemo(() => contextData?.prev.at(-1), [contextData?.prev]);
  const nextEntity = useMemo(() => contextData?.next[0], [contextData?.next]);
  const adjacentEntities = useMemo(
    () => [previousEntity, nextEntity].filter((item): item is Entity => Boolean(item)),
    [nextEntity, previousEntity],
  );

  function toggleDetails() {
    setShowDetails((prev) => {
      const next = !prev;
      localStorage.setItem('entityShowDetails', JSON.stringify(next));
      return next;
    });
  }

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

  function goToHome() {
    void navigate({ to: '/' });
  }

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'ArrowLeft' && previousEntity) {
        goToEntity(previousEntity);
      } else if (e.key === 'ArrowRight' && nextEntity) {
        goToEntity(nextEntity);
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [goToEntity, nextEntity, previousEntity]);

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
      <div className="fixed inset-0 z-40 flex h-full w-full items-center justify-center bg-gray-600/50">
        <Loader size={36} className="animate-spin text-primary" />
      </div>
    );
  }
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />;
  if (!entity) return <p className="p-4">Entity not found.</p>;

  const homeButton = (
    <button
      type="button"
      onClick={goToHome}
      className="-ml-2 flex items-center gap-2 rounded-full p-2 text-indigo-600 hover:bg-gray-100"
      aria-label="Home"
    >
      <Home size={24} className="text-indigo-600" />
    </button>
  );

  return (
    <div className="fixed inset-0 z-40 flex h-full w-full flex-col bg-gray-600/50">
      <div className="flex flex-grow flex-col">
        <div className="relative mx-auto mt-6 flex h-[calc(100vh-180px)] w-11/12 max-w-[95vw] flex-col overflow-hidden rounded-t-md bg-white">
          <div className="flex-grow overflow-hidden">
            <div className="h-full px-10 py-4">
              <div className="flex h-full flex-col md:flex-row">
                <EntityImage
                  entity={entity}
                  showDetails={showDetails}
                  toggleDetails={toggleDetails}
                  leftIcon={homeButton}
                />
                {showDetails && <EntityDetail entity={entity} />}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="h-[180px] w-full border-t bg-gray-50 shadow-inner">
        <div className="mx-auto h-full py-3">
          {contextData && (
            <ContextNavigationBar
              entity={entity}
              contextData={contextData}
              onSelectEntity={goToEntity}
            />
          )}
        </div>
      </div>
    </div>
  );
}
