import { createScenarioEvent, normalizeEvent } from "./sampleData.js";

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

  const event = normalizeEvent({
    ...(data.event || data.analysis || {}),
    source: "uploaded_clip_analysis",
    summary: data.event?.summary || data.analysis?.summary || data.text || "The model analyzed this clip."
  });

  return {
    provider: data.provider || "cat-model",
    text: data.text || event.summary,
    file: data.file || { name: file.name, type: file.type, size: file.size },
    event
  };
}

export async function analyzeCurrentMoment({ mediaEnabled, timeline }) {
  await wait(450);

  if (!mediaEnabled) {
    const fallback = createScenarioEvent("live");
    return {
      ...fallback,
      source: "demo_without_media",
      summary: "Demo analysis used a simulated audio/video window because media preview is not active."
    };
  }

  const recentWatchEvents = timeline.filter((event) => event.riskLevel !== "normal").length;
  if (recentWatchEvents >= 3) {
    return createScenarioEvent("conflict");
  }

  return createScenarioEvent("live");
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
