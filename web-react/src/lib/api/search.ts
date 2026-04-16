import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { apiFetch } from './client';
import { buildSearchPath, type SearchParams } from '$/lib/search-params';
import type { SearchResult } from './types';

export const searchKeys = {
  all: ['search'] as const,
  query: (params: SearchParams) => [...searchKeys.all, params] as const,
};

export function useSearch(params: SearchParams) {
  return useQuery({
    queryKey: searchKeys.query(params),
    queryFn: ({ signal }) => apiFetch<SearchResult>(buildSearchPath(params), { signal }),
    placeholderData: keepPreviousData,
  });
}
