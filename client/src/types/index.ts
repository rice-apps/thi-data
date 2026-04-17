export type TableCellValue = string | number | boolean | null | undefined;

export type CellError = {
  raw_value: string;
  error: string;
};

export type TableRow = Record<string, TableCellValue> & {
  id?: number | string;
  original_csv_row_id?: number | string;
  _is_corrupted?: boolean;
  _error_context?: Record<string, CellError>;
};

export type TableMetadata = {
  name: string;
  uploadedBy: string | null;
  dateUploaded: string | null;
  dateModified: string | null;
  size: string | null;
};

export type PaginationParams = {
  skip?: number;
  limit?: number;
};

export type PaginatedResponse<T> = {
  data: T[];
  total: number;
  page: number;
  limit: number;
};

export type TableSchemaResponse = {
  columns: string[];
};
