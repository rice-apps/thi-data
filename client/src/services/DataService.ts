import {
  PaginatedResponse,
  TableRow,
  TableSchemaResponse,
  TableMetadata,
  PaginationParams,
} from './types';

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
