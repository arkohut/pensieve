import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { Entity } from './types';

export const entityKeys = {
  all: ['entities'] as const,
  detail: (id: number) => [...entityKeys.all, id] as const,
  context: (libraryId: number, id: number, size: number) =>
    [...entityKeys.all, id, 'context', libraryId, size] as const,
};

export function useEntity(id: number) {
  return useQuery({
    queryKey: entityKeys.detail(id),
    queryFn: ({ signal }) => apiFetch<Entity>(`/entities/${id}`, { signal }),
    enabled: Number.isFinite(id) && id > 0,
  });
}

export interface EntityContext {
  prev: Entity[];
  next: Entity[];
}

export function useEntityContext(
  libraryId: number | undefined,
  id: number,
  size: number = 12,
) {
  return useQuery({
    queryKey: entityKeys.context(libraryId ?? 0, id, size),
    queryFn: ({ signal }) =>
      apiFetch<EntityContext>(
        `/libraries/${libraryId}/entities/${id}/context?prev=${size}&next=${size}`,
        { signal },
      ),
    enabled: Number.isFinite(id) && id > 0 && !!libraryId,
  });
}
