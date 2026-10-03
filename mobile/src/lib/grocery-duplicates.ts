import type { ListDetail, ListItem } from './lists-api';

export function normalizeItemName(name: string): string {
  return name.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ').trim().replace(/\s+/g, ' ');
}

function singular(word: string): string {
  if (word.length > 4 && word.endsWith('ies')) return word.slice(0, -3) + 'y';
  if (/(ches|shes|xes|zes|sses)$/.test(word)) return word.slice(0, -2);
  if (word.length > 3 && word.endsWith('s') && !/(ss|us|is)$/.test(word)) return word.slice(0, -1);
  return word;
}

function smallTypo(a: string, b: string): boolean {
  // Short food names (rice/ice, milk/silk) and different phrases are too ambiguous.
  if (Math.min(a.length, b.length) < 5 || Math.abs(a.length - b.length) > 1) return false;
  let i = 0;
  while (i < Math.min(a.length, b.length) && a[i] === b[i]) i++;
  if (a.length !== b.length) {
    const [shorter, longer] = a.length < b.length ? [a, b] : [b, a];
    return shorter.slice(i) === longer.slice(i + 1);
  }
  return a.slice(i + 1) === b.slice(i + 1) ||
    (a[i] === b[i + 1] && a[i + 1] === b[i] && a.slice(i + 2) === b.slice(i + 2));
}

export interface DuplicateMatch {
  item: ListItem;
  category: string;
  exact: boolean;
}

/** Advisory only: no merging, fuzzy database constraints, or cross-list search. */
export function findDuplicateItems(list: ListDetail, name: string, excludeId?: number): DuplicateMatch[] {
  const normalized = normalizeItemName(name);
  if (!normalized) return [];
  const originalWords = normalized.split(' ');
  const words = originalWords.map(singular);
  const matches: DuplicateMatch[] = [];
  for (const category of list.categories) {
    for (const item of category.items) {
      if (item.id === excludeId) continue;
      const existing = normalizeItemName(item.name);
      const otherOriginalWords = existing.split(' ');
      const otherWords = otherOriginalWords.map(singular);
      const exact = normalized === existing;
      const differentWords = words.filter((word, index) => word !== otherWords[index]);
      const similar = words.length === otherWords.length && differentWords.length <= 1 &&
        words.every((word, index) => word === otherWords[index] ||
          smallTypo(word, otherWords[index]) || smallTypo(originalWords[index], otherOriginalWords[index]));
      if (exact || similar) matches.push({ item, category: category.name, exact });
    }
  }
  return matches.sort((a, b) => Number(b.exact) - Number(a.exact));
}
