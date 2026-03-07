/**
 * UI configuration constants.
 */
export const UI = {
  PAGE_SIZE: 50,
  DEBOUNCE_MS: 150,
  TOAST_SUCCESS_MS: 3000,
  TOAST_ERROR_MS: 5000,
} as const;

/**
 * Color palette.
 */
export const COLORS = {
  PRIMARY: '#1c66bb',
  PRIMARY_DARK: '#0d4a8f',
  SUCCESS: '#22c55e',
  ERROR: '#ef4444',
  WARNING: '#f59e0b',
} as const;

/**
 * Branding configuration.
 */
export const BRANDING = {
  COMPANY_NAME: 'Texas Hearing Institute',
  APP_SUBTITLE: 'Data Warehouse',
} as const;

/**
 * File upload configuration.
 */
export const FILE_UPLOAD = {
  ALLOWED_TYPES: ['text/csv', 'application/vnd.ms-excel'] as string[],
  ALLOWED_EXTENSIONS: ['.csv', '.xlsx'] as string[],
};
