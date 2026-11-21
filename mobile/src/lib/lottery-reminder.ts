const easternDay = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  weekday: 'short',
  hour: '2-digit',
  hourCycle: 'h23',
});

/** The weekly plan starts with Monday's draw, so stop reminding at its cutoff. */
export function mondayLotteryDay(now = Date.now()): string | null {
  const parts = Object.fromEntries(
    easternDay.formatToParts(new Date(now)).map(({ type, value }) => [type, value]),
  );
  return parts.weekday === 'Mon' && Number(parts.hour) < 22
    ? `${parts.year}-${parts.month}-${parts.day}`
    : null;
}

interface ReminderStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
}

export function createMondayLotteryReminder(store: ReminderStore) {
  // Also prevents repeats during this app session if device storage fails.
  const shown = new Map<number, string>();
  return {
    async claim(userId: number, active: () => boolean, clock = Date.now) {
      const day = mondayLotteryDay(clock());
      if (!day || !active() || shown.get(userId) === day) return false;
      const key = `lottery.monday-reminder.${userId}`;
      const previous = await store.get(key).catch(() => null);
      // A delayed storage read must not open a popup after navigation or logout.
      if (!active() || day !== mondayLotteryDay(clock()) || shown.get(userId) === day)
        return false;
      shown.set(userId, day);
      if (previous === day) return false;
      void store.set(key, day).catch(() => {});
      return true;
    },
  };
}
