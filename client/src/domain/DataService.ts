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

export interface DataService {
  getTablesWithMetadata(): Promise<{ tables: TableMetadata[] }>;
  getTableSchema(tableName: string): Promise<TableSchemaResponse>;
  getTableData(
    tableName: string,
    params?: PaginationParams
  ): Promise<PaginatedResponse<TableRow>>;
  searchTableData(
    tableName: string,
    column: string,
    value: string,
    params?: PaginationParams
  ): Promise<PaginatedResponse<TableRow>>;
  createRow(tableName: string, data: Omit<TableRow, 'id'>): Promise<TableRow>;
  updateRow(
    tableName: string,
    id: string | number,
    data: Partial<TableRow>
  ): Promise<TableRow>;
  deleteRow(tableName: string, id: string | number): Promise<void>;
}
