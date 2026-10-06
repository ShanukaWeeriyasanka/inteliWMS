// zod mirror of database/twin/ui_command.schema.json — every incoming command
// (agent answer, realtime row, mock agent, clicks) is validated before it can
// touch the map.
import { z } from 'zod'

const productId = z.string().regex(/^PRD-\d{5}$/, 'must look like PRD-00002')
const floorId = z.string().regex(/^WH\d+-F\d+$/, 'must look like WH1-F2')
const navNodeId = z.string().regex(/^WH\d+-F\d+-N\d{3}$/)
const locationId = z
  .string()
  .regex(/^WH\d+(-F\d+(-Z\d{2}(-R\d{2}(-S\d{2}(-B\d{2})?)?)?)?)?$/, 'must look like WH1-F2-Z01-R02')
const routeEndpoint = z.union([locationId, navNodeId, productId])

export const ACTIONS = [
  'locate_product', 'show_location', 'navigate', 'count', 'heatmap',
  'show_alerts', 'clarify', 'not_found', 'clear',
]

const candidate = z
  .strictObject({
    product_id: productId.optional(),
    location_id: locationId.optional(),
    label: z.string(),
    score: z.number().optional(),
  })
  .refine((c) => (c.product_id == null) !== (c.location_id == null), {
    message: 'a candidate needs exactly one of product_id or location_id',
  })

export const uiCommandSchema = z
  .strictObject({
    version: z.enum(['1.0', '1.1']),
    action: z.enum(ACTIONS),
    answer_text: z.string(),
    product_ids: z.array(productId).optional(),
    location_ids: z.array(locationId).optional(),
    floor_id: floorId.optional(),
    scope: z
      .strictObject({
        level: z.enum(['warehouse', 'floor', 'zone', 'rack', 'shelf', 'bin']),
        id: locationId,
      })
      .optional(),
    metric: z.enum(['fill_ratio', 'total_units', 'product_quantity', 'distinct_products']).optional(),
    route: z
      .strictObject({
        from_id: routeEndpoint.optional(),
        to_id: routeEndpoint.optional(),
        prefer: z.enum(['lift', 'stairs', 'fastest']).optional(),
      })
      .optional(),
    alert_types: z.array(z.enum(['low_stock', 'out_of_stock', 'bin_over_capacity'])).optional(),
    candidates: z.array(candidate).optional(),
  })
  .superRefine((c, ctx) => {
    const need = (ok, message) => { if (!ok) ctx.addIssue({ code: 'custom', message }) }
    if (c.action === 'locate_product') need(c.product_ids?.length > 0, 'locate_product needs product_ids')
    if (c.action === 'count') need(!!c.scope, 'count needs a scope')
    if (c.action === 'heatmap') need(!!c.floor_id, 'heatmap needs a floor_id')
    if (c.action === 'show_location') need(c.location_ids?.length > 0, 'show_location needs location_ids')
    if (c.action === 'clarify') need((c.candidates?.length ?? 0) >= 2, 'clarify needs at least 2 candidates')
    if (c.action === 'navigate') need(!!c.route?.to_id, 'navigate needs route.to_id')
  })

/** Validate a payload. Returns { ok: true, command } or { ok: false, error: 'readable message' }. */
export function validateCommand(payload) {
  const res = uiCommandSchema.safeParse(payload)
  if (res.success) return { ok: true, command: res.data }
  const issue = res.error.issues[0]
  const where = issue.path?.length ? `${issue.path.join('.')}: ` : ''
  return { ok: false, error: `Invalid map command — ${where}${issue.message}` }
}

/** Every location / product / node ID a command refers to (for the registry check). */
export function commandIds(cmd) {
  const ids = [...(cmd.product_ids || []), ...(cmd.location_ids || [])]
  if (cmd.floor_id) ids.push(cmd.floor_id)
  if (cmd.scope?.id) ids.push(cmd.scope.id)
  if (cmd.route?.from_id) ids.push(cmd.route.from_id)
  if (cmd.route?.to_id) ids.push(cmd.route.to_id)
  for (const c of cmd.candidates || []) ids.push(c.product_id || c.location_id)
  return [...new Set(ids)]
}
