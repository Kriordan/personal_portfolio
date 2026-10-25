import { Image } from 'expo-image';
import { useTheme } from '@/hooks/use-theme';

// Small, shared line icons keep the web and Android fallback free of font/emoji dependencies.
const paths = {
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  add: '<path d="M12 4v16M4 12h16"/>',
  filter: '<path d="M3 6h18M6 12h12M10 18h4"/>',
  sort: '<path d="M8 20V4L4 8m4-4 4 4M16 4v16l4-4m-4 4-4-4"/>',
} as const;

export function JobToolbarIcon({ name }: { name: keyof typeof paths }) {
  const theme = useTheme();
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="${theme.accent}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths[name]}</svg>`;
  return <Image accessible={false} source={{ uri: `data:image/svg+xml;base64,${btoa(svg)}` }} style={{ width: 22, height: 22 }} />;
}
