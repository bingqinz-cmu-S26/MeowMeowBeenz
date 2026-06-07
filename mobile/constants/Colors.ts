import { Theme } from '@/constants/Theme';

export default {
  light: {
    text: Theme.text,
    background: Theme.bg,
    tint: Theme.green,
    tabIconDefault: Theme.muted,
    tabIconSelected: Theme.button,
  },
  dark: {
    text: Theme.text,
    background: Theme.bg,
    tint: Theme.button,
    tabIconDefault: Theme.muted,
    tabIconSelected: Theme.button,
  },
};
