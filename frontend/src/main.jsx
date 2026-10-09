import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import WarehouseMapPage from './pages/WarehouseMapPage.jsx'
import './index.css'

const isMapRoute = window.location.pathname.startsWith('/map')

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {isMapRoute ? <WarehouseMapPage /> : <App />}
  </React.StrictMode>
)

