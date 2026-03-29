import type {
  TableRow,
  TableMetadata,
  PaginationParams,
  PaginatedResponse,
  TableSchemaResponse,
} from '@/types';
import type {
  ValidateSchemaResponse,
  FileRegistryUpdate,
} from './HttpDataService';

/**
 * Minimal type for dependency injection of auth into data services.
 */
export type AuthProvider = {
  getCurrentUserName(): Promise<string>;
};

/**
 * Authentication service interface.
 */
export interface IAuthService {
  getCurrentUserName(): Promise<string>;
  getCurrentUserEmail(): Promise<string | null>;
  signOut(): Promise<void>;
  isAuthenticated(): Promise<boolean>;
}

/**
 * Data service interface for CRUD operations on tables.
 */
export interface IDataService {
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

  validateSchema(fileId: string): Promise<ValidateSchemaResponse>;
  updateFileRegistry(
    fileId: string,
    update: FileRegistryUpdate
  ): Promise<{ file_id: string; updated_fields: FileRegistryUpdate }>;
  processFile(
    fileId: string,
    proposedSchema: Record<string, string>
  ): Promise<{ file_id: string; status: string }>;

  checkDuplicate(
    tableName: string
  ): Promise<{ table_name: string; exists: boolean }>;
}
