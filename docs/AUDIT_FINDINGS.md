# Aleefy — Recovered Audit Findings

**334 findings** recovered from the 18 agents that completed before the exhaustive audit was stopped.

> **Nobody argued back.** The audit runs finders, then skeptics whose job is to kill each finding — wrong role, misread code, a guard that already handles it, inflated severity. The skeptics never ran. Every item here is *reported and claimed reproduced*, not confirmed. Expect a meaningful share to be wrong.

> Duplicates across the three axes (happy path / edge cases / money) are only removed where the titles match exactly, so the same underlying bug can appear more than once.

| Severity | Count |
|---|---|
| BLOCKER | 63 |
| MAJOR | 143 |
| MINOR | 112 |
| INFO | 16 |

| Module | Findings |
|---|---|
| Attendance | 74 |
| Finance | 71 |
| Whatsapp | 57 |
| Hr | 49 |
| System | 45 |
| Ai Assistant | 23 |
| Petshop | 15 |

---

## Attendance  (74)

### [BLOCKER] Lateness and auto-close judge every employee against ONE clinic-wide shift — evening and night staff are flagged Late daily and auto-closed to ZERO paid hours

**Steps** — Stock install; the seeder creates four ACTIVE shifts (verified on live demo: Morning 08:00-16:00, Evening 14:00-22:00, Night 22:00-06:00, Weekend Morning 09:00-15:00). Assign a nurse to the Evening shift via HR (blueprints/hr/routes.py:585 writes staff_shifts). She opens /attendance/checkin and clocks in at 14:00, on time for her own shift. Reproduced locally: with shifts Morning 08:00-16:00 and Evening 16:00-23:00 active, status_for_checkin(conn,'16:02') returned ('Late', 467). Then the same nurse forgets to clock out; close_forgotten_checkouts (run nightly from app.py:760) produced check_out='16:02', hours_worked=0.0, notes '[auto-closed at shift end 16:02; no check-out was recorded]'.

**Expected** — The 14:00 arrival is Present. If she forgets to clock out, the record closes at HER shift end (22:00) and pays ~7.5 hours, which is the stated purpose of close_forgotten_checkouts.

**Actual** — She is flashed "Checked in at 14:00 — 345 minutes after the shift start" every single day, her record is stamped Late, and the nightly auto-close pays her 0.0 hours because her check-in is after the MORNING shift's end so the `if _minutes(check_in) > _minutes(end)` guard collapses check_out onto check_in. hours_worked is what payroll pays. The docstring at routes.py:80 says the whole point is "Paying an estimate is fairer than paying zero" — it pays zero.

**Cause** — blueprints/attendance/routes.py:32 default_shift() — `SELECT ... FROM shifts WHERE is_active=1 ORDER BY id LIMIT 1`, i.e. the lowest-id active shift for everyone. Consumed at routes.py:71 (status_for_checkin) and routes.py:96 (close_forgotten_checkouts). The per-employee assignment already exists and record_edit at routes.py:430 already resolves it correctly through staff_shifts — the lateness/auto-close engine just never asks.

**Fix** — Give default_shift a user_id/work_date and resolve through staff_shifts first (reuse the exact query already in record_edit at routes.py:430), falling back to the lowest-id active shift only for unrostered staff. Both call sites already have the user id in hand.

*reproduced · edge cases*


### [BLOCKER] A leave request that starts next year permanently eats the employee's balance and is never deducted from anything

**Steps** — As a nurse in December, book 5-9 January of next year (/attendance/leaves/new). Manager approves it. Reproduced locally with a 21-day balance for 2026 and a request for 2027-01-05 to 2027-01-09.

**Expected** — 4 days reserved, then moved from pending to used against the year the leave falls in, with a balance row created for that year if needed.

**Actual** — AFTER SUBMIT the 2026 row reads allocated 21 / used 0 / pending 4 / remaining 21. AFTER APPROVE it is byte-identical — pending is still 4 and used is still 0, and no 2027 row exists. The employee has permanently lost 4 days of available balance (leave_new computes availability as remaining - pending) and the leave she actually takes was never charged to anyone. Reject has the identical mismatch, so a rejected cross-year request also leaves the reservation stuck forever. Nothing in the UI can clear it except an HR manager manually overriding the balance.

**Cause** — blueprints/attendance/routes.py:487 leave_new reserves pending under `year = date.today().year`, but leave_approve at routes.py:608 and leave_reject at routes.py:637 both use `yr = date.fromisoformat(req["start_date"]).year`. When those differ the UPDATE matches no row and silently no-ops. leave_approve also never calls the existing _get_or_create_balance helper (routes.py:143), so a missing target-year row is not created.

**Fix** — Use one year everywhere — the start_date year — in leave_new too, and route both approve and reject through _get_or_create_balance so the row exists before the UPDATE. Then assert rowcount and flash if it is 0 instead of reporting success.

*reproduced · edge cases*


### [BLOCKER] Approved leave is never deducted for any leave type that has no pre-existing balance row — _get_or_create_balance() is defined and never called

**Steps** — LIVE DEMO, reproduced end to end. 1) Sign in as dr.sara / Demo@1234. 2) /attendance/leaves/new — the 'My Balances' panel shows Emergency Leave: Used 0.0d, Remaining 3.0d. 3) Submit Emergency Leave 2026-09-21 → 2026-09-23 (3 days). 4) Sign in as admin / Aleefy@Demo2026, open /attendance/leaves/51, click Approve (302, flash 'Leave request approved'). 5) Go back to dr.sara's /attendance/leaves/new. On the demo, only Annual Leave and Sick Leave have rows in leave_balances; Emergency / Maternity / Study / Unpaid have none for any of the 15 staff (see /attendance/balances — those four columns read 'اضغط للتعيين' for everyone).

**Expected** — Emergency Leave now reads Used 3.0d, Remaining 0.0d, and a further request warns 'Insufficient balance'.

**Actual** — Emergency Leave still reads Used 0.0d, Remaining 3.0d. leave_balances is still empty for that type. She can request and have approved the same 3 days again, without limit, forever. Nothing on any screen shows the leave was ever taken against an entitlement.

**Cause** — blueprints/attendance/routes.py:526 (leave_new reserves pending only `if bal:`) and :609 (leave_approve UPDATEs leave_balances for a row that does not exist, affecting 0 rows). The helper written for exactly this, `_get_or_create_balance` at routes.py:143, is never called from anywhere in the codebase (`grep -rn _get_or_create_balance` returns only its own definition).

**Fix** — In leave_new, before reserving pending, call `_get_or_create_balance(conn, user['id'], lt_id, year, lt_row['days_per_year'])` and use its row instead of the raw SELECT; do the same in leave_approve/leave_reject before the UPDATE. Failing test to write: tests/test_attendance_routes.py::test_approved_leave_deducts_even_when_no_balance_row_exists — create a user with no leave_balances rows, POST /attendance/leaves/new, approve it, assert leave_balances.used == days_requested.

*reproduced · happy path*


### [BLOCKER] Every employee is judged against one clinic-wide shift, so evening/night staff are always marked Late and the nightly auto-close pays them for the wrong hours

**Steps** — LOCAL. The demo already has four shifts configured (Morning 08:00-16:00, Evening 14:00-22:00, Night 22:00-06:00, Weekend Morning 09:00-15:00 — see /attendance/shifts). 1) Roster a receptionist onto the Evening shift (staff_shifts, which is what HR's roster screen writes). 2) Have them check in at 14:00, exactly on time. 3) Separately: insert an attendance row for that employee with check_in 14:00 and no check_out for yesterday, then run close_forgotten_checkouts(conn, yesterday) — the job app.py schedules at 00:20 daily.

**Expected** — Status 'Present'. Auto-close writes check_out 22:00 and 7.0 hours (8h minus the 60-min break).

**Actual** — Status 'Late', and the check-in screen flashes in their face '345 minutes after the shift start (grace 15 min)'. A night-shift arrival at 22:00 is 'Late' by 825 minutes. The auto-close writes check_out 16:00 and hours_worked 1.0 for the evening employee (verified: `{'check_in': '14:00', 'check_out': '16:00', 'hours_worked': 1.0}`); a 22:00 night arrival gets check_out=22:00 and 0.0 hours, because the code falls back to the arrival time when it is past the 'shift end'. Payroll reads hours_worked.

**Cause** — blueprints/attendance/routes.py:32 `default_shift()` — `SELECT ... FROM shifts WHERE is_active=1 ORDER BY id LIMIT 1` — ignores staff_shifts entirely. Consumed by status_for_checkin (:73) and close_forgotten_checkouts (:98). The per-employee shift is already resolvable: record_edit at routes.py:429 does exactly that lookup against staff_shifts.

**Fix** — Give default_shift a user_id and resolve through staff_shifts (the query at routes.py:429), falling back to the clinic-wide shift only when the employee is unrostered. Failing tests: test_evening_shift_checkin_is_not_late and test_autoclose_uses_the_employees_own_shift_end.

*reproduced · happy path*


### [BLOCKER] A no-op Save on the Balances screen silently destroys leave entitlement (pending subtracted twice)

**Steps** — Local, real routes, admin login. 1) POST /attendance/balances/set allocated=21 used=0 pending=0 -> row {21,0,0,rem 21}. 2) Employee POSTs /attendance/leaves/new for Mon 2026-09-07..Fri 09-11 -> days_requested=5, pending=5, remaining still 21, leave_form correctly offers 21-5=16 available. 3) Manager opens the SAME cell on /attendance/balances and clicks Save WITHOUT CHANGING ANYTHING (balances.html openModal(...pending) pre-fills the Pending box with the stored 5, so the form posts allocated=21 used=0 pending=5). Row becomes {21,0,5,rem 16}. Employee is now offered 16-5=11 days. 4) Manager approves -> {allocated 21, used 5, pending 0, remaining 11}.

**Expected** — Employee took 5 of 21 days. remaining = 16. Reopening and re-saving a balance unchanged must be a no-op.

**Actual** — remaining = 11. Five days of paid entitlement gone, with a green "Balance updated." flash and no negative number anywhere on screen. Cumulative: every time a manager touches that cell while a request is pending, the pending days are deducted again.

**Cause** — blueprints/attendance/routes.py:800 `remaining = max(0, alloc - used - pending)` (balance_set) vs routes.py:514 `if bal and (bal["remaining"] - bal["pending"]) < days_req` (leave_new) vs routes.py:611 `remaining=MAX(0,remaining-?)` (leave_approve). Three routes use three different definitions of `remaining`; templates/attendance/balances.html:47 states the intended one ("Remaining = Allocated − Used − Pending") and the other two contradict it.

**Fix** — Pick one definition and enforce it in one place. Cheapest: make `remaining` mean allocated - used ONLY (never net of pending), i.e. drop `- pending` from balance_set:800, and keep leave_new's `remaining - pending` as the availability figure. Then leave_approve's `remaining=remaining-days` and `pending=pending-days` are both correct and re-saving a cell is idempotent.

*reproduced · money & records*


### [BLOCKER] Approving a leave request that starts in a different year deducts nothing, and strands the reservation forever

**Steps** — Local, real routes. 1) Give user a 2026 balance for leave type X: {allocated 21, used 0, pending 0, remaining 21}. 2) In 2026, POST /attendance/leaves/new start_date=2027-01-05 end_date=2027-01-09 -> request created, days_requested=4, and the 2026 row becomes pending=4. 3) POST /attendance/leaves/<id>/approve. Flash says "Leave request approved."

**Expected** — The reservation clears and 4 days are recorded as used against the correct year.

**Actual** — 2026 row is unchanged: {21, used 0, pending 4, remaining 21}. Nothing is written for 2027 at all. The 4 pending days sit on the 2026 balance permanently — every future 2026 request is checked against remaining-pending and is 4 days short forever — and the 2027 leave is recorded as zero days used. Rejecting a cross-year request has the identical bug. /attendance/leaves/<id> then shows the WRONG year's balance too.

**Cause** — blueprints/attendance/routes.py:529 reserves pending using `year = date.today().year`, but routes.py:608 (approve) and routes.py:637 (reject) release/deduct using `yr = date.fromisoformat(req["start_date"]).year`. The UPDATE matches zero rows and nothing checks the rowcount. routes.py:575 (leave_detail) has the same today-vs-start_date mismatch.

**Fix** — Use one year for the whole lifecycle of a request — `date.fromisoformat(start_date).year` at reservation time in leave_new:529 too — and check the UPDATE rowcount so a miss is loud instead of silent.

*reproduced · money & records*


### [BLOCKER] Every hand-clocked day pays an hour of overtime for the unpaid lunch break — 22 hours per employee per month

**Steps** — Demo shift is Morning 08:00-16:00, break_minutes=60. 1) Employee checks out through /attendance/checkin; templates/attendance/checkin.html:49 renders the break box as `value="0"` and nobody changes it. hours_worked = _calc_hours('08:00','16:00',0) = 8.0. 2) Run blueprints.payroll.routes._get_attendance_summary for a month of 22 such days: overtime_hours = 22.0. 3) Set break_minutes=60 on the same 22 rows and re-run: overtime_hours = 0.0.

**Expected** — A staff member who works their exact rostered shift generates zero overtime.

**Actual** — 22.0 overtime hours per employee per month, billed at salaries.overtime_rate, purely because the check-out form defaults the break to 0 while payroll computes standard_hours as shift span minus the shift's break (16:00-08:00 - 60min = 7.0h). With ~15 staff that is ~330 unearned overtime hours a month. It is also exactly backwards: the same day auto-closed by the 00:20 job stores 7.0h (it uses the shift's break) and generates zero overtime — so the employee who forgets to clock out is paid correctly and the one who clocks out properly is overpaid.

**Cause** — templates/attendance/checkin.html:49 `value="0"` (and :105 for the manager form); blueprints/attendance/routes.py:257 `int(request.form.get("break_minutes", 0) or 0)` and routes.py:293; consumed at blueprints/payroll/routes.py:174 `standard_hours = (e-s).seconds/3600 - break_minutes/60`.

**Fix** — Default the check-out break box to the shift's break_minutes (default_shift(conn)["break_minutes"]) rather than 0, in both the template and the route's fallback, so the manual and auto-closed paths compute the same hours for the same day.

*reproduced · money & records*


### [BLOCKER] record_edit accepts a check-out earlier than check-in and stores 23.98 hours worked

**Steps** — Manager opens /attendance/records/edit/<id> and types check_in=09:00, check_out=08:59 (a normal typo for 18:59, or the two fields swapped). Submit.

**Expected** — Rejected: "check-out must be after check-in".

**Actual** — HTTP 200, green flash "Attendance record updated.", and hours_worked = 23.98 is written. Payroll reads exactly that column and bills ~17 hours of overtime for that single day. A second variant: check_in=09:00 check_out=17:00 break_minutes=-120 is accepted and stores 10.0 hours from an 8-hour window — a negative break ADDS paid time, and the -120 is persisted to break_minutes. There is no validation on this route at all.

**Cause** — blueprints/attendance/routes.py:412 `hrs = _calc_hours(check_in, check_out, brk) if check_in and check_out else 0` — no ordering check; routes.py:24-25 in _calc_hours treats any `co < ci` as a night shift crossing midnight, which is right for 22:00->06:00 and catastrophic for a one-minute inversion. routes.py:410 `int(request.form.get("break_minutes", 0) or 0)` accepts negatives.

**Fix** — One guard in _calc_hours (routes.py:18), where every caller routes through: clamp break to >=0, and treat the co<ci branch as a night shift only when the gap is large (e.g. co+24h - ci <= 16h), otherwise return 0 and let the caller reject. Add the min=0 to the break input.

*reproduced · money & records*


### [BLOCKER] Everyone is judged against the first shift in the table — evening and night staff are permanently "Late", and the nightly auto-close pays them 1 hour instead of 8

**Steps** — Local, seeded shifts (Morning 08:00-16:00 id=1, Evening 14:00-22:00, Night 22:00-06:00). Assign a nurse to Evening Shift via staff_shifts, sign in as that nurse, go to /attendance/checkin and click 'Check In Now' at 14:00. Then leave the record open and let the 00:20 job (app.py:753 _close_attendance) run.

**Expected** — Status 'Present' (she is exactly on time for her shift), flash 'Check-in recorded successfully.' If she forgets to clock out, the auto-closer closes at HER shift end (22:00) for ~7 net hours.

**Actual** — status_for_checkin returns ('Late', 345). Flash: "Checked in at 14:00 - 345 minutes after the shift start (grace 15 min)." Night nurse at 22:00 -> ('Late', 825). close_forgotten_checkouts then writes check_out='16:00', hours_worked=1.0 for the evening nurse (verified: `{'check_in': '14:00', 'check_out': '16:00', 'hours_worked': 1.0}`). hours_worked is the column payroll reads, so she is paid 1 hour for an 8-hour night.

**Cause** — blueprints/attendance/routes.py:32 default_shift() — `SELECT ... FROM shifts WHERE is_active=1 ORDER BY id LIMIT 1`. It never looks at staff_shifts, even though record_edit (routes.py:429) already knows how to resolve a user's shift from staff_shifts. Consumed by status_for_checkin (:65) and close_forgotten_checkouts (:80,:98).

**Fix** — Give default_shift a user_id and resolve through staff_shifts the way record_edit already does (staff_shifts JOIN shifts, effective_from <= work_date AND (effective_to IS NULL OR >= work_date)), falling back to the current query only when the person is unrostered. Same lookup in status_for_checkin and per-row inside close_forgotten_checkouts.

*reproduced · happy path*


### [BLOCKER] Leave arithmetic uses a Mon-Fri week — a Sunday off costs the employee zero days, a Friday off costs them one

**Steps** — Sign in as any employee, /attendance/leaves/new, pick Sick Leave, start_date = next Sunday, end_date = same Sunday, Submit. Repeat with Sat->Sun, with a Friday, and with Sat->Wed.

**Expected** — This deployment's week is Egyptian: the demo seed itself skips Friday as the day off (scripts/seed/demo_showcase.py:1148 `if day.weekday() == 4: continue`). Sunday-only = 1 day. Sat+Sun = 2. Friday-only = 0. Sat->Wed = 5.

**Actual** — Sunday-only -> days_requested = 0.0, flash "Leave request submitted for 0 day(s)", nothing reserved, nothing deducted on approval — a free working day off. Sat+Sun -> 0.0. Friday-only (the actual day off) -> charged 1.0. Sat->Wed (5 working days) -> charged 3.0. The leave form's own text says "(business days, excl. weekends & holidays)", and its JS preview (leave_form.html calcDays) makes the same Sat/Sun assumption.

**Cause** — blueprints/attendance/routes.py:138 — `if cur.weekday() < 5 and ...` inside _business_days.

**Fix** — Make the non-working days configurable (clinic setting, or derive from shifts.days_of_week) instead of hardcoding weekday()<5; default to Friday(+Saturday) for this deployment. Fix templates/attendance/leave_form.html calcDays to match so the preview and the saved number agree.

*reproduced · happy path*


### [BLOCKER] Leave types with no balance row are completely untracked, while the request form shows a full allowance that does not exist

**Steps** — Live demo, sign in as any staff member -> /attendance/leaves/new. Emergency Leave shows "Remaining: 3.0d". Request Emergency Leave for 15 business days. Sign in as hr.marwa -> open the request -> Approve. Then open /attendance/balances.

**Expected** — Either the request is blocked/warned against a real 3-day allowance, or a balance row is created and 15 days are recorded against it.

**Actual** — Submit: no warning at all, flash "Leave request submitted for 15 day(s). Awaiting approval." Approve: flash "Leave request approved." leave_balances still has zero rows for that leave type; the balances matrix still shows "— click to set". 15 days of leave exist nowhere in any balance. On the live demo only Annual and Sick are seeded, so this is true for Emergency, Maternity, Unpaid and Study leave for all 15 staff — and true for every leave type in a brand-new clinic (fresh DB has zero leave_balances rows).

**Cause** — blueprints/attendance/routes.py:511-516 — the balance check is inside `if bal:`, so a missing row means no check and no pending reservation; routes.py:609 leave_approve UPDATEs leave_balances, which affects 0 rows and reports success anyway. leave_form.html falls back to `lt.days_per_year` for the displayed remaining, which makes an absent balance look like a full one. `_get_or_create_balance` (routes.py:143) exists for exactly this and is called from nowhere in the app.

**Fix** — Call _get_or_create_balance(conn, user_id, lt_id, year, lt.days_per_year) in leave_new and leave_approve so the row always exists before it is checked or decremented, and have leave_approve verify the UPDATE touched a row before flashing success.

*reproduced · happy path*


### [BLOCKER] Editing any attendance record on the live demo wipes the check-in/check-out times and zeroes the hours

**Steps** — Live demo, log in as admin / Aleefy@Demo2026. Go to /attendance/records (default 30-day range) → click تعديل (Edit) on any row, e.g. https://demo.aleefy.online/attendance/records/edit/6020. The page emits `<input type="time" name="check_in" value="2026-08-06 08:00:00">`. A time input rejects any value that is not HH:MM, so the browser shows an empty --:-- field for both times. Press "Save Changes" without touching anything.

**Expected** — The record reopens with 08:00 / 17:40 and hours_worked 8.2 unchanged; a manager who only wanted to add a note keeps the times.

**Actual** — The form submits check_in="" and check_out="", the route stores NULL/NULL and, because `hrs = _calc_hours(...) if check_in and check_out else 0`, forces hours_worked to 0. The day's worked hours — the exact column payroll reads — are destroyed, and the screen says "Attendance record updated." Reproduced locally: POSTing the edit form with empty times leaves check_in=None, check_out=None, hours_worked=0.0 with a success flash. Reproduced live: the invalid time value is in the served HTML of every record on the demo (~1,300 rows, every staff member, 90 days).

**Cause** — scripts/seed/demo_showcase.py:340 `_dt()` writes check_in/check_out as "YYYY-MM-DD HH:MM:00" while every reader in blueprints/attendance/routes.py treats the column as "HH:MM" (_calc_hours line 22 slices [:5], _minutes line 59 the same). The durable code defect is blueprints/attendance/routes.py:412 — record_edit trusts whatever the DB holds to round-trip through `<input type="time">` and silently rewrites hours_worked to 0 when it does not.

**Fix** — Two parts. (1) Make the seeder write HH:MM like the app does (`_dt(...)[11:16]`). (2) In record_edit, normalise on read (`(rec['check_in'] or '')[-8:][:5]` in the template) and refuse the save rather than zeroing: if the record already had times and the form sends none, flash an error and keep the row. A failing test: assert that POSTing record_edit with check_in='' to a record that had 8.2 hours does not set hours_worked to 0.

*reproduced · edge cases*


### [MAJOR] Correcting a record with the two times swapped silently books a 15-hour day

**Steps** — Manager opens /attendance/records, clicks Edit on a normal 09:00-17:00 / 60-min-break record, and puts 17:00 in Check-In and 09:00 in Check-Out (both are plain <input type="time">, record_edit.html:35 and :39 — nothing stops it). Save.

**Expected** — Rejected, or at minimum flagged, because check-out precedes check-in on a day-shift record.

**Actual** — "Attendance record updated." — and the row now reads hours_worked = 15.0 instead of 7.0. _calc_hours treats any check_out < check_in as an overnight shift and adds 24 hours. Payroll reads hours_worked. Doubling a day of paid hours takes one transposed entry and gives no signal at all.

**Cause** — blueprints/attendance/routes.py:24 `if co < ci: co += timedelta(days=1)` in _calc_hours, applied unconditionally with no shift context — even though record_edit already looked up this employee's assigned shift at routes.py:430 and passes it to the template.

**Fix** — Only apply the midnight rollover when the resolved shift actually crosses midnight (end_time < start_time); otherwise flash an error and do not save. Same guard covers the checkin route's checkout branch at routes.py:294.

*reproduced · edge cases*


### [MAJOR] The monthly attendance report counts status "Leave" — nothing in the app has ever written that string; every leave day is dropped from the per-staff totals

**Steps** — Open /attendance/report for any month containing a day marked On Leave. On the live demo there are 49 such rows (SELECT status, count(*) FROM attendance_records: Present 873, On Leave 49, Absent 46, Late 124). Example day 2026-08-04: 14 records = 10 Present + 3 Late + 1 On Leave.

**Expected** — The per-staff summary cards account for every record in the month.

**Actual** — The report's summary buckets on 'Leave'; every writer in the app writes 'On Leave' (hr_attendance.html:351 dropdown, blueprints/hr/routes.py:1465 `FILTER (WHERE ar.status='On Leave')`, both seeders). So On-Leave days fall through every branch of the if/elif and appear in no column, while their hours are still added to total_hours. For 2026-08-04 the cards show 10+0+3 = 13 of 14 records. Worse, the attendance edit screen's own dropdown (record_edit.html:50) offers 'Leave' and 'Holiday' while the HR screen offers 'On Leave' — two screens writing the same table with incompatible vocabularies, and hr_attendance.html:121 renders a 'Leave' row as Absent.

**Cause** — blueprints/attendance/routes.py:868 `elif st == "Leave": s["leave"] += 1` vs. the 'On Leave' string used everywhere else. Vocabulary set at templates/attendance/record_edit.html:50.

**Fix** — Pick one vocabulary — 'On Leave' is what the data and the rest of the app already use — and change record_edit.html:50 and routes.py:868 to match. Add an `else` branch so an unrecognised status is visibly counted rather than silently swallowed.

*reproduced · edge cases*


### [MAJOR] The attendance dashboard's "Present" tile excludes late arrivals, so the daily numbers never reconcile with head-count

**Steps** — Open /attendance/ (the dashboard the clinic looks at every morning). Live demo, today 2026-08-06: 14 attendance records = 12 Present + 2 Late, 15 active users.

**Expected** — The five tiles account for the staff: Present + Late + On Leave + Absent should be reconcilable against Total Staff.

**Actual** — The tiles read Present 12, Checked In n, On Leave 0, Absent 0, Total Staff 15. The two people who arrived late ARE at work but appear in no tile, so the owner sees three staff unaccounted for and no way to tell whether they are late, absent, or simply have no record. There is no Late tile at all, even though status_for_checkin now actively writes 'Late' (124 rows on the demo).

**Cause** — blueprints/attendance/routes.py:174 counts `status='Present'` only; there is no query for status='Late', and the template templates/attendance/dashboard.html:17-40 has five tiles with no Late among them.

**Fix** — Add a `late` count alongside `present` in routes.py:174 and a sixth tile (or fold Late into Present with a sub-label "n late"). One extra COUNT and one template block.

*reproduced · edge cases*


### [MAJOR] Double-clicking Submit on a leave request creates one request per click and reserves the balance each time

**Steps** — As a nurse with a 21-day balance, fill in /attendance/leaves/new (5-day range) and double- or triple-click Submit Request. Reproduced with 3 identical POSTs.

**Expected** — One request; a repeat submission is ignored or rejected as overlapping.

**Actual** — 3 leave_requests rows, all Pending, all for the same dates, and the balance reads pending 15 of 21 — the employee's available days silently drop by 15 for a week she asked for once. The button is a bare `<button type="submit">` (templates/attendance/leave_form.html:58) with no disable-on-submit, no POST/Redirect/Get token, and no overlap check against existing requests. The manager's queue now shows three identical requests and approving all three charges 15 days.

**Cause** — blueprints/attendance/routes.py:517 — the INSERT runs unconditionally; there is no check for an existing Pending/Approved request over the same dates for the same user.

**Fix** — Before the INSERT, `SELECT 1 FROM leave_requests WHERE user_id=? AND status IN ('Pending','Approved') AND start_date<=? AND end_date>=?` and flash "You already have a request covering those dates." That kills the double-click and genuine overlaps in one guard. Disabling the button on submit is cosmetic on top.

*reproduced · edge cases*


### [MAJOR] A mistyped year in the leave date box is accepted as a 61,051-day request

**Steps** — As a nurse, on /attendance/leaves/new pick a leave type, start 2026-03-01, and in the End Date box type 2260 for the year instead of 2026 (a date input's year spinner accepts any 4 digits). Submit.

**Expected** — Rejected as implausible, or capped.

**Actual** — "Leave request submitted for 61051 day(s). Awaiting approval." The row is stored with days_requested = 61051.0, appears in the manager's pending queue, and if approved sets used = 61051 on the balance and makes the employee show as On Leave on the dashboard for the next 234 years (the dashboard's on_leave query is `start_date<=today AND end_date>=today`). There is no upper bound anywhere on the range.

**Cause** — blueprints/attendance/routes.py:507 `days_req = _business_days(start_date, end_date, conn)` runs on whatever the form sent; only `end_date < start_date` is checked (routes.py:501).

**Fix** — One extra guard next to the existing end<start check: reject if the span exceeds a sane maximum (e.g. 365 days) or if either date is more than a year or two from today. Same guard makes the unbounded loop in _business_days safe.

*reproduced · edge cases*


### [MAJOR] "Insufficient balance" is advisory only, and the overdraft is then made invisible by clamping remaining at zero

**Steps** — Give a nurse a 5-day annual balance. She requests 1 Jun to 31 Jul (/attendance/leaves/new). Manager approves.

**Expected** — Either the request is blocked, or the balance afterwards shows the overdraft.

**Actual** — She is shown TWO contradictory messages in the same page load — "Insufficient balance. Available: 5.0 days." and "Leave request submitted for 45 day(s)." — and the request is created regardless. After approval the balance row reads allocated 5 / used 45 / pending 0 / remaining 0. Because remaining is written with MAX(0, ...), the 40-day overdraft is not visible anywhere; /attendance/balances just shows 0 remaining, the same as a nurse who used exactly her entitlement. HR has no way to see who is over.

**Cause** — blueprints/attendance/routes.py:514 flashes a warning and falls through to the INSERT at :517 with no `return`; leave_approve at routes.py:610 writes `remaining=MAX(0,remaining-?)`.

**Fix** — Decide which it is. Either make the check at :514 blocking (flash + redirect), or drop the MAX(0,...) so remaining can go negative and the balances screen can show the overdraft in red. Doing both — warn and hide — is the only option that helps nobody.

*reproduced · edge cases*


### [MAJOR] Blank or unparseable numbers in the balance and leave-type forms are silently saved as 0, with a success message — the parser's error is thrown away

**Steps** — As HR, open /attendance/balances, click a cell to open Set Balance, clear the Allocated box (or paste something the number input rejects, which a browser submits as empty), and Save. Reproduced by posting allocated="2l" against an existing 21/3/0/18 balance.

**Expected** — "'2l' is not a valid allocated days." and nothing written — which is exactly what money.form_amount returns and what its own docstring says it exists to do ("Silently coercing to 0 would be worse than the crash").

**Actual** — "Balance updated." and the row becomes allocated 0 / used 3 / pending 0 / remaining 0. The employee's entire annual entitlement is wiped and the manager is told it worked. Same pattern in leave_type_save: posting days_per_year="2l" stores 0.0 and flashes "Leave type added." — a leave type that grants nobody any days.

**Cause** — The error return value is discarded at both call sites: blueprints/attendance/routes.py:797-799 `alloc, _ = money.form_amount(...)` (and the same for used/pending) and routes.py:733 `days, _ = money.form_amount(...)`. models/money.py:82 does return the message.

**Fix** — Capture the second value and bail: `alloc, err = money.form_amount(...)` then `if err: flash(err,'error'); return redirect(...)`. Four lines total across both routes. Worth grepping for `, _ = money.form_amount` project-wide — this discard pattern is likely not confined to attendance.

*reproduced · edge cases*


### [MAJOR] Leave spanning a year boundary permanently freezes the employee's pending balance (reserved against this year, released against next year)

**Steps** — LOCAL, Flask test client. Give a user allocated=21, used=0, pending=0, remaining=21 for leave_type Annual, year 2026. Sign in as that user and POST /attendance/leaves/new with start_date=2027-01-04, end_date=2027-01-08. Then sign in as admin and POST /attendance/leaves/<id>/reject with a reason.

**Expected** — After the rejection the balance is back to allocated 21, used 0, pending 0, remaining 21.

**Actual** — After submit: {allocated 21, used 0, pending 5, remaining 21} — reserved on the 2026 row. After reject: identical, pending is still 5. The release UPDATE targeted year=2027, where no row exists, so it changed nothing. The employee's available balance (remaining − pending) is permanently 16 instead of 21, and there is no screen that lets her release it; only a manager hand-editing /attendance/balances can. Approving such a request has the mirror bug: 'used' is added to a non-existent 2027 row while the 2026 pending stays reserved.

**Cause** — blueprints/attendance/routes.py:487 `year = date.today().year` (used for the pending reservation in leave_new) vs routes.py:608 and :637 `yr = date.fromisoformat(req['start_date']).year` (used for the release/deduction in leave_approve / leave_reject).

**Fix** — Use one definition of the balance year in all three routes — the start_date year is the correct one — and store it on the request so approve/reject cannot disagree with submit. Failing test: test_cross_year_leave_release_returns_pending.

*reproduced · happy path*


### [MAJOR] Duplicate / overlapping leave requests are both accepted and both deducted

**Steps** — LOCAL. As an employee with a 21-day Annual balance, POST /attendance/leaves/new twice with the same start_date=2026-10-05 and end_date=2026-10-09. Then sign in as admin and approve both.

**Expected** — The second submission is refused (or at least flagged) as overlapping an existing request for the same dates.

**Actual** — Both are accepted with 'Leave request submitted for 5 day(s)'. pending goes to 10.0. After approving both: used 10.0, remaining 11.0 — ten days charged for one five-day absence. There is no overlap check in leave_new or in leave_approve.

**Cause** — blueprints/attendance/routes.py:491-533 (leave_new) does no overlap query against leave_requests.

**Fix** — Before the INSERT, SELECT any Pending/Approved request for the same user where start_date <= new end_date AND end_date >= new start_date, and refuse with a flash naming the clashing request. Failing test: test_overlapping_leave_request_is_refused.

*reproduced · happy path*


### [MAJOR] Over-drafting a leave balance is warned about, submitted anyway, and then hidden by MAX(0, …)

**Steps** — LOCAL. Employee with allocated 21, used 10, remaining 11. POST /attendance/leaves/new for 2026-11-02 → 2026-12-25 (40 business days). Then approve it as admin.

**Expected** — Either the request is refused, or the resulting balance shows the over-draft so a manager can see it.

**Actual** — Two contradictory flashes on one page: 'Insufficient balance. Available: 11.0 days.' (warning) immediately followed by 'Leave request submitted for 40 day(s). Awaiting approval.' (success). The request is created as Pending. After approval the balance row reads allocated 21, used 50, remaining 0 — the numbers no longer reconcile (21 − 50 is not 0), and the 29-day over-draft is invisible on /attendance/balances, on the leave detail sidebar, and in the leave form's balance panel. Approve also gives no warning at all that the balance is being blown.

**Cause** — blueprints/attendance/routes.py:514-517 flashes but does not return; routes.py:611 `remaining=MAX(0,remaining-?)` clamps the negative away.

**Fix** — Either block the submission (return before the INSERT) or, better, block/warn at approval — the approver is the one authorising the cost — and let remaining go negative so the over-draft is visible. Failing test: test_overdraft_is_refused_or_visible.

*reproduced · happy path*


### [MAJOR] Business-day counting uses a Monday–Friday week in an Egyptian product, so every leave request is charged the wrong number of days

**Steps** — LOCAL. Call _business_days for the Egyptian working week Sun 2026-08-09 → Thu 2026-08-13, and for the Egyptian weekend Fri 2026-08-07 → Sat 2026-08-08. Same arithmetic runs in the leave form's day preview.

**Expected** — Sun–Thu = 5 days charged. Fri–Sat = 0 days charged.

**Actual** — Sun–Thu = 4 (Sunday excluded as 'weekend'). Fri–Sat = 1 (Friday charged as a working day). Every full week of leave under-charges the employee's balance by one day, and anyone taking Friday off is charged for it. The demo is Cairo-time, Arabic-first, EGP; seed_hr.py:235 carries the comment '# skip Fri/Sat (Egyptian weekend = Fri+Sat → use >=4)', so the intended locale is not in doubt.

**Cause** — blueprints/attendance/routes.py:138 `if cur.weekday() < 5`. The browser-side preview in templates/attendance/leave_form.html:131 has the same Sat/Sun assumption (`d.getDay() !== 0 && d.getDay() !== 6`), so the two agree with each other and both disagree with the clinic.

**Fix** — Make the weekend a clinic setting (default Fri+Sat) and read it in both _business_days and the JS preview; the shifts table already carries days_of_week, which is the natural home for it. Failing test: test_business_days_uses_friday_saturday_weekend.

*reproduced · happy path*


### [MAJOR] Editing a record with check-out earlier than check-in saves a 23-hour day and reports success

**Steps** — LOCAL, and the same form is live at /attendance/records → Edit. As admin open /attendance/records/edit/<id> and save check_in=09:00, check_out=08:00, break 0 — the exact result of a manager typing the two times in the wrong boxes.

**Expected** — Rejected with 'Check-out must be after check-in', or at minimum not stored as a full day of overtime.

**Actual** — Saved silently with hours_worked = 23.0 and the flash 'Attendance record updated.' (success). _calc_hours treats any check_out < check_in as a night shift crossing midnight, which is right for a night-shift row and catastrophic for a typo. hours_worked is the column payroll pays on.

**Cause** — blueprints/attendance/routes.py:412 calls _calc_hours with no sanity check; _calc_hours at routes.py:24 unconditionally adds a day when co < ci. record_edit has no validation at all.

**Fix** — Only apply the midnight roll when the employee's shift actually crosses midnight (or when the resulting span is under, say, 14 hours); otherwise reject the edit with a flash. Failing test: test_record_edit_rejects_checkout_before_checkin.

*reproduced · happy path*


### [MAJOR] Late/on-time is judged against the first shift for everyone, so evening and night staff are marked hundreds of minutes late for arriving on time

**Steps** — Create the demo's shifts (Morning 08:00-16:00 id 1, Evening 14:00-22:00 id 2, Night 22:00-06:00 id 3) and roster a night nurse onto shift 3 via staff_shifts — which is exactly what the HR screen writes at blueprints/hr/routes.py:585. Then have them check in through /attendance/checkin at 22:00.

**Expected** — On time. status='Present'.

**Actual** — status_for_checkin returns ('Late', 825). The check-in screen flashes "Checked in at 22:00 — 825 minutes after the shift start" at the nurse. An evening nurse arriving at 14:00 gets ('Late', 345). Every evening and night shift day is a permanently wrong attendance record, and payroll's late_count is built from it. The demo already carries 117 'Late' rows out of 1,078. staff_shifts is read by record_edit (routes.py:429) and shifts_list (routes.py:661) and by payroll (payroll/routes.py:161) — attendance's own status logic is the only place that ignores it.

**Cause** — blueprints/attendance/routes.py:73 `shift = default_shift(conn)`, and default_shift at routes.py:40-42 is `SELECT ... FROM shifts WHERE is_active=1 ORDER BY id LIMIT 1` — clinic-wide, no user_id.

**Fix** — Give default_shift an optional user_id and resolve through staff_shifts first (the same query record_edit already has at routes.py:429-435), falling back to the first active shift only for unrostered staff. status_for_checkin and close_forgotten_checkouts both call it.

*reproduced · money & records*


### [MAJOR] Night and evening staff who forget to clock out are auto-closed at ZERO hours — the exact bug that function exists to prevent

**Steps** — Night nurse rostered on Night Shift (22:00-06:00) checks in at 22:00 on 2026-03-10 and never checks out. The 00:20 scheduler job runs close_forgotten_checkouts.

**Expected** — Closed at their shift end (06:00) with roughly 7 hours worked, stamped recorded_by='system'.

**Actual** — Closed with check_out='22:00', hours_worked=0.0, note "[auto-closed at shift end 22:00; no check-out was recorded]" — the "shift end" it names is their own check-in time. Payroll reads hours_worked and pays them for nothing, which is precisely what the function's docstring (routes.py:83) says it was written to stop. It only works for staff on whichever shift has the lowest id.

**Cause** — blueprints/attendance/routes.py:98 `shift = default_shift(conn)` picks the Morning shift end (16:00) for everyone; routes.py:110 `if _minutes(r["check_in"]) > _minutes(end): end = r["check_in"]` — 22:00 > 16:00 is true, so the safety branch meant for someone arriving after close fires on every night shift.

**Fix** — Same root cause as the Late finding — resolve the shift per user via staff_shifts inside default_shift. That one change fixes both.

*reproduced · money & records*


### [MAJOR] The attendance dashboard's "Present" card excludes Late staff, so nobody who arrived late is counted anywhere

**Steps** — Live demo, 2026-08-05: 11 records status='Present' and 3 status='Late' — 14 people worked. Open /attendance/ (also reproduced locally with 1 Present + 2 Late + 1 Absent).

**Expected** — The headline row accounts for everyone who has a record today.

**Actual** — Present card shows 11. Absent shows 0, On Leave shows 0. The 3 Late staff appear in no card at all — present + absent + on_leave does not reach the headcount, and there is no Late card. A manager glancing at the dashboard to see who is in the building gets a number that is short by however many people hit traffic. /attendance/records does have a separate Late stat; only the dashboard drops them.

**Cause** — blueprints/attendance/routes.py:173-175 `WHERE work_date=? AND status='Present'`. The 'Late' status is now actually assigned (routes.py:65) but this query predates that and was never widened; templates/attendance/dashboard.html:21 has five cards and none of them is Late.

**Fix** — `status IN ('Present','Late')` at routes.py:174, or add a sixth card. Payroll already does the right thing at payroll/routes.py:184 (`status in ("Present","Late")`) — copy that.

*reproduced · money & records*


### [MAJOR] The same leave dates can be requested and approved twice, charging the balance twice for one absence

**Steps** — Employee POSTs /attendance/leaves/new for 2026-09-07..2026-09-11 twice (browser Back then Submit again, a double-click, or deliberately). Manager approves both.

**Expected** — The second request is refused as overlapping, or at least flagged on the approval screen.

**Actual** — Two identical Pending requests are created, both approve cleanly, and the balance goes to used=10, remaining=11 for a single 5-day absence. Nothing in leave_new, leave_detail or leave_approve looks at existing requests for the same dates, and the approval screen shows no sibling requests, so the manager has no way to notice.

**Cause** — blueprints/attendance/routes.py:517 — the INSERT into leave_requests is preceded by a date-order check (routes.py:502) and a balance warning (routes.py:514) but no query for existing Pending/Approved rows overlapping [start_date, end_date] for that user.

**Fix** — One SELECT before the INSERT at routes.py:517: any leave_requests row for this user with status IN ('Pending','Approved') AND start_date <= ? AND end_date >= ? — refuse with the conflicting dates named.

*reproduced · money & records*


### [MAJOR] Leave against a type the employee has no balance row for is recorded as taken but tracked nowhere

**Steps** — Create leave type "Unpaid" with days_per_year=10 and do NOT set a balance for the employee on /attendance/balances (which is the default state — balances are only created by a manager visiting that screen). Employee POSTs /attendance/leaves/new for 2026-05-04..2026-06-30. Manager approves.

**Expected** — A balance row is created from days_per_year and 42 days are recorded against it (or the request is refused).

**Actual** — days_requested=42 is approved and leave_balances has ZERO rows for that user and type. The Balance Matrix shows an empty cell. The employee can do it again next month, indefinitely, and no screen in the product will ever show a number. `_get_or_create_balance` — the helper written for exactly this, at routes.py:143 — is defined and called from nowhere in the codebase.

**Cause** — blueprints/attendance/routes.py:526 `if bal:` guards the pending reservation, and routes.py:609 UPDATEs a row that was never created. routes.py:143 `_get_or_create_balance` is dead code.

**Fix** — Call the existing `_get_or_create_balance(conn, user_id, lt_id, year, lt_row["days_per_year"])` at routes.py:511 instead of the bare SELECT, and drop the `if bal:` guard.

*reproduced · money & records*


### [MAJOR] Leave overdraft is clamped to zero rather than shown, so a manager cannot see that an employee is over their allowance

**Steps** — Employee has allocated=5 for a leave type. POST /attendance/leaves/new for 2026-03-02..2026-04-30 (44 working days). Manager approves.

**Expected** — Either the request is refused, or the Balance Matrix shows the overdraft plainly.

**Actual** — The "Insufficient balance. Available: 5.0 days." message is a `warning` flash that does not stop submission, and nothing at all warns the approver. After approval: {allocated 5, used 44, pending 0, remaining 0}. allocated - used = -39 but `remaining` reads 0 on every screen, because the UPDATE clamps it. The only way to see the overdraft is to mentally subtract two columns.

**Cause** — blueprints/attendance/routes.py:611 `remaining=MAX(0,remaining-?)`; routes.py:514-515 warns without blocking and the approve route (routes.py:595) re-checks nothing.

**Fix** — Drop the MAX(0,...) on remaining so the column can go negative and the number is true, and repeat the balance check on the approve path where the decision is actually made.

*reproduced · money & records*


### [MAJOR] Leave day counting uses the Monday-Friday weekend in an Egypt-market product, so Sunday leave is free and Friday leave is charged

**Steps** — Call the leave form for the dates below (server and demo are both Africa/Cairo; the code comments reference Cairo traffic explicitly). 2026-08-09 is a Sunday, 2026-08-14 a Friday.

**Expected** — For an Egyptian clinic the weekend is Friday+Saturday: Sun 09 -> Thu 13 = 5 days, Fri 14 alone = 0 days, Sun 09 alone = 1 day.

**Actual** — Sun 09 -> Thu 13 (a full Egyptian working week) is charged 4 days. Fri 14 alone is charged 1 day. Sun 09 alone is charged 0 days — the request is created with days_requested=0, is approvable, deducts nothing from the balance and appears in no report as leave. Every full working week of leave costs the clinic a fifth of a week in un-deducted entitlement, and staff are charged for Fridays they were never working.

**Cause** — blueprints/attendance/routes.py:138 `if cur.weekday() < 5` in _business_days — hardcoded Mon-Fri. The `shifts.days_of_week` column exists (populated '1,2,3,4,5' and '6,7' on the demo) and is never read by this function.

**Fix** — Read the working days from shifts.days_of_week, or at minimum make the weekend a config value like LATE_GRACE_MINUTES already is (routes.py:54). Also refuse a request whose computed days_requested is 0.

*reproduced · money & records*


### [MAJOR] HR writes status 'On Leave', Attendance filters and reports on 'Leave' — 49 demo records are invisible, and opening one for edit silently turns it into 'Present'

**Steps** — Live demo as admin: (1) /attendance/records?date_from=2026-01-01&date_to=2026-12-31 and set Status = 'Leave'. (2) /attendance/report?year=2026&month=7 and add up one staff card. (3) Open any 'On Leave' record from the records list, click Edit, then click Save Changes without touching anything.

**Expected** — (1) The 49 leave days appear. (2) Present+Absent+Late+Leave equals the number of records that month. (3) The record keeps its status.

**Actual** — (1) Status='Leave' returns 0 rows; Status filter has no 'On Leave' option; the 49 rows are only reachable by hand-editing the query string. (2) Ali Sobhy's July card reads Present 22 / Absent 1 / Late 3 = 26, but July has ~27 non-Friday days — the 'On Leave' days fall into no bucket and vanish. The route computes a `leave` counter (routes.py:868) that report.html never renders at all. (3) The edit form's status dropdown offers ['Present','Late','Absent','Leave','Holiday']; with rec.status='On Leave' no option carries `selected`, so the browser shows and submits 'Present' — the leave day becomes a present day with 0 hours.

**Cause** — blueprints/hr/routes.py:1576 and templates/hr/hr_attendance.html:351 write 'On Leave'; blueprints/attendance/routes.py:868 and templates/attendance/records_list.html:41 and record_edit.html:49 use 'Leave'. Seed writes 'On Leave' (scripts/seed/demo_showcase.py:1154).

**Fix** — Pick one spelling (HR's 'On Leave' is what is already in the data), use it in both blueprints' status lists, and add a `Leave`/`On Leave` tile to report.html so the bucket the route already counts is actually shown. A one-line data fix for existing rows if you standardise on 'Leave'.

*reproduced · happy path*


### [MAJOR] A record with no check-in locks the employee out of clocking in for the whole day, and both flash messages lie about why

**Steps** — HR marks someone Absent for today from /hr/attendance (that route inserts an attendance_records row with status='Absent' and check_in NULL). The person then turns up at 11:00, signs in, goes to /attendance/checkin and clicks 'Check In Now'. Then clicks 'Check Out Now'.

**Expected** — Check In records an 11:00 arrival and overwrites the provisional Absent.

**Actual** — Check In -> flash "Already checked in today." and nothing is written. The page then renders the green 'Checked In' card with "Since " and a blank time, so Check Out is the only button offered — and Check Out -> flash "No check-in record found for today." The employee can never clock in. Record stays `{'status': 'Absent', 'check_in': None, 'check_out': None, 'hours_worked': 0.0}` and payroll pays zero for a day worked. The same trap fires on any pre-created row: the seed itself creates check_in-NULL rows for Absent and On Leave days.

**Cause** — blueprints/attendance/routes.py:264 — `if rec:` treats any existing row as a check-in. routes.py:288 (`if not rec or not rec["check_in"]`) already has the right test for the other branch. templates/attendance/checkin.html:37 branches on `my_record` / `my_record.check_out`, never on check_in.

**Fix** — routes.py:264 -> `if rec and rec["check_in"]:` and UPDATE the existing row's check_in/status instead of INSERTing; checkin.html:37 -> `{% if not my_record or not my_record.check_in %}` so the correct card is shown.

*reproduced · happy path*


### [MAJOR] Over-balance leave is waved through, with two contradictory flash messages on the same screen

**Steps** — Give a nurse Annual Leave allocated=21, used=0, pending=0 via /attendance/balances. As that nurse, /attendance/leaves/new -> Annual Leave -> a range covering 87 business days -> Submit. Then approve it as HR.

**Expected** — The request is blocked, or at minimum the employee is told clearly that it will not be granted.

**Actual** — Both flashes render together: "Insufficient balance. Available: 21.0 days." AND "Leave request submitted for 87 day(s). Awaiting approval." The request is created. leave_balances becomes allocated=21, pending=87 — a pending reservation four times the allowance, which the balances matrix then displays as a real number. On approval: used=87, pending=0, remaining silently clamps to 0 (MAX(0,...)). Nothing anywhere records that 66 days were taken beyond entitlement.

**Cause** — blueprints/attendance/routes.py:514-516 flashes a warning and then falls through to the INSERT at :517 regardless; routes.py:611 uses MAX(0, remaining-?) which hides the overdraft.

**Fix** — Return to the form on insufficient balance (the same early-return shape already used at :502 for a bad date range), or require an explicit manager override flag. Let remaining go negative, or record the overdraft, rather than clamping it to 0.

*reproduced · happy path*


### [MAJOR] The manager's "Record Attendance for Staff" panel has no time field, so every record it makes is stamped 'Late', and the Break box on it is silently discarded

**Steps** — Sign in as hr.marwa (or admin), /attendance/checkin, use the 'Record Attendance for Staff' card on the right: pick a doctor, Action = Check In, Break (min) = 60, Notes = 'arrived 08:00', click Record. (Done at 15:39 in the reproduction — i.e. any time reception catches up on the morning's arrivals.)

**Expected** — Either a time field so the manager can enter the real arrival, or at least the break they typed being saved.

**Actual** — check_in is forced to `datetime.now()` — 15:39 — and status becomes 'Late' with a flash reading "Checked in at 15:39 - 444 minutes after the shift start (grace 15 min)" (phrased as if the manager checked themselves in). The record saves `break_minutes: 0` despite 60 being posted, because the INSERT at routes.py:269-276 does not include the column the form sends. Every retro-entered arrival is wrong on both time and status, and the manager has to open record_edit for each one to fix it.

**Cause** — blueprints/attendance/routes.py:242 (`now`) is used unconditionally at :276; break_min is read at :257 and only used on the checkout branch (:293). templates/attendance/checkin.html:99 offers Break on a form whose default action is Check In.

**Fix** — Add a time input to the manager panel (default `now`) and honour it in the INSERT; include break_minutes in the INSERT column list. If a time field is not wanted, drop the Break box from the check-in form so it stops promising something it discards.

*reproduced · happy path*


### [MAJOR] Attendance dashboard has no 'Late' tile and its 'Present' count excludes late arrivals, so late staff appear nowhere on the owner's first screen

**Steps** — Two staff work today, one clocks in 08:00 (Present) and one 08:40 (Late). Open /attendance/ as admin.

**Expected** — The top row accounts for both people who are at work.

**Actual** — Present 1, Checked In 0, On Leave 0, Absent 0, Total Staff 3. There is no Late card in the five-tile row at all, so the second person is in none of them. On the live demo 117 of 1078 attendance records are 'Late' — roughly one in nine working days is unaccounted for on the dashboard. The records list (records_list.html:57) does show a Late tile, so the two screens disagree.

**Cause** — blueprints/attendance/routes.py:173 counts only `status='Present'`; templates/attendance/dashboard.html:17-45 has five tiles and none of them is Late. This became live when status_for_checkin (routes.py:65) started actually assigning 'Late'.

**Fix** — Either count Present as `status IN ('Present','Late')` and add a separate Late tile, or add a sixth tile. The records screen's four-tile layout is the model.

*reproduced · happy path*


### [MAJOR] Approving leave deducts nothing when the employee has no balance row — the default state

**Steps** — Live demo: /attendance/balances shows Emergency, Maternity, Study and Unpaid Leave as "—  اضغط للتعيين" (click to set) for all 15 staff. /attendance/report?year=2026&month=7 lists an APPROVED leave: Dalia Serag, Emergency Leave, 2026-07-23 → 2026-07-25, 3.0 days. Go back to /attendance/balances — Dalia's Emergency cell is still "—". Reproduced locally: create a user with no leave_balances row, submit a 5-day request, approve it as a manager. Request status becomes Approved; `SELECT * FROM leave_balances WHERE user_id=?` returns [].

**Expected** — Approving 3 days of Emergency Leave reduces that employee's Emergency entitlement by 3, whether or not a manager pre-seeded the row.

**Actual** — leave_new only reserves pending `if bal:` (routes.py:526) and leave_approve's UPDATE matches zero rows (routes.py:609). No row exists, so nothing is written. The leave form keeps showing "Remaining: 3.0d" forever and the balances matrix stays blank. Staff can take unlimited leave of any type nobody explicitly allocated. `_get_or_create_balance` (routes.py:143) — the helper written for exactly this — is dead code, referenced nowhere but its own definition.

**Cause** — blueprints/attendance/routes.py:143 (_get_or_create_balance, never called), :511-529 (leave_new), :609 (leave_approve)

**Fix** — Call `_get_or_create_balance(conn, user_id, lt_id, year, lt_row['days_per_year'])` at the top of leave_new's POST branch and again in leave_approve/leave_reject before the UPDATE. Failing test: `test_approve_leave_creates_and_deducts_balance` — user with no balance row, submit 5 days, approve, assert leave_balances.used == 5.

*reproduced · edge cases*


### [MAJOR] Leave requests are never blocked by an insufficient balance — only warned, and the overdraft is then hidden

**Steps** — Local: give a user a 5-day allocation of a leave type, then submit a request for 2026-02-02 → 2026-03-31 (42 business days). Approve it as a manager.

**Expected** — The request is refused, or at minimum the balance afterwards shows the employee is 37 days over.

**Actual** — Two contradictory flashes appear together — "Insufficient balance. Available: 5.0 days." (warning) and "Leave request submitted for 42 day(s)." (success) — and the row is created with pending=42 against allocated=5. On approval the balance becomes used=42, remaining=MAX(0, 5-42)=0, so the overdraft is clamped away and the balances screen reports a tidy 0 rather than -37. Separately, a date-picker slip is uncapped: 1900-01-01 → 2099-12-31 is accepted and stored as days_requested = 52179.

**Cause** — blueprints/attendance/routes.py:514-517 (warns then falls through to the INSERT), :611 (MAX(0, remaining-?))

**Fix** — Make the insufficient-balance branch return instead of falling through, and drop the MAX(0,…) clamps so an over-allocation is visible if it ever happens. Also cap days_requested (e.g. refuse a range over 365 days). Failing test: `test_leave_over_balance_is_rejected`.

*reproduced · edge cases*


### [MAJOR] The attendance dashboard counts a late arrival nowhere — "Present" reads 0 while someone is standing there

**Steps** — Live demo: log in as nurse.mariam / Demo@1234, go to /attendance/checkin, press "Check In Now" (any time after 08:15 gets status Late). Then open /attendance/ as admin.

**Expected** — Someone who arrived, late or not, is counted somewhere on the daily summary.

**Actual** — Reproduced live at 15:53 Cairo: the today's-records table on the dashboard shows "Mariam Adly · nurse · 15:53 · 15:54 · متأخر", and directly above it every card reads 0 — حاضر (Present) 0, تم الوصول (Checked In) 0, في إجازة 0, غائب 0. The dashboard counts only `status='Present'` and has no Late card at all, so on a normal morning with 5 of 15 staff late the manager's headline number is 10 when 15 people are at work. The Late status was added deliberately by status_for_checkin (routes.py:65) and no screen was taught to count it.

**Cause** — blueprints/attendance/routes.py:173-178 (present/absent queries) and templates/attendance/dashboard.html:20-42 (five cards, none for Late)

**Fix** — Either count Late into `present` (`status IN ('Present','Late')`) or add a sixth card. Failing test: seed one Present + one Late record for today, assert the dashboard's Present card is 2 or that a Late card shows 1.

*reproduced · edge cases*


### [MAJOR] Leave day-counting uses a Monday–Friday week in an Egyptian product whose weekend is Friday–Saturday

**Steps** — Local: `from blueprints.attendance.routes import _business_days` — _business_days('2026-05-01','2026-05-01') (a Friday) = 1; ('2026-05-02','2026-05-02') (Saturday) = 0; ('2026-05-03','2026-05-03') (Sunday) = 0.

**Expected** — In Cairo, Friday and Saturday are the weekend and Sunday is a working day, so Friday should count 0 and Sunday 1.

**Actual** — Exactly inverted. An employee who books Sunday–Thursday (the real Egyptian work week, 5 working days) is charged 4 days. An employee who books the Friday–Saturday weekend — no working days at all — is charged 1 day. The app's own demo seeder agrees the weekend is Friday (scripts/seed/demo_showcase.py: `if day.weekday() == 4: continue`) while the leave arithmetic says Saturday–Sunday; the two halves of the same product disagree about which days people work. Every leave request in the system is mis-costed against the employee's entitlement.

**Cause** — blueprints/attendance/routes.py:138 `if cur.weekday() < 5` (the comment above it, "Sat=6, Sun=0 depending on locale", is not what Python's weekday() returns)

**Fix** — `if cur.weekday() not in WEEKEND` with WEEKEND = {4, 5} for Fri+Sat, ideally read from a clinic setting alongside the shifts screen. Failing test: `test_business_days_skips_friday_and_saturday` — assert _business_days over a Sun–Thu span is 5 and over a Fri–Sat span is 0.

*reproduced · edge cases*


### [MAJOR] A leave request that starts next year permanently freezes days out of this year's balance

**Steps** — Local: give a user a 21-day balance for both 2026 and 2027. In 2026, submit a request for 2027-01-05 → 2027-01-09 (4 business days). A manager approves it. Inspect leave_balances.

**Expected** — The 4 days move from pending to used in the 2027 row; the 2026 row is untouched.

**Actual** — After submit: 2026 row pending=4 (wrong year), 2027 row pending=0. After approve: 2026 row still pending=4 forever, 2027 row used=4 remaining=17. The 2026 pending is never released by anything, and leave_new's own availability check is `remaining - pending`, so the employee is silently short 4 days of 2026 entitlement for the rest of the year with no request to explain it. A rejection has the same split (reject also releases against the start-date year).

**Cause** — blueprints/attendance/routes.py:487 `year = date.today().year` used for the pending reservation vs :608 / :637 `yr = date.fromisoformat(req['start_date']).year` used for the deduction/release

**Fix** — Use the start-date year in leave_new too. Failing test: `test_next_year_leave_reserves_pending_on_the_right_year`.

*reproduced · edge cases*


### [MAJOR] Double-clicking Submit on the leave form files the same request twice and reserves double the days

**Steps** — Local (and any browser — the form has no submit guard and the route has no idempotency check): open /attendance/leaves/new, fill leave type + 2026-06-01 → 2026-06-05, click Submit twice (or click once, press Back, and click again).

**Expected** — One request. The second attempt is rejected as a duplicate, or at worst does not double-charge the balance.

**Actual** — Two identical Pending rows for 2026-06-01 → 2026-06-05, and leave_balances.pending = 10 for one 5-day absence. The employee's available balance (remaining - pending) drops by 10; if the manager approves both, used becomes 10. Nothing on the leaves list marks them as duplicates.

**Cause** — blueprints/attendance/routes.py:517-530 — unconditional INSERT plus an unconditional `pending = pending + days`

**Fix** — Before the INSERT, reject an existing Pending/Approved request for the same user + leave type with an overlapping date range. Failing test: `test_duplicate_leave_submission_is_rejected`.

*reproduced · edge cases*


### [MAJOR] Swapping the two time fields when correcting a record silently records a 16-hour day

**Steps** — Local and via the UI: /attendance/records → Edit any record → type 17:00 in "Check In Time" and 09:00 in "Check Out Time", break 0 → Save Changes.

**Expected** — Refused, or at least flagged — a check-out before the check-in on a day shift is a typo, not a shift.

**Actual** — "Attendance record updated." and hours_worked = 16.0. _calc_hours treats any check_out < check_in as a night shift crossing midnight, so a transposition on the edit screen books eight extra paid hours with a success message. The same code also means break_minutes < 0 invents hours (`_calc_hours('09:00','17:00',-600)` = 18.0), though the form's min="0" blocks that from a browser.

**Cause** — blueprints/attendance/routes.py:24-25 (the unconditional midnight rollover) called from :412

**Fix** — Only roll over midnight when the record's shift actually crosses midnight (record_edit already resolves the shift at :429 for display), otherwise flash "check-out is before check-in" and do not save. Failing test: `test_record_edit_rejects_checkout_before_checkin_on_a_day_shift`.

*reproduced · edge cases*


### [MAJOR] The monthly attendance report's per-staff totals do not add up — leave days are counted in no bucket

**Steps** — Live demo: /attendance/report?year=2026&month=7. Read Dalia Serag's summary card, then count her rows in the "Daily Records" table below it on the same page.

**Expected** — Present + Absent + Late (+ Leave) equals the number of days listed for her.

**Actual** — Card says Present 18 / Absent 1 / Late 5 = 24, but the table below lists 26 days for her. Same gap for Dr. Hossam (25 vs 26), Dr. Nourhan (24 vs 26), Dr. Mostafa (25 vs 26). The route buckets on `st == 'Leave'` while the data holds 'On Leave', so those days land nowhere — and the template never renders `s.leave` even when it is populated. A manager reconciling this report against payroll cannot make it balance and has no clue which days are missing.

**Cause** — blueprints/attendance/routes.py:865-868 (the if/elif chain has no else) and templates/attendance/report.html:56-72 (four tiles, no Leave tile)

**Fix** — Add an `else: s['other'] += 1` bucket, normalise 'On Leave'/'Leave' to one spelling in the seeder and the status list, and render Leave/Other on the card. Failing test: assert present+absent+late+leave+other == len(records) for every user in the summary.

*reproduced · edge cases*


### [MAJOR] Opening an "On Leave" record in the edit screen preselects "Present" — saving turns a leave day into a worked day

**Steps** — Live demo: /attendance/records/edit/5780 (an 'On Leave' record; find one on /attendance/records?date_from=2026-07-01&date_to=2026-07-31, its status column reads the untranslated "On Leave"). Look at the Status dropdown.

**Expected** — The dropdown shows the record's current status.

**Actual** — No option carries `selected` — the served HTML is `<option value="Present" >…<option value="Late" >…<option value="Absent" >…<option value="Leave" >…<option value="Holiday" >` — so the browser displays the first option, "Present". A manager opening the record to add a note and pressing Save silently converts an unpaid/paid leave day into a present day. The same rows also render "On Leave" in raw English on the Arabic records list while every other status is translated, because the badge if/elif has no case for it.

**Cause** — templates/attendance/record_edit.html:49-52 (hard-coded list ['Present','Late','Absent','Leave','Holiday']) and templates/attendance/records_list.html / report.html badge chains

**Fix** — Prepend the record's own status to the option list when it is not in the standard set (or normalise 'On Leave' → 'Leave' everywhere, including the seeder). Failing test: assert the edit page for a record with any status contains that status marked `selected`.

*reproduced · edge cases*


### [MINOR] Rejecting a leave request that was approved by mistake does nothing and says nothing

**Steps** — Manager approves a request, realises it was the wrong one, opens /attendance/leaves/<id> and clicks Reject with a reason.

**Expected** — Either the rejection is applied (and the balance unwound), or the manager is told why it cannot be.

**Actual** — The page reloads showing status Approved, with no flash message of any kind. Reproduced: status after reject = 'Approved', no flash in the response body. The manager clicks again, gets the same nothing, and has no route out except editing the database. The mirror case (approving an already-rejected request) behaves the same way.

**Cause** — blueprints/attendance/routes.py:628 `if req and req["status"] == "Pending":` — the else path falls straight through to the redirect with no flash. Same shape in leave_approve at routes.py:600.

**Fix** — Add an else that flashes "This request is already <status> and cannot be changed." If un-approving is a real need, that is a separate route that also reverses the balance.

*reproduced · edge cases*


### [MINOR] Unvalidated int() on query and form parameters returns a 500 page on ten routes

**Steps** — Hit any of these while logged in as a manager (a stale bookmark, a hand-edited URL, or an integration): /attendance/report?year=abc&month=1 · ?year=2026&month=13 · ?month=0 · ?month= · ?year=0 · ?year=99999 · /attendance/balances?year=abc · /attendance/balances?year= · /attendance/holidays?year=abc. Form side: POST /attendance/records/edit/<id> with break_minutes=abc, and POST /attendance/shifts/save with break_minutes=abc.

**Expected** — The bad value is ignored or reported; the page renders.

**Actual** — 500. `ValueError: invalid literal for int() with base 10: 'abc'` and `ValueError: month must be in 1..12, not 13`. Reproduced on all eleven. The year/month values come from <select> boxes so a normal click cannot reach them, which is why this is minor rather than major — but the form-field cases (break_minutes) sit behind number inputs whose min/max a non-browser client ignores entirely, and any of these is a 500 in the log rather than a handled input.

**Cause** — blueprints/attendance/routes.py:829-830 (report year/month), :761 (balances year), :906 (holidays year), :410 (record_edit break_minutes), :686 (shift_save break_minutes), :258 (checkin break_minutes). All bare `int(...)`. Note Arabic-Indic digits (٢٠٢٦, ٦٠) DO work — int() handles them — so that is not the gap.

**Fix** — One small helper — `def _int(raw, default): try: return int(raw) except (TypeError, ValueError): return default` — at each of the six sites, plus clamping month to 1..12 before date(year, month, 1).

*reproduced · edge cases*


### [MINOR] Three write paths report success when nothing was written

**Steps** — (a) POST /attendance/shifts/save with shift_id=999999 and a name. (b) POST /attendance/holidays/999999/delete. (c) POST /attendance/records/edit/999999.

**Expected** — "Not found", or at least no success message.

**Actual** — (a) "Shift updated." — the UPDATE matched no row and no shift named Ghost exists. (b) "Holiday removed." — nothing was removed. (c) correctly says "Record not found" (this one is right). Cases (a) and (b) are reachable in practice through a stale tab: open the shifts screen, delete the shift in another tab, then save the first tab — you are told it saved.

**Cause** — blueprints/attendance/routes.py:697 and :963 — the flash is unconditional and the cursor rowcount is never inspected.

**Fix** — Check rowcount after the UPDATE/DELETE and flash "That record no longer exists" when it is 0.

*reproduced · edge cases*


### [MINOR] Leave day-counting uses the Western weekend, so an Egyptian clinic charges the wrong number of days for every request

**Steps** — Request leave for Sunday 2026-03-08 to Thursday 2026-03-12 — a full working week in Egypt. Then request Friday 2026-03-06 to Saturday 2026-03-07 — the Egyptian weekend, zero working days.

**Expected** — 5 days charged for the working week, 0 for the weekend.

**Actual** — 4 and 1 respectively. _business_days excludes Saturday and Sunday (`cur.weekday() < 5`), but this app is explicitly Egyptian — Cairo re-seed schedule, EGP, Arabic throughout — where the weekend is Friday-Saturday and Sunday is a working day. Every leave request is off by roughly one day per week: staff are undercharged for the weeks they take off and charged for Fridays they were never going to work. The helper's own docstring at routes.py:128 hedges "(Sat=6, Sun=0 depending on locale)", which is wrong about Python too (Sat=5, Sun=6). There is no weekend setting anywhere in the codebase.

**Cause** — blueprints/attendance/routes.py:138 `if cur.weekday() < 5`.

**Fix** — The shifts table already carries days_of_week (routes.py:688 writes it). Derive the working days from the active shift, or add a clinic setting with a Fri/Sat default. Hard-coding weekday() < 5 is the only thing that needs to change in _business_days.

*reproduced · edge cases*


### [MINOR] /attendance/api/today returns every employee's check-in, check-out and hours to any logged-in user

**Steps** — Log in as a nurse (no manager role) and GET /attendance/api/today.

**Expected** — The same restriction /attendance/records applies — a non-manager sees only their own row.

**Actual** — JSON containing every staff member's full_name, check_in, check_out, status and hours_worked. Reproduced: the nurse's /attendance/records page correctly hid the manager's row, while the JSON endpoint returned both. In a clinic where hours drive pay, staff being able to read each other's clock times is an HR problem. No template or script in the codebase consumes this endpoint (the only /api/today reference is workflow's own, at templates/workflow/index.html:1385), so restricting it breaks nothing.

**Cause** — blueprints/attendance/routes.py:1019 — `@login_required` only, with no _allowed_manager gate and no user_id filter, unlike records_list at routes.py:344 and report at routes.py:831 which both get it right.

**Fix** — Add the same three lines records_list uses: if not _allowed_manager(user), append `AND ar.user_id=?` with the session user's id.

*reproduced · edge cases*


### [MINOR] The clinic-wide shift accepts an end before its start and a negative break, and that shift drives lateness and auto-close for everyone

**Steps** — As a manager, POST /attendance/shifts/save with start_time=17:00, end_time=09:00, break_minutes=-120.

**Expected** — Rejected.

**Actual** — "Shift updated." and the row stores ('17:00','09:00',-120). Because default_shift feeds status_for_checkin and close_forgotten_checkouts, a negative break there ADDS two hours to every auto-closed record in the clinic. Confirmed separately that a negative break inflates hours directly: editing a 09:00-17:00 record with break_minutes=-600 stored hours_worked = 18.0 for an eight-hour day, and 1000000 stored hours_worked = 0.0 — both saved with "Attendance record updated." The record-edit form carries min=0 max=480 so a browser blocks it, but shift_save's own break field (shifts.html:97) has no server-side check at all and the time inputs have none in either place.

**Cause** — blueprints/attendance/routes.py:686-688 — no validation between start_time/end_time and no lower bound on break_minutes; blueprints/attendance/routes.py:26 clamps only the upper side (`max(0, mins/60)`).

**Fix** — Clamp break_minutes to 0..600 server-side in shift_save (:686), record_edit (:410) and checkin (:258) — one shared helper — and reject end_time == start_time. Overnight shifts are legitimate so end < start must stay allowed for shifts, but then _calc_hours needs to know about it (see the swapped-times finding).

*reproduced · edge cases*


### [MINOR] Attendance dashboard headline cards do not count Late staff, so the numbers do not add up

**Steps** — LIVE DEMO right now. Sign in as admin, open /attendance/.

**Expected** — The five cards account for the staff who are in the clinic today.

**Actual** — Cards read Present 12, Checked In 0, On Leave 0, Absent 0, Total Staff 15. The table directly underneath lists 14 records for today: 12 Present and 2 Late. The two late arrivals are counted in no card at all, and a manager scanning the top row cannot tell whether 3 people are missing or 1. 'Absent' is also permanently 0 — nothing in the codebase ever writes status='Absent' except a manual record edit.

**Cause** — blueprints/attendance/routes.py:173-178 — `present` counts only status='Present'; there is no Late count and no Late card in templates/attendance/dashboard.html:17-43.

**Fix** — Add a Late card (the report page already has one) and either count Late inside Present or label the card 'On time'. Failing test: test_dashboard_counts_late_arrivals.

*reproduced · happy path*


### [MINOR] 'Export Excel' on the records screen ignores the status filter you just applied

**Steps** — LIVE DEMO. /attendance/records?status=Late&date_from=2026-02-01&date_to=2026-08-06 shows 124 rows. Click 'Export Excel'.

**Expected** — A spreadsheet with the 124 Late rows you are looking at.

**Actual** — A spreadsheet with every status in the range (873 Present + 124 Late + 46 Absent). The export link carries date_from, date_to and user_id but not status, and the route never reads it — so the file silently disagrees with the screen it was exported from.

**Cause** — templates/attendance/records_list.html:8 builds the URL without `status`; blueprints/attendance/routes.py:973-989 (export_xlsx) never reads request.args['status'].

**Fix** — Add status to both the link and the query. One line each. Failing test: test_export_respects_status_filter.

*reproduced · happy path*


### [MINOR] The manager check-in panel has a Break field that is silently thrown away on check-in

**Steps** — LIVE/LOCAL. As a manager on /attendance/checkin, use the 'Record Attendance for Staff' panel: pick a staff member, Action = Check In, Break (min) = 30, click Record.

**Expected** — Either the 30 minutes is stored, or the field is hidden/disabled for the Check In action.

**Actual** — Flash says the check-in was recorded; break_minutes on the row is 0. The value is parsed into a variable and never written — only the checkout branch stores it. The manager has no way to know it was dropped.

**Cause** — blueprints/attendance/routes.py:257 reads break_min, and the INSERT at :269-276 does not include the column. templates/attendance/checkin.html:101-104 shows the field for both actions.

**Fix** — Include break_minutes in the check-in INSERT, or hide the field unless Action = Check Out.

*reproduced · happy path*


### [MINOR] Editing any shift silently deletes Sunday from its working days

**Steps** — LIVE DEMO. /attendance/shifts — the Night Shift row renders its days as 'Mon Tue Wed Thu Fri Sat 7'. Click Edit on it, change nothing, click Update Shift.

**Expected** — days_of_week comes back as it went in, '1,2,3,4,5,6,7'.

**Actual** — It is saved as '1,2,3,4,5,6' — Sunday is gone, with no warning. The seeded data encodes Sunday as 7; the checkbox row is [(1,Mon)…(6,Sat),(0,Sun)], so the edit JS `dayArr.includes(cb.value)` finds no checkbox for '7' and leaves Sunday unchecked. That is also why the table prints a bare '7' where a day name should be. Separately, the 'Add Shift' defaults pre-check `val < 6`, which includes Sunday(0) — a new shift starts with six days ticked, not five.

**Cause** — templates/attendance/shifts.html:24 (day_names maps 0→Sun, nothing maps 7), :104 (`{% if val < 6 %}checked`), :144 (`cb.checked = dayArr.includes(cb.value)`), against data seeded with 7 for Sunday.

**Fix** — Pick one encoding for Sunday (0 or 7) and normalise on read and on save. Low blast radius today because nothing in the attendance logic actually reads days_of_week — but the shifts screen is where a manager believes they are setting it.

*reproduced · happy path*


### [MINOR] Status 'Holiday' can be set on a record and is then counted in none of the monthly report's tiles

**Steps** — As a manager, /attendance/records/edit/<id>, set Status = Holiday, Save. Open /attendance/report for that month.

**Expected** — The day shows up somewhere in that staff member's summary.

**Actual** — The per-staff summary card counts only Present / Absent / Late / Total Hrs; a 'Holiday' row is tallied in none of them. The row still appears in the Daily Records table with a plain grey badge, so the summary and the detail disagree. Same for any other status a future edit introduces.

**Cause** — blueprints/attendance/routes.py:864-869 has branches for Present/Absent/Late/Leave only; templates/attendance/record_edit.html:50 offers five statuses including Holiday.

**Fix** — Either drop Holiday from the dropdown or add it (and 'Leave', which is also collected but not shown) to the report's summary cards.

*reproduced · happy path*


### [MINOR] Employees cannot file a leave request for days that have already passed

**Steps** — As any staff member, open /attendance/leaves/new the morning after two days off sick and try to enter last Sunday's date.

**Expected** — Sick leave is retroactive by nature — you file it when you get back.

**Actual** — Both date inputs carry min="{{ today }}", so the browser refuses any past date. The server would accept it, but there is no route through the UI: leave_new always files against session['user'], so a manager cannot enter it on the employee's behalf either. The clinic's only option is for HR to hand-edit the balance on /attendance/balances, which leaves no leave record at all.

**Cause** — templates/attendance/leave_form.html:38 and :44 (`min="{{ today }}"`); blueprints/attendance/routes.py:522 hardcodes user['id'] as the requester.

**Fix** — Drop the min= on start_date (the server already rejects end < start), or add a manager 'file on behalf of' path the way the check-in screen already has one.

*reproduced · happy path*


### [MINOR] Non-numeric or out-of-range year/month in the URL returns a 500 instead of falling back

**Steps** — As admin: GET /attendance/report?month=13&year=2026, /attendance/report?month=abc, /attendance/balances?year=abc, /attendance/holidays?year=abc.

**Expected** — The page renders with the current month/year, or a flash saying the value was ignored.

**Actual** — Uncaught ValueError → 500 error page ('month must be in 1..12, not 13' / "invalid literal for int() with base 10: 'abc'"). Only reachable by hand-editing the URL or following a stale bookmark — the dropdowns are constrained — which is why this is minor and not major.

**Cause** — blueprints/attendance/routes.py:831-832, :765, :910 — bare int(request.args.get(...)) and date(year, month, 1) with no guard.

**Fix** — One small helper that coerces with a default, used at all four call sites.

*reproduced · happy path*


### [MINOR] The Excel export ignores the status filter shown on screen, so the downloaded file has rows the page did not

**Steps** — Two records: 2026-03-02 Present, 2026-03-03 Absent. Open /attendance/records?date_from=2026-03-01&date_to=2026-03-31&status=Present — page lists 03-02 only. Click Export (which carries the same query string).

**Expected** — The file matches what was on screen.

**Actual** — The .xlsx contains both 2026-03-02 and 2026-03-03. Anyone exporting a filtered view to send to an accountant sends a different dataset than they reviewed.

**Cause** — blueprints/attendance/routes.py:971-989 — export_xlsx reads date_from, date_to and user_id from the query string but never `status`, while records_list (routes.py:359-361) does.

**Fix** — Add the same three lines export_xlsx already has for user_id: read `status` and append `AND ar.status=?`.

*reproduced · money & records*


### [MINOR] The 'Remaining' days an employee is shown ignores their own pending requests

**Steps** — As a nurse with Annual Leave allocated 21, used 0: submit a 15-day request. Then open /attendance/ and /attendance/leaves/new.

**Expected** — Something under 21 — the employee has 15 days already in flight.

**Actual** — The dashboard's 'My Leave Balances' card and the leave form's balance panel both print 21.0d, because they render `remaining` and only `pending` was incremented. The insufficient-balance check inside leave_new uses `remaining - pending` correctly, so the number shown to the employee and the number the server enforces disagree — she is told she has 21 days and then told she has 6.

**Cause** — leave_new increments only pending (blueprints/attendance/routes.py:527-529); dashboard.html:110 and leave_form.html:88 display `b.remaining`.

**Fix** — Display `remaining - pending` (or show pending alongside it) in dashboard.html and leave_form.html — leave_detail.html:130 already lists Allocated/Used/Pending/Remaining separately and reads correctly.

*reproduced · happy path*


### [MINOR] Editing a shift silently drops Sunday from its working days

**Steps** — As admin, /attendance/shifts. The seeded 'Weekend Morning' shift stores days_of_week '6,7'. Click Edit on it, change nothing, click Update Shift.

**Expected** — days_of_week stays '6,7'.

**Actual** — It becomes '6'. The day checkboxes are numbered [(1,'Mon')...(6,'Sat'),(0,'Sun')], so the JS `dayArr.includes(cb.value)` never matches the stored '7' and Sunday comes back unticked. The list column also renders a bare '7' chip because its day_names map has no key 7. Any shift whose days were seeded or entered with 7-for-Sunday loses that day the first time anyone opens the edit form.

**Cause** — templates/attendance/shifts.html:23 (day_names has 0:'Sun', no 7) and shifts.html:101 (checkbox values 1..6,0) versus the seeded '6,7' in scripts/seed/demo_showcase.py.

**Fix** — Pick one numbering. Either use 7 for Sunday in the checkbox list and the day_names map, or normalise 7->0 in shift_save (routes.py:687).

*reproduced · happy path*


### [MINOR] A manager's correction to an attendance record is attributed to the employee, and is not audit-logged

**Steps** — A record exists with check_in 08:05, check_out 16:00, hours 7.9, recorded_by 'vet.ali'. As admin, /attendance/records/edit/<id>, change Check Out to 20:00, Save Changes.

**Expected** — The record shows who actually changed it — three extra paid hours is exactly the number someone will dispute.

**Actual** — hours_worked becomes 11.0 and recorded_by is still 'vet.ali'. The record now asserts the employee themselves recorded 11 hours. No audit_log row is written either — blueprints/attendance/routes.py imports nothing from the audit layer, while blueprints/hr/routes.py calls db.log_audit at :590, :790, :830 for comparable edits. close_forgotten_checkouts (routes.py:113-122) deliberately stamps recorded_by='system' and annotates notes for exactly this reason; record_edit does neither.

**Cause** — blueprints/attendance/routes.py:413-418 — the UPDATE sets check_in/check_out/status/break/hours/notes/updated_at and leaves recorded_by alone.

**Fix** — Add `recorded_by=?` with session['user']['username'] to that UPDATE, and a db.log_audit call alongside it.

*reproduced · happy path*


### [MINOR] The Public Holidays screen is not linked from anywhere, and the demo has zero holidays — so Eid is charged against annual leave

**Steps** — Sign in as hr.marwa on the live demo and try to reach the public holidays screen from any page: sidebar, attendance dashboard, its four manager quick-link cards, balances, shifts, leave types. Then go directly to https://demo.aleefy.online/attendance/holidays.

**Expected** — A link somewhere, since holidays are subtracted from every leave request.

**Actual** — No template in the repo references `attendance.holidays` — the only nav entry for the whole module is `attendance.dashboard` (base.html:239), and the dashboard's four quick-link cards are Records / Leaves / Balances / Shifts. The screen renders fine at the URL and is completely functional (add, edit, delete all verified working). The live demo has zero holidays configured, and _business_days (routes.py:130) subtracts holiday_date rows from every leave request, so an Eid week is currently deducted from staff annual balances.

**Cause** — Missing link, not a broken route. templates/attendance/dashboard.html:187-207 (quick links) and templates/base.html:239 (nav).

**Fix** — Add a fifth quick-link card on the attendance dashboard, next to Shifts. Same one-line fix would cover leave-types, which is only reachable via a button on the balances screen.

*reproduced · happy path*


### [MINOR] Approving or rejecting an already-decided leave request gives no message at all

**Steps** — Approve a pending request. Then press the browser Back button and click Approve again (or have two managers open the same request).

**Expected** — "This request has already been approved by admin on ..."

**Actual** — 302 back to the detail page with no flash whatsoever. Nothing changed (which is correct), but the manager gets zero feedback and cannot tell whether the click worked. Same for reject.

**Cause** — blueprints/attendance/routes.py:602 and :631 — `if req and req["status"] == "Pending":` with no else branch before the redirect at :618/:645.

**Fix** — Add an else that flashes what the current status is and who set it.

*reproduced · happy path*


### [MINOR] Malformed query strings return 500 on the live demo

**Steps** — As admin on https://demo.aleefy.online: GET /attendance/report?month=13, ?month=0, ?year=abc, ?month=x, /attendance/balances?year=abc, /attendance/holidays?year=abc.

**Expected** — The page renders with the default month/year, or a 400.

**Actual** — All six return 500. Not reachable by clicking (the selects only offer 1-12 and 2024-2027), but a shared/bookmarked/edited URL or a stale link hits it — the same shape as the mistyped-subdomain 500 that was already found once.

**Cause** — blueprints/attendance/routes.py:831-832 `int(request.args.get(...))` then `date(year, month, 1)` at :838; routes.py:765 and :910 have the same unguarded int().

**Fix** — One small helper: `_int_arg(name, default, lo, hi)` that falls back to the default on ValueError and clamps. Three call sites.

*reproduced · happy path*


### [MINOR] A mistyped number in the leave-type or balance form saves 0 and reports success

**Steps** — As a manager: /attendance/leave-types → Add, name "Study", Days per Year "2l" (digit-two, letter-L) → Save. Or /attendance/balances → click a cell → Allocated "2l" → Save Balance.

**Expected** — "'2l' is not a valid days per year" — the message money.form_amount already builds and returns.

**Actual** — "Leave type added." / "Balance updated.", and the stored value is 0.0. The entitlement is now zero and nothing told anyone. money.form_amount was written specifically so this would be reported ("Silently coercing to 0 would be worse than the crash"), and attendance throws the error away with `days, _ =` / `alloc, _ =`. Negative values pass too: days_per_year = -30 and allocated = -50 / used = -5 are all stored as given.

**Cause** — blueprints/attendance/routes.py:733 and :797-799 — the second element of money.form_amount's return is discarded in all four calls

**Fix** — Keep the error and bail: `days, err = money.form_amount(...); if err: flash(err,'error'); return redirect(...)`. Add a `< 0` guard in the same place. Failing test: `test_leave_type_rejects_unparseable_days`.

*reproduced · edge cases*


### [MINOR] Five raw int() calls on form input 500 on values a number input legitimately submits

**Steps** — Post break_minutes="1e5" from the manager's "Record Attendance for Staff" box on /attendance/checkin (that field is `<input type="number" min="0">` with no max and no step, so 1e5 passes the browser's own validation and is submitted verbatim). Same for "1.5" or "30.0" from any client that is not Chrome's constraint validator.

**Expected** — Either the value is parsed or the user is told which box to fix.

**Actual** — ValueError: invalid literal for int() with base 10: '1e5' → 500 page. Confirmed for /attendance/checkin (checkout), /attendance/records/edit/<id>, /attendance/shifts/save (break_minutes), and /attendance/balances/set (year).

**Cause** — blueprints/attendance/routes.py:257, 410, 686, 796 — `int(request.form.get(...) or N)`

**Fix** — Route these through money.form_amount like the rest of the codebase already does, or `int(float(...))` inside a try with a flash. Failing test: post break_minutes='1e5' to the checkout and assert a 302, not a 500.

*reproduced · edge cases*


### [MINOR] Hand-typed or bookmarked attendance URLs 500 on the live demo

**Steps** — Logged in on https://demo.aleefy.online: GET /attendance/report?month=13 → 500. /attendance/report?month=0 → 500. /attendance/report?year=abc → 500. /attendance/balances?year= → 500. /attendance/holidays?year=abc → 500.

**Expected** — A clamp to a sane month/year, or a flash and a redirect.

**Actual** — Uncaught ValueError → the platform 500 page. The screens' own dropdowns cannot produce these, so this is a stale bookmark, a shared link, or a hand-edited URL — the same shape as the "500 on every mistyped subdomain" bug already found once here.

**Cause** — blueprints/attendance/routes.py:765 (balances year), :831-832 (report year/month, then `date(year, month, 1)`), :910 (holidays year)

**Fix** — One helper: `def _int_arg(name, default): try: return int(request.args.get(name) or default) except ValueError: return default`, plus clamping month to 1..12 and year to 1..9999. Failing test: parametrised GET over those five URLs asserting 200.

*reproduced · edge cases*


### [MINOR] An apostrophe in a shift, leave-type or holiday name kills its Edit button

**Steps** — As a manager: /attendance/shifts → Add Shift named "O'Brien Night" → Save. Return to the shifts list and click Edit on that row. Same for a leave type "Hajj O'Leave" on /attendance/leave-types and a holiday "Founder's Day" on /attendance/holidays.

**Expected** — The edit modal opens prefilled.

**Actual** — Nothing happens; the row can never be edited again from the UI. Verified against the rendered HTML: the server emits `onclick="editShift(5,'O&#39;Brien Night','20:00','04:00',30,'1,2,3,4,5','#3b82f6',1)"`, and an HTML parser decodes `&#39;` inside the attribute before the script is compiled — the JS the browser actually receives is `editShift(5,'O'Brien Night',…)`, an unterminated string literal, so the handler never runs. Confirmed the decoded form with a spec-compliant parser; I could not click the button in a real browser, hence "likely" rather than "reproduced". Arabic names are unaffected, but any Latin name with an apostrophe (common in staff-facing labels) is.

**Cause** — templates/attendance/shifts.html:63, templates/attendance/leave_types.html:45, templates/attendance/holidays.html:37 — Python values interpolated straight into a JS call inside an onclick attribute

**Fix** — Drop the onclick arguments and use `data-*` attributes read by a delegated listener, or pass the id alone and look the row up from a `|tojson` blob. Same edit fixes all three files. (The same interpolation also emits a bare `None` for a NULL break_minutes — `editShift(6,'NullBreak','08:00','17:00',None,…)` — which is a ReferenceError, though a NULL there needs a hand-written row.)

*likely · edge cases*


### [MINOR] The "Day" column on the monthly report repeats the date instead of the weekday

**Steps** — Live demo: /attendance/report?year=2026&month=7. Compare the Date (التاريخ) and Day (اليوم) columns.

**Expected** — Date 2026-07-02, Day Thu.

**Actual** — Both cells read 2026-07-02. The template computes the weekday list and the `d` variable and then never uses either. On a printed payroll report the day of the week is the fastest way to spot a weekend shift that should not exist, and it is simply absent.

**Cause** — templates/attendance/report.html:120-129 — `{% set wd = ['Mon',…] %}` and `{% set d = r.work_date | string %}` are both dead; the cell renders `{{ r.work_date }}`

**Fix** — `{{ wd[(d[:10] | todate).weekday()] }}` or, with no filter available, a tiny route-side field. Failing test: assert the report HTML for a known Thursday record contains 'Thu'.

*reproduced · edge cases*


### [MINOR] The holidays screen's quick-add list is hard-coded to 2026 and its year picker stops at 2027

**Steps** — /attendance/holidays → change the year dropdown to 2027 (or 2024/2025).

**Expected** — The "QUICK ADD — 2027 Egyptian Holidays" panel offers 2027's holidays.

**Actual** — The heading says 2027 and the panel below it is empty — the eight Egyptian holidays are literal 2026 dates filtered by `hdate[:4] == year|string`, so they only ever appear on the 2026 view. The year dropdown itself is `range(2024, 2028)`, so from January 2028 the screen cannot be pointed at the current year at all.

**Cause** — templates/attendance/holidays.html:82-100 (hard-coded 2026 dates) and :9 / templates/attendance/report.html:17 / templates/attendance/balances.html:8 (`range(2024, 2028)`)

**Fix** — Store the eight holidays as (month, day) and render them with the selected year; make the year ranges relative (`range(today.year-2, today.year+3)`). Note the fixed-date list is only correct for the civil holidays — the Islamic ones move each year and are not in the list at all.

*reproduced · edge cases*


### [INFO] A CSRF failure is presented to the user as a permissions problem

**Steps** — Trigger any CSRF failure (e.g. submit a form from a tab whose session was replaced). The route passes msg='Invalid or missing security token. Please go back and try again.'

**Expected** — That message is what the user reads.

**Actual** — error.html hardcodes the 403 copy — 'You don't have permission to enter this area' / 'You don't have the required permissions to access this page. Contact your administrator' — and discards msg entirely for code 403. A recoverable stale-token problem is reported as a rights problem, which sends the user to the wrong person. I hit this myself while auditing and it cost me a wrong diagnosis until I read the JS.

**Cause** — templates/error.html:363 and :383 — the `{% elif code == 403 %}` branches ignore `msg`, which is only used in the `{% else %}` fallback.

**Fix** — Use `{{ msg or <the generic 403 text> }}` in the 403 branches. App-wide, not attendance-specific.

*reproduced · happy path*


### [INFO] An employee cannot cancel their own pending leave request, so the reserved days stay locked until a manager acts

**Steps** — As a nurse, submit a leave request, then change your mind. Look at /attendance/leaves and /attendance/leaves/<id>.

**Expected** — A Cancel / Withdraw control on your own pending request.

**Actual** — No such control exists anywhere (leaves_list.html and leave_detail.html have no Cancel/Withdraw/Delete for the requester; only managers get Approve/Reject). The `pending` days stay reserved against her balance indefinitely, and the insufficient-balance check counts them, so she is blocked from requesting the days she actually wants.

**Cause** — No route: blueprints/attendance/routes.py has approve and reject and nothing else that transitions a request out of Pending.

**Fix** — A /leaves/<id>/cancel POST restricted to the requester while status='Pending', releasing pending the same way leave_reject does at routes.py:638-641.

*reproduced · happy path*


### [INFO] The dashboard's today table and /attendance/api/today show every colleague's hours to every employee, while /attendance/records correctly restricts them to their own

**Steps** — Sign in as nurse.mariam on the live demo. GET /attendance/records (own rows only, correct). GET /attendance/api/today and open /attendance/ .

**Expected** — Consistent scoping across the module.

**Actual** — records_list, report and export_xlsx all restrict non-managers to their own user_id. The dashboard's "Today's Attendance" table (routes.py:189, rendered unconditionally by dashboard.html:65) and /attendance/api/today (routes.py:1019, no role check) return the whole clinic's check-in/check-out times and hours to anyone signed in. Verified accessible as nurse.mariam on the live demo (200, unfiltered). May well be intentional for a small clinic — flagging the inconsistency, not asserting a breach.

**Cause** — blueprints/attendance/routes.py:189 and :1019 have no `if not _allowed_manager(user)` branch, unlike :352, :835 and :985.

**Fix** — Decide one way. If it is intentional, leave it; if not, add the same user_id filter the other three routes use.

*reproduced · happy path*


## Finance  (71)

### [BLOCKER] Discount is unbounded — an invoice can be saved with a negative total, and it lands in "Outstanding"

**Steps** — Local, through the real form. POST /finance/invoices/new with owner_id=<any>, description[]=Spay surgery, qty[]=1, unit_price[]=500, discount_type=percent, discount_value=150, tax_rate=0. Second case: unit_price[]=300, discount_type=value, discount_value=500, tax_rate=14. Both are exactly what the browser posts — templates/finance/invoice_form.html line 136 and invoice_edit.html line 110 give discount_value min="0" and NO max, and the SAME input serves both 'Fixed Amount (EGP)' and 'Percentage (%)', so leaving the type on Percentage and typing an EGP figure (200 on a 500 bill) is the realistic path.

**Expected** — The invoice is refused, or the discount is clamped at the subtotal. A bill can never be worth less than nothing.

**Actual** — Case 1 saved as subtotal 500.00, discount_amount 750.00, total -250.00, due_amount -250.00, status 'Unpaid'. The detail page renders 'TOTAL -250.00 EGP'. The Finance dashboard 'Outstanding' card, which is SUM(due_amount) WHERE status IN ('Unpaid','Partial'), read -250.00. Case 2 saved as subtotal 300.00, discount 500.00, tax_amount -28.00, total -228.00 — a negative VAT figure that flows into the P&L and the Excel export.

**Cause** — models/database.py:3431-3436 (create_invoice) computes disc_amt/tax_amt/total with no clamp; blueprints/finance/routes.py:236-238 passes discount_value straight through; the same arithmetic is duplicated at blueprints/finance/routes.py:417-421 (invoice_edit) and models/database.py:3510-3517 (_money, used by estimates).

**Fix** — Clamp in models/database.py _money()/create_invoice: cap percent at 100 and cap disc_amt at subtotal, floor tax_amt and total at 0, and reject rather than silently clamp when the posted discount exceeds the subtotal so the user sees why. Add max="100" to discount_value when discount_type=percent in both templates as a second line of defence.

*reproduced · money & records*


### [BLOCKER] Credit note has no ceiling, and a full credit note double-counts in every finance total

**Steps** — A) Create a 200 EGP invoice. POST /finance/invoices/<id>/credit-note with amount=999999, reason=oops. The form (templates/finance/invoice_detail.html:287) is min="0.01" with no max, prefilled with invoice.total — one extra zero on 1200 gives 12000.  B) Create a 1000 EGP unpaid invoice, note SUM(due_amount) for Unpaid/Partial, then POST credit-note with amount=1000.

**Expected** — A) The credit note is refused above the invoice total.  B) Outstanding falls by exactly 1000 and 'Invoiced' falls by exactly 1000.

**Actual** — A) A new invoice INV-2026-00007 was created with subtotal -999,999.00, total -999,999.00, due_amount -999,999.00, status 'Unpaid', and the original 200 EGP invoice was set to 'Cancelled'.  B) Outstanding went -3550 -> -5550, i.e. it moved by -2000 for a 1000 credit note. The original is set Cancelled (its +1000 leaves the sum) AND the negative credit invoice is inserted with status 'Unpaid' (subtracting another 1000). get_finance_summary()['invoiced'] moved identically.

**Cause** — blueprints/finance/routes.py:480-542 — no bound on `amount` against invoice['total'], and the credit note is created via db.create_invoice() so it is a real invoice row with status 'Unpaid' and a negative due_amount, while the original is separately flipped to 'Cancelled' at line 521.

**Fix** — Cap amount at invoice['total'] (or at paid_amount for a refund) and reject above it. Give the credit note a status that is excluded from the outstanding/invoiced aggregates (e.g. its own 'Credit' status), or leave the original invoice alone when a credit note is issued rather than cancelling it — cancelling AND inserting a negative row is what causes the double count.

*reproduced · money & records*


### [BLOCKER] Double-clicking Record Payment records the money twice — the built-in idempotency is never used

**Steps** — Create a 300 EGP invoice. POST /finance/invoices/<id>/pay twice with amount=100, method=Cash (what a double-click on a slow connection sends — templates/finance/invoice_detail.html:259 is a plain submit button with no disable-on-submit and no confirm dialog, unlike the credit-note button beside it which does have one).

**Expected** — The second submission is recognised as the same payment and suppressed. models/payments/__init__.py:127-136 was written specifically to do this: "Re-submitting the same idempotency_key returns the EXISTING intent... That is what stops a double-clicked Pay button."

**Actual** — Two ledger rows: payments = [{amount: 100.0, reference: 'CASH-1'}, {amount: 100.0, reference: 'CASH-2'}], invoice paid_amount=200.00, due_amount=100.00. The two payment_intents carry keys 'auto-8a0e5046-...' and 'auto-1646228b-...' — different random UUIDs, so the dedupe can never fire. The client handed over 100 and the system says 200; the till is 100 short with no trace. The only thing bounding it is the due-amount check, so it stops at the invoice total.

**Cause** — blueprints/finance/routes.py:337-345 calls db.add_payment() without idempotency_key; models/database.py:3757-3758 passes `idempotency_key or ""`; models/payments/__init__.py:133 then falls back to `f"auto-{uuid.uuid4()}"`, which is unique per request by construction.

**Fix** — Put a per-form nonce in the pay form (a hidden field seeded once per rendered page) and pass it as idempotency_key from invoice_pay. A cheaper stopgap that covers the common case: key on f"inv{inv_id}-{amount}-{method}-{reference}-{date}". Also disable the submit button on submit.

*reproduced · money & records*


### [BLOCKER] Clearing any number box on the invoice/estimate form returns a 500 (reproduced on the live demo)

**Steps** — Live: log in as admin at https://demo.aleefy.online, open /finance/invoices/new, pick an owner, type a description, then CLEAR the Qty box (or Unit Price, Discount, Discount value, or Tax %) and press Save. Reproduced end-to-end against the live demo with a POST carrying qty[]='' -> HTTP 500, and confirmed in the server journal: "ValueError: could not convert string to float: ''" at POST /finance/invoices/new. Same on /finance/invoices/<id>/edit and /finance/estimates/new. Note the number inputs have min= but NO required=, so an empty box submits; and because they are type=number, typing "1,500" or "abc" also leaves the field empty on submit -> identical crash.

**Expected** — "1,500 is not a valid quantity" (or treat blank as 1) and the form comes back with the typed lines intact.

**Actual** — HTTP 500 error page. Every line the receptionist typed is lost; she retypes the whole invoice with a client at the counter. Nothing is saved.

**Cause** — blueprints/finance/routes.py:201-203 (float(qtys[i]) / float(unit_prices[i]) / float(discounts[i])), :235-236 (discount_value, tax_rate), :402-404 and :419-420 (invoice_edit), :907-909 and :932-933 (estimate_new). models/money.py already has form_amount() written for exactly this and it is not used on these fields. Templates: templates/finance/invoice_form.html:114-116,136,140; invoice_edit.html:85-87,110-116; estimate_form.html:109-111,130,134 — no required= on any of them.

**Fix** — Route every one of these through money.form_amount() and flash the error instead of coercing with float(). Blank quantity should default to 1, blank price to 0.

*reproduced · edge cases*


### [BLOCKER] Double-clicking Record Payment charges the client twice

**Steps** — Open an unpaid 500 EGP invoice, type 100 in Record Payment, click the button twice (or click once on a slow connection and click again). Reproduced with two sequential POSTs to /finance/invoices/<id>/pay with amount=100.

**Expected** — One payment of 100. paid_amount=100, due=400, one ledger row, one loyalty award.

**Actual** — paid_amount=200, due=300, TWO ledger rows of 100 each, and 2 loyalty rows (20 points). The client is recorded as having paid 200 when he handed over 100 — the till is over and the invoice is wrong. There is no disable-on-submit and no idempotency token on the form.

**Cause** — blueprints/finance/routes.py:336 calls db.add_payment() without idempotency_key; models/database.py:3731-3757 defaults it to "", and models/payments/__init__.py:create_intent then generates auto-<uuid4>, so the duplicate-suppression the module was explicitly built for never engages. templates/finance/invoice_detail.html:234-259 has no submit guard.

**Fix** — Render a per-page-load nonce as a hidden field in the payment form and pass it as idempotency_key to add_payment; the suppression logic in create_intent already handles the rest. Disable the button on submit as a second line of defence.

*reproduced · edge cases*


### [BLOCKER] Applying account credit to a cancelled invoice destroys the client's credit and 500s

**Steps** — Owner has 500 EGP on account. Open his unpaid invoice in tab A (the "Client has credit" card is showing). In tab B issue a credit note on that same invoice, which marks it Cancelled. Back in tab A click Apply credit for 100. Reproduced directly by POSTing /finance/invoices/<id>/apply-credit with amount=100 on a Cancelled invoice.

**Expected** — "That invoice has been cancelled" flashed, credit untouched.

**Actual** — HTTP 500. The owner_credits debit row is already committed: balance goes 500.00 -> 400.00. The invoice is untouched (paid 0, due 200, still Cancelled). 100 EGP of the client's money has vanished with no payment to show for it and no error the staff member can act on.

**Cause** — models/database.py:3669-3711 apply_credit() INSERTs the -amount owner_credits row and commits, then calls add_payment() outside that transaction; add_payment -> payments.create_intent raises PaymentError("That invoice has been cancelled."). blueprints/finance/routes.py:1062-1068 catches only ValueError, so PaymentError escapes as a 500. Any failure in add_payment (not just this one) loses the credit the same way.

**Fix** — Write the owner_credits debit and the payment in one transaction, or take the payment first and only debit the credit on success. Also catch payments.PaymentError in invoice_apply_credit.

*reproduced · edge cases*


### [BLOCKER] Editing an invoice below what has already been paid hides the overpayment and marks it Paid

**Steps** — Create a 1000 EGP invoice, record a 800 EGP deposit (status becomes Partial, so editing is still allowed), then edit the invoice down to 100 EGP because the surgery did not happen. Reproduced via POST /finance/invoices/<id>/edit.

**Expected** — The clinic is told it now holds 700 EGP that belongs to the client — as credit on account or a refund to issue.

**Actual** — total=100, paid_amount=800, due_amount=-700, status='Paid'. The invoice reads as settled. The 700 EGP the clinic owes back appears nowhere: not on the invoice, not on the client's account balance, not in any report. The ledger still correctly says 800 was received, so the books and the invoice disagree by 700.

**Cause** — blueprints/finance/routes.py:426-428 computes due_amount = total - paid_amount with no floor and derives status from it, bypassing payments._reconcile_invoice() which clamps due at 0. Nothing converts the excess into owner credit.

**Fix** — Refuse the edit if the new total is below paid_amount, or move the excess to owner_credits as a deposit and say so. Recompute through payments._reconcile_invoice() instead of writing status/due by hand.

*reproduced · edge cases*


### [BLOCKER] Money collected today never shows in "Today's Revenue" — revenue is attributed by invoice ISSUE date, not payment date

**Steps** — REPRODUCED LIVE on https://demo.aleefy.online as admin. 1) GET /finance/ — card "إيرادات اليوم / Today's Revenue" = 0 EGP, subtitle "المدفوعات المستلمة اليوم" (payments received today); "Outstanding" = 134,668 EGP. 2) Open /finance/invoices/1966 (INV-202602-0001, issued 2026-02-07, status Partial) and record a 10 EGP cash payment through the normal payment box. 3) Reload /finance/. Also reproduced locally with the Flask test client: invoice issued 40 days ago, 800 EGP paid today.

**Expected** — Today's Revenue rises by the 10 EGP just taken; the 30-day revenue chart gets a bar for today; This Month's Revenue rises by 10.

**Actual** — Today's Revenue stays 0 EGP and "Today's Payments" stays 0 transactions. Only "Outstanding" moved (134,668 -> 134,658), proving the payment landed. The 10 EGP is credited to FEBRUARY's revenue, because the query is SUM(paid_amount) filtered on invoices.issue_date. get_revenue_by_day() has the same filter, so today has no bar. Local run: today's revenue 0.0 before AND after an 800 EGP cash payment; payments row exists with received_at = today. With 119 unpaid invoices in the demo, every collection against an older bill is invisible on the screen the clinic closes the day with, and the till can never be reconciled against it.

**Cause** — platform/models/database.py:3765-3767 (get_finance_summary revenue = SUM(paid_amount) WHERE issue_date BETWEEN ?), :3816-3817 (get_revenue_by_day, same), :3800-3801 (get_dashboard_stats revenue_today/revenue_month, same). Consumed by platform/blueprints/finance/routes.py:63-65 and :80-82.

**Fix** — Revenue is a payments-table question, not an invoices-table one. Sum payments.amount over payments.received_at for the window (status captured/succeeded), and count payment rows for paid_count_today rather than invoices with issue_date=today. The payments ledger already exists and already carries received_at.

*reproduced · edge cases*


### [BLOCKER] Quantity 0 is silently stored as 1 — the invoice charges for a line the screen showed as 0.00

**Steps** — Local, admin, POST /finance/invoices/new with owner_id set and one line: description="Free sample", qty[]="0", unit_price[]="150", discount[]="0". The browser form's own recalc() JS uses parseFloat(qty)||0, so the line total on screen reads 0.00 and the grand total reads 0.00 before you press Save.

**Expected** — Either the line is stored at quantity 0 / total 0, or the form refuses a quantity of 0. Whatever is saved must equal what the screen showed.

**Actual** — Stored invoice_lines.quantity = 1.0, line total = 150.00, invoice total = 150.00. The user saw 0.00 and the client is billed 150. Same bug in the estimate form (estimate stored total 1000 for qty 0). Cause is `float(qtys[i]) or 1` — Python treats 0.0 as falsy and substitutes 1.

**Cause** — platform/blueprints/finance/routes.py:201 (invoice_new), :402 (invoice_edit), :907 (estimate_new) — `qty = float(qtys[i] if i < len(qtys) else 1) or 1`

**Fix** — Drop the `or 1` fallback; default only when the field is absent. Same line also needs the parse guard from the next finding. Note `up = float(...) or 0` and `disc = float(...) or 0` on the following lines are harmless only by accident.

*reproduced · edge cases*


### [BLOCKER] Any number box left empty or mistyped on New Invoice / Edit Invoice / New Estimate returns a 500 and loses the whole typed invoice

**Steps** — Local, admin. POST /finance/invoices/new with a valid owner and one line, but with any ONE of these submitted as an empty string: qty[], unit_price[], discount[]. Same with any of them non-numeric ("two", "1O0"), and same for discount_value="abc". Repeat against /finance/invoices/<id>/edit and /finance/estimates/new. These are <input type="number"> boxes with no `required`: a browser submits "" whenever the field is cleared, and Chrome clears the box outright when the user types Arabic-Indic digits (٥٠٠) or a letter into it — so "clear the 1, type ٢ with the Arabic keyboard, press Enter" is the ordinary path to this.

**Expected** — A red "that is not a valid quantity" on the form with everything else still filled in — exactly what models/money.form_amount() was written to do and what the payment box already does.

**Actual** — ValueError: could not convert string to float: '' -> HTTP 500. The entire invoice — every line, the owner, the notes — is gone. Confirmed for qty[], unit_price[], discount[] on invoice_new; qty[] on invoice_edit; qty[] on estimate_new; discount_value/tax_rate on invoice_new and invoice_edit (empty string is tolerated there by `or 0`, non-numeric is not).

**Cause** — platform/blueprints/finance/routes.py:201-203 and :235-236 (invoice_new), :402-404 and :419-420 (invoice_edit), :907-909 and :932-933 (estimate_new) — bare float() on form input. models/money.py:form_amount already exists for exactly this and is used at routes.py:324 for payments.

**Fix** — Route the six parse sites through money.form_amount(), collect the errors, and re-render the form with the submitted values instead of raising.

*reproduced · edge cases*


### [BLOCKER] Finance dashboard "Today's Revenue" and "Payments Today" ignore money collected on any invoice not issued today — reproduced on the live demo

**Steps** — LIVE (demo.aleefy.online), signed in as fin.dalia / Demo@1234. 1) Open /finance/ and read the four cards: Today's Revenue = 0 EGP, Month Revenue = 20,247 EGP, Outstanding = 134,778 EGP, Payments Today = 0. 2) Open /finance/invoices?status=Unpaid, click INV-202602-0001 (id 1966, issued 2026-02-07). 3) In the Record Payment box enter 100, method Cash, submit. Flash: "Payment of 100.00 recorded. +10 loyalty points awarded." 4) Go back to /finance/.

**Expected** — Today's Revenue = 100 EGP and Payments Today = 1. The card's own subtitle says "Payments received today" / "Transactions".

**Actual** — Today's Revenue stays 0 EGP, Payments Today stays 0. Only Outstanding moved (134,778 -> 134,678). The 100 EGP now in the till is invisible on every revenue figure, today and forever: next day the invoice is neither "today" nor in this month, so it never appears on any Today's Revenue at all. A clinic collecting arrears — 119 unpaid invoices in this dataset — closes the day showing zero revenue.

**Cause** — blueprints/finance/routes.py:63 calls db.get_finance_summary(date_from=today, date_to=today); models/database.py:3765 computes revenue as SUM(invoices.paid_amount) WHERE invoices.issue_date BETWEEN ?, i.e. keyed on when the invoice was raised, not when the money arrived. blueprints/finance/routes.py:80 does the same for paid_count_today (COUNT of invoices issued today, labelled "Payments Today / Transactions").

**Fix** — Both figures should come from the payments ledger, which already records the real timestamp: revenue = SELECT COALESCE(SUM(amount),0) FROM payments WHERE received_at::date BETWEEN ?, and paid_count_today = COUNT(*) over the same rows. models.payments already writes payments.received_at (verified: '2026-08-07 12:37:30' on a 2026-08-02 invoice).

*reproduced · happy path*


### [BLOCKER] A closed month's P&L keeps moving: /finance/reports dates revenue by invoice issue date, so a July invoice paid in August retroactively becomes July revenue

**Steps** — LOCAL, throwaway SQLite, signed in as a finance user. 1) Create an invoice for 5,000 dated 2026-07-15 via /finance/invoices/new. 2) Open /finance/reports?date_from=2026-07-01&date_to=2026-07-31 — the July close. Revenue 0, Invoiced 5000, Net 0. 3) On 7 Aug the client pays the 5,000 in cash via the invoice's Record Payment box. 4) Re-open the identical July report URL. 5) Also open /finance/reports?date_from=2026-08-01&date_to=2026-08-07.

**Expected** — July's revenue stays 0 once July is closed; the 5,000 shows as August revenue, in the month the cash actually arrived.

**Actual** — July's report now reads Revenue 5000, Net 5000 — a signed-off month silently restated. August's report reads Revenue 0, Net 0 for the month the money landed. Every prior month's P&L changes every time an old invoice is settled, and the Excel export inherits the same basis. Two people running the same July report a week apart get different net profit.

**Cause** — models/database.py:3765 — get_finance_summary() revenue/expenses window on invoices.issue_date. Used by blueprints/finance/routes.py:736 (reports) and :63-64 (dashboard).

**Fix** — Same one-line root fix as the dashboard: source revenue from payments.received_at rather than invoices.issue_date. Everything else on the report (invoiced, invoice_count) is correctly issue-date based and should stay.

*reproduced · happy path*


### [BLOCKER] A credit note subtracts the invoice from Outstanding twice — proven on the live demo: one 12,345.67 void moved Outstanding by 24,692

**Steps** — Live demo, admin. 1) Read the Finance dashboard Outstanding card: 147,004 EGP. 2) Open an unpaid invoice (I used INV-2026-00391, total 12,345.67) and press Credit Note for the full amount. 3) Re-read the Outstanding card: 122,312 EGP.

Reproduced locally too (Flask test client, SQLite): one 1,000 EGP unpaid invoice, Outstanding = 1,000. Issue a full credit note. Outstanding = -1,000. Moved by -2,000 for a 1,000 invoice.

**Expected** — Voiding a 12,345.67 EGP unpaid invoice should reduce Outstanding by 12,345.67, to 134,658.

**Actual** — Outstanding dropped by 24,692 (2x). The void does two things: it sets the ORIGINAL to status='Cancelled' (which removes it from the Outstanding query) and it creates a SECOND invoice with total = -12,345.67, due_amount = -12,345.67, status = 'Unpaid' — which the same query then adds. The clinic's receivables figure is wrong by the value of every credit note it has ever issued, and goes negative once credit notes exceed genuinely unpaid bills.

The same negative row leaks into three other screens I verified:
- /finance/invoices?status=Unpaid lists credit note INV-2026-00392 showing -12,345.67, i.e. it reads as a bill the client owes. Confirmed live.
- The invoices-list footer totals include it (footer showed -1,000.00 locally).
- /finance/reports "Revenue by Line Type" moved by -1,200 when a 600 EGP invoice was voided, same double count (the service line leaves via status!='Cancelled' AND a -600 'credit' line arrives).
- The main app dashboard (get_dashboard_stats) shows outstanding = -1,000 with invoices_unpaid = 1.

**Cause** — blueprints/finance/routes.py:517-521 — invoice_credit_note() implements a void as create_invoice() with a negative line, then UPDATE invoices SET status='Cancelled' on the original. The aggregates that consume it were written before credit notes existed: models/database.py:3772 (get_finance_summary outstanding), blueprints/finance/routes.py:76-78 (finance dashboard Outstanding card), models/database.py:3803 (get_dashboard_stats outstanding), blueprints/finance/routes.py:741-749 (revenue_by_type), models/database.py:3477 (list_invoices).

**Fix** — The negative invoice needs to be distinguishable from a real invoice. Cheapest correct change: give credit notes their own status (e.g. status='Credit') at routes.py:517 instead of leaving them 'Unpaid', then every existing `status IN ('Unpaid','Partial')` and `status != 'Cancelled'` filter excludes them for free. That is a one-word change at the creation site plus a data fix for existing rows, versus editing five aggregate queries. Whichever way, the invariant to hold is: voiding an unpaid invoice moves Outstanding by exactly the invoice total, once.

*reproduced · money & records*


### [BLOCKER] Applying account credit to a cancelled invoice destroys the client's deposit and returns a 500

**Steps** — 1) Create a 500 EGP invoice for an owner. 2) Take a 100 EGP cash payment (invoice becomes Partial, due 400). 3) Issue a full 500 credit note — the invoice becomes status='Cancelled' but due_amount stays 400. 4) Take a 400 EGP deposit from the same owner at /finance/owners/<id>/credit. Balance = 400.00. 5) On the cancelled invoice, use the Apply Credit box for 400.

**Expected** — Either the credit applies, or it is refused with a flash message and the client's 400 EGP stays on their account.

**Actual** — HTTP 500 (uncaught models.payments.PaymentError: 'That invoice has been cancelled.') AND the owner's credit balance goes from 400.00 to 0.00. The owner_credits ledger shows [('applied', -400.0), ('deposit', 400.0)]. The payments ledger for the invoice still shows only the original 100 — no payment was recorded. The invoice is unchanged (paid 100, due 400). 400 EGP of a client's money has been deducted from their account and applied to nothing. Nothing on any screen shows where it went.

**Cause** — models/database.py:3700-3710 — apply_credit() commits the negative owner_credits row in its own `with conn:` block and only THEN calls add_payment(). If add_payment raises, the debit is already committed and there is no rollback. The check at :3697 only rejects `amount > due`; it never checks invoice status, so a Cancelled invoice with due_amount > 0 walks straight past it into payments.create_intent (models/payments/__init__.py:159-160) which raises. blueprints/finance/routes.py:1067 catches only ValueError, and PaymentError subclasses Exception — hence the 500.

**Fix** — Two things, both small. (1) In apply_credit(), do the add_payment() FIRST and insert the owner_credits debit only after it returns — the payment path is the one that can fail. (2) Add the status check next to the existing due check at models/database.py:3696: `if (inv.get('status') or '') == 'Cancelled': raise ValueError('that invoice has been cancelled')`, so the route's existing `except ValueError` shows a flash instead of a 500. Failing test: assert owner_credit_balance is unchanged after apply-credit against a cancelled invoice.

*reproduced · money & records*


### [BLOCKER] Clearing any Qty / Price / Discount box on an invoice, estimate or invoice-edit form returns a 500 and loses the whole form

**Steps** — 1) /finance/invoices/new. 2) Fill in an owner and one line: description 'Consultation', price 150. 3) Click into the Qty box and delete the '1' so the box is empty (an <input type=number> with an empty value passes browser validation — min="0.01" does not make it required — and submits as an empty string). 4) Press Save.

Same result for the Price box, the Discount box, on /finance/estimates/new, and on /finance/invoices/<id>/edit.

**Expected** — "Quantity is required" next to the offending box, with everything else the operator typed still on screen.

**Actual** — HTTP 500. ValueError: could not convert string to float: ''. Everything typed is gone. Reproduced on all three routes:
  invoice_new  Qty box cleared      -> 500
  invoice_new  Price box cleared    -> 500
  invoice_new  Discount box cleared -> 500
  estimate_new (all three)          -> 500
  invoice_edit Price box cleared    -> 500

**Cause** — blueprints/finance/routes.py:201-203 (invoice_new), :402-404 (invoice_edit), :907-909 (estimate_new). All three do `float(qtys[i] ...) or 1`. The `or 1` / `or 0` guard runs AFTER float(), so float('') raises before it can help. Same family: :235-236 and :419-420 and :932-933 use `float(f.get(...) or 0)`, which does survive an empty box but still raises on any non-empty non-number.

models/money.py:55 form_amount() was written for exactly this — its docstring says `float(request.form.get(...))` "appears in thirteen places in this codebase" — and it is used on the payment route (routes.py:324) but on none of these.

**Fix** — Route the six line-item parses through money.form_amount() the way invoice_pay already does: parse, collect the errors, and on any error flash and re-render the form with the submitted values instead of redirecting. Failing test: POST /finance/invoices/new with qty[]='' and assert a 200 re-render, not a 500.

*reproduced · money & records*


### [BLOCKER] Editing a part-paid invoice below what the client already paid leaves a negative balance marked "Paid" — the overpayment is invisible

**Steps** — 1) Create a 500 EGP invoice. 2) Take a 300 EGP cash payment (Partial, due 200). 3) Open Edit and change the line price from 500 to 200 (the price was wrong / a service was not performed). 4) Save.

**Expected** — Either the edit is refused because the new total is below what has been collected, or 100 EGP is pushed back onto the client's account as credit so somebody knows the clinic owes it.

**Actual** — total=200, paid_amount=300, due_amount=-100, status='Paid'. The payments ledger still holds 300. The clinic is holding 100 EGP of the client's money and no screen says so: the invoice reads "Paid", the client's credit balance is zero, and the negative due_amount silently reduces the Outstanding figure on the dashboard.

**Cause** — blueprints/finance/routes.py:426-428 — invoice_edit computes `due_amount = round(total - paid_amount, 2)` and `status = "Paid" if due_amount <= 0 ...` inline, with no floor at zero and no refund/credit path. It also writes status and due_amount by hand rather than going through payments._reconcile_invoice(), which does clamp `if due < 0: due = 0` (models/payments/__init__.py:447-448). The guard at routes.py:378 only blocks editing when status == 'Paid', so every Partial invoice is editable to any amount.

**Fix** — After the UPDATE, call `payments._reconcile_invoice(inv_id)` instead of computing paid/due/status by hand — it already derives them from the ledger and clamps the negative. Then, if `total < paid_amount`, raise the excess as an owner_credits 'deposit' row so the overpayment lands somewhere a human can see and refund it.

*reproduced · money & records*


### [BLOCKER] A voided (credit-noted) invoice can be edited back to life at any amount, and the credit note stays

**Steps** — 1) Create a 500 EGP invoice. 2) Issue a full credit note — status becomes 'Cancelled'. 3) Open /finance/invoices/<id>/edit (the Edit button is still there; nothing blocks it). 4) Change the price to 900 and save.

**Expected** — "This invoice has been cancelled and cannot be edited."

**Actual** — HTTP 302, and the invoice is now status='Unpaid', total=900, due_amount=900. The credit note for the original 500 still exists as a separate row. The client is now billed 900 for work that was voided, the clinic's books carry both a live 900 receivable and a -500 credit note against the same event, and the audit_log has a credit_note entry for an invoice that is no longer cancelled.

**Cause** — blueprints/finance/routes.py:378 — `if invoice["status"] == "Paid":` is the only status guard. 'Cancelled' falls through, and the UPDATE at :440-454 unconditionally writes a fresh status computed from the new total.

**Fix** — One line at routes.py:378: `if invoice["status"] in ("Paid", "Cancelled"):`. Same guard belongs on the credit-note route so a cancelled invoice cannot be credited again.

*reproduced · money & records*


### [BLOCKER] "Today's Revenue" and "Payments Today" count invoice issue dates, not money received — the live demo shows 0 EGP on a day 120 EGP was taken

**Steps** — Live demo, right now, read-only. 1) Open /finance/. The dashboard reads: Today's Revenue = 0 EGP, Payments Today = 0. 2) Query the payments ledger for the same day: three cash payments totalling 120 EGP, received 2026-08-07 15:42–15:43 by Dalia Serag and Platform Administrator, all against INV-202602-0001 (issued 2026-02-07, status Partial). 3) Over the last 30 days on the demo: the app's revenue figure is 66,792.52 while the payments ledger for the same window is 66,912.52.

Reproduced locally: invoice issued 40 days ago, 777 EGP paid today by cash. get_finance_summary(today, today).revenue does not include the 777.

**Expected** — A clinic closing the till reads Today's Revenue and it matches the cash in the drawer.

**Actual** — Today's Revenue = 0 EGP while 120 EGP is in the drawer. The figure is SUM(paid_amount) over invoices whose ISSUE date falls in the window — so money collected today on an older invoice is credited to the month the invoice was written, and an invoice issued today that gets paid next month will retro-add itself to today's figure later. It is neither cash-basis nor accrual, and it cannot be reconciled against anything. The same wrong basis drives month revenue, the 30-day revenue chart, the P&L "Net" on /finance/reports (revenue - expenses, where expenses ARE date-of-spend), and the main app dashboard.

"Payments Today" is separately wrong: it counts INVOICES with issue_date = today and status Paid/Partial, not payments. Reproduced locally: 1 payment received today, card reads 0.

**Cause** — models/database.py:3765-3767 (get_finance_summary revenue), :3800-3801 (get_dashboard_stats revenue_today/revenue_month), :3816-3817 (get_revenue_by_day), and blueprints/finance/routes.py:80-82 (paid_count_today). All filter on invoices.issue_date. The payments table has received_at and is the correct source — it exists and is populated (models/payments/__init__.py:399-406) but no report reads it.

**Fix** — Point these five queries at the payments ledger: `SELECT COALESCE(SUM(amount),0) FROM payments WHERE received_at >= ? AND received_at < ?`. It is already the authoritative source — _reconcile_invoice derives paid_amount from it — and it makes refunds (which write negative rows) net out correctly for free. paid_count_today becomes COUNT(*) over the same query. Note the server timezone is correctly Africa/Cairo, so date.today() is the right day; only the column being filtered is wrong.

*reproduced · money & records*


### [MAJOR] The invoice ledger's Totals row is capped at 200 rows and understates outstanding by 44% on the live demo

**Steps** — Log into https://demo.aleefy.online as admin and open /finance/invoices with no filter.

**Expected** — The Totals row reflects every invoice matching the filter, or the page paginates and says 'showing 200 of 393'.

**Actual** — The footer reads 'Totals (200 invoices)  299,495.00 / 223,736.64 / 75,758.36'. The dataset has 393 invoices; /finance/reports over 2000-01-01..2030-12-31 reports Invoiced 576,383 and Outstanding 134,778. So the main invoice screen understates total due by 59,020 EGP. There is no pagination and no 'next page' — the other 193 invoices are simply unreachable from this screen, and the only hint is the parenthesised count.

**Cause** — blueprints/finance/routes.py:117-122 calls db.list_invoices(..., limit=200); lines 140-142 then compute total_amount/total_paid/total_due by summing only that truncated list. templates/finance/invoices_list.html:122-125 prints them as 'Totals'. The same shape exists on /finance/expenses (routes.py:693, LIMIT 200 — 48 rows on the demo, so not yet biting) and estimates (list_estimates default limit=100).

**Fix** — Compute the three totals with a separate SELECT SUM(...) using the same WHERE clause, unbounded by LIMIT, and add paging (or at least render 'showing 200 of N') to the row list.

*reproduced · money & records*


### [MAJOR] Editing a partly-paid invoice down below what was paid produces a negative balance labelled "Paid"

**Steps** — Create a 1000 EGP invoice. POST /finance/invoices/<id>/pay amount=400 (invoice now Partial, due 600). Then POST /finance/invoices/<id>/edit with the same single line but unit_price[]=100, discount_value=0, tax_rate=0 — a normal correction when the wrong service was billed.

**Expected** — The clinic is told it now owes the client 300, either by refusing the edit, by issuing credit automatically, or at minimum by flagging the overpayment.

**Actual** — Invoice becomes total 100.00, paid_amount 400.00, due_amount -300.00, status 'Paid'. The ledger still shows 400.00 collected. The detail page renders 'Balance Due -300.00 EGP' in green (templates/finance/invoice_detail.html:162 colours anything <= 0 as success), so it reads as settled. The clinic is holding 300 EGP of the client's money and nothing anywhere records it — it is not in the owner's credit balance either.

**Cause** — blueprints/finance/routes.py:417-424 recomputes due_amount and status inline (`status = "Paid" if due_amount <= 0 ...`) and UPDATEs the invoice directly at lines 435-447, bypassing models/payments/_reconcile_invoice(), which does floor `due` at zero and would at least not produce a negative.

**Fix** — In invoice_edit, refuse the update when the new total is below the ledger's paid sum, or write the difference to owner_credits as held credit for that owner. Either way, stop invoice_edit computing paid/due/status itself — write the lines and header, then call payments._reconcile_invoice(inv_id) so there is one place that owns this arithmetic.

*reproduced · money & records*


### [MAJOR] Revenue is booked to the invoice's issue date, not the payment date — today's till can never be reconciled

**Steps** — Create an invoice dated 2026-01-15 for 700 EGP. Today (2026-08-06) POST /finance/invoices/<id>/pay amount=700 method=Cash. Then read the Finance dashboard's 'Today's Revenue' card and /finance/reports for today.

**Expected** — Today's revenue rises by 700 — that is the cash that went in the drawer today. January, a closed month, does not change.

**Actual** — get_finance_summary(today, today)['revenue'] stayed at 0.00. get_finance_summary('2026-01-01','2026-01-31')['revenue'] rose to 700.00 — a month the clinic already closed and reported now shows 700 more. The payments row exists with received_at 2026-08-06 19:03:22 and is simply not what the report reads. Chasing an old debt therefore never shows up on the day you collected it, and every month's P&L keeps moving after it is closed.

**Cause** — models/database.py:3765-3767 — revenue is `SUM(paid_amount) FROM invoices WHERE issue_date BETWEEN ? AND ?`. Same in get_revenue_by_day (models/database.py:3814-3818) and get_dashboard_stats revenue_today/revenue_month (models/database.py:3796-3797). The `payments` table with its received_at column already holds the right data and is not used by any of them.

**Fix** — Read cash-in from the payments ledger: SUM(amount) FROM payments WHERE date(received_at) BETWEEN ? AND ?. Keep the invoice-dated figure alongside it if accrual revenue is also wanted, but label the two differently — 'Collected' vs 'Invoiced'.

*reproduced · money & records*


### [MAJOR] A credit note on a fully paid invoice leaves the payment on the ledger with nothing reversing it

**Steps** — Create a 1200 EGP invoice, pay it in full (Cash), then POST /finance/invoices/<id>/credit-note with only a reason (the amount box is prefilled with the total, so this is the ordinary 'client wants a refund' flow).

**Expected** — Either a reversing payments row, or 1200 pushed onto the owner's account credit, so the books show where the money went.

**Actual** — The original invoice becomes status 'Cancelled' with paid_amount 1200.00 still on it, and its payments row is untouched at +1200.00 Cash. get_finance_summary revenue fell from 8,854 to 7,654 because Cancelled invoices are dropped from the revenue query. The owner's credit balance stayed 0.00. So SUM(payments.amount) and the finance report now disagree by 1200, and nothing in the system says whether the client actually got their 1200 back. models/payments/refund() exists, is fully implemented, writes the reversing negative ledger row, and is never called from the finance blueprint.

**Cause** — blueprints/finance/routes.py:480-542 — the credit-note route only creates a negative invoice and flips the original's status; it never touches the payments ledger or owner_credits.

**Fix** — When the invoice being credited has paid_amount > 0, call models.payments.refund() on the relevant intent(s), or post the credited amount into owner_credits as held credit. Do one of the two, not neither.

*reproduced · money & records*


### [MAJOR] The Excel export includes Cancelled invoices; the report on screen excludes them

**Steps** — Create an invoice for 9,999 dated today, set its status to Cancelled. Open /finance/reports for today, then click the Excel export for the same date range.

**Expected** — The workbook the accountant opens matches the screen it was exported from.

**Actual** — The on-screen 'Invoiced' figure excluded the 9,999 (reported 5,121). The exported sheet1.xml contains the 9,999 row with status 'Cancelled'. Same date range, two different totals, and the export is what leaves the building.

**Cause** — blueprints/finance/routes.py:808-816 — the export query filters only on `i.issue_date BETWEEN ? AND ?`, while models/database.py:3768-3770 (get_finance_summary) and blueprints/finance/routes.py:740-747 (revenue_by_type) both add `status != 'Cancelled'`.

**Fix** — Add `AND i.status != 'Cancelled'` to the export query, or add a Status column filter note and a totals row that matches the screen. One rule, applied in one place.

*reproduced · money & records*


### [MAJOR] A thousands separator or any stray character in an amount box is an unhandled 500

**Steps** — POST /finance/expenses with description=Rent, amount=1,500. Also POST /finance/invoices/new with unit_price[]=1,500, and with tax_rate=14%.

**Expected** — '"1,500" is not a valid amount' — the exact message models/money.py form_amount() was written to produce, which the payment box already uses.

**Actual** — ValueError: could not convert string to float: '1,500' propagates out of the route — a 500 page. Reproduced at the route level for all three fields. Honest caveat: these inputs are type="number", so a desktop browser normally blanks a comma before submit; the reachable paths are paste, autofill, a mobile/Arabic keyboard, or any client that does not run HTML5 validation. The identical bug on the payment box was one of the ten real bugs a human found, which is why money.form_amount exists — it just was not applied here.

**Cause** — blueprints/finance/routes.py:651 (`float(f.get("amount") or 0)` in expenses_list), :201-203 and :391-393 (`float(qtys[i])`, `float(unit_prices[i])`, `float(discounts[i])` in the line loops), :234-235 and :415-416 (`float(f.get("discount_value") or 0)`, `float(f.get("tax_rate") or 0)`), and :908-910 in estimate_new. models/money.py:52 form_amount already handles commas, Arabic digits and currency symbols.

**Fix** — Replace every bare float() on a form value in this blueprint with money.form_amount() and flash the returned error. The helper is already imported at blueprints/finance/routes.py:12.

*reproduced · money & records*


### [MAJOR] Loyalty points reward splitting a payment — pay in slices and earn double

**Steps** — Create a 100 EGP invoice and pay it as 20 payments of 5 EGP each (POST /finance/invoices/<id>/pay amount=5, twenty times). Compare with paying 100 in one go.

**Expected** — 100 EGP earns 10 points either way.

**Actual** — Owner loyalty_balance went 885 -> 905, i.e. 20 points for the same 100 EGP; a single 100 EGP payment awards 10. Because `points = max(1, int(amount * 0.1))`, every payment under 10 EGP still earns a full point, and int() truncates the rest. Paid in 1 EGP slices, 100 EGP earns 100 points, which redeem at 0.5 EGP each (_REDEEM_RATE) = 50 EGP of value against a 100 EGP bill. Instalment plans and part-payments — normal in a clinic — quietly earn a multiple.

**Cause** — blueprints/finance/routes.py:28-31, _award_points() — max(1, int(amount * _POINTS_PER_EGP)) is applied per payment rather than per invoice.

**Fix** — Award once per invoice on the transition to fully Paid, computed from invoices.total, and record the ref so a re-run cannot award twice. Drop the max(1, ...) floor.

*reproduced · money & records*


### [MAJOR] A quantity of 0 is silently billed as 1

**Steps** — On /finance/invoices/new enter a line at 100 EGP and set Qty to 0 (the browser allows 0 to be typed even with min=0.01 in some paths, and the same code runs on /edit and /estimates/new). Reproduced via POST with qty[]='0'.

**Expected** — Either a 0-value line, or "quantity must be at least 1".

**Actual** — The line is saved with quantity=1.0 and total=100.00, and the invoice total is 100.00. A line the staff member deliberately zeroed out is billed to the client at full price. The on-screen summary showed 0.00 before saving, so the number changes between what she saw and what was stored.

**Cause** — blueprints/finance/routes.py:201 `qty = float(qtys[i] if i < len(qtys) else 1) or 1` — the `or 1` turns 0.0 into 1. Same at :402 (invoice_edit) and :907 (estimate_new).

**Fix** — Drop the `or 1` and validate explicitly; a zero-quantity line should either be skipped or rejected with a message.

*reproduced · edge cases*


### [MAJOR] A header discount larger than the subtotal saves a negative invoice, and on edit flips it to Paid

**Steps** — On /finance/invoices/new build a 100 EGP invoice and type 99999 in Discount value (the field has min=0 but no max, verified in the live demo HTML). Save. Then do the same on /finance/invoices/<id>/edit of an unpaid invoice.

**Expected** — "Discount cannot exceed the subtotal."

**Actual** — Create: subtotal=100, discount_amount=99999, total=-99899, due_amount=-99899, status='Unpaid'. Edit: total=-99899 and status flips to 'Paid' on an invoice nobody paid. Same with discount_type=percent and a value over 100. Nothing on the server side caps it, and a negative invoice pollutes every revenue figure (get_finance_summary 'invoiced' went to -100099 in the run).

**Cause** — blueprints/finance/routes.py:235 and models/database.py:3424-3437 (create_invoice) compute disc_amt with no cap; routes.py:423-428 (invoice_edit) does the same and derives status='Paid' from the resulting negative due. templates/finance/invoice_form.html:136 and invoice_edit.html:110 have no max attribute.

**Fix** — Clamp the discount at the subtotal server-side (in create_invoice and invoice_edit) and reject anything larger with a message.

*reproduced · edge cases*


### [MAJOR] Credit note amount is uncapped, and a resubmit issues a second full credit note

**Steps** — Open a 300 EGP invoice, click Issue Credit Note, and type 99999 in the Amount box (no max on the field), confirm. Separately: issue a full 300 credit note, press Back, and resubmit.

**Expected** — Refuse anything above the invoice total; refuse a second credit note once the invoice is fully credited.

**Actual** — 99999 case: a credit invoice with total=-99999 is created and the original is marked Cancelled. 99,999 EGP of negative revenue now sits in the books with no UI to delete it. Resubmit case: TWO credit invoices of -300 each against one 300 invoice — the clinic has written off 600 on a 300 bill.

**Cause** — blueprints/finance/routes.py:480-537 — invoice_credit_note never compares the amount to invoice['total'] and never checks whether the invoice is already Cancelled. templates/finance/invoice_detail.html:289-290 has min=0.01 but no max.

**Fix** — Cap the amount at (total - already credited), and return early if the invoice is already Cancelled.

*reproduced · edge cases*


### [MAJOR] Dashboard and P&L "revenue" is bucketed by invoice date, not by the day the money arrived

**Steps** — Create an invoice dated 2026-01-15 for 700 EGP. Today (2026-08-06) record the 700 EGP payment. Open /finance/ and /finance/reports for today. Reproduced locally; the demo dataset hides it only because the seeder pays every invoice on its own issue date (verified: 0 invoices on the demo have a payment on a different day).

**Expected** — Today's revenue includes the 700 collected today.

**Actual** — get_finance_summary(today) returns revenue 0.00 — today's dashboard card and today's P&L both show nothing. get_finance_summary(January) returns 700.00, so a closed month's revenue moves every time an old bill is settled. With 119 unpaid invoices in the demo dataset this is the normal case, not an edge: the clinic's daily cash figure and its monthly P&L never match the till.

**Cause** — models/database.py:3765-3767 sums invoices.paid_amount filtered on issue_date; :3812-3819 get_revenue_by_day does the same; :3820 get_dashboard_stats revenue_today/revenue_month likewise. The payments table already has received_at, which is the correct key.

**Fix** — Sum payments.amount grouped by substr(received_at,1,10) for revenue; keep issue_date only for the 'invoiced' figure. This also fixes the P&L Net line, which currently mixes payment-date expenses with invoice-date revenue.

*reproduced · edge cases*


### [MAJOR] Editing a cancelled invoice resurrects it as Unpaid

**Steps** — Issue a full credit note on a 100 EGP invoice (it becomes Cancelled). Then POST to /finance/invoices/<id>/edit — reachable from a stale edit tab, or the Back button after the credit note.

**Expected** — "Cancelled invoices cannot be edited."

**Actual** — The invoice comes back as status='Unpaid', total=100, and reappears in the outstanding list. The clinic now has both a -100 credit note AND a live 100 EGP bill for the same work, and will chase the client for money it already wrote off.

**Cause** — blueprints/finance/routes.py:378 guards only `if invoice["status"] == "Paid"`; 'Cancelled' is not in the guard, and :428 recomputes status from scratch instead of preserving it.

**Fix** — Add 'Cancelled' to the guard at routes.py:378 and never let invoice_edit overwrite a Cancelled status.

*reproduced · edge cases*


### [MAJOR] Invoice search only looks at the newest 200 invoices — an older invoice reports "no invoices found"

**Steps** — REPRODUCED LIVE as admin. 1) GET /finance/invoices — exactly 200 rows, oldest shown is INV-202605-0191. 2) GET /finance/invoices?q=INV-202602-0001 — an invoice that demonstrably exists (it is /finance/invoices/1966, and I recorded a payment on it minutes earlier). Also reproduced locally with 230 filler invoices: searching an older client's name returns nothing.

**Expected** — The search box searches invoices. Finding INV-202602-0001 by its number.

**Actual** — "لا توجد فواتير" — no invoices found. list_invoices() is called with limit=200 and the q= filter is then applied in Python to that already-truncated list, so nothing older than the 200th newest invoice is searchable. On the demo (393 invoices) everything before May is unreachable by search; a real clinic passes 200 invoices in weeks. Same truncation poisons the summary strip under the list: with 220 invoices for one owner totalling 2,200, the page reports 2,000.

**Cause** — platform/blueprints/finance/routes.py:117-142 — db.list_invoices(..., limit=200) then `if search: invoices = [i for i in invoices if ...]`, then total_amount/total_paid/total_due summed over the truncated list.

**Fix** — Push the search term into the SQL WHERE (owner name / invoice_number / pet_name ILIKE) so the limit applies after filtering, and compute the three totals with a separate COUNT/SUM query over the full filtered set, not over the page.

*reproduced · edge cases*


### [MAJOR] The due date typed on New Invoice is silently thrown away — which also means the automatic overdue-payment WhatsApp reminder can never fire

**Steps** — Local, admin. POST /finance/invoices/new with issue_date=2026-01-05 and due_date=2026-02-05 (the form at templates/finance/invoice_form.html:82 has the field). Then read the row back.

**Expected** — invoices.due_date = '2026-02-05'; the invoice detail and printout show "Due: 2026-02-05"; the invoice enters the overdue chaser three days later.

**Actual** — invoices.due_date is NULL. Checked the whole test database after creating one through the form: `SELECT COUNT(*) FROM invoices WHERE due_date IS NOT NULL` = 0. The user filled a field, got "Invoice created successfully", and the value was never written. Knock-on: blueprints/whatsapp/scheduler.py:185 selects overdue invoices with `AND inv.due_date <= ?`, and NULL never satisfies it — so the built-in overdue-invoice WhatsApp chaser is dead for every invoice the app creates. (invoice_edit DOES save due_date, at routes.py:452, so the value can only be added by editing an invoice after creating it.)

**Cause** — platform/models/database.py:3442-3449 — the create_invoice INSERT column list omits due_date entirely, while platform/blueprints/finance/routes.py:233 dutifully reads it out of the form and puts it in `data`.

**Fix** — Add due_date to the create_invoice INSERT (column list, placeholder, and data.get("due_date")).

*reproduced · edge cases*


### [MAJOR] A discount bigger than the invoice makes a negative invoice that subtracts from the clinic's Outstanding total

**Steps** — Local, admin. POST /finance/invoices/new: one line at 100 EGP, discount_type=value, discount_value=5000 (the box is <input type=number min=0> with NO max, so this is just a typo away). Read the dashboard's outstanding query before and after.

**Expected** — Rejected — a discount cannot exceed the subtotal — or at worst clamped to zero.

**Actual** — Invoice stored with total = -4,900.00, due_amount = -4,900.00, status = 'Unpaid'. The dashboard's Outstanding figure went from 3,377.00 to -1,523.00. One mistyped discount hides 4,900 EGP of real receivables from the owner's headline number, and the negative invoice sits in the Unpaid list waiting to be chased. Same shape reached by a >100% line discount (total -100) and by a negative quantity (total -500).

**Cause** — platform/blueprints/finance/routes.py:227-242 and platform/models/database.py:3432-3438 — no floor on subtotal - disc_amt. Aggregated blind at routes.py:76-78 and models/database.py:3771-3772 (`SUM(due_amount) WHERE status IN ('Unpaid','Partial')`).

**Fix** — Reject discount_amount > subtotal in create_invoice/_money (and in invoice_edit's copy at routes.py:423), and exclude negative-total rows from the Outstanding aggregate.

*reproduced · edge cases*


### [MAJOR] Credit notes have no cap and no double-issue guard: 100 EGP invoice took a 100,000 EGP credit note, and two clicks made two full ones

**Steps** — Local, finance role. (a) On an invoice totalling 100 EGP, POST /finance/invoices/<id>/credit-note with amount=100000. (b) On an invoice totalling 900 EGP, POST the credit-note form twice with amount=900 — what a double-click, or Back-then-resubmit, does; the form is at templates/finance/invoice_detail.html:280.

**Expected** — (a) refused — you cannot credit more than the invoice is worth. (b) the second refused — the invoice is already fully credited and already Cancelled.

**Actual** — (a) A credit-note invoice for -100,000.00 was created and flashed "Credit note created successfully"; the original was marked Cancelled. (b) TWO credit notes of -900.00 each against one 900.00 invoice — net -900 booked for this client where the correct answer is 0. Both negative invoices then carry status 'Unpaid' with a negative due_amount, so they also feed the Outstanding bug above, and their own detail pages still offer "Issue Credit Note" and a payment box.

**Cause** — platform/blueprints/finance/routes.py:480-537 — no check of amount against invoice total, no check for an existing credit note, no guard on invoice.status already being Cancelled.

**Fix** — Cap amount at invoice.total minus credits already issued against it, and refuse when the invoice is already Cancelled. Hide the credit-note and payment cards on invoices whose total is negative.

*reproduced · edge cases*


### [MAJOR] Re-submitting a payment (double-click, or Back then Save again) records it again — the client is booked as having paid twice

**Steps** — Local, admin. On a 1,000 EGP invoice, POST /finance/invoices/<id>/pay with amount=300 three times, as a double-click or a Back-and-resubmit does. Same test on the deposit form: POST /finance/owners/<id>/credit twice with amount=500. Same on New Invoice: submit the identical form twice.

**Expected** — One payment of 300; a duplicate submission of the same amount within seconds is recognised and ignored.

**Actual** — Three payment rows, paid_amount 900, due 100 — the client handed over 300 and the ledger says 900, so the drawer is 600 short with a full paper trail saying otherwise. Deposit form: balance 1,000 for one 500 EGP deposit. New Invoice: two invoices (INV-2026-00006 and -00007) for the same visit. Note models.database.add_payment already accepts an `idempotency_key` and the finance route passes nothing (routes.py:336-343), while estimate conversion HAS a double-click guard (database.py:3604) — so the protection exists in the codebase and is simply not wired to the payment box. The over-payment guard does catch the specific case where both clicks pay the FULL balance, which is why this looks safe in casual testing.

**Cause** — platform/blueprints/finance/routes.py:336-343 (invoice_pay), :1020-1041 (owner_credit deposit), :241-255 (invoice_new)

**Fix** — Put a per-form nonce in the payment/deposit/invoice forms and pass it as add_payment's idempotency_key; reject a repeat of the same key.

*reproduced · edge cases*


### [MAJOR] Editing a part-paid invoice down leaves a negative balance and no credit for the client — the overpayment simply vanishes

**Steps** — Local, admin. Create a 500 EGP invoice, take a 400 EGP payment (status Partial), then POST /finance/invoices/<id>/edit reducing the line to 50 EGP — the ordinary "I billed the wrong item, let me fix it" flow.

**Expected** — The 350 EGP the client is now owed is visible: refused, or moved onto the owner's account credit, or at minimum flagged on screen.

**Actual** — invoices row becomes total 50.00, paid_amount 400.00, due_amount -350.00, status 'Paid'. owner_credit_balance is still 0.00. The clinic owes this client 350 EGP and nothing anywhere says so; the invoice reads as a clean, fully-paid 50 EGP bill. The detail page renders 200 with no warning.

**Cause** — platform/blueprints/finance/routes.py:426-428 — `due_amount = round(total - paid_amount, 2)` and `status = "Paid" if due_amount <= 0`, with no check that paid_amount now exceeds the new total.

**Fix** — When the recomputed total falls below paid_amount, either refuse the edit or write the difference to owner_credits as a deposit (db.add_deposit) so the balance shows on the client's account.

*reproduced · edge cases*


### [MAJOR] Changing the owner on a part-paid invoice moves the invoice but leaves its payments attributed to the old client

**Steps** — Local, admin. Invoice for Client A (id 16) at 200 EGP, take a 50 EGP payment, then POST /finance/invoices/<id>/edit with owner_id = Client B (id 17) — the fix for "I picked the wrong client".

**Expected** — The payment follows the invoice, or the owner change is refused once money has been taken.

**Actual** — invoices.owner_id = 17 (Client B) but payments.owner_id is still 16 (Client A). Client A's payment history shows 50 EGP against an invoice that is no longer hers; Client B's invoice shows 50 EGP paid by nobody on her record. Any per-owner statement or reconciliation built off payments.owner_id now disagrees with the invoice list.

**Cause** — platform/blueprints/finance/routes.py:440-454 — the UPDATE sets invoices.owner_id with no corresponding update to the payments rows and no guard on paid_amount > 0.

**Fix** — Refuse an owner change once paid_amount > 0 (the credit-note path exists for genuine mistakes), or update payments.owner_id and owner_credits in the same transaction.

*reproduced · edge cases*


### [MAJOR] A mistyped year on the issue date removes a real paid invoice from every financial report

**Steps** — Local, admin. POST /finance/invoices/new with issue_date=2016-08-07 instead of 2026-08-07 — one wrong digit in the date spinner — for 3,000 EGP, then take the 3,000 EGP payment. Open /finance/reports for the current month.

**Expected** — Rejected, or at least questioned: an invoice dated ten years ago is not a thing a clinic issues.

**Actual** — Stored as-is. This month's report shows revenue 0.00 and does not count the invoice; the 3,000 EGP is invisible in every date window a human would look at, while still appearing in the invoice list as a normal paid bill. The extreme version confirms there is no validation at all: a POST with issue_date="not-a-date" is stored verbatim, and that invoice is then excluded even from a 2000-01-01..2099-12-31 report (string comparison), so 5,000 EGP of paid work exists in the database and in no report anywhere.

**Cause** — platform/blueprints/finance/routes.py:232 — `"issue_date": f.get("issue_date") or date.today().isoformat()`, no parse and no range check. Same at :929 for estimates and :670 for expenses.

**Fix** — Parse with date.fromisoformat() and reject anything outside a sane window (say issue_date within one year either side of today) before insert.

*reproduced · edge cases*


### [MAJOR] Credit notes deflate accounts receivable — a credit note is stored as a negative invoice with status 'Unpaid', so it is subtracted from Outstanding and sits in the Unpaid queue

**Steps** — LOCAL, signed in as a finance user. 1) Create a 3,000 invoice and leave it unpaid. Dashboard Outstanding = 3,000. Correct. 2) Create a second 800 invoice and take the full 800 payment — it goes Paid. 3) On that paid invoice press Issue Credit Note, amount 800, reason "billed in error". 4) Reload /finance/ and /finance/invoices?status=Unpaid.

**Expected** — Outstanding stays 3,000 — only one client owes the clinic anything. The 800 credit note is money the clinic owes the client, not a receivable.

**Actual** — Outstanding drops to 2,200. The credit note is written as a brand-new invoice with total -800, due_amount -800 and status 'Unpaid', which lands inside the dashboard's SUM(due_amount) WHERE status IN ('Unpaid','Partial'). It also shows up in the Unpaid filter and the list footer as a row reading Total -800.00 / Due -800.00, and its detail page offers a Record Payment form and an Edit button. Every credit note the clinic issues understates what clients owe by that amount, and reception is left chasing a negative invoice. (Confirmed with a partial 400 credit note too: Outstanding fell by 400 on an invoice that was already fully paid.)

**Cause** — blueprints/finance/routes.py:509-517 builds the credit note through db.create_invoice(), and models/database.py:3444 hardcodes status='Unpaid', due_amount=total for every new invoice — so a negative total becomes a negative receivable. The dashboard sum is blueprints/finance/routes.py:76.

**Fix** — Give the credit note a status of its own after create_invoice() — e.g. UPDATE invoices SET status='Credit', due_amount=0 WHERE id=credit_id — and exclude that status from the outstanding sum and the Unpaid filter. The status column already carries 'Cancelled' as a non-receivable value, so nothing new is needed downstream.

*reproduced · happy path*


### [MAJOR] The invoices list is capped at 200 rows with no pagination, and its search box only filters those 200 — an invoice older than the cap cannot be found from the screen

**Steps** — LIVE, as fin.dalia. 1) Open /finance/invoices with no filter. Count the rows: exactly 200, newest INV-202608-0390, oldest INV-202605-0191. Footer reads "200 invoices". No Next / page controls anywhere on the page. 2) Type INV-202602-0001 into the search box (/finance/invoices?q=INV-202602-0001). 3) Now open /finance/invoices/1966 directly.

**Expected** — Searching an exact invoice number finds it, or the list pages so an older invoice is reachable by clicking.

**Actual** — The search returns zero rows, with no message saying anything was truncated. The invoice exists and renders fine at /finance/invoices/1966 (INV-202602-0001, 2026-02-07, unpaid). Everything before May is unreachable from the Invoices screen: this demo has 393 invoices and the screen can show 200. "Find Mrs X's invoice from February" — a daily reception task — silently returns nothing. The date filter does reach them (a Feb range returns 63 rows) but there is nothing on the page telling anyone that is the only way.

**Cause** — blueprints/finance/routes.py:117-123 passes limit=200 to db.list_invoices() and blueprints/finance/routes.py:133-138 applies the `q` search in Python to that already-truncated list, so search can never see row 201 onward. The footer totals at :140-142 sum the same 200 and are presented as "Totals (N invoices)".

**Fix** — Push `q` into db.list_invoices() as a SQL predicate (owner name / invoice_number / pet_name LIKE) so search hits the whole table, and either paginate or show "showing the 200 most recent — narrow by date" when len(invoices) == limit so the footer total is not read as the real total.

*reproduced · happy path*


### [MAJOR] New Invoice, New Estimate and Edit Invoice all return a 500 if a quantity, unit price or line discount box is left blank

**Steps** — LOCAL, app configured as production (TESTING off, PROPAGATE_EXCEPTIONS off), signed in as a finance user. 1) Open /finance/invoices/new, pick an owner, type a line description. 2) Clear the Unit Price box (select the 0 and delete it) and submit. Repeat with Qty cleared, and with Discount cleared. 3) Same three on /finance/estimates/new and on /finance/invoices/<id>/edit.

**Expected** — A flash naming the box to fix, with the form redisplayed and the typed lines kept — the behaviour the payment box already has ("'1O0' is not a valid payment amount").

**Actual** — HTTP 500 on all nine combinations. The whole form is lost. The inputs are <input type="number"> with no `required` (verified in the live page source), so the browser happily submits an empty string, and it also submits an empty string for anything it cannot parse — "1,500", "150O", Arabic-Indic digits from an Arabic keyboard. This is the exact bug class the payment box was already hardened against via models/money.form_amount; the invoice, estimate and edit forms were never given the same treatment.

**Cause** — blueprints/finance/routes.py:201-203 (invoice_new), :402-404 (invoice_edit), :907-909 (estimate_new) — `float(qtys[i] ...) or 1` raises ValueError on '' before the `or` can default it. Note float(f.get("tax_rate") or 0) at :236 is safe because of the `or`; the line-item three are not.

**Fix** — Route the three line fields through models.money.form_amount() the way invoice_pay already does, and flash the returned error instead of raising. One helper reused in all three loops covers every case, including thousands separators and Arabic digits.

*reproduced · happy path*


### [MAJOR] /finance/expenses is unreachable from the UI — no page anywhere links to it, yet the P&L's Expenses and Net Profit depend on it

**Steps** — LIVE, as fin.dalia. 1) Load /, /finance/, /finance/invoices, /finance/reports and /finance/estimates and search each page's HTML for any href containing "expense". 2) Open the sidebar BUSINESS group and the Ctrl+K command palette. 3) Then type /finance/expenses in the address bar.

**Expected** — A finance user can reach the Expenses screen by clicking, from the finance dashboard or the sidebar.

**Actual** — Zero links on all five pages, nothing in the sidebar, nothing in the command palette (which does carry an Estimates chip). Confirmed by grep too: the string "/finance/expenses" and url_for('finance.expenses_list') appear only inside expenses_list.html itself (its own Reset link and its own form action). Typing the URL renders a perfectly good page with a working add-expense form. Meanwhile /finance/reports prints Expenses and Net Profit cards — so a clinic reads a Net Profit that equals gross revenue because it never found the screen where rent, salaries and supplier bills go in.

**Cause** — Route exists at blueprints/finance/routes.py:647 with a template at templates/finance/expenses_list.html; no template references it. templates/base.html:189 links only finance.dashboard, and templates/finance/dashboard.html links only invoice_new, invoices_list and reports.

**Fix** — One <a> on the finance dashboard action bar next to "All Invoices" (and/or the Expenses card on /finance/reports linking through), gated the same way the route is — role_required super_admin/clinic_owner/branch_manager/finance/auditor, so reception is not shown a link she gets bounced from.

*reproduced · happy path*


### [MAJOR] Editing an invoice down below what has already been paid leaves due_amount negative and status 'Paid' — the client's overpayment vanishes

**Steps** — LOCAL, signed in as a finance user. 1) Create a 1,000 invoice. 2) Take a 800 cash payment — status goes Partial, due 200. 3) Realise a line was billed wrong: open Edit, change the line to 300, save. Flash: "Invoice updated successfully."

**Expected** — Either the edit is refused (the invoice already has money against it), or the 500 overpayment is surfaced — as client account credit, a refund due, or at minimum a visible warning.

**Actual** — The invoice is stored as total 300, paid_amount 800, due_amount -500, status 'Paid'. The payments ledger still correctly holds 800. The 500 the clinic now owes the client appears on no screen: the dashboard Outstanding sum only reads Unpaid/Partial rows so it excludes this one, and the invoice itself just says Paid. Reducing a partly-paid invoice is an everyday correction (wrong item, wrong quantity) and it silently absorbs the client's money.

**Cause** — blueprints/finance/routes.py:426-428 — due_amount = round(total - paid_amount, 2) with no floor, then status = "Paid" if due_amount <= 0.

**Fix** — Guard before the UPDATE: if total < paid_amount, refuse with a flash pointing at the credit-note / refund path ("this invoice already has 800.00 against it — issue a credit note instead"). That mirrors the guard already in place for fully Paid invoices at routes.py:378.

*reproduced · happy path*


### [MAJOR] A credit note can be issued for any amount, with no cap against the invoice

**Steps** — 1) Create a 200 EGP invoice. 2) POST the credit-note form with amount = 99999.

**Expected** — "A credit note cannot exceed the 200.00 on this invoice."

**Actual** — Accepted. A new invoice is created with total = -99,999.00, due_amount = -99,999.00, status 'Unpaid', and the original is marked Cancelled. Combined with the first finding, that single mistyped credit note moves the clinic's Outstanding figure by -99,999 and shows up in the Unpaid invoice list. Nothing in the app can undo it — there is no delete path and editing it just changes it to something else.

**Cause** — blueprints/finance/routes.py:487-492 — money.form_amount() parses the amount and the only check is `if amount <= 0`. There is no comparison against invoice['total'] or invoice['paid_amount']. Note the sibling guards elsewhere in the same codebase do this properly: apply_credit caps at the balance and the due (models/database.py:3690, 3697), and payments.refund caps at the captured amount (models/payments/__init__.py:236).

**Fix** — After the `<= 0` check at routes.py:490, add `if amount > (invoice.get('total') or 0): flash(...)`. Same shape as the message payments.refund already produces.

*reproduced · money & records*


### [MAJOR] The Credit Note button has no double-submit guard — three clicks make three credit notes

**Steps** — 1) Create a 500 EGP invoice. 2) Press Credit Note for 500. 3) The page redirects to the new credit note; go back and press it twice more (or double-click, or refresh the POST).

**Expected** — The second attempt is refused — the invoice is already cancelled.

**Actual** — Three separate credit notes exist, totalling -1,500 against a 500 EGP invoice. Outstanding moves by -1,500 (or -2,000 counting the cancelled original per the first finding). The estimate-conversion route right next door is explicitly guarded against exactly this (models/database.py:3593-3607: "two clicks on 'Convert' would otherwise bill the client twice") and invoice payments are guarded by the due-amount cap — the credit-note route is the one that was missed.

**Cause** — blueprints/finance/routes.py:482 — invoice_credit_note() re-reads the invoice but never checks whether it is already cancelled or already has a credit note against it.

**Fix** — Same pattern as convert_estimate: refuse when `invoice['status'] == 'Cancelled'`. Two lines after the get_invoice at routes.py:483.

*reproduced · money & records*


### [MAJOR] Two staff saving an invoice at the same moment: one loses it to a raw "UNIQUE constraint failed" error

**Steps** — Two receptionists press Save on /finance/invoices/new within the same moment. Reproduced with 8 concurrent test clients posting the form: 4 invoices were created, 4 failed. The user sees the flash "Error creating invoice: UNIQUE constraint failed: invoices.invoice_number" and everything typed is gone.

Deterministic proof of the underlying race: calling db._next_invoice_number() twice with no insert in between returns the same string (INV-2026-00005 / INV-2026-00005).

**Expected** — Both invoices save with consecutive numbers.

**Actual** — Whoever commits second gets a UNIQUE violation on invoices.invoice_number and loses the invoice with a database error message in front of a client. On PostgreSQL (the live deployment) invoice_number carries a UNIQUE constraint, confirmed on the demo: "invoices_invoice_number_key" UNIQUE CONSTRAINT.

Second consequence of the same code: the number is derived from COUNT(*), so if a single invoice row is ever removed (a manual SQL cleanup, a restore), COUNT permanently trails MAX and EVERY subsequent invoice creation collides forever — I hit this accidentally mid-audit and could not create another invoice in that database until I stopped deleting.

**Cause** — models/database.py:3418-3422 — _next_invoice_number() does SELECT COUNT(*), closes the connection, and formats the number; the INSERT happens in a separate transaction at :3441. Nothing serialises the two. models/database.py:3494-3501 already documents this exact defect verbatim ("_next_invoice_number() uses COUNT(*), which repeats a number as soon as any row is deleted -- and invoice_number is UNIQUE, so the next insert raises") and _next_estimate_number deliberately does not copy it — but the invoice generator was left as-is.

**Fix** — MAX(id)+1 the way _next_estimate_number already does fixes the deletion half but not the race. The race needs the number allocated inside the same transaction as the INSERT (move the SELECT inside the `with conn:` at :3440), or a retry loop around the UNIQUE violation. Either is a small diff; the current code is the only one of the two generators without a fix.

*reproduced · money & records*


### [MAJOR] The header discount is uncapped, in the UI and on the server — a discount larger than the bill produces a negative invoice

**Steps** — 1) /finance/invoices/new. 2) One line: Consultation, 200 EGP. 3) In the Discount box under Totals choose "Value" and type 500 (or choose "Percent" and type 300). 4) Save. No dev tools needed — templates/finance/invoice_form.html:136 declares the field `min="0" step="0.01"` with no max, unlike tax_rate (max=100) and the per-line discount (max=100) right beside it.

**Expected** — "The discount cannot exceed the 200.00 subtotal", or the discount clamps to the subtotal.

**Actual** — Saved: subtotal 200.00, discount_amount 500.00, total -300.00, due_amount -300.00, status 'Unpaid'. Percent mode with 300: discount 600.00, total -400.00. A negative invoice then behaves like the credit-note rows in the first finding — it sits in the Unpaid list and pulls the Outstanding figure down by its own value. A mistyped discount (500 meant as 50) silently corrupts the receivables total.

**Cause** — models/database.py:3435 — `disc_amt = round(disc_val, 2) if disc_type == "value" else round(subtotal * disc_val / 100, 2)`, with no clamp; models/database.py:3518 for estimates, and blueprints/finance/routes.py:423 for the edit path, all identical. Template templates/finance/invoice_form.html:136 and estimate_form.html:130 have no max attribute.

**Fix** — One clamp in the shared arithmetic, models/database.py:3435 and the identical line in _money() at :3518: `disc_amt = min(disc_amt, subtotal)`. invoice_edit at routes.py:423 should call _money() rather than repeating the formula a third time. (The per-line discount has the same hole at routes.py:204 but max="100" in the template blocks it in a browser, so it is a lower priority.)

*reproduced · money & records*


### [MAJOR] /finance/reports: two panels ignore the date filter the page is titled with

**Steps** — 1) Create an invoice dated 120 days ago for 'ZOLD SERVICE', 4,321 EGP. 2) Open /finance/reports?date_from=<today>&date_to=<today>. The page header reads "<today> → <today>".

**Expected** — Everything on a page subtitled with a date range is about that date range.

**Actual** — 'ZOLD SERVICE' from 120 days ago appears in the Top Services table. And the Outstanding stat card in the summary row reads the all-time figure (3,332 in my run) while the Revenue / Expenses / Net cards beside it are correctly date-filtered. An owner comparing months reads two of the six numbers as if they were the month's when they are the whole history's.

(The daily-revenue chart is also fixed at 30 days regardless of the filter, but it is honestly labelled "Daily Revenue — Last 30 Days", so that one is fine.)

**Cause** — blueprints/finance/routes.py:762 calls `db.get_top_services(limit=10)`, which takes no date arguments at all (models/database.py:3821-3827). models/database.py:3771-3772 — get_finance_summary's outstanding query has no BETWEEN clause while every other figure in the same function does.

**Fix** — Give get_top_services(date_from, date_to) the same JOIN + BETWEEN the revenue_by_type query at routes.py:741-749 already uses, and pass df/dt into the outstanding query at models/database.py:3771. Both are one-line changes to existing SQL.

*reproduced · money & records*


### [MINOR] Top Services on the Financial Reports page ignores the date filter and counts Cancelled invoices

**Steps** — Live demo: open https://demo.aleefy.online/finance/reports?date_from=2019-01-01&date_to=2019-12-31 and scroll to 'Top Services'.

**Expected** — Empty, or labelled 'all time' so nobody reads it as belonging to the filter.

**Actual** — The summary cards read Revenue 0 and '0 invoices issued', and directly beneath, Top Services lists 'General Consultation 279 / 97,650.00' and 'Mass Removal 11 / 38,500.00' — all-time data with no label, under a filter that says the period had no activity. Locally I also confirmed the query counts lines from Cancelled invoices: a Cancelled 800 EGP 'Dental scale' still appears with revenue 800.00. (The daily-revenue chart alongside it is also unfiltered, but it is at least labelled 'last 30 days'.)

**Cause** — blueprints/finance/routes.py:762 calls db.get_top_services(limit=10) with no date arguments; models/database.py:3821-3828 has no date parameters and no status filter — it reads invoice_lines with only `line_type='service'`.

**Fix** — Give get_top_services(date_from, date_to) parameters, join invoices and add `AND i.status != 'Cancelled'`, and pass the page's filter through.

*reproduced · money & records*


### [MINOR] The printed invoice and the PDF never show the payment history — the receipt the client takes home has no proof of payment

**Steps** — Live demo: open /finance/invoices/1965 (a Paid invoice), then /finance/invoices/1965/print. Locally: pay a 500 invoice by Instapay with reference IP-778899, then fetch /print and /pdf.

**Expected** — The receipt shows how, when and by whom the money was taken — both templates draw exactly that block.

**Actual** — Live: the detail page shows 'Cash · 2026-08-06 · rec.mahmoud'; the print page shows nothing. Locally: 'IP-778899' appears on the detail page and appears in neither the print HTML nor the decompressed PDF streams; the PDF contains no 'Payment History' heading and no 'Instapay'. Both blocks are dead code — templates/finance/invoice_print.html:112 `{% if invoice.payments %}` and models/pdf_generator.py:518 `payments = invoice.get("payments") or []` can never be true.

**Cause** — models/database.py:3474 — get_invoice() sets `inv["payments"] = []` unconditionally. Only invoice_detail (blueprints/finance/routes.py:279-283) replaces it with the real rows; invoice_print (:544) and invoice_pdf (:558) use get_invoice() as-is.

**Fix** — Move the SELECT from blueprints/finance/routes.py:280-283 into models/database.py get_invoice(). One change fixes the print page, the PDF, and anything else that calls it.

*reproduced · money & records*


### [MINOR] A mistyped amount on Apply Credit and Credit Note is reported with the wrong reason

**Steps** — On an invoice with held credit available, POST /finance/invoices/<id>/apply-credit with amount=5O (letter O). Same shape on POST /finance/invoices/<id>/credit-note.

**Expected** — '"5O" is not a valid amount' — money.form_amount() returns exactly that string as its second element.

**Actual** — The error is discarded, amount becomes 0.0, and the user is told 'the amount to apply must be positive' (credit note: 'Credit note amount must be greater than zero'). The balance is correctly untouched, so no money moves — but the message sends the user hunting for a sign problem instead of the typo. Verified: balance stayed 300.00 across the attempt.

**Cause** — blueprints/finance/routes.py:1071-1073 discards the error by indexing `money.form_amount(...)[0]`; blueprints/finance/routes.py:487-489 assigns it to `_err` and never checks it. The two other call sites in this file (invoice_pay :323, owner_credit :1023) do check it.

**Fix** — Check the second return value and flash it, the way invoice_pay already does.

*reproduced · money & records*


### [MINOR] Negative quantities, negative prices and line discounts over 100% all save as negative invoices

**Steps** — POST /finance/invoices/new with qty[]=-3, or unit_price[]=-100, or discount[]=200 (the last is blocked client-side by max=100 but not server-side; the first two are reachable from any stale or non-browser submit).

**Expected** — Rejected with a message.

**Actual** — qty=-3 -> subtotal -300, total -300, due -300. unit_price=-100 -> total -100. discount=200 -> line total -100. Negative invoices land in the Unpaid list and net against the clinic's outstanding total, understating what clients actually owe.

**Cause** — blueprints/finance/routes.py:201-214 (and the identical block at :399-412 and :904-917) validates nothing about sign or range before storing.

**Fix** — Validate qty>0, unit_price>=0, 0<=discount<=100 server-side in all three line-parsing blocks.

*reproduced · edge cases*


### [MINOR] A mistyped year on an invoice or expense makes it disappear from every report

**Steps** — On /finance/invoices/new set the date picker to 2099-12-31 (a plausible fat-finger for 2026) and save. Then look at /finance/reports for this month, and at the invoice list filtered by date. Also verified that a literal 'not-a-date' or '2026-13-45' is stored verbatim — issue_date is TEXT on the live PostgreSQL too (checked information_schema on aleefy_demo), so nothing rejects it at any layer.

**Expected** — Either a warning about a date far in the future, or at minimum the invoice still findable.

**Actual** — The invoice is stored with issue_date='2099-12-31' and is excluded from the P&L, the revenue chart, the daily/monthly dashboard cards and every date-filtered list, forever. Same for an expense dated wrong: it shows in the expense list total but not in the P&L, so the two screens disagree and nobody can see why.

**Cause** — blueprints/finance/routes.py:232 (issue_date) and :670 (expense_date) accept whatever arrives; models/database.py stores dates as TEXT with no validation and every report uses BETWEEN.

**Fix** — Validate with date.fromisoformat() and reject dates outside a sane window (say issue_date within a year either side of today) with a confirm-or-correct message.

*reproduced · edge cases*


### [MINOR] Applying account credit twice by double-clicking spends twice the intended credit

**Steps** — Owner has 200 EGP on account, invoice owes 300. Click Apply credit for 50 twice.

**Expected** — 50 applied once.

**Actual** — Balance 200 -> 100 and paid_amount 100: 100 of the client's credit spent for one intended 50. It can never exceed the balance or the amount due (both are re-checked), so no money is created — but the client's account is drained faster than the staff member intended and there is no undo in the UI.

**Cause** — blueprints/finance/routes.py:1055-1069 and models/database.py:3669 — no idempotency key, same root cause as the double-click payment finding. templates/finance/invoice_detail.html:209-219 has no submit guard.

**Fix** — Same fix as the payment double-click: a per-page nonce carried into add_payment as idempotency_key.

*reproduced · edge cases*


### [MINOR] A non-numeric expense amount 500s

**Steps** — POST /finance/expenses with amount='abc' or amount='1,500' and a description.

**Expected** — "1,500 is not a valid amount."

**Actual** — HTTP 500, ValueError: could not convert string to float. Not reachable from Chrome or Firefox (the field is required and type=number), but reachable from any non-browser client, an older Safari, and from anything that posts the form directly. Note the '1,500' case matters: staff type thousands separators, and money.form_amount() already handles them everywhere else.

**Cause** — blueprints/finance/routes.py:652 `amount = float(f.get("amount") or 0)`.

**Fix** — Use money.form_amount() here as the payment route already does.

*reproduced · edge cases*


### [MINOR] An expired estimate can be approved and converted to an invoice with no warning

**Steps** — Create an estimate with Valid until in the past (or let one expire), mark it Approved, then click Convert to invoice.

**Expected** — At least a warning that the quote expired on <date>.

**Actual** — Converts silently into a full invoice at last year's prices. valid_until is stored but never checked by any route; a 1999 valid_until is accepted at creation time without comment.

**Cause** — blueprints/finance/routes.py:957-987 — estimate_decide and estimate_convert never look at valid_until; models/database.py:3593-3630 convert_estimate checks only status and invoice_id.

**Fix** — Warn (or require an explicit override) when valid_until is in the past, in both decide and convert.

*reproduced · edge cases*


### [MINOR] An expense can never be corrected or deleted, so one typo permanently destroys the P&L

**Steps** — Local, finance role. POST /finance/expenses with description="Typo rent", amount=1000000 (a slipped zero on 100,000). Then look for any way to fix it: GET /finance/expenses/<id>, /finance/expenses/<id>/edit, /finance/expenses/<id>/delete.

**Expected** — An edit or delete on the expense row, or at least a reversing entry.

**Actual** — All three return 404 — the blueprint has only a list+create route. Net profit for the day is now -1,000,000.00 and there is no route in the application that can change it. Recovering requires direct database access.

**Cause** — platform/blueprints/finance/routes.py:647-713 — expenses_list is the only expense route.

**Fix** — Add a delete (or a void/reversal) route for expenses, restricted to the same roles that can create them.

*reproduced · edge cases*


### [MINOR] "Not a valid amount" errors are reported as "must be greater than zero", because the parser's error message is discarded

**Steps** — Local. (a) POST /finance/invoices/<id>/credit-note with amount="abc". (b) POST /finance/invoices/<id>/apply-credit with amount="abc" or empty.

**Expected** — "'abc' is not a valid amount" — the message money.form_amount() returns and which the payment box (routes.py:324-327) shows correctly.

**Actual** — (a) "Credit note amount must be greater than zero." (b) "the amount to apply must be positive". Both discard the real reason, so the user is told a number they never typed is too small. Nothing is written in either case, so no money is at risk — it is purely a wrong message on a money screen.

**Cause** — platform/blueprints/finance/routes.py:487-489 (`amount, _err = money.form_amount(...)` with _err never checked) and :1064 (`money.form_amount(...)[0]`).

**Fix** — Check the error and flash it, the same three lines as invoice_pay.

*reproduced · edge cases*


### [MINOR] An invoice can be saved against a pet belonging to a different client

**Steps** — Local, admin. POST /finance/invoices/new with owner_id = Client A and pet_id = a pet owned by Client B.

**Expected** — Rejected — the pet does not belong to the client being billed.

**Actual** — Accepted. The invoice detail page renders and shows Client A's name above Client B's pet "Bella". No server-side check that pets.owner_id matches invoices.owner_id. Reachability caveat, stated honestly: the form's filterPets() JS (templates/finance/invoice_form.html:172-180) hides non-matching options, so a desktop Chrome user will not stumble into this — but it hides them with `option.style.display='none'`, which several browsers (notably Safari, i.e. an iPad at the front desk) ignore for <option> elements, leaving every pet selectable with no server-side backstop. I reproduced the server accepting it; I did not reproduce it in Safari.

**Cause** — platform/blueprints/finance/routes.py:227-242 — pet_id is taken from the form and inserted with no ownership check.

**Fix** — One SELECT in create_invoice/invoice_new: if pet_id is given and its owner_id is not the invoice's owner_id, reject.

*reproduced · edge cases*


### [MINOR] An expired estimate converts to an invoice with no warning

**Steps** — Local, admin. Create an estimate with issue_date 2020-01-01 and valid_until 2020-01-15, mark it Approved, then POST /finance/estimates/<id>/convert.

**Expected** — A warning that the quote expired six years ago, or a refusal.

**Actual** — An invoice is created silently at the 2020 prices, dated today. estimate_convert never looks at valid_until — the field is collected on the form and used for display only. A clinic that quotes surgery in January and bills it in November bills January's prices.

**Cause** — platform/models/database.py:3593-3628 (convert_estimate checks status and invoice_id, never valid_until); platform/blueprints/finance/routes.py:978-987.

**Fix** — Warn (or require a confirm) when valid_until is in the past at conversion time.

*reproduced · edge cases*


### [MINOR] A Cancelled (credit-noted) invoice can be re-opened through /edit and returns to the receivables queue

**Steps** — LOCAL, as a finance user. 1) Create a 1,000 invoice, take the full 1,000 payment. 2) Issue a full credit note for 1,000 — the original correctly flips to status 'Cancelled'. 3) The detail page correctly stops showing the Edit button. But GET /finance/invoices/<id>/edit still returns 200 with a live form (a stale tab, the browser Back button, or a bookmark gets you there). 4) Change the line to 9,999 and save.

**Expected** — Editing a Cancelled invoice is refused, the same way a Paid one is.

**Actual** — Flash: "Invoice updated successfully." The voided invoice comes back as total 9,999, paid 1,000, due 8,999, status 'Partial' — a cancelled bill silently re-enters accounts receivable, while its credit note still exists.

**Cause** — blueprints/finance/routes.py:378 blocks only `if invoice["status"] == "Paid"`. 'Cancelled' is not in the guard.

**Fix** — Widen the existing guard to `if invoice["status"] in ("Paid", "Cancelled")`. Same flash, one word changed.

*reproduced · happy path*


### [MINOR] "Top Services" on /finance/reports ignores the report's own date filter and includes cancelled invoices

**Steps** — LIVE, as fin.dalia. 1) Open /finance/reports?date_from=2026-08-07&date_to=2026-08-07 (a single day — the page subtitle shows that range). Scroll to the Top Services table. 2) Open /finance/reports?date_from=2026-01-01&date_to=2026-12-31 and compare the same table.

**Expected** — A revenue table on a date-filtered report reflects the chosen range.

**Actual** — Byte-identical for both: General Consultation 276 / 96,600.00, Mass Removal 11 / 38,500.00, CBC Blood Count 63 / 28,350.00, and so on. The one-day report shows a year of revenue in a column headed "Revenue (EGP)" under a page subtitle that reads 2026-08-07 -> 2026-08-07. The Daily Revenue chart above it is at least honestly labelled "Last 30 Days"; this one is not labelled at all. The same query also has no join to invoices, so lines from Cancelled invoices are counted.

**Cause** — blueprints/finance/routes.py:762 calls db.get_top_services(limit=10); models/database.py:3821 selects from invoice_lines with no date bound and no invoices join.

**Fix** — Give get_top_services() date_from/date_to arguments, join invoices and add `AND i.status != 'Cancelled'`, then pass the page's range from routes.py:762.

*reproduced · happy path*


### [MINOR] Reception sees a "Full Report" link on the finance dashboard that bounces her straight back out

**Steps** — LIVE. Sign in as rec.yasmine / Demo@1234. Open /finance/ — the page loads, and the Revenue chart header carries a "Full Report ->" link to /finance/reports (confirmed present in the served HTML). Click it.

**Expected** — Either the link is not shown to a role that cannot open it, or it opens.

**Actual** — 302 straight back to the main dashboard. Reception can load the finance dashboard, the invoices list, invoice detail and the payment form (she needs those), but /finance/reports and /finance/expenses are role-gated to finance/owner/manager/auditor — correctly, per the comment at routes.py:640. The dashboard just never got the matching template gate, so it advertises a door she cannot walk through. This is the same shape as the two dead dashboard cards that survived for months.

**Cause** — templates/finance/dashboard.html:75 renders url_for('finance.reports') unconditionally; the route is gated at blueprints/finance/routes.py:727-728.

**Fix** — Wrap that <a> in the same role check the route uses — the template already has session["user"]["role"] available.

*reproduced · happy path*


### [MINOR] The WhatsApp invoice message is hardcoded to "Aleefy" and never reads the clinic record, unlike the print and PDF paths

**Steps** — LOCAL. Open any invoice and press Send via WhatsApp (POST /finance/invoices/<id>/whatsapp). Read the message body the route builds. Compare with /finance/invoices/<id>/print and /pdf, which both call db.get_clinic() and render the tenant's own name and letterhead.

**Expected** — In a product where every clinic gets its own tenant database and its own branding, the invoice a client receives on WhatsApp carries that clinic's name.

**Actual** — Every tenant's clients receive a message headed "🐾 *Aleefy*" and signed "Thank you for choosing Aleefy 🐾 / Happy Pets, Healthy Lives". invoice_whatsapp() never calls db.get_clinic(). The arithmetic in the message is correct (subtotal, discount, tax, total, paid, balance all read from the invoice), only the branding is wrong. On this deployment WhatsApp is not configured so the flash reads "WhatsApp is not configured. Set the Wapilot API token…" — clear and actionable, that part is fine.

**Cause** — blueprints/finance/routes.py:598-615.

**Fix** — clinic = db.get_clinic() at the top of the function and interpolate clinic.get('name') into the header and footer, matching invoice_print at routes.py:550.

*reproduced · happy path*


### [MINOR] Paying from account credit awards zero loyalty points; the same amount paid in cash awards 100

**Steps** — LOCAL, as a finance user, one owner. 1) Take a 1,000 deposit on /finance/owners/<id>/credit. 2) Raise a 1,000 invoice and settle it with Apply Credit. Read owners.loyalty_balance. 3) Raise a second 1,000 invoice and settle it with a cash payment on the invoice page. Read the balance again.

**Expected** — 1,000 EGP of business earns the same points however the client settles it.

**Actual** — Apply Credit -> +0 points. Cash -> +100 points. The client who prepaid a surgery deposit is quietly penalised for it, and the flash on the credit path ("Credit applied to the invoice.") never mentions points, so nobody notices the inconsistency until a client compares.

**Cause** — _award_points() is called only from blueprints/finance/routes.py:346 inside invoice_pay. db.apply_credit() (models/database.py:3705) calls add_payment() directly and bypasses it.

**Fix** — Call _award_points() in invoice_apply_credit (routes.py:1062) after db.apply_credit() succeeds, in the same try/except shape as invoice_pay — or, cleaner and one call site fewer, move the award into models.payments.capture() so every settlement path gets it.

*reproduced · happy path*


### [MINOR] Apply-credit reports a mistyped amount as "must be positive" instead of naming the typo

**Steps** — LOCAL. On an invoice with credit available, submit the Apply Credit form with amount "abc" (or blank).

**Expected** — "'abc' is not a valid amount" — the message models/money.form_amount already produces and that the payment box on the same page already shows.

**Actual** — "the amount to apply must be positive". Nothing is written (safe), but the user is told the wrong thing about a field they can see has text in it. Small, but this is the same page where the payment box gets it right, so the inconsistency is visible side by side.

**Cause** — blueprints/finance/routes.py:1064 — money.form_amount(...)[0] discards the error string, so a parse failure silently becomes 0.0 and trips apply_credit()'s positivity guard.

**Fix** — Unpack both values and flash the error, as invoice_pay does at routes.py:324-327. Three lines.

*reproduced · happy path*


### [MINOR] Top Services counts revenue from cancelled and voided invoices

**Steps** — 1) Create an invoice with one line 'ZZZ CANCELLED SERVICE' at 5,000 EGP. 2) Issue a full credit note (invoice becomes Cancelled). 3) Look at Top Services on /finance/reports.

**Expected** — A voided invoice contributes nothing.

**Actual** — 'ZZZ CANCELLED SERVICE' is still listed with revenue 5,000.00 and count 1. The panel next to it (Revenue by Line Type) does filter cancelled invoices; Top Services does not.

**Cause** — models/database.py:3821-3827 — get_top_services selects straight from invoice_lines with no join to invoices, so it cannot see status at all.

**Fix** — Add the same `JOIN invoices i ON i.id = il.invoice_id ... AND i.status != 'Cancelled'` that revenue_by_type uses at blueprints/finance/routes.py:744-746. Fold into the date-filter fix above — it is the same query.

*reproduced · money & records*


### [MINOR] Every money column on the live PostgreSQL deployment is `real` (float4); the migration written to fix it has never been run anywhere

**Steps** — On the demo server: `sudo -u postgres psql -d aleefy_demo -c "\d invoices"` shows subtotal, discount_amount, tax_amount, total, paid_amount, due_amount all typed `real`. Across the schema: 21 money columns are `real`, 1 is `numeric`. Same on aleefy_platform. There is no alembic_version or schema_migrations table in either database — no migration has ever been applied.

**Expected** — The money columns are NUMERIC(12,2), as db_migrations/versions/0002_money_numeric.py was written to make them.

**Actual** — `real` is 4-byte float — about 7 significant decimal digits. Measured on the demo's own data: SUM(amount) over the 329 payment rows returns 437,724.84 as `real` versus 437,724.82 exact — 2 piastres of accumulated error on one query, growing with row count and invoice size. Individual values still display correctly (I created a 12,345.67 invoice through the demo UI and it reads back 12,345.67 on screen and on the print view), so this is drift in totals rather than corrupted invoices today. It gets worse as a clinic accumulates history and as invoice values grow.

The reason this is worth the owner's time is not the 2 piastres — it is that the fix is already written, already tested ("Tested on a copy of the live database: 84 tables' row counts unchanged, all 499 money values round-trip to the same 2-dp amount" per its own docstring) and has never been run. And the SQLite test suite cannot see it: SQLite REAL is a 64-bit double, so all 1,781 tests pass on a type that behaves differently from the one in production.

**Cause** — models/database.py:1601-1609 (and ~18 more sites) still declare money columns as REAL in the base DDL, so every newly provisioned clinic gets float4 too — running the migration once on the demo would not stop the next clinic getting it. db_migrations/versions/0002_money_numeric.py is the fix, unapplied.

**Fix** — Run 0002_money_numeric against both live databases, and change the REAL declarations in the models/database.py DDL to NUMERIC(12,2) so freshly provisioned clinics start correct. Verification query for afterwards: `SELECT data_type, count(*) FROM information_schema.columns WHERE table_schema='public' AND column_name IN ('total','subtotal','amount','paid_amount','due_amount','unit_price') GROUP BY data_type` should report numeric only.

*reproduced · money & records*


### [MINOR] Printed invoice: unit price x quantity does not equal the line total a client can check

**Steps** — 1) Create an invoice with one line: quantity 3, unit price 33.333 (a per-ml or per-kg drug price). 2) Open /finance/invoices/<id>/print.

**Expected** — The three numbers on the printed line are consistent with each other.

**Actual** — The printed line reads unit price 33.33 and line total 100.00. 33.33 x 3 = 99.99. A client checking the arithmetic on their own invoice finds a piastre that is not explained by anything on the page. The header is internally correct (subtotal 100.00 - discount 7.50 + tax 12.95 = total 105.45, verified against the database, the detail screen and the print view — all three agree), so this is only the unit-price display.

**Cause** — models/database.py:3432 rounds each line total to 2dp (3 x 33.333 = 99.999 -> 100.00) but stores unit_price unrounded at :3457, and the template formats it to 2dp on the way out. The rounded unit price and the rounded line total are computed from different precisions.

**Fix** — Round unit_price to 2dp on save, at models/database.py:3457, so what is stored is what is printed and multiplies out. Anything that genuinely needs sub-piastre unit pricing needs a stated unit ('per 10 ml') rather than a hidden third decimal.

*reproduced · money & records*


### [INFO] Expenses accept a date decades in the future with no warning

**Steps** — POST /finance/expenses with description=Rent, amount=50000, category=Rent, expense_date=2099-12-31.

**Expected** — A fat-fingered year is at least questioned.

**Actual** — Saved as-is: {'description': 'Rent', 'amount': 50000.0, 'expense_date': '2099-12-31'}. It vanishes from every P&L for the next 73 years, so a real 50,000 EGP expense typed with the wrong year silently overstates net profit and is very hard to find again.

**Cause** — blueprints/finance/routes.py:648-668 — expense_date is inserted with no range check.

**Fix** — Reject an expense_date more than a few days in the future, or flag it on the list screen.

*reproduced · money & records*


### [INFO] An unrecognised payment method is silently filed as Cash

**Steps** — POST /finance/invoices/<id>/pay with method='Bitcoin' (reachable from a stale page whose method list no longer matches, or any direct submit).

**Expected** — Refuse, or record the label as given.

**Actual** — The ledger row reads method='Cash', channel='cash'. The evening drawer reconciliation will look for money in a drawer it was never in — exactly the failure models/payments/cash.py documents for the Insurance method. The fallback is deliberate (gateway_for_method says so) but it discards the label instead of preserving it.

**Cause** — models/payments/__init__.py gateway_for_method() falls back to 'cash', and _succeed() writes get(gateway).label rather than the submitted method string.

**Fix** — Keep the submitted label on the ledger row when it is not in the alias table, even while routing it through the cash gateway.

*reproduced · edge cases*


## Whatsapp  (57)

### [BLOCKER] The nightly job cannot use the WhatsApp token/instance saved in the UI — it only reads $WAPILOT_TOKEN, and posts to a different API than the rest of the blueprint

**Steps** — Connect WhatsApp the only way the product offers: WhatsApp → Settings, enter the Wapilot API token and Instance ID, Save. The Control Center then works (it builds its client from the settings table). Now wait for 09:00, or press WhatsApp → Scheduler → Run. Local repro: platform/tests/test_zzz_wa_integrity_probe.py::test_D_ui_token_reaches_the_nightly_job — writes wapilot_token/wapilot_instance_id into settings with no env var set, calls scheduler._send_whatsapp().

**Expected** — The reminder goes out through the same configured instance the Send Center uses.

**Actual** — scheduler._send_whatsapp returns 'Not Configured' and writes a whatsapp_log row saying "WhatsApp is not connected — no API token is set. Connect it under WhatsApp → Settings" — the very thing the owner just did. The scheduler never calls _client()/WapilotClient: it reads os.environ['WAPILOT_TOKEN'] only, ignores the instance ID entirely, and when a token IS present it POSTs to https://api.wapilot.io/send with an `Authorization: Bearer` header and {phone, message}, while WapilotClient posts to https://api.wapilot.net/api/v2/{instance}/send-message with a `token` header and {chat_id, text}. Different host, different auth, different body, no instance. On the live demo every one of today's 110 reminder log rows reads 'Not Configured'.

**Cause** — platform/blueprints/whatsapp/scheduler.py:72 (token from env only) and :78 (api.wapilot.io/send) vs platform/blueprints/whatsapp/wapilot.py:11 + :119 and platform/blueprints/whatsapp/routes.py:32 _client()

**Fix** — Have _send_whatsapp build the client through routes._client() (settings table, env fallback) and send via WapilotClient.send_message, so one configuration and one endpoint serve both the interactive and the scheduled path.

*reproduced · money & records*


### [BLOCKER] An unpaid invoice is WhatsApped to the client every single day, forever, until it is paid

**Steps** — One invoice, status Unpaid or Partial, due_date 3+ days ago, owner has a whatsapp_phone. Let the 09:00 job run on five consecutive days (or press Scheduler → Run Invoice Reminders on five days). platform/tests/test_zzz_wa_integrity_probe.py::test_A_invoice_reminder_repeats_every_single_day, with urlopen counted.

**Expected** — The client is chased once, or on a defined cadence (weekly, escalating). The module docstring claims "Deduplication via reminder_runs table to prevent double-sending".

**Actual** — 5 days = 5 real HTTP sends for the same invoice, and it never stops. The dedup gate is per-CALENDAR-DAY (_already_sent compares DATE(run_at) to today), so it only blocks a second run on the same day; the next morning the same invoice is eligible again and _mark_sent just refreshes run_at. Live demo: reminder_runs shows the identical 107 invoices reminded on 2026-08-05 and again on 2026-08-06 — 107 messages a day to 48 people, and one owner (Moataz Elbanna, 7 unpaid invoices) receives 7 separate messages every day because the job iterates invoices, not owners. At a real clinic that is ~39,000 paid API messages a year and a WhatsApp number that gets reported as spam.

**Cause** — platform/blueprints/whatsapp/scheduler.py:41-46 (_already_sent, day-scoped) and :49-64 (_mark_sent refreshes rather than latches); _invoice_reminders at :175-203 re-selects every eligible invoice each run

**Fix** — Latch on the entity, not the day: skip when a reminder_runs row exists at all for (run_type, entity_id, entity_type), or gate on run_at older than a configured interval (e.g. 7 days) and cap the number of chases. Group invoice reminders by owner so one owner gets one message listing their balances.

*reproduced · money & records*


### [BLOCKER] The overdue-invoice message quotes the invoice TOTAL, not what is still owed — partly-paid clients are told they owe the full amount

**Steps** — Invoice total 1000, paid_amount 900, due_amount 100, status Partial, due_date 9 days ago. Run the invoice reminder job. platform/tests/test_zzz_wa_integrity_probe.py::test_B_partial_invoice_quotes_full_total.

**Expected** — "Invoice #X for 100.00 ... remains unpaid."

**Actual** — "Invoice #PROBE-PARTIAL-1 for 1000.00 was due on 2026-07-28 and remains unpaid." The SQL selects inv.total and the f-string formats inv['total'], while the invoices table carries paid_amount and due_amount right next to it. The job selects status IN ('Unpaid','Partial') — so every partly-paid client is dunned for money they already handed over. Live demo: the 107 messages tonight's run would send quote 145,740 EGP against 117,077.59 EGP actually outstanding — 28,662 EGP of debt invented across 48 clients, 55 of whom have already paid something.

**Cause** — platform/blueprints/whatsapp/scheduler.py:180 (SELECT inv.total) and :195 (message text)

**Fix** — Select and quote inv.due_amount (falling back to total - paid_amount when due_amount is stale), and word Partial invoices as a remaining balance.

*reproduced · money & records*


### [BLOCKER] Every button on /whatsapp/reminders is dead — no CSRF token in the form, so both actions 403

**Steps** — Sign in as rec.yasmine / Demo@1234 on https://demo.aleefy.online. Go to WhatsApp → Message Log → "Pending Reminders" (or /whatsapp/reminders directly). The demo shows 23 pending reminders. Click "✓ Mark Sent" on any row, or click "📱 Send WA", fill the modal and press "Send Message 📤". Reproduced locally: tests/test_zzz_wa_happy_audit.py::test_reminders_buttons_as_rendered renders the page, harvests the two <form>s exactly as the template emits them, and POSTs them.

**Expected** — Mark Sent flips reminders.status to 'Sent' and redirects back with "Reminder marked as sent."; Send WA writes a whatsapp_log row and reports the result.

**Actual** — Both return HTTP 403 "Invalid or missing security token. Please go back and try again." The reminder stays Pending, whatsapp_log gets 0 rows. Server log: "CSRF validation failed: /whatsapp/reminders/2/mark-sent" and "... /whatsapp/send". Confirmed on the live demo too — `curl -b cookies https://demo.aleefy.online/whatsapp/reminders | grep -c _csrf_token` returns 0 while the page renders 23 mark-sent forms.

**Cause** — D:\vet\platform\templates\whatsapp\reminders.html:93 and :122 — the two <form method="post"> blocks are the only whatsapp forms besides scheduler.html that never emit `<input type="hidden" name="_csrf_token" value="{{ csrf_token }}">`. app.py:300-307 enforces CSRF on every non-GET request app-wide.

**Fix** — Add `<input type="hidden" name="_csrf_token" value="{{ csrf_token }}">` inside both forms in reminders.html (the mark-sent form and the send modal form), matching what reminder_admin.html:76 already does.

*reproduced · happy path*


### [BLOCKER] The nightly reminder job ignores the Wapilot token saved in WhatsApp → Settings — every scheduled reminder logs "Not Configured" and is never sent

**Steps** — Configure WhatsApp → Settings with a valid API Token and Instance ID (saved to settings.category='wapilot'). Control Center then shows the instance connected and Send Center sends fine. Now go to /whatsapp/reminder-admin and press "Trigger Reminder Job" (or wait for 09:00). Reproduced locally: tests/test_zzz_wa_happy_audit.py::test_scheduler_uses_ui_token saves the token through the real /whatsapp/settings POST, then runs the appointment job.

**Expected** — The reminder job uses the token the clinic entered in the UI and sends the messages.

**Actual** — whatsapp_log row: status='Not Configured', error='WhatsApp is not connected — no API token is set. Connect it under WhatsApp → Settings.' Nothing reaches Wapilot (0 client calls captured). The live demo has 110 such rows out of 214 in whatsapp_log — the nightly job has been failing silently for the whole dataset.

**Cause** — D:\vet\platform\blueprints\whatsapp\scheduler.py:72 — `token = os.environ.get("WAPILOT_TOKEN", "")`. It never reads the settings table. The rest of the blueprint goes through `_client()` (routes.py:32-48), which reads settings first and falls back to env. scheduler.py:78 also posts to a different host and shape entirely (`https://api.wapilot.io/send`, Bearer auth, {phone, message}) than the client the whole app uses (`https://api.wapilot.net/api/v2/{instance}/send-message`, `token:` header, {chat_id, text}) — so even with WAPILOT_TOKEN exported it is calling a different API with no instance id.

**Fix** — Delete `_send_whatsapp` in scheduler.py and route all three job functions through `blueprints.whatsapp.routes._send_and_log` (or a shared helper built on `_client()`), so there is exactly one send path and one token source.

*reproduced · happy path*


### [BLOCKER] A reminder that failed to send is still recorded as sent in reminder_runs, so the retry the same day sends nothing

**Steps** — With WhatsApp unconfigured (or any transient send failure), run the appointment job — /whatsapp/reminder-admin → "Trigger Reminder Job". It logs "Not Configured". Now fix the configuration and press Trigger again the same day. Reproduced locally: tests/test_zzz_wa_happy_audit.py::test_dedup_blocks_retry_after_failed_send.

**Expected** — The second run retries the reminders that did not go out.

**Actual** — Second run sends 0. The first run wrote reminder_runs(run_type='appt_reminder', entity_id=1, status='sent') even though the message failed, and `_already_sent` matches on run_type+entity+date, so every failed reminder is skipped for the rest of the day. Live evidence: the demo has 214 reminder_runs rows for invoice_reminder against 110 whatsapp_log rows that say "Not Configured" — the runs table claims sent for messages that never left.

**Cause** — D:\vet\platform\blueprints\whatsapp\scheduler.py:135, :169, :200 — `_mark_sent(...)` is called unconditionally right after `_send_whatsapp`, and `_mark_sent` (line 49-64) hardcodes `status='sent'` regardless of the returned status.

**Fix** — Only call `_mark_sent` when `status == "Sent"` (or record the real status and have `_already_sent` match on `status='sent'` only).

*reproduced · happy path*


### [BLOCKER] The nightly reminder job can never deliver a message — it ignores the token saved in WhatsApp → Settings and posts to a different API than the one the app is configured for

**Steps** — Live demo, as admin: WhatsApp → Settings, enter the Wapilot API token + Instance ID, Save. Confirm the Control Center goes green and Send Center delivers a test message. Then WhatsApp → Scheduler → Run now (or wait for the 09:00 job). Local repro: tests/test_zzz_wa_integrity_probe.py::test_D_ui_token_reaches_the_nightly_job — writes wapilot_token to settings, calls sch._send_whatsapp(), asserts status != 'Not Configured'. Fails.

**Expected** — Reminders go out over the same WhatsApp connection the Settings screen just configured.

**Actual** — Nothing is transmitted. scheduler._send_whatsapp reads only os.environ['WAPILOT_TOKEN'] — it never touches the settings table, so the UI-saved token is invisible to it and every message is logged status='Not Configured'. Even with the env var set it POSTs https://api.wapilot.io/send with header 'Authorization: Bearer …' and body {"phone","message"} and no instance id, while the configured API (wapilot.py, used by every manual send) is https://api.wapilot.net/api/v2/{instance}/send-message with header 'token: …' and body {"chat_id","text"}. GET https://api.wapilot.io/send returns 404 (the host root does answer with a WAPILOT banner, so the host is right and the path is absent). Live demo aleefy_demo proves it end to end: whatsapp_log holds 107 invoice_reminder + 6 vaccine_reminder + 5 appt_reminder rows, ALL status='Not Configured', zero delivered — while reminder_runs holds 339 rows all marked status='sent'. (The 100 green 'Sent' rows in the Message Log are seed fabrications under a different template_name, 'appointment_reminder', which no code path produces.)

**Cause** — blueprints/whatsapp/scheduler.py:70-90 (_send_whatsapp: os.environ only, wrong host/path/auth header/body shape); contrast blueprints/whatsapp/routes.py:32-48 (_client reads settings) and blueprints/whatsapp/wapilot.py:11,111-119

**Fix** — Delete _send_whatsapp's hand-rolled urllib call and route it through routes._client() / WapilotClient.send_message(chat_id, text) so it uses the same settings-backed token, instance id, host and body shape as every manual send. Format the phone as {digits}@c.us exactly as routes._send_and_log does.

*reproduced · money & records*


### [BLOCKER] Overdue-invoice WhatsApp quotes the invoice TOTAL, not what the client still owes — 50 live clients would be over-billed by EGP 28,662

**Steps** — Create an invoice for 1000, take a 900 payment (status becomes 'Partial', paid_amount 900, due_amount 100), let the due date pass by 3+ days, run the invoice reminder job. Local repro: tests/test_zzz_wa_integrity_probe.py::test_B_partial_invoice_quotes_full_total.

**Expected** — "Invoice #X for 100.00 …" — the outstanding balance, which is sitting in invoices.due_amount right there.

**Actual** — "Dear <owner>,\nInvoice #PROBE-PARTIAL-1 for 1000.00 was due on … and remains unpaid." The SELECT pulls inv.total and never looks at paid_amount or due_amount, and the wording says "remains unpaid" for an invoice the client has part-paid. On the live demo this fires for 50 partially-paid invoices: sum(total)=EGP 64,328.00 vs sum(due_amount)=EGP 35,665.60 — EGP 28,662.40 of phantom debt demanded by WhatsApp. Worst single case INV-202602-0012: client owes 1,593.20, message would say 2,600.00.

**Cause** — blueprints/whatsapp/scheduler.py:176-195 (_invoice_reminders: SELECT inv.total …, message uses {inv['total']:.2f})

**Fix** — SELECT inv.due_amount and quote it; skip rows where due_amount <= 0. Reword to "an outstanding balance of X" so a part-paid invoice is not described as unpaid.

*reproduced · money & records*


### [BLOCKER] The three on/off switches and the three message templates on WhatsApp → Settings are write-only — turning reminders off does not stop them

**Steps** — WhatsApp → Settings, untick 'Invoice Overdue Alerts' (and the appointment/vaccine ones), Save. Confirm the page reloads with them off. Then run the reminder job. Separately: edit 'Invoice Message' to your own wording or Arabic, Save, run the job. Local repro: tests/test_zzz_wa_integrity_probe.py::test_C_settings_toggles_switch_reminders_off and tests/test_zzz_wa_integrity_probe2.py::test_N1_custom_reminder_wording_is_used.

**Expected** — Off means no invoice reminders. A custom/Arabic message means clients receive that message.

**Actual** — Both settings are stored and never read. reminder_appt_enabled / reminder_vaccine_enabled / reminder_invoice_enabled and reminder_appt_msg / reminder_vaccine_msg / reminder_invoice_msg appear only in routes.py (the form definition) and reminder_settings.html (the form) — grep across blueprints/ and models/ finds no reader. scheduler.py has all three messages hardcoded in English inside the f-strings. With every toggle set to '0' the job still sent the reminder; with an Arabic template saved the client still gets 'Dear N1 Owner, Invoice #… was due on … and remains unpaid.'

**Cause** — blueprints/whatsapp/routes.py:704-716 (keys defined and written); blueprints/whatsapp/scheduler.py:110-200 (_appointment_reminders / _vaccine_reminders / _invoice_reminders read neither)

**Fix** — In run_reminder_jobs, load the settings rows once and (a) skip each sub-job whose *_enabled key is '0', (b) use the *_msg value as a .format() template with the {owner}/{pet}/{date}/{time}/{vaccine}/{invoice}/{amount} names the Settings screen already advertises, falling back to the hardcoded string only when the key is blank.

*reproduced · money & records*


### [BLOCKER] The daily reminder engine ignores the token saved on the Settings screen and posts to the wrong API host — no automatic reminder can ever be sent

**Steps** — Live demo, admin: WhatsApp -> Settings, paste a Wapilot API Token + Instance ID, Save. Then WhatsApp -> Scheduler -> "Run appointment reminders" (or wait for the automatic 09:00 run). Reproduced locally: tests/test_whatsapp_edges_audit.py::test_scheduler_uses_the_token_saved_in_settings — it saves the token via POST /whatsapp/settings exactly as the form does, then POSTs /whatsapp/scheduler/run with type=appt.

**Expected** — The reminder goes out using the token the clinic just saved (that is what /whatsapp/control and every manual Send button do — _client() reads the settings table first, env second).

**Actual** — Every row in whatsapp_log comes back status='Not Configured', error='WhatsApp is not connected — no API token is set. Connect it under WhatsApp -> Settings.' — telling the user to do the exact thing they just did. scheduler._send_whatsapp reads ONLY os.environ['WAPILOT_TOKEN'] and never the settings table, and even with the env var set it POSTs to https://api.wapilot.io/send with an `Authorization: Bearer` header, while the rest of the blueprint uses https://api.wapilot.net/api/v2/{instance}/send-message with a `token:` header. Confirmed on the live box: `grep -ci wapilot /etc/aleefy/aleefy.env` = 0, and all 118 of today's 09:00 reminder rows in aleefy_demo read "lm turs — WhatsApp ghyr mtsl" on /whatsapp/log.

**Cause** — blueprints/whatsapp/scheduler.py:72 (os.environ.get("WAPILOT_TOKEN")) and :78 (https://api.wapilot.io/send)

**Fix** — Make _send_whatsapp call the same routes._send_and_log / WapilotClient path the manual buttons use, so it reads the settings table and hits api.wapilot.net/api/v2/{instance}/send-message. Delete the second, divergent HTTP client.

*reproduced · edge cases*


### [BLOCKER] A reminder run that sent nothing still marks the day done — tomorrow's appointment reminders are lost permanently

**Steps** — tests/test_whatsapp_edges_audit.py::test_unsent_reminder_is_retried_after_whatsapp_is_connected. Create an appointment for tomorrow; run the appointment job while WhatsApp is not connected (this is what the automatic 09:00 job does every morning today); connect WhatsApp; run the job again.

**Expected** — The second run sends the reminder that the first run could not.

**Actual** — The first run writes reminder_runs(run_type='appt_reminder', entity_id=<appt>, status='sent') even though _send_whatsapp returned 'Not Configured'. _already_sent then matches for the rest of the day, so the second run produces no new whatsapp_log row at all. Because appointment reminders are only for TOMORROW's appointments, tomorrow's job looks at the day after — that client is never reminded. Same happens on a plain network 'Failed'. On the live demo, 339 reminder_runs rows all say 'sent' while 118 of the messages were never transmitted.

**Cause** — blueprints/whatsapp/scheduler.py:135, :169, :200 — _mark_sent(...) is called unconditionally, outside the `if status in ("Sent","Pending")` check used two lines later for the counter

**Fix** — Only call _mark_sent when the send actually succeeded, and store the real status in reminder_runs instead of the hardcoded 'sent'.

*reproduced · edge cases*


### [MAJOR] A reminder that was never delivered is marked as run anyway and is never retried

**Steps** — An appointment tomorrow, owner has WhatsApp, no token configured (or the API is briefly down). 09:00 job runs — nothing is transmitted. The clinic notices at 09:30, connects WhatsApp, presses Scheduler → Run Appointment Reminders the same day. platform/tests/test_zzz_wa_integrity_probe.py::test_E_undelivered_reminder_is_retried_next_run.

**Expected** — The re-run sends the reminder that failed; tomorrow's patients still get told.

**Actual** — Second run sends 0. _mark_sent is called unconditionally after _send_whatsapp, whatever the status came back as ('Failed', 'Not Configured', anything), so the dedup marker is written for a message that never left the building. Appointment reminders only have the one day to fire, so that reminder is lost permanently. Live demo right now: 110 whatsapp_log rows with status 'Not Configured' and 110 matching reminder_runs rows stamped today — 110 reminders recorded as done that nobody received.

**Cause** — platform/blueprints/whatsapp/scheduler.py:135, :169, :200 — _mark_sent() outside any status check

**Fix** — Only _mark_sent when status in ('Sent','Pending'); record failures with status='failed' so the next run retries them and the history screen can show them.

*reproduced · money & records*


### [MAJOR] A vaccine overdue by more than 7 days is never reminded again — the pets most at risk are the ones the system gives up on

**Steps** — WhatsApp → Scheduler shows "Overdue Vaccines: 13" on the live demo. Press Run Vaccine Reminders. Or query the job's own window against the screen's.

**Expected** — The 13 pets the screen counts as overdue get chased.

**Actual** — 3 messages. _vaccine_reminders selects next_due_at BETWEEN today-7 AND today, so a vaccine that slipped 8 days ago drops out of the window forever — on the live demo that is 10 of the 13 pets, silently. The window is also entirely retrospective: nothing is sent BEFORE the due date, although the setting that supposedly controls it is labelled "Remind owners of upcoming vaccines". A booster that lapses is a medical outcome, not a marketing miss.

**Cause** — platform/blueprints/whatsapp/scheduler.py:143-154 (BETWEEN week_ago AND today)

**Fix** — Send an advance reminder (e.g. next_due_at BETWEEN today AND today+14) and keep chasing overdue ones on a decaying cadence instead of dropping them; pair with the per-entity latch from the daily-repeat finding so it does not become daily nagging.

*reproduced · money & records*


### [MAJOR] Every switch and message box in WhatsApp → Settings is ignored by the job it claims to control

**Steps** — WhatsApp → Settings: untick Appointment Reminders, Vaccine Due Reminders and Invoice Overdue Alerts; edit the three message templates (e.g. into Arabic). Save — "Settings saved." Run the job. platform/tests/test_zzz_wa_integrity_probe.py::test_C_settings_toggles_switch_reminders_off.

**Expected** — Nothing goes out; and when re-enabled, the clinic's own wording is used.

**Actual** — The reminders go out anyway, in hardcoded English ("Dear {name}, ... Please arrive 10 minutes early. Reply CONFIRM to confirm."). scheduler.py never reads the settings table at all — not reminder_appt_enabled / reminder_vaccine_enabled / reminder_invoice_enabled, not reminder_appt_msg / reminder_vaccine_msg / reminder_invoice_msg, and not the whatsapp_templates table with its scenario / language / is_default columns. Combined with the daily-repeat finding, a clinic whose clients are complaining has no way to stop it from the UI — the only off switch is deleting the token. An Arabic clinic's clients receive English.

**Cause** — platform/blueprints/whatsapp/routes.py:704-717 writes the keys; platform/blueprints/whatsapp/scheduler.py has no SELECT against settings or whatsapp_templates anywhere

**Fix** — Read the three _enabled flags at the top of each _*_reminders() and return 0 when off; load the matching _msg template (or the whatsapp_templates row for the scenario in the clinic's language) and .format() the fields instead of hardcoding the English string.

*reproduced · money & records*


### [MAJOR] Sending an appointment reminder by hand does not stop the 09:00 job sending the same one again

**Steps** — An appointment tomorrow with a matching Pending row in the reminders table (the demo seeds 23 of these, and online bookings create them). Reception opens WhatsApp → Reminders and clicks Send. The 09:00 job then runs. platform/tests/test_zzz_wa_integrity_probe.py::test_J_manual_send_stops_the_nightly_job.

**Expected** — One message per appointment.

**Actual** — Two messages, worded differently, for one appointment. The Reminders screen and the nightly job are two disconnected systems: the manual send updates reminders.status='Sent' and writes whatsapp_log, but writes no reminder_runs marker, and _appointment_reminders never looks at the reminders table (it dedups on reminder_runs keyed by appointment id). Neither side can see the other's work.

**Cause** — platform/blueprints/whatsapp/routes.py:632-658 (reminder_send) and :931-959 (reminder_send_now) write no reminder_runs row; platform/blueprints/whatsapp/scheduler.py:112-137 ignores reminders.appointment_id

**Fix** — Have the manual send paths write the same reminder_runs marker (run_type='appt_reminder', entity_id=reminders.appointment_id), and have _appointment_reminders skip appointments that already have a Sent reminders row.

*reproduced · money & records*


### [MAJOR] "Send now" on a reminder has no already-sent guard — every click is another message to the client

**Steps** — WhatsApp → Reminder Admin, pick any Pending reminder, click Send Now. Click it again (or hit browser Back and re-submit, or refresh after the redirect). platform/tests/test_zzz_wa_integrity_probe.py::test_H_double_submit_send_now — two POSTs to /reminder-admin/reminders/<id>/send-now plus one to /reminders/<id>/send.

**Expected** — The second and third attempts are refused: the reminder is already Sent.

**Actual** — 3 clicks, 3 WhatsApp messages to the same client for the same reminder. Neither route checks status before sending; both just UPDATE reminders SET status='Sent' afterwards. /whatsapp/send (the CRM shortcut) redirects to request.referrer, so a plain browser refresh re-POSTs and sends again. mark-sent has the mirror problem: it will flip a Cancelled reminder to Sent, because the UPDATE has no status predicate (unlike cancel, which correctly carries AND status='Pending').

**Cause** — platform/blueprints/whatsapp/routes.py:931-959, :632-658, :661-671 (UPDATE reminders SET status='Sent' with no WHERE status='Pending')

**Fix** — Gate the send on a conditional claim first — UPDATE reminders SET status='Sending' WHERE id=? AND status='Pending' — and only send if rowcount is 1; add AND status='Pending' to mark-sent.

*reproduced · money & records*


### [MAJOR] The three headline numbers on WhatsApp → Scheduler are not the numbers the buttons underneath them act on

**Steps** — Open WhatsApp → Scheduler on the live demo (admin / Aleefy@Demo2026). Read the three cards, then compare with what each Run button would send. platform/tests/test_zzz_wa_integrity_probe.py::test_F_scheduler_screen_counts_match_what_is_sent.

**Expected** — "13 overdue vaccines" means pressing Run Vaccine Reminders messages 13 owners.

**Actual** — Live demo: card says Overdue Vaccines 13, the job sends 3. Card says Unpaid Invoices 119, the job sends 107. The card queries are written independently of the job's and use different rules — the vaccine card is next_due_at <= today with no lower bound (the job uses a 7-day window) and does not exclude empty-string phones; the invoice card counts every Unpaid/Partial invoice with no due_date rule at all (the job requires due_date <= today-3). The owner presses a button expecting 119 chases and gets 107, with no report of the difference.

**Cause** — platform/blueprints/whatsapp/routes.py:1047-1056 and :1058-1066 vs platform/blueprints/whatsapp/scheduler.py:143-154 and :177-187

**Fix** — Have the screen call the same predicate the job uses — extract the three WHERE clauses into functions in scheduler.py that both a count() and the send loop consume.

*reproduced · money & records*


### [MAJOR] The custom reminder message text saved in WhatsApp → Settings is never used — the hardcoded English message is sent instead

**Steps** — WhatsApp → Settings, set "Appointment Message" to anything (e.g. an Arabic message, or "SALAM {owner}, {pet} MY CUSTOM TEXT"), Save — the flash says "Settings saved." and reloading the page shows your text. Now run the appointment reminder job. Reproduced locally: tests/test_zzz_wa_happy_audit.py::test_settings_message_templates_are_used.

**Expected** — The message the clinic wrote is what the owner receives.

**Actual** — The message actually written to whatsapp_log is "Dear Audit Owner,\nReminder: Bassem has a Checkup appointment tomorrow (2026-08-07 at 10:00).\nPlease arrive 10 minutes early. Reply CONFIRM to confirm." — the hardcoded English string. The saved setting is never read by anything. Same for reminder_vaccine_msg and reminder_invoice_msg.

**Cause** — D:\vet\platform\blueprints\whatsapp\scheduler.py:127-132, :161-166, :193-197 build the message from f-strings. Grep for `reminder_appt_msg` finds it only in blueprints/whatsapp/routes.py:708 (where it is written) and templates/whatsapp/reminder_settings.html:72 (where it is displayed) — never in a read path.

**Fix** — In each `_*_reminders`, read the corresponding `reminder_*_msg` setting and `.format(owner=..., pet=..., date=..., ...)` it, falling back to the current hardcoded string when the setting is blank.

*reproduced · happy path*


### [MAJOR] The three reminder on/off switches in WhatsApp → Settings do nothing — turning them off still generates reminders

**Steps** — WhatsApp → Settings, untick "Appointment Reminders", "Vaccine Due Reminders" and "Invoice Overdue Alerts". Save — the settings table now holds reminder_appt_enabled='0' etc. Run the appointment job (/whatsapp/reminder-admin → Trigger, or /whatsapp/scheduler → Appointment Reminders). Reproduced locally: tests/test_zzz_wa_happy_audit2.py::test_toggle_off_still_writes_messages.

**Expected** — No appointment reminders are generated while the toggle is off.

**Actual** — toggles saved as {'reminder_appt_enabled': '0', 'reminder_vaccine_enabled': '0', 'reminder_invoice_enabled': '0'} and a whatsapp_log row is still written for the appointment (template_name='appt_reminder'). With a working token this means the clinic sends messages it explicitly switched off.

**Cause** — D:\vet\platform\blueprints\whatsapp\scheduler.py — none of `_appointment_reminders`, `_vaccine_reminders`, `_invoice_reminders`, or `run_reminder_jobs` reads the settings table at all. The keys are only written (routes.py:732-741) and rendered.

**Fix** — In `run_reminder_jobs` (and in the per-type branches of `scheduler_run`, routes.py:1091-1105) load the three `reminder_*_enabled` settings and skip the disabled job.

*reproduced · happy path*


### [MAJOR] A reminder created in Reminder Admin with a scheduled date is never delivered by anything

**Steps** — /whatsapp/reminder-admin → "Create Reminder": fill Owner ID, Pet ID, a scheduled date/time in the past, and a message. Submit — flash says "Reminder created." and the row appears in the list. Then run every job the UI offers (Trigger Reminder Job / all four buttons on /whatsapp/scheduler / wait for 09:00). Reproduced locally: tests/test_zzz_wa_happy_audit2.py::test_manual_reminder_is_ever_delivered.

**Expected** — When the scheduled time passes, the reminder is sent and its status becomes 'Sent'.

**Actual** — The row stays status='Pending' forever and whatsapp_log stays empty. The demo has 23 such rows sitting Pending. The only way to actually deliver one is to press "Send Now" on each row by hand.

**Cause** — D:\vet\platform\blueprints\whatsapp\scheduler.py — no query in the module ever touches the `reminders` table. The three jobs regenerate reminders from appointments/vaccinations/invoices and only ever write `reminder_runs` and `whatsapp_log`. So a form that collects a scheduled datetime feeds a table no scheduler reads.

**Fix** — Add a fourth job to `run_reminder_jobs` that selects `reminders WHERE status='Pending' AND scheduled_for <= now`, sends via the shared send helper, and sets status='Sent'/'Failed'.

*reproduced · happy path*


### [MAJOR] All five buttons on /whatsapp/scheduler 403 — no CSRF token in any of its forms (and the page is unreachable from the UI)

**Steps** — Go to /whatsapp/scheduler (you have to type the URL — no page in the app links to it). Confirm the "Run ALL Jobs Now", "Appointment Reminders", "Vaccine Reminders", "Invoice Reminders" and "Clear Old History" buttons. Reproduced locally: tests/test_zzz_wa_happy_audit.py::test_scheduler_buttons_as_rendered harvests the five forms as rendered and POSTs them.

**Expected** — Each button runs its job and redirects back with a count.

**Actual** — All five return HTTP 403 "Invalid or missing security token." Nothing runs. Verified on the live demo as well: the rendered /whatsapp/scheduler page contains zero `_csrf_token` inputs. Separately, `grep -rl "whatsapp.scheduler'" templates/` returns nothing — no nav item, no card, no link points at this screen.

**Cause** — D:\vet\platform\templates\whatsapp\scheduler.html:55, :62, :69, :76, :83 — five <form method="post"> blocks, none emitting the hidden `_csrf_token`.

**Fix** — Add `<input type="hidden" name="_csrf_token" value="{{ csrf_token }}">` to all five forms, and decide whether the page should be linked from the Control Center (it duplicates /whatsapp/reminder-admin) or removed.

*reproduced · happy path*


### [MAJOR] "Reminder job triggered successfully" is flashed even when every message failed to send

**Steps** — /whatsapp/reminder-admin → "⚡ Trigger Reminder Job" with an appointment due tomorrow and WhatsApp not connected. Reproduced locally: tests/test_zzz_wa_happy_audit2.py::test_trigger_flash_truthful.

**Expected** — The flash reflects what happened — e.g. "0 sent, 1 not sent (WhatsApp not connected)".

**Actual** — Flash reads "Reminder job triggered successfully. Check the run log." while whatsapp_log records status='Not Configured' with error 'WhatsApp is not connected — no API token is set.' The run log the flash points at (reminder_runs) also says status='sent'. The owner has to open the Message Log to discover nothing was delivered. Same on /whatsapp/scheduler with type=all: "All reminder jobs triggered successfully."

**Cause** — D:\vet\platform\blueprints\whatsapp\routes.py:883-891 — `run_reminder_jobs()` returns nothing and the flash is unconditional. Same pattern at routes.py:1091-1093.

**Fix** — Have `run_reminder_jobs` return the (sent, failed) counts and flash them; the per-type branches at routes.py:1094-1105 already flash a count and should distinguish sent from attempted.

*reproduced · happy path*


### [MAJOR] The Overdue Vaccines and Unpaid Invoices cards on /whatsapp/scheduler count far more than the job will actually send

**Steps** — Open /whatsapp/scheduler on the live demo as admin. Cards read: Tomorrow's Appointments 0, Overdue Vaccines 13, Unpaid Invoices 119. Then compare against what the jobs select (the vaccine job only covers next_due_at within the last 7 days; the invoice job only covers due_date <= today-3). Reproduced locally: tests/test_zzz_wa_happy_audit2.py::test_cards_vs_run seeds one invoice due in 30 days and one vaccine 60 days overdue.

**Expected** — The card under "Run Vaccine Reminders" tells the owner how many messages that button will send.

**Actual** — On the live demo the cards say 13 vaccines / 119 invoices while the jobs would touch 3 and 107. Locally the cards read 1 and 1 while the run sends 0 and 0 — the card counts a not-yet-due invoice as "Unpaid" and a 60-day-overdue vaccine as in scope. The buttons are labelled "this will send real WhatsApp messages", so the owner is told he is about to message 119 clients when it is 107, and 13 when it is 3.

**Cause** — D:\vet\platform\blueprints\whatsapp\routes.py:1047-1056 (`v.next_due_at <= today`, no lower bound) and :1058-1066 (`status IN ('Unpaid','Partial')` with no due_date filter at all), versus scheduler.py:145-154 (`BETWEEN week_ago AND today`) and scheduler.py:179-187 (`due_date <= today-3`).

**Fix** — Make the three card queries in routes.py:1036-1066 literally the same WHERE clauses the scheduler uses, or better, expose count-only variants from scheduler.py and call those.

*reproduced · happy path*


### [MAJOR] A receptionist clicking "WhatsApp" in the sidebar is bounced back to the dashboard with a permission error

**Steps** — Sign in to https://demo.aleefy.online as rec.yasmine / Demo@1234. Click "WhatsApp" in the left sidebar (base.html:263 → whatsapp.control_center). Reproduced live with curl following redirects.

**Expected** — The WhatsApp Control Center, or at worst a page telling reception the module is not connected yet and who to ask.

**Actual** — /whatsapp/ → 302 /whatsapp/control → 302 /whatsapp/settings → 302 / (launcher), ending on the dashboard with two red flashes: "WhatsApp is not configured. Set the Wapilot API token and instance ID under WhatsApp → Settings..." followed by "You don't have permission to access this page." The main nav item for the whole module is a dead end for the role that uses it most.

**Cause** — D:\vet\platform\blueprints\whatsapp\routes.py:24-29 — the WapilotNotConfigured handler redirects everyone to `whatsapp.wa_settings`, which is `@role_required("super_admin","clinic_owner","branch_manager","support_admin")` (routes.py:698), and role_required (blueprints/auth/routes.py:176-178) redirects to launcher.index. Reception has no reachable landing page in the module.

**Fix** — In `_handle_unconfigured`, redirect roles that cannot reach Settings to a page they can use (`whatsapp.reminders` or `whatsapp.message_log`) with a message naming who can connect it; or render control_center with a "not connected" banner instead of redirecting.

*reproduced · happy path*


### [MAJOR] A reminder that was never delivered is marked done anyway and is never retried

**Steps** — With WhatsApp not yet connected, run the 09:00 job (appointment reminders for tomorrow). Notice the failures, connect WhatsApp, press Run now again the same day. Local repro: tests/test_zzz_wa_integrity_probe.py::test_E_undelivered_reminder_is_retried_next_run.

**Expected** — The reminders that did not go out are sent on the retry.

**Actual** — Zero sent. _mark_sent() is called unconditionally after every send attempt, whatever the status, so 'Not Configured' and 'Failed' both write the day's dedup marker and _already_sent() blocks the retry until tomorrow — by which time an appointment reminder for 'tomorrow' is worthless. On the live demo reminder_runs has 339 rows all status='sent' for 118 messages that were never transmitted.

**Cause** — blueprints/whatsapp/scheduler.py:135-137, 165-167, 196-198 (_mark_sent called before the status is inspected); dedup gate at scheduler.py:41-46

**Fix** — Only call _mark_sent when status == 'Sent'. Keep a separate failure row (or reuse reminder_runs.status='failed', which is already selected-for but never written) so the retry is bounded rather than infinite.

*reproduced · money & records*


### [MAJOR] An overdue invoice is WhatsApped to the client every single day, forever, with no cap

**Steps** — Create an unpaid invoice with a due date 10 days ago. Run the invoice reminder job on five consecutive days. Local repro: tests/test_zzz_wa_integrity_probe.py::test_A_invoice_reminder_repeats_every_single_day (fakes date.today() across 5 days).

**Expected** — A bounded chase — one message, or a small escalating series.

**Actual** — 5 messages in 5 days for the same invoice, and nothing stops it at day 500. The dedup gate is per-day (DATE(run_at)=today) and _mark_sent refreshes run_at every run, while the SELECT has only a lower bound (due_date <= today-3) and no upper bound and no send-count. The vaccine chase is correctly capped at 7 days; the invoice chase is not capped at all. On the live demo this would be 107 clients receiving a debt-collection WhatsApp every morning indefinitely.

**Cause** — blueprints/whatsapp/scheduler.py:176-182 (_invoice_reminders SELECT) with the per-day gate at scheduler.py:41-46

**Fix** — Add an upper bound (e.g. due_date >= today - 30) and/or count prior reminder_runs rows for that invoice and stop after N. Simplest lazy version: bound the window the same way the vaccine job already does.

*reproduced · money & records*


### [MAJOR] A pet that already received its booster is still chased as 'OVERDUE' for that vaccine for up to 7 days

**Steps** — Pet has a Rabies dose whose next_due_at was 4 days ago. Owner brings the pet in 2 days ago and the booster IS given and recorded (Clinical → Vaccinations → new record). Run the vaccine reminder job today. Local repro: tests/test_zzz_wa_integrity_probe2.py::test_N4_vaccine_given_stops_the_overdue_chase.

**Expected** — No message — the vaccine was given.

**Actual** — "Dear <owner>,\nOVERDUE: <pet> is overdue for the Rabies vaccine (due: <4 days ago>).\nPlease book an appointment at your earliest convenience." Recording a vaccination INSERTs a new row (blueprints/clinical/routes.py:283-297) and never touches the previous dose's next_due_at, and _vaccine_reminders selects any row whose next_due_at falls in the last 7 days with no check for a later dose of the same vaccine on the same pet. The clinic tells a client who just paid for the shot that their pet is overdue for it. (Not present in the demo seed — 0 rows match today — but it is the ordinary flow whenever a booster is given a day or two after it fell due.)

**Cause** — blueprints/whatsapp/scheduler.py:143-152 (_vaccine_reminders SELECT has no NOT EXISTS on a later dose)

**Fix** — Add AND NOT EXISTS (SELECT 1 FROM vaccinations v2 WHERE v2.pet_id=v.pet_id AND v2.vaccine_name=v.vaccine_name AND v2.administered_at > v.next_due_at) to the SELECT.

*reproduced · money & records*


### [MAJOR] Reception sending tomorrow's reminder by hand does not stop the 09:00 job sending it again — the owner gets two messages

**Steps** — Appointment tomorrow 11:00, with a matching row in `reminders` (reminder_type='appointment', appointment_id set). Reception opens /whatsapp/reminders and clicks Send on it. The 09:00 job then runs the same day. Local repro: tests/test_zzz_wa_integrity_probe.py::test_J_manual_send_stops_the_nightly_job.

**Expected** — One message per appointment.

**Actual** — Two. The manual path flips reminders.status to 'Sent' and writes whatsapp_log; the job's dedup lives in a completely separate table keyed on (run_type, appointment_id) and knows nothing about the reminders row, even though that row carries appointment_id. Same in reverse: the job never writes the reminders row, so it stays 'Pending' on screen after being sent.

**Cause** — blueprints/whatsapp/routes.py:632-658 (reminder_send) vs blueprints/whatsapp/scheduler.py:110-140 (_appointment_reminders / _already_sent)

**Fix** — In _appointment_reminders, also skip appointments that already have a reminders row with appointment_id=a.id and status='Sent' dated today; and have reminder_send write the matching reminder_runs marker.

*reproduced · money & records*


### [MAJOR] 'Send now' on a reminder has no state guard — three clicks send three WhatsApp messages to the client

**Steps** — /whatsapp/reminder-admin, pick a Pending reminder, click 'Send now'. The page redirects; click it again (or the user hits back/refresh and re-posts). Then hit Send on the same reminder from /whatsapp/reminders. Local repro: tests/test_zzz_wa_integrity_probe.py::test_H_double_submit_send_now — 3 posts, 3 outbound messages.

**Expected** — The second and third attempts are refused because the reminder is already 'Sent'.

**Actual** — 3 identical WhatsApp messages to the client and 3 whatsapp_log rows. Neither reminder_send_now nor reminder_send checks the current status before sending; both unconditionally re-send and re-stamp sent_at.

**Cause** — blueprints/whatsapp/routes.py:931-962 (reminder_send_now) and routes.py:632-658 (reminder_send)

**Fix** — Guard both: re-read status inside the same statement, e.g. UPDATE reminders SET status='Sent', sent_at=NOW() WHERE id=? AND status='Pending' and only send when rowcount==1.

*reproduced · money & records*


### [MAJOR] The three cards on /whatsapp/scheduler do not match what pressing Run actually sends

**Steps** — Log in to the live demo, open WhatsApp → Scheduler. Compare 'overdue vaccines' and 'overdue invoices' with what the corresponding Run button reports. Local repro: tests/test_zzz_wa_integrity_probe.py::test_F_scheduler_screen_counts_match_what_is_sent.

**Expected** — The number on the card is the number of clients the button will message.

**Actual** — Live demo right now: the vaccine card counts 18, the job sends 6; the invoice card counts 119, the job sends 107. The card queries and the job queries are written differently — the vaccine card uses next_due_at <= today with no 7-day lower bound, the invoice card has no due_date filter at all versus the job's due_date <= today-3, and both cards test whatsapp_phone IS NOT NULL while the jobs also require != ''. An owner deciding whether to press the button is reading a number that is 3x the truth.

**Cause** — blueprints/whatsapp/routes.py:1045-1073 (scheduler view counts) vs blueprints/whatsapp/scheduler.py:143-152 and 176-182

**Fix** — Have the view call the same WHERE clauses the job uses — cheapest is to move each job's SELECT into a helper returning rows, and let the card do len() on a count-only variant of it.

*reproduced · money & records*


### [MAJOR] /whatsapp/scheduler reports messages that were never sent as "total sent (all time)", and the number is capped at 200

**Steps** — Live demo, admin -> WhatsApp -> Scheduler. Read the three stat cards and the reminder-run table. Compare with the database.

**Expected** — "total sent (all time)" = the number of reminders actually delivered, over all time.

**Actual** — Page shows Invoice Reminder 186, Vaccine Reminder 9, Appt Reminder 5 — exactly 200, because the query is `ORDER BY rr.run_at DESC LIMIT 200` and the stats are computed from that truncated list, not from the table. The real counts in aleefy_demo are 321 / 9 / 9 = 339. Worse, every one of those 339 rows has status='sent' and renders green in the run table, yet whatsapp_log shows 118 of them as 'Not Configured' (never sent). /whatsapp/log tells the truth; /whatsapp/scheduler contradicts it. Also templates/whatsapp/scheduler.html:128 renders `h.status or 'sent'`, so a NULL status also displays as sent.

**Cause** — blueprints/whatsapp/routes.py:1017 (LIMIT 200 feeding the "all time" stats), blueprints/whatsapp/scheduler.py:56,62 (status hardcoded 'sent'), templates/whatsapp/scheduler.html:101,128

**Fix** — Compute the stat cards with a separate `SELECT run_type, COUNT(*) ... GROUP BY run_type` over the whole table; store the real delivery status in reminder_runs; drop the `or 'sent'` default.

*reproduced · edge cases*


### [MAJOR] Every control on the Reminder Settings screen is dead — the off switches do not switch off and the message bodies are never used

**Steps** — Sidebar -> Reminder Settings (/whatsapp/reminder-settings -> /whatsapp/settings). Untick "Invoice Overdue Alerts", rewrite "Invoice Overdue Message" in Arabic, Save (page says "Settings saved."). Then run the invoice job. tests/test_whatsapp_edges_audit.py::test_disabling_invoice_reminders_actually_disables_them.

**Expected** — No invoice reminders go out; if reminders are on, they use the message the clinic wrote.

**Actual** — The job still ran and logged an invoice reminder, using its own hardcoded English string. `grep -rn 'reminder_appt_enabled|reminder_vaccine_enabled|reminder_invoice_enabled|reminder_appt_msg|reminder_vaccine_msg|reminder_invoice_msg'` over the whole non-test codebase returns only the definition in routes.py and the two templates that render the inputs — nothing reads them. On the live demo all six controls are present and editable. templates/whatsapp/reminder_settings.html is an orphan: no route renders it.

**Cause** — blueprints/whatsapp/routes.py:704-717 writes the six keys; blueprints/whatsapp/scheduler.py never reads any of them

**Fix** — Have _appointment_reminders/_vaccine_reminders/_invoice_reminders read the *_enabled flag and format the *_msg template from settings. Delete templates/whatsapp/reminder_settings.html or wire it up.

*reproduced · edge cases*


### [MAJOR] "Create Manual Reminder" 500s on any Owner ID that is not a real owner — and the field is free-text with no way to look an owner up

**Steps** — WhatsApp -> Reminder Admin -> Create Manual Reminder. The "Owner ID *" field is a bare `<input type=number>` — no name, no dropdown, no search. Type any number that is not an existing owner id (a receptionist has no way to know one from this screen), fill message + date, Create. tests/test_whatsapp_edges_audit.py::test_manual_reminder_rejects_unknown_owner_without_500.

**Expected** — "No owner with that ID" and the form back with the typed values.

**Actual** — Uncaught IntegrityError: FOREIGN KEY constraint failed -> 500 error page, everything typed is lost. The constraint exists on the live engine too — `reminders_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES owners(id)` is present in aleefy_demo. The same 500 fires for a pet_id that does not exist.

**Cause** — blueprints/whatsapp/routes.py:908 (bare INSERT, no existence check, no try/except); templates/whatsapp/reminder_admin.html:81 (free-text Owner ID)

**Fix** — Validate the owner (and pet) exists before the INSERT and re-render the form with an error; replace the raw-ID inputs with an owner/pet picker.

*reproduced · edge cases*


### [MAJOR] A reminder created through the UI for earlier today shows under "Upcoming", never under "Overdue"

**Steps** — Reminder Admin -> Create Manual Reminder, set Scheduled For to a time earlier today (the field is `<input type=datetime-local>`), Create. Reload the page. tests/test_whatsapp_edges_audit.py::test_manually_created_overdue_reminder_lands_in_overdue.

**Expected** — It appears in "Overdue Reminders" — that is the list staff work from.

**Actual** — It appears in "Upcoming Reminders". datetime-local posts `2026-08-07T12:41` and the value is stored verbatim in the TEXT column scheduled_for, while the bucket query compares it as text against `2026-08-07 15:41:14`. 'T' (0x54) sorts after ' ' (0x20), so every same-day past reminder tests as `>= now`. The seeder writes a space separator, so this only bites reminders the clinic creates itself — and it also makes them sort after every seeded one in /whatsapp/reminders.

**Cause** — templates/whatsapp/reminder_admin.html:103 (datetime-local) vs blueprints/whatsapp/routes.py:825,835,848

**Fix** — Normalise scheduled_for to 'YYYY-MM-DD HH:MM:SS' in reminder_create (replace('T',' ') plus a parse check) — one line, and it fixes ordering everywhere too.

*reproduced · edge cases*


### [MAJOR] Renaming a WhatsApp template to a name that already exists gives a 500 error page

**Steps** — WhatsApp -> Templates. Two templates exist (the seed ships 6). Open one, change its Name to another existing template's name, Save. tests/test_whatsapp_edges_audit.py::test_duplicate_template_rename_does_not_500.

**Expected** — "A template with that name already exists." and the form back.

**Actual** — Uncaught IntegrityError: UNIQUE constraint failed: whatsapp_templates.name -> 500. Confirmed the same constraint exists live: `whatsapp_templates_name_key UNIQUE (name)` in aleefy_demo, so on PostgreSQL this is `duplicate key value violates unique constraint`. Note the create path (routes.py:519) wraps the same INSERT in try/except; the edit path has no guard at all.

**Cause** — blueprints/whatsapp/routes.py:559-568 — UPDATE with no try/except and no pre-check

**Fix** — Check for a conflicting name before the UPDATE (or wrap it) and re-render the form with a message.

*reproduced · edge cases*


### [MAJOR] Editing a template with a blank name silently wipes the template and reports success

**Steps** — Open any template's Edit page, clear the Name and Message fields, Save. Or, equivalently, a stale/partial form submit. tests/test_whatsapp_edges_audit.py::test_template_edit_requires_a_name.

**Expected** — "Template name is required." — exactly what /templates/new says for the same input (routes.py:515).

**Actual** — name='' and template_text='' are written, is_active flips to 0, and the page flashes "Template updated." The template disappears from the Send Center and from the active-template list with no trace of what it used to say. /templates/new validates; /templates/<id>/edit validates nothing.

**Cause** — blueprints/whatsapp/routes.py:557-568

**Fix** — Apply the same `if not name` guard the create route already has, and reject an empty template_text.

*reproduced · edge cases*


### [MAJOR] "Send Now" on a reminder has no double-submit guard and no status check — a double-click sends the client the same WhatsApp twice, and a cancelled reminder can still be sent

**Steps** — Reminder Admin -> any pending reminder -> click the "Send Now" button twice (it is a plain form POST, no confirm, no disable-on-submit; back-and-resubmit does the same). Then cancel a reminder and click Send Now on it. tests/test_whatsapp_edges_audit.py::test_send_now_twice_sends_one_message and ::test_send_now_refuses_a_cancelled_reminder.

**Expected** — One message per reminder; a cancelled reminder is not sent.

**Actual** — Three clicks = three WhatsApp messages to the pet owner and three whatsapp_log rows, each flashing "Reminder sent successfully." A Cancelled reminder is sent and its status is flipped back to 'Sent' — the cancellation is erased. /whatsapp/reminders/<id>/send has the identical hole.

**Cause** — blueprints/whatsapp/routes.py:933-959 (reminder_send_now) and :634-658 (reminder_send) — neither checks status before sending

**Fix** — Guard both on `UPDATE reminders SET status='Sent' ... WHERE id=? AND status='Pending'` and send only if rowcount==1.

*reproduced · edge cases*


### [MAJOR] A reminder message containing a line break kills the "Send WA" button on that row — it does nothing when clicked

**Steps** — Reminder Admin -> Create Manual Reminder, type a two-line message in the textarea (press Enter — the placeholder invites a sentence), Create. Go to WhatsApp -> Reminders and click "📱 Send WA" on that row. tests/test_whatsapp_edges_audit.py::test_multiline_reminder_does_not_break_the_send_button.

**Expected** — The send modal opens pre-filled.

**Actual** — Nothing happens, no error shown. The rendered handler is `onclick="openSendModal('2010', 1, 'Dear client,\r\nYour pet is due.')"` — a raw CR/LF inside a JS string literal, which is a SyntaxError, so the whole inline handler is dead. The `|replace("'","\\'")` filter only handles apostrophes; a trailing backslash breaks it the same way. (The 25 seeded demo reminders are single-line, so it does not show on the demo today.)

**Cause** — templates/whatsapp/reminders.html:99

**Fix** — Pass the values via data- attributes and read them with dataset in the handler, or use `|tojson` instead of the hand-rolled replace.

*reproduced · edge cases*


### [MAJOR] A receptionist can fire the whole reminder engine — including the invoice blast to every client with an unpaid bill — from /whatsapp/scheduler

**Steps** — Log in as rec.yasmine / Demo@1234 on the live demo and open /whatsapp/scheduler: it renders 200 with all four "Run now" forms (type=all/appt/vaccine/invoice) and "Clear old history". Authorization reproduced locally: tests/test_whatsapp_edges_audit.py::test_reception_cannot_trigger_a_mass_send — reception POSTing /whatsapp/scheduler/run gets 302 -> /whatsapp/scheduler (allowed).

**Expected** — The same gate as the identical button on the other screen. POST /whatsapp/reminder-admin/trigger from reception gets 302 -> / (denied, role_required super_admin/clinic_owner/branch_manager/support_admin).

**Actual** — /whatsapp/scheduler/run carries only @login_required, and 'whatsapp' is in reception's default module grant, so reception may run it. On the demo dataset that is 119 owners with unpaid invoices getting a debt message, in one click, irreversibly. /whatsapp/scheduler/clear-history is open to reception for the same reason. Reception also sees the reminder-admin trigger button that will always be refused.

**Cause** — blueprints/whatsapp/routes.py:1081 and :1116 (@login_required) vs :882 (@role_required)

**Fix** — Put the same role_required list on scheduler_run and scheduler_clear_history, and hide both button groups from roles that cannot use them.

*reproduced · edge cases*


### [MINOR] "Total sent (all time)" on the Scheduler screen stops counting at 200 and counts entities, not messages

**Steps** — Open WhatsApp → Scheduler on the live demo and read the per-type stat cards.

**Expected** — A running total of reminders sent.

**Actual** — The cards read 196 / 3 / 1 — exactly 200 — while reminder_runs holds 221 rows and whatsapp_log holds 214 sends. stats is built by looping over `history`, which is `SELECT ... FROM reminder_runs ... LIMIT 200`, so the label "total sent (all time)" is capped at 200 and will sit there forever. It is also the wrong unit: reminder_runs carries UNIQUE(run_type, entity_id, entity_type) and _mark_sent refreshes the row in place, so it counts distinct entities ever touched, not messages sent — the same invoice chased 30 days running contributes 1.

**Cause** — platform/blueprints/whatsapp/routes.py:1028-1031 (stats built from the LIMIT 200 history list) and templates/whatsapp/scheduler.py label at templates/whatsapp/scheduler.html:101

**Fix** — Compute the cards with a separate SELECT run_type, COUNT(*) FROM whatsapp_log GROUP BY template_name (the table that actually holds one row per message), and leave the LIMIT 200 on the history table only.

*reproduced · money & records*


### [MINOR] A reminder created through the UI is never shown as overdue on the day it is due

**Steps** — WhatsApp → Reminder Admin → New Reminder, set the datetime picker to 00:05 today, save. Reload the page at any later hour. platform/tests/test_zzz_wa_integrity_probe.py::test_I_same_day_reminder_lands_in_overdue.

**Expected** — At 22:13 a reminder due at 00:05 sits in the red Overdue table.

**Actual** — It sits in Upcoming all day. The form is <input type="datetime-local">, which submits '2026-08-06T00:05' with a T, and the row is stored verbatim in a TEXT column. The screen splits overdue from upcoming by string comparison against datetime.now().strftime('%Y-%m-%d %H:%M:%S') — a SPACE separator. 'T' (0x54) sorts after ' ' (0x20), so for the current date every T-format row compares as later than now, whatever time it says. The same mismatch scrambles ORDER BY scheduled_for: UI-created reminders sort after all space-format rows of the same date regardless of time.

**Cause** — platform/blueprints/whatsapp/routes.py:825 (now_s) vs :835/:848 comparisons; templates/whatsapp/reminder_admin.html:101 (datetime-local); platform/blueprints/whatsapp/routes.py:894-917 stores the raw form value

**Fix** — Normalise in reminder_create: scheduled_for.replace('T', ' ') and pad to seconds before the INSERT (and one UPDATE to repair existing rows).

*reproduced · money & records*


### [MINOR] The Message Log's summary counters silently omit every message that was never sent

**Steps** — WhatsApp → Message Log on the live demo. Read the four pills across the top, then count the red rows below.

**Expected** — Sent + Failed + Pending accounts for Total Shown.

**Actual** — Total Shown 200, Sent 90, Failed 0, Pending 0 — 110 messages are in no counter. The template counts only the three literal statuses and the scheduler's not-delivered status is the fourth, 'Not Configured'. The rows themselves are handled correctly (red badge, "⚠ Not sent — WhatsApp not connected"), so the fix is only in the tally — but since the scheduler cannot read the UI token at all (first finding), 'Not Configured' is the normal state for a configured clinic, not an edge case, and the top-of-page summary is where an owner looks first.

**Cause** — platform/templates/whatsapp/message_log.html:36-38

**Fix** — Add a not_sent count for status not in ('Sent','Failed','Pending'), or derive the pills from a groupby so any future status is accounted for.

*reproduced · money & records*


### [MINOR] A reminder due three hours ago is listed under "Upcoming", not "Overdue"

**Steps** — /whatsapp/reminder-admin → Create Reminder with a scheduled date/time earlier today (the field is <input type="datetime-local">, which posts "2026-08-06T19:12"). Reload /whatsapp/reminder-admin. Reproduced locally: tests/test_zzz_wa_happy_audit2.py::test_overdue_reminder_shows_as_overdue.

**Expected** — It appears in the red "Overdue Reminders" table.

**Actual** — It appears under "Upcoming Reminders". Any reminder created through this form for earlier today is classified as upcoming, so the overdue list under-reports. The raw value is also shown to the user with the 'T' in it ("2026-08-06T19:12").

**Cause** — D:\vet\platform\blueprints\whatsapp\routes.py:825-851 — `scheduled_for` is a TEXT column compared as a string against `now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")`. datetime-local posts a 'T' separator (routes.py:902 stores it verbatim), and 'T' (0x54) sorts above ' ' (0x20), so any same-day value compares as later than now regardless of its time.

**Fix** — Normalise in `reminder_create` (routes.py:902): `sched = f.get("scheduled_for","").replace("T", " ")`, and pad to seconds, so stored values match the format the seeded rows and the comparison already use.

*reproduced · happy path*


### [MINOR] Messages sent from the Send Center are not attributed to the owner, so they never appear in that owner's Communication History

**Steps** — CRM → open any owner → "✉️ Send Message" in the Communication History header. Send a message from the Send Center. Go back to the owner's page. Reproduced locally: tests/test_zzz_wa_happy_audit.py::test_send_center_send_lands_in_log — the resulting whatsapp_log row has owner_id NULL.

**Expected** — The message appears in that owner's Communication History and the Message Log shows their name in the Owner column.

**Actual** — The link opens a blank Send Center with no phone and no owner pre-filled (the receptionist retypes the number), and because owner_id is never posted, the whatsapp_log row has owner_id NULL. crm/routes.py:370-376 builds Communication History with `FROM whatsapp_log WHERE owner_id = ?`, so the message is invisible there and shows as '—' in the WhatsApp Message Log.

**Cause** — D:\vet\platform\templates\crm\owner_detail.html:585 links to `url_for('whatsapp.send_center')` with no query args; templates/whatsapp/send_center.html:288-291 posts only {phone, text, template_name}; blueprints/whatsapp/routes.py:255 reads an `owner_id` that is never sent.

**Fix** — Pass `owner_id` (and phone) on the CRM link, have send_center() prefill from `request.args`, and include owner_id in the JSON body at send_center.html:289.

*reproduced · happy path*


### [MINOR] The chat-ID lookup endpoints build a URL with /api/v2 twice

**Steps** — Send Center → "Quick phone lookup", type a number, press Lookup. That calls /whatsapp/api/lookup/phone/<phone>. Reproduced locally: tests/test_zzz_wa_happy_audit3.py::test_lookup_urls captures the URL the client would put on the wire.

**Expected** — GET https://api.wapilot.net/api/v2/<instance>/lids/pn/<phone>

**Actual** — GET https://api.wapilot.net/api/v2/api/v2/<instance>/lids/pn/<phone> — the path segment is duplicated, so the lookup can only ever return "Not found". Same for /whatsapp/api/lookup/lid/<lid>. Every other one of the client's 40 methods builds its path relative to BASE_URL correctly; these two are the only ones that re-prepend it.

**Cause** — D:\vet\platform\blueprints\whatsapp\wapilot.py:248 and :251 — `self._get(f"/api/v2/{iid}/lids/{lid}")` while BASE_URL (wapilot.py:11) already ends in /api/v2.

**Fix** — Drop the leading `/api/v2` from both paths.

*reproduced · happy path*


### [MINOR] The Wapilot token and instance ID cannot be cleared once set

**Steps** — WhatsApp → Settings, empty the API Token and Instance ID fields, Save. Reproduced locally: tests/test_zzz_wa_happy_audit.py::test_settings_cannot_be_cleared.

**Expected** — The credentials are removed and the module reports itself as not connected.

**Actual** — Flash says "Settings saved." and the old token and instance ID are still in the settings table and still used to send. Disconnecting a clinic's WhatsApp requires a database edit.

**Cause** — D:\vet\platform\blueprints\whatsapp\routes.py:722-723 — `val = request.form.get(key, "").strip()` then `if val:` skips the upsert entirely for an empty value.

**Fix** — Only skip the write when the field is absent from the form, not when it is empty; or add an explicit "Disconnect" action.

*reproduced · happy path*


### [MINOR] Deleting a template that does not exist reports "Template deleted."

**Steps** — POST /whatsapp/templates/9999/delete with a valid CSRF token (reachable in practice by double-submitting the delete form, or from a stale Templates list open in another tab). Reproduced locally: tests/test_zzz_wa_happy_audit.py::test_template_crud_roundtrip.

**Expected** — "Template not found." — the template_edit route already does exactly this (routes.py:553-556).

**Actual** — Green flash "Template deleted." for a row that was never there. There is also no audit-log entry for the delete, while create (routes.py:532) and update (routes.py:571) both write one — the destructive action is the untracked one.

**Cause** — D:\vet\platform\blueprints\whatsapp\routes.py:589-595 — DELETE then unconditional success flash, no rowcount check, no db.log_audit call.

**Fix** — Check `cur.rowcount` before flashing, and add the matching `db.log_audit(action="delete", ...)` call.

*reproduced · happy path*


### [MINOR] A reminder that fell due earlier today is listed as 'Upcoming', never 'Overdue', so nobody chases it

**Steps** — /whatsapp/reminder-admin → New reminder, pick an owner, set 'scheduled for' to 00:05 today (the field is <input type="datetime-local">), save. Reload /whatsapp/reminder-admin at any time later that day. Local repro: tests/test_zzz_wa_probe3.py::test_overdue_reminder_renders_under_upcoming — asserts on the rendered HTML section offsets, fails.

**Expected** — It appears under Overdue.

**Actual** — It renders under Upcoming, all day, however late. datetime-local posts '2026-08-07T00:05' and it is stored verbatim in the TEXT column, while the split compares against a bound '2026-08-07 15:41:44'. String comparison hits 'T' (0x54) vs ' ' (0x20) at index 10, so any same-day 'T' value sorts as greater than any same-day space value — i.e. always future. Seeded/API reminders use the space format ('2026-08-19 18:00:00' on the demo), so the two formats also interleave wrongly under ORDER BY scheduled_for.

**Cause** — blueprints/whatsapp/routes.py:826-849 (upcoming/overdue split on now_s); templates/whatsapp/reminder_admin.html:101 (datetime-local); blueprints/whatsapp/routes.py:894-918 (reminder_create stores the raw form value)

**Fix** — Normalise on write: sched.replace('T', ' ') and pad to seconds in reminder_create (and the same in blueprints/public_api/routes.py:231). One line, and it fixes the ordering too.

*reproduced · money & records*


### [MINOR] Template placeholders are sent to the client literally — the owner receives "Dear {owner}, invoice {invoice} for {amount} is due."

**Steps** — WhatsApp → Templates → New, template_text 'Dear {owner}, invoice {invoice} for {amount} is due.', variables_json ["owner","invoice","amount"], active. Then from a screen that posts to /whatsapp/send (Send Center / the CRM send shortcut), choose that template, leave the custom message blank, Send. Local repro: tests/test_zzz_wa_integrity_probe2.py::test_N3_template_placeholders_are_filled_in.

**Expected** — The braces are replaced with the owner's name, the invoice number and the amount — the variables_json column exists precisely to declare them.

**Actual** — The raw text is sent as-is, braces included. send_message() does `message = tmpl["template_text"]` with no substitution anywhere, and variables_json is stored but never read by any code path. The client receives a message with visible placeholders.

**Cause** — blueprints/whatsapp/routes.py:975-983 (send_message)

**Fix** — Either substitute from the owner/invoice context before sending, or — if the intent is that reception edits the text in the box first — pre-fill the textarea with the resolved text client-side and refuse to send a message that still contains '{'.

*reproduced · money & records*


### [MINOR] 'Mark as sent' flips a Cancelled reminder back to Sent

**Steps** — Cancel a reminder from /whatsapp/reminder-admin (status → 'Cancelled'). Then POST /whatsapp/reminders/<id>/mark-sent (reachable if the row is still on screen, or from a stale tab). Local repro: tests/test_zzz_wa_integrity_probe2.py::test_N5_mark_sent_respects_cancelled.

**Expected** — Cancelled stays cancelled.

**Actual** — status becomes 'Sent' and sent_at is stamped, so the record now claims a message went to the client that was deliberately cancelled and never sent. The UPDATE has no status guard, unlike reminder_cancel which correctly carries AND status='Pending'.

**Cause** — blueprints/whatsapp/routes.py:661-675 (mark_reminder_sent)

**Fix** — Add AND status='Pending' to the UPDATE, matching reminder_cancel at routes.py:920-929.

*reproduced · money & records*


### [MINOR] The Wapilot token cannot be cleared from the Settings screen, but the page says it saved

**Steps** — WhatsApp -> Settings, save a token. Then blank both the API Token and Instance ID fields and Save. tests/test_whatsapp_edges_audit.py::test_wapilot_token_can_be_cleared.

**Expected** — WhatsApp is disconnected, or at minimum the page says the fields were ignored.

**Actual** — The page flashes "Settings saved." and the old token is still in the settings table. `if val:` skips empty values, so a clinic that pasted a wrong or expired token has no way to remove it from the UI and no indication that its Save did nothing.

**Cause** — blueprints/whatsapp/routes.py:723

**Fix** — Write the submitted value even when empty (the field is only present when the form was actually rendered), or show "nothing changed" instead of "Settings saved."

*reproduced · edge cases*


### [MINOR] The Send Center's "check this number on WhatsApp" lookup builds a URL with /api/v2 twice and can never succeed

**Steps** — WhatsApp -> Send Center -> the phone lookup box (send_center.html:320 fetches /whatsapp/api/lookup/phone/<phone>). tests/test_whatsapp_edges_audit.py::test_lid_lookup_url_is_not_double_prefixed asserts the constructed URL.

**Expected** — https://api.wapilot.net/api/v2/<instance>/lids/pn/<phone>

**Actual** — https://api.wapilot.net/api/v2/api/v2/inst1/lids/pn/201000000 — BASE_URL already ends in /api/v2 and the method prepends it again. The feature will 404 for any clinic with a working token; it cannot be observed on the demo only because WhatsApp is unconfigured there and the request never leaves. get_chat_id_by_lid has the same defect.

**Cause** — blueprints/whatsapp/wapilot.py:248 and :251

**Fix** — Drop the '/api/v2' prefix from both paths.

*reproduced · edge cases*


### [MINOR] Creating a template with a name that already exists shows the raw database error to the user (and this is what a double-click produces)

**Steps** — WhatsApp -> Templates -> New Template, name it the same as an existing one and Save. Same thing happens if you double-click Save on a new template: the first POST succeeds, the second returns this.

**Expected** — "A template with that name already exists."

**Actual** — The form comes back with the flash "Error: UNIQUE constraint failed: whatsapp_templates.name" (on the live PostgreSQL: "duplicate key value violates unique constraint whatsapp_templates_name_key"). After a double-click the template WAS created, but the second response tells the user it errored, so they retry and get the same message.

**Cause** — blueprints/whatsapp/routes.py:542 — `flash(f"Error: {e}")` prints the exception verbatim

**Fix** — Catch the uniqueness case specifically and say so in plain language; log the exception instead of showing it.

*reproduced · edge cases*


### [MINOR] Reminder actions on records that do not exist (or are cancelled) report success

**Steps** — POST /whatsapp/templates/999999/delete, POST /whatsapp/reminders/999999/mark-sent, and "Mark Sent" on a reminder that has already been cancelled. tests/test_whatsapp_edges_audit.py::test_mark_sent_refuses_a_cancelled_reminder.

**Expected** — "Not found" / "That reminder was cancelled".

**Actual** — All three redirect with a green "Template deleted." / "Reminder marked as sent." flash and change nothing (or, for the cancelled reminder, silently flip Cancelled -> Sent, so the reminder log now claims a message went out that was deliberately cancelled). By contrast /reminder-admin/.../send-now does check and says "Reminder not found."

**Cause** — blueprints/whatsapp/routes.py:589-595 (template_delete) and :663-671 (mark_reminder_sent) — neither checks rowcount or existence

**Fix** — Check rowcount and flash accordingly; scope the mark-sent UPDATE with `AND status='Pending'`.

*reproduced · edge cases*


### [MINOR] POST /whatsapp/api/send/text 500s instead of returning 400 when a field is not a string

**Steps** — POST /whatsapp/api/send/text with {"phone": 20100, "text": "hi"} (a JSON number, which any integration will send sooner or later), or with a JSON array body. tests/test_whatsapp_edges_audit.py::test_api_send_text_rejects_non_string_fields.

**Expected** — 400 with the same {"ok": false, "error": ...} shape the route already returns for missing fields.

**Actual** — AttributeError: 'int' object has no attribute 'strip' -> 500 with an HTML error page from a JSON endpoint. A list body gives AttributeError: 'list' object has no attribute 'get'. The Send Center itself always sends strings, so this only bites an API caller.

**Cause** — blueprints/whatsapp/routes.py:247-249

**Fix** — `str(body.get("phone", "")).strip()` and reject a non-dict body up front.

*reproduced · edge cases*


### [MINOR] Section headings on Reminder Admin are hardcoded English on an otherwise fully Arabic screen

**Steps** — Live demo with the Arabic UI (default for admin): /whatsapp/reminder-admin. Everything — sidebar, page title, form labels, buttons — is Arabic except the two section headings.

**Expected** — Both headings translated, like every other string on the page which goes through t().

**Actual** — "🔴 Overdue Reminders (N)" and "📅 Upcoming Reminders (24)" render in English. Confirmed in the live HTML: `Upcoming Reminders (24)` verbatim.

**Cause** — templates/whatsapp/reminder_admin.html:114 and :149

**Fix** — Wrap both in t('Overdue Reminders', 'التذكيرات المتأخرة') / t('Upcoming Reminders', 'التذكيرات القادمة').

*reproduced · edge cases*


### [INFO] Nothing the reminder scheduler sends ever appears on /whatsapp/reminders or on the Control Center 'Pending reminders' card

**Steps** — Run the vaccine or invoice reminder job, then open /whatsapp/reminders and the Control Center. Local repro: tests/test_zzz_wa_integrity_probe.py::test_G_reminders_screen_shows_scheduler_work.

**Expected** — The screen named 'Reminders' shows the reminders the system is actually working through.

**Actual** — Unchanged. The scheduler writes only whatsapp_log and reminder_runs; it never inserts into `reminders`. The /whatsapp/reminders list and the Control Center's reminder_count are fed exclusively by manually-created and seeded rows, so they are an unrelated second reminder system. Worth knowing before fixing anything above: there are two, and only the invisible one runs nightly.

**Cause** — blueprints/whatsapp/scheduler.py (no INSERT INTO reminders anywhere) vs blueprints/whatsapp/routes.py:614-630 and routes.py:104-107

**Fix** — No action needed on its own — but decide which table is canonical before wiring up the dedup fixes in findings 4 and 7, or you will build the guard on the wrong side.

*reproduced · money & records*


## Hr  (49)

### [BLOCKER] Editing an HR Officer's profile silently promotes them to Super Admin

**Steps** — Live demo, sign in as admin. Go to /hr/staff, open Marwa Ezzat (hr.marwa, user 85), click Edit. The Role dropdown displays "Super Admin". Change nothing else (e.g. fix her phone number) and click Save Changes. Reproduced read-only on live: GET https://demo.aleefy.online/hr/staff/85/edit — the <select name="role"> contains 13 options and NOT ONE carries a `selected` attribute, so every browser displays and submits the first one, super_admin. Locally reproduced the same rendering for any user whose role is 'hr'.

**Expected** — The Role dropdown shows the staff member's actual role (HR Officer) preselected; saving an unrelated field leaves the role untouched.

**Actual** — 'hr' is missing from the option list, so nothing matches, the browser preselects option #1 (super_admin), and Save writes role='super_admin'. An HR officer silently gains full system access — RBAC admin, backups, every clinic's data — from a routine profile edit. The same omission means you cannot hire an HR Officer from /hr/staff/new at all, and the role filter on /hr/staff has no HR entry.

**Cause** — blueprints/hr/routes.py:20 — _ROLES = [...] omits "hr" (and _ROLE_COLORS at :26 omits it too), while models/database.py:2410 ships "hr" as a real seeded role and blueprints/hr/routes.py:49 grants it access. templates/hr/staff_form.html:146-152 renders the select from _ROLES with no placeholder option.

**Fix** — Add "hr" to _ROLES and _ROLE_COLORS (better: build the list from `SELECT name FROM roles`). Separately, make _save_staff_fields refuse to write a role that is not in the allowed list rather than trusting the posted value — that closes the class, not just this instance. Failing test: test_editing_hr_officer_preserves_role — GET /hr/staff/<hr_user>/edit and assert 'value="hr"' with selected is present in the role select.

*reproduced · happy path*


### [BLOCKER] Night-shift attendance stores NULL hours — every night shift is worth zero overtime pay

**Steps** — Sign in as owner/HR. /hr/attendance → "+ تسجيل حضور". Pick a nurse, work_date 2026-08-01, check-in 22:00, check-out 06:00, status Present, Save. Flash: "Attendance record saved." Then SELECT hours_worked FROM attendance_records for that row. The clinic seeds a real "Night Shift 22:00 - 06:00" so this is a shift they run.

**Expected** — hours_worked = 8.0 (22:00 → 06:00 next day), and payroll credits the overtime.

**Actual** — hours_worked = NULL. blueprints/payroll/routes.py:188 does `if r["status"] in ("Present","Late") and r["hours_worked"]` — NULL is falsy, so the day contributes 0 to overtime_hours. Every night shift ever recorded through the HR screen is unpaid overtime. The staff profile's "hours this month" and the attendance board's "avg hours" also silently exclude them.

**Cause** — blueprints/hr/routes.py:1550-1557 — `diff = (t_out - t_in).total_seconds()/3600` with both times parsed as %H:%M on the same nominal day; `if diff > 0` leaves hours_worked as None when the shift crosses midnight.

**Fix** — `if diff <= 0: diff += 24` before the round. Failing test: test_overnight_attendance_records_eight_hours — post 22:00/06:00 to /hr/attendance/add and assert hours_worked == 8.0. (tests/test_hr_edges_audit2.py:117 already probes this but only prints a note and currently dies on an ImportError, so nothing enforces it.)

*reproduced · happy path*


### [BLOCKER] HR attendance never deducts the shift break, so every HR-entered day pays an extra hour of overtime

**Steps** — Local, reproduced end to end. 1) Shift "Fnd Day" 09:00-17:00 with break_minutes=60, assigned to a nurse (standard net day = 7h). 2) As clinic_owner open /hr/attendance, "Add Attendance Record", enter the nurse, 2026-04-01..2026-04-20, check_in 09:00, check_out 18:00, status Present (20 ordinary days). 3) Call payroll's _get_attendance_summary(conn, user, 2026, 4) — this is what /payroll/generate uses to build the month's salaries. Failing test: tests/test_hr_integrity_findings.py::test_F1_hr_attendance_ignores_the_break_and_inflates_overtime

**Expected** — 09:00-18:00 minus a 60-minute break is 8.0 net hours, which is 1h over the 7h standard. 20 days = 20h overtime. At EGP 50/h on a 10,000 basic that is a net of 11,000 — which is exactly what the same 20 days produce when recorded through the clock/attendance screen (blueprints/attendance/routes.py::_calc_hours subtracts break_minutes).

**Actual** — HR stores hours_worked = 9.0 per day and leaves break_minutes at 0. Payroll computes 40.0h overtime instead of 20.0h and a net of 12,000 instead of 11,000 — EGP 1,000 too much on one person for one month, and it scales with headcount. The same physical workday produces two different pay figures depending on which screen recorded it.

**Cause** — D:\vet\platform\blueprints\hr\routes.py:1550-1557 — hr_attendance_add computes `diff = (t_out - t_in).total_seconds()/3600` inline and never looks at break_minutes, while blueprints/attendance/routes.py:18 (_calc_hours) and blueprints/payroll/routes.py:174 (standard_hours) both do.

**Fix** — Delete the inline calculation in hr_attendance_add and call blueprints.attendance.routes._calc_hours(check_in, check_out, brk), taking brk from the staff member's shift (attendance.routes.default_shift is already the fallback). Write the same break_minutes onto the row so the column the HR table renders matches the hours it renders.

*reproduced · money & records*


### [BLOCKER] A night shift entered on the HR screen stores NULL hours and flashes success — the whole month's hours vanish

**Steps** — Local, reproduced. The live demo ships a "Night Shift" 22:00-06:00 (shifts id=3), so this is a shift the product defines. 1) /hr/attendance, Add Attendance Record: nurse, work_date 2026-05-01, check_in 22:00, check_out 06:00, status Present. 2) Repeat for 20 nights. Failing test: tests/test_hr_integrity_findings.py::test_F2_night_shift_hours_are_silently_dropped

**Expected** — 22:00 -> 06:00 is 8 hours (7 net of the 60-minute break). blueprints/attendance/routes.py:24 already rolls past midnight with `if co < ci: co += timedelta(days=1)`.

**Actual** — diff is -16h, the `if diff > 0` guard skips the assignment, hours_worked is written as NULL, and the page still flashes "Attendance record saved". Over 20 nights: SUM(hours_worked) = 0, payroll's overtime_hours = 0, and the staff profile's "Attendance this month" hours card reads 0. Mixed month probe (10 day shifts + 10 nights): DB holds 20 rows, 10 with hours, total 80h where the truth is 160h — and the page's average-hours strip still reads a healthy 8.0 because AVG filters hours_worked > 0. Half the month is gone and nothing on screen says so.

**Cause** — D:\vet\platform\blueprints\hr\routes.py:1551-1557 — the inline midnight-unaware calculation, plus `if diff > 0` silently discarding the result instead of erroring.

**Fix** — Same single fix as the previous finding: route hr_attendance_add through attendance.routes._calc_hours, which already handles the midnight roll. If the result is still 0, reject the submission with a flash rather than saving a row with no hours.

*reproduced · money & records*


### [BLOCKER] Correcting a status on the HR attendance screen wipes the clocked-in times and the hours

**Steps** — Local, reproduced. 1) A nurse clocks in/out normally: attendance_records row for 2026-03-11 with check_in 09:00, check_out 18:00, break_minutes 60, hours_worked 8.0, status Present. 2) HR wants to mark that day Late. The only affordance is the "Add Attendance Record" modal on /hr/attendance (templates/hr/hr_attendance.html:330-368) — there is no edit button on existing rows, and the modal's time fields are always blank. 3) HR picks the staff member, the same date, status Late, adds a note, saves. Failing test: tests/test_hr_integrity_findings.py::test_F3_hr_add_modal_wipes_an_existing_clock_record

**Expected** — The status changes to Late. The clocked times and the 8.0 hours the clinic pays from are untouched.

**Actual** — The row becomes check_in NULL, check_out NULL, hours_worked NULL, status Late. The hours column on the HR table renders "—" and payroll counts zero hours for that day. The clock record is destroyed by a form the operator believed only changed a dropdown.

**Cause** — D:\vet\platform\blueprints\hr\routes.py:1545-1573 — check_in/check_out are `f.get(...) or None`, hours_worked starts at None, and the UPDATE branch writes all three unconditionally over the existing row.

**Fix** — In the UPDATE branch, COALESCE against the stored row: only overwrite check_in/check_out/hours_worked when the form actually supplied a time. Longer term give existing rows a real edit route that prefills, rather than reusing a blank add modal as an upsert.

*reproduced · money & records*


### [BLOCKER] Overnight shifts record zero hours worked, and payroll under-pays the overtime

**Steps** — Local, Flask test client, logged in as admin. HR > Attendance > "Log Attendance Record": Staff Member = any, Date = today, Status = Present, Check In = 20:00, Check Out = 08:00, Save. (Both fields are <input type="time"> at templates/hr/hr_attendance.html:356,360 — this is ordinary UI entry, not tampering.) Then read blueprints/payroll/routes._get_attendance_summary for that user/month. Reproduced with the person on a standard 09:00-17:00 (8h) shift and two 12-hour records in the same month: 08:00->20:00 on day 1, 20:00->08:00 on day 2.

**Expected** — 12 hours worked on each day; overtime_hours = 8.0 (4h over standard on each).

**Actual** — The night row saves with the green flash "Attendance record saved.", but hours_worked is NULL. The HR attendance screen renders its Hours cell as "—". _get_attendance_summary returned overtime_hours = 4.0 instead of 8.0 — exactly half the overtime, silently. The day row was 12.0h as expected. The live demo's own shifts table ships "Night Shift (22:00-06:00)", so this is the normal case for any 24-hour or emergency clinic.

**Cause** — blueprints/hr/routes.py:1553-1560 — `diff = (t_out - t_in).total_seconds()/3600` then `if diff > 0: hours_worked = round(diff,2)`. Any shift crossing midnight yields diff < 0, so hours_worked is left None. Payroll then credits overtime only from attendance_records.hours_worked (blueprints/payroll/routes.py:186-193).

**Fix** — When check_out <= check_in, treat it as crossing midnight: add 24h before computing diff (and reject only when the resulting span exceeds a sane cap such as 24h). The same helper should be shared with the attendance blueprint's checkout path rather than duplicated.

*reproduced · edge cases*


### [BLOCKER] Any hr / branch_manager / support_admin user can promote themselves to super_admin from the Edit Staff form

**Steps** — Create a user with role "hr" via HR > Staff > Add Staff. Log in as that user. Open HR > Staff > (own record) > Edit, change the Role dropdown to "Super Admin", Save. Reproduced with the Flask test client: POST /hr/staff/<own id>/edit with role=super_admin.

**Expected** — An HR officer cannot grant a role above their own; the change is refused.

**Actual** — Flash "Staff member updated successfully.", and users.role for that account is now super_admin. Read back from the DB: [{"role": "super_admin"}]. The comment at blueprints/hr/routes.py:44-47 says the hr role is deliberately denied password resets, record deletion and RBAC admin — one form save hands over all of it, plus every other blueprint. role_required is a plain role-list check (blueprints/auth/routes.py:170-179) with no ceiling on what role value may be written.

**Cause** — blueprints/hr/routes.py:490-538 (_save_staff_fields) writes `role = f.get("role", "reception")` straight from the form, and staff_edit (routes.py:772) is granted to hr, branch_manager and support_admin.

**Fix** — In _save_staff_fields, reject any role the caller is not entitled to grant: only super_admin may set super_admin/clinic_owner; validate the value is in _ROLES at all; and refuse role changes on the caller's own row.

*reproduced · edge cases*


### [BLOCKER] An account can deactivate and demote itself, including the last super_admin, with no warning and no way back in

**Steps** — HR > Staff > (your own record) > Edit. Untick "Active — user can log in" and/or change your Role, Save. Reproduced: POST /hr/staff/<admin id>/edit with role=reception and the is_active checkbox absent, then a fresh client POST /auth/login with admin's correct password.

**Expected** — A confirmation at minimum, and a hard refusal when the target is the caller's own account or the last active super_admin.

**Actual** — Flash "Staff member updated successfully." users row becomes {"username":"admin","role":"reception","is_active":0}. The login attempt afterwards fails and lands back on /auth/login with no session. The operator does not find out immediately, because the current session keeps working (GET /hr/staff still returned 200 — the role is cached in the session, not re-read). There is no in-app recovery path once the last owner account is off.

**Cause** — blueprints/hr/routes.py:774 staff_edit -> _save_staff_fields (routes.py:490) writes is_active and role unconditionally. No self-target guard, no last-active-super_admin guard.

**Fix** — Refuse to clear is_active or lower the role on the caller's own user id, and refuse either when it would leave zero active super_admin/clinic_owner accounts. Confirm dialog on any is_active change.

*reproduced · edge cases*


### [MAJOR] "Next →" on the HR attendance board 404s on the default view

**Steps** — Live demo: GET https://demo.aleefy.online/hr/attendance with no filters. The footer reads "عرض 50 من 84 سجل … 1 / 2 التالي ←". The Next link is href="https://demo.aleefy.online/hr/attendance&page=2". Following it returns HTTP 404.

**Expected** — Page 2 loads the remaining 34 attendance records.

**Actual** — 404. The link concatenates '&page=2' onto a URL that has no query string at all, producing a bogus path. Records 51-84 are unreachable from the page a clinic lands on; they only become reachable if the user happens to apply a filter first (which adds the '?'). Prev works only because it uses string-replace on an existing page= param.

**Cause** — templates/hr/hr_attendance.html:236 and :240 — `request.url ~ '&page='~(page+1)` when 'page=' is not already in request.url.

**Fix** — Build the link with url_for: `url_for('hr.hr_attendance', **dict(request.args, page=page+1))`. Failing test: test_attendance_next_link_is_reachable — GET /hr/attendance with >50 rows in the default 7-day window, extract the Next href, GET it, assert 200.

*reproduced · happy path*


### [MAJOR] Overtime page headline totals are capped at 200 rows and understate the real hours by a third

**Steps** — Live demo: GET https://demo.aleefy.online/hr/overtime. KPI cards read "200 إجمالي السجلات" and "197.8 الساعات المعتمدة". Now fetch the same page four times with date_from/date_to covering Jan-May, June, July, August: KPIs are 72/77.2, 101/95.4, 95/91.6, 24/27.0 — i.e. the truth is 292 records and 291.2 approved hours. Reproduced locally too: 250 approved 1.0h rows render as "200 / 200.0".

**Expected** — Either the true totals, or an explicit "showing 200 of 292".

**Actual** — The page silently drops everything past row 200 and computes both KPIs from what survived. An owner reading "197.8 approved overtime hours" is missing 93.4 hours — about a third of the clinic's overtime liability — with nothing on screen suggesting the number is partial. The dashboard card correctly says 60 pending, but the unfiltered overtime list only shows 43 of them.

**Cause** — blueprints/hr/routes.py:1334 (`LIMIT 200`) combined with :1337 `total_hours = sum(... for r in rows ...)` — the sum is over the truncated page, and templates/hr/overtime.html:39-50 labels them "Total Records" / "Approved Hours".

**Fix** — Compute the counts and SUM(hours) with a separate aggregate query over the full filtered set, and paginate the table the way /hr/attendance does (once its Next link is fixed). Failing test: test_overtime_totals_ignore_the_row_limit — insert 250 approved rows, assert the Approved Hours KPI reads 250.0.

*reproduced · happy path*


### [MAJOR] The Work Shift dropdown on Edit Staff is decorative — it never shows the current shift and never saves

**Steps** — Open any staff member with an assigned shift, click Edit. The "Work Shift" select shows "— No Shift —" with the hint "Assigning a shift here will set it from today." Pick Morning Shift, click Save Changes. Flash: "Staff member updated successfully." Then SELECT * FROM staff_shifts WHERE user_id=<id>.

**Expected** — Either the field is preselected with the current shift and saving moves them to the chosen one, or the field is not rendered on the edit page at all.

**Actual** — No rows written; staff_shifts is unchanged. Verified locally: after posting the edit form with shift_id=1 the table is empty, yet the success flash fires. And on GET the select never carries a `selected` option even when the person does have a shift, so it always reads "No Shift". An HR officer will believe they rostered someone and they did not. (The same field on /hr/staff/new does work — routes.py:578-588 — which makes the edit page's silence more convincing, not less.)

**Cause** — blueprints/hr/routes.py:785-797 — staff_edit POST calls only _save_staff_fields and never reads request.form['shift_id']; templates/hr/staff_form.html:167-175 renders the select unconditionally and matches on `form.get('shift_id')`, a key the users row does not have.

**Fix** — Either wrap the Work Shift block in `{% if not editing %}` and point HR at the existing assign-shift form on the staff detail page, or make staff_edit call the same staff_shifts logic staff_new uses and preselect from the current assignment. Failing test: test_staff_edit_saves_shift — post the edit form with shift_id and assert a staff_shifts row exists.

*reproduced · happy path*


### [MAJOR] An employee can never open their own performance review, so nobody can ever acknowledge one

**Steps** — Live demo: sign in as dr.sara / Demo@1234, go to /hr/performance/<id> for her own 2026-H1 review. Reproduced locally as a nurse: GET /hr/performance/<id> → 302 to /. Then POST /hr/performance/<id>/acknowledge → 302 back to /hr/performance/<id> → 302 to /.

**Expected** — The employee reads their review and clicks Acknowledge; status moves Submitted → Acknowledged.

**Actual** — performance_detail carries only @login_required, so the module-level grant for the 'hr' blueprint bounces every non-HR role to the launcher before _may_act_on is ever consulted. The Acknowledge button lives only on that page. The POST route itself IS marked @self_service and works when called directly — status does flip to Acknowledged — but it then redirects to the page the employee cannot open. So the entire 'Acknowledged' status, the _may_act_on ownership check, and the review-acknowledgement workflow are unreachable through the UI. All 9 reviews on the live demo are stuck at "مُرسل" (Submitted). Same shape for the warnings acknowledge route: it works, then redirects to /hr/staff/<id> which the employee also cannot open.

**Cause** — blueprints/hr/routes.py:969-970 — @hr_bp.route("/performance/<int:rev_id>") with @login_required and no @self_service, while :1038-1041 (acknowledge) does have it.

**Fix** — Add @self_service to performance_detail (it already scopes correctly via _may_act_on at :985), and redirect acknowledge_warning to somewhere the employee can reach — /auth/profile or an attendance self-service page. Failing test: test_employee_can_open_own_review — log in as the reviewed nurse, GET /hr/performance/<id>, assert 200.

*reproduced · happy path*


### [MAJOR] HR password reset and new-staff creation write legacy SHA-256 hashes instead of bcrypt

**Steps** — Open a staff member, use Reset Password with a valid 12+ char password. Flash: "Password reset successfully." Then SELECT password_hash FROM users WHERE id=<id>. Same for any account created via /hr/staff/new.

**Expected** — The stored hash starts with $2b$ (bcrypt, rounds=12), matching every other password write in the app.

**Actual** — The hash is a bare SHA-256 hex digest with one global salt shared by every user (verified: prefix 5bb4dd… after a reset, 048347… after a create). Login still works because db._verify_and_migrate falls back to SHA-256 and rehashes on first successful login — but until that person next signs in, their credential sits in the database as a single unsalted-per-user SHA-256 that a leaked dump cracks at GPU speed and that rainbow-tables across all accounts at once. This is the one path an owner uses to set a password FOR a locked-out vet, and it is the weakest write in the system. models/database.py:2717 even documents _hash_password as "the public API used by HR/reset routes" — HR just doesn't call it.

**Cause** — blueprints/hr/routes.py:110-111 defines a local `_hash` using hashlib.sha256 with _SALT, used at :530 (create) and :827 (reset). blueprints/auth/routes.py:575 correctly uses _db._hash (bcrypt) for the self-service change-password path.

**Fix** — Delete the local _hash and _SALT from blueprints/hr/routes.py; call db._hash_password at both sites. Failing test: test_hr_reset_password_stores_bcrypt — reset, assert password_hash.startswith('$2b$').

*reproduced · happy path*


### [MAJOR] New staff accounts can be created with a one-character password

**Steps** — /hr/staff/new. Username n2, Password "1", Confirm "1", role nurse, Create Staff Member.

**Expected** — Rejected with the same rule the rest of the app enforces (models/security.py validate_password_strength — minimum 12 characters).

**Actual** — Flash: "Staff member 'n2' created successfully." The account exists and can sign in with "1". The field's own placeholder promises "Min 6 characters" and even that is not checked. Meanwhile /hr/staff/<id>/reset-password on the very same profile correctly refuses with "Password must be at least 12 characters." — so the clinic gets a strict rule when changing a password and no rule at all when creating one, on accounts that reach medical records.

**Cause** — blueprints/hr/routes.py:564-573 — staff_new checks only presence and confirm-match; it never calls _sec.validate_password_strength the way staff_reset_password does at :820.

**Fix** — Call the same `ok, why = _sec.validate_password_strength(password)` before insert and re-render the form with `why` on failure. Fix the placeholder text at templates/hr/staff_form.html:52 too. Failing test: test_staff_new_rejects_weak_password.

*reproduced · happy path*


### [MAJOR] The Weekly Roster is completely empty on the live demo, and re-seeds empty every night

**Steps** — Live demo: GET https://demo.aleefy.online/hr/roster. Also check any staff profile, e.g. /hr/staff/74 (Dr. Mostafa Kamal).

**Expected** — A week grid showing who works which shift, with attendance chips per day — the screen the "Weekly Roster" button on the HR dashboard promises.

**Actual** — All four shift rows read "0 موظف" (0 staff). Every one of the 15 staff sits in "موظفون بدون مناوبة (15)". Every staff profile says "لا توجد مناوبة معينة" (no shift assigned). The HR dashboard card reads "بدون مناوبة — 15 موظف". The roster template and the assign-shift route both work correctly (verified locally: assign a shift, add attendance, and the chips render with the right present/late/absent colours) — there is simply no data. This is the same shape as the empty vaccination-reminder screen: a headline module button on the flagship demo that opens onto nothing, on a dataset that otherwise has 90 days of attendance, salaries, certifications and overtime.

**Cause** — scripts/seed/demo_showcase.py:1138 seed_hr — it seeds attendance_records, overtime_log, salaries and leave, but never inserts a single staff_shifts row. (The older standalone seed_hr.py:140-150 does assign shifts; the nightly demo re-seed uses demo_showcase.py instead.)

**Fix** — Add the shift-assignment loop from seed_hr.py:139-149 to demo_showcase.seed_hr, round-robining the 4 seeded shifts across the 15 users with effective_from well in the past. Failing test: test_demo_seed_assigns_shifts — after seeding, assert staff_shifts has a current row for every active user.

*reproduced · happy path*


### [MAJOR] The HR dashboard's birthdays and work-anniversaries panels are permanently empty on PostgreSQL

**Steps** — Reproduced against the live demo database. Run on the production engine: `SELECT id, full_name, hire_date FROM users WHERE is_active=1 AND hire_date IS NOT NULL AND substr(hire_date,6,2)='08' AND hire_date < '2026-08-07'` — this is verbatim the query at blueprints/hr/routes.py:365-372. Then open https://demo.aleefy.online/hr/dashboard as admin.

**Expected** — The dashboard shows this month's work anniversaries. The demo has hire dates in 10 of 12 months (May has 3 people, June 2, July 2), so the panel should have content most of the year.

**Actual** — PostgreSQL: `ERROR: function substr(date, integer, integer) does not exist`. users.dob and users.hire_date are real DATE columns on PG (created by the ALTER TABLE at blueprints/hr/routes.py:142,149 and confirmed in information_schema). The route wraps both queries in a bare `except: db.rollback_quietly(conn)` with no logging, so the lists come back empty and the templates guard on `{% if birthdays_this_month %}` — the panels do not render at all. Neither panel has ever worked in production. On SQLite the identical query succeeds (SQLite has no real DATE type), so the whole test suite is green and there is no test that touches these panels at all. The code comment at routes.py:337-346 asserts "dob and hire_date are TEXT columns" and "substr on an ISO date is native to both engines" — both are false on the deployed schema.

**Cause** — D:\vet\platform\blueprints\hr\routes.py:351-358 (birthdays) and 365-372 (anniversaries) — substr() applied to DATE columns, inside try/except blocks that swallow without logging.

**Fix** — Use `EXTRACT(MONTH FROM dob) = ?` / `EXTRACT(DAY FROM ...)` for ordering, or cast explicitly with `substr(dob::text, 6, 2)`, which works on both engines. Give these two except blocks the same `logger.exception(...)` the payroll and recent-hires blocks above them already have — the silence is what let this live.

*reproduced · money & records*


### [MAJOR] Overtime page "Approved Hours" and "Total Records" are summed over only the first 200 rows — live demo under-reports by a third

**Steps** — Reproduced on the live demo. 1) Log in to https://demo.aleefy.online as admin. 2) Open /hr/overtime with no filters. 3) Read the two KPI tiles. 4) Truth from the database: `SELECT status, count(*), sum(hours) FROM overtime_log GROUP BY status` -> Approved 232 rows / 291.2 h, Pending 60 / 74.4 h. Also reproducible locally: tests/test_hr_integrity_findings.py::test_F4_overtime_page_totals_are_capped_at_200_rows

**Expected** — Records 292, Approved Hours 291.2 — the totals for the filter the manager selected.

**Actual** — The page shows Records 200 and Approved Hours 197.8. Ninety-three hours of approved overtime are missing from the headline number a manager reads before authorising pay. The shortfall grows with history and moves whenever a row is added, so it never looks obviously wrong.

**Cause** — D:\vet\platform\blueprints\hr\routes.py:1326-1337 — the row query carries `LIMIT 200`, then `total_hours = sum(... for r in rows ...)` and the template renders `rows|length` (templates/hr/overtime.html:40,44). Both KPIs describe the page, not the filter.

**Fix** — Compute the KPIs in their own aggregate query over the same WHERE clause without the LIMIT: `SELECT COUNT(*), COALESCE(SUM(hours) FILTER (WHERE status='Approved'),0) FROM overtime_log ol JOIN users u ... WHERE {where}`. Same pattern the attendance page already uses correctly at routes.py:1460-1469.

*reproduced · money & records*


### [MAJOR] add_overtime accepts negative hours, and approving one silently reduces the clinic's approved total

**Steps** — Local, reproduced. 1) POST /hr/staff/<id>/overtime/add with hours=-5, work_date 2026-06-01. 2) POST again with hours=8 for 2026-06-02. 3) Approve both from /hr/overtime. 4) Read the approved total. Failing test: tests/test_hr_integrity_findings.py::test_F5_overtime_accepts_negative_and_out_of_range_hours. Also tried: hours=30 accepted, hours=1e3 accepted and stored as 1000.

**Expected** — A negative or absurd overtime entry is refused at the form. The approved total for the two legitimate-looking entries is 8h.

**Actual** — "-5.0h overtime recorded" is flashed as a success and the row is stored. The approved total reads 3 instead of 8. 30h and 1000h on a single day are also accepted. On PostgreSQL the column is NUMERIC(4,1), so 1000 raises `numeric field overflow` and the operator gets a raw psycopg2 error string in a flash message; on SQLite it stores fine — so this is also an engine divergence the tests cannot see.

**Cause** — D:\vet\platform\blueprints\hr\routes.py:1363 — `hours = float(f.get("hours") or 0)` with no range check before the INSERT.

**Fix** — One guard before the INSERT: reject anything outside 0 < hours <= 24 (the column is NUMERIC(4,1), so 24 is well inside it) and flash a readable message. Add `min="0" max="24" step="0.25"` on the form input as the cheap half.

*reproduced · money & records*


### [MAJOR] Resubmitting the overtime form duplicates the entry — three clicks, triple pay

**Steps** — Local, reproduced. POST /hr/staff/<id>/overtime/add three times with identical hours=4, work_date=2026-09-01, reason="emergency surgery" — the real-world equivalent of a slow save and an impatient second click, or a browser refresh on the redirect. Failing test: tests/test_hr_integrity_findings.py::test_F6_overtime_double_submit_double_counts

**Expected** — One overtime record for that day, 4h.

**Actual** — Three rows, 12h total. All three can be approved independently and all three feed the /hr/overtime approved-hours total that pay decisions are read from. Nothing on the staff profile or the overtime list flags that one day has three identical entries.

**Cause** — D:\vet\platform\blueprints\hr\routes.py:1357-1379 — add_overtime is a bare INSERT with no uniqueness check; overtime_log has no unique constraint on (user_id, work_date).

**Fix** — Same read-then-write the attendance route next door already uses: look for an existing row on (user_id, work_date) and update it instead of inserting, or add a UNIQUE(user_id, work_date) index and handle the conflict.

*reproduced · money & records*


### [MAJOR] HR creates users and resets passwords with legacy SHA-256, bypassing the bcrypt the rest of the app uses

**Steps** — Local, reproduced. 1) POST /hr/staff/new with a strong password. 2) `SELECT password_hash FROM users WHERE username=?`. Compare with any seeded account on the live demo: `SELECT username, left(password_hash,7), length(password_hash) FROM users` -> all 15 are `$2b$12$`, 60 chars. Failing test: tests/test_hr_integrity_findings.py::test_F7_hr_writes_legacy_sha256_password_hashes

**Expected** — bcrypt cost 12, the same as every other account. models/database.py:2717 defines `_hash_password` whose docstring literally says "Alias for _hash — public API used by HR/reset routes".

**Actual** — The HR blueprint defines its own `_hash` at routes.py:110-111 as `sha256("pah_platform_2026" + password)` — one hard-coded salt shared across every tenant, no per-user salt, no work factor. Both staff_new (routes.py:530) and staff_reset_password (routes.py:827) use it. The account logs in (verify_credentials has a legacy SHA-256 branch that transparently rehashes on first successful login), so nothing looks broken — but a staff account created and not yet used, or one reset for someone who is locked out and cannot log in, sits in the database as a rainbow-table-able hash. Password reset is the one path where an owner sets a password *for* somebody else, and it is the weakest one in the app.

**Cause** — D:\vet\platform\blueprints\hr\routes.py:110-111, used at :530 and :827.

**Fix** — Delete the local `_hash` and `_SALT` and call `db._hash_password` at both call sites. One-line change each; the login path already accepts both formats so nothing needs migrating.

*reproduced · money & records*


### [MAJOR] A shift that starts mid-week is invisible on that week's roster and the staff member is listed as having no shift

**Steps** — Local, reproduced. 1) A nurse with no shift assignment. 2) Open their staff profile, assign a shift with effective_from = Wednesday of the current week (or leave effective_from blank on any day that is not a Monday — the route defaults it to today, routes.py:846). 3) Open /hr/roster for the current week. Failing test: tests/test_hr_integrity_findings.py::test_F8_roster_hides_a_shift_that_starts_midweek

**Expected** — The nurse appears in the shift grid on Wednesday, Thursday and Friday — the days they are actually rostered.

**Actual** — They appear nowhere in the grid for the whole week, and are listed under "Staff without shift assignment". Next week's roster is correct. Meanwhile the HR dashboard's own "without shift" KPI counts them as assigned, so the dashboard and the roster give opposite answers about the same person on the same day. Because effective_from defaults to today, this fires on six days out of seven for the ordinary "assign a shift to a new hire" flow.

**Cause** — D:\vet\platform\blueprints\hr\routes.py:1247 — the roster's assignment query filters `ss.effective_from <= week_start` (the Monday) instead of overlapping the week; the dashboard at routes.py:328-335 ignores effective_from entirely.

**Fix** — Make the roster query an interval overlap: `ss.effective_from <= <last day of week> AND (ss.effective_to IS NULL OR ss.effective_to >= <first day of week>)`, and per-day, only draw the chip on days within the assignment's range. Then make the dashboard's unassigned count use the same predicate so the two screens agree.

*reproduced · money & records*


### [MAJOR] The shipped demo has zero shift assignments, so the weekly roster is an empty screen and all 15 staff read as unassigned

**Steps** — Reproduced on the live demo. 1) Log in to https://demo.aleefy.online as admin. 2) Open /hr/roster. 3) Open /hr/dashboard and read the "without shift" tile. 4) Confirm in the database: `SELECT count(*) FROM staff_shifts` -> 0, while `SELECT * FROM shifts` -> 4 fully-defined shifts (Morning 08:00-16:00/60, Evening 14:00-22:00/60, Night 22:00-06:00/60, Weekend Morning 09:00-15:00/30).

**Expected** — A populated weekly grid — this is the screen a clinic opens every morning to see who is on. The seed defines four shifts and 15 staff; it should assign them.

**Actual** — The shift grid renders zero rows. All 15 staff are listed under "Staff without shift assignment (15)", and the dashboard tile reads 15. The seeder creates shifts and never links anyone to one. Downstream, payroll's _get_attendance_summary finds no shift row and falls back to a generic 8.0h standard day (blueprints/payroll/routes.py:177-178) for the whole clinic. On the demo's July attendance that is the difference between 214.87h and 529.68h of overtime — at the seeded EGP 67.50/h rate, roughly EGP 21,000 a month riding on a fallback nobody chose. (salary_detail.html does at least print "No shift assigned", so the fallback is disclosed on that one page.)

**Cause** — Seed data, not route logic: D:\vet\platform\scripts\seed\demo_showcase.py clears and repopulates staff_shifts' siblings but leaves staff_shifts empty. The HR blueprint's roster and dashboard are where it surfaces.

**Fix** — In the demo seeder, assign each of the 15 staff to one of the four shifts with effective_from at their hire_date — doctors and nurses across Morning/Evening/Night, reception and finance on Morning. Costs a dozen INSERTs and turns the roster from an empty screen into the demo's best-looking one.

*reproduced · money & records*


### [MAJOR] The "Work Shift" dropdown on the Edit Staff form does nothing and always shows "No Shift"

**Steps** — HR > Staff > (any staff member) > Edit. The Employment section renders a "Work Shift" dropdown with the hint "Assigning a shift here will set it from today." Pick a shift, Save. Reproduced with the test client, and the form itself confirmed live: GET https://demo.aleefy.online/hr/staff/1/edit renders <select name="shift_id"> with the four seeded shifts and no `selected` option, even after that person has a shift assigned.

**Expected** — Saving assigns the chosen shift from today, and re-opening the form shows the person's current shift pre-selected.

**Actual** — Flash "Staff member updated successfully." and staff_shifts is unchanged — 0 rows for that user. Re-opening the edit form always reads "— No Shift —" regardless of the real assignment, so HR sees "no shift", picks one, saves, and nothing happens. The only working path is the separate "Update Shift" form on the staff detail page.

**Cause** — blueprints/hr/routes.py:772-805 staff_edit never reads request.form["shift_id"] — only staff_new (routes.py:578-590) does. The template still renders the control at templates/hr/staff_form.html:167-176, and `form` on the edit path is the users row, which has no shift_id column, so the {% if form.get('shift_id') %} comparison never matches.

**Fix** — Either handle shift_id in staff_edit the way staff_new does, or drop the control and its hint from the edit rendering ({% if not editing %}) so the only shift UI is the one that works.

*reproduced · edge cases*


### [MAJOR] A shift assigned on any day but Monday is invisible on this week's roster; the person shows as Unassigned all week

**Steps** — On a non-Monday (reproduced Friday 2026-08-07, week starting Monday 2026-08-03): HR > Staff > (person) > Work Shift card > pick a shift > "Update Shift". Then open HR > Roster (current week). Roster template context captured via flask's template_rendered signal.

**Expected** — The shift appears at least on the remaining days of the current week.

**Actual** — Flash "Shift assigned successfully.", staff_shifts row written with effective_from = 2026-08-07, and the staff detail page shows the shift. But /hr/roster for the current week returns assignments = [] and unassigned = ["Platform Administrator"] — the person has no shift on any of the seven days, including Friday itself. /hr/roster?week=2026-08-10 shows it correctly. The mirror case is equally wrong: a shift ended mid-week still renders on all seven days, because effective_to is compared to the same Monday.

**Cause** — blueprints/hr/routes.py:1244-1247 — `WHERE ss.effective_from <= ? AND (ss.effective_to IS NULL OR ss.effective_to >= ?)` binds week_start (Monday) to both. It should overlap the whole week: effective_from <= week_days[-1] AND (effective_to IS NULL OR effective_to >= week_start).

**Fix** — Bind week_days[-1].isoformat() to the effective_from comparison and keep week_start for effective_to, so the row is selected when its range overlaps the week rather than covering its first day.

*reproduced · edge cases*


### [MAJOR] Creating a staff account has no password policy; resetting the same account's password requires 12 characters

**Steps** — HR > Staff > Add Staff. Username zz_p1, Password "1", Confirm "1", Active ticked, Save. Then log in as zz_p1 with "1". Then, as an owner, use Reset Password on that same staff record with "1".

**Expected** — The same rule on both paths — models/security.validate_password_strength, which returns (False, "Password must be at least 12 characters.") for "1".

**Actual** — Creation: "Staff member 'zz_p1' created successfully." The account then logs in with the password "1" (session user = zz_p1, landed on /). Reset Password on the identical value: "Password must be at least 12 characters." So the only route that mints a new credential is the one with no policy, and the field's own placeholder says "Min 6 characters" — which matches neither.

**Cause** — blueprints/hr/routes.py:553-577 staff_new checks only `not username or not password` and password == confirm. blueprints/hr/routes.py:817 staff_reset_password correctly calls _sec.validate_password_strength. Placeholder text at templates/hr/staff_form.html:52.

**Fix** — Call _sec.validate_password_strength(password) in staff_new before _save_staff_fields, re-rendering the form with the returned message; correct the placeholder to match.

*reproduced · edge cases*


### [MINOR] The Status filter on Performance Reviews does nothing

**Steps** — Live demo: /hr/performance shows 9 reviews, all "مُرسل" (Submitted). Pick "مسودة" (Draft) in the Status dropdown and click Filter. Verified by URL: /hr/performance?status=Draft and ?status=Acknowledged both return the identical 9 review rows.

**Expected** — ?status=Draft returns 0 rows (there are no drafts); ?status=Submitted returns 9.

**Actual** — The filter is ignored entirely — the same 9 rows come back for every value. The dropdown is rendered, the value round-trips into the form so it looks like it stuck, and the result set never changes. This is the pattern where a control returns 200 and changes nothing.

**Cause** — blueprints/hr/routes.py:905-908 builds the WHERE clause from `period` and `user_id` only; :922 passes `status_filter=request.args.get("status","")` to the template purely for redisplay. templates/hr/performance_list.html:43 renders <select name="status">.

**Fix** — Two lines next to the existing filters: `if status: q += " AND pr.status=?"; params.append(status)`. Failing test: test_performance_status_filter_narrows_results.

*reproduced · happy path*


### [MINOR] HR officers are shown five buttons that all bounce them back to the launcher

**Steps** — Sign in as hr.marwa / Demo@1234 (role 'hr' — the role this module was built for). Open any staff profile: the Reset Password form, the ✕ on any warning and the ✕ on any HR note are all rendered. Type a new password and submit → 302 to / with "You don't have permission to access this page." Click ✕ on a warning → same bounce, and the warning is still there. On /hr/staff the "View Roles" button bounces. On /hr/dashboard the "Payroll Dashboard" quick link bounces.

**Expected** — Controls an HR officer cannot use are not rendered for them.

**Actual** — Every one renders and every one dead-ends after the user has already done the work of filling the form. Verified locally for all five. The route-level gating is deliberate and correct (routes.py:48 explains why HR gets no password resets or payroll) — the templates just never got the matching conditions.

**Cause** — templates/hr/staff_detail.html:124 (reset password), :307 (delete warning), :409 (delete note); templates/hr/staff_list.html:11 (View Roles); templates/hr/dashboard.html:188 (Payroll Dashboard). None wrap in a role check.

**Fix** — Wrap each in `{% if session.user.role in ('super_admin','clinic_owner','support_admin') %}` matching the route's own role_required list. Failing test: test_hr_officer_sees_no_reset_password_form.

*reproduced · happy path*


### [MINOR] Negative overtime is accepted, confirmed as success, and drags the Approved Hours total below zero

**Steps** — Staff profile → "تسجيل عمل إضافي" (Record Overtime). Date today, Hours -5, any reason, Save. Then /hr/overtime → Approve that row.

**Expected** — Rejected: "Hours must be greater than zero."

**Actual** — Flash reads "-5.0h overtime recorded." as a success. The row is approvable, and the Approved Hours KPI on /hr/overtime then reads -5.0. A typo or a deliberate adjustment silently corrupts the clinic's overtime total, and there is no edit or delete for an overtime row so it cannot be removed from the UI.

**Cause** — blueprints/hr/routes.py:1363 — `hours = float(f.get("hours") or 0)` with no range check before the insert at :1364.

**Fix** — `if hours <= 0: flash(...); return redirect(...)` before the insert; add a CHECK (hours > 0) on overtime_log. Failing test: test_overtime_rejects_non_positive_hours.

*reproduced · happy path*


### [MINOR] Blank certifications and blank disciplinary warnings save with a success message

**Steps** — On a staff profile, open "إضافة شهادة" (Add Certification) and submit with every field empty. Then open "إصدار إنذار" (Issue Warning) and submit with the Reason box empty.

**Expected** — "Certification name is required." / "Reason is required."

**Actual** — "Certification added." and "Warning recorded." Both write a row: staff_certifications with cert_name='' and staff_warnings with reason=''. The blank cert then appears on /hr/certifications and in the dashboard's expiring-certs panel as a nameless entry; the blank warning becomes a permanent, unexplainable line on someone's disciplinary record. Contrast /hr/staff/<id>/notes/add at routes.py:1185, which correctly refuses an empty note.

**Cause** — blueprints/hr/routes.py:1146 (add_certification) and :1070 (add_warning) insert straight from request.form with no required-field check. The templates set no `required` attribute either.

**Fix** — Mirror add_note: bail out with a danger flash when cert_name / reason is blank. Failing test: test_blank_certification_is_rejected.

*reproduced · happy path*


### [MINOR] Roster week-navigation buttons render "&larr;" as literal text

**Steps** — Live demo: /hr/roster. The Prev/Next week buttons read "&larr; الأسبوع السابق" and "الأسبوع التالي &larr;" on screen. Confirmed in the served HTML: it contains &amp;larr; (double-escaped) in two places.

**Expected** — An arrow glyph.

**Actual** — The literal seven characters "&larr;". The links themselves work — this is purely the label. It happens because the entity is written inside t(), which returns a plain Python string that Jinja autoescaping then escapes again. Same bug on the "Attendance &rarr; Shifts" hint at the bottom of the empty-state.

**Cause** — templates/hr/roster.html:52, :56, :150 — HTML entities inside `t('&larr; Prev Week','&larr; الأسبوع السابق')`.

**Fix** — Use the literal characters ← and → inside t(), or mark the result |safe. (Also note the Arabic Next-week label uses &larr; where it should point the other way for RTL.) Failing test: test_roster_arrows_are_not_double_escaped — assert '&amp;larr;' not in the response body.

*reproduced · happy path*


### [MINOR] Check-in and check-out render as full timestamps on the HR attendance board

**Steps** — Live demo: /hr/attendance. Every row's Check-in column reads e.g. "2026-08-06 08:09:00" and Check-out "2026-08-06 17:02:00", in a table that already has a separate Date column.

**Expected** — "08:09" and "17:02".

**Actual** — The date is repeated three times per row and the columns are twice as wide as they need to be, on the HR screen a clinic looks at daily. The cause is a data-shape mismatch, not a formatting choice: the demo seed writes full 'YYYY-MM-DD HH:MM:SS' strings while the app's own write paths store 'HH:MM'. That mismatch is load-bearing elsewhere — blueprints/attendance/routes.py:22 does `datetime.strptime(check_in[:5], fmt)`, which on a seeded value slices "2026-" and raises.

**Cause** — scripts/seed/demo_showcase.py:340 `_dt()` returns f"{d.isoformat()} {hh:02d}:{mm:02d}:00" and is used for check_in/check_out at :1163-1166, whereas blueprints/hr/routes.py:1545-1546 stores the raw 'HH:MM' from the <input type=time>.

**Fix** — Have the seed write f"{hh:02d}:{mm:02d}" for check_in/check_out and keep _dt for created_at only. Failing test: test_seeded_attendance_times_are_hh_mm.

*reproduced · happy path*


### [MINOR] English-only labels on Arabic HR screens

**Steps** — Live demo (running in Arabic): /hr/dashboard shows two topbar buttons reading "Certifications" and "Staff List" beside four correctly-translated ones. /hr/staff/74 shows "Certifications & Training", "Add Certification", "Overtime / Extra Hours", "View All" and "— Remove Shift —" in English inside an otherwise fully Arabic page. /hr/certifications has the same English page title.

**Expected** — All chrome respects the language toggle, on a product whose stated differentiator is being Arabic-first.

**Actual** — Nine hardcoded English strings across three HR templates, sitting next to correctly-wrapped t() calls — so it reads as breakage rather than a design choice.

**Cause** — templates/hr/dashboard.html:11-12; templates/hr/staff_detail.html:151, 337, 340, 377, 394, 432, 433; templates/hr/certifications_list.html:2-3.

**Fix** — Wrap each in t('English','عربي') like their neighbours.

*reproduced · happy path*


### [MINOR] Raw database and Python errors are shown to the user as flash messages

**Steps** — /hr/staff/new with a username that already exists → "Error creating user: UNIQUE constraint failed: users.username". POST to /hr/staff/<id>/overtime/add with a non-numeric hours value → "Error: could not convert string to float: 'abc'". POST a performance review with no staff selected → "Error: invalid literal for int() with base 10: ''".

**Expected** — "That username is already taken." / "Hours must be a number."

**Actual** — The raw exception text is rendered to whoever is at the keyboard, leaking column names, the storage engine and Python internals. The duplicate-username case is the one a receptionist-grade HR user will actually hit; the others need a crafted POST because the form has required/select constraints.

**Cause** — blueprints/hr/routes.py:598 `flash(f"Error creating user: {e}")`, :1376 and :960 `flash(f"Error: {e}")`.

**Fix** — Log the exception, flash a written-for-humans message. For the duplicate case, check `SELECT 1 FROM users WHERE username=?` before insert and say so.

*reproduced · happy path*


### [MINOR] "Attendance this month" on the staff profile has no upper date bound and counts future-dated records

**Steps** — Local, reproduced. 1) Delete a nurse's attendance. 2) /hr/attendance -> Add Attendance Record with a work_date three months in the future (the date input has no max attribute) — 12 hours, Present. 3) Open /hr/staff/<id> and read the "Attendance this month" card. Failing test: tests/test_hr_integrity_findings.py::test_F9_staff_detail_this_month_has_no_upper_bound

**Expected** — 0 present days, 0 hours — the only record is not in this month.

**Actual** — 1 present day, 12.0 hours. Every future-dated attendance row is folded into the current month's totals forever.

**Cause** — D:\vet\platform\blueprints\hr\routes.py:663-673 — the query is `WHERE user_id=? AND work_date >= ?` with only the first-of-month bound and no end.

**Fix** — Add the upper bound: `AND work_date <= ?` with the last day of the month. While there, add a `max` on the work_date input in templates/hr/hr_attendance.html:343 so a future attendance record cannot be entered by accident in the first place.

*reproduced · money & records*


### [MINOR] Overtime hours are silently rounded to one decimal on PostgreSQL while the confirmation message reports the un-rounded value

**Steps** — Reproduced against the live PostgreSQL: `SELECT 2.75::numeric(4,1)` -> 2.8, `SELECT 2.25::numeric(4,1)` -> 2.3, `SELECT 1000::numeric(4,1)` -> numeric field overflow. Locally, POST /hr/staff/<id>/overtime/add with hours=2.75 flashes "2.75h overtime recorded".

**Expected** — What the screen confirms is what the database holds. Quarter-hours are the natural unit for overtime.

**Actual** — The flash says "2.75h overtime recorded"; PostgreSQL stores 2.8. The clinic is billed for 2.8h. On SQLite the same input stores 2.75 verbatim, so the two engines disagree and every test runs on the one that agrees with the flash message. Anything at or above 1000 raises numeric field overflow and shows the operator a raw driver error.

**Cause** — D:\vet\platform\blueprints\hr\routes.py:214 declares `hours NUMERIC(4,1)`; routes.py:1363-1373 stores and echoes the un-rounded float.

**Fix** — Either widen the column to NUMERIC(5,2) so quarter-hours survive, or round in Python before both the INSERT and the flash so the message and the row always match. Combine with the range guard from the negative-hours finding.

*reproduced · money & records*


### [MINOR] A certification can be saved with an expiry date before its issue date

**Steps** — Local, reproduced. POST /hr/staff/<id>/certifications/add with cert_name "Radiology Licence", issue_date 2026-06-01, expiry_date 2020-01-01, status Active. Failing test: tests/test_hr_integrity_findings.py::test_F10_certification_expiry_may_precede_its_issue_date

**Expected** — Refused — a licence cannot expire six years before it was issued.

**Actual** — "Certification added" and the row is stored. It then appears on /hr/certifications with a large negative days_left and is marked expired on the staff profile. For a clinic tracking veterinary syndicate licences this is a compliance record that quietly holds nonsense; it also means a typo'd expiry can drop a still-valid licence out of the dashboard's 30-day expiry warning.

**Cause** — D:\vet\platform\blueprints\hr\routes.py:1142-1157 — add_certification writes every form field straight through with no date ordering check (cert_name is not checked for emptiness either).

**Fix** — Two lines before the INSERT: reject an empty cert_name, and reject expiry_date < issue_date with a flash. Both dates are already parsed as ISO strings so a string comparison is enough.

*reproduced · money & records*


### [MINOR] POST /hr/staff/<id>/assign-shift raises an uncaught IntegrityError (500 error page)

**Steps** — POST /hr/staff/999999/assign-shift with shift_id=1 and a valid CSRF token, as admin.

**Expected** — A flash such as "User not found." and a redirect, matching every neighbouring HR write route.

**Actual** — sqlite3.IntegrityError: FOREIGN KEY constraint failed propagates out of the view — 500. staff_assign_shift is the one HR write route with no try/except and no existence check. Reachable from a stale staff profile tab, or any shift_id that no longer resolves.

**Cause** — blueprints/hr/routes.py:842-872 — the INSERT at routes.py:855 into staff_shifts (FKs to users and shifts, models/database.py:1995-2003) runs bare.

**Fix** — Wrap the body in the same try/except/db.rollback_quietly/flash pattern used by add_overtime and add_warning, and verify the user and shift rows exist before inserting.

*reproduced · edge cases*


### [MINOR] POST /hr/attendance/add with a non-numeric user_id 500s and leaks a database connection

**Steps** — POST /hr/attendance/add with user_id=abc, status=Present and a valid CSRF token.

**Expected** — "Select a staff member." and a redirect — the same handling the uid==0 case already gets.

**Actual** — ValueError: invalid literal for int() with base 10: 'abc' propagates — 500. The connection opened on the line above is never closed, so on the PostgreSQL deployment every such request leaks one pooled connection.

**Cause** — blueprints/hr/routes.py:1535-1536 — `conn = db.get_db()` and `uid = int(f.get("user_id") or 0)` both sit outside the try/except/finally block that starts at line 1539.

**Fix** — Move `conn = db.get_db()` inside the try (or after the uid parse) and parse uid defensively: `uid = request.form.get("user_id", type=int) or 0`, which returns None for junk instead of raising.

*reproduced · edge cases*


### [MINOR] Success messages are shown for records that do not exist

**Steps** — As admin, POST each of: /hr/staff/999999/reset-password (new_password=Aleefy@Demo2026), /hr/overtime/999999/approve, /hr/overtime/999999/reject, /hr/attendance/999999/delete, /hr/staff/1/warnings/999999/delete, /hr/staff/1/certifications/999999/delete, /hr/staff/1/notes/999999/delete.

**Expected** — "Not found" and no success claim when zero rows were affected.

**Actual** — Every one flashes success. The reset-password case is the clearest: the response carries both "Password reset successfully." and, from the redirect target, "User not found." — two contradictory messages stacked on one screen. The others flash "Overtime approved.", "Overtime rejected.", "Record deleted.", "Warning deleted.", "Certification removed.", "Note deleted." with nothing having happened.

**Cause** — blueprints/hr/routes.py:812 (reset), :1384 / :1398 (overtime approve/reject), :1595 (attendance delete), :1113 (warning delete), :1170 (cert delete), :1206 (note delete) — each runs an UPDATE/DELETE by id and flashes success without inspecting rowcount.

**Fix** — Check the cursor rowcount (or SELECT the row first, as performance_acknowledge already does) and flash "not found" when nothing was affected.

*reproduced · edge cases*


### [MINOR] Overtime approve/reject is not a state machine; a rejected row keeps its approver

**Steps** — HR > Overtime. Approve a Pending row. Approve it again. Then Reject it. Reproduced against overtime_log directly.

**Expected** — Re-approving an already-approved row says so; rejecting clears approved_by.

**Actual** — The second approve flashes "Overtime approved." again as if it were new. Rejecting an approved row leaves the DB at {"status":"Rejected","approved_by":1}, so /hr/overtime renders a rejected entry alongside an approver's name. Two managers clicking opposite buttons on the same row get no conflict warning; the last click silently wins.

**Cause** — blueprints/hr/routes.py:1382-1409 — both routes are unconditional UPDATEs with no status precondition, and reject never clears approved_by.

**Fix** — Add `AND status='Pending'` to both UPDATEs, report "already decided" when rowcount is 0, and set approved_by=? on reject as well (it is the decider, not the approver) or NULL it.

*reproduced · edge cases*


### [MINOR] Raw database and Python error text is flashed to the user

**Steps** — On real forms, as admin: (a) HR > Performance > New Review with Rating outside 1-5; (b) double-click Save on HR > Staff > Add Staff; (c) Log Attendance with a check-in the browser did not normalise; (d) Add Overtime with a non-numeric hours value; (e) submit the performance form without a staff member selected.

**Expected** — A sentence a clinic manager can act on.

**Actual** — Verbatim flashes captured: "Error: CHECK constraint failed: rating BETWEEN 1 AND 5"; "Error creating user: UNIQUE constraint failed: users.username"; "Error: time data '9am' does not match format '%H:%M'"; "Error: could not convert string to float: 'abc'"; "Error: 400 Bad Request: The browser (or proxy) sent a request that this server could not understand." The inputs are correctly rejected — only the wording leaks the schema.

**Cause** — blueprints/hr/routes.py:598 (`flash(f"Error creating user: {e}")`), :801, :955, :1029, :1088, :1163, :1200, :1377, :1587 — every HR except block interpolates the exception into the flash.

**Fix** — Log the exception and flash a fixed message per form ("That username is already taken.", "Rating must be between 1 and 5."). Validate rating and hours in Python before the INSERT so the CHECK constraint is a backstop rather than the UI.

*reproduced · edge cases*


### [MINOR] Fields the browser guards are not validated on the server: overtime hours, role, attendance status, review status and period

**Steps** — POST each field past its client-side guard (browser back + resubmit, a mobile browser that skips HTML5 validation, or any direct POST): /hr/staff/1/overtime/add with hours=-8 and with hours=1000000; /hr/staff/new with role=banana; /hr/attendance/add with status=banana; /hr/performance/new with status=banana and period empty.

**Expected** — Server-side rejection of values outside the documented sets (_ROLES, _OT_STATUSES, _REVIEW_STATUSES, the four attendance statuses) and of non-positive/absurd hours.

**Actual** — All accepted. "-8.0h overtime recorded." and "1000000.0h overtime recorded." are the literal flashes; the form declares min=0.5 max=24 client-side only (templates/hr/staff_detail.html:474). role=banana is stored (users.role is plain text on the live PostgreSQL demo) and that account then matches no permission row anywhere. An attendance row with status=banana is counted in total_n but by none of the Present/Late/Absent/On Leave tiles, so the four cards no longer add up to the total. A review saved with an empty period appears as a blank entry in the period filter dropdown. Note: overtime_log does not reach pay — payroll derives overtime from attendance_records.hours_worked — so the damage is confined to the /hr/overtime report.

**Cause** — blueprints/hr/routes.py:1364 `float(f.get("hours") or 0)`; :494 `f.get("role", "reception")`; :1544 `f.get("status", "Present")`; :949 `f.get("status", "Draft")` and `f.get("period","").strip()`.

**Fix** — One shared helper that rejects a value not in the module's own constant list, plus a positive/upper bound on hours. The constants (_ROLES, _OT_STATUSES, _REVIEW_STATUSES) already exist and are only used to render the dropdowns.

*reproduced · edge cases*


### [MINOR] Warnings, certifications, notes and overtime are written for staff who do not exist, and the app says so in the same breath

**Steps** — POST /hr/staff/999999/warnings/add (or .../certifications/add, .../notes/add, .../overtime/add) as admin.

**Expected** — Nothing written, one "User not found." message.

**Actual** — Two flashes in the same response: "Warning recorded." and "User not found." (likewise "Certification added.", "Note saved.", "4.0h overtime recorded."). The rows are in the tables — verified staff_warnings, staff_certifications, staff_notes and overtime_log each hold a user_id=999999 row afterwards — and are invisible on every screen, since /hr/certifications, /hr/overtime and /hr/performance all inner-join users. They accumulate silently.

**Cause** — The HR-owned tables created in blueprints/hr/routes._ensure_hr_tables (routes.py:135-224) carry no FOREIGN KEY on user_id, unlike staff_shifts and attendance_records in models/database.py. None of the add_* routes check that the user exists before inserting.

**Fix** — Add the FK to those four tables, or (cheaper, no migration) look the user row up once at the top of each add_* route and redirect with "User not found." — the pattern staff_detail already uses.

*reproduced · edge cases*


### [MINOR] A backdated shift assignment inverts the previous assignment's dates and erases it from the record

**Steps** — HR > Staff > (person) > Work Shift: assign shift A with no effective-from date (defaults to today). Then assign shift B with Effective From set to an earlier date — e.g. correcting a shift change to start at the beginning of the month.

**Expected** — The previous assignment is closed at a date at or after its own start, and remains readable as history.

**Actual** — Row A becomes effective_from 2026-08-07, effective_to 2020-01-01 — an impossible range. Both the roster query and the staff-detail "current shift" query require effective_to >= the date being asked about while effective_from <= it, so row A can never match again: shift A silently vanishes from the person's history with no delete and no audit entry.

**Cause** — blueprints/hr/routes.py:851-854 — `UPDATE staff_shifts SET effective_to=<new effective_from> WHERE user_id=? AND (effective_to IS NULL OR effective_to >= today)` without checking the new date is after the row's own effective_from. The Effective From input (templates/hr/staff_detail.html:158) has no min attribute.

**Fix** — Only close rows whose effective_from is strictly before the new effective_from; for rows that start on or after it, delete or supersede them explicitly. Set min on the date input to the current assignment's start.

*reproduced · edge cases*


### [MINOR] Double-clicking Save duplicates performance reviews, HR notes, warnings and shift rows

**Steps** — Submit the same form twice in quick succession (a double-click, or back-then-resubmit) on: HR > Performance > New Review; the Add Note box on a staff profile; the Add Warning box; the Update Shift box.

**Expected** — One record, or a clear "already recorded".

**Actual** — Two identical performance reviews, two identical HR notes, two identical "Final Warning" rows (a duplicated disciplinary record is not cosmetic), and two staff_shifts rows — the first left with effective_from == effective_to == today, an empty one-day assignment. Only Add Staff is protected, by the users.username unique index, and that protection surfaces as "Error creating user: UNIQUE constraint failed: users.username".

**Cause** — No idempotency on any of the HR POST handlers; no submit-button disabling in templates/hr/staff_detail.html or performance_form.html.

**Fix** — Cheapest fix that covers all of them: disable the submit button on first submit in the shared form partial. For warnings and reviews specifically, a natural key check (same user + same period, same user + same type + same issued_date) before insert.

*reproduced · edge cases*


### [MINOR] Certification and warning dates are accepted inverted, and a certification saves with no name

**Steps** — Staff profile > Add Certification: Certification = "Rabies Licence", Issue Date = 2026-08-01, Expiry Date = 2020-01-01, Save. Then Add Certification with the name left blank. Then Add Warning with Type = "Final Warning" and Reason left blank.

**Expected** — "Expiry date must be after the issue date", "Certification name is required", "Reason is required".

**Actual** — All three save with a green flash. The inverted certification is stored with status "Active" and immediately renders as "Expired" on /hr/certifications — the row on screen reads "Rabies Licence — — 2026-08-01 2020-01-01 Expired". The nameless certification renders as an unidentifiable blank row on the certifications screen; a mistyped expiry year is the realistic version of this, and it puts a valid licence into the expired list (or vice versa) with no warning. The empty-reason Final Warning is a disciplinary record with nothing in it.

**Cause** — blueprints/hr/routes.py:1140-1166 add_certification and :1064-1090 add_warning insert whatever the form carries. add_note (routes.py:1183-1187) is the only one of the three that rejects an empty body.

**Fix** — Mirror add_note's guard: require cert_name and reason, and compare expiry_date > issue_date (and expiry_date > issued_date for warnings) before insert.

*reproduced · edge cases*


### [INFO] Five HR tests fail today, and the one that would have caught the night-shift bug cannot even import

**Steps** — .venv/Scripts/python.exe -m pytest tests/test_hr_routes.py tests/test_hr_edges_audit.py tests/test_hr_edges_audit2.py tests/test_hr_integrity_audit.py tests/test_hr_probe.py -q → 5 failed, 151 passed.

**Expected** — Green, or the files removed.

**Actual** — test_hr_edges_audit2.py::test_overnight_attendance_costs_payroll dies on `ImportError: cannot import name '_attendance_summary' from blueprints.payroll.routes` — the exact scenario in finding #2, written by an earlier audit, never asserting and now not even running. test_hr_edges_audit.py::test_assign_shift_bogus_shift / _nonnumeric / _ghost_user each surface an unhandled sqlite3.IntegrityError, i.e. POSTing /hr/staff/<id>/assign-shift with a shift_id that does not exist returns a 500 rather than a flash (routes.py:842-869 has no try/except). test_attendance_add_nonnumeric_user shows the same for `int(f.get("user_id"))` at routes.py:1536, which sits outside the try block. All four are only reachable by hand-crafting a POST, so they are low-priority on their own — but the files are noise that hides the useful signal.

**Cause** — tests/test_hr_edges_audit.py, tests/test_hr_edges_audit2.py:128 (stale import), blueprints/hr/routes.py:1536 and :842-869 (unguarded conversions/inserts).

**Fix** — Either turn these into real assertions or delete the files. If keeping them, wrap staff_assign_shift's inserts and hr_attendance_add's int() in the same try/except+rollback_quietly pattern the neighbouring routes already use.

*reproduced · happy path*


### [INFO] The test suite is order-dependent — HR's own shift tests break the attendance integrity module

**Steps** — cd D:\vet\platform. Run `python -m pytest tests/test_attendance_integrity.py -q` -> 8 passed. Now run `python -m pytest tests/test_hr_routes.py tests/test_attendance_integrity.py -q` -> 1 failed, 64 passed, 7 errors, all `sqlite3.IntegrityError: FOREIGN KEY constraint failed`. Same with tests/test_hr_edges_audit.py in the pair (4 failed).

**Expected** — The same tests give the same result regardless of what ran before them.

**Actual** — test_attendance_integrity.py's `shift` fixture does `DELETE FROM shifts`, which violates the foreign key from the staff_shifts rows that hr.staff_assign_shift tests leave behind in the session-scoped database. Whether the suite is green depends on the order pytest-randomly happens to pick. Worth knowing given that "1,781 tests pass" is the number the project's confidence rests on — that number is not stable across runs.

**Cause** — D:\vet\platform\tests\test_attendance_integrity.py:26-37 (the DELETE FROM shifts fixture) colliding with residue from D:\vet\platform\tests\test_hr_routes.py:335-355. Not a product bug.

**Fix** — Have the shift fixture clear staff_shifts before shifts, or scope it to a shift it created itself rather than truncating the table. My own new file's day_shift fixture has the same residue and would need the same treatment.

*reproduced · money & records*


### [INFO] Attendance check-in times are stored in two different formats in the same text column

**Steps** — Read the live demo: attendance_records.check_in and check_out are `text` on aleefy_demo (verified via information_schema). The seeded rows render as "2026-08-06 08:11:00" on https://demo.aleefy.online/hr/attendance, while the HR "Log Attendance Record" form writes the bare "HH:MM" its <input type="time"> produces.

**Expected** — One format per column.

**Actual** — Two. /hr/attendance orders by `ar.check_in NULLS LAST` (blueprints/hr/routes.py:1481), a plain text sort, so a hand-entered "09:00" sorts after every seeded "2026-..." timestamp regardless of the actual time, and the Check In column shows the two shapes side by side. No screen crashes and no arithmetic depends on it today — hours_worked is computed from the form values before storage — but any future code that parses this column will meet both shapes.

**Cause** — blueprints/hr/routes.py:1541-1542 stores the raw form values; the seeder writes full timestamps into the same TEXT column.

**Fix** — Normalise on write (store HH:MM, or store a full timestamp) and backfill, or sort on a derived time value rather than the raw text.

*likely · edge cases*


## System  (45)

### [BLOCKER] System → Roles lists every built-in role a second time under "Custom Roles (14)" — with working Edit and Delete buttons

**Steps** — Log in to https://demo.aleefy.online as admin / Aleefy@Demo2026 → System → Roles & Permissions. Scroll past the Management / Clinical / Front Desk sections (which show Super Admin, Doctor / Vet, Receptionist… each tagged "built-in") to the section headed "Custom Roles (14)". Every one of those same 14 roles is listed again — super_admin, clinic_owner, doctor, nurse, reception, pharmacist, finance, hr, inventory_mgr, groomer, boarding_staff, auditor, support_admin, branch_manager — each with an "Edit Role" button and (as super_admin) a "Delete" button. Verified live: the page contains 14 openEdit(...) calls and 14 delete forms, and 'Doctor / Vet' + 'Doctor / Veterinarian' both appear. Reproduced locally too.

**Expected** — The Custom Roles section lists only roles the clinic actually created. The built-in roles appear once, read-only, exactly as their own detail panel promises: "System roles are enforced in code and cannot be modified."

**Actual** — Every built-in role is rendered twice: once read-only as "built-in", once as a deletable "custom" role. A clinic owner tidying up roles he never created will click Delete on the real doctor/reception/nurse role. Locally I deleted role id 1 (super_admin) through this route and the row was gone. Combined with the next finding, deleting `doctor` silently grants every doctor in the clinic access to every module.

**Cause** — D:\vet\platform\blueprints\system\routes.py:768-787 — roles_list() passes BOTH the hardcoded _SYSTEM_ROLE_PERMS dict and db.list_roles(); the roles table already contains all 14 built-ins, so D:\vet\platform\templates\system\roles.html:230-240 renders them again as "Custom Roles", and the macro at roles.html:168-186 attaches Edit/Delete to that copy because it is called with is_system=False.

**Fix** — In roles_list(), exclude the 14 built-in names from `roles` before passing them to the template (`roles = [r for r in db.list_roles() if r['name'] not in _SYSTEM_ROLE_PERMS]`) — or drop the hardcoded section entirely and drive the whole page from the roles table, which is what the app actually enforces. Also refuse role_delete for a name in the built-in set.

*reproduced · edge cases*


### [BLOCKER] Deleting a role does not move the staff who hold it, and a user with an unknown role falls OPEN to every module

**Steps** — System → Roles → "+ New Custom Role", key `night_shift`, tick only "Patients". Assign a staff member to it in the Staff Access tab. Confirm that user is blocked from /finance/invoices, /accounting/, /inventory/, /hr/ (all redirect to /). Now delete the night_shift role (one click + a browser confirm()). The user's users.role is still 'night_shift'. Log in as that user again — or just keep the tab they already had open.

**Expected** — Deleting a role either refuses while users still hold it, or moves those users to a safe default. Either way, the user's access never widens.

**Actual** — Reproduced locally end to end. Before delete: /finance/invoices, /accounting/, /hr/, /inventory/, /reports/ all 302 → / (denied). After the role row is deleted, the exact same user gets 200 on /finance/invoices, /accounting/, /inventory/ and reaches /hr/dashboard and /reports/dashboard. Same for the session that was already open. The only thing still holding is routes with an explicit @role_required — which is 105 of 406 routes. Note the demo has 15 staff spread over 11 roles, all of which are deletable per the previous finding.

**Cause** — D:\vet\platform\models\database.py:4225 delete_role() is a bare `DELETE FROM roles WHERE id=?` — it never touches users. D:\vet\platform\blueprints\auth\routes.py:113-115: `granted = _role_permissions(role); if granted is None: return None` — _role_permissions (auth/routes.py:210-236) returns None when there is no row for that role name, and the gate deliberately falls open on None.

**Fix** — Two guards, both cheap: (1) in role_delete, refuse if `SELECT COUNT(*) FROM users WHERE role=?` > 0 and say how many staff are affected; (2) distinguish "role name not found at all" from "role exists with no grant data" in _role_permissions — the fall-open was written for the upgrade case (a role row with an empty permissions_json), not for a name that has no row, which now means deleted.

*reproduced · edge cases*


### [BLOCKER] Sync conflict "Keep Local" throws the device's version away and reports "Conflict resolved. Kept: local version."

**Steps** — System → Data Migration / Sync → Unresolved Conflicts. The screen shows the local (device) payload and the server payload side by side under the caption "Choose which version to keep — local (device) or server", with a "Keep Local" and a "Keep Server" button. Click Keep Local. Reproduced locally with a seeded conflict whose local_payload was {"id":1,"name":"Bosy-from-tablet","weight":12.4} and server_payload {"id":1,"name":"Bosy-from-server","weight":9.0}.

**Expected** — Keep Local writes the device's version over the server record. Keep Server leaves the server record alone. The two buttons do different things.

**Actual** — Both buttons do exactly the same thing: the row gets resolution_status='MANUAL_RESOLVED', resolved_by and resolved_at, and nothing else. local_payload is never applied to any table — it just sits in sync_conflicts forever. The user is told "Conflict resolved. Kept: local version." The `keep` value is not even validated: posting keep=banana flashes "Conflict resolved. Kept: banana version." A clinic that resolves a weight or a vaccination date in favour of the tablet gets the server's value and is told the opposite.

**Cause** — D:\vet\platform\models\sync.py:157-169 — resolve_conflict() takes `keep` in its signature and its docstring says "keep='server'|'local'", but the body only runs one UPDATE of sync_conflicts and never branches on `keep`. Caller: D:\vet\platform\blueprints\system\routes.py:711-733.

**Fix** — Either implement the local branch (apply local_payload to the named entity inside the same transaction) or — the honest lazy fix until sync is real — remove the Keep Local button from D:\vet\platform\templates\system\sync.html:200-205 and change the flash to say the conflict was dismissed, not resolved. Reject any `keep` value that is not 'server'/'local'. Failing test to write: test_sync_keep_local_applies_local_payload.

*reproduced · edge cases*


### [BLOCKER] Backup / Restore screen operates on the WRONG database in any tenant-resolved deployment — "Restore" would wipe the clinic with another database's dump

**Steps** — Live demo, proven end to end.
1. Sign in at https://demo.aleefy.online as admin (tenant slug `demo` -> PostgreSQL database `aleefy_demo`).
2. Open System -> Backup & Restore (/system/backup). It lists exactly ONE archive: `platform_backup_20260806_212817.dump`, 0.23 MB, "last successful backup 18 hours ago".
3. On the server: `pg_restore --list /srv/aleefy/data/backups/platform_backup_20260806_212817.dump` ->
   `dbname: aleefy_platform`, 83 TABLE DATA entries.
4. The demo clinic's REAL nightly backups are in a different directory and are not on the screen at all:
   /srv/aleefy/data/backups/demo/platform_backup_20260807_020000.dump -> `dbname: aleefy_demo`, 95 TABLE DATA entries, 446 KB, taken today 02:00.
   Same for 20260806_020000.dump.
5. Reproduced locally: tests/conftest app + `import models.backup as bk`; in a web request `bk._backup_dir` = <data>/backups and `bk._postgres_dsn()` = the process-wide DSN, while inside `with bk.for_clinic('demo', pg_dsn=...)` (what the scheduler uses) it is <data>/backups/demo and the clinic's own DSN.

**Expected** — The Backup screen for clinic X lists clinic X's archives, "Backup Now" dumps clinic X's database, and "Restore" restores clinic X.

**Actual** — models/backup.py keeps `_backup_dir` and the DSN as PROCESS GLOBALS set once at startup (app.py:156-157 `bk.configure(...)`), with no clinic slug. models/database.py resolves the tenant PER REQUEST via models/tenancy.py. Nothing on the request path ever calls `bk.for_clinic()`. Consequences on the live demo, all three confirmed: (a) the nightly per-clinic backups are invisible and unrestorable from the UI; (b) "Backup Now" dumps `aleefy_platform` instead of the clinic you are looking at — that is exactly what the 241 KB file family is; (c) "Restore" would run pg_restore --clean of an `aleefy_platform` dump against the process DSN while the operator believes they are restoring the demo clinic. bk.health()/check_and_notify() also measure staleness against the wrong folder, so the green "18 hours ago" badge is describing a foreign database.

**Cause** — blueprints/system/routes.py:442-541 (backup, backup_run, backup_verify, backup_download, backup_restore) via models/backup.py:66 `configure()` / :104 `_postgres_dsn()` / :403 `list_backups()`; process globals `_db_path`, `_backup_dir`, `_tenant_dsn` set at app.py:156-157 and only ever re-pointed by app.py:700 in the scheduler.

**Fix** — Make the request path tenant-aware the same way the scheduler already is: wrap every /system/backup* view in `bk.for_clinic(tenancy.current(), db_path=..., pg_dsn=...)` (a `before_request` on system_bp, or a small decorator), reading the row from `models.tenancy`. Failing test to write: `tests/test_system_routes.py::test_backup_screen_targets_the_request_tenant` — register two clinics, run the scheduler's backup for clinic A, then GET /system/backup under clinic A's host and assert the archive appears in list_backups() and that `bk._postgres_dsn()` inside the view is clinic A's DSN, not the process default.

*reproduced · money & records*


### [BLOCKER] The Staff Access role dropdown offers "staff", a role that does not exist — picking it grants Finance, Accounting, Inventory and Procurement

**Steps** — 1. Open /system/roles. The role table advertises "Staff" as the most restricted role: Manage Patients + Manage Appointments only (blueprints/system/routes.py:751).
2. Open the Staff Access tab. The role <select> is built from a hardcoded JS list (templates/system/roles.html:471-472) that includes `staff`.
3. Pick a receptionist, choose "staff", save. Flash: "Role assigned successfully."
4. Sign in as that user.
Local reproduction (Flask test client, throwaway DB):
  role=reception -> /finance/ 200, /accounting/ 302, /inventory/ 302, /procurement/ 302
  POST /system/roles/assign {user_id, role: 'staff'} -> "Role assigned successfully"
  role=staff     -> /finance/ 200, /accounting/ 200, /inventory/ 200, /procurement/ 200

**Expected** — A user given the most limited role on the screen can reach less than a receptionist, not more.

**Actual** — There is no row named `staff` in the `roles` table (confirmed on the live demo: roles.csv from /system/export/all has 14 roles, none of them `staff`). `_role_permissions('staff')` (blueprints/auth/routes.py:208) finds no row and returns None, and `_permission_denied` (blueprints/auth/routes.py:114) is documented to FALL OPEN on None. So the user is un-gated at the module level and reaches every blueprint that has no explicit @role_required list — including the ledger, stock and purchasing. The owner picks the lock and gets the master key.

**Cause** — templates/system/roles.html:471-472 (hardcoded dropdown incl. 'staff') + blueprints/system/routes.py:871 role_assign (no validation that the role exists) + blueprints/auth/routes.py:114 fall-open on unknown role.

**Fix** — Validate in `role_assign`: reject any role not present in `db.list_roles()` and flash an error instead of writing it. Either drop `staff` from the dropdown or seed a real `staff` row. Build the dropdown from `db.list_roles()` only. Failing test: `tests/test_role_consistency.py::test_every_role_the_ui_offers_exists_in_the_roles_table` — assert the hardcoded list in templates/system/roles.html and in `_SYSTEM_ROLE_PERMS` is a subset of `{r['name'] for r in db.list_roles()}`.

*reproduced · money & records*


### [BLOCKER] Deleting a role silently gives every staff member who held it access to Finance, Accounting and Inventory

**Steps** — Local reproduction against the real routes:
1. As admin, POST /system/roles/create {name: kennel_hand, display_name: Kennel Hand, permissions: [patients]}.
2. A user with role=kennel_hand: /finance/ 302, /accounting/ 302, /inventory/ 302 (correctly denied).
3. On /system/roles, click Delete on that role. The only confirmation is `confirm('Delete role Kennel Hand?')` (templates/system/roles.html:178) — it does not say how many staff hold it, even though the page already loaded `user_counts` and displays that number one column over.
4. The same user, unchanged, now: /finance/ 200, /accounting/ 200, /inventory/ 200.

**Expected** — Deleting a role either refuses while users still hold it, or at minimum does not WIDEN what those users can see.

**Actual** — `db.delete_role` (models/database.py:4225) is a bare DELETE with no check on `users.role`; the users keep the now-orphaned role string. `_role_permissions` then finds no row, returns None, and `_permission_denied` falls open (blueprints/auth/routes.py:114). Revoking a role is the one action an owner takes when someone should see LESS, and it is the action that grants the most.

**Cause** — blueprints/system/routes.py:855 role_delete -> models/database.py:4225 delete_role; fall-open at blueprints/auth/routes.py:113-115.

**Fix** — Refuse the delete when `SELECT COUNT(*) FROM users WHERE role=?` is non-zero and tell the owner how many staff to move first (the count is already in `user_counts` on that page). Failing test: `tests/test_role_consistency.py::test_deleting_a_role_does_not_widen_its_users_access`.

*reproduced · money & records*


### [BLOCKER] Unticking every permission on a role WIDENS it — nurses gain Finance, Accounting and Inventory, and the screen says "Role updated successfully"

**Steps** — Local reproduction against the real routes:
1. Shipped nurse grant: [patients, appointments, visits, pharmacy, inpatient, imaging, attendance].
   role=nurse -> /finance/ 302, /accounting/ 302, /inventory/ 302, /pharmacy/ 200.
2. /system/roles -> edit Nurse -> untick every permission box -> Save.
   Flash: "Role updated successfully."  Stored `permissions_json` becomes `[]`.
3. role=nurse -> /finance/ 200, /accounting/ 200, /inventory/ 200.

**Expected** — A role with no permissions ticked can reach nothing, or the save is refused with "a role must have at least one permission".

**Actual** — `_role_permissions` (blueprints/auth/routes.py:233 `perms = keys or None`) deliberately maps an empty list to None — "no data, fall back" — and `_permission_denied` falls open on None. That fallback exists for the upgrade path (roles seeded without permissions_json), but the Roles screen writes exactly the same value, so the UI's only lock-down gesture is indistinguishable from "never configured" and does the opposite of what the button says.

**Cause** — blueprints/system/routes.py:825 role_edit -> models/database.py:4215 update_role writes '[]'; blueprints/auth/routes.py:231-233 collapses [] to None; :113-115 falls open on None.

**Fix** — Distinguish "never configured" (NULL permissions_json) from "explicitly empty" ('[]'). Simplest: have role_edit refuse an empty permission list with a flash, so '[]' can never be written from the UI. Failing test: `tests/test_role_consistency.py::test_clearing_every_permission_does_not_widen_a_role`.

*reproduced · money & records*


### [BLOCKER] Roles screen: assigning the "staff" role hands a nurse the clinic's money screens

**Steps** — Live demo as admin (or owner.hossam). System → Roles & Permissions → "Staff Access" tab → pick any nurse (e.g. nurse.mariam) → in her row's role dropdown choose "staff" → Save. Then sign in as that nurse and open /finance/invoices, /accounting/, /inventory/, /procurement/, /reports/dashboard. Reproduced locally against tests/conftest fixtures: a user with role='nurse' gets 302→/ on all five; after POST /system/roles/assign {user_id, role:'staff'} the same user gets 200 on all five.

**Expected** — "Staff" is the most restricted role on the Roles screen — it is displayed there with exactly two permissions (Manage Patients, Manage Appointments). Assigning it should narrow access, not widen it.

**Actual** — Flash says "Role assigned successfully." The user now reaches every blueprint that carries only @login_required — invoices, payments, the general ledger, stock, purchasing, reports. Cause: 'staff' has no row in the `roles` table (the demo's table holds 14 roles and 'staff' is not one of them), so _role_permissions('staff') returns None, and _permission_denied() treats None as "ungovernable, fall open". The same happens for any typo: I assigned role='recepton' and got the identical full-access result.

**Cause** — templates/system/roles.html:470-472 (the `sys` array in _roleOpts offers 'staff'); blueprints/auth/routes.py:113-115 (_permission_denied returns None → allow when granted is None); blueprints/system/routes.py:871 role_assign performs no validation that the role exists.

**Fix** — Build the Staff Access dropdown from db.list_roles() only — drop the hardcoded `sys` array that contains a role with no permission row. And reject an unknown role in role_assign (`if role not in {r['name'] for r in db.list_roles()}: flash(...); return`). The fail-open in _permission_denied is defensible for an upgrade path, but it must not be reachable from a dropdown.

*reproduced · happy path*


### [BLOCKER] Deleting a role from the Roles screen silently grants that role's users full access

**Steps** — System → Roles & Permissions. Every real role (Doctor, Nurse, Receptionist, Finance…) is listed a second time under the "Custom Roles (14)" heading with Edit and Delete buttons — on the live demo those are /system/roles/{1..14}/delete. Click Delete on "Nurse". Reproduced locally: a user with role='nurse' gets 302→/ on /finance/invoices, /accounting/, /inventory/, /procurement/, /reports/dashboard; after POST /system/roles/5/delete the same user gets 200 on all five. Same result deleting 'doctor'.

**Expected** — Deleting a role should either be refused while users still hold it, or leave those users with no more access than before.

**Actual** — Flash: "Role deleted." Every user holding that role immediately gains access to the clinic's invoices, payments, accounting, stock, purchasing and reports. Nothing on screen reveals it: the Roles page still renders "Nurse" in its built-in section with its old permission list, because that section is drawn from a hardcoded dict, not from the table the row was deleted from. Same fail-open path as the finding above (_role_permissions returns None → allow).

**Cause** — blueprints/system/routes.py:855-868 role_delete (no check for users holding the role); models/database.py:4225 delete_role; templates/system/roles.html:229-238 renders every roles-table row as a deletable "custom" role.

**Fix** — Refuse the delete when `SELECT COUNT(*) FROM users WHERE role=?` is non-zero, and stop rendering the 14 built-in roles under "Custom Roles" — only rows that are not in db.DEFAULT_ROLE_PERMISSIONS belong there.

*reproduced · happy path*


### [BLOCKER] Backup Manager backs up and restores the wrong database on the multi-tenant deployment

**Steps** — Sign in to https://demo.aleefy.online as admin or owner.hossam → System → Backup Manager. It lists exactly one archive: platform_backup_20260806_212817.dump, 0.23 MB. On the server, that file lives in /srv/aleefy/data/backups/ (the platform directory). The demo clinic's own archives are in /srv/aleefy/data/backups/demo/ — three of them, including today's 02:00 run at 446 KB — and none appear on the page. `pg_restore -l` on the listed file shows 83 TABLE DATA entries; the clinic's own dump has 95, matching the 95 tables Diagnostics reports. `SELECT count(*) FROM visits` is 0 in aleefy_platform and 390 in aleefy_demo.

**Expected** — The clinic's Backup Manager lists the clinic's backups, "Backup Now" dumps the clinic's database, Download hands over the clinic's records, and Restore restores the clinic.

**Actual** — Every button on the page operates on aleefy_platform (the tenant registry), not on aleefy_demo. "Backup Now" flashes "Backup completed: platform_backup_….dump (235.9 KB)" while dumping a database containing zero of the clinic's 390 visits, 392 invoices and 329 payments — that 2026-08-06 21:28 file is exactly such a click. Download gives the owner a file he believes is his records and which contains none of them. Restore runs `pg_restore --clean --if-exists -d aleefy_platform`, i.e. it wipes and replaces the platform/tenant database while the confirmation dialog tells the owner he is about to lose his own visits and invoices. The nightly scheduler is correct — it wraps each clinic in bk.for_clinic() — but the web routes never do, and models.backup keeps its target in module globals set once at create_app().

**Cause** — app.py:157 bk.configure(db_path=app.config['DATABASE_PATH'], backup_dir=…) sets process-wide globals; models/backup.py:104-116 _postgres_dsn() falls back to os.environ['POSTGRES_DSN'] (= …/aleefy_platform) whenever _tenant_dsn is empty; blueprints/system/routes.py:442-540 (backup, backup_run, backup_verify, backup_download, backup_restore) never enter bk.for_clinic().

**Fix** — Wrap the five backup views in bk.for_clinic(tenancy.current(), …) the same way app.py's _daily_backup does — one contextmanager around the body of each view. Until then the Backup page on a tenant subdomain is worse than absent.

*reproduced · happy path*


### [MAJOR] The Roles screen shows the wrong permissions for every built-in role — the list it displays is not the list the app enforces

**Steps** — Live: open System → Roles as admin and expand "Doctor / Vet" in the Clinical section. It shows WhatsApp ticked, and Price Catalog / Inpatient / Imaging / Telemedicine / Attendance unticked. Then log in as dr.sara / Demo@1234 and try each of those pages.

**Expected** — The permissions grid on the Roles screen is what the app enforces.

**Actual** — Verified against the live demo: dr.sara gets 302 → / (denied) on /whatsapp/ which the screen shows as GRANTED, and 200 on /catalog/, /inpatient/ and /attendance/ which the screen shows as NOT granted. The screen is wrong in both directions, for every built-in role. Worse, the same role is drawn twice on the same page (see the first finding) with two different permission lists — the "built-in" copy from the hardcoded dict, the "custom" copy from the DB. Hardcoded doctor = [ai, appointments, patients, pharmacy, reports, visits, whatsapp]; DB/enforced doctor = [ai, appointments, attendance, catalog, imaging, inpatient, patients, pharmacy, reports, telemedicine, visits]. An owner asking "can my vet see my prices?" is told no; the app says yes.

**Cause** — D:\vet\platform\blueprints\system\routes.py:740-752 — _SYSTEM_ROLE_PERMS is a second, stale copy of the permission map. Enforcement reads roles.permissions_json (D:\vet\platform\blueprints\auth\routes.py:226-236, seeded from DEFAULT_ROLE_PERMISSIONS in models/database.py). The two have drifted.

**Fix** — Delete _SYSTEM_ROLE_PERMS and render the built-in section from db.list_roles() as well — one source, the one that is enforced. Add a test that asserts the page's permission grid for each role equals db's permissions_json.

*reproduced · edge cases*


### [MAJOR] "Export everything" ZIP hands out every staff password hash, TOTP secret and 2FA backup code

**Steps** — System → any page with the data-export action, or GET /system/export/all as admin or a clinic_owner. Unzip. Reproduced locally: 76 CSVs.

**Expected** — A "take your data with you" export contains the clinic's records. Credentials are not records.

**Actual** — users.csv has columns `id,username,password_hash,full_name,…,totp_secret,totp_enabled,totp_confirmed_at,last_totp_counter` — bcrypt hashes and plaintext TOTP seeds — and totp_backup_codes.csv is in there too. The bundled README.txt tells the recipient to open the files in Excel or Google Sheets, i.e. it is designed to be forwarded. Anyone who receives this ZIP can generate valid 2FA codes for every staff member forever and can crack the weaker passwords offline. The route is open to clinic_owner, not just super_admin.

**Cause** — D:\vet\platform\blueprints\system\routes.py:907-911 — _EXPORT_SKIP excludes log/queue tables but not users or totp_backup_codes; routes.py:945 does `SELECT *` per table.

**Fix** — Add "totp_backup_codes" to _EXPORT_SKIP and drop the sensitive columns from users.csv (password_hash, totp_secret, last_totp_counter) rather than the whole table — the clinic legitimately wants its staff list. Failing test: test_export_contains_no_credentials.

*reproduced · edge cases*


### [MAJOR] Stored XSS on System → Roles → Staff Access: staff names go straight into innerHTML

**Steps** — Set any user's full_name to `<img src=x onerror=alert(1)>` (reachable from staff/HR profile editing). Then open System → Roles → Staff Access tab as admin. Locally I set the name and confirmed GET /system/roles/users returns it verbatim in JSON: ["<img src=x onerror=alert(1)>"].

**Expected** — A staff name is displayed as text.

**Actual** — The Staff Access table is built by string-concatenating u.full_name, u.username and u.role into innerHTML with no escaping, so the markup executes in the browser of whoever opens the tab — which by role gating is always a super_admin, clinic_owner or support_admin. The same row also embeds the CSRF token and a ready-made role-assignment form, so injected script can promote its own account silently.

**Cause** — D:\vet\platform\templates\system\roles.html:511-530, inside saRender(): `tbody.innerHTML = page.map(function(u){ … '<span style="font-weight:600">'+(u.full_name||u.username)+'</span>' … '<span class="rbadge">'+u.role+'</span>' … }).join('')`. Data source: /system/roles/users (routes.py:790-799).

**Fix** — One helper: `function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return '&#'+c.charCodeAt(0)+';';});}` and wrap the three interpolations. Same pattern is used for the pager and role options — check those too.

*likely · edge cases*


### [MAJOR] Role edit / delete / assign report success for records that do not exist

**Steps** — POST /system/roles/999999/edit, POST /system/roles/999999/delete, POST /system/roles/assign with user_id=999999. Real-world version: two admins, or one admin with the Roles page open in two tabs — A deletes a role, B (whose page is 30 seconds stale) clicks Edit Role on it and saves.

**Expected** — "That role no longer exists — someone else may have deleted it."

**Actual** — All three flash success: "Role updated successfully.", "Role deleted.", "Role assigned successfully." Nothing was changed. Reproduced. The admin walks away believing the permission change is live. Same for assigning a role to a user id that does not exist.

**Cause** — D:\vet\platform\blueprints\system\routes.py:846-849, 857-865, 879-884 — the flashes fire on "no exception", and update_role/delete_role/assign_user_role (models/database.py:4215-4234) are bare UPDATE/DELETE statements whose rowcount is never checked.

**Fix** — Return `cur.rowcount` from the three model functions and flash the success message only when it is 1. Failing test: test_editing_a_deleted_role_does_not_claim_success.

*reproduced · edge cases*


### [MAJOR] Staff Access role dropdown silently pre-selects "super_admin" for any user whose role is not in the option list

**Steps** — Create a custom role, assign a staff member to it, delete the role (see finding 2 — the role name stays on the user). Reopen System → Roles → Staff Access. The row shows the true role in the badge column, but the Assign Role <select> next to it has no matching <option>, so the browser displays the first one — super_admin. Click Save on that row.

**Expected** — The dropdown shows the user's current role, or an explicit "(unknown role — choose one)" entry.

**Actual** — The dropdown displays super_admin while the badge two columns left says something else. An admin who clicks Save on that row — the natural reflex when a row "looks wrong" — promotes that staff member to super_admin, and the server accepts it without complaint. The server-side route also accepts any arbitrary string: POST role=banana_role set the user's role to 'banana_role' and flashed "Role assigned successfully." (reproduced), which then triggers the fall-open in finding 2.

**Cause** — D:\vet\platform\templates\system\roles.html:516 — `var opts = _roleOpts.replace('value="'+u.role+'"','value="'+u.role+'" selected');` — a plain string replace that matches nothing when the role is not in _roleOpts (roles.html:468-476). Server side: D:\vet\platform\blueprints\system\routes.py:871-887 never checks `role` against the roles table.

**Fix** — Validate in role_assign: reject a role that has no row in `roles`. In the template, when u.role has no matching option, prepend a disabled selected option showing the actual value.

*reproduced · edge cases*


### [MAJOR] Editing a role and saving with no permission boxes ticked wipes its permissions and says "Role updated successfully"

**Steps** — System → Roles → Custom Roles → Edit Role on any role → submit without ticking any permission (or POST /system/roles/<id>/edit with display_name only). Reproduced on role id 1 (super_admin): permissions_json became '[]'.

**Expected** — A role with zero permissions is either refused or warned about loudly, since it locks out everyone who holds it.

**Actual** — permissions_json is set to '[]' and the flash says "Role updated successfully." A role with '[]' is not the fall-open case — it is enforced as "allowed nothing", so every staff member holding that role is locked out of every module on their next request, with no clue what happened. Because the built-in roles are editable through the Custom Roles section (finding 1), this can be done to `reception` or `doctor`.

**Cause** — D:\vet\platform\blueprints\system\routes.py:832-847 — `permissions = f.getlist("permissions")` with no check; only display_name is validated as required.

**Fix** — Refuse an empty permission list, or require a typed confirmation the way backup_restore does. Same check in role_create (routes.py:810).

*reproduced · edge cases*


### [MAJOR] The Roles & Permissions screen shows a permission matrix that does not match what the system enforces — for all 11 built-in roles

**Steps** — Live demo, admin.
1. Open /system/roles. Read the permission chips on each built-in role row.
2. Download /system/export/all and open roles.csv (that is the table enforcement actually reads).
3. Compare. Every built-in role differs. Measured diff (shown-but-not-granted / granted-but-not-shown):
   nurse       : shows `reports`   / actually has pharmacy, inpatient, imaging, attendance
   pharmacist  : shows `procurement` / actually has patients, visits, attendance
   reception   : —                / actually has boarding, grooming, petshop, catalog, attendance
   doctor      : shows `whatsapp` / actually has catalog, imaging, inpatient, telemedicine, attendance
   branch_manager: shows ai, hr   / actually has imaging, inpatient, petshop, telemedicine
   hr          : shows `reports`  / actually has payroll
   clinic_owner: —                / actually has payroll, imaging, inpatient, petshop, telemedicine
   groomer     : —                / actually has attendance
   support_admin: shows `reports` / —

**Expected** — The Roles screen is the owner's answer to "who can open the pharmacy / see the ledger / read a medical record". It must render what is enforced.

**Actual** — The built-in rows are rendered from `_SYSTEM_ROLE_PERMS`, a Python literal in the route file used ONLY for display. Enforcement reads `roles.permissions_json`. The two have drifted apart on every role. Two live examples that matter: the screen tells the owner a nurse CANNOT enter the Pharmacy (she can, and can dispense) and that a pharmacist CANNOT open patient records or medical visits (he can).

**Cause** — blueprints/system/routes.py:740-752 `_SYSTEM_ROLE_PERMS`, passed to templates/system/roles.html:192-227; enforcement path is blueprints/auth/routes.py:208 `_role_permissions` reading `roles.permissions_json`.

**Fix** — Delete `_SYSTEM_ROLE_PERMS` and render every row, built-in included, from `db.list_roles()`. Failing test: `tests/test_role_consistency.py::test_roles_page_shows_the_permissions_that_are_enforced` — for each name in `_SYSTEM_ROLE_PERMS`, assert `set(_SYSTEM_ROLE_PERMS[name]) == set(db.get_role_by_name(name)['permissions'])`.

*reproduced · money & records*


### [MAJOR] System Monitor reports "Errors (24h): 0" and an empty log panel no matter how many 500s the app has thrown — it queries a column that does not exist

**Steps** — Local reproduction:
1. Write 40 genuine server errors: `log_backend(level='ERROR', module_name='finance', endpoint='/finance/boom', status_code=500, error_message='KABOOM n')` x40. `SELECT COUNT(*) FROM backend_logs` -> 40, all with `created_at` = now.
2. GET /system/monitor. Captured template context: `error_count_24h = 0`, `recent_logs = []`. The string "KABOOM" and "/finance/boom" appear nowhere on the page.
3. Direct proof of the cause:
   `SELECT COUNT(*) FROM backend_logs WHERE timestamp >= '2000-01-01'` -> OperationalError: no such column: timestamp
   `SELECT COUNT(*) FROM backend_logs WHERE created_at >= '2000-01-01'` -> 40
Matches the live demo, which shows a green "الأخطاء (24 ساعة) 0" card and an empty log area.

**Expected** — The system-health screen counts the errors in backend_logs and lists the 25 most recent.

**Actual** — Both queries name `backend_logs.timestamp`; the column is `created_at` (models/database.py:2288). Both raise, and both are swallowed by bare `except Exception: pass`, so the card renders a confident green zero. The documented fallback (`app_logs`) is dead too — grep shows no code anywhere writes to `app_logs`. The one screen an owner opens to ask "is my system healthy?" cannot report a single error.

**Cause** — blueprints/system/routes.py:105 (`ORDER BY timestamp DESC`) and :122 (`AND timestamp >= ?`); column is `created_at` per models/database.py:2288. Swallowed at :108 and :125.

**Fix** — Rename both to `created_at`, and let the exception surface (or log it) instead of `pass` so the next schema drift is visible. Failing test: `tests/test_system_routes.py::test_monitor_counts_recent_errors` — insert an ERROR row via log_backend, assert the rendered context has `error_count_24h == 1` and `len(recent_logs) == 1`.

*reproduced · money & records*


### [MAJOR] System Monitor shows "Database Size 0.0 MB" and a SQLite file path that does not exist on the PostgreSQL server

**Steps** — 1. Sign in at https://demo.aleefy.online as admin.
2. Open /system/monitor.
3. The Database Size card reads `0.0 MB` / `0.0 KB on disk`, and the Database panel reads: engine `PostgreSQL`, size `0.0 MB (0.0 KB)`, path `/srv/aleefy/data/platform.db`.
4. That path does not exist — the clinic's data is in PostgreSQL database `aleefy_demo` (confirmed on the host).

**Expected** — Either the real database size (`pg_database_size(current_database())`) or no size card at all, and no fictional file path.

**Actual** — `monitor()` does `os.path.getsize(current_app.config['DATABASE_PATH'])` inside `try/except: pass`, so on PostgreSQL it silently yields 0. The engine badge was correctly made PostgreSQL-aware (as /system/diagnostics was) but the size card and the path were not. Same shape as the previously found "dashboard card pointing at something that isn't on a Linux server": an owner monitoring storage growth is shown a permanent zero.

**Cause** — blueprints/system/routes.py:79-88 and :186-188 (`db_size_kb`, `db_size_mb`, `db_path`), rendered by templates/system/monitor.html.

**Fix** — Branch on `db.is_postgres()` the way diagnostics() at :564 already does: `SELECT pg_database_size(current_database())` for the size and `current_database()` for the identity. Failing test: `tests/test_postgres_full.py::test_monitor_reports_a_nonzero_database_size`.

*reproduced · money & records*


### [MAJOR] Backup health and the nightly-backup alert are computed from the wrong directory, so a healthy clinic can be told its backups stopped (and vice versa)

**Steps** — Consequence of finding 1, listed separately because it is the alerting path rather than the button.
1. Live demo /system/backup shows "آخر نسخة احتياطية ناجحة — 18 ساعة مضت — platform_backup_20260806_212817.dump" and "النسخ المحفوظة: 1", with a 30-day retention policy.
2. The clinic's real nightly backups for 2026-08-06 02:00 and 2026-08-07 02:00 exist and are perfect — in /srv/aleefy/data/backups/demo/ — and are not counted.
3. `bk.health()` -> `get_latest_backup()` -> `list_backups()` all read the process-global `_backup_dir` (the un-slugged root), so the age, the count, the green/red badge and `check_and_notify()`'s manager alert all describe a directory the nightly job never writes to.

**Expected** — "Last backup 13 hours ago, 3 archives kept" for a clinic whose 02:00 job ran at 02:00 today.

**Actual** — "Last backup 18 hours ago, 1 archive kept", describing a dump of a different database. In a deployment where the un-slugged directory happens to be empty, `check_and_notify()` fires "No backup has ever been taken on this server" to every manager, every day, while backups run perfectly — and the reverse is equally possible: one stale file in the root keeps the badge green for two days after the real nightly job dies.

**Cause** — models/backup.py:403 list_backups / :439 get_latest_backup / :764 health / :829 check_and_notify, all reading the module global `_backup_dir`; called from blueprints/system/routes.py:196 (monitor) and :447 (backup).

**Fix** — Same fix as finding 1 — resolve the tenant before calling into models.backup on the request path. Failing test: `tests/test_backup.py::test_health_sees_the_scheduler_s_archives`.

*reproduced · money & records*


### [MAJOR] support_admin can promote any user — including itself — to super_admin

**Steps** — Local reproduction:
1. Session with role=support_admin (the external support account; /system/roles is open to it per blueprints/system/routes.py:872).
2. POST /system/roles/assign {user_id: <any id, including its own>, role: 'super_admin'} with a valid CSRF token.
3. -> 200, flash "Role assigned successfully", `users.role` is now `super_admin`.

**Expected** — A support account cannot mint an account more privileged than itself, and cannot grant a role it does not hold.

**Actual** — `role_assign` takes `user_id` and `role` straight from the form with no check on either the target or the grant. `@role_required("super_admin", "clinic_owner", "support_admin")` gates who may reach the route but nothing gates what they may hand out. A support_admin who is meant to be able to fix a locked-out receptionist can instead give itself the keys to backups, restores and the whole audit trail.

**Cause** — blueprints/system/routes.py:871-887 role_assign -> models/database.py:4231 assign_user_role.

**Fix** — Refuse to assign a role the acting user does not itself hold (`super_admin` grantable only by `super_admin`), and refuse self-assignment. Failing test: `tests/test_auth_security.py::test_support_admin_cannot_grant_super_admin`.

*reproduced · money & records*


### [MAJOR] Assigning a role that does not exist succeeds silently and un-gates the user

**Steps** — Local reproduction:
1. POST /system/roles/assign {user_id: <real user>, role: 'wizard_of_oz'} -> 200, "Role assigned successfully."
2. `SELECT role FROM users WHERE id=?` -> 'wizard_of_oz'.
3. A session with role='recepton' (a one-character typo of 'reception') reaches /accounting/ with 200, where 'reception' gets 302.
Same route also accepts a `user_id` that matches no user: POST /system/roles/assign {user_id: 987654, role: 'nurse'} -> "Role assigned successfully", 0 rows updated, no error.

**Expected** — An unknown role is rejected; an unknown user id is reported as an error, not as success.

**Actual** — `role_assign` writes any string into `users.role`. An unknown role then hits the fall-open path in `_permission_denied` and the user ends up with MORE access than the role they were meant to get. And an assignment that updated nothing still reports success, so an owner who fixes someone's access, sees "Role assigned successfully" and hears the next day that they still cannot get in has no reason to suspect the screen.

**Cause** — blueprints/system/routes.py:871-887 role_assign; no existence check on either argument; models/database.py:4231 assign_user_role does a bare UPDATE and ignores rowcount.

**Fix** — Validate `role` against `db.list_roles()` and check `cur.rowcount` on the UPDATE, flashing an error when either fails. Same one-line guard covers finding 2. Failing test: `tests/test_role_consistency.py::test_assign_rejects_an_unknown_role_and_an_unknown_user`.

*reproduced · money & records*


### [MAJOR] System Monitor reports "0 Errors (24h)" and "No server logs yet" even when errors are recorded

**Steps** — Insert rows into backend_logs (level ERROR and CRITICAL, created_at = now) and load /system/monitor. Reproduced locally: with 3 rows present, 2 of them ERROR/CRITICAL, the page renders "🟢 0 Errors (24h)" and "📭 No server logs yet — appear after the first API requests.", and the error text "boom one" does not appear anywhere in the HTML.

**Expected** — The error counter and the Recent Server Logs panel show what is in backend_logs.

**Actual** — Both queries name a column `timestamp`; the backend_logs table has `created_at` and no `timestamp` (verified: SELECT timestamp FROM backend_logs → "no such column: timestamp"; SELECT created_at → OK). Both queries are wrapped in `except Exception: pass`, so the OperationalError is swallowed and the page renders zeros. The fallback path reads app_logs, which does have `timestamp` but is empty on a current install. Net effect: the one screen an owner opens to ask "is anything broken?" is hardcoded green.

**Cause** — blueprints/system/routes.py:105 (`ORDER BY timestamp DESC`) and :122 (`AND timestamp >= ?`) vs models/database.py:2287 (`created_at TEXT DEFAULT (datetime('now'))`).

**Fix** — Change both to `created_at`. Also narrow the two bare `except Exception: pass` blocks so a schema mismatch cannot present itself as "all clear" again.

*reproduced · happy path*


### [MAJOR] Roles screen shows the wrong permissions for every built-in role, and lists four real roles not at all

**Steps** — Open /system/roles and expand any built-in role. Compare against the enforced permissions. Computed directly: `from blueprints.system.routes import _SYSTEM_ROLE_PERMS` vs `models.database.DEFAULT_ROLE_PERMISSIONS`.

**Expected** — The permissions screen is where an owner answers "who can see the medical record / touch the money". It should show what is actually enforced.

**Actual** — The screen is drawn from a hardcoded dict that has drifted from the source of truth. Doctor is shown with "WhatsApp Messaging" (not granted) and without inpatient, telemedicine, imaging, catalog, attendance (all granted). Nurse is shown with "Reports" (not granted) and without pharmacy, inpatient, imaging, attendance (all granted). Pharmacist is shown with "Procurement" (not granted) and without patients, visits, attendance (granted). Branch Manager is shown with HR and AI (not granted). Reception is missing five granted modules. Separately, four roles that real staff hold — finance (fin.dalia), inventory_mgr (inv.tamer), boarding_staff (board.sameh) and auditor — have no built-in row at all, so the demo's finance user does not appear anywhere in the role listing. And the roles table's 14 rows are then re-listed under "Custom Roles (14)", so the live page renders 25 role rows for 14 roles, each real role appearing twice with two different permission lists.

**Cause** — blueprints/system/routes.py:740-752 _SYSTEM_ROLE_PERMS (stale copy); templates/system/roles.html:189-238 (hardcoded built-in rows plus a full re-listing of db.list_roles()).

**Fix** — Delete _SYSTEM_ROLE_PERMS and the hardcoded macro calls; render one row per row of db.list_roles(), marking a role built-in when its name is in db.DEFAULT_ROLE_PERMISSIONS. One list, one source.

*reproduced · happy path*


### [MAJOR] A custom role can never be granted anything in the System module — those four checkboxes do nothing

**Steps** — System → Roles → "+ New Custom Role", name head_nurse, tick System Admin, Backup & Restore, Audit Log, Platform Settings, Save. Assign it to a staff member on the Staff Access tab. Sign in as that person and open /system/monitor, /system/backup, /system/audit, /system/settings. Reproduced locally: all four return 302 → /.

**Expected** — Ticking "System Admin" and "Backup & Restore" on a role gives that role the System pages, otherwise the checkboxes should not be offered.

**Actual** — All 21 routes in the System blueprint are gated by @role_required with a hardcoded role list ("super_admin", "clinic_owner", "support_admin"), and role_required rejects anything not literally in that list regardless of stored permissions — a grant can only narrow, never widen. So an owner who creates "IT Support" with backup rights gets a role that cannot open the backup page. The same is true, more weakly, across the app: 96 routes use @role_required with hardcoded names against 3 that use @permission_required.

**Cause** — blueprints/auth/routes.py:176 (`if user_role != "super_admin" and user_role not in roles`), applied at blueprints/system/routes.py:77, 231, 322, 443, 459, 476, 489, 499, 516, 544, 554, 639, 712, 769, 791, 803, 826, 856, 872, 930.

**Fix** — Either migrate the system routes to @permission_required("system.x", …fallback roles) as the docstring at blueprints/auth/routes.py:281 already describes, or remove system/backup/audit/settings from the checkbox grid so the screen stops promising something it cannot deliver.

*reproduced · happy path*


### [MAJOR] Currency and Timezone on System Settings are write-only — every invoice still says EGP

**Steps** — System → Settings → Preferences → set Currency to SAR (or AED/USD) and Timezone to Asia/Riyadh → Save All Settings. Then open any invoice, the finance dashboard, or an accounting report.

**Expected** — "Used on invoices and financial reports" — the hint under the dropdown. A Gulf clinic sets its currency once and the system uses it.

**Actual** — Flash: "Settings saved successfully." The value is written to clinic.currency and clinic.timezone and nothing anywhere reads either one. `grep -rn "clinic.currency|clinic\['currency'\]|clinic.get('currency'"` over the whole tree matches exactly one file — templates/system/settings.html, the dropdown itself. Every amount is hardcoded, e.g. templates/finance/invoice_detail.html:153-163 renders Subtotal / Discount / Tax / TOTAL / Paid / Balance Due each with a literal " EGP". clinic.timezone has zero readers at all.

**Cause** — blueprints/system/routes.py:356-368 writes both columns; no consumer exists. templates/finance/invoice_detail.html:153-163 and ~40 other templates hardcode EGP.

**Fix** — Expose the clinic currency through the existing context processor in app.py:321 and have models/money.format_money append it, then replace the hardcoded " EGP" literals. If that is not on the roadmap, remove the two dropdowns rather than leave a control that lies about what it did.

*reproduced · happy path*


### [MAJOR] System Monitor's Database Size card is permanently 0.0 MB on PostgreSQL, and Log Files is permanently 0

**Steps** — Open https://demo.aleefy.online/system/monitor as admin. The headline card reads "🗄️ 0.0 MB — Database Size — 0.0 KB on disk", and the Database panel below it reads "PostgreSQL · Size 0.0 MB (0.0 KB) · Path /srv/aleefy/data/platform.db". Meanwhile `pg_size_pretty(pg_database_size('aleefy_demo'))` on the server = 21 MB. The Log Files card reads "0.0 MB · 0 files · 7d retention".

**Expected** — A monitoring page tells the truth about the size of the database it is monitoring and where the logs are.

**Actual** — monitor() computes size with os.path.getsize(DATABASE_PATH) — a SQLite file path that is meaningless (and absent) on a PostgreSQL deployment, so it silently returns 0 forever. The panel labels the engine "PostgreSQL" and prints a SQLite path in the same breath. The Log Files card derives its directory as dirname(DATABASE_PATH)/logs/backend = /srv/aleefy/data/logs/backend, which does not exist; the real directory is /srv/aleefy/app/logs/backend (models/logging_db.py:34, _BASE_DIR/logs/backend). Both cards are structurally incapable of showing a number.

**Cause** — blueprints/system/routes.py:84 (os.path.getsize on db_path) and :157 (log_dir from dirname(db_path)).

**Fix** — When db.is_postgres(), read `SELECT pg_database_size(current_database())` for the size and show the database name instead of a file path. Derive the log directory from models.logging_db._LOG_DIR_BACK rather than re-deriving it from the database path.

*reproduced · happy path*


### [MINOR] /system/audit with a very large page number returns a 500 on production

**Steps** — GET https://demo.aleefy.online/system/audit?page=99999999999999999999 as admin. Confirmed live: HTTP 500. Locally it raises OverflowError: Python int too large to convert to SQLite INTEGER.

**Expected** — Clamp to the last page, or a 400.

**Actual** — 500 error page. page=0, page=-3, page=abc and page=999999 are all handled correctly, so only the oversized-integer case is unguarded; a mistyped URL or a crawler will hit it.

**Cause** — D:\vet\platform\blueprints\system\routes.py:257-260 — `page = request.args.get("page", type=int) or 1` accepts an arbitrary-precision Python int; it is clamped below 1 but never above, then handed to the driver as an OFFSET parameter at routes.py:268-272.

**Fix** — One line after the existing clamp: `page = min(page, 10**6)` — or compute `pages` first and clamp to it, which also fixes the next finding.

*reproduced · edge cases*


### [MINOR] Audit log past the last page says "Showing 24951–2 of 2 entries" and renders an empty table

**Steps** — GET /system/audit?page=500 on a database with 2 audit rows.

**Expected** — "Showing 1–2 of 2" (clamped) or "No entries".

**Actual** — "Showing 24951–2 of 2 entries" above an empty table. The pager is hidden (pages == 1) so there is no way back except editing the URL or hitting Clear. On a real clinic's audit log the same thing happens when the row count shrinks after log retention runs while an admin has a deep page bookmarked — the screen looks like the audit trail was wiped.

**Cause** — D:\vet\platform\templates\system\audit_log.html:102 prints `(page-1)*page_size+1` unconditionally; `page` is never clamped to `pages` in D:\vet\platform\blueprints\system\routes.py:257-298.

**Fix** — Clamp after the COUNT: compute `pages` first, then `page = min(page, pages)`. Fixes both this and the 500 above.

*reproduced · edge cases*


### [MINOR] Audit log "Record ID" filter cannot match the Arabic-Indic digits its own Arabic placeholder tells you to type

**Steps** — System → Audit Log in Arabic. The Record ID field's placeholder reads "مثال: ١٠٤٢". Type ١٠٤٢ and click Filter.

**Expected** — The same result as typing 1042.

**Actual** — "No entries" (reproduced: entity_id=1042 → "Showing 1–1 of 1 entries"; entity_id=١٠٤٢ → "No entries"). The app's own placeholder demonstrates input that will never match, and an Arabic-keyboard user concludes the record has no audit history.

**Cause** — D:\vet\platform\blueprints\system\routes.py:243 — `f_eid = request.args.get("entity_id", "").strip()` is used as an exact match at routes.py:252, with no digit normalisation. The project already has the translator: D:\vet\platform\models\money.py:52 `_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", …)`.

**Fix** — `f_eid = f_eid.translate(money._DIGITS)`. Same for the date fields if a date is ever typed rather than picked.

*reproduced · edge cases*


### [MINOR] Creating a role with a name that already exists shows the raw SQL error

**Steps** — System → Roles → + New Custom Role, key `head_nurse`, create it, then create it again (or double-click Create Role, or press Back and resubmit).

**Expected** — "A role called head_nurse already exists."

**Actual** — "Error creating role: UNIQUE constraint failed: roles.name" — reproduced. Note the name is normalised server-side (lowercased, spaces → underscores), so "Head Nurse", "head nurse" and "HEAD_NURSE" all collide with head_nurse and all produce this message, which reads to an owner like a broken system rather than a duplicate.

**Cause** — D:\vet\platform\blueprints\system\routes.py:820-821 flashes str(e) from the driver.

**Fix** — Check for an existing name before the insert and flash a sentence; keep the exception handler as a fallback that says something generic.

*reproduced · edge cases*


### [MINOR] Role name validation is client-side only — the server stores 500-character names, Arabic keys and apostrophes

**Steps** — The create form has pattern="[a-z0-9_]+", so a browser blocks these. POST directly, or use a browser that ignores the pattern: name="X"*500, name="مدير العيادة", name="o'brien".

**Expected** — The server enforces the same rule the form advertises.

**Actual** — All three were stored (reproduced). A role key is compared byte-for-byte against users.role everywhere in the app, so a 500-character or right-to-left key is a permanent eyesore in every badge and dropdown and cannot be renamed — role_edit does not update `name` (the Role Key field in the edit modal is disabled), so the only way out is Delete, which triggers finding 2.

**Cause** — D:\vet\platform\blueprints\system\routes.py:806-813 checks only that name and display_name are non-empty after strip(); models/database.py:4204 lowercases and replaces spaces but validates nothing.

**Fix** — One regex in role_create: `if not re.fullmatch(r'[a-z0-9_]{2,32}', name): flash(...)`.

*reproduced · edge cases*


### [MINOR] Double-clicking "Back Up Now" produces two identical backups

**Steps** — System → Backup → click "Back Up Now" twice quickly.

**Expected** — One backup, or the second click ignored.

**Actual** — Two files, same second, same size: platform_backup_20260807_154615.db and platform_backup_20260807_154615_1.db (reproduced). No data is at risk — the collision suffix works correctly — but the backup list and the 30-day retention budget fill with duplicates, and on the live server each is a full pg_dump.

**Cause** — D:\vet\platform\blueprints\system\routes.py:458-472 — backup_run has no in-flight guard.

**Fix** — Disable the button on submit in templates/system/backup.html; that is enough for a one-person clinic. A file lock in models/backup.run_backup if the scheduler and a manual click can ever overlap.

*reproduced · edge cases*


### [MINOR] A mistyped date in the audit-log filter shows an empty log with no explanation

**Steps** — 1. Live demo, /system/audit?date_from=2026-08-07 -> 28 rows.
2. /system/audit?date_from=garbage (or a typo like `07-08-2026`) -> 200, zero rows, no message, no indication the filter was invalid.

**Expected** — "That date could not be read" — or the filter is ignored.

**Actual** — The value is concatenated straight into the comparison (`f_from + " 00:00:00"`) and compared lexically against a TEXT timestamp column, so anything sorting after '2026...' matches nothing. Someone checking who deleted an invoice sees an empty audit log and concludes nothing was recorded.

**Cause** — blueprints/system/routes.py:253-254.

**Fix** — Parse with `datetime.strptime(v, '%Y-%m-%d')`; on failure flash "Ignored an unreadable date" and drop that clause.

*reproduced · money & records*


### [MINOR] Deleting a role that does not exist reports "Role deleted."

**Steps** — POST /system/roles/999999/delete -> 200, flash "Role deleted." No such role ever existed.

**Expected** — 404, or "That role no longer exists."

**Actual** — `db.delete_role` runs `DELETE FROM roles WHERE id=?`, matches nothing, raises nothing, and the route flashes success unconditionally. Two admins working at once each see a confirmation for the same delete; whichever one is wrong never learns it.

**Cause** — blueprints/system/routes.py:855-868; models/database.py:4225 ignores rowcount.

**Fix** — Check `db.get_role(role_id)` first (the route already fetches it for the audit message — just act on a None) or check rowcount.

*reproduced · money & records*


### [MINOR] /healthz returns 503 HTML during a restore, contradicting its documented contract

**Steps** — 1. `bk.maintenance_on('probe')` (what a restore does).
2. GET /healthz -> 503 with an HTML error page, not the JSON body.
3. GET /auth/login -> 200 (correctly exempt).

**Expected** — app.py:525-529 states plainly that the health probe's HTTP status answers one question — can this instance serve traffic — and that only an unreachable database makes it false; backup state is reported in the body and must not fail the probe.

**Actual** — `_backup_maintenance_gate` exempts only /static/ and /auth/, so it intercepts /healthz too. On the demo host the app runs under systemd with `Restart=always` behind nginx; a 15-minute restore window makes the instance look dead to anything polling /healthz, and the upgrade path reads that endpoint.

**Cause** — blueprints/system/routes.py:53-67.

**Fix** — Add "/healthz" to the exempt prefixes on line 53.

*reproduced · money & records*


### [MINOR] Default Theme and Default Language on System Settings never take effect

**Steps** — System → Settings → Appearance → Default Language = Arabic, Default Theme = Logo → Save All Settings. Sign out, sign in as any other staff member. Reproduced locally: settings.default_language is stored as 'ar', but the fresh session's session['lang'] is 'en' and the page renders <html lang="en" dir="ltr">.

**Expected** — The hint under the control says "Applied to new sessions by default."

**Actual** — Flash "Settings saved successfully." The rows land in the settings table and nothing reads them. Language resolution is `user.get('language') or session.get('lang') or os.environ.get('PLATFORM_DEFAULT_LANG','en')` — the clinic-wide setting is not consulted. Theme resolution is `user.get('theme_preference') or session.get('theme') or 'medical'` — same. Combined with the Currency and Timezone finding, all four dropdowns in the bottom two cards of the System Settings page are dead, and all four report success.

**Cause** — blueprints/system/routes.py:372-382 writes the keys; app.py:322-329 resolves theme and language without reading them.

**Fix** — In app.py's context processor, fall back to db.get_setting('default_language') / ('default_theme') before the env default. Two lines.

*reproduced · happy path*


### [MINOR] Diagnostics permanently shows a Warning and a dead "Test Connectivity" card for a legacy app that is switched off

**Steps** — Open https://demo.aleefy.online/system/diagnostics as admin.

**Expected** — A health page for a deployment with LEGACY_APP_ENABLED=0 shows all-clear.

**Actual** — The page headline reads "⚠️ 1 Warning — the platform is working but some items need attention", and check 6 is "Legacy App Directory — LEGACY_APP_DIR not configured". Below the checks sits a "🔗 Live Legacy App Connectivity" card showing "http://localhost:5000" and a "Test Connectivity" button whose JS fetches localhost:5000 from the viewer's own browser — it can only ever say "❌ Legacy app unreachable". monitor.html already guards its equivalent block with `{% if legacy_enabled %}` (line 384); diagnostics.html has no such guard. This is the same dead-card pattern that survived on the dashboard for months.

**Cause** — blueprints/system/routes.py:613-619 (unconditional legacy check) and templates/system/diagnostics.html:133-158 (no legacy_enabled guard, unlike templates/system/monitor.html:384).

**Fix** — Pass legacy_enabled into the diagnostics template and wrap both the check and the card in `{% if legacy_enabled %}`, matching monitor.html.

*reproduced · happy path*


### [MINOR] Assigning a role to a user id that does not exist reports success

**Steps** — POST /system/roles/assign with user_id=999999 and role=nurse.

**Expected** — "No such user" — or at least not a success message.

**Actual** — Flash: "Role assigned successfully." and an audit row is written saying "Assigned role 'nurse' to user id=999999". db.assign_user_role runs an UPDATE that matches zero rows and the rowcount is never checked. Reachable in practice when two admins have the Staff Access tab open and one deactivates/removes a user first — the other gets a green confirmation for a change that did not happen, and the audit log records a change that never occurred.

**Cause** — models/database.py:4231 assign_user_role (rowcount ignored); blueprints/system/routes.py:880-885.

**Fix** — Return cur.rowcount from assign_user_role and flash a warning when it is 0.

*reproduced · happy path*


### [MINOR] Resolving a sync conflict that no longer exists reports success

**Steps** — POST /system/sync/conflicts/does-not-exist/resolve with keep=server.

**Expected** — "That conflict is already resolved" or an error.

**Actual** — HTTP 200, flash "Conflict resolved. Kept: server version." resolve_conflict() raises nothing for an unknown id, so the route's try/except sees success. Two managers working the Sync dashboard at once will both be told they resolved the same conflict, and the second one's chosen side was never applied.

**Cause** — blueprints/system/routes.py:713-733; models/sync.resolve_conflict.

**Fix** — Have resolve_conflict report whether it matched a row, and flash a warning when it did not.

*reproduced · happy path*


### [MINOR] Audit log renders nonsense when the page number is past the end

**Steps** — Open /system/audit?page=99999 on the live demo (305 entries, 7 pages).

**Expected** — Clamp to the last page, or an empty state with a way back.

**Actual** — The header reads "4999901–305 من 305" (i.e. "showing 4999901–305 of 305") over an empty table. page is clamped at the bottom (page<1 → 1) but never at the top against `pages`. Cosmetic, but it is the screen an auditor uses and a bookmarked or hand-edited URL lands there.

**Cause** — blueprints/system/routes.py:257-260 (only the lower bound is clamped); templates/system/audit_log.html:100-103.

**Fix** — After computing `pages`, add `page = min(page, pages)` and recompute offset.

*reproduced · happy path*


### [MINOR] Maintenance mode answers API clients with an HTML page instead of JSON

**Steps** — Turn on maintenance (start a restore) and request /api/v1/health. Reproduced locally with bk.maintenance_on().

**Expected** — A JSON 503 for a JSON endpoint — the offline sync client is the only consumer.

**Actual** — 503 with Content-Type: text/html and the rendered error.html page. Every /api/v1/* route behaves the same during a restore. _permission_denied elsewhere in the codebase already special-cases `request.path.startswith('/api/')`; this gate does not. Low impact today because no devices are registered, but it is the path the whole offline-sync feature depends on.

**Cause** — blueprints/system/routes.py:64-67 (_backup_maintenance_gate always renders error.html).

**Fix** — Mirror the check at blueprints/auth/routes.py:119 — return jsonify(...) with 503 when the path starts with /api/ or the client accepts JSON.

*reproduced · happy path*


### [INFO] /system/settings writes every clinic column from the form on every save, so any caller that omits a field blanks it

**Steps** — POST /system/settings with only _csrf_token, after a full save.

**Expected** — n/a — informational.

**Actual** — name, phone, email, address, website, license_number, tax_number, tagline, doctor_name and the two Instapay fields are all set to '' and the flash says "Settings saved successfully." (reproduced). This is NOT reachable from the shipped page — templates/system/settings.html is a single form containing all 15 fields — so there is no bug to fix today. It is a landmine: the day someone adds a second, smaller form on this page, or a mobile view that omits a card, saving it silently wipes the clinic's licence and tax numbers with a success message. Currency and timezone are safe because the route supplies defaults ('EGP', 'Africa/Cairo') when the key is absent — which is itself asymmetric.

**Cause** — D:\vet\platform\blueprints\system\routes.py:355-368 — one UPDATE of all columns from f.get(x, "").

**Fix** — Build the SET clause from the keys actually present in request.form (models/database.py:2846 already has that pattern). No urgency.

*reproduced · edge cases*


### [INFO] The full data export ships the audit log because the skip list has the table name wrong

**Steps** — 1. /system/export/all on the live demo -> 84 CSVs, one of them audit_log.csv with 265-270 rows.
2. `_EXPORT_SKIP` lists `audit_logs` (plural, the unused v2 table) but not `audit_log`, which is the table every route in this blueprint actually reads. It also lists `petsy_usage` and `rate_hits`, neither of which exists.

**Expected** — Whatever the skip list intends. The stated intent (blueprints/system/routes.py:904-906) is "the clinic's records, not our logs, and small enough to email".

**Actual** — The audit trail is exported. Arguably a feature — but audit_log is the fastest-growing table in the schema, so on a clinic that has been running a year this is the thing that makes the "one file you can email" stop being emailable. Flagging so the owner decides deliberately rather than by typo. Everything else about the export checked out: 84 tables, and every row count in the ZIP matched the database (owners 60, pets 83, visits 390, invoices 390, invoice_lines 1144, payments 329, prescriptions 348, dispensing_log 532, vaccinations 119), with a UTF-8 BOM so Arabic names open correctly in Excel.

**Cause** — blueprints/system/routes.py:907-911.

**Fix** — Decide and spell it out: either add `audit_log` to the skip set, or drop the dead `audit_logs`/`petsy_usage`/`rate_hits` entries and keep exporting it on purpose.

*reproduced · money & records*


### [INFO] The full data export includes the audit log, which the skip list intended to exclude

**Steps** — GET /system/export/all on the live demo and list the zip: audit_log.csv is present with 314 rows.

**Expected** — Per the comment at blueprints/system/routes.py:904-911, the export is "the clinic's data, not our logs".

**Actual** — _EXPORT_SKIP lists "audit_logs" (plural). The live table is `audit_log` (singular) — `audit_logs` is a second, unused table. So the intended exclusion never matches. Harmless in itself, and arguably the audit log is the clinic's data too, but the skip list does not do what it says and will keep growing the export as the table grows without bound.

**Cause** — blueprints/system/routes.py:908 ("audit_logs" vs the real table name `audit_log`, models/database.py:1184).

**Fix** — Decide which is intended and make the name match. If the audit log should ship, drop it from the list so the comment stops disagreeing with the code.

*reproduced · happy path*


## Ai Assistant  (23)

### [BLOCKER] AI Insights on the home dashboard reports "no items requiring reordering" while four items sit at zero stock

**Steps** — LIVE, right now: log in to https://demo.aleefy.online as admin / Aleefy@Demo2026. The home screen (launcher) has an "AI Insights" card (#ai-insights-text, templates/launcher.html:700) that POSTs /ai/insights. It currently returns: {"icon":"✅","text":"Inventory levels are stable with no items currently requiring immediate reordering.","type":"success"}. Now open https://demo.aleefy.online/inventory/ — the "Low Stock Alerts" panel lists FOUR items at 0 on hand: CBC Reagent Kit (0 kit, reorder 4.0), Meloxicam Oral Suspension (0 bottle, reorder 8.0), Scalpel Blade #10 (0 unit, reorder 50.0), Sterile Gauze Pack (0 pack, reorder 40.0).

Minimal local reproduction (SQLite test app, seeds one item): insert an item with reorder_level=8, then db.add_stock_batch(iid, 1, 'B1', '2027-01-01', 40, 10, 'x') followed by db.deduct_stock(iid, 40, 'dispensing', None, 'x'). On-hand SUM(batches.quantity) = 0.0. db.get_low_stock_items() returns the item. POST /ai/insights, inspect the snapshot handed to the model.

**Expected** — "Inventory items at or below reorder level: 4" (or at minimum, the same number the inventory dashboard shows), and an amber/red insight naming the short items.

**Actual** — "Inventory items at or below reorder level: 0", and a green success card telling the owner stock is fine. In the local reproduction: insights low-stock count = 0, correct low-stock count = 1, with SUM(stock_movements.quantity) = 80.0 (rows: [('in', 40.0), ('out', 40.0)]) versus true on-hand 0.0. The failure is structural, not a rounding error: the more an item turns over, the further the number climbs above reorder_level, so a fast-moving medication can never be flagged.

**Cause** — blueprints/ai_assistant/routes.py:530-534 — the low_stock subquery computes on-hand as `(SELECT COALESCE(SUM(sm.quantity),0) FROM stock_movements sm WHERE sm.item_id = i.id)`. stock_movements is an append-only ledger where outgoing rows are stored with a POSITIVE quantity and the direction lives in movement_type — see models/database.py:3374, deduct_stock() inserting ('out', use) with `use` positive. So the subquery sums receipts AND dispensings as additions. Every other place in the platform computes on-hand as SUM(batches.quantity): models/database.py:3295 (list_items, which backs get_low_stock_items and the inventory dashboard) and :3315 (get_item).

**Fix** — Use the same expression the rest of the platform uses: replace the stock_movements subquery with `COALESCE((SELECT SUM(b.quantity) FROM batches b WHERE b.item_id = i.id), 0) <= i.reorder_level`. Better still, call models.database.get_low_stock_items() and take len() — one source of truth for "what is short". Failing test to add: seed one item, receive 40, dispense 40, assert the /ai/insights snapshot line reads "Inventory items at or below reorder level: 1".

*reproduced · edge cases*


### [MAJOR] "Revenue collected today" on the dashboard does not count money collected today

**Steps** — Local (SQLite test app): create an owner; insert an invoice issued 40 days ago, status 'Paid', total 1000, paid_amount 1000, due_amount 0; insert a payments row against it with amount=1000 and received_at = today. Then POST /ai/insights as clinic_owner and read the snapshot line handed to the model.

**Expected** — "Revenue collected today: 1,000 EGP" — the clinic took 1000 EGP at the counter today.

**Actual** — "Revenue collected today: 0 EGP". SELECT SUM(amount) FROM payments WHERE SUBSTR(received_at,1,10)=today returns 1000.0. Symmetrically, an invoice issued today that is later marked Paid retroactively appears in *today's* revenue even though the cash arrived on another day. On a clinic with 64 open invoices (the demo's own figure), chasing receivables is precisely the money that never shows up on the owner's daily card.

**Cause** — blueprints/ai_assistant/routes.py:528 — `SELECT COALESCE(SUM(paid_amount),0) FROM invoices WHERE SUBSTRING(issue_date::text,1,10)=? AND status IN ('Paid','Partial')`. It filters on invoices.issue_date (when the bill was written) and sums a running balance column, rather than summing payments.amount over payments.received_at (when the money arrived). The payments table exists and carries received_at — models/database.py:1698-1711.

**Fix** — `SELECT COALESCE(SUM(amount),0) FROM payments WHERE SUBSTRING(received_at::text,1,10)=?`. If the card is meant to mean "billed today", relabel it — but the snapshot text says "Revenue collected today", and the AI reasons from that wording.

*reproduced · edge cases*


### [MAJOR] The AI chat "rate limit" counts failed logins, not chat — so it never throttles the AI, and it 429s the whole clinic when one person mistypes a password

**Steps** — Local (Flask test client, logged in as clinic_owner):
1. POST /ai/chat 30 times in a row with {"message":"q0"}...{"message":"q29"} from X-Forwarded-For: 203.0.113.99. Count the 429s.
2. Now call models.security.record_failed_login('203.0.113.99', 'nosuchuser') six times — i.e. simulate one staff member fat-fingering their password from the clinic's shared public IP.
3. POST /ai/chat once more from the same IP.

**Expected** — Step 1: some form of throttle kicks in, because the code comment at routes.py:432 says "Rate limit authenticated chat to prevent token abuse" and every one of those requests spends real model tokens. Step 3: unrelated login failures have nothing to do with AI usage and must not block a signed-in user's assistant.

**Actual** — Step 1: `30 CHAT POSTS -> [200], 429s: 0`. There is no AI rate limit at all — 30 uncapped model calls, and nothing stops 3,000. Step 3: `CHAT AFTER 6 FAILED LOGINS -> 429 {"error": "Too many requests. Please wait before sending another message."}` for 900 seconds. Every signed-in user behind that IP is affected, because the lock is keyed on the IP and a clinic NATs all its staff behind one.

**Cause** — blueprints/ai_assistant/routes.py:435-438 calls `_sec.is_rate_limited(ip)`, which (models/security.py:193-221) reads the `login_attempts` table. Only record_failed_login() ever writes rows there. This is the identical mistake already found and fixed elsewhere in the same file — models/security.py:86-94 documents it verbatim: "The public API used to call is_rate_limited(ip), which counts rows that ONLY record_failed_login writes — so a bot hammering /api/public/book incremented nothing and the check it was guarded by could never fire. A limiter has to count the traffic it limits." The general-purpose throttle built for that fix (the `rate_hits` table, models/security.py:95-110) exists and is not used here.

**Fix** — Use the general throttle the module already provides — record a hit into the rate_hits bucket per user_id (not per IP; staff share an IP) on every /ai/chat POST and check that bucket, instead of calling is_rate_limited(). Two failing tests to add: "N chat posts past the limit returns 429" and "failed logins do not throttle chat".

*reproduced · edge cases*


### [MAJOR] /ai/health-alerts silently drops every Stock and Finance alert because it queries a table that does not exist

**Steps** — LIVE: log in to https://demo.aleefy.online as admin and GET https://demo.aleefy.online/ai/health-alerts. Compare with https://demo.aleefy.online/finance/invoices?status=Unpaid (64 unpaid invoices, oldest issued 2026-02-08 — six months overdue) and https://demo.aleefy.online/inventory/ (4 items at zero stock).

Local reproduction: seed one pet with an overdue vaccination AND an unpaid invoice issued 2025-01-01, then GET /ai/health-alerts.

**Expected** — Alerts in all three categories the route builds: Vaccine, Stock, and Finance — the route explicitly constructs "📦 Stock" and "🧾 Finance" entries.

**Actual** — Live: `{"alerts":[ 5 x category "Vaccine" ],"count":5}` — zero Stock, zero Finance, on a clinic with 64 unpaid invoices and 4 zero-stock items. Local: `{"alerts":[{"category":"Vaccine",...}],"count":1}` — the seeded seven-month-overdue invoice is absent. HTTP 200 with a confident, complete-looking list. The endpoint is published in docs/gen_tech.js:239 and docs/security/access-control-matrix.md:75 as part of the API surface, so an integrator gets a truncated action list with no error.

**Cause** — blueprints/ai_assistant/routes.py:743 — `FROM inventory_items`. That table does not exist; the stock catalogue is `items` (models/database.py:1487). Confirmed locally: `OperationalError: no such table: inventory_items`. The same mistake was already found and fixed in blueprints/reports/builder_routes.py:120, whose comment reads "There is no `inventory_items` table — the stock catalogue is `items`". Here the OperationalError is caught by the bare `except: pass` at routes.py:762, which wraps ALL THREE query blocks in one try — so the failure of the second block also abandons the third (the >30-day unpaid invoices), which is why the money alerts vanish too.

**Fix** — Two changes, both needed. (1) Point the low-stock query at `items` with the same on-hand expression the rest of the platform uses (SUM(batches.quantity)) — or just call db.get_low_stock_items(). (2) Split the one try/except into three, or drop it entirely, so a failure in one section cannot silently delete the other two. Note: no template currently fetches this endpoint, so nothing renders it today — but it is documented API and returns 200, which is worse than erroring.

*reproduced · edge cases*


### [MAJOR] Photo analysis prints the AI provider's raw error, naming another vendor and an internal host, straight into the vet's chat panel

**Steps** — Open a visit, click the photo-analyze control (templates/visits/visit_detail.html:1066), upload any image, on a clinic where the AI backend is unreachable or returns any error (bad key, quota, timeout). Local reproduction: monkeypatch ai._client() to raise RuntimeError("Missing credentials. Please pass an `api_key`... host=internal-proxy.example:3001"), POST /ai/analyze-photo {"image_b64":"AAAA"}. Second local case, no stubbing at all, just an unset AI_API_KEY with nothing on localhost:3001.

**Expected** — The same message the rest of this blueprint gives for an unusable AI: "🤖 AI is not enabled on this installation" / "The AI assistant is temporarily unavailable." The module already made exactly this fix — routes.py:174-183 documents removing the provider text because it "names another vendor, blames the reader, and tells an attacker what we run. Log it, do not print it."

**Actual** — The vet's AI panel shows: "⚠️ Photo analysis error: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable." Verbatim, reproduced locally on both paths, HTTP 500. With a network failure it reads "Photo analysis error: Connection error."

**Cause** — analyze_photo() bypasses call_ai() entirely — it builds its own client at routes.py:830 and ends with `return jsonify({"error": str(e)}), 500` at routes.py:842, so the sanitisation in call_ai's except block never applies. The frontend renders it unfiltered: templates/visits/visit_detail.html:1080, `if (d.error) aiAddMsg('assistant', '⚠️ Photo analysis error: ' + d.error);`. Compounding it, the route's only precondition is `_OPENAI_AVAILABLE` (routes.py:782, "is the openai package importable") and never calls ai_configured() — the very distinction routes.py:90-108 was written to draw. So on a clinic with no AI the button attempts a real outbound call every time and always ends in that message.

**Fix** — Add `if not ai_configured(): return jsonify({"error": "AI is not enabled on this installation."}), 503` at the top, and in the except: `_logger.warning("analyze_photo failed: %s", e)` then return the same two-language canned text call_ai returns. The str(e) leak repeats at routes.py:609 (pet_summary) and routes.py:875 (discharge_instructions) — fix all three, it is one shared shape.

*reproduced · edge cases*


### [MAJOR] On a SQLite-backed install, /ai/pet-summary is a hard 500 for any pet that has ever had a visit, and the doctor's patient-context panel shows a Python error

**Steps** — Run the app against SQLite (the documented fallback — app.py:100 logs "POSTGRES_DSN not set - falling back to SQLite"). Seed an owner, a pet, one visit and one diagnosis. As clinic_owner or doctor: POST /ai/pet-summary/<pet_id>. Then GET /ai/context/visit/<visit_id>.

**Expected** — 200 with a narrative summary; 200 with a populated patient-context block.

**Actual** — POST /ai/pet-summary/<id> raises `AttributeError: 'sqlite3.Row' object has no attribute 'get'` — an unhandled 500, because the prompt is assembled AFTER the `finally: conn.close()` and outside the try. GET /ai/context/visit/<id> returns 200 with `{"context": "[Patient context unavailable: 'sqlite3.Row' object has no attribute 'get']", "visit_id": 1}` — the doctor's AI patient-context panel displays a Python error message where the patient's allergies, medications and vitals should be. Reproduced on a freshly seeded SQLite test app. Note this is why 1,781 SQLite tests pass without catching it: no existing test posts pet-summary for a pet that actually has visits.

**Cause** — The routes call dict-style `.get()` on raw DB rows. blueprints/ai_assistant/routes.py:618 `{v.get('chief_complaint','')}` and :620 `d.get('severity')` (pet_summary); :305 `d.get('severity')` and :312 `r.get('dosage')` (_build_patient_context — that one IS inside a try, hence the error text rather than a 500); :882 `r.get('dosage','')` and :888 `treatment.get('followup_unit','days')` (discharge_instructions). models/database.py:1092 sets `conn.row_factory = sqlite3.Row`, which supports `row['x']` but has no `.get`. PostgreSQL escapes it only by accident: psycopg2's DictRow does define .get, so a PG-backed clinic (including the live demo) is unaffected.

**Fix** — The other reads in the same file already do it right — `visit = dict(visit)` at routes.py:224 and `pet = dict(pet)` at routes.py:586. Do the same for the fetchall() results: `visits = [dict(r) for r in ...]`, likewise diags, rxs, vax, and `treatment = dict(treatment) if treatment else None`. Failing test to add: test_pet_summary_for_a_pet_with_visits — seed pet + 1 visit + 1 diagnosis, assert POST /ai/pet-summary/<id> returns 200.

*reproduced · edge cases*


### [MAJOR] Dashboard "AI Insights" card is permanently blank and holds a worker for 30s on every load

**Steps** — Log into https://demo.aleefy.online as admin/Aleefy@Demo2026 and open the dashboard (/). Watch the "AI Insights" card in the right-hand Clinic Health Panel. Then reproduce the mismatch directly: curl -X POST https://demo.aleefy.online/ai/insights with the page's csrf-token.

**Expected** — The card shows the four insights the endpoint just generated.

**Actual** — The card shows the fallback string "AI ready for queries." every time, forever. The route returns {"generated_at":"2026-08-07","insights":[{...}x4]} but launcher.html line 707 reads `d.insight` (singular), which is always undefined. The deployed HTML on the demo contains the string `d.insight ||`, so this is live, not just local. Worse, the discarded call is not cheap: I timed the live endpoint twice at 31.0s and 29.6s. gunicorn runs --workers 3 --threads 2, so six staff opening the dashboard at the same time block every request slot for half a minute on a result nobody sees. The fetch fires unconditionally on DOMContentLoaded for every role holding the "ai" grant (super_admin, clinic_owner, doctor).

**Cause** — templates/launcher.html:707 reads `d.insight`; blueprints/ai_assistant/routes.py:569 returns key `insights`. Wiring at templates/launcher.html:808.

**Fix** — Read `d.insights` and render the array (it already carries icon/text/type). Separately, do not fire a 30-second synchronous AI call from the most-loaded page on every render — cache the result per clinic per day, or render the raw snapshot numbers server-side and load the AI commentary lazily behind a button.

*reproduced · money & records*


### [MAJOR] "Inventory items at or below reorder level" is always 0 — the manager gets a green all-clear on empty shelves

**Steps** — POST /ai/insights on the live demo as admin. Read the returned insight text. Then compare against the real stock: SELECT name, reorder_level, (SELECT SUM(quantity) FROM batches b WHERE b.item_id=i.id) FROM items i WHERE is_active=1 AND reorder_level>0.

**Expected** — 4 of the 20 active items are at or below reorder level (Meloxicam Oral Suspension 3.2 vs reorder 8; Sterile Gauze Pack 16 vs 40; Scalpel Blade #10 20 vs 50; CBC Reagent Kit 1.6 vs 4).

**Actual** — The snapshot says "Inventory items at or below reorder level: 0" and the AI answered the manager: "Inventory levels are stable with no items currently at or below reorder levels." (verbatim from the live 2026-08-07 response). The query sums stock_movements.quantity, but that column is stored POSITIVE for every movement_type — 'in', 'out' and 'Dispensed' alike (models/database.py:3374 writes 'out' with a positive `use`; blueprints/pharmacy/routes.py:227 writes 'Dispensed' with a positive qty). So received-100 + dispensed-100 computes as 200 on hand instead of 0. Once an item has ever been received above its reorder level it can never be flagged again. Reproduced locally: item with reorder_level 10, one 'in' 100 and one 'out' 100, batches on hand 0, SUM(stock_movements)=200, snapshot reports 0 low-stock items.

**Cause** — blueprints/ai_assistant/routes.py:530-534

**Fix** — On-hand lives in `batches.quantity` — that is what deduct_stock() maintains and what get_low_stock_items() already uses. Replace the stock_movements subquery with `(SELECT COALESCE(SUM(b.quantity),0) FROM batches b WHERE b.item_id=i.id)`. If stock_movements must be the source, it needs a signed sum: SUM(CASE WHEN lower(movement_type) IN ('out','dispensed','expired','damaged') THEN -quantity ELSE quantity END).

*reproduced · money & records*


### [MAJOR] Receivables understated by 32% — "Unpaid invoices" ignores every Partial invoice

**Steps** — POST /ai/insights on the live demo. Compare its unpaid figure to: SELECT COUNT(*), SUM(due_amount) FROM invoices WHERE status IN ('Unpaid','Partial').

**Expected** — 120 invoices carrying 122,312 EGP still owed (64 Unpaid + 56 Partial).

**Actual** — The AI told the manager, verbatim on the live demo: "Address the 64 unpaid invoices totaling 82,986 EGP to improve cash flow immediately." 56 partially-paid invoices carrying 39,326 EGP of outstanding balance are invisible. A Partial invoice by definition still has money owed on it — its due_amount is non-zero — but the filter is status='Unpaid' only. Reproduced locally too: fixture with one Unpaid 3,000 and one Partial owing 6,000 reported "Unpaid invoices: 1 totalling 3,000 EGP".

**Cause** — blueprints/ai_assistant/routes.py:528-529

**Fix** — status IN ('Unpaid','Partial') in both the count and the SUM. The same filter is wrong for the same reason in health_alerts' old_unpaid query (routes.py:757-763).

*reproduced · money & records*


### [MAJOR] "Revenue collected today" is not revenue collected today — it misses every payment against an older invoice

**Steps** — Locally: create invoice A issued today, paid 1,000 today; invoice B issued 60 days ago, paid 5,000 in full today; write matching rows in `payments`. POST /ai/insights and read the snapshot handed to the model.

**Expected** — Revenue collected today: 6,000 EGP (that is what the payments ledger holds for today).

**Actual** — "Revenue collected today: 1,000 EGP". The query is SUM(paid_amount) over invoices whose ISSUE_DATE is today — so money taken today against any invoice raised on an earlier day is not counted, and it never will be, because by the time it is paid the issue_date no longer matches. On the live demo the snapshot reported 0 while the payments table holds 120 EGP received today. The number is neither cash-basis nor accrual; for a clinic where most balances are settled after the visit it systematically under-reports the day's takings.

**Cause** — blueprints/ai_assistant/routes.py:527

**Fix** — The `payments` table is the ledger (models/database.py:1698 comment says so explicitly). Use SELECT COALESCE(SUM(amount),0) FROM payments WHERE SUBSTRING(received_at::text,1,10)=?.

*reproduced · money & records*


### [MAJOR] Overdue-vaccination count and reminder list include pets that have already been re-vaccinated

**Steps** — GET https://demo.aleefy.online/ai/health-alerts as admin and read the vaccine alerts. For each pet named, look up its latest dose of that vaccine: SELECT MAX(administered_at) FROM vaccinations WHERE pet_id=? AND vaccine_name=?.

**Expected** — Only pets whose MOST RECENT dose of a given vaccine is now past due should appear. On the demo that is 10 pet/vaccine pairs.

**Actual** — The route counts every historical vaccination row whose next_due_at has passed, regardless of whether a newer dose superseded it — 17 on the demo, and /ai/insights told the manager "Contact the 17 patients with overdue vaccinations". Named live examples visible right now: Simba is listed as "FVRCP Feline Vaccine overdue since 2026-07-04" but Simba's latest FVRCP dose was given 2026-06-28, six days BEFORE the alert date. Molly is listed as "DHPP Combo Vaccine overdue since 2026-07-05" with a latest DHPP dose of 2026-06-20, and Molly appears TWICE in the overdue set (two stale rows). Daisy's latest FVRCP was 2026-06-11 and she is also flagged. Reception phones an owner who was in the clinic last month; the count only grows over time because old rows never stop being overdue.

**Cause** — blueprints/ai_assistant/routes.py:535 (insights overdue_vax) and routes.py:725-734 (health_alerts overdue)

**Fix** — Reduce to the latest dose per (pet_id, vaccine_name) before testing next_due_at — e.g. SELECT DISTINCT ON (pet_id, vaccine_name) ... ORDER BY pet_id, vaccine_name, administered_at DESC, then filter next_due_at < today. On the demo this takes 17 down to 10 and drops the duplicate Molly row.

*reproduced · money & records*


### [MAJOR] The AI chat carries the previous patient's exchange into the next patient's question, with no marker that the patient changed

**Steps** — As a doctor, POST /ai/chat {"message":"Bruno is 40 kg, what meloxicam dose?","visit_id":<Bruno's visit>}. Then POST /ai/chat {"message":"and for this one?","visit_id":<Tiny's visit, a 2 kg dog>}. Inspect the message list handed to the model.

**Expected** — The model's transcript for the second question either contains only the current patient, or explicitly marks that the patient changed.

**Actual** — The second call sends: [{"role":"user","content":"Bruno is 40 kg, what meloxicam dose?"},{"role":"assistant",...},{"role":"user","content":"and for this one?"}], while the system prompt separately states "Weight: 2.0 kg" for Tiny. Nothing in the transcript tells the model the patient switched. The system prompt for the doctor role instructs it to do "dosage calculations (mg/kg)". A 40 kg weight and a 2 kg weight are both in context with no boundary — a 20x spread on an NSAID. _build_messages_for_api replays the last 20 exchanges keyed on user_id alone; it never sees visit_id.

**Cause** — blueprints/ai_assistant/routes.py:352-362 and routes.py:460-461

**Fix** — Store visit_id on ai_conversations and either scope _build_messages_for_api to the current visit, or insert an explicit system turn whenever the visit_id changes between consecutive rows ("--- patient changed: now discussing Tiny, 2.0 kg ---"). The second option keeps the conversational flow and is a few lines.

*reproduced · money & records*


### [MINOR] /ai/context/visit/<id> returns 200 and an empty context for a visit that does not exist

**Steps** — As a doctor or clinic_owner: GET /ai/context/visit/999999, /ai/context/visit/0, /ai/context/visit/2147483647.

**Expected** — 404 with {"error": "Visit not found"} — the sibling routes pet_summary (routes.py:583) and discharge_instructions (routes.py:857) both do exactly that, and both were verified to return proper 404 JSON for id 999999.

**Actual** — 200 with {"context": "", "visit_id": 999999}. The visit panel renders an empty patient-context box, which reads to a vet as "this patient has no recorded history" rather than "you are looking at the wrong record". Same for id 0 and 2147483647.

**Cause** — blueprints/ai_assistant/routes.py:246 — _build_patient_context() returns "" when the visit row is missing, and context_visit (routes.py:405) jsonifies that empty string with a 200 without distinguishing "no such visit" from "visit with nothing in it".

**Fix** — Have context_visit return 404 when _build_patient_context returns "" for a visit id that has no row — cheapest version is a `SELECT 1 FROM visits WHERE id=?` guard before the call, which the branch-IDOR check at routes.py:394 already performs anyway for doctors.

*reproduced · edge cases*


### [MINOR] An oversized pet id in the URL 500s and prints the raw database error to the browser

**Steps** — As clinic_owner: POST /ai/pet-summary/99999999999999999999

**Expected** — 404 {"error": "Pet not found"} — which is what /ai/pet-summary/999999 and /ai/pet-summary/0 both correctly return.

**Actual** — 500 {"error": "Python int too large to convert to SQLite INTEGER"}. On PostgreSQL the same URL produces a numeric-out-of-range error, likewise echoed verbatim. Negative and non-numeric ids are fine — Flask's <int:> converter 404s them before the route runs.

**Cause** — blueprints/ai_assistant/routes.py:609 — `except Exception as e: return jsonify({"error": str(e)}), 500`. The driver's overflow error is passed straight through to the client. Same construct at routes.py:875 (discharge_instructions) and :842 (analyze_photo).

**Fix** — Log the exception and return a fixed string: `_logger.exception(...)` then `return jsonify({"error": "Could not build the summary."}), 500`. Fixing this alongside the analyze_photo leak is one change in three places.

*reproduced · edge cases*


### [MINOR] The drug-interaction checker accepts a plain string for current_medications and asks the model about ten single letters

**Steps** — POST /ai/drug-interactions with {"new_drug": "Meloxicam", "current_medications": "Ketoprofen", "species": "Cat"} — i.e. a caller that sends one drug as a string rather than a one-element list.

**Expected** — Either the string is treated as one medication name, or the request is rejected. Never a check silently run against nonsense.

**Actual** — 200, and the prompt actually sent to the model reads: "CURRENT active medications: K, e, t, o, p, r, o, f, e, n". The model is asked about ten single-letter drugs and can only answer "no interaction found" — Meloxicam plus Ketoprofen in a cat is a genuine NSAID-stacking risk that this check will never see. Note the safety net does hold on the *unreachable* path: an unparseable reply correctly comes back severity "unchecked", safe=false. It is only the well-formed-answer-to-a-mangled-question path that gets through.

**Cause** — blueprints/ai_assistant/routes.py:982 `current_rx = data.get("current_medications", [])` with no type check, then routes.py:1010 `', '.join(current_rx)` — join over a str iterates characters. Both in-app callers currently send arrays (templates/visits/visit_detail.html:1136 and templates/workflow/index.html:1337), so this is reachable from an API client or a future caller, not from today's screens.

**Fix** — One line at the top of the route: `if isinstance(current_rx, str): current_rx = [current_rx]`, then `current_rx = [str(m).strip() for m in current_rx if str(m).strip()]` — which also kills the sibling cases below (a list of ints or None currently 500s with a TypeError from the same join).

*reproduced · edge cases*


### [MINOR] /ai/health-alerts silently drops its Stock and Finance sections — a missing table swallowed by a bare except

**Steps** — GET https://demo.aleefy.online/ai/health-alerts as admin. Then check the data it claims to look for: SELECT COUNT(*), SUM(due_amount) FROM invoices WHERE status='Unpaid' AND issue_date < CURRENT_DATE-30.

**Expected** — Vaccine alerts, plus low-stock alerts, plus the overdue-invoice alerts the route explicitly queries.

**Actual** — Only 5 vaccine alerts, count:5. The low-stock query reads FROM inventory_items, which does not exist in this schema — the stock catalogue is `items`. On SQLite it raises "no such table: inventory_items"; on the demo's PostgreSQL information_schema confirms zero such table. Because the whole body sits in one try/except Exception: pass, and the finance query runs AFTER the stock query, the exception also kills the finance section: 49 unpaid invoices older than 30 days totalling 68,933 EGP never appear. Rated minor only because no template or JS currently calls this endpoint — but the same wrong tables/filters are the ones feeding /ai/insights, and this endpoint is a loaded gun for whoever wires it up. Note the identical mistake was already found and fixed in blueprints/reports/builder_routes.py:120, which carries a comment saying "There is no `inventory_items` table"; this copy was missed.

**Cause** — blueprints/ai_assistant/routes.py:741-746 (table name) and routes.py:769-770 (except Exception: pass)

**Fix** — Point the query at items joined to batches for on-hand, and give each of the three sections its own try/except so one failure cannot silently delete the other two. Also note `count` is len(alerts) after three LIMIT 5 caps, so it reports 5 while 66 issues exist — return the real totals alongside the sample.

*reproduced · money & records*


### [MINOR] Outbreak radar groups diagnoses by exact case-sensitive text, so a real cluster is downgraded by capitalisation

**Steps** — Insert three diagnoses in the last 7 days on three different pets, recorded as "Parvovirus", "Parvovirus" and "parvovirus" (staff free-type this field). GET /ai/outbreak-radar.

**Expected** — 3 distinct pets with the same disease crosses the >=3 threshold, level "alert", alert_count 1, and the AI public-health commentary fires.

**Actual** — {"outbreaks":[{"diagnosis":"Parvovirus","pet_count":2,"level":"watch"}], "alert_count":0, "ai_comment":""}. The lowercase case is split into its own group of 1, which HAVING COUNT(DISTINCT pet_id) >= 2 then discards entirely — so the third parvovirus case is not merely miscounted, it disappears from the screen. The one thing this feature exists to catch is exactly the thing a stray capital letter suppresses. (The demo's seeded diagnoses happen to be consistently cased, so it does not misfire there today — but the field is free text, entered by whoever is typing.)

**Cause** — blueprints/ai_assistant/routes.py:928-936 — GROUP BY d.diagnosis

**Fix** — GROUP BY lower(trim(d.diagnosis)) and display MIN(d.diagnosis) as the label.

*reproduced · money & records*


### [MINOR] Outbreak radar raises infection-control alerts for non-infectious diagnoses

**Steps** — GET https://demo.aleefy.online/ai/outbreak-radar as admin.

**Expected** — Clusters that could plausibly be an outbreak.

**Actual** — Live response flags "Soft Tissue Trauma" across 4 pets at level "alert" (one of only 2 alerts), which then drove the AI to write "immediate investigation into zoonotic risks and clinic hygiene", "strict isolation protocols", "Reinforce PPE usage". Trauma is not transmissible. Any diagnosis text that repeats — dental grades, dermatitis, trauma — trips the same threshold. A public-health alarm that cries wolf on trauma is one staff learn to close without reading, which defeats the feature the day it matters.

**Cause** — blueprints/ai_assistant/routes.py:927-949 — no notion of which diagnoses are communicable

**Fix** — Either restrict the scan to an explicit communicable-disease list, or drop the "outbreak/alert" framing for uncategorised diagnoses and label them neutrally as "recurring presentations this week".

*reproduced · money & records*


### [MINOR] Patient context reports the pet record's weight while labelling it as the current visit's — the dosing number the AI is told to use

**Steps** — Create a pet with weight_kg 40, and a visit for that pet with weight_kg 99. GET /ai/context/visit/<id> as a doctor.

**Expected** — The weight recorded at this visit, since the block is headed "PATIENT CONTEXT (current visit)".

**Actual** — "Weight   : 40.0 kg" — the pets-table value. The visit's own weight_kg is selected (v.* is in the query) but never preferred. The doctor system prompt tells the model to do "dosage calculations (mg/kg)" off this block. On the demo 244 of 390 visits carry a weight that differs from the pet record, though the spread there is small (max ~5%); the risk is a fast-growing or fast-losing patient, or a historical visit being reviewed. Secondary: when both weights are NULL the line renders "Weight   : None kg" rather than "?", because visit.get('weight_kg','?') returns the present-but-None value.

**Cause** — blueprints/ai_assistant/routes.py:279

**Fix** — Prefer the visit's recorded weight, fall back to the pet record, and say which one it is: `visit.get('weight_kg') or visit.get('pet_weight') or '?'` with a "(recorded at this visit)" / "(from patient record)" suffix.

*reproduced · money & records*


### [MINOR] /ai/insights hands daily takings and receivables to doctors, who are deliberately granted no money modules

**Steps** — Log in as dr.sara / Demo@1234 (or set a session role of 'doctor' locally) and POST /ai/insights.

**Expected** — 403 or a snapshot with the financial lines removed — DEFAULT_ROLE_PERMISSIONS at models/database.py:4131 states for clinicians: "the medical record and what they prescribe from it. No money."

**Actual** — 200. The blueprint-level grant for ai_assistant is the single key "ai", which doctor holds for the chat assistant, so the same grant also opens the clinic's financial snapshot. The returned insight text restates the figures verbatim ("Address the 64 unpaid invoices totaling 82,986 EGP"). Verified against the gate: nurse, reception, pharmacist, finance, inventory_mgr and hr all get 302, doctor gets 200. Contrast /ai/context/visit/<id>, which does carry an explicit CLINICAL_ROLES check and correctly 403s a groomer.

**Cause** — blueprints/ai_assistant/routes.py:511-513 — @login_required only; grant mapping at blueprints/auth/routes.py:130

**Fix** — Add an explicit role gate on insights (and health_alerts) matching the finance/owner set, the same way context_visit gates on CLINICAL_ROLES — or split the money lines out of the snapshot when the caller is not a finance/owner role.

*reproduced · money & records*


### [INFO] Non-string JSON scalars produce unhandled 500s across five AI routes

**Steps** — POST any of these as a logged-in user: /ai/suggest-diagnosis {"complaint": 5} or {"complaint": ["a"]}; /ai/nl-report {"query": 5} or {"query": ["a"]}; /ai/draft-message {"context": ["a"]}; /ai/drug-interactions {"new_drug": 42} or {"new_drug": null} or {"current_medications": [1,2]}.

**Expected** — 400 with a message, or the value coerced.

**Actual** — Unhandled `AttributeError: 'int' object has no attribute 'strip'` / `'list' object has no attribute 'strip'` / `TypeError: sequence item 0: expected str instance, int found` — a 500 with a stack trace in the log. Not reachable from any of the app's own screens (every in-app caller sends strings), so this costs a clinic nothing today; it matters only for the documented API surface and for the noise it puts in the error log.

**Cause** — Every one of these does `(data.get(k) or "").strip()` or joins the value without checking the type — routes.py:983 (new_drug), :1067 (complaint), :690 (query), :639 (context), :1010 (join).

**Fix** — `str(data.get(k) or "").strip()` at each site. Low priority; fold it in when touching those routes for the higher-severity items above.

*reproduced · edge cases*


### [INFO] Outbreak radar scans 8 days but tells the model it is 7

**Steps** — GET /ai/outbreak-radar and read scan_period.

**Expected** — scan_period spanning 7 days.

**Actual** — "scan_period":"2026-07-31 → 2026-08-07" — cutoff is today-7 and the filter is >=, so 8 dates are included, while the AI prompt states "in the last 7 days" and the alert threshold is calibrated against that. Small, but it is the denominator of a rate the model is asked to judge.

**Cause** — blueprints/ai_assistant/routes.py:921 and 960

**Fix** — Use timedelta(days=6) with >=, or state the actual window in the prompt.

*reproduced · money & records*


### [INFO] Three AI routes return the raw Python exception string to the browser

**Steps** — Trigger any DB or provider error on POST /ai/pet-summary/<id>, POST /ai/discharge-instructions/<id>, or POST /ai/analyze-photo.

**Expected** — A neutral message, the way call_ai() already handles it.

**Actual** — jsonify({"error": str(e)}), 500 — the raw driver/SDK text goes to the client. This is precisely the failure call_ai was hardened against at routes.py:189-202 ("That names another vendor, blames the reader, and tells an attacker what we run. Log it, do not print it."), and it is how the earlier `vaccinated_at` column bug surfaced to users as a database error string. The three sibling handlers were not given the same treatment.

**Cause** — blueprints/ai_assistant/routes.py:607-608, 876-877, 842-843

**Fix** — _logger.exception(...) then return a fixed neutral message, matching call_ai.

*reproduced · money & records*


## Petshop  (15)

### [BLOCKER] POS order-level discount is never sent to the invoice — every discounted sale leaves the customer owing the discount forever

**Steps** — Local, real routes (Flask test client, admin). POST /petshop/orders/create with {"items":[{"product_id":P,"product_name":"DiscBook","qty":1,"unit_price":100.0,"tax_rate":0,"discount":0}],"discount_amount":20.0,"paid_amount":80.0,"payment_method":"Cash"} — i.e. exactly what templates/petshop/pos.html submitOrder() sends when the cashier types 20 into the Discount box on a 100 EGP cart and takes 80 EGP.

**Expected** — ps_order.total = 80 AND invoice.total = 80, paid 80, due 0, status Paid. The customer paid the discounted price in full and owes nothing.

**Actual** — ps_order: subtotal=100 discount=20 total=80 paid=80 (correct). invoice INV-2026-00001: subtotal=100.0 discount_amount=0.0 total=100.0 paid_amount=80.0 due_amount=20.0 status='Partial'. The customer walks out square with the till and permanently owes 20 EGP in the books — it shows on their account, in AR aging, and in collections. Every discounted pet-shop sale creates a phantom receivable equal to the discount.

**Cause** — blueprints/petshop/routes.py:516-520 — inv_data passed to db.create_invoice() carries owner_id/pet_id/issue_date/notes/created_by and no discount_type or discount_value, while inv_lines (routes.py:521-535) are built at full unit_price. models/database.py:3435 therefore computes disc_amt=0 and total=subtotal. Only the per-LINE discount survives; the order-level Discount box is dropped. The payment is then add_payment(amount=min(paid_amt, total)) at routes.py:539-546 using the pet-shop total (80), not the invoice total (100).

**Fix** — Pass the order-level discount into create_invoice: inv_data["discount_type"]="value"; inv_data["discount_value"]=discount_g. Existing test test_pos_order_discount_comes_off_the_total (tests/test_petshop_routes.py:220) only asserts ps_orders.total, which is why 1,781 green tests never saw this. Failing test to add: test_pos_order_discount_also_comes_off_the_invoice — assert invoice.total == ps_order.total and invoice.due_amount == 0.

*reproduced · edge cases*


### [BLOCKER] Card / Transfer / Instapay sales record no payment at all — 3 of the 4 payment buttons book the sale as revenue and the invoice as Unpaid

**Steps** — Local, real routes. POST /petshop/orders/create with {"items":[{"product_id":P,"product_name":"CardSale","qty":1,"unit_price":250.0}],"paid_amount":0,"payment_method":"Card"}. This is the default UI flow: on /petshop/pos the cashier taps a product, taps the 'Card' button, taps Charge. The 'Amount tendered (EGP)' box (pos.html:161) is a cash concept, is never pre-filled, and nothing prompts for it.

**Expected** — A 250 EGP card sale produces an invoice with paid_amount 250, due 0, status Paid, and one payments row of 250.

**Actual** — ps_order: total=250 paid_amount=0 status='paid'. invoice: total=250 paid_amount=0 due_amount=250 status='Unpaid'. payments table: zero rows. So the Pet Shop dashboard and reports count 250 EGP of revenue, the accounting module shows the customer owing 250, and the cash-drawer/payments ledger has no record the money ever arrived. Every non-cash pet-shop sale diverges from the books.

**Cause** — blueprints/petshop/routes.py:538 — `if paid_amt > 0 and inv_id:` skips db.add_payment entirely when paid_amount is 0. templates/petshop/pos.html:348 guards underpayment only for cash: `if(method==='Cash' && paid < grand)`, so a Card/Transfer/Instapay sale ships paid_amount=0 (pos.html:342, `parseFloat(...)||0`) with no warning. ps_orders.status is hardcoded 'paid' at routes.py:484 regardless of paid_amt.

**Fix** — For non-cash methods treat the sale as settled in full: pay = total if method != 'Cash' else paid_amt, and always call add_payment when pay > 0. Or auto-fill / hide the tendered box for non-cash and require it. Failing test: test_card_sale_settles_its_invoice — post a Card sale with paid_amount 0 and assert invoice.status == 'Paid' and one payments row.

*reproduced · edge cases*


### [BLOCKER] A mistyped discount produces a negative-total sale: the till displays 0.00, the sale goes through, and Revenue Today goes DOWN

**Steps** — On /petshop/pos: add one 40 EGP item. In the Discount box type 50 (meaning '5', or typing the price into the discount field). The TOTAL line and the Charge button both show 0.00 EGP. Leave 'Amount tendered' empty and press Charge. Reproduced locally as POST /petshop/orders/create {"items":[{..."qty":1,"unit_price":40.0}],"discount_amount":50.0,"paid_amount":0.0,"payment_method":"Cash"}.

**Expected** — Either the discount is clamped to the subtotal (total 0.00) or the sale is refused. A sale can never have a negative total.

**Actual** — HTTP 200 {"success":true,"total":-10.0,"change":10.0}. ps_order total=-10.0 status='paid'. The receipt modal tells the cashier to hand over 10.00 EGP change that was never tendered. Dashboard Revenue Today fell from 80.00 to 70.00. /petshop/reports for the day then rendered Revenue -4,022, Cost -148, Gross Profit -3,874, Margin 96.3% — one typo poisons the whole month's report. The invoice created alongside is total=40 due=40 Unpaid, so the customer also owes 40 they were never asked for.

**Cause** — blueprints/petshop/routes.py:473 — `total = round(subtotal - discount_g + tax_amt, 2)` with no floor at 0 and no check that discount_g <= subtotal. The screen looks fine because templates/petshop/pos.html:274 clamps only the DISPLAY (`if(grand<0) grand=0`), while submitOrder() (pos.html:344) recomputes `grand = sub-disc+tax` WITHOUT the clamp — so the cash guard `paid(0) < grand(-10)` is false and lets it through, and the raw disc is what gets posted.

**Fix** — Server side: reject or clamp — `discount_g = min(max(discount_g, 0), subtotal + tax_amt)`, and refuse the order if total < 0. Client side: clamp disc to sub in recalc() and reuse the same clamped grand in submitOrder(). Failing test: test_a_discount_larger_than_the_cart_cannot_make_a_negative_sale.

*reproduced · edge cases*


### [MAJOR] Pet Shop Reports 500s the moment either date box is cleared — verified on the live PostgreSQL demo

**Steps** — On https://demo.aleefy.online/petshop/reports (admin), click the 'from' date box in the Period filter, clear it, press Apply. Verified live: GET /petshop/reports?date_from=&date_to=2026-08-07 -> 500; GET /petshop/reports?date_from=2026-08-01&date_to= -> 500; GET /petshop/reports?date_from=&date_to= -> 500.

**Expected** — A cleared date falls back to the route's default (month start / today), or the filter is ignored. Same as /petshop/orders, where GET /petshop/orders?date_from=&date_to= correctly returns 200.

**Actual** — HTTP 500 error page. Server log: `psycopg2.errors.InvalidDatetimeFormat: invalid input syntax for type date: ""` then `ERROR app: Exception on /petshop/reports [GET]` -> `GET /petshop/reports -> 500 in 34.9ms`. The same URL returns 200 with zeros on SQLite, which is exactly why the local suite never caught it.

**Cause** — blueprints/petshop/routes.py:627-628 — `request.args.get("date_from", <default>)` only applies the default when the parameter is ABSENT. The filter form (templates/petshop/reports.html:47-49) always submits both inputs, so a cleared box sends `date_from=` (present, empty string) and the empty string reaches five `date(created_at) BETWEEN ? AND ?` queries (routes.py:635, 647, 667, 677, 687). PostgreSQL rejects ''; SQLite silently yields NULL. Contrast routes.py:409-414 where the orders list guards with `if date_from:`.

**Fix** — `date_from = request.args.get("date_from") or datetime.utcnow().strftime("%Y-%m-01")` (same for date_to) — `or` catches the empty string, `get(default)` does not. Failing test (must run against PostgreSQL, TEST_POSTGRES_DSN): test_reports_survives_a_cleared_date_box — assert client.get('/petshop/reports?date_from=&date_to=').status_code == 200.

*reproduced · edge cases*


### [MAJOR] Clearing the quick stock-adjust box on the Products page 500s

**Steps** — On /petshop/products every product card has a quick stock form: a number input pre-filled with 1 and '+ In' / '- Out' buttons. Select the 1, press Delete, click '+ In'. Reproduced locally with PROPAGATE_EXCEPTIONS off: POST /petshop/products/<pid>/stock with qty='' -> HTTP 500. Also qty='abc' -> 500 and qty='2.5' -> 500.

**Expected** — An empty or non-integer quantity is rejected with a flash message, or treated as no-op. Never a 500.

**Actual** — HTTP 500 error page; the whole products screen is lost and the adjustment is not recorded. `2.5` also 500s, which bites any clinic stocking by kg/litre/bottle — the unit dropdown (templates/petshop/product_form.html:100) offers non-integer units while the adjust route forces int().

**Cause** — blueprints/petshop/routes.py:326 — `qty = int(request.form.get("qty", 0))` sits outside any try/except; ValueError escapes the route. The input at templates/petshop/products.html:81 has `min="1"` but no `required`, so the browser happily submits an empty value. (Related: qty is also missing entirely -> int(0) works, stock unchanged, but 'Stock updated.' is still flashed — a silent no-op reported as success.)

**Fix** — Parse defensively and validate: `try: qty = float(request.form.get('qty') or 0) except ValueError: flash('Enter a quantity.', 'danger'); return redirect(...)`, plus `if qty <= 0: return` so the false 'Stock updated' goes away. Failing test: test_stock_adjust_with_an_empty_quantity_does_not_500.

*reproduced · edge cases*


### [MAJOR] Cancelling a pet-shop order reverses the invoice but leaves the payment on the books

**Steps** — Sell 300 EGP cash on /petshop/pos, then open the order and press Cancel (POST /petshop/orders/<oid>/cancel). Reproduced locally end to end.

**Expected** — A cancelled sale leaves no money in the ledger: the payment is reversed or a refund row is written, and invoice.paid_amount returns to 0.

**Actual** — invoice goes status 'Paid' -> 'Cancelled' correctly, and stock is restored correctly. But the payments row survives untouched (id, invoice_id, amount 300.0, method Cash, received_by admin) and invoice.paid_amount stays 300.0 on a Cancelled invoice. SUM(amount) over payments for that invoice after cancel = 300.0. Any cash-drawer, daily-collections, or payment-method report built on the payments table still counts a sale that was cancelled — and the invoice itself now says Cancelled/paid 300/due 0, which is internally inconsistent.

**Cause** — blueprints/petshop/routes.py:599-613 — the cancel transaction updates ps_orders.status, sets invoices.status='Cancelled' (line 604-606), and restores stock, but never touches the payments table or invoices.paid_amount/due_amount.

**Fix** — Inside the same transaction either insert a reversing payments row (amount = -paid) or delete the pet-shop payment and reset invoices.paid_amount=0, due_amount=total. Failing test: test_cancelling_a_pos_sale_reverses_its_payment — assert SUM(payments.amount) for the invoice == 0 after cancel.

*reproduced · edge cases*


### [MAJOR] Pet Shop profit report values sold goods at TODAY's cost price — last month's profit changes when a supplier raises a price

**Steps** — Sell one unit of a product whose cost_price is 40 and sell_price is 100. Open /petshop/reports for today: Cost 40, Gross Profit 60. Now edit that product (/petshop/products/<pid>/edit) and set Cost Price to 95 — a normal thing to do when the supplier's price changes. Reload /petshop/reports for the SAME past date range.

**Expected** — A completed sale's cost is fixed at the moment it was sold. Historical Cost / Gross Profit / Margin never move.

**Actual** — Reported cost of goods sold for that already-completed sale changed from 40.0 to 95.0, so Gross Profit for a closed period silently dropped from 60 to 5 and Margin from 60% to 5%. Reprinting last month's report gives a different answer than the one the owner saw last month. ps_order_items stores id, order_id, product_id, product_name, qty, unit_price, discount, tax_rate, line_total — no cost column at all, so the historical cost is simply not recorded.

**Cause** — blueprints/petshop/routes.py:642-649 — `SUM(oi.qty * p.cost_price)` joins ps_order_items to the LIVE ps_products row. Contrast the revenue side, which correctly reads oi.line_total off the frozen order line.

**Fix** — Add a cost_price column to ps_order_items, snapshot the product's cost at sale time in order_create (routes.py:495-499), and have the report sum oi.qty * oi.cost_price. Failing test: test_changing_a_products_cost_does_not_move_a_past_months_profit.

*reproduced · edge cases*


### [MAJOR] Two tills sell the same last unit — the server never re-checks stock, so the shop oversells with no error to either cashier

**Steps** — One unit of a 500 EGP product on the shelf. Two cashiers each open /petshop/pos (both pages rendered when stock was 1). Cashier A adds it and charges; cashier B, whose page still says 1 in stock, adds it and charges. Reproduced locally by posting the same well-formed cart twice against stock_qty=1.

**Expected** — The second sale is refused ('Only 0 left in stock') and no order, invoice, or payment is created for it.

**Actual** — Both sales succeed: PS-202608-0001 total 500.0 and PS-202608-0002 total 500.0, HTTP 200 both times, no warning to either cashier. Stock lands at 0 after 2 units were sold from a shelf that held 1. The shop has taken 500 EGP for a product it cannot hand over, and the stock ledger shows two 'out' movements totalling 2 against an opening balance of 1. Same route also accepts qty=1,000,000 against stock 5 (total 100,000,000 EGP) and floors stock at 0 without complaint.

**Cause** — blueprints/petshop/routes.py:501 — `UPDATE ps_products SET stock_qty=MAX(0,stock_qty-?) WHERE id=?`. MAX(0, ...) silently absorbs the shortfall instead of surfacing it; there is no `SELECT stock_qty` check anywhere in order_create. The cart clamp lives only in the browser (templates/petshop/pos.html:224 and :262) and each tab clamps to the stock IT rendered.

**Fix** — Inside the order transaction, do a conditional update per line: `UPDATE ps_products SET stock_qty=stock_qty-? WHERE id=? AND stock_qty>=?` and, if rowcount is 0, roll back and return 409 with the product name. Failing test: test_two_concurrent_sales_cannot_both_take_the_last_unit.

*reproduced · edge cases*


### [MAJOR] A negative quantity in a POS order mints stock out of nothing and writes a negative invoice

**Steps** — Any logged-in user (order_create is @login_required with no role check, so a groomer or nurse qualifies) posts to /petshop/orders/create: {"items":[{"product_id":P,"product_name":"Mint","qty":-50,"unit_price":100.0}],"paid_amount":0}. Product started with stock_qty=3.

**Expected** — A quantity of zero or less is rejected.

**Actual** — HTTP 200 {"success":true,"total":-5000.0,"change":5000.0}. Product stock went 3 -> 53: fifty units appeared on the shelf that were never bought. The stock ledger records the fabrication as movement='out', qty=-50.0, ref_type='sale' — a negative 'out', which no stock report will read as an increase. An invoice for -5000 EGP is created against the walk-in owner. Same route accepts unit_price=-500 and qty=0 without complaint.

**Cause** — blueprints/petshop/routes.py:490-506 — qty and unit_price are float()'d and used directly with no sign or zero check; `MAX(0, stock_qty - (-50))` evaluates to stock_qty + 50. routes.py:471-473 computes subtotal/total from the same unvalidated numbers.

**Fix** — Validate every line before the transaction: `if qty <= 0 or price < 0: return jsonify({"error": "Invalid line"}), 400`. Failing test: test_a_negative_quantity_is_rejected_and_does_not_create_stock.

*reproduced · edge cases*


### [MAJOR] Pet Shop Reports shows zero revenue against 172 real orders on the live demo — every aggregate filters status='paid' but the orders carry 'completed'

**Steps** — Live, admin. GET https://demo.aleefy.online/petshop/orders — 172 orders, e.g. PS-202608-0171 dated 2026-08-07 19:00 for 1,450.00 EGP, others at 6,680.00 and 6,865.00 EGP, all rendered with class="status-completed". Now GET https://demo.aleefy.online/petshop/reports (default range, and also ?date_from=2020-01-01&date_to=2030-01-01). Also GET https://demo.aleefy.online/petshop/ .

**Expected** — Reports totals reconcile with the orders list for the same period.

**Actual** — /petshop/reports KPIs read Total Orders 0, Revenue 0, Cost 0, Gross Profit 0, Margin 0.0%, Avg Order 0 — even over a 2020-2030 range. /petshop/ dashboard reads Orders Today 0 and Revenue Today 0 EGP while orders timestamped today exist. Confirmed by filtering: /petshop/orders?status=completed returns 172 rows, ?status=paid returns effectively none. The one screen an owner opens to see whether the shop made money says it made nothing. (Cosmetic corollary: templates only define .status-paid, not .status-completed, so the badge renders unstyled.)

**Cause** — Every aggregate in blueprints/petshop/routes.py hardcodes status='paid' — index() at lines 186 and 187, reports() at 635, 647, 667, 677, 687 — while scripts/seed/demo_showcase.py:1109 inserts status='completed'. order_create writes 'paid' (routes.py:484). Two names for the same state, and nothing reconciles them.

**Fix** — Pick one terminal status and match it everywhere, or widen the filter to `status IN ('paid','completed')` in all seven queries and add .status-completed to the three templates. Failing test: test_a_completed_order_is_counted_by_petshop_reports. (Note: a sibling audit thread appears to have found this too — tests/test_zz_audit_petshop_happy.py:92 references it.)

*reproduced · edge cases*


### [MINOR] Gross Profit on the Pet Shop report counts VAT as profit — 14% VAT overstates margin by 14 points

**Steps** — Set a product's Tax Rate to 14 on /petshop/products/<pid>/edit (the field accepts 0-100), cost 60, price 100. Sell one on /petshop/pos, then open /petshop/reports for that day.

**Expected** — Revenue for a margin calculation is net of the VAT the clinic is only collecting on the tax authority's behalf: 100 - 60 = 40 profit, 40% margin.

**Actual** — ps_order stores subtotal=100, tax_amount=14, total=114. The report's Revenue KPI is SUM(total)=114 (VAT included) while Cost is 60 (VAT-free), so Gross Profit shows 54 and Margin 47.4% instead of 40 and 40%. Currently masked only because every seeded tax_rate is 0 — it surfaces the day a clinic switches VAT on, and it inflates the number the owner prices against.

**Cause** — blueprints/petshop/routes.py:633 `COALESCE(SUM(total),0) as revenue` includes tax_amount, while total_cost at 642-649 does not. gross_profit = total_revenue - total_cost (line 651) mixes the two bases.

**Fix** — Use `SUM(total - tax_amount)` for the profit calculation (keep SUM(total) if a gross 'takings' figure is also wanted, but label it separately). Failing test: test_vat_is_not_counted_as_gross_profit.

*reproduced · edge cases*


### [MINOR] Cancelling an order that does not exist reports success and writes a false 'order_cancelled' row to the audit log

**Steps** — POST /petshop/orders/999999/cancel (reachable by pressing Cancel on a stale tab after the order was removed, or by editing the URL).

**Expected** — 'Order not found' and nothing written.

**Actual** — The page shows BOTH 'Order cancelled and stock restored.' and 'Order not found.' at the same time. The audit log gains a row: action='order_cancelled', entity_id='999999', details='Order 999999 cancelled, stock restored' — for an order that never existed. Anyone auditing who voided what is reading fiction. Same shape twice more: cancelling an already-cancelled order re-flashes success, and pressing Back and re-submitting a cancel does the same.

**Cause** — blueprints/petshop/routes.py:594 — `if order and order["status"] not in (...)` guards only the writes; the `_log(...)` at line 615 and `flash("Order cancelled and stock restored.", "success")` at line 616 sit outside the guard and run unconditionally.

**Fix** — Move the _log and flash inside the `if`, with an else branch that flashes 'Order not found or already cancelled.' Failing test: test_cancelling_a_missing_order_does_not_claim_success.

*reproduced · edge cases*


### [MINOR] Deleting a category that does not exist reports 'Category deleted.'

**Steps** — POST /petshop/categories with action=delete and cat_id=999999, or cat_id=abc, or cat_id omitted entirely (the last two happen when a stale Categories tab posts after the row is gone).

**Expected** — 'Category not found.' — or at minimum, no success message.

**Actual** — All three cases flash 'Category deleted.' and nothing is deleted. A user working from two tabs deletes a category in tab A, presses delete again in tab B, is told it worked, and only finds out otherwise on refresh.

**Cause** — blueprints/petshop/routes.py:356-360 — the COUNT of products in the category is 0 for a nonexistent id, so the code takes the delete branch, runs `DELETE FROM ps_categories WHERE id=?` (0 rows affected), and flashes success without checking rowcount.

**Fix** — Check the category exists first, or test the DELETE's rowcount before flashing. Failing test: test_deleting_a_missing_category_does_not_claim_success.

*reproduced · edge cases*


### [MINOR] A whitespace-only product name is accepted and becomes an unlabelled card on the Products page and the POS grid

**Steps** — On /petshop/products/new type a single space into Product Name (the field is `required`, but a space satisfies it), fill Sell Price, Save. Also reachable via /petshop/products/<pid>/edit — blanking the name of an existing product saves name='' with no complaint.

**Expected** — A name that is empty after trimming is rejected, the same way the Categories form already rejects it.

**Actual** — The product saves with name='   ' (or '' via edit) and renders as a nameless card on /petshop/products and a nameless tile on the POS grid — the cashier sees a blank button and cannot tell what it sells. The product is still fully sellable and still appears in reports as a blank line. Note the Categories route gets this right (routes.py:365 does `.strip()` then `if name:`), so the two forms disagree.

**Cause** — blueprints/petshop/routes.py:251 and :301 — `f.get("name")` is inserted with no strip and no emptiness check, and ps_products.name is TEXT NOT NULL, which '' satisfies.

**Fix** — `name = (f.get("name") or "").strip()` and bail with a flash if falsy, in both product_new and product_edit. Failing test: test_a_blank_product_name_is_rejected.

*reproduced · edge cases*


### [INFO] A malformed POS cart returns HTTP 500 with the raw Python exception text in the JSON body

**Steps** — POST /petshop/orders/create with a line missing a key or holding a bad value, e.g. {"items":[{"product_id":1,"qty":1,"unit_price":1}]} (no product_name), or qty:"abc", or {"items":"notalist"}.

**Expected** — HTTP 400 with a message the POS can show ('Cart is invalid'), like the empty-cart case already does (routes.py:460-461 correctly returns 400 'No items').

**Actual** — HTTP 500 and the body echoes the Python exception verbatim: {"error": "'product_name'"}, {"error": "'qty'"}, {"error": "could not convert string to float: 'abc'"}, {"error": "string indices must be integers, not 'str'"}. pos.html:369 alerts that string straight to the cashier. Not reachable from the shipped POS page (which always builds a well-formed cart) — it matters for the integration surface and for leaking internals. Bright spot found while probing this: float() correctly parses Arabic-Indic digits, so ٠١٢٣ in a money box becomes 123.0 rather than erroring.

**Cause** — blueprints/petshop/routes.py:561-562 — a single bare `except Exception as e: return jsonify({"error": str(e)}), 500` wraps the whole handler, so a client input error is reported as a server error carrying internal detail.

**Fix** — Validate items up front (each needs product_id, product_name, numeric qty>0, numeric unit_price>=0) and return 400 with a fixed message; keep the 500 branch for genuine server faults and log the detail instead of returning it.

*reproduced · edge cases*

