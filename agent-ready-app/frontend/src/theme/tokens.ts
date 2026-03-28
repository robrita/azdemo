/**
 * Shared theme tokens.
 * Import from here for status/severity style maps — never duplicate inline.
 */

export const colors = {
  primary: {
    50: "#E5F1FF",
    100: "#D2E5FF",
    200: "#9BC5FD",
    300: "#69A6FC",
    400: "#1972F9",
    500: "#007CFF",
    600: "#005CE5",
    700: "#0A2FB2",
    800: "#072592",
    900: "#071969",
  },
  navy: {
    50: "#F6F9FD",
    100: "#EEF2F9",
    200: "#E0E8F3",
    600: "#6780A9",
    700: "#445C85",
    800: "#183462",
    900: "#0A2757",
  },
  success: {
    50: "#E7F8F0",
    500: "#27C990",
    600: "#12AF80",
  },
  warning: {
    50: "#FEF5E7",
    500: "#F9A60B",
    600: "#C67D10",
  },
  danger: {
    50: "#F8E6E6",
    500: "#D61B2C",
    600: "#B50707",
  },
} as const;

/** Generic status badge styles */
export const statusStyles: Record<string, string> = {
  active: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200",
  pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200",
  inactive: "bg-navy-100 text-navy-800 dark:bg-navy-800 dark:text-navy-200",
  error: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200",
};
