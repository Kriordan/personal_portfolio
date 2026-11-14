import { Platform } from 'react-native';

export const mobileTools = [
  ...(Platform.OS === 'ios' ? [{
    title: 'Intervals',
    description: 'Build a workout. Run at your own rhythm.',
    href: '/intervals',
    badge: 'I',
  } as const] : []),
  {
    title: 'Scratch-offs',
    description: 'Compare NY and CT ticket odds.',
    href: '/scratch-offs',
    badge: 'S',
  },
  {
    title: 'Draw planner',
    description: 'Powerball, Mega Millions, and fewer stops.',
    href: '/draw-games',
    badge: 'D',
  },
  {
    title: 'Grocery',
    description: 'Your lists, ready for the next shop.',
    href: '/lists',
    badge: 'G',
  },
  {
    title: 'Wishlist',
    description: 'Keep gift ideas close at hand.',
    href: '/wishlist',
    badge: 'W',
  },
  {
    title: 'Library',
    description: 'Browse your saved video playlists.',
    href: '/library',
    badge: 'L',
  },
  {
    title: 'Learning',
    description: 'Revisit notes. Make knowledge stick.',
    href: '/learning',
    badge: 'R',
  },
  {
    title: 'Jobwizard',
    description: 'Keep track of saved job listings.',
    href: '/jobwizard',
    badge: 'J',
  },
] as const;
