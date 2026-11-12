export const kindLabels: Record<string, string> = {
  UNKNOWN: "Unidentified document",
  EPC: "Energy performance certificate",
  ASBESTOS_CERTIFICATE: "Asbestos certificate",
  ELECTRICAL_INSPECTION: "Electrical inspection",
  SOIL_CERTIFICATE: "Soil certificate",
  SYNDIC_INFORMATION: "Syndic information",
  AGM_MINUTES: "General meeting minutes",
  EXTRAORDINARY_AGM_MINUTES: "Extraordinary meeting minutes",
  BASIS_DEED: "Basis deed",
  CO_OWNERSHIP_REGULATIONS: "Co-ownership regulations",
  INTERNAL_RULES: "Internal rules",
  PERIODIC_CHARGE_STATEMENT: "Periodic charge statements",
  BALANCE_SHEET: "Approved balance sheet",
  CAPITAL_CALL: "Capital call",
  RESERVE_FUND_STATEMENT: "Reserve-capital statement",
  OTHER_CO_OWNERSHIP_DOCUMENT: "Other co-ownership document",
};
export const statusLabels: Record<string, string> = {
  UNSUPPORTED_LAYOUT: "Layout not supported",
  UNPARSEABLE: "Could not read supported fields",
  PARTIALLY_PARSED: "Partly analyzed",
  INVALID_SOURCE_RESPONSE: "Official selection could not be confirmed",
  NOT_RESOLVED: "Property not yet confirmed",
  ANALYZED: "Analyzed",
  UNKNOWN: "Unknown document",
  OCR_REQUIRED: "Needs OCR",
  FAILED: "Processing failed",
  PENDING: "Waiting",
  IN_PROGRESS: "Analyzing",
  NOT_ANALYZED: "Not analyzed",
  SAFETY_REVIEW: "File safety review",
  MATCHED: "Matched",
  POSSIBLE_MATCH: "Review association",
  UNVERIFIED: "Not verified",
  MISMATCH: "Different property",
  PRESENT: "Available",
  EXPLICIT_NONE: "Explicitly none",
  MISSING: "Missing",
  PARTIAL: "Partial",
  UNUSABLE: "Not usable",
  EXPIRED: "Expired",
  MISMATCHED: "Different property",
  CONDITIONAL: "Conditional",
  REQUIRED: "Required",
  NOT_REQUIRED: "Not required",
  NOT_YET_EFFECTIVE: "Not yet applicable",
  INFO: "Info",
  REVIEW: "Review",
  WARNING: "Needs attention",
  BLOCKING_DATA_GAP: "Missing information",
  COMPLETE: "Complete",
  INCOMPLETE: "Incomplete",
  BLOCKED_BY_MISSING_DATA: "More information needed",
  NOT_APPLICABLE: "Scope not established",
  RESOLVED: "Official address confirmed",
  PARTIALLY_RESOLVED: "Some official information unavailable",
  UPSTREAM_UNAVAILABLE: "Official source unavailable",
  NOT_FOUND: "Property not found",
  NEEDS_SELECTION: "Choose a property",
  NOT_ESTABLISHED: "No co-ownership information identified",
  DOCUMENTED: "Information available",
  APPROVED: "Approved",
  PROPOSED: "Proposed",
  REJECTED: "Rejected",
  POSTPONED: "Postponed",
  INFORMATION_ONLY: "For information",
  UNKNOWN_ALLOCATION: "Expense allocation not established",
  INSUFFICIENT_BUDGET: "Approved budget not established",
  CONFLICTING_INPUTS: "Conflicting information",
  CALCULATED: "Estimate available",
};
export function label(code: string) {
  return statusLabels[code] ?? code.toLowerCase().replaceAll("_", " ");
}
export function kind(code: string) {
  return kindLabels[code] ?? code.toLowerCase().replaceAll("_", " ");
}
export function money(
  amount: string | number | null | undefined,
  currency = "EUR",
) {
  return amount == null
    ? "Not available"
    : new Intl.NumberFormat("en-BE", {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
      }).format(Number(amount));
}
export function date(value: string | null | undefined) {
  return value
    ? new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      }).format(new Date(value))
    : "Date not supplied";
}
export function safeUri(uri: string | null) {
  if (!uri) return undefined;
  try {
    const u = new URL(uri);
    return u.protocol === "https:" && !u.username && !u.password
      ? u.href
      : undefined;
  } catch {
    return undefined;
  }
}

const componentLabels: Record<string, string> = {
  WORKING_CAPITAL: "Working capital amount",
  RESERVE_CAPITAL: "Reserve capital amount",
  SELLER_ARREARS: "Seller's outstanding arrears",
  RESERVE_CAPITAL_CALLS: "Reserve-capital calls",
  PENDING_LITIGATION: "Pending co-ownership litigation",
  AGM_MINUTES_3Y: "General meeting minutes · previous 3 years",
  PERIODIC_CHARGES_2Y: "Periodic charges · previous 2 years",
  LATEST_APPROVED_BALANCE_SHEET: "Latest approved balance copy",
};
export function componentLabel(code: string) {
  return componentLabels[code] ?? label(code);
}
