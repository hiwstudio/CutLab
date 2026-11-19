/**
 * Remotion root (architecture §6). Registers the single HIW composition.
 *
 * The manifest arrives as inputProps. calculateMetadata re-validates + normalizes it
 * (so studio-edited or raw props are safe) and derives dimensions / fps / duration
 * from the manifest, and resolves a default (silent) audio plan when none is given.
 */
import React from "react";
import { Composition } from "remotion";
import { ManifestSchema } from "../engine/manifest/schema";
import { normalizeManifest } from "../engine/manifest/normalizeManifest";
import { metadataFromManifest } from "../engine/timeline/buildTimeline";
import { buildAudioPlan } from "../engine/audio/audioUtils";
import { HIWComposition } from "./HIWComposition";
import { Thumbnail } from "./Thumbnail";
import { ChannelAvatar, ChannelBanner, ChannelLogo, SubscribeWatermark } from "./ChannelArt";
import { DEFAULT_MANIFEST } from "./defaultManifest";
import { assertRegistryComplete } from "./assetRegistry";
import { AuditionLongform, AuditionThumbnail } from "./AuditionLongform";
import { AuditionLongformV3 } from "./AuditionLongformV3";
import { AuditionCleanLongform } from "./clean/AuditionCleanLongform";
import { AUDITION_SHOTLIST } from "./auditionData";
import { AUDITION_SHOTLIST_V3 } from "./auditionDataV3";
import { AUDITION_CLEAN_SHOTLIST } from "./clean/auditionCleanData";

// Fail fast if the catalog and component registry have drifted apart.
assertRegistryComplete();

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="HIWVideo"
        component={HIWComposition}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{ manifest: DEFAULT_MANIFEST }}
        calculateMetadata={({ props }) => {
          const manifest = normalizeManifest(ManifestSchema.parse(props.manifest));
          const meta = metadataFromManifest(manifest);
          const audioPlan = props.audioPlan ?? buildAudioPlan(manifest, { fileExists: () => false });
          return {
            ...meta,
            props: { ...props, manifest, audioPlan },
          };
        }}
      />

      <Composition
        id="HIWThumbnail"
        component={Thumbnail}
        durationInFrames={1}
        fps={30}
        width={1280}
        height={720}
        defaultProps={{ manifest: DEFAULT_MANIFEST, sceneIndex: 0 }}
        calculateMetadata={({ props }) => {
          const manifest = normalizeManifest(ManifestSchema.parse(props.manifest));
          return { props: { ...props, manifest } };
        }}
      />

      <Composition
        id="HIWThumbnailVertical"
        component={Thumbnail}
        durationInFrames={1}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{ manifest: DEFAULT_MANIFEST, sceneIndex: 0 }}
        calculateMetadata={({ props }) => {
          const manifest = normalizeManifest(ManifestSchema.parse(props.manifest));
          return { props: { ...props, manifest } };
        }}
      />

      {/* Channel art (YouTube profile picture + banner) — static stills. */}
      <Composition
        id="ChannelAvatar"
        component={ChannelAvatar}
        durationInFrames={1}
        fps={30}
        width={800}
        height={800}
        defaultProps={{ panic: false }}
      />

      <Composition
        id="ChannelBanner"
        component={ChannelBanner}
        durationInFrames={1}
        fps={30}
        width={2560}
        height={1440}
      />

      {/* Transparent mascot logo / video watermark — render as PNG to keep alpha. */}
      <Composition
        id="ChannelLogo"
        component={ChannelLogo}
        durationInFrames={1}
        fps={30}
        width={1024}
        height={1024}
        defaultProps={{ halo: false }}
      />

      {/* 150x150 "Subscribe" branding watermark (rendered at scale, exported as GIF). */}
      <Composition
        id="SubscribeWatermark"
        component={SubscribeWatermark}
        durationInFrames={1}
        fps={30}
        width={150}
        height={150}
      />

      {/* E1 Longform Pilot: Why Talking to Someone You Like Feels Like an Audition (591.96s / 17,759f @ 30fps) */}
      <Composition
        id="AuditionLongform"
        component={AuditionLongform}
        durationInFrames={AUDITION_SHOTLIST.totalFrames}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* E1 Longform Pilot v3: 48-beat dynamic motion, animated video clips & spatial consistency */}
      <Composition
        id="AuditionLongformV3"
        component={AuditionLongformV3}
        durationInFrames={AUDITION_SHOTLIST_V3.totalFrames}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* E2 Longform Pilot: Clean White Classy Edition (Why Talking to Someone You Like Feels Like an Audition) */}
      <Composition
        id="AuditionCleanLongform"
        component={AuditionCleanLongform}
        durationInFrames={AUDITION_CLEAN_SHOTLIST.totalFrames}
        fps={30}
        width={1920}
        height={1080}
      />

      <Composition
        id="AuditionThumbnail"
        component={AuditionThumbnail}
        durationInFrames={1}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
