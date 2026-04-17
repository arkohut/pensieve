import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { Library } from './types';

export function useLibraries() {
  return useQuery({
    queryKey: ['libraries'],
    queryFn: ({ signal }) => apiFetch<Library[]>('/libraries', { signal }),
    staleTime: 5 * 60 * 1000,
  });
}
