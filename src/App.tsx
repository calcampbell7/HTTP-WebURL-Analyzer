import { FormEvent, useState } from 'react'
import './App.css'

type CookieInfo = {
  domain: string | null
  expires: string | null
  name: string
}

type AnalysisResult = {
  cookies: CookieInfo[]
  headers: string
  input: string
  passwordProtected: boolean
  request: string
  resolvedUrl: string
  statusCode: string
  supportsHttp2: boolean
  tlsCertificateVerified: boolean
  transport: string
}

function App() {
  const [url, setUrl] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const trimmedUrl = url.trim()
    if (!trimmedUrl) {
      setError('Enter a website URL to analyze.')
      setResult(null)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: trimmedUrl }),
      })

      const responseText = await response.text()
      let data: AnalysisResult & { error?: string }

      try {
        data = JSON.parse(responseText)
      } catch {
        throw new Error(
          response.ok
            ? 'The analyzer returned an invalid response.'
            : `The analyzer endpoint is unavailable (HTTP ${response.status}).`,
        )
      }

      if (!response.ok) {
        throw new Error(data.error || 'Unable to analyze the website.')
      }

      setResult(data)
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : 'Unable to analyze the website.'
      setError(message)
      setResult(null)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <div className="app">
        <header className="hero">
          <h1>HTTP Website Analyzer</h1>
          <p className="hero-copy">
            Enter a website URI to inspect the response headers, transport details, cookies, and
            access status directly in the page.
          </p>
        </header>

        <main className="content">
          <form className="analyzer-form" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="website-url">
              Website URL
            </label>
            <input
              id="website-url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="Enter website URI"
              autoComplete="off"
            />
            <button type="submit" disabled={isLoading}>
              {isLoading ? 'Analyzing...' : 'Analyze'}
            </button>
          </form>

          {error ? <p className="status-message error-message">{error}</p> : null}

          {result ? (
            <section className="results-panel">
              <div className="results-overview">
                <div className="overview-card">
                  <span className="overview-label">Original Input</span>
                  <strong>{result.input}</strong>
                </div>
                <div className="overview-card">
                  <span className="overview-label">Resolved URL</span>
                  <strong>{result.resolvedUrl}</strong>
                </div>
                <div className="overview-card">
                  <span className="overview-label">Status Code</span>
                  <strong>{result.statusCode}</strong>
                </div>
                <div className="overview-card">
                  <span className="overview-label">Transport</span>
                  <strong>{result.transport.toUpperCase()}</strong>
                </div>
              </div>

              <div className="characteristics-grid">
                <div className="characteristic-card">
                  <span>HTTP/2</span>
                  <strong>{result.supportsHttp2 ? 'Supported' : 'Not detected'}</strong>
                </div>
                <div className="characteristic-card">
                  <span>Password Protection</span>
                  <strong>{result.passwordProtected ? 'Yes' : 'No'}</strong>
                </div>
                <div className="characteristic-card">
                  <span>TLS Certificate</span>
                  <strong>{result.tlsCertificateVerified ? 'Verified' : 'Not verified'}</strong>
                </div>
                <div className="characteristic-card">
                  <span>Cookies</span>
                  <strong>{result.cookies.length}</strong>
                </div>
              </div>

              <div className="results-sections">
                <section className="result-card">
                  <h2>Response Headers</h2>
                  <pre>{result.headers}</pre>
                </section>

                <section className="result-card">
                  <h2>Request Sent</h2>
                  <pre>{result.request}</pre>
                </section>

                <section className="result-card">
                  <h2>Cookies</h2>
                  {result.cookies.length > 0 ? (
                    <ul className="cookie-list">
                      {result.cookies.map((cookie) => (
                        <li key={`${cookie.name}-${cookie.domain ?? 'host'}`}>
                          <strong>{cookie.name}</strong>
                          <span>Domain: {cookie.domain ?? 'Not provided'}</span>
                          <span>Expires: {cookie.expires ?? 'Session cookie'}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="empty-state">No cookies found in the response headers.</p>
                  )}
                </section>
              </div>
            </section>
          ) : (
            <section className="results-panel empty-panel">
              <p className="empty-state">
                Analyzer results will appear here underneath the input after you submit a website.
              </p>
            </section>
          )}
        </main>
      </div>
    </div>
  )
}

export default App
