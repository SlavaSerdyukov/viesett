import type { DossierSnapshotResponse } from "./contracts";
export function processingInterval(
  data: DossierSnapshotResponse | undefined,
  failures: number,
  now = Date.now(),
) {
  if (
    failures >= 4 ||
    !data?.documents.some(
      (d) =>
        ["PENDING", "IN_PROGRESS"].includes(d.status) &&
        now - new Date(d.processing_since ?? d.created_at).getTime() < 120_000,
    )
  )
    return false;
  return Math.min(30_000, 3000 * 2 ** failures);
}
