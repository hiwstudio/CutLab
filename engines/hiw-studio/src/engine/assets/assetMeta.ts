/**
 * Asset metadata (V2 — Pillar 4). Tags + descriptions for every catalog asset, used
 * by the asset library for "reuse before create" search and by `hiw inspect-assets`.
 *
 * Plain data, no React/fs — safe in browser and Node. Keep in sync with
 * catalog.ts (assetLibrary.metaCoverageGaps() / the test suite enforce this).
 */

export type MetaKind =
  | "character"
  | "variant"
  | "background"
  | "motion"
  | "prop"
  | "effect"
  | "camera"
  | "captionStyle"
  | "expression";

export interface AssetRecord {
  kind: MetaKind;
  id: string;
  name: string;
  description: string;
  tags: string[];
}

const A = (kind: MetaKind, id: string, name: string, description: string, tags: string[]): AssetRecord => ({
  kind,
  id,
  name,
  description,
  tags,
});

export const ASSET_META: AssetRecord[] = [
  // Characters
  A("character", "human", "Human", "The everyperson puppet representing all humans.", ["person", "everyperson", "stickman", "puppet", "main", "guy"]),
  A("character", "ancient_brain", "Ancient Brain", "The channel mascot: the outdated survival brain that overreacts to modern life.", ["brain", "mascot", "instinct", "survival", "ancient", "mind", "panic"]),
  A("character", "dog", "Dog", "A friendly sitting dog: floppy ears, wagging tail, lolling tongue and a collar. Humanity's best friend.", ["dog", "puppy", "pet", "animal", "companion", "best friend", "wag", "tail", "loyal", "domesticated", "good boy"]),

  // Human variants
  A("variant", "default", "Default", "Plain human look.", ["plain", "basic", "everyperson", "default"]),
  A("variant", "caveman", "Caveman", "Prehistoric human with fur, bare arms, messy hair and a beard.", ["caveman", "prehistoric", "cave", "survival", "fur", "beard", "ancient", "tribe", "stone age"]),
  A("variant", "modern", "Modern", "Casual modern human in a t-shirt.", ["modern", "casual", "everyday", "tshirt", "contemporary"]),
  A("variant", "office", "Office", "Office worker with collar and tie.", ["office", "work", "corporate", "shirt", "tie", "job", "professional", "9 to 5"]),
  A("variant", "tired", "Tired", "Worn-out, drained human.", ["tired", "exhausted", "drained", "sleepy", "burnout", "fatigue"]),
  A("variant", "excited", "Excited", "Energetic, thrilled human.", ["excited", "energetic", "thrilled", "hyped", "happy"]),
  A("variant", "waiter", "Waiter", "Restaurant server: white shirt, dark apron and a black bow tie.", ["waiter", "server", "restaurant", "diner", "cafe", "service", "apron", "bow tie", "host", "staff"]),

  // Backgrounds
  A("background", "cave", "Cave", "Stylized prehistoric cave with a small fire.", ["cave", "prehistoric", "survival", "fire", "ancient", "dark", "stone age"]),
  A("background", "living_room", "Living Room", "Cozy home interior with couch, lamp and window.", ["living room", "home", "couch", "relax", "indoor", "domestic", "house"]),
  A("background", "office", "Office", "Workplace with desk, monitor, plant and a city window.", ["office", "work", "desk", "corporate", "window", "city", "job"]),
  A("background", "abstract_explainer", "Abstract Explainer", "Clean branded gradient backdrop for explanations.", ["abstract", "explainer", "neutral", "branded", "gradient", "backdrop", "concept", "purple"]),
  A("background", "street", "Street", "Stylized city street with buildings and road.", ["street", "city", "outdoor", "urban", "sidewalk", "walking", "road"]),
  A("background", "park", "Park", "Sunny outdoor park with trees, bushes, a path, a bench and a sign. Great for walks and pets.", ["park", "outdoor", "nature", "trees", "grass", "walk", "dog walk", "bench", "path", "garden", "sunny"]),
  A("background", "diner", "Diner", "Warm restaurant interior: evening window, hanging pendant lamps, a booth bench and a bistro table. For dining, service and small-talk scenes.", ["diner", "restaurant", "cafe", "eatery", "table", "booth", "waiter", "food", "dining", "meal", "indoor", "date"]),

  // Motions
  A("motion", "idle", "Idle", "Standing still with gentle breathing.", ["idle", "still", "stand", "neutral", "breathe", "default"]),
  A("motion", "walk", "Walk", "Walking in place with swinging arms.", ["walk", "walking", "move", "run", "travel", "step", "go"]),
  A("motion", "panic", "Panic", "Frantic flailing and shaking.", ["panic", "freak out", "scared", "anxious", "alarm", "stress", "flail", "emergency", "freak"]),
  A("motion", "scrollPhone", "Scroll Phone", "Hunched-over phone scrolling.", ["scroll", "phone", "scrolling", "doom scroll", "addiction", "swipe", "social media"]),
  A("motion", "point", "Point", "Leaning to point/indicate.", ["point", "pointing", "indicate", "show", "direct", "emphasis"]),
  A("motion", "shrug", "Shrug", "An 'I don't know' shoulder shrug.", ["shrug", "dont know", "unsure", "confused", "indifferent", "whatever"]),
  A("motion", "facepalm", "Facepalm", "Hand-to-head despair/frustration.", ["facepalm", "frustrated", "disappointed", "embarrassed", "ugh", "regret", "despair"]),
  A("motion", "celebrate", "Celebrate", "Jumping with both arms thrown up.", ["celebrate", "cheer", "happy", "win", "excited", "victory", "yay", "party"]),
  A("motion", "lookAround", "Look Around", "Cautiously scanning left and right.", ["look around", "search", "cautious", "scan", "alert", "watch", "wary"]),
  A("motion", "lightbulbIdea", "Lightbulb Idea", "An 'aha!' realization pop.", ["idea", "aha", "eureka", "realization", "insight", "lightbulb", "think", "solution"]),
  A("motion", "wave", "Wave", "A friendly raised-hand wave hello/goodbye.", ["wave", "hello", "hi", "goodbye", "bye", "greet", "greeting", "hand", "acknowledge", "social"]),

  // Props
  A("prop", "phone", "Phone", "A smartphone (supports glow).", ["phone", "smartphone", "mobile", "tech", "notification", "scroll", "screen", "addiction"]),
  A("prop", "notification_bubble", "Notification Bubble", "A red alert badge (supports glow).", ["notification", "alert", "ping", "badge", "message", "social media", "red dot"]),
  A("prop", "money_stack", "Money Stack", "A stack of cash.", ["money", "cash", "wealth", "rich", "stack", "bills", "finance", "status"]),
  A("prop", "brain", "Brain Icon", "A small standalone brain icon.", ["brain", "mind", "thought", "think", "idea", "mental"]),
  A("prop", "speech_bubble", "Speech Bubble", "A speech/dialog bubble.", ["speech", "talk", "say", "dialog", "comment", "words", "conversation"]),
  A("prop", "club", "Club", "A caveman club.", ["club", "caveman", "weapon", "prehistoric", "bonk", "stone age"]),
  A("prop", "coin", "Coin", "A gold coin (supports glow).", ["coin", "money", "gold", "cash", "wealth", "finance", "reward"]),
  A("prop", "bill", "Bill", "A single banknote.", ["bill", "money", "cash", "dollar", "banknote", "payment", "finance"]),
  A("prop", "laptop", "Laptop", "An open laptop.", ["laptop", "computer", "work", "tech", "email", "office", "typing"]),
  A("prop", "warning_sign", "Warning Sign", "A yellow caution triangle (supports glow).", ["warning", "danger", "alert", "caution", "problem", "risk", "threat", "task"]),
  A("prop", "bone", "Bone", "A classic dog bone.", ["bone", "dog", "treat", "pet", "chew", "reward", "fetch", "good boy"]),
  A("prop", "vending_machine", "Vending Machine", "A front-facing snack machine (glowing selection panel).", ["vending machine", "snack", "machine", "object", "consumerism", "anthropomorphism", "modern", "personify", "thank the machine"]),

  // Effects
  A("effect", "pop", "Pop", "A starburst pop at scene start.", ["pop", "appear", "emphasis", "burst", "reveal", "attention"]),
  A("effect", "sweatDrops", "Sweat Drops", "Anxiety sweat drops.", ["sweat", "nervous", "anxious", "stress", "worried", "panic", "drip"]),
  A("effect", "speedLines", "Speed Lines", "Comic urgency streaks.", ["speed", "fast", "rush", "motion", "urgency", "action", "hurry"]),
  A("effect", "glow", "Glow", "A warm spotlight glow.", ["glow", "shine", "highlight", "tempting", "aura", "light"]),
  A("effect", "alarmFlash", "Alarm Flash", "Pulsing red alert tint.", ["alarm", "alert", "red flash", "emergency", "danger", "warning", "panic"]),
  A("effect", "thoughtBubble", "Thought Bubble", "A drifting thought cloud.", ["thought", "thinking", "daydream", "imagine", "cloud", "ponder"]),
  A("effect", "motionLines", "Motion Lines", "Impact arcs around the subject.", ["motion", "impact", "emphasis", "action", "energy", "movement"]),
  A("effect", "faceDetect", "Face Detect", "A camera-style reticle that scans a centered subject and locks with a MIND DETECTED label.", ["face detect", "reticle", "scan", "detect", "mind", "recognition", "anthropomorphism", "agency", "person", "label", "targeting"]),

  // Cameras
  A("camera", "static", "Static", "No camera movement.", ["static", "still", "fixed", "no movement"]),
  A("camera", "slowZoomIn", "Slow Zoom In", "Gentle push-in for emphasis.", ["zoom in", "push in", "emphasis", "focus", "slow zoom", "intensify"]),
  A("camera", "slowZoomOut", "Slow Zoom Out", "Gentle pull-back/reveal.", ["zoom out", "pull back", "reveal", "wide", "end"]),
  A("camera", "quickZoom", "Quick Zoom", "Snappy punch-in for shock/emphasis.", ["quick zoom", "punch in", "snap", "emphasis", "sudden", "shock"]),
  A("camera", "shake", "Shake", "Camera shake for chaos/impact.", ["shake", "camera shake", "impact", "chaos", "panic", "intense", "earthquake"]),
  A("camera", "panLeft", "Pan Left", "Track/slide to the left.", ["pan left", "slide", "move", "track", "reveal"]),
  A("camera", "panRight", "Pan Right", "Track/slide to the right.", ["pan right", "slide", "move", "track", "reveal"]),

  // Caption styles
  A("captionStyle", "hiw_default", "Default Caption", "Bold white outlined caption.", ["caption", "default", "white", "readable", "standard"]),
  A("captionStyle", "hiw_emphasis", "Emphasis Caption", "Big yellow uppercase punchline caption.", ["caption", "emphasis", "punchline", "yellow", "big", "bold", "highlight"]),
  A("captionStyle", "hiw_quiet", "Quiet Caption", "Smaller, softer aside caption.", ["caption", "quiet", "aside", "small", "subtle"]),

  // Expressions
  A("expression", "neutral", "Neutral", "Calm default face.", ["neutral", "plain", "calm", "default"]),
  A("expression", "happy", "Happy", "Smiling, pleased face.", ["happy", "smile", "joy", "pleased", "glad"]),
  A("expression", "anxious", "Anxious", "Nervous, uneasy face.", ["anxious", "worried", "nervous", "stressed", "uneasy"]),
  A("expression", "shocked", "Shocked", "Wide-eyed, open-mouth surprise.", ["shocked", "surprised", "gasp", "stunned", "wide eyes", "scared"]),
  A("expression", "confused", "Confused", "Puzzled, unsure face.", ["confused", "puzzled", "unsure", "baffled", "what"]),
  A("expression", "angry", "Angry", "Annoyed, upset face.", ["angry", "mad", "annoyed", "frustrated", "upset"]),
  A("expression", "tired", "Tired", "Sleepy, drained face.", ["tired", "sleepy", "exhausted", "drained", "weary"]),
  A("expression", "worried", "Worried", "Concerned face (alias of anxious).", ["worried", "anxious", "concerned", "fearful"]),
  A("expression", "excited", "Excited", "Thrilled, eager face (alias of happy).", ["excited", "thrilled", "energetic", "eager"]),
];
