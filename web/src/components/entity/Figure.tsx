import { useEffect, useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '$/components/ui/button';
import { EntityImage } from './EntityImage';
import { EntityDetail } from './EntityDetail';
import { EntityViewerToolbar, type ViewerLayout } from './EntityViewerToolbar';
import type { Entity } from '$/lib/api/types';

interface Props {
  entity: Entity;
  onClose: () => void;
  onNext: () => void;
  onPrevious: () => void;
}

const LAYOUT_KEY = 'entityViewerLayout';
const LAYOUT_VALUES: ViewerLayout[] = ['both', 'image', 'details'];

function loadLayout(): ViewerLayout {
  if (typeof window === 'undefined') return 'both';
  const saved = localStorage.getItem(LAYOUT_KEY);
  return saved && (LAYOUT_VALUES as string[]).includes(saved)
    ? (saved as ViewerLayout)
    : 'both';
}

export function Figure({ entity, onClose, onNext, onPrevious }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [layout, setLayoutState] = useState<ViewerLayout>(loadLayout);

  function setLayout(next: ViewerLayout) {
    setLayoutState(next);
    localStorage.setItem(LAYOUT_KEY, next);
  }

  const showImage = layout !== 'details';
  const showDetails = layout !== 'image';

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowRight') onNext();
      else if (e.key === 'ArrowLeft') onPrevious();
    }
    window.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose, onNext, onPrevious]);

  function goToDetail() {
    onClose();
    void navigate({ to: '/entities/$id', params: { id: String(entity.id) } });
  }

  return (
    <div
      className="fixed inset-0 z-40 flex h-full w-full items-center justify-center bg-black/50"
      id="my-modal"
    >
      <div className="group relative mx-auto h-[95vh] w-11/12 max-w-[95vw] rounded-md border bg-background shadow-lg">
        <div className="absolute inset-0 flex flex-col px-4 py-4 sm:px-6 lg:px-10">
          <button
            type="button"
            onClick={onPrevious}
            className="absolute left-2 top-1/2 z-[51] flex -translate-y-1/2 rounded-full border bg-background/80 p-2 opacity-0 transition-all duration-200 hover:bg-accent group-hover:opacity-100"
            aria-label="Previous"
          >
            <ChevronLeft size={24} className="text-primary" />
          </button>
          <button
            type="button"
            onClick={onNext}
            className="absolute right-2 top-1/2 z-[51] flex -translate-y-1/2 rounded-full border bg-background/80 p-2 opacity-0 transition-all duration-200 hover:bg-accent group-hover:opacity-100"
            aria-label="Next"
          >
            <ChevronRight size={24} className="text-primary" />
          </button>

          <EntityViewerToolbar
            entity={entity}
            layout={layout}
            onLayoutChange={setLayout}
            rightAction={
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                onClick={onClose}
                aria-label="Close"
                title="Close (Esc)"
              >
                <X size={18} />
              </Button>
            }
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

          <div className="pointer-events-none absolute bottom-8 left-1/2 z-[53] flex w-full -translate-x-1/2 justify-center">
            <button
              type="button"
              onClick={goToDetail}
              className="pointer-events-auto rounded-full border bg-background/80 px-4 py-2 text-sm font-semibold text-primary shadow-lg transition hover:bg-accent"
            >
              {t('figure.viewContext', { defaultValue: 'View Context' })}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
