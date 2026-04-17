from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import os, datetime, io, smtplib, json
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'guardtire-secret-2025')
# Fix postgres:// -> postgresql:// and add reconnect/SSL options
_db_url = os.environ.get('DATABASE_URL', 'sqlite:///guardtire.db')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 280,
    'connect_args': {'sslmode': 'require'} if 'postgresql' in _db_url else {},
}
app.config['PDF_FOLDER'] = os.environ.get('PDF_FOLDER', 'pdfs')

db = SQLAlchemy(app)

# ─── MODELS ────────────────────────────────────────────────────────────────────
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='operario')  # admin or operario
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Garantia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, unique=True, nullable=False)
    placa = db.Column(db.String(20))
    marca = db.Column(db.String(60))
    ref_llanta = db.Column(db.String(60))
    km = db.Column(db.String(20))
    fecha = db.Column(db.String(20))
    pct_llanta_1 = db.Column(db.String(10))
    pct_llanta_2 = db.Column(db.String(10))
    pct_llanta_3 = db.Column(db.String(10))
    pct_llanta_4 = db.Column(db.String(10))
    alineacion = db.Column(db.String(5))
    balanceo = db.Column(db.String(5))
    observaciones = db.Column(db.Text)
    tipo_llanta = db.Column(db.String(20))  # nueva/usada
    pdf_path = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    created_by = db.Column(db.String(80))

# ─── TIRE DATA ─────────────────────────────────────────────────────────────────
TIRE_DATA = {
    "155/80R13": 1.12564, "165/65R13": 1.128836, "175/70R13": 1.26429,
    "185/60R13": 1.283092, "165/60R14": 1.147281, "185/65R15": 1.444117,
    "195/65R15": 1.554017, "205/65R15": 1.667183, "205/55R16": 1.627016,
    "215/65R16": 1.852204, "205/60R16": 1.6798, "205/55R17": 1.692416,
    "225/45R17": 1.792532, "225/60R17": 1.983287, "225/65R17": 2.046872,
    "265/70R17": 2.67204, "225/45R18": 1.864312, "235/50R18": 2.043098,
    "265/60R18": 2.580176, "265/65R18": 2.668378, "225/55R19": 2.063263,
    "235/50R19": 2.118068, "235/55R19": 2.187431, "245/45R19": 2.163579,
    "255/55R20": 2.525408, "275/55R20": 2.799467, "275/60R20": 2.894452,
    "255/40R21": 2.361745, "265/45R21": 2.569192, "275/40R21": 2.602244,
    "315/40R21": 3.107357, "265/40ZR22": 2.565531, "275/45R22": 2.78496
}

# ─── AUTH HELPERS ──────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return jsonify({'error': 'Acceso solo para administradores'}), 403
        return f(*args, **kwargs)
    return decorated

# ─── ROUTES ────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        user = User.query.filter_by(username=data['username']).first()
        if user and user.check_password(data['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return jsonify({'success': True, 'role': user.role})
        return jsonify({'success': False, 'error': 'Usuario o contraseña incorrectos'}), 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session.get('username'), role=session.get('role'))

# ─── CALCULATOR API ────────────────────────────────────────────────────────────
@app.route('/api/tires')
@login_required
def get_tires():
    return jsonify(list(TIRE_DATA.keys()))

@app.route('/api/calculate', methods=['POST'])
@login_required
def calculate():
    data = request.json
    ref = data.get('referencia', '')
    qty = int(data.get('cantidad', 1))
    if ref in TIRE_DATA:
        kg_per_tire = TIRE_DATA[ref]
        total_kg = round(kg_per_tire * qty, 4)
        return jsonify({'kg_por_llanta': kg_per_tire, 'total_kg': total_kg, 'cantidad': qty})
    # manual calculation
    w = float(data.get('w', 0))
    pct = float(data.get('pct', 0)) / 100
    r = float(data.get('r', 0))
    if w and r:
        espesor = 0.004
        cant_glue = espesor * (2 * 3.14159 * (r * 25.4) * w * pct + 2 * 3.14159 * (r * 25.4) * w * pct) * 1000
        kg = round(cant_glue / 1000 * qty, 4)
        return jsonify({'kg_por_llanta': round(cant_glue / 1000, 4), 'total_kg': kg, 'cantidad': qty})
    return jsonify({'error': 'Referencia no encontrada'}), 404

# ─── GARANTÍA API ──────────────────────────────────────────────────────────────
@app.route('/api/garantia/next-number')
@login_required
def next_number():
    last = Garantia.query.order_by(Garantia.numero.desc()).first()
    next_n = (last.numero + 1) if last else 501
    return jsonify({'numero': next_n})

@app.route('/api/garantia', methods=['POST'])
@login_required
def create_garantia():
    data = request.json
    last = Garantia.query.order_by(Garantia.numero.desc()).first()
    numero = (last.numero + 1) if last else 501

    g = Garantia(
        numero=numero,
        placa=data.get('placa', ''),
        marca=data.get('marca', ''),
        ref_llanta=data.get('ref_llanta', ''),
        km=data.get('km', ''),
        fecha=data.get('fecha', datetime.date.today().strftime('%d/%m/%Y')),
        pct_llanta_1=data.get('pct_llanta_1', ''),
        pct_llanta_2=data.get('pct_llanta_2', ''),
        pct_llanta_3=data.get('pct_llanta_3', ''),
        pct_llanta_4=data.get('pct_llanta_4', ''),
        alineacion=data.get('alineacion', ''),
        balanceo=data.get('balanceo', ''),
        observaciones=data.get('observaciones', ''),
        tipo_llanta=data.get('tipo_llanta', 'nueva'),
        created_by=session.get('username')
    )
    db.session.add(g)
    db.session.flush()

    pdf_path = generate_pdf(g)
    g.pdf_path = pdf_path
    db.session.commit()

    return jsonify({'success': True, 'numero': numero, 'pdf_path': pdf_path})

@app.route('/api/garantia/<int:numero>/pdf')
@login_required
def download_pdf(numero):
    g = Garantia.query.filter_by(numero=numero).first_or_404()
    if not g.pdf_path or not os.path.exists(g.pdf_path):
        return jsonify({'error': 'PDF no encontrado'}), 404
    return send_file(g.pdf_path, as_attachment=True,
                     download_name=f'garantia_{numero}.pdf',
                     mimetype='application/pdf')

@app.route('/api/garantia/<int:numero>/email', methods=['POST'])
@login_required
def send_email_garantia(numero):
    data = request.json
    email_to = data.get('email')
    g = Garantia.query.filter_by(numero=numero).first_or_404()
    if not g.pdf_path or not os.path.exists(g.pdf_path):
        return jsonify({'error': 'PDF no encontrado'}), 404
    try:
        send_email(email_to, g)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/garantias')
@login_required
def list_garantias():
    page = request.args.get('page', 1, type=int)
    gs = Garantia.query.order_by(Garantia.numero.desc()).paginate(page=page, per_page=20)
    return jsonify({
        'items': [{'numero': g.numero, 'placa': g.placa, 'marca': g.marca,
                   'fecha': g.fecha, 'tipo': g.tipo_llanta,
                   'created_by': g.created_by} for g in gs.items],
        'total': gs.total, 'pages': gs.pages, 'current': gs.page
    })

# ─── ADMIN: USER MANAGEMENT ────────────────────────────────────────────────────
@app.route('/api/users', methods=['GET'])
@admin_required
def list_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'username': u.username, 'role': u.role} for u in users])

@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    data = request.json
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Usuario ya existe'}), 400
    u = User(username=data['username'], role=data.get('role', 'operario'))
    u.set_password(data['password'])
    db.session.add(u)
    db.session.commit()
    return jsonify({'success': True, 'id': u.id})

@app.route('/api/users/<int:uid>', methods=['DELETE'])
@admin_required
def delete_user(uid):
    u = User.query.get_or_404(uid)
    if u.id == session['user_id']:
        return jsonify({'error': 'No puedes eliminarte a ti mismo'}), 400
    db.session.delete(u)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/users/<int:uid>/password', methods=['PUT'])
@admin_required
def change_password(uid):
    data = request.json
    u = User.query.get_or_404(uid)
    u.set_password(data['password'])
    db.session.commit()
    return jsonify({'success': True})

# ─── PDF GENERATION ────────────────────────────────────────────────────────────
def generate_pdf(g):
    os.makedirs(app.config['PDF_FOLDER'], exist_ok=True)
    filename = f"garantia_{g.numero}.pdf"
    filepath = os.path.join(app.config['PDF_FOLDER'], filename)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=1.5*cm, rightMargin=1.5*cm)

    BLACK      = colors.HexColor('#000000')
    DARK       = colors.HexColor('#1a1a1a')
    MID        = colors.HexColor('#444444')
    WHITE      = colors.white
    GRAY_LIGHT = colors.HexColor('#F2F2F2')
    GRAY_MID   = colors.HexColor('#BBBBBB')
    GRAY_DARK  = colors.HexColor('#888888')

    title_style   = ParagraphStyle('title',   fontName='Helvetica-Bold',   fontSize=15,
                                   textColor=WHITE, alignment=TA_CENTER)
    label_style   = ParagraphStyle('label',   fontName='Helvetica-Bold',   fontSize=8,
                                   textColor=MID)
    value_style   = ParagraphStyle('value',   fontName='Helvetica',        fontSize=10,
                                   textColor=BLACK)
    section_style = ParagraphStyle('section', fontName='Helvetica-Bold',   fontSize=9,
                                   textColor=BLACK, spaceBefore=6)
    body_style    = ParagraphStyle('body',    fontName='Helvetica',        fontSize=8,
                                   textColor=colors.HexColor('#333333'), leading=12)

    story = []

    # ── HEADER with logo ────────────────────────────────────────────────────────
    from reportlab.platypus import Image as RLImage
    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'logo.png')

    logo_cell = ''
    if os.path.exists(logo_path):
        logo_img = RLImage(logo_path, width=1.6*cm, height=1.6*cm)
        logo_cell = logo_img

    brand_style = ParagraphStyle('brand', fontName='Helvetica-Bold', fontSize=17,
                                  textColor=WHITE, alignment=TA_LEFT, spaceAfter=2)
    sub_style   = ParagraphStyle('sub',   fontName='Helvetica',       fontSize=10,
                                  textColor=colors.HexColor('#CCCCCC'), alignment=TA_LEFT)
    right_style = ParagraphStyle('right', fontName='Helvetica-Bold',  fontSize=10,
                                  textColor=WHITE, alignment=TA_CENTER)
    num_style   = ParagraphStyle('num',   fontName='Helvetica-Bold',  fontSize=26,
                                  textColor=WHITE, alignment=TA_CENTER)

    header_inner = Table([
        [logo_cell,
         [Paragraph('GUARDTIRE', brand_style), Paragraph('ANTIPINCHAZOS', sub_style)],
         [Paragraph('GARANTÍA DEL POLÍMERO', right_style),
          Paragraph(f'#{g.numero}', num_style)]]
    ], colWidths=[2*cm, 9*cm, 7*cm])
    header_inner.setStyle(TableStyle([
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING',(0,0), (-1,-1), 6),
    ]))

    header_wrap = Table([[header_inner]], colWidths=[18*cm])
    header_wrap.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,-1), BLACK),
        ('ROWPADDING',  (0,0), (-1,-1), 10),
        ('BOX',         (0,0), (-1,-1), 1, DARK),
    ]))
    story.append(header_wrap)
    story.append(Spacer(1, 8))

    # ── INFO PRINCIPAL ──────────────────────────────────────────────────────────
    def lbl(t): return Paragraph(t, label_style)
    def val(t): return Paragraph(t or '—', value_style)

    info_data = [
        [lbl('PLACA'), val(g.placa), lbl('MARCA'), val(g.marca), lbl('FECHA'), val(g.fecha)],
        [lbl('REF. LLANTA'), val(g.ref_llanta), lbl('KILÓMETROS'), val(g.km),
         lbl('TIPO'), val((g.tipo_llanta or 'Nueva').upper())],
    ]
    info_table = Table(info_data, colWidths=[3*cm, 4.5*cm, 2.8*cm, 3.2*cm, 2.2*cm, 2.3*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (0,-1), GRAY_LIGHT), ('BACKGROUND',  (2,0), (2,-1), GRAY_LIGHT),
        ('BACKGROUND',  (4,0), (4,-1), GRAY_LIGHT),
        ('BOX',         (0,0), (-1,-1), 0.8, BLACK),
        ('INNERGRID',   (0,0), (-1,-1), 0.3, GRAY_MID),
        ('ROWPADDING',  (0,0), (-1,-1), 7),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 4))

    # ── % LLANTAS ───────────────────────────────────────────────────────────────
    pct_data = [[
        lbl('% LLANTA 1'), val(g.pct_llanta_1),
        lbl('% LLANTA 2'), val(g.pct_llanta_2),
        lbl('% LLANTA 3'), val(g.pct_llanta_3),
        lbl('% LLANTA 4'), val(g.pct_llanta_4),
    ]]
    pct_table = Table(pct_data, colWidths=[2.5*cm, 2*cm, 2.5*cm, 2*cm, 2.5*cm, 2*cm, 2.5*cm, 2*cm])
    pct_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (0,0), GRAY_LIGHT), ('BACKGROUND', (2,0), (2,0), GRAY_LIGHT),
        ('BACKGROUND',  (4,0), (4,0), GRAY_LIGHT), ('BACKGROUND', (6,0), (6,0), GRAY_LIGHT),
        ('BOX',         (0,0), (-1,-1), 0.8, BLACK),
        ('INNERGRID',   (0,0), (-1,-1), 0.3, GRAY_MID),
        ('ROWPADDING',  (0,0), (-1,-1), 7),
    ]))
    story.append(pct_table)
    story.append(Spacer(1, 4))

    # ── ALINEACIÓN / BALANCEO / OBSERVACIONES ───────────────────────────────────
    alin_val = '✓  SÍ' if g.alineacion == 'si' else '✗  NO'
    bal_val  = '✓  SÍ' if g.balanceo   == 'si' else '✗  NO'
    checks_data = [[
        lbl('ALINEACIÓN'), val(alin_val),
        lbl('BALANCEO'),   val(bal_val),
        lbl('OBSERVACIONES'), val(g.observaciones),
    ]]
    checks_table = Table(checks_data, colWidths=[2.8*cm, 2.2*cm, 2.5*cm, 2.2*cm, 3.2*cm, 5.1*cm])
    checks_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (0,0), GRAY_LIGHT), ('BACKGROUND', (2,0), (2,0), GRAY_LIGHT),
        ('BACKGROUND',  (4,0), (4,0), GRAY_LIGHT),
        ('BOX',         (0,0), (-1,-1), 0.8, BLACK),
        ('INNERGRID',   (0,0), (-1,-1), 0.3, GRAY_MID),
        ('ROWPADDING',  (0,0), (-1,-1), 7),
    ]))
    story.append(checks_table)
    story.append(Spacer(1, 10))

    story.append(HRFlowable(width="100%", thickness=1.2, color=BLACK))
    story.append(Spacer(1, 5))

    # ── POLÍTICAS ───────────────────────────────────────────────────────────────
    story.append(Paragraph('POLÍTICAS DE GARANTÍA', section_style))
    story.append(Paragraph('De conformidad con las disposiciones colombianas:', body_style))
    story.append(Paragraph('1. Ley 1480 de 2011 (Estatuto del Consumidor): Art. 3 - Derecho a la calidad. Art. 10 - Garantías mínimas. Art. 26 - Plazo mínimo 1 año.', body_style))
    story.append(Paragraph('2. Decreto 1163 de 2014: Reglamenta garantías y responsabilidades posventa.', body_style))
    story.append(Paragraph('3. Resolución 4100 de 2009 (Min. Transporte): Normas técnicas para neumáticos.', body_style))
    story.append(Spacer(1, 5))

    # ── TABLA VIGENCIA ──────────────────────────────────────────────────────────
    hdr_style = ParagraphStyle('hdr', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)
    vig_data = [
        [Paragraph('Producto', hdr_style), Paragraph('Vigencia', hdr_style),
         Paragraph('Protección', hdr_style), Paragraph('Exclusiones', hdr_style)],
        [Paragraph('Llantas Nuevas', body_style), Paragraph('30,000 km o 2 años', body_style),
         Paragraph('Sellado pinchazos ≤6mm (superficie rodadura)', body_style),
         Paragraph('Daños laterales, talleres no autorizados, presión incorrecta, fuerza mayor.', body_style)],
        [Paragraph('Llantas Usadas', body_style), Paragraph('12 meses', body_style),
         Paragraph('Sellado pinchazos ≤6mm. Cobertura proporcional al desgaste.', body_style),
         Paragraph('—', body_style)],
    ]
    vig_table = Table(vig_data, colWidths=[3.5*cm, 3.5*cm, 5*cm, 6*cm])
    vig_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1, 0), BLACK),
        ('BACKGROUND',  (0,1), (-1, 1), GRAY_LIGHT),
        ('FONTSIZE',    (0,0), (-1,-1), 8),
        ('BOX',         (0,0), (-1,-1), 0.8, BLACK),
        ('INNERGRID',   (0,0), (-1,-1), 0.3, GRAY_MID),
        ('ROWPADDING',  (0,0), (-1,-1), 5),
        ('VALIGN',      (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(vig_table)
    story.append(Spacer(1, 5))

    # ── RECOMENDACIONES ─────────────────────────────────────────────────────────
    story.append(Paragraph('RECOMENDACIONES', section_style))
    for rec in [
        '• Balancear la llanta después de aplicarse el producto.',
        '• Monitorear la presión de aire según indicaciones del fabricante.',
        '• Alinear el vehículo cada 6 meses o 10,000 Km.',
        '• No rodar la llanta más de 20 metros sin presión.',
    ]:
        story.append(Paragraph(rec, body_style))
    story.append(Spacer(1, 5))

    # ── PROCESO RECLAMACIÓN ─────────────────────────────────────────────────────
    story.append(Paragraph('PROCESO DE RECLAMACIÓN', section_style))
    story.append(Paragraph('1. Documentación: Certificado de Garantía + fotos del daño.', body_style))
    story.append(Paragraph('2. Evaluación: Verificación por Guardtire Antipinchazos.', body_style))
    story.append(Paragraph('3. Solución: Respuesta en máximo 10 días hábiles (Art. 26 Decreto 1163/2014).', body_style))
    story.append(Spacer(1, 6))

    # ── SOPORTE ─────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_MID))
    story.append(Spacer(1, 5))
    support_data = [[
        Paragraph('SOPORTE TÉCNICO', label_style),
        Paragraph('Tel: 300 412 6814', body_style),
        Paragraph('guardtire2025@gmail.com', body_style),
    ]]
    support_table = Table(support_data, colWidths=[4*cm, 5*cm, 9*cm])
    support_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRAY_LIGHT),
        ('BOX',        (0,0), (-1,-1), 0.5, GRAY_MID),
        ('ROWPADDING', (0,0), (-1,-1), 7),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(support_table)
    story.append(Spacer(1, 7))

    # ── NOTA FINAL ──────────────────────────────────────────────────────────────
    nota = '"Guardtire AntiPinchazos cumple con la normativa colombiana y supera los estándares mínimos de garantía. La protección está en sus manos: revise sus llantas periódicamente y siga las recomendaciones técnicas."'
    story.append(Paragraph(nota, ParagraphStyle('nota', fontName='Helvetica-Oblique', fontSize=8,
                                                 textColor=GRAY_DARK, alignment=TA_CENTER,
                                                 borderColor=GRAY_MID, borderWidth=0.5,
                                                 borderPadding=8, backColor=GRAY_LIGHT)))

    doc.build(story)
    return filepath

# ─── EMAIL ─────────────────────────────────────────────────────────────────────
def send_email(to_email, g):
    smtp_host = os.environ.get('SMTP_HOST', 'smtp.hostinger.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 465))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = to_email
    msg['Subject'] = f'Garantía Guardtire #{g.numero} - {g.placa}'

    body = f"""Estimado cliente,

Adjunto encontrará el certificado de garantía #{g.numero} para el vehículo con placa {g.placa}.

Vehículo: {g.placa}
Marca llanta: {g.marca}
Referencia: {g.ref_llanta}
Fecha: {g.fecha}

Para cualquier reclamación contáctenos:
📞 300 412 6814
✉ guardtire2025@gmail.com

Guardtire AntiPinchazos
"""
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    with open(g.pdf_path, 'rb') as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename=garantia_{g.numero}.pdf')
        msg.attach(part)

    # Try TLS (port 587) first - Railway blocks 465 SSL
    try:
        with smtplib.SMTP(smtp_host, 587, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, msg.as_string())
    except Exception:
        # Fallback to SSL port 465
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, msg.as_string())

# ─── INIT ──────────────────────────────────────────────────────────────────────
def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role='admin')
            admin.set_password('guardtire2025')
            db.session.add(admin)
            db.session.commit()
            print("Admin creado: admin / guardtire2025")

# Auto-init DB (runs on gunicorn startup too, safe - only creates if not exists)
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
