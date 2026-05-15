import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ChevronLeft, ChevronRight, Loader, Maximize2, X } from 'lucide-react';
import { Button } from '$/components/ui/button';
import { ErrorState } from '$/components/common/ErrorState';
import { EntityImage } from '$/components/entity/EntityImage';
import { EntityDetail } from '$/components/entity/EntityDetail';
import {
  EntityViewerToolbar,
  type ViewerLayout,
} from '$/components/entity/EntityViewerToolbar';
import {
  entityKeys,
  fetchEntity,
  preloadEntityImage,
  useEntity,
} from '$/lib/api/entities';
import { useLibraries } from '$/lib/api/libraries';
import type { SearchParams } from '$/lib/search-params';

interface Props {
  entityId: number;
  onClose: () => void;
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded border border-border bg-secondary/60 px-1 font-mono text-[10px] font-medium text-foreground">
      {children}
    </kbd>
  );
}

export function HitViewerModal({ entityId, onClose }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // The grid behind the modal stores the ordered hit ids in sessionStorage
  // (see routes/index.tsx). Read on every entityId change so newly-loaded
  // search pages are reflected when this hook eventually supports pagination.
  const hitIds = useMemo<number[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const raw = sessionStorage.getItem('memos:searchHitIds');
      return raw ? (JSON.parse(raw) as number[]) : [];
    } catch {
      return [];
    }
  }, [entityId]);

  const index = useMemo(() => hitIds.indexOf(entityId), [hitIds, entityId]);
  const onHit = index >= 0;
  // List-position semantics: ← steps to the previous hit (one up in the grid),
  // → steps to the next hit (one down). No mixing with temporal direction —
  // the context view owns that, this modal only walks the result list.
  const prevId = onHit && index > 0 ? hitIds[index - 1] : null;
  const nextId = onHit && index < hitIds.length - 1 ? hitIds[index + 1] : null;

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
  // Static libraries have no temporal context to expand into — hide the
  // affordance entirely rather than render a button that does nothing.
  const canExpandContext = library !== undefined && library.kind !== 'static';

  const goToHit = useCallback(
    (targetId: number) => {
      void navigate({
        // Stay on the home route, just swap which hit is open.
        to: '/',
        search: (s: Partial<SearchParams>) => ({ ...s, open: targetId }),
        replace: true,
      });
    },
    [navigate],
  );

  const expandContext = useCallback(() => {
    void navigate({
      to: '/entities/$id',
      params: { id: String(entityId) },
      search: { from: 'hit' },
    });
  }, [navigate, entityId]);

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      } else if (e.key === 'ArrowLeft' && prevId != null) {
        e.preventDefault();
        goToHit(prevId);
      } else if (e.key === 'ArrowRight' && nextId != null) {
        e.preventDefault();
        goToHit(nextId);
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [goToHit, prevId, nextId, onClose]);

  // Warm the cache for the immediate ±1 neighbors so ← / → feels instant.
  useEffect(() => {
    const adjacent = [prevId, nextId].filter((x): x is number => x != null);
    for (const id of adjacent) {
      void queryClient
        .ensureQueryData({
          queryKey: entityKeys.detail(id),
          queryFn: ({ signal }) => fetchEntity(id, signal),
        })
        .then(preloadEntityImage)
        .catch(() => undefined);
    }
  }, [prevId, nextId, queryClient]);

  // Lock background scroll while the modal is up — the home grid sits right
  // behind it and would otherwise scroll on wheel/trackpad.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  const leftCluster = (
    <div className="flex items-center gap-1">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-muted-foreground hover:text-foreground"
        onClick={onClose}
        aria-label={t('entityViewer.close')}
        title={t('entityViewer.closeTitle')}
      >
        <X size={18} />
      </Button>
      {hitIds.length > 0 && (
        <div className="ml-1 flex items-center gap-1 border-l border-border pl-2">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            disabled={prevId == null}
            onClick={() => prevId != null && goToHit(prevId)}
            aria-label={t('entityViewer.previousResult')}
            title={t('entityViewer.previousResultTitle')}
          >
            <ChevronLeft size={16} />
          </Button>
          <span className="min-w-[3.5rem] text-center font-mono text-[11px] tabular-nums text-muted-foreground">
            {onHit ? (
              <>
                <span className="text-foreground">{index + 1}</span>
                <span className="mx-1 opacity-50">/</span>
                {hitIds.length}
              </>
            ) : (
              <span className="opacity-60">— / {hitIds.length}</span>
            )}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            disabled={nextId == null}
            onClick={() => nextId != null && goToHit(nextId)}
            aria-label={t('entityViewer.nextResult')}
            title={t('entityViewer.nextResultTitle')}
          >
            <ChevronRight size={16} />
          </Button>
        </div>
      )}
    </div>
  );

  if (isLoading) {
    return (
      <div className="fixed inset-0 z-40 flex h-full w-full items-center justify-center bg-black/50">
        <Loader size={36} className="animate-spin text-primary" />
      </div>
    );
  }
  if (isError) {
    return (
      <div className="fixed inset-0 z-40 flex h-full w-full items-center justify-center bg-black/50">
        <ErrorState error={error} onRetry={() => void refetch()} />
      </div>
    );
  }
  if (!entity) return null;

  return (
    <div className="fixed inset-0 z-40 flex h-full w-full flex-col bg-black/50">
      <div className="flex flex-grow flex-col">
        <div className="relative mx-auto mt-6 flex h-[calc(100vh-48px)] w-11/12 max-w-[95vw] flex-col overflow-hidden rounded-t-md bg-background">
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
              <div className="mt-2 flex items-center gap-1.5 font-mono text-[10.5px] text-muted-foreground">
                <Kbd>←</Kbd>
                <Kbd>→</Kbd>
                <span>{t('entityViewer.hintResults')}</span>
                <span className="mx-1 opacity-50">·</span>
                <Kbd>Esc</Kbd>
                <span>{t('entityViewer.hintClose')}</span>
              </div>
            </div>
          </div>
          {canExpandContext && (
            <Button
              type="button"
              variant="secondary"
              onClick={expandContext}
              className="absolute bottom-6 left-1/2 z-30 -translate-x-1/2 shadow-lg"
              aria-label={t('entityViewer.exploreContext')}
              title={t('entityViewer.exploreContextTitle')}
            >
              <Maximize2 size={16} className="mr-2" />
              {t('entityViewer.exploreContext')}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
