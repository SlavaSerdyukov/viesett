import type {
  DossierSnapshotResponse as Dossier,
  PolicyOut,
  PreviewResponse,
  SessionResponse,
  WebConfigResponse,
  WorkspaceOut,
} from "./contracts";
let token: string | null = null;
export function setToken(value: string | null) {
  token = value;
}
export class ApiError extends Error {
  constructor(public status: number) {
    super(
      status === 401
        ? "Your private session has ended. Reconnect to continue."
        : status === 429
          ? "Too many requests. Please wait a minute before trying again."
          : status === 403
            ? "This action is not available from this page."
            : status === 404
              ? "This dossier or document is not available to this session."
              : status === 413
                ? "This PDF is too large. Choose a smaller file."
                : status === 409
                  ? "The dossier changed or a required acknowledgement is missing. Refresh and try again."
                  : status === 422 || status === 415
                    ? "Please check the input and use a supported PDF."
                    : "The service could not complete this request. Please try again.",
    );
  }
}
export async function request<T>(
  path: string,
  init: RequestInit = {},
  authenticated = true,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api/v1" + path, {
      ...init,
      credentials: "omit",
      cache: "no-store",
      headers: {
        ...(init.body instanceof Blob
          ? {}
          : { "Content-Type": "application/json" }),
        ...(authenticated && token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new Error(
      "Connection interrupted. Your property has not been marked as invalid. Try again.",
    );
  }
  if (!response.ok) throw new ApiError(response.status);
  return (response.status === 204 ? undefined : await response.json()) as T;
}
export type Selection = {
  query: string;
  selected_address_object_id?: string;
  selected_building_unit_object_id?: string;
};
export const api = {
  config: () => request<WebConfigResponse>("/web-config", {}, false),
  preview: (selection: Selection) =>
    request<PreviewResponse>(
      "/property-preview",
      { method: "POST", body: JSON.stringify(selection) },
      false,
    ),
  session: () =>
    request<SessionResponse>("/development/session", { method: "POST" }, false),
  workspaces: () => request<WorkspaceOut[]>("/workspaces"),
  create: (selection: Selection) =>
    request<Dossier>("/dossiers", {
      method: "POST",
      body: JSON.stringify(selection),
    }),
  demo: () => request<Dossier>("/development/demo-dossier", { method: "POST" }),
  dossier: (id: string) => request<Dossier>(`/workspaces/${id}/dossier`),
  refresh: (id: string) =>
    request<Dossier>(`/workspaces/${id}/refresh`, {
      method: "POST",
      body: JSON.stringify({ public_sources: true }),
    }),
  resolve: (id: string, selection: Selection) =>
    request<unknown>(`/workspaces/${id}/property-resolution`, {
      method: "POST",
      body: JSON.stringify(selection),
    }),
  retry: (wid: string, did: string) =>
    request<unknown>(`/workspaces/${wid}/documents/${did}/analyze`, {
      method: "POST",
      body: "{}",
    }),
  policies: () => request<PolicyOut[]>("/policies"),
  acknowledge: (id: string) =>
    request<void>("/me/policy-acknowledgements", {
      method: "POST",
      body: JSON.stringify({ policy_version_id: id }),
    }),
  upload: (id: string, file: File) =>
    request<Dossier>(`/workspaces/${id}/document-intake`, {
      method: "POST",
      headers: {
        "Content-Type": "application/pdf",
        "X-Filename": encodeURIComponent(file.name),
      },
      body: file,
    }),
  remove: (wid: string, did: string) =>
    request<void>(`/workspaces/${wid}/documents/${did}`, { method: "DELETE" }),
  classify: (wid: string, did: string, kind: string) =>
    request<unknown>(`/workspaces/${wid}/documents/${did}/analyze`, {
      method: "POST",
      body: JSON.stringify({ manual_kind: kind }),
    }),
  draft: (id: string, kinds: string[]) =>
    request<{ generated_text: string }>(
      `/workspaces/${id}/document-request-draft`,
      {
        method: "POST",
        body: JSON.stringify({
          requested_document_types: kinds,
          language: "en",
        }),
      },
    ),
};
export async function privatePdf(
  wid: string,
  did: string,
  signal: AbortSignal,
): Promise<string> {
  const response = await fetch(
    `/api/v1/workspaces/${wid}/documents/${did}/content`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: "omit",
      cache: "no-store",
      signal,
    },
  );
  if (!response.ok) throw new ApiError(response.status);
  return URL.createObjectURL(await response.blob());
}
