import 'leaflet/dist/leaflet.css'

import L from 'leaflet'
import { useMemo } from 'react'
import { ImageOverlay, MapContainer, Marker, Polyline, useMapEvents } from 'react-leaflet'

import { Fit } from '../viewer/SlideViewer.tsx'
import type { ImageSize } from '../viewer/useImageSize.ts'
import { imagePointToMap, mapToImagePoint, type Point } from './scale.ts'

interface Props {
  imageUrl: string
  size: ImageSize
  alt: string
  marks: Point[]
  onMark: (point: Point) => void
}

/** Thin crosshair with a label beside it, so the mark doesn't hide the tick it sits on. */
function markIcon(label: string) {
  return L.divIcon({
    className: '',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    html: `<div class="pointer-events-none relative size-8">
      <span class="absolute top-0 left-1/2 h-full w-px -translate-x-1/2 bg-cyan-400 shadow-[0_0_2px_#000]"></span>
      <span class="absolute top-1/2 left-0 h-px w-full -translate-y-1/2 bg-cyan-400 shadow-[0_0_2px_#000]"></span>
      <span class="absolute -top-3 left-5 rounded bg-cyan-600 px-1 text-[11px] leading-4 font-bold text-white">${label}</span>
    </div>`,
  })
}

const ICONS = [markIcon('A'), markIcon('B')]

function ClickToMark({ size, onMark }: Pick<Props, 'size' | 'onMark'>) {
  useMapEvents({
    // Leaflet fires no click after a drag, so panning never places a mark.
    click: (e) => {
      const point = mapToImagePoint(e.latlng.lat, e.latlng.lng, size)
      if (point) onMark(point)
    },
  })
  return null
}

/**
 * Zoomable stage-micrometer photo for placing the two calibration marks precisely
 * (scroll/pinch or +/- to zoom, drag to pan). Marks are in natural image pixels, so
 * µm/px does not depend on zoom or display size.
 */
export function MicrometerCanvas({ imageUrl, size, alt, marks, onMark }: Props) {
  // CRS.Simple: one map unit per image pixel, origin bottom-left (as in SlideViewer).
  const bounds = useMemo(() => L.latLngBounds([0, 0], [size.height, size.width]), [size])
  const positions = marks.map((m) => imagePointToMap(m, size))

  return (
    <MapContainer
      crs={L.CRS.Simple}
      bounds={bounds}
      maxZoom={3}
      zoomSnap={0.25}
      zoomDelta={0.5}
      wheelPxPerZoomLevel={90}
      // A double-click would also fire two clicks and put A and B on the same spot.
      doubleClickZoom={false}
      attributionControl={false}
      className="h-80 w-full rounded-lg sm:h-[28rem]"
      // Inline: leaflet.css sets its own grey background and grab cursor on the container.
      style={{ cursor: 'crosshair', background: '#0f172a' }}
    >
      <Fit bounds={bounds} />
      <ImageOverlay url={imageUrl} bounds={bounds} alt={alt} />
      <ClickToMark size={size} onMark={onMark} />
      {positions.length === 2 && (
        <Polyline positions={positions} interactive={false} pathOptions={{ color: '#22d3ee', weight: 1.5, dashArray: '6 4' }} />
      )}
      {positions.map((p, i) => (
        <Marker key={i} position={p} icon={ICONS[i]} interactive={false} keyboard={false} />
      ))}
    </MapContainer>
  )
}
