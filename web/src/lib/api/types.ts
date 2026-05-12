export interface MetadataEntry {
  key: string;
  source: string;
  value: string;
  data_type?: string;
}

export interface Entity {
  id: number;
  library_id: number;
  folder_id: number;
  filepath: string;
  filename: string;
  file_created_at: string;
  file_last_modified_at: string;
  file_type?: string;
  file_type_group?: string;
  size?: number;
  tags: string[];
  metadata_entries: MetadataEntry[];
}

export interface FacetCount {
  value: string;
  count: number;
}

export interface Facet {
  field_name: string;
  counts: FacetCount[];
  sampled?: boolean;
}

export interface DateRange {
  earliest: string | null;
  latest: string | null;
}

export interface DateBucket {
  date: string; // 'YYYY-MM' or 'YYYY-MM-DD' depending on bucket_unit
  count: number;
}

export interface Hit {
  document: Entity;
  highlight?: Record<string, unknown>;
  text_match?: number;
}

export interface SearchResult {
  hits: Hit[];
  facet_counts: Facet[];
  found: number;
  out_of: number;
  search_time_ms: number;
  phase_timings_ms?: Record<string, number> | null;
  date_range?: DateRange | null;
  date_buckets?: DateBucket[] | null;
  bucket_unit?: 'day' | 'month' | null;
}

export interface Folder {
  id: number;
  path: string;
  library_id: number;
}

export type LibraryKind = 'record' | 'static';

export interface Library {
  id: number;
  name: string;
  kind: LibraryKind;
  folders: Folder[];
  plugins?: unknown[];
}
