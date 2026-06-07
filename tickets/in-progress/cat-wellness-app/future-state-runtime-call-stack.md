# Future-State Runtime Call Stack

Status: Current

## Use Case 1: Live Current-State Analysis

1. User opens the app.
2. `main.js` initializes app state from localStorage.
3. User clicks Enable Camera.
4. `main.js:startMediaPreview()` calls `navigator.mediaDevices.getUserMedia()`.
5. Browser stream is attached to the preview video.
6. User clicks Analyze Now.
7. `main.js:handleAnalyze()` calls `modelAdapter.analyzeCurrentMoment()`.
8. `modelAdapter` returns a normalized `TimelineEvent`.
9. `main.js:addEvent()` saves the event in state/localStorage.
10. `main.js:render()` updates the current status card, timeline, health report, and agent context.

## Use Case 2: Demo Sample Event

1. User clicks a scenario button such as Low Activity, Night Yowl, or Litter Concern.
2. `main.js:addScenarioEvent(type)` calls `sampleData.createScenarioEvent(type)`.
3. The event is normalized and added to timeline state.
4. The same render path updates all views.

## Use Case 3: Owner Asks Agent

1. User types a question in Ask Cat Agent.
2. `main.js:handleAsk()` reads the current timeline.
3. `main.js` calls `healthRules.buildDailyReport(events)` to provide report context.
4. `chatAgent.answerOwnerQuestion(question, events, report)` generates grounded text.
5. `main.js` appends owner and assistant messages to chat state.
6. Chat view re-renders with the new answer.

## Use Case 4: Health Report and Warning Signals

1. Any timeline update triggers `renderHealth()`.
2. `healthRules.buildDailyReport(events)` groups today's events.
3. Rules evaluate appetite, litter, activity, grooming/scratching, vocalization, and multimodal conflict signals.
4. The report returns overall level, counts, alerts, and daily narrative.
5. Health view renders alert cards with evidence and suggestions.

## Replacement Path: Real Services

1. LiveKit can replace browser-only capture by publishing/subscribing room tracks.
2. Backend segmenter can call the model service and return the same event contract.
3. Gemini can replace `chatAgent.answerOwnerQuestion()` using the same timeline/report prompt context.
4. AWS/S3/DB can replace localStorage for clips and timeline persistence.
