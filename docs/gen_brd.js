const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, LevelFormat,
  ExternalHyperlink
} = require('docx');
const fs = require('fs');

const BLUE  = "1F4E79";
const LBLUE = "2E75B6";
const TBLUE = "D6E4F0";
const GREY  = "F2F2F2";
const WHITE = "FFFFFF";
const BLACK = "000000";

const border  = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LBLUE, space: 4 } },
    children: [new TextRun({ text, bold: true, size: 32, color: BLUE, font: "Arial" })]
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 80 },
    children: [new TextRun({ text, bold: true, size: 26, color: LBLUE, font: "Arial" })]
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 160, after: 60 },
    children: [new TextRun({ text, bold: true, size: 22, color: "404040", font: "Arial" })]
  });
}
function para(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({ text, size: 22, font: "Arial", ...opts })]
  });
}
function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 60 },
    children: [new TextRun({ text, size: 22, font: "Arial" })]
  });
}
function sp(n = 1) {
  return new Paragraph({ spacing: { after: n * 80 }, children: [new TextRun("")] });
}
function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}
function cell(text, fill, bold = false, span = 1, align = AlignmentType.LEFT) {
  return new TableCell({
    borders,
    width: { size: Math.floor(9360 / span), type: WidthType.DXA },
    shading: { fill: fill || WHITE, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({ text, size: 20, font: "Arial", bold, color: fill === BLUE || fill === LBLUE ? WHITE : BLACK })]
    })]
  });
}
function twoCol(col1, col2, w1 = 4680, w2 = 4680) {
  return new TableCell({
    borders,
    width: { size: w1, type: WidthType.DXA },
    shading: { fill: WHITE, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text: col1, size: 20, font: "Arial" })] })]
  });
}

// ─── COVER PAGE ───────────────────────────────────────────────────────────────
const coverPage = [
  sp(8),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 80 },
    children: [new TextRun({ text: "BUSINESS REQUIREMENTS DOCUMENT", size: 48, bold: true, color: BLUE, font: "Arial" })]
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 80 },
    children: [new TextRun({ text: "Premium Animal Hospital ERP Platform", size: 36, color: LBLUE, font: "Arial" })]
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [new TextRun({ text: "مستشفى بريميوم للحيوانات", size: 28, color: "606060", font: "Arial" })]
  }),
  sp(2),
  new Table({
    width: { size: 6000, type: WidthType.DXA },
    columnWidths: [3000, 3000],
    rows: [
      new TableRow({ children: [
        new TableCell({ borders, width: { size: 3000, type: WidthType.DXA }, shading: { fill: TBLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Document Version", bold: true, size: 20, font: "Arial" })] })] }),
        new TableCell({ borders, width: { size: 3000, type: WidthType.DXA }, shading: { fill: WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "1.0 — Final", size: 20, font: "Arial" })] })] }),
      ]}),
      new TableRow({ children: [
        new TableCell({ borders, width: { size: 3000, type: WidthType.DXA }, shading: { fill: TBLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Date", bold: true, size: 20, font: "Arial" })] })] }),
        new TableCell({ borders, width: { size: 3000, type: WidthType.DXA }, shading: { fill: WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "May 2026", size: 20, font: "Arial" })] })] }),
      ]}),
      new TableRow({ children: [
        new TableCell({ borders, width: { size: 3000, type: WidthType.DXA }, shading: { fill: TBLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Client", bold: true, size: 20, font: "Arial" })] })] }),
        new TableCell({ borders, width: { size: 3000, type: WidthType.DXA }, shading: { fill: WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Dr. Hatem El Khateeb", size: 20, font: "Arial" })] })] }),
      ]}),
      new TableRow({ children: [
        new TableCell({ borders, width: { size: 3000, type: WidthType.DXA }, shading: { fill: TBLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Status", bold: true, size: 20, font: "Arial" })] })] }),
        new TableCell({ borders, width: { size: 3000, type: WidthType.DXA }, shading: { fill: WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Approved — Pre-Production", size: 20, font: "Arial" })] })] }),
      ]}),
    ]
  }),
  pageBreak(),
];

// ─── SECTIONS ─────────────────────────────────────────────────────────────────
const sections_content = [
  // 1. EXECUTIVE SUMMARY
  h1("1. Executive Summary"),
  para("The Premium Animal Hospital ERP Platform is a comprehensive, bilingual (Arabic/English) veterinary clinic management system developed for Dr. Hatem El Khateeb's Premium Animal Hospital in Egypt. The system replaces a fragmented Excel-based legacy workflow with an integrated digital platform covering all clinic operations from patient intake to financial reporting."),
  para("The platform is built on Flask (Python) with a PostgreSQL database backend, serving 31 operational modules across clinical, administrative, financial, and support functions. It is designed for multi-user concurrent access by up to 30 staff members across various roles, with full Arabic/English bilingual support and integrated AI-powered assistance."),
  sp(),

  // 2. BUSINESS CONTEXT
  h1("2. Business Context & Problem Statement"),
  h2("2.1 Current State"),
  para("Prior to this platform, the clinic operated using:"),
  bullet("Microsoft Excel spreadsheets for patient records, appointments, and invoices"),
  bullet("Paper-based prescription and diagnosis records"),
  bullet("Manual WhatsApp messages for appointment reminders"),
  bullet("Separate cash registers with no integrated financial reporting"),
  bullet("No centralised inventory tracking or low-stock alerts"),
  bullet("No staff payroll or attendance management system"),
  sp(),
  h2("2.2 Business Problems"),
  para("The following problems drove the need for this platform:"),
  bullet("Data loss risk: patient histories stored only in Excel files on single PCs"),
  bullet("Double-booking: no real-time appointment slot visibility"),
  bullet("Revenue leakage: uninvoiced services and untracked inventory shrinkage"),
  bullet("Staff inefficiency: 2-3 hours daily spent on manual reporting"),
  bullet("No audit trail: impossible to trace who changed what in patient records"),
  bullet("No business analytics: owner had no KPI visibility without manual calculations"),
  sp(),
  h2("2.3 Business Goals"),
  bullet("Centralise all clinic data in a single, secure, cloud-ready database"),
  bullet("Reduce administrative overhead by 60% through automation"),
  bullet("Achieve full traceability of every patient interaction, invoice, and inventory movement"),
  bullet("Enable the clinic owner to view real-time business KPIs from any device"),
  bullet("Support clinic growth to multiple branches without re-architecting"),
  sp(),

  // 3. STAKEHOLDERS
  h1("3. Stakeholders"),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2500, 2500, 2360, 2000],
    rows: [
      new TableRow({ children: [
        new TableCell({ borders, width: { size: 2500, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Stakeholder", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
        new TableCell({ borders, width: { size: 2500, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Role", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
        new TableCell({ borders, width: { size: 2360, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Interest", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
        new TableCell({ borders, width: { size: 2000, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Priority", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
      ]}),
      ...[
        ["Dr. Hatem El Khateeb", "Clinic Owner / Super Admin", "Full system visibility, financial reports, staff management", "Critical"],
        ["Receptionist Staff", "Front Desk / Reception", "Appointments, owner & pet management, invoicing", "High"],
        ["Veterinary Doctors", "Doctor / Clinician", "Visit records, diagnoses, prescriptions, AI assistance", "High"],
        ["Nurses / Technicians", "Clinical Support", "Visit workflows, medication dispensing", "High"],
        ["Inventory Manager", "Stock Control", "Item tracking, batch management, reorder alerts", "Medium"],
        ["Finance User", "Accounting", "Invoices, payments, expense tracking, payroll", "High"],
        ["Grooming Staff", "Service Delivery", "Grooming bookings, service records", "Medium"],
        ["Boarding Staff", "Inpatient Care", "Boarding check-in/out, daily care logs", "Medium"],
        ["Pharmacist", "Pharmacy", "Prescription dispensing, drug inventory", "Medium"],
        ["IT / Support Admin", "Technical", "System health, backups, audit logs", "Medium"],
      ].map(([s, r, i, p]) => new TableRow({ children: [
        new TableCell({ borders, width: { size: 2500, type: WidthType.DXA }, shading: { fill: WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: s, size: 20, font: "Arial", bold: true })] })] }),
        new TableCell({ borders, width: { size: 2500, type: WidthType.DXA }, shading: { fill: WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: r, size: 20, font: "Arial" })] })] }),
        new TableCell({ borders, width: { size: 2360, type: WidthType.DXA }, shading: { fill: WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: i, size: 20, font: "Arial" })] })] }),
        new TableCell({ borders, width: { size: 2000, type: WidthType.DXA }, shading: { fill: p === "Critical" ? "FFE0E0" : p === "High" ? "E0F0E0" : GREY, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: p, size: 20, font: "Arial", bold: p === "Critical" })] })] }),
      ]}))
    ]
  }),
  sp(),
  pageBreak(),

  // 4. SCOPE
  h1("4. Project Scope"),
  h2("4.1 In Scope"),
  bullet("Clinical Operations: appointments, visits, SOAP notes, diagnoses, prescriptions, vaccinations, lab requests"),
  bullet("Client & Patient Management: owner CRM, pet records, pet timeline, loyalty points, VIP classification"),
  bullet("Financial Management: invoicing, payments, expense tracking, petty cash, financial reports"),
  bullet("Inventory & Pharmacy: item catalogue, batch tracking, stock movements, reorder alerts, prescription dispensing"),
  bullet("Human Resources: staff profiles, shift management, attendance tracking, payroll with deductions"),
  bullet("Grooming & Boarding: booking management, service pricing, capacity management"),
  bullet("Telemedicine: video consultation sessions via Jitsi integration"),
  bullet("AI Assistant: patient-context AI chat, health alerts, command palette (Gemini 2.5 Flash)"),
  bullet("WhatsApp Integration: automated appointment reminders, vaccine due notifications, invoice alerts"),
  bullet("Reporting & Analytics: financial reports, inventory reports, doctor revenue, Excel exports"),
  bullet("System Administration: user management, role-based access, audit log, automated daily backups"),
  bullet("Bilingual Interface: full Arabic (RTL) and English (LTR) support"),
  bullet("Pet Shop Module: retail products, online orders, payment processing"),
  sp(),
  h2("4.2 Out of Scope (Version 1.0)"),
  bullet("Mobile native application (iOS / Android) — planned for v2.0"),
  bullet("Integration with external veterinary lab systems"),
  bullet("Multi-currency support (EGP only in v1.0)"),
  bullet("Patient-facing owner portal / app"),
  bullet("Insurance claims management"),
  bullet("Radiology / DICOM image management"),
  sp(),

  // 5. FUNCTIONAL REQUIREMENTS
  h1("5. Functional Requirements"),
  h2("5.1 Authentication & Security"),
  bullet("FR-001: System shall authenticate users via username/password with bcrypt hashing (minimum 12 rounds)"),
  bullet("FR-002: System shall lock accounts after 5 consecutive failed login attempts for 15 minutes"),
  bullet("FR-003: System shall enforce role-based access control across all 13 defined roles"),
  bullet("FR-004: System shall maintain a complete audit log of all login, logout, and data-change events"),
  bullet("FR-005: System shall automatically expire sessions after 60 minutes of inactivity"),
  bullet("FR-006: System shall enforce CSRF token validation on all state-changing requests"),
  sp(),
  h2("5.2 Clinical Operations"),
  bullet("FR-010: System shall support appointment scheduling with configurable time slots per doctor"),
  bullet("FR-011: System shall prevent double-booking for the same doctor and time slot"),
  bullet("FR-012: System shall allow visit records with SOAP notes (Subjective, Objective, Assessment, Plan)"),
  bullet("FR-013: System shall generate invoices automatically on visit completion with pre-filled service lines"),
  bullet("FR-014: System shall maintain vaccination records with due-date tracking and automated reminders"),
  bullet("FR-015: System shall support prescription generation linked to the pharmacy dispensing module"),
  bullet("FR-016: System shall maintain complete pet medical history (timeline view)"),
  bullet("FR-017: System shall support telemedicine video sessions via Jitsi"),
  sp(),
  h2("5.3 Financial Operations"),
  bullet("FR-020: System shall generate itemised invoices with tax, discount, and line-item support"),
  bullet("FR-021: System shall track payments by method (cash, card, bank transfer, insurance)"),
  bullet("FR-022: System shall calculate outstanding balances and flag overdue invoices"),
  bullet("FR-023: System shall generate daily, weekly, and monthly revenue reports"),
  bullet("FR-024: System shall support expense tracking by category with budget target monitoring"),
  bullet("FR-025: System shall calculate staff payroll with attendance-based deductions and overtime"),
  bullet("FR-026: System shall export financial reports to Excel (.xlsx) format"),
  sp(),
  h2("5.4 Inventory Management"),
  bullet("FR-030: System shall track inventory items by batch with expiry dates and FIFO dispensing"),
  bullet("FR-031: System shall generate reorder alerts when stock falls at or below reorder level"),
  bullet("FR-032: System shall support multiple warehouses/storage locations"),
  bullet("FR-033: System shall log all stock movements (purchase, dispense, adjustment, return)"),
  bullet("FR-034: System shall provide expiry alerts for items expiring within 30 days"),
  sp(),
  h2("5.5 AI & Automation"),
  bullet("FR-040: System shall provide an AI chat assistant with patient context awareness"),
  bullet("FR-041: System shall generate AI health alerts for overdue vaccinations and pending follow-ups"),
  bullet("FR-042: System shall send automated WhatsApp reminders for appointments 24 hours in advance"),
  bullet("FR-043: System shall send automated WhatsApp notifications for vaccination due dates"),
  bullet("FR-044: System shall support a command palette for quick navigation via keyboard shortcut"),
  sp(),
  pageBreak(),

  // 6. NON-FUNCTIONAL REQUIREMENTS
  h1("6. Non-Functional Requirements"),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [1800, 2500, 5060],
    rows: [
      new TableRow({ children: [
        new TableCell({ borders, width: { size: 1800, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Category", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
        new TableCell({ borders, width: { size: 2500, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Requirement", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
        new TableCell({ borders, width: { size: 5060, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Specification", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
      ]}),
      ...[
        ["Performance", "Page Load Time", "All pages load in under 3 seconds on a local network connection"],
        ["Performance", "Concurrent Users", "Support minimum 30 concurrent users without degradation"],
        ["Availability", "Uptime", "99.5% uptime during clinic operating hours (8:00–22:00)"],
        ["Reliability", "Backup", "Automated daily database backup at 02:00 with 30-day retention"],
        ["Security", "Encryption", "All passwords bcrypt-hashed; session cookies HttpOnly + SameSite=Lax"],
        ["Security", "HTTPS", "All traffic encrypted via TLS 1.2+ in production"],
        ["Usability", "Languages", "Full bilingual Arabic (RTL) + English (LTR) interface"],
        ["Usability", "Browser Support", "Chrome, Firefox, Edge, Safari (latest 2 versions)"],
        ["Scalability", "Data Volume", "Support 100,000+ patient records without query degradation"],
        ["Scalability", "Multi-branch", "Architecture supports adding branches without re-deployment"],
        ["Compliance", "Data Retention", "Patient data retained for minimum 7 years per Egyptian law"],
        ["Maintainability", "Audit Trail", "All data changes logged with user, timestamp, IP, and user-agent"],
      ].map(([cat, req, spec], i) => new TableRow({ children: [
        new TableCell({ borders, width: { size: 1800, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? GREY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: cat, size: 20, font: "Arial", bold: true })] })] }),
        new TableCell({ borders, width: { size: 2500, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? GREY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: req, size: 20, font: "Arial" })] })] }),
        new TableCell({ borders, width: { size: 5060, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? GREY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: spec, size: 20, font: "Arial" })] })] }),
      ]}))
    ]
  }),
  sp(),
  pageBreak(),

  // 7. USE CASES
  h1("7. Key Use Cases"),
  h2("UC-001: Patient Visit Workflow"),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2000, 7360],
    rows: [
      ...[
        ["Actor", "Doctor, Receptionist"],
        ["Precondition", "Owner and pet must exist in the system. Appointment scheduled."],
        ["Main Flow", "1. Receptionist checks patient in via Appointments > Queue\n2. Doctor opens Visit from queue\n3. Doctor records SOAP notes, diagnosis, and treatment\n4. System auto-generates invoice on visit completion\n5. Receptionist collects payment and issues receipt\n6. System updates pet timeline and triggers follow-up reminder"],
        ["Alternate Flow", "Walk-in patient: Receptionist creates emergency visit without prior appointment"],
        ["Postcondition", "Visit record saved, invoice created, audit log updated, WhatsApp notification sent"],
      ].map(([label, value], i) => new TableRow({ children: [
        new TableCell({ borders, width: { size: 2000, type: WidthType.DXA }, shading: { fill: TBLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: label, size: 20, font: "Arial", bold: true })] })] }),
        new TableCell({ borders, width: { size: 7360, type: WidthType.DXA }, shading: { fill: WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: value, size: 20, font: "Arial" })] })] }),
      ]}))
    ]
  }),
  sp(),
  h2("UC-002: Monthly Payroll Generation"),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2000, 7360],
    rows: [
      ...[
        ["Actor", "Finance User, Super Admin"],
        ["Precondition", "Attendance records for the month must be complete. Staff shifts configured."],
        ["Main Flow", "1. Finance User navigates to Payroll > Generate\n2. System pulls attendance records for selected month\n3. System calculates absent days, late count, overtime hours\n4. System pre-fills absence deductions and overtime additions\n5. Finance User reviews and approves each salary slip\n6. System marks salaries as paid and locks the record"],
        ["Postcondition", "Salary slips generated, payroll expense recorded, downloadable PDF generated"],
      ].map(([label, value]) => new TableRow({ children: [
        new TableCell({ borders, width: { size: 2000, type: WidthType.DXA }, shading: { fill: TBLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: label, size: 20, font: "Arial", bold: true })] })] }),
        new TableCell({ borders, width: { size: 7360, type: WidthType.DXA }, shading: { fill: WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: value, size: 20, font: "Arial" })] })] }),
      ]}))
    ]
  }),
  sp(),
  pageBreak(),

  // 8. ACCEPTANCE CRITERIA
  h1("8. Acceptance Criteria"),
  h2("8.1 Go-Live Checklist"),
  bullet("All 31 modules load without 500 errors"),
  bullet("Admin user can log in and all role-based access restrictions are enforced"),
  bullet("A full patient visit workflow (appointment > visit > invoice > payment) completes without error"),
  bullet("Automated WhatsApp reminder sends successfully for a test appointment"),
  bullet("Daily backup runs at 02:00 and a backup file appears in /data/backups/"),
  bullet("All 171 automated tests pass with 0 failures"),
  bullet("Security scan: no hardcoded credentials, HTTPS enforced, CSRF validated"),
  bullet("Bilingual toggle switches interface to Arabic RTL layout correctly"),
  bullet("Clinic owner can view Dashboard KPIs, financial reports, and audit log"),
  sp(),

  // 9. CONSTRAINTS & ASSUMPTIONS
  h1("9. Constraints & Assumptions"),
  h2("9.1 Constraints"),
  bullet("Platform: Windows Server or Ubuntu 22.04 LTS (minimum 8 GB RAM, 4 vCPU, 100 GB SSD)"),
  bullet("Database: PostgreSQL 15+ (primary), SQLite 3.40+ (development/fallback only)"),
  bullet("Network: Reliable local network for multi-user access; internet for AI/WhatsApp features"),
  bullet("Language: Python 3.11+, Node.js 18+ (for document generation tooling)"),
  bullet("Currency: Egyptian Pound (EGP) only in v1.0"),
  sp(),
  h2("9.2 Assumptions"),
  bullet("Staff will receive 4-hour onboarding training before go-live"),
  bullet("All historical data migration from Excel will be performed by the clinic owner"),
  bullet("A dedicated server or cloud VM will be provisioned by the clinic"),
  bullet("Internet access is available for AI assistant and WhatsApp integration features"),
  bullet("Dr. Hatem El Khateeb has authority to approve all business decisions"),
  sp(),

  // 10. RISKS
  h1("10. Risks & Mitigations"),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [3000, 1500, 1500, 3360],
    rows: [
      new TableRow({ children: [
        new TableCell({ borders, width: { size: 3000, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Risk", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
        new TableCell({ borders, width: { size: 1500, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Likelihood", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
        new TableCell({ borders, width: { size: 1500, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Impact", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
        new TableCell({ borders, width: { size: 3360, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Mitigation", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
      ]}),
      ...[
        ["Staff resistance to adopting new system", "Medium", "High", "Phased rollout; run parallel with legacy for 2 weeks; daily training sessions"],
        ["Data loss due to server failure", "Low", "Critical", "Automated daily backups; manual backup before each major update"],
        ["PostgreSQL connection exhaustion under load", "Medium", "High", "Implement connection pooling (psycopg2.pool) in v1.1"],
        ["AI service unavailability (freellmapi)", "Medium", "Low", "All AI features gracefully degrade; core clinical workflow unaffected"],
        ["WhatsApp integration downtime (Wapilot)", "Medium", "Low", "Manual reminder fallback; integration monitored via audit log"],
        ["Default admin password not changed", "High", "Critical", "Mandatory password change on first login enforced in production config"],
      ].map(([risk, like, imp, mit], i) => new TableRow({ children: [
        new TableCell({ borders, width: { size: 3000, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? GREY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: risk, size: 20, font: "Arial" })] })] }),
        new TableCell({ borders, width: { size: 1500, type: WidthType.DXA }, shading: { fill: like === "High" ? "FFE0E0" : like === "Medium" ? "FFF3CD" : "E0F0E0", type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: like, size: 20, font: "Arial" })] })] }),
        new TableCell({ borders, width: { size: 1500, type: WidthType.DXA }, shading: { fill: imp === "Critical" ? "FFE0E0" : imp === "High" ? "FFF3CD" : "E0F0E0", type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: imp, size: 20, font: "Arial" })] })] }),
        new TableCell({ borders, width: { size: 3360, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? GREY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: mit, size: 20, font: "Arial" })] })] }),
      ]}))
    ]
  }),
  sp(),

  // 11. GLOSSARY
  h1("11. Glossary"),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2500, 6860],
    rows: [
      new TableRow({ children: [
        new TableCell({ borders, width: { size: 2500, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Term", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
        new TableCell({ borders, width: { size: 6860, type: WidthType.DXA }, shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Definition", bold: true, size: 20, font: "Arial", color: WHITE })] })] }),
      ]}),
      ...[
        ["ERP", "Enterprise Resource Planning — integrated management of core business processes"],
        ["SOAP Notes", "Subjective, Objective, Assessment, Plan — structured clinical documentation format"],
        ["CSRF", "Cross-Site Request Forgery — security attack prevented by token validation"],
        ["BCrypt", "Password hashing algorithm using adaptive cost factor (rounds=12 in this system)"],
        ["Blueprint", "Flask module pattern for organising related routes and templates"],
        ["DXA", "Document eXtended Attribute units — 1440 DXA = 1 inch, used for Word document sizing"],
        ["Wapilot", "Third-party WhatsApp Business API gateway used for automated messaging"],
        ["freellmapi", "Local AI API proxy providing access to Gemini 2.5 Flash model"],
        ["FIFO", "First In First Out — inventory dispensing method ensuring oldest stock used first"],
        ["KPI", "Key Performance Indicator — measurable value showing how effectively objectives are met"],
        ["VIP Flag", "Classification for high-value owners generating above-average revenue"],
        ["Loyalty Points", "Reward system: 1 point per 10 EGP spent; 100 points = 50 EGP discount"],
      ].map(([term, def], i) => new TableRow({ children: [
        new TableCell({ borders, width: { size: 2500, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? GREY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: term, size: 20, font: "Arial", bold: true })] })] }),
        new TableCell({ borders, width: { size: 6860, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? GREY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: def, size: 20, font: "Arial" })] })] }),
      ]}))
    ]
  }),
  sp(),
];

const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }, { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 360 } } } }] },
    ]
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 32, bold: true, font: "Arial", color: BLUE }, paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 26, bold: true, font: "Arial", color: LBLUE }, paragraph: { spacing: { before: 240, after: 80 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 22, bold: true, font: "Arial", color: "404040" }, paragraph: { spacing: { before: 160, after: 60 }, outlineLevel: 2 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({ children: [
        new Paragraph({
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: LBLUE, space: 4 } },
          children: [
            new TextRun({ text: "Premium Animal Hospital ERP  |  Business Requirements Document  |  v1.0", size: 18, color: "606060", font: "Arial" }),
          ]
        })
      ]})
    },
    footers: {
      default: new Footer({ children: [
        new Paragraph({
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: LBLUE, space: 4 } },
          alignment: AlignmentType.RIGHT,
          children: [
            new TextRun({ text: "Page ", size: 18, color: "606060", font: "Arial" }),
            new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "606060", font: "Arial" }),
            new TextRun({ text: " of ", size: 18, color: "606060", font: "Arial" }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: "606060", font: "Arial" }),
          ]
        })
      ]})
    },
    children: [...coverPage, ...sections_content]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("C:\\vet\\platform\\docs\\BRD_Premium_Animal_Hospital_v1.0.docx", buf);
  console.log("BRD created successfully.");
});
