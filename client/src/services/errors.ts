/**
 * Base API error class with status code and response data.
 */
export class ApiError extends Error {
  public readonly statusCode: number;
  public readonly data: unknown;

  constructor(message: string, statusCode: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.data = data;
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

/**
 * Network error for timeout or connection issues.
 */
export class NetworkError extends Error {
  public readonly cause?: Error;

  constructor(message: string, cause?: Error) {
    super(message);
    this.name = 'NetworkError';
    this.cause = cause;
    Object.setPrototypeOf(this, NetworkError.prototype);
  }
}

/**
 * Validation error for 400 Bad Request responses.
 */
export class ValidationError extends ApiError {
  public readonly fields?: Record<string, string[]>;

  constructor(
    message: string,
    fields?: Record<string, string[]>,
    data?: unknown
  ) {
    super(message, 400, data);
    this.name = 'ValidationError';
    this.fields = fields;
    Object.setPrototypeOf(this, ValidationError.prototype);
  }
}

/**
 * Get a user-friendly error message from any error type.
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof ValidationError) {
    if (error.fields) {
      const fieldErrors = Object.entries(error.fields)
        .map(([field, messages]) => `${field}: ${messages.join(', ')}`)
        .join('; ');
      return fieldErrors || error.message;
    }
    return error.message;
  }

  if (error instanceof NetworkError) {
    return 'Network error. Please check your connection and try again.';
  }

  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return 'An unexpected error occurred';
}
