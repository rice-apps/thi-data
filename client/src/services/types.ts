export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
}

export type TableCellValue = string | number | boolean | null;

export type TableRow = {
  id?: number | string;
  [key: string]: TableCellValue | undefined;
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
