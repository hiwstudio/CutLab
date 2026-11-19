import { Editor } from "@/components/Editor";

export default async function EditorPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const base = process.env.CUTLAB_API ?? 'http://127.0.0.1:8787';
  const [project, edl, assets] = await Promise.all(['', '/edl', '/assets'].map(async suffix => {
    const response = await fetch(`${base}/api/v1/projects/${encodeURIComponent(id)}${suffix}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(`Could not load CutLab project (${response.status})`);
    return response.json();
  }));
  return <Editor projectId={id} initial={{edl, assets, headRev: project.head_rev}} />;
}
