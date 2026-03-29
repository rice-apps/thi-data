import type {
  TableRow,
  TableMetadata,
  PaginationParams,
  PaginatedResponse,
  TableSchemaResponse,
} from '@/types';

type ValidateSchemaField = {
  name?: string;
  type?: string;
};

export type ValidateSchemaResponse = {
  file_id?: string;
  columns?: ValidateSchemaField[];
};

export type FileRegistryUpdate = {
  status?: string;
  object_key?: string;
  file_schema?: unknown;
};
import type { IDataService, AuthProvider } from './interfaces';
import { HttpClient } from './HttpClient';

export class HttpDataService implements IDataService {
  private httpClient: HttpClient;
  private authProvider: AuthProvider;

  constructor(authProvider: AuthProvider, baseUrl?: string) {
    this.authProvider = authProvider;
    const url =
      baseUrl || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    this.httpClient = new HttpClient({
      baseUrl: `${url.replace(/\/$/, '')}/api`,
    });
  }

  private async getAuthHeaders(): Promise<Record<string, string>> {
    const userName = await this.authProvider.getCurrentUserName();
    if (userName) {
      return { 'X-User-Name': userName };
    }
    return {};
  }

  async getTablesWithMetadata(): Promise<{ tables: TableMetadata[] }> {
    const headers = await this.getAuthHeaders();
    return this.httpClient.get<{ tables: TableMetadata[] }>(
      'tables_with_metadata',
      {
        cache: 'no-store',
        headers,
      }
    );
  }

  async validateSchema(fileId: string): Promise<ValidateSchemaResponse> {
    const headers = await this.getAuthHeaders();
    const query = new URLSearchParams({ file_id: fileId });
    return this.httpClient.post<ValidateSchemaResponse>(
      `validate_schema?${query}`,
      undefined,
      { headers }
    );
  }

  async updateFileRegistry(
    fileId: string,
    update: FileRegistryUpdate
  ): Promise<{ file_id: string; updated_fields: FileRegistryUpdate }> {
    const headers = await this.getAuthHeaders();
    return this.httpClient.patch<{
      file_id: string;
      updated_fields: FileRegistryUpdate;
    }>(`files/${encodeURIComponent(fileId)}`, update, { headers });
  }

  async processFile(
    fileId: string,
    proposedSchema: Record<string, string>
  ): Promise<{ file_id: string; status: string }> {
    const headers = await this.getAuthHeaders();
    return this.httpClient.post<{ file_id: string; status: string }>(
      `files/${encodeURIComponent(fileId)}/process`,
      { proposed_schema: proposedSchema },
      { headers }
    );
  }

  async getTableSchema(tableName: string): Promise<TableSchemaResponse> {
    const headers = await this.getAuthHeaders();
    return this.httpClient.get<TableSchemaResponse>(`schema/${tableName}`, {
      cache: 'no-store',
      headers,
    });
  }

  async getTableData(
    tableName: string,
    params?: PaginationParams
  ): Promise<PaginatedResponse<TableRow>> {
    const headers = await this.getAuthHeaders();
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined)
      searchParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined)
      searchParams.append('limit', params.limit.toString());

    const queryString = searchParams.toString();
    const endpoint = queryString ? `${tableName}?${queryString}` : tableName;

    return this.httpClient.get<PaginatedResponse<TableRow>>(endpoint, {
      cache: 'no-store',
      headers,
    });
  }

  async searchTableData(
    tableName: string,
    column: string,
    value: string,
    params?: PaginationParams
  ): Promise<PaginatedResponse<TableRow>> {
    const headers = await this.getAuthHeaders();
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined)
      searchParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined)
      searchParams.append('limit', params.limit.toString());

    const queryString = searchParams.toString();
    const endpoint = `${tableName}/search/${column}/${encodeURIComponent(
      value
    )}${queryString ? `?${queryString}` : ''}`;

    return this.httpClient.get<PaginatedResponse<TableRow>>(endpoint, {
      cache: 'no-store',
      headers,
    });
  }

  async createRow(
    tableName: string,
    data: Omit<TableRow, 'id'>
  ): Promise<TableRow> {
    const headers = await this.getAuthHeaders();
    return this.httpClient.post<TableRow>(tableName, data, { headers });
  }

  async updateRow(
    tableName: string,
    id: string | number,
    data: Partial<TableRow>
  ): Promise<TableRow> {
    const headers = await this.getAuthHeaders();
    return this.httpClient.put<TableRow>(`${tableName}/${id}`, data, {
      headers,
    });
  }

  async deleteRow(tableName: string, id: string | number): Promise<void> {
    const headers = await this.getAuthHeaders();
    await this.httpClient.delete(`${tableName}/${id}`, { headers });
  }

  async checkDuplicate(
    tableName: string
  ): Promise<{ table_name: string; exists: boolean }> {
    const headers = await this.getAuthHeaders();
    const query = new URLSearchParams({ table_name: tableName });
    return this.httpClient.get<{ table_name: string; exists: boolean }>(
      `files/check-duplicate?${query}`,
      { headers }
    );
  }
}
