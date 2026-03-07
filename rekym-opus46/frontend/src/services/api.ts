/**
 * Shared API client for backend requests.
 *
 * Uses Vite's proxy to forward /api/v1/* to the backend.
 * Add typed fetch helpers here as you add endpoints.
 */

const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

// ---- Items (example) ----

export interface Item {
  id: string;
  name: string;
  status: string;
  createdAt: string;
  updatedAt: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export function fetchItems(page = 1, pageSize = 20) {
  return request<PaginatedResponse<Item>>(
    `/items?page=${page}&pageSize=${pageSize}`,
  );
}

export function fetchItem(id: string) {
  return request<Item>(`/items/${encodeURIComponent(id)}`);
}

export function createItem(data: { name: string }) {
  return request<Item>("/items", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
