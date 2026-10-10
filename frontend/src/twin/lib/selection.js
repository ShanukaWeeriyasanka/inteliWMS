import { isWithin } from './ids'

export function productHighlightRows(selection, locationsByProduct) {
  if (selection?.kind !== 'product') return []
  return (selection.highlightProductIds || [selection.id]).flatMap((id) =>
    (locationsByProduct.get(id) || []).filter((row) => row.quantity > 0 &&
      (!selection.locationScopes?.length || selection.locationScopes.some((scope) => isWithin(row.bin_id, scope)))))
}
