# System — Settings, Roles & Permissions, Users, Backup, Branches, Multi-Clinic
# النظام — الإعدادات والأدوار والصلاحيات والمستخدمين والنسخ الاحتياطي والفروع والعيادات المتعددة

> **How this chapter was written.** Every screen, button, field, flash message and
> refusal below was read out of the source. Nothing here is aspirational. Where the
> product is missing something, or does something different from what the screen
> implies, it is written down in **Known limits and bugs** at the end — not glossed
> over in the steps. Every screen is listed with its `file:line` in section 1, and every
> claim in **Known limits and bugs** carries its own `file:line`, so the next writer can
> check any of it in under a minute.
>
> **Bilingual.** Labels are given in both languages exactly as the template renders
> them, e.g. `💾 Back Up Now / 💾 انسخ احتياطياً الآن`. Interface language comes
> from `t(en, ar)` in `app.py:405-407`; Arabic flips the page to RTL.
>
> **Flash messages are quoted verbatim** in `"quotes"`. If the screen says something
> different from what is quoted here, the code changed and this chapter is stale.

---

## 0. The cast, for the examples

| Person | Username | Role | Why they appear |
|---|---|---|---|
| Dr Ahmed Hassan / د. أحمد حسن | `dr.ahmed` | `clinic_owner` | Owns Nile Vet Clinic, Zamalek, Cairo. Does the settings, roles, backups. |
| Mona Farid / منى فريد | `mona` | `reception` | Front desk. Shares one PC with everyone else. |
| Dr Youssef Adel / د. يوسف عادل | `dr.youssef` | `doctor` | New vet hired in the examples. |
| Salma Nabil / سلمى نبيل | `salma` | `hr` | Creates the staff logins. |
| Karim (IT) | `support` | `support_admin` | The outside IT contractor. Can see the system pages, cannot touch settings or restore. |

Clinic: **Nile Vet Clinic / عيادة النيل البيطرية**, currency **EGP**, timezone
**Africa/Cairo**, licence `VET-EG-04412`, Instapay `nilevet@instapay`.

---

## 1. Map of the area

Everything in this chapter lives under three URL prefixes: `/system` (`blueprints/system/__init__.py:2`),
`/auth` (`blueprints/auth/__init__.py:3`) and `/hr` for the user accounts themselves.

| Route | Screen name | Who can open it | Source |
|---|---|---|---|
| `GET /system/` | no page — redirects to `/system/monitor` | any logged-in user with the `system` grant | `blueprints/system/routes.py:70-73` |
| `GET /system/monitor` | System Monitor / مراقبة النظام | super_admin, clinic_owner, support_admin | `templates/system/monitor.html`; route `blueprints/system/routes.py:76-216` |
| `GET /system/audit` | Audit Log / سجل التدقيق | super_admin, clinic_owner, support_admin (auditor is declared but blocked — see Limit 1) | `templates/system/audit_log.html`; route `blueprints/system/routes.py:234-318` |
| `GET+POST /system/settings` | Clinic Settings / إعدادات العيادة | super_admin, clinic_owner | `templates/system/settings.html`; route `blueprints/system/routes.py:325-413` |
| `GET /system/backup` | Backup & Restore / النسخ الاحتياطي والاستعادة | super_admin, clinic_owner, support_admin | `templates/system/backup.html`; route `blueprints/system/routes.py:453-471` |
| `POST /system/backup/run` | "Back Up Now" | super_admin, clinic_owner, support_admin | `blueprints/system/routes.py:474-492` |
| `POST /system/backup/<file>/verify` | "✓ Check" | super_admin, clinic_owner, support_admin | `blueprints/system/routes.py:495-506` |
| `GET /system/backup/<file>/download` | "⬇ Download" | super_admin, clinic_owner | `blueprints/system/routes.py:509-517` |
| `POST /system/backup/upload` | "Upload backup file" | super_admin, clinic_owner | `blueprints/system/routes.py:520-536` |
| `POST /system/backup/<file>/restore` | "↺ Restore" | super_admin, clinic_owner | `blueprints/system/routes.py:539-565` |
| `POST /system/backup/maintenance/off` | "Clear maintenance mode" | super_admin, clinic_owner | `blueprints/system/routes.py:568-575` |
| `GET /system/diagnostics` | System Diagnostics / تشخيص النظام | super_admin, clinic_owner, support_admin | `templates/system/diagnostics.html`; route `blueprints/system/routes.py:576-653` |
| `GET /system/sync` | Sync Dashboard / لوحة المزامنة | super_admin, clinic_owner, support_admin | `templates/system/sync.html`; route `blueprints/system/routes.py:661-731` |
| `POST /system/sync/conflicts/<id>/resolve` | Keep Local / Keep Server | super_admin, clinic_owner, support_admin | `blueprints/system/routes.py:734-771` |
| `GET /system/roles` | Roles & Permissions / الأدوار والصلاحيات | super_admin, clinic_owner, support_admin | `templates/system/roles.html`; route `blueprints/system/routes.py:799-818` |
| `GET /system/roles/users` | JSON feed for the Staff Access tab | super_admin, clinic_owner, support_admin | `blueprints/system/routes.py:821-830` |
| `POST /system/roles/create` | "+ New Custom Role" | super_admin, clinic_owner | `blueprints/system/routes.py:833-853` |
| `POST /system/roles/<id>/edit` | "Edit Role" | super_admin, clinic_owner | `blueprints/system/routes.py:856-899` |
| `POST /system/roles/<id>/delete` | "Delete" | super_admin only | `blueprints/system/routes.py:902-914` |
| `POST /system/roles/assign` | Staff Access → "Save" | super_admin, clinic_owner, support_admin | `blueprints/system/routes.py:917-969` |
| `GET /system/export/all` | "Export All Data / تصدير كل البيانات" | super_admin, clinic_owner | `blueprints/system/routes.py:1010-1065` |
| `GET+POST /auth/login` | Sign in | public | `templates/login.html`; route `blueprints/auth/routes.py:533-613` |
| `GET+POST /auth/2fa` | Two-Step Verification / التحقق بخطوتين | public, only with a live pending half-login | `templates/auth/two_factor.html`; route `blueprints/auth/routes.py:616-683` |
| `GET /auth/logout` | Logout | any logged-in user | `blueprints/auth/routes.py:686-698` |
| `GET+POST /auth/profile` | My Profile / ملفي الشخصي | any logged-in user | `templates/profile.html`; route `blueprints/auth/routes.py:701-807` |
| `GET /auth/2fa/admin` | Staff Two-Step Verification | super_admin, clinic_owner | `templates/auth/2fa_admin.html`; route `blueprints/auth/routes.py:827-830` |
| `POST /auth/2fa/admin/reset/<id>` | "Reset" | super_admin, clinic_owner | `blueprints/auth/routes.py:833-853` |
| `GET+POST /auth/desk/add` | Add a user to this PC / إضافة مستخدم لهذا الجهاز | any logged-in user | `templates/auth/desk_add.html`; route `blueprints/auth/routes.py:899-967` |
| `POST /auth/desk/switch/<id>` | avatar menu → a colleague's name | any logged-in user | `templates/base.html:452-477`; route `blueprints/auth/routes.py:970-1006` |
| `POST /auth/desk/remove/<id>` | "Sign off / تسجيل خروج" | any logged-in user | `blueprints/auth/routes.py:1009-1040` |
| `GET /hr/staff` | Staff List — where user accounts live | super_admin, clinic_owner, branch_manager, support_admin, hr | `templates/hr/staff_list.html`; route `blueprints/hr/routes.py:459-491` |
| `GET+POST /hr/staff/new` | New Staff Member / موظف جديد | same five roles | `templates/hr/staff_form.html`; route `blueprints/hr/routes.py:581-641` |
| `GET+POST /hr/staff/<id>/edit` | Edit Staff Member | same five roles | `blueprints/hr/routes.py:802-846` |
| `POST /hr/staff/<id>/reset-password` | Reset Password | super_admin, clinic_owner, support_admin | `blueprints/hr/routes.py:852-878` |
| `GET /hr/roles` | second, read-only roles list | super_admin, clinic_owner, branch_manager, support_admin | `templates/hr/roles_list.html`; route `blueprints/hr/routes.py:934-946` |

**Sidebar.** The `SYSTEM / النظام` group is rendered only for `super_admin`,
`clinic_owner`, `support_admin` and contains six links: Settings, System Monitor,
Roles & Permissions, Backup Manager, Audit Log, Data Migration
(`templates/base.html:288-322`). Diagnostics and the Sync Dashboard are **not** in the
sidebar — reach them from the Monitor top bar.

### The two gates every one of these pages passes

1. **Module grant.** `login_required` calls `_permission_denied()`, which maps the
   blueprint name to a permission key (`system` → `system`) and checks the role's
   `permissions_json`. Fail = flash `"You don't have permission to access this page."`
   and redirect to the launcher. `super_admin` skips the check entirely.
   Source: `blueprints/auth/routes.py:59-131`.
2. **Role list.** `@role_required(...)` then checks the named roles. A grant can only
   ever narrow, never widen. Source: `blueprints/auth/routes.py:155-190`.

Permission sets are cached for 60 seconds (`_PERM_TTL`, `blueprints/auth/routes.py:207`)
and every role write calls `clear_permission_cache()` so the change is live at once.

---

## Workflow 1 — Sign in for the day, with or without two-step

**Who:** everybody, every morning.
**When:** the first request to any page. `login_required` bounces them to
`/auth/login?next=/the/page/they/wanted`.
**Why:** `session["user"]` is set in exactly one function, `_establish_session`
(`blueprints/auth/routes.py:496-530`), so gating that one assignment gates all 400-odd routes.

**Preconditions**
- A `users` row with `is_active = 1`. `verify_credentials` filters on it
  (`models/database.py:2829-2845`), so a deactivated account fails exactly like a wrong
  password — no separate message.
- On a multi-clinic deployment, the subdomain must resolve to a registered, active
  clinic (see Workflow 17).

### Happy path — no two-step

1. Mona opens `https://nilevet.aleefy.online/`. She is not signed in, so she gets
   the flash `"Please log in to continue."` and lands on **Sign in**.
2. The page is split: marketing hero on one side, sign-in card on the other. Top right
   there is an **EN / عربي** switch (posts to `/settings/lang`) and a light/dark toggle.
   Source: `templates/login.html:710-726`.
3. She types **Username / اسم المستخدم** = `mona` and **Password / كلمة المرور**.
   The eye button 👁️ toggles the password visible.
4. She presses **Sign In / تسجيل الدخول**.
5. The server checks the rate limit, then `verify_credentials`, then
   `sec.totp_required(user.id)`. No 2FA → `_establish_session` runs:
   - `users.last_login_at` is stamped;
   - `session["user"]` is filled with the row **minus** `password_hash`, `password`,
     `pin`, `totp_secret`, `last_totp_counter` (`_SESSION_STRIP`, `blueprints/auth/routes.py:481-483`);
   - `session["tenant"]` records which clinic this cookie is for;
   - an `audit_log` row `action='login'`, `module='auth'`, `details='login via password'`
     is written with her IP and user agent.
6. She is redirected to whatever `?next=` asked for — passed through
   `safe_redirect_target()` first — or to the module launcher.

### Happy path — with two-step

5a. `sec.totp_required` returns True. **No session is created.** A pending half-login is
    parked in `session["_pending_2fa"]` with `expires_at = now + 300 s`
    (`PENDING_2FA_TTL`, `blueprints/auth/routes.py:477`), an audit row
    `action='2fa_challenge'`, `details='password accepted, awaiting TOTP code'` is written,
    and she is sent to `/auth/2fa`.
5b. **Two-Step Verification / التحقق بخطوتين** is a standalone page — no sidebar, no
    user menu, because she is not logged in yet. One field,
    **Authentication code / رمز المصادقة**, `maxlength=13`.
5c. She types the 6-digit code from Google Authenticator and presses **Verify / التحقق**.
5d. The code is checked as TOTP first; if that fails it is checked as a backup code.
    On success the user row is **re-read from the database** — the account may have been
    deactivated in the last five minutes — and only then is the session established, with
    `details='login via TOTP'`.

### Alternative scenarios

| Situation | What actually happens |
|---|---|
| **Arabic interface** | The EN/عربي switch posts to `/settings/lang` (`blueprints/settings/routes.py:149-160`) and sets `session["lang"]`. It affects the login page immediately. **After sign-in it can be lost** — see Limit 12. |
| **Backup code instead of TOTP** | Accepted in the same box. Extra flash: `"Signed in with a backup code — 7 left. Generate new codes from your profile."` (warning). Codes are one-use; 10 are issued (`BACKUP_CODE_COUNT`, `models/security.py:393`). |
| **Deep link** | `/system/backup` when signed out → `?next=/system/backup` → after sign-in she lands there, not on the launcher. |
| **Already signed in** | `GET /auth/login` redirects straight to the launcher (`blueprints/auth/routes.py:535-536`). |
| **Session idle > 1 hour** | `SESSION_TIMEOUT = 3600` (`models/security.py:40`). The session is cleared and flashed `"Your session has expired. Please log in again."` (`app.py:342-347`). |
| **Cookie from another clinic** | `app.py:327-340` clears it and flashes `"Please sign in to this clinic."` |

### Errors and refusals — exact text

| Trigger | Message |
|---|---|
| Wrong password | `"Invalid username or password."` |
| 5 failures inside 15 min, by IP **or** by username | `"Too many failed attempts. Account locked for 15 minutes."` (`RATE_LIMIT_MAX = 5`, `RATE_LIMIT_WINDOW = 900`, `models/security.py:38-40`) |
| Trying again while locked | `"Too many failed attempts. Try again in 12 minute(s)."` |
| 2FA enrolled but `pyotp` missing on the server | `"Two-factor authentication is required for this account but is not available on this server. Contact your administrator."` — the login is **refused**, never downgraded to password-only. Audit row `login_blocked_2fa_unavailable`. Operator escape hatch `TOTP_FAIL_OPEN=1` is named in the server log only (`models/security.py:563-591`). |
| Took longer than 5 minutes on the 2FA page | `"Your sign-in request expired. Please log in again."` |
| Wrong code | `"Invalid authentication code."` |
| 5 wrong codes | `"Too many incorrect codes. Locked for 15 minutes."` — the 2FA step has its **own** rate-limit key `2fa:<username>`, separate from the password step |
| Account deactivated between the password step and the code | `"That account is no longer active."` |
| Logout | `"You have been logged out."` |

**Failed logins are audited too:** `action='login_failed'`,
`details="Failed login for 'mona' from 197.x.x.x"`.

### What is written

- `users.last_login_at`
- `login_attempts` (one row per failure; swept hourly by the `rl_cleanup` job)
- `audit_log`: `login`, `login_failed`, `2fa_challenge`, `2fa_failed`,
  `login_blocked_2fa_unavailable`, `logout`
- session cookie: `user`, `tenant`, `theme`, `lang`

### Screens that change afterwards

`/system/audit` filtered to module `auth` shows the login; `/hr/staff/<id>` shows the new
last-login; the top-bar avatar shows her name.

```mermaid
flowchart TD
  A["Any page, not signed in"] --> B["/auth/login?next=..."]
  B --> C{"Rate limited?"}
  C -->|Yes| D["Too many failed attempts. Try again in N minute(s)."]
  C -->|No| E{"verify_credentials"}
  E -->|Fail| F["Invalid username or password. + audit login_failed"]
  F --> B
  E -->|OK| G{"totp_required?"}
  G -->|pyotp missing| H["Refused: 2FA required but unavailable"]
  G -->|No| I["_establish_session + audit login"]
  G -->|Yes| J["pending half-login, 300s"]
  J --> K["/auth/2fa"]
  K --> L{"TOTP or backup code"}
  L -->|Bad| M["Invalid authentication code."]
  M --> K
  L -->|Good| N["Re-read user row from DB"]
  N -->|Row gone| O["That account is no longer active."]
  N -->|Row live| I
  I --> P["safe_redirect_target(next) or launcher"]
```

---

## Workflow 2 — Run a shared reception PC with up to five people signed in

**Who:** everyone who touches the one machine at the front desk.
**Why it exists, in the code's own words:** logging out and back in is slow enough that
nobody does it, so everyone works under whichever account is open, and every
"recorded by", every audit row and every per-vet report names the wrong person
(`blueprints/auth/routes.py:855-880`).

**The trade, stated plainly:** anyone physically at that PC can act as any of the up-to-five
signed-in accounts **with no password**. That is the feature. What actually mitigates it:
adding somebody needs their real password, 2FA accounts are refused, role and `is_active`
are re-read from the database on every switch, and every add/switch/sign-off is audited.

**Preconditions:** one person already signed in; up to four more accounts, each with
`is_active=1` and **no 2FA enrolled**.

### Happy path — adding Dr Youssef to Mona's PC

1. Mona is signed in. She opens the **avatar menu** in the top bar (her initials, top
   right) and clicks **Add a user to this PC / إضافة مستخدم لهذا الجهاز (1/5)**.
   Source: `templates/base.html:466-471`.
2. The page lists who is already on this PC with their role badge; whoever is active is
   marked `— using this screen now / يستخدم الشاشة الآن`, and each has a
   **Sign off / تسجيل خروج** button.
3. Dr Youssef types his own **Username** and **Password** — the hint under the field says
   `"Their own password — this signs them in, it does not switch to them."`
4. He presses **Sign in on this PC / تسجيل الدخول على هذا الجهاز**.
5. Full authentication runs: same rate limit, same `verify_credentials`, same lockout as
   `/auth/login`.
6. On success: Mona is put on the desk too (so the switcher always lists everyone),
   Dr Youssef is put on the desk first, and **the active user does not change** —
   `session["user"] = current or added` (`blueprints/auth/routes.py:955-958`). Mona is
   still driving.
7. Flash: `"Dr Youssef Adel is now signed in on this PC."` Redirect to the launcher.
   Audit row `desk_add`, `details="added to the shared desk by mona"`.

### Happy path — switching

1. Anyone at the PC opens the avatar menu. Below Profile and Settings there is a divider,
   then one submit button per other person on the desk showing their initials, name and
   role. Source: `templates/base.html:452-465`.
2. Click it. `POST /auth/desk/switch/<user_id>` — **no password**.
3. The row is re-read from the database. `session["user"]` becomes the fresh copy, the
   session-idle clock is reset, and an audit row `desk_switch`,
   `details="took over a shared PC from mona"` is written.
4. Back on the launcher, now as Dr Youssef. Everything he does from here is recorded
   under him.

### Happy path — signing off

- **Sign off / تسجيل خروج** on `/auth/desk/add` posts `POST /auth/desk/remove/<id>`.
- Signing off somebody who is **not** active: they leave the desk, flash `"Signed off this PC."`
- Signing off the **active** user: the next person on the desk takes over automatically.
- Signing off the **last** person: `session.clear()`, flash `"Signed out."`, redirect to login.
  A session with no user is never allowed to exist.

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| Sixth person | The form is replaced by `"This PC is full. Sign someone off to add another person."` The server refuses independently: `"This PC already has 5 people signed in. Sign one off first."` (`MAX_DESK_USERS = 5`) |
| The account has 2FA | `"This account uses two-factor authentication, so it cannot be added to a shared PC. Sign in to it directly instead."` — enrolling in 2FA takes you off the shared desk permanently |
| The account was deactivated since it joined | On the next switch: `"That account is no longer active. It has been removed from this PC."` and it is dropped from the desk |
| Switching to somebody not on this PC (crafted URL) | `"That user is not signed in on this PC."` |
| Wrong password when adding | `"Invalid username or password."` + audit row `desk_add_failed` |
| Locked out | `"Too many failed attempts. Try again in N minute(s)."` |

### What is written

`users.last_login_at` for the added person; `session["desk"]` (cookie only — the desk does
not survive a browser profile change); `audit_log`: `desk_add`, `desk_add_failed`,
`desk_switch`, `desk_remove`.

```mermaid
flowchart TD
  A["Mona signed in"] --> B["Avatar menu → Add a user to this PC"]
  B --> C{"Desk already 5?"}
  C -->|Yes| D["This PC is full. Sign someone off."]
  C -->|No| E["Username + own password"]
  E --> F{"Credentials OK?"}
  F -->|No| G["Invalid username or password. + audit desk_add_failed"]
  F -->|Yes| H{"2FA enrolled?"}
  H -->|Yes| I["Refused: cannot join a shared PC"]
  H -->|No| J["Both on desk, ACTIVE user unchanged, audit desk_add"]
  J --> K["Avatar menu lists colleagues"]
  K --> L["POST /auth/desk/switch/id — no password"]
  L --> M{"Row still active?"}
  M -->|No| N["Removed from this PC"]
  M -->|Yes| O["session.user = fresh row, audit desk_switch"]
  O --> P["Sign off → next person takes over, or full logout"]
```

---

## Workflow 3 — Enrol or reset two-step verification

**Who:** any staff member, for themselves (self-service); an owner or super admin, for
somebody who lost their phone (admin path).

### Happy path — enrolling (self-service)

1. Avatar menu → **Profile / حسابي**, i.e. `/auth/profile`.
2. Scroll to the card **🔐 Two-Step Verification / التحقق بخطوتين**. It reads
   `"Off. Your password alone signs you in."`
3. Press **Set Up Two-Step Verification / إعداد التحقق بخطوتين**.
   A **new secret is generated on every press**, so an abandoned half-enrolment can never
   be resumed by somebody else (`blueprints/auth/routes.py:735-741`).
4. The card now shows three numbered instructions, a **QR image**, and the field
   **Or type this key in manually / أو أدخل هذا المفتاح يدوياً** (click to select).
5. Scan with Google Authenticator / Microsoft Authenticator / Authy.
6. Type the 6 digits into **Code from your app / الرمز من التطبيق** and press
   **Turn On Two-Step Verification / تفعيل التحقق بخطوتين**.
7. The page re-renders — deliberately **not** a redirect — showing
   **⚠️ Save these backup codes now / احفظ رموز الاحتياط هذه الآن**: ten codes in a
   two-column monospace grid. *"They will not be shown again — print them or keep them
   somewhere safe and private."* This is the only moment they exist in plaintext
   (`blueprints/auth/routes.py:753-763`). Audit row `2fa_enabled`.

### Happy path — resetting somebody else's 2FA

1. Dr Ahmed opens **Profile** → **Quick Links** card → **🔐 Staff Two-Step Verification /
   التحقق بخطوتين للموظفين** (the link only renders for `super_admin` and `clinic_owner`,
   `templates/profile.html:179-181`).
2. `/auth/2fa/admin` lists every **active** user: User, Role, Two-Step (`✅ On / مفعّل`
   or `— Off / غير مفعّل`), Enabled On, and a **Reset / إعادة الضبط** button on the
   enrolled rows only.
3. Press Reset. A browser confirm asks
   *"Turn off two-step verification for this user? / هل تريد إيقاف التحقق بخطوتين لهذا المستخدم؟"*
4. Confirm. 2FA is switched **OFF**: secret destroyed, `totp_enabled=0`,
   `totp_confirmed_at=NULL`, every backup code deleted (`models/security.py:711-721`).
5. Flash: `"Two-factor authentication reset for dr.youssef. They can log in with their
   password and enrol again."` Audit row `2fa_admin_reset`,
   `details="dr.ahmed reset two-factor authentication for 'dr.youssef' (id=7)"`.

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **Running low on backup codes** | Profile → type your **current password** → **Generate New Backup Codes / إنشاء رموز احتياط جديدة**. A fresh ten are rendered once. Audit `2fa_backup_codes_regenerated`. The old ones stop working. |
| **Turning 2FA off yourself** | Same card, same password box, **Turn Off / الإيقاف**. Flash `"Two-factor authentication is now off."` Audit `2fa_disabled`. |
| **Server has no `pyotp`** | The card reads `"Not available on this server yet. Ask your administrator."`; pressing Set Up flashes `"Two-factor authentication is unavailable on this server. Ask your administrator to install it."` |
| **The person is on a shared desk** | Enrolling makes the account ineligible for `/auth/desk/add` from that moment. It stays on any desk it already joined until signed off. |

### Errors and refusals

| Trigger | Message |
|---|---|
| Wrong confirmation code during enrolment | `"That code was not accepted. Check your phone's clock is correct and try the current code."` — you stay on the setup screen with the same secret |
| Wrong password on regenerate / disable | `"Current password is incorrect."` |
| Reset pressed for an id that is not an active user | `"No such active user."` |

### What is written

`users.totp_secret` (encrypted at rest with a key derived from `SECRET_KEY`),
`users.totp_enabled`, `users.totp_confirmed_at`, `users.last_totp_counter`;
`totp_backup_codes` (bcrypt-hashed, cost 10); `audit_log`: `2fa_enabled`, `2fa_disabled`,
`2fa_backup_codes_regenerated`, `2fa_admin_reset`, `2fa_failed`.

### Residual risk, documented in the source

One compromised owner account can strip 2FA from every other account
(`blueprints/auth/routes.py:812-825`). The audit trail is the only detection control;
there is no two-person approval. Owner and super-admin accounts are therefore the ones
that most need to enrol first.

```mermaid
flowchart TD
  A["/auth/profile"] --> B{"2FA state"}
  B -->|Off| C["Set Up → NEW secret every press"]
  C --> D["QR + manual key + 6-digit field"]
  D --> E{"Code correct?"}
  E -->|No| F["That code was not accepted..."]
  F --> D
  E -->|Yes| G["10 backup codes rendered ONCE, audit 2fa_enabled"]
  B -->|On| H["Status + codes remaining"]
  H --> I["Password → Generate New Backup Codes"]
  H --> J["Password → Turn Off"]
  B -->|pyotp missing| K["Not available on this server yet."]
  L["Owner: Profile → Quick Links"] --> M["/auth/2fa/admin"]
  M --> N["Reset on an enrolled row + confirm()"]
  N --> O["2FA OFF, secret and codes destroyed, audit 2fa_admin_reset"]
```

---

## Workflow 4 — Create a login for a new staff member and give it the right access

**Who:** `super_admin`, `clinic_owner`, `branch_manager`, `support_admin`, `hr`.
**Where:** **the System area has no user-creation screen.** User accounts are created in
HR. This surprises people; it is how the code is built.

**Preconditions:** you know which role the person needs, and your own role is entitled to
grant it (see the refusals below).

### Happy path

1. Salma (HR) opens **HR → Staff List** (`/hr/staff`). Filters across the top: search over
   name/username/email/job title, role, contract type, status (defaults to **active**).
   Each row shows the branch name via a LEFT JOIN on `branches`.
2. Press **New Staff** → `/hr/staff/new`. The form has five cards.
3. **Account Credentials / بيانات الحساب**
   - **Username / اسم المستخدم** \* — e.g. `dr.youssef`
   - **Password / كلمة المرور** \* — the placeholder says *"Min 6 characters"*; the server
     requires **12 characters with upper, lower, digit and a special character**. See Limit 9.
   - **Confirm Password / تأكيد كلمة المرور** \*
4. **Personal Information / البيانات الشخصية** — Full Name (English), Full Name (Arabic)
   `د. يوسف عادل`, Email, Phone `+20 10 xxxx xxxx`, Gender, Date of Birth, National ID.
5. **Emergency Contact / جهة الاتصال في الطوارئ** — name and phone.
6. **Employment Details / بيانات التوظيف** — Job Title, Contract Type
   (Full-time / Part-time / Contract / Probation / Intern), Hire Date.
7. **Role & Access Control / الدور والصلاحيات**
   - **Role / الدور** \* — a fixed list of thirteen: `super_admin, clinic_owner,
     branch_manager, doctor, nurse, reception, inventory_mgr, pharmacist, finance,
     groomer, boarding_staff, support_admin, auditor` (`blueprints/hr/routes.py:20-24`).
     **Custom roles do not appear here.**
   - **Branch / الفرع** — one option, `Main Branch`, unless somebody seeded more. See Limit 6.
   - **Work Shift / المناوبة** — hint: *"Assigning a shift here will set it from today."*
   - **Account Status / حالة الحساب** — checkbox
     **Active — user can log in / نشط — يمكن للمستخدم تسجيل الدخول**
8. Press **Create Staff Member / إنشاء موظف**.
9. Every save — create and edit alike — runs `guard_role_change` first
   (`blueprints/hr/routes.py:501-509`), then the INSERT, then the shift row if one was
   chosen, then an audit row `create`, module `hr`, `details="Created user: dr.youssef"`.
10. Flash `"Staff member 'dr.youssef' created successfully."` → back to the Staff List.

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **Account created switched off** | Untick Active. The row exists, `verify_credentials` filters it out, so the sign-in fails exactly like a wrong password. |
| **Person exists, needs a new password** | Do **not** re-create. `/hr/staff/<id>` → **Reset Password / إعادة تعيين كلمة المرور**, `super_admin`/`clinic_owner`/`support_admin` only. |
| **Person exists, needs a different role** | `/hr/staff/<id>/edit`, or the Staff Access tab on `/system/roles` (Workflow 6). Both run the same guard. |
| **They should reach a module the role does not grant** | Do not invent a role per person. Edit the role's permissions (Workflow 5) or move them onto a role that already has it. |

### Errors and refusals — exact text

| Trigger | Message |
|---|---|
| Missing username or password | `"Username and password are required."` |
| Confirmation mismatch | `"Passwords do not match."` |
| Weak password | `"Error creating user: Password must be at least 12 characters."` — and equivalently `"...at least one uppercase letter."`, `"...one lowercase letter."`, `"...one digit."`, `"...one special character."` (`models/security.py:346-366`) |
| Duplicate username | `"Error creating user: UNIQUE constraint failed: users.username"` (the raw database error is shown) |
| Role that does not exist | `"There is no role called 'wizard'."` |
| Granting above your own rank | `"Your role (hr) cannot grant super_admin."` Only a `super_admin` can mint a `super_admin` — a clinic owner cannot (`may_grant_role`, `blueprints/auth/routes.py:326-336`) |
| Changing **your own** role | `"You cannot change your own role. Ask another administrator."` |
| Deactivating **your own** account | `"You cannot deactivate your own account."` |
| Demoting or switching off the last active super admin | `"This is the last active super admin. Promote somebody else first, or nobody will be able to get back in."` |
| Reset password too weak | The strength message is flashed on `/hr/staff/<id>` and nothing is written |

**Rank table** (`ROLE_RANK`, `blueprints/auth/routes.py:294-320`):
super_admin 100 · clinic_owner 90 · support_admin 80 · branch_manager 70 · hr 60 ·
finance 60 · auditor 50 · doctor / nurse / reception / pharmacist / inventory_mgr /
groomer / boarding_staff 10. Only `super_admin, clinic_owner, support_admin,
branch_manager, hr` may grant anything at all (`ROLE_GRANTERS`).

### What is written

`users` (new row, bcrypt hash), `staff_shifts` if a shift was picked,
`audit_log` (`create` / `update` / `reset_password`, module `hr`).

### Screens that change

`/hr/staff`, `/hr/staff/<id>`, `/system/roles` (the role's user count and the Staff Access
tab), `/auth/2fa/admin` (the person appears as `— Off`), `/system/monitor` (`users` row count).

```mermaid
flowchart TD
  A["/hr/staff"] --> B["New Staff"]
  B --> C["Username, password x2, name, role, branch, shift, Active"]
  C --> D["Create Staff Member"]
  D --> E{"Username and password present?"}
  E -->|No| F["Username and password are required."]
  E -->|Yes| G{"Passwords match?"}
  G -->|No| H["Passwords do not match."]
  G -->|Yes| I{"guard_role_change"}
  I -->|Unknown role| J["There is no role called 'x'."]
  I -->|Above your rank| K["Your role (hr) cannot grant super_admin."]
  I -->|Your own role| L["You cannot change your own role."]
  I -->|Last super admin| M["This is the last active super admin..."]
  I -->|OK| N{"Password strength, 12+ chars"}
  N -->|Weak| O["Error creating user: Password must be at least 12 characters."]
  N -->|Strong| P["INSERT users + audit create"]
  P --> Q["Staff member 'x' created successfully."]
```

---

## Workflow 5 — Change what a role can see

**Who:** `super_admin` or `clinic_owner` (create and edit); `super_admin` alone (delete).
**When:** receptionists should not reach Accounting; the clinic needs a role the built-in
set does not cover.

**Preconditions:** open `/system/roles`. Understand that permissions are **per module**,
25 keys drawn from `db.ALL_PERMISSIONS` (`models/database.py:4302-4331`): Manage Patients
& Owners, Manage Appointments, Medical Visits & SOAP, Pharmacy & Dispensing, Invoicing &
Payments, Inventory & Stock, Procurement & Purchasing, Reports & Analytics, WhatsApp
Messaging, Service Catalog, Grooming, Boarding, HR & Staff, Attendance & Leave,
Accounting, AI Assistant, System Admin, Backup & Restore, Audit Log, Platform Settings,
Payroll & Salaries, Inpatient & Hospitalisation, Telemedicine, Imaging & Radiology,
Pet Shop & Retail.

### The screen

`/system/roles` has two tabs.

**Tab 1 — Roles & Permissions / الأدوار والصلاحيات.** Roles grouped under
Management / الإدارة, Clinical / السريري, Front Desk / الاستقبال,
Pharmacy & Stock / الصيدلية والمخزون, Services / الخدمات,
System & IT / النظام وتقنية المعلومات. Each row: colour dot, display name, role key,
`n users`, `n perms`, and on the built-ins a `built-in / مدمج` badge. Click a row to
expand its permission grid. Built-in rows show
*"System roles are enforced in code and cannot be modified."* and no buttons.
Below that, a **Custom Roles (n)** section with **Edit Role / تعديل الدور** and
**Delete / حذف** — **but see Limit 2: on a fresh install that heading reads
"Custom Roles (14)" and lists the built-ins again, editable.**

**Tab 2 — Staff Access / صلاحيات الموظفين.** Covered in Workflow 6.

### Happy path — a new custom role

1. Top bar → **+ New Custom Role / + دور مخصص جديد**. A modal opens.
2. **Role Key \* / مفتاح الدور** — lowercase letters, digits, underscores only
   (`pattern="[a-z0-9_]+"`), e.g. `head_nurse`.
3. **Display Name (EN) \*** = `Head Nurse`; **Display Name (AR)** = `رئيس الممرضين`;
   **Badge Color / لون الشارة** — a colour picker, default `#1a3a6b`.
4. **Permissions / الصلاحيات** — tick from the 25-box grid.
5. **Create Role / إنشاء دور**.
6. A `roles` row is written with `permissions_json` as a flat JSON array; the 60-second
   permission cache is cleared immediately; an audit row `create_role`,
   `details="Created role: head_nurse"` is written.
7. Flash `"Role 'Head Nurse' created successfully."`

**Important:** creating the role is not the end. A `clinic_owner` **cannot then assign it
to anybody** — see Limit 3. Only a `super_admin` can.

### Happy path — editing a role's permissions

1. Expand the role → **Edit Role / تعديل الدور**. The modal pre-ticks its current boxes.
   Role Key is shown greyed and disabled — keys never change.
2. Adjust ticks → **Save Changes / حفظ التغييرات**.
3. The write is wrapped in `audit.audit_row("roles", role_id, module="system",
   action="edit_role")` — this is the worked example of field-level auditing in the
   codebase (`blueprints/system/routes.py:880-884`). The audit row records the **full
   permission list before and after**, and `/system/audit` renders it in the
   **What changed / ما الذي تغيّر** column.
4. Cache cleared. Flash `"Role updated successfully."` Live on the next request.

### Happy path — deleting a role

1. `super_admin` only: the **Delete / حذف** button renders only when
   `session.user.role == 'super_admin'` (`templates/system/roles.html:176`).
2. A browser confirm asks *"Delete role Head Nurse?"*.
3. `delete_role` first checks holders. If nobody holds it, the row is deleted, cache
   cleared, audit row `delete_role`, flash `"Role deleted."`

### Errors and refusals — exact text

| Trigger | Message |
|---|---|
| Create with no key or no display name | `"Role name and display name are required."` |
| Duplicate role key | `"Error creating role: UNIQUE constraint failed: roles.name"` |
| Edit with an empty display name | `"Display name is required."` |
| **Saving a role with zero modules ticked** | `"A role must grant at least one module. To stop this role being used at all, move its staff to another role and delete it."` — refused on purpose: an empty list is read as *no data* by the loader and would silently **widen** the role back to its built-in defaults (`blueprints/system/routes.py:866-884` and `blueprints/auth/routes.py:245-266`) |
| Deleting a role somebody still holds | `"Error deleting role: 2 staff member(s) still hold this role: mona, salma. Move them to another role first."` |

### What is written

`roles.permissions_json`, `display_name`, `display_name_ar`, `color`;
`audit_log` (`create_role`, `edit_role` with a before/after diff, `delete_role`);
the in-process permission cache is emptied.

### Screens that change

Every page the role can or can no longer reach; the sidebar groups shown to those users;
`/system/roles` counts; `/hr/roles`.

```mermaid
flowchart TD
  A["/system/roles — Tab 1"] --> B["+ New Custom Role"]
  B --> C["Key, EN name, AR name, colour, 25 permission boxes"]
  C --> D{"Key and EN name present?"}
  D -->|No| E["Role name and display name are required."]
  D -->|Yes| F["INSERT roles + clear cache + audit create_role"]
  A --> G["Expand a role → Edit Role"]
  G --> H{"Display name present?"}
  H -->|No| I["Display name is required."]
  H -->|Yes| J{"At least one module ticked?"}
  J -->|No| K["A role must grant at least one module..."]
  J -->|Yes| L["audit_row before/after → update_role → clear cache"]
  L --> M["Role updated successfully."]
  A --> N["Delete — super_admin only"]
  N --> O{"Anyone still on this role?"}
  O -->|Yes| P["N staff member(s) still hold this role: ..."]
  O -->|No| Q["Role deleted."]
```

---

## Workflow 6 — Move one person onto a different role

**Who:** `super_admin`, `clinic_owner`, `support_admin` (view and assign).
**When:** a promotion, or the wrong role was picked at creation.
**Two doors, one rule.** The Staff Access tab and the HR staff form both write
`users.role`, and **both** run `guard_role_change`, so the rule cannot be dodged by using
the other screen (`blueprints/system/routes.py:942-955`).

### Happy path

1. `/system/roles` → tab **Staff Access / صلاحيات الموظفين**.
2. The tab loads lazily: the first click fires `GET /system/roles/users`, which returns
   id, username, full_name, role, is_active for up to **300** users ordered by full name.
   Until it lands you see `⏳ Loading staff list… / جارٍ تحميل قائمة الموظفين…`.
3. Filter with **Search name or username… / ابحث بالاسم أو اسم المستخدم…**, the role
   dropdown (**All roles / جميع الأدوار**), and the status dropdown
   (**Any status / Active / Inactive**). Everything is filtered in the browser; the
   counter on the right reads e.g. `18 staff members`.
4. The table shows Staff Member, Username, Current Role (badge), Status
   (`● Active` green / `● Inactive` red) and **Assign Role / تعيين دور**.
5. Pick the new role in that person's dropdown and press **Save**. 25 rows per page;
   pager at the bottom reads `1–25 of 44`.
6. The route re-checks the role exists (built-ins **plus** every row of the `roles` table),
   runs `guard_role_change`, writes `users.role`, clears the permission cache and writes an
   audit row `assign_role`, `details="Assigned role 'doctor' to user id=7"`.
7. Flash `"Role assigned successfully."`

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **Alternative door** | `/hr/staff/<id>/edit` → Role dropdown → Save Changes. Same guard, different audit row (module `hr`, `action='update'`). |
| **More than 300 staff** | The tab silently shows only the first 300 by full name. Use the HR staff form for the rest. See Limit 4. |
| **Assigning a custom role** | Refused for everyone except `super_admin`. See Limit 3. |
| **Inactive staff** | They appear and can be reassigned. Reassigning does not reactivate them — the Active flag lives on the HR form only. |

### Errors and refusals

| Trigger | Message |
|---|---|
| No user or no role in the post | `"User and role are required."` |
| A role name that exists nowhere | `"There is no role called 'staff'. Pick one that exists, or create it first."` (`staff` used to be offered in a hardcoded dropdown and matched nothing) |
| Your own row | `"You cannot change your own role. Ask another administrator."` |
| Above your rank | `"Your role (support_admin) cannot grant clinic_owner."` |
| Last super admin | `"This is the last active super admin. Promote somebody else first, or nobody will be able to get back in."` |
| Anything else | `"Error assigning role: ..."` |

### What is written

`users.role`, `users.updated_at`; `audit_log` (`assign_role`); permission cache cleared.

```mermaid
flowchart TD
  A["/system/roles → Staff Access tab"] --> B["GET /system/roles/users — LIMIT 300"]
  B --> C["Filter by name, role, status — all client-side"]
  C --> D["Pick a role → Save → POST /system/roles/assign"]
  D --> E{"Role exists in built-ins or roles table?"}
  E -->|No| F["There is no role called 'x'."]
  E -->|Yes| G{"guard_role_change"}
  G -->|Own row| H["You cannot change your own role."]
  G -->|Above rank / custom role| I["Your role (x) cannot grant y."]
  G -->|Last super admin| J["This is the last active super admin..."]
  G -->|OK| K["UPDATE users.role + clear cache + audit assign_role"]
  K --> L["Role assigned successfully."]
```

---

## Workflow 7 — Set up the clinic's identity and branding

**Who:** `super_admin`, `clinic_owner`. A `support_admin` sees the sidebar link and is
bounced — Limit 5.
**When:** first run (the clinic row ships **blank on purpose**, `models/database.py:2630-2639`,
so a new clinic never prints the vendor's name on its own invoices), a rebrand, a new
licence number, or a new Instapay account.

### Happy path

1. Sidebar **SYSTEM → Settings / الإعدادات**, i.e. `/system/settings`. Top bar also offers
   **🖥️ Monitor** and **🔬 Diagnostics**.
2. **🏥 Clinic Information / بيانات العيادة**
   - **Clinic Name (English) \*** = `Nile Vet Clinic`
   - **Clinic Name (Arabic)** = `عيادة النيل البيطرية` (RTL input)
   - **Lead Doctor / Owner** = `Dr. Ahmed Hassan`
   - **Phone Number** = `+20 2 2735 1122`
   - **Email Address**, **Website**
   - **Tagline / الشعار النصي** — *"Shown beside your clinic name in the app"*
   - **Address (English)** = `12 Brazil Street, Zamalek, Cairo`; **Address (Arabic)** = `١٢ شارع البرازيل، الزمالك، القاهرة`
   - **License Number** = `VET-EG-04412`; **Tax / VAT Number** = `123-456-789`
3. **🖼️ Clinic Logo / شعار العيادة** — a 104 px preview frame, then
   **Upload a New Logo / رفع شعار جديد** accepting PNG, JPEG, GIF or WebP up to **2 MB**.
   The hint states the storage design plainly: *"resized to 400 px and stored inside the
   database, so it is kept in every backup"* and *"The logo appears on invoices, vaccination
   certificates and payslips."* Once a logo exists a checkbox appears:
   **Remove the current logo when saving / حذف الشعار الحالي عند الحفظ**.
4. **💳 Instapay / إنستاباي**
   - **Instapay address / عنوان إنستاباي** = `nilevet@instapay`
   - **Instapay payment link / رابط الدفع** = `https://ipn.eg/S/nilevet/instapay/xxxxxx`
     — *"A client reading the invoice on their own phone cannot scan their own screen"*
   - **Upload your Instapay QR** — kept at **800 px** so it still scans
   - **Remove the current QR when saving / حذف الكود الحالي عند الحفظ**
   - The card says what the software does and does not do:
     *"The staff member still confirms the transfer arrived before recording the payment —
     the app records it, it does not receive it."*
5. **🌍 Preferences / التفضيلات** — **Currency / العملة**: EGP, USD, EUR, GBP, SAR, AED.
   **Timezone / المنطقة الزمنية**: Africa/Cairo, UTC, Asia/Riyadh, Asia/Dubai,
   Europe/London, America/New_York.
6. **🎨 Appearance / المظهر** — **Default Theme** and **Default Language**.
   **Both are write-only. Nothing in the product reads them.** See Limit 7.
7. Press **💾 Save All Settings / حفظ كل الإعدادات**.
8. Images are resolved **first**, so a rejected upload reports its own reason and never
   half-writes the text fields (`blueprints/system/routes.py:328-357`). Then the `clinic`
   row (id=1) is updated, the appearance rows are upserted into `settings`, the
   **5-minute `clinic_row` cache is invalidated** so headers, invoices and certificates
   pick the change up at once, and an audit row `update` / `clinic` /
   `"Updated clinic settings"` is written.
9. Flash `"Settings saved successfully."` → back to `/system/settings`.

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **Arabic-only clinic** | Fill the Arabic name and address. Templates use `loc(row, field)` (`app.py:409-438`), which returns the `_ar` column when the reader is in Arabic and falls back to the Latin value when it is blank. |
| **Removing the logo** | Tick the removal checkbox and save. `logo_data` is set to NULL; invoices fall back to the neutral header. |
| **Replacing the logo** | Just upload a new file — no need to remove first. |
| **Changing currency** | Only the label on invoices and financial reports changes. **No amount is converted.** |
| **First run** | Every field is empty by design. Until the name is filled, pages and PDFs use the neutral fallbacks. |

### Errors and refusals — exact text

Image rejections come from `encode_logo` (`blueprints/settings/routes.py:68-98`) and are
flashed verbatim as `danger`, with **nothing** saved:

| Trigger | Message |
|---|---|
| Empty file | `"No file received."` |
| Over 2 MB | `"Image is too large. Maximum 2 MB."` |
| Wrong bytes — magic-byte sniff, not the extension | `"That file is not a PNG, JPEG, GIF or WebP image."` |
| Pillow missing on the server | `"Image support is unavailable on this server (Pillow missing)."` |
| Truncated or corrupt image | `"That image could not be read. Try re-saving it as a PNG."` |
| Anything else during the write | `"Error saving settings: ..."` |

### What is written

`clinic` (id=1): name, name_ar, tagline, doctor_name, phone, email, address, address_ar,
website, license_number, tax_number, currency, timezone, instapay_handle, instapay_link,
`logo_data`, `instapay_qr`, updated_at. `settings`: `default_theme`, `default_language`
(category `appearance`, stamped with who saved). `audit_log`: one `update` row.

### Screens that change

Sidebar and page headers, every invoice and receipt PDF, vaccination certificates,
payslips, the payment screen's Instapay panel, the installed PWA name.

```mermaid
flowchart TD
  A["/system/settings"] --> B["Fill the four cards + Appearance"]
  B --> C["💾 Save All Settings"]
  C --> D{"Logo / QR uploads validated first"}
  D -->|Rejected| E["e.g. That file is not a PNG, JPEG, GIF or WebP image. — NOTHING saved"]
  D -->|OK or none| F["UPDATE clinic id=1"]
  F --> G["UPSERT settings default_theme + default_language"]
  G --> H["cache_invalidate('clinic_row')"]
  H --> I["audit update / clinic"]
  I --> J["Settings saved successfully."]
  J --> K["Headers, invoices, certificates, payslips pick it up at once"]
```

---

## Workflow 8 — Nightly and manual backup

**Who runs it:** nobody, most nights. APScheduler fires at **02:00** in the one process
that holds `.scheduler.lock` (`app.py:755-773`), looping every active clinic through
`tenancy.each_clinic()`. A person can also press the button.
**Why the lock:** `create_app()` runs in every gunicorn worker; without an OS-level
exclusive lock, 02:00 would fire N concurrent backups (`app.py:668-706`).

**Preconditions:** `BACKUP_DIR` configured; on PostgreSQL, `pg_dump` on the PATH.
Off-site targets are optional and are skipped cleanly when unset.

### Happy path — the manual run

1. Sidebar **SYSTEM → Backup Manager**, i.e. `/system/backup`. Top bar:
   **← Monitor / ← المراقبة** and **💾 Back Up Now / 💾 انسخ احتياطياً الآن**.
   (The same run is also reachable as **💾 Now / 💾 الآن** on the Monitor's Backup Status
   card, which asks *"Run backup now?"* first.)
2. Press **💾 Back Up Now**.
3. The module is scoped to this clinic — `with bk.for_current_clinic()` — so a
   multi-clinic deployment writes into `<backup_dir>/<slug>` and never into another
   clinic's directory.
4. **SQLite:** the copy goes through SQLite's own online backup API, never `shutil.copy2`
   — workers hold connections open and the database is in WAL mode, so a file copy would
   yield a torn database (`models/backup.py:265-289`). The result is
   `platform_backup_YYYYMMDD_HHMMSS.db`, then an integrity check; a file that fails the
   check is **deleted** and the run reported as a failure.
   **PostgreSQL:** `pg_dump --no-password -Fc -f <file> <dsn>`, producing
   `platform_backup_YYYYMMDD_HHMMSS.dump`, with a 30-minute timeout.
5. On success, retention runs — archives older than **30 days** (`RETENTION_DAYS`, `models/backup.py:45`) whose
   filenames carry an older timestamp are deleted — and the archive is pushed to every
   configured off-site target.
6. Flash `"Backup completed: platform_backup_20260819_143012.db (8420.5 KB)"` and an
   audit row `manual_backup`.
7. The page reloads with the new file at the top of **Available backups / النسخ المتاحة**
   (Date & time, File, Size MB, Type `Automatic / تلقائي`, and the action buttons), and the
   headline card now reads **0 hours ago**.

### What the page shows

- **Last successful backup / آخر نسخة احتياطية ناجحة** — a big number: `N hours ago` under
  24 h, otherwise `N days ago`, with the timestamp, filename and size beneath. Green left
  border when healthy, red when stale.
- **Copies kept / النسخ المحفوظة** — the count, with `30-day retention · daily at 02:00`.
- **Off-site copy / نسخة خارج الموقع** — the folder path and/or the S3 label. When there
  is none it says **None configured / غير مُعدّة** and explains why that matters:
  *"Backups sit on the same disk as the database. One disk failure loses both."*
- **Restore from USB / استعادة من ذاكرة USB** — see Workflow 11.
- **Available backups** — every archive, newest first.

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **Off-site folder configured** (`BACKUP_OFFSITE_DIR`) | The archive is copied there and the same 30-day purge is applied to that folder too (`models/backup.py:722-725`). |
| **S3-compatible bucket** (`BACKUP_S3_ENDPOINT/BUCKET/KEY/SECRET`, optional `REGION`, `PREFIX`) | A single signed PUT, path-style addressing, SigV4 hand-rolled over stdlib `hmac` — no new dependency. Ceiling: 5 GB per archive, single-part. |
| **Off-site fails, local succeeds** | The local backup is still a success. An extra `danger` flash names the target: `"Off-site copy to /mnt/usb FAILED: [Errno 28] No space left on device. The local backup is fine, but there is no second copy."` A manager notification goes out as well. One copy beats zero. |
| **A restore is running** | `"Backup failed: A restore is in progress — backup skipped"` |
| **Nightly run in a 20-clinic deployment** | Each clinic is backed up in its own `with bk.for_clinic(...)` block; one clinic raising does not stop the rest, and a failure notifies managers with the clinic named: title `Backup Failed — nilevet` (`app.py:756-772`). |
| **Support admin presses it** | Allowed — `/system/backup/run` includes `support_admin`. |

### Errors and refusals — exact text

| Trigger | Message |
|---|---|
| Any failure | `"Backup failed: <reason>"` plus a manager notification titled `Backup FAILED` |
| `pg_dump` missing | `"pg_dump not found on PATH — PostgreSQL backup cannot run. Install postgresql-client on the host."` — deliberately **not** reported as success |
| `pg_dump` produced nothing | `"pg_dump produced an empty file"` |
| Over 30 minutes | `"pg_dump timed out after 30 minutes"` |
| SQLite source file missing | `"source database is not there: /path/platform.db"` — checked because `sqlite3.connect()` would otherwise create an empty database that passes `integrity_check` |
| Copy came out corrupt | `"Backup failed integrity check: <reason>"`, and the bad file is removed |
| Nothing configured | `"Backup not configured"` |

### What is written

A file in `<backup_dir>[/<slug>]`; copies at each off-site target; `audit_log`
(`manual_backup`); `notifications` for managers on failure. **No status table** — the
newest readable archive on disk *is* the record, so "backup OK" can never be logged while
no file exists (`models/backup.py:21-26`).

```mermaid
flowchart TD
  A["02:00 cron in the lock-holding process"] --> B["for each active clinic"]
  A2["Person presses 💾 Back Up Now"] --> C
  B --> C{"Maintenance marker present?"}
  C -->|Yes| D["A restore is in progress — backup skipped"]
  C -->|No| E{"Engine"}
  E -->|SQLite| F["SQLite online backup API → .db"]
  E -->|PostgreSQL| G["pg_dump -Fc → .dump"]
  F --> H{"Integrity check ok?"}
  H -->|No| I["Delete the file + Backup failed integrity check"]
  H -->|Yes| J["Purge archives older than 30 days"]
  G --> J
  J --> K["Copy to every off-site target"]
  K -->|Target failed| L["Loud flash + manager alert, local backup still OK"]
  K -->|All fine| M["Backup completed: file (N KB) + audit manual_backup"]
```

---

## Workflow 9 — Notice that backups have stopped

**Who:** whoever opens `/system/backup` or `/system/monitor` — both call
`check_and_notify()` on page load — plus a daily **09:05** job.
**Why a page view is a trigger:** a scheduler that has quietly died leaves no failure to
report. Something that still runs has to ask the question (`models/backup.py:865-876`).

**How health is decided:** from the files on disk, never from a status table. Stale =
newest archive older than `BACKUP_STALE_DAYS`, default **2** (`models/backup.py:51`).

### Happy path — the alarm working

1. The scheduler dies on a Tuesday night. Nobody notices.
2. Thursday morning Dr Ahmed opens `/system/monitor` for something unrelated.
3. `check_and_notify()` runs. The newest archive is 58 hours old, so `stale = True`.
4. Managers — `super_admin`, `clinic_owner`, `branch_manager`, `hr`
   (`models/database.py:4167-4171`) — get a notification titled **"Backup is out of date"**
   with body `"Last backup is 2 day(s) old — backups have probably stopped. Open System →
   Backup and run one now."`, icon ❌, linking to `/system/backup`.
5. He clicks through. `/system/backup` shows the headline in red and a `danger` banner:
   *"⚠️ Backups appear to have stopped. Nothing newer than 2 day(s) exists. Press
   “Back Up Now”, and if it fails, call your IT support today."*
   (Arabic: *"يبدو أن النسخ الاحتياطي توقف… اضغط «انسخ احتياطياً الآن»، وإذا فشل فاتصل بالدعم الفني اليوم."*)
6. He presses **💾 Back Up Now** — Workflow 8.

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **No backup has ever run** | Headline reads **Never / أبداً** in red, and the banner is blunter: *"This server has no backup at all. If the disk fails today, every record is lost. Press “Back Up Now”."* Alert title is **"No backup exists"**. |
| **Alert already sent today** | Suppressed. At most one notification per alert **title** per 24 h (`ALERT_COOLDOWN_HOURS = 24`), tracked in `.backup_alerts.json` inside the backup directory, so a broken backup does not bury the bell. |
| **`/healthz`** | Reports `backup: stale` in the body but still returns **200** as long as the database is reachable — a stale backup must not make container health checks restart a healthy instance or make `upgrade.sh` roll back a completed migration (`app.py:576-596`). |
| **Multi-clinic** | Health is computed per clinic. Reading the deployment's own directory instead of `<backup_dir>/<slug>` is what once made `/healthz` report "stale, 60 hours" permanently while every clinic's real backup was four hours old (`models/backup.py:105-137`). |
| **Threshold too tight or too loose** | `BACKUP_STALE_DAYS` env var. |

### What is written

`notifications` (one per manager, cooled down); `.backup_alerts.json`; an ERROR line in
the server log either way, so the log stays a second channel when the notification table
is itself the casualty.

```mermaid
flowchart TD
  A["Someone opens /system/monitor or /system/backup"] --> C
  B["09:05 daily job, per clinic"] --> C["check_and_notify()"]
  C --> D["Read the newest archive ON DISK"]
  D --> E{"Exists?"}
  E -->|No| F["No backup has ever been taken on this server."]
  E -->|Yes| G{"Older than BACKUP_STALE_DAYS = 2?"}
  G -->|No| H["Last backup N hour(s) ago — green"]
  G -->|Yes| I["Last backup N day(s) old — backups have probably stopped."]
  F --> J{"Same alert title in the last 24h?"}
  I --> J
  J -->|Yes| K["Suppressed — bell not buried"]
  J -->|No| L["notify_managers + red banner + link to /system/backup"]
```

---

## Workflow 10 — Restore the database from a backup

**Who:** `super_admin`, `clinic_owner` only. A `support_admin` can see the ↺ Restore
button and will be bounced when pressing it — Limit 5.
**When:** data loss, a bad import, a rebuilt machine. **Do this out of clinic hours.**

**The order is the whole point** (`models/backup.py:561-634`):
verify → maintenance ON → snapshot the live database → restore → maintenance OFF.
Step 3 is mandatory: **if the snapshot fails, nothing is overwritten.**

**Preconditions:** the archive is in this clinic's backup directory (it was made here, or
uploaded per Workflow 11), and it came from the **same database engine** this server runs.

### Happy path

1. `/system/backup` → find the row you want by **Date & time** and **Type**.
2. Press **✓ Check / ✓ فحص** first. This verifies without restoring:
   - SQLite: size ≥ 512 bytes, magic header `SQLite format 3\0`, `PRAGMA integrity_check`,
     and at least one table.
   - PostgreSQL: `pg_restore --list` must succeed and contain `TABLE DATA`.
   Flash on success: `"platform_backup_20260817_020014.db is readable and complete."`
3. Press **↺ Restore / ↺ استعادة**. A modal opens headed
   **⚠️ Read this before you restore / اقرأ هذا قبل الاستعادة**, naming the backup's date
   and listing three consequences:
   - *"Every visit, invoice, payment and prescription entered SINCE that date will be gone."*
   - *"Staff will be locked out of the system for a few minutes."*
   - *"A safety snapshot of the CURRENT data is taken first, so this can be undone."*
4. **Type the file name to confirm / اكتب اسم الملف للتأكيد.** The filename is displayed
   in a monospace box above the input; it must be typed **exactly**. A modal a tired owner
   can click through at 22:00 is not a confirmation (`blueprints/system/routes.py:539-546`).
5. Press **Restore and lose newer data / استعادة وفقدان البيانات الأحدث**.
6. The server: re-verifies → writes the maintenance marker (a **file**, so every gunicorn
   worker sees it) → creates `pre_restore_YYYYMMDD_HHMMSS.db|.dump` → restores
   (SQLite backup API, or `pg_restore --clean --if-exists --no-owner --single-transaction`)
   → clears the marker in a `finally`.
7. Flash: `"Database restored from platform_backup_20260817_020014.db. Your previous data
   was saved as pre_restore_20260819_2201.db — restore that file to undo this."`
   Audit row `backup_restore` naming both files.
8. The safety snapshot appears in the table with the type badge
   **Safety snapshot / لقطة أمان**.

### What staff see while it runs

Any request outside `/static/`, `/auth/` and `/system/backup` gets a **503** page:
*"Maintenance in progress: Restoring platform_backup_20260817_020014.db. The system will
be back in a few minutes."* (`blueprints/system/routes.py:32-66`.) The marker is checked
when a request **starts**; a request already inside a view is not interrupted — on SQLite
that is safe anyway, because the backup API takes the write lock and stragglers wait or
fail, never corrupt.

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **Undoing a restore** | Restore the `pre_restore_...` file named in the success flash. It is an ordinary archive with its own row. |
| **PostgreSQL deployment** | Same screen. The engine is checked before anything is touched. |
| **Restoring an archive older than 30 days** | Works. Retention deliberately runs only in `run_backup()`, never inside the snapshot path — it once purged the very archive being restored, and the copy that followed put an empty database over the live one and called it success (`models/backup.py:395-406`). |
| **Two archives made in the same second** | Names are disambiguated with `_1`, `_2` so the pre-restore snapshot can never overwrite the archive being restored. |

### Errors and refusals — exact text

| Trigger | Message |
|---|---|
| Typed name does not match | `"Restore cancelled — the filename you typed did not match."` (warning) — nothing happens |
| Wrong engine | `"That backup came from a different database engine than this server runs. Restore aborted — nothing was changed."` |
| Corrupt or empty archive | `"That file is not a usable backup (file is empty or truncated). Restore aborted — nothing was changed."` Other reasons: `not a SQLite database file`, `database has no tables — nothing to restore`, `pg_restore not installed — cannot verify this dump`, `dump contains no table data` |
| Already restoring | `"Another restore is already running. Wait for it to finish."` |
| Snapshot failed | `"Could not snapshot the current database (<reason>). Restore aborted — nothing was changed."` |
| Restore itself blew up | `"Restore failed: <reason>"` plus a manager alert titled `Database restore FAILED` |
| Not configured | `"Backup is not configured on this server."` / `"Database path is not configured on this server."` |
| Crafted filename with `..`, `/`, `\`, or a wrong extension | **HTTP 400**, not a flash — refusal, never a silent rewrite (`blueprints/system/routes.py:416-437`) |
| A legitimate name for a file that is not here | **HTTP 404** |
| Verify on a bad file | `"platform_backup_x.db is NOT usable: not a SQLite database file"` |

### What is written

The live database is **replaced**; a new `pre_restore_...` archive; the maintenance marker
file (self-expiring after `MAINTENANCE_MAX_MINUTES = 15`); `audit_log` (`backup_restore`).

### Screens that change

Everything. Every module now reads the restored data. `/system/monitor` row counts jump;
`/system/audit` contains only what the archive contained, plus the `backup_restore` row.

```mermaid
flowchart TD
  A["/system/backup"] --> B["✓ Check — verify without restoring"]
  B --> C["↺ Restore → modal"]
  C --> D["Type the filename EXACTLY"]
  D --> E{"Typed name matches?"}
  E -->|No| F["Restore cancelled — the filename you typed did not match."]
  E -->|Yes| G{"Same engine? Verifies?"}
  G -->|No| H["Restore aborted — nothing was changed."]
  G -->|Yes| I{"Another restore running?"}
  I -->|Yes| J["Another restore is already running."]
  I -->|No| K["Maintenance marker ON — all staff get 503"]
  K --> L["pre_restore_ snapshot"]
  L -->|Snapshot failed| M["Restore aborted — nothing was changed."]
  L -->|Snapshot OK| N["Replace the live database"]
  N --> O["Maintenance OFF in a finally block"]
  O --> P["Restored... previous data saved as pre_restore_x — restore that file to undo"]
```

---

## Workflow 11 — Carry a backup between machines on a USB stick

**Who:** `super_admin`, `clinic_owner` (download and upload are both restricted).
**When:** moving a clinic to a new PC, or handing an archive to IT support.

### Happy path — off the old machine

1. `/system/backup` → **💾 Back Up Now** so the archive is current.
2. On its row press **⬇ Download / ⬇ تنزيل**. The file is streamed as an attachment under
   its own name. An audit row `backup_download` records who took it.
3. Copy it onto the USB stick.

### Happy path — onto the new machine

1. Open `/system/backup` on the new machine.
2. In the **Restore from USB / استعادة من ذاكرة USB** tile, use the file input
   (`accept=".db,.dump"`) and press **Upload backup file / رفع ملف النسخة**.
   The tile promises *"The file is checked before it is kept."*
3. The upload route alone raises the request size limit to **2 GB**, and does it before the
   CSRF check touches `request.form`, because that is what would otherwise trigger the
   app-wide 16 MB limit (`blueprints/system/routes.py:29-58`).
4. The file is stored under a **generated** name `uploaded_YYYYMMDD_HHMMSS.<ext>` — only
   the extension comes from the submitted filename, so a hostile name has nothing to steer.
5. It is verified **immediately**. If it is not a usable backup it is **deleted again**, so
   the owner finds out the stick is bad while it is still plugged in.
6. Flash `"Uploaded and verified: uploaded_20260819_144502.db"`. Audit row `backup_upload`.
7. The archive appears in the table with the badge **Uploaded / مرفوع** and can now be
   restored — Workflow 10.

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **Two uploads in the same second** | Named `uploaded_..._1`, `uploaded_..._2`. Deliberate: without it a second, failing upload would delete the first, good one on its way out. |
| **PostgreSQL dump** | Upload the `.dump`. It can only be restored onto a PostgreSQL server; the engine check refuses the mismatch. |
| **Uploaded archives and retention** | `uploaded_` is one of the three recognised prefixes, so uploads are purged at 30 days like everything else. |

### Errors and refusals — exact text

| Trigger | Message |
|---|---|
| Nothing chosen | `"Choose a backup file first."` (warning) |
| Wrong extension | `"Only .db (SQLite) or .dump (PostgreSQL) backup files can be uploaded."` |
| Not a real backup | `"That file is not a usable backup (not a SQLite database file). It was not kept."` |
| Backup not configured | `"Backup is not configured on this server."` |
| A `support_admin` presses Download or Upload | Bounced to the launcher with `"You don't have permission to access this page."` — Limit 5 |

### What is written

A new `uploaded_...` archive (or nothing at all, if it failed verification);
`audit_log` (`backup_download`, `backup_upload`).

```mermaid
flowchart TD
  A["Old PC — /system/backup"] --> B["💾 Back Up Now"]
  B --> C["⬇ Download + audit backup_download"]
  C --> D["USB stick"]
  D --> E["New PC — Restore from USB tile"]
  E --> F["Upload backup file — 2 GB limit on this route only"]
  F --> G["Stored as uploaded_TIMESTAMP.ext, submitted name discarded"]
  G --> H{"Verify now"}
  H -->|Bad| I["Deleted again + That file is not a usable backup. It was not kept."]
  H -->|Good| J["Uploaded and verified: uploaded_x.db + audit backup_upload"]
  J --> K["Row appears with type Uploaded / مرفوع → restore workflow"]
```

---

## Workflow 12 — Clear a stuck maintenance mode

**Who:** `super_admin`, `clinic_owner`.
**When:** a restore crashed and left the marker behind, so the whole platform is serving
503s to every member of staff.
**Escape hatch, not the only way out:** the marker self-expires after
`MAINTENANCE_MAX_MINUTES = 15` and `maintenance_active()` clears it on the next read
(`models/backup.py:234-262`). This button is for not waiting.

### Happy path

1. `/system/backup` still loads for you — the maintenance gate deliberately lets
   `/system/backup*`, `/auth/*` and `/static/*` through.
2. At the top of the page a warning banner reads
   **"The system is in maintenance mode. / النظام في وضع الصيانة."** followed by the
   reason, `started N minutes ago / بدأت منذ N دقيقة`, and
   *"Staff cannot use the platform until it clears."*
3. Press **Clear maintenance mode / إلغاء وضع الصيانة**.
4. The marker file is deleted, an audit row `maintenance_cleared` /
   `"Maintenance mode cleared manually"` is written.
5. Flash `"Maintenance mode cleared. The system is serving again."` Staff can work again
   on their next request.

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **The marker is unreadable** (truncated JSON, bad disk) | It is cleared automatically on the next read, with a warning in the log. |
| **The marker is stale** (over 15 minutes) | Cleared automatically. The banner will already be gone by the time you look. |
| **A restore really is running** | Clearing the marker does **not** stop the restore. It only reopens the doors while a database swap is in progress. Wait unless you are certain the restoring process is dead. |

### What is written

`.maintenance.json` is deleted from the backup directory; `audit_log`
(`maintenance_cleared`).

```mermaid
flowchart TD
  A["Restore crashed"] --> B[".maintenance.json left behind"]
  B --> C["Every non-/auth, non-/static, non-/system/backup request → 503 page"]
  C --> D{"Older than 15 minutes?"}
  D -->|Yes| E["Cleared automatically on the next read"]
  D -->|No| F["/system/backup still opens → banner"]
  F --> G["Clear maintenance mode"]
  G --> H["Marker deleted + audit maintenance_cleared"]
  H --> I["Maintenance mode cleared. The system is serving again."]
```

---

## Workflow 13 — Take the clinic's data out of the product

**Who:** `super_admin`, `clinic_owner`.
**When:** an owner wants proof the records are theirs, or is leaving.
**Why it exists:** every table screen has an Excel button and the nightly job writes a
database dump, and neither is what a clinic needs the day it wants to leave —
**one file, everything in it, openable without this software**
(`blueprints/system/routes.py:972-990`).

### Happy path

1. `/system/monitor` → the **💾 Backup Status / حالة النسخ الاحتياطي** card → press
   **Export All Data / تصدير كل البيانات**.
2. There is no page. The browser downloads `aleefy-data-2026-08-19.zip`.
3. Inside: **one CSV per table**, plus `README.txt`.
4. Every CSV is written as **UTF-8 with BOM**. That is not decoration: without the BOM,
   Excel on a Windows machine in Egypt opens `منى فريد` as mojibake and the clinic
   concludes its data is corrupt.
5. `README.txt` is bilingual and lists every table with its row count:
   *"One CSV per table. Open any of them in Excel, Google Sheets, or LibreOffice. These
   files need no software from us to read." / "ملف CSV لكل جدول. تقدر تفتح أي واحد منهم في
   إكسل. الملفات دي مش محتاجة أي برنامج مننا عشان تقراها."*
6. An audit row `data_export`, `details="Full data export (79 tables)"` is written.

### What is and is not in the ZIP

**Excluded** — operational noise, not the clinic's records (`_EXPORT_SKIP`,
`blueprints/system/routes.py:992-996`): `app_logs`, `backend_logs`, `frontend_logs`,
`audit_logs`, `sync_queue`, `sync_conflicts`, `rate_hits`, `user_sessions`,
`ai_conversations`, `petsy_usage`, `login_attempts`, `sqlite_sequence`, and anything
starting `sqlite_`.

**Included** — everything else, including `users` (with `password_hash`), `clinic`
(logo and Instapay QR as `data:` URIs — long base64 strings inside a CSV cell), owners,
pets, visits, invoices, payments, items, batches. Treat the ZIP as sensitive: it contains
every client's contact details and the whole medical record.

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **One table is unreadable** | It is skipped and logged; the other seventy-eight still export. One broken table must not cost the clinic everything else. |
| **PostgreSQL** | Table list comes from `information_schema` instead of `sqlite_master`. Same output. |
| **Multi-clinic** | The export is scoped by the ordinary tenant routing, so it contains this clinic's database and no other. |
| **Very large clinic** | The ZIP is built in memory and streamed. There is no chunking; a multi-gigabyte database will be slow and memory-hungry. |

### Errors

There is no flash path — this route either streams a file or raises. Access is the only
refusal: a `support_admin` who reaches the URL is bounced with
`"You don't have permission to access this page."`

### What is written

Nothing is changed in the database except one `audit_log` row (`data_export`,
entity type `backup`).

```mermaid
flowchart TD
  A["/system/monitor → Backup Status card"] --> B["Export All Data"]
  B --> C["List every table minus the operational ones"]
  C --> D["One UTF-8-BOM CSV per table"]
  D -->|Table unreadable| E["Skip it, log it, keep going"]
  D --> F["Bilingual README.txt with row counts"]
  F --> G["aleefy-data-YYYY-MM-DD.zip streams to the browser"]
  G --> H["audit data_export"]
```

---

## Workflow 14 — Investigate who changed a record

**Who:** `super_admin`, `clinic_owner`, `support_admin`. The `auditor` role is **declared
on the route and cannot actually open it** — Limit 1.
**When:** a price, a role or a clinical field is not what somebody expected; a 2FA reset
looks unexpected; a client says they were charged twice.

**Preconditions:** the change was made through the app. `audit_log` is append-only and
grows without bound; the page never selects the whole table.

### The screen

`/system/audit`, **Audit Log / سجل التدقيق**, subtitle
*"Who changed what, and when / من غيّر ماذا، ومتى"*. Top bar: **🖥️ Monitor** and
**⚙️ Settings**. **There is no export button.**

Seven filters:

| Filter | Type | Matching |
|---|---|---|
| **User / المستخدم** | dropdown of distinct usernames | exact |
| **Module / الوحدة** | dropdown of distinct modules | exact |
| **Action / الإجراء** | free text, placeholder *"e.g. update, delete"* | `LIKE %text%` |
| **Record type / نوع السجل** | dropdown of distinct entity types | exact |
| **Record ID / رقم السجل** | free text, placeholder *"e.g. 1042"* | exact |
| **From date / من تاريخ** | date picker | `timestamp >= date 00:00:00` |
| **To date / إلى تاريخ** | date picker | `timestamp <= date 23:59:59` |

Buttons **🔍 Filter / تصفية** and **✕ Clear / مسح**.

Columns: **Time**, **User**, **Action**, **Module**, **Record**, **What changed / ما الذي
تغيّر**, **IP**. 50 rows per page; the pager reads
`« First / Previous / Page 3 / 12 / Next / Last »`.

### Happy path

1. Dr Ahmed opens `/system/audit`.
2. He sets **Module** = `system` and **Action** = `edit_role`, presses **🔍 Filter**.
3. The counter above the table reads `Showing 1–4 of 4 entries`.
4. The **What changed** cell decodes the field-level diff written by
   `audit.audit_row(...)` — for a role edit it shows the permission list **before** and
   **after**, with `empty / فارغ` rendered where a side is blank
   (`models/audit.py:130-151`).
5. He clicks the **Record** cell. That is a link to the same page pre-filtered to that
   `entity_type` + `entity_id`, titled
   *"Show all changes to this record / عرض كل التغييرات على هذا السجل"* — every change ever
   made to that one row, in order.

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **Older rows** | Writers that used plain `db.log_audit()` stored an English sentence in `details`, e.g. `"Updated clinic settings"` or `"Assigned role 'doctor' to user id=7"`. `parse_details()` returns `None` for those and the cell renders the sentence as text. Field-level diffs only exist where a writer used `audit.audit_row` — **role editing is the worked example**; most other writes are sentences. |
| **Who logged in when** | Module `auth`, actions `login`, `logout`, `login_failed`, `2fa_challenge`, `2fa_failed`, `2fa_enabled`, `2fa_disabled`, `2fa_admin_reset`, `desk_add`, `desk_switch`, `desk_remove`, `desk_add_failed`. |
| **Backup and restore history** | Module `system`, entity type `backup`: `manual_backup`, `backup_download`, `backup_upload`, `backup_restore`, `maintenance_cleared`, `data_export`. |
| **A shared reception PC** | `desk_switch` rows say who took over from whom, so a disputed entry can be tied to a person even though the switch needed no password. |
| **No filters at all** | The most recent 50 rows across the whole clinic. |
| **Nothing matches** | *"No audit entries found / لا توجد إدخالات في سجل التدقيق"* with the hint *"Try widening the filters or the date range."* |

### Errors and edge cases

- `?page=0` or a negative page is normalised to page 1.
- A page beyond the end renders an empty table with the pager still showing the true
  `Page n / m`.
- **Silent audit failures.** `db.log_audit()` wraps everything in
  `try/except Exception: pass` (`models/database.py:2965-2975`). If the audit write fails
  the user action still succeeds and **nothing anywhere says a row is missing.**
- The three filter dropdowns run `SELECT DISTINCT` over the whole table on every page load
  — acknowledged in the source as the one unbounded scan left
  (`blueprints/system/routes.py:276-287`). On a clinic with a year of history this is the
  slow part of the page.

### What is read and written

Read-only. Nothing on this screen writes anything.

```mermaid
flowchart TD
  A["/system/audit"] --> B["Filters: user, module, action LIKE, record type, record id, date range"]
  B --> C["50 rows + COUNT for the pager"]
  C --> D{"details starts with a JSON object?"}
  D -->|Yes| E["What changed: field-level before/after"]
  D -->|No| F["What changed: the legacy English sentence"]
  E --> G["Click the Record cell"]
  F --> G
  G --> H["Same page re-filtered to entity_type + entity_id"]
  H --> I["Every change ever made to that one record"]
```

---

## Workflow 15 — Work out why the system feels wrong

**Who:** `super_admin`, `clinic_owner`, `support_admin`.
**When:** staff report slowness, errors, or *"it says it saved but nothing changed"*.
**Nothing here repairs anything.** It is a read-only health read that points at the next
action.

### Step 1 — the Monitor

`/system/monitor`, **System Monitor / مراقبة النظام**. It **auto-refreshes every 60
seconds** (`templates/system/monitor.html:416`).

Top bar: **⚡ Sync Dashboard**, **🔬 Diagnostics**, **📋 Audit Log**, **↻ Refresh**.

Statistic tiles: Database Size · Synced Records · Pending Sync · Sync Failures ·
Conflicts · **Errors (24h) / الأخطاء (24 ساعة)** · Active Devices · Log Files.

Cards:
- **⚡ Sync Queue** — four counters and, when there are failures or conflicts, a warning
  strip with **Resolve → / حل ←**.
- **🚀 Platform Version** — Version, Build, Release Date, Python, Flask, Platform.
- **🗄️ Database** — Size, Path, and **Records by Module**: row counts for `owners`, `pets`,
  `appointments`, `visits`, `invoices`, `items`, `users`, `reminders`, `whatsapp_log`,
  `audit_log`, `batches`, `payments`. A table that cannot be read shows `0` rather than
  breaking the page.
- **💾 Backup Status** — **All Backups**, **Export All Data**, **💾 Now**. Note that two
  fields on this card are permanently blank or `?` — Limit 8. Use `/system/backup` for the
  truth.
- **📁 Log Files** — up to ten backend log files with size, age and days to expiry
  (`LOG_FILE_RETENTION_DAYS`, default 7).
- **📱 Registered Devices** — Online (last 1h) vs Total Registered.
- **📝 Recent Server Logs** — the last 25 rows of `backend_logs` (Time, Level, Module,
  Endpoint, Status, ms, User, Error), falling back to the older `app_logs` table.
- **🔗 Legacy App Status** with a **Check Status** button.

### Step 2 — Diagnostics

`/system/diagnostics`, reached from the Monitor or Settings top bar — **not in the
sidebar**. Eight checks run live on every page load
(`blueprints/system/routes.py:576-653`):

| # | Check | Pass / Warning / Fail |
|---|---|---|
| 1 | **Database File Writable** (SQLite) or **Database Server Reachable** (PostgreSQL, shows `version()`) | Fail on any exception |
| 2 | **Database Integrity (PRAGMA)** on SQLite; on PostgreSQL a committed `SELECT 1`, detail *"server responded to a read"* | Fail if `integrity_check` is not `ok` |
| 3 | **Database Tables** — `N tables found (expected ≥30)` | **Warning** below 30 |
| 4 | **Super Admin User Exists** — `N active super_admin user(s)` | Fail at zero |
| 5 | **Clinic Record** — `N clinic record(s)` | Fail at zero |
| 6 | **Legacy App Directory** | Warning if missing or `LEGACY_APP_DIR not configured` |
| 7 | **Python Version** | always Pass |
| 8 | **Static Folder** | Fail if the directory is gone |

Summary tiles: **Total Checks / Passed / Warnings / Failed**, and one of three headlines —
**All Systems Operational / جميع الأنظمة تعمل**, *"Platform is operational but some items
need attention."*, or *"Review the failed checks below and take corrective action."*
Top bar: **🔄 Re-run Diagnostics**, **🖥️ Monitor**, **⚙️ Settings**.

There is also a **🔗 Live Legacy App Connectivity** card with **🔍 Test Connectivity**.
That test runs **in the browser**, as a `no-cors` fetch from the staff member's machine
(`templates/system/diagnostics.html:153-159`) — it tells you whether **that PC** can reach
the legacy app, not whether the server can.

### Step 3 — follow the symptom

| Symptom | Where to go next |
|---|---|
| "It saved but nothing changed" | `/system/audit` filtered to that record — if there is no row, the write never happened |
| Errors (24h) is non-zero | The **Recent Server Logs** table on the Monitor, then the log files |
| Pending / Failed / Conflicts non-zero | `/system/sync` — Workflow 16 |
| Backup card red | `/system/backup` — Workflows 8-10 |
| Somebody cannot open a page they used to | `/system/roles`, then `/system/audit` filtered to `action=edit_role` or `assign_role` |
| Table count under 30 | A migration did not finish. Do not restore blindly; check the deployment log first |
| Log files growing | Retention is `LOG_FILE_RETENTION_DAYS`; the sweep job runs at **03:30**, not 03:00 as the Monitor text claims — Limit 11 |

### Errors and edge cases

- Every block on the Monitor is individually wrapped in `try/except`, so a broken table
  shows `0` instead of a 500. **A zero can therefore mean "none" or "could not read".**
  Diagnostics is the screen that distinguishes them.
- Diagnostics opens its own connection per check group; if the database is unreachable the
  page still renders, with a single **Database Connection / Fail** row carrying the
  exception text.

```mermaid
flowchart TD
  A["Staff report a problem"] --> B["/system/monitor — auto-refresh 60s"]
  B --> C{"What is off?"}
  C -->|Errors 24h| D["Recent Server Logs card → log files"]
  C -->|Sync counters| E["/system/sync"]
  C -->|Backup red| F["/system/backup"]
  C -->|Nothing obvious| G["/system/diagnostics — 8 live checks"]
  G --> H{"Any Fail?"}
  H -->|Yes| I["Storage, integrity, super_admin, clinic row, static folder"]
  H -->|Warning only| J["Table count < 30, or legacy dir missing"]
  H -->|All pass| K["/system/audit — filter to the record that looks wrong"]
```

---

## Workflow 16 — Resolve an offline-sync conflict

**Who:** `super_admin`, `clinic_owner`, `support_admin`.
**When:** a device synced a record the server had also changed. The conflict lands in
`sync_conflicts` with `resolution_status='PENDING'` and shows on the Monitor's
**Conflicts / التعارضات** counter.

**Read this before you use the screen.** *"Keep Local" does not push the device's data to
the server.* It closes the conflict, records that the local side was chosen, and leaves
the device's payload on the conflict row for somebody to copy across by hand. The flash
message says so; the browser confirm dialog on the same button says the opposite —
Limit 10.

### Happy path

1. `/system/monitor` → the Conflicts chip, or the warning strip → **Resolve → / حل ←**.
2. `/system/sync`, **Sync Dashboard / لوحة المزامنة**. Four chips at the top: Pending,
   Synced, Failed, Conflicts.
3. The **Conflicts** section lists up to 50 pending conflicts, each as a card with the
   conflict id, its type badge, and two payload panes side by side:
   **Device version (local) / نسخة الجهاز (محلية)** and
   **Server version (current) / نسخة الخادم (الحالية)**. The section header says
   *"Choose which version to keep — local (device) or server."*
4. Read both panes. Decide.
5. **Keep Server / الاحتفاظ بالخادم** — a confirm asks *"Keep SERVER version? Device change
   will be discarded."* Confirm.
6. `sync_conflicts.resolution_status` becomes `MANUAL_RESOLVED_SERVER`, with `resolved_by`
   and `resolved_at`. Audit row `resolve_conflict`,
   `details="Resolved sync conflict — kept: server"`.
7. Flash `"Conflict resolved — the server version is kept."` The card disappears from the
   list and the Conflicts counter drops.

### The other branch — Keep Local

5a. **Keep Local / الاحتفاظ بالمحلية**. The confirm dialog says
    *"Keep LOCAL version? This overwrites server data."* — **this is wrong; nothing is
    overwritten.**
6a. `resolution_status` becomes `MANUAL_RESOLVED_LOCAL`. The server record is **unchanged**.
7a. Flash, deliberately a `warning` and deliberately blunt:
    `"Conflict closed, marked KEPT LOCAL. The server record is unchanged; the device's
    version is stored on the conflict for you to copy across by hand."`
8a. Somebody must now open the record in its own module and retype the device's values.
    Until they do, the device's version exists only on the conflict row.

### The rest of the page

- **⚡ Sync Queue** — the last 100 `sync_queue` rows: Time, Status, Entity, Operation,
  Device, User, Retries, a payload viewer and the error text. Filters for status, device
  and entity, applied as GET parameters, with a **Filter / تصفية** button.
- **📱 Registered Devices** — up to 50, showing platform, app version, user id, last
  online, last sync and registration date. *Active = seen within 1 hour.*

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **More than 50 pending conflicts** | Only 50 are shown. Resolve some and reload for the rest. |
| **A failed queue item** | There is no retry button on this screen. Retries are the device's job, capped at 5 (`max 5 retries`, shown on the Monitor tile). |
| **No conflicts** | *"No unresolved conflicts — everything is in sync. / لا توجد تعارضات غير محلولة — كل شيء متزامن."* |
| **Sync tables absent** | Every query on this page is wrapped in `try/except`; the sections render empty rather than erroring. |

### Errors

| Trigger | Message |
|---|---|
| Anything raised during resolution | `"Error resolving conflict: <reason>"` (danger) |

### What is written

`sync_conflicts.resolution_status` / `resolved_by` / `resolved_at`; `audit_log`
(`resolve_conflict`). **No business table is touched by either button.**

```mermaid
flowchart TD
  A["Device syncs a record the server also changed"] --> B["sync_conflicts row, status PENDING"]
  B --> C["/system/monitor Conflicts chip → Resolve →"]
  C --> D["/system/sync — device pane vs server pane"]
  D --> E{"Which side?"}
  E -->|Keep Server| F["status MANUAL_RESOLVED_SERVER"]
  F --> G["Conflict resolved — the server version is kept."]
  E -->|Keep Local| H["status MANUAL_RESOLVED_LOCAL — server record UNCHANGED"]
  H --> I["Conflict closed, marked KEPT LOCAL... copy across by hand"]
  I --> J["Open the record in its own module and retype the values"]
```

---

## Workflow 17 — Bring a new clinic onto the deployment (multi-clinic)

**Who:** whoever has a shell on the server.
**When:** a new clinic signs up.
**There is no screen for any of this.** Grepping the templates for "tenant" returns
nothing. Provisioning, listing, suspending and renaming are all terminal work.

### Why database-per-clinic

The alternative was a `clinic_id` column on all 74 tables plus a WHERE clause on all
400-odd queries. It was rejected on **safety**: with row-level tenancy, one forgotten
clause silently shows one clinic another clinic's patients — and still returns 200.
A separate database makes the isolation physical (`models/tenancy.py:1-30`).
The honest cost: migrations run once per clinic, and any cross-clinic report is a loop.

### Happy path

1. SSH to the server, into the platform directory.
2. Check what exists:
   ```
   python scripts/add_clinic.py --list
   ```
   Prints SLUG / STATUS / NAME. **The STATUS column always prints `active`** — Limit 13.
3. Create the clinic:
   ```
   python scripts/add_clinic.py --slug nilevet --name "Nile Vet Clinic"
   ```
   For a PostgreSQL clinic add `--postgres "postgresql://user:pass@host:5432/nilevet"`.
   Other flags: `--admin-user` (default `admin`), `--admin-pass` (leave unset — one is
   generated), `--db-dir`, `--registry` / `$TENANT_REGISTRY`, `--domain` / `$PLATFORM_DOMAIN`.
4. `provision()` writes the registry row, then builds the full schema inside
   `tenancy.use(slug)`, then sets `clinic.name` so the new clinic is not branded with the
   schema placeholder. **If the schema build fails the registry row is rolled back** — a
   half-provisioned clinic would resolve, reach a login page, and fail on every query.
5. The terminal prints, once:
   ```
     Clinic created.

       Name      : Nile Vet Clinic
       Slug      : nilevet
       Database  : /srv/aleefy/data/tenants/nilevet.db
       Sign in as: admin
       Password  : <generated>

     This password is shown once and is not stored anywhere.
     Give it to the clinic owner and have them change it at first login.
   ```
   With `--domain` it also prints the URL and the exact `certbot` line.
   **The password is never written to a file and never logged** — a credential in a log is
   a credential in every backup of that log.
6. Point DNS at the server, issue the certificate, hand over the URL.
7. The owner signs in at `https://nilevet.aleefy.online` and starts at **Workflow 7**
   (Clinic Settings) — the clinic row ships blank on purpose.

### How a request finds its clinic

Resolution order (`models/tenancy.py:26-40`): `PLATFORM_TENANT` env var → `X-Tenant`
header → host subdomain → nothing, i.e. legacy single-database mode, unchanged.
`app.py:302-314` resolves the clinic **before anything touches a database**, and:

- an **unregistered** subdomain → **404**, *"No clinic is registered at this address."*
- a **suspended** clinic → **403**, *"This clinic's account is not active. Please contact support."*
- a session cookie presented to a **different** clinic → cleared, flash
  *"Please sign in to this clinic."*

`www`, `app`, `api`, `admin`, `static`, `cdn`, `mail`, `localhost` are reserved and never
read as clinic names; bare IP addresses are not subdomains either.

### What each clinic gets of its own

Its own database, its own backup directory `<backup_dir>/<slug>` (retention purges by age
across a directory, so a shared one would let the busiest clinic delete everyone else's
archives), and its own turn in every nightly job through `tenancy.each_clinic()` — backup,
WhatsApp reminders, rate-limit cleanup, attendance close-out, log retention.

### Alternative scenarios

| Situation | Behaviour |
|---|---|
| **Suspending a clinic** (non-payment, migration) | No screen and no CLI flag. It is `tenancy.set_status(slug, "suspended")` from a Python shell (`models/tenancy.py:314-319`). The clinic then gets 403 on every page. |
| **Renaming or deleting a clinic** | Neither exists anywhere. |
| **Single-clinic install** | Nothing changes. `enabled()` is False until at least one tenant is registered, and every path behaves exactly as it did before this module existed. |
| **Backups for a PostgreSQL clinic** | The per-clinic DSN wins over the process-wide one, deliberately: using the deployment's DSN would dump the same database N times under N clinic names, and every archive would look present and correct (`models/backup.py:140-178`). |

### Errors and refusals — exact text

| Trigger | Message |
|---|---|
| Slug already registered | `"ERROR: 'nilevet' already exists (Nile Vet Clinic)."` then `"       Pick another slug, or remove it deliberately first."` — never overwritten, because re-provisioning would rebuild the schema over live records |
| Bad slug | `"invalid slug 'Nile_Vet': 3-32 chars, lowercase letters, digits and hyphens, not starting or ending with a hyphen"` |
| Reserved slug | `"'www' is reserved"` |
| No name | `"a clinic name is required"` |
| Admin password under 8 characters via `--admin-pass` | `"the first admin password must be at least 8 characters"` |
| Schema build failed | `"ERROR: provisioning failed and was rolled back: <reason>"` — the wording distinguishes "it failed" from "it failed and left something behind" |
| `tenancy.configure()` never called | `"tenancy.configure() has not been called"` |

### What is written

A row in `tenants` (slug, name, db_path **or** pg_dsn, status, created_at) in the registry
SQLite file; a fully built clinic database; a backup directory on first backup.

```mermaid
flowchart TD
  A["python scripts/add_clinic.py --list"] --> B["python scripts/add_clinic.py --slug x --name '...'"]
  B --> C{"Slug valid, unreserved, unused?"}
  C -->|No| D["ERROR: invalid slug / reserved / already exists"]
  C -->|Yes| E["INSERT tenants row"]
  E --> F["Build the schema inside tenancy.use(slug)"]
  F -->|Fails| G["Registry row rolled back + ERROR ... was rolled back"]
  F -->|OK| H["Set clinic.name, print the password ONCE"]
  H --> I["DNS + certbot for slug.domain"]
  I --> J["Owner signs in → Workflow 7, Clinic Settings"]
  K["Request arrives"] --> L{"Subdomain in the registry?"}
  L -->|No| M["404 No clinic is registered at this address."]
  L -->|Suspended| N["403 This clinic's account is not active."]
  L -->|Active| O{"session.tenant matches?"}
  O -->|No| P["Session cleared — Please sign in to this clinic."]
  O -->|Yes| Q["Serve, against that clinic's database"]
```

---

## 18. Branches — what actually exists

There is **no branch management anywhere in the product.** Written down here because the
word appears on two screens and people reasonably assume more.

**What exists**
- One table, `branches`, seeded with exactly one row: `Main Branch / الفرع الرئيسي`
  (`models/database.py:2641-2643`).
- A **Branch / الفرع** dropdown on the staff form, sourced from
  `SELECT * FROM branches WHERE is_active=1 ORDER BY name`.
- A LEFT JOIN on the staff list and staff detail so a row can show a branch name.

**What does not exist**
- No branch list, no create, no rename, no deactivate screen or route. The only writes to
  `branches` outside the schema seed are in demo/seed scripts.
- No branch switcher.
- **No branch scoping of any data.** `users.branch_id` is a label. No query anywhere filters
  patients, appointments, invoices or stock by branch.
- The role `branch_manager` is a permission set, not a per-branch boundary: it grants 18
  modules across the whole clinic (`models/database.py:4347-4352`).

**If a group genuinely needs separate branches today**, the working answer is the
multi-clinic path — one clinic per branch, one database each (Workflow 17) — with the cost
that nothing is shared between them.

---

## 19. Known limits and bugs

Every item below was read in the source. Line numbers are from the files as they stand.

**1. The `auditor` role can never open the Audit Log, although the route names it.**
`/system/audit` is decorated `@role_required(..., "auditor")`
(`blueprints/system/routes.py:235`), but `role_required` wraps `login_required`, which
enforces the per-blueprint **module grant** first (`blueprints/auth/routes.py:170-176`).
The system blueprint's key is `system`; the seeded auditor grant is
`["reports", "audit", "accounting"]` (`models/database.py:4378`) and the auditor row
**is** seeded into `roles` (`models/database.py:2449`), so the lookup returns a real set
that lacks `system` and the user is redirected to the launcher with
`"You don't have permission to access this page."` The same trap catches any future role
granted `audit` but not `system`.

**2. Built-in roles are listed twice on `/system/roles`, and the second copy is editable.**
The route passes `db.list_roles()` — every row of the `roles` table, i.e. all **14** seeded
built-ins plus any custom ones. The template renders 10 built-ins as hardcoded,
non-editable rows and then renders the **same query again** under
`Custom Roles ({{ roles|length }})` with **Edit Role** and **Delete** buttons
(`templates/system/roles.html:232-245`). On a fresh install the heading reads
**"Custom Roles (14)"**. Delete is still refused while staff hold the role, but editing a
built-in role's permissions from there **does take effect**.

**3. A clinic owner cannot assign a custom role to anybody.**
`may_grant_role` ends in `role_rank(actor) >= role_rank(target) > 0`
(`blueprints/auth/routes.py:326-336`), and `ROLE_RANK` contains only the 14 built-ins
(`blueprints/auth/routes.py:294-320`). A custom role such as `head_nurse` ranks **0**, so
`0 > 0` is False and the grant is refused with
`"Your role (clinic_owner) cannot grant head_nurse."` Only a `super_admin` gets through,
because `may_grant_role` returns True for `super_admin` before the rank comparison.
Net effect: `clinic_owner` and `hr` can **create** a custom role on `/system/roles` and
then cannot put anyone on it. This applies to both doors — the Staff Access tab and the HR
staff form — because both call `guard_role_change`.

**4. The Staff Access tab is capped at 300 users.**
`GET /system/roles/users` is `LIMIT 300` (`blueprints/system/routes.py:826-828`). Search,
role filter and paging all run in the browser over those 300 rows, so a larger clinic
silently cannot see or reassign the rest from this screen. Use `/hr/staff` instead.

**5. The Backup page shows buttons some viewers cannot use.**
The page is granted to `support_admin`, but **Download** (`routes.py:509-510`),
**Upload** (`:520-521`), **Restore** (`:539-540`) and **Clear maintenance**
(`:568-569`) are `super_admin` / `clinic_owner` only, and `templates/system/backup.html`
renders all four controls with **no role condition** (lines 100-104, 148-163, 208-216,
23-26). A `support_admin` pressing them is redirected to the launcher with a permission
flash. **Back Up Now** and **✓ Check** do work for them.

**6. The sidebar SYSTEM group is shown to `support_admin` and includes Settings.**
`templates/base.html:289-290` renders the group for `support_admin`, and its first item is
Settings — but `/system/settings` is `@role_required("super_admin", "clinic_owner")`
(`blueprints/system/routes.py:326`). A support admin clicking it is bounced.
Data Migration in the same group has its own gate.

**7. The Appearance card on Clinic Settings is write-only, and offers a theme that no
longer exists.** The POST writes `default_theme` and `default_language` into `settings`
with no validation (`blueprints/system/routes.py:376-386`). Grepping the whole codebase
for either key returns **only that line** — nothing reads them. Separately, the theme
dropdown still offers **"Logo (Navy / Yellow / Blue)"** (`templates/system/settings.html:227-232`)
while `blueprints/settings/routes.py:13` defines `_VALID_THEMES = {"medical"}` and silently
normalises anything else; the profile page correspondingly offers one theme radio.

**8. Two dead fields on the Monitor's Backup Status card.**
`templates/system/monitor.html:270` renders `latest_backup.created_at` and `:275` renders
`latest_backup.integrity`, but `models/backup.py:439-473` returns
`timestamp / age_days / age_hours / kind / engine` and neither of those keys. **Last Backup**
is therefore always blank and **Integrity** always shows the `?` fallback with the red
badge. `/system/backup` shows the same data correctly — trust that page.

**9. Three password screens advertise the wrong rule.**
`models/security.py:346-366` requires 12 characters with upper, lower, digit and special.
But the new-staff form's placeholder says *"Min 6 characters / 6 أحرف على الأقل"*
(`templates/hr/staff_form.html:52`) and the reset-password box says
*"New password (min 6 chars)"* with `minlength="6"` (`templates/hr/staff_detail.html:126`).
The browser lets a 6-character password through and the server then rejects it.

**10. The "Keep Local" confirm dialog contradicts what the code does.**
`templates/system/sync.html:201` asks *"Keep LOCAL version? This overwrites server data."*
Nothing is overwritten: `resolve_conflict` only records `MANUAL_RESOLVED_LOCAL`
(`models/sync.py:157-186`) and the flash says so explicitly. Believe the flash, not the
dialog.

**11. Small schedule mismatch on the Monitor.**
`templates/system/monitor.html:284` prints `Backup 02:00 · WhatsApp 09:00 · Log cleanup
03:00 UTC`. The log-retention job is registered at **03:30** (`app.py:842-843`). Backup and
WhatsApp are correct.

**12. Language preference does not survive sign-out.**
The login form posts no `lang` or `theme` field (`templates/login.html:748-800`), so
`_establish_session` always stores `session["lang"] = "en"`
(`blueprints/auth/routes.py:514`). The context processor prefers `users.language`
(`app.py:377-378`), but the profile page's Language select writes that value **into the
session only** — `db.update_user_theme` persists the theme and nothing persists the
language (`blueprints/auth/routes.py:786-796`). So a member of staff who chooses Arabic on
the login page, or in their profile, is back in English at the next sign-in unless
`PLATFORM_DEFAULT_LANG=ar` is set on the deployment.

**13. `add_clinic.py --list` always prints `active`.**
`scripts/add_clinic.py:69` computes the status from `r.get("is_active", 1)`, but the
registry column is `status` (`models/tenancy.py:67-77`). The default is always returned, so
a suspended clinic is listed as active. Check the registry directly if it matters.

**14. Multi-clinic has no UI at all, and branches have no management screen.**
See Workflow 17 and section 18.

**15. There is no change-your-own-password screen.**
`blueprints/auth/routes.py:707-731` fully implements `action=change_password` — old
password verified, confirmation matched, strength checked, audited — but
`templates/profile.html` contains **no form, field or button for it**. In practice the only
way a password changes is an administrator using `POST /hr/staff/<id>/reset-password`,
which means the administrator knows it.

**16. Audit writes fail silently.**
`db.log_audit()` swallows every exception (`models/database.py:2965-2975`). If the audit
insert fails, the user's action still completes and nothing anywhere reports the missing
row. The field-level path (`audit.audit_row`) is used by exactly one caller today,
role editing.

**17. Scale note on the Audit Log.**
The paged query is bounded, but the three filter dropdowns run `SELECT DISTINCT` over the
whole `audit_log` table on **every** page load — acknowledged in the source comment as the
one unbounded scan left (`blueprints/system/routes.py:276-287`).

**18. A dead JavaScript reference on the profile page.**
The theme radio's `onchange` sets `document.getElementById('lbl-logo').style.borderColor`
(`templates/profile.html:44`), but no element with that id exists — the logo theme was
removed. Harmless today because there is only one radio and it is already selected, so the
handler never fires.

### Not verified

Nothing was executed. This chapter is a static read of the source. In particular the
following were **not** observed running: backup and restore against a live PostgreSQL
deployment; the contents of a real tenant registry; whether any deployed clinic has custom
`roles` rows beyond the 14 seeded ones; the S3 off-site path against a real bucket; and the
sync dashboard with real device traffic. HR screens are documented only to the depth needed
for user accounts and roles — payroll, attendance, performance, roster, warnings and
certifications are out of scope for this chapter.

---

## 20. Source index

| Area | File |
|---|---|
| System routes — monitor, audit, settings, backup, diagnostics, sync, roles, export | `D:/vet/platform/blueprints/system/routes.py` |
| Auth routes — login, 2FA, profile, shared desk, permission gates, `guard_role_change` | `D:/vet/platform/blueprints/auth/routes.py` |
| Backup, restore, off-site, health, maintenance marker | `D:/vet/platform/models/backup.py` |
| Multi-clinic registry and resolution | `D:/vet/platform/models/tenancy.py` |
| Clinic provisioning | `D:/vet/platform/models/provisioning.py` |
| Clinic creation CLI | `D:/vet/platform/scripts/add_clinic.py` |
| Permissions catalogue, default grants, seed roles, role CRUD, `log_audit` | `D:/vet/platform/models/database.py` |
| Password strength, rate limiting, TOTP, backup codes, CSRF, session timeout | `D:/vet/platform/models/security.py` |
| Field-level audit — `audit_row`, `record_change`, `parse_details` | `D:/vet/platform/models/audit.py` |
| Sync conflict resolution | `D:/vet/platform/models/sync.py` |
| Logo/QR validation and encoding, theme and language switches | `D:/vet/platform/blueprints/settings/routes.py` |
| Staff accounts, staff form, password reset, HR roles list | `D:/vet/platform/blueprints/hr/routes.py` |
| Scheduler, tenant gate, session-clinic check, context processor, `/healthz` | `D:/vet/platform/app.py` |
| Sidebar SYSTEM group, avatar menu and desk switcher | `D:/vet/platform/templates/base.html` |
| Screens | `D:/vet/platform/templates/system/{monitor,audit_log,settings,backup,diagnostics,sync,roles}.html`, `templates/{login,profile}.html`, `templates/auth/{two_factor,2fa_admin,desk_add}.html`, `templates/hr/{staff_list,staff_form,staff_detail,roles_list}.html` |
