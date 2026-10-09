import React, { useEffect, useRef, useState } from 'react'

export default function SplineScene({ isChatActive = false, className = '' }) {
  const viewerRef = useRef(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return

    let observer = null

    const purgeLogo = () => {
      try {
        const sr = viewer.shadowRoot
        if (!sr) return

        // Inject high-specificity stylesheet inside Shadow DOM to suppress all branding
        if (!sr.querySelector('#hide-spline-branding')) {
          const style = document.createElement('style')
          style.id = 'hide-spline-branding'
          style.textContent = `
            #logo,
            a[href*="spline.design"],
            .logo,
            [part="logo"],
            a[target="_blank"] {
              display: none !important;
              opacity: 0 !important;
              visibility: hidden !important;
              pointer-events: none !important;
              width: 0 !important;
              height: 0 !important;
              clip: rect(0, 0, 0, 0) !important;
              position: absolute !important;
              bottom: -9999px !important;
            }
          `
          sr.appendChild(style)
        }

        // Directly remove any logo or anchor elements found
        const logos = sr.querySelectorAll('#logo, a[href*="spline"], a[target="_blank"]')
        logos.forEach((el) => {
          el.style.display = 'none'
          el.style.opacity = '0'
          el.remove()
        })
      } catch (e) {
        // Silently handle any shadowRoot security edge cases
      }
    }

    const attachObserver = () => {
      try {
        const sr = viewer.shadowRoot
        if (sr && !observer) {
          purgeLogo()
          observer = new MutationObserver(() => {
            purgeLogo()
          })
          observer.observe(sr, { childList: true, subtree: true })
        }
      } catch (e) {}
    }

    const handleLoad = () => {
      setLoaded(true)
      purgeLogo()
      attachObserver()
    }

    // <spline-viewer> announces a finished scene with "load-complete" ("load" kept for older viewers)
    viewer.addEventListener('load', handleLoad)
    viewer.addEventListener('load-complete', handleLoad)

    // Check shadowRoot periodically during initialization and scene loading
    const interval = setInterval(() => {
      attachObserver()
      purgeLogo()
    }, 150)

    // Keep checking for up to 10 seconds to ensure any late-rendered watermarks are eliminated
    const timer = setTimeout(() => {
      setLoaded(true)
      purgeLogo()
    }, 2000)

    const stopIntervalTimer = setTimeout(() => {
      clearInterval(interval)
    }, 12000)

    return () => {
      viewer.removeEventListener('load', handleLoad)
      viewer.removeEventListener('load-complete', handleLoad)
      clearInterval(interval)
      clearTimeout(timer)
      clearTimeout(stopIntervalTimer)
      if (observer) {
        observer.disconnect()
      }

      // <spline-viewer> does not stop its WebGL app when removed from the page: the render loop
      // keeps drawing into a detached 0x0 canvas ("Framebuffer is incomplete" on every frame).
      // Once the element is really gone (not a StrictMode re-run), dispose the scene via the
      // viewer's own unload() — now, or as soon as a load still in flight completes.
      const releaseIfDetached = () => {
        if (viewer.isConnected) return
        try {
          viewer.unload?.()
        } catch (e) {
          // the third-party viewer may already be torn down
        }
      }
      setTimeout(releaseIfDetached, 0)
      viewer.addEventListener('load-complete', releaseIfDetached, { once: true })
    }
  }, [])

  return (
    <div className={`spline-scene-wrapper ${isChatActive ? 'mode-chat' : 'mode-hero'} ${className}`}>
      {!loaded && (
        <div className="spline-scene-loader" aria-label="Loading 3D scene">
          <div className="spline-loading-bar-track">
            <div className="spline-loading-bar-fill" />
          </div>
        </div>
      )}
      <spline-viewer
        ref={viewerRef}
        url="https://prod.spline.design/E-DqDimz9wGt9TEZ/scene.splinecode"
        className={`spline-webgl-canvas ${loaded ? 'visible' : 'loading'}`}
      />
      {/* Bottom right safety mask to ensure no residual watermark can ever show */}
      <div className="spline-watermark-blocker" />
    </div>
  )
}
