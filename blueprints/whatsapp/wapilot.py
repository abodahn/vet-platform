"""
wapilot.py — Wapilot v2 API client for the Aleefy platform.

All methods return (data, error_string).
data is the parsed JSON response on success, {} on failure.
error_string is "" on success, a message on failure.
"""
import json, urllib.request, urllib.error, urllib.parse
from typing import Any, Dict, Tuple, Optional

BASE_URL = "https://api.wapilot.net/api/v2"

Result = Tuple[Any, str]   # (data, error)


class WapilotClient:
    def __init__(self, token: str, instance_id: str = ""):
        self.token       = token
        self.instance_id = instance_id

    # ── Internal helpers ─────────────────────────────────────────────

    def _headers(self, content_type: str = "") -> dict:
        h = {"token": self.token}
        if content_type:
            h["Content-Type"] = content_type
        return h

    def _request(self, method: str, path: str, body=None,
                 content_type: str = "application/json") -> Result:
        url  = f"{BASE_URL}{path}"
        data = None
        if body is not None:
            data = json.dumps(body).encode() if isinstance(body, dict) else body

        req  = urllib.request.Request(
            url,
            data=data,
            headers=self._headers(content_type if data else ""),
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    return json.loads(raw), ""
                except Exception:
                    return {"raw": raw}, ""
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw)
            except Exception:
                detail = {"raw": raw}
            return detail, f"HTTP {e.code}: {e.reason}"
        except Exception as exc:
            return {}, str(exc)

    def _get(self, path: str)  -> Result:
        return self._request("GET",    path)

    def _post(self, path: str, body=None) -> Result:
        return self._request("POST",   path, body or {})

    def _patch(self, path: str, body=None) -> Result:
        return self._request("PATCH",  path, body or {})

    def _put(self, path: str, body=None) -> Result:
        return self._request("PUT",    path, body or {})

    def _delete(self, path: str, body=None) -> Result:
        return self._request("DELETE", path, body)

    # ── Instances ────────────────────────────────────────────────────

    def list_instances(self) -> Result:
        return self._get("/instances")

    def instance_details(self, iid: str = "") -> Result:
        return self._get(f"/instances/{iid or self.instance_id}")

    def instance_status(self, iid: str = "") -> Result:
        return self._get(f"/instances/{iid or self.instance_id}/status")

    def start_instance(self, iid: str = "") -> Result:
        return self._post(f"/instances/{iid or self.instance_id}/start")

    def restart_instance(self, iid: str = "") -> Result:
        return self._post(f"/instances/{iid or self.instance_id}/restart")

    def logout_instance(self, iid: str = "") -> Result:
        return self._post(f"/instances/{iid or self.instance_id}/logout")

    def troubleshoot_instance(self, iid: str = "") -> Result:
        return self._post(f"/instances/{iid or self.instance_id}/troubleshoot")

    def get_qr(self, iid: str = "") -> Result:
        return self._get(f"/instances/{iid or self.instance_id}/qr-code")

    def get_screenshot(self, iid: str = "") -> Result:
        return self._get(f"/instances/{iid or self.instance_id}/screenshot")

    def get_queue_settings(self, iid: str = "") -> Result:
        return self._get(f"/instances/{iid or self.instance_id}/queue-settings")

    def update_queue_settings(self, settings: dict, iid: str = "") -> Result:
        return self._put(f"/instances/{iid or self.instance_id}/queue-settings", settings)

    # ── Messages ─────────────────────────────────────────────────────

    def send_message(self, chat_id: str, text: str,
                     priority: int = 0, send_at: str = "",
                     iid: str = "") -> Result:
        body = {"chat_id": chat_id, "text": text}
        if priority:
            body["priority"] = priority
        if send_at:
            body["send_at"] = send_at
        return self._post(f"/{iid or self.instance_id}/send-message", body)

    def list_messages(self, iid: str = "", **filters) -> Result:
        qs = urllib.parse.urlencode({k: v for k, v in filters.items() if v})
        path = f"/{iid or self.instance_id}/messages"
        if qs:
            path += "?" + qs
        return self._get(path)

    def message_details(self, message_id: str, iid: str = "") -> Result:
        return self._get(f"/{iid or self.instance_id}/messages/{message_id}")

    def retry_message(self, message_id: str, iid: str = "") -> Result:
        return self._post(f"/{iid or self.instance_id}/messages/{message_id}/retry")

    def retry_all_messages(self, body: dict = None, iid: str = "") -> Result:
        return self._post(f"/{iid or self.instance_id}/messages/retry-all", body or {})

    # ── Media ────────────────────────────────────────────────────────

    def send_image(self, chat_id: str, file_bytes: bytes, filename: str,
                   caption: str = "", iid: str = "") -> Result:
        return self._send_media(
            f"/{iid or self.instance_id}/send-image",
            chat_id, file_bytes, filename, caption
        )

    def send_file(self, chat_id: str, file_bytes: bytes, filename: str,
                  caption: str = "", iid: str = "") -> Result:
        return self._send_media(
            f"/{iid or self.instance_id}/send-file",
            chat_id, file_bytes, filename, caption
        )

    def send_video(self, chat_id: str, file_bytes: bytes, filename: str,
                   caption: str = "", iid: str = "") -> Result:
        return self._send_media(
            f"/{iid or self.instance_id}/send-video",
            chat_id, file_bytes, filename, caption
        )

    def _send_media(self, path: str, chat_id: str, file_bytes: bytes,
                    filename: str, caption: str) -> Result:
        import email.mime.multipart
        boundary = "----WapilotBoundary7623"
        body  = f'--{boundary}\r\n'
        body += f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
        if caption:
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
        body_bytes  = body.encode()
        file_part   = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
            f'Content-Type: application/octet-stream\r\n\r\n'
        ).encode() + file_bytes + f'\r\n--{boundary}--\r\n'.encode()
        payload = body_bytes + file_part
        return self._request(
            "POST", path, body=payload,
            content_type=f"multipart/form-data; boundary={boundary}"
        )

    def send_list_message(self, chat_id: str, interactive: dict,
                          iid: str = "") -> Result:
        return self._post(
            f"/{iid or self.instance_id}/send-list",
            {"chat_id": chat_id, "interactive": interactive}
        )

    # ── Campaigns ────────────────────────────────────────────────────

    def list_campaigns(self) -> Result:
        return self._get("/campaigns")

    def create_campaign(self, instance_uns: list,
                        default_message: str = "") -> Result:
        body = {"instance_uns": instance_uns}
        if default_message:
            body["default_message"] = default_message
        return self._post("/campaigns", body)

    def campaign_stats(self, campaign: str) -> Result:
        return self._get(f"/campaigns/{campaign}/messages/stats")

    def campaign_messages(self, campaign: str) -> Result:
        return self._get(f"/campaigns/{campaign}/messages")

    def campaign_queue(self, campaign: str) -> Result:
        return self._get(f"/campaigns/{campaign}/messages/queue")

    def campaign_done(self, campaign: str) -> Result:
        return self._get(f"/campaigns/{campaign}/messages/done")

    def bulk_add_messages(self, campaign: str, messages: list) -> Result:
        return self._post(f"/campaigns/{campaign}/messages", {"messages": messages})

    def bulk_delete_messages(self, campaign: str, ids: list) -> Result:
        return self._delete(f"/campaigns/{campaign}/messages", {"ids": ids})

    def start_campaign(self, campaign: str) -> Result:
        return self._post(f"/campaigns/{campaign}/start")

    def pause_campaign(self, campaign: str) -> Result:
        return self._post(f"/campaigns/{campaign}/pause")

    def schedule_campaign(self, campaign: str, schedule_date: str) -> Result:
        return self._post(f"/campaigns/{campaign}/schedule",
                          {"schedule_date": schedule_date})

    def unschedule_campaign(self, campaign: str) -> Result:
        return self._delete(f"/campaigns/{campaign}/schedule")

    def finish_campaign(self, campaign: str) -> Result:
        return self._patch(f"/campaigns/{campaign}/finish")

    def copy_campaign(self, campaign: str) -> Result:
        return self._post(f"/campaigns/{campaign}/copy")

    def reset_failed(self, campaign: str) -> Result:
        return self._post(f"/campaigns/{campaign}/reset-failed")

    def get_delay(self, campaign: str) -> Result:
        return self._get(f"/campaigns/{campaign}/delay")

    def update_delay(self, campaign: str, settings: dict) -> Result:
        return self._patch(f"/campaigns/{campaign}/delay", settings)

    # ── Chat ID Lookup ───────────────────────────────────────────────

    def get_chat_id_by_lid(self, lid: str, iid: str = "") -> Result:
        return self._get(f"/api/v2/{iid or self.instance_id}/lids/{lid}")

    def get_lid_by_phone(self, phone: str, iid: str = "") -> Result:
        return self._get(f"/api/v2/{iid or self.instance_id}/lids/pn/{phone}")
