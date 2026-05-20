const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak, LevelFormat
} = require('docx');
const fs = require('fs');

const BLUE="1F4E79",LBLUE="2E75B6",TBLUE="D6E4F0",GREY="F2F2F2",WHITE="FFFFFF",BLACK="000000",GREEN="1A6B3A",LGREEN="E8F5E9",RED="B71C1C",LRED="FFEBEE",AMBER="E65100",LAMBER="FFF3E0";
const border={style:BorderStyle.SINGLE,size:1,color:"CCCCCC"};
const borders={top:border,bottom:border,left:border,right:border};

const h1=(t)=>new Paragraph({heading:HeadingLevel.HEADING_1,spacing:{before:360,after:120},border:{bottom:{style:BorderStyle.SINGLE,size:6,color:LBLUE,space:4}},children:[new TextRun({text:t,bold:true,size:32,color:BLUE,font:"Arial"})]});
const h2=(t)=>new Paragraph({heading:HeadingLevel.HEADING_2,spacing:{before:240,after:80},children:[new TextRun({text:t,bold:true,size:26,color:LBLUE,font:"Arial"})]});
const h3=(t)=>new Paragraph({heading:HeadingLevel.HEADING_3,spacing:{before:160,after:60},children:[new TextRun({text:t,bold:true,size:22,color:"404040",font:"Arial"})]});
const para=(t,opts={})=>new Paragraph({spacing:{after:120},children:[new TextRun({text:t,size:22,font:"Arial",...opts})]});
const code=(t)=>new Paragraph({spacing:{after:80},shading:{fill:"F5F5F5",type:ShadingType.CLEAR},children:[new TextRun({text:t,size:20,font:"Courier New",color:"2D2D2D"})]});
const bullet=(t,lvl=0)=>new Paragraph({numbering:{reference:"bullets",level:lvl},spacing:{after:60},children:[new TextRun({text:t,size:22,font:"Arial"})]});
const num=(t,lvl=0)=>new Paragraph({numbering:{reference:"numbers",level:lvl},spacing:{after:60},children:[new TextRun({text:t,size:22,font:"Arial"})]});
const sp=(n=1)=>new Paragraph({spacing:{after:n*80},children:[new TextRun("")]});
const pb=()=>new Paragraph({children:[new PageBreak()]});

function noteBox(text, color, label) {
  return new Table({
    width:{size:9360,type:WidthType.DXA},columnWidths:[9360],
    rows:[new TableRow({children:[new TableCell({borders:{top:{style:BorderStyle.SINGLE,size:6,color:color},bottom:{style:BorderStyle.SINGLE,size:2,color:color},left:{style:BorderStyle.SINGLE,size:12,color:color},right:{style:BorderStyle.SINGLE,size:2,color:color}},width:{size:9360,type:WidthType.DXA},shading:{fill:color==="B71C1C"?LRED:color==="E65100"?LAMBER:LGREEN,type:ShadingType.CLEAR},margins:{top:100,bottom:100,left:160,right:160},children:[new Paragraph({children:[new TextRun({text:`${label}  `,bold:true,size:20,font:"Arial",color}),new TextRun({text,size:20,font:"Arial",color:BLACK})]})]})]})]
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
  new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:80},children:[new TextRun({text:"DEPLOYMENT & OPERATIONS GUIDE",size:44,bold:true,color:BLUE,font:"Arial"})]}),
  new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:200},children:[new TextRun({text:"Premium Animal Hospital ERP Platform",size:32,color:LBLUE,font:"Arial"})]}),
  sp(2),
  makeTable(["Field","Detail"],[["Version","1.0 — Production Release"],["Date","May 2026"],["Audience","System Administrator, DevOps"],["OS","Ubuntu 22.04 LTS (recommended) or Windows Server 2022"],["Estimated Setup Time","2–4 hours for a clean server"]],[4000,5360]),
  pb(),
];

const content=[
  h1("1. Prerequisites"),
  h2("1.1 Hardware Requirements"),
  makeTable(["Resource","Minimum","Recommended"],[
    ["CPU","2 vCPU","4 vCPU"],
    ["RAM","4 GB","8 GB"],
    ["Storage","50 GB SSD","100 GB SSD (NVMe preferred)"],
    ["Network","100 Mbps LAN","1 Gbps LAN + 100 Mbps WAN"],
    ["OS","Ubuntu 22.04 LTS","Ubuntu 22.04 LTS"],
  ],[3000,3180,3180]),
  sp(),
  h2("1.2 Software Prerequisites"),
  bullet("Python 3.11+ with pip"),
  bullet("PostgreSQL 15+"),
  bullet("Nginx 1.24+"),
  bullet("Node.js 18+ (for document generation tooling only)"),
  bullet("Git (for cloning the repository)"),
  bullet("certbot (for Let's Encrypt SSL)"),
  sp(),pb(),

  h1("2. Installation — Step by Step"),
  h2("Step 1: System Update & Dependencies"),
  code("sudo apt update && sudo apt upgrade -y"),
  code("sudo apt install -y python3.11 python3.11-venv python3-pip postgresql-15 nginx certbot python3-certbot-nginx git"),
  sp(),
  h2("Step 2: Create Application User"),
  code("sudo useradd -m -s /bin/bash pah"),
  code("sudo mkdir -p /var/www/pah-platform"),
  code("sudo chown pah:pah /var/www/pah-platform"),
  sp(),
  h2("Step 3: Clone & Install"),
  code("sudo -u pah git clone <your-repo-url> /var/www/pah-platform"),
  code("cd /var/www/pah-platform"),
  code("python3.11 -m venv venv"),
  code("source venv/bin/activate"),
  code("pip install -r requirements.txt"),
  code("pip install fpdf2 gunicorn"),
  sp(),
  noteBox("fpdf2 must be installed separately — it is listed in requirements.txt but may need pip install fpdf2 explicitly if the package name differs.", AMBER, "WARNING:"),
  sp(),
  h2("Step 4: Configure PostgreSQL"),
  code("sudo -u postgres psql"),
  code("CREATE USER pah_user WITH PASSWORD 'STRONG_PASSWORD_HERE';"),
  code("CREATE DATABASE vetclinic OWNER pah_user ENCODING 'UTF8';"),
  code("GRANT ALL PRIVILEGES ON DATABASE vetclinic TO pah_user;"),
  code("\\q"),
  sp(),
  h2("Step 5: Environment Configuration"),
  para("Create the environment file at /var/www/pah-platform/.env:"),
  code("PLATFORM_SECRET_KEY=<generate: python -c \"import secrets; print(secrets.token_hex(64))\">"),
  code("POSTGRES_DSN=postgresql://pah_user:STRONG_PASSWORD_HERE@localhost:5432/vetclinic"),
  code("PLATFORM_ADMIN_USER=admin"),
  code("PLATFORM_ADMIN_PASS=<STRONG_ADMIN_PASSWORD>"),
  code("PLATFORM_DEBUG=0"),
  code("PLATFORM_PORT=5100"),
  code("PLATFORM_HOST=127.0.0.1"),
  sp(),
  noteBox("CRITICAL: Never use the default password '1234' in production. Generate a strong password with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"", RED, "CRITICAL:"),
  sp(),
  h2("Step 6: Load Environment & Initialise Database"),
  code("source venv/bin/activate"),
  code("export $(cat .env | xargs)"),
  code("python -c \"from app import create_app; create_app()\""),
  para("This will create all 55 database tables and seed the admin user."),
  sp(),
  h2("Step 7: Test Application Startup"),
  code("python run.py"),
  para("Verify the application starts without errors. Press Ctrl+C to stop."),
  sp(),
  h2("Step 8: Configure Gunicorn Systemd Service"),
  para("Create /etc/systemd/system/pah-platform.service:"),
  code("[Unit]"),
  code("Description=PAH Platform (Gunicorn)"),
  code("After=network.target postgresql.service"),
  code(""),
  code("[Service]"),
  code("User=pah"),
  code("Group=pah"),
  code("WorkingDirectory=/var/www/pah-platform"),
  code("EnvironmentFile=/var/www/pah-platform/.env"),
  code("ExecStart=/var/www/pah-platform/venv/bin/gunicorn \\"),
  code("    --workers 4 --bind 127.0.0.1:5100 \\"),
  code("    --timeout 120 --log-level info \\"),
  code("    'app:create_app()'"),
  code("Restart=always"),
  code("RestartSec=5"),
  code(""),
  code("[Install]"),
  code("WantedBy=multi-user.target"),
  sp(),
  code("sudo systemctl daemon-reload"),
  code("sudo systemctl enable pah-platform"),
  code("sudo systemctl start pah-platform"),
  sp(),
  h2("Step 9: Configure Nginx"),
  para("Create /etc/nginx/sites-available/pah-platform:"),
  code("server {"),
  code("    listen 80;"),
  code("    server_name your-clinic-domain.com;"),
  code("    return 301 https://$host$request_uri;"),
  code("}"),
  code(""),
  code("server {"),
  code("    listen 443 ssl;"),
  code("    server_name your-clinic-domain.com;"),
  code(""),
  code("    ssl_certificate /etc/letsencrypt/live/your-domain/fullchain.pem;"),
  code("    ssl_certificate_key /etc/letsencrypt/live/your-domain/privkey.pem;"),
  code(""),
  code("    location /static/ {"),
  code("        alias /var/www/pah-platform/static/;"),
  code("        expires 7d;"),
  code("    }"),
  code(""),
  code("    location / {"),
  code("        proxy_pass http://127.0.0.1:5100;"),
  code("        proxy_set_header Host $host;"),
  code("        proxy_set_header X-Real-IP $remote_addr;"),
  code("        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;"),
  code("        proxy_set_header X-Forwarded-Proto $scheme;"),
  code("        client_max_body_size 16M;"),
  code("    }"),
  code("}"),
  sp(),
  code("sudo ln -s /etc/nginx/sites-available/pah-platform /etc/nginx/sites-enabled/"),
  code("sudo nginx -t && sudo systemctl reload nginx"),
  sp(),
  h2("Step 10: SSL Certificate"),
  code("sudo certbot --nginx -d your-clinic-domain.com"),
  para("Certbot will auto-renew. Verify with: sudo certbot renew --dry-run"),
  sp(),pb(),

  h1("3. Running the Test Suite"),
  para("Before go-live, run all tests against the production database to confirm everything works:"),
  code("cd /var/www/pah-platform"),
  code("source venv/bin/activate"),
  code("python -X utf8 -m pytest tests/ -v --tb=short"),
  para("Expected result: 171 passed, 18 skipped, 0 failed"),
  sp(),
  noteBox("The test suite creates and destroys a vetclinic_test database. Ensure the pah_user has CREATE DATABASE privilege, or run: GRANT CREATEDB ON DATABASE postgres TO pah_user;", AMBER, "NOTE:"),
  sp(),pb(),

  h1("4. Operations & Maintenance"),
  h2("4.1 Service Management"),
  makeTable(["Task","Command"],[
    ["Start service","sudo systemctl start pah-platform"],
    ["Stop service","sudo systemctl stop pah-platform"],
    ["Restart service","sudo systemctl restart pah-platform"],
    ["View logs","sudo journalctl -u pah-platform -f"],
    ["Check status","sudo systemctl status pah-platform"],
    ["Reload Nginx","sudo systemctl reload nginx"],
  ],[3500,5860]),
  sp(),
  h2("4.2 Database Backup & Restore"),
  h3("Manual Backup"),
  code("sudo -u pah pg_dump vetclinic > /var/backups/pah/vetclinic_$(date +%Y%m%d).sql"),
  sp(),
  h3("Automated Backup"),
  para("The platform runs an automated backup at 02:00 daily via APScheduler. Backup files are stored in /var/www/pah-platform/data/backups/ and can be managed from System > Backup Manager in the web interface."),
  sp(),
  h3("Restore from Backup"),
  code("sudo -u postgres psql -c \"DROP DATABASE IF EXISTS vetclinic;\""),
  code("sudo -u postgres psql -c \"CREATE DATABASE vetclinic OWNER pah_user;\""),
  code("sudo -u pah psql vetclinic < /var/backups/pah/vetclinic_20260101.sql"),
  code("sudo systemctl restart pah-platform"),
  sp(),
  h2("4.3 Updating the Application"),
  num("Put the site into maintenance mode (create a maintenance page in Nginx)"),
  num("Pull the latest code: git pull origin main"),
  num("Install new dependencies: pip install -r requirements.txt"),
  num("Run database migrations (if any schema changes)"),
  num("Run the test suite: python -X utf8 -m pytest tests/ -q"),
  num("Restart the service: sudo systemctl restart pah-platform"),
  num("Verify the application loads and remove maintenance mode"),
  sp(),
  h2("4.4 Log Files"),
  makeTable(["Log","Location","Contents"],[
    ["Application","journalctl -u pah-platform","Flask + APScheduler output"],
    ["Nginx Access","/var/log/nginx/access.log","All HTTP requests"],
    ["Nginx Error","/var/log/nginx/error.log","Proxy and SSL errors"],
    ["PostgreSQL","/var/log/postgresql/","Slow queries, connection errors"],
    ["Audit Log","System > Audit Log (web UI)","All user actions with IP + timestamp"],
  ],[2500,3500,3360]),
  sp(),pb(),

  h1("5. Post-Deployment Checklist"),
  new Table({
    width:{size:9360,type:WidthType.DXA},columnWidths:[1000,7000,1360],
    rows:[
      new TableRow({children:[new TableCell({borders,width:{size:1000,type:WidthType.DXA},shading:{fill:BLUE,type:ShadingType.CLEAR},margins:{top:80,bottom:80,left:120,right:120},children:[new Paragraph({children:[new TextRun({text:"Done",bold:true,size:20,font:"Arial",color:WHITE})]})]}),new TableCell({borders,width:{size:7000,type:WidthType.DXA},shading:{fill:BLUE,type:ShadingType.CLEAR},margins:{top:80,bottom:80,left:120,right:120},children:[new Paragraph({children:[new TextRun({text:"Checklist Item",bold:true,size:20,font:"Arial",color:WHITE})]})]}),new TableCell({borders,width:{size:1360,type:WidthType.DXA},shading:{fill:BLUE,type:ShadingType.CLEAR},margins:{top:80,bottom:80,left:120,right:120},children:[new Paragraph({children:[new TextRun({text:"Priority",bold:true,size:20,font:"Arial",color:WHITE})]})]})]}),
      ...[
        ["[ ]","Default admin password changed from '1234' to a strong password","CRITICAL"],
        ["[ ]","PLATFORM_SECRET_KEY set to a unique 64-character random string","CRITICAL"],
        ["[ ]","PLATFORM_DEBUG=0 confirmed in .env","CRITICAL"],
        ["[ ]","HTTPS enforced via Nginx + Let's Encrypt SSL certificate","CRITICAL"],
        ["[ ]","SESSION_COOKIE_SECURE=True confirmed (add to Config if needed)","CRITICAL"],
        ["[ ]","fpdf2 installed and PDF generation tested","High"],
        ["[ ]","171 automated tests pass with 0 failures","High"],
        ["[ ]","Daily backup job verified (check System > Backup Manager after 02:00)","High"],
        ["[ ]","WhatsApp reminder test sent successfully","High"],
        ["[ ]","Inpatient blueprint registered in app.py","Medium"],
        ["[ ]","All staff accounts created with correct roles","High"],
        ["[ ]","Clinic information updated in System > Settings","Medium"],
        ["[ ]","Service catalog populated with current pricing","Medium"],
        ["[ ]","PostgreSQL connection credentials in .env (not hardcoded)","CRITICAL"],
        ["[ ]","Backup directory has sufficient disk space (monitor > 20% free)","High"],
      ].map(([done,item,pri],i)=>new TableRow({children:[
        new TableCell({borders,width:{size:1000,type:WidthType.DXA},shading:{fill:i%2===0?GREY:WHITE,type:ShadingType.CLEAR},margins:{top:80,bottom:80,left:120,right:120},children:[new Paragraph({alignment:AlignmentType.CENTER,children:[new TextRun({text:done,size:20,font:"Courier New"})]})]}),
        new TableCell({borders,width:{size:7000,type:WidthType.DXA},shading:{fill:i%2===0?GREY:WHITE,type:ShadingType.CLEAR},margins:{top:80,bottom:80,left:120,right:120},children:[new Paragraph({children:[new TextRun({text:item,size:20,font:"Arial"})]})]  }),
        new TableCell({borders,width:{size:1360,type:WidthType.DXA},shading:{fill:pri==="CRITICAL"?LRED:pri==="High"?LAMBER:WHITE,type:ShadingType.CLEAR},margins:{top:80,bottom:80,left:120,right:120},children:[new Paragraph({children:[new TextRun({text:pri,size:20,font:"Arial",bold:pri==="CRITICAL"})]})]}),
      ]}))
    ]
  }),
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
    headers:{default:new Header({children:[new Paragraph({border:{bottom:{style:BorderStyle.SINGLE,size:4,color:LBLUE,space:4}},children:[new TextRun({text:"Premium Animal Hospital ERP  |  Deployment & Operations Guide  |  v1.0",size:18,color:"606060",font:"Arial"})]})]})} ,
    footers:{default:new Footer({children:[new Paragraph({border:{top:{style:BorderStyle.SINGLE,size:4,color:LBLUE,space:4}},alignment:AlignmentType.RIGHT,children:[new TextRun({text:"Page ",size:18,color:"606060",font:"Arial"}),new TextRun({children:[PageNumber.CURRENT],size:18,color:"606060",font:"Arial"}),new TextRun({text:" of ",size:18,color:"606060",font:"Arial"}),new TextRun({children:[PageNumber.TOTAL_PAGES],size:18,color:"606060",font:"Arial"})]})]})} ,
    children:[...cover,...content]
  }]
});

Packer.toBuffer(doc).then(buf=>{
  fs.writeFileSync("C:\\vet\\platform\\docs\\Deployment_Operations_Guide_v1.0.docx",buf);
  console.log("Deployment & Operations Guide created.");
});
