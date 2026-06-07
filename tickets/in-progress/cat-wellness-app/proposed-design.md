# Proposed Design

Status: Current

## Product Shape

The app is a browser-first MVP with three primary tabs:

1. Live Status
   - Camera/microphone preview.
   - Analyze-now action.
   - Current cat state card.
   - Recent timeline events.

2. Ask Cat Agent
   - Owner chat input.
   - Assistant answers grounded in current timeline.
   - Suggested owner questions.

3. Health Assistant
   - Daily report summary.
   - Health warning cards.
   - Behavior distribution and evidence timeline.

## Data-Flow Spine

```text
Capture/demo trigger
  -> modelAdapter.analyzeCurrentMoment()
  -> normalized TimelineEvent
  -> app state/localStorage
  -> Live Status current card
  -> Agent context
  -> Health rules/report
```

## Ownership

- `index.html`: static application shell and DOM targets.
- `styles.css`: visual design, layout, responsive behavior, interaction states.
- `src/main.js`: app state, rendering, browser media capture, local demo orchestration.
- `src/modelAdapter.js`: mock-compatible model contract and event generation.
- `src/healthRules.js`: behavior-health signal rules and daily report aggregation.
- `src/chatAgent.js`: grounded timeline assistant with a Gemini-compatible replacement boundary.
- `src/sampleData.js`: sample timeline events and demo scenarios.

## Model Adapter Boundary

`analyzeCurrentMoment({ mode, mediaState, existingEvents })` returns one normalized event. Today it can mock; later it can call the model person's endpoint.

The app should not depend on model internals. It only consumes:

- state,
- intent,
- behaviorLabel,
- soundType,
- confidence,
- riskLevel,
- signals,
- summary,
- suggestion.

## Agent Boundary

`answerOwnerQuestion(question, timeline, report)` returns a conversational answer. Today it is local and deterministic; later it can send the same timeline/report context to Gemini.

The assistant must:

- use timeline evidence,
- explain uncertainty,
- avoid diagnosis,
- suggest monitoring or vet contact only when appropriate.

## Health Rules Boundary

`buildDailyReport(events)` returns:

- overall status,
- counts,
- behavior mix,
- detected health alerts,
- short daily summary.

Rules are deterministic and evidence-based so they remain explainable during a demo.

## Visual Direction

This is an operational pet wellness tool, not a landing page. The first viewport should show the live monitoring interface immediately. The design should be calm, scan-friendly, and polished:

- compact top navigation,
- dark neutral base with warm status accents,
- clear cards only for repeated items and framed tools,
- no medical overclaiming.

## Failure States

- If media permission fails, show a concise permission message and keep demo controls available.
- If the model is unavailable later, keep the app running with sample scenarios.
- If timeline is empty, show empty states and suggested demo actions.
- If the owner asks a question before any events exist, the agent should explain that it needs observations and offer sample questions/actions.
- If the health report has no events, it should show a neutral baseline-building state instead of a warning.
