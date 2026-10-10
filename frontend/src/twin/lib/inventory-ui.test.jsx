import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import FloorMap from '../components/map/FloorMap'
import { ProductDetail } from '../components/panels/DetailPanel'
import InventoryPanel from '../components/panels/InventoryPanel'

function fixture() {
  const shelf={id:'WH2-F1-Z01-R01-S01',rack_id:'WH2-F1-Z01-R01',level_index:1}
  const bins=[1,2].map((i) => ({id:`${shelf.id}-B0${i}`,shelf_id:shelf.id,position_index:i,status:'active'}))
  const rack={id:shelf.rack_id,name:'Rack 1',type:'crate_rack',floor_id:'WH2-F1',x:2,y:2,width_m:5,depth_m:5}
  const row={product_id:'PRD-00002',bin_id:bins[1].id,rack_id:rack.id,rack_name:rack.name,
    rack_x:2,rack_y:2,rack_width_m:5,rack_depth_m:5,shelf_id:shelf.id,level_index:1,position_index:2,
    capacity_units:40,floor_id:'WH2-F1',floor_name:'Floor 1',warehouse_id:'WH2',warehouse_name:'Second warehouse',
    zone_name:'Zone A',quantity:7,available_quantity:4,reserved_quantity:2,quarantined_quantity:1,
    updated_at:'2026-10-09T10:00:00Z',location_label:'Second warehouse · Floor 1 · Zone A · Rack 1 · Shelf 1 · Bin 2'}
  const layout={floorsById:new Map([['WH2-F1',{name:'Floor 1',width_m:20,height_m:20}]]),
    zonesByFloor:new Map(),racksByFloor:new Map([['WH2-F1',[rack]]]),nodesByFloor:new Map(),
    rackGrid:new Map([[rack.id,{shelves:[shelf],cols:2}]]),binsByShelf:new Map([[shelf.id,bins]]),
    racksById:new Map([[rack.id,rack]])}
  return {bins,row,layout}
}

describe('inventory UI data agreement', () => {
  it('labels alert provenance and unassigned stock without implying a warehouse assignment', () => {
    const {layout,row}=fixture()
    const product={product_id:row.product_id,name:'Imported printer',unit:'pcs',data_source:'imported',
      updated_at:row.updated_at,total_quantity:15,available_quantity:13,reserved_quantity:2,unplaced_quantity:15}
    const data={layout:{...layout,raw:{warehouses:[]}},products:[product],locationsByProduct:new Map(),
      fillByRack:new Map(),alerts:[{id:1,product_id:row.product_id,product_name:product.name,
        level:'warning',created_at:row.updated_at,message:'15 left, reorder point 20'}]}
    const html=renderToStaticMarkup(<InventoryPanel data={data} floorId="WH2-F1" tab="alerts" query="" />)
    expect(html).toContain('All warehouses')
    expect(html).toContain('imported')
    expect(html).toContain('15 pcs awaiting bin assignment')
    expect(html).toContain('13 available')
  })
  it('highlights only the exact box, using the supplied floor and stock values', () => {
    const {bins,row,layout}=fixture()
    const html=renderToStaticMarkup(<FloorMap svgRef={{current:null}} layout={layout} edges={[]}
      floorId="WH2-F1" vb={{x:0,y:0,w:20,h:20}} markers={[]} binQty={new Map([[row.bin_id,7]])}
      view={{highlight:new Set([row.rack_id]),targetBins:new Set([row.bin_id]),targetShelves:new Set(),
        badges:new Map(),alertRacks:new Set(),flash:new Map()}}
      route={{segments:[]}} registry={{current:new Map()}} reducedMotion />)
    expect(html).toContain(`data-loc-id="${bins[1].id}"`)
    expect(html.match(/class="twin-cell is-target"/g)).toHaveLength(1)
    expect(html).toContain(`data-loc-id="${bins[0].id}"`)
  })
  it('lists full locations across warehouses with quantity breakdowns and provenance', () => {
    const {row,layout}=fixture()
    const second={...row,bin_id:'WH1-F2-Z01-R02-S03-B04',floor_id:'WH1-F2',quantity:3,
      location_label:'First warehouse · Floor 2 · Rack 2 · Shelf 3 · Bin 4'}
    const product={product_id:'PRD-00002',product_no:2,sku:'EL-PWR-65W',name:'Power Adapter',
      total_quantity:10,available_quantity:7,reserved_quantity:2,quarantined_quantity:1,
      unit:'pcs',reorder_point:2,data_source:'demo',updated_at:row.updated_at}
    const html=renderToStaticMarkup(<ProductDetail product={product} rows={[row,second]} layout={layout}
      focusBinId={row.bin_id} reducedMotion />)
    expect(html).toContain('Second warehouse')
    expect(html).toContain('First warehouse')
    expect(html).toContain(row.bin_id)
    expect(html).toContain(second.bin_id)
    expect(html).toContain('Available 7')
    expect(html).toContain('Reserved 2')
    expect(html).toContain('Quarantined 1')
    expect(html).toContain('demo')
    expect(html).toContain(row.updated_at)
  })
})
