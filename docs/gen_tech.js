const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, LevelFormat
} = require('docx');
const fs = require('fs');

const BLUE="1F4E79", LBLUE="2E75B6", TBLUE="D6E4F0", GREY="F2F2F2", WHITE="FFFFFF", BLACK="000000", GREEN="1E6B3C", LGREEN="E6F4EA";
const border={style:BorderStyle.SINGLE,size:1,color:"CCCCCC"};
const borders={top:border,bottom:border,left:border,right:border};

const h1=(t)=>new Paragraph({heading:HeadingLevel.HEADING_1,spacing:{before:360,after:120},border:{bottom:{style:BorderStyle.SINGLE,size:6,color:LBLUE,space:4}},children:[new TextRun({text:t,bold:true,size:32,color:BLUE,font:"Arial"})]});
const h2=(t)=>new Paragraph({heading:HeadingLevel.HEADING_2,spacing:{before:240,after:80},children:[new TextRun({text:t,bold:true,size:26,color:LBLUE,font:"Arial"})]});
const h3=(t)=>new Paragraph({heading:HeadingLevel.HEADING_3,spacing:{before:160,after:60},children:[new TextRun({text:t,bold:true,size:22,color:"404040",font:"Arial"})]});
const para=(t,opts={})=>new Paragraph({spacing:{after:120},children:[new TextRun({text:t,size:22,font:"Arial",...opts})]});
const bullet=(t,lvl=0)=>new Paragraph({numbering:{reference:"bullets",level:lvl},spacing:{after:60},children:[new TextRun({text:t,size:22,font:"Arial"})]});
const sp=(n=1)=>new Paragraph({spacing:{after:n*80},children:[new TextRun("")]});
const pb=()=>new Paragraph({children:[new PageBreak()]});
const mkCell=(t,fill,bold=false)=>new TableCell({borders,width:{size:0,type:WidthType.AUTO},shading:{fill:fill||WHITE,type:ShadingType.CLEAR},margins:{top:80,bottom:80,left:120,right:120},children:[new Paragraph({children:[new TextRun({text:t,size:20,font:"Arial",bold,color:(fill===BLUE||fill===LBLUE)?WHITE:BLACK})]})]});

function makeTable(headers, rows, widths) {
  const totalW = widths.reduce((a,b)=>a+b,0);
  return new Table({
    width:{size:totalW,type:WidthType.DXA},
    columnWidths:widths,
    rows:[
      new TableRow({children:headers.map((h,i)=>new TableCell({borders,width:{size:widths[i],type:WidthType.DXA},shading:{fill:BLUE,type:ShadingType.CLEAR},margins:{top:80,bottom:80,left:120,right:120},children:[new Paragraph({children:[new TextRun({text:h,bold:true,size:20,font:"Arial",color:WHITE})]})]})) }),
      ...rows.map((row,ri)=>new TableRow({children:row.map((cell,ci)=>new TableCell({borders,width:{size:widths[ci],type:WidthType.DXA},shading:{fill:ri%2===0?GREY:WHITE,type:ShadingType.CLEAR},margins:{top:80,bottom:80,left:120,right:120},children:[new Paragraph({children:[new TextRun({text:cell,size:20,font:"Arial"})]})]})) }))
    ]
  });
}

const cover=[
  sp(8),
  new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:80},children:[new TextRun({text:"TECHNICAL ARCHITECTURE",size:48,bold:true,color:BLUE,font:"Arial"})]}),
  new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:80},children:[new TextRun({text:"& DESIGN DOCUMENT",size:48,bold:true,color:BLUE,font:"Arial"})]}),
  new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:200},children:[new TextRun({text:"Premium Animal Hospital ERP Platform",size:32,color:LBLUE,font:"Arial"})]}),
  sp(2),
  makeTable(["Field","Value"],[["Document Type","Technical Architecture & Design Document"],["Version","1.0 — Final"],["Date","May 2026"],["Audience","Developers, DevOps, Technical Reviewers"],["Stack","Python 3.11 / Flask / PostgreSQL 15 / Nginx"]],[4000,5360]),
  pb(),
];

const content=[
  // 1. SYSTEM OVERVIEW
  h1("1. System Architecture Overview"),
  para("The Premium Animal Hospital ERP is a monolithic Flask application structured using the Blueprint pattern for modularity. It uses PostgreSQL as the primary database and provides a full-featured web interface for all clinic operations. The application is designed for single-server deployment with an Nginx reverse proxy handling HTTPS termination and static file serving."),
  sp(),
  h2("1.1 High-Level Architecture"),
  new Paragraph({spacing:{after:120},children:[new TextRun({text:"Client Browser  →  Nginx (Port 443/80)  →  Gunicorn WSGI (Port 5100)  →  Flask App  →  PostgreSQL 15",size:22,font:"Courier New",color:"2D2D2D"})]}),
  sp(),
  para("The architecture follows a three-tier model:"),
  bullet("Presentation Tier: Jinja2 HTML templates with custom CSS (platform.css), vanilla JavaScript for dynamic interactions, RTL/LTR bilingual layout switching"),
  bullet("Application Tier: Flask application with 31 blueprints, APScheduler for background jobs, bcrypt authentication, CSRF protection middleware"),
  bullet("Data Tier: PostgreSQL 15 with 55 tables, a custom SQLite-compatibility shim (_PGConn/_PGCursor) enabling dual-backend support"),
  sp(),

  h2("1.2 Technology Stack"),
  makeTable(["Layer","Technology","Version","Purpose"],[
    ["Runtime","Python","3.11","Application language"],
    ["Framework","Flask","2.3+","Web framework + routing"],
    ["Database","PostgreSQL","15+","Primary data store"],
    ["DB Fallback","SQLite","3.40+","Development / offline fallback"],
    ["WSGI Server","Gunicorn","21+","Production application server"],
    ["Reverse Proxy","Nginx","1.24+","SSL termination, static files"],
    ["Auth","bcrypt","4.0+","Password hashing (12 rounds)"],
    ["Scheduler","APScheduler","3.10+","Background jobs (backup, WhatsApp)"],
    ["Excel Export","openpyxl","3.1+","XLSX report generation"],
    ["PDF","fpdf2","2.7+","Salary slip PDF generation"],
    ["AI Gateway","freellmapi","local","Gemini 2.5 Flash proxy on port 3001"],
    ["WhatsApp","Wapilot","API","Automated messaging gateway"],
    ["Testing","pytest","9.0+","Test runner (171 tests)"],
  ],[2500,2000,1500,3360]),
  sp(),pb(),

  // 2. BLUEPRINT STRUCTURE
  h1("2. Application Module Structure"),
  para("The application is organised as 31 Flask Blueprints, each owning its URL namespace, route handlers, and template directory. All blueprints are registered in app.py at startup."),
  sp(),
  makeTable(["Blueprint","URL Prefix","Key Responsibilities","Role Restriction"],[
    ["auth","  /auth/","Login, logout, profile, password change","Public (login), Login required (profile)"],
    ["launcher","  /","Dashboard, AI insights, command palette","login_required"],
    ["crm","  /crm/","Owners, pets, loyalty points, VIP flags","reception, doctor+"],
    ["appointments","  /appointments/","Scheduling, queue, slot management","reception+"],
    ["visits","  /visits/","Visit records, SOAP notes, invoice auto-gen","doctor, nurse+"],
    ["clinical","  /clinical/","Diagnoses, lab requests, clinical notes","doctor+"],
    ["finance","  /finance/","Invoices, payments, expense reports","finance, manager+"],
    ["inventory","  /inventory/","Items, batches, stock movements","inventory_mgr+"],
    ["pharmacy","  /pharmacy/","Prescription dispensing, drug stock","pharmacist+"],
    ["hr","  /hr/","Staff records, shifts, departments","branch_manager+"],
    ["payroll","  /payroll/","Salary calculation, payslips, Excel export","finance+"],
    ["attendance","  /attendance/","Check-in/out, attendance records","All authenticated"],
    ["accounting","  /accounting/","Budget targets, P&L, expense categories","finance+"],
    ["reports","  /reports/","Financial, inventory, doctor revenue reports","manager+"],
    ["grooming","  /grooming/","Grooming bookings, service pricing","groomer+"],
    ["boarding","  /boarding/","Boarding check-in/out, care logs","boarding_staff+"],
    ["doctor","  /doctor/","Doctor personal dashboard","doctor+"],
    ["telemedicine","  /telemedicine/","Video sessions (Jitsi), session management","doctor+"],
    ["whatsapp","  /whatsapp/","Templates, send messages, scheduler logs","manager+"],
    ["ai_assistant","  /ai/","Chat, patient context, health alerts","login_required"],
    ["system","  /system/","Settings, audit log, backup manager","super_admin"],
    ["notifications","  /notifications/","In-app alerts, mark read","login_required"],
    ["uploads","  /uploads/","File attachments, serve files","login_required"],
    ["petshop","  /petshop/","Retail products, orders, reports","reception+"],
    ["petsy","  /petsy/","Public AI widget endpoint","Public (rate-limited)"],
    ["public_api","  /api/public/","Queue display, waiting room","Public (rate-limited)"],
    ["procurement","  /procurement/","Purchase orders, supplier management","inventory_mgr+"],
    ["catalog","  /catalog/","Service catalog, pricing","manager+"],
    ["migration","  /migration/","Excel/CSV data import","super_admin"],
    ["payroll","  /payroll/","Payroll module","finance+"],
    ["inpatient","  /inpatient/","Hospitalisation management","doctor+"],
  ],[2000,1800,3560,2000]),
  sp(),pb(),

  // 3. DATABASE DESIGN
  h1("3. Database Design"),
  h2("3.1 Database Layer Architecture"),
  para("The database layer uses a custom compatibility shim that makes psycopg2 (PostgreSQL driver) behave identically to sqlite3. This enables the same application code to run against both backends without modification."),
  sp(),
  h3("3.1.1 SQL Translation Layer (_fix_sql)"),
  para("All SQL strings pass through _fix_sql() before execution, which applies these transformations:"),
  bullet("? placeholders  →  %s (psycopg2 format)"),
  bullet("INTEGER PRIMARY KEY AUTOINCREMENT  →  SERIAL PRIMARY KEY"),
  bullet("datetime('now')  →  NOW()"),
  bullet("TEXT DEFAULT (NOW())  →  TEXT DEFAULT (NOW()::TEXT)"),
  bullet("INSERT OR IGNORE  →  INSERT ... ON CONFLICT DO NOTHING"),
  bullet("INSERT OR REPLACE  →  INSERT ... ON CONFLICT DO NOTHING"),
  sp(),
  h3("3.1.2 _PGConn / _PGCursor Shim"),
  para("The _PGConn class wraps psycopg2.connection and exposes the sqlite3.Connection interface. Key features:"),
  bullet("Savepoint-based transaction isolation: each execute() call creates a named SAVEPOINT so individual statement failures can be rolled back without aborting the transaction"),
  bullet("lastrowid: captured via RETURNING id clause on INSERT statements"),
  bullet("executescript(): splits DDL scripts on semicolons, translates each statement, executes idempotently (failures silently ignored for IF NOT EXISTS compatibility)"),
  bullet("NUL byte sanitisation: string parameters are cleaned of \\x00 bytes before being passed to psycopg2"),
  sp(),
  h2("3.2 Schema Overview (55 Tables)"),
  makeTable(["Domain","Tables","Key Columns"],[
    ["Core","clinic, branches, settings","name, address, license_number"],
    ["Users & Auth","users, roles","username, password_hash, role, is_active"],
    ["CRM","owners, pets","full_name, phone, vip_flag, loyalty_balance"],
    ["Appointments","appointments","doctor_name, appt_date, appt_start, status"],
    ["Clinical","visits, diagnoses, lab_requests, lab_results","visit_type, status, soap_*"],
    ["Prescriptions","prescriptions, prescription_items","drug_name, dose, frequency"],
    ["Vaccinations","vaccinations","vaccine_name, vaccinated_at, next_due_at"],
    ["Finance","invoices, invoice_lines, payments","status, total_amount, due_amount, paid_amount"],
    ["Expenses","expenses, expense_categories","amount, category_id, approved_by"],
    ["Inventory","items, item_categories, batches, stock_movements","sku, reorder_level, quantity, expiry_date"],
    ["Pharmacy","pharmacy_dispensing","prescription_id, item_id, qty_dispensed"],
    ["HR","staff_profiles, departments, shifts, staff_shifts","employee_id, shift_id, start_time"],
    ["Payroll","salaries, salary_components","basic_salary, absence_deduction, net_salary"],
    ["Attendance","attendance_records","work_date, check_in, check_out, status"],
    ["Grooming","grooming_bookings","service_type, duration_min, groomer_id"],
    ["Boarding","boarding_bookings","check_in_date, check_out_date, daily_rate"],
    ["Telemedicine","telemedicine_sessions","started_at, ended_at, jitsi_room"],
    ["WhatsApp","whatsapp_templates, reminder_runs","template_name, language, body_text"],
    ["Petshop","ps_categories, ps_products, ps_orders, ps_order_items","stock_qty, price, order_total"],
    ["Loyalty","loyalty_points","owner_id, points, ref_type, ref_id"],
    ["System","audit_log, notifications, attachments","action, module, ip, user_agent"],
    ["Catalog","service_catalog","code, standard_price, duration_min"],
    ["Budget","budget_targets","category, monthly_egp"],
  ],[2000,3500,3860]),
  sp(),pb(),

  // 4. SECURITY ARCHITECTURE
  h1("4. Security Architecture"),
  h2("4.1 Authentication Flow"),
  para("1. User submits credentials via POST /auth/login (CSRF-exempt endpoint)"),
  para("2. Rate limiter checks: if IP has 5+ failed attempts within 15 minutes → 403 response"),
  para("3. db.verify_credentials() fetches user record and calls _verify_and_migrate():"),
  bullet("bcrypt.checkpw() for modern hashes ($2b$ prefix)"),
  bullet("SHA-256 fallback for legacy hashes, with transparent re-hash to bcrypt on success"),
  para("4. On success: sensitive fields stripped (password_hash, pin) before session storage"),
  para("5. session[\"user\"] stored in Flask signed cookie (SECRET_KEY encrypted)"),
  para("6. touch_last_login() records timestamp; audit log entry written with IP + User-Agent"),
  sp(),
  h2("4.2 Role-Based Access Control"),
  para("13 roles are defined with hierarchical access. The @role_required(*roles) decorator is applied to every sensitive route. super_admin bypasses all role checks."),
  makeTable(["Role","Level","Key Permissions"],[
    ["super_admin","1 — Full","All modules, system settings, audit log, user management"],
    ["clinic_owner","2","All clinical and financial modules, reports"],
    ["branch_manager","3","All modules except system admin"],
    ["doctor","4","Visits, clinical, appointments, AI assistant"],
    ["nurse","5","Visits (limited), clinical support, inventory view"],
    ["reception","6","Appointments, CRM, invoices, payments"],
    ["finance","7","Finance, payroll, accounting, expense management"],
    ["inventory_mgr","8","Inventory, procurement, pharmacy"],
    ["pharmacist","9","Pharmacy dispensing, drug inventory"],
    ["groomer","10","Grooming bookings only"],
    ["boarding_staff","11","Boarding bookings only"],
    ["support_admin","12","System monitoring, no data modification"],
    ["auditor","13 — Read-only","Read access to reports and audit log only"],
  ],[2500,1500,5360]),
  sp(),
  h2("4.3 CSRF Protection"),
  bullet("Token: 64-character hex string (secrets.token_hex(32)) stored in Flask session"),
  bullet("Validated on all POST/PUT/DELETE requests via before_request hook"),
  bullet("Checked in: form field _csrf_token, header X-CSRF-Token, JSON body _csrf_token"),
  bullet("Exempt routes: /auth/login, /settings/theme, /settings/lang, /api/public/*, /petsy/chat"),
  bullet("Failure response: HTTP 403 with error template (logged to audit)"),
  sp(),
  h2("4.4 HTTP Security Headers"),
  makeTable(["Header","Value","Purpose"],[
    ["X-Content-Type-Options","nosniff","Prevent MIME-type sniffing"],
    ["X-Frame-Options","SAMEORIGIN","Prevent clickjacking"],
    ["X-XSS-Protection","1; mode=block","Legacy XSS filter"],
    ["Referrer-Policy","strict-origin-when-cross-origin","Limit referrer information leakage"],
    ["Content-Security-Policy","default-src 'self'; script-src 'self' 'unsafe-inline' meet.jit.si","Restrict resource origins"],
    ["Server","PAH-Platform","Remove Werkzeug/Python version disclosure"],
  ],[3500,3000,2860]),
  sp(),pb(),

  // 5. BACKGROUND JOBS
  h1("5. Background Jobs & Scheduler"),
  para("APScheduler (BackgroundScheduler, daemon=True) runs three jobs inside the application process. Jobs run with Flask app_context() so they can access the database and application config."),
  makeTable(["Job ID","Schedule","Function","Failure Handling"],[
    ["daily_backup","02:00 daily","bk.run_backup() — copies SQLite/PG to backups/ folder","Failure sends in-app notification to all managers"],
    ["wa_reminders","09:00 daily","run_reminder_jobs() — sends WhatsApp for appts within 24h, overdue vaccinations","Errors logged; individual failures don't stop batch"],
    ["rl_cleanup","Every hour","sec.cleanup_rate_limits() — purges expired rate-limit entries from memory","No failure handling needed (in-memory purge)"],
  ],[2000,2000,3500,1860]),
  sp(),

  // 6. API DESIGN
  h1("6. Internal API Patterns"),
  h2("6.1 Route Conventions"),
  bullet("GET routes: always return HTTP 200 with rendered template or JSON"),
  bullet("POST routes: redirect on success (Post/Redirect/Get pattern), re-render on validation failure"),
  bullet("AJAX endpoints: return JSON with keys: success (bool), error (str), data (object/array)"),
  bullet("File downloads: return send_file() with appropriate Content-Disposition header"),
  sp(),
  h2("6.2 Public API Endpoints (/api/public/)"),
  para("These endpoints are rate-limited and CSRF-exempt, designed for the waiting room queue display:"),
  makeTable(["Endpoint","Method","Response","Auth"],[
    ["/api/public/queue","GET","JSON array of today's appointments with status","None"],
    ["/api/public/clinic-info","GET","JSON clinic name, logo, doctor name","None"],
  ],[3500,1500,3000,1360]),
  sp(),
  h2("6.3 AI Assistant Endpoint"),
  makeTable(["Endpoint","Method","Body","Response"],[
    ["/ai/chat","POST","JSON: {message, visit_id?}","JSON: {content, role}"],
    ["/ai/health-alerts","GET","—","JSON array of health alert objects"],
    ["/ai/context/visit/<id>","GET","—","JSON patient context summary"],
  ],[3000,1500,2500,2360]),
  sp(),pb(),

  // 7. DEPLOYMENT ARCHITECTURE
  h1("7. Deployment Architecture"),
  h2("7.1 Production Server Layout"),
  para("Recommended production deployment on a single Ubuntu 22.04 LTS server:"),
  new Paragraph({spacing:{after:80},children:[new TextRun({text:"/etc/nginx/sites-enabled/pah-platform  (reverse proxy + SSL)",size:20,font:"Courier New",color:"2D2D2D"})]}),
  new Paragraph({spacing:{after:80},children:[new TextRun({text:"/etc/systemd/system/pah-platform.service  (Gunicorn service)",size:20,font:"Courier New",color:"2D2D2D"})]}),
  new Paragraph({spacing:{after:80},children:[new TextRun({text:"/var/www/pah-platform/  (application root)",size:20,font:"Courier New",color:"2D2D2D"})]}),
  new Paragraph({spacing:{after:80},children:[new TextRun({text:"/var/lib/postgresql/15/  (PostgreSQL data)",size:20,font:"Courier New",color:"2D2D2D"})]}),
  new Paragraph({spacing:{after:120},children:[new TextRun({text:"/var/www/pah-platform/data/backups/  (database backups)",size:20,font:"Courier New",color:"2D2D2D"})]}),
  sp(),
  h2("7.2 Environment Variables (Required)"),
  makeTable(["Variable","Example Value","Required"],[
    ["PLATFORM_SECRET_KEY","<random 64-char hex string>","YES — critical for session security"],
    ["POSTGRES_DSN","postgresql://pah_user:STRONG_PW@localhost:5432/vetclinic","YES"],
    ["PLATFORM_ADMIN_USER","admin","YES"],
    ["PLATFORM_ADMIN_PASS","<strong password>","YES — change from default 1234"],
    ["PLATFORM_DEBUG","0","YES — must be 0 in production"],
    ["PLATFORM_PORT","5100","Recommended"],
    ["PLATFORM_HOST","127.0.0.1","Recommended (Nginx proxies externally)"],
  ],[3500,3500,2360]),
  sp(),

  // 8. TESTING
  h1("8. Testing Strategy"),
  makeTable(["Test Suite","File","Tests","Coverage"],[
    ["Security Tests","tests/test_security.py","62","Auth, CSRF, SQLi, XSS, headers, rate limiting, session, path traversal"],
    ["PostgreSQL Integration","tests/test_postgres_full.py","56","Schema, CRUD, transactions, HTTP routes (live DB)"],
    ["Workflow Tests","tests/test_workflow.py","9","Full visit-to-invoice workflow, appointment checkin"],
    ["Pet Shop Tests","tests/test_pet_shop.py","8","Product CRUD, order flow, reports"],
    ["CRM Tests","tests/test_crm.py","6","Owner and pet management"],
    ["Finance Tests","tests/test_finance.py","3","Invoice creation and payment"],
    ["Auth Tests","tests/test_auth.py","4","Login, logout, session"],
    ["CSRF Tests","tests/test_csrf.py","7","Token validation, exempt routes"],
    ["Launcher Tests","tests/test_launcher.py","7","Dashboard, AI insights"],
    ["Accounting Tests","tests/test_accounting.py","6","Budget, P&L, expense reports"],
    ["Other Tests","test_database, test_inventory, etc.","13","Database wrapper, inventory routes"],
    ["TOTAL","—","171 passed / 18 skipped","Full PostgreSQL schema, security, and workflow coverage"],
  ],[3000,3000,1500,2860]),
  sp(),
  h2("8.1 Test Configuration"),
  para("Tests use an isolated vetclinic_test PostgreSQL database created fresh for each test session (conftest.py). The database is dropped and recreated before each test run, ensuring test isolation from production data. The executescript() fix enables fresh schema creation on empty PostgreSQL databases."),
  sp(),pb(),

  // 9. PERFORMANCE
  h1("9. Performance Considerations"),
  h2("9.1 Current Optimisations"),
  bullet("SQL query result caching: _fix_sql() uses an in-process dict cache (_FIX_CACHE) to avoid regex overhead on repeated queries"),
  bullet("Static files: served directly by Nginx, not Flask (significantly reduces Python overhead)"),
  bullet("Session data: lightweight — user profile dict only, no large objects"),
  bullet("Templates: Jinja2 cached in memory after first render"),
  sp(),
  h2("9.2 Known Performance Risks"),
  bullet("No connection pooling: each request opens/closes a psycopg2 connection — HIGH PRIORITY for v1.1"),
  bullet("N+1 query patterns: some dashboard queries make multiple DB round-trips — acceptable for current scale"),
  bullet("APScheduler in-process: competes with web requests during backup window (02:00) — no user impact expected"),
  bullet("AI chat synchronous: each AI request blocks the worker thread — consider async workers for v2.0"),
  sp(),

  // 10. FUTURE ARCHITECTURE
  h1("10. Recommended v2.0 Architecture Changes"),
  makeTable(["Component","Current","Recommended v2.0","Priority"],[
    ["DB Access","Custom psycopg2 shim","SQLAlchemy ORM + Alembic migrations","High"],
    ["Connection Pool","None (new connection per request)","psycopg2.pool.ThreadedConnectionPool (min=2, max=20)","Critical"],
    ["Background Jobs","APScheduler (in-process)","Celery + Redis (out-of-process, reliable)","High"],
    ["Session Store","Flask signed cookie","Redis-backed Flask-Session (server-side)","Medium"],
    ["Error Tracking","logging to stdout","Sentry DSN integration","High"],
    ["Caching","None","Redis cache for dashboard stats (TTL=60s)","Medium"],
    ["Static Files","Nginx direct serve","CDN (CloudFront / Bunny) for images","Low"],
    ["Deployment","Manual","Docker Compose + Nginx + Let's Encrypt","High"],
  ],[2500,2500,2860,1500]),
  sp(),
];

const doc = new Document({
  numbering:{config:[{reference:"bullets",levels:[{level:0,format:LevelFormat.BULLET,text:"•",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:720,hanging:360}}}},{level:1,format:LevelFormat.BULLET,text:"◦",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:1080,hanging:360}}}}]}]},
  styles:{
    default:{document:{run:{font:"Arial",size:22}}},
    paragraphStyles:[
      {id:"Heading1",name:"Heading 1",basedOn:"Normal",next:"Normal",quickFormat:true,run:{size:32,bold:true,font:"Arial",color:BLUE},paragraph:{spacing:{before:360,after:120},outlineLevel:0}},
      {id:"Heading2",name:"Heading 2",basedOn:"Normal",next:"Normal",quickFormat:true,run:{size:26,bold:true,font:"Arial",color:LBLUE},paragraph:{spacing:{before:240,after:80},outlineLevel:1}},
      {id:"Heading3",name:"Heading 3",basedOn:"Normal",next:"Normal",quickFormat:true,run:{size:22,bold:true,font:"Arial",color:"404040"},paragraph:{spacing:{before:160,after:60},outlineLevel:2}},
    ]
  },
  sections:[{
    properties:{page:{size:{width:12240,height:15840},margin:{top:1440,right:1440,bottom:1440,left:1440}}},
    headers:{default:new Header({children:[new Paragraph({border:{bottom:{style:BorderStyle.SINGLE,size:4,color:LBLUE,space:4}},children:[new TextRun({text:"Premium Animal Hospital ERP  |  Technical Architecture Document  |  v1.0",size:18,color:"606060",font:"Arial"})]})]})} ,
    footers:{default:new Footer({children:[new Paragraph({border:{top:{style:BorderStyle.SINGLE,size:4,color:LBLUE,space:4}},alignment:AlignmentType.RIGHT,children:[new TextRun({text:"Page ",size:18,color:"606060",font:"Arial"}),new TextRun({children:[PageNumber.CURRENT],size:18,color:"606060",font:"Arial"}),new TextRun({text:" of ",size:18,color:"606060",font:"Arial"}),new TextRun({children:[PageNumber.TOTAL_PAGES],size:18,color:"606060",font:"Arial"})]})]})} ,
    children:[...cover,...content]
  }]
});

Packer.toBuffer(doc).then(buf=>{
  fs.writeFileSync("C:\\vet\\platform\\docs\\Technical_Architecture_v1.0.docx",buf);
  console.log("Technical Architecture document created.");
});
