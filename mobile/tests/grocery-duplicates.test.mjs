import assert from 'node:assert/strict';
import { test } from 'node:test';
import { findDuplicateItems, normalizeItemName } from '../src/lib/grocery-duplicates.ts';

const list = {
  categories: [
    { id: 1, name: 'Produce', items: [
      { id: 10, name: 'Apples', completed: false },
      { id: 11, name: 'Cherry tomatoes', completed: false },
      { id: 12, name: 'Blueberries', completed: false },
    ] },
    { id: 2, name: 'Pantry', items: [
      { id: 20, name: 'Olive oil', completed: true },
      { id: 21, name: 'Milk', completed: false },
      { id: 22, name: 'Café beans', completed: false },
      { id: 23, name: 'White rice', completed: false },
    ] },
  ],
};

test('duplicate suggestions span categories and include completed items', () => {
  for (const name of [' Apples ', 'APPLES', 'apples!']) {
    assert.deepEqual(findDuplicateItems(list, name).map((match) => [match.item.id, match.exact]), [[10, true]]);
  }
  const match = findDuplicateItems(list, '  Olive   oil ')[0];
  assert.equal(match.item.completed, true);
  assert.equal(match.category, 'Pantry');
  assert.equal(findDuplicateItems(list, 'cafe beans')[0].item.id, 22);
});

test('simple plurals and conservative typos are suggestions, not exact matches', () => {
  for (const [name, id] of [['Apple', 10], ['Appls', 10], ['Appels', 10], ['Blueberry', 12], ['Chery tomatoes', 11]]) {
    const matches = findDuplicateItems(list, name);
    assert.equal(matches.length, 1, name);
    assert.equal(matches[0].item.id, id, name);
    assert.equal(matches[0].exact, false, name);
  }
});

test('different food phrases and ambiguous short words are not merged or flagged', () => {
  for (const name of ['', '!!!', 'Almond milk', 'Oat milk', 'Silk', 'White mice', 'Green apples', 'Apple juice', 'Tomato sauce']) {
    assert.deepEqual(findDuplicateItems(list, name), [], name);
  }
  assert.equal(normalizeItemName('  Café—BEANS  '), 'cafe beans');
});

test('editing excludes the same row, but still sees another actual duplicate', () => {
  assert.deepEqual(findDuplicateItems(list, 'Apples', 10), []);
  const duplicate = structuredClone(list);
  duplicate.categories[1].items.push({ id: 30, name: 'Apples', completed: true });
  assert.deepEqual(findDuplicateItems(duplicate, 'Apples', 10).map((match) => match.item.id), [30]);
  assert.equal(list.categories[1].items.length, 4, 'Matching does not mutate data');
});
