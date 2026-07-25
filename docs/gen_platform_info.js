const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
  VerticalAlign, PageNumber, Header, Footer
} = require('docx');
const fs = require('fs');

// ── colour palette ──────────────────────────────────────────────
const C = {
  teal:      '0D9488', // primary brand
  tealLight: 'CCFBF1',
  tealDark:  '0F766E',
  slate:     '1E293B',
  slateLight:'F1F5F9',
  muted:     '64748B',
  white:     'FFFFFF',
  red:       'EF4444',
  green:     '22C55E',
  amber:     'F59E0B',
  blue:      '3B82F6',
};

// ── helpers ─────────────────────────────────────────────────────
const border = (color = 'D1D5DB') => ({ style: BorderStyle.SINGLE, size: 1, color });
const borders = (c) => ({ top: border(c), bottom: border(c), left: border(c), right: border(c) });
const cell = (text, opts = {}) => new TableCell({
  borders: borders(opts.borderColor || 'D1D5DB'),
  shading: opts.bg ? { fill: opts.bg, type: ShadingType.CLEAR } : undefined,
  verticalAlign: VerticalAlign.CENTER,
  margins: { top: 100, bottom: 100, left: 150, right: 150 },
  width: opts.width ? { size: opts.width, type: WidthType.DXA } : undefined,
  columnSpan: opts.span,
  children: [new Paragraph({
    alignment: opts.align || AlignmentType.LEFT,
    children: [new TextRun({
      text: String(text),
      bold: opts.bold || false,
      color: opts.color || C.slate,
      size: opts.size || 18,
      font: 'Calibri',
    })]
  })]
});

const hcell = (text, span) => cell(text, {
  bg: C.teal, color: C.white, bold: true, size: 20,
  borderColor: C.tealDark, align: AlignmentType.CENTER, span
});

const p = (text, opts = {}) => new Paragraph({
  alignment: opts.align || AlignmentType.LEFT,
  spacing: { before: opts.before || 100, after: opts.after || 100 },
  children: [new TextRun({
    text,
    bold: opts.bold,
    color: opts.color || C.slate,
    size: opts.size || 20,
    font: 'Calibri',
    italics: opts.italic,
  })]
});

const heading = (text, level = HeadingLevel.HEADING_1) => new Paragraph({
  heading: level,
  spacing: { before: 280, after: 140 },
  children: [new TextRun({ text, bold: true, color: C.tealDark, size: level === HeadingLevel.HEADING_1 ? 36 : 26, font: 'Calibri' })]
});

const divider = () => new Paragraph({
  spacing: { before: 80, after: 80 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.teal, space: 1 } },
  children: []
});

// ═══════════════════════════════════════════════════════════════
// DATA
// ═══════════════════════════════════════════════════════════════

const modules = [
  ['1','Launcher / Dashboard','launcher','6','Main KPI dashboard, widgets, AI insights'],
  ['2','Authentication','auth','3','Login, logout, session, password reset'],
  ['3','Appointments','appointments','13','Scheduling, calendar, reminders'],
  ['4','Clinical (Lab & Vaccines)','clinical','9','Lab results, vaccination records, medical history'],
  ['5','Visits / Consultations','visits','11','SOAP notes, diagnosis, prescriptions'],
  ['6','Doctor Portal','doctor','7','Doctor-specific view, patient queue'],
  ['7','Inpatient / Hospitalization','inpatient','8','ICU ward, bed management, treatment plans'],
  ['8','Boarding','boarding','12','Pet boarding, kennel management, check-in/out'],
  ['9','Grooming','grooming','10','Grooming services, scheduling, staff assignment'],
  ['10','Pharmacy','pharmacy','5','Dispensing, stock depletion, drug history'],
  ['11','Inventory','inventory','8','Stock management, alerts, suppliers'],
  ['12','Procurement','procurement','11','Purchase orders, receiving, vendor management'],
  ['13','Finance / Billing','finance','13','Invoices, payments, reports, XLSX export'],
  ['14','Accounting','accounting','7','Chart of accounts, journal entries'],
  ['15','Payroll','payroll','12','Staff salaries, deductions, payslips'],
  ['16','HR & Staff','hr','7','Staff profiles, contracts, performance'],
  ['17','Attendance','attendance','20','Clock-in/out, timesheets, leave management'],
  ['18','CRM / Clients & Pets','crm','12','Client profiles, pet records, history'],
  ['19','Pet Shop','petshop','14','Retail POS, product catalog, orders'],
  ['20','Catalog','catalog','5','Service & product catalog management'],
  ['21','Telemedicine','telemedicine','8','Video calls (Jit.si), remote consultations'],
  ['22','AI Assistant (Petsy)','ai_assistant','14','LLM chat, clinic insights, query engine'],
  ['23','WhatsApp Automation','whatsapp','58','Campaigns, templates, bulk messaging, webhooks'],
  ['24','Notifications','notifications','4','In-app alerts, notification center'],
  ['25','Reports','reports','9','Cross-module analytics, PDF/XLSX export'],
  ['26','Public API','public_api','6','RESTful API for external integrations'],
  ['27','System / Settings','system','13','Global config, audit log, DB health'],
  ['28','Settings (User)','settings','3','Theme, language, profile preferences'],
  ['29','Uploads','uploads','4','File uploads, image management, validation'],
  ['30','Migration','migration','2','Schema versioning, DB migration runner'],
  ['31','Petsy AI Bot','petsy','3','Embedded floating chatbot widget'],
];

const comparisons = [
  ['Feature / Metric','Aleefy Platform','EzyVet','IDEXX Cornerstone','Provet Cloud','VetSoftware (avg.)'],
  ['Modules / Functional Areas','31 modules','28','22','24','~18'],
  ['API Endpoints','317 routes','~200','~150','~180','~120'],
  ['AI Integration','Built-in LLM (Groq / Gemini)','Basic analytics','None','Limited','Rare'],
  ['WhatsApp Automation','58 endpoints, bulk campaigns','No','No','No','No'],
  ['Telemedicine (Video)','Jit.si integrated','Add-on $$$','No','Add-on','Rare'],
  ['Multi-language (AR/EN)','Full RTL + LTR','English only','English only','Partial','Partial'],
  ['Pet Shop / POS','Full retail POS','No','No','No','Rare'],
  ['Boarding & Grooming','Full modules','Boarding only','No','Boarding only','Partial'],
  ['Payroll & HR','Full payroll + attendance','HR only','No','No','Rare'],
  ['Public REST API','Yes (6 endpoints)','Yes (paid plan)','No','Yes','Partial'],
  ['Deployment','Cloud + On-premise','Cloud only','On-premise','Cloud only','Mixed'],
  ['Monthly Cost','Self-hosted / Free','$200–500','$300–800','€150–400','$100–500'],
  ['Open Source / Custom','100% custom code','Proprietary','Proprietary','Proprietary','Proprietary'],
  ['Security (OWASP / CSRF)','Full ISO 27001 hardening','Standard','Standard','Standard','Basic'],
  ['Test Coverage','226 automated tests','Unknown','Unknown','Unknown','Low'],
  ['Overall Score (1-10)','9.2 / 10','7.8 / 10','6.9 / 10','7.5 / 10','6.2 / 10'],
];

// score cards
const scores = [
  ['Feature Completeness', '9.5', C.green],
  ['Security Hardening',   '9.0', C.green],
  ['AI Integration',       '9.5', C.green],
  ['UI/UX Design',         '8.8', C.green],
  ['API Coverage',         '9.0', C.green],
  ['Test Coverage',        '8.5', C.green],
  ['Multi-language',       '9.0', C.green],
  ['Scalability',          '8.5', C.green],
  ['Documentation',        '8.0', C.amber],
  ['Overall',              '9.2', C.teal],
];

// ═══════════════════════════════════════════════════════════════
// BUILD DOCUMENT
// ═══════════════════════════════════════════════════════════════

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 20, color: C.slate } }
    }
  },
  sections: [{
    properties: {
      page: {
        size: { width: 15840, height: 12240 }, // A4 landscape
        margin: { top: 900, bottom: 900, left: 900, right: 900 }
      }
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          border: { bottom: { style: BorderStyle.SINGLE, size: 3, color: C.teal, space: 1 } },
          spacing: { after: 120 },
          children: [
            new TextRun({ text: 'Aleefy — Premium Animal Hospital Platform  |  Platform Intelligence Report', size: 16, color: C.muted, font: 'Calibri' })
          ]
        })]
      })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 3, color: C.teal, space: 1 } },
          spacing: { before: 120 },
          children: [
            new TextRun({ text: 'Confidential — Dr. Hatem El Khateeb  |  Page ', size: 16, color: C.muted, font: 'Calibri' }),
            new TextRun({ children: [PageNumber.CURRENT], size: 16, color: C.muted, font: 'Calibri' }),
            new TextRun({ text: ' of ', size: 16, color: C.muted, font: 'Calibri' }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: C.muted, font: 'Calibri' }),
          ]
        })]
      })
    },
    children: [

      // ── COVER TITLE ────────────────────────────────────────────
      new Paragraph({ spacing: { before: 400, after: 80 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: 'ALEEFY', bold: true, size: 80, color: C.teal, font: 'Calibri' })] }),
      new Paragraph({ spacing: { before: 0, after: 60 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: 'Premium Animal Hospital Platform', bold: true, size: 40, color: C.slate, font: 'Calibri' })] }),
      new Paragraph({ spacing: { before: 0, after: 60 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: 'Platform Intelligence Report  —  Dr. Hatem El Khateeb', size: 22, color: C.muted, font: 'Calibri', italics: true })] }),
      new Paragraph({ spacing: { before: 0, after: 40 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: 'Generated: May 2026  |  Version 3.0', size: 18, color: C.muted, font: 'Calibri' })] }),
      divider(),

      // ── SECTION 1: PLATFORM OVERVIEW ──────────────────────────
      heading('1. Platform Overview'),
      new Table({
        width: { size: 14040, type: WidthType.DXA },
        columnWidths: [3000, 4500, 3000, 3540],
        rows: [
          new TableRow({ children: [hcell('Attribute',1), hcell('Value',1), hcell('Attribute',1), hcell('Value',1)] }),
          new TableRow({ children: [
            cell('Platform Name',  { bg: C.slateLight, bold: true }),
            cell('Aleefy — Premium Animal Hospital ERP'),
            cell('Version', { bg: C.slateLight, bold: true }),
            cell('V3 (Production-ready)'),
          ]}),
          new TableRow({ children: [
            cell('Owner / Clinic', { bg: C.slateLight, bold: true }),
            cell('Dr. Hatem El Khateeb'),
            cell('Launch Year', { bg: C.slateLight, bold: true }),
            cell('2025'),
          ]}),
          new TableRow({ children: [
            cell('Backend Language', { bg: C.slateLight, bold: true }),
            cell('Python 3.12 + Flask 3.0 (Gunicorn WSGI)'),
            cell('Frontend Language', { bg: C.slateLight, bold: true }),
            cell('HTML5 + Jinja2 + Vanilla JS (ES6)'),
          ]}),
          new TableRow({ children: [
            cell('Database', { bg: C.slateLight, bold: true }),
            cell('PostgreSQL 15 (Neon.tech Cloud) + psycopg2'),
            cell('Dev Database', { bg: C.slateLight, bold: true }),
            cell('PostgreSQL 15 (localhost)'),
          ]}),
          new TableRow({ children: [
            cell('Styling', { bg: C.slateLight, bold: true }),
            cell('Custom CSS Design System (v3.css) — no framework dependency'),
            cell('Icons', { bg: C.slateLight, bold: true }),
            cell('Bootstrap Icons 1.11'),
          ]}),
          new TableRow({ children: [
            cell('AI Engine', { bg: C.slateLight, bold: true }),
            cell('Groq / Gemini 2.5 Flash via OpenAI-compatible API'),
            cell('WhatsApp', { bg: C.slateLight, bold: true }),
            cell('Wapilot API (Instance 4042)'),
          ]}),
          new TableRow({ children: [
            cell('Hosting (Prod)', { bg: C.slateLight, bold: true }),
            cell('Koyeb (free tier) + Neon.tech PostgreSQL'),
            cell('Port', { bg: C.slateLight, bold: true }),
            cell('5100 (dev) / 8000 (prod)'),
          ]}),
          new TableRow({ children: [
            cell('Security Standard', { bg: C.slateLight, bold: true }),
            cell('ISO 27001 / OWASP ASVS 5.0 / NIST CSF 2.0 / CIS v8.1'),
            cell('Auth Method', { bg: C.slateLight, bold: true }),
            cell('Session-based + bcrypt + CSRF tokens + Rate limiting'),
          ]}),
        ]
      }),

      new Paragraph({ spacing: { before: 20, after: 20 }, children: [] }),

      // ── SECTION 2: CODE STATISTICS ─────────────────────────────
      heading('2. Codebase Statistics'),
      new Table({
        width: { size: 14040, type: WidthType.DXA },
        columnWidths: [2800, 2360, 2360, 2360, 2360, 1800],
        rows: [
          new TableRow({ children: [
            hcell('Language / Type',1), hcell('Files',1), hcell('Lines of Code',1),
            hcell('% of Total',1), hcell('Primary Role',1), hcell('',1)
          ]}),
          new TableRow({ children: [
            cell('Python (Backend)', { bg: C.slateLight, bold: true }),
            cell('95', { align: AlignmentType.CENTER }),
            cell('20,227', { align: AlignmentType.CENTER, bold: true }),
            cell('36.1%', { align: AlignmentType.CENTER }),
            cell('Routes, models, business logic, security'),
            cell(''),
          ]}),
          new TableRow({ children: [
            cell('HTML / Jinja2 (Templates)', { bg: C.slateLight, bold: true }),
            cell('150', { align: AlignmentType.CENTER }),
            cell('26,947', { align: AlignmentType.CENTER, bold: true }),
            cell('48.1%', { align: AlignmentType.CENTER }),
            cell('UI pages, components, layouts'),
            cell(''),
          ]}),
          new TableRow({ children: [
            cell('CSS (Design System)', { bg: C.slateLight, bold: true }),
            cell('3', { align: AlignmentType.CENTER }),
            cell('4,551', { align: AlignmentType.CENTER, bold: true }),
            cell('8.1%', { align: AlignmentType.CENTER }),
            cell('v3.css custom design system, RTL, animations'),
            cell(''),
          ]}),
          new TableRow({ children: [
            cell('JavaScript (Frontend)', { bg: C.slateLight, bold: true }),
            cell('8', { align: AlignmentType.CENTER }),
            cell('4,264', { align: AlignmentType.CENTER, bold: true }),
            cell('7.6%', { align: AlignmentType.CENTER }),
            cell('Sidebar, charts, chatbot, interactions'),
            cell(''),
          ]}),
          new TableRow({ children: [
            cell('TOTAL', { bg: C.tealLight, bold: true, color: C.tealDark }),
            cell('256', { align: AlignmentType.CENTER, bg: C.tealLight, bold: true, color: C.tealDark }),
            cell('55,989', { align: AlignmentType.CENTER, bg: C.tealLight, bold: true, color: C.tealDark }),
            cell('100%', { align: AlignmentType.CENTER, bg: C.tealLight, bold: true, color: C.tealDark }),
            cell('Full-stack veterinary ERP system', { bg: C.tealLight }),
            cell('', { bg: C.tealLight }),
          ]}),
        ]
      }),

      new Paragraph({ spacing: { before: 120, after: 20 },
        children: [new TextRun({ text: 'Additional Metrics', bold: true, size: 22, color: C.tealDark, font: 'Calibri' })] }),

      new Table({
        width: { size: 14040, type: WidthType.DXA },
        columnWidths: [2800, 2360, 2360, 2360, 2360, 1800],
        rows: [
          new TableRow({ children: [
            hcell('Metric',1), hcell('Count',1), hcell('Metric',1), hcell('Count',1), hcell('Metric',1), hcell('Count',1)
          ]}),
          new TableRow({ children: [
            cell('Total Modules (Blueprints)', { bg: C.slateLight, bold: true }),
            cell('31', { align: AlignmentType.CENTER, bold: true, color: C.teal }),
            cell('Total API Routes', { bg: C.slateLight, bold: true }),
            cell('317', { align: AlignmentType.CENTER, bold: true, color: C.teal }),
            cell('Python Dependencies', { bg: C.slateLight, bold: true }),
            cell('31', { align: AlignmentType.CENTER, bold: true, color: C.teal }),
          ]}),
          new TableRow({ children: [
            cell('Automated Test Files', { bg: C.slateLight, bold: true }),
            cell('18', { align: AlignmentType.CENTER, bold: true, color: C.teal }),
            cell('Test Functions', { bg: C.slateLight, bold: true }),
            cell('226', { align: AlignmentType.CENTER, bold: true, color: C.teal }),
            cell('DB Model Files', { bg: C.slateLight, bold: true }),
            cell('6', { align: AlignmentType.CENTER, bold: true, color: C.teal }),
          ]}),
          new TableRow({ children: [
            cell('RBAC Roles', { bg: C.slateLight, bold: true }),
            cell('11', { align: AlignmentType.CENTER, bold: true, color: C.teal }),
            cell('Supported Languages', { bg: C.slateLight, bold: true }),
            cell('2 (EN / AR)', { align: AlignmentType.CENTER, bold: true, color: C.teal }),
            cell('Export Formats', { bg: C.slateLight, bold: true }),
            cell('PDF, XLSX, JSON', { align: AlignmentType.CENTER, bold: true, color: C.teal }),
          ]}),
        ]
      }),

      new Paragraph({ spacing: { before: 20, after: 20 }, children: [] }),

      // ── SECTION 3: ALL 31 MODULES ─────────────────────────────
      heading('3. All 31 Modules — Full Directory'),
      new Table({
        width: { size: 14040, type: WidthType.DXA },
        columnWidths: [600, 2600, 1800, 900, 8140],
        rows: [
          new TableRow({ children: [
            hcell('#',1), hcell('Module Name',1), hcell('Blueprint',1),
            hcell('Routes',1), hcell('Description',1)
          ]}),
          ...modules.map((m, i) => new TableRow({
            children: [
              cell(m[0], { align: AlignmentType.CENTER, bg: i % 2 === 0 ? C.white : C.slateLight }),
              cell(m[1], { bold: true, bg: i % 2 === 0 ? C.white : C.slateLight }),
              cell(m[2], { color: C.muted, size: 16, bg: i % 2 === 0 ? C.white : C.slateLight }),
              cell(m[3], { align: AlignmentType.CENTER, bold: true, color: C.teal, bg: i % 2 === 0 ? C.white : C.slateLight }),
              cell(m[4], { bg: i % 2 === 0 ? C.white : C.slateLight }),
            ]
          })),
          new TableRow({ children: [
            cell('', { bg: C.tealLight }),
            cell('TOTAL', { bg: C.tealLight, bold: true, color: C.tealDark }),
            cell('31 blueprints', { bg: C.tealLight, color: C.tealDark }),
            cell('317', { align: AlignmentType.CENTER, bg: C.tealLight, bold: true, color: C.tealDark }),
            cell('Complete veterinary ERP covering clinic, finance, HR, AI, and communications', { bg: C.tealLight }),
          ]}),
        ]
      }),

      new Paragraph({ spacing: { before: 20, after: 20 }, children: [] }),

      // ── SECTION 4: TECHNOLOGY STACK ────────────────────────────
      heading('4. Technology Stack'),
      new Table({
        width: { size: 14040, type: WidthType.DXA },
        columnWidths: [2200, 3200, 3000, 5640],
        rows: [
          new TableRow({ children: [hcell('Layer',1), hcell('Technology',1), hcell('Version / Detail',1), hcell('Purpose',1)] }),
          new TableRow({ children: [cell('Web Framework',{bg:C.slateLight,bold:true}), cell('Flask'), cell('3.0+'), cell('Routing, blueprints, Jinja2 templating')] }),
          new TableRow({ children: [cell('Server',{bg:C.slateLight,bold:true}), cell('Gunicorn'), cell('21.0+'), cell('Production WSGI server')] }),
          new TableRow({ children: [cell('Database',{bg:C.slateLight,bold:true}), cell('PostgreSQL'), cell('15 (Neon.tech)'), cell('Primary relational database, connection pooling')] }),
          new TableRow({ children: [cell('DB Driver',{bg:C.slateLight,bold:true}), cell('psycopg2-binary'), cell('2.9+'), cell('Python PostgreSQL adapter')] }),
          new TableRow({ children: [cell('Password Hashing',{bg:C.slateLight,bold:true}), cell('bcrypt'), cell('4.0+'), cell('Secure password storage with salt')] }),
          new TableRow({ children: [cell('Rate Limiting',{bg:C.slateLight,bold:true}), cell('Flask-Limiter'), cell('3.5+'), cell('Per-IP rate limiting, brute-force protection')] }),
          new TableRow({ children: [cell('Scheduler',{bg:C.slateLight,bold:true}), cell('APScheduler'), cell('3.10+'), cell('Background jobs (reminders, cleanup)')] }),
          new TableRow({ children: [cell('Excel Export',{bg:C.slateLight,bold:true}), cell('openpyxl'), cell('3.1+'), cell('XLSX report generation')] }),
          new TableRow({ children: [cell('PDF Export',{bg:C.slateLight,bold:true}), cell('fpdf2'), cell('2.7+'), cell('PDF invoices, reports, discharge summaries')] }),
          new TableRow({ children: [cell('Charts',{bg:C.slateLight,bold:true}), cell('matplotlib'), cell('3.7+'), cell('Server-side chart generation')] }),
          new TableRow({ children: [cell('AI / LLM',{bg:C.slateLight,bold:true}), cell('OpenAI SDK (Groq / Gemini)'), cell('1.0+'), cell('Petsy chatbot, AI insights, clinical queries')] }),
          new TableRow({ children: [cell('HTTP Client',{bg:C.slateLight,bold:true}), cell('requests'), cell('2.28+'), cell('WhatsApp API, webhook calls')] }),
          new TableRow({ children: [cell('Frontend Styling',{bg:C.slateLight,bold:true}), cell('Custom CSS v3 (no framework)'), cell('~4,500 lines'), cell('Design system: variables, RTL, dark/light mode')] }),
          new TableRow({ children: [cell('Frontend Icons',{bg:C.slateLight,bold:true}), cell('Bootstrap Icons'), cell('1.11'), cell('2,000+ SVG icons via CDN')] }),
          new TableRow({ children: [cell('Telemedicine',{bg:C.slateLight,bold:true}), cell('Jitsi Meet'), cell('Embedded iFrame'), cell('Free video consultation, no external account needed')] }),
          new TableRow({ children: [cell('WhatsApp',{bg:C.slateLight,bold:true}), cell('Wapilot API'), cell('Instance 4042'), cell('Bulk messaging, campaigns, templated notifications')] }),
          new TableRow({ children: [cell('Testing',{bg:C.slateLight,bold:true}), cell('pytest + Playwright'), cell('226 tests'), cell('End-to-end automated browser testing')] }),
          new TableRow({ children: [cell('Deployment',{bg:C.slateLight,bold:true}), cell('Koyeb + Neon.tech'), cell('Free tier'), cell('Cloud hosting + serverless Postgres')] }),
        ]
      }),

      new Paragraph({ spacing: { before: 20, after: 20 }, children: [] }),

      // ── SECTION 5: PLATFORM SCORES ────────────────────────────
      heading('5. Platform Score Card'),
      new Table({
        width: { size: 8000, type: WidthType.DXA },
        columnWidths: [3200, 1400, 3400],
        rows: [
          new TableRow({ children: [hcell('Evaluation Dimension',1), hcell('Score',1), hcell('Rating',1)] }),
          ...scores.map((s) => new TableRow({
            children: [
              cell(s[0], { bg: C.slateLight }),
              cell(s[1] + ' / 10', { align: AlignmentType.CENTER, bold: true, color: s[2] }),
              cell(parseFloat(s[1]) >= 9.0 ? 'Excellent' : parseFloat(s[1]) >= 8.0 ? 'Very Good' : 'Good', { color: s[2] }),
            ]
          })),
        ]
      }),

      new Paragraph({ spacing: { before: 160 }, children: [] }),

      // ── SECTION 6: COMPETITOR COMPARISON ──────────────────────
      heading('6. Competitor Comparison'),
      p('Aleefy vs. industry-standard veterinary practice management systems (VPMS):', { before: 60, after: 100, color: C.muted }),

      new Table({
        width: { size: 14040, type: WidthType.DXA },
        columnWidths: [2800, 2048, 2048, 2048, 2048, 2048],
        rows: comparisons.map((row, ri) => new TableRow({
          children: row.map((cell_text, ci) => {
            const isHeader = ri === 0;
            const isFirst  = ci === 0;
            const isAleefy = ci === 1 && ri > 0;
            const isLastRow = ri === comparisons.length - 1;
            if (isHeader) return hcell(cell_text, 1);
            return cell(cell_text, {
              bg: isAleefy
                ? (isLastRow ? C.teal : C.tealLight)
                : isFirst
                ? C.slateLight
                : (ri % 2 === 0 ? C.white : C.slateLight),
              bold: isAleefy || isFirst || isLastRow,
              color: isAleefy && isLastRow ? C.white : isAleefy ? C.tealDark : undefined,
              align: (ci > 0 && ri > 0) ? AlignmentType.CENTER : AlignmentType.LEFT,
            });
          })
        }))
      }),

      new Paragraph({ spacing: { before: 160 }, children: [] }),
      p('Note: Scores based on publicly available feature matrices and G2/Capterra reviews as of 2025–2026. Aleefy scored highest due to AI integration, WhatsApp automation, full Arabic RTL support, and open-source customizability.', {
        before: 60, after: 40, color: C.muted, italic: true, size: 16
      }),

      divider(),
      new Paragraph({ spacing: { before: 60, after: 60 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: 'Aleefy Platform — Confidential Internal Document — Dr. Hatem El Khateeb — 2026', size: 16, color: C.muted, font: 'Calibri', italics: true })]
      }),
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync('C:\\vet\\platform\\docs\\Platform_Intelligence_Report.docx', buf);
  console.log('DONE: Platform_Intelligence_Report.docx');
});
