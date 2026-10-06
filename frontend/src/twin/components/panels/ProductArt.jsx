// Product picture: the database image_url when there is one, otherwise a
// clean illustration chosen from the product's name and category.
import React, { useState } from 'react'
import { Bolt, Cable, Coffee, Drill, Hand, HardHat, Lightbulb, Milk, Package, PlugZap, Wrench, CircleDot } from 'lucide-react'
import { productArt } from '../../lib/products'

const ICONS = { cable: Cable, plug: PlugZap, bolt: Bolt, wrench: Wrench, drill: Drill, tape: CircleDot, box: Package,
  cup: Coffee, milk: Milk, hand: Hand, helmet: HardHat, bulb: Lightbulb }

export default function ProductArt({ product, size = 'sm' }) {
  const [broken, setBroken] = useState(false)
  const { art, tone } = productArt(product)
  const Icon = ICONS[art] || Package
  if (product?.image_url && !broken) {
    return (
      <span className={`twin-art is-${size} is-photo`}>
        <img src={product.image_url} alt={product.name} onError={() => setBroken(true)} />
      </span>
    )
  }
  return (
    <span className={`twin-art is-${size} tone-${tone}`} aria-hidden="true">
      <Icon size={size === 'lg' ? 64 : 16} strokeWidth={size === 'lg' ? 1.4 : 2} />
    </span>
  )
}
