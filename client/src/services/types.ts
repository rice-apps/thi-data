export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
}

export type TableCellValue = string | number | boolean | null | undefined;

export type TableRow = Record<string, TableCellValue> & {
  id?: number | string;
};

export interface TableSchemaResponse {
  columns: string[];
}

export interface TableMetadata {
  name: string;
  uploadedBy: string | null;
  dateUploaded: string | null;
  dateModified: string | null;
  size: string | null;
}

export interface TableListResponse {
  tables: TableMetadata[];
}

export interface PaginationParams {
  skip?: number;
  limit?: number;
}
