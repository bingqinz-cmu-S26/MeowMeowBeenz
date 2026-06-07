# Hands-free voice mode

Architecture: **MiniMax stays the brain.** A LiveKit Agents worker joins the same room as the
app and runs the realtime loop:

```
mic  ─▶  AssemblyAI STT  ─▶  MiniMax M2 (LLM)  ─▶  MiniMax Speech-02 (TTS)  ─▶  speaker
        (LiveKit Inference)     │
                                └── calls the moss retrieval tool (lookup_cat_activity)
                                    over data/mockData.json to ground every answer
```

MiniMax has no speech-to-text, so STT is borrowed — but it runs through **LiveKit Inference**
(AssemblyAI), billed on your LiveKit key, so there's **no separate STT account**. Everything else
(reasoning, retrieval grounding, and the voice) is MiniMax. LiveKit handles VAD, turn-taking, and
barge-in. Note: Inference requires **LiveKit Cloud** (not self-hosted).

## 1. Backend worker

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt -r requirements-voice.txt
```

Set these in the project-root `.env` (see `.env.example`):

- `MINIMAX_API_KEY`, `MINIMAX_MODEL` (default `M2-her`), `MINIMAX_API_URL`
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (also authenticate Inference STT — no Deepgram key needed)

Run it:

```bash
python voice_agent.py console   # talk in your terminal, no app/room needed — fastest sanity check
python voice_agent.py dev       # joins LiveKit rooms (run alongside the FastAPI server)
python voice_agent.py start     # production worker
```

`console` mode is the quickest way to confirm the MiniMax brain + retrieval tool + TTS work
before wiring up the mobile client.

## 2. Mobile client

The **"Start voice chat" button is on the Agent tab** (`mobile/app/(tabs)/agent.tsx`), backed by
`mobile/lib/useVoiceChat.ts`, which mints a token (`api.fetchLiveKitToken()` → `POST /api/livekit-token`),
joins the LiveKit room, publishes the mic, and plays the agent's spoken replies.

It uses the LiveKit React Native SDK, which pulls in native WebRTC. **This requires a custom dev
build — it does not run in Expo Go**, and the app will not even bundle until the packages are installed:

```bash
cd mobile
npx expo install @livekit/react-native @livekit/react-native-webrtc livekit-client
npx expo prebuild           # generate native projects (reads the app.json mic permissions + webrtc plugin)
npx expo run:ios            # or run:android — a dev build, not Expo Go
```

`package.json`, `app.json` (mic permissions + `@livekit/react-native-webrtc` plugin), the voice hook,
and the Agent-tab button are already wired. Once the worker is running and `LIVEKIT_*` is set, tap
the button and ask out loud — e.g. "what was Mochi doing last night?" — and Beenz answers hands-free.

## Client

The voice UI is the **native SwiftUI app** (`MeowMeowBeenz/`): Chat tab → mic button → voice sheet
(`VoiceView` / `VoiceChatModel`), using the LiveKit Swift SDK. It builds and runs on the iOS 26
simulator. The old Expo `mobile/` client is superseded.

## Status / not yet done

- The worker (`voice_agent.py`) syntax-checks but has **not been run end-to-end** here — it needs
  the `requirements-voice.txt` deps plus live LiveKit Cloud + MiniMax credentials and an audio
  session. Verify with `python voice_agent.py console` first.
- Plugin specifics to confirm against the installed versions: the `inference.STT` model string
  (`assemblyai/universal-streaming`), the `minimax.TTS` model (`speech-02-turbo`) and a `voice` id,
  and the `@function_tool` method signature.
