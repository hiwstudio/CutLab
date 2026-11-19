import type {
  ApplyResult,
  AssetRow,
  Canvas,
  DirectorResult,
  EDL,
  Issue,
  Job,
  LibrarySound,
  Op,
  Project,
  RevisionRow,
  Understanding,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_CUTLAB_API ?? "";

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
  engineProjects: () => request<{ name: string; scene_count: number; duration_ms: number }[]>("/api/v1/engines/mixfix/projects"),
  importEngine: (sourceProject: string, mode: string, canvas: Canvas) =>
    request<{project_id: string; job_id: string; warnings: string[]}>("/api/v1/engines/mixfix/import", {
      method: "POST", body: JSON.stringify({source_project: sourceProject, mode, canvas}),
    }),
  engineLink: (id: string, rev?: number) => request<EngineLink>(`/api/v1/projects/${id}/engine-link${rev === undefined ? "" : `?rev=${rev}`}`),
  engineScene: (id: string, sceneId: string, baseRev: number, action: "refresh" | "request", note = "") =>
    request<{job_id: string}>(`/api/v1/projects/${id}/engine-scenes/${sceneId}/${action}`, {
      method: "POST", body: JSON.stringify({base_rev: baseRev, note}),
    }),
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
  listSounds: () => request<LibrarySound[]>("/api/v1/sound-library"),
  soundPreviewUrl: (soundId: string) => `${API_BASE}/api/v1/sound-library/${soundId}/preview`,
  importSound: (id: string, soundId: string) =>
    request<{ asset_id: string; job_id: string; status: string }>(
      `/api/v1/projects/${id}/sound-library/${soundId}`,
      { method: "POST" },
    ),
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
  analyzeAsset: (id: string, assetId: string, language?: string) =>
    request<{ asset_id: string; job_id: string; status: string }>(
      `/api/v1/projects/${id}/assets/${assetId}/analyze`,
      { method: "POST", body: JSON.stringify(language ? { language } : {}) },
    ),
  cutoutAsset: (id: string, assetId: string) =>
    request<{ asset_id: string; job_id: string; status: string }>(
      `/api/v1/projects/${id}/assets/${assetId}/cutout`,
      { method: "POST" },
    ),
  extractAudio: (id: string, assetId: string) =>
    request<{ asset_id: string; job_id: string; status: string }>(
      `/api/v1/projects/${id}/assets/${assetId}/extract-audio`,
      { method: "POST" },
    ),
  textToSound: (id: string, text: string) =>
    request<{ asset_id: string; job_id: string; status: string }>(
      `/api/v1/projects/${id}/text-to-sound`,
      { method: "POST", body: JSON.stringify({ text }) },
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
  cancelJob: (jobId: string) => request<{ok: boolean}>(`/api/v1/jobs/${jobId}/cancel`, {method: "POST"}),
  recapAsset: (id: string, assetId: string, targetMinutes: number) =>
    request<{ job_id: string }>(
      `/api/v1/projects/${id}/assets/${assetId}/recap`,
      { method: "POST", body: JSON.stringify({ target_minutes: targetMinutes }) },
    ),
  compactAsset: (id: string, assetId: string, targetMs: number) =>
    request<{ job_id: string }>(
      `/api/v1/projects/${id}/assets/${assetId}/compact`,
      { method: "POST", body: JSON.stringify({ target_ms: targetMs }) },
    ),
  previewSegment: (id: string, fromMs: number, toMs: number, rev?: number) =>
    request<{ job_id: string; rev: number; output: string }>(
      `/api/v1/projects/${id}/preview`,
      {
        method: "POST",
        body: JSON.stringify({ from_ms: fromMs, to_ms: toMs, ...(rev !== undefined && { rev }) }),
      },
    ),
};

export interface EngineScene {
  id: string;
  narration?: string;
  visual_intent?: string;
  visual?: {kind: string; source?: {url?: string; title?: string; channel?: string}; path: string};
  alternatives?: {title?: string; url?: string}[];
}

export interface EngineLink {
  source: Record<string, string>;
  manifest: {warnings: string[]; scenes: EngineScene[]; total_ms: number};
  scenes: Record<string, {source_scene_id: string; clip_id: string}>;
  requests: {id: string; state: string; scene_id: string; note: string}[];
}

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
  const origin = API_BASE || window.location.origin;
  const url = origin.replace(/^http/, "ws") + "/ws";
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
