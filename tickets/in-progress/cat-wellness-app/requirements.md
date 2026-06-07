# Cat Wellness App Requirements

Status: Design-ready

## User Intent

Build a hackathon MVP on top of a cat audio/video intent model inspired by Meow-Omni 1. The app should turn live cat audio/video observations into current-state insight, owner-agent interaction, and behavior-based health warnings.

## Core Features

1. Live status capture
   - Record or stream cat video and audio.
   - Analyze the current moment and return the cat's present state.
   - Show intent/state, confidence, evidence signals, and a safe owner suggestion.
   - Provide a demo fallback that can create realistic sample events without camera permissions.

2. Owner-agent interaction
   - Let the owner chat with an assistant using MiniMax, Gemini, or a compatible backend.
   - Ground answers in the cat context captured from LiveKit-style real-time audio/video records.
   - Use a timeline of model events as the primary context source.
   - Answer common owner questions such as "How is my cat today?", "Why was she meowing?", and "Should I worry?"
   - Include uncertainty and cite timeline evidence in natural language.

3. Health assistant
   - Generate daily reports from the event timeline.
   - Detect behavior-based health warning signals.
   - Avoid diagnosis; frame alerts as behavior changes worth monitoring.
   - Show alert level, evidence, and suggested owner action for each signal.

## Health Warning Signals

- possible_appetite_change: missing usual eating events or vocalization near feeding context without eating.
- possible_litter_box_issue: frequent litter digging without urinating/defecating, or repeated litter visits.
- low_activity_alert: walking/jumping/climbing/play decreases while resting/lying increases.
- possible_skin_ear_discomfort: grooming/scratching/head-shake increases.
- unusual_vocalization: nighttime yowl/caterwauling, high-frequency meow, sudden vocalization increase, or distress-like sound with inactivity.
- multimodal_conflict: audio/video/time-series evidence disagree, such as resting video with distress-like vocalization.

## Safety Constraints

- Do not claim to diagnose disease.
- Explain uncertainty and confidence.
- Recommend monitoring or contacting a veterinarian only when behavior changes persist or combine with concerning evidence.

## Implementation Assumptions

- The model owner will provide an inference endpoint later.
- The MVP can use a local mock model adapter with the same response shape.
- LiveKit integration can be represented by browser camera/microphone capture for the hackathon prototype if credentials are not available.
- MiniMax text interaction should use a local backend proxy so the API key is not exposed in browser JavaScript.
- Gemini text interaction can remain a later replacement option.

## MiniMax Agent Integration

- Default model: `MiniMax-M3`.
- Default endpoint: `https://api.minimax.io/v1/chat/completions`.
- API key source: `MINIMAX_API_KEY` environment variable.
- Optional overrides: `MINIMAX_MODEL`, `MINIMAX_API_URL`.
- The frontend should call local `/api/agent` and fall back to the local timeline assistant if the backend or key is unavailable.

## LiveKit Integration

- LiveKit Docs MCP is installed as `livekit-docs`.
- LiveKit CLI should be installed locally as `lk`.
- The browser should never receive `LIVEKIT_API_SECRET`.
- The backend should expose `/api/livekit-token` to mint short-lived room tokens from:
  - `LIVEKIT_URL`
  - `LIVEKIT_API_KEY`
  - `LIVEKIT_API_SECRET`
- Frontend should connect to room `mochi-monitor-demo`, publish local audio/video, and continue to support local camera preview when LiveKit config is missing.

## Model Event Contract

Each analyzed clip/current-state sample should become a timeline event:

```json
{
  "id": "evt_...",
  "time": "2026-06-06T16:00:00.000Z",
  "source": "live_capture",
  "state": "resting_with_vocalization",
  "intent": "attention_or_discomfort",
  "behaviorLabel": "inactive_lying.resting",
  "soundType": "repeated_meow",
  "confidence": 0.74,
  "riskLevel": "watch",
  "signals": ["unusual_vocalization", "multimodal_conflict"],
  "summary": "The cat is visually inactive but producing repeated vocalization.",
  "suggestion": "Check food, water, and litter box. Continue monitoring if this repeats."
}
```

## Acceptance Criteria

- The app opens to the product experience, not a marketing page.
- User can enable camera/microphone preview when browser permissions allow it.
- User can run an analysis and see a current status card update.
- User can add sample events for demo and see a chronological timeline.
- User can ask the assistant about today's cat behavior and receive a grounded answer based on timeline events.
- User can see a daily health report with counts, overall status, and health warning signals.
- Health alerts use monitoring language and do not diagnose disease.
- App remains usable without external API keys.

## Out of Scope for MVP

- Real veterinary diagnosis.
- Full LiveKit cloud room provisioning.
- Multi-cat identity recognition.
- Long-term account storage.
- Real Gemini API integration unless credentials are later provided.
