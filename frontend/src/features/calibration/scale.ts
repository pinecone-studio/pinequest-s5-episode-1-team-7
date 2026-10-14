/** Pixel point in an image's natural size. */
export interface Point {
  x: number
  y: number
}

/**
 * Map position in the zoomable viewer (Leaflet CRS.Simple: one unit per image pixel,
 * origin bottom-left, as in viewer/SlideViewer.tsx) to a natural-pixel point (origin
 * top-left). Null when the click is outside the photo.
 */
export function mapToImagePoint(lat: number, lng: number, size: { width: number; height: number }): Point | null {
  const point = { x: lng, y: size.height - lat }
  if (point.x < 0 || point.y < 0 || point.x > size.width || point.y > size.height) return null
  return point
}

/** Inverse of mapToImagePoint: [lat, lng] for a natural-pixel point. */
export function imagePointToMap(point: Point, size: { width: number; height: number }): [number, number] {
  return [size.height - point.y, point.x]
}

/**
 * µm/px from two clicked marks a known distance apart (issue #35): the stage
 * micrometer's true distance divided by the marks' pixel distance. Null when
 * the marks coincide or the distance is not positive.
 */
export function umPerPx(markA: Point, markB: Point, distanceUm: number): number | null {
  const px = Math.hypot(markA.x - markB.x, markA.y - markB.y)
  if (!(px > 0) || !(distanceUm > 0)) return null
  return distanceUm / px
}

/**
 * µm/px of a capture taken at `objective` from a setup calibrated at
 * `calibratedObjective` — mirrors backend/app/setups.py. Null on bad labels.
 */
export function scaledUmPerPx(calibratedUmPerPx: number, calibratedObjective: string, objective: string): number | null {
  const parse = (label: string) => {
    const m = /^\s*(\d+(?:\.\d+)?)\s*x\s*$/i.exec(label ?? '')
    const mag = m ? Number(m[1]) : NaN
    return mag > 0 ? mag : NaN
  }
  const calib = parse(calibratedObjective)
  const mag = parse(objective)
  if (!(calibratedUmPerPx > 0) || Number.isNaN(calib) || Number.isNaN(mag)) return null
  return (calibratedUmPerPx * calib) / mag
}
