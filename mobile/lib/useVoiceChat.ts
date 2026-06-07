import { useCallback, useEffect, useRef, useState } from 'react';

import { AudioSession, registerGlobals } from '@livekit/react-native';
import { Room, RoomEvent } from 'livekit-client';

import { fetchLiveKitToken } from '@/lib/api';

// Install WebRTC globals once on load. Safe to call at import time; the native
// connection only happens in start(), where failures are caught.
registerGlobals();

export type VoiceState = 'idle' | 'connecting' | 'connected' | 'error';

/**
 * Hands-free voice chat over LiveKit. Connects to the room the voice_agent.py worker
 * is in (STT -> MiniMax + moss retrieval -> MiniMax TTS), publishes the mic, and plays
 * the agent's spoken replies. Audio-only: remote tracks are auto-played by the SDK.
 *
 * Requires a native dev build (WebRTC) — this does not run in Expo Go.
 */
export function useVoiceChat() {
  const roomRef = useRef<Room | null>(null);
  const [state, setState] = useState<VoiceState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [agentSpeaking, setAgentSpeaking] = useState(false);

  const stop = useCallback(async () => {
    try {
      await roomRef.current?.disconnect();
    } finally {
      roomRef.current = null;
      await AudioSession.stopAudioSession().catch(() => undefined);
      setAgentSpeaking(false);
      setState('idle');
    }
  }, []);

  const start = useCallback(async () => {
    if (roomRef.current) return;
    setState('connecting');
    setError(null);
    try {
      const lk = await fetchLiveKitToken();
      if (!lk.configured || !lk.url || !lk.token) {
        throw new Error('Voice is not configured on the server. Set LIVEKIT_* in .env and run voice_agent.py.');
      }

      await AudioSession.startAudioSession();
      const room = new Room();
      roomRef.current = room;

      room.on(RoomEvent.Disconnected, () => {
        roomRef.current = null;
        setAgentSpeaking(false);
        setState('idle');
      });
      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        const localId = room.localParticipant.identity;
        setAgentSpeaking(speakers.some((participant) => participant.identity !== localId));
      });

      await room.connect(lk.url, lk.token);
      await room.localParticipant.setMicrophoneEnabled(true);
      setState('connected');
    } catch (caught) {
      await AudioSession.stopAudioSession().catch(() => undefined);
      roomRef.current = null;
      setError(caught instanceof Error ? caught.message : 'Could not start voice chat.');
      setState('error');
    }
  }, []);

  // Disconnect if the screen unmounts mid-call.
  useEffect(() => () => void stop(), [stop]);

  return { state, error, agentSpeaking, start, stop };
}
