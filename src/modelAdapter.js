import { createScenarioEvent } from "./sampleData.js";

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
