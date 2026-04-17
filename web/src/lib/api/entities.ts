import { useQuery } from '@tanstack/react-query';
import { apiEndpoint, apiFetch } from './client';
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

export function entityFileUrl(entity: Pick<Entity, 'filepath'>): string {
  return `${apiEndpoint}/files/${entity.filepath.replace(/^\/+/, '')}`;
}

export function entityThumbnailUrl(entity: Pick<Entity, 'filepath'>): string {
  return `${apiEndpoint}/thumbnails/${entity.filepath.replace(/^\/+/, '')}`;
}

export function entityVideoUrl(entity: Pick<Entity, 'filepath'>): string {
  return `${apiEndpoint}/files/video/${entity.filepath.replace(/^\/+/, '')}`;
}

export interface EntityContext {
  prev: Entity[];
  next: Entity[];
}

export function fetchEntityContext(
  libraryId: number,
  id: number,
  size: number = 12,
  signal?: AbortSignal,
) {
  return apiFetch<EntityContext>(
    `/libraries/${libraryId}/entities/${id}/context?prev=${size}&next=${size}`,
    { signal },
  );
}

export function useEntityContext(libraryId: number | undefined, id: number, size: number = 12) {
  return useQuery({
    queryKey: entityKeys.context(libraryId ?? 0, id, size),
    queryFn: ({ signal }) => fetchEntityContext(libraryId!, id, size, signal),
    enabled: Number.isFinite(id) && id > 0 && !!libraryId,
  });
}
