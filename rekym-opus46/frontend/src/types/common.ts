/**
 * Shared TypeScript types.
 * Add domain-specific interfaces here as the app grows.
 */

/** Standard paginated response envelope from the backend. */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

/** API error shape returned by the backend. */
export interface ApiErrorResponse {
  detail: string;
  errorCode?: string;
}
