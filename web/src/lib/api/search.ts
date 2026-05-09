import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { apiFetch } from './client';
import { buildSearchPath, facetScope, type SearchParams } from '$/lib/search-params';
import type { DateBucket, DateRange, Facet, SearchResult } from './types';

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

export type FacetParams = Pick<SearchParams, 'library_ids' | 'start' | 'end' | 'date'> & {
  submitted_q: string;
};

export const facetKeys = {
  all: ['facets'] as const,
  query: (p: FacetParams) => [...facetKeys.all, p] as const,
};

export interface FacetData {
  facets: Facet[];
  dateRange: DateRange | null;
  dateBuckets: DateBucket[];
  bucketUnit: 'day' | 'month' | null;
}

// Drops app_names so the App facet stays stable as the user toggles app filters.
// Uses facetScope(date) (always ≤ month-level) so the Date facet shows sibling
// buckets one level below the current scope: no date → all months; month
// selected → days within that month; day selected → days within the same month
// (sibling switching). Lets the user switch sideways or clear back to months
// without losing the facet to single-bucket suppression.
export function useFacets(p: FacetParams) {
  return useQuery<FacetData>({
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
          date: facetScope(p.date),
        }),
        { signal },
      );
      return {
        facets: r.facet_counts,
        dateRange: r.date_range ?? null,
        dateBuckets: r.date_buckets ?? [],
        bucketUnit: r.bucket_unit ?? null,
      };
    },
    staleTime: 30 * 1000,
    placeholderData: keepPreviousData,
  });
}
