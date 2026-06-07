export const Theme = {
  bg: '#111312',
  panel: '#191d1b',
  panel2: '#202622',
  line: '#334038',
  text: '#f3f0e8',
  muted: '#aab4ac',
  soft: '#d3c7a3',
  green: '#66d19e',
  yellow: '#e4bd5b',
  red: '#ef7c73',
  cyan: '#76c7d8',
  button: '#e8dfc8',
  buttonText: '#151814',
  tabBar: '#151816',
  tabBarBorder: '#2a332d',
} as const;

export type RiskLevel = 'normal' | 'watch' | 'review';

export function riskColor(level: RiskLevel): string {
  if (level === 'review') return Theme.red;
  if (level === 'watch') return Theme.yellow;
  return Theme.green;
}

export function riskLabel(level: RiskLevel): string {
  if (level === 'review') return 'review';
  if (level === 'watch') return 'watch';
  return 'nice';
}
