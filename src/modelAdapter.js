export async function analyzeUploadedClip(file) {
  const form = new FormData();
  form.append("clip", file);

  const response = await fetch("/api/analyze-clip", {
    method: "POST",
    body: form
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "Clip analysis failed.");
  }

  const rawEvent = data.event || data.analysis || {};
  const event = {
    ...rawEvent,
    source: rawEvent.source || "uploaded_clip_analysis",
    summary: rawEvent.summary || data.text || "The model analyzed this clip."
  };

  return {
    provider: data.provider || "cat-model",
    text: data.text || event.summary,
    file: data.file || { name: file.name, type: file.type, size: file.size },
    event
  };
}

export async function analyzeCurrentMoment({ mediaEnabled, timeline }) {
  if (mediaEnabled) {
    const recentWatchEvents = timeline.filter((event) => event.riskLevel !== "normal").length;
    if (recentWatchEvents >= 3) {
      return requestScenarioEvent("conflict");
    }
  }

  return requestScenarioEvent("live");
}

async function requestScenarioEvent(type) {
  await wait(450);

  const response = await fetch(`/api/events/scenario/${type}`, {
    method: "POST"
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok || !data.event) {
    throw new Error(data.error || "Scenario event unavailable.");
  }

  return {
    ...data.event,
    source: data.event.source || type
  };
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
