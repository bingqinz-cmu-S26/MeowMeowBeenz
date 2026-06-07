# Docs Sync

Status: Pass

## Decision

No standalone `docs/` directory exists in this new repository. No external documentation needs synchronization.

## Durable Documentation

The ticket contains the durable task documentation:

- `requirements.md`
- `proposed-design.md`
- `future-state-runtime-call-stack.md`
- `implementation.md`
- `api-e2e-testing.md`
- `code-review.md`

## Run Notes

Start the app without MiniMax:

```sh
python3 server.py
```

Then open:

```text
http://localhost:4173
```

Start the app with MiniMax:

```sh
MINIMAX_API_KEY=your_key_here python3 server.py
```

Optional overrides:

```sh
MINIMAX_MODEL=MiniMax-M3
MINIMAX_API_URL=https://api.minimax.io/v1/chat/completions
```

Start the app with MiniMax and LiveKit:

```sh
MINIMAX_API_KEY=your_minimax_key \
LIVEKIT_URL=wss://your-project.livekit.cloud \
LIVEKIT_API_KEY=your_livekit_api_key \
LIVEKIT_API_SECRET=your_livekit_api_secret \
python3 server.py
```

LiveKit setup notes:

- The LiveKit CLI is installed as `lk`.
- Project URL/API key/API secret come from the LiveKit Cloud project settings.
- The app uses `/api/livekit-token` so the API secret stays server-side.
- The Live Status tab has a `Connect LiveKit` button that joins room `mochi-monitor-demo` and publishes browser audio/video.
