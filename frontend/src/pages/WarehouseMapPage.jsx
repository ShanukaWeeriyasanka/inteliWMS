import React, { useEffect, useRef, useState, useMemo } from 'react'
import * as THREE from 'three'
import {
  Search,
  Sparkles,
  Navigation,
  Box,
  Truck,
  Layers,
  Crosshair,
  Maximize2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Send,
  Bot,
  User,
  MapPin,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
  Info,
  Shield,
  Snowflake,
  BatteryCharging,
  CornerDownRight,
  Eye,
  PanelLeftClose,
  PanelLeftOpen,
  ArrowUpRight,
  Compass,
  Cpu,
  HelpCircle,
  X
} from 'lucide-react'
import axios from 'axios'

const KNOWLEDGE_API = 'http://localhost:8002'
const BACKEND_API = 'http://localhost:8000'

// Complete Static Fallback Spatial Registry matching agents/knowledge_agent/spatial_registry.py
const SPATIAL_REGISTRY = {
  facility: {
    id: 'WH-01',
    name: 'IntelliWMS Logistics Center & Digital Twin',
  },
  origins: {
    'DOCK-01': { id: 'DOCK-01', name: 'Receiving Dock Door 1', coords: [-22, 0, -22], floor: 1, desc: 'Inbound container unloading bay' },
    'DOCK-02': { id: 'DOCK-02', name: 'Receiving Dock Door 2', coords: [-14, 0, -22], floor: 1, desc: 'Inbound LTL freight dock' },
    'DOCK-04': { id: 'DOCK-04', name: 'Dispatch Dock Door 4', coords: [14, 0, -22], floor: 1, desc: 'Outbound courier dispatch' },
    'DESK-MAIN': { id: 'DESK-MAIN', name: 'Main Dispatch Desk', coords: [-18, 0, -12], floor: 1, desc: 'Supervisor console and RF scanner pickup' },
    'LIFT-MEZZ': { id: 'LIFT-MEZZ', name: 'Mezzanine Freight Lift', coords: [0, 0, -8], floor: 1, desc: 'Vertical access to Floor 2 Mezzanine' }
  },
  zones: {
    'ZONE-A': {
      id: 'ZONE-A',
      name: 'Zone A — High-Bay Storage',
      facilityName: 'Building A (High-Bay Storage)',
      center: [-8.5, 0, 2],
      size: [24, 10, 24],
      floor: 1,
      tag: 'ZONE A',
      color: '#3b82f6',
      desc: 'High-bay racking for heavy palletized goods (Racks 01–08)'
    },
    'ZONE-B': {
      id: 'ZONE-B',
      name: 'Zone B — Bulk Storage & Shipping',
      facilityName: 'Building B (Bulk Distribution)',
      center: [8.5, 0, 2],
      size: [18, 9, 24],
      floor: 1,
      tag: 'ZONE B',
      color: '#8b5cf6',
      desc: 'Bulk reserve storage & outbound dispatch staging (Racks 09–12)'
    },
    'ZONE-C': {
      id: 'ZONE-C',
      name: 'Zone C — Electronics Mezzanine',
      facilityName: 'Building C (Tech Mezzanine)',
      center: [-8.5, 7, 2],
      size: [20, 6, 20],
      floor: 2,
      tag: 'ZONE C (MEZZANINE)',
      color: '#06b6d4',
      desc: 'Floor 2 Mezzanine: ESD-protected small parts & electronics (Racks 13–18)'
    },
    'COLD-VAULT': {
      id: 'COLD-VAULT',
      name: 'Cold-Chain Chilled Vault',
      facilityName: 'Chilled Storage Facility',
      center: [10.5, 7, -2],
      size: [12, 6, 12],
      floor: 2,
      tag: 'COLD VAULT 2°-4°C',
      color: '#0284c7',
      desc: 'Temperature controlled vault maintained strictly at 2°C–4°C (Racks 19–20)'
    },
    'INBOUND-DOCKS': {
      id: 'INBOUND-DOCKS',
      name: 'Inbound Receiving Terminal',
      facilityName: 'Receiving Freight Terminal',
      center: [-18, 0, -22],
      size: [16, 6, 10],
      floor: 1,
      tag: 'INBOUND DOCKS 1-2',
      color: '#10b981',
      desc: 'Container intake & cross-docking'
    },
    'OUTBOUND-DOCKS': {
      id: 'OUTBOUND-DOCKS',
      name: 'Outbound Courier Terminal',
      facilityName: 'Dispatch Logistics Bay',
      center: [14, 0, -22],
      size: [12, 6, 10],
      floor: 1,
      tag: 'OUTBOUND DOCK 4',
      color: '#f59e0b',
      desc: 'Carrier loading & outbound dispatch'
    },
    'MHE-DEPOT': {
      id: 'MHE-DEPOT',
      name: 'MHE Fleet Depot & Chargers',
      facilityName: 'Fleet Station & Charging Hub',
      center: [20, 0, -13],
      size: [10, 4, 12],
      floor: 1,
      tag: 'MHE FLEET DEPOT',
      color: '#f97316',
      desc: 'Forklift and reach truck parking & battery chargers'
    },
    'BAY-11': {
      id: 'BAY-11',
      name: 'Quarantine Staging Bay 11',
      facilityName: 'Quarantine Inspection Facility',
      center: [20, 0, 12],
      size: [10, 5, 10],
      floor: 1,
      tag: 'QUARANTINE BAY 11',
      color: '#ef4444',
      desc: 'Damaged pallet hold and RMA returns inspection'
    }
  },
  racks: {
    'RACK-01': { number: 1, floor: 1, zone: 'Zone A (High-Bay)', aisle: 'Aisle 1', coords: [-16, 0, -4], ucid: 'WH-01:FL-01:ZN-A:AISLE-01:BAY-01' },
    'RACK-02': { number: 2, floor: 1, zone: 'Zone A (High-Bay)', aisle: 'Aisle 1', coords: [-11, 0, -4], ucid: 'WH-01:FL-01:ZN-A:AISLE-01:BAY-02' },
    'RACK-03': { number: 3, floor: 1, zone: 'Zone A (High-Bay)', aisle: 'Aisle 2', coords: [-16, 0, 8], ucid: 'WH-01:FL-01:ZN-A:AISLE-02:BAY-03' },
    'RACK-04': { number: 4, floor: 1, zone: 'Zone A (High-Bay)', aisle: 'Aisle 2', coords: [-11, 0, 8], ucid: 'WH-01:FL-01:ZN-A:AISLE-02:BAY-04' },
    'RACK-05': { number: 5, floor: 1, zone: 'Zone A (High-Bay)', aisle: 'Aisle 3', coords: [-6, 0, -4], ucid: 'WH-01:FL-01:ZN-A:AISLE-03:BAY-05' },
    'RACK-06': { number: 6, floor: 1, zone: 'Zone A (High-Bay)', aisle: 'Aisle 3', coords: [-1, 0, -4], ucid: 'WH-01:FL-01:ZN-A:AISLE-03:BAY-06' },
    'RACK-07': { number: 7, floor: 1, zone: 'Zone A (High-Bay)', aisle: 'Aisle 4', coords: [-6, 0, 8], ucid: 'WH-01:FL-01:ZN-A:AISLE-04:BAY-07' },
    'RACK-08': { number: 8, floor: 1, zone: 'Zone A (High-Bay)', aisle: 'Aisle 4', coords: [-1, 0, 8], ucid: 'WH-01:FL-01:ZN-A:AISLE-04:BAY-08' },
    'RACK-09': { number: 9, floor: 1, zone: 'Zone B (Bulk Storage)', aisle: 'Aisle 7', coords: [6, 0, -4], ucid: 'WH-01:FL-01:ZN-B:AISLE-07:BAY-09' },
    'RACK-10': { number: 10, floor: 1, zone: 'Zone B (Bulk Storage)', aisle: 'Aisle 8', coords: [11, 0, -4], ucid: 'WH-01:FL-01:ZN-B:AISLE-08:BAY-10' },
    'RACK-11': { number: 11, floor: 1, zone: 'Zone B (Bulk Storage)', aisle: 'Aisle 9', coords: [6, 0, 8], ucid: 'WH-01:FL-01:ZN-B:AISLE-09:BAY-11' },
    'RACK-12': { number: 12, floor: 1, zone: 'Zone B (Bulk Storage)', aisle: 'Aisle 10', coords: [11, 0, 8], ucid: 'WH-01:FL-01:ZN-B:AISLE-10:BAY-12' },
    'RACK-13': { number: 13, floor: 2, zone: 'Zone C (Mezzanine Electronics)', aisle: 'Aisle 11', coords: [-14, 7, -4], ucid: 'WH-01:FL-02:ZN-C:AISLE-11:BAY-13' },
    'RACK-14': { number: 14, floor: 2, zone: 'Zone C (Mezzanine Electronics)', aisle: 'Aisle 12', coords: [-9, 7, -4], ucid: 'WH-01:FL-02:ZN-C:AISLE-12:BAY-14' },
    'RACK-15': { number: 15, floor: 2, zone: 'Zone C (Mezzanine Electronics)', aisle: 'Aisle 13', coords: [-14, 7, 6], ucid: 'WH-01:FL-02:ZN-C:AISLE-13:BAY-15' },
    'RACK-16': { number: 16, floor: 2, zone: 'Zone C (Mezzanine Electronics)', aisle: 'Aisle 14', coords: [-9, 7, 6], ucid: 'WH-01:FL-02:ZN-C:AISLE-14:BAY-16' },
    'RACK-17': { number: 17, floor: 2, zone: 'Zone C (Mezzanine Electronics)', aisle: 'Aisle 15', coords: [-4, 7, -4], ucid: 'WH-01:FL-02:ZN-C:AISLE-15:BAY-17' },
    'RACK-18': { number: 18, floor: 2, zone: 'Zone C (Mezzanine Electronics)', aisle: 'Aisle 16', coords: [-4, 7, 6], ucid: 'WH-01:FL-02:ZN-C:AISLE-16:BAY-18' },
    'RACK-19': { number: 19, floor: 2, zone: 'Zone Cold (Chilled Vault)', aisle: 'Cold Aisle 1', coords: [8, 7, -2], ucid: 'WH-01:FL-02:ZN-COLD:COLD-AISLE-01:BAY-19' },
    'RACK-20': { number: 20, floor: 2, zone: 'Zone Cold (Chilled Vault)', aisle: 'Cold Aisle 2', coords: [13, 7, -2], ucid: 'WH-01:FL-02:ZN-COLD:COLD-AISLE-02:BAY-20' }
  },
  equipment: [
    { id: 'EQ-FL-01', name: 'Counterbalance Forklift #1', type: 'FORKLIFT', coords: [18, 0, -16], zone: 'MHE Fleet Depot', status: 'Available • 92% Battery', ucid: 'WH-01:FL-01:ZN-MHE:STATION-01' },
    { id: 'EQ-FL-02', name: 'Counterbalance Forklift #2', type: 'FORKLIFT', coords: [22, 0, -16], zone: 'MHE Fleet Depot', status: 'Available • 88% Battery', ucid: 'WH-01:FL-01:ZN-MHE:STATION-02' },
    { id: 'EQ-RT-01', name: 'High-Reach Narrow Truck #1', type: 'REACH_TRUCK', coords: [18, 0, -10], zone: 'MHE Fleet Depot', status: 'Available • 100% Charged', ucid: 'WH-01:FL-01:ZN-MHE:STATION-03' },
    { id: 'EQ-RT-02', name: 'High-Reach Narrow Truck #2', type: 'REACH_TRUCK', coords: [22, 0, -10], zone: 'MHE Fleet Depot', status: 'In Inspection per SOP-SAF-003', ucid: 'WH-01:FL-01:ZN-MHE:STATION-04' },
    { id: 'EQ-PJ-01', name: 'Electric Pallet Jack #1', type: 'PALLET_JACK', coords: [-3, 0, 15], zone: 'Aisle 4 Staging Bay', status: 'Staged at Cross-dock', ucid: 'WH-01:FL-01:ZN-A:STAGING-PJ1' }
  ],
  products: {
    'SKU-4521': { sku: 'SKU-4521', name: 'Industrial Barcode Scanner', category: 'Electronics', rack_id: 'RACK-16', shelf: 'Shelf B', bin: 'Bin 2', quantity: 42 },
    'SKU-1088': { sku: 'SKU-1088', name: 'Thermal Label Printer', category: 'Electronics', rack_id: 'RACK-10', shelf: 'Shelf A', bin: 'Bin 1', quantity: 18 },
    'SKU-2045': { sku: 'SKU-2045', name: 'Heavy-Duty Hydraulic Jack', category: 'MHE Parts', rack_id: 'RACK-03', shelf: 'Shelf A', bin: 'Bin 1', quantity: 12 },
    'SKU-9012': { sku: 'SKU-9012', name: 'Hazmat Spill Neutralizer Kit', category: 'Safety Gear', rack_id: 'RACK-07', shelf: 'Shelf A', bin: 'Bin 1', quantity: 35 },
    'SKU-7711': { sku: 'SKU-7711', name: 'Chilled Organic Vaccine Reagent', category: 'Cold Chain', rack_id: 'RACK-19', shelf: 'Shelf B', bin: 'Cold Vault', quantity: 50 },
    'SKU-3301': { sku: 'SKU-3301', name: 'Reinforced Pallet Stretch Film', category: 'Packaging', rack_id: 'RACK-01', shelf: 'Shelf A', bin: 'Bin 2', quantity: 80 }
  }
}

// Client-side Spatial Solver (Instant, Robust Fallback)
function resolveSpatialQueryClient(queryText) {
  const q = queryText.toLowerCase().trim()
  
  // 1. Rack query (e.g., 'rack 4', 'rack no 4', 'where is rack 4')
  const rackMatch = q.match(/\brack(?:\s*(?:no\.?|number))?\s*(\d+)\b/)
  if (rackMatch) {
    const rNum = parseInt(rackMatch[1], 10)
    const rKey = `RACK-${String(rNum).padStart(2, '0')}`
    const rack = SPATIAL_REGISTRY.racks[rKey]
    if (rack) {
      return {
        found: true,
        target_type: 'rack',
        name: `Rack #${rack.number}`,
        building: rack.floor === 2 ? 'Building C (Tech Mezzanine)' : (rack.number <= 8 ? 'Building A (High-Bay)' : 'Building B (Bulk Storage)'),
        zone: rack.zone,
        floor: rack.floor,
        aisle: rack.aisle,
        ucid: rack.ucid,
        coordinates: { x: rack.coords[0], y: rack.coords[1], z: rack.coords[2] },
        message: `📍 Rack #${rack.number} is situated on Floor ${rack.floor} in ${rack.zone}, ${rack.aisle}. UCID: ${rack.ucid}.`,
        waypoints: [
          SPATIAL_REGISTRY.origins['DOCK-01'].coords,
          [-18, 0, -4],
          [rack.coords[0], 0, rack.coords[2]]
        ]
      }
    }
  }

  // 2. SKU query
  for (const [skuKey, p] of Object.entries(SPATIAL_REGISTRY.products)) {
    if (q.includes(skuKey.toLowerCase()) || q.includes(p.name.toLowerCase())) {
      const rack = SPATIAL_REGISTRY.racks[p.rack_id]
      return {
        found: true,
        target_type: 'sku',
        name: `${p.name} (${p.sku})`,
        building: rack.floor === 2 ? 'Building C (Tech Mezzanine)' : (rack.number <= 8 ? 'Building A (High-Bay)' : 'Building B (Bulk Storage)'),
        zone: rack.zone,
        floor: rack.floor,
        aisle: `${rack.aisle} • ${p.shelf} / ${p.bin}`,
        ucid: rack.ucid,
        quantity: p.quantity,
        coordinates: { x: rack.coords[0], y: rack.coords[1], z: rack.coords[2] },
        message: `📦 ${p.name} [${p.sku}] is stocked in ${rack.zone}, ${rack.aisle}, ${p.shelf}, ${p.bin} (Rack #${rack.number}). Available Stock: ${p.quantity} units.`,
        waypoints: [
          SPATIAL_REGISTRY.origins['DOCK-01'].coords,
          [-18, 0, -4],
          [rack.coords[0], 0, rack.coords[2]]
        ]
      }
    }
  }

  // 3. Equipment queries
  if (q.includes('forklift') || q.includes('reach truck') || q.includes('mhe') || q.includes('pallet jack') || q.includes('fleet') || q.includes('depot')) {
    if (q.includes('1') || q.includes('first')) {
      const eq = SPATIAL_REGISTRY.equipment[0]
      return {
        found: true,
        target_type: 'equipment_single',
        name: eq.name,
        building: 'MHE Fleet Depot & Charging Station',
        zone: eq.zone,
        floor: 1,
        ucid: eq.ucid,
        status: eq.status,
        coordinates: { x: eq.coords[0], y: eq.coords[1], z: eq.coords[2] },
        message: `🚜 ${eq.name} is parked at Station 1 in the MHE Fleet Depot. Status: ${eq.status}.`,
        waypoints: [
          SPATIAL_REGISTRY.origins['DESK-MAIN'].coords,
          [0, 0, -12],
          [eq.coords[0], 0, eq.coords[2]]
        ]
      }
    }
    const allEq = SPATIAL_REGISTRY.equipment
    return {
      found: true,
      target_type: 'equipment_fleet',
      name: 'Warehouse MHE Fleet',
      building: 'MHE Fleet Depot & Charging Hub',
      zone: 'MHE Fleet Depot (East Wing)',
      floor: 1,
      ucid: 'WH-01:FL-01:ZN-MHE:FLEET-GROUP',
      all_pins: allEq,
      coordinates: { x: 20, y: 0, z: -13 },
      message: `🚜 MHE Fleet Status: 5 active units (2 Counterbalance Forklifts, 2 Reach Trucks, 1 Electric Pallet Jack) spotlighted at the Fleet Depot.`,
      waypoints: [
        SPATIAL_REGISTRY.origins['DESK-MAIN'].coords,
        [0, 0, -12],
        [20, 0, -13]
      ]
    }
  }

  // 4. Special Zones
  if (q.includes('bay 11') || q.includes('quarantine') || q.includes('rma') || q.includes('return')) {
    const z = SPATIAL_REGISTRY.zones['BAY-11']
    return {
      found: true,
      target_type: 'special_zone',
      name: z.name,
      building: z.facilityName,
      zone: 'Quarantine Inspection',
      floor: 1,
      ucid: 'WH-01:FL-01:ZN-RET:BAY-11',
      coordinates: { x: z.center[0], y: z.center[1], z: z.center[2] },
      message: `⚠️ Quarantine Bay 11 is located in the East Logistics Yard. Dedicated for damaged pallets & RMA returns per SOP-RET-004.`,
      waypoints: [
        SPATIAL_REGISTRY.origins['DOCK-04'].coords,
        [14, 0, 0],
        [z.center[0], 0, z.center[2]]
      ]
    }
  }

  if (q.includes('cold') || q.includes('chilled') || q.includes('vault') || q.includes('freezer')) {
    const z = SPATIAL_REGISTRY.zones['COLD-VAULT']
    return {
      found: true,
      target_type: 'special_zone',
      name: z.name,
      building: z.facilityName,
      zone: 'Cold Chain Vault (Floor 2)',
      floor: 2,
      ucid: 'WH-01:FL-02:ZN-COLD:VAULT',
      coordinates: { x: z.center[0], y: z.center[1], z: z.center[2] },
      message: `❄️ Chilled Storage Vault is located on Floor 2. Temperature maintained strictly between 2°C and 4°C for perishables and reagents.`,
      waypoints: [
        SPATIAL_REGISTRY.origins['LIFT-MEZZ'].coords,
        [8, 7, -8],
        [z.center[0], 7, z.center[2]]
      ]
    }
  }

  if (q.includes('dock 1') || q.includes('receiving') || q.includes('dock 2') || q.includes('inbound')) {
    const d = SPATIAL_REGISTRY.origins['DOCK-01']
    return {
      found: true,
      target_type: 'dock',
      name: d.name,
      building: 'Receiving Freight Terminal',
      zone: 'Inbound Logistics West',
      floor: 1,
      ucid: 'WH-01:FL-01:ZN-DOCK:DOOR-01',
      coordinates: { x: d.coords[0], y: d.coords[1], z: d.coords[2] },
      message: `🚛 Receiving Dock Door 1 is active on the West Perimeter. Configured for 40ft container intake and cross-dock unloading.`,
      waypoints: [
        SPATIAL_REGISTRY.origins['DESK-MAIN'].coords,
        [-18, 0, -18],
        [d.coords[0], 0, d.coords[2]]
      ]
    }
  }

  if (q.includes('dock 4') || q.includes('dispatch') || q.includes('outbound')) {
    const d = SPATIAL_REGISTRY.origins['DOCK-04']
    return {
      found: true,
      target_type: 'dock',
      name: d.name,
      building: 'Dispatch Courier Logistics Bay',
      zone: 'Outbound Logistics East',
      floor: 1,
      ucid: 'WH-01:FL-01:ZN-DOCK:DOOR-04',
      coordinates: { x: d.coords[0], y: d.coords[1], z: d.coords[2] },
      message: `📦 Dispatch Dock Door 4 is active on the East Perimeter. Staged for courier line-haul and outbound trailer departures.`,
      waypoints: [
        [0, 0, 0],
        [14, 0, -10],
        [d.coords[0], 0, d.coords[2]]
      ]
    }
  }

  return null
}

export default function WarehouseMapPage() {
  const mountRef = useRef(null)
  const sceneRef = useRef(null)
  const cameraRef = useRef(null)
  const rendererRef = useRef(null)
  const animFrameRef = useRef(null)
  const controlsRef = useRef({
    isDragging: false,
    prevX: 0,
    prevY: 0,
    rotX: Math.PI / 6,
    rotY: -Math.PI / 4,
    distance: 260,
    panX: 0,
    panZ: 0,
    targetPanX: 0,
    targetPanZ: 0
  })

  // State
  const [activeFloor, setActiveFloor] = useState('ALL') // 'ALL', '1', '2', 'FLEET'
  const [showLabels, setShowLabels] = useState(true)
  const [chatOpen, setChatOpen] = useState(true)
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      text: 'Hello! I am your Warehouse Spatial Assistant. I can pinpoint racks, inventory items, equipment, and storage bays across the digital twin. Ask me a question or pick a suggested query below!',
      timestamp: new Date()
    }
  ])
  const [inputQuery, setInputQuery] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [activeTarget, setActiveTarget] = useState(null)
  const [hoveredBuilding, setHoveredBuilding] = useState(null)

  const beaconGroupRef = useRef(null)
  const pathMeshRef = useRef(null)
  const buildingMeshesRef = useRef([])

  // Setup broadcast channel & URL parameter listening
  useEffect(() => {
    const bc = new BroadcastChannel('intelliwms_map_channel')
    bc.onmessage = (event) => {
      if (event.data?.type === 'LOCATE_TARGET' && event.data?.payload) {
        handleApplyLocationTarget(event.data.payload)
      }
    }

    const params = new URLSearchParams(window.location.search)
    const targetParam = params.get('target')
    if (targetParam) {
      handleUserSubmit(`where is ${targetParam}`)
    } else {
      // Default initial spotlight: Rack #4
      setTimeout(() => {
        const defaultTarget = resolveSpatialQueryClient('where is rack no 4')
        if (defaultTarget) handleApplyLocationTarget(defaultTarget)
      }, 500)
    }

    return () => bc.close()
  }, [])

  // Three.js Scene Setup
  useEffect(() => {
    if (!mountRef.current) return
    const container = mountRef.current
    const width = container.clientWidth
    const height = container.clientHeight

    const scene = new THREE.Scene()
    // Sleek modern slate/fog background (High contrast, vibrant, NOT washed out)
    scene.background = new THREE.Color(0xf1f5f9)
    scene.fog = new THREE.FogExp2(0xf1f5f9, 0.0018)
    sceneRef.current = scene

    // Camera setup - zoomed in for grand, crisp, recognizable warehouse scale
    const aspect = width / height
    const zoom = 75
    const camera = new THREE.OrthographicCamera(-zoom * aspect, zoom * aspect, zoom, -zoom, -1000, 1000)
    cameraRef.current = camera

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.15
    container.innerHTML = ''
    container.appendChild(renderer.domElement)
    rendererRef.current = renderer

    // Rich Dynamic Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.75)
    scene.add(ambientLight)

    const sunLight = new THREE.DirectionalLight(0xffffff, 1.4)
    sunLight.position.set(150, 250, 120)
    sunLight.castShadow = true
    sunLight.shadow.mapSize.width = 4096
    sunLight.shadow.mapSize.height = 4096
    sunLight.shadow.camera.left = -300
    sunLight.shadow.camera.right = 300
    sunLight.shadow.camera.top = 300
    sunLight.shadow.camera.bottom = -300
    sunLight.shadow.bias = -0.0005
    sunLight.shadow.normalBias = 0.02
    scene.add(sunLight)

    const softFill = new THREE.DirectionalLight(0x93c5fd, 0.45)
    softFill.position.set(-150, 80, -150)
    scene.add(softFill)

    // Ground Platform: Dark tarmac with high contrast markings
    const groundGeo = new THREE.PlaneGeometry(800, 800)
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0xe2e8f0,
      roughness: 0.9,
      metalness: 0.05
    })
    const ground = new THREE.Mesh(groundGeo, groundMat)
    ground.rotation.x = -Math.PI / 2
    ground.position.y = -0.2
    ground.receiveShadow = true
    scene.add(ground)

    // Crisp Grid Lines
    const grid = new THREE.GridHelper(600, 60, 0x94a3b8, 0xcfd8e3)
    grid.position.y = -0.15
    scene.add(grid)

    // Build the Logistics Park Facilities
    buildingMeshesRef.current = []
    buildLogisticsCampus(scene)

    // Animation Loop
    let clock = new THREE.Clock()
    const animate = () => {
      animFrameRef.current = requestAnimationFrame(animate)
      const elapsedTime = clock.getElapsedTime()

      // Smooth camera pan interpolation
      const c = controlsRef.current
      c.panX += (c.targetPanX - c.panX) * 0.08
      c.panZ += (c.targetPanZ - c.panZ) * 0.08

      const r = c.distance
      camera.position.x = c.panX + r * Math.sin(c.rotY) * Math.cos(c.rotX)
      camera.position.y = r * Math.sin(c.rotX)
      camera.position.z = c.panZ + r * Math.cos(c.rotY) * Math.cos(c.rotX)
      camera.lookAt(c.panX, 0, c.panZ)

      // Animate Target Beacon
      if (beaconGroupRef.current) {
        const beacon = beaconGroupRef.current
        const pulse = 1.0 + Math.sin(elapsedTime * 4) * 0.15
        const rings = beacon.getObjectByName('radarRings')
        if (rings) {
          rings.scale.set(pulse, 1, pulse)
          rings.children.forEach((ring, idx) => {
            ring.rotation.z += 0.01 * (idx + 1)
          })
        }
        const beam = beacon.getObjectByName('verticalBeam')
        if (beam) {
          beam.material.opacity = 0.4 + Math.sin(elapsedTime * 6) * 0.2
        }
        const pin = beacon.getObjectByName('pinHead')
        if (pin) {
          pin.position.y = 18 + Math.sin(elapsedTime * 3) * 1.5
        }
      }

      renderer.render(scene, camera)
    }
    animate()

    // Interactive mouse drag to orbit and pan
    const onMouseDown = (e) => {
      controlsRef.current.isDragging = true
      controlsRef.current.prevX = e.clientX
      controlsRef.current.prevY = e.clientY
      controlsRef.current.button = e.button
    }

    const onMouseMove = (e) => {
      if (!controlsRef.current.isDragging) return
      const dx = e.clientX - controlsRef.current.prevX
      const dy = e.clientY - controlsRef.current.prevY
      controlsRef.current.prevX = e.clientX
      controlsRef.current.prevY = e.clientY

      if (controlsRef.current.button === 0) {
        // Orbit
        controlsRef.current.rotY -= dx * 0.006
        controlsRef.current.rotX = Math.max(0.15, Math.min(Math.PI / 2.3, controlsRef.current.rotX + dy * 0.006))
      } else if (controlsRef.current.button === 2) {
        // Pan
        const factor = 0.4
        controlsRef.current.targetPanX -= (dx * Math.cos(controlsRef.current.rotY) - dy * Math.sin(controlsRef.current.rotY)) * factor
        controlsRef.current.targetPanZ -= (dx * Math.sin(controlsRef.current.rotY) + dy * Math.cos(controlsRef.current.rotY)) * factor
      }
    }

    const onMouseUp = () => {
      controlsRef.current.isDragging = false
    }

    const onWheel = (e) => {
      e.preventDefault()
      const factor = e.deltaY > 0 ? 1.1 : 0.9
      const newZoom = Math.max(40, Math.min(300, zoom * factor))
      camera.left = -newZoom * (container.clientWidth / container.clientHeight)
      camera.right = newZoom * (container.clientWidth / container.clientHeight)
      camera.top = newZoom
      camera.bottom = -newZoom
      camera.updateProjectionMatrix()
    }

    const onContextMenu = (e) => e.preventDefault()

    const dom = renderer.domElement
    dom.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    dom.addEventListener('wheel', onWheel, { passive: false })
    dom.addEventListener('contextmenu', onContextMenu)

    const handleResize = () => {
      if (!container) return
      const w = container.clientWidth
      const h = container.clientHeight
      renderer.setSize(w, h)
      const a = w / h
      camera.left = -zoom * a
      camera.right = zoom * a
      camera.top = zoom
      camera.bottom = -zoom
      camera.updateProjectionMatrix()
    }
    window.addEventListener('resize', handleResize)

    return () => {
      cancelAnimationFrame(animFrameRef.current)
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      dom.removeEventListener('mousedown', onMouseDown)
      dom.removeEventListener('wheel', onWheel)
      dom.removeEventListener('contextmenu', onContextMenu)
      renderer.dispose()
    }
  }, [])

  // Construct Detailed 3D Logistics Platform Campus
  const buildLogisticsCampus = (scene) => {
    // 1. Roadways & Aprons
    const roadMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.9 })
    const lineMat = new THREE.MeshBasicMaterial({ color: 0xffffff })
    const yellowMat = new THREE.MeshBasicMaterial({ color: 0xf59e0b })

    const addRoad = (x, z, w, d) => {
      const road = new THREE.Mesh(new THREE.PlaneGeometry(w, d), roadMat)
      road.rotation.x = -Math.PI / 2
      road.position.set(x, 0.02, z)
      road.receiveShadow = true
      scene.add(road)
    }

    // Access Roads
    addRoad(0, -32, 180, 14) // North Perimeter Transport Lane
    addRoad(-32, 0, 14, 160) // West Freight Corridor
    addRoad(34, 0, 14, 160)  // East Equipment & Logistics Corridor
    addRoad(0, 28, 180, 12)  // South Dispatch Arterial

    // Road Markings (Dashed central stripes)
    const addStripe = (x, z, w, d, isYellow = false) => {
      const stripe = new THREE.Mesh(new THREE.PlaneGeometry(w, d), isYellow ? yellowMat : lineMat)
      stripe.rotation.x = -Math.PI / 2
      stripe.position.set(x, 0.04, z)
      scene.add(stripe)
    }
    addStripe(0, -32, 160, 0.8)
    addStripe(-32, 0, 0.8, 140)
    addStripe(34, 0, 0.8, 140)

    // 2. High-Tech Buildings with architectural contrast
    const whiteWallMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.25,
      metalness: 0.08
    })
    const charcoalBaseMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.4,
      metalness: 0.2
    })
    const glassMat = new THREE.MeshPhysicalMaterial({
      color: 0x38bdf8,
      roughness: 0.1,
      metalness: 0.2,
      transmission: 0.6,
      transparent: true,
      opacity: 0.85
    })
    const roofTrimMat = new THREE.MeshStandardMaterial({
      color: 0x475569,
      roughness: 0.5
    })
    const coldMat = new THREE.MeshStandardMaterial({
      color: 0xe0f2fe,
      roughness: 0.2,
      metalness: 0.1
    })

    const createWarehouseFacility = ({ id, name, tag, x, z, w, d, h, floor = 1, isCold = false, isQuarantine = false }) => {
      const group = new THREE.Group()
      group.position.set(x, 0, z)
      group.userData = { id, name, tag, floor, coords: [x, 0, z] }

      // Main Architectural Block
      const bodyMat = isCold ? coldMat : whiteWallMat
      const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), bodyMat)
      body.position.y = h / 2
      body.castShadow = true
      body.receiveShadow = true
      group.add(body)

      // Charcoal Foundation Plinth
      const plinth = new THREE.Mesh(new THREE.BoxGeometry(w + 1.2, 0.8, d + 1.2), charcoalBaseMat)
      plinth.position.y = 0.4
      plinth.receiveShadow = true
      group.add(plinth)

      // Upper Roof Coping & Trim
      const roof = new THREE.Mesh(new THREE.BoxGeometry(w + 0.6, 0.6, d + 0.6), roofTrimMat)
      roof.position.y = h + 0.3
      roof.castShadow = true
      group.add(roof)

      // Roof Skylights & HVAC Units
      const hvacGeo = new THREE.BoxGeometry(3, 1.2, 3)
      const hvac = new THREE.Mesh(hvacGeo, charcoalBaseMat)
      hvac.position.set(-w * 0.25, h + 1, -d * 0.2)
      hvac.castShadow = true
      group.add(hvac)

      const skylight = new THREE.Mesh(new THREE.BoxGeometry(w * 0.5, 0.2, d * 0.3), glassMat)
      skylight.position.set(0, h + 0.7, 0)
      group.add(skylight)

      // Glass Office Facade Ribbon
      const ribbonGeo = new THREE.BoxGeometry(w * 0.7, 1.8, 0.4)
      const ribbon = new THREE.Mesh(ribbonGeo, glassMat)
      ribbon.position.set(0, h * 0.6, d / 2 + 0.21)
      group.add(ribbon)

      // Roll-Up Dock Doors on the front
      const doorCount = Math.floor(w / 7)
      for (let i = 0; i < doorCount; i++) {
        const doorX = -w / 2 + 4 + i * 7
        const door = new THREE.Mesh(new THREE.PlaneGeometry(4.5, 4), charcoalBaseMat)
        door.position.set(doorX, 2, d / 2 + 0.05)
        group.add(door)

        // Yellow warning stripe above dock door
        const warningStripe = new THREE.Mesh(new THREE.PlaneGeometry(4.5, 0.4), yellowMat)
        warningStripe.position.set(doorX, 4.3, d / 2 + 0.06)
        group.add(warningStripe)
      }

      // Edge Highlights for Crisp Visual Geometry
      const edges = new THREE.EdgesGeometry(new THREE.BoxGeometry(w, h, d))
      const lineMesh = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: isCold ? 0x0284c7 : 0x94a3b8 }))
      lineMesh.position.y = h / 2
      group.add(lineMesh)

      // Special Quarantine Chevron Trim if applicable
      if (isQuarantine) {
        const hazardGeo = new THREE.PlaneGeometry(w + 3, d + 3)
        const hazardMat = new THREE.MeshBasicMaterial({ color: 0xef4444, transparent: true, opacity: 0.15 })
        const hazardPlane = new THREE.Mesh(hazardGeo, hazardMat)
        hazardPlane.rotation.x = -Math.PI / 2
        hazardPlane.position.y = 0.05
        group.add(hazardPlane)
      }

      scene.add(group)
      buildingMeshesRef.current.push(group)
      return group
    }

    // Build the Main Facilities
    // 1. Building A — Zone A (High-Bay Storage)
    createWarehouseFacility({
      id: 'ZONE-A',
      name: 'Building A (High-Bay)',
      tag: 'ZONE A',
      x: -8.5,
      z: 2,
      w: 24,
      d: 22,
      h: 11,
      floor: 1
    })

    // 2. Building B — Zone B (Bulk Storage & Fulfillment)
    createWarehouseFacility({
      id: 'ZONE-B',
      name: 'Building B (Bulk Reserve)',
      tag: 'ZONE B',
      x: 10,
      z: 2,
      w: 18,
      d: 22,
      h: 10,
      floor: 1
    })

    // 3. Building C — Zone C (Electronics Mezzanine Floor 2)
    createWarehouseFacility({
      id: 'ZONE-C',
      name: 'Mezzanine Tech Facility',
      tag: 'ZONE C',
      x: -8.5,
      z: -16,
      w: 22,
      d: 14,
      h: 12,
      floor: 2
    })

    // 4. Cold Storage Vault
    createWarehouseFacility({
      id: 'COLD-VAULT',
      name: 'Cold-Chain Chilled Vault',
      tag: 'COLD VAULT',
      x: 12,
      z: -16,
      w: 14,
      d: 14,
      h: 9,
      floor: 2,
      isCold: true
    })

    // 5. Inbound Receiving Docks 1 & 2
    createWarehouseFacility({
      id: 'INBOUND-DOCKS',
      name: 'Inbound Receiving Terminal',
      tag: 'DOCKS 1-2',
      x: -20,
      z: -26,
      w: 18,
      d: 10,
      h: 7,
      floor: 1
    })

    // 6. Outbound Dispatch Dock 4
    createWarehouseFacility({
      id: 'OUTBOUND-DOCKS',
      name: 'Outbound Courier Terminal',
      tag: 'DOCK 4',
      x: 16,
      z: -26,
      w: 16,
      d: 10,
      h: 7,
      floor: 1
    })

    // 7. MHE Fleet Depot & Chargers
    createWarehouseFacility({
      id: 'MHE-DEPOT',
      name: 'MHE Fleet Depot & Chargers',
      tag: 'MHE FLEET',
      x: 23,
      z: -8,
      w: 12,
      d: 14,
      h: 6,
      floor: 1
    })

    // 8. Quarantine Staging Bay 11
    createWarehouseFacility({
      id: 'BAY-11',
      name: 'Quarantine Staging Bay 11',
      tag: 'BAY 11',
      x: 23,
      z: 14,
      w: 12,
      d: 14,
      h: 6,
      floor: 1,
      isQuarantine: true
    })

    // Parked Trucks & Equipment for realistic logistics feel
    addParkedTrailer(scene, -20, -32, 0)
    addParkedTrailer(scene, -14, -32, 0)
    addParkedTrailer(scene, 16, -32, 0)

    // Add MHE Forklifts Models in the depot
    addMHEModel(scene, 21, -14, 0x3b82f6)
    addMHEModel(scene, 25, -14, 0x3b82f6)
    addMHEModel(scene, 21, -8, 0x10b981)
  }

  // Semi-Trailer 3D Model
  const addParkedTrailer = (scene, x, z, rot) => {
    const group = new THREE.Group()
    group.position.set(x, 0, z)
    group.rotation.y = rot

    // Trailer Box
    const boxMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.3 })
    const box = new THREE.Mesh(new THREE.BoxGeometry(4.2, 4.2, 12), boxMat)
    box.position.y = 2.8
    box.castShadow = true
    group.add(box)

    // Wheels
    const wheelMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.8 })
    const wheelGeo = new THREE.CylinderGeometry(0.8, 0.8, 0.6, 12)
    const w1 = new THREE.Mesh(wheelGeo, wheelMat)
    w1.rotation.z = Math.PI / 2
    w1.position.set(1.9, 0.8, 3.5)
    group.add(w1)
    const w2 = new THREE.Mesh(wheelGeo, wheelMat)
    w2.rotation.z = Math.PI / 2
    w2.position.set(-1.9, 0.8, 3.5)
    group.add(w2)

    scene.add(group)
  }

  // Forklift 3D Model
  const addMHEModel = (scene, x, z, colorHex) => {
    const group = new THREE.Group()
    group.position.set(x, 0, z)

    const mat = new THREE.MeshStandardMaterial({ color: colorHex, roughness: 0.3 })
    const chassis = new THREE.Mesh(new THREE.BoxGeometry(2, 1.4, 3), mat)
    chassis.position.y = 0.9
    chassis.castShadow = true
    group.add(chassis)

    // Mast
    const mast = new THREE.Mesh(new THREE.BoxGeometry(0.3, 3, 0.3), new THREE.MeshStandardMaterial({ color: 0x1e293b }))
    mast.position.set(0.6, 1.8, 1.6)
    group.add(mast)
    const mast2 = new THREE.Mesh(new THREE.BoxGeometry(0.3, 3, 0.3), new THREE.MeshStandardMaterial({ color: 0x1e293b }))
    mast2.position.set(-0.6, 1.8, 1.6)
    group.add(mast2)

    // Forks
    const fork = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.1, 1.8), new THREE.MeshStandardMaterial({ color: 0x475569 }))
    fork.position.set(0.5, 0.2, 2.4)
    group.add(fork)
    const fork2 = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.1, 1.8), new THREE.MeshStandardMaterial({ color: 0x475569 }))
    fork2.position.set(-0.5, 0.2, 2.4)
    group.add(fork2)

    scene.add(group)
  }

  // Handle Location Target Highlight & Pin Drop
  const handleApplyLocationTarget = (target) => {
    setActiveTarget(target)
    if (!sceneRef.current || !target.coordinates) return

    const { x, y = 0, z } = target.coordinates

    // 1. Remove previous beacon and path
    if (beaconGroupRef.current) {
      sceneRef.current.remove(beaconGroupRef.current)
      beaconGroupRef.current = null
    }
    if (pathMeshRef.current) {
      sceneRef.current.remove(pathMeshRef.current)
      pathMeshRef.current = null
    }

    // 2. Build High-Visibility Vibrant Location Indicator Pin
    const beacon = new THREE.Group()
    beacon.position.set(x, 0, z)

    // Concentric Pulsing Radar Rings on Floor
    const ringsGroup = new THREE.Group()
    ringsGroup.name = 'radarRings'
    const ringMat1 = new THREE.MeshBasicMaterial({ color: 0x2563eb, side: THREE.DoubleSide })
    const ring1 = new THREE.Mesh(new THREE.RingGeometry(2.5, 3.2, 32), ringMat1)
    ring1.rotation.x = -Math.PI / 2
    ring1.position.y = 0.2
    ringsGroup.add(ring1)

    const ringMat2 = new THREE.MeshBasicMaterial({ color: 0x60a5fa, side: THREE.DoubleSide })
    const ring2 = new THREE.Mesh(new THREE.RingGeometry(4.5, 5.0, 32), ringMat2)
    ring2.rotation.x = -Math.PI / 2
    ring2.position.y = 0.18
    ringsGroup.add(ring2)
    beacon.add(ringsGroup)

    // Vertical Holographic Light Beam
    const beamGeo = new THREE.CylinderGeometry(0.8, 1.5, 45, 16, 1, true)
    const beamMat = new THREE.MeshBasicMaterial({
      color: 0x3b82f6,
      transparent: true,
      opacity: 0.55,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending
    })
    const beam = new THREE.Mesh(beamGeo, beamMat)
    beam.name = 'verticalBeam'
    beam.position.y = 22.5
    beacon.add(beam)

    // Floating 3D Pin Head (Distinct high-visibility diamond/sphere)
    const pinHead = new THREE.Group()
    pinHead.name = 'pinHead'
    pinHead.position.y = 18

    const pinSphere = new THREE.Mesh(
      new THREE.SphereGeometry(2.4, 24, 24),
      new THREE.MeshStandardMaterial({
        color: 0x2563eb,
        emissive: 0x1d4ed8,
        emissiveIntensity: 0.5,
        roughness: 0.2,
        metalness: 0.8
      })
    )
    pinSphere.castShadow = true
    pinHead.add(pinSphere)

    // Target Crosshair Ring around pin
    const crossRing = new THREE.Mesh(
      new THREE.TorusGeometry(3.6, 0.3, 12, 32),
      new THREE.MeshBasicMaterial({ color: 0x60a5fa })
    )
    crossRing.rotation.x = Math.PI / 2
    pinHead.add(crossRing)

    beacon.add(pinHead)

    sceneRef.current.add(beacon)
    beaconGroupRef.current = beacon

    // 3. Draw Dynamic Glowing Wayfinding Corridor Line
    let waypoints = target.waypoints
    if (!waypoints || waypoints.length === 0) {
      waypoints = [
        [-22, 0, -22], // Origin (Dock 1)
        [-22, 0, z],
        [x, 0, z]
      ]
    }

    const points = waypoints.map((w) => new THREE.Vector3(w[0], 0.6, w[2]))
    if (points.length >= 2) {
      const curve = new THREE.CatmullRomCurve3(points, false, 'catmullrom', 0.15)
      
      // Main Core Tube
      const tubeGeo = new THREE.TubeGeometry(curve, 64, 0.9, 8, false)
      const tubeMat = new THREE.MeshBasicMaterial({ color: 0x2563eb })
      const tubeMesh = new THREE.Mesh(tubeGeo, tubeMat)

      // Outer Neon Glow
      const glowGeo = new THREE.TubeGeometry(curve, 64, 2.0, 8, false)
      const glowMat = new THREE.MeshBasicMaterial({
        color: 0x93c5fd,
        transparent: true,
        opacity: 0.45,
        blending: THREE.AdditiveBlending
      })
      const glowMesh = new THREE.Mesh(glowGeo, glowMat)
      tubeMesh.add(glowMesh)

      sceneRef.current.add(tubeMesh)
      pathMeshRef.current = tubeMesh
    }

    // 4. Smooth Camera Focus Glide
    controlsRef.current.targetPanX = x
    controlsRef.current.targetPanZ = z
  }

  // Submit Prompt to AI Agent
  const handleUserSubmit = async (queryText) => {
    const text = (queryText || inputQuery).trim()
    if (!text) return

    // Add user message to chat stream
    const userMsg = {
      id: Date.now(),
      role: 'user',
      text: text,
      timestamp: new Date()
    }
    setMessages((prev) => [...prev, userMsg])
    setInputQuery('')
    setIsProcessing(true)

    try {
      // 1. Try real Knowledge Agent backend endpoint first
      let resolvedTarget = null
      let agentReply = ''

      try {
        const res = await axios.post(`${KNOWLEDGE_API}/query`, {
          query: text,
          user_role: 'staff'
        })
        if (res.data?.status === 'success' && res.data.spatial_target?.found) {
          resolvedTarget = res.data.spatial_target
          agentReply = res.data.response || res.data.spatial_target.formatted_message
        }
      } catch (err) {
        // Fallback to client-side spatial solver
      }

      // 2. Client-side spatial solver if backend didn't return spatial target
      if (!resolvedTarget) {
        resolvedTarget = resolveSpatialQueryClient(text)
      }

      if (resolvedTarget) {
        handleApplyLocationTarget(resolvedTarget)
        const botMsg = {
          id: Date.now() + 1,
          role: 'assistant',
          text: resolvedTarget.message || `Found target: ${resolvedTarget.name}. Location highlighted on map!`,
          target: resolvedTarget,
          timestamp: new Date()
        }
        setMessages((prev) => [...prev, botMsg])
      } else {
        const botMsg = {
          id: Date.now() + 1,
          role: 'assistant',
          text: `I couldn't locate "${text}" in the warehouse spatial twin. Try asking for "Rack 4", "SKU-4521", "Forklifts", "Quarantine Bay 11", or "Cold Storage".`,
          timestamp: new Date()
        }
        setMessages((prev) => [...prev, botMsg])
      }
    } catch (e) {
      console.error(e)
    } finally {
      setIsProcessing(false)
    }
  }

  // Reset Camera View
  const handleResetCamera = () => {
    controlsRef.current.rotX = Math.PI / 6
    controlsRef.current.rotY = -Math.PI / 4
    controlsRef.current.targetPanX = 0
    controlsRef.current.targetPanZ = 0
  }

  // Preset suggested queries
  const SUGGESTIONS = [
    { label: '📍 Where is Rack #4?', query: 'Where is rack no 4?' },
    { label: '📦 Locate SKU-4521', query: 'Where is SKU-4521?' },
    { label: '🚜 Where are the Forklifts?', query: 'Where are the forklifts?' },
    { label: '⚠️ Quarantine Bay 11', query: 'Where is quarantine bay 11?' },
    { label: '❄️ Cold Storage Vault', query: 'Locate cold storage vault' },
    { label: '🚛 Receiving Dock 1', query: 'Where is Receiving Dock 1?' },
    { label: '🏷️ Thermal Label Printer', query: 'Where is Thermal Label Printer?' }
  ]

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-slate-900 font-sans text-slate-800 flex flex-col select-none">
      
      {/* Top Header / Status Navigation */}
      <header className="h-16 bg-white/95 backdrop-blur-md border-b border-slate-200/80 shadow-sm flex items-center justify-between px-6 z-30 shrink-0">
        
        {/* Left: Brand & Status */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setChatOpen(!chatOpen)}
            className="p-2 hover:bg-slate-100 rounded-lg text-slate-600 transition"
            title="Toggle Agent Chat Drawer"
          >
            {chatOpen ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeftOpen className="w-5 h-5 text-blue-600" />}
          </button>

          <div className="w-8 h-8 bg-blue-600 rounded-xl flex items-center justify-center text-white shadow-md shadow-blue-500/20">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-[14px] text-slate-900 tracking-tight">IntelliWMS</span>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                3D SPATIAL TWIN
              </span>
            </div>
            <div className="text-[11px] text-slate-500 font-medium flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>Facility WH-01 • Real-time Wayfinding</span>
            </div>
          </div>
        </div>

        {/* Center: Quick Search Bar */}
        <div className="flex-1 max-w-xl mx-8">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleUserSubmit(inputQuery)
            }}
            className="relative flex items-center w-full"
          >
            <Search className="absolute left-3.5 w-4 h-4 text-blue-500" />
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Ask agent: 'Where is rack no 4?' or 'Locate SKU-4521'..."
              className="w-full bg-slate-100/70 hover:bg-slate-100 focus:bg-white border border-slate-200 text-[13px] py-2 pl-10 pr-24 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all font-medium text-slate-800 placeholder:text-slate-400"
            />
            <button
              type="submit"
              disabled={isProcessing}
              className="absolute right-1.5 top-1 bottom-1 bg-blue-600 hover:bg-blue-700 text-white px-3.5 rounded-lg text-[11px] font-bold transition flex items-center gap-1 shadow-sm"
            >
              {isProcessing ? 'Locating...' : 'Locate'}
            </button>
          </form>
        </div>

        {/* Right: Actions & Return */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowLabels(!showLabels)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border flex items-center gap-1.5 transition ${
              showLabels
                ? 'bg-blue-50 border-blue-200 text-blue-700'
                : 'bg-slate-50 border-slate-200 text-slate-600'
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            <span>{showLabels ? 'Labels On' : 'Labels Off'}</span>
          </button>

          <button
            onClick={handleResetCamera}
            className="p-2 hover:bg-slate-100 rounded-lg text-slate-600 border border-slate-200 transition"
            title="Reset Isometric Camera"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <button
            onClick={() => (window.location.href = '/')}
            className="px-3.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-bold transition shadow-sm flex items-center gap-1.5"
          >
            <span>Operations Portal</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {/* Main Workspace Stage */}
      <div className="flex flex-1 overflow-hidden relative">
        
        {/* Left Side: Knowledge Agent Interactive Chat Panel */}
        {chatOpen && (
          <aside className="w-[380px] h-full bg-white/95 backdrop-blur-xl border-r border-slate-200/80 shadow-xl flex flex-col z-20 shrink-0 animate-in slide-in-from-left duration-200">
            
            {/* Chat Panel Header */}
            <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-blue-600/10 text-blue-600 flex items-center justify-center border border-blue-200">
                  <Bot className="w-4 h-4" />
                </div>
                <div>
                  <h2 className="text-[14px] font-bold text-slate-900 leading-tight">Knowledge Agent</h2>
                  <p className="text-[11px] text-slate-500 font-medium">Spatial Twin & SOP Co-pilot</p>
                </div>
              </div>
              <span className="text-[10px] font-bold font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                PORT 8002 READY
              </span>
            </div>

            {/* Quick Suggestions Chips */}
            <div className="p-3 bg-slate-50 border-b border-slate-100 overflow-x-auto whitespace-nowrap flex gap-1.5 scrollbar-thin">
              {SUGGESTIONS.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => handleUserSubmit(item.query)}
                  className="px-2.5 py-1 bg-white hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200 border border-slate-200 rounded-md text-[11px] font-semibold text-slate-600 transition shrink-0"
                >
                  {item.label}
                </button>
              ))}
            </div>

            {/* Message Thread */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}
                >
                  <div
                    className={`max-w-[90%] rounded-2xl p-3.5 text-[13px] leading-relaxed shadow-sm ${
                      m.role === 'user'
                        ? 'bg-blue-600 text-white rounded-br-xs'
                        : 'bg-slate-100 text-slate-800 rounded-bl-xs border border-slate-200/80'
                    }`}
                  >
                    <p className="font-medium">{m.text}</p>

                    {/* Rich Spatial Target Card attached to bot response */}
                    {m.target && (
                      <div className="mt-3 pt-3 border-t border-slate-200/60 bg-white rounded-xl p-3 shadow-xs text-slate-800">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-bold text-[13px] text-blue-600 flex items-center gap-1.5">
                            <MapPin className="w-3.5 h-3.5 fill-current" />
                            {m.target.name}
                          </span>
                          <span className="text-[10px] font-mono bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-bold">
                            Floor {m.target.floor}
                          </span>
                        </div>

                        <div className="text-[11px] space-y-1 text-slate-600">
                          <div>
                            <span className="font-semibold text-slate-500">Building:</span>{' '}
                            {m.target.building || (m.target.floor === 2 ? 'Building C (Mezzanine)' : 'Facility WH-01 Main Campus')}
                          </div>
                          <div>
                            <span className="font-semibold text-slate-500">Zone / Aisle:</span>{' '}
                            {m.target.zone || m.target.aisle || 'Zone A'}
                          </div>
                          {m.target.ucid && (
                            <div className="font-mono text-[10px] bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200 text-slate-700">
                              UCID: {m.target.ucid}
                            </div>
                          )}
                          {m.target.coordinates && (
                            <div className="font-mono text-[10px] text-slate-500">
                              Coords: X {m.target.coordinates.x.toFixed(1)}, Z {m.target.coordinates.z.toFixed(1)}
                            </div>
                          )}
                        </div>

                        <button
                          onClick={() => handleApplyLocationTarget(m.target)}
                          className="mt-2.5 w-full bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-bold py-1.5 rounded-lg transition flex items-center justify-center gap-1"
                        >
                          <Crosshair className="w-3.5 h-3.5" />
                          <span>Spotlight on 3D Map</span>
                        </button>
                      </div>
                    )}
                  </div>
                  <span className="text-[10px] text-slate-400 mt-1 px-1">
                    {new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              ))}
            </div>

            {/* Chat Input Box */}
            <div className="p-3 border-t border-slate-200 bg-white">
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  handleUserSubmit(inputQuery)
                }}
                className="relative flex items-center"
              >
                <input
                  type="text"
                  value={inputQuery}
                  onChange={(e) => setInputQuery(e.target.value)}
                  placeholder="Ask location (e.g. 'Where is rack 4?')..."
                  className="w-full bg-slate-50 border border-slate-200 text-[13px] py-2.5 pl-3.5 pr-12 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium text-slate-800"
                />
                <button
                  type="submit"
                  disabled={isProcessing}
                  className="absolute right-2 top-1.5 bottom-1.5 w-9 bg-blue-600 hover:bg-blue-700 text-white rounded-lg flex items-center justify-center transition shadow-sm"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </form>
            </div>
          </aside>
        )}

        {/* 3D WebGL Canvas Layer */}
        <div ref={mountRef} className="absolute inset-0 z-0 cursor-grab active:cursor-grabbing" />

        {/* Floating 3D Facility Labels (HTML Overlays on top of buildings) */}
        {showLabels && (
          <div className="absolute inset-0 pointer-events-none z-10 overflow-hidden">
            {Object.entries(SPATIAL_REGISTRY.zones).map(([key, zone]) => (
              <div
                key={key}
                className="absolute transition-all duration-300"
                style={{
                  // Position calibrated for zoom 75 isometric projection
                  left: `calc(50% + ${zone.center[0] * 10.8 + zone.center[2] * -10.8}px)`,
                  top: `calc(46% + ${zone.center[0] * 6.3 + zone.center[2] * 6.3 - zone.floor * 24}px)`
                }}
              >
                <div className="transform -translate-x-1/2 -translate-y-1/2 pointer-events-auto">
                  <button
                    onClick={() => handleUserSubmit(`where is ${zone.name}`)}
                    className="bg-white/95 hover:bg-blue-600 hover:text-white backdrop-blur-md px-2.5 py-1 rounded-md text-[10px] font-bold text-slate-800 shadow-md border border-slate-200/80 transition flex items-center gap-1.5 hover:scale-105"
                  >
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: zone.color }}
                    ></span>
                    <span>{zone.tag}</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Floating Camera & Control Stack (Top Right) */}
        <div className="absolute right-6 top-6 z-20 bg-white/95 backdrop-blur-md border border-slate-200/80 shadow-md rounded-xl flex flex-col overflow-hidden text-slate-600">
          <button
            onClick={handleResetCamera}
            className="p-3 hover:bg-blue-50 hover:text-blue-600 border-b border-slate-100 transition"
            title="Reset Isometric Angle"
          >
            <Compass className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              if (activeTarget?.coordinates) {
                controlsRef.current.targetPanX = activeTarget.coordinates.x
                controlsRef.current.targetPanZ = activeTarget.coordinates.z
              }
            }}
            className="p-3 hover:bg-blue-50 hover:text-blue-600 border-b border-slate-100 transition"
            title="Focus On Active Target"
          >
            <Crosshair className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowLabels(!showLabels)}
            className="p-3 hover:bg-blue-50 hover:text-blue-600 transition"
            title="Toggle Building Labels"
          >
            <Layers className="w-4 h-4" />
          </button>
        </div>

        {/* Floating Floor Selector Tabs (Bottom Center) */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 bg-white/95 backdrop-blur-md border border-slate-200 shadow-lg rounded-full flex items-center p-1 text-[12px] font-bold text-slate-600">
          <button
            onClick={() => {
              setActiveFloor('ALL')
              handleResetCamera()
            }}
            className={`px-4 py-2 rounded-full transition flex items-center gap-1.5 ${
              activeFloor === 'ALL' ? 'bg-slate-900 text-white shadow-sm' : 'hover:text-slate-900'
            }`}
          >
            <div className="w-2 h-2 rounded-full bg-blue-500"></div>
            <span>All Facilities</span>
          </button>

          <button
            onClick={() => {
              setActiveFloor('1')
              handleUserSubmit('where is rack no 4')
            }}
            className={`px-4 py-2 rounded-full transition ${
              activeFloor === '1' ? 'bg-slate-900 text-white shadow-sm' : 'hover:text-slate-900'
            }`}
          >
            Floor 1 (Heavy Bay)
          </button>

          <button
            onClick={() => {
              setActiveFloor('2')
              handleUserSubmit('where is SKU-4521')
            }}
            className={`px-4 py-2 rounded-full transition ${
              activeFloor === '2' ? 'bg-slate-900 text-white shadow-sm' : 'hover:text-slate-900'
            }`}
          >
            Floor 2 (Mezzanine & Cold)
          </button>

          <button
            onClick={() => {
              setActiveFloor('FLEET')
              handleUserSubmit('where are the forklifts')
            }}
            className={`px-4 py-2 rounded-full transition ${
              activeFloor === 'FLEET' ? 'bg-slate-900 text-white shadow-sm' : 'hover:text-slate-900'
            }`}
          >
            MHE Fleet Depot
          </button>
        </div>

        {/* Active Target Floating Pin HUD Card (Anchored gracefully beside the chat drawer) */}
        {activeTarget && (
          <div
            className={`absolute bottom-6 ${
              chatOpen ? 'left-[396px]' : 'left-6'
            } z-20 bg-white/95 backdrop-blur-xl border border-slate-200/90 shadow-2xl rounded-2xl p-4 w-[360px] transition-all duration-200 animate-in slide-in-from-bottom-4`}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-200 shadow-xs">
                  {activeTarget.target_type === 'equipment_fleet' || activeTarget.target_type === 'equipment_single' ? (
                    <Truck className="w-5 h-5" />
                  ) : activeTarget.name?.includes('Cold') ? (
                    <Snowflake className="w-5 h-5 text-cyan-600" />
                  ) : (
                    <Box className="w-5 h-5" />
                  )}
                </div>
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-blue-600">
                    Active Location Spotlight
                  </span>
                  <h3 className="font-bold text-[15px] text-slate-900 leading-tight">
                    {activeTarget.name}
                  </h3>
                </div>
              </div>
              <button
                onClick={() => setActiveTarget(null)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-3 text-[12px] text-slate-600 leading-relaxed font-medium bg-slate-50/80 p-2.5 rounded-xl border border-slate-100">
              {activeTarget.message}
            </div>

            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] font-mono">
              <div className="bg-slate-100/70 p-2 rounded-lg border border-slate-200">
                <span className="text-slate-400 block text-[9px] uppercase font-sans font-bold">Floor Level</span>
                <span className="font-bold text-slate-800">Floor {activeTarget.floor || 1}</span>
              </div>
              <div className="bg-slate-100/70 p-2 rounded-lg border border-slate-200">
                <span className="text-slate-400 block text-[9px] uppercase font-sans font-bold">Coordinates</span>
                <span className="font-bold text-slate-800">
                  X: {activeTarget.coordinates?.x.toFixed(1)}, Z: {activeTarget.coordinates?.z.toFixed(1)}
                </span>
              </div>
            </div>

            {activeTarget.ucid && (
              <div className="mt-2 text-[10px] font-mono bg-blue-50/70 text-blue-800 p-1.5 rounded-lg border border-blue-200 flex items-center justify-between">
                <span>{activeTarget.ucid}</span>
                <span className="text-blue-500 font-bold uppercase text-[9px]">Verified UCID</span>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
