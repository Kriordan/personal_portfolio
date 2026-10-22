export type Viewport = { width: number; height: number };
export type ImageTransform = { scale: number; x: number; y: number };
export const initialTransform: ImageTransform = { scale: 1, x: 0, y: 0 };

export function validScreenshotSize(width: number, height: number) {
  return (
    Number.isInteger(width) &&
    Number.isInteger(height) &&
    width > 0 &&
    height > 0 &&
    width * height <= 24_000_000
  );
}

export function boundTransform(
  viewport: Viewport,
  imageHeight: number,
  next: ImageTransform,
): ImageTransform {
  'worklet';
  const scale = Math.max(1, Math.min(4, next.scale));
  return {
    scale,
    x: Math.max(viewport.width * (1 - scale), Math.min(0, next.x)),
    y: Math.max(
      Math.min(0, viewport.height - imageHeight * scale),
      Math.min(0, next.y),
    ),
  };
}

// Keep the image point beneath the gesture/button anchor in the same place.
export function zoomAt(
  viewport: Viewport,
  imageHeight: number,
  previous: ImageTransform,
  scale: number,
  x: number,
  y: number,
): ImageTransform {
  'worklet';
  const boundedScale = Math.max(1, Math.min(4, scale));
  const ratio = boundedScale / previous.scale;
  return boundTransform(viewport, imageHeight, {
    scale: boundedScale,
    x: x - (x - previous.x) * ratio,
    y: y - (y - previous.y) * ratio,
  });
}
