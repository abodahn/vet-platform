const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak, LevelFormat
} = require('docx');
const fs = require('fs');

const BLUE="1F4E79",LBLUE="2E75B6",TBLUE="D6E4F0",GREY="F2F2F2",WHITE="FFFFFF",BLACK="000000",GREEN="1A6B3A",LGREEN="E8F5E9";
const border={style:BorderStyle.SINGLE,size:1,color:"CCCCCC"};
const borders={top:border,bottom:border,left:border,right:border};

const h1=(t)=>new Paragraph({heading:HeadingLevel.HEADING_1,spacing:{before:360,after:120},border:{bottom:{style:BorderStyle.SINGLE,size:6,color:LBLUE,space:4}},children:[new TextRun({text:t,bold:true,size:32,color:BLUE,font:"Arial"})]});
const h2=(t)=>new Paragraph({heading:HeadingLevel.HEADING_2,spacing:{before:240,after:80},children:[new TextRun({text:t,bold:true,size:26,color:LBLUE,font:"Arial"})]});
const h3=(t)=>new Paragraph({heading:HeadingLevel.HEADING_3,spacing:{before:160,after:60},children:[new TextRun({text:t,bold:true,size:22,color:"404040",font:"Arial"})]});
const para=(t,opts={})=>new Paragraph({spacing:{after:120},children:[new TextRun({text:t,size:22,font:"Arial",...opts})]});
const bullet=(t,lvl=0)=>new Paragraph({numbering:{reference:"bullets",level:lvl},spacing:{after:60},children:[new TextRun({text:t,size:22,font:"Arial"})]});
const num=(t,lvl=0)=>new Paragraph({numbering:{reference:"numbers",level:lvl},spacing:{after:80},children:[new TextRun({text:t,size:22,font:"Arial"})]});
const sp=(n=1)=>new Paragraph({spacing:{after:n*80},children:[new TextRun("")]});
const pb=()=>new Paragraph({children:[new PageBreak()]});

function tip(text) {
  return new Table({
    width:{size:9360,type:WidthType.DXA},columnWidths:[9360],
    rows:[new TableRow({children:[new TableCell({borders:{top:{style:BorderStyle.SINGLE,size:2,color:"2E75B6"},bottom:{style:BorderStyle.SINGLE,size:2,color:"2E75B6"},left:{style:BorderStyle.SINGLE,size:10,color:"2E75B6"},right:{style:BorderStyle.SINGLE,size:2,color:"2E75B6"}},width:{size:9360,type:WidthType.DXA},shading:{fill:TBLUE,type:ShadingType.CLEAR},margins:{top:100,bottom:100,left:160,right:160},children:[new Paragraph({children:[new TextRun({text:"TIP:  ",bold:true,size:20,font:"Arial",color:LBLUE}),new TextRun({text,size:20,font:"Arial",color:BLACK})]})]})]}) ]
  });
}

function makeTable(headers, rows, widths) {
  const totalW=widths.reduce((a,b)=>a+b,0);
  return new Table({
    width:{size:totalW,type:WidthType.DXA},columnWidths:widths,
    rows:[
      new TableRow({children:headers.map((h,i)=>new TableCell({borders,width:{size:widths[i],type:WidthType.DXA},shading:{fill:BLUE,type:ShadingType.CLEAR},margins:{top:80,bottom:80,left:120,right:120},children:[new Paragraph({children:[new TextRun({text:h,bold:true,size:20,font:"Arial",color:WHITE})]})]})) }),
      ...rows.map((row,ri)=>new TableRow({children:row.map((c,ci)=>new TableCell({borders,width:{size:widths[ci],type:WidthType.DXA},shading:{fill:ri%2===0?GREY:WHITE,type:ShadingType.CLEAR},margins:{top:80,bottom:80,left:120,right:120},children:[new Paragraph({children:[new TextRun({text:c,size:20,font:"Arial"})]})]})) }))
    ]
  });
}

const cover=[
  sp(8),
  new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:80},children:[new TextRun({text:"USER GUIDE & OPERATIONS MANUAL",size:44,bold:true,color:BLUE,font:"Arial"})]}),
  new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:80},children:[new TextRun({text:"Premium Animal Hospital ERP Platform",size:32,color:LBLUE,font:"Arial"})]}),
  new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:200},children:[new TextRun({text:"Dr. Hatem El Khateeb  |  مستشفى بريميوم للحيوانات",size:24,color:"606060",font:"Arial"})]}),
  sp(2),
  makeTable(["Field","Detail"],[
    ["Version","1.0"],["Date","May 2026"],["Audience","All clinic staff"],["Language","English (Arabic interface also available)"],["Support","System Administrator"],
  ],[4000,5360]),
  pb(),
];

const content=[
  h1("1. Getting Started"),
  h2("1.1 Accessing the Platform"),
  para("Open your web browser and navigate to the clinic platform URL (provided by your system administrator). The platform works best with Google Chrome, Firefox, or Microsoft Edge (latest versions)."),
  sp(),
  h2("1.2 Logging In"),
  num("Enter your username and password in the login screen"),
  num("Select your preferred language (English / Arabic) and theme"),
  num("Click Login — you will be taken to the Dashboard"),
  sp(),
  tip("If you see 'Too many failed attempts', your account is temporarily locked for 15 minutes. Contact your administrator if this happens frequently."),
  sp(),
  h2("1.3 The Dashboard"),
  para("The Dashboard shows your clinic's key metrics at a glance:"),
  bullet("Today's appointments and open visits"),
  bullet("Revenue and unpaid invoices"),
  bullet("Low stock alerts and expiring medicines"),
  bullet("Overdue vaccinations"),
  bullet("AI Smart Insights — click Refresh to update"),
  sp(),
  h2("1.4 Navigation"),
  para("The top navigation bar provides quick access to all modules. You can also use the Command Palette (press Ctrl+K or click the search icon) to jump to any page instantly."),
  sp(),
  h2("1.5 Changing Language"),
  para("Click the Language toggle in the top bar to switch between English (LTR) and Arabic (RTL). Your preference is saved automatically."),
  sp(),pb(),

  h1("2. Patient Intake Workflow"),
  h2("2.1 Registering a New Owner"),
  num("Go to CRM > Owners > New Owner"),
  num("Fill in: Full Name (required), Phone (required), Email, Address, Species preference"),
  num("Check VIP flag if applicable"),
  num("Click Save — the owner record is created"),
  sp(),
  h2("2.2 Registering a New Pet"),
  num("From the Owner detail page, click Add Pet"),
  num("Fill in: Pet Name, Species, Breed, Date of Birth, Gender, Colour, Weight, Microchip number"),
  num("Add any known allergies or chronic conditions"),
  num("Click Save"),
  sp(),
  tip("You can view a pet's complete medical history (visits, vaccinations, invoices) by clicking the Timeline tab on the Pet detail page."),
  sp(),
  h2("2.3 Booking an Appointment"),
  num("Go to Appointments > New Appointment"),
  num("Select Owner, then Pet from the dropdown"),
  num("Select Doctor, Date, and Time Slot — only free slots are shown"),
  num("Enter the reason for visit"),
  num("Click Book — a WhatsApp confirmation is sent automatically"),
  sp(),pb(),

  h1("3. Clinical Workflow"),
  h2("3.1 Starting a Visit"),
  num("Go to Appointments > Today's Queue"),
  num("Find the patient and click Check In — status changes to In Progress"),
  num("The Doctor opens the Visit from the queue or from Visits > Active Visits"),
  sp(),
  h2("3.2 Recording a Visit (SOAP Notes)"),
  para("The visit form uses the standard SOAP format:"),
  bullet("Subjective (S): Owner's complaint and history as described"),
  bullet("Objective (O): Physical examination findings, vital signs, measurements"),
  bullet("Assessment (A): Diagnoses, differential diagnoses"),
  bullet("Plan (P): Treatment plan, medications, follow-up instructions"),
  sp(),
  h2("3.3 Adding a Diagnosis"),
  num("In the visit form, scroll to Diagnoses section"),
  num("Type or search for the diagnosis"),
  num("Add ICD code if applicable"),
  num("Multiple diagnoses can be added per visit"),
  sp(),
  h2("3.4 Creating a Prescription"),
  num("From the visit page, click Add Prescription"),
  num("Add each medication: Drug name, Dose, Frequency, Duration, Instructions"),
  num("Save — the prescription is linked to the visit and available in Pharmacy"),
  sp(),
  h2("3.5 Completing a Visit"),
  num("Review all notes and diagnoses"),
  num("Click Complete Visit"),
  num("The system automatically generates an invoice with the consultation fee pre-filled"),
  num("Redirect to invoice for review before presenting to the owner"),
  sp(),
  tip("The AI Assistant button (robot icon) on the visit page gives you patient context — the AI already knows the pet's history, active prescriptions, and due vaccinations."),
  sp(),pb(),

  h1("4. Finance & Invoicing"),
  h2("4.1 Creating an Invoice"),
  num("Go to Finance > Invoices > New Invoice"),
  num("Select Owner"),
  num("Add line items: Description, Quantity, Unit Price, Discount"),
  num("Apply tax if applicable"),
  num("Click Save — invoice status is Unpaid"),
  sp(),
  h2("4.2 Recording a Payment"),
  num("Open the invoice"),
  num("Click Record Payment"),
  num("Select payment method: Cash, Card, Bank Transfer, Insurance"),
  num("Enter amount received"),
  num("Click Save — invoice status updates to Paid or Partial"),
  sp(),
  h2("4.3 Loyalty Points"),
  para("Owners earn 1 loyalty point for every 10 EGP spent on paid invoices. Points are shown on the owner's profile. Redemption: 100 points = 50 EGP discount on the next invoice."),
  sp(),pb(),

  h1("5. Inventory Management"),
  h2("5.1 Adding Stock (New Batch)"),
  num("Go to Inventory > Items > select item > Add Batch"),
  num("Enter: Supplier, Quantity, Cost Price, Expiry Date, Batch Number"),
  num("Click Save — stock level updates immediately"),
  sp(),
  h2("5.2 Low Stock Alerts"),
  para("Items at or below their reorder level appear in the Dashboard low stock alert and in Inventory > Low Stock report. Configure reorder levels per item in the item settings."),
  sp(),
  h2("5.3 Expiry Alerts"),
  para("Items expiring within 30 days are highlighted in the Dashboard and in Inventory > Expiring Soon. Check this daily and follow your clinic's expiry disposal policy."),
  sp(),pb(),

  h1("6. Staff & HR"),
  h2("6.1 Managing Staff Accounts"),
  num("Go to System > Users (super_admin only)"),
  num("Click New User — fill in name, username, password, role"),
  num("Select the appropriate role from the dropdown"),
  num("Click Save — the staff member can log in immediately"),
  sp(),
  h2("6.2 Attendance Tracking"),
  para("Staff check in and out via Attendance > Check In / Check Out. The system records the time and calculates hours worked automatically. Late check-ins are flagged."),
  sp(),
  h2("6.3 Payroll Generation"),
  num("Go to Payroll > Salaries > Generate"),
  num("Select month and year"),
  num("System pulls attendance data and pre-calculates deductions for absences"),
  num("Review each salary slip, adjust if needed"),
  num("Click Approve to lock the record"),
  num("Download PDF salary slips for distribution"),
  sp(),pb(),

  h1("7. WhatsApp & Reminders"),
  h2("7.1 Automated Reminders"),
  para("The platform automatically sends WhatsApp messages for:"),
  bullet("Appointment reminders: 24 hours before the appointment"),
  bullet("Vaccination due alerts: when a pet's vaccination is overdue"),
  bullet("Invoice notifications: when an invoice is created"),
  sp(),
  h2("7.2 Manual Messages"),
  para("Go to WhatsApp > Send Message to send a custom message to any owner. Select a template or type a custom message."),
  sp(),
  h2("7.3 Message Templates"),
  para("Go to WhatsApp > Templates to view and edit the message templates used for automated reminders. Templates support variables like {owner_name}, {pet_name}, {date}, {time}."),
  sp(),pb(),

  h1("8. Reports & Analytics"),
  makeTable(["Report","Location","Contents"],[
    ["Daily Revenue","Finance > Reports","Payments received today, by method"],
    ["Monthly Revenue","Finance > Reports","Revenue by month, trend chart"],
    ["Doctor Revenue","Reports > Doctor Revenue","Revenue and patient count per doctor"],
    ["Inventory Report","Reports > Inventory","Stock levels, value, low-stock items"],
    ["Payroll Summary","Payroll > Reports","Staff salaries, deductions, net pay totals"],
    ["Petshop Sales","Petshop > Reports","Top products, daily sales, payment breakdown"],
    ["Audit Log","System > Audit Log","All user actions with timestamp and IP"],
    ["Owner List","CRM > Owners (Export button)","Full owner list with loyalty points, VIP status"],
  ],[3000,3000,3360]),
  sp(),
  para("Most reports have an Export Excel button that downloads an .xlsx file for further analysis."),
  sp(),pb(),

  h1("9. AI Assistant"),
  h2("9.1 General Chat"),
  para("Go to AI > Chat to open the AI assistant. Ask clinical questions, get drug interaction checks, or request protocol guidance. The AI is powered by Gemini 2.5 Flash."),
  sp(),
  h2("9.2 Patient Context Chat"),
  para("When viewing a Visit, click the AI button (robot icon) on the page. The AI automatically receives the patient's history, active prescriptions, and due vaccinations — no need to type the history manually."),
  sp(),
  h2("9.3 Health Alerts"),
  para("The Dashboard AI Insights card shows automatically generated alerts for overdue vaccinations, pending follow-ups, and other clinical priorities. Click Refresh to update."),
  sp(),
  h2("9.4 Command Palette"),
  para("Press Ctrl+K (or Cmd+K on Mac) from any page to open the Command Palette. Type a question or a page name to navigate instantly."),
  sp(),pb(),

  h1("10. Troubleshooting"),
  makeTable(["Problem","Likely Cause","Solution"],[
    ["Cannot log in","Wrong password or account locked","Contact admin; wait 15 min if locked"],
    ["Page shows 403 error","Insufficient role for this module","Request role upgrade from super_admin"],
    ["AI insights unavailable","AI service (port 3001) not running","Contact IT; AI is optional, all other features work"],
    ["WhatsApp not sent","Wapilot service issue","Check WhatsApp > Logs; messages can be sent manually"],
    ["Cannot book appointment slot","Slot taken by another appointment","Choose a different time or doctor"],
    ["Invoice won't save","Required fields missing","Check all required fields (marked with *)"],
    ["Stock level not updating","Batch not saved correctly","Go to item and verify batch was added"],
    ["PDF download fails","fpdf2 library not installed","Contact IT to install: pip install fpdf2"],
    ["Session expired","60-minute idle timeout","Log in again; unsaved work may be lost"],
  ],[3000,3000,3360]),
  sp(),

  h1("11. Keyboard Shortcuts"),
  makeTable(["Shortcut","Action"],[
    ["Ctrl + K","Open Command Palette (global search + AI)"],
    ["Esc","Close modal dialogs or command palette"],
    ["Ctrl + S","Save form (in supported pages)"],
    ["Alt + L","Toggle language (English / Arabic)"],
  ],[3000,6360]),
  sp(),
];

const doc=new Document({
  numbering:{config:[
    {reference:"bullets",levels:[{level:0,format:LevelFormat.BULLET,text:"•",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:720,hanging:360}}}},{level:1,format:LevelFormat.BULLET,text:"◦",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:1080,hanging:360}}}}]},
    {reference:"numbers",levels:[{level:0,format:LevelFormat.DECIMAL,text:"%1.",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:720,hanging:360}}}}]},
  ]},
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
    headers:{default:new Header({children:[new Paragraph({border:{bottom:{style:BorderStyle.SINGLE,size:4,color:LBLUE,space:4}},children:[new TextRun({text:"Premium Animal Hospital ERP  |  User Guide & Operations Manual  |  v1.0",size:18,color:"606060",font:"Arial"})]})]})} ,
    footers:{default:new Footer({children:[new Paragraph({border:{top:{style:BorderStyle.SINGLE,size:4,color:LBLUE,space:4}},alignment:AlignmentType.RIGHT,children:[new TextRun({text:"Page ",size:18,color:"606060",font:"Arial"}),new TextRun({children:[PageNumber.CURRENT],size:18,color:"606060",font:"Arial"}),new TextRun({text:" of ",size:18,color:"606060",font:"Arial"}),new TextRun({children:[PageNumber.TOTAL_PAGES],size:18,color:"606060",font:"Arial"})]})]})} ,
    children:[...cover,...content]
  }]
});

Packer.toBuffer(doc).then(buf=>{
  fs.writeFileSync("C:\\vet\\platform\\docs\\User_Guide_Operations_Manual_v1.0.docx",buf);
  console.log("User Guide created.");
});
