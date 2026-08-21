# HTTP Website Analyzer

This project is a React + TypeScript + Vite frontend paired with a Python socket-based website analyzer.

This app lets you enter a website URL in the browser and view the analyzer output directly underneath the input bar.

## What The App Shows

For a submitted website, the app displays:

- The resolved URL
- The HTTP status code
- The transport used (`http` or `https`)
- Whether HTTP/2 was detected
- Whether the site appears password protected
- Whether the TLS certificate was verified
- Response headers
- The raw request that was sent
- Any cookies found in the response headers

## How It Works

- The React app submits the entered URL to a local `/api/analyze` endpoint.
- That endpoint is implemented inside the Vite dev server in `vite.config.ts`.
- The Vite server runs `backend/Webtester.py --json <url>`.
- The Python script performs the request and returns structured JSON.
- The frontend renders that data below the input bar.

## Run Locally

You need Node.js, npm, and Python 3 installed. From the project directory, run:

```bash
npm install
npm run dev
```

Then open the local URL printed by Vite. The development server exposes
`/api/analyze` and runs the Python analyzer automatically.

## Try it Out!
https://vite-react-ochre-zeta-22.vercel.app
