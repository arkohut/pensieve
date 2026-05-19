import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { ProcessingStatus } from '$/lib/processing-status';

export function useProcessingStatus(libraryId: number | undefined) {
  return useQuery({
    queryKey: ['processing-status', libraryId],
    queryFn: ({ signal }) =>
      apiFetch<ProcessingStatus>(
        `/libraries/${libraryId}/processing-status?window_hours=24`,
        { signal },
      ),
    enabled: libraryId !== undefined,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    staleTime: 25_000,
  });
}
