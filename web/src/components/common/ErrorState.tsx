import { useTranslation } from 'react-i18next';
import { Button } from '$/components/ui/button';
import { ApiError } from '$/lib/api/client';

interface Props {
  error: Error;
  onRetry?: () => void;
}

export function ErrorState({ error, onRetry }: Props) {
  const { t } = useTranslation();
  const message =
    error instanceof ApiError ? `${error.status}: ${error.message}` : error.message;
  return (
    <div className="flex min-h-[200px] flex-col items-center justify-center gap-2">
      <p className="text-sm text-muted-foreground">{message}</p>
      {onRetry && (
        <Button onClick={onRetry}>{t('retry', { defaultValue: 'Retry' })}</Button>
      )}
    </div>
  );
}
