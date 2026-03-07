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
  schema?: {
    fields?: ValidateSchemaField[];
    [key: string]: unknown;
  };
  sample?: unknown;
};

export type FileRegistryUpdate = {
  status?: string;
  object_key?: string;
  file_schema?: unknown;
};

type AuthProvider = {
  getCurrentUserName(): Promise<string>;
};

export class HttpDataService {
  private baseUrl: string;
  private authProvider: AuthProvider;

  constructor(authProvider: AuthProvider, baseUrl?: string) {
    this.authProvider = authProvider;
    this.baseUrl =
      baseUrl || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const cleanEndpoint = endpoint.startsWith('/')
      ? endpoint.slice(1)
      : endpoint;
    const url = `${this.baseUrl.replace(/\/$/, '')}/api/${cleanEndpoint}`;

    const userName = await this.authProvider.getCurrentUserName();

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(userName ? { 'X-User-Name': userName } : {}),
      ...(options.headers as Record<string, string>),
    };

    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `API Error: ${response.statusText}`);
    }

    return response.json();
  }

  async getTablesWithMetadata(): Promise<{ tables: TableMetadata[] }> {
    return this.request<{ tables: TableMetadata[] }>('tables_with_metadata', {
      cache: 'no-store',
    });
  }

  async validateSchema(fileId: string): Promise<ValidateSchemaResponse> {
    const query = new URLSearchParams({ file_id: fileId });
    return this.request<ValidateSchemaResponse>(`validate_schema?${query}`, {
      method: 'POST',
    });
  }

  async updateFileRegistry(
    fileId: string,
    update: FileRegistryUpdate
  ): Promise<{ file_id: string; updated_fields: FileRegistryUpdate }> {
    return this.request<{
      file_id: string;
      updated_fields: FileRegistryUpdate;
    }>(`files/${encodeURIComponent(fileId)}`, {
      method: 'PATCH',
      body: JSON.stringify(update),
    });
  }

  async processFile(
    fileId: string,
    proposedSchema: Record<string, string>
  ): Promise<{ file_id: string; status: string }> {
    return this.request<{ file_id: string; status: string }>(
      `files/${encodeURIComponent(fileId)}/process`,
      {
        method: 'POST',
        body: JSON.stringify({ proposed_schema: proposedSchema }),
      }
    );
  }

  async getTableSchema(tableName: string): Promise<TableSchemaResponse> {
    return this.request<TableSchemaResponse>(`schema/${tableName}`, {
      cache: 'no-store',
    });
  }

  async getTableData(
    tableName: string,
    params?: PaginationParams
  ): Promise<PaginatedResponse<TableRow>> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined)
      searchParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined)
      searchParams.append('limit', params.limit.toString());

    const queryString = searchParams.toString();
    const endpoint = queryString ? `${tableName}?${queryString}` : tableName;

    return this.request<PaginatedResponse<TableRow>>(endpoint, {
      cache: 'no-store',
    });
  }

  async searchTableData(
    tableName: string,
    column: string,
    value: string,
    params?: PaginationParams
  ): Promise<PaginatedResponse<TableRow>> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined)
      searchParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined)
      searchParams.append('limit', params.limit.toString());

    const queryString = searchParams.toString();
    const endpoint = `${tableName}/search/${column}/${encodeURIComponent(
      value
    )}${queryString ? `?${queryString}` : ''}`;

    return this.request<PaginatedResponse<TableRow>>(endpoint, {
      cache: 'no-store',
    });
  }

  async createRow(
    tableName: string,
    data: Omit<TableRow, 'id'>
  ): Promise<TableRow> {
    return this.request<TableRow>(tableName, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateRow(
    tableName: string,
    id: string | number,
    data: Partial<TableRow>
  ): Promise<TableRow> {
    return this.request<TableRow>(`${tableName}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteRow(tableName: string, id: string | number): Promise<void> {
    await this.request(`${tableName}/${id}`, {
      method: 'DELETE',
    });
  }
}
