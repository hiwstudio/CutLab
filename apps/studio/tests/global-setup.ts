import { execFileSync, execSync } from "child_process";
import fs from "fs";
import path from "path";
import { SMOKE_DATA } from "../playwright.config";

export const FIXTURE = path.join(SMOKE_DATA, "fixture", "clip5s.mp4");

/** Resolve ffmpeg next to ffprobe (mirrors the server's config.py: another
 * tool may shadow ffmpeg itself on PATH). */
function resolveFfmpeg(): string {
  try {
    const out = execSync("where ffprobe", { encoding: "utf-8" });
    const ffprobe = out.split(/\r?\n/).find((l) => l.trim());
    if (ffprobe) {
      const sibling = path.join(path.dirname(ffprobe.trim()), "ffmpeg.exe");
      if (fs.existsSync(sibling)) return sibling;
    }
  } catch {
    /* fall through */
  }
  return "ffmpeg";
}

export default function globalSetup(): void {
  // The API webServer is already running against SMOKE_DATA (Playwright
  // starts web servers before global setup), so never delete the dir here.
  if (fs.existsSync(FIXTURE)) return;
  fs.mkdirSync(path.dirname(FIXTURE), { recursive: true });
  execFileSync(resolveFfmpeg(), [
    "-hide_banner", "-y",
    "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=5",
    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=5",
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
    "-c:a", "aac", "-b:a", "128k", "-shortest",
    FIXTURE,
  ]);
}
