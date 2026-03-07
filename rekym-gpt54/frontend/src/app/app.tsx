import { useEffect, useState } from "react";

import { DashboardPage } from "@/features/dashboard/dashboard-page";
import { installFrontendTelemetry } from "@/services/telemetry-client";
import { resolveAppTitle } from "@/theme/tokens";

export function App() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    document.title = resolveAppTitle();
    const disposeTelemetry = installFrontendTelemetry();
    return disposeTelemetry;
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  return <DashboardPage onToggleTheme={() => setTheme((current) => (current === "light" ? "dark" : "light"))} theme={theme} />;
}