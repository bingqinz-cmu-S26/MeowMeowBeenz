# API/E2E Testing

Status: Pass

## Environment

- Static server: `python3 -m http.server 4173`
- Browser target: `http://localhost:4173`

## Scenarios

1. Initial render
   - Result: Pass.
   - Evidence: app title and Live tab rendered; no console errors.

2. Demo day to Health report
   - Result: Pass.
   - Evidence: Load demo day produced 5 events, overall status `Review`, and alerts for low activity, unusual vocalization, and audio-video mismatch.

3. Active/resting count correctness
   - Result: Pass.
   - Evidence: seed report shows Active `1`, Resting `3`; inactive labels are no longer counted as active.

4. Live analyze without media
   - Result: Pass.
   - Evidence: Analyze Now generated a simulated current-state event and kept the app usable without camera permission.

5. Owner agent question
   - Result: Pass.
   - Evidence: asking "Why was she meowing?" returned a timeline-grounded answer referencing repeated meow, confidence, intent, and uncertainty-safe advice.

6. Post-review CSS split
   - Result: Pass.
   - Evidence: page reloaded at `http://localhost:4173/?v=3`; no console errors and no horizontal overflow.

7. Dynamic text escaping
   - Result: Pass.
   - Evidence: chat input `<img src=x onerror=alert(1)> Why meow?` rendered as text; `.chat-message img` count stayed `0`; no console errors.

8. MiniMax agent fallback
   - Result: Pass.
   - Evidence: with `MINIMAX_API_KEY` unset, Agent attempted `/api/agent`, showed `Agent · local`, and returned a local grounded answer plus the fallback reason.

9. MiniMax proxy syntax
   - Result: Pass.
   - Evidence: `PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile server.py`.

10. Live MiniMax response cleanup
   - Result: Pass.
   - Evidence: with user-provided key loaded into process env, Agent returned `Agent · minimax`; DOM snapshot contained `NO_THINK` and no console errors.

11. LiveKit CLI
   - Result: Pass.
   - Evidence: `lk --version` returned `lk version 2.16.4`.

12. LiveKit token generation
   - Result: Pass.
   - Evidence: with dummy `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`, `create_livekit_token()` returned configured `true` and a three-part JWT.

## Residual Risk

- Real LiveKit, Gemini, AWS, and model endpoint integration are represented by replacement boundaries and mock adapters, not live credentials.
- Real MiniMax is connected in the current local server process. Future restarts require `MINIMAX_API_KEY`.
- LiveKit frontend/runtime connection requires real LiveKit Cloud credentials at server startup.
