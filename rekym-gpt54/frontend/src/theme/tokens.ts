export const statusStyles: Record<string, string> = {
  healthy: "badge-success",
  degraded: "badge-warning",
  ready: "badge-primary",
  not_ready: "badge-danger",
};

export const riskTierStyles: Record<string, string> = {
  low: "badge-primary",
  medium: "badge-warning",
  high: "badge-danger",
};

export function resolveAppTitle(): string {
  return import.meta.env.VITE_APP_TITLE || "Template Merchant Hub";
}

export function resolveApiBaseUrl(): string {
  return import.meta.env.VITE_API_URL || "/api/v1";
}