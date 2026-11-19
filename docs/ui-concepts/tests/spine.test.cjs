// Run: node --test docs/ui-concepts/tests/spine.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function sample() {
  const context = vm.createContext({
    performance, setTimeout, clearTimeout, assert,
    document: { addEventListener() {}, getElementById() { return null; } },
    addCss() {}, ACTS: {}, CONCEPTS: { D: { mount() {}, pros: [] } },
  });
  for (const file of ['core.js', 'spine-enhancements.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  }
  return (code) => vm.runInContext(code, context);
}

test('precise timing preserves source limits, invalidates review and round-trips through history', () => {
  sample()(`
    const c = role('main').clips[0], before = snap();
    assert.equal(S.p.scenes[0].ok, true);
    assert.equal(spineTiming(c.id, {start: 0, in: 1200, dur: 8000}).ok, true);
    assert.equal(c.dur, 8000);
    assert.equal(S.p.scenes[0].ok, false);
    assert.equal(S.past.length, 1);
    undo(); assert.equal(snap(), before);
    redo(); assert.equal(role('main').clips[0].dur, 8000);
    assert.equal(S.p.scenes[0].ok, false);
  `);
});

test('overlap, source overflow, bad values and locked-track edits reject atomically', () => {
  sample()(`
    const c = role('main').clips[0], before = snap();
    for (const values of [
      {start: 1000, in: 1200, dur: 9000},
      {start: 0, in: 6000, dur: 9000},
      {start: -1, in: 1200, dur: 9000},
      {start: 0, in: NaN, dur: 9000},
      {start: 0, in: 1200, dur: 50},
    ]) {
      assert.ok(spineTiming(c.id, values).error);
      assert.equal(snap(), before); assert.equal(S.past.length, 0);
    }
    role('main').locked = true;
    const locked = snap();
    assert.ok(spineTiming(c.id, {start:0, in:1200, dur:8000}).error);
    assert.equal(snap(), locked);
  `);
});

test('mixer preserves relative clip levels, expires pending proposals and undoes once', () => {
  sample()(`
    const t = role('music'); t.clips[1].gain = -18;
    const before = snap();
    S.proposal = {summary:'Pending sample change'};
    assert.equal(spineTrackGain(t.id, -20).ok, true);
    assert.equal(t.clips[0].gain, -20); assert.equal(t.clips[1].gain, -24);
    assert.equal(S.proposal, null); assert.equal(S.past.length, 1);
    undo(); assert.equal(snap(), before);
    redo(); assert.equal(role('music').clips[1].gain, -24);
  `);
});

test('mixer rejects clipping the supported range and locked tracks without partial edits', () => {
  sample()(`
    const t = role('sfx'); t.clips[1].gain = 12;
    const before = snap();
    assert.ok(spineTrackGain(t.id, 0).error);
    assert.equal(snap(), before); assert.equal(S.past.length, 0);
    t.locked = true; const locked = snap();
    assert.ok(spineTrackGain(t.id, -10).error); assert.equal(snap(), locked);
  `);
});
