import { Image } from 'expo-image';
import { useRef, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import {
  ScreenshotControls,
  type ScreenshotCanvasProps,
} from './screenshot-controls';

// Web remains a development convenience: ordinary scrollbars plus zoom buttons.
export default function ScreenshotCanvas(props: ScreenshotCanvasProps) {
  const [width, setWidth] = useState(1),
    [height, setHeight] = useState(1),
    [zoom, setZoom] = useState(1);
  const vertical = useRef<ScrollView>(null),
    horizontal = useRef<ScrollView>(null),
    offset = useRef(0);
  return (
    <View style={styles.fill}>
      <ScreenshotControls
        onZoom={(factor) =>
          setZoom((value) => Math.max(1, Math.min(4, value * factor)))
        }
        onPage={(direction) =>
          vertical.current?.scrollTo({
            y: Math.max(0, offset.current + direction * height * 0.8),
          })
        }
        onReset={() => {
          setZoom(1);
          vertical.current?.scrollTo({ y: 0 });
          horizontal.current?.scrollTo({ x: 0 });
        }}
      />
      <View
        style={styles.fill}
        onLayout={({ nativeEvent: { layout } }) => {
          setWidth(layout.width);
          setHeight(layout.height);
        }}
      >
        <ScrollView
          ref={horizontal}
          horizontal
          contentContainerStyle={{ height: '100%' }}
        >
          <ScrollView
            ref={vertical}
            style={{ width: width * zoom }}
            scrollEventThrottle={16}
            onScroll={(event) => {
              offset.current = event.nativeEvent.contentOffset.y;
            }}
          >
            <Image
              source={{ uri: props.uri }}
              cachePolicy="none"
              recyclingKey={props.uri}
              contentFit="contain"
              style={{
                width: width * zoom,
                height: (width * zoom * props.height) / props.width,
              }}
              accessibilityLabel={props.label}
              onError={props.onError}
            />
          </ScrollView>
        </ScrollView>
      </View>
    </View>
  );
}
const styles = StyleSheet.create({ fill: { flex: 1 } });
