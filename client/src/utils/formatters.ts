/**
 * Format a value for display, returning a fallback for null/undefined.
 */
export function formatValue(
  value: string | number | boolean | null | undefined,
  fallback: string = '—'
): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

/**
 * Format a date string for display.
 * Returns fallback if the date is invalid or null.
 */
export function formatDate(
  date: string | Date | null | undefined,
  fallback: string = '—'
): string {
  if (!date) {
    return fallback;
  }

  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    if (isNaN(dateObj.getTime())) {
      return fallback;
    }

    return dateObj.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return fallback;
  }
}

/**
 * Format a date with time for display.
 */
export function formatDateTime(
  date: string | Date | null | undefined,
  fallback: string = '—'
): string {
  if (!date) {
    return fallback;
  }

  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    if (isNaN(dateObj.getTime())) {
      return fallback;
    }

    return dateObj.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return fallback;
  }
}
