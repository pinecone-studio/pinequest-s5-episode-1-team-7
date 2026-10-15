import 'leaflet/dist/leaflet.css'

import L from 'leaflet'
import { useEffect, useId, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ImageOverlay, MapContainer, useMap } from 'react-leaflet'

import { useFormat } from '../../shared/lib/useFormat.ts'
import { SegmentedControl } from '../../shared/ui/SegmentedControl.tsx'
import { type ImageSize, useImageSize } from './useImageSize.ts'

interface Props {
  imageUrl: string
  /** RGBA PNG the size of the photo (engine/pipeline/heatmap.py); absent until the slide is scored. */
  heatmapUrl?: string
}

/** Fits the photo in view, and limits zoom-out and panning to around it. */
export function Fit({ bounds }: { bounds: L.LatLngBounds }) {
  const map = useMap()
  useEffect(() => {
    map.fitBounds(bounds)
    map.setMinZoom(map.getBoundsZoom(bounds) - 1)
    map.setMaxBounds(bounds.pad(0.5))
  }, [map, bounds])
  return null
}

/** Zoomable tissue photo with the AI heatmap on top (TDD 6.2 dual-layer canvas). */
export function SlideViewer({ imageUrl, heatmapUrl }: Props) {
  const { t } = useTranslation('viewer')
  const { size, error } = useImageSize(imageUrl)
  if (error) return <p className="flex size-full items-center justify-center text-sm text-critical">{t('imageMissing')}</p>
  if (!size) return <p className="flex size-full items-center justify-center text-sm text-ink-faint">{t('loading')}</p>
  return <Canvas imageUrl={imageUrl} heatmapUrl={heatmapUrl} size={size} />
}

function Canvas({ imageUrl, heatmapUrl, size }: Props & { size: ImageSize }) {
  const { t } = useTranslation('viewer')
  const f = useFormat()
  const opacityId = useId()
  const [showHeatmap, setShowHeatmap] = useState(true)
  const [opacity, setOpacity] = useState(0.5)
  // CRS.Simple: one map unit per image pixel, origin bottom-left.
  const bounds = useMemo(() => L.latLngBounds([0, 0], [size.height, size.width]), [size])
  const heatmapOn = !!heatmapUrl && showHeatmap

  return (
    <div className="relative size-full">
      <MapContainer
        crs={L.CRS.Simple}
        bounds={bounds}
        maxZoom={3}
        zoomSnap={0.25}
        zoomDelta={0.5}
        wheelPxPerZoomLevel={90}
        attributionControl={false}
        className="size-full"
      >
        <Fit bounds={bounds} />
        <ImageOverlay url={imageUrl} bounds={bounds} />
        {heatmapOn && <ImageOverlay url={heatmapUrl} bounds={bounds} opacity={opacity} zIndex={2} />}
      </MapContainer>

      <div className="absolute top-3 right-3 z-[500] w-60 space-y-2 rounded-xl border border-line bg-surface/90 p-3 text-xs text-ink shadow-[0_16px_40px_-16px_rgb(0_0_0/0.7)] backdrop-blur-md">
        <SegmentedControl
          tone="dark"
          className="text-xs"
          label={t('overlay.label')}
          value={heatmapOn ? 'heat' : 'none'}
          onChange={(v) => setShowHeatmap(v === 'heat')}
          options={[
            { value: 'heat', label: t('overlay.heat'), disabled: !heatmapUrl, title: heatmapUrl ? undefined : t('overlay.heatMissing') },
            { value: 'none', label: t('overlay.none') },
          ]}
        />
        <div>
          <label htmlFor={opacityId} className="flex justify-between text-ink-dim">
            <span>{t('overlay.opacity')}</span>
            <span className="tnum">{f.pct(opacity)}</span>
          </label>
          <input
            id={opacityId}
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={opacity}
            disabled={!heatmapOn}
            onChange={(e) => setOpacity(Number(e.target.value))}
            className="w-full accent-mist disabled:opacity-40"
          />
        </div>
        {heatmapOn && (
          <div className="space-y-1.5" aria-hidden>
            <div className="flex items-center gap-2">
              <span className="text-ink-faint">{t('legend.low')}</span>
              <span className="h-2 flex-1 rounded-full bg-gradient-to-r from-[#4a8f5d] via-[#c9ac7c] to-[#cf8d8d]" />
              <span className="text-ink-faint">{t('legend.high')}</span>
            </div>
            <div className="flex items-center gap-2 text-ink-dim">
              <span className="size-3 shrink-0 rounded-sm border-2 border-mist" />
              {t('legend.hotspot')}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
