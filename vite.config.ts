import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

const execFileAsync = promisify(execFile)

function localAnalyzerApi(): Plugin {
  return {
    name: 'local-analyzer-api',
    configureServer(server) {
      server.middlewares.use('/api/analyze', (request, response) => {
        response.setHeader('Content-Type', 'application/json')

        if (request.method !== 'POST') {
          response.statusCode = 405
          response.end(JSON.stringify({ error: 'Method not allowed' }))
          return
        }

        let rawBody = ''
        request.setEncoding('utf8')
        request.on('data', (chunk) => {
          rawBody += chunk
        })
        request.on('end', async () => {
          try {
            const payload = JSON.parse(rawBody || '{}') as { url?: unknown }
            const url = typeof payload.url === 'string' ? payload.url.trim() : ''

            if (!url) {
              response.statusCode = 400
              response.end(JSON.stringify({ error: 'A website URL is required' }))
              return
            }

            const { stdout } = await execFileAsync(
              'python3',
              ['backend/Webtester.py', '--json', url],
              { cwd: process.cwd(), timeout: 30_000, maxBuffer: 1024 * 1024 },
            )
            const result = JSON.parse(stdout)
            response.statusCode = 200
            response.end(JSON.stringify(result))
          } catch (error) {
            const processError = error as Error & { stdout?: string }
            let message = processError.message || 'Unable to analyze the website.'

            if (processError.stdout) {
              try {
                const result = JSON.parse(processError.stdout) as { error?: string }
                message = result.error || message
              } catch {
                // Keep the original process error when stdout is not JSON.
              }
            }

            response.statusCode = 500
            response.end(JSON.stringify({ error: message }))
          }
        })
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), localAnalyzerApi()],
})
