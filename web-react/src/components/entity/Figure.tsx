import { useEffect, useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { EntityImage } from './EntityImage';
import { EntityDetail } from './EntityDetail';
import type { Entity } from '$/lib/api/types';

interface Props {
  entity: Entity;
  onClose: () => void;
  onNext: () => void;
  onPrevious: () => void;
}

export function Figure({ entity, onClose, onNext, onPrevious }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [showDetails, setShowDetails] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    const saved = localStorage.getItem('figureShowDetails');
    return saved ? JSON.parse(saved) : false;
  });

  function toggleDetails() {
    setShowDetails((prev) => {
      const next = !prev;
      localStorage.setItem('figureShowDetails', JSON.stringify(next));
      return next;
    });
  }

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
      className="fixed inset-0 z-40 flex h-full w-full items-center justify-center bg-gray-600/50"
      id="my-modal"
    >
      <div className="group relative mx-auto h-[95vh] w-11/12 max-w-[95vw] rounded-md border bg-white shadow-lg">
        <div className="absolute inset-0 px-10 py-4">
          <button
            type="button"
            onClick={onPrevious}
            className="absolute left-2 top-1/2 z-[51] flex -translate-y-1/2 rounded-full border bg-white/80 p-2 opacity-0 transition-all duration-200 hover:bg-gray-100 group-hover:opacity-100"
            aria-label="Previous"
          >
            <ChevronLeft size={24} className="text-indigo-600" />
          </button>
          <button
            type="button"
            onClick={onNext}
            className="absolute right-2 top-1/2 z-[51] flex -translate-y-1/2 rounded-full border bg-white/80 p-2 opacity-0 transition-all duration-200 hover:bg-gray-100 group-hover:opacity-100"
            aria-label="Next"
          >
            <ChevronRight size={24} className="text-indigo-600" />
          </button>

          <div className="relative flex h-full flex-col md:flex-row">
            <EntityImage
              entity={entity}
              showDetails={showDetails}
              toggleDetails={toggleDetails}
            />
            {showDetails && <EntityDetail entity={entity} />}
          </div>

          <div className="absolute right-2 top-2 z-[52]">
            <button
              type="button"
              onClick={onClose}
              className="rounded-full bg-white/80 p-2 opacity-0 transition-all duration-200 hover:bg-gray-100 group-hover:opacity-100"
              aria-label="Close"
            >
              <X size={24} className="text-indigo-600" />
            </button>
          </div>

          <div className="pointer-events-none absolute bottom-8 left-1/2 z-[53] flex w-full -translate-x-1/2 justify-center">
            <button
              type="button"
              onClick={goToDetail}
              className="pointer-events-auto rounded-full border border-indigo-200 bg-white/80 px-4 py-2 text-sm font-semibold text-indigo-700 shadow-lg transition hover:bg-indigo-100"
            >
              {t('figure.viewContext', { defaultValue: 'View Context' })}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
