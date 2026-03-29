import { ApiError, NetworkError, ValidationError } from './errors';

export type HttpClientConfig = {
  baseUrl: string;
  headers?: Record<string, string>;
  timeout?: number;
};

export type RequestOptions = {
  headers?: Record<string, string>;
  timeout?: number;
  cache?: RequestCache;
};

/**
 * HTTP client abstraction with configurable base URL, headers, and timeout support.
 */
export class HttpClient {
  private baseUrl: string;
  private defaultHeaders: Record<string, string>;
  private defaultTimeout: number;

  constructor(config: HttpClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/$/, '');
    this.defaultHeaders = config.headers || {};
    this.defaultTimeout = config.timeout || 30000;
  }

  private async request<T>(
    method: string,
    endpoint: string,
    body?: unknown,
    options: RequestOptions = {}
  ): Promise<T> {
    const url = `${this.baseUrl}/${endpoint.replace(/^\//, '')}`;
    const timeout = options.timeout ?? this.defaultTimeout;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...this.defaultHeaders,
      ...options.headers,
    };

    try {
      const response = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
        cache: options.cache,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const message = errorData.detail || `API Error: ${response.statusText}`;

        if (response.status === 400) {
          throw new ValidationError(message, errorData.fields, errorData);
        }

        throw new ApiError(message, response.status, errorData);
      }

      // Handle empty responses (e.g., 204 No Content)
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        return undefined as T;
      }

      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof ApiError || error instanceof ValidationError) {
        throw error;
      }

      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new NetworkError('Request timed out');
      }

      if (error instanceof TypeError) {
        throw new NetworkError(
          'Network error. Please check your connection.',
          error
        );
      }

      throw error;
    }
  }

  async get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('GET', endpoint, undefined, options);
  }

  async post<T>(
    endpoint: string,
    body?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>('POST', endpoint, body, options);
  }

  async put<T>(
    endpoint: string,
    body?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>('PUT', endpoint, body, options);
  }

  async patch<T>(
    endpoint: string,
    body?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>('PATCH', endpoint, body, options);
  }

  async delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('DELETE', endpoint, undefined, options);
  }

  /**
   * Update default headers (e.g., for adding auth tokens).
   */
  setHeader(key: string, value: string): void {
    this.defaultHeaders[key] = value;
  }

  /**
   * Remove a default header.
   */
  removeHeader(key: string): void {
    delete this.defaultHeaders[key];
  }
}
