import type { RiskLevel } from '@/constants/Theme';

export type ReportRange = 'day' | 'week' | 'month';
export type ActivityFilter = 'all' | 'activity' | 'eating' | 'litter' | 'vocal' | 'warnings';

export type CatStatus = 'nice' | 'perfect' | 'watch' | 'alert' | 'review';

export type CatProfile = {
  id: string;
  ownerId?: string;
  ownerUsername?: string;
  name: string;
  initials: string;
  age: string;
  birthDate: string;
  device?: string | null;
  accent: string;
  status?: CatStatus;
  room?: string;
  routine?: string;
  eventCount?: number;
  alertCount?: number;
};

export type CreateCatInput = {
  name: string;
  birthDate: string;
  device?: string;
};

export type UpdateCatInput = CreateCatInput;

export type TimelineEvent = {
  id: string;
  time: string;
  source: string;
  state: string;
  intent: string;
  behaviorLabel: string;
  soundType: string;
  confidence: number;
  riskLevel: RiskLevel;
  signals: string[];
  summary: string;
  suggestion: string;
};

export type Alert = {
  signal: string;
  level: RiskLevel;
  title: string;
  evidence: string[];
  suggestion: string;
  confidence: number;
};

export type EventCounts = {
  eating: number;
  litter: number;
  active: number;
  resting: number;
  grooming: number;
  vocal: number;
  review: number;
};

export type HealthReport = {
  dateLabel: string;
  range: ReportRange;
  totalEvents: number;
  counts: EventCounts;
  alerts: Alert[];
  overall: RiskLevel;
  summary: string;
};

export type ChatMessage = {
  role: 'owner' | 'assistant';
  text: string;
  provider?: 'local' | 'minimax';
};

export type ScenarioType = {
  id: string;
  label: string;
};

export type AuthUser = {
  id: string;
  username: string;
  displayName: string;
  createdAt?: string;
};
