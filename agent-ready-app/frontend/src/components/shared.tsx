/**
 * Shared / layout components.
 *
 * Add common UI primitives here (e.g. PageHeader, LoadingSpinner, ErrorBanner).
 * Keep feature-specific components in src/features/<feature>/.
 */

export function LoadingSpinner({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center py-8 ${className}`}>
      <span className="spinner" />
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200">
      {message}
    </div>
  );
}
