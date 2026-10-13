import { useEffect, useState } from 'react'

export type ImageSize = { width: number; height: number }

/** Natural pixel size of the image at `url` (the API doesn't report it). `error` if it fails to load. */
export function useImageSize(url: string) {
  const [state, setState] = useState<{ url: string; size?: ImageSize; error?: boolean }>({ url })
  useEffect(() => {
    let cancelled = false
    const img = new Image()
    img.onload = () => !cancelled && setState({ url, size: { width: img.naturalWidth, height: img.naturalHeight } })
    img.onerror = () => !cancelled && setState({ url, error: true })
    img.src = url
    return () => {
      cancelled = true
    }
  }, [url])
  // Ignore a result that belongs to a previous URL.
  return state.url === url ? state : { url }
}
