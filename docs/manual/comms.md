# WhatsApp & Communications — Reference Manual

**Modules:** WhatsApp Control Center / مركز تحكم واتساب · Notifications / الإشعارات
**URL prefixes:** `/whatsapp/` and `/notifications/`
**Blueprints:** `whatsapp`, `notifications`
**Outbound transport:** Wapilot v2 (`https://api.wapilot.net/api/v2`)

This chapter is a **screen-by-screen reference**. It describes only what the code
in `blueprints/whatsapp/routes.py`, `blueprints/whatsapp/wapilot.py`,
`blueprints/whatsapp/scheduler.py`, `blueprints/notifications/routes.py` and the
templates under `templates/whatsapp/` and `templates/notifications/` actually
does today. A control that exists on screen but does nothing, a column the query
never returns, and a database field with no screen behind it are listed under
[Known limits](#known-limits) rather than written up as working features.

Two things are worth knowing before you read a single screen:

1. **Nothing is sent from the browser.** Every WhatsApp call is proxied through
   the Flask backend so the Wapilot API token never reaches the page. The
   token lives in the `settings` table under category `wapilot`, or in the
   `WAPILOT_TOKEN` / `WAPILOT_INSTANCE` environment variables.
2. **If the token or the instance ID is missing, most WhatsApp screens will not
   open at all.** They redirect to Settings with a flash. See §3.2.

> Source: `platform/app.py:219`, `:231` (blueprint imports), `:247`, `:259`
> (registration), `platform/blueprints/whatsapp/__init__.py:1-3`,
> `platform/blueprints/notifications/__init__.py:1-3`,
> `platform/blueprints/whatsapp/wapilot.py:11` (`BASE_URL`)

---

## 1. Getting into the modules

### 1.1 WhatsApp

| Door | Where | Goes to |
|---|---|---|
| Sidebar → PLATFORM / المنصة → **WhatsApp / واتساب** | every page | `/whatsapp/control` (Control Center) |
| Sidebar → PLATFORM / المنصة → **Reminder Settings / إعدادات التذكير** | every page, four roles only | `/whatsapp/reminder-settings` → redirects to `/whatsapp/settings` |
| Launcher card **WhatsApp Communication Center / مركز التواصل عبر واتساب** (💬) | `/` | `/whatsapp/control` |
| Launcher stat tile **Reminders / التذكيرات** (WhatsApp pending / واتساب معلّق) | `/` | `/whatsapp/control` |
| Client record → Communication History → **✉️ Send Message / إرسال رسالة** | `/crm/owners/<id>` | `/whatsapp/send-center` |
| `/whatsapp/` (bare prefix) | typed URL | 302 to `/whatsapp/control` |

The **WhatsApp** sidebar entry carries **no role condition** — it is rendered for
every signed-in user. A role that does not hold the `whatsapp` grant sees the
link, clicks it, and is bounced to the launcher with *"You don't have permission
to access this page."* See §2.

The **Reminder Settings** sidebar entry is wrapped in a role test for
`super_admin`, `clinic_owner`, `branch_manager`, `support_admin`. Three of those
four can use it. `support_admin` cannot — see [Known limits](#permissions).

> Source: `platform/templates/base.html:263-266` (WhatsApp, no role guard),
> `:276-281` (Reminder Settings, role-guarded),
> `platform/blueprints/launcher/routes.py:308-322` (module card),
> `platform/templates/launcher.html:415-420` (stat tile),
> `platform/templates/crm/owner_detail.html:584-586`,
> `platform/blueprints/whatsapp/routes.py:79-82` (`/whatsapp/` redirect)

### 1.2 Notifications

| Door | Where | Goes to |
|---|---|---|
| Top bar 🔔 bell | every page, signed-in only | `/notifications/` |
| Sidebar → PLATFORM / المنصة → **Notifications / الإشعارات** | every page, signed-in only | `/notifications/` |
| Launcher card **Notifications Center / مركز الإشعارات** (🔔) | `/` | `/notifications/` |

Both the bell and the sidebar item carry a red count badge when there are unread
notifications. The badge prints the number up to 99 and then `99+`. The count
comes from the application-wide context processor, which runs
`count_unread_notifications()` on **every page render** for the signed-in user.

> Source: `platform/templates/base.html:267-275` (sidebar item + badge),
> `:421-431` (top-bar bell + badge),
> `platform/app.py:400-404` (`unread_count`), `:452`,
> `platform/blueprints/launcher/routes.py:415-429` (module card),
> `platform/models/database.py:4183-4190` (`count_unread_notifications`)

---

## 2. Who can open what

### 2.1 The two gates

Two independent gates apply to every WhatsApp route, and **both must pass**:

1. **The module grant.** The blueprint name `whatsapp` maps directly to the
   `whatsapp` permission key, which is a real, grantable key on the Roles
   screen. It is checked for every route in the blueprint, including the many
   that carry no role list of their own. `super_admin` bypasses it entirely.
2. **The route's own role list**, where one is declared with `@role_required`.

A grant can only ever **narrow**. It never widens: holding the `whatsapp` grant
does not let a receptionist delete a template if the delete route names only
three roles.

Roles holding `whatsapp` by default: **clinic_owner** (holds every key),
**branch_manager**, **reception** — plus **super_admin**, which is exempt.

Every other role — doctor, nurse, pharmacist, inventory_mgr, finance, hr,
groomer, boarding_staff, support_admin, auditor — does **not** hold `whatsapp`
and is redirected to the launcher from every WhatsApp URL.

> Source: `platform/blueprints/auth/routes.py:59-69` (`login_required`),
> `:88-131` (`_permission_denied`, the module gate), `:137-160`
> (`_BP_PERMISSION` — `whatsapp` is not remapped, so it uses its own name),
> `:167-194` (`role_required`),
> `platform/models/database.py:4302-4329` (`ALL_PERMISSIONS`, `whatsapp` at
> `:4310`), `:4346-4379` (`DEFAULT_ROLE_PERMISSIONS`)

### 2.2 Notifications has no gate

The blueprint name `notifications` is **not** in `ALL_PERMISSIONS`, so
`_permission_for()` returns an empty key and the module gate falls open. Every
signed-in user of any role can open `/notifications/` and its endpoints. This is
deliberate — there is nothing to grant, and each route is already scoped to
`session["user"]["id"]`, so one user cannot read or mark another's notifications.

> Source: `platform/blueprints/auth/routes.py:113-115`, `:149-160`
> (`_permission_for` returns `""` for an ungrantable blueprint),
> `platform/blueprints/notifications/routes.py:12`, `:23`, `:30`, `:38-39`

### 2.3 Effective access, per route — WhatsApp

`Role list` is what `@role_required` declares. `Who can actually use it` is that
list intersected with the roles that hold the `whatsapp` grant, plus
`super_admin`.

#### Screens (HTML)

| Screen / action | Route | Role list on the route | Who can actually use it |
|---|---|---|---|
| Redirect to Control Center | `GET /whatsapp/` | none (login only) | super_admin, clinic_owner, branch_manager, reception |
| Control Center | `GET /whatsapp/control` | none | same as above |
| Send Center | `GET /whatsapp/send-center` | none | same as above |
| Campaigns list | `GET /whatsapp/campaigns` | none | same as above |
| New campaign | `GET/POST /whatsapp/campaigns/new` | super_admin, clinic_owner, branch_manager, support_admin | super_admin, clinic_owner, branch_manager |
| Campaign detail | `GET /whatsapp/campaigns/<campaign_id>` | none | super_admin, clinic_owner, branch_manager, reception |
| Templates list | `GET /whatsapp/templates` | none | same as above |
| New template | `GET/POST /whatsapp/templates/new` | super_admin, clinic_owner, branch_manager, support_admin, reception | super_admin, clinic_owner, branch_manager, reception |
| Edit template | `GET/POST /whatsapp/templates/<tid>/edit` | same as above | super_admin, clinic_owner, branch_manager, reception |
| Delete template | `POST /whatsapp/templates/<tid>/delete` | super_admin, clinic_owner, branch_manager | super_admin, clinic_owner, branch_manager |
| Pending Reminders | `GET /whatsapp/reminders` | none | super_admin, clinic_owner, branch_manager, reception |
| Send one reminder (JSON) | `POST /whatsapp/reminders/<rid>/send` | none | same as above |
| Mark reminder sent | `POST /whatsapp/reminders/<rid>/mark-sent` | none | same as above |
| Message Log | `GET /whatsapp/log` | none | same as above |
| Settings | `GET/POST /whatsapp/settings` | super_admin, clinic_owner, branch_manager, support_admin | super_admin, clinic_owner, branch_manager |
| Reminder Settings alias | `GET /whatsapp/reminder-settings` | none | super_admin, clinic_owner, branch_manager, reception — but the destination refuses reception |
| Reminder Admin | `GET /whatsapp/reminder-admin` | none | super_admin, clinic_owner, branch_manager, reception |
| Run reminder job now | `POST /whatsapp/reminder-admin/trigger` | super_admin, clinic_owner, branch_manager, support_admin | super_admin, clinic_owner, branch_manager |
| Create manual reminder | `POST /whatsapp/reminder-admin/reminders/new` | none | super_admin, clinic_owner, branch_manager, reception |
| Cancel reminder | `POST /whatsapp/reminder-admin/reminders/<rid>/cancel` | none | same as above |
| Send reminder now | `POST /whatsapp/reminder-admin/reminders/<rid>/send-now` | none | same as above |
| Send free-text message | `POST /whatsapp/send` | none | same as above |
| Scheduler page | `GET /whatsapp/scheduler` | none | same as above |
| Run scheduler jobs | `POST /whatsapp/scheduler/run` | none | same as above |
| Clear run history | `POST /whatsapp/scheduler/clear-history` | none | same as above |

#### Background JSON endpoints

| Endpoint | Method | Role list | Who can actually use it |
|---|---|---|---|
| `/whatsapp/api/instance/status` | GET | none | super_admin, clinic_owner, branch_manager, reception |
| `/whatsapp/api/instance/details` | GET | none | same |
| `/whatsapp/api/instance/qr` | GET | none | same |
| `/whatsapp/api/instance/screenshot` | GET | none | same |
| `/whatsapp/api/instance/start` | POST | super_admin, clinic_owner, branch_manager, support_admin | super_admin, clinic_owner, branch_manager |
| `/whatsapp/api/instance/restart` | POST | same | super_admin, clinic_owner, branch_manager |
| `/whatsapp/api/instance/logout` | POST | same | super_admin, clinic_owner, branch_manager |
| `/whatsapp/api/instance/troubleshoot` | POST | super_admin, clinic_owner | super_admin, clinic_owner |
| `/whatsapp/api/instance/queue-settings` | GET, PUT | none | super_admin, clinic_owner, branch_manager, reception |
| `/whatsapp/api/messages` | GET | none | same |
| `/whatsapp/api/messages/<msg_id>` | GET | none | same |
| `/whatsapp/api/messages/<msg_id>/retry` | POST | none | same |
| `/whatsapp/api/messages/retry-all` | POST | super_admin, clinic_owner, branch_manager | super_admin, clinic_owner, branch_manager |
| `/whatsapp/api/send/text` | POST | none | super_admin, clinic_owner, branch_manager, reception |
| `/whatsapp/api/send/image` | POST | none | same |
| `/whatsapp/api/send/file` | POST | none | same |
| `/whatsapp/api/send/video` | POST | none | same |
| `/whatsapp/api/campaigns` | GET | none | same |
| `/whatsapp/api/campaigns` | POST | super_admin, clinic_owner, branch_manager | super_admin, clinic_owner, branch_manager |
| `/whatsapp/api/campaigns/<cid>/start` | POST | super_admin, clinic_owner, branch_manager, support_admin | super_admin, clinic_owner, branch_manager |
| `/whatsapp/api/campaigns/<cid>/pause` | POST | same | super_admin, clinic_owner, branch_manager |
| `/whatsapp/api/campaigns/<cid>/finish` | PATCH | super_admin, clinic_owner, branch_manager | super_admin, clinic_owner, branch_manager |
| `/whatsapp/api/campaigns/<cid>/copy` | POST | same | super_admin, clinic_owner, branch_manager |
| `/whatsapp/api/campaigns/<cid>/reset-failed` | POST | same | super_admin, clinic_owner, branch_manager |
| `/whatsapp/api/campaigns/<cid>/schedule` | POST, DELETE | same | super_admin, clinic_owner, branch_manager |
| `/whatsapp/api/campaigns/<cid>/delay` | GET, PATCH | none | super_admin, clinic_owner, branch_manager, reception |
| `/whatsapp/api/campaigns/<cid>/messages` | GET, POST, DELETE | none | same |
| `/whatsapp/api/campaigns/<cid>/stats` | GET | none | same |
| `/whatsapp/api/campaigns/<cid>/queue` | GET | none | same |
| `/whatsapp/api/campaigns/<cid>/done` | GET | none | same |
| `/whatsapp/api/templates` | GET | none | same |
| `/whatsapp/api/lookup/lid/<lid>` | GET | none | same |
| `/whatsapp/api/lookup/phone/<phone>` | GET | none | same |

**`support_admin` is named on seven route role lists and can reach none of
them.** Its default grant set is `["system","backup","audit","settings"]`, which
does not contain `whatsapp`, so the module gate refuses it before the role list
is ever consulted. To make those seven role lists meaningful, an administrator
must add the `whatsapp` grant to the `support_admin` role on the Roles screen.

**Reception sees buttons it cannot use.** Start / Restart / Logout / Fix on the
Control Center, and Start / Pause / Copy / Reset / New Campaign on the Campaigns
screen, are rendered unconditionally. A receptionist pressing them gets a silent
no-op — see [Known limits](#permissions) for why nothing appears on screen.

> Source: `platform/blueprints/whatsapp/routes.py:79-81, 85-87, 126-128,
> 133-135, 140-142, 147-149, 154-156, 161-163, 168-170, 175-177, 182-184,
> 198-200, 206-208, 213-215, 220-222, 232-234, 244-246, 270-272, 283-285,
> 296-298, 313-315, 326-328, 356-358, 382-384, 389-391, 400-402, 407-409,
> 414-416, 421-423, 428-430, 435-437, 446-448, 457-459, 472-474, 479-481,
> 486-488, 497-499, 509-511, 548-550, 587-589, 598-600, 614-616, 632-634,
> 661-663, 678-680, 697-699, 773-775, 783-785, 790-792, 803-805, 881-883,
> 894-896, 920-922, 931-933, 964-966, 1001-1003, 1080-1082, 1115-1117`;
> `platform/models/database.py:4376` (`support_admin` grants)

### 2.4 Effective access — Notifications

| Screen / action | Route | Gate | Who can use it |
|---|---|---|---|
| Notification list | `GET /notifications/` | login only | every signed-in user |
| Mark one read | `POST /notifications/mark-read/<notif_id>` | login only | every signed-in user, own rows only |
| Mark all read | `POST /notifications/mark-all-read` | login only | every signed-in user, own rows only |
| Unread JSON | `GET /notifications/api/unread` | login only | every signed-in user, own rows only |

> Source: `platform/blueprints/notifications/routes.py:8-40`

---

## 3. Things that apply to every screen in this chapter

### 3.1 The Wapilot client

Every outbound WhatsApp call goes through `WapilotClient`, a thin
`urllib.request` wrapper with a **15-second timeout** per call. Authentication is
a raw `token:` header — not `Authorization: Bearer`. Every method returns a
`(data, error)` pair: `error` is `""` on success, and on an HTTP error it reads
`HTTP <code>: <reason>` while `data` still carries the parsed error body. On a
transport failure (DNS, connection refused, timeout) `data` is `{}` and `error`
is the raw exception text.

The base URL is hard-coded as `https://api.wapilot.net/api/v2`. There is no
setting for it.

> Source: `platform/blueprints/whatsapp/wapilot.py:11`, `:23-27` (headers),
> `:29-57` (`_request`, timeout at `:43`, error shapes at `:49-57`)

### 3.2 "WhatsApp is not configured"

`_client()` reads `wapilot_token` and `wapilot_instance_id` from the `settings`
table (category `wapilot`), falling back to `$WAPILOT_TOKEN` and
`$WAPILOT_INSTANCE`. If **either** is blank it raises `WapilotNotConfigured`
with this exact message:

> WhatsApp is not configured. Set the Wapilot API token and instance ID under
> WhatsApp → Settings, or via the WAPILOT_TOKEN / WAPILOT_INSTANCE environment
> variables.

A blueprint-level error handler catches it and behaves in one of two ways:

- **Request path contains `/api/` or the request is JSON** → HTTP **503** with
  body `{"ok": false, "data": {}, "error": "<the message above>"}`.
- **Anything else** → the message is flashed as `danger` and the browser is
  redirected to `/whatsapp/settings`.

Which screens are affected, because they call `_client()` before rendering:

| Screen | Behaviour when unconfigured |
|---|---|
| Control Center `/whatsapp/control` | redirect to Settings + flash |
| Campaigns list `/whatsapp/campaigns` | redirect to Settings + flash |
| Campaign detail `/whatsapp/campaigns/<id>` | redirect to Settings + flash |
| New campaign `POST` | redirect to Settings + flash |
| Send Center `/whatsapp/send-center` | **opens normally**; each send returns 503 |
| Templates, Message Log, Reminders, Reminder Admin, Scheduler, Settings | **open normally** — they touch no API |

Because the redirect target is `/whatsapp/settings`, and that route refuses
`reception`, a receptionist on an unconfigured clinic who clicks WhatsApp in the
sidebar is bounced twice and lands on the launcher.

> Source: `platform/blueprints/whatsapp/routes.py:20-29` (`WapilotNotConfigured`
> and the handler), `:32-48` (`_client`), `:89`, `:315`, `:329`, `:359`,
> `:697-699` (Settings role list)

### 3.3 Phone numbers and chat IDs

The Wapilot v2 API addresses a **conversation**, not a phone number. The
platform builds the chat ID like this, in three of the four send paths:

```
chat_id = phone  if "@" in phone  else  phone.lstrip("+") + "@c.us"
```

So `+201012345678` and `201012345678` both become `201012345678@c.us`, and a
value you type that already contains `@` is passed through untouched. The
Send Center placeholder says so: *"e.g. 201012345678 or chat_id@c.us"*.

**The nightly reminder job does not do this.** It passes the stored
`owners.whatsapp_phone` straight through with only `.strip()` applied. See
[Known limits](#sending-and-logging).

Owner phone numbers are read as `whatsapp_phone` first, then `phone`, in the two
reminder send routes.

> Source: `platform/blueprints/whatsapp/routes.py:56` (`_send_and_log`), `:250`
> (`api_send_text`), `:275`, `:288`, `:300` (media), `:347`, `:946` (phone
> fallback); `platform/blueprints/whatsapp/scheduler.py:148-149`

### 3.4 CSRF

Every state-changing request needs the token. Server-rendered forms carry it as
a hidden `_csrf_token` field; every `fetch()` in this module sends it as an
`X-CSRF-Token` header read from `<meta name="csrf-token">`. A request without it
never reaches the route — the application renders a 403 page reading *"Invalid
or missing security token. Please go back and try again."*

> Source: `platform/app.py:349-357`,
> `platform/models/security.py:270-279` (accepted token sources)

### 3.5 Toasts and result boxes

The Control Center, Campaigns list and Campaign detail all use the same
bottom-right **toast**: dark green on success, dark red on failure, gone after
**4 seconds**. Success text is generic — `"<action> triggered"`, `"Queue
settings saved"`, `"Message retried"` — and failure text is `"Error: <the API's
error string>"`.

The Send Center uses an inline **result box** under the form instead:
`✅ Sent to <phone>` / `✅ <type> sent` in green, `❌ Error: <message>` in red,
hidden again after **6 seconds**.

> Source: `platform/templates/whatsapp/control_center.html:275-281`,
> `campaigns_list.html:117-123`, `campaign_detail.html:242-248`,
> `send_center.html:276-282`

### 3.6 Audit trail

Only these WhatsApp actions write an audit row, all under module `whatsapp`:

| Action | Audit `action` / `entity_type` | Details written |
|---|---|---|
| Create campaign | `create` / `campaign` | `Created campaign <id>: <first 60 chars of default message>` |
| Create template | `create` / `template` | `Created template: <name>` |
| Update template | `update` / `template` (with `entity_id`) | `Updated template: <name>` |
| Save Settings | `update` / `settings` | `Updated WhatsApp / Wapilot settings` |
| Nightly reminder run | `reminder_run` / `scheduler`, username `scheduler`, role `system` | `appt=<n> vaccine=<n> invoice=<n>` |

**Not audited:** deleting a template, sending any message (manual or media),
creating / cancelling / sending a reminder, marking a reminder sent, triggering
the scheduler from the Scheduler page, clearing run history, and every instance
and campaign control (start, restart, logout, troubleshoot, pause, copy,
schedule, reset-failed, queue settings, bulk add, bulk delete).

> Source: `platform/blueprints/whatsapp/routes.py:341-349` (campaign),
> `:532-540` (template create), `:571-579` (template update), `:744-750`
> (settings), `platform/blueprints/whatsapp/scheduler.py:353-360` (run)

### 3.7 Bilingual coverage

Almost every visible label in this module is written `t('English', 'العربية')`
and flips with the interface language, and the layout flips to RTL in Arabic.
The exceptions are called out per screen and collected in
[Known limits](#bilingual-coverage). The largest of them: the whole
**Notifications** screen body, the Reminder Admin's **Overdue** and **Upcoming**
section headings, the campaign form's explanatory paragraph, and every string
produced by JavaScript (toasts, result boxes, `confirm()` dialogs, table
headers rendered by `renderMessages()`).

### 3.8 Times and dates

`whatsapp_log.sent_at`, `reminders.sent_at` and `reminder_runs.run_at` are all
written with SQL `NOW()` or `datetime('now')`, both of which the database layer
rewrites to the **clinic's local time** on either engine — SQLite gets
`datetime('now','localtime')` appended, PostgreSQL evaluates `NOW()` in the
server timezone. The reminder scheduler additionally binds its own timestamp
from Python's `datetime.now()` so that its dedup gate and its stored marker
agree on one clock.

Screens truncate rather than format: the Message Log prints
`sent_at[:16]` (`YYYY-MM-DD HH:MM`), the Reminder Admin prints
`scheduled_for[:16]`, and the Scheduler history prints `run_at[:16]`. There is
no locale-aware date formatting anywhere in this module.

> Source: `platform/models/database.py:625-662` (`_fix_sql_sqlite`, `NOW()` →
> local), `platform/blueprints/whatsapp/scheduler.py:13-38` (`_run_stamp`,
> `_run_date`)

---

## 4. Screen: WhatsApp Control Center

**URL.** `GET /whatsapp/control` (and `GET /whatsapp/`, which redirects here)

**Purpose.** The landing page of the module: connection state of the WhatsApp
instance, the QR code for linking a phone, a live screenshot of the session,
Wapilot's throttling settings, the last ten logged messages, and the live
message queue from the API.

**How to reach it.** Sidebar → WhatsApp; the launcher card; the launcher
Reminders tile; `← Control Center / ← مركز التحكم` from Send Center, Settings,
Campaigns, Reminder Admin or Scheduler.

**Who can open it.** Any role holding the `whatsapp` grant — super_admin,
clinic_owner, branch_manager, reception. **If the Wapilot credentials are not
set the page does not render at all**; see §3.2.

**Page title.** `WhatsApp Control Center / مركز تحكم واتساب`
**Subtitle.** `Manage your WhatsApp instance, campaigns, templates & messaging /
إدارة حساب واتساب والحملات والقوالب والمراسلة`

### 4.1 Toolbar buttons

| Button | Goes to |
|---|---|
| `✉️ Send Message` / `✉️ إرسال رسالة` | `/whatsapp/send-center` |
| `📣 Campaigns` / `📣 الحملات` | `/whatsapp/campaigns` |
| `📋 Templates` / `📋 القوالب` | `/whatsapp/templates` |
| `⚙️ Settings` / `⚙️ الإعدادات` | `/whatsapp/settings` — denied to reception |
| `🔔 Reminder Admin` / `🔔 إدارة التذكيرات` | `/whatsapp/reminder-admin` |

There is **no link from this page to the Message Log** other than the
`View All Logs → / عرض كل السجلات ←` button inside the log tab, and **no link at
all to the Scheduler page**.

> Source: `platform/templates/whatsapp/control_center.html:6-12`, `:239-241`

### 4.2 The four counters

| Card | What it shows | Where the number comes from |
|---|---|---|
| **Instance Status / حالة الحساب** | The status word in upper case, e.g. `CONNECTED` | Filled by JavaScript from `/whatsapp/api/instance/status` on page load and every 30 s. Shows `—` until the first response, `Unreachable` if the fetch throws |
| **Active Templates / القوالب النشطة** | Rendered server-side | `SELECT COUNT(*) FROM whatsapp_templates WHERE is_active=1` |
| **Pending Reminders / تذكيرات معلقة** | Rendered server-side | `SELECT COUNT(*) FROM reminders WHERE status='Pending'` |
| **Messages Queued / رسائل في الطابور** | `—` until you open the API Messages tab and press Refresh | Counted in the browser from the fetched list: messages whose `status` is `queued` or `pending` |

> Source: `platform/blueprints/whatsapp/routes.py:103-108`,
> `platform/templates/whatsapp/control_center.html:96-113`, `:294-316`,
> `:431-433`, `:473-476`

### 4.3 Instance card (left column)

Heading: `📱 Instance — <instance_id>`, where `<instance_id>` is the configured
Wapilot instance unique name. **This heading is English-only.**

**Status badge.** A coloured pill with a dot. The CSS class is the status word
returned by the API, lower-cased, so only four are actually styled:

| Status word | Pill | Dot |
|---|---|---|
| `connected` | green | green, pulsing every 2 s |
| `disconnected` | red | red, static |
| `qr` | amber | amber, pulsing every 1 s |
| `unknown` | grey | grey, static |
| anything else | unstyled (transparent) | unstyled |

The badge text is the raw status word with its first letter capitalised. Before
the first response it reads `Checking… / جارٍ الفحص…`.

**QR section.** Hidden by default. It appears automatically when the status is
`qr` or `scan`, and the QR image is fetched at the same time. It also appears
when you press `📷 Show QR`. Under the image:
*"Open WhatsApp → Linked Devices → Scan this QR code" / "افتح واتساب ← الأجهزة
المرتبطة ← امسح رمز QR"*.

The QR image is accepted from any of four keys in the API response — `qr`,
`qr_code`, `base64`, `image` — and rendered as a `data:image/png;base64,…` URI
unless the value already starts with `data:`. If none of the four is present the
box shows the API error, or the fallback text *"QR not available yet. Make sure
instance is started."* (English-only).

**Action buttons.**

| Button | Calls | Toast on press | Effect |
|---|---|---|---|
| `▶ Start` / `▶ بدء` | `POST /whatsapp/api/instance/start` | `Starting…` | Starts the Wapilot instance |
| `🔄 Restart` / `🔄 إعادة تشغيل` | `POST …/restart` | `Restarting…` | Restarts it |
| `↩ Logout` / `↩ تسجيل خروج` | `POST …/logout` | `Logging out…` | Unlinks the phone. The next connection needs a fresh QR scan |
| `🛠 Fix` / `🛠 إصلاح` | `POST …/troubleshoot` | `Troubleshooting…` | Runs Wapilot's own troubleshoot routine. **super_admin and clinic_owner only** |
| `📷 Show QR` / `📷 عرض QR` | `GET …/qr` | — | Reveals the QR panel and loads the code |

The four action buttons show an immediate "in progress" toast, then a second
toast reading `<action> successful` or `Error: <message>`, then re-poll the
status after **2 seconds**. None of them asks for confirmation — including
Logout, which drops the WhatsApp session for the whole clinic.

All five buttons are rendered for every user who can open the page. Reception
and (for Fix) branch_manager will be refused server-side, and because the
refusal is an HTML redirect rather than JSON, `r.json()` throws and **no toast
appears at all** — the button looks like it did nothing.

> Source: `platform/templates/whatsapp/control_center.html:120-146`, `:293-335`,
> `:354-365`; `platform/blueprints/whatsapp/routes.py:154-179`;
> `platform/blueprints/auth/routes.py:184-190` (the redirect)

### 4.4 Live Screenshot card

Heading `🖼 Live Screenshot / 🖼 لقطة شاشة مباشرة`. Starts empty with
*"Click to load… / اضغط للتحميل…"*. `🔄 Refresh Screenshot / 🔄 تحديث اللقطة`
calls `GET /whatsapp/api/instance/screenshot` and renders the returned image from
whichever of `screenshot`, `image` or `base64` is present, again as a base64
data URI. On failure it prints the API error or `Screenshot unavailable`
(English-only).

> Source: `platform/templates/whatsapp/control_center.html:148-155`, `:337-352`

### 4.5 Queue Settings card

Heading `⚙️ Queue Settings / ⚙️ إعدادات الطابور`. Six numeric boxes that map
one-for-one onto Wapilot's instance throttling settings. **The boxes start
empty** — nothing is loaded until you press Load.

| Field | Label | Wapilot key | `min` | Placeholder |
|---|---|---|---|---|
| `q-wf` | Min delay (s) / أقل تأخير (ث) | `wait_between_messages_from` | 0 | `e.g. 3` |
| `q-wt` | Max delay (s) / أقصى تأخير (ث) | `wait_between_messages_to` | 0 | `e.g. 8` |
| `q-sf` | Sleep after (min) / الإيقاف بعد (أدنى) | `sleep_after_from` | 1 | `e.g. 20` |
| `q-st` | Sleep after (max) / الإيقاف بعد (أقصى) | `sleep_after_to` | 1 | `e.g. 50` |
| `q-stf` | Sleep time min (s) / مدة الإيقاف الدنيا (ث) | `sleep_time_from` | 0 | `e.g. 30` |
| `q-stt` | Sleep time max (s) / مدة الإيقاف القصوى (ث) | `sleep_time_to` | 0 | `e.g. 60` |

The first pair is the pause between two consecutive messages. The second pair is
how many messages to send before taking a long break. The third pair is how long
that break lasts.

| Button | Effect |
|---|---|
| `🔄 Load` / `🔄 تحميل` | `GET /whatsapp/api/instance/queue-settings`, fills the six boxes, toasts `Queue settings loaded` |
| `💾 Save` / `💾 حفظ` | `PUT` the six values as JSON numbers. Toasts `Queue settings saved` or `Error: …` |

Save coerces every box with `+value`, so an **empty box is sent as `0`**, not
omitted. Pressing Save before Load therefore writes six zeros to the instance.

> Source: `platform/templates/whatsapp/control_center.html:157-190`, `:367-396`;
> `platform/blueprints/whatsapp/routes.py:182-191`;
> `platform/blueprints/whatsapp/wapilot.py:103-107`

### 4.6 Right column — three tabs

#### Tab 1: `📜 Message Log / 📜 سجل الرسائل` (default)

The **ten most recent rows** of `whatsapp_log`, newest first, left-joined to
`owners` for the name.

| Column | Content |
|---|---|
| Time / الوقت | `sent_at[:16]` |
| Owner / المالك | Owner full name, or `—` |
| Phone / الهاتف | `phone`, or `—` |
| Message / الرسالة | First 50 characters; the full text is the cell's `title` tooltip |
| Status / الحالة | See below |

Status rendering on this tab is only three-way:

| Stored status | Rendered as |
|---|---|
| `Sent` | green pill `Sent / مُرسل` |
| `Failed` | red pill `Failed / فشل` |
| anything else — `Not Configured`, `Not Sent`, `Pending` | **amber pill printing the raw status string, untranslated** |

When there are no rows: *"No messages yet. / لا توجد رسائل بعد."*
`View All Logs → / عرض كل السجلات ←` opens `/whatsapp/log`.

#### Tab 2: `📨 API Messages / 📨 رسائل API`

Live from Wapilot, not from the database. Starts with
*"Click Refresh to load live messages from Wapilot. / اضغط تحديث لتحميل الرسائل
المباشرة من Wapilot."*

| Button | Effect |
|---|---|
| `🔄 Refresh` / `🔄 تحديث` | `GET /whatsapp/api/messages` |
| `↩ Retry All Failed` / `↩ إعادة محاولة كل الفاشلة` | `POST /whatsapp/api/messages/retry-all`. Toasts `Retry-all triggered` — it does **not** refresh the table afterwards |

The table is built in the browser and its headers are **English-only**: `ID`,
`Phone`, `Text`, `Status`, and an unlabelled action column. Status pills use
Wapilot's own words: `done` and `sent` are green, `failed` is red, everything
else is amber. A `failed` row gets a `↩` button that calls
`POST /whatsapp/api/messages/<id>/retry`, toasts `Message retried`, and reloads
the tab.

**Only the first 50 messages are rendered.** When there are more, a line reads
*"Showing 50 of N messages."* (English-only).

#### Tab 3: `ℹ️ Details / ℹ️ التفاصيل`

`🔄 Refresh / 🔄 تحديث` calls `GET /whatsapp/api/instance/details` and dumps the
response as a two-column key/value table — **whatever keys Wapilot returns**, in
whatever order, with nested objects rendered as raw JSON. Nothing is translated
or relabelled. If the response is empty it prints the API error or
`No details available`.

> Source: `platform/templates/whatsapp/control_center.html:193-262`, `:283-291`,
> `:398-470`; `platform/blueprints/whatsapp/routes.py:96-102`, `:198-225`

### 4.7 What the page does on its own

`refreshStatus()` runs on `DOMContentLoaded` and then **every 30 seconds** for as
long as the tab is open. Nothing else auto-refreshes.

> Source: `platform/templates/whatsapp/control_center.html:472-476`

**Source:** `platform/blueprints/whatsapp/routes.py:85-119`;
`platform/templates/whatsapp/control_center.html:1-478`

---

## 5. Screen: Send Center

**URL.** `GET /whatsapp/send-center`

**Purpose.** Send one ad-hoc WhatsApp message — text, image, document or video —
to one number, optionally starting from a saved template, with an AI drafting
assistant and a phone-number lookup tool.

**How to reach it.** Control Center → `✉️ Send Message`; client record →
Communication History → `✉️ Send Message / إرسال رسالة`.

**Who can open it.** Any role holding the `whatsapp` grant. **This screen opens
even when WhatsApp is not configured** — the failure only shows when you press
Send, as `❌ Error: WhatsApp is not configured…`.

**Page title.** `Send Message / إرسال رسالة`
**Subtitle.** `Send text, images, files or videos via WhatsApp / إرسال نصوص أو
صور أو ملفات أو فيديوهات عبر واتساب`

### 5.1 The shared phone field

One field serves all four tabs.

| Field | Label | Notes |
|---|---|---|
| `send-phone` | `Phone Number *` / `رقم الهاتف *` | Free text. Placeholder *"e.g. 201012345678 or chat_id@c.us"* (English-only). No format validation in the browser or on the server beyond "not empty" |

### 5.2 Tab: `💬 Text / 💬 نص`

| Control | Effect |
|---|---|
| `Message *` / `الرسالة *` textarea, 5 rows | The message body. Placeholder *"Type your message… / اكتب رسالتك…"* |
| `✨ AI Draft` / `✨ مسودة بالذكاء الاصطناعي` | Opens the AI drafting modal (§5.6) |
| `📤 Send Message` / `📤 إرسال رسالة` | Posts to `/whatsapp/api/send/text` |

**What Send does.** The browser refuses an empty phone or message with
`Phone and message required` (English-only) in the red result box. Otherwise it
posts `{phone, text, template_name}` as JSON. The server:

1. Rejects a blank phone or text with HTTP 400 and
   `{"ok": false, "error": "phone and text required"}`.
2. Builds the chat ID (§3.3) and calls Wapilot's send-message endpoint.
3. **Writes one row to `whatsapp_log`** with `status` `Sent` when the API
   returned no error, `Failed` otherwise; the message is truncated to 500
   characters and the API response to 500 characters.
4. Returns `{"ok": …, "data": …, "error": …}`.

The result box shows `✅ Sent to <phone>` or `❌ Error: <message>` and hides
after 6 seconds.

`owner_id` is read from the request body but the Send Center never sends one, so
messages from this screen are logged **with no owner** and do not appear in a
client's Communication History.

The `template_name` sent is the selected template's **numeric ID**, not its name
— see [Known limits](#templates-1).

> Source: `platform/blueprints/whatsapp/routes.py:244-267`;
> `platform/templates/whatsapp/send_center.html:66-83`, `:284-294`

### 5.3 Tabs: `🖼 Image`, `📎 File`, `🎬 Video`

The three media tabs are identical apart from the endpoint and the file
`accept` filter.

| Tab | Bilingual label | File field label | `accept` | Endpoint |
|---|---|---|---|---|
| Image | `🖼 Image` / `🖼 صورة` | `Image File *` / `ملف الصورة *` | `image/*` | `POST /whatsapp/api/send/image` |
| File | `📎 File` / `📎 ملف` | `Document File *` / `ملف المستند *` | none | `POST /whatsapp/api/send/file` |
| Video | `🎬 Video` / `🎬 فيديو` | `Video File *` / `ملف الفيديو *` | `video/*` | `POST /whatsapp/api/send/video` |

Each has a `Caption (optional)` / `تعليق (اختياري)` text box, placeholder
*"Caption… / تعليق…"*, and a `📤 Send <type>` / `📤 إرسال …` button.

The browser refuses a missing phone or file with `Phone and file required`
(English-only). The request is `multipart/form-data` carrying `phone`, `caption`
and `media`; the server rejects a missing phone or file with HTTP 400 and
`{"ok": false, "error": "phone and media required"}`.

The whole file is read into memory and re-encoded into a multipart body by hand
with a fixed boundary, then posted to Wapilot with `Content-Type:
application/octet-stream` for the file part regardless of its real type. The
application-wide upload cap of **16 MB** applies.

**Media sends are not logged.** None of the three routes writes to
`whatsapp_log`, so an image sent to a client leaves no trace on the Message Log,
the Control Center log tab or the client's Communication History.

> Source: `platform/blueprints/whatsapp/routes.py:270-306`;
> `platform/blueprints/whatsapp/wapilot.py:139-178`;
> `platform/app.py:296` (`MAX_CONTENT_LENGTH`);
> `platform/templates/whatsapp/send_center.html:158-201`, `:296-313`

### 5.4 Template picker (right column)

Heading `📋 Templates / 📋 القوالب`, with the note *"Click a template to load its
text into the message box. / اضغط على قالب لتحميل نصه في صندوق الرسالة."*

Only templates with `is_active=1` are listed, ordered by name. Each card shows
the template **name** and the first two lines of its text (or `(empty)` when the
text is blank).

| Control | Effect |
|---|---|
| Search box | Placeholder *"Search templates… / ابحث في القوالب…"*. Filters the cards in the browser on name **or** body text, case-insensitive. No server round trip |
| Template card | Highlights the card, copies its text into the message box, switches to the Text tab, and remembers the template's **ID** |
| `Manage Templates →` / `إدارة القوالب ←` | Opens `/whatsapp/templates` |

When there are no active templates: *"No templates yet. / لا توجد قوالب بعد."*
with a `Create one → / أنشئ واحداً ←` link.

**The text a card loads is not the full template.** It is passed through the
click handler after `replace("'", "")` and `truncate(200)` — so apostrophes are
stripped and anything past roughly 200 characters is cut and replaced with `…`.
The preview underneath shows the full text; the message box does not.

> Source: `platform/blueprints/whatsapp/routes.py:232-241`;
> `platform/templates/whatsapp/send_center.html:206-233`, `:260-274`

### 5.5 Phone Lookup

Heading `🔍 Phone Lookup / 🔍 البحث عن رقم`. Type a number, press
`Lookup / بحث`, and the page calls `GET /whatsapp/api/lookup/phone/<phone>`,
which asks Wapilot for the LID (linked-device identifier) behind that number.

On success it prints `LID: <lid>   PN: <pn>` plus a `Use` button (English-only)
that copies the returned number into the Phone field. On failure it prints the
API error, or `Not found`.

> Source: `platform/blueprints/whatsapp/routes.py:790-794`;
> `platform/blueprints/whatsapp/wapilot.py:247-251`;
> `platform/templates/whatsapp/send_center.html:234-242`, `:315-330`

### 5.6 The AI Draft modal

Opened by `✨ AI Draft`. Title `AI Message Drafter / مُحرّر الرسائل بالذكاء
الاصطناعي`.

| Control | Label | Notes |
|---|---|---|
| Context textarea | `What's the message about?` / `ما موضوع الرسالة؟` | Placeholder *"e.g. Remind owner about vaccination due next week for their cat Mimi… / مثال: ذكّر المالك بموعد تطعيم قطته ميمي الأسبوع القادم…"* |
| Language select | `English` / `الإنجليزية` · `Arabic` / `العربية` | Passed to the model as an instruction |
| `🤖 Generate Message` / `🤖 توليد الرسالة` | — | Posts `{context, lang}` to `POST /ai/draft-message` |
| `✅ Use This Message` / `✅ استخدم هذه الرسالة` | — | Hidden until a draft comes back. Copies the draft into the message box and closes the modal |
| `Cancel` / `إلغاء` and `×` | — | Close without copying |

An empty context is refused with a browser `alert('Please describe what the
message should say.')` (English-only). While generating, the button reads `...`
and is disabled. A network failure raises `alert('AI unavailable. Please write
the message manually.')` (English-only), and the button label is restored to the
English string `🤖 Generate Message` even in Arabic mode.

The AI route builds a fixed prompt — *"You are writing a WhatsApp message on
behalf of Aleefy (Happy Pets, Healthy Lives)… Write a warm, professional message
(2-4 sentences)… Max 2 emojis. End with: Aleefy."* — and returns
`{"message": "<reply>"}`. If the reply is empty the box shows `(no response)`.
The route also accepts an `owner_id` to add the client's name and pet count to
the prompt; **the Send Center never sends one**.

> Source: `platform/templates/whatsapp/send_center.html:85-156`;
> `platform/blueprints/ai_assistant/routes.py:646-682`

**Source:** `platform/blueprints/whatsapp/routes.py:232-306`, `:790-794`;
`platform/templates/whatsapp/send_center.html:1-332`

---

## 6. Screen: Campaigns list

**URL.** `GET /whatsapp/campaigns`

**Purpose.** List the bulk-messaging campaigns held by Wapilot and drive them —
start, pause, schedule, copy, reset failures.

**How to reach it.** Control Center → `📣 Campaigns`; `← Campaigns / ← الحملات`
from the campaign form or a campaign detail.

**Who can open it.** Any role holding the `whatsapp` grant. **The page does not
render when WhatsApp is unconfigured** — it calls the API before rendering.

**Page title.** `Campaigns / الحملات`
**Subtitle.** `Bulk WhatsApp messaging campaigns via Wapilot / حملات مراسلة
واتساب جماعية عبر Wapilot`

### 6.1 Where the list comes from

The route calls Wapilot's `GET /campaigns` and then unwraps the payload
defensively: it takes `data["data"]`, or `data["campaigns"]`, or the response
itself when it is already a list. If none of those shapes fits, the list is
empty.

**An API error does not stop the page.** The error string is passed to the
template and rendered as an amber banner above the grid:

> ⚠️ Could not load campaigns from Wapilot: `<error>`
> Check your API token and instance ID in **Settings** / تحقق من رمز API ومعرّف
> الحساب في **الإعدادات**.

(The first line is English-only; the second is bilingual.)

### 6.2 What each campaign card shows

| Element | Source | Fallback |
|---|---|---|
| `ID: <id>` | `id`, else `campaign_id` | `—` |
| Title | `name`, else `default_message`, else the literal word `Campaign` | — |
| Status pill | `status`, else `state`, lower-cased and title-cased for display | `Unknown` |
| `Total: / الإجمالي:` | `total`, else `messages_count` | `0` |
| `Sent: / أُرسلت:` | `sent`, else `done` | `0` |
| `Failed: / فشلت:` | `failed` | `0` |
| `Queued: / في الطابور:` | `queued` | `0` |

Status pill colours: `active` green, `paused` amber, `finished` or `done` grey,
`scheduled` violet, anything else grey.

### 6.3 Per-card buttons

| Button | Calls | Confirmation | After |
|---|---|---|---|
| `📊 Details` / `📊 التفاصيل` | link to `/whatsapp/campaigns/<id>` | — | — |
| `▶ Start` / `▶ بدء` | `POST /whatsapp/api/campaigns/<id>/start` | none | toast, then **page reload after 1.5 s** |
| `⏸ Pause` / `⏸ إيقاف مؤقت` | `POST …/pause` | none | toast, reload |
| `🕐 Schedule` / `🕐 جدولة` | opens the schedule modal | — | — |
| `📋 Copy` / `📋 نسخ` | `POST …/copy` | none | toast, reload |
| `↩ Reset` / `↩ إعادة تعيين` | `POST …/reset-failed` | none | toast, reload |

Every one of these is `super_admin` / `clinic_owner` / `branch_manager` only
(`support_admin` is listed on start and pause but is blocked by the module gate).
The buttons are rendered for **reception** as well, and pressing one produces no
visible response at all.

The toast text is the raw action slug: `start triggered`, `pause triggered`,
`copy triggered`, `reset-failed triggered` — all English-only.

### 6.4 Schedule modal

Title `📅 Schedule Campaign / 📅 جدولة الحملة`. One `datetime-local` input, then
`Schedule / الجدول` and `Cancel / إلغاء`.

Pressing Schedule with an empty box toasts `Select a date/time first`
(English-only). Otherwise it posts `{"schedule_date": "<the datetime-local
value>"}` to `POST /whatsapp/api/campaigns/<id>/schedule`, toasts
`Campaign scheduled` or `Error: …`, closes the modal, and reloads after 1.5 s on
success.

The value sent is the browser's local `YYYY-MM-DDTHH:MM` string, passed to
Wapilot verbatim. Nothing converts it to UTC or attaches a timezone.

### 6.5 Empty state

`📣` · `No campaigns yet / لا توجد حملات بعد` ·
*"Create your first campaign to send bulk WhatsApp messages. / أنشئ أول حملة
لإرسال رسائل واتساب جماعية."* · `➕ Create Campaign / ➕ إنشاء حملة`.

**Source:** `platform/blueprints/whatsapp/routes.py:313-323`;
`platform/templates/whatsapp/campaigns_list.html:1-164`

---

## 7. Screen: New Campaign

**URL.** `GET/POST /whatsapp/campaigns/new`

**Purpose.** Create an empty campaign on Wapilot bound to this clinic's
instance.

**How to reach it.** Campaigns list → `➕ New Campaign / ➕ حملة جديدة`, or the
`➕ Create Campaign` button in the empty state.

**Who can open it.** super_admin, clinic_owner, branch_manager. (`support_admin`
is on the role list but blocked by the module gate.)

**Page title.** `Create Campaign / إنشاء حملة`
**Subtitle.** `Create a new bulk WhatsApp campaign via Wapilot / إنشاء حملة
واتساب جماعية جديدة عبر Wapilot`

### 7.1 The one field

| Field | Label | Required | Notes |
|---|---|---|---|
| `default_message` | `Default Message` / `الرسالة الافتراضية` | No | 5-row textarea. Placeholder `Hello {name}, this is a message from {clinic}…` |

Below it, an English-only paragraph: *"This message will be sent to contacts that
don't have an individual message set. You can also leave this empty and assign
messages when adding contacts."*

Below that, an amber note: `ℹ️ Note: / ℹ️ ملاحظة:` followed by the English-only
sentence *"The campaign will be created using your configured instance
(**instance4042**). After creation, you'll be taken to the campaign page where
you can add contacts and start sending."*

**`instance4042` is hard-coded in the template.** It is not read from your
settings, so it is wrong for every clinic whose instance is named anything else.

There is no name field, no contact list, no scheduling and no template picker on
this form. A campaign is created empty and populated afterwards on its detail
page.

### 7.2 What Create does

`🚀 Create Campaign / 🚀 إنشاء الحملة` posts the form. The server calls Wapilot's
`POST /campaigns` with `{"instance_uns": [<your instance id>]}` plus
`{"default_message": …}` when the box is not blank, then:

- **On API error:** flashes *"Failed to create campaign: `<error>`"* as `danger`
  and re-renders the form with what you typed.
- **On success:** writes an audit row, flashes *"Campaign created."* as
  `success`, and redirects to the new campaign's detail page. If the response
  carried no `data.id`, it redirects to the campaigns list instead.

`Cancel / إلغاء` returns to the campaigns list.

**Source:** `platform/blueprints/whatsapp/routes.py:326-353`;
`platform/blueprints/whatsapp/wapilot.py:192-197`;
`platform/templates/whatsapp/campaign_form.html:1-46`

---

## 8. Screen: Campaign detail

**URL.** `GET /whatsapp/campaigns/<campaign_id>`

**Purpose.** Run one campaign: see its delivery statistics, add and remove
contacts, start / pause / finish / copy it, tune its throttling, and retry
individual failures.

**How to reach it.** Campaigns list → `📊 Details`; automatically after creating
a campaign.

**Who can open it.** Any role holding the `whatsapp` grant. Most of the buttons
on it are restricted further.

**Page title.** `Campaign Details / تفاصيل الحملة`
**Subtitle.** `ID: <campaign_id>`

### 8.1 What the server loads

Three Wapilot calls, in order: the campaign's messages, its stats, and its delay
settings. **All three discard their error strings.** A failing API therefore
renders as an empty campaign with zero everything and no message on screen at
all.

Each response is unwrapped the same way as the campaigns list — `data["data"]`,
then `data["messages"]`, then the raw list.

### 8.2 Toolbar buttons

| Button | Effect |
|---|---|
| `← Campaigns` / `← الحملات` | Back to the list |
| `▶ Start` / `▶ بدء` | `POST …/start` |
| `⏸ Pause` / `⏸ إيقاف مؤقت` | `POST …/pause` |
| `⏱ Delay` / `⏱ التأخير` | Opens the delay modal (§8.6) |
| `➕ Add Contacts` / `➕ إضافة جهات اتصال` | Opens the bulk-add modal (§8.6) |
| `↩ Reset Failed` / `↩ إعادة تعيين الفاشلة` | `POST …/reset-failed` |

None of the four action buttons asks for confirmation, and none reloads the page
— the statistics on screen stay stale until you refresh manually.

### 8.3 Stats card (left column)

Heading `📊 Stats / 📊 الإحصائيات`.

| Row | Source key(s) | Fallback |
|---|---|---|
| `Total` / `الإجمالي` | `total`, else `messages_count` | `0` |
| `✅ Sent` / `✅ أُرسلت` | `sent`, else `done` | `0` |
| `❌ Failed` / `❌ فشلت` | `failed` | `0` |
| `⏳ Queued` / `⏳ في الطابور` | `queued` | `0` |

When `Total` is above zero, a green progress bar and a `N% delivered` caption
(English-only) appear underneath, computed as `sent / total × 100` rounded to a
whole number.

### 8.4 Delay Settings card

Rendered **only when the delay API returned something**. Read-only; it displays
the three ranges as `from–to`:

| Row | Shows |
|---|---|
| `Msg delay` / `تأخير الرسالة` | `wait_between_messages_from`–`wait_between_messages_to` s |
| `Sleep after` / `الإيقاف بعد` | `sleep_after_from`–`sleep_after_to` msgs |
| `Sleep time` / `مدة الإيقاف` | `sleep_time_from`–`sleep_time_to` s |

Missing values render as `—`.

### 8.5 Actions card

Heading `🔧 Actions / 🔧 الإجراءات`. Seven stacked buttons:

| Button | Calls | Confirmation | Toast |
|---|---|---|---|
| `▶ Start Campaign` / `▶ بدء الحملة` | `POST …/start` | none | `start triggered` |
| `⏸ Pause` / `⏸ إيقاف مؤقت` | `POST …/pause` | none | `pause triggered` |
| `📅 Schedule` / `📅 الجدول` | opens the schedule modal | none | `Scheduled` |
| `🗑 Unschedule` / `🗑 إلغاء الجدولة` | `DELETE …/schedule` | `Remove schedule?` | `Unscheduled` |
| `📋 Copy` / `📋 نسخ` | `POST …/copy` | none | `copy triggered` |
| `✅ Mark Finished` / `✅ تعليم كمنتهية` | `PATCH …/finish` | none | `Marked as finished` |
| `↩ Reset Failed` / `↩ إعادة تعيين الفاشلة` | `POST …/reset-failed` | none | `reset-failed triggered` |

All toast strings are English-only. Only Unschedule confirms.

### 8.6 The three modals

**Add Contacts.** Title `➕ Add Contacts to Campaign / ➕ إضافة جهات اتصال للحملة`.
A 10-row monospace textarea, one contact per line, in the format
`phone_number|message text` — the instruction line reads *"One per line: / واحد
في كل سطر:"* `phone_number|message text` *"(message optional, uses campaign
default) / (الرسالة اختيارية، تُستخدم رسالة الحملة الافتراضية)"*.

The browser splits each line on the **first** `|`; anything after it (including
further pipes) becomes the message. Blank lines are dropped. A line with no pipe
becomes `{phone_number: …}` with no text, so the campaign default applies. With
nothing usable it toasts `No contacts found`. Otherwise it posts
`{"messages": [...]}` to `POST /whatsapp/api/campaigns/<id>/messages`, toasts
`<n> contacts added`, closes, and reloads the All Messages tab.

Numbers are sent exactly as typed — the `@c.us` suffix is **not** appended here.

**Schedule.** Title `📅 Schedule Campaign / 📅 جدولة الحملة`. One
`datetime-local` box, then `Schedule / الجدول` and `Cancel / إلغاء`. Empty →
`Select date/time`. Otherwise posts `{"schedule_date": …}`, toasts `Scheduled`,
and closes. It does **not** reload the page.

**Delay.** Title `⏱ Update Delay Settings / ⏱ تحديث إعدادات التأخير`. The same
six fields as the Control Center queue settings (§4.5), with the same bilingual
labels. Opening the modal fetches the current values and — unlike the Control
Center card — falls back to sensible defaults when a value is missing: **3, 8,
20, 50, 30, 60**. `Save / حفظ` sends all six as `PATCH …/delay`, toasts
`Delay updated`, and closes.

### 8.7 Message tabs

Three tabs across the top of the main panel:

| Tab | Label | Loads from |
|---|---|---|
| 1 | `All Messages (N)` — **English-only**, N = rows rendered server-side | server-side render, then `GET …/messages` on Refresh |
| 2 | `⏳ Queue` / `⏳ الطابور` | `GET …/queue` |
| 3 | `✅ Done` / `✅ تم` | `GET …/done` |

**All Messages toolbar.**

| Control | Effect |
|---|---|
| Filter box | Placeholder *"Filter by phone or text… / تصفية بالهاتف أو النص…"*. Hides non-matching rows in the browser, matching on the phone or the first 80 characters of the text |
| `🔄 Refresh` / `🔄 تحديث` | Re-fetches and re-renders the table |
| `🗑 Delete Selected` / `🗑 حذف المحدد` | See below |

**Message table columns.** A select-all checkbox, then:

| Column | Content |
|---|---|
| (checkbox) | Carries the message's Wapilot `id` |
| `Phone` / `الهاتف` | `phone_number`, else `chat_id`, else `—` |
| `Message` / `الرسالة` | First 60 characters, full text as the tooltip |
| `Status` / `الحالة` | `done` or `sent` → green `Sent / مُرسل`; `failed` → red `Failed / فشل`; anything else → amber pill with the status word title-cased |
| `Actions` / `إجراءات` | A `↩` retry button, **only on failed rows** |

`↩` calls `POST /whatsapp/api/messages/<id>/retry` and toasts `Retried`. It does
not refresh the table.

**Delete Selected** collects the ticked ids, refuses with `Select messages first`
when none are ticked, asks `Delete N message(s)?`, then sends
`DELETE /whatsapp/api/campaigns/<id>/messages` with `{"ids": [...]}`, toasts
`<n> deleted`, and reloads the All Messages tab.

The table rendered by JavaScript on Refresh / Queue / Done uses **English-only**
headers (`Phone`, `Message`, `Status`) even in Arabic, unlike the server-rendered
first view.

**Source:** `platform/blueprints/whatsapp/routes.py:356-379`, `:400-489`;
`platform/blueprints/whatsapp/wapilot.py:189-243`;
`platform/templates/whatsapp/campaign_detail.html:1-441`

---

## 9. Screen: Templates

**URL.** `GET /whatsapp/templates`

**Purpose.** Browse, search and manage the reusable message templates stored in
the platform's own `whatsapp_templates` table. These are **not** WhatsApp
Business API templates and are never submitted to Meta for approval — they are
local text snippets.

**How to reach it.** Control Center → `📋 Templates`; `💬 Templates / 💬 القوالب`
from the Message Log or the Pending Reminders screen; `← Templates / ← القوالب`
from the template form; `Manage Templates → / إدارة القوالب ←` from the Send
Center.

**Who can open it.** Any role holding the `whatsapp` grant.

**Page title.** `WhatsApp Templates / قوالب واتساب`
**Subtitle.** `Manage message templates for WhatsApp communication / إدارة قوالب
الرسائل للتواصل عبر واتساب`

**Everything is listed** — the query is `SELECT * FROM whatsapp_templates ORDER
BY name`, with no `is_active` filter, so inactive templates appear here (marked
as such) while the Send Center picker shows only active ones.

### 9.1 Toolbar buttons

| Button | Goes to |
|---|---|
| `➕ New Template` / `➕ قالب جديد` | `/whatsapp/templates/new` |
| `📋 Message Log` / `📋 سجل الرسائل` | `/whatsapp/log` |
| `🔔 Reminders` / `🔔 التذكيرات` | `/whatsapp/reminders` |

### 9.2 Category tabs

Five pills with live counts, filtering the grid in the browser.

| Tab | Matches templates whose `scenario` is | Colour when active |
|---|---|---|
| `📋 All` / `📋 الكل` | anything | dark grey |
| `📅 Appointment` / `📅 موعد` | `appointment` | cyan |
| `🔄 Follow-up` / `🔄 متابعة` | `followup` | teal |
| `💉 Vaccine` / `💉 تطعيم` | `vaccine` | violet |
| `📢 Campaign & Other` / `📢 حملة وأخرى` | **everything else** — `invoice`, `campaign`, `custom`, blank, or any value not in the first three | amber |

The counts are computed server-side in the template. Note that the fifth tab is
a catch-all: an `invoice` template is counted and filtered under
*Campaign & Other*.

### 9.3 Search

One box, placeholder *"Search templates by name or message… / ابحث في القوالب
بالاسم أو الرسالة…"*. Case-insensitive substring match against the template's
name **and** body combined. It combines with the active category tab (both must
match).

Above the grid, a count line reads `N template(s) available` on first load, and
`N template(s) shown` after any filtering. **Both are English-only.** With no
matches, a `🔍 No templates found / لا توجد قوالب` panel appears with
*"Try a different search term or category. / جرّب كلمة بحث أو فئة مختلفة."*

### 9.4 What each template card shows

| Element | Content |
|---|---|
| Title | The template name with `_` replaced by spaces and title-cased — `appt_reminder` displays as `Appt Reminder` |
| Code line | The raw stored name, in monospace |
| Category badge | The `scenario` word, title-cased. Colour matches the tab colours; `invoice`, `campaign` and `custom` share amber; an unrecognised scenario gets grey |
| `👁 Preview message` / `👁 معاينة الرسالة` | A collapsed `<details>` block. Expanded, it shows the full template text with line breaks preserved, or `(empty)` |
| `Variables` / `المتغيرات` | Rendered only when `variables_json` is set and is not `[]`. Each entry becomes a `{name}` chip |
| Language | `🌐 Arabic` when `language == 'ar'`, otherwise `🌐 English`. **English-only, and `Any` displays as `English`** |
| Active flag | `● Active / ● نشط` in green, or `● Inactive / ● غير نشط` in red |
| Default flag | `⭐ Default / ⭐ افتراضي` in amber, only when `is_default` is set |
| `✏️ Edit` / `✏️ تعديل` | Opens the edit form |
| `🗑` | Deletes, after a browser confirm |

The card's top border is colour-coded by scenario: cyan for appointment, teal for
follow-up, violet for vaccine, amber for campaign / invoice / custom, WhatsApp
green (`#25D366`) for anything else.

### 9.5 Delete

The `🗑` button submits a form to `POST /whatsapp/templates/<tid>/delete` after
a browser confirm reading `Delete template '<name>'?` (English-only).

The server deletes the row unconditionally — there is no check that the template
is unused, no soft delete, and **no audit row**. It then flashes
*"Template deleted."* as `success` and returns to the list.

Restricted to super_admin, clinic_owner and branch_manager. A receptionist sees
the button on every card and is redirected to the launcher when they press it.

### 9.6 Empty state

`💬` · `No templates yet / لا توجد قوالب بعد` · *"Create your first WhatsApp
message template to get started. / أنشئ أول قالب رسالة واتساب للبدء."* ·
`➕ Create Template / ➕ إنشاء قالب`.

**Source:** `platform/blueprints/whatsapp/routes.py:497-506`, `:587-596`;
`platform/templates/whatsapp/templates_list.html:1-262`

---

## 10. Screens: New Template and Edit Template

**URLs.** `GET/POST /whatsapp/templates/new` · `GET/POST /whatsapp/templates/<tid>/edit`

**Purpose.** Define one reusable message body with `{placeholder}` variables.

**How to reach it.** Templates list → `➕ New Template`, or a card's `✏️ Edit`;
the Send Center's `Create one →` link when there are no templates.

**Who can open it.** super_admin, clinic_owner, branch_manager, reception.
(`support_admin` is on the role list but blocked by the module gate.)

**Page title.** `New WhatsApp Template` or `Edit WhatsApp Template` —
**English-only**, built from the `action` flag rather than through `t()`.
**Subtitle.** `Define reusable message templates with dynamic variables / تعريف
قوالب رسائل قابلة لإعادة الاستخدام بمتغيرات ديناميكية`

### 10.1 Fields

| Field | Label | Control | Required | Stored in |
|---|---|---|---|---|
| `name` | `Template Name *` / `اسم القالب *` | text, `required` in the browser. Placeholder *"e.g. Appointment Reminder / مثال: تذكير بموعد"* | Yes — also re-checked on the server | `whatsapp_templates.name` (**UNIQUE**) |
| `scenario` | `Scenario` / `السيناريو` | select: `Appointment`, `Followup`, `Vaccine`, `Invoice`, `Campaign`, `Custom` — **the six option labels are English-only** | No | `scenario` |
| `language` | `Language` / `اللغة` | select: `English` / `الإنجليزية`, `Arabic` / `العربية`, `Any` / `أي` | No, defaults `en` | `language` |
| `is_active` | `Active` / `نشط` | checkbox, ticked by default on a new template | No | `is_active` (1/0) |
| `is_default` | `Default` / `افتراضي` | checkbox, unticked by default | No | `is_default` (1/0) |
| `template_text` | `Message Text *` / `نص الرسالة *` | 7-row textarea, `required` in the browser. Placeholder `Dear {owner}, {pet} has an appointment on {date} at {time}.` | Browser only — the server does not re-check it | `template_text` |
| `variables_json` | `Variables JSON (optional)` / `متغيرات JSON (اختياري)` | text, defaults to `[]`. Placeholder `["owner","pet","date","time"]` | No | `variables_json` |

Above the message box, the helper line `Variables: / المتغيرات:` lists nine
placeholder names as code chips:
`{owner}` `{pet}` `{date}` `{time}` `{vet}` `{clinic}` `{vaccine}` `{invoice}`
`{amount}`.

**`variables_json` is decoration.** Nothing substitutes variables using it; it
only drives the chips on the template card. Substitution, where it happens at
all, is done by the reminder scheduler against a fixed set of field names —
see §17.

### 10.2 Live preview

A green panel headed `📱 WhatsApp Preview / 📱 معاينة واتساب` re-renders on every
keystroke, substituting a fixed sample set:

| Placeholder | Sample value |
|---|---|
| `{owner}` | Ahmed Hassan |
| `{pet}` | Max |
| `{date}` | Monday 2 June |
| `{time}` | 10:00 AM |
| `{vet}` | Dr. Sarah |
| `{clinic}` | Aleefy Veterinary Clinic |
| `{vaccine}` | Rabies |
| `{invoice}` | INV-0042 |
| `{amount}` | 350 EGP |

With an empty box it reads *"Your message preview will appear here…"*
(English-only). The preview substitutes any of the nine names regardless of
whether the reminder job would recognise them in that context.

### 10.3 Buttons

| Button | Effect |
|---|---|
| `💾 Create Template` (new) / `💾 Save Changes` (edit) — **English-only** | Submits the form |
| `Cancel` / `إلغاء` | Returns to the templates list without saving |
| `🗑 Delete` / `🗑 حذف` | Edit mode only. Confirms with `Delete this template?` (English-only), then deletes |

### 10.4 What Save does

**New.** A blank name is refused with *"Template name is required."* as `danger`,
and the form is re-rendered with what you typed. Otherwise the row is inserted,
an audit row is written, and *"Template '`<name>`' created."* is flashed as
`success` before returning to the list. **Any database error — most commonly a
duplicate name, because `name` is `UNIQUE` — is caught and flashed verbatim as
`Error: <the raw exception text>`,** and the form is re-rendered.

**Edit.** A missing template id flashes *"Template not found."* as `danger` and
returns to the list. Otherwise every field is overwritten, an audit row is
written, and *"Template updated."* is flashed as `success`. There is **no name
validation on edit**: clearing the name saves an empty name, and renaming onto
an existing name raises an uncaught `UNIQUE` violation and a 500 page.

Neither form writes `created_at` explicitly; the column defaults to the current
local time on insert and is never displayed anywhere.

**Source:** `platform/blueprints/whatsapp/routes.py:509-545`, `:548-585`;
`platform/templates/whatsapp/template_form.html:1-119`;
`platform/models/database.py:1858-1867` (table)

---

## 11. Screen: Pending Reminders

**URL.** `GET /whatsapp/reminders`

**Purpose.** A worklist of every reminder row still waiting to go out, with two
one-click ways to clear it: send a WhatsApp message, or just mark it done.

**How to reach it.** `🔔 Reminders / 🔔 التذكيرات` from the Templates list;
`🔔 View Pending Reminders / 🔔 عرض التذكيرات المعلقة` from the empty Message
Log. **There is no link to it from the Control Center.**

**Who can open it.** Any role holding the `whatsapp` grant.

**Page title.** `Pending Reminders / تذكيرات معلقة`
**Subtitle.** `Appointments, follow-ups, and vaccine reminders awaiting action /
مواعيد ومتابعات وتذكيرات تطعيم بانتظار الإجراء`

### 11.1 What is listed

Every row of `reminders` with `status = 'Pending'`, ordered by `scheduled_for`
ascending, left-joined to `owners` and `pets`. **There is no limit and no
pagination** — a backlog of a thousand pending reminders renders as one page.

Above the table: `N pending reminder(s)` — **English-only**.

### 11.2 Columns

| Column | Content |
|---|---|
| `Due Date` / `تاريخ الاستحقاق` | `scheduled_for[:10]`, or `—`. Intended to be colour-coded red for overdue, amber for today, green for future — **the colour coding never fires**; see [Known limits](#reminders-and-the-nightly-job) |
| `Owner` / `المالك` | Owner full name in bold, with `whatsapp_phone` underneath in small grey type when present |
| `Pet` / `الحيوان` | Pet name, or `—` |
| `Type` / `النوع` | A coloured badge carrying `reminder_type` with `_` replaced by spaces, title-cased. Styled for `appointment` (blue), `followup` (green), `vaccine` (violet), `medication` (pink), `custom` (grey); any other value renders unstyled |
| `Message` / `الرسالة` | One truncated line, full text in the tooltip |
| `Actions` / `إجراءات` | Two buttons, below |

### 11.3 The two buttons

**`✓ Mark Sent` / `✓ تعليم كمرسلة`** — tooltip *"Mark as sent without sending
WhatsApp / تعليم كمرسلة بدون إرسال واتساب"*.

Posts to `POST /whatsapp/reminders/<rid>/mark-sent`. Sets `status='Sent'` and
`sent_at = NOW()` **unconditionally** — no status check, no confirmation, no
message sent, no `whatsapp_log` row, no audit row. Flashes *"Reminder marked as
sent."* as `success` and returns to this screen.

**`📱 Send WA` / `📱 إرسال واتساب`** — tooltip *"Send WhatsApp message / إرسال
رسالة واتساب"*.

Opens a modal pre-filled from the row, titled `📱 Send WhatsApp Message / 📱 إرسال
رسالة واتساب`:

| Field | Label | Pre-filled with |
|---|---|---|
| `phone` | `Phone Number` / `رقم الهاتف` | The owner's `whatsapp_phone`. Placeholder `+20 10 xxxx xxxx`. `required` |
| `owner_id` | (hidden) | The reminder's owner id |
| `custom_message` | `Message` / `الرسالة` | The reminder's message text. Placeholder *"Type your message… / اكتب رسالتك…"*. `required` |

`Send Message 📤 / إرسال الرسالة 📤` posts to `POST /whatsapp/send`;
`Cancel / إلغاء` or a click on the dark backdrop closes it.

**Sending from this modal does not change the reminder.** The route writes a
`whatsapp_log` row and flashes the result, but never touches `reminders.status`
— so the reminder stays `Pending` and reappears on this list on the next page
load.

### 11.4 What `POST /whatsapp/send` does

This is the shared free-text send used by the modal above.

| Input | Handling |
|---|---|
| `phone` | Required. Blank → *"Phone number is required."* as `danger`, back to the referring page (or Pending Reminders) |
| `custom_message` | The message body |
| `template_id` | Optional. When set **and** the message box is empty, the template's text and name are loaded and used |
| `owner_id` | Optional. Stored on the log row |

If there is still no message after the template lookup: *"Message content is
required."* as `danger`, back to the referring page.

Otherwise it sends and logs, then flashes:

- `Message sent to <phone>.` as `success` when the status came back `Sent`;
- `Message queued / failed — check log.` as `warning` otherwise.

It then redirects to the referring page, falling back to `/whatsapp/log`.

### 11.5 Empty state

`🎉` · `No pending reminders / لا توجد تذكيرات معلقة` · *"All reminders have been
handled. Great work! / تمت معالجة كل التذكيرات. عمل رائع!"*

**Source:** `platform/blueprints/whatsapp/routes.py:614-629`, `:661-675`,
`:964-993`; `platform/templates/whatsapp/reminders.html:1-154`

---

## 12. Screen: Reminder Admin

**URL.** `GET /whatsapp/reminder-admin`

**Purpose.** The reminder control panel: counts by status, a form to create a
reminder by hand, separate Overdue and Upcoming worklists, a run log, and the
button that fires the nightly job on demand.

**How to reach it.** Control Center → `🔔 Reminder Admin / 🔔 إدارة التذكيرات`.

**Who can open it.** Any role holding the `whatsapp` grant. The `▶ Run Reminder
Job Now` button is restricted further.

**Page title.** `Reminder Admin / إدارة التذكيرات`
**Subtitle.** `View, create, and manually trigger WhatsApp reminders / عرض
وإنشاء وتشغيل تذكيرات واتساب يدوياً`

### 12.1 Toolbar

| Button | Effect |
|---|---|
| `← Control Center` / `← مركز التحكم` | Back to `/whatsapp/control` |
| `▶ Run Reminder Job Now` / `▶ تشغيل مهمة التذكير الآن` | Confirms with `Run the reminder job now?` (English-only), then posts to `POST /whatsapp/reminder-admin/trigger` |

**Run Reminder Job Now** calls `run_reminder_jobs()` — the same function
APScheduler runs at 09:00 — inside a `try`. On success it flashes *"Reminder job
triggered successfully. Check the run log."* as `success`. On any exception it
flashes *"Reminder job failed: `<error>`"* as `danger`. Either way it returns
here. This is super_admin / clinic_owner / branch_manager only.

Note that "triggered successfully" only means the function returned without
raising. It says nothing about whether any message was delivered — check the
Message Log for that.

### 12.2 The three counters

| Card | Counts |
|---|---|
| `⏳ Pending` / `⏳ قيد الانتظار` (amber) | `SELECT COUNT(*) FROM reminders WHERE status='Pending'` |
| `✅ Sent` / `✅ أُرسلت` (green) | `… WHERE status='Sent'` |
| `❌ Failed` / `❌ فشلت` (red) | `… WHERE status='Failed'` |

Rows with `status='Cancelled'` are counted nowhere on this page.

### 12.3 Create Manual Reminder

Heading `➕ Create Manual Reminder / ➕ إنشاء تذكير يدوي`. Posts to
`POST /whatsapp/reminder-admin/reminders/new`.

| Field | Label | Control | Required |
|---|---|---|---|
| `owner_id` | `Owner ID *` / `رقم المالك *` | number box, placeholder `Owner ID / رقم المالك` | Yes, browser and server |
| `pet_id` | `Pet ID (optional)` / `رقم الحيوان (اختياري)` | number box | No |
| `reminder_type` | `Reminder Type` / `نوع التذكير` | select: `Appointment` / `موعد`, `Vaccine` / `اللقاح`, `Follow-up` / `المتابعة`, `Medication` / `دواء`, `Custom` / `مخصص` (pre-selected) | No, defaults `custom` |
| `scheduled_for` | `Scheduled For *` / `مجدول لـ *` | `datetime-local` | Yes, browser and server |
| `message` | `Message *` / `الرسالة *` | textarea, placeholder `Dear {name}, your appointment is tomorrow…` | Yes, browser and server |

`💾 Create Reminder / 💾 إنشاء تذكير` inserts a row with `status='Pending'` and
flashes *"Reminder created."* as `success`. If owner, schedule or message is
missing the server flashes *"Owner, scheduled date, and message are required."*
as `danger` and returns here — **your typing is lost**, the form is not
re-populated.

**Owner ID and Pet ID are raw numbers with no lookup, no autocomplete and no
existence check.** You must already know the client's database id. Nothing on
this form validates that the owner exists or that the pet belongs to them. The
placeholder `{name}` in the message hint is not a placeholder the platform ever
substitutes.

The reminder is stored exactly as typed and sent verbatim — the manual reminder
path performs **no** variable substitution at all.

### 12.4 Overdue and Upcoming lists

Both queries take `status='Pending'` rows joined to owners and pets and compare
`scheduled_for` against the current local time as a bound string. Both are
capped at **50 rows**.

| Section | Heading | Contains |
|---|---|---|
| Overdue | `🔴 Overdue Reminders (N)` — **English-only**, rendered only when there is at least one | `scheduled_for < now`, earliest first. Rows have a pale orange background and a red bold timestamp |
| Upcoming | `📅 Upcoming Reminders (N)` — **English-only**, always rendered | `scheduled_for >= now`, earliest first. Timestamps in the primary colour |

Columns in both: `Scheduled / مجدول` (`scheduled_for[:16]`),
`Owner / المالك` (name plus `whatsapp_phone` underneath),
`Pet / الحيوان`, `Type / النوع` (the same coloured badges as §11.2),
`Message / الرسالة` (one truncated line, full text as tooltip),
`Actions / إجراءات`.

Empty Upcoming state: `🎉 No upcoming reminders / 🎉 لا توجد تذكيرات قادمة`.

**Note on the 7-day claim.** The route's own comment describes "upcoming
reminders (next 7 days)", but the query has no upper bound — it returns the
first 50 pending reminders scheduled from now onwards, however far ahead.

### 12.5 The two row buttons

**`📱 Send Now` / `📱 إرسال الآن`** → `POST /whatsapp/reminder-admin/reminders/<rid>/send-now`.
No confirmation.

1. Loads the reminder and the owner's `whatsapp_phone`, falling back to `phone`.
2. Missing reminder → *"Reminder not found."* as `danger`.
3. No phone at all → *"Owner has no phone number."* as `warning`.
4. Otherwise sends and logs. On `Sent`, sets `status='Sent'` and
   `sent_at = NOW()` and flashes *"Reminder sent successfully."* as `success`.
   On anything else the reminder is **left Pending** and it flashes
   *"Send failed — check message log."* as `warning`.

**`✕`** → `POST /whatsapp/reminder-admin/reminders/<rid>/cancel`. Confirms with
`Cancel this reminder?` (English-only), then runs
`UPDATE reminders SET status='Cancelled' WHERE id=? AND status='Pending'` and
flashes *"Reminder cancelled."* as `success`. Because of the `AND status =
'Pending'` guard, cancelling an already-sent reminder changes nothing — but the
success flash appears anyway.

Neither button is role-gated beyond the module grant, so a receptionist can send
and cancel reminders even though they cannot run the job.

### 12.6 Reminder Run Log

Heading `📋 Reminder Run Log / 📋 سجل تشغيل التذكيرات`. The **20 most recent rows
of `reminder_runs`**, newest first, each rendered as one line:

```
<run_at[:19]>   <run_type>          ✅ 0 sent   ❌ 0 failed   0 processed
```

`run_type` falls back to the word `scheduled` when empty.

**The three numbers are always zero.** `reminder_runs` has no `sent_count`,
`failed_count` or `total_processed` column — the table stores one row per
*entity reminded*, not one row per run. See
[Known limits](#reminders-and-the-nightly-job).

The whole query is wrapped in a bare `except: pass`, so if the table is missing
the section silently renders its empty state instead of erroring.

Empty state: *"No runs yet. Click "Run Reminder Job Now" to start."*
(English-only).

**Source:** `platform/blueprints/whatsapp/routes.py:803-878`, `:881-891`,
`:894-917`, `:920-928`, `:931-959`;
`platform/templates/whatsapp/reminder_admin.html:1-212`;
`platform/models/database.py:2164-2172` (`reminder_runs`)

---

## 13. Screen: WhatsApp Reminder Scheduler

**URL.** `GET /whatsapp/scheduler`

**Purpose.** Show how much work the nightly job would find right now, let an
operator run any one of the three jobs on demand, and list what has already been
sent.

**How to reach it.** **Nothing links to this page.** No sidebar entry, no
launcher card and no toolbar button anywhere in the product points at
`/whatsapp/scheduler`. You reach it by typing the URL.

**Who can open it.** Any role holding the `whatsapp` grant — including
`reception`. The route carries no role list, so **every button on this page,
including "Run All Jobs Now", is available to a receptionist**, while the
equivalent button on Reminder Admin is not.

**Page title.** `WhatsApp Reminder Scheduler / مجدول تذكيرات واتساب`
**Subtitle.** `Manual triggers, history & queue status / التشغيل اليدوي والسجل
وحالة الطابور`

### 13.1 Queue overview — three cards

Each is a live count against today's data. All three are wrapped in
`try/except` and fall back to `0` if the query fails.

| Card | Caption | What it counts |
|---|---|---|
| `📅 Tomorrow's Appointments` / `📅 مواعيد الغد` | `owners with WhatsApp who have appointments tomorrow / مالك لديهم واتساب ولديهم مواعيد غداً` | appointments dated tomorrow with status `Scheduled` or `Confirmed`, whose owner has a non-empty `whatsapp_phone` |
| `💉 Overdue Vaccines` / `💉 تطعيمات متأخرة` (red) | `pets with vaccine due or overdue (owner has WhatsApp) / حيوان لديه تطعيم مستحق أو متأخر (المالك لديه واتساب)` | vaccinations with `next_due_at <= today` whose owner's `whatsapp_phone` is not NULL |
| `🧾 Unpaid Invoices` / `🧾 فواتير غير مدفوعة` (amber) | `owners with unpaid invoices and WhatsApp / مالك لديهم فواتير غير مدفوعة وواتساب` | invoices with status `Unpaid` or `Partial` whose owner's `whatsapp_phone` is not NULL |

**These three counts are not what the job will send.** The Overdue Vaccines card
has no lower bound while the job only looks back 7 days; the Unpaid Invoices card
has no due-date filter while the job requires the invoice to be at least 3 days
overdue; and neither card excludes the entities already reminded today. Treat
them as rough workload indicators.

### 13.2 Manual Trigger panel

Heading `⚡ Manual Trigger / ⚡ تشغيل يدوي`, with the note *"Normally runs
automatically at 09:00 daily. Use these buttons to trigger right now. / تعمل
تلقائياً الساعة 09:00 يومياً. استخدم هذه الأزرار للتشغيل الآن."*

All five buttons post to their route with a confirm dialog. Every confirm string
is **English-only**.

| Button | Posts | Confirm text | Result flash |
|---|---|---|---|
| `🚀 Run All Jobs Now` / `🚀 تشغيل كل المهام الآن` | `/whatsapp/scheduler/run` with `type=all` | `Run ALL reminder jobs now? This will send real WhatsApp messages.` | *"All reminder jobs triggered successfully."* (`success`) |
| `📅 Appointment Reminders` / `📅 تذكيرات المواعيد` | `type=appt` | `Send appointment reminders now?` | *"Appointment reminders sent: `<n>`."* (`success`) |
| `💉 Vaccine Reminders` / `💉 تذكيرات التطعيم` | `type=vaccine` | `Send vaccine reminders now?` | *"Vaccine reminders sent: `<n>`."* (`success`) |
| `🧾 Invoice Reminders` / `🧾 تذكيرات الفواتير` | `type=invoice` | `Send invoice reminders now?` | *"Invoice reminders sent: `<n>`."* (`success`) |
| `🗑 Clear Old History` / `🗑 مسح السجل القديم` | `/whatsapp/scheduler/clear-history` | `Clear history older than 30 days?` | see §13.4 |

Any exception during a run is caught and flashed as *"Scheduler error:
`<error>`"* (`danger`). An unrecognised `type` value flashes *"Unknown job
type."* (`warning`).

The `<n>` in the three per-job flashes counts reminders whose send returned
`Sent` **or** `Pending` — not the number of rows examined, and not the number
delivered. A run against a disconnected instance reports `0`.

`type=all` runs the whole job through `run_reminder_jobs()`, which opens its own
connection and shares one transport across the three sub-jobs. The three
individual buttons call the sub-job functions directly **without a shared
sender**, which means the settings lookup runs once per message and the
consecutive-failure budget (§17.5) is not shared. See
[Known limits](#reminders-and-the-nightly-job).

### 13.3 Stats summary

One tile per distinct `run_type` found in the history below, each showing a
coloured job badge (`Appt Reminder` blue, `Vaccine Reminder` green,
`Invoice Reminder` amber — badge labels are the raw type title-cased, in
English) and a count, captioned `total sent (all time) / إجمالي المرسل (الإجمالي
الكلي)`.

The caption is wrong on two counts: the number is computed from the **200-row
history slice** below, not all time, and `reminder_runs` holds one row per
entity refreshed in place, so it counts *entities ever reminded of this type*,
not messages sent.

### 13.4 Clear Old History

Deletes `reminder_runs` rows whose `run_at` is older than **30 days**, using an
ISO cutoff bound as a parameter so it works on both database engines. Flashes
*"History cleared (entries older than 30 days removed)."* as `success`. A
fallback path exists for older SQLite databases and flashes the shorter
*"History cleared."*; if both fail it flashes *"Could not clear history:
`<error>`"* as `warning`.

Deleting a dedup row means the entity it referred to becomes eligible again — a
7-day-old vaccine reminder is safe, but this is why the cutoff is 30 days and
not shorter.

### 13.5 Reminder History table

Heading `📋 Reminder History / 📋 سجل التذكيرات`. The **200 most recent
`reminder_runs` rows**, newest first.

| Column | Content |
|---|---|
| `#` | Row id |
| `Type` / `النوع` | The `run_type` badge, `_` replaced by spaces, title-cased |
| `Entity` / `الكيان` | `<entity_type> #<entity_id>` — e.g. `appointment #412` |
| `Status` / `الحالة` | `status` from the row, defaulting to `sent`. In practice **always `sent`**, because that is the only value the job ever writes |
| `Sent At` / `أُرسلت في` | `run_at[:16]` |

The query attempts a left join onto `whatsapp_log` to pull the real delivery
status and error for each run, and **the template renders neither** — the joined
`wa_status` and `wa_error` columns are fetched and discarded. If the join fails,
a fallback query without it runs instead; if that fails too, the table is empty.

Empty state: *"No reminder history yet. Reminders run automatically at 09:00
daily, or trigger manually above."* (English-only).

**Source:** `platform/blueprints/whatsapp/routes.py:1001-1077`, `:1080-1112`,
`:1115-1148`; `platform/templates/whatsapp/scheduler.html:1-139`

---

## 14. Screen: Message Log

**URL.** `GET /whatsapp/log`

**Purpose.** The delivery record. Every WhatsApp message the platform attempted
to send — from the Send Center, from a reminder, from an invoice, from a
telemedicine invite — with what happened to it.

**How to reach it.** Control Center → log tab → `View All Logs → / عرض كل
السجلات ←`; `📋 Message Log / 📋 سجل الرسائل` from the Templates list or the
Pending Reminders screen.

**Who can open it.** Any role holding the `whatsapp` grant.

**Page title.** `Message Log / سجل الرسائل`
**Subtitle.** `Recent WhatsApp messages sent from the platform / أحدث رسائل
واتساب المرسلة من المنصة`

### 14.1 What is listed

`SELECT wl.*, o.full_name AS owner_name FROM whatsapp_log wl LEFT JOIN owners o
ON wl.owner_id = o.id ORDER BY wl.sent_at DESC LIMIT 200`.

**The 200-row cap has no pagination, no date filter, no status filter and no
search.** There is no way to reach message 201 from any screen. There is no CSV
or PDF export of this log.

### 14.2 The four stat pills

Computed in the template **from the 200 rows on screen**, not from the table.

| Pill | Counts rows whose `status` is exactly |
|---|---|
| `Total Shown` / `إجمالي المعروض` | any — the number of rows rendered |
| `Sent` / `مُرسل` | `Sent` |
| `Failed` / `فشل` | `Failed` |
| `Pending` / `قيد الانتظار` | `Pending` |

Rows carrying `Not Configured` or `Not Sent` are inside `Total Shown` and inside
**none** of the other three, so on a clinic whose WhatsApp is disconnected the
three counters can all read zero while the table is full.

### 14.3 Columns

| Column | Content |
|---|---|
| `Date / Time` / `التاريخ / الوقت` | `sent_at[:16]`, or `—`. Local clinic time |
| `Owner` / `المالك` | Owner full name via the join, or `—` when the row has no `owner_id` |
| `Phone` / `الهاتف` | `phone`, monospace, or `—`. This is the number as it was **given to the send routine**, before the `@c.us` suffix is added |
| `Message` / `الرسالة` | One truncated line; the full stored text is the tooltip. The stored text is capped at 500 characters for the manual send paths and stored in full by the nightly job |
| `Template` / `القالب` | `template_name` in a monospace chip, or the grey word `custom / مخصص` when blank |
| `Status` / `الحالة` | See §15 |

### 14.4 Empty state

`💬` in WhatsApp green · `No messages sent yet / لم تُرسل رسائل بعد` ·
*"Messages sent via WhatsApp will appear here. / ستظهر هنا الرسائل المرسلة عبر
واتساب."* · `🔔 View Pending Reminders / 🔔 عرض التذكيرات المعلقة`.

**Source:** `platform/blueprints/whatsapp/routes.py:678-691`;
`platform/templates/whatsapp/message_log.html:1-119`;
`platform/models/database.py:1870-1882` (`whatsapp_log`)

---

## 15. The log statuses, in full

`whatsapp_log.status` is a free-text column with a schema default of `Pending`.
Five values are ever written or displayed.

### 15.1 What each status means

| Status | Written by | Means |
|---|---|---|
| **`Sent`** | every send path, when the Wapilot call returned no error | The message was **accepted by Wapilot**. It does not mean the client's phone received it, and does not mean it was read — the platform never polls for delivery receipts |
| **`Failed`** | every send path, when the Wapilot call returned an error | The API refused the message or was unreachable. The reason is in the `error` column |
| **`Not Configured`** | the nightly reminder job only | There is no Wapilot token or no instance ID, so **nothing was transmitted**. The `error` column carries the reason and what to do about it |
| **`Not Sent`** | the nightly reminder job only | The run had already suffered 5 consecutive failures and gave up, so this message was **deliberately skipped** |
| **`Pending`** | nothing writes it | The schema default. It only appears on rows created by an insert that omitted the status column — for example seeded demo data |

### 15.2 Where each status comes from

| Status | Manual send (`/whatsapp/send`, Send Center text, invoice, telemedicine, Send Now) | Nightly job / Scheduler run |
|---|---|---|
| `Sent` | ✔ | ✔ |
| `Failed` | ✔ | ✔ |
| `Not Configured` | ✘ — the manual paths raise `WapilotNotConfigured` instead and **write no log row at all** | ✔ |
| `Not Sent` | ✘ | ✔ |
| `Pending` | ✘ | ✘ |

The most important consequence: **when WhatsApp is not connected, a manual send
leaves no trace in the log.** The Send Center shows a red `❌ Error: WhatsApp is
not configured…` box and that is the only record. Only the nightly job records
its non-delivery.

### 15.3 How each status is displayed

**Message Log (`/whatsapp/log`):**

| Stored status | Pill | Text |
|---|---|---|
| `Not Configured` | red | `⚠ Not sent — WhatsApp not connected` / `⚠ لم تُرسل — واتساب غير متصل`. The full `error` is the tooltip |
| `Sent` | green | `✓ Sent` / `✓ أُرسلت` |
| `Failed` | red | `✗ Failed` / `✗ فشلت`, plus the **first 40 characters** of `error` followed by `…` underneath in small red type; the full error is the tooltip |
| `Not Sent` | amber | `⏳ Pending` / `⏳ قيد الانتظار` — **the skip reason is not shown, and the row reads as if it were still on its way** |
| `Pending` | amber | `⏳ Pending` / `⏳ قيد الانتظار` |
| anything else | amber | `⏳ Pending` / `⏳ قيد الانتظار` |

The `Not Configured` case is handled deliberately and carries a comment in the
template saying why: *"Never render as sent. WhatsApp is not connected, so this
message never left the building — the clinic must be able to see that."*

**Control Center log tab:** three-way only — `Sent` green, `Failed` red,
everything else an amber pill printing the **raw status string untranslated**,
so `Not Configured` and `Not Sent` show as those English words.

**Client record → Communication History (`/crm/owners/<id>`):** the raw status
word.

### 15.4 The other columns on a log row

| Column | Written by |
|---|---|
| `http_status` | Only `_send_and_log` writes it, taking `data["status"]` from the Wapilot response when the response is a dict and `0` otherwise. `api_send_text` and the nightly job leave it NULL. Nothing displays it anywhere |
| `response` | The Wapilot response serialised to JSON and truncated to 500 characters, by the two manual paths only. The nightly job leaves it NULL. Nothing displays it |
| `error` | The error string, truncated to 300 characters by `_send_and_log`, stored in full by the other paths. Displayed only on the Message Log, and only for `Failed` (40 chars) and `Not Configured` (tooltip) |
| `reminder_id`, `pet_id` | Columns exist in the schema. **Nothing in the application ever writes them** |
| `template_name` | The template's *name* from `/whatsapp/send`; the template's *numeric id* from the Send Center; the job type (`appt_reminder`, `vaccine_reminder`, `invoice_reminder`) from the nightly job; `invoice_whatsapp` from a finance send; `telemedicine_invite` from a telemedicine send; blank from everything else |

> Source: `platform/blueprints/whatsapp/routes.py:51-72` (`_send_and_log`),
> `:254-266` (`api_send_text`);
> `platform/blueprints/whatsapp/scheduler.py:127-165` (`_send_whatsapp`),
> `:139`, `:143-146`;
> `platform/templates/whatsapp/message_log.html:36-38`, `:90-104`;
> `platform/templates/whatsapp/control_center.html:223-231`;
> `platform/models/database.py:1870-1882`

---

## 16. Screen: WhatsApp Settings

**URL.** `GET/POST /whatsapp/settings` (also reached as `/whatsapp/reminder-settings`, which is a 302 to here)

**Purpose.** Store the Wapilot credentials, switch the three automated reminder
types on and off, and edit the three reminder message templates.

**How to reach it.** Control Center → `⚙️ Settings`; sidebar → `Reminder Settings
/ إعدادات التذكير`; automatically, whenever a WhatsApp screen finds no
credentials.

**Who can open it.** super_admin, clinic_owner, branch_manager. (`support_admin`
is on the role list but blocked by the module gate; `reception` holds the grant
but is not on the role list.)

**Page title.** `WhatsApp Settings / إعدادات واتساب`
**Subtitle.** `Configure Wapilot API connection and reminder messages / إعداد
اتصال Wapilot API ورسائل التذكير`

### 16.1 Section: Wapilot API Connection

Heading `🔌 Wapilot API Connection / 🔌 اتصال Wapilot API`, with the line
`Credentials from / بيانات الاعتماد من` **wapilot.net** (a link opening
`https://wapilot.net` in a new tab) `dashboard.` — the word "dashboard" is
English-only.

| Field | Label | Description under it | Input type | Placeholder | Saved as |
|---|---|---|---|---|---|
| `wapilot_token` | `API Token` | `API token from wapilot.net` | **password** | `API token…` | `settings` key `wapilot_token`, category `wapilot` |
| `wapilot_instance_id` | `Instance ID` | `Your WhatsApp instance unique name` | text | `instance4042` | `settings` key `wapilot_instance_id`, category `wapilot` |

**Both labels and both descriptions are English-only** — they are Python strings
in the route, not `t()` calls, so they stay English in Arabic mode.

**These two fields are only saved when non-empty.** The route skips any blank
value, which means **there is no way to clear a token or an instance ID from
this screen.** Once set, a credential can only be replaced, not removed.

The token input is `type="password"` so it renders as dots — but its `value`
attribute holds the real token, so it is visible in the page source and to
anything with access to the rendered HTML.

**`🔍 Test Connection` / `🔍 اختبار الاتصال`** calls
`GET /whatsapp/api/instance/status` and prints the result beside itself:

- `Testing…` in grey while it runs (English-only);
- `✅ Connected — Status: <status>` in green, where `<status>` is `data.status`,
  then `data.state`, then the literal `OK`;
- `❌ <error>` or `❌ Connection failed` in red;
- `❌ Network error: <message>` in red if the fetch itself throws.

All four are English-only. **Test Connection tests the saved credentials, not
what is currently typed in the boxes** — it makes no attempt to send the form
first, so testing a newly pasted token before pressing Save reports on the old
one.

### 16.2 Section: Automated Reminder Settings

Heading `🔔 Automated Reminder Settings / 🔔 إعدادات التذكير التلقائي`, with the
variables line `Variables: / المتغيرات:` listing seven code chips:
`{owner}` `{pet}` `{date}` `{time}` `{vaccine}` `{invoice}` `{amount}`.

Six controls, in this order.

| Key | Label | Description | Control | Default |
|---|---|---|---|---|
| `reminder_appt_enabled` | `Appointment Reminders` | `Send reminders 24h before appointment` | checkbox | ticked |
| `reminder_vaccine_enabled` | `Vaccine Due Reminders` | `Remind owners of upcoming vaccines` | checkbox | ticked |
| `reminder_invoice_enabled` | `Invoice Overdue Alerts` | `Alert owners on unpaid invoices` | checkbox | ticked |
| `reminder_appt_msg` | `Appointment Message` | — | 3-row textarea | `Dear {owner}, {pet} has an appointment tomorrow ({date} at {time}).` |
| `reminder_vaccine_msg` | `Vaccine Message` | — | 3-row textarea | `Dear {owner}, {pet} is due for the {vaccine} vaccine (due: {date}).` |
| `reminder_invoice_msg` | `Invoice Message` | — | 3-row textarea | `Dear {owner}, Invoice #{invoice} ({amount}) was due on {date} and remains unpaid.` |

**All six labels and all three descriptions are English-only** — again, they are
Python strings in the route.

Which placeholders each message may use is fixed by the job, not by the chip list
above:

| Message | Placeholders that resolve |
|---|---|
| Appointment | `{owner}` `{pet}` `{date}` `{time}` `{type}` |
| Vaccine | `{owner}` `{pet}` `{vaccine}` `{date}` |
| Invoice | `{owner}` `{invoice}` `{amount}` `{date}` `{total}` |

`{amount}` on the invoice message is what is **still owed** (`due_amount`), not
the invoice total; `{total}` is the invoice total. Both are formatted to two
decimal places with no currency symbol — add `EGP` or `جنيه` to your message
text yourself if you want one.

**A placeholder the job does not recognise does not break the reminder** — the
job catches the substitution error, logs a warning, and sends its built-in
English wording for that reminder type instead. So a typo in your Arabic message
silently reverts that whole night's reminders of that type to English.

### 16.3 Saving

`💾 Save Settings / 💾 حفظ الإعدادات` writes both groups in one transaction:

- The two Wapilot keys, **only if non-empty**, into category `wapilot`.
- All six reminder keys unconditionally into category `whatsapp`. An unticked
  checkbox is stored as the string `"0"`; a ticked one as `"1"`. A cleared
  textarea is stored as an **empty string**, and the job then falls back to its
  built-in wording for that type.

Each write records `updated_at` and `updated_by` (your username). An audit row is
written reading *"Updated WhatsApp / Wapilot settings"*. It flashes
*"Settings saved."* as `success` and returns here.

`Cancel / إلغاء` returns to the Control Center.

### 16.4 Reading the switches back

The checkbox on screen is ticked when the stored value is exactly `"1"`.
The **job** uses a looser test: a reminder type is ON unless its stored value is
one of `0`, `false`, `no`, `off` (case-insensitively, after stripping). A missing
key means ON.

**Source:** `platform/blueprints/whatsapp/routes.py:697-769`, `:773-776`;
`platform/blueprints/whatsapp/scheduler.py:168-208`;
`platform/templates/whatsapp/wa_settings.html:1-101`

---

## 17. The nightly reminder job

There is no screen for this, but three screens trigger it and two display its
output, so it is documented here in full.

### 17.1 When it runs

APScheduler fires `run_reminder_jobs()` at **09:00 every day**, in whichever
worker process holds the scheduler lock, **once per registered clinic**. A
failure in one clinic is logged and the loop continues to the next.

It can also be run on demand from:

- Reminder Admin → `▶ Run Reminder Job Now` (all three jobs) — role-gated;
- Scheduler → `🚀 Run All Jobs Now` (all three) — **not** role-gated;
- Scheduler → the three per-type buttons (one job each) — **not** role-gated.

> Source: `platform/app.py:775-780`, `:668` (the lock), `:849`;
> `platform/blueprints/whatsapp/scheduler.py:338-365`

### 17.2 Job 1 — Appointment reminders

Skipped entirely if `reminder_appt_enabled` is off.

**Who gets one:** appointments whose `appt_date` is **tomorrow**, whose status is
`Scheduled` or `Confirmed`, joined to an owner whose `whatsapp_phone` is neither
NULL nor empty, joined to a pet.

**What is sent:** your `reminder_appt_msg` with `{owner}`, `{pet}`, `{date}`,
`{time}`, `{type}` filled in. `{time}` is `appt_start`, or the literal `TBD` when
blank. If your message is empty or has an unknown placeholder, the built-in
English wording goes out instead:

```
Dear <owner>,
Reminder: <pet> has a <type> appointment tomorrow (<date> at <time>).
Please arrive 10 minutes early. Reply CONFIRM to confirm.
```

**Nothing listens for a CONFIRM reply.** There is no inbound webhook anywhere in
the platform.

**Logged with** `template_name = "appt_reminder"`, `entity_type = "appointment"`.

### 17.3 Job 2 — Vaccine reminders

Skipped entirely if `reminder_vaccine_enabled` is off.

**Who gets one:** vaccinations whose `next_due_at` falls **between 7 days ago and
today inclusive**, whose pet's owner has a non-empty `whatsapp_phone`.

**What is sent:** your `reminder_vaccine_msg` with `{owner}`, `{pet}`,
`{vaccine}`, `{date}`. The built-in fallback distinguishes due from overdue:

```
Dear <owner>,
[OVERDUE: ]<pet> is due for / overdue for the <vaccine> vaccine (due: <date>).
Please book an appointment at your earliest convenience.
```

Your own message text gets no overdue marker — the `OVERDUE:` prefix exists only
in the built-in wording.

**Logged with** `template_name = "vaccine_reminder"`, `entity_type =
"vaccination"`.

### 17.4 Job 3 — Invoice reminders

Skipped entirely if `reminder_invoice_enabled` is off.

**Who gets one:** invoices whose status is `Unpaid` or `Partial` and whose
`due_date` is **3 or more days in the past**, whose owner has a non-empty
`whatsapp_phone`. There is no lower bound, so an invoice overdue by a year is
still in scope every day until it is paid or its status changes.

**What is sent:** your `reminder_invoice_msg` with `{owner}`, `{invoice}`,
`{amount}`, `{date}`, `{total}`. `{amount}` is `due_amount` — what is still owed
— falling back to `total` only when `due_amount` is NULL. Built-in fallback:

```
Dear <owner>,
Invoice #<number> has <owed> outstanding (due <date>).
Please contact us to settle your balance. Thank you.
```

Amounts are printed to two decimals with **no currency symbol**.

**Logged with** `template_name = "invoice_reminder"`, `entity_type = "invoice"`.

### 17.5 Deduplication and the failure budget

**One reminder per entity per day.** Before sending, the job checks
`reminder_runs` for a row with the same `run_type`, `entity_id` and
`entity_type` whose `DATE(run_at)` is today (clinic-local). If one exists, the
entity is skipped. After sending — **whatever the outcome** — the row is written
or refreshed with today's timestamp.

Because the marker is written even for a failure, **a message that failed today
will not be retried today**. It will be retried tomorrow only if the entity is
still eligible; a failed appointment reminder is gone for good, because the
appointment is no longer "tomorrow".

**The 5-failure budget.** One `_Sender` is built per run and carries a counter.
After **5 consecutive failures** the run gives up: every remaining message is
logged with status `Not Sent` and the error

> Skipped: 5 sends in a row failed, so the rest of this run was abandoned rather
> than left retrying a dead connection.

One success resets the counter to zero. The budget exists because a single send
against an unreachable host was measured at 535 seconds — without the cap, a
clinic with 200 clients and a dead instance would occupy the scheduler thread
for most of a day.

**When WhatsApp is not configured**, no send is attempted at all: every message
is logged as `Not Configured` with the error

> WhatsApp is not connected — no API token is set. Connect it under WhatsApp →
> Settings.

(or `…no API instance ID is set…` when the token is present but the instance is
not).

### 17.6 What the run records

- One `whatsapp_log` row per message, always, with the full untruncated message
  text.
- One `reminder_runs` row per entity, inserted or refreshed.
- One audit row per full `run_reminder_jobs()` call, under username `scheduler`,
  role `system`, action `reminder_run`, details `appt=<n> vaccine=<n>
  invoice=<n>`. The three per-type Scheduler buttons write **no** audit row.
- Log lines: an INFO summary, a WARNING per unconfigured message, an ERROR when
  the run is abandoned.

**The nightly job never touches the `reminders` table.** The Pending Reminders
list and the Reminder Admin worklists are populated only by the manual form on
Reminder Admin and by the public website booking API. The three automated jobs
read appointments, vaccinations and invoices directly.

**Source:** `platform/blueprints/whatsapp/scheduler.py:1-365`;
`platform/app.py:775-780`;
`platform/blueprints/public_api/routes.py:223-236` (the only other reminder
writer)

---

## 18. Background JSON endpoints — the full surface

Every endpoint below returns `{"ok": <bool>, "data": <parsed API response>,
"error": "<string>"}` and HTTP 200 unless noted. `ok` is simply "the Wapilot call
produced no error string" — it is not an HTTP status check beyond that.

When WhatsApp is unconfigured they all return HTTP **503** with
`{"ok": false, "data": {}, "error": "WhatsApp is not configured. …"}`.

### 18.1 Instance

| Endpoint | Wapilot call |
|---|---|
| `GET /whatsapp/api/instance/status` | `GET /instances/<iid>/status` |
| `GET /whatsapp/api/instance/details` | `GET /instances/<iid>` |
| `GET /whatsapp/api/instance/qr` | `GET /instances/<iid>/qr-code` |
| `GET /whatsapp/api/instance/screenshot` | `GET /instances/<iid>/screenshot` |
| `POST /whatsapp/api/instance/start` | `POST /instances/<iid>/start` |
| `POST /whatsapp/api/instance/restart` | `POST /instances/<iid>/restart` |
| `POST /whatsapp/api/instance/logout` | `POST /instances/<iid>/logout` |
| `POST /whatsapp/api/instance/troubleshoot` | `POST /instances/<iid>/troubleshoot` |
| `GET /whatsapp/api/instance/queue-settings` | `GET /instances/<iid>/queue-settings` |
| `PUT /whatsapp/api/instance/queue-settings` | `PUT /instances/<iid>/queue-settings`, body forwarded verbatim |

### 18.2 Messages

| Endpoint | Wapilot call | Notes |
|---|---|---|
| `GET /whatsapp/api/messages` | `GET /<iid>/messages` | **Every query-string parameter you pass is forwarded as a Wapilot filter**, empty values dropped. The UI never sends any |
| `GET /whatsapp/api/messages/<msg_id>` | `GET /<iid>/messages/<id>` | No UI caller |
| `POST /whatsapp/api/messages/<msg_id>/retry` | `POST /<iid>/messages/<id>/retry` | |
| `POST /whatsapp/api/messages/retry-all` | `POST /<iid>/messages/retry-all`, body forwarded | |

### 18.3 Send

| Endpoint | Body | Logs to `whatsapp_log`? |
|---|---|---|
| `POST /whatsapp/api/send/text` | JSON `{phone, text, owner_id?, template_name?}` | **Yes** |
| `POST /whatsapp/api/send/image` | multipart `phone`, `caption`, `media` | No |
| `POST /whatsapp/api/send/file` | multipart `phone`, `caption`, `media` | No |
| `POST /whatsapp/api/send/video` | multipart `phone`, `caption`, `media` | No |

Validation failures return HTTP 400 with
`{"ok": false, "error": "phone and text required"}` or
`{"ok": false, "error": "phone and media required"}`.

The client also implements a `send-list` interactive-message call
(`send_list_message`). **No route exposes it and no screen uses it.**

### 18.4 Campaigns

| Endpoint | Wapilot call |
|---|---|
| `GET /whatsapp/api/campaigns` | `GET /campaigns` — no UI caller |
| `POST /whatsapp/api/campaigns` | `POST /campaigns` — no UI caller; body may carry `instance_uns` and `default_message` |
| `POST /whatsapp/api/campaigns/<cid>/start` | `POST /campaigns/<cid>/start` |
| `POST /whatsapp/api/campaigns/<cid>/pause` | `POST /campaigns/<cid>/pause` |
| `PATCH /whatsapp/api/campaigns/<cid>/finish` | `PATCH /campaigns/<cid>/finish` |
| `POST /whatsapp/api/campaigns/<cid>/copy` | `POST /campaigns/<cid>/copy` |
| `POST /whatsapp/api/campaigns/<cid>/reset-failed` | `POST /campaigns/<cid>/reset-failed` |
| `POST /whatsapp/api/campaigns/<cid>/schedule` | `POST /campaigns/<cid>/schedule` with `{schedule_date}` |
| `DELETE /whatsapp/api/campaigns/<cid>/schedule` | `DELETE /campaigns/<cid>/schedule` |
| `GET /whatsapp/api/campaigns/<cid>/delay` | `GET /campaigns/<cid>/delay` |
| `PATCH /whatsapp/api/campaigns/<cid>/delay` | `PATCH /campaigns/<cid>/delay`, body forwarded |
| `GET /whatsapp/api/campaigns/<cid>/messages` | `GET /campaigns/<cid>/messages` |
| `POST /whatsapp/api/campaigns/<cid>/messages` | `POST /campaigns/<cid>/messages` with `{messages: [...]}` |
| `DELETE /whatsapp/api/campaigns/<cid>/messages` | `DELETE /campaigns/<cid>/messages` with `{ids: [...]}` |
| `GET /whatsapp/api/campaigns/<cid>/stats` | `GET /campaigns/<cid>/messages/stats` — no UI caller |
| `GET /whatsapp/api/campaigns/<cid>/queue` | `GET /campaigns/<cid>/messages/queue` |
| `GET /whatsapp/api/campaigns/<cid>/done` | `GET /campaigns/<cid>/messages/done` |

### 18.5 Templates and lookup

| Endpoint | Returns |
|---|---|
| `GET /whatsapp/api/templates` | A **bare JSON array** (not the `ok/data/error` envelope) of active templates: `id`, `name`, `scenario`, `template_text`, ordered by name. **No UI caller** |
| `GET /whatsapp/api/lookup/lid/<lid>` | Wapilot's chat ID for a linked-device id. **No UI caller** |
| `GET /whatsapp/api/lookup/phone/<phone>` | Wapilot's LID for a phone number. Used by the Send Center |

**Both lookup endpoints target a malformed path.** The client builds
`/api/v2/<iid>/lids/…` and prepends the base URL, which already ends in
`/api/v2` — so the request goes to
`https://api.wapilot.net/api/v2/api/v2/<iid>/lids/…`. See
[Known limits](#the-wapilot-integration).

**Source:** `platform/blueprints/whatsapp/routes.py:126-225`, `:244-306`,
`:382-489`, `:598-611`, `:783-794`;
`platform/blueprints/whatsapp/wapilot.py:76-251`

---

## 19. Screen: Notifications

**URL.** `GET /notifications/`

**Purpose.** The in-app alert inbox for the signed-in user: backup failures,
role-targeted operational alerts, and anything else another module chose to
raise.

**How to reach it.** The 🔔 bell in the top bar; sidebar → PLATFORM →
Notifications; the launcher card.

**Who can open it.** Every signed-in user, any role. Each user sees only their
own rows.

**Page title.** `Notifications / الإشعارات`
**Subtitle.** `Your in-app alerts and messages` — **English-only**.

### 19.1 What is listed

`SELECT * FROM notifications WHERE recipient_id = <you> ORDER BY created_at DESC
LIMIT 50`.

**Fifty rows, newest first, read and unread together.** There is no pagination,
no filter, no search, no per-module tab, and no way to reach notification 51.

### 19.2 Toolbar

| Button | Shown when | Effect |
|---|---|---|
| `Mark All Read` — **English-only** | there is at least one notification | Posts to `POST /notifications/mark-all-read`, which sets `is_read=1` on **every** notification for this user — including the ones beyond the fifty on screen — and redirects back to wherever you came from |

There is **no confirmation** and **no undo**.

### 19.3 What each row shows

| Element | Content |
|---|---|
| Icon | The row's `icon`, or `🔔` |
| Title | `title`. Bold at weight 700 when unread, 500 when read |
| Timestamp | `created_at`, printed **raw and in full** — not truncated, not reformatted |
| `New` badge — **English-only** | Green pill, unread rows only |
| Body | `body`, in smaller grey type |
| `View →` — **English-only** | Rendered only when the row has a `link`. A plain link to that URL |
| `Read` button — **English-only** | Unread rows only |

Read rows are rendered at 75% opacity on the page background; unread rows sit at
full opacity on the surface colour.

### 19.4 The `Read` button

Calls `POST /notifications/mark-read/<id>` and, on `{"ok": true}`, updates the
row in place without reloading: dims it, removes the `New` badge, removes the
button, and decrements the bell badge — removing the badge entirely when it
reaches zero.

The server's update is scoped `WHERE id=? AND recipient_id=?`, so marking
another user's notification is impossible. It always returns `{"ok": true}`
regardless of whether a row was actually updated.

### 19.5 Empty state

`🔔` · `All caught up!` · `No notifications to show.` — **all three
English-only**.

### 19.6 Where notifications come from

There is no screen anywhere in the platform for creating a notification. Three
helper functions do it:

| Function | What it does |
|---|---|
| `create_notification(recipient_id, title, body, icon, link, module, entity_type, entity_id, recipient_role)` | One row for one user |
| `notify_role(role, …)` | One row for every **active** user holding that role |
| `notify_managers(…)` | `notify_role` for `super_admin`, `clinic_owner`, `branch_manager`, `hr` |

All three swallow every exception silently — a failure to notify never breaks
the action that raised it. A worked example is the nightly backup: when it
fails, it calls `notify_managers(title="Backup Failed — <clinic>", body=<the
error>, icon="❌", link="/system/monitor", module="system")`.

`notifications.module`, `entity_type` and `entity_id` are stored and **displayed
nowhere**.

### 19.7 The unread endpoint

`GET /notifications/api/unread` returns
`{"count": <int>, "items": [ …up to 10 notifications… ]}`.

**Nothing in the product calls it.** The bell badge is rendered server-side from
the context processor on every page load, so it only updates on navigation.

**Source:** `platform/blueprints/notifications/routes.py:1-40`;
`platform/templates/notifications/index.html:1-80`;
`platform/models/database.py:4133-4199`, `:2127-2142` (table);
`platform/app.py:400-404`, `:452`, `:763-769` (backup alert example);
`platform/templates/base.html:267-275`, `:421-431`

---

## 20. Where communications show up elsewhere

Four other modules send WhatsApp messages or display WhatsApp data. Their
screens are documented in their own chapters; this is what they do to the
communications data.

| Where | What it does | Logged as |
|---|---|---|
| **Finance → Invoice detail → `📱 Send WhatsApp` / `إرسال`** (`POST /finance/invoices/<id>/whatsapp`) | Builds a formatted invoice summary — clinic name, invoice number, date, each line with its total in **EGP**, subtotal, discount, tax, total, paid, balance due, then *"Thank you for choosing Aleefy 🐾 / Happy Pets, Healthy Lives"* — and sends it to `owner_phone`. Flashes *"Invoice sent via WhatsApp to `<phone>`."* or *"WhatsApp queued / failed — check message log."*, and *"Owner has no phone number on file."* when there is no number. If WhatsApp is unconfigured the raised error is caught and flashed as *"WhatsApp error: `<message>`"*, and **no log row is written** | `template_name = "invoice_whatsapp"` |
| **Telemedicine → session detail → send room link** | Sends the consultation time and the room URL to the owner's `whatsapp_phone`. Flashes *"Room link sent to `<phone>` via WhatsApp."* — **regardless of whether the send succeeded**, because it ignores the returned status. Flashes *"Owner has no WhatsApp number registered."* when there is no number and *"Could not send WhatsApp: `<error>`"* on an exception | `template_name = "telemedicine_invite"` |
| **Client record** (`/crm/owners/<id>`) → Communication History / سجل التواصل | Merges the owner's **last 20 `whatsapp_log` rows** with their **last 20 `reminders` rows** into one list, showing date, channel, status, subject (template name or reminder type) and body. An `✉️ Send Message / إرسال رسالة` button opens the Send Center | reads only |
| **Visit / Patient 360 screens** | List the owner's last 50 `whatsapp_log` rows. Visit detail and the Hatem Way exam screen also carry plain `https://wa.me/<number>` links that open WhatsApp Web directly in a new tab — **these bypass Wapilot entirely and are never logged** | reads only, plus unlogged `wa.me` links |

> Source: `platform/blueprints/finance/routes.py:709-752`;
> `platform/blueprints/telemedicine/routes.py:335-360`;
> `platform/blueprints/crm/routes.py:387-400`;
> `platform/blueprints/visits/routes.py:998-1001`;
> `platform/templates/visits/visit_detail.html:128`, `:1043`;
> `platform/templates/visits/exam.html:1803-1804`, `:2120`;
> `platform/templates/crm/owner_detail.html:580-586`

---

## Known limits

Everything below is a real behaviour of the code as it stands. None of it is
speculative, and none of it is described as working anywhere above.

### Navigation and reachability

1. **The Scheduler page is unreachable from the interface.** No sidebar entry,
   no launcher card and no button anywhere links to `/whatsapp/scheduler`. Its
   three per-job trigger buttons and its Clear Old History button only exist on
   that page, so they are effectively hidden features. (no
   `url_for('whatsapp.scheduler')` anywhere under `templates/`)
2. **`POST /whatsapp/reminders/<rid>/send` has no caller.** The route sends a
   reminder, marks it `Sent` on success and returns JSON, but no template posts
   to it. The equivalent working button lives on Reminder Admin under a
   different route. (`routes.py:632-659`)
3. **The Control Center does not link to the Message Log directly**, only from
   inside its log tab, and it does not link to Pending Reminders at all.
   (`control_center.html:6-12`)
4. **`templates/whatsapp/reminder_settings.html` is orphaned.** No route renders
   it; `/whatsapp/reminder-settings` is a redirect to `/whatsapp/settings`.
   (`routes.py:773-776`)
5. **Seven JSON endpoints have no caller anywhere in the product:**
   `/api/templates`, `/api/lookup/lid/<lid>`, `/api/messages/<msg_id>`,
   `GET /api/campaigns`, `POST /api/campaigns`, `/api/campaigns/<cid>/stats`,
   and `/notifications/api/unread`. (`routes.py:598-611, 783-788, 206-211,
   382-398, 472-477`; `notifications/routes.py:34-40`)
6. **The Wapilot client implements `send_list_message` (interactive list
   messages) and `list_instances`, and no route exposes either.**
   (`wapilot.py:76-77, 180-185`)

### Permissions

7. **`support_admin` is named on seven route role lists and can reach none of
   them** — instance start / restart / logout, campaign create / start / pause,
   Settings, and the reminder trigger. Its default grant set is
   `["system","backup","audit","settings"]`, which has no `whatsapp` key, so the
   module gate refuses it first. The **Reminder Settings sidebar link is shown
   to it** and bounces it to the launcher. (`routes.py:155, 162, 169, 327, 401,
   408, 698, 882` versus `database.py:4376`; `base.html:276-281`)
8. **The Scheduler page is not role-gated at all.** `POST /whatsapp/scheduler/run`
   carries only `@login_required`, so **a receptionist can trigger real
   WhatsApp sends to the entire client base** from that page, while the
   identical action on Reminder Admin is restricted to three roles.
   (`routes.py:1080-1081` versus `:881-882`)
9. **Clearing 30 days of run history is not role-gated either**
   (`routes.py:1115-1116`), and deleting dedup rows can cause entities to be
   re-reminded.
10. **Creating, cancelling and sending individual reminders is not role-gated**
    beyond the module grant. (`routes.py:894-895, 920-921, 931-932`)
11. **Sending any message is not role-gated** beyond the module grant — all four
    `/api/send/*` endpoints and `POST /whatsapp/send` carry only
    `@login_required`. (`routes.py:244-245, 270-271, 283-284, 296-297, 964-965`)
12. **Queue settings can be changed by reception.** `PUT
    /whatsapp/api/instance/queue-settings` alters the clinic's throttling for
    every future send and carries only `@login_required`. (`routes.py:182-183`)
13. **The QR code is exposed to reception.** `/whatsapp/api/instance/qr` and
    `/api/instance/screenshot` carry only `@login_required`, so any role holding
    the `whatsapp` grant can read the linking QR and a live screenshot of the
    WhatsApp session. (`routes.py:140-151`)
14. **Buttons are rendered without checking the role behind them.** Start,
    Restart, Logout, Fix on the Control Center; New Campaign, Start, Pause,
    Copy, Reset on the Campaigns list; every action on the Campaign detail; the
    `🗑` delete on every template card — all are shown to users who will be
    refused.
15. **A refused API button produces no visible feedback.** `role_required`
    answers with an HTML redirect to the launcher, not JSON, so `r.json()`
    throws inside the click handler and no toast appears. The button looks
    inert. (`auth/routes.py:184-190`)
16. **The WhatsApp sidebar entry has no role condition**, so doctors, nurses,
    pharmacists, finance, HR, groomers, boarding staff and auditors all see the
    link and are bounced to the launcher when they click it.
    (`base.html:263-266`)
17. **On an unconfigured clinic, reception is bounced twice.** Opening
    `/whatsapp/control` redirects to `/whatsapp/settings`, which reception
    cannot open, so it redirects again to the launcher with a permission flash
    that has nothing to do with the real problem. (`routes.py:28-29, 697-699`)

### The Wapilot integration

18. **Both chat-ID lookup endpoints request a doubled path.**
    `get_chat_id_by_lid` and `get_lid_by_phone` build `/api/v2/<iid>/lids/…`,
    and `_request` prepends a base URL that already ends in `/api/v2` — so the
    request goes to `…/api/v2/api/v2/<iid>/lids/…`. The Send Center's Phone
    Lookup therefore cannot succeed. (`wapilot.py:11, 31, 247-251`)
19. **`instance4042` is hard-coded in the New Campaign note.** The amber box
    tells every clinic that its campaign will use `instance4042`, whatever its
    instance is actually called. (`campaign_form.html:33`)
20. **Every Wapilot call has a fixed 15-second timeout and no retry.** A slow
    instance turns into `Failed` rows. (`wapilot.py:43`)
21. **The API base URL is hard-coded** with no setting to change it.
    (`wapilot.py:11`)
22. **Media uploads are read fully into memory** and re-encoded into a
    hand-built multipart body with a fixed boundary and a hard-coded
    `application/octet-stream` part type. A file containing that boundary string
    would corrupt the request. (`wapilot.py:160-178`)
23. **Delivery is never confirmed.** There is no inbound webhook, no delivery
    receipt polling and no read-receipt handling anywhere in the platform.
    `Sent` means "Wapilot accepted it", nothing more. The built-in appointment
    reminder asks the client to *"Reply CONFIRM to confirm"* and **no reply is
    ever received or processed**. (`scheduler.py:232-236`)
24. **Campaign detail swallows all three of its API errors.** A failing Wapilot
    call renders as an empty campaign with zero statistics and no message on
    screen. (`routes.py:359-363`)
25. **Nothing on the Campaign detail refreshes after an action.** Start, Pause,
    Finish, Copy, Reset, Schedule and Unschedule all toast and leave the stale
    statistics on screen. (`campaign_detail.html:258-272, 386-407`)
26. **Campaign schedule times are sent as a bare local `datetime-local` string**
    with no timezone and no conversion. (`campaigns_list.html:152-157`,
    `campaign_detail.html:389-399`)
27. **Saving queue settings before loading them writes six zeros.** Empty boxes
    are coerced with `+value`, which yields `0`, and all six are always sent.
    (`control_center.html:381-396`)
28. **The Control Center status badge only styles four status words.** Anything
    else Wapilot returns renders as an unstyled transparent pill.
    (`control_center.html:26-34, 303`)
29. **The API Messages tab renders at most 50 messages** and the "Retry All
    Failed" button does not refresh the list afterwards.
    (`control_center.html:410, 428, 445-451`)
30. **The `status_data` the Control Center route fetches is never used.** The
    template ignores it entirely and fetches the status again from the browser,
    so every page load makes two API calls where one would do.
    (`routes.py:91-93` versus `control_center.html`)
31. **The campaign list title filter is misapplied.** `c.name or
    c.default_message or 'Campaign' | truncate(50)` binds the filter to the
    literal `'Campaign'` only, so a long default message is rendered untruncated
    as the card title. (`campaigns_list.html:48`)

### Sending and logging

32. **Media sends are never logged.** Images, files and videos leave no row in
    `whatsapp_log`, so they are absent from the Message Log, the Control Center,
    the client's Communication History and every count.
    (`routes.py:270-306`)
33. **A manual send on an unconfigured clinic leaves no record at all.**
    `_client()` raises before any row is written, so the only evidence is the
    transient red box in the browser. Only the nightly job records
    `Not Configured`. (`routes.py:32-48, 51-57`)
34. **The nightly job sends the bare phone number as the chat ID.** Every manual
    path appends `@c.us`; `_send_whatsapp` passes `owners.whatsapp_phone`
    through with only `.strip()`. The code comment directly above that line says
    the opposite of what the line does. (`scheduler.py:148-149` versus
    `routes.py:56`)
35. **`Not Sent` rows display as `⏳ Pending` on the Message Log.** A message the
    job deliberately abandoned reads as if it were still queued, and the skip
    reason stored in `error` is not shown. (`message_log.html:102-104`)
36. **`Not Configured` and `Not Sent` rows are counted by none of the Message
    Log's Sent / Failed / Pending pills.** On a disconnected clinic all three can
    read zero over a full table. (`message_log.html:36-38`)
37. **The Control Center log tab prints unknown statuses raw and untranslated**,
    so `Not Configured` appears as those English words in Arabic mode.
    (`control_center.html:228-230`)
38. **The Send Center logs the template's numeric ID in the `template_name`
    column**, so the Message Log's Template column shows `7` instead of
    `appt_reminder` for anything sent from that screen. The selection is also
    never cleared, so a subsequent free-text message is still tagged with the
    last template's id. (`send_center.html:260-266, 289`)
39. **Clicking a template in the Send Center loads a mangled copy.**
    Apostrophes are stripped and the text is cut at roughly 200 characters with
    `…` appended, while the preview beside it shows the full text.
    (`send_center.html:217`)
40. **The Send Center never records an owner**, so every message sent from it is
    logged with a NULL `owner_id` and never appears in a client's Communication
    History. (`send_center.html:289` versus `routes.py:255`)
41. **`whatsapp_log.reminder_id` and `whatsapp_log.pet_id` are never written**
    by anything in the application. (`database.py:1870-1882`)
42. **`http_status` and `response` are written by only two of the send paths and
    displayed by none.** (`routes.py:59-60, 263`)
43. **The Message Log is capped at 200 rows with no pagination, no filters, no
    search and no export.** Message 201 is unreachable from any screen.
    (`routes.py:678-691`)
44. **The telemedicine invite reports success unconditionally.** It ignores the
    status returned by `_send_and_log` and always flashes *"Room link sent…"*,
    even when the row it just wrote says `Failed`.
    (`telemedicine/routes.py:353-356`)
45. **`wa.me` links on the visit screens bypass the platform entirely.** They
    open WhatsApp Web in the operator's own browser, so the message is not sent
    from the clinic's number, is not throttled, and is never logged.
    (`visit_detail.html:128, 1043`, `exam.html:1803-1804, 2120`)

### Templates

46. **`variables_json` does nothing.** It drives the chips on a template card and
    nothing else. No substitution engine reads it.
    (`templates_list.html:173-189`)
47. **Templates are never substituted at send time.** Clicking a template copies
    its raw text — `{owner}`, `{pet}` and all — into the message box, and
    `POST /whatsapp/send` sends whatever is there. The only substitution in the
    whole module happens inside the nightly job, against the three Settings
    messages. (`routes.py:975-986`, `scheduler.py:193-208`)
48. **Editing a template performs no validation.** A blank name saves; renaming
    onto an existing name raises an uncaught `UNIQUE` violation and a 500 page.
    Only the create form checks for a blank name, and it reports a duplicate by
    flashing the raw database exception as `Error: <exception text>`.
    (`routes.py:548-585` versus `:509-545`)
49. **Deleting a template is not audited, not soft, and not checked for use.**
    A template referenced by nothing but a log row's `template_name` string
    disappears without trace. (`routes.py:587-596`)
50. **`is_default` is stored, displayed as a `⭐ Default` chip, and read by
    nothing.** No screen or job selects a template because it is the default.
    (`templates_list.html:196`)
51. **`language` is stored and never acted upon.** Nothing filters templates by
    the interface language, and the value `Any` displays as `English` on the
    card. (`templates_list.html:193`)
52. **The template `scenario` is decorative.** Nothing matches a template to a
    reminder type, an invoice or a campaign by scenario. The tabs are a
    presentation filter only.
53. **`whatsapp_templates.created_at` is never displayed anywhere.**
    (`database.py:1866`)

### Reminders and the nightly job

54. **The Run Log's three numbers are always zero.** `reminder_admin.html` prints
    `sent_count`, `failed_count` and `total_processed`, and `reminder_runs` has
    none of those columns — it stores one row per entity, not one per run.
    (`reminder_admin.html:199-201` versus `database.py:2164-2172`)
55. **The Scheduler history's `Status` column is always `sent`.** That is the
    only value `_mark_sent` ever writes, including for a message that failed.
    (`scheduler.py:55-64`, `scheduler.html:128`)
56. **The Scheduler history query fetches the real delivery status and throws it
    away.** It left-joins `whatsapp_log` for `wa_status` and `wa_error`, and the
    template renders neither. (`routes.py:1008-1018`, `scheduler.html:123-130`)
57. **The Scheduler stats tiles are labelled "total sent (all time)" and are
    neither.** They count run rows inside the 200-row history slice, and those
    rows are refreshed in place per entity rather than appended per send.
    (`routes.py:1027-1031`, `scheduler.html:94-105`)
58. **The dedup marker is written even when the send failed**, so a failure is
    never retried the same day — and an appointment reminder that failed is
    never retried at all, because tomorrow the appointment is no longer
    tomorrow. (`scheduler.py:242-247`)
59. **The three per-type Scheduler buttons do not share a sender.** Each message
    re-reads the credentials from the database and each job carries its own
    fresh 5-failure budget, so a dead instance costs up to 15 timeouts instead
    of 5. Only `type=all` shares one. (`routes.py:1094-1105` versus
    `scheduler.py:347-350`)
60. **The three per-type Scheduler buttons write no audit row.** Only
    `run_reminder_jobs()` does. (`routes.py:1094-1105`)
61. **"Reminder job triggered successfully" says nothing about delivery.** It
    only means the function returned without raising; every message inside it
    may have been logged `Not Configured`. (`routes.py:885-890`)
62. **The Pending Reminders due-date colour coding never fires.** The template
    computes `today` from a Jinja global named `now`, which the application does
    not register, so `today` is the empty string and every row falls through to
    the green "upcoming" class — an overdue reminder looks fine.
    (`reminders.html:68-71`; no `now` in `app.py:369-462`)
63. **`📱 Send WA` on Pending Reminders does not clear the reminder.** It posts
    to the generic send route, which never touches `reminders.status`, so the
    row stays `Pending` and returns to the list. (`routes.py:964-993`)
64. **`✓ Mark Sent` marks any reminder sent with no confirmation, no status
    check and no audit** — including one already `Cancelled` or `Failed`.
    (`routes.py:661-675`)
65. **Cancelling an already-sent reminder flashes success while changing
    nothing**, because of the `AND status='Pending'` guard.
    (`routes.py:920-928`)
66. **The manual reminder form asks for raw numeric IDs.** Owner ID and Pet ID
    have no lookup, no autocomplete and no existence check, and a validation
    failure discards everything you typed. (`routes.py:894-917`,
    `reminder_admin.html:78-97`)
67. **A manual reminder is sent verbatim.** No placeholder is ever substituted
    on that path, yet the form's own placeholder text suggests `{name}` — which
    nothing in the platform recognises even in the job.
    (`reminder_admin.html:105`)
68. **The Reminder Admin's "upcoming (next 7 days)" is not bounded to 7 days.**
    The query returns the first 50 pending reminders from now onwards, however
    far ahead. (`routes.py:827-838`)
69. **The Overdue and Upcoming lists are capped at 50 rows each, and Pending
    Reminders has no cap at all** — a large backlog renders as one enormous
    page. (`routes.py:837, 850`, `:614-629`)
70. **The three Scheduler queue-overview counts do not match what the job would
    send.** The vaccine card has no 7-day lower bound, the invoice card has no
    3-day overdue filter, and neither excludes entities already reminded today.
    (`routes.py:1047-1066` versus `scheduler.py:256-267, 297-307`)
71. **Cancelled reminders are counted nowhere.** The Reminder Admin's three
    cards cover Pending, Sent and Failed only. (`routes.py:809-817`)
72. **Nothing ever sets a reminder to `Failed`.** The schema documents the
    status and no code path writes it, so the red Failed counter can only be
    non-zero from imported or seeded data. (`database.py:1849`)
73. **`reminders.retry_count`, `api_response`, `appointment_id`, `channel` and
    `created_by` are stored by the schema and written or displayed by nothing on
    any WhatsApp screen.** (`database.py:1840-1856`)
74. **`create_reminder()`, `list_reminders()` and `list_wa_templates()` in the
    database layer have no callers.** (`database.py:4076-4102`)
75. **An unknown placeholder in a Settings message silently reverts that whole
    reminder type to its built-in English wording** for that run, with only a
    log line to say so. A clinic working in Arabic would see its clients
    receive English. (`scheduler.py:193-208`)
76. **Reminder amounts carry no currency symbol.** `{amount}` and `{total}` are
    formatted to two decimals only; if you want `EGP` or `جنيه` you must type it
    into the message yourself. (`scheduler.py:325-328`)

### Settings

77. **A Wapilot credential cannot be cleared.** Blank values are skipped on
    save, so a token or instance ID can only ever be replaced.
    (`routes.py:721-731`)
78. **The saved token is rendered into the page source.** The input is
    `type="password"`, which hides it visually, but the real value sits in the
    HTML `value` attribute. (`wa_settings.html:26-29`)
79. **Test Connection tests the saved credentials, not what is on screen.** It
    calls the status endpoint without submitting the form first, so a freshly
    pasted token reports on the old one. (`wa_settings.html:81-99`)
80. **Every label and description in the Settings form is English-only**,
    because they are Python strings in the route rather than `t()` calls —
    `API Token`, `Instance ID`, `Appointment Reminders`, `Vaccine Due
    Reminders`, `Invoice Overdue Alerts`, `Appointment Message`, `Vaccine
    Message`, `Invoice Message` and all four descriptions.
    (`routes.py:700-717`)
81. **The variables list on Settings does not match what each message accepts.**
    It advertises the same seven placeholders for all three messages; the
    appointment message cannot use `{vaccine}`, `{invoice}` or `{amount}`, the
    vaccine message cannot use `{time}`, `{invoice}` or `{amount}`, and the
    invoice message cannot use `{pet}`, `{time}` or `{vaccine}`. An unusable
    placeholder silently reverts that message to English (see #75).
    (`wa_settings.html:45-46` versus `scheduler.py:238-241, 280-282, 325-328`)
82. **The screen's checkbox test and the job's are not the same.** The checkbox
    renders ticked only for the exact string `"1"`, while the job treats
    anything that is not `0`, `false`, `no` or `off` as ON — so a value like
    `yes` shows as switched off and behaves as switched on.
    (`wa_settings.html:54` versus `scheduler.py:188-190`)

### Notifications

83. **The Notifications screen is almost entirely English-only.** The subtitle,
    `Mark All Read`, the `New` badge, the `Read` button, `View →`, `All caught
    up!` and `No notifications to show.` are all hard-coded English. Only the
    page title and browser title use `t()`. (`notifications/index.html:4-54`)
84. **The list is capped at 50 rows with no pagination and no filters** — no way
    to see older notifications, filter by module or search.
    (`notifications/routes.py:12`)
85. **`Mark All Read` marks everything, including rows you cannot see**, with no
    confirmation and no undo. (`notifications/routes.py:27-31`)
86. **Timestamps are printed raw.** `created_at` renders in full, unformatted and
    unlocalised. (`notifications/index.html:28`)
87. **Notifications cannot be deleted, snoozed or archived** from any screen, and
    nothing prunes the table.
88. **`module`, `entity_type`, `entity_id` and `recipient_role` are stored and
    displayed nowhere.** (`database.py:2127-2140`)
89. **`mark-read` always returns `{"ok": true}`**, whether or not a row was
    updated. (`notifications/routes.py:20-24`)
90. **The bell badge only updates on navigation.** It is rendered server-side by
    the context processor, and the `/notifications/api/unread` endpoint built to
    refresh it live has no caller. (`app.py:400-404`;
    `notifications/routes.py:34-40`)
91. **The unread count runs a `COUNT(*)` on every single page render** for every
    signed-in user. (`app.py:400-404`)
92. **The launcher card for Notifications lists nine roles**, but the module has
    no gate at all, so every role can open it — the list has no effect.
    (`launcher/routes.py:424`)

### Bilingual coverage

93. **Every JavaScript-produced string in the module is English-only** — all
    toasts (`start triggered`, `Queue settings saved`, `Message retried`,
    `Retry-all triggered`, `Campaign scheduled`, `Delay updated`, `<n> deleted`,
    `<n> contacts added`, `Scheduled`, `Unscheduled`, `Marked as finished`,
    `Error: …`), the Send Center's `Phone and message required` and `Phone and
    file required`, the AI modal's two `alert()` texts, and every `confirm()`
    dialog in the module.
94. **Table headers rendered by JavaScript are English-only** — the API Messages
    tab (`ID`, `Phone`, `Text`, `Status`) and the campaign message tables after
    a Refresh (`Phone`, `Message`, `Status`), while the server-rendered first
    view of the same table is bilingual.
    (`control_center.html:409`, `campaign_detail.html:316-319`)
95. **Section headings on Reminder Admin are English-only** —
    `🔴 Overdue Reminders (N)` and `📅 Upcoming Reminders (N)`.
    (`reminder_admin.html:114, 149`)
96. **The template form's page title, its Save button label and its six Scenario
    options are English-only.** (`template_form.html:2-3, 28-30, 89`)
97. **The Templates list count line is English-only** (`N template(s)
    available` / `N template(s) shown`), as are the campaign detail's
    `All Messages (N)` tab and its `N% delivered` caption.
    (`templates_list.html:145, 258`, `campaign_detail.html:70, 105`)
98. **The Control Center instance heading is English-only** —
    `📱 Instance — <id>`. (`control_center.html:121`)
99. **The New Campaign form's explanatory paragraph and its amber note are
    English-only.** (`campaign_form.html:23-24, 32-34`)
100. **The Pending Reminders count line and the empty-state strings on the
     Scheduler and Reminder Admin run logs are English-only.**
     (`reminders.html:53`, `scheduler.html:133`, `reminder_admin.html:208`)
101. **The Send Center phone placeholder is English-only.**
     (`send_center.html:63`)

---

*Verified against the source on 2026-08-19. Every screen section above ends with
the file and line range it was written from; if a screen disagrees with this
text, the code is the authority and this file is stale.*
