import type {
  TableRow,
  TableCellValue,
  TableMetadata,
  PaginationParams,
  PaginatedResponse,
  TableSchemaResponse,
} from '@/types';
import type { IDataService, AuthProvider } from './interfaces';
import { HttpClient } from './HttpClient';

export class HttpDataService implements IDataService {
  private httpClient: HttpClient;
  private authProvider: AuthProvider;

  constructor(authProvider: AuthProvider, baseUrl?: string) {
    this.authProvider = authProvider;
    const url = baseUrl || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    this.httpClient = new HttpClient({
      baseUrl: `${url.replace(/\/$/, '')}/api`,
    });
  }

  private async setAuthHeader(): Promise<void> {
    const userName = await this.authProvider.getCurrentUserName();
    if (userName) {
      this.httpClient.setHeader('X-User-Name', userName);
    }
  }

  async getTablesWithMetadata(): Promise<{ tables: TableMetadata[] }> {
    await this.setAuthHeader();
    return this.httpClient.get<{ tables: TableMetadata[] }>('tables_with_metadata', {
      cache: 'no-store',
    });
  }

  async getTableSchema(tableName: string): Promise<TableSchemaResponse> {
    await this.setAuthHeader();
    return this.httpClient.get<TableSchemaResponse>(`schema/${tableName}`, {
      cache: 'no-store',
    });
  }

  async getTableData(
    tableName: string,
    params?: PaginationParams
  ): Promise<PaginatedResponse<TableRow>> {
    await this.setAuthHeader();
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined)
      searchParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined)
      searchParams.append('limit', params.limit.toString());

    const queryString = searchParams.toString();
    const endpoint = queryString ? `${tableName}?${queryString}` : tableName;

    return this.httpClient.get<PaginatedResponse<TableRow>>(endpoint, {
      cache: 'no-store',
    });
  }

  async searchTableData(
    tableName: string,
    column: string,
    value: string,
    params?: PaginationParams
  ): Promise<PaginatedResponse<TableRow>> {
    await this.setAuthHeader();
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
    });
  }

  async createRow(
    tableName: string,
    data: Omit<TableRow, 'id'>
  ): Promise<TableRow> {
    await this.setAuthHeader();
    return this.httpClient.post<TableRow>(tableName, data);
  }

  async updateRow(
    tableName: string,
    id: string | number,
    data: Partial<TableRow>
  ): Promise<TableRow> {
    await this.setAuthHeader();
    return this.httpClient.put<TableRow>(`${tableName}/${id}`, data);
  }

  async deleteRow(tableName: string, id: string | number): Promise<void> {
    await this.setAuthHeader();
    await this.httpClient.delete(`${tableName}/${id}`);
  }

  async resolveCorruptedRow(
    tableName: string,
    rowId: string | number,
    fixes: Record<string, TableCellValue>
  ): Promise<TableRow> {
    await this.setAuthHeader();
    return this.httpClient.patch<TableRow>(`${tableName}/${rowId}/resolve`, fixes);
  }
}
