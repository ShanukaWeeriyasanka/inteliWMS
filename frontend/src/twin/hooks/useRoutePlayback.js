// Guided route playback: draw floor segment → walker reaches lift/stairs →
// "Lift A → Floor 3" pill + floor slide → draw next segment → … → arrive.
// With prefers-reduced-motion everything is shown at once on the final floor.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

export const DRAW_MS = 900
const HOLD_MS = 350
const TRANSFER_MS = 1100

export function useRoutePlayback(segments, { reducedMotion, playKey, autoplay, onFloor, onDone }) {
  // Floors the lift only passes through have nothing to walk: skip them.
  const walk = useMemo(() => segments.filter((s) => !s.passThrough), [segments])
  const [cursor, setCursor] = useState({ i: 0, phase: 'idle' }) // idle | draw | transfer | done
  const [playing, setPlaying] = useState(false)
  const timer = useRef(null)
  const cb = useRef({ onFloor, onDone })
  cb.current = { onFloor, onDone }

  const clear = () => clearTimeout(timer.current)

  const finish = useCallback(() => {
    clear()
    setPlaying(false)
    const last = walk[walk.length - 1]
    setCursor({ i: walk.length - 1, phase: 'done' })
    if (last) cb.current.onFloor?.(last.floorId)
    cb.current.onDone?.()
  }, [walk])

  // Run the current step's timer whenever we are playing.
  useEffect(() => {
    if (!playing || !walk.length) return undefined
    const { i, phase } = cursor
    if (phase === 'draw') {
      cb.current.onFloor?.(walk[i].floorId)
      timer.current = setTimeout(() => {
        if (i < walk.length - 1) setCursor({ i, phase: 'transfer' })
        else finish()
      }, DRAW_MS + HOLD_MS)
    } else if (phase === 'transfer') {
      timer.current = setTimeout(() => setCursor({ i: i + 1, phase: 'draw' }), TRANSFER_MS)
    }
    return clear
  }, [cursor, playing, walk, finish])

  const replay = useCallback(() => {
    clear()
    if (!walk.length) return
    if (reducedMotion) { finish(); return }
    setCursor({ i: 0, phase: 'draw' })
    setPlaying(true)
  }, [walk, reducedMotion, finish])

  // New route → start (or show final state) automatically.
  useEffect(() => {
    clear()
    if (!walk.length || !playKey) {
      setCursor({ i: 0, phase: 'idle' })
      setPlaying(false)
      return
    }
    if (autoplay) replay()
    else finish()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playKey, walk.length])

  const pause = useCallback(() => { clear(); setPlaying(false) }, [])
  const play = useCallback(() => {
    if (cursor.phase === 'done' || cursor.phase === 'idle') replay()
    else setPlaying(true)
  }, [cursor.phase, replay])

  useEffect(() => clear, [])

  const current = walk[cursor.i] || null
  const next = walk[cursor.i + 1] || null
  return {
    walk, cursor, playing, play, pause, replay, skip: finish,
    currentSegment: current,
    transfer: cursor.phase === 'transfer' && next
      ? { label: next.connectorLabel, via: next.arrivedVia, toFloorId: next.floorId, up: next.floorLevel > current.floorLevel }
      : null,
  }
}
