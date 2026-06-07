import { answerOwnerQuestion } from '@/lib/chatAgent';
import { buildRangeReport } from '@/lib/healthRules';
import { createScenarioEvent, createSeedEvents } from '@/lib/sampleData';
import { CAT_PROFILES } from '@/lib/cats';
import type { AuthUser, CatProfile, HealthReport, ReportRange, TimelineEvent } from '@/types';

const API_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

function parseError(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') return fallback;
  const detail = (data as { detail?: unknown; error?: unknown }).detail ?? (data as { error?: unknown }).error;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0] && typeof detail[0] === 'object' && 'msg' in detail[0]) {
    return String((detail[0] as { msg: string }).msg);
  }
  return fallback;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...(options?.headers || {}),
    },
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(parseError(data, 'Request failed'));
  }
  return data as T;
}

export async function login(username: string, password: string) {
  return request<{ user: AuthUser; token: string }>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export async function register(username: string, password: string, displayName?: string) {
  return request<{ user: AuthUser; token: string }>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      username,
      password,
      display_name: displayName,
    }),
  });
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  const data = await request<{ user: AuthUser }>('/api/auth/me');
  return data.user;
}

export async function checkHealth(): Promise<boolean> {
  try {
    await request('/api/health');
    return true;
  } catch {
    return false;
  }
}

export async function fetchCats(): Promise<CatProfile[]> {
  try {
    const data = await request<{ cats: CatProfile[] }>('/api/cats');
    return data.cats;
  } catch {
    return CAT_PROFILES;
  }
}

export async function fetchEvents(): Promise<TimelineEvent[]> {
  try {
    const data = await request<{ events: TimelineEvent[] }>('/api/events');
    return data.events;
  } catch {
    return createSeedEvents();
  }
}

export async function seedEvents(): Promise<TimelineEvent[]> {
  try {
    const data = await request<{ events: TimelineEvent[] }>('/api/events/seed', { method: 'POST' });
    return data.events;
  } catch {
    return createSeedEvents();
  }
}

export async function addScenarioEvent(scenarioType: string): Promise<TimelineEvent> {
  try {
    const data = await request<{ event: TimelineEvent }>(`/api/events/scenario/${scenarioType}`, { method: 'POST' });
    return data.event;
  } catch {
    return createScenarioEvent(scenarioType);
  }
}

export async function clearEvents(): Promise<void> {
  try {
    await request('/api/events', { method: 'DELETE' });
  } catch {
    // local-only mode
  }
}

export async function fetchReport(range: ReportRange): Promise<HealthReport> {
  try {
    const data = await request<{ report: HealthReport }>(`/api/report?range=${range}`);
    return data.report;
  } catch {
    return buildRangeReport(createSeedEvents(), range);
  }
}

export async function askAgent(question: string, timeline: TimelineEvent[], report: HealthReport) {
  try {
    const data = await request<{ answer: string; provider: 'local' | 'minimax' }>('/api/agent', {
      method: 'POST',
      body: JSON.stringify({ question, timeline, report }),
    });
    return { provider: data.provider, text: data.answer };
  } catch {
    return {
      provider: 'local' as const,
      text: `${answerOwnerQuestion(question, timeline, report)}\n\nMiniMax is taking too long, so Beenz used the local timeline summary.`,
    };
  }
}
