import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { apiFetch } from './client';
import { buildSearchPath, type SearchParams } from '$/lib/search-params';
import type { Facet, SearchResult } from './types';

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

export type FacetParams = Pick<SearchParams, 'library_ids' | 'start' | 'end'> & {
  submitted_q: string;
};

export const facetKeys = {
  all: ['facets'] as const,
  query: (p: FacetParams) => [...facetKeys.all, p] as const,
};

export function useFacets(p: FacetParams) {
  return useQuery<Facet[]>({
    queryKey: facetKeys.query(p),
    queryFn: async ({ signal }) => {
      const r = await apiFetch<SearchResult>(
        buildSearchPath({
          q: p.submitted_q,
          submitted_q: p.submitted_q,
          start: p.start,
          end: p.end,
          library_ids: p.library_ids,
          app_names: [],
        }),
        { signal },
      );
      return r.facet_counts;
    },
    staleTime: 30 * 1000,
    placeholderData: keepPreviousData,
  });
}
