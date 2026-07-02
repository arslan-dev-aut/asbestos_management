import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import type { Plugin } from 'vite'

// Dev-only plugin: proxies blob storage downloads through Node so the browser
// receives Content-Disposition: attachment and saves the file instead of opening it.
// The presigned URL is passed as a query param; Node fetches it server-side
// (no CORS restriction) and streams the bytes back with the correct headers.
function blobDownloadProxy(): Plugin {
  return {
    name: 'blob-download-proxy',
    configureServer(server) {
      server.middlewares.use('/blob-download', async (req, res) => {
        const qs = new URL(req.url ?? '', 'http://localhost').searchParams
        const blobUrl = qs.get('url')
        const fileName = qs.get('name') ?? 'download'
        if (!blobUrl) { res.statusCode = 400; res.end('Missing url'); return }
        try {
          const upstream = await fetch(blobUrl)
          if (!upstream.ok) { res.statusCode = upstream.status; res.end('Upstream error'); return }
          const contentType = upstream.headers.get('content-type') ?? 'application/octet-stream'
          res.setHeader('Content-Type', contentType)
          res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(fileName)}"`)
          res.setHeader('Cache-Control', 'no-store')
          const buf = await upstream.arrayBuffer()
          res.end(Buffer.from(buf))
        } catch (e) {
          res.statusCode = 500
          res.end(String(e))
        }
      })
    },
  }
}

export default defineConfig(({ mode }) => {
  // Toggle the backend the dev proxy points at via VITE_PROXY_TARGET in .env:
  //   - ngrok (default): https://suspense-pasted-collar.ngrok-free.dev
  //   - local backend:   http://localhost:8002
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_URL || 'https://suspense-pasted-collar.ngrok-free.dev'
  const isNgrok = target.includes('ngrok')

  return {
    plugins: [vue(), blobDownloadProxy()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target,
          changeOrigin: true,
          secure: false,
          // ngrok's free tier shows a browser-warning interstitial unless this
          // header is present; harmless when pointing at a local backend.
          ...(isNgrok ? { headers: { 'ngrok-skip-browser-warning': 'true' } } : {}),
        },
        // The QR public link is served by the backend at /public/{token} (no
        // /api prefix) and returns the site's view-only register as JSON. The
        // SPA route at /site/:token/asbestos fetches /public/{token} and renders
        // it. These data fetches must reach the backend, so proxy /public too.
        // NOTE: in dev this means the SPA's own /site/... route handles the page
        // and JS fetches /public/... for data — they don't collide.
        '/public': {
          target,
          changeOrigin: true,
          secure: false,
          ...(isNgrok ? { headers: { 'ngrok-skip-browser-warning': 'true' } } : {}),
        },
      },
    },
  }
})
