import type {
  ApplyResult,
  AssetRow,
  Canvas,
  DirectorResult,
  EDL,
  Issue,
  Job,
  Op,
  Project,
  RevisionRow,
  Understanding,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_CUTLAB_API ?? "http://127.0.0.1:8787";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public issues: Issue[] = [],
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers:
      init?.body && typeof init.body === "string"
        ? { "Content-Type": "application/json" }
        : undefined,
    ...init,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error ?? {};
    throw new ApiError(
      res.status,
      err.code ?? "E_HTTP",
      err.message ?? res.statusText,
      err.issues ?? [],
    );
  }
  return body as T;
}

export const api = {
  createProject: (name: string, canvas: Canvas) =>
    request<Project>("/api/v1/projects", {
      method: "POST",
      body: JSON.stringify({ name, canvas }),
    }),
  listProjects: () => request<Project[]>("/api/v1/projects"),
  getProject: (id: string) => request<Project>(`/api/v1/projects/${id}`),
  getEdl: (id: string, rev?: number) =>
    request<EDL>(
      `/api/v1/projects/${id}/edl${rev !== undefined ? `?rev=${rev}` : ""}`,
    ),
  apply: (id: string, baseRev: number, ops: Op[], mode = "commit") =>
    request<ApplyResult>(`/api/v1/projects/${id}/apply`, {
      method: "POST",
      body: JSON.stringify({ base_rev: baseRev, ops, mode }),
    }),
  undo: (id: string) =>
    request<{ rev: number }>(`/api/v1/projects/${id}/undo`, { method: "POST" }),
  redo: (id: string) =>
    request<{ rev: number }>(`/api/v1/projects/${id}/redo`, { method: "POST" }),
  revisions: (id: string) =>
    request<RevisionRow[]>(`/api/v1/projects/${id}/revisions`),
  proposals: (id: string) =>
    request<RevisionRow[]>(`/api/v1/projects/${id}/proposals`),
  acceptProposal: (id: string, rev: number) =>
    request<{ rev: number }>(`/api/v1/projects/${id}/proposals/${rev}/accept`, {
      method: "POST",
    }),
  rejectProposal: (id: string, rev: number) =>
    request<{ rev: number }>(`/api/v1/projects/${id}/proposals/${rev}/reject`, {
      method: "POST",
    }),
  listAssets: (id: string) => request<AssetRow[]>(`/api/v1/projects/${id}/assets`),
  uploadAsset: async (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file, file.name);
    return request<{ asset_id: string; job_id: string; status: string }>(
      `/api/v1/projects/${id}/assets`,
      { method: "POST", body: form },
    );
  },
  render: (id: string, rev?: number) =>
    request<{ job_id: string; rev: number }>(`/api/v1/projects/${id}/render`, {
      method: "POST",
      body: JSON.stringify(rev !== undefined ? { rev } : {}),
    }),
  analyzeAsset: (id: string, assetId: string) =>
    request<{ asset_id: string; job_id: string; status: string }>(
      `/api/v1/projects/${id}/assets/${assetId}/analyze`,
      { method: "POST" },
    ),
  getUnderstanding: (id: string, assetId: string) =>
    request<Understanding>(
      `/api/v1/projects/${id}/assets/${assetId}/understanding`,
    ),
  directorBackend: (id: string) =>
    request<{ backend: string }>(`/api/v1/projects/${id}/director/backend`),
  directorCommand: (id: string, text: string) =>
    request<DirectorResult>(`/api/v1/projects/${id}/director/command`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  directorAnswer: (id: string, requestId: string, answer: string) =>
    request<DirectorResult>(`/api/v1/projects/${id}/director/answer`, {
      method: "POST",
      body: JSON.stringify({ request_id: requestId, answer }),
    }),
  getJob: (jobId: string) => request<Job>(`/api/v1/jobs/${jobId}`),
};

export function mediaUrl(projectId: string, relPath: string): string {
  return `${API_BASE}/media/${projectId}/${relPath}`;
}

export type WsEvent =
  | { type: "job"; job: Job }
  | {
      type: "revision";
      project_id: string;
      rev: number;
      summary: string;
      state: string;
    };

export function connectWs(
  projectId: string,
  onEvent: (e: WsEvent) => void,
): () => void {
  const url = API_BASE.replace(/^http/, "ws") + "/ws";
  let ws: WebSocket | null = null;
  let closed = false;
  let retry: ReturnType<typeof setTimeout> | null = null;

  const open = () => {
    ws = new WebSocket(url);
    ws.onopen = () => ws?.send(JSON.stringify({ project_id: projectId }));
    ws.onmessage = (m) => {
      try {
        onEvent(JSON.parse(m.data) as WsEvent);
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onclose = () => {
      if (!closed) retry = setTimeout(open, 1000);
    };
  };
  open();
  return () => {
    closed = true;
    if (retry) clearTimeout(retry);
    ws?.close();
  };
}
