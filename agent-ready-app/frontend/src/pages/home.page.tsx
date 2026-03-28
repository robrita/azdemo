export function HomePage() {
  return (
    <div className="page-container">
      <h1 className="page-title mb-6">Dashboard</h1>

      <div className="card">
        <h2 className="mb-2 text-lg font-semibold">Welcome to My App</h2>
        <p className="text-navy-600 dark:text-[var(--color-text-secondary)]">
          Your starter template is running. Edit{" "}
          <code className="rounded bg-navy-100 px-1.5 py-0.5 text-sm dark:bg-[var(--color-surface-alt)]">
            src/pages/home.page.tsx
          </code>{" "}
          to start building.
        </p>
        <div className="mt-4 flex gap-3">
          <button className="btn-primary">Primary Action</button>
          <button className="btn-secondary">Secondary</button>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="card">
          <span className="badge-success">Active</span>
          <h3 className="mt-2 font-semibold">Backend API</h3>
          <p className="text-sm text-navy-600 dark:text-[var(--color-text-secondary)]">
            FastAPI on port 8000
          </p>
        </div>
        <div className="card">
          <span className="badge-primary">Vite</span>
          <h3 className="mt-2 font-semibold">Frontend</h3>
          <p className="text-sm text-navy-600 dark:text-[var(--color-text-secondary)]">
            React + TypeScript on port 5173
          </p>
        </div>
        <div className="card">
          <span className="badge-warning">Pending</span>
          <h3 className="mt-2 font-semibold">Cosmos DB</h3>
          <p className="text-sm text-navy-600 dark:text-[var(--color-text-secondary)]">
            Configure in .env to connect
          </p>
        </div>
      </div>
    </div>
  );
}
