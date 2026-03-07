/**
 * Shared theme tokens for the Re-KYM platform.
 * Colors sourced from the GCash official Webflow design system (2026).
 *
 * Primary brand blue: #007CFF (gcash-b300)
 * Primary text navy:  #0A2757 (slate-deep)
 */

export const colors = {
  primary: {
    50:  "#E5F1FF",   // blue-pale
    100: "#D2E5FF",   // blue-lightest
    200: "#9BC5FD",   // blue-lighter
    300: "#69A6FC",   // blue-light
    400: "#1972F9",   // blue-mid
    500: "#007CFF",   // gcash-b300 — hero brand blue
    600: "#005CE5",   // blue (default interactive)
    700: "#0A2FB2",   // blue-dark
    800: "#072592",   // blue-darker
    900: "#071969",   // blue-darkest
  },
  navy: {
    50:  "#F6F9FD",
    100: "#EEF2F9",
    200: "#E0E8F3",
    600: "#6780A9",
    700: "#445C85",
    800: "#183462",
    900: "#0A2757",
  },
  success: {
    50:  "#E7F8F0",   // green-pale
    100: "#CAF2E0",   // green-lightest
    500: "#27C990",   // GCash green
    600: "#12AF80",   // green-dark
  },
  warning: {
    50:  "#FEF5E7",   // mango-pale
    100: "#FAE3C2",   // mango-lightest
    500: "#F9A60B",   // GCash mango
    600: "#C67D10",   // mango-dark
  },
  danger: {
    50:  "#F8E6E6",   // red-pale
    100: "#F4C7C9",   // red-lightest
    500: "#D61B2C",   // GCash red
    600: "#B50707",   // red-dark
  },
  teal: {
    50:  "#E9FBFB",   // teal-pale
    500: "#10BCB4",   // GCash teal
    600: "#179B95",   // teal-dark
  },
} as const;

/** Case workflow state badges */
export const caseStateColors: Record<string, string> = {
  Due: "bg-navy-100 text-navy-800 dark:bg-navy-800 dark:text-navy-200",
  Notified: "bg-primary-100 text-primary-800 dark:bg-primary-900/40 dark:text-primary-200",
  AwaitingSubmission: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200",
  UnderMakerReview: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-200",
  PendingCheckerReview: "bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300",
  NeedsCorrection: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200",
  Approved: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200",
  Rejected: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200",
  Completed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
  Exception: "bg-red-200 text-red-900 dark:bg-red-900/50 dark:text-red-200",
};

/** Audit trail action badges */
export const actionColors: Record<string, string> = {
  state_transition: "bg-primary-100 text-primary-800 dark:bg-primary-900/40 dark:text-primary-200",
  policy_violation: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200",
  exception_proposal: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200",
};

/** Generic status badges (open, pending, reviewed, etc.) */
export const statusStyles: Record<string, string> = {
  open:        "bg-primary-50 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300",
  in_progress: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200",
  reviewed:    "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200",
  closed:      "bg-navy-100 text-navy-800 dark:bg-navy-800 dark:text-navy-200",
  merged:      "bg-primary-100 text-primary-800 dark:bg-primary-900/40 dark:text-primary-200",
  completed:   "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200",
  reverted:    "bg-navy-100 text-navy-800 dark:bg-navy-800 dark:text-navy-200",
  pending:     "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200",
  dismissed:   "bg-navy-100 text-navy-800 dark:bg-navy-800 dark:text-navy-200",
  expired:     "bg-navy-100 text-navy-600 dark:bg-navy-800 dark:text-navy-400",
};

/** Priority badges */
export const priorityStyles: Record<string, string> = {
  low:    "bg-navy-100 text-navy-800 dark:bg-navy-800 dark:text-navy-200",
  medium: "bg-primary-50 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300",
  high:   "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200",
  urgent: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200",
};

/** Severity badges (S1–S4) */
export const severityStyles: Record<string, string> = {
  s4: "bg-navy-100 text-navy-700 dark:bg-navy-800 dark:text-navy-300",
  s3: "bg-primary-50 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300",
  s2: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  s1: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
};

/** Confidence level styles */
export const confidenceStyles: Record<string, string> = {
  high:   "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  medium: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
  low:    "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
};
