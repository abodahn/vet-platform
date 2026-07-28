"""
Medical Imaging Module — Aleefy Platform
- Upload X-ray, ultrasound, MRI, endoscopy images per pet/visit
- AI photo analysis powered by Gemini Vision (freellmapi)
- Standalone AI photo analyzer (no pet required — drop any animal photo)
"""

import os
import base64
import uuid
import io
from datetime import datetime
from flask import (current_app, render_template, request, jsonify,
                   redirect, url_for, flash, session, send_from_directory)
from werkzeug.utils import secure_filename

from . import imaging_bp
from blueprints.auth.routes import login_required

import os as _os
_BASE_URL     = _os.environ.get("AI_BASE_URL",    "http://localhost:3001/v1")
_API_KEY      = _os.environ.get("AI_API_KEY",    "")   # Must be set via env var — no hardcoded fallback
_MODEL        = _os.environ.get("AI_MODEL",      "gemini-2.5-flash")
_GOOGLE_KEY   = _os.environ.get("GOOGLE_API_KEY", "")
# Vision models to try in order via freellmapi
_VISION_MODELS_PROXY = ["gpt-4o", "gemini-3.1-pro-preview", "gemini-2.5-flash", "openai/gpt-4.1"]
_VISION_MODEL_GENAI  = "gemini-2.0-flash"

ALLOWED_EXT = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff"}
MAX_BYTES   = 10 * 1024 * 1024  # 10 MB


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _uploads_dir() -> str:
    path = current_app.config.get("UPLOADS_PATH", "uploads")
    imaging = os.path.join(path, "imaging")
    os.makedirs(imaging, exist_ok=True)
    return imaging


def _get_db():
    import models.database as db
    return db.get_db()


# ── AI Vision Analysis ────────────────────────────────────────────────────────

_VET_PROMPT = """\
You are an expert veterinary diagnostician with 20+ years of clinical experience.
A photo of an animal has been submitted for triage assessment.

Analyze the image carefully and provide a structured veterinary assessment:

1. **Animal Identification**: Species, approximate age/size, breed if recognizable
2. **Visible Condition**: Describe what you see — wounds, swelling, skin issues, posture, eye/ear condition, coat/feathers, mobility signs
3. **Severity Level**: 🟢 Minor | 🟡 Moderate | 🔴 Urgent | 🚨 Emergency
4. **Possible Diagnoses**: List 2-4 most likely conditions based on visible signs
5. **Immediate First Aid**: What the owner can safely do RIGHT NOW before seeing a vet
6. **Veterinary Urgency**: How soon should this animal see a vet? Today / Within 24h / Within a week / Routine checkup
7. **Do NOT Do**: Any actions that could worsen the condition
8. **Additional Notes**: Anything else clinically relevant

⚕️ Always end with: "This is an AI-assisted triage assessment. Please consult Dr. Hatem or a licensed veterinarian for definitive diagnosis and treatment."

Be clear, professional, and compassionate. Reply in the same language the user is using (Arabic or English).
"""

def _compress_image(image_bytes: bytes) -> tuple[bytes, str]:
    """
    Resize to max 1024px on longest side, convert to JPEG quality 82.
    Returns (compressed_bytes, 'image/jpeg').
    Falls back to original bytes if Pillow is not installed.
    """
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        # Convert palette / RGBA → RGB so JPEG encoding works
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        # Resize: max 1024px on longest side
        MAX = 1024
        w, h = img.size
        if max(w, h) > MAX:
            scale = MAX / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except ImportError:
        # Pillow not installed — fall through with original bytes
        return image_bytes, "image/jpeg"
    except Exception:
        return image_bytes, "image/jpeg"


def _analyze_image(image_bytes: bytes, mime_type: str, user_note: str = "") -> str:
    """
    Analyze animal photo with three-tier fallback:
      1. freellmapi proxy (localhost:3001) — tries vision-capable models
      2. Google Gemini API directly via google-genai SDK (needs GOOGLE_API_KEY)
      3. Friendly error with setup instructions
    """
    prompt_text = _VET_PROMPT + (f"\n\nOwner/staff note: {user_note}" if user_note else "")

    # Always compress image first
    compressed, mime_type = _compress_image(image_bytes)
    b64      = base64.b64encode(compressed).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"

    # ── Tier 1: freellmapi proxy (existing credentials) ──────────────────────
    try:
        from openai import OpenAI
        client = OpenAI(base_url=_BASE_URL, api_key=_API_KEY)
        last_err = None
        for vision_model in _VISION_MODELS_PROXY:
            try:
                resp = client.chat.completions.create(
                    model=vision_model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {"type": "text", "text": prompt_text},
                        ]
                    }],
                    max_tokens=1200,
                )
                text = (resp.choices[0].message.content or "").strip()
                if text:
                    return text
            except Exception as e:
                last_err = e
                continue  # try next model
    except Exception:
        pass

    # ── Tier 2: Google Gemini API directly (google-genai SDK) ────────────────
    if _GOOGLE_KEY:
        try:
            import google.genai as genai
            from google.genai import types as gtypes
            client_g = genai.Client(api_key=_GOOGLE_KEY)
            img_part = gtypes.Part.from_bytes(data=compressed, mime_type=mime_type)
            result   = client_g.models.generate_content(
                model=_VISION_MODEL_GENAI,
                contents=[img_part, prompt_text],
            )
            text = (result.text or "").strip()
            if text:
                return text
        except Exception as e:
            err = str(e)
            if "API_KEY" in err or "401" in err:
                return "❌ **Invalid GOOGLE_API_KEY** — please check the key is correct."
            if "quota" in err.lower() or "429" in err:
                return "⚠️ **Rate limit** — try again in a few minutes."

    # ── Tier 3: Setup instructions ────────────────────────────────────────────
    return (
        "## ⚙️ Vision Setup Required\n\n"
        "The **freellmapi proxy** (`localhost:3001`) does not currently support image analysis "
        "— it returns an error for all vision models.\n\n"
        "**To enable AI Photo Analysis, choose one option:**\n\n"
        "### Option A — Get a free Google Gemini API key *(recommended, 2 min)*\n"
        "1. Go to **https://aistudio.google.com/app/apikey**\n"
        "2. Click **Create API Key** — it's free (1,500 requests/day)\n"
        "3. Open `C:\\vet\\START_PLATFORM.bat` and add:\n"
        "   `set GOOGLE_API_KEY=AIza...your_key...`\n"
        "4. Restart the platform\n\n"
        "### Option B — Use a vision-capable proxy\n"
        "Switch to a proxy that forwards image content (e.g. OpenRouter.ai with `gpt-4o`):\n"
        "```\n"
        "set AI_BASE_URL=https://openrouter.ai/api/v1\n"
        "set AI_API_KEY=sk-or-...\n"
        "set AI_MODEL=openai/gpt-4o\n"
        "```"
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@imaging_bp.route("/")
@login_required
def index():
    """All imaging studies — recent 100."""
    conn = _get_db()
    try:
        rows = conn.execute("""
            SELECT s.*, p.pet_name, p.species, o.full_name AS owner_name
            FROM imaging_studies s
            LEFT JOIN pets   p ON p.id = s.pet_id
            LEFT JOIN owners o ON o.id = s.owner_id
            ORDER BY s.created_at DESC LIMIT 100
        """).fetchall()
        studies = [dict(r) for r in rows]
    except Exception:
        studies = []
    finally:
        conn.close()
    return render_template("imaging/index.html",
                           studies=studies, active="clinical",
                           page_title="Medical Imaging")


@imaging_bp.route("/pet/<int:pet_id>")
@login_required
def pet_studies(pet_id):
    """All imaging studies for one pet."""
    conn = _get_db()
    try:
        pet = dict(conn.execute("SELECT * FROM pets WHERE id=?", (pet_id,)).fetchone() or {})
        rows = conn.execute("""
            SELECT * FROM imaging_studies WHERE pet_id=? ORDER BY created_at DESC
        """, (pet_id,)).fetchall()
        studies = [dict(r) for r in rows]
    except Exception:
        pet, studies = {}, []
    finally:
        conn.close()
    return render_template("imaging/pet_studies.html",
                           pet=pet, studies=studies, active="clinical",
                           page_title=f"Imaging — {pet.get('pet_name','Pet')}")


@imaging_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Upload a new imaging study (with optional AI analysis)."""
    conn = _get_db()
    if request.method == "POST":
        pet_id    = request.form.get("pet_id", "").strip()
        study_type  = request.form.get("study_type", "X-Ray").strip()
        body_region = request.form.get("body_region", "").strip()
        notes       = request.form.get("notes", "").strip()
        run_ai      = bool(request.form.get("run_ai"))
        file        = request.files.get("image_file")

        if not pet_id or not file or file.filename == "":
            flash("Pet and image file are required.", "danger")
        elif not _allowed(file.filename):
            flash("Unsupported file type. Use JPG, PNG, GIF, WebP, or TIFF.", "danger")
        else:
            raw = file.read()
            if len(raw) > MAX_BYTES:
                flash("File too large (max 10 MB).", "danger")
            else:
                ext = file.filename.rsplit(".", 1)[1].lower()
                fname = f"{uuid.uuid4().hex}.{ext}"
                save_path = os.path.join(_uploads_dir(), fname)
                with open(save_path, "wb") as f:
                    f.write(raw)

                ai_result = ""
                if run_ai:
                    mime = f"image/{ext if ext != 'jpg' else 'jpeg'}"
                    ai_result = _analyze_image(raw, mime, notes)

                owner_row = conn.execute(
                    "SELECT owner_id FROM pets WHERE id=?", (pet_id,)
                ).fetchone()
                owner_id = owner_row["owner_id"] if owner_row else None
                visit_id = request.form.get("visit_id") or None

                conn.execute("""
                    INSERT INTO imaging_studies
                        (pet_id, owner_id, visit_id, study_type, body_region,
                         file_path, notes, ai_analysis, created_by)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (pet_id, owner_id, visit_id, study_type, body_region,
                      fname, notes, ai_result,
                      session.get("user", {}).get("username", "")))
                conn.commit()
                flash("Imaging study saved successfully.", "success")
                conn.close()
                return redirect(url_for("imaging.pet_studies", pet_id=pet_id))

    # GET — load pets list
    try:
        pets = [dict(r) for r in conn.execute(
            "SELECT id, pet_name, species FROM pets WHERE is_active=1 ORDER BY pet_name"
        ).fetchall()]
    except Exception:
        pets = []
    finally:
        conn.close()

    pet_id_pre = request.args.get("pet_id", "")
    return render_template("imaging/upload.html",
                           pets=pets, pet_id_pre=pet_id_pre, active="clinical",
                           page_title="Upload Imaging Study")


@imaging_bp.route("/study/<int:study_id>")
@login_required
def study_detail(study_id):
    conn = _get_db()
    try:
        # linked_*_id is NULL when the row is missing, so the template can tell
        # "no visit recorded" apart from "visit recorded but deleted" and link
        # only what actually resolves.
        row = conn.execute("""
            SELECT s.*, p.id linked_pet_id, p.pet_name, p.species,
                   o.id linked_owner_id, o.full_name AS owner_name,
                   v.id linked_visit_id, v.visit_date
            FROM imaging_studies s
            LEFT JOIN pets   p ON p.id = s.pet_id
            LEFT JOIN owners o ON o.id = s.owner_id
            LEFT JOIN visits v ON v.id = s.visit_id
            WHERE s.id=?
        """, (study_id,)).fetchone()
        study = dict(row) if row else None
    finally:
        conn.close()
    if not study:
        flash("Study not found.", "danger")
        return redirect(url_for("imaging.index"))
    return render_template("imaging/study_detail.html",
                           study=study, active="clinical",
                           page_title=f"Study #{study_id}")


@imaging_bp.route("/file/<filename>")
@login_required
def serve_file(filename):
    """Serve uploaded imaging file."""
    return send_from_directory(_uploads_dir(), secure_filename(filename))


# ── AI PHOTO ANALYZER (standalone — no pet required) ─────────────────────────

@imaging_bp.route("/analyzer")
@login_required
def analyzer():
    """Standalone AI animal photo analyzer."""
    conn = _get_db()
    try:
        pets = [dict(r) for r in conn.execute(
            "SELECT id, pet_name, species FROM pets WHERE is_active=1 ORDER BY pet_name"
        ).fetchall()]
    except Exception:
        pets = []
    finally:
        conn.close()
    return render_template("imaging/analyzer.html",
                           pets=pets, active="clinical",
                           page_title="AI Photo Analyzer",
                           api_key_set=bool(_GOOGLE_KEY))


@imaging_bp.route("/analyzer/analyze", methods=["POST"])
@login_required
def analyzer_run():
    """AJAX endpoint — analyze an uploaded photo."""
    file = request.files.get("photo")
    note = (request.form.get("note") or "").strip()

    if not file or file.filename == "":
        return jsonify({"error": "No photo uploaded"}), 400
    if not _allowed(file.filename):
        return jsonify({"error": "Unsupported file type"}), 400

    raw = file.read()
    if len(raw) > MAX_BYTES:
        return jsonify({"error": "File too large (max 10 MB)"}), 400

    ext  = file.filename.rsplit(".", 1)[1].lower()
    mime = f"image/{ext if ext != 'jpg' else 'jpeg'}"
    result = _analyze_image(raw, mime, note)
    return jsonify({"result": result})


@imaging_bp.route("/analyzer/save", methods=["POST"])
@login_required
def analyzer_save():
    """Save an analyzer result as an imaging study for a specific pet."""
    data = request.get_json(silent=True) or {}
    pet_id    = data.get("pet_id")
    result    = data.get("result", "")
    filename  = data.get("filename", "")

    if not pet_id or not result:
        return jsonify({"error": "pet_id and result are required"}), 400

    conn = _get_db()
    try:
        owner_row = conn.execute("SELECT owner_id FROM pets WHERE id=?", (pet_id,)).fetchone()
        owner_id  = owner_row["owner_id"] if owner_row else None
        conn.execute("""
            INSERT INTO imaging_studies
                (pet_id, owner_id, study_type, file_path, notes, ai_analysis, created_by)
            VALUES (?,?,'AI Analysis',?,?,?,?)
        """, (pet_id, owner_id, filename or None, "Via AI Analyzer", result,
              session.get("user", {}).get("username", "")))
        conn.commit()
        return jsonify({"ok": True, "pet_id": pet_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
