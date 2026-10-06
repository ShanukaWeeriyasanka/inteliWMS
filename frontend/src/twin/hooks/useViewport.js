// Map viewport: the SVG viewBox (metres) plus the container size, with smooth
// animated moves. The viewBox keeps the container's aspect ratio, so one
// screen pixel is always vb.w / size.w metres.
import { useCallback, useEffect, useRef, useState } from 'react'
import { lerpView } from '../lib/viewport'

const MOVE_MS = 420

export function useViewport({ reducedMotion }) {
  const [vb, setVb] = useState(null)
  const [size, setSize] = useState({ w: 0, h: 0 })
  const vbRef = useRef(null)
  vbRef.current = vb
  const anim = useRef(0)
  const observer = useRef(null)

  // Callback ref: the map container appears only after the layout has loaded.
  const containerRef = useCallback((el) => {
    observer.current?.disconnect()
    if (!el) return
    observer.current = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize((s) => (s.w === width && s.h === height ? s : { w: width, h: height }))
    })
    observer.current.observe(el)
  }, [])

  const aspect = size.w > 0 && size.h > 0 ? size.w / size.h : 0

  // Keep the viewBox aspect equal to the container's when the container resizes.
  useEffect(() => {
    if (!aspect) return
    setVb((v) => {
      if (!v) return v
      const h = v.w / aspect
      return Math.abs(h - v.h) < 1e-6 ? v : { ...v, y: v.y + (v.h - h) / 2, h }
    })
  }, [aspect])

  const set = useCallback((next) => {
    cancelAnimationFrame(anim.current)
    setVb(typeof next === 'function' ? next(vbRef.current) : next)
  }, [])

  const animateTo = useCallback((target) => {
    cancelAnimationFrame(anim.current)
    const from = vbRef.current
    if (!from || reducedMotion) {
      setVb(target)
      return
    }
    const t0 = performance.now()
    const step = (now) => {
      const t = Math.min(1, (now - t0) / MOVE_MS)
      setVb(lerpView(from, target, 1 - (1 - t) ** 3))
      if (t < 1) anim.current = requestAnimationFrame(step)
    }
    anim.current = requestAnimationFrame(step)
  }, [reducedMotion])

  useEffect(() => () => {
    cancelAnimationFrame(anim.current)
    observer.current?.disconnect()
  }, [])

  return { containerRef, vb, size, aspect, set, animateTo, mpp: vb && size.w ? vb.w / size.w : 0 }
}
