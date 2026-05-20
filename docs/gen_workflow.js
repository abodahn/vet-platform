/**
 * gen_workflow.js
 * Generate: Workflow & Process Manual — Premium Animal Hospital Platform
 * Run: node gen_workflow.js
 */
"use strict";

const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, ExternalHyperlink,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
  VerticalAlign, PageNumber, PageBreak, TableOfContents,
} = require("docx");
const fs = require("fs");

// ── Colours ───────────────────────────────────────────────────
const BLUE   = "1F4E79";
const LBLUE  = "2E75B6";
const TEAL   = "0E7C86";
const GREEN  = "1A6B3C";
const ORANGE = "7B3F00";
const PURPLE = "4B0082";
const GRAY   = "F0F4F8";
const WHITE  = "FFFFFF";

// ── Helpers ───────────────────────────────────────────────────
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 320, after: 160 },
    children: [new TextRun({ text, font: "Arial", size: 36, bold: true, color: BLUE })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 120 },
    children: [new TextRun({ text, font: "Arial", size: 28, bold: true, color: LBLUE })],
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 200, after: 100 },
    children: [new TextRun({ text, font: "Arial", size: 24, bold: true, color: TEAL })],
  });
}
function para(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 80, after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 22, ...opts })],
  });
}
function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { before: 60, after: 60 },
    children: [new TextRun({ text, font: "Arial", size: 22 })],
  });
}
function step(num, title, detail) {
  return new Paragraph({
    numbering: { reference: "numbers", level: 0 },
    spacing: { before: 80, after: 80 },
    children: [
      new TextRun({ text: `${title} — `, font: "Arial", size: 22, bold: true }),
      new TextRun({ text: detail, font: "Arial", size: 22 }),
    ],
  });
}
function spacer() {
  return new Paragraph({ children: [new TextRun("")], spacing: { before: 60, after: 60 } });
}
function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

// ── Role badge cell ───────────────────────────────────────────
function roleCell(text, color = LBLUE) {
  return new TableCell({
    width: { size: 2200, type: WidthType.DXA },
    shading: { fill: color, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, font: "Arial", size: 18, bold: true, color: WHITE })],
    })],
  });
}
function dataCell(text, width = 3000, shade = false) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: { fill: shade ? GRAY : WHITE, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 1, color: "D0D8E4" },
      bottom: { style: BorderStyle.SINGLE, size: 1, color: "D0D8E4" },
      left: { style: BorderStyle.SINGLE, size: 1, color: "D0D8E4" },
      right: { style: BorderStyle.SINGLE, size: 1, color: "D0D8E4" },
    },
    children: [new Paragraph({
      children: [new TextRun({ text, font: "Arial", size: 20 })],
    })],
  });
}
function hdrCell(text, width = 3000, color = BLUE) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: { fill: color, type: ShadingType.CLEAR },
    margins: { top: 100, bottom: 100, left: 120, right: 120 },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 1, color: "1F4E79" },
      bottom: { style: BorderStyle.SINGLE, size: 1, color: "1F4E79" },
      left: { style: BorderStyle.SINGLE, size: 1, color: "1F4E79" },
      right: { style: BorderStyle.SINGLE, size: 1, color: "1F4E79" },
    },
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, font: "Arial", size: 20, bold: true, color: WHITE })],
    })],
  });
}

// ── Arrow flow item ───────────────────────────────────────────
function flowRow(steps) {
  // steps: [{label, color}]
  const cells = [];
  steps.forEach((s, i) => {
    cells.push(new TableCell({
      width: { size: Math.floor(9360 / steps.length), type: WidthType.DXA },
      shading: { fill: s.color || LBLUE, type: ShadingType.CLEAR },
      margins: { top: 100, bottom: 100, left: 100, right: 100 },
      children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: s.label, font: "Arial", size: 18, bold: true, color: WHITE })],
      })],
    }));
    if (i < steps.length - 1) {
      cells.push(new TableCell({
        width: { size: 300, type: WidthType.DXA },
        shading: { fill: WHITE, type: ShadingType.CLEAR },
        margins: { top: 100, bottom: 100, left: 40, right: 40 },
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "→", font: "Arial", size: 22, bold: true, color: BLUE })],
        })],
      }));
    }
  });
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: steps.flatMap((_, i) => i < steps.length - 1
      ? [Math.floor(9360 / steps.length), 300]
      : [Math.floor(9360 / steps.length)]
    ),
    rows: [new TableRow({ children: cells })],
  });
}

// ── Info box (colored highlight paragraph) ────────────────────
function infoBox(label, text, color = LBLUE) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [new TableRow({
      children: [new TableCell({
        width: { size: 9360, type: WidthType.DXA },
        shading: { fill: color === "green" ? "EAF7EE" : color === "orange" ? "FFF3E0" : color === "red" ? "FFEBEE" : "EBF3FB", type: ShadingType.CLEAR },
        margins: { top: 120, bottom: 120, left: 200, right: 200 },
        borders: {
          top: { style: BorderStyle.SINGLE, size: 3, color: color === "green" ? "1A6B3C" : color === "orange" ? "7B3F00" : color === "red" ? "C62828" : LBLUE },
          bottom: { style: BorderStyle.SINGLE, size: 3, color: color === "green" ? "1A6B3C" : color === "orange" ? "7B3F00" : color === "red" ? "C62828" : LBLUE },
          left: { style: BorderStyle.SINGLE, size: 12, color: color === "green" ? "1A6B3C" : color === "orange" ? "7B3F00" : color === "red" ? "C62828" : LBLUE },
          right: { style: BorderStyle.NONE },
        },
        children: [
          new Paragraph({ children: [new TextRun({ text: label, font: "Arial", size: 20, bold: true, color: color === "green" ? "1A6B3C" : color === "orange" ? "7B3F00" : color === "red" ? "C62828" : BLUE })] }),
          new Paragraph({ children: [new TextRun({ text, font: "Arial", size: 20, color: "2D3748" })], spacing: { before: 60 } }),
        ],
      })],
    })],
  });
}

// ── Simple 2-col table ────────────────────────────────────────
function twoColTable(rows, col1 = 3000, col2 = 6360) {
  const borderStyle = { style: BorderStyle.SINGLE, size: 1, color: "D0D8E4" };
  const borders = { top: borderStyle, bottom: borderStyle, left: borderStyle, right: borderStyle };
  return new Table({
    width: { size: col1 + col2, type: WidthType.DXA },
    columnWidths: [col1, col2],
    rows: rows.map((r, i) => new TableRow({
      children: [
        new TableCell({
          width: { size: col1, type: WidthType.DXA },
          shading: { fill: i === 0 ? BLUE : GRAY, type: ShadingType.CLEAR },
          borders, margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({
            children: [new TextRun({ text: r[0], font: "Arial", size: 20, bold: i === 0, color: i === 0 ? WHITE : "2D3748" })],
          })],
        }),
        new TableCell({
          width: { size: col2, type: WidthType.DXA },
          shading: { fill: i === 0 ? LBLUE : WHITE, type: ShadingType.CLEAR },
          borders, margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({
            children: [new TextRun({ text: r[1], font: "Arial", size: 20, bold: i === 0, color: i === 0 ? WHITE : "2D3748" })],
          })],
        }),
      ],
    })),
  });
}

// ── Multi-col header table ────────────────────────────────────
function multiColTable(headers, rows, widths) {
  const borderStyle = { style: BorderStyle.SINGLE, size: 1, color: "D0D8E4" };
  const borders = { top: borderStyle, bottom: borderStyle, left: borderStyle, right: borderStyle };
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({
        tableHeader: true,
        children: headers.map((h, i) => new TableCell({
          width: { size: widths[i], type: WidthType.DXA },
          shading: { fill: BLUE, type: ShadingType.CLEAR },
          borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ text: h, font: "Arial", size: 20, bold: true, color: WHITE })],
          })],
        })),
      }),
      ...rows.map((row, ri) => new TableRow({
        children: row.map((cell, ci) => new TableCell({
          width: { size: widths[ci], type: WidthType.DXA },
          shading: { fill: ri % 2 === 0 ? WHITE : GRAY, type: ShadingType.CLEAR },
          borders, margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({
            children: [new TextRun({ text: cell, font: "Arial", size: 20 })],
          })],
        })),
      })),
    ],
  });
}

// ═══════════════════════════════════════════════════════════════
// DOCUMENT CONTENT
// ═══════════════════════════════════════════════════════════════

const children = [

  // ── COVER ──────────────────────────────────────────────────
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 1440, after: 240 },
    children: [new TextRun({ text: "🐾  Premium Animal Hospital", font: "Arial", size: 52, bold: true, color: BLUE })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 200 },
    children: [new TextRun({ text: "Dr. Hatem El Khateeb", font: "Arial", size: 28, color: LBLUE })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 600 },
    children: [new TextRun({ text: "Workflow & Process Manual", font: "Arial", size: 44, bold: true, color: TEAL })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LBLUE, space: 1 } },
    children: [new TextRun({ text: "Complete operational workflows — from patient intake to financial close", font: "Arial", size: 24, italics: true, color: "555555" })],
  }),
  spacer(),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 400, after: 80 },
    children: [new TextRun({ text: "Version 1.0  |  May 2026  |  CONFIDENTIAL", font: "Arial", size: 20, color: "777777" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Platform Port 5100  |  PostgreSQL Backend  |  31 Modules", font: "Arial", size: 20, color: "777777" })],
  }),
  pageBreak(),

  // ── TABLE OF CONTENTS ─────────────────────────────────────
  new TableOfContents("Table of Contents", {
    hyperlink: true,
    headingStyleRange: "1-3",
    stylesWithLevels: [],
  }),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 1: PLATFORM OVERVIEW
  // ════════════════════════════════════════════════════════════
  h1("1. Platform Overview"),
  para("Premium Animal Hospital Platform is a full-stack veterinary ERP system built on Flask + PostgreSQL. It manages every operational touchpoint in a modern veterinary clinic — from patient check-in to payroll — in a single unified interface running at port 5100."),
  spacer(),

  h2("1.1 Role Matrix — Who Does What"),
  para("The platform enforces Role-Based Access Control (RBAC) with 13 distinct roles. The table below maps each role to its primary responsibilities:"),
  spacer(),
  multiColTable(
    ["Role", "Primary Responsibilities", "Key Modules"],
    [
      ["super_admin", "Full system access, configuration, user management", "All modules + System Settings"],
      ["clinic_owner", "Business oversight, financial reports, staff management", "Finance, HR, Reports, Accounting"],
      ["branch_manager", "Day-to-day operations, scheduling, approvals", "Appointments, HR, Inventory, Reports"],
      ["doctor", "Clinical care, diagnoses, prescriptions, visits", "Visits, Clinical, Pharmacy, AI Assistant"],
      ["nurse", "Patient preparation, vitals, wound care, boarding", "Visits, Boarding, Inpatient"],
      ["reception", "Check-in, appointments, CRM, invoicing", "CRM, Appointments, Finance"],
      ["inventory_mgr", "Stock management, procurement, FEFO tracking", "Inventory, Procurement, Petshop"],
      ["pharmacist", "Drug dispensing, prescription validation", "Pharmacy, Inventory"],
      ["finance", "Invoices, payments, salary approval, budget", "Finance, Payroll, Accounting"],
      ["groomer", "Grooming appointments, services, notes", "Grooming"],
      ["boarding_staff", "Kennel management, feeding, health monitoring", "Boarding"],
      ["support_admin", "User password resets, audit viewing", "HR (limited), System (limited)"],
      ["auditor", "Read-only access to all financial & audit data", "Finance, Reports, Audit Log"],
    ],
    [2200, 4360, 2800]
  ),
  spacer(),

  h2("1.2 Core Workflow Interconnections"),
  para("The diagram below shows how the primary workflows connect:"),
  spacer(),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [new TableRow({ children: [new TableCell({
      width: { size: 9360, type: WidthType.DXA },
      shading: { fill: "EBF3FB", type: ShadingType.CLEAR },
      margins: { top: 200, bottom: 200, left: 200, right: 200 },
      children: [
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Owner & Pet Registration (CRM)", font: "Arial", size: 22, bold: true, color: BLUE })], spacing: { before: 60, after: 80 } }),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "↓", font: "Arial", size: 28, bold: true, color: LBLUE })], spacing: { before: 0, after: 80 } }),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Appointment Booking → Check-In → Clinical Visit", font: "Arial", size: 22, bold: true, color: TEAL })], spacing: { before: 0, after: 80 } }),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "↓", font: "Arial", size: 28, bold: true, color: LBLUE })], spacing: { before: 0, after: 80 } }),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Diagnosis + Prescription → Pharmacy Dispense", font: "Arial", size: 22, bold: true, color: GREEN })], spacing: { before: 0, after: 80 } }),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "↓", font: "Arial", size: 28, bold: true, color: LBLUE })], spacing: { before: 0, after: 80 } }),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Invoice → Payment → Loyalty Points → Reports", font: "Arial", size: 22, bold: true, color: ORANGE })], spacing: { before: 0, after: 60 } }),
      ],
    })] })],
  }),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 2: PATIENT INTAKE
  // ════════════════════════════════════════════════════════════
  h1("2. Patient Intake Workflow"),
  para("Every clinical interaction begins with patient registration. This workflow is managed by Reception staff."),
  spacer(),

  h2("2.1 New Owner + Pet Registration"),
  infoBox("Who performs this", "Reception staff (role: reception) or any logged-in user with CRM access.", "blue"),
  spacer(),
  step(1, "Navigate to CRM", "Go to CRM → Owners → + New Owner"),
  step(2, "Fill Owner Details", "Full name, phone (required), email, address, city, preferred language (AR/EN)"),
  step(3, "Save Owner Record", "System creates owner with unique ID. WhatsApp reminders will use the phone number."),
  step(4, "Add a Pet", "From the owner detail page, click '+ Add Pet'. Fill: pet name, species, breed, date of birth, sex, weight (kg), colour, microchip number."),
  step(5, "Medical History", "Enter allergies, chronic conditions, vaccination history if known. These feed into the AI patient context automatically."),
  step(6, "Upload Photo", "Optional: upload a pet photo (max 16 MB, JPG/PNG). Appears on all visit pages."),
  step(7, "Confirm", "Pet record is created and linked to owner. System is ready to book an appointment."),
  spacer(),

  h2("2.2 Quick Walk-In Registration"),
  para("For emergency walk-ins where time is critical:"),
  bullet("Use CRM → Quick Register: enter only name + phone to create a minimal owner record"),
  bullet("Book an Emergency appointment immediately"),
  bullet("Complete full registration details later via Edit Owner"),
  spacer(),

  h2("2.3 Owner Loyalty Points — Automatic Accrual"),
  infoBox("Loyalty Rule", "Owners earn 1 point per 10 EGP spent on paid invoices. 100 points = 50 EGP discount on next invoice. Balance shown on owner profile and CRM list.", "green"),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 3: APPOINTMENT WORKFLOW
  // ════════════════════════════════════════════════════════════
  h1("3. Appointment Booking & Check-In"),
  spacer(),

  h2("3.1 Booking a New Appointment"),
  infoBox("Who", "Reception (role: reception) or any staff with appointment access.", "blue"),
  spacer(),
  step(1, "Open Appointments", "Appointments → + New Appointment"),
  step(2, "Select Owner & Pet", "Type owner name to search. Select the pet from the dropdown (filtered by owner)."),
  step(3, "Choose Doctor", "Select from active doctors. The slot picker immediately shows only FREE slots for that doctor on the chosen date. Booked/taken slots are greyed out — double-booking is blocked at both UI and server level."),
  step(4, "Select Time Slot", "30-minute slots 08:00–19:30. Slots blocked if another appointment (non-Cancelled) exists for same doctor at that time."),
  step(5, "Fill Details", "Type (Consultation/Vaccination/Surgery/Grooming/Lab/Follow-up/Emergency), Priority (Normal/Urgent/Emergency), Channel (Walk-in/WhatsApp/Phone/Online), notes."),
  step(6, "Save", "Appointment created with status: Scheduled. Owner receives WhatsApp reminder if configured."),
  spacer(),

  h2("3.2 Day-of-Appointment Flow"),
  multiColTable(
    ["Status", "Action", "Who", "Result"],
    [
      ["Scheduled", "Doctor/date confirmed", "System", "Starting status"],
      ["Confirmed", "Staff clicks Confirm", "Reception", "WhatsApp confirmation sent"],
      ["Checked-in", "Patient arrives, click Check-In", "Reception", "Patient flagged as present"],
      ["Completed", "Visit completed (via Visit module)", "Doctor", "Invoice auto-generated"],
      ["Cancelled", "Owner calls to cancel", "Reception", "Slot freed for rebooking"],
      ["No-Show", "Patient does not arrive", "Reception", "Recorded for reporting"],
    ],
    [1600, 2800, 1800, 3160]
  ),
  spacer(),

  h2("3.3 Rescheduling"),
  step(1, "Open Appointment", "Click the appointment → Edit"),
  step(2, "Change Date/Doctor", "Slot picker reloads for new doctor/date. Original slot is excluded from blocking."),
  step(3, "Save", "Old slot freed; new slot reserved."),
  spacer(),

  h2("3.4 WhatsApp Reminders"),
  bullet("Daily job runs at 09:00 — sends WhatsApp messages to owners with appointments the next day"),
  bullet("Uses Wapilot API (Instance: instance4042) with owner's phone number"),
  bullet("Can be triggered manually via System → WhatsApp → Send Reminders"),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 4: CLINICAL VISIT WORKFLOW
  // ════════════════════════════════════════════════════════════
  h1("4. Clinical Visit Workflow"),
  para("The visit is the core clinical record in the system. It uses SOAP (Subjective, Objective, Assessment, Plan) format."),
  spacer(),

  h2("4.1 Opening a Visit"),
  step(1, "From Appointment", "Click Checked-In appointment → Start Visit. System auto-creates a visit record linked to the appointment, owner, and pet."),
  step(2, "OR Direct Entry", "Visits → + New Visit. Select owner, pet, doctor, visit type, date."),
  step(3, "Visit Page Opens", "Status: Open. All clinical tabs are now available."),
  spacer(),

  h2("4.2 Vital Signs & Examination"),
  step(1, "Record Vitals", "Temperature (°C), heart rate (bpm), respiratory rate, weight, blood pressure, O2 saturation, pain score (0–10)"),
  step(2, "Subjective (S)", "Chief complaint, symptoms, owner-reported history, duration"),
  step(3, "Objective (O)", "Physical exam findings, lab results, imaging notes"),
  step(4, "Assessment (A)", "Working diagnosis — enter in the Diagnosis section below"),
  step(5, "Plan (P)", "Treatment plan, prescriptions, follow-up date"),
  spacer(),

  h2("4.3 AI Clinical Assistant — On-Visit Context"),
  infoBox("AI Patient Context", "When the AI button is opened from a visit page, it automatically loads: pet name, species, breed, age, weight, allergies, chronic conditions, last 5 diagnoses, active prescriptions, and upcoming vaccinations. The AI knows who you are treating without any manual input.", "green"),
  spacer(),
  step(1, "Click AI Button", "Floating blue AI button (bottom-right of visit page)"),
  step(2, "Context Loads", "Panel shows 'Patient context loaded — AI knows [Pet Name]\'s history'"),
  step(3, "Ask Questions", "Type clinical questions: 'What are the differential diagnoses for these symptoms?', 'Calculate ketamine dose for 8kg dog', 'Check drug interactions: metronidazole + phenobarbital'"),
  step(4, "Photo Diagnosis", "Upload wound/eye/skin photo → AI analyses and provides visual diagnosis support"),
  step(5, "Discharge Instructions", "Click 'Discharge Instructions' → AI generates personalised care instructions based on current diagnoses. Copy to give to owner."),
  step(6, "Drug Interaction Check", "Automatically checks active prescriptions when adding a new medication"),
  spacer(),

  h2("4.4 Adding Diagnoses"),
  step(1, "Diagnosis Tab", "Click + Add Diagnosis in visit detail"),
  step(2, "Enter Diagnosis", "ICD-10 or free-text diagnosis, severity (Mild/Moderate/Severe/Critical)"),
  step(3, "Multiple Diagnoses", "Add as many as needed. At least one is required before completing the visit."),
  spacer(),

  h2("4.5 Prescriptions"),
  step(1, "Add Prescription", "From visit: + Add Prescription"),
  step(2, "Medications", "Add one or more medication items: drug name, dosage (mg/kg or fixed), frequency, duration (days), route, instructions"),
  step(3, "Drug Check", "AI automatically checks interactions against existing active prescriptions"),
  step(4, "Save", "Prescription saved as Active status, linked to visit and pet"),
  step(5, "Pharmacy Queue", "Prescription appears in Pharmacy module for dispensing"),
  spacer(),

  h2("4.6 Completing a Visit"),
  infoBox("Before Completing", "At least one diagnosis must exist. The Complete Visit button is disabled until a diagnosis is added.", "orange"),
  spacer(),
  step(1, "Click Complete Visit", "Top-right button on visit page"),
  step(2, "Confirm Prompt", "Confirm: 'Mark this visit as Completed? An invoice will be auto-generated.'"),
  step(3, "Auto Invoice", "System automatically creates a draft invoice for all services in the visit"),
  step(4, "Visit Status", "Changes to Completed. No further clinical edits allowed."),
  step(5, "Next", "Doctor prints discharge summary or reception handles payment"),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 5: PHARMACY WORKFLOW
  // ════════════════════════════════════════════════════════════
  h1("5. Pharmacy & Dispensing Workflow"),
  spacer(),

  h2("5.1 Dispensing a Prescription"),
  infoBox("Who", "Pharmacist (role: pharmacist) or doctor.", "blue"),
  spacer(),
  step(1, "Open Pharmacy", "Pharmacy → Pending Queue. All active prescriptions awaiting dispense appear here."),
  step(2, "Select Prescription", "Click the prescription to view full medication list"),
  step(3, "Check Stock", "System shows current inventory quantity for each medication"),
  step(4, "Dispense", "Click Dispense — system deducts stock from inventory (FEFO batch first)"),
  step(5, "Label", "Optional: print dispensing label with patient name, dosage, instructions"),
  step(6, "Status Update", "Prescription status changes from Active → Dispensed"),
  spacer(),

  h2("5.2 Drug Inventory Link"),
  bullet("Every dispense event updates inventory_transactions with type='dispense'"),
  bullet("Reorder alerts triggered when stock falls below reorder_level"),
  bullet("FEFO (First Expired, First Out) batches are automatically selected"),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 6: INVOICE & PAYMENT WORKFLOW
  // ════════════════════════════════════════════════════════════
  h1("6. Invoice & Payment Workflow"),
  spacer(),

  h2("6.1 Auto-Generated Invoice (Post-Visit)"),
  step(1, "Triggered", "Auto-created when doctor clicks Complete Visit"),
  step(2, "Lines Auto-Filled", "Visit services, consultation fee, lab fees pulled from service catalog"),
  step(3, "Review", "Reception opens invoice: Finance → Invoices → find the new draft"),
  step(4, "Edit if Needed", "Add/remove line items, apply manual discount"),
  step(5, "Send to Owner", "Print PDF or WhatsApp the invoice link"),
  spacer(),

  h2("6.2 Manual Invoice"),
  step(1, "Finance → + New Invoice", "Select owner and pet"),
  step(2, "Add Lines", "Each line: service/product name, quantity, unit price. Lines auto-price from service catalog."),
  step(3, "Discount", "Apply % or EGP discount per line or on total"),
  step(4, "Tax", "VAT applied automatically if configured in clinic settings"),
  step(5, "Save as Draft", "Invoice created with status: Unpaid"),
  spacer(),

  h2("6.3 Loyalty Points Redemption"),
  infoBox("Redeem Rule", "100 loyalty points = 50 EGP discount. Owner must have sufficient balance. Redemption adds a discount line to the invoice automatically.", "green"),
  spacer(),
  step(1, "Owner Detail", "CRM → Owner → Loyalty tab"),
  step(2, "Check Balance", "Shows current points balance and full history"),
  step(3, "Redeem", "Click Redeem Points. Choose how many to redeem (multiples of 100)."),
  step(4, "Discount Applied", "System adds a discount line to the owner's next invoice"),
  step(5, "Balance Updated", "loyalty_balance reduced immediately"),
  spacer(),

  h2("6.4 Recording Payment"),
  step(1, "Open Invoice", "Finance → Invoice → [number]"),
  step(2, "Click Pay", "Enter: payment method (Cash/Card/Bank Transfer/Insurance/Wallet), amount, date, notes"),
  step(3, "Partial Payment", "Enter partial amount — invoice status becomes Partial"),
  step(4, "Full Payment", "Full amount → status: Paid"),
  step(5, "Loyalty Award", "System auto-awards 1 point per 10 EGP to the owner"),
  step(6, "Receipt", "Print receipt PDF or send via WhatsApp"),
  spacer(),

  multiColTable(
    ["Payment Method", "System Action", "Loyalty Points?"],
    [
      ["Cash", "Records full payment immediately", "Yes"],
      ["Card (Visa/MC)", "Records payment with card reference", "Yes"],
      ["Bank Transfer", "Records with transfer reference", "Yes"],
      ["Insurance", "Records insurer name, tracks claim", "No"],
      ["Wallet (Vodafone/Orange)", "Records with transaction ID", "Yes"],
      ["Loyalty Redemption", "Discount line on invoice", "Not earned (redemption)"],
    ],
    [2400, 4360, 2600]
  ),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 7: INVENTORY WORKFLOW
  // ════════════════════════════════════════════════════════════
  h1("7. Inventory Management Workflow"),
  spacer(),

  h2("7.1 Daily Stock Operations"),
  step(1, "Check Dashboard", "Inventory → Dashboard: Shows low-stock alerts, expiring items, recent movements"),
  step(2, "Review Alerts", "Items below reorder_level shown in red. Expiring within 30 days highlighted orange."),
  step(3, "Create Purchase Order", "Click + New PO for items needing reorder → goes to Procurement"),
  spacer(),

  h2("7.2 Receiving Stock (GRN — Goods Received Note)"),
  step(1, "Procurement → GRN", "Link to existing PO or create standalone GRN"),
  step(2, "Enter Batch Details", "Batch number, manufacturing date, expiry date, quantity received, unit cost"),
  step(3, "FEFO Tracking", "System records each batch with expiry. Dispensing always uses earliest-expiry batch first."),
  step(4, "Stock Updated", "inventory_items.quantity increases. inventory_transactions records the receipt."),
  spacer(),

  h2("7.3 Stock Adjustments"),
  bullet("Manual adjustment: Inventory → Items → [item] → Adjust Stock (reason required: Breakage/Expired/Count Correction)"),
  bullet("All adjustments are logged in inventory_transactions with user, reason, and timestamp"),
  bullet("Expired stock removal: mark batch as expired → quantity zeroed with audit trail"),
  spacer(),

  h2("7.4 Petshop Integration"),
  step(1, "Petshop products share inventory", "A sold product at Petshop deducts from the same inventory batch"),
  step(2, "POS sales", "Petshop → New Order → add products → pay → stock auto-deducted"),
  step(3, "Sales reports", "Reports → Petshop: top sellers, revenue by product, daily sales chart"),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 8: GROOMING WORKFLOW
  // ════════════════════════════════════════════════════════════
  h1("8. Grooming Workflow"),
  spacer(),
  step(1, "Book Grooming", "Grooming → + New Appointment → Select owner/pet, groomer, service (Bath/Full Groom/Trim/Nail/etc.), time slot"),
  step(2, "Check-In", "Day of appointment: mark pet as Arrived"),
  step(3, "Service Notes", "Add groomer notes: coat condition, special instructions, owner requests"),
  step(4, "Complete", "Mark as Completed → auto-generates grooming invoice"),
  step(5, "Payment", "Processed via Finance module (same payment flow as clinical)"),
  spacer(),
  infoBox("Grooming Packages", "Recurring grooming packages can be set up per pet (e.g., monthly full groom). Package sessions are tracked and auto-deducted on each visit.", "blue"),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 9: BOARDING WORKFLOW
  // ════════════════════════════════════════════════════════════
  h1("9. Boarding / Kennel Workflow"),
  spacer(),

  h2("9.1 Boarding Check-In"),
  step(1, "Open Boarding", "Boarding → + New Stay"),
  step(2, "Pet Details", "Select owner/pet, select kennel/room, check-in date, expected check-out date"),
  step(3, "Medical Notes", "Record any medications, feeding instructions, behavioural notes"),
  step(4, "Daily Care Log", "Boarding staff record: feeding times, exercise, health observations, weight"),
  step(5, "Health Alert", "If symptoms observed, boarding staff creates a clinical alert → doctor is notified"),
  spacer(),

  h2("9.2 Boarding Check-Out"),
  step(1, "Mark Departure", "Boarding → [Stay] → Check Out. Enter actual departure date."),
  step(2, "Invoice Generated", "System calculates boarding fees (daily rate × nights)"),
  step(3, "Additional Charges", "Any medications given, vet visits during stay are added as line items"),
  step(4, "Payment", "Same as standard invoice payment flow"),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 10: HR & PAYROLL WORKFLOW
  // ════════════════════════════════════════════════════════════
  h1("10. HR & Payroll Workflow"),
  spacer(),

  h2("10.1 Staff Management"),
  step(1, "Add Staff", "HR → Staff → + New Staff: full name, username, role, email, phone, join date, national ID, contract type"),
  step(2, "Assign Shift", "HR → Shifts → assign shift template (start/end time, break minutes) to staff member with effective date"),
  step(3, "Set Salary Grade", "Payroll → Grades: set basic salary and overtime rate per role. Applied to all staff in that role during bulk generate."),
  spacer(),

  h2("10.2 Attendance Tracking"),
  step(1, "Daily Check-In", "HR → Attendance → Mark attendance. Status: Present / Late / Absent / On-Leave."),
  step(2, "Hours Worked", "Enter actual hours worked if different from shift (enables overtime calculation)"),
  step(3, "Leave Management", "HR → Leave: approve/reject leave requests. Approved leave days excluded from absence deductions."),
  spacer(),

  h2("10.3 Payroll Cycle — Month End"),
  infoBox("Attendance → Salary Integration", "When generating salary records, the system auto-pulls attendance data: absent days become absence_deduction (absent_days ÷ working_days × basic_salary) and overtime hours are pre-filled from hours_worked beyond the standard shift.", "green"),
  spacer(),
  step(1, "Bulk Generate", "Payroll → Bulk Generate → select year/month → system creates draft salary records for all active staff without existing records"),
  step(2, "Auto-Fill", "Each record: basic (from grade), overtime hours (from attendance), absence deduction (auto-calculated)"),
  step(3, "Review Drafts", "Finance/manager reviews each record. Adjust allowances, add manual deductions, edit overtime if needed."),
  step(4, "Approve", "Manager clicks Approve. Status: Draft → Approved"),
  step(5, "Pay", "Finance clicks Pay. Enter payment method, date → status: Paid"),
  step(6, "Export", "Payroll → Salaries → Export Excel (.xlsx) for accounting / bank upload"),
  spacer(),
  multiColTable(
    ["Field", "Source", "Editable?"],
    [
      ["Basic Salary", "Salary grade table (role-based)", "Yes — override per record"],
      ["Allowances", "Manual entry", "Yes"],
      ["Overtime Hours", "Attendance records (auto-pulled)", "Yes — override"],
      ["Overtime Rate", "Salary grade table", "Yes"],
      ["Absence Deduction", "Absent days × (basic ÷ working days)", "Yes — override"],
      ["Tax Deduction", "Manual entry (no auto-tax in v1)", "Yes"],
      ["Gross", "basic + allowances + (OT hrs × OT rate)", "Calculated"],
      ["Net", "gross − deductions − absence − tax", "Calculated"],
    ],
    [2800, 4000, 2560]
  ),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 11: FINANCE & ACCOUNTING WORKFLOW
  // ════════════════════════════════════════════════════════════
  h1("11. Finance & Accounting Workflow"),
  spacer(),

  h2("11.1 Daily Finance Tasks"),
  step(1, "Finance Dashboard", "Finance → Dashboard: today's revenue, pending invoices, cash vs card breakdown"),
  step(2, "Process Payments", "Open unpaid invoices → process any walk-in payments"),
  step(3, "Record Expenses", "Finance → Expenses → + New Expense: amount, category, vendor, receipt photo"),
  step(4, "Petty Cash", "Finance → Petty Cash: track small cash disbursements with running balance"),
  spacer(),

  h2("11.2 Budget Monitoring"),
  step(1, "Set Budgets", "Accounting → Budget: edit monthly EGP targets per category (Staff, Drugs, Utilities, Marketing, Equipment, Other)"),
  step(2, "Dashboard", "Accounting → Dashboard: budget vs actual bar chart. Red = over budget, Green = under"),
  step(3, "Drill Down", "Click any category to see individual expense transactions"),
  spacer(),

  h2("11.3 Monthly Financial Close"),
  step(1, "Reports", "Finance → Reports: filter by date range → total revenue, collected, outstanding"),
  step(2, "Export", "Click Export Excel → .xlsx file with full invoice/payment breakdown"),
  step(3, "P&L View", "Accounting → P&L: revenue vs expenses by category for the period"),
  step(4, "Doctor Revenue", "Reports → Doctor Revenue: see per-doctor revenue breakdown by service type"),
  step(5, "Archive", "Save reports to shared drive. System retains full history."),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 12: REPORTS WORKFLOW
  // ════════════════════════════════════════════════════════════
  h1("12. Reports & Analytics Workflow"),
  spacer(),
  multiColTable(
    ["Report", "Location", "Filters", "Export"],
    [
      ["Financial Summary", "Finance → Reports", "Date range", "CSV, Excel"],
      ["Doctor Revenue", "Reports → Doctor Revenue", "Date range, doctor", "—"],
      ["Inventory Report", "Reports → Inventory", "Category, status", "CSV, Excel"],
      ["Clinical Report", "Reports → Clinical", "Date range, species, vet", "—"],
      ["Payroll Summary", "Payroll → Salaries", "Year, month, status", "Excel"],
      ["Petshop Sales", "Petshop → Reports", "Date range", "—"],
      ["Audit Log", "System → Audit Log", "User, action, date", "—"],
      ["Attendance Summary", "HR → Attendance", "User, month", "—"],
      ["Custom Report Builder", "Reports → Builder", "Any field/table", "CSV"],
    ],
    [2200, 2800, 2360, 1800 + 200]
  ),
  spacer(),

  h2("12.1 Doctor Revenue Report — Detail"),
  para("Navigate to Reports → Doctor Revenue. Select a date range. The report shows:"),
  bullet("Total invoiced per doctor (all their visit invoices)"),
  bullet("Total collected (paid invoices only)"),
  bullet("Pending/outstanding amount"),
  bullet("Breakdown by service type (Consultation, Surgery, Lab, Vaccination, etc.)"),
  bullet("Bar chart for visual comparison across doctors"),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 13: SYSTEM ADMINISTRATION WORKFLOW
  // ════════════════════════════════════════════════════════════
  h1("13. System Administration Workflow"),
  spacer(),

  h2("13.1 Backup & Restore"),
  infoBox("Auto-Backup", "System runs automated backup every day at 02:00 AM. Backups are stored in platform/data/backups/ with timestamp in filename.", "blue"),
  spacer(),
  step(1, "Manual Backup", "System → Backup → Create Backup Now"),
  step(2, "View Backups", "System → Backup Manager: list of all backup files with size and date"),
  step(3, "Download", "Click Download to save a backup copy off-server"),
  step(4, "Restore (SQLite)", "Click Restore → confirm modal → system saves pre-restore snapshot → replaces DB file → restart recommended"),
  step(5, "PostgreSQL Restore", "System shows message: use pg_restore or hosting provider tools. Provide the backup file to DBA."),
  spacer(),

  h2("13.2 User Management"),
  step(1, "Create User", "HR → Staff → + New Staff (creates user account simultaneously)"),
  step(2, "Deactivate", "HR → Staff → [user] → Deactivate. User cannot log in. Records retained."),
  step(3, "Reset Password", "HR → Staff → [user] → Reset Password (admin enters new password, min 12 characters)"),
  step(4, "Change Role", "System → Roles & Permissions → change role assignment"),
  spacer(),

  h2("13.3 Clinic Settings"),
  step(1, "Settings → Clinic Info", "Name (Arabic & English), address, phone, email, logo, working hours"),
  step(2, "Settings → Financial", "Currency (EGP), tax rate %, invoice number prefix"),
  step(3, "Settings → Notifications", "WhatsApp reminder timing, templates, enable/disable per event type"),
  step(4, "Settings → Security", "Session timeout, password policy, allowed IP ranges"),
  spacer(),

  h2("13.4 Audit Log"),
  para("Every significant action in the platform is recorded in the audit log:"),
  bullet("User login / logout"),
  bullet("Invoice created, edited, paid"),
  bullet("Salary approved / paid"),
  bullet("Stock adjusted"),
  bullet("Password changed / reset"),
  bullet("Settings modified"),
  para("Access: System → Audit Log. Filter by user, action type, date range. Read-only — cannot be modified."),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 14: TELEMEDICINE & PETSY WORKFLOW
  // ════════════════════════════════════════════════════════════
  h1("14. Telemedicine & Petsy Chat Widget"),
  spacer(),

  h2("14.1 Telemedicine Consultations"),
  step(1, "Doctor Books Session", "Telemedicine → + New Session: select owner/pet, duration, video link (Zoom/Meet)"),
  step(2, "Owner Notified", "WhatsApp message sent with session link and time"),
  step(3, "Conduct Session", "Doctor joins video call, records notes in the telemedicine session"),
  step(4, "Clinical Notes", "After session, doctor can create a full visit record linked to the telemedicine session"),
  step(5, "Invoice", "Telemedicine consultation fee invoiced same as in-clinic visit"),
  spacer(),

  h2("14.2 Petsy — Owner-Facing Chat Widget"),
  para("Petsy is an AI chatbot widget that can be embedded on the clinic's public website. Owners can ask questions 24/7."),
  bullet("Endpoint: POST /petsy/chat — no authentication required (rate-limited)"),
  bullet("Powered by Gemini 2.5 Flash via freellmapi proxy"),
  bullet("Responds in Arabic or English based on owner's message"),
  bullet("Handles: appointment questions, general vet advice, clinic hours, contact info"),
  bullet("Cannot access patient records (no login) — general information only"),
  spacer(),
  infoBox("Embed Code", "Add <script src='https://your-platform-url/petsy/widget.js'></script> to your clinic website to show the chat bubble.", "blue"),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 15: END-TO-END WORKFLOW SUMMARY
  // ════════════════════════════════════════════════════════════
  h1("15. Complete End-to-End Patient Journey"),
  para("The following table maps the full journey of a patient from first contact to payment, including all staff roles and system actions:"),
  spacer(),
  multiColTable(
    ["Stage", "Action", "Staff Role", "System Module", "Output"],
    [
      ["1. First Contact", "Owner calls / walks in", "Reception", "CRM", "Owner record created"],
      ["2. Pet Registration", "Pet details entered", "Reception", "CRM → Pets", "Pet profile with medical history"],
      ["3. Appointment", "Slot booked, doctor assigned", "Reception", "Appointments", "Appointment: Scheduled"],
      ["4. Reminder", "WhatsApp reminder sent (D-1)", "Automated", "WhatsApp / Wapilot", "Owner reminded"],
      ["5. Check-In", "Patient arrives, marked checked-in", "Reception", "Appointments", "Status: Checked-in"],
      ["6. Visit Opens", "Doctor starts examination", "Doctor", "Visits", "Open visit record"],
      ["7. Vitals", "Temperature, HR, weight recorded", "Nurse/Doctor", "Visits → Vitals", "Vitals saved to visit"],
      ["8. AI Consult", "Doctor asks AI for clinical support", "Doctor", "AI Assistant", "Clinical recommendations"],
      ["9. Diagnosis", "Diagnosis added (ICD-10/free text)", "Doctor", "Visits → Diagnosis", "Diagnosis record"],
      ["10. Prescription", "Medications prescribed", "Doctor", "Visits → Prescriptions", "Prescription: Active"],
      ["11. Pharmacy", "Pharmacist dispenses medications", "Pharmacist", "Pharmacy", "Stock deducted; Prescription: Dispensed"],
      ["12. Complete Visit", "Doctor marks visit done", "Doctor", "Visits", "Visit: Completed; Invoice auto-created"],
      ["13. Invoice Review", "Reception reviews/edits invoice", "Reception", "Finance", "Invoice: Unpaid"],
      ["14. Payment", "Owner pays (cash/card/etc.)", "Reception", "Finance", "Invoice: Paid; Loyalty points awarded"],
      ["15. Receipt", "Receipt printed or WhatsApp'd", "Reception", "Finance", "Owner has receipt"],
      ["16. Reports", "Manager reviews daily revenue", "branch_manager", "Reports", "Business intelligence"],
    ],
    [1200, 2400, 1600, 1800, 2360]
  ),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 16: COMMON SCENARIOS & TROUBLESHOOTING
  // ════════════════════════════════════════════════════════════
  h1("16. Common Scenarios & Troubleshooting"),
  spacer(),

  h2("16.1 Scenario: Emergency Walk-In"),
  bullet("No prior appointment needed — start at CRM → Quick Register"),
  bullet("Create owner + pet record (minimum: name + phone)"),
  bullet("Go directly to Visits → + New Visit (type: Emergency)"),
  bullet("Appointment can be back-created if needed for reporting"),
  spacer(),

  h2("16.2 Scenario: Owner Disputes Invoice"),
  step(1, "Open Invoice", "Finance → find invoice number"),
  step(2, "View History", "See all line items, who added them, and when"),
  step(3, "Edit if Error", "Click Edit Invoice → adjust lines → save"),
  step(4, "Add Note", "Add resolution note in invoice notes field"),
  step(5, "If Refund Needed", "Create a credit note (negative value invoice) linked to original"),
  spacer(),

  h2("16.3 Scenario: Doctor Leaving the Practice"),
  step(1, "Reassign Appointments", "Appointments → filter by doctor → reassign each to new doctor"),
  step(2, "Complete Open Visits", "Visits → filter status: Open → assign to covering doctor"),
  step(3, "Deactivate Account", "HR → Staff → [doctor] → Deactivate (records preserved, login disabled)"),
  step(4, "Final Payroll", "Generate final salary record for their last month pro-rata"),
  spacer(),

  h2("16.4 Scenario: Drug Stock Runs Out During Dispense"),
  step(1, "Pharmacy alert", "System shows insufficient stock warning"),
  step(2, "Create PO", "Inventory → + New PO for the drug immediately"),
  step(3, "Substitute", "Doctor prescribes equivalent alternative"),
  step(4, "Partial Dispense", "Dispense available quantity; mark remainder as pending"),
  spacer(),

  h2("16.5 Common Error Codes"),
  multiColTable(
    ["Error", "Cause", "Fix"],
    [
      ["Slot not available", "Doctor already booked at that time", "Choose different time or doctor"],
      ["Cannot complete visit", "No diagnosis added", "Add at least one diagnosis first"],
      ["Insufficient stock", "Drug quantity below requested", "Check Inventory; create PO or substitute"],
      ["CSRF token invalid", "Session expired or form re-submitted", "Refresh page and try again"],
      ["Session expired", "30-minute inactivity timeout", "Log in again (data saved)"],
      ["AI service unavailable", "freellmapi proxy not running", "Check localhost:3001 is running"],
      ["WhatsApp failed", "Wapilot instance offline or number invalid", "Check System → WhatsApp Status"],
    ],
    [2400, 3200, 3760]
  ),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // SECTION 17: KEY KEYBOARD SHORTCUTS & TIPS
  // ════════════════════════════════════════════════════════════
  h1("17. Quick Reference — URLs & Navigation"),
  spacer(),
  multiColTable(
    ["Module", "URL Path", "Shortcut Description"],
    [
      ["Dashboard", "/", "Main launcher with all module tiles"],
      ["CRM — Owners", "/crm/owners", "Search owners by name/phone"],
      ["New Appointment", "/appointments/new", "Book new appointment"],
      ["Today's Schedule", "/appointments/schedule", "Day view of all appointments"],
      ["New Visit", "/visits/new", "Start clinical visit directly"],
      ["AI Assistant", "/ai/", "Standalone AI chat (no patient context)"],
      ["Inventory", "/inventory/items", "Stock levels and alerts"],
      ["Finance Dashboard", "/finance/", "Revenue overview"],
      ["New Invoice", "/finance/invoices/new", "Manual invoice creation"],
      ["Payroll", "/payroll/", "Salary dashboard"],
      ["Bulk Generate Payroll", "/payroll/bulk-generate", "Generate all staff salaries (POST)"],
      ["Doctor Revenue", "/reports/doctor-revenue", "Per-doctor revenue report"],
      ["Budget Editor", "/accounting/", "Edit monthly budget targets"],
      ["Backup Manager", "/system/backup", "Backup and restore"],
      ["Audit Log", "/system/audit-log", "Full action history"],
      ["Settings", "/settings/", "Clinic configuration"],
    ],
    [2400, 3200, 3760]
  ),
  spacer(),
  pageBreak(),

  // ════════════════════════════════════════════════════════════
  // APPENDIX
  // ════════════════════════════════════════════════════════════
  h1("Appendix A: Workflow Checklists"),
  spacer(),

  h2("Morning Opening Checklist"),
  bullet("Log in and review Today's Schedule (Appointments → Schedule)"),
  bullet("Check inventory alerts (Inventory → Dashboard — any red alerts?)"),
  bullet("Check pending pharmacy queue (Pharmacy → Pending)"),
  bullet("Confirm doctor availability and reassign if needed"),
  bullet("Verify WhatsApp reminders were sent for today's appointments (System → Logs)"),
  spacer(),

  h2("End-of-Day Closing Checklist"),
  bullet("Complete all open visits (Visits → Open → action required)"),
  bullet("Process all pending payments (Finance → Invoices → Unpaid)"),
  bullet("Count petty cash and record balance"),
  bullet("Review any stock adjustment needs"),
  bullet("Check for boarding daily logs (Boarding → Current Stays)"),
  bullet("Ensure backup ran (System → Backup — check last backup timestamp)"),
  spacer(),

  h2("Month-End Checklist"),
  bullet("Generate payroll for all staff (Payroll → Bulk Generate)"),
  bullet("Review and approve all salary records"),
  bullet("Run financial report for the month (Finance → Reports)"),
  bullet("Export to Excel and send to accountant"),
  bullet("Review Doctor Revenue report"),
  bullet("Check budget vs actual (Accounting → Dashboard)"),
  bullet("Reconcile petty cash"),
  bullet("Archive monthly backup off-server"),
  spacer(),

  // ── FOOTER MATTER ─────────────────────────────────────────
  new Paragraph({
    spacing: { before: 320 },
    border: { top: { style: BorderStyle.SINGLE, size: 4, color: LBLUE, space: 4 } },
    children: [
      new TextRun({ text: "Premium Animal Hospital Platform — Workflow & Process Manual v1.0  |  Confidential  |  May 2026", font: "Arial", size: 18, color: "777777" }),
    ],
  }),
];

// ═══════════════════════════════════════════════════════════════
// ASSEMBLE DOCUMENT
// ═══════════════════════════════════════════════════════════════

const doc = new Document({
  creator: "Premium Animal Hospital Platform",
  title:   "Workflow & Process Manual",
  description: "Complete operational workflows — Premium Animal Hospital Platform",

  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "•",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }, {
          level: 1, format: LevelFormat.BULLET, text: "◦",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1080, hanging: 360 } } },
        }],
      },
      {
        reference: "numbers",
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: "%1.",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
    ],
  },

  styles: {
    default: {
      document: { run: { font: "Arial", size: 22 } },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: BLUE },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: LBLUE },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 },
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: TEAL },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 },
      },
    ],
  },

  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          children: [
            new TextRun({ text: "Premium Animal Hospital — Workflow & Process Manual", font: "Arial", size: 18, color: LBLUE }),
            new TextRun({ text: "\t\tv1.0 — May 2026", font: "Arial", size: 18, color: "999999" }),
          ],
          tabStops: [{ type: "right", position: 9360 }],
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "DDDDDD", space: 4 } },
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          children: [
            new TextRun({ text: "Page ", font: "Arial", size: 18, color: "999999" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 18, color: "999999" }),
            new TextRun({ text: " of ", font: "Arial", size: 18, color: "999999" }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], font: "Arial", size: 18, color: "999999" }),
            new TextRun({ text: "\t\tCONFIDENTIAL — Internal Use Only", font: "Arial", size: 18, color: "BBBBBB" }),
          ],
          tabStops: [{ type: "right", position: 9360 }],
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: "DDDDDD", space: 4 } },
        })],
      }),
    },
    children,
  }],
});

// ── Write ──────────────────────────────────────────────────────
Packer.toBuffer(doc).then(buf => {
  const out = "Workflow_Process_Manual_v1.0.docx";
  fs.writeFileSync(out, buf);
  console.log(`✅  Created: ${out}  (${(buf.length / 1024).toFixed(0)} KB)`);
}).catch(err => {
  console.error("❌  Error:", err);
  process.exit(1);
});
