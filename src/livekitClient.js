let room = null;
let localTracks = [];

export async function connectLiveKit({ previewVideo, statusCallback }) {
  const tokenResponse = await fetch("/api/livekit-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      room: "mochi-monitor-demo",
      identity: `owner-${Date.now()}`
    })
  });
  const tokenData = await tokenResponse.json();
  if (!tokenResponse.ok || !tokenData.ok) {
    throw new Error(tokenData.error || "LiveKit token unavailable.");
  }

  const livekit = await import("https://esm.sh/livekit-client@2?bundle");
  const { Room, RoomEvent, createLocalTracks } = livekit;

  room = new Room({ adaptiveStream: true, dynacast: true });
  room.on(RoomEvent.Connected, () => statusCallback?.(`Connected to ${tokenData.room}`));
  room.on(RoomEvent.Reconnecting, () => statusCallback?.("LiveKit reconnecting"));
  room.on(RoomEvent.Reconnected, () => statusCallback?.("LiveKit reconnected"));
  room.on(RoomEvent.Disconnected, () => statusCallback?.("LiveKit disconnected"));

  await room.connect(tokenData.url, tokenData.token);
  localTracks = await createLocalTracks({ audio: true, video: true });

  for (const track of localTracks) {
    await room.localParticipant.publishTrack(track);
    if (track.kind === "video" && previewVideo) {
      track.attach(previewVideo);
    }
  }

  return {
    room: tokenData.room,
    identity: tokenData.identity
  };
}

export function disconnectLiveKit() {
  localTracks.forEach((track) => {
    track.stop();
    track.detach?.();
  });
  localTracks = [];
  room?.disconnect();
  room = null;
}

export function isLiveKitConnected() {
  return Boolean(room);
}
