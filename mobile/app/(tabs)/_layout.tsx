import { Redirect, Tabs } from 'expo-router';
import { SymbolView } from 'expo-symbols';

import { useAuth } from '@/context/AuthContext';
import { Theme } from '@/constants/Theme';

function TabsNavigator() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: Theme.tabBar,
          borderTopColor: Theme.tabBarBorder,
        },
        tabBarActiveTintColor: Theme.button,
        tabBarInactiveTintColor: Theme.muted,
      }}>
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color }) => (
            <SymbolView name={{ ios: 'house.fill', android: 'home', web: 'home' }} tintColor={color} size={24} />
          ),
        }}
      />
      <Tabs.Screen
        name="live"
        options={{
          title: 'Live',
          tabBarIcon: ({ color }) => (
            <SymbolView name={{ ios: 'video.fill', android: 'videocam', web: 'videocam' }} tintColor={color} size={24} />
          ),
        }}
      />
      <Tabs.Screen
        name="agent"
        options={{
          title: 'Agent',
          tabBarIcon: ({ color }) => (
            <SymbolView
              name={{ ios: 'bubble.left.and.bubble.right.fill', android: 'chat', web: 'chat' }}
              tintColor={color}
              size={24}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="activity"
        options={{
          title: 'Activity',
          tabBarIcon: ({ color }) => (
            <SymbolView name={{ ios: 'chart.bar.fill', android: 'bar_chart', web: 'bar_chart' }} tintColor={color} size={24} />
          ),
        }}
      />
      <Tabs.Screen
        name="health"
        options={{
          title: 'Health',
          tabBarIcon: ({ color }) => (
            <SymbolView name={{ ios: 'heart.fill', android: 'favorite', web: 'favorite' }} tintColor={color} size={24} />
          ),
        }}
      />
    </Tabs>
  );
}

export default function TabLayout() {
  const { user, booting } = useAuth();

  if (booting) {
    return null;
  }

  if (!user) {
    return <Redirect href="/(auth)" />;
  }

  return <TabsNavigator />;
}
