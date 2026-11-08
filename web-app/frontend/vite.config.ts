import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const cert = process.env.VIBICLE_DEV_TLS_CERT
const key = process.env.VIBICLE_DEV_TLS_KEY

export default defineConfig({
  plugins: [react()],
  server: {
    https: cert && key ? { cert: readFileSync(cert), key: readFileSync(key) } : undefined,
    // Browser sees a single origin. Production serves the build through Caddy.
    proxy: { '/api': { target: 'http://127.0.0.1:8000' } },
  },
})
