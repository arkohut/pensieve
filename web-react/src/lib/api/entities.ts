import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { Entity } from './types';

export const entityKeys = {
  all: ['entities'] as const,
  detail: (id: number) => [...entityKeys.all, id] as const,
};

export function useEntity(id: number) {
  return useQuery({
    queryKey: entityKeys.detail(id),
    queryFn: ({ signal }) => apiFetch<Entity>(`/entities/${id}`, { signal }),
    enabled: Number.isFinite(id) && id > 0,
  });
}
