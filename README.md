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

## Requirements

- Node.js
- npm
- Python 3

## Install

```sh
npm install
```

## Run The App

Start the Vite development server:

```sh
npm run dev
```

Then open the local URL Vite prints in the terminal, enter a website URI, and the analyzer results will appear on the page.

## Python Analyzer

The analyzer script lives in [backend/Webtester.py](./backend/Webtester.py).

It can still be run directly from the command line:

```sh
cd backend
python3 Webtester.py github.com
```

It also supports JSON output for the frontend bridge:

```sh
cd backend
python3 Webtester.py --json github.com
```

## Notes

- If a URL is entered without a scheme, the analyzer defaults to `https://`.
- Custom ports such as `http://localhost:5173` are supported.
- Redirects are followed.
- If certificate verification fails locally, the analyzer can still connect and will report that the TLS certificate was not verified.
- The browser-to-Python integration is implemented in the Vite dev server, so `npm run dev` is the intended way to use the full app locally.

## Build

You can still build the frontend with:

```sh
npm run build
```

This verifies the React and Vite code, but the Python-backed analyzer route is designed for local development through the Vite dev server.
