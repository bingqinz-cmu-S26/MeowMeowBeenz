import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import * as api from '@/lib/api';
import { CAT_PROFILES } from '@/lib/cats';
import { buildRangeReport } from '@/lib/healthRules';
import { createSeedEvents } from '@/lib/sampleData';
import type { ActivityFilter, CatProfile, ChatMessage, HealthReport, ReportRange, TimelineEvent } from '@/types';

type AppContextValue = {
  cats: CatProfile[];
  events: TimelineEvent[];
  report: HealthReport;
  reportRange: ReportRange;
  activityFilter: ActivityFilter;
  chat: ChatMessage[];
  apiConnected: boolean;
  loading: boolean;
  setReportRange: (range: ReportRange) => void;
  setActivityFilter: (filter: ActivityFilter) => void;
  refresh: () => Promise<void>;
  seedDemo: () => Promise<void>;
  clearTimeline: () => Promise<void>;
  addScenario: (type: string) => Promise<void>;
  analyzeNow: () => Promise<void>;
  sendMessage: (question: string) => Promise<void>;
};

const AppContext = createContext<AppContextValue | null>(null);

const initialChat: ChatMessage[] = [
  {
    role: 'assistant',
    provider: 'local',
    text: 'Ask Beenz about today, any cat\'s routine, nighttime vocalizations, activity, or whether a pattern is worth watching.',
  },
];

export function AppProvider({ children }: { children: ReactNode }) {
  const [cats, setCats] = useState<CatProfile[]>(CAT_PROFILES);
  const [events, setEvents] = useState<TimelineEvent[]>(createSeedEvents());
  const [reportRange, setReportRange] = useState<ReportRange>('day');
  const [activityFilter, setActivityFilter] = useState<ActivityFilter>('all');
  const [chat, setChat] = useState<ChatMessage[]>(initialChat);
  const [apiConnected, setApiConnected] = useState(false);
  const [loading, setLoading] = useState(true);

  const report = useMemo(() => buildRangeReport(events, reportRange), [events, reportRange]);

  const refresh = useCallback(async () => {
    setLoading(true);
    const connected = await api.checkHealth();
    setApiConnected(connected);
    if (connected) {
      const [nextCats, nextEvents] = await Promise.all([api.fetchCats(), api.fetchEvents()]);
      setCats(nextCats);
      setEvents(nextEvents);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const seedDemo = useCallback(async () => {
    const nextEvents = await api.seedEvents();
    setEvents(nextEvents);
  }, []);

  const clearTimeline = useCallback(async () => {
    await api.clearEvents();
    setEvents([]);
  }, []);

  const addScenario = useCallback(async (type: string) => {
    const event = await api.addScenarioEvent(type);
    setEvents((current) => [...current, event]);
  }, []);

  const analyzeNow = useCallback(async () => {
    const event = await api.addScenarioEvent('live');
    setEvents((current) => [...current, event]);
  }, []);

  const sendMessage = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed) return;
      setChat((current) => [...current, { role: 'owner', text: trimmed }]);
      const answer = await api.askAgent(trimmed, events, report);
      setChat((current) => [...current, { role: 'assistant', text: answer.text, provider: answer.provider }]);
    },
    [events, report],
  );

  const value = useMemo(
    () => ({
      cats,
      events,
      report,
      reportRange,
      activityFilter,
      chat,
      apiConnected,
      loading,
      setReportRange,
      setActivityFilter,
      refresh,
      seedDemo,
      clearTimeline,
      addScenario,
      analyzeNow,
      sendMessage,
    }),
    [
      cats,
      events,
      report,
      reportRange,
      activityFilter,
      chat,
      apiConnected,
      loading,
      refresh,
      seedDemo,
      clearTimeline,
      addScenario,
      analyzeNow,
      sendMessage,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
}
