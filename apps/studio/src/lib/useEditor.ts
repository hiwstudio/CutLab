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
  startRender: () => Promise<string | null>;
  analyze: (assetId: string) => Promise<string | null>;
  loadUnderstanding: (assetId: string) => Promise<Understanding | null>;
  proposeOps: (ops: Op[]) => Promise<boolean>;
  acceptProposal: (rev: number) => Promise<void>;
  rejectProposal: (rev: number) => Promise<void>;
  refresh: () => Promise<void>;
  clearError: () => void;
}

export function useEditor(projectId: string): EditorApi {
  const [edl, setEdl] = useState<EDL | null>(null);
  const [headRev, setHeadRev] = useState(0);
  const [viewRev, setViewRev] = useState<number | null>(null);
  const [assets, setAssets] = useState<AssetRow[]>([]);
  const [revisions, setRevisions] = useState<RevisionRow[]>([]);
  const [proposals, setProposals] = useState<RevisionRow[]>([]);
  const [jobs, setJobs] = useState<Record<string, Job>>({});
  const [selection, setSelection] = useState<string | null>(null);
  const [playheadMs, setPlayheadMs] = useState(0);
  const [pxPerSec, setPxPerSec] = useState(80);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [serverDown, setServerDown] = useState(false);
  const headRevRef = useRef(0);
  headRevRef.current = headRev;

  // fetch() throws TypeError when the server is unreachable.
  const isNetworkError = (e: unknown) =>
    e instanceof TypeError || (e instanceof Error && /fetch/i.test(e.message));

  const refreshAll = useCallback(async () => {
    const [project, freshEdl, freshAssets, revs, props] = await Promise.all([
      api.getProject(projectId),
      api.getEdl(projectId),
      api.listAssets(projectId),
      api.revisions(projectId),
      api.proposals(projectId),
    ]);
    setHeadRev(project.head_rev);
    setEdl(freshEdl);
    setAssets(freshAssets);
    setRevisions(revs);
    setProposals(props);
    setServerDown(false);
  }, [projectId]);

  useEffect(() => {
    refreshAll().catch((e) => {
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
      if (viewRev !== null) return false; // read-only while viewing history
      setBusy(true);
      try {
        const result = await api.apply(projectId, headRevRef.current, ops);
        setEdl(result.edl);
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
        setBusy(false);
      }
    },
    [projectId, refreshAll, viewRev],
  );

  const undo = useCallback(async () => {
    try {
      await api.undo(projectId);
      await refreshAll();
    } catch (e) {
      if (isNetworkError(e)) setServerDown(true);
      else if (!(e instanceof ApiError && e.status === 422)) setError(String(e));
    }
  }, [projectId, refreshAll]);

  const redo = useCallback(async () => {
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
      setViewRev(rev);
      if (rev === null) {
        await refreshAll().catch(() => undefined);
      } else {
        const snapshot = await api.getEdl(projectId, rev);
        setEdl(snapshot);
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
      const r = await api.render(projectId);
      return r.job_id;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      return null;
    }
  }, [projectId]);

  const analyze = useCallback(
    async (assetId: string): Promise<string | null> => {
      try {
        const r = await api.analyzeAsset(projectId, assetId);
        return r.job_id;
      } catch (e) {
        if (isNetworkError(e)) setServerDown(true);
        else setError(e instanceof ApiError ? e.message : String(e));
        return null;
      }
    },
    [projectId],
  );

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
    setZoom: (v: number) => setPxPerSec(Math.min(400, Math.max(10, v))),
    viewRevision,
    refreshAssets,
    upload,
    startRender,
    analyze,
    loadUnderstanding,
    proposeOps,
    acceptProposal,
    rejectProposal,
    refresh: () => refreshAll().catch(() => undefined),
    clearError: () => setError(null),
  };
}
