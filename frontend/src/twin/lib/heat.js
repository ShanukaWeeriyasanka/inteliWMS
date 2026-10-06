// Sequential single-hue scale (pale → deep green) for the rack heatmap.
export const HEAT_STEPS = ['#EEF7F0', '#CDEBD4', '#A3D8AF', '#6FBE83', '#3F9C57', '#21703A']

export function heatColor(value, max) {
  if (!max || value == null) return HEAT_STEPS[0]
  const t = Math.max(0, Math.min(1, value / max))
  return HEAT_STEPS[Math.min(HEAT_STEPS.length - 1, Math.round(t * (HEAT_STEPS.length - 1)))]
}

export function formatMetric(metric, value) {
  if (value == null) return '–'
  if (metric === 'fill_ratio') return `${Math.round(value * 100)}%`
  return String(value)
}
