#!/usr/bin/env python3
"""Minimal web server for the AI Photographer application."""

import base64
import json
import logging
import mimetypes
import os
import pathlib
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import cgi

from templates.templates_data import TEMPLATES


PUBLIC_DIR = pathlib.Path(__file__).parent / "public"
DEFAULT_STATIC_FILE = PUBLIC_DIR / "index.html"


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class GeminiClient:
    """Client for the Gemini 2.7 Flash NanoBanana API."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model = os.environ.get("GEMINI_MODEL", "gemini-2.7-flash")
        base_url = os.environ.get("GEMINI_API_BASE", "https://nanobanana.googleapis.com")
        self.endpoint = f"{base_url.rstrip('/')}/v1beta/models/{self.model}:generateContent"
        self.enable_mock = _bool_env("GEMINI_USE_MOCK", default=not bool(self.api_key))

    def generate_image(self, *, template, prompt, image_mime_type, image_base64):
        if self.enable_mock:
            logging.info("Using mock Gemini response (GEMINI_USE_MOCK enabled or API key missing).")
            return {
                "image": image_base64,
                "mimeType": image_mime_type or "image/png",
                "source": "mock",
                "note": "Mock response because Gemini API key was not provided."
            }

        if not self.api_key:
            raise RuntimeError("Gemini API key is required when mock mode is disabled.")

        payload = {
            "system_instruction": {
                "role": "system",
                "parts": [
                    {"text": template["system_prompt"]}
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt or "Please restyle this portrait using the selected creative direction."},
                        {
                            "inlineData": {
                                "mimeType": image_mime_type or "image/jpeg",
                                "data": image_base64
                            }
                        }
                    ]
                }
            ]
        }

        request_body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.endpoint}?key={self.api_key}",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:  # pragma: no cover - depends on network
            detail = exc.read().decode("utf-8", errors="ignore")
            logging.error("Gemini API error: %s", detail)
            raise RuntimeError(f"Gemini API request failed with status {exc.code}.") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - depends on network
            logging.error("Gemini API connection error: %s", exc)
            raise RuntimeError("Could not reach Gemini API endpoint.") from exc

        candidate = (result.get("candidates") or [{}])[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        image_part = next((part.get("inlineData") for part in parts if "inlineData" in part), None)
        if image_part:
            return {
                "image": image_part.get("data"),
                "mimeType": image_part.get("mimeType", "image/png"),
                "source": "gemini"
            }

        text_part = next((part.get("text") for part in parts if "text" in part), "")
        raise RuntimeError(
            "Gemini API did not return an image. "
            + (f"Response text: {text_part}" if text_part else "")
        )


class AIPhotographerHandler(BaseHTTPRequestHandler):
    server_version = "AIPhotographer/1.0"

    gemini_client = GeminiClient()

    def do_OPTIONS(self):  # noqa: N802 - method name required by BaseHTTPRequestHandler
        self.send_response(HTTPStatus.NO_CONTENT)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/templates"):
            self._handle_templates()
            return

        if self.path == "/" or self.path == "":
            self._serve_static(DEFAULT_STATIC_FILE)
            return

        target = PUBLIC_DIR / self.path.lstrip("/")
        if target.is_dir():
            target = target / "index.html"
        if target.exists() and target.is_file():
            self._serve_static(target)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/api/generate"):
            self._handle_generate()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def log_message(self, format, *args):  # noqa: A003 - overriding BaseHTTPRequestHandler
        logging.info("%s - - [%s] %s", self.client_address[0], self.log_date_time_string(), format % args)

    # Helpers -----------------------------------------------------------------

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _handle_templates(self):
        payload = [
            {
                "id": template["id"],
                "name": template["name"],
                "description": template["description"],
                "guidance": template["guidance"]
            }
            for template in TEMPLATES
        ]
        self._send_json(payload)

    def _handle_generate(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": self.headers.get("Content-Type"),
        }
        form = cgi.FieldStorage(
            fp=BytesIO(raw_body),
            headers=self.headers,
            environ=environ
        )

        template_id = form.getfirst("templateId")
        custom_prompt = form.getfirst("prompt")
        image_field = form["image"] if "image" in form else None

        if not template_id:
            self._send_json({"error": "templateId is required."}, status=HTTPStatus.BAD_REQUEST)
            return
        if image_field is None or not getattr(image_field, "file", None):
            self._send_json({"error": "An image upload is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        template = next((item for item in TEMPLATES if item["id"] == template_id), None)
        if template is None:
            self._send_json({"error": "Unknown templateId."}, status=HTTPStatus.BAD_REQUEST)
            return

        image_bytes = image_field.file.read()
        if not image_bytes:
            self._send_json({"error": "Uploaded image is empty."}, status=HTTPStatus.BAD_REQUEST)
            return

        image_mime_type = image_field.type or mimetypes.guess_type(image_field.filename)[0] or "image/jpeg"
        image_base64 = base64.b64encode(image_bytes).decode("ascii")

        try:
            generation = self.gemini_client.generate_image(
                template=template,
                prompt=custom_prompt,
                image_mime_type=image_mime_type,
                image_base64=image_base64,
            )
        except Exception as exc:  # pragma: no cover - network
            logging.exception("Generation failed")
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        response_payload = {
            "templateId": template_id,
            "templateName": template["name"],
            "guidance": template["guidance"],
            "mimeType": generation.get("mimeType", "image/png"),
            "imageBase64": generation.get("image"),
            "source": generation.get("source"),
            "note": generation.get("note")
        }
        self._send_json(response_payload)

    def _serve_static(self, path: pathlib.Path):
        try:
            with path.open("rb") as handle:
                data = handle.read()
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        mime_type, _ = mimetypes.guess_type(str(path))
        self.send_response(HTTPStatus.OK)
        self._set_cors_headers()
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload, status=HTTPStatus.OK):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run(server_class=ThreadingHTTPServer, handler_class=AIPhotographerHandler):
    port = int(os.environ.get("PORT", "8000"))
    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Starting AI Photographer server on port %s", port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - manual stop
        logging.info("Shutting down server")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()
