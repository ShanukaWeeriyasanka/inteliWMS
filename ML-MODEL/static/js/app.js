let activeInventoryList = [];
let currentOrionData = null;
let debounceTimer = null;
let currentTimeline = '3M';

document.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  refreshAllData();

  window.addEventListener('resize', () => {
    renderDynamicFlowRibbons();
  });

  const flowStage = document.getElementById('flowStageContainer');
  if (flowStage && window.ResizeObserver) {
    new ResizeObserver(() => {
      renderDynamicFlowRibbons();
    }).observe(flowStage);
  }
});

// ──────────────────────────────────────────────
// 1. Data Refresh Orchestrator
// ──────────────────────────────────────────────
async function refreshAllData() {
  await Promise.all([
    loadOrionOverview(),
    loadDatasetList(),
    loadProcurementQueue(),
    loadClearanceCandidates(),
  ]);
  lucide.createIcons();
}

// ──────────────────────────────────────────────
// 2. Tab Navigation
// ──────────────────────────────────────────────
function switchTab(tabId) {
  const panes = document.querySelectorAll('.tab-pane');
  panes.forEach(p => p.classList.add('hidden'));

  const activePane = document.getElementById(`tab-${tabId}`);
  if (activePane) activePane.classList.remove('hidden');

  const buttons = document.querySelectorAll('.nav-tab-btn');
  buttons.forEach(btn => {
    btn.className = 'nav-tab-btn px-3.5 py-1.5 rounded-full transition flex items-center gap-1.5 text-slate-400 hover:text-white font-medium';
  });

  const activeBtn = document.getElementById(`tab-btn-${tabId}`);
  if (activeBtn) {
    activeBtn.className = 'nav-tab-btn active px-3.5 py-1.5 rounded-full transition flex items-center gap-1.5 bg-[#4F46E5] text-white shadow-md shadow-indigo-500/30 font-semibold';
  }

  lucide.createIcons();
  if (tabId === 'overview') {
    requestAnimationFrame(() => {
      renderDynamicFlowRibbons();
    });
  }
}

function setTimeline(tl) {
  currentTimeline = tl;
  ['1W', '1M', '3M', '1Y', 'ALL'].forEach(t => {
    const btn = document.getElementById(`tBtn-${t}`);
    if (btn) {
      if (t === tl) {
        btn.className = 'px-2.5 py-1 text-xs rounded-full font-bold bg-[#4F46E5] text-white shadow-sm transition';
      } else {
        btn.className = 'px-2.5 py-1 text-xs rounded-full font-medium text-slate-400 hover:text-white transition';
      }
    }
  });
  showToast(`Switched timeline window to ${tl}`);
}

// ──────────────────────────────────────────────
// 3. Dynamic Ribbon Engine (Zero-Drift Vector Flow)
// ──────────────────────────────────────────────
function renderDynamicFlowRibbons() {
  const container = document.getElementById('flowStageContainer');
  const svg = document.getElementById('orionRibbonCanvas');
  const leftGroup = document.getElementById('leftDemandNodesContainer');
  const centerDisc = document.getElementById('centerDiscElement');
  const rightGroup = document.getElementById('rightHealthNodesContainer');
  const ribbonGroup = document.getElementById('ribbonPathsGroup');
  const laserGroup = document.getElementById('laserPathsGroup');

  if (!container || !svg || !leftGroup || !centerDisc || !rightGroup || !ribbonGroup || !laserGroup) return;

  const leftCards = leftGroup.querySelectorAll('.flow-node');
  const rightCards = rightGroup.querySelectorAll('.flow-node');
  if (leftCards.length === 0 || rightCards.length === 0) return;

  const cRect = container.getBoundingClientRect();
  if (cRect.width <= 0 || cRect.height <= 0) return;

  // Set 1:1 pixel coordinate space
  svg.setAttribute('viewBox', `0 0 ${cRect.width} ${cRect.height}`);

  const dRect = centerDisc.getBoundingClientRect();
  const discRadius = dRect.width / 2;
  const discCenterX = (dRect.left + discRadius) - cRect.left;
  const discCenterY = (dRect.top + discRadius) - cRect.top;
  const ribbonThickness = 12;

  let ribbonHtml = '';
  let laserHtml = '';

  // 1. INFLOWING: Left Stream Cards -> Center Disc
  // Disperse angles smoothly around the rim so ribbons do not pinch together
  leftCards.forEach((card, idx) => {
    const cardRect = card.getBoundingClientRect();
    const xStart = cardRect.right - cRect.left;
    const yStart = (cardRect.top + cardRect.height / 2) - cRect.top;

    // Contact anchor on left rim of disc: spread across ~70 degrees
    const angleRad = Math.PI + ((idx - 1.5) * 0.42);
    const xEnd = discCenterX + Math.cos(angleRad) * discRadius;
    const yEnd = discCenterY + Math.sin(angleRad) * discRadius;

    // Smooth Bézier control points
    const cpDx = Math.max(35, (xEnd - xStart) * 0.52);
    const cp1x = xStart + cpDx;
    const cp1y = yStart;
    const cp2x = xEnd - cpDx;
    const cp2y = yEnd;

    const gradId = `flowGradL${idx % 4}`;
    const halfTh = ribbonThickness / 2;
    const ribbonD = `M ${xStart.toFixed(1)},${(yStart - halfTh).toFixed(1)} C ${cp1x.toFixed(1)},${(yStart - halfTh).toFixed(1)} ${cp2x.toFixed(1)},${(yEnd - halfTh).toFixed(1)} ${xEnd.toFixed(1)},${(yEnd - halfTh).toFixed(1)} L ${xEnd.toFixed(1)},${(yEnd + halfTh).toFixed(1)} C ${cp2x.toFixed(1)},${(yEnd + halfTh).toFixed(1)} ${cp1x.toFixed(1)},${(yStart + halfTh).toFixed(1)} ${xStart.toFixed(1)},${(yStart + halfTh).toFixed(1)} Z`;

    ribbonHtml += `<path class="ribbon-path" fill="url(#${gradId})" fill-opacity="0.65" d="${ribbonD}" />`;
    laserHtml += `<path class="laser-line" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round" stroke-dasharray="6,8" opacity="0.8" fill="none" d="M ${xStart.toFixed(1)},${yStart.toFixed(1)} C ${cp1x.toFixed(1)},${yStart.toFixed(1)} ${cp2x.toFixed(1)},${yEnd.toFixed(1)} ${xEnd.toFixed(1)},${yEnd.toFixed(1)}" />`;
  });

  // 2. OUTFLOWING: Center Disc -> Right Stream Cards
  rightCards.forEach((card, idx) => {
    const cardRect = card.getBoundingClientRect();
    const xEnd = cardRect.left - cRect.left;
    const yEnd = (cardRect.top + cardRect.height / 2) - cRect.top;

    // Contact anchor on right rim of disc: spread across ~70 degrees
    const angleRad = (idx - 1.5) * 0.42;
    const xStart = discCenterX + Math.cos(angleRad) * discRadius;
    const yStart = discCenterY + Math.sin(angleRad) * discRadius;

    const cpDx = Math.max(35, (xEnd - xStart) * 0.52);
    const cp1x = xStart + cpDx;
    const cp1y = yStart;
    const cp2x = xEnd - cpDx;
    const cp2y = yEnd;

    const gradId = `flowGradR${idx % 4}`;
    const halfTh = ribbonThickness / 2;
    const ribbonD = `M ${xStart.toFixed(1)},${(yStart - halfTh).toFixed(1)} C ${cp1x.toFixed(1)},${(yStart - halfTh).toFixed(1)} ${cp2x.toFixed(1)},${(yEnd - halfTh).toFixed(1)} ${xEnd.toFixed(1)},${(yEnd - halfTh).toFixed(1)} L ${xEnd.toFixed(1)},${(yEnd + halfTh).toFixed(1)} C ${cp2x.toFixed(1)},${(yEnd + halfTh).toFixed(1)} ${cp1x.toFixed(1)},${(yStart + halfTh).toFixed(1)} ${xStart.toFixed(1)},${(yStart + halfTh).toFixed(1)} Z`;

    ribbonHtml += `<path class="ribbon-path" fill="url(#${gradId})" fill-opacity="0.65" d="${ribbonD}" />`;
    laserHtml += `<path class="laser-line" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round" stroke-dasharray="6,8" opacity="0.8" fill="none" d="M ${xStart.toFixed(1)},${yStart.toFixed(1)} C ${cp1x.toFixed(1)},${yStart.toFixed(1)} ${cp2x.toFixed(1)},${yEnd.toFixed(1)} ${xEnd.toFixed(1)},${yEnd.toFixed(1)}" />`;
  });

  ribbonGroup.innerHTML = ribbonHtml;
  laserGroup.innerHTML = laserHtml;
}

// ──────────────────────────────────────────────
// 4. Tab 1: ORION Data Visualisation Loader
// ──────────────────────────────────────────────
async function loadOrionOverview() {
  try {
    const res = await fetch('/api/orion-overview');
    if (!res.ok) throw new Error('Failed to load Orion overview data');
    const d = await res.json();
    currentOrionData = d;

    // A. Left Sidebar Card 1: Monthly Best Seller
    const topSku = d.top_selling_sku || {};
    document.getElementById('sbTopVal').textContent = topSku.revenue || '$1,875';
    document.getElementById('sbTopSku').textContent = topSku.sku || 'JNE3797-KR-L';
    document.getElementById('sbTopCategory').textContent = `${topSku.category || 'Western Dress'} · Size ${topSku.size || 'L'}`;
    document.getElementById('sbTopUnits').textContent = `${topSku.total_units_sold || 274} Units Sold`;

    // B. Left Sidebar Card 2: Concentric 3-Ring Donut Gauge (140x140: r=58, 48, 38)
    const rings = d.health_rings || {};
    document.getElementById('sbTotalEarning').textContent = rings.total_active_stock || '$8,952';
    document.getElementById('sbHealthyPct').textContent = `${rings.healthy_pct || 68}%`;
    document.getElementById('sbLowPct').textContent = `${rings.low_stock_pct || 21}%`;
    document.getElementById('sbCritPct').textContent = `${rings.critical_pct || 11}%`;

    // Ring 1 (r=58, circ=364.42)
    const healthyOffset = 364.42 * (1 - (rings.healthy_pct || 68) / 100);
    const ringH = document.getElementById('gaugeRingHealthy');
    if (ringH) ringH.style.strokeDashoffset = healthyOffset;

    // Ring 2 (r=48, circ=301.59)
    const lowOffset = 301.59 * (1 - (rings.low_stock_pct || 21) / 100);
    const ringL = document.getElementById('gaugeRingLow');
    if (ringL) ringL.style.strokeDashoffset = lowOffset;

    // Ring 3 (r=38, circ=238.76)
    const critOffset = 238.76 * (1 - (rings.critical_pct || 11) / 100);
    const ringC = document.getElementById('gaugeRingCritical');
    if (ringC) ringC.style.strokeDashoffset = critOffset;

    // Mini breakdown list (Dark Jet Black styling)
    const breakdownEl = document.getElementById('sbCategoryBreakdownList');
    if (breakdownEl && rings.breakdown) {
      breakdownEl.innerHTML = '';
      rings.breakdown.slice(0, 4).forEach(b => {
        const row = document.createElement('div');
        row.className = 'flex items-center justify-between text-[11px] py-1 border-b border-white/5 last:border-none';
        row.innerHTML = `
          <span class="font-semibold text-slate-300">${b.label}</span>
          <div class="flex items-center gap-2 font-mono text-[10px]">
            <span class="text-slate-400 font-medium">${b.stock} st</span>
            <span class="text-[#818CF8] font-bold">${b.demand} dem</span>
          </div>
        `;
        breakdownEl.appendChild(row);
      });
    }

    // C. Left Sidebar Card 3: Total Reorder Plan
    document.getElementById('sbReorderPlanVal').textContent = d.procurement_total || '$120,875';

    // D. Center Hero Stage: Central Focal Disc
    const hub = d.center_hub || {};
    renderCenterHub(hub);

    // E. Left Demand Nodes (4 Categories - Dark iOS Frosted Glass Nodes)
    const leftContainer = document.getElementById('leftDemandNodesContainer');
    if (leftContainer && d.left_demand_streams) {
      leftContainer.innerHTML = '';
      d.left_demand_streams.forEach((s) => {
        const card = document.createElement('div');
        card.className = 'flow-node p-2.5 transition group';
        card.onclick = () => selectCategoryStream(s.category);
        card.innerHTML = `
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-bold text-white group-hover:text-[#818CF8] transition truncate max-w-[100px]">${s.category}</span>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full border shadow-xs" style="background-color: ${s.color}25; color: ${s.color}; border-color: ${s.color}40">
              ${s.share}
            </span>
          </div>
          <div class="flex items-baseline justify-between font-mono">
            <span class="text-xs font-bold text-white">${s.units} u</span>
            <span class="text-[11px] font-semibold text-slate-300">${s.revenue}</span>
          </div>
        `;
        leftContainer.appendChild(card);
      });
    }

    // F. Right Health Outcome Nodes (4 States - Dark iOS Frosted Glass Nodes)
    const rightContainer = document.getElementById('rightHealthNodesContainer');
    if (rightContainer && d.right_health_streams) {
      rightContainer.innerHTML = '';
      d.right_health_streams.forEach((h) => {
        const card = document.createElement('div');
        card.className = 'flow-node p-2.5 transition group';
        card.onclick = () => {
          if (h.status.includes('Critical') || h.status.includes('Low')) switchTab('procurement');
          else if (h.status.includes('Aged')) switchTab('clearance');
        };
        card.innerHTML = `
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-bold text-white group-hover:text-[#818CF8] transition truncate max-w-[100px]">${h.status}</span>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full border shadow-xs" style="background-color: ${h.color}25; color: ${h.color}; border-color: ${h.color}40">
              ${h.sku_count} SKUs
            </span>
          </div>
          <div class="flex items-baseline justify-between font-mono">
            <span class="text-xs font-bold text-white">${h.units_needed > 0 ? h.units_needed + ' req' : 'Balanced'}</span>
            <span class="text-[11px] font-semibold text-slate-300">${h.capital}</span>
          </div>
        `;
        rightContainer.appendChild(card);
      });
    }

    // G. Bottom Strip Stats
    const bMetrics = d.bottom_metrics || {};
    const pulseNum = parseInt(bMetrics.velocity_pulse) || 438;
    document.getElementById('stripPulseNum').textContent = pulseNum;
    document.getElementById('stripPredNum').textContent = hub.forecast_7d_units ? Math.round(hub.forecast_7d_units * 3.2) : 875;
    document.getElementById('stripActiveSkus').textContent = bMetrics.active_skus || '16 SKUs';

    // Measure and render ribbons cleanly
    requestAnimationFrame(() => {
      renderDynamicFlowRibbons();
    });

  } catch (err) {
    console.error('Error loading Orion overview:', err);
  }
}

// ──────────────────────────────────────────────
// 5. Central Hub Renderer & Dynamic Styling
// ──────────────────────────────────────────────
function renderCenterHub(hub) {
  document.getElementById('centerTargetSku').textContent = hub.sku || 'WD-LUXE-042';
  document.getElementById('centerForecastUnits').textContent = hub.forecast_7d_units || 15;
  
  const stockStr = `${hub.current_stock || 3} In Stock`;
  const revStr = hub.revenue_val ? ` • ${hub.revenue_val}` : ' • $821';
  document.getElementById('centerStockSub').textContent = `${stockStr}${revStr}`;

  const runwayStr = hub.runway_days ? `${hub.runway_days}d Runway` : '1.4d Runway';
  const leadStr = hub.lead_time_days ? ` • ${hub.lead_time_days}d Lead` : ' • 5d Lead';
  document.getElementById('centerRunwayPill').textContent = `${runwayStr}${leadStr}`;

  // Health Status Pill styling (iOS Embossed Glow Badge)
  const pill = document.getElementById('centerStatusPill');
  const status = (hub.status || 'HEALTHY').toUpperCase();

  if (status.includes('HEALTHY')) {
    pill.className = 'px-2.5 py-0.5 rounded-full text-[9px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-xs flex items-center gap-1 transition-all';
    pill.innerHTML = '<span>● HEALTHY</span>';
  } else if (status.includes('LOW') || status.includes('REORDER')) {
    pill.className = 'px-2.5 py-0.5 rounded-full text-[9px] font-bold bg-orange-500/20 text-orange-400 border border-orange-500/40 shadow-xs flex items-center gap-1 transition-all';
    pill.innerHTML = '<span>● LOW STOCK</span>';
  } else {
    pill.className = 'px-2.5 py-0.5 rounded-full text-[9px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40 shadow-xs flex items-center gap-1 transition-all';
    pill.innerHTML = '<span>● OVERDUE / CRITICAL</span>';
  }

  requestAnimationFrame(() => {
    renderDynamicFlowRibbons();
  });
}

// ──────────────────────────────────────────────
// 5. Interactive SKU Search & Stream Selection
// ──────────────────────────────────────────────
function handleSkuSearchInput(e) {
  const q = e.target.value.trim();
  const clearBtn = document.getElementById('clearSearchBtn');
  if (clearBtn) clearBtn.classList.toggle('hidden', q.length === 0);

  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    if (!q) return;
    const match = activeInventoryList.find(i => 
      i.sku.toLowerCase().includes(q.toLowerCase()) || 
      i.category.toLowerCase().includes(q.toLowerCase())
    );
    if (match) {
      focusSkuInCenterHub(match);
    }
  }, 300);
}

function clearSearchInput() {
  const input = document.getElementById('orionSkuSearch');
  if (input) {
    input.value = '';
    document.getElementById('clearSearchBtn').classList.add('hidden');
  }
}

async function focusSkuInCenterHub(skuItem) {
  try {
    const res = await fetch('/api/predict-sku', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sku: skuItem.sku,
        category: skuItem.category,
        size: skuItem.size,
        current_stock: skuItem.current_stock,
        lead_time_days: skuItem.lead_time_days || 3,
        sales_last_7d: skuItem.sales_last_7d || 15.0,
        sales_last_14d: skuItem.sales_last_14d || 28.0,
        sales_lag_1: skuItem.sales_lag_1 || 3.0,
        zero_days_last_14d: skuItem.zero_days_last_14d || 2.0,
      })
    });
    if (res.ok) {
      const data = await res.json();
      renderCenterHub(data.center_hub);
      showToast(`Updated center focal target to ${skuItem.sku}`);
    }
  } catch (err) {
    console.error('Error focusing SKU:', err);
  }
}

function selectCategoryStream(categoryName) {
  const found = activeInventoryList.find(i => i.category.toLowerCase() === categoryName.toLowerCase());
  if (found) {
    focusSkuInCenterHub(found);
  } else {
    showToast(`Focused stream: ${categoryName}`);
  }
}

// ──────────────────────────────────────────────
// 6. Dataset Loader & Forecaster Integration
// ──────────────────────────────────────────────
async function loadDatasetList() {
  try {
    const res = await fetch('/api/inventory-dataset');
    if (!res.ok) throw new Error('Failed to load dataset list');
    const data = await res.json();
    activeInventoryList = data.items || [];

    // Header badge
    const badge = document.getElementById('activeDatasetBadge');
    if (badge) {
      badge.textContent = `${activeInventoryList.length} SKUs Live`;
    }

    // Populate Forecaster SKU Picker
    const picker = document.getElementById('forecasterSkuPicker');
    if (picker) {
      picker.innerHTML = '';
      activeInventoryList.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item.sku;
        opt.textContent = `${item.sku} (${item.category} - ${item.size}) | Stock: ${item.current_stock}`;
        picker.appendChild(opt);
      });
      if (activeInventoryList.length > 0) {
        populateForecasterWithSku(activeInventoryList[0]);
      }
    }

  } catch (err) {
    console.error('Error loading dataset list:', err);
  }
}

function handleSkuPickerChange() {
  const val = document.getElementById('forecasterSkuPicker').value;
  const found = activeInventoryList.find(i => i.sku === val);
  if (found) {
    populateForecasterWithSku(found);
  }
}

function populateForecasterWithSku(skuData) {
  document.getElementById('fcCategory').value = skuData.category || 'Western Dress';
  document.getElementById('fcSize').value = skuData.size || 'M';
  
  document.getElementById('slStock').value = skuData.current_stock || 12;
  document.getElementById('lblStock').textContent = `${skuData.current_stock || 12} units`;

  document.getElementById('slLead').value = skuData.lead_time_days || 3;
  document.getElementById('lblLead').textContent = `${skuData.lead_time_days || 3} days`;

  const s7 = Math.round(skuData.sales_last_7d || 18);
  document.getElementById('slS7').value = s7;
  document.getElementById('lblS7').textContent = `${s7} units`;

  const z14 = Math.round(skuData.zero_days_last_14d || 2);
  document.getElementById('slZero').value = z14;
  document.getElementById('lblZero').textContent = `${z14} days`;

  document.getElementById('fcUnitCost').value = (skuData.unit_cost || 18.00).toFixed(2);
  document.getElementById('fcUnitPrice').value = (skuData.unit_price || 42.00).toFixed(2);

  triggerSimulationUpdate();
}

function handleSliderChange(sliderId, labelId, suffix) {
  const val = document.getElementById(sliderId).value;
  document.getElementById(labelId).textContent = `${val}${suffix}`;
  triggerSimulationUpdate();
}

async function triggerSimulationUpdate() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(async () => {
    const picker = document.getElementById('forecasterSkuPicker');
    const skuName = picker ? picker.value : 'JNE3797-KR-M';

    const payload = {
      sku: skuName,
      category: document.getElementById('fcCategory').value,
      size: document.getElementById('fcSize').value,
      current_stock: parseInt(document.getElementById('slStock').value),
      lead_time_days: parseInt(document.getElementById('slLead').value),
      sales_last_7d: parseFloat(document.getElementById('slS7').value),
      sales_last_14d: parseFloat(document.getElementById('slS7').value) * 1.9,
      sales_lag_1: Math.max(0, parseFloat(document.getElementById('slS7').value) / 6.0),
      zero_days_last_14d: parseFloat(document.getElementById('slZero').value),
      unit_cost: parseFloat(document.getElementById('fcUnitCost').value),
      unit_price: parseFloat(document.getElementById('fcUnitPrice').value),
    };

    try {
      const res = await fetch('/api/predict-sku', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) return;
      const data = await res.json();
      const m = data.metrics;

      document.getElementById('fcResultSku').textContent = data.sku;
      document.getElementById('fcForecastUnits').textContent = m.predicted_7d_demand.toFixed(1);
      document.getElementById('fcReorderPoint').textContent = m.reorder_point.toFixed(1);
      document.getElementById('fcStockRunway').textContent = `${m.stockout_timeline_days} d`;
      document.getElementById('fcRecommendedPo').textContent = m.recommended_reorder_qty;
      document.getElementById('fcActionAdvice').textContent = m.actionable_advice;

      // Verdict badge (iOS Jet Black glowing neon badge)
      const verdEl = document.getElementById('fcResultVerdict');
      verdEl.textContent = m.risk_status;
      if (m.risk_status === 'Healthy') {
        verdEl.className = 'px-3 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-xs';
      } else if (m.risk_status === 'Reorder Advised') {
        verdEl.className = 'px-3 py-0.5 rounded-full text-xs font-bold bg-orange-500/20 text-orange-400 border border-orange-500/40 shadow-xs';
      } else {
        verdEl.className = 'px-3 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40 shadow-xs';
      }

      // Depletion curve
      const trajGrid = document.getElementById('fcTrajectoryGrid');
      if (trajGrid && data.projected_trajectory) {
        trajGrid.innerHTML = '';
        const maxVal = Math.max(...data.projected_trajectory.map(t => t.projected_stock), 10);
        data.projected_trajectory.forEach(t => {
          const col = document.createElement('div');
          col.className = 'flex-1 flex flex-col items-center gap-1.5 h-full justify-end group';
          const pct = Math.max(8, Math.min(100, Math.round((t.projected_stock / maxVal) * 100)));
          col.innerHTML = `
            <div class="w-full max-w-[28px] bg-gradient-to-t from-[#4F46E5] to-[#7C3AED] rounded-t-lg transition group-hover:brightness-125 shadow-xs" style="height: ${pct}%"></div>
            <span class="text-[10px] font-semibold text-slate-400">${t.day}</span>
          `;
          trajGrid.appendChild(col);
        });
      }

    } catch (e) {
      console.error('Simulator error:', e);
    }
  }, 250);
}

// ──────────────────────────────────────────────
// 7. Tab 3: Dynamic Procurement Queue Loader
// ──────────────────────────────────────────────
async function loadProcurementQueue() {
  try {
    const res = await fetch('/api/procurement-queue');
    if (!res.ok) throw new Error('Failed to load procurement queue');
    const data = await res.json();
    const sum = data.summary;

    document.getElementById('poTotalCap').textContent = `$${sum.total_capital_required.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
    document.getElementById('poCritCount').textContent = `${sum.critical_stockouts_count} SKUs`;
    document.getElementById('poTotalUnits').textContent = `${sum.total_units_to_order.toLocaleString()} Units`;
    document.getElementById('poAvgLt').textContent = `${sum.avg_lead_time_days} Days`;
    document.getElementById('poSkusCountBadge').textContent = `${sum.skus_to_reorder_count} SKUs`;

    const tbody = document.getElementById('procurementTableBody');
    tbody.innerHTML = '';

    data.queue.forEach(item => {
      let badge = 'bg-indigo-500/20 text-[#818CF8] border border-indigo-500/40 font-semibold';
      if (item.urgency === 'CRITICAL') badge = 'bg-rose-500/20 text-rose-400 border border-rose-500/40 animate-pulse font-bold';
      if (item.urgency === 'HIGH') badge = 'bg-orange-500/20 text-orange-400 border border-orange-500/40 font-bold';

      const tr = document.createElement('tr');
      tr.className = 'hover:bg-white/5 transition';
      tr.innerHTML = `
        <td class="py-2.5 px-3 font-mono font-bold text-white">${item.sku}</td>
        <td class="py-2.5 px-3 font-medium text-slate-300">${item.category} (${item.size})</td>
        <td class="py-2.5 px-3 font-bold text-white">${item.current_stock} u</td>
        <td class="py-2.5 px-3 font-mono text-slate-400">${item.reorder_point.toFixed(1)} u</td>
        <td class="py-2.5 px-3 font-bold text-white">${item.days_runway} d</td>
        <td class="py-2.5 px-3 font-mono font-bold text-[#818CF8]">+${item.recommended_reorder_qty} u</td>
        <td class="py-2.5 px-3 font-mono text-slate-400">$${item.unit_cost.toFixed(2)}</td>
        <td class="py-2.5 px-3 font-mono font-bold text-white">$${item.total_po_cost.toFixed(2)}</td>
        <td class="py-2.5 px-3">
          <span class="inline-block px-2.5 py-0.5 rounded-full text-[10px] ${badge}">
            ${item.urgency}
          </span>
        </td>
      `;
      tbody.appendChild(tr);
    });

  } catch (err) {
    console.error('Procurement error:', err);
  }
}

// ──────────────────────────────────────────────
// 8. Tab 4: Aged Stock Matrix Loader
// ──────────────────────────────────────────────
async function loadClearanceCandidates() {
  try {
    const res = await fetch('/api/clearance-candidates');
    if (!res.ok) throw new Error('Failed to load clearance candidates');
    const data = await res.json();
    const sum = data.summary;

    document.getElementById('clTotalDrain').textContent = `$${sum.total_monthly_fba_drain.toLocaleString(undefined, {minimumFractionDigits: 2})}/mo`;
    document.getElementById('clCapitalLocked').textContent = `$${sum.capital_locked.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
    document.getElementById('clIdleUnits').textContent = `${sum.idle_units_count} Units`;
    document.getElementById('clCandidatesCount').textContent = `${sum.clearance_skus_count} SKUs`;

    const tbody = document.getElementById('clearanceTableBody');
    tbody.innerHTML = '';

    data.candidates.forEach(c => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-white/5 transition';
      tr.innerHTML = `
        <td class="py-2.5 px-3 font-mono font-bold text-white">${c.sku}</td>
        <td class="py-2.5 px-3 font-medium text-slate-300">${c.category} · Size ${c.size}</td>
        <td class="py-2.5 px-3"><span class="font-mono font-semibold text-rose-400 bg-rose-500/15 px-2 py-0.5 rounded border border-rose-500/30 text-xs">${c.zero_days_last_14d} days idle</span></td>
        <td class="py-2.5 px-3 font-bold text-white">${c.current_stock} units</td>
        <td class="py-2.5 px-3 font-mono text-[#F87171] font-bold">$${c.est_monthly_fba_fee.toFixed(2)}/mo</td>
        <td class="py-2.5 px-3 font-medium text-slate-200">${c.action}</td>
        <td class="py-2.5 px-3 text-right">
          <button onclick="executeClearanceSingle('${c.sku}', '${c.action}')" class="px-3 py-1 rounded-full text-xs font-semibold bg-[#4F46E5] hover:bg-indigo-600 text-white shadow-xs transition border border-indigo-400/30">
            Apply
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });

  } catch (err) {
    console.error('Clearance error:', err);
  }
}

function executeClearanceSingle(sku, action) {
  showToast(`Executed '${action}' on SKU ${sku}`);
}

function applyBulkClearance() {
  showToast('Bulk markdown schedule scheduled on all slow-moving inventory lots.');
}

// ──────────────────────────────────────────────
// 9. Multi-Format File Upload Handlers
// ──────────────────────────────────────────────
function openUploadModal() {
  document.getElementById('uploadModal').classList.remove('hidden');
  const statusArea = document.getElementById('uploadStatusArea');
  if (statusArea) statusArea.classList.add('hidden');
  const spinner = document.getElementById('uploadSpinner');
  if (spinner) spinner.classList.add('hidden');
  const statusText = document.getElementById('uploadStatusText');
  if (statusText) statusText.textContent = '';
}

function closeUploadModal() {
  document.getElementById('uploadModal').classList.add('hidden');
}

function triggerFileInputClick() {
  const fi = document.getElementById('fileInput');
  if (fi) {
    fi.value = '';
    fi.click();
  }
}

function handleDragOver(e) {
  e.preventDefault();
  document.getElementById('dropZone').classList.add('border-[#6366F1]', 'bg-indigo-500/15');
}

function handleDragLeave(e) {
  e.preventDefault();
  document.getElementById('dropZone').classList.remove('border-[#6366F1]', 'bg-indigo-500/15');
}

function handleFileDrop(e) {
  e.preventDefault();
  document.getElementById('dropZone').classList.remove('border-[#6366F1]', 'bg-indigo-500/15');
  const files = e.dataTransfer.files;
  if (files && files.length > 0) {
    uploadFileToServer(files[0]);
  }
}

function handleFileSelected(e) {
  const files = e.target.files;
  if (files && files.length > 0) {
    uploadFileToServer(files[0]);
  }
}

async function uploadFileToServer(file) {
  const statusArea = document.getElementById('uploadStatusArea');
  const statusText = document.getElementById('uploadStatusText');
  const spinner = document.getElementById('uploadSpinner');

  statusArea.classList.remove('hidden');
  if (spinner) spinner.classList.remove('hidden');
  statusText.textContent = `Extracting SKU attributes & running model on '${file.name}'...`;

  const formData = new FormData();
  formData.append('file', file);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 20000);

  try {
    const res = await fetch('/api/upload-inventory', {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      let errDetail = 'File parsing failed';
      try {
        const errJson = await res.json();
        errDetail = errJson.detail || errDetail;
      } catch (e) {
        errDetail = await res.text();
      }
      throw new Error(errDetail);
    }

    const data = await res.json();
    if (spinner) spinner.classList.add('hidden');
    statusText.textContent = `✓ ${data.message}`;

    showToast(`Loaded ${data.extracted_count} SKUs from '${file.name}'`);

    // Refresh all dynamic tabs immediately
    await refreshAllData();

    setTimeout(() => {
      closeUploadModal();
    }, 1200);

  } catch (err) {
    clearTimeout(timeoutId);
    console.error('Upload error:', err);
    if (spinner) spinner.classList.add('hidden');
    statusText.innerHTML = `
      <div class="flex items-center justify-between gap-2">
        <span class="text-rose-400 font-bold leading-tight">Error: ${err.message}</span>
        <button onclick="document.getElementById('uploadStatusArea').classList.add('hidden')" class="text-[11px] underline text-slate-400 hover:text-white font-semibold whitespace-nowrap">Dismiss</button>
      </div>
    `;
  }
}

// ──────────────────────────────────────────────
// 10. Toast Helper
// ──────────────────────────────────────────────
function showToast(msg) {
  const toast = document.getElementById('toast');
  const toastMsg = document.getElementById('toastMsg');
  toastMsg.textContent = msg;
  toast.classList.remove('opacity-0', 'pointer-events-none');
  setTimeout(() => {
    toast.classList.add('opacity-0', 'pointer-events-none');
  }, 3500);
}
