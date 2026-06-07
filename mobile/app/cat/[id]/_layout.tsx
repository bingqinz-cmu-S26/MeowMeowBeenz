import { Stack } from 'expo-router';

export default function CatProfileLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="events" />
      <Stack.Screen name="alerts" />
    </Stack>
  );
}
