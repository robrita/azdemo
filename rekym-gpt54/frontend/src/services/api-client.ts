import { resolveApiBaseUrl } from "@/theme/tokens";

export type HealthResponse = {
  status: string;
  dependencies: {
    cosmos: string;
  };
};

export type Merchant = {
  id: string;
  type: string;
  tenantId: string;
  merchantId: string;
  legalName: string;
  riskTier: string;
  createdAt: string;
  updatedAt: string;
};

export type CreateMerchantInput = {
  tenantId: string;
  merchantId: string;
  legalName: string;
  riskTier: string;
};

export type FrontendErrorPayload = {
  message: string;
  source: string;
  stack?: string;
  url?: string;
  correlationId?: string;
};

const apiBaseUrl = resolveApiBaseUrl();

async function request<T>(path: string, init?: RequestInit, useApiBase = true): Promise<T> {
  const requestPath = useApiBase ? `${apiBaseUrl}${path}` : path;
  const response = await fetch(requestPath, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health", undefined, false);
}

export function fetchMerchants(tenantId: string): Promise<Merchant[]> {
  const query = new URLSearchParams({ tenantId });
  return request<Merchant[]>(`/merchants?${query.toString()}`);
}

export function createMerchant(payload: CreateMerchantInput): Promise<Merchant> {
  return request<Merchant>("/merchants", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function postFrontendError(payload: FrontendErrorPayload): Promise<{ status: string }> {
  return request<{ status: string }>("/telemetry/frontend-errors", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}