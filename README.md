# AI-Photographer

AI Photographer is a lightweight web experience that lets people upload a reference portrait,
select from ten production-ready visual templates, and then trigger an AI restyle using
Google's Gemini 2.7 Flash model via the NanoBanana API. The project ships with a Python-based
server that serves the static front-end and proxies image generation requests to Gemini (or a
mock generator when credentials are unavailable).

## Features

- ✨ Ten curated templates, each with bespoke creative guidance.
- 📤 Client-side image upload with multipart form submission.
- 🤖 Server-side Gemini 2.7 Flash request builder with system instructions per template.
- 🧪 Optional mock mode so you can develop the UI without real API calls.
- 🛡️ Minimal dependencies so the project can run in restricted environments.

## Project structure

```
.
├── public/                 # Static front-end assets (HTML, CSS, JS)
├── server.py               # HTTP server and Gemini proxy
├── templates/              # Template metadata
└── README.md
```

## Prerequisites

- Python 3.10 or newer.
- A Gemini API key that has access to the NanoBanana endpoint.

## Running the development server

1. Export your Gemini credentials (optional but recommended):

   ```bash
   export GEMINI_API_KEY="your-nanobanana-api-key"
   export GEMINI_MODEL="gemini-2.7-flash"            # optional override
   export GEMINI_API_BASE="https://nanobanana.googleapis.com"  # optional override
   ```

   If you skip the API key, the server automatically falls back to mock mode and simply
   echoes the uploaded photo so you can still test the flow end-to-end.

2. Start the server:

   ```bash
   python server.py
   ```

3. Visit <http://localhost:8000> in your browser. Upload a portrait, pick a template,
   optionally add more creative direction, and click **Generate portrait**.

## API endpoints

| Method | Endpoint        | Description                                     |
| ------ | --------------- | ----------------------------------------------- |
| GET    | `/api/templates` | Returns the list of available templates.        |
| POST   | `/api/generate`  | Accepts `multipart/form-data` with `image`, `templateId`, and optional `prompt`, forwards to Gemini, and returns the generated image as a Base64 string. |

## Environment variables

| Name                | Description                                                                 | Default                                 |
| ------------------- | --------------------------------------------------------------------------- | --------------------------------------- |
| `GEMINI_API_KEY`    | API key used to authenticate with the Gemini NanoBanana endpoint.           | `None` (mock mode enabled)              |
| `GEMINI_MODEL`      | Gemini model identifier.                                                    | `gemini-2.7-flash`                      |
| `GEMINI_API_BASE`   | Base URL for the NanoBanana API.                                            | `https://nanobanana.googleapis.com`     |
| `GEMINI_USE_MOCK`   | Force-enable mock mode when set to `true`.                                  | `true` when `GEMINI_API_KEY` is empty.  |
| `PORT`              | Server port.                                                                | `8000`                                  |

## Notes on production usage

- The server intentionally keeps a minimal dependency footprint (standard library only), which means it does not perform
  advanced request validation beyond basic checks. Harden the input handling if you deploy publicly.
- Gemini NanoBanana responses must include an `inlineData` image payload. If the API returns a different structure,
  adjust the parsing logic in `GeminiClient.generate_image` accordingly.
- For persistent storage of generated images, extend the `/api/generate` handler to upload to cloud storage or a database.

## License

MIT
