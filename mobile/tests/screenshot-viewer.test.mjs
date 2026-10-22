import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  boundTransform,
  initialTransform,
  validScreenshotSize,
  zoomAt,
} from '../src/lib/screenshot-viewer.ts';

test('full-page screenshots stay within the existing image budget', () => {
  assert.ok(validScreenshotSize(1280, 9090));
  for (const pair of [
    [0, 100],
    [-1, 100],
    [1.5, 100],
    [Infinity, 1],
    [1280, 20000],
  ])
    assert.equal(validScreenshotSize(...pair), false);
});
test('tall screenshots start at readable width and pan all the way to their footer', () => {
  const viewport = { width: 390, height: 650 },
    height = (390 * 9090) / 1280;
  assert.deepEqual(
    boundTransform(viewport, height, initialTransform),
    initialTransform,
  );
  assert.deepEqual(
    boundTransform(viewport, height, { scale: 1, x: 900, y: -10000 }),
    { scale: 1, x: 0, y: 650 - height },
  );
  assert.deepEqual(
    boundTransform(viewport, height, { scale: 2, x: -10000, y: 100 }),
    { scale: 2, x: -390, y: 0 },
  );
});
test('zoom keeps the tapped point fixed until an image boundary is reached', () => {
  const viewport = { width: 390, height: 650 };
  const zoomed = zoomAt(viewport, 3000, initialTransform, 2, 100, 300);
  assert.deepEqual(zoomed, { scale: 2, x: -100, y: -300 });
  assert.deepEqual(
    zoomAt(viewport, 3000, zoomed, 1, 100, 300),
    initialTransform,
  );
  assert.equal(zoomAt(viewport, 3000, initialTransform, 100, 0, 0).scale, 4);
  assert.deepEqual(
    zoomAt(viewport, 3000, initialTransform, 0.1, 0, 0),
    initialTransform,
  );
});
test('short images and viewport changes never pan into blank space', () => {
  assert.deepEqual(
    boundTransform({ width: 390, height: 650 }, 200, {
      scale: 1,
      x: -100,
      y: -100,
    }),
    initialTransform,
  );
  assert.deepEqual(
    boundTransform({ width: 200, height: 800 }, 1000, {
      scale: 2,
      x: -390,
      y: -2000,
    }),
    { scale: 2, x: -200, y: -1200 },
  );
});
