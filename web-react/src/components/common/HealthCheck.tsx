import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Loader } from 'lucide-react';
import { apiEndpoint } from '$/lib/api/client';

interface Props {
  onStatusChange: () => void;
}

const MAX_ATTEMPTS = 60;

export function HealthCheck({ onStatusChange }: Props) {
  const { t } = useTranslation();
  const [isRestarting, setIsRestarting] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const attemptsRef = useRef(0);

  useEffect(() => {
    function clearCheck() {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    async function check() {
      try {
        const res = await fetch(`${apiEndpoint}/health`, { cache: 'no-store' });
        if (res.ok) {
          setIsRestarting(false);
          onStatusChange();
          clearCheck();
          toast.success(t('config.title'), { description: t('config.servicesRestarted') });
          return;
        }
      } catch {
        // still restarting
      }
      attemptsRef.current++;
      if (attemptsRef.current >= MAX_ATTEMPTS) {
        setIsRestarting(false);
        onStatusChange();
        clearCheck();
        toast.error(t('config.error'), { description: t('config.servicesRestartTimeout') });
      }
    }

    const timer = setTimeout(() => {
      intervalRef.current = setInterval(check, 1000);
    }, 1000);

    return () => {
      clearTimeout(timer);
      clearCheck();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!isRestarting) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/70">
      <Loader size={36} className="mb-4 animate-spin text-primary" />
      <h3 className="mb-2 text-xl font-medium text-white">
        {t('config.servicesRestartingTitle')}
      </h3>
      <p className="max-w-md text-center text-white">
        {t('config.servicesRestartingMessage')}
      </p>
    </div>
  );
}
