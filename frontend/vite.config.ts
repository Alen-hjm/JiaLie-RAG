import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({mode}) => {
  const env = loadEnv(mode, '.', '')
  const runtimeEnv = (globalThis as unknown as {process?: {env?: Record<string, string>}}).process?.env
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { '/api': runtimeEnv?.MINGLIE_API_TARGET || env.MINGLIE_API_TARGET || 'http://localhost:8010' }
    }
  }
})
