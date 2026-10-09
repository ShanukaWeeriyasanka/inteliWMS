// Pan / zoom maths for the floor plan. The SVG viewBox is in metres, the same
// units as the database coordinates, so a view is just { x, y, w, h } in metres.
// The viewBox always has the container's aspect ratio, so metres-per-pixel is w / width.

export const MIN_VIEW_W = 10
const PAD = { x: 3, top: 3, bottom: 3 }

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))

/** Whole floor (plus a small margin) centred in a container of the given aspect (width / height). */
export function fitView(floor, aspect, pad = PAD) {
  const W = floor.width_m + pad.x * 2
  const H = floor.height_m + pad.top + pad.bottom
  let w = W
  let h = W / aspect
  if (h < H) {
    h = H
    w = H * aspect
  }
  return {
    x: floor.width_m / 2 - w / 2,
    y: (floor.height_m + pad.bottom - pad.top) / 2 - h / 2,
    w,
    h,
  }
}

/** Zoom by `factor` (> 1 = closer) keeping the point (cx, cy) fixed on screen. */
export function zoomAt(vb, factor, cx, cy, { minW = MIN_VIEW_W, maxW = Infinity } = {}) {
  const w = clamp(vb.w / factor, minW, maxW)
  const f = w / vb.w
  return { x: cx - (cx - vb.x) * f, y: cy - (cy - vb.y) * f, w, h: vb.h * f }
}

/**
 * View that frames `box` (metres) with context around it.
 * `occludeRight` is the fraction of the container covered by a panel on the right;
 * the box is centred in the part that stays visible.
 */
export function focusView(box, aspect, { scale = 3, minW = 22, maxW = Infinity, occludeRight = 0 } = {}) {
  const visible = 1 - clamp(occludeRight, 0, 0.6)
  const w = clamp(Math.max((box.w * scale) / visible, box.h * scale * aspect, minW), MIN_VIEW_W, maxW)
  const h = w / aspect
  const cx = box.x + box.w / 2
  const cy = box.y + box.h / 2
  return { x: cx - (w * visible) / 2, y: cy - h / 2, w, h }
}

/** Bounding box of rack rectangles (metres). */
export function racksBox(racks) {
  if (!racks.length) return null
  const x1 = Math.min(...racks.map((r) => r.x))
  const y1 = Math.min(...racks.map((r) => r.y))
  const x2 = Math.max(...racks.map((r) => r.x + r.width_m))
  const y2 = Math.max(...racks.map((r) => r.y + r.depth_m))
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 }
}

/** Smallest box holding every given box (nulls ignored). */
export function unionBox(boxes) {
  const list = boxes.filter(Boolean)
  if (!list.length) return null
  const x1 = Math.min(...list.map((b) => b.x))
  const y1 = Math.min(...list.map((b) => b.y))
  const x2 = Math.max(...list.map((b) => b.x + b.w))
  const y2 = Math.max(...list.map((b) => b.y + b.h))
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 }
}

/** `box` grown by the given margins (metres). */
export const growBox = (box, { left = 0, right = 0, top = 0, bottom = 0 }) =>
  box && { x: box.x - left, y: box.y - top, w: box.w + left + right, h: box.h + top + bottom }

// Floating UI may cover at most this share of the map's width or height when framing
const MAX_COVERED = 0.75

/**
 * View that shows `box` (metres) in the part of the map that floating UI does not cover.
 * `size` is the map container in px; `insets` are the px covered on each side (the detail
 * panel on the right, the agent reply at the bottom, a bottom sheet on small screens).
 * The box is grown by `scale` for context, at least `minVisibleW` metres stay visible,
 * and the box is centred in the uncovered part.
 */
export function frameView(box, size, { insets = {}, scale = 1, minVisibleW = 0, maxW = Infinity } = {}) {
  const W = size.w
  const H = size.h
  const fit = (a, b, total) => {
    const covered = a + b
    const cap = total * MAX_COVERED
    return covered <= cap ? [a, b] : [(a * cap) / covered, (b * cap) / covered]
  }
  const [left, right] = fit(insets.left || 0, insets.right || 0, W)
  const [top, bottom] = fit(insets.top || 0, insets.bottom || 0, H)
  const visW = W - left - right
  const visH = H - top - bottom
  const w = clamp(
    Math.max((box.w * scale * W) / visW, (box.h * scale * W) / visH, (minVisibleW * W) / visW),
    MIN_VIEW_W,
    Math.max(MIN_VIEW_W, maxW),
  )
  const mpp = w / W
  const cx = box.x + box.w / 2
  const cy = box.y + box.h / 2
  return { x: cx - (left + visW / 2) * mpp, y: cy - (top + visH / 2) * mpp, w, h: H * mpp }
}

export const lerpView = (a, b, t) => ({
  x: a.x + (b.x - a.x) * t,
  y: a.y + (b.y - a.y) * t,
  w: a.w + (b.w - a.w) * t,
  h: a.h + (b.h - a.h) * t,
})

/** Scale-bar length: a round number of metres that is 50–130 px long at this zoom. */
export function scaleBar(metresPerPx) {
  for (const m of [1, 2, 5, 10, 20, 50, 100]) {
    const px = m / metresPerPx
    if (px >= 50) return { metres: m, px: Math.min(px, 130), feet: Math.round(m * 3.281) }
  }
  return { metres: 100, px: 100 / metresPerPx, feet: 328 }
}
