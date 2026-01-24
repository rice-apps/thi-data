export type TableCellValue = string | number | boolean | null | undefined;

export type TableRow = Record<string, TableCellValue> & {
  id?: number | string;
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
