import {
  PaginatedResponse,
  TableRow,
  TableSchemaResponse,
  TableMetadata,
  PaginationParams,
} from './types';

// Use environment variable or default to localhost
const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  'http://localhost:8000';

class ApiService {
  private static async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    // Ensure clean URL construction
    const cleanEndpoint = endpoint.startsWith('/')
      ? endpoint.slice(1)
      : endpoint;
    const url = `${BACKEND_URL.replace(/\/$/, '')}/api/${cleanEndpoint}`;

    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `API Error: ${response.statusText}`);
    }

    return response.json();
  }

  static async getTablesWithMetadata(): Promise<{ tables: TableMetadata[] }> {
    return this.request<{ tables: TableMetadata[] }>('tables_with_metadata', {
      cache: 'no-store',
    });
  }

  static async getTableSchema(tableName: string): Promise<TableSchemaResponse> {
    return this.request<TableSchemaResponse>(`schema/${tableName}`, {
      cache: 'no-store',
    });
  }

  static async getTableData(
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

  static async searchTableData(
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
    const endpoint = `${tableName}/search/${column}/${encodeURIComponent(value)}${queryString ? `?${queryString}` : ''}`;

    return this.request<PaginatedResponse<TableRow>>(endpoint, {
      cache: 'no-store',
    });
  }

  static async createRow(
    tableName: string,
    data: Omit<TableRow, 'id'>
  ): Promise<TableRow> {
    return this.request<TableRow>(`${tableName}`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async updateRow(
    tableName: string,
    id: string | number,
    data: Partial<TableRow>
  ): Promise<TableRow> {
    return this.request<TableRow>(`${tableName}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  static async deleteRow(
    tableName: string,
    id: string | number
  ): Promise<void> {
    await this.request(`${tableName}/${id}`, {
      method: 'DELETE',
    });
  }
}

export default ApiService;
