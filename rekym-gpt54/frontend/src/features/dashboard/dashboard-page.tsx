import { FormEvent, useEffect, useState } from "react";

import { StatusPill } from "@/components/status-pill";
import { createMerchant, fetchHealth, fetchMerchants, type Merchant } from "@/services/api-client";
import { riskTierStyles } from "@/theme/tokens";

type DashboardPageProps = {
  theme: "light" | "dark";
  onToggleTheme: () => void;
};

const initialForm = {
  tenantId: "tenant-demo",
  merchantId: "merchant-001",
  legalName: "Template Merchant Co.",
  riskTier: "low",
};

export function DashboardPage({ theme, onToggleTheme }: DashboardPageProps) {
  const [healthStatus, setHealthStatus] = useState("degraded");
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [formState, setFormState] = useState(initialForm);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    void fetchHealth()
      .then((response) => setHealthStatus(response.status))
      .catch(() => setHealthStatus("degraded"));

    void fetchMerchants(initialForm.tenantId)
      .then((response) => setMerchants(response))
      .catch((error: Error) => setErrorMessage(error.message));
  }, []);

  const submitMerchant = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage("");

    try {
      const created = await createMerchant(formState);
      setMerchants((current) => [created, ...current]);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to create merchant");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page-shell">
      <div className="page-container space-y-8">
        <section className="hero-card">
          <div className="space-y-4">
            <span className="badge-primary">Portable Template Contract</span>
            <div className="space-y-3">
              <h1 className="text-4xl font-semibold">FastAPI, React, Azure Functions, and Cosmos DB in one starter.</h1>
              <p className="support-copy max-w-2xl">
                This sample screen proves the template runtime is wired end to end: themed frontend,
                proxy-backed API access, typed backend routes, and Cosmos-backed health checks.
              </p>
            </div>
          </div>

          <div className="card space-y-4">
            <div className="flex items-center justify-between">
              <span className="support-copy">Theme mode</span>
              <button className="btn-secondary" onClick={onToggleTheme} type="button">
                Switch to {theme === "light" ? "dark" : "light"}
              </button>
            </div>
            <div className="space-y-2">
              <p className="support-copy">Backend health</p>
              <StatusPill status={healthStatus} label={healthStatus.replace("_", " ")} />
            </div>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="card space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="section-title">Starter merchants</h2>
              <span className="support-copy">Route -> service -> repository -> Cosmos DB</span>
            </div>

            {errorMessage ? <p className="badge-danger">{errorMessage}</p> : null}

            <div className="space-y-3">
              {merchants.length === 0 ? (
                <p className="support-copy">No merchants yet. Create one with the form.</p>
              ) : (
                merchants.map((merchant) => (
                  <article className="rounded-2xl border border-navy-100 p-4 dark:border-[#1e3a5f]" key={merchant.id}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h3 className="text-lg font-semibold">{merchant.legalName}</h3>
                        <p className="support-copy">
                          {merchant.merchantId} · {merchant.tenantId}
                        </p>
                      </div>
                      <span className={riskTierStyles[merchant.riskTier] || "badge-primary"}>
                        {merchant.riskTier}
                      </span>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>

          <div className="card space-y-4">
            <div>
              <h2 className="section-title">Create a merchant</h2>
              <p className="support-copy">This writes a merchant document and an audit event in parallel.</p>
            </div>

            <form className="space-y-3" onSubmit={submitMerchant}>
              <input
                onChange={(event) => setFormState((current) => ({ ...current, tenantId: event.target.value }))}
                placeholder="Tenant ID"
                value={formState.tenantId}
              />
              <input
                onChange={(event) => setFormState((current) => ({ ...current, merchantId: event.target.value }))}
                placeholder="Merchant ID"
                value={formState.merchantId}
              />
              <input
                onChange={(event) => setFormState((current) => ({ ...current, legalName: event.target.value }))}
                placeholder="Legal name"
                value={formState.legalName}
              />
              <select
                onChange={(event) => setFormState((current) => ({ ...current, riskTier: event.target.value }))}
                value={formState.riskTier}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
              <button className="btn-primary w-full" disabled={isSubmitting} type="submit">
                {isSubmitting ? "Creating..." : "Create merchant"}
              </button>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
}