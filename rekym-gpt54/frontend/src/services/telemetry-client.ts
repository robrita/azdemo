import { postFrontendError } from "@/services/api-client";

export function installFrontendTelemetry(): () => void {
  const onError = (event: ErrorEvent) => {
    void postFrontendError({
      message: event.message || "Unhandled window error",
      source: "window.error",
      stack: event.error instanceof Error ? event.error.stack : undefined,
      url: window.location.href,
    }).catch(() => undefined);
  };

  const onUnhandledRejection = (event: PromiseRejectionEvent) => {
    const reason = event.reason instanceof Error ? event.reason.message : String(event.reason);
    const stack = event.reason instanceof Error ? event.reason.stack : undefined;
    void postFrontendError({
      message: reason,
      source: "window.unhandledrejection",
      stack,
      url: window.location.href,
    }).catch(() => undefined);
  };

  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onUnhandledRejection);

  return () => {
    window.removeEventListener("error", onError);
    window.removeEventListener("unhandledrejection", onUnhandledRejection);
  };
}