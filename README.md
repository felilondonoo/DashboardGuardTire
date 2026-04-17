# Guardtire – Portal de Garantías y Calculadora

Aplicación web para operarios y admins de Guardtire AntiPinchazos.

## Funcionalidades

- 🔐 Login con usuario y contraseña (admin / operario)
- 🔢 Calculadora de Kg de polímero por referencia de llanta
- 📄 Formulario de garantía → genera PDF automáticamente
- ✉ Envío de PDF por correo al cliente
- 📋 Historial de garantías con descarga de PDF
- ⚙️ Panel admin para gestionar usuarios

---

## Despliegue en Railway

### 1. Subir código a GitHub

```bash
cd guardtire
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/TU_USUARIO/guardtire.git
git push -u origin main
```

### 2. Crear proyecto en Railway

1. Ir a https://railway.app → New Project
2. Seleccionar **Deploy from GitHub repo** → seleccionar tu repo
3. Railway detectará automáticamente Python y usará el `Procfile`

### 3. Agregar base de datos PostgreSQL

1. En tu proyecto Railway → **+ New** → **Database** → **PostgreSQL**
2. La variable `DATABASE_URL` se agrega automáticamente al servicio

### 4. Configurar variables de entorno

En Railway → tu servicio → **Variables**, agregar:

| Variable | Valor |
|----------|-------|
| `SECRET_KEY` | una_clave_aleatoria_segura_ej_abc123xyz |
| `SMTP_HOST` | smtp.hostinger.com |
| `SMTP_PORT` | 465 |
| `SMTP_USER` | tu_correo@guardtire.com |
| `SMTP_PASS` | tu_contraseña_correo |
| `PDF_FOLDER` | /app/pdfs |

### 5. Persistencia de PDFs (opcional pero recomendado)

Railway puede reiniciarse y borrar archivos locales. Para PDFs permanentes:
- Opción A: Guardar PDFs en un bucket de S3/Cloudflare R2 (se puede agregar)
- Opción B: Para MVP, los PDFs se regeneran desde la DB si se necesitan

### 6. Primer acceso

Usuario inicial creado automáticamente:
- **Usuario:** `admin`
- **Contraseña:** `guardtire2025`

⚠️ **Cambiar la contraseña del admin desde el panel después del primer login.**

---

## Variables de entorno locales (desarrollo)

Crear archivo `.env`:
```
SECRET_KEY=dev-secret
DATABASE_URL=sqlite:///guardtire.db
SMTP_HOST=smtp.hostinger.com
SMTP_PORT=465
SMTP_USER=correo@guardtire.com
SMTP_PASS=tu_password
PDF_FOLDER=pdfs
```

## Ejecutar localmente

```bash
pip install -r requirements.txt
python app.py
# Abre http://localhost:5000
```

---

## Estructura del proyecto

```
guardtire/
├── app.py              # Backend Flask completo
├── requirements.txt    # Dependencias Python
├── Procfile            # Comando Railway/Gunicorn
├── nixpacks.toml       # Config build Railway
├── init_db.py          # Script inicialización DB
├── templates/
│   ├── login.html      # Página de login
│   └── dashboard.html  # App principal
└── pdfs/               # PDFs generados (creado automáticamente)
```

---

## Roles de usuario

| Rol | Acceso |
|-----|--------|
| **admin** | Calculadora + Garantías + Historial + Gestión usuarios |
| **operario** | Calculadora + Garantías + Historial |
