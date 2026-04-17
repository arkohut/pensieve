import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { Home, Loader } from 'lucide-react';
import { EntityImage } from '$/components/entity/EntityImage';
import { EntityDetail } from '$/components/entity/EntityDetail';
import { ContextNavigationBar } from '$/components/entity/ContextNavigationBar';
import { ErrorState } from '$/components/common/ErrorState';
import { useEntity, useEntityContext } from '$/lib/api/entities';

export const Route = createFileRoute('/entities/$id')({
  component: EntityPage,
});

function EntityPage() {
  const { id } = Route.useParams();
  const entityId = Number(id);
  const navigate = useNavigate();

  const [showDetails, setShowDetails] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    const saved = localStorage.getItem('entityShowDetails');
    return saved !== null ? JSON.parse(saved) : true;
  });

  const { data: entity, isLoading, isError, error, refetch } = useEntity(entityId);
  const { data: contextData } = useEntityContext(entity?.library_id, entityId);

  function toggleDetails() {
    setShowDetails((prev) => {
      const next = !prev;
      localStorage.setItem('entityShowDetails', JSON.stringify(next));
      return next;
    });
  }

  function goToEntity(targetId: number) {
    void navigate({ to: '/entities/$id', params: { id: String(targetId) } });
  }

  function goToHome() {
    void navigate({ to: '/' });
  }

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'ArrowLeft' && contextData?.prev?.length) {
        goToEntity(contextData.prev[contextData.prev.length - 1].id);
      } else if (e.key === 'ArrowRight' && contextData?.next?.length) {
        goToEntity(contextData.next[0].id);
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contextData]);

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
