"""
AI Assistant Blueprint — Premium Animal Hospital Platform
Backend : freellmapi  (OpenAI-compatible proxy at localhost:3001)
"""

import json
import re
from datetime import date

try:
    from openai import OpenAI as _OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OpenAI = None
    _OPENAI_AVAILABLE = False

from flask import render_template, request, redirect, url_for, session, flash, jsonify
from . import ai_bp
from blueprints.auth.routes import login_required
import models.database as db

# ── freellmapi config ─────────────────────────────────────────────────────────
FREELLM_BASE_URL = "http://localhost:3001/v1"
FREELLM_API_KEY  = "freellmapi-4ddad5d50504e98e27a4001eb5422e23a89cc957233ea3d0"
FREELLM_MODEL    = "gemini-2.5-flash"   # fast, capable; change to gpt-4o for OpenAI


# ── System prompts ────────────────────────────────────────────────────────────

def get_system_prompt(role: str) -> str:
    base = (
        "You are the AI assistant for Premium Animal Hospital (Dr. Hatem El Khateeb). "
        "You help veterinary staff with clinical and operational decisions. "
        "Always be professional, accurate, and include a disclaimer that AI suggestions "
        "should be reviewed by a licensed veterinarian.\n"
        "You support both English and Arabic. Respond in the same language as the user's message.\n"
    )
    role_context = {
        "doctor": (
            "You are assisting a veterinarian. Provide clinical decision support: "
            "drug interactions, dosage calculations (mg/kg), differential diagnoses, treatment protocols."
        ),
        "nurse": (
            "You are assisting a veterinary nurse. Help with patient care, medication "
            "administration, vital signs interpretation."
        ),
        "reception": (
            "You are assisting reception staff. Help with appointment scheduling, owner "
            "communication, FAQ answers."
        ),
        "inventory_mgr": (
            "You are assisting inventory management. Help with FEFO stock management, "
            "reorder decisions, expiry tracking."
        ),
        "pharmacist": (
            "You are assisting the pharmacist. Provide medication information, dosage "
            "templates, drug interactions."
        ),
        "finance": (
            "You are assisting finance staff. Help with billing questions, insurance, "
            "payment processing."
        ),
    }
    return base + "\n" + role_context.get(
        role,
        "You are assisting veterinary clinic staff."
    )


def _client() -> "_OpenAI":
    return _OpenAI(base_url=FREELLM_BASE_URL, api_key=FREELLM_API_KEY)


def call_ai(messages: list, role: str,
            patient_context: str = "") -> tuple[str, str, str]:
    """Call freellmapi and return (reply_text, model_used, routed_via).

    `messages` must be the alternating user/assistant list (no system message).
    The system prompt is prepended here.  If `patient_context` is supplied it
    is appended to the system prompt so the model knows the current patient.
    """
    if not _OPENAI_AVAILABLE:
        return "AI requires the 'openai' package. Run: pip install openai", "none", ""
    try:
        sys_content = get_system_prompt(role)
        if patient_context:
            sys_content += "\n\n" + patient_context
        full_messages = [
            {"role": "system", "content": sys_content},
            *messages,
        ]
        client = _client()
        resp = client.chat.completions.create(
            model=FREELLM_MODEL,
            messages=full_messages,
            max_tokens=1024,
        )
        text       = resp.choices[0].message.content or ""
        model_used = resp.model or FREELLM_MODEL
        # The proxy sets x-routed-via; grab it if the client exposes raw headers
        routed_via = ""
        try:
            routed_via = resp._raw_response.headers.get("x-routed-via", "") or model_used
        except Exception:
            routed_via = model_used
        return text, model_used, routed_via
    except Exception as e:
        return f"AI service temporarily unavailable: {str(e)}", "none", ""


# ── Patient context builder ───────────────────────────────────────────────────

def _build_patient_context(visit_id: int) -> str:
    """Return a rich text block describing the patient for this visit.
    Injected into the system prompt so the AI knows who it's talking about.
    """
    conn = db.get_db()
    try:
        visit = conn.execute("""
            SELECT v.*, p.pet_name, p.species, p.breed, p.sex, p.dob,
                   p.weight_kg AS pet_weight, p.allergies, p.chronic_conditions,
                   p.neutered, o.full_name AS owner_name, o.phone AS owner_phone
            FROM visits v
            JOIN pets  p ON p.id = v.pet_id
            JOIN owners o ON o.id = v.owner_id
            WHERE v.id = %s
        """, (visit_id,)).fetchone()
        if not visit:
            return ""
        visit = dict(visit)

        # Age
        age_str = ""
        if visit.get("dob"):
            try:
                from datetime import date
                dob  = date.fromisoformat(str(visit["dob"])[:10])
                days = (date.today() - dob).days
                if days >= 365:
                    age_str = f"{days // 365} years"
                else:
                    age_str = f"{days} days"
            except Exception:
                pass

        # Last 5 diagnoses
        diags = conn.execute("""
            SELECT diagnosis, severity, created_at
            FROM diagnoses WHERE pet_id = %s
            ORDER BY created_at DESC LIMIT 5
        """, (visit["pet_id"],)).fetchall()

        # Active prescriptions
        rxs = conn.execute("""
            SELECT pi.medication_name, pi.dosage, pi.frequency, pi.duration_days
            FROM prescriptions pr
            JOIN prescription_items pi ON pi.prescription_id = pr.id
            WHERE pr.pet_id = %s AND pr.status IN ('Active','Dispensed')
            ORDER BY pr.created_at DESC LIMIT 5
        """, (visit["pet_id"],)).fetchall()

        # Upcoming vaccinations
        vax = conn.execute("""
            SELECT vaccine_name, next_due_at
            FROM vaccinations
            WHERE pet_id = %s AND next_due_at >= CURRENT_DATE
            ORDER BY next_due_at LIMIT 5
        """, (visit["pet_id"],)).fetchall()

        lines = [
            "═══ PATIENT CONTEXT (current visit) ═══",
            f"Pet      : {visit['pet_name']} ({visit['species']}"
            + (f", {visit['breed']}" if visit.get('breed') else "") + ")",
            f"Sex/Age  : {visit.get('sex','Unknown')}, {age_str}",
            f"Weight   : {visit.get('pet_weight') or visit.get('weight_kg','?')} kg",
        ]
        if visit.get("allergies"):
            lines.append(f"⚠️ Allergies: {visit['allergies']}")
        if visit.get("chronic_conditions"):
            lines.append(f"Chronic  : {visit['chronic_conditions']}")
        lines.append(f"Owner    : {visit['owner_name']} ({visit.get('owner_phone','')})")
        lines.append(f"Visit    : #{visit_id} — {visit.get('visit_type','?')} on {str(visit.get('visit_date',''))[:10]}")
        if visit.get("chief_complaint"):
            lines.append(f"Complaint: {visit['chief_complaint']}")
        if visit.get("symptoms"):
            lines.append(f"Symptoms : {visit['symptoms']}")

        vitals = []
        if visit.get("temp_c"):      vitals.append(f"Temp {visit['temp_c']}°C")
        if visit.get("heart_rate"):  vitals.append(f"HR {visit['heart_rate']} bpm")
        if visit.get("respiratory_rate"): vitals.append(f"RR {visit['respiratory_rate']}")
        if vitals:
            lines.append(f"Vitals   : {', '.join(vitals)}")

        if diags:
            lines.append("\nRecent diagnoses:")
            for d in diags:
                lines.append(f"  • {d['diagnosis']}" + (f" [{d['severity']}]" if d.get('severity') else ""))

        if rxs:
            lines.append("\nActive medications:")
            for r in rxs:
                lines.append(f"  • {r['medication_name']}" +
                             (f" — {r['dosage']}, {r['frequency']}" if r.get('dosage') else ""))

        if vax:
            lines.append("\nUpcoming vaccinations:")
            for v in vax:
                lines.append(f"  • {v['vaccine_name']} due {str(v['next_due_at'])[:10]}")

        lines.append("═══ END PATIENT CONTEXT ═══")
        return "\n".join(lines)
    except Exception as e:
        return f"[Patient context unavailable: {e}]"
    finally:
        conn.close()


# ── Conversation helpers ──────────────────────────────────────────────────────

def _save_pair(user_id: int, user_role: str, user_msg: str,
               assistant_reply: str, model_used: str = "",
               routed_via: str = "") -> None:
    """Persist a user+assistant exchange as one row in ai_conversations."""
    conn = db.get_db()
    with conn:
        conn.execute(
            """INSERT INTO ai_conversations
               (user_id, role, prompt, response, model_used)
               VALUES (?,?,?,?,?)""",
            (user_id, user_role, user_msg, assistant_reply,
             routed_via or model_used),
        )
    conn.close()


def _get_history_raw(user_id: int, limit: int = 50) -> list:
    """Fetch raw conversation rows newest-first."""
    conn = db.get_db()
    rows = conn.execute(
        "SELECT * FROM ai_conversations WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _build_messages_for_api(user_id: int) -> list:
    """Build the alternating user/assistant messages list for the Claude API (oldest first)."""
    rows = _get_history_raw(user_id, limit=20)
    rows.reverse()  # chronological
    messages = []
    for row in rows:
        if row.get("prompt"):
            messages.append({"role": "user", "content": row["prompt"]})
        if row.get("response"):
            messages.append({"role": "assistant", "content": row["response"]})
    return messages


# ── Routes ────────────────────────────────────────────────────────────────────

@ai_bp.route("/")
@login_required
def index():
    user = session["user"]
    history = _get_history_raw(user["id"], limit=50)
    history.reverse()  # chronological for display
    api_configured = _OPENAI_AVAILABLE
    return render_template(
        "ai_assistant/chat.html",
        active="ai",
        page_title="AI Assistant",
        history=history,
        api_configured=api_configured,
        user_role=user.get("role", ""),
    )


@ai_bp.route("/context/visit/<int:visit_id>")
@login_required
def context_visit(visit_id: int):
    """Return patient context for a visit as JSON (used by the visit detail panel)."""
    ctx = _build_patient_context(visit_id)
    return jsonify({"context": ctx, "visit_id": visit_id})


@ai_bp.route("/chat", methods=["POST"])
@login_required
def chat():
    user = session["user"]
    user_id = user["id"]
    user_role = user.get("role", "")

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    visit_id = data.get("visit_id")   # optional — set by visit detail panel

    if not message:
        return jsonify({"error": "Empty message"}), 400

    # Build patient context if a visit is specified
    patient_ctx = ""
    if visit_id:
        try:
            patient_ctx = _build_patient_context(int(visit_id))
        except Exception:
            patient_ctx = ""

    # Build context from history, then append the new user message
    messages = _build_messages_for_api(user_id)
    messages.append({"role": "user", "content": message})

    reply, model_used, routed_via = call_ai(messages, user_role,
                                            patient_context=patient_ctx)

    # Save the exchange as one row
    _save_pair(user_id, user_role, message, reply, model_used, routed_via)

    return jsonify({
        "role":       "assistant",
        "content":    reply,
        "model":      model_used,
        "routed_via": routed_via,
    })


@ai_bp.route("/history")
@login_required
def history():
    user = session["user"]
    rows = _get_history_raw(user["id"], limit=200)
    rows.reverse()
    # Group by date
    grouped: dict = {}
    for row in rows:
        date_key = (row.get("created_at") or "")[:10] or "Unknown"
        grouped.setdefault(date_key, []).append(row)

    return render_template(
        "ai_assistant/history.html",
        active="ai",
        page_title="AI Conversation History",
        grouped=grouped,
    )


@ai_bp.route("/clear", methods=["POST"])
@login_required
def clear():
    user = session["user"]
    conn = db.get_db()
    with conn:
        conn.execute("DELETE FROM ai_conversations WHERE user_id=?", (user["id"],))
    conn.close()
    flash("Conversation history cleared.", "success")
    return redirect(url_for("ai_assistant.index"))


# ── AI Smart Insights ─────────────────────────────────────────────────────────

@ai_bp.route("/insights", methods=["POST"])
@login_required
def insights():
    """Generate AI-powered daily clinic insights from live data."""
    today = date.today().isoformat()
    conn = db.get_db()

    def _q(sql, params=()):
        try:
            return conn.execute(sql, params).fetchone()[0]
        except Exception:
            return 0

    try:
        appts_today  = _q("SELECT COUNT(*) FROM appointments WHERE SUBSTRING(appt_date::text,1,10)=?", (today,))
        open_visits  = _q("SELECT COUNT(*) FROM visits WHERE status='Open'")
        rev_today    = _q("SELECT COALESCE(SUM(amount),0) FROM payments WHERE SUBSTRING(received_at::text,1,10)=?", (today,))
        unpaid_count = _q("SELECT COUNT(*) FROM invoices WHERE status='Unpaid'")
        unpaid_total = _q("SELECT COALESCE(SUM(due_amount),0) FROM invoices WHERE status='Unpaid'")
        low_stock    = _q("""
            SELECT COUNT(*) FROM items i
            WHERE i.reorder_level > 0 AND i.is_active = 1
            AND (SELECT COALESCE(SUM(sm.quantity),0) FROM stock_movements sm WHERE sm.item_id = i.id) <= i.reorder_level
        """)
        overdue_vax  = _q("SELECT COUNT(*) FROM vaccinations WHERE SUBSTRING(next_due_at::text,1,10)<? AND next_due_at IS NOT NULL", (today,))
        new_owners   = _q("SELECT COUNT(*) FROM owners WHERE SUBSTRING(created_at::text,1,10)=?", (today,))
    finally:
        conn.close()

    snapshot = (
        f"Today ({today}) clinic snapshot:\n"
        f"- Appointments today: {appts_today}\n"
        f"- Open/active visits right now: {open_visits}\n"
        f"- Revenue collected today: {float(rev_today):,.0f} EGP\n"
        f"- Unpaid invoices: {unpaid_count} totalling {float(unpaid_total):,.0f} EGP\n"
        f"- Inventory items at or below reorder level: {low_stock}\n"
        f"- Overdue vaccinations across all patients: {overdue_vax}\n"
        f"- New clients registered today: {new_owners}\n"
    )

    prompt = (
        f"You are the AI advisor for Premium Animal Hospital. Based on this clinic snapshot, "
        f"generate exactly 4 concise actionable insights for the clinic manager.\n\n"
        f"{snapshot}\n\n"
        f"Rules:\n"
        f"- Each insight must be 1-2 sentences, specific and actionable\n"
        f"- Choose appropriate severity: 'critical' (red), 'warning' (amber), 'success' (green), 'info' (blue)\n"
        f"- Return ONLY a valid JSON array — no markdown, no explanation\n"
        f"- Format: [{{\"icon\":\"emoji\",\"text\":\"insight text\",\"type\":\"critical|warning|success|info\"}}]"
    )
    reply, _, _ = call_ai([{"role": "user", "content": prompt}], "finance")

    try:
        m = re.search(r'\[.*\]', reply, re.DOTALL)
        result = json.loads(m.group()) if m else []
    except Exception:
        result = [{"icon": "🤖", "text": reply[:300], "type": "info"}]

    return jsonify({"insights": result, "generated_at": today})


# ── AI Pet Medical Summary ────────────────────────────────────────────────────

@ai_bp.route("/pet-summary/<int:pet_id>", methods=["POST"])
@login_required
def pet_summary(pet_id):
    """Generate a narrative clinical summary for a pet."""
    conn = db.get_db()
    try:
        pet = conn.execute("""
            SELECT p.*, o.full_name owner_name, o.phone owner_phone
            FROM pets p JOIN owners o ON o.id=p.owner_id
            WHERE p.id=?
        """, (pet_id,)).fetchone()
        if not pet:
            return jsonify({"error": "Pet not found"}), 404
        pet = dict(pet)

        visits = conn.execute(
            "SELECT visit_type, visit_date, doctor_name, chief_complaint FROM visits WHERE pet_id=? ORDER BY visit_date DESC LIMIT 10",
            (pet_id,)).fetchall()
        diags = conn.execute(
            "SELECT diagnosis, severity, created_at FROM diagnoses WHERE pet_id=? ORDER BY created_at DESC LIMIT 10",
            (pet_id,)).fetchall()
        rxs = conn.execute("""
            SELECT pi.medication_name, pi.dosage, pi.frequency
            FROM prescriptions pr JOIN prescription_items pi ON pi.prescription_id=pr.id
            WHERE pr.pet_id=? ORDER BY pr.created_at DESC LIMIT 8
        """, (pet_id,)).fetchall()
        vax = conn.execute(
            "SELECT vaccine_name, vaccinated_at, next_due_at FROM vaccinations WHERE pet_id=? ORDER BY vaccinated_at DESC LIMIT 8",
            (pet_id,)).fetchall()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

    prompt = (
        f"Write a professional veterinary medical summary for this patient (referral-letter style):\n\n"
        f"Patient: {pet['pet_name']}, {pet.get('species','?')}, {pet.get('breed','')}, "
        f"{pet.get('gender') or pet.get('sex','?')}\n"
        f"Owner: {pet['owner_name']} — {pet.get('owner_phone','')}\n"
        f"DOB: {str(pet.get('dob','?'))[:10]}  |  Weight: {pet.get('weight') or pet.get('weight_kg','?')} kg\n"
        f"Allergies: {pet.get('allergies') or 'None known'}\n"
        f"Chronic conditions: {pet.get('chronic_conditions') or 'None'}\n\n"
        f"Visit history ({len(visits)} recent):\n"
        + "\n".join(f"  • {v['visit_type']} on {str(v['visit_date'])[:10]} — {v.get('chief_complaint','')}" for v in visits) + "\n\n"
        f"Diagnoses:\n" + "\n".join(f"  • {d['diagnosis']}" + (f" [{d['severity']}]" if d.get('severity') else "") for d in diags) + "\n\n"
        f"Medications: {', '.join(r['medication_name'] for r in rxs) if rxs else 'None'}\n"
        f"Vaccinations: {', '.join(v['vaccine_name'] for v in vax) if vax else 'None'}\n\n"
        f"Write 2-3 professional paragraphs. Cover health background, notable medical history, "
        f"and current status/recommendations. Clinical tone."
    )
    reply, _, _ = call_ai([{"role": "user", "content": prompt}], "doctor")
    return jsonify({"summary": reply, "pet_name": pet["pet_name"]})


# ── AI WhatsApp Message Drafter ───────────────────────────────────────────────

@ai_bp.route("/draft-message", methods=["POST"])
@login_required
def draft_message():
    """AI-generate a personalized WhatsApp message."""
    data     = request.get_json(silent=True) or {}
    context  = data.get("context", "").strip()
    owner_id = data.get("owner_id")
    lang     = data.get("lang", "en")

    owner_info = ""
    if owner_id:
        conn = db.get_db()
        try:
            row = conn.execute("""
                SELECT o.full_name, o.phone,
                       COUNT(p.id) AS pet_count
                FROM owners o LEFT JOIN pets p ON p.owner_id=o.id
                WHERE o.id=? GROUP BY o.id
            """, (owner_id,)).fetchone()
            if row:
                owner_info = f"\nClient: {row['full_name']}, {row['pet_count']} pet(s)"
        except Exception:
            pass
        finally:
            conn.close()

    lang_instruction = "Write in Arabic." if lang == "ar" else "Write in English."
    prompt = (
        f"You are writing a WhatsApp message on behalf of Premium Animal Hospital (Dr. Hatem El Khateeb). "
        f"{lang_instruction}\n\n"
        f"Context: {context}{owner_info}\n\n"
        f"Write a warm, professional message (2-4 sentences). "
        f"Use the client's name if available. Max 2 emojis. "
        f"End with: Premium Animal Hospital."
    )
    reply, _, _ = call_ai([{"role": "user", "content": prompt}], "reception")
    return jsonify({"message": reply})


# ── AI Natural-Language Report Builder ───────────────────────────────────────

@ai_bp.route("/nl-report", methods=["POST"])
@login_required
def nl_report():
    """Parse a natural language request into report builder config."""
    data  = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "No query"}), 400

    today = date.today().isoformat()
    prompt = (
        f"Convert this natural language report request into a report configuration.\n"
        f"Request: \"{query}\"\n"
        f"Today: {today}\n\n"
        f"Available sources (use exact key):\n"
        f"  invoices — billing records\n"
        f"  appointments — scheduled visits\n"
        f"  visits — medical visit records\n"
        f"  payments — payments received\n"
        f"  owners — client/owner records\n"
        f"  pets — patient/pet records\n"
        f"  expenses — clinic expenses\n"
        f"  inventory — stock items\n\n"
        f"Return ONLY a JSON object (no markdown):\n"
        f"{{\"source\":\"key\",\"date_from\":\"YYYY-MM-DD or empty\",\"date_to\":\"YYYY-MM-DD or empty\","
        f"\"status\":\"status value or empty\",\"suggestion\":\"brief explanation\"}}\n\n"
        f"For relative dates (last month, this week etc), compute exact dates from today."
    )
    reply, _, _ = call_ai([{"role": "user", "content": prompt}], "finance")

    try:
        m = re.search(r'\{.*\}', reply, re.DOTALL)
        config = json.loads(m.group()) if m else {"suggestion": reply[:200]}
    except Exception:
        config = {"suggestion": reply[:200]}

    return jsonify(config)


# ── AI Predictive Health Alerts ───────────────────────────────────────────────

@ai_bp.route("/health-alerts", methods=["GET"])
@login_required
def health_alerts():
    """Return AI-scored action items: overdue vaccines, inactive clients, low stock."""
    today = date.today().isoformat()
    conn  = db.get_db()
    alerts = []
    try:
        # Overdue vaccinations
        overdue = conn.execute("""
            SELECT v.vaccine_name, p.pet_name, p.species, o.full_name owner_name,
                   v.next_due_at, o.id owner_id
            FROM vaccinations v
            JOIN pets p ON p.id=v.pet_id
            JOIN owners o ON o.id=p.owner_id
            WHERE v.next_due_at IS NOT NULL
              AND SUBSTRING(v.next_due_at::text,1,10) < ?
            ORDER BY v.next_due_at LIMIT 5
        """, (today,)).fetchall()
        for r in overdue:
            alerts.append({"icon":"💉","type":"warning","category":"Vaccine",
                           "text":f"{r['pet_name']} ({r['owner_name']}) — {r['vaccine_name']} overdue since {str(r['next_due_at'])[:10]}",
                           "link":f"/crm/owners/{r['owner_id']}"})

        # Low stock items
        low = conn.execute("""
            SELECT name, quantity, reorder_level, supplier
            FROM inventory_items
            WHERE quantity <= reorder_level AND reorder_level > 0
            ORDER BY (quantity - reorder_level) LIMIT 5
        """).fetchall()
        for r in low:
            alerts.append({"icon":"📦","type":"critical" if r["quantity"]==0 else "warning",
                           "category":"Stock",
                           "text":f"{r['name']} — {r['quantity']} left (reorder at {r['reorder_level']})" +
                                  (f" | Supplier: {r['supplier']}" if r.get('supplier') else ""),
                           "link":"/inventory"})

        # Unpaid invoices > 30 days
        from datetime import timedelta
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        old_unpaid = conn.execute("""
            SELECT i.invoice_number, o.full_name, i.due_amount, i.issue_date, o.id owner_id
            FROM invoices i JOIN owners o ON o.id=i.owner_id
            WHERE i.status='Unpaid'
              AND SUBSTRING(i.issue_date::text,1,10) < ?
            ORDER BY i.due_amount DESC LIMIT 5
        """, (cutoff,)).fetchall()
        for r in old_unpaid:
            alerts.append({"icon":"🧾","type":"critical","category":"Finance",
                           "text":f"Invoice {r['invoice_number']} — {r['full_name']} owes {float(r['due_amount']):,.0f} EGP (issued {str(r['issue_date'])[:10]})",
                           "link":f"/crm/owners/{r['owner_id']}"})

    except Exception:
        pass
    finally:
        conn.close()

    return jsonify({"alerts": alerts, "count": len(alerts)})


# ── AI Photo / Image Diagnosis ────────────────────────────────────────────────

@ai_bp.route("/analyze-photo", methods=["POST"])
@login_required
def analyze_photo():
    """Gemini Vision: analyze a clinical photo and suggest findings."""
    if not _OPENAI_AVAILABLE:
        return jsonify({"error": "AI package not installed"}), 503

    data     = request.get_json(silent=True) or {}
    b64      = data.get("image_b64", "")
    mime     = data.get("mime", "image/jpeg")
    context  = data.get("context", "")          # species, breed, chief complaint
    visit_id = data.get("visit_id")

    if not b64:
        return jsonify({"error": "No image data"}), 400

    patient_ctx = ""
    if visit_id:
        try:
            patient_ctx = _build_patient_context(int(visit_id))
        except Exception:
            pass

    system_txt = (
        "You are a veterinary clinical AI at Premium Animal Hospital. "
        "Analyze clinical images with professional accuracy. "
        "Always state this is AI-assisted analysis and requires veterinarian confirmation.\n"
    )
    if patient_ctx:
        system_txt += "\n" + patient_ctx

    user_content = [
        {
            "type": "text",
            "text": (
                f"Analyze this veterinary clinical image.\n"
                f"Context: {context or 'No additional context provided.'}\n\n"
                "Provide:\n"
                "1. **Visual Findings** — what you observe\n"
                "2. **Differential Diagnoses** — ranked by likelihood (top 3)\n"
                "3. **Recommended Next Steps** — tests or treatments\n"
                "4. **Urgency Level** — Emergency / Urgent / Routine\n\n"
                "Be concise and clinically precise."
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        },
    ]

    try:
        client = _client()
        resp = client.chat.completions.create(
            model=FREELLM_MODEL,
            messages=[
                {"role": "system", "content": system_txt},
                {"role": "user",   "content": user_content},
            ],
            max_tokens=1024,
        )
        analysis = resp.choices[0].message.content or ""
        return jsonify({"analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── AI Discharge Instructions ─────────────────────────────────────────────────

@ai_bp.route("/discharge-instructions/<int:visit_id>", methods=["POST"])
@login_required
def discharge_instructions(visit_id):
    """Generate bilingual discharge instructions for a completed visit."""
    conn = db.get_db()
    try:
        visit = conn.execute("""
            SELECT v.*, p.pet_name, p.species, p.breed, o.full_name owner_name, o.phone
            FROM visits v
            JOIN pets  p ON p.id = v.pet_id
            JOIN owners o ON o.id = v.owner_id
            WHERE v.id = ?
        """, (visit_id,)).fetchone()
        if not visit:
            return jsonify({"error": "Visit not found"}), 404
        visit = dict(visit)

        diags = conn.execute(
            "SELECT diagnosis, severity FROM diagnoses WHERE visit_id=? ORDER BY id",
            (visit_id,)).fetchall()
        rxs = conn.execute("""
            SELECT pi.medication_name, pi.dosage, pi.frequency, pi.duration_days, pi.instructions
            FROM prescriptions pr JOIN prescription_items pi ON pi.prescription_id=pr.id
            WHERE pr.visit_id=?
        """, (visit_id,)).fetchall()
        treatment = conn.execute(
            "SELECT plan_text, followup_in, followup_unit FROM treatment_plans WHERE visit_id=? LIMIT 1",
            (visit_id,)).fetchone()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

    diag_list = ", ".join(d["diagnosis"] for d in diags) if diags else "Not specified"
    med_lines = "\n".join(
        f"  • {r['medication_name']}: {r.get('dosage','')} — {r.get('frequency','')} for {r.get('duration_days','')} days"
        for r in rxs
    ) if rxs else "  None prescribed"
    followup = ""
    if treatment and treatment["followup_in"]:
        followup = f"Follow-up in {treatment['followup_in']} {treatment.get('followup_unit','days')}"

    prompt = (
        f"Generate professional discharge instructions for:\n"
        f"Patient: {visit['pet_name']} ({visit['species']}{', '+visit['breed'] if visit.get('breed') else ''})\n"
        f"Owner: {visit['owner_name']}\n"
        f"Diagnosis: {diag_list}\n"
        f"Medications:\n{med_lines}\n"
        f"Treatment Plan: {treatment['plan_text'] if treatment else 'Standard care'}\n"
        f"{followup}\n\n"
        "Write discharge instructions in TWO sections:\n"
        "**ENGLISH VERSION** — warm, clear, owner-friendly (not overly clinical)\n"
        "**ARABIC VERSION (التعليمات بالعربية)** — same content in Arabic\n\n"
        "Each version should include: care instructions at home, medications schedule, "
        "warning signs to watch for, and when to return. Keep each version under 200 words."
    )

    reply, _, _ = call_ai([{"role": "user", "content": prompt}], "doctor")
    return jsonify({
        "instructions": reply,
        "pet_name": visit["pet_name"],
        "owner_name": visit["owner_name"],
        "diagnosis": diag_list,
    })


# ── Outbreak Radar ────────────────────────────────────────────────────────────

@ai_bp.route("/outbreak-radar", methods=["GET"])
@login_required
def outbreak_radar():
    """Scan recent diagnoses for disease clusters — flag potential outbreaks."""
    today   = date.today().isoformat()
    cutoff  = (date.today() - __import__("datetime").timedelta(days=7)).isoformat()
    conn    = db.get_db()
    outbreaks = []
    raw_data  = []

    try:
        rows = conn.execute("""
            SELECT d.diagnosis, COUNT(DISTINCT d.pet_id) pet_count,
                   COUNT(*) case_count,
                   MIN(SUBSTRING(d.created_at::text,1,10)) first_seen,
                   MAX(SUBSTRING(d.created_at::text,1,10)) last_seen
            FROM diagnoses d
            WHERE SUBSTRING(d.created_at::text,1,10) >= ?
            GROUP BY d.diagnosis
            HAVING COUNT(DISTINCT d.pet_id) >= 2
            ORDER BY pet_count DESC
        """, (cutoff,)).fetchall()
        raw_data = [dict(r) for r in rows]

        for r in raw_data:
            level = "alert" if r["pet_count"] >= 3 else "watch"
            outbreaks.append({
                "diagnosis":  r["diagnosis"],
                "pet_count":  r["pet_count"],
                "case_count": r["case_count"],
                "first_seen": r["first_seen"],
                "last_seen":  r["last_seen"],
                "level":      level,
            })
    except Exception:
        pass
    finally:
        conn.close()

    # AI commentary on clusters (if any alerts)
    ai_comment = ""
    if any(o["level"] == "alert" for o in outbreaks):
        names = [o["diagnosis"] for o in outbreaks if o["level"] == "alert"]
        prompt = (
            f"The following diagnoses have appeared in 3+ different pets in the last 7 days "
            f"at a veterinary clinic: {', '.join(names)}. "
            "In 2-3 sentences, assess the public health risk and recommend any immediate actions "
            "for the clinic. Be concise and professional."
        )
        ai_comment, _, _ = call_ai([{"role": "user", "content": prompt}], "doctor")

    return jsonify({
        "outbreaks": outbreaks,
        "ai_comment": ai_comment,
        "scan_period": f"{cutoff} → {today}",
        "alert_count": sum(1 for o in outbreaks if o["level"] == "alert"),
    })


# ── Drug Interaction Checker ──────────────────────────────────────────────────

@ai_bp.route("/drug-interactions", methods=["POST"])
@login_required
def drug_interactions():
    """Check for dangerous drug interactions using AI."""
    data       = request.get_json(silent=True) or {}
    new_drug   = data.get("new_drug", "").strip()
    current_rx = data.get("current_medications", [])   # list of strings
    species    = data.get("species", "")

    if not new_drug:
        return jsonify({"safe": True, "message": "No drug specified"})

    if not current_rx:
        return jsonify({
            "safe": True,
            "message": f"No current medications on file — {new_drug} can be prescribed.",
            "severity": "none",
        })

    prompt = (
        f"You are a veterinary pharmacist. Check for drug interactions.\n"
        f"Patient species: {species or 'Unknown'}\n"
        f"NEW drug being prescribed: {new_drug}\n"
        f"CURRENT active medications: {', '.join(current_rx)}\n\n"
        "Reply with a JSON object ONLY (no markdown):\n"
        '{"safe": true/false, "severity": "none|mild|moderate|severe", '
        '"interactions": [{"drugs": "A + B", "effect": "description"}], '
        '"recommendation": "brief clinical recommendation"}'
    )

    reply, _, _ = call_ai([{"role": "user", "content": prompt}], "doctor")

    try:
        m = re.search(r'\{.*\}', reply, re.DOTALL)
        result = json.loads(m.group()) if m else {}
        if not result:
            raise ValueError
    except Exception:
        result = {
            "safe": True,
            "severity": "unknown",
            "interactions": [],
            "recommendation": reply[:300],
        }

    return jsonify(result)
