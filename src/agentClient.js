import { answerOwnerQuestion } from "./chatAgent.js?v=4";

export async function askAgent(question, timeline, report) {
  try {
    const response = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, timeline, report })
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "MiniMax agent is unavailable.");
    }
    return {
      provider: data.provider || "minimax",
      text: data.answer
    };
  } catch (error) {
    return {
      provider: "local",
      text: `${answerOwnerQuestion(question, timeline, report)}\n\nMiniMax is taking too long, so Beenz used the local timeline summary.`
    };
  }
}
