import { Image } from 'expo-image';
import { useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import {
  Gesture,
  GestureDetector,
  GestureHandlerRootView,
} from 'react-native-gesture-handler';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
} from 'react-native-reanimated';
import {
  ScreenshotControls,
  type ScreenshotCanvasProps,
} from './screenshot-controls';
import {
  boundTransform,
  initialTransform,
  zoomAt,
  type Viewport,
} from '@/lib/screenshot-viewer';

export default function ScreenshotCanvas(props: ScreenshotCanvasProps) {
  const [viewport, setViewport] = useState<Viewport>({ width: 0, height: 0 });
  return (
    <GestureHandlerRootView style={styles.fill}>
      <View
        style={styles.fill}
        onLayout={({ nativeEvent: { layout } }) => {
          setViewport((previous) =>
            previous.width === layout.width && previous.height === layout.height
              ? previous
              : { width: layout.width, height: layout.height },
          );
        }}
      >
        {viewport.width > 0 && viewport.height > 0 ? (
          <Viewer
            key={`${viewport.width}:${viewport.height}:${props.width}:${props.height}`}
            {...props}
            viewport={viewport}
          />
        ) : null}
      </View>
    </GestureHandlerRootView>
  );
}
function Viewer({
  viewport: outer,
  ...props
}: ScreenshotCanvasProps & { viewport: Viewport }) {
  const [viewport, setViewport] = useState<Viewport>({
    width: outer.width,
    height: Math.max(1, outer.height - 64),
  });
  const [loadedUri, setLoadedUri] = useState<string | null>(null);
  const imageHeight = (viewport.width * props.height) / props.width;
  const transform = useSharedValue(initialTransform);
  const start = useSharedValue(initialTransform);
  const pinchStart = useSharedValue(initialTransform);
  const anchor = useSharedValue({ x: 0, y: 0 });
  const imageStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: transform.get().x },
      { translateY: transform.get().y },
      { scale: transform.get().scale },
    ],
  }));
  const movePan = (event: { translationX: number; translationY: number }) => {
    'worklet';
    transform.set(
      boundTransform(viewport, imageHeight, {
        ...start.get(),
        x: start.get().x + event.translationX,
        y: start.get().y + event.translationY,
      }),
    );
  };
  const pan = Gesture.Pan()
    .maxPointers(1)
    .minDistance(3)
    .onStart(() => {
      start.set(transform.get());
    })
    .onUpdate(movePan);
  const pinch = Gesture.Pinch()
    .onStart((event) => {
      pinchStart.set(transform.get());
      anchor.set({ x: event.focalX, y: event.focalY });
    })
    .onUpdate((event) => {
      const next = zoomAt(
        viewport,
        imageHeight,
        pinchStart.get(),
        pinchStart.get().scale * event.scale,
        anchor.get().x,
        anchor.get().y,
      );
      transform.set(
        boundTransform(viewport, imageHeight, {
          ...next,
          x: next.x + event.focalX - anchor.get().x,
          y: next.y + event.focalY - anchor.get().y,
        }),
      );
    });
  const doubleTap = Gesture.Tap()
    .numberOfTaps(2)
    .onEnd((event) => {
      transform.set(
        zoomAt(
          viewport,
          imageHeight,
          transform.get(),
          transform.get().scale > 1 ? 1 : 2,
          event.x,
          event.y,
        ),
      );
    });
  const page = (direction: number) => {
    transform.set(
      boundTransform(viewport, imageHeight, {
        ...transform.get(),
        y: transform.get().y - direction * viewport.height * 0.8,
      }),
    );
  };
  return (
    <View style={styles.fill}>
      <ScreenshotControls
        onZoom={(factor) => {
          transform.set(
            zoomAt(
              viewport,
              imageHeight,
              transform.get(),
              transform.get().scale * factor,
              viewport.width / 2,
              viewport.height / 2,
            ),
          );
        }}
        onPage={page}
        onReset={() => {
          transform.set(initialTransform);
        }}
      />
      <GestureDetector
        gesture={Gesture.Race(Gesture.Simultaneous(pan, pinch), doubleTap)}
      >
        <View
          style={styles.viewport}
          onLayout={({ nativeEvent: { layout } }) => {
            setViewport((previous) =>
              previous.width === layout.width &&
              previous.height === layout.height
                ? previous
                : { width: layout.width, height: layout.height },
            );
          }}
        >
          <Animated.View
            style={[
              { width: viewport.width, height: imageHeight },
              styles.image,
              imageStyle,
            ]}
          >
            <Image
              source={{ uri: props.uri }}
              cachePolicy="none"
              recyclingKey={props.uri}
              contentFit="contain"
              allowDownscaling={false}
              style={styles.fill}
              accessibilityLabel={props.label}
              accessibilityHint="Use the zoom and scroll buttons above to read the screenshot."
              onLoad={() => setLoadedUri(props.uri)}
              onError={props.onError}
            />
          </Animated.View>
          {loadedUri !== props.uri ? (
            <View pointerEvents="none" style={styles.loading}>
              <ActivityIndicator accessibilityLabel="Loading screenshot" />
            </View>
          ) : null}
        </View>
      </GestureDetector>
    </View>
  );
}
const styles = StyleSheet.create({
  fill: { flex: 1 },
  viewport: { flex: 1, overflow: 'hidden', backgroundColor: '#18232b' },
  image: { position: 'absolute', top: 0, left: 0, transformOrigin: [0, 0, 0] },
  loading: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
