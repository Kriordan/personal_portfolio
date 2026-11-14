import { readIntervalLibrary, type IntervalLibrary } from './interval-model.ts';

export function createIntervalStore(storage: { readLibrary(): Promise<string | null>; writeLibrary(json: string): Promise<void> }) {
  let library: IntervalLibrary | null = null;
  let tail: Promise<unknown> = Promise.resolve();
  const serial = <T>(run: () => Promise<T>) => {
    const next = tail.then(run, run);
    tail = next.catch(() => {});
    return next;
  };
  const read = async () => {
    if (library) return library;
    const raw = await storage.readLibrary();
    const next = readIntervalLibrary(raw);
    if (raw === null) await storage.writeLibrary(JSON.stringify(next));
    library = next;
    return next;
  };
  return {
    read: () => serial(read),
    change: (edit: (current: IntervalLibrary) => IntervalLibrary) => serial(async () => {
      const current = await read();
      const next = readIntervalLibrary(JSON.stringify(edit(current)));
      await storage.writeLibrary(JSON.stringify(next));
      library = next;
      return next;
    }),
  };
}
