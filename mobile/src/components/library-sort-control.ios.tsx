import { NativeChoice } from '@/components/native-choice';
import type { useLibrarySort } from '@/hooks/use-library-sort';

export function LibrarySortControl({
  sort,
}: {
  sort: ReturnType<typeof useLibrarySort>;
}) {
  return (
    <NativeChoice
      label="Sort"
      value={sort.value}
      options={sort.options}
      onChange={sort.select}
      enabled={sort.ready}
    />
  );
}
