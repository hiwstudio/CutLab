"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, connectWs, WsEvent } from "./api";
import type { AssetRow, EDL, Job, Op, RevisionRow, Understanding } from "./types";

export interface EditorState {
  projectId: string;
  edl: EDL | null;
  headRev: number;
  viewRev: number | null; // non-null = read-only view of an old revision
  assets: AssetRow[];
  revisions: RevisionRow[];
  proposals: RevisionRow[];
  jobs: Record<string, Job>;
  selection: string | null; // clip id
  playheadMs: number;
  pxPerSec: number;
  error: string | null;
  busy: boolean;
  serverDown: boolean;
}

export interface EditorApi extends EditorState {
  applyOps: (ops: Op[]) => Promise<boolean>;
  undo: () => Promise<void>;
  redo: () => Promise<void>;
  select: (clipId: string | null) => void;
  setPlayhead: (ms: number) => void;
  setZoom: (pxPerSec: number) => void;
  viewRevision: (rev: number | null) => void;
  refreshAssets: () => Promise<void>;
  upload: (file: File) => Promise<void>;
  uploadAndWait: (file: File) => Promise<AssetRow | null>;
  startRender: () => Promise<string | null>;
  analyze: (assetId: string, language?: string) => Promise<string | null>;
  cutout: (assetId: string) => Promise<string | null>;
  extractAudio: (assetId: string) => Promise<string | null>;
  textToSound: (text: string) => Promise<string | null>;
  importSound: (soundId: string) => Promise<AssetRow | null>;
  loadUnderstanding: (assetId: string) => Promise<Understanding | null>;
  proposeOps: (ops: Op[]) => Promise<boolean>;
  acceptProposal: (rev: number) => Promise<void>;
  rejectProposal: (rev: number) => Promise<void>;
  refresh: () => Promise<void>;
  clearError: () => void;
}

export type InitialEditor = { edl: EDL; headRev: number; assets: AssetRow[] };

export function useEditor(projectId: string, initial?: InitialEditor): EditorApi {
  const [edl, setEdl] = useState<EDL | null>(initial?.edl ?? null);
  const [headRev, setHeadRev] = useState(initial?.headRev ?? 0);
  const [viewRev, setViewRev] = useState<number | null>(null);
  const [assets, setAssets] = useState<AssetRow[]>(initial?.assets ?? []);
  const [revisions, setRevisions] = useState<RevisionRow[]>([]);
  const [proposals, setProposals] = useState<RevisionRow[]>([]);
  const [jobs, setJobs] = useState<Record<string, Job>>({});
  const [selection, setSelection] = useState<string | null>(null);
  const [playheadMs, setPlayheadMs] = useState(0);
  const [pxPerSec, setPxPerSec] = useState(80);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [serverDown, setServerDown] = useState(false);
  const headRevRef = useRef(initial?.headRev ?? 0);
  const viewRevRef = useRef<number | null>(null);
  const mutationRef = useRef(false);

  // fetch() throws TypeError when the server is unreachable.
  const isNetworkError = (e: unknown) =>
    e instanceof TypeError || (e instanceof Error && /fetch/i.test(e.message));

  const refreshAll = useCallback(async () => {
    // Timeline data is essential. Do not hide the entire edit when a secondary
    // history/proposal request is slow or unavailable.
    const [project, freshEdl, freshAssets] = await Promise.all([
      api.getProject(projectId),
      api.getEdl(projectId),
      api.listAssets(projectId),
    ]);
    headRevRef.current = project.head_rev;
    setHeadRev(project.head_rev);
    if (viewRevRef.current === null) setEdl(freshEdl);
    setAssets(freshAssets);
    api.revisions(projectId).then(setRevisions).catch(() => undefined);
    api.proposals(projectId).then(setProposals).catch(() => undefined);
    setServerDown(false);
  }, [projectId]);

  useEffect(() => {
    Promise.resolve().then(refreshAll).catch((e) => {
      if (isNetworkError(e)) setServerDown(true);
      else setError(String(e));
    });
  }, [refreshAll]);

  // While offline, probe every 3s and recover automatically.
  useEffect(() => {
    if (!serverDown) return;
    const t = setInterval(() => {
      refreshAll().catch(() => undefined);
    }, 3000);
    return () => clearInterval(t);
  }, [serverDown, refreshAll]);

  // WS: job progress + external revisions (e.g. ingest registering assets).
  useEffect(() => {
    return connectWs(projectId, (event: WsEvent) => {
      if (event.type === "job") {
        setJobs((prev) => ({ ...prev, [event.job.id]: event.job }));
        if (event.job.state === "done" || event.job.state === "failed") {
          refreshAll().catch(() => undefined);
        }
      } else if (event.type === "revision") {
        // A new proposal, an accept/reject, or an external commit — refresh.
        if (event.state === "proposed" || event.state === "rejected") {
          refreshAll().catch(() => undefined);
        } else if (event.state === "committed" && event.rev !== headRevRef.current) {
          refreshAll().catch(() => undefined);
        }
      }
    });
  }, [projectId, refreshAll]);

  const applyOps = useCallback(
    async (ops: Op[]): Promise<boolean> => {
      if (viewRevRef.current !== null || mutationRef.current) return false; // read-only while viewing history
      mutationRef.current = true;
      setBusy(true);
      try {
        const result = await api.apply(projectId, headRevRef.current, ops);
        setEdl(result.edl);
        headRevRef.current = result.rev;
        setHeadRev(result.rev);
        api.revisions(projectId).then(setRevisions).catch(() => undefined);
        return true;
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) {
          setError("Timeline changed elsewhere — reloaded latest state.");
          await refreshAll().catch(() => undefined);
        } else if (e instanceof ApiError) {
          setError(
            e.issues.length ? `${e.issues[0].code}: ${e.issues[0].message}` : e.message,
          );
        } else if (isNetworkError(e)) {
          setServerDown(true);
        } else {
          setError(String(e));
        }
        return false;
      } finally {
        mutationRef.current = false;
        setBusy(false);
      }
    },
    [projectId, refreshAll],
  );

  const undo = useCallback(async () => {
    if (viewRevRef.current !== null || mutationRef.current) return;
    try {
      await api.undo(projectId);
      await refreshAll();
    } catch (e) {
      if (isNetworkError(e)) setServerDown(true);
      else if (!(e instanceof ApiError && e.status === 422)) setError(String(e));
    }
  }, [projectId, refreshAll]);

  const redo = useCallback(async () => {
    if (viewRevRef.current !== null || mutationRef.current) return;
    try {
      await api.redo(projectId);
      await refreshAll();
    } catch (e) {
      if (isNetworkError(e)) setServerDown(true);
      else if (!(e instanceof ApiError && e.status === 422)) setError(String(e));
    }
  }, [projectId, refreshAll]);

  const viewRevision = useCallback(
    async (rev: number | null) => {
      viewRevRef.current = rev;
      setViewRev(rev);
      if (rev === null) {
        await refreshAll().catch(() => undefined);
      } else {
        const snapshot = await api.getEdl(projectId, rev);
        if (viewRevRef.current === rev) setEdl(snapshot);
      }
    },
    [projectId, refreshAll],
  );

  const refreshAssets = useCallback(async () => {
    setAssets(await api.listAssets(projectId));
  }, [projectId]);

  const upload = useCallback(
    async (file: File) => {
      try {
        await api.uploadAsset(projectId, file);
        await refreshAssets();
      } catch (e) {
        if (isNetworkError(e)) setServerDown(true);
        else setError(String(e));
      }
    },
    [projectId, refreshAssets],
  );

  const startRender = useCallback(async (): Promise<string | null> => {
    try {
      const r = await api.render(projectId, viewRevRef.current ?? undefined);
      return r.job_id;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      return null;
    }
  }, [projectId]);

  const analyze = useCallback(
    async (assetId: string, language?: string): Promise<string | null> => {
      try {
        const r = await api.analyzeAsset(projectId, assetId, language);
        return r.job_id;
      } catch (e) {
        if (isNetworkError(e)) setServerDown(true);
        else setError(e instanceof ApiError ? e.message : String(e));
        return null;
      }
    },
    [projectId],
  );

  const uploadAndWait = useCallback(async (file: File): Promise<AssetRow | null> => {
    try {
      const result = await api.uploadAsset(projectId, file);
      const deadline = Date.now() + 120_000;
      while (Date.now() < deadline) {
        const job = await api.getJob(result.job_id);
        setJobs(prev => ({ ...prev, [job.id]: job }));
        if (job.state === "failed" || job.state === "cancelled") {
          throw new Error(job.error || "Media ingest failed.");
        }
        if (job.state === "done") {
          const fresh = await api.listAssets(projectId);
          setAssets(fresh);
          await refreshAll();
          return fresh.find(asset => asset.asset_id === result.asset_id) ?? null;
        }
        await new Promise(resolve => window.setTimeout(resolve, 250));
      }
      throw new Error("Media ingest timed out.");
    } catch (e) {
      if (isNetworkError(e)) setServerDown(true);
      else setError(e instanceof ApiError ? e.message : String(e));
      return null;
    }
  }, [projectId, refreshAll]);

  const cutout = useCallback(async (assetId: string): Promise<string | null> => {
    try {
      const result = await api.cutoutAsset(projectId, assetId);
      return result.job_id;
    } catch (e) {
      if (isNetworkError(e)) setServerDown(true);
      else setError(e instanceof ApiError ? e.message : String(e));
      return null;
    }
  }, [projectId]);

  const extractAudio = useCallback(async (assetId: string): Promise<string | null> => {
    try {
      const result = await api.extractAudio(projectId, assetId);
      return result.job_id;
    } catch (e) {
      if (isNetworkError(e)) setServerDown(true);
      else setError(e instanceof ApiError ? e.message : String(e));
      return null;
    }
  }, [projectId]);

  const textToSound = useCallback(async (text: string): Promise<string | null> => {
    try {
      const result = await api.textToSound(projectId, text);
      return result.job_id;
    } catch (e) {
      if (isNetworkError(e)) setServerDown(true);
      else setError(e instanceof ApiError ? e.message : String(e));
      return null;
    }
  }, [projectId]);

  const importSound = useCallback(async (soundId: string): Promise<AssetRow | null> => {
    try {
      const result = await api.importSound(projectId, soundId);
      const deadline = Date.now() + 120_000;
      while (Date.now() < deadline) {
        const job = await api.getJob(result.job_id);
        setJobs(prev => ({ ...prev, [job.id]: job }));
        if (job.state === "failed" || job.state === "cancelled") {
          throw new Error(job.error || "Sound ingest failed.");
        }
        if (job.state === "done") {
          const fresh = await api.listAssets(projectId);
          setAssets(fresh);
          await refreshAll();
          return fresh.find(asset => asset.asset_id === result.asset_id) ?? null;
        }
        await new Promise(resolve => window.setTimeout(resolve, 250));
      }
      throw new Error("Sound ingest timed out.");
    } catch (e) {
      if (isNetworkError(e)) setServerDown(true);
      else setError(e instanceof ApiError ? e.message : String(e));
      return null;
    }
  }, [projectId, refreshAll]);

  const loadUnderstanding = useCallback(
    async (assetId: string): Promise<Understanding | null> => {
      try {
        return await api.getUnderstanding(projectId, assetId);
      } catch {
        return null;
      }
    },
    [projectId],
  );

  const proposeOps = useCallback(
    async (ops: Op[]): Promise<boolean> => {
      if (viewRevRef.current !== null) return false;
      try {
        await api.apply(projectId, headRevRef.current, ops, "propose");
        await refreshAll();
        return true;
      } catch (e) {
        if (isNetworkError(e)) setServerDown(true);
        else if (e instanceof ApiError) {
          setError(e.issues.length ? `${e.issues[0].code}: ${e.issues[0].message}` : e.message);
        } else setError(String(e));
        return false;
      }
    },
    [projectId, refreshAll],
  );

  const acceptProposal = useCallback(
    async (rev: number) => {
      if (viewRevRef.current !== null) return;
      try {
        await api.acceptProposal(projectId, rev);
        await refreshAll();
      } catch (e) {
        if (isNetworkError(e)) setServerDown(true);
        else if (e instanceof ApiError && e.status === 409) {
          setError("Proposal is stale (the timeline changed) — reload and re-propose.");
          await refreshAll().catch(() => undefined);
        } else setError(e instanceof ApiError ? e.message : String(e));
      }
    },
    [projectId, refreshAll],
  );

  const rejectProposal = useCallback(
    async (rev: number) => {
      if (viewRevRef.current !== null) return;
      try {
        await api.rejectProposal(projectId, rev);
        await refreshAll();
      } catch (e) {
        if (isNetworkError(e)) setServerDown(true);
        else setError(e instanceof ApiError ? e.message : String(e));
      }
    },
    [projectId, refreshAll],
  );

  return {
    projectId,
    edl,
    headRev,
    viewRev,
    assets,
    revisions,
    proposals,
    jobs,
    selection,
    playheadMs,
    pxPerSec,
    error,
    busy,
    serverDown,
    applyOps,
    undo,
    redo,
    select: setSelection,
    setPlayhead: (ms: number) => setPlayheadMs(Math.max(0, Math.round(ms))),
    setZoom: (v: number) => setPxPerSec(Math.min(400, Math.max(0.01, v))),
    viewRevision,
    refreshAssets,
    upload,
    uploadAndWait,
    startRender,
    analyze,
    cutout,
    extractAudio,
    textToSound,
    importSound,
    loadUnderstanding,
    proposeOps,
    acceptProposal,
    rejectProposal,
    refresh: () => refreshAll().catch(() => undefined),
    clearError: () => setError(null),
  };
}
