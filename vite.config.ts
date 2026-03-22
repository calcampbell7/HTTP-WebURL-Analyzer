import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const projectRoot = fileURLToPath(new URL('.', import.meta.url))
const analyzerPath = path.resolve(projectRoot, 'backend', 'Webtester.py')

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'webtester-api',
      configureServer(server) {
        server.middlewares.use('/api/analyze', (req, res) => {
          if (req.method !== 'POST') {
            res.statusCode = 405
            res.setHeader('Content-Type', 'application/json')
            res.end(JSON.stringify({ error: 'Method not allowed' }))
            return
          }

          const bodyChunks: Buffer[] = []

          req.on('data', (chunk) => {
            bodyChunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk))
          })

          req.on('end', () => {
            let parsedBody: { url?: string }

            try {
              parsedBody = JSON.parse(Buffer.concat(bodyChunks).toString('utf8'))
            } catch {
              res.statusCode = 400
              res.setHeader('Content-Type', 'application/json')
              res.end(JSON.stringify({ error: 'Invalid JSON body' }))
              return
            }

            const url = parsedBody.url?.trim()

            if (!url) {
              res.statusCode = 400
              res.setHeader('Content-Type', 'application/json')
              res.end(JSON.stringify({ error: 'A website URL is required' }))
              return
            }

            const pythonProcess = spawn('python3', [analyzerPath, '--json', url], {
              cwd: path.resolve(projectRoot, 'backend'),
            })

            let stdout = ''
            let stderr = ''

            pythonProcess.stdout.on('data', (chunk) => {
              stdout += chunk.toString()
            })

            pythonProcess.stderr.on('data', (chunk) => {
              stderr += chunk.toString()
            })

            pythonProcess.on('close', (code) => {
              res.setHeader('Content-Type', 'application/json')

              if (code !== 0) {
                res.statusCode = 500
                res.end(
                  JSON.stringify({
                    error: stderr.trim() || stdout.trim() || 'Analyzer failed',
                  }),
                )
                return
              }

              try {
                const data = JSON.parse(stdout)
                if (!data.ok) {
                  res.statusCode = 500
                  res.end(JSON.stringify({ error: data.error || 'Analyzer failed' }))
                  return
                }

                res.statusCode = 200
                res.end(JSON.stringify(data))
              } catch {
                res.statusCode = 500
                res.end(
                  JSON.stringify({
                    error: 'Analyzer returned invalid JSON',
                    raw: stdout.trim(),
                  }),
                )
              }
            })

            pythonProcess.on('error', (error) => {
              res.statusCode = 500
              res.setHeader('Content-Type', 'application/json')
              res.end(JSON.stringify({ error: `Unable to start analyzer: ${error.message}` }))
            })
          })

          req.on('error', () => {
            res.statusCode = 400
            res.setHeader('Content-Type', 'application/json')
            res.end(JSON.stringify({ error: 'Unable to read request body' }))
          })
        })
      },
    },
  ],
})
