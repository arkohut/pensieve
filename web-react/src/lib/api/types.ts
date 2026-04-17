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
}

export interface Folder {
  id: number;
  path: string;
  library_id: number;
}

export interface Library {
  id: number;
  name: string;
  folders: Folder[];
  plugins?: unknown[];
}
