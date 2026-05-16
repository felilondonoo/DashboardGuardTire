# Guardtire – Portal de Garantías

Aplicación web para emitir garantías, calcular kilogramos de polímero y gestionar
usuarios de Guardtire AntiPinchazos.

> Esta guía está escrita para que **alguien sin conocimientos de programación**
> pueda volver a poner la app en línea en menos de 30 minutos. Sigue los pasos
> tal cual. Si algo se ve distinto a lo descrito, busca el botón equivalente.

---

## ⚡ Qué tener a la mano antes de empezar

Antes de tocar nada, ten estos datos guardados en un lugar seguro (Google Keep,
una nota en el teléfono, un papel):

1. **Cuenta de GitHub** con acceso al repositorio del código.
   - Si no la tienes, pide al desarrollador original que te dé acceso.
2. **API Key de Resend** (el servicio que envía los correos).
   - Empieza con `re_...`
   - Se obtiene en https://resend.com → **API Keys**.
   - Si la perdiste, puedes crear una nueva, **pero verifica que el dominio
     `guardtire.com` siga validado** en Resend (sección **Domains**).
3. **(Recomendado) El último Excel de garantías** descargado desde la app.
   Es tu respaldo de los datos.

---

## 🚀 Cómo subir la app a Railway (paso a paso)

### Paso 1 — Entrar a Railway

1. Ve a https://railway.app
2. Haz clic en **Login** → **Login with GitHub** y acepta los permisos.

### Paso 2 — Crear el proyecto

1. Una vez dentro, clic en **+ New Project**.
2. Elige **Deploy from GitHub repo**.
3. Selecciona el repositorio de Guardtire.
4. Railway empezará a construir la app automáticamente (lee el `Dockerfile`).
   **Espera 2–3 minutos.** Verás un círculo verde cuando termine.

### Paso 3 — Agregar la base de datos

1. Dentro del proyecto, clic en **+ New** (arriba a la derecha).
2. Elige **Database** → **Add PostgreSQL**.
3. Railway crea la base y conecta la variable `DATABASE_URL` automáticamente.
   **No tienes que hacer nada más aquí.**

### Paso 4 — Configurar las variables de entorno

1. Haz clic en el servicio de la **app** (no el de Postgres).
2. Ve a la pestaña **Variables** → **+ New Variable**.
3. Agrega estas tres, una por una:

   | Nombre | Qué poner |
   |--------|-----------|
   | `SECRET_KEY` | Una cadena larga y aleatoria. Ejemplo: `xK9mP2nQ8wL5rT3vY7zB4aC6eF1dH0g` |
   | `RESEND_API_KEY` | Tu API key de Resend (empieza con `re_`) |
   | `PDF_FOLDER` | `/app/pdfs` |

4. Al guardar la última, Railway re-despliega solo. Espera 1–2 minutos más.

### Paso 5 — Generar la URL pública

1. En el servicio de la app, pestaña **Settings**.
2. Busca la sección **Networking** o **Domains** → **Generate Domain**.
3. Railway te da una dirección tipo `guardtire-production-xxxx.up.railway.app`.
4. Ábrela en el navegador.

### Paso 6 — Primer ingreso

- **Usuario:** `admin`
- **Contraseña:** `guardtire2025`

🔒 **Cambia esa contraseña inmediatamente** desde ⚙️ Usuarios.

---

## 💾 Cómo respaldar los datos (hazlo cada semana)

La app tiene una función de **copia de seguridad completa con un solo clic**.

### Descargar la copia (lo más importante)

1. Entra como **admin**.
2. Ve a la pestaña **⚙️ Usuarios**.
3. En la tarjeta **💾 Copia de Seguridad**, clic en **📥 Descargar copia de seguridad**.
4. Se descarga un archivo `guardtire_backup_AAAAMMDD.json` con TODO:
   usuarios (con sus contraseñas), garantías y plantilla de correo.
5. Guarda ese archivo en Google Drive / Dropbox / disco externo.
   **Recomendado: una vez por semana.**

### Restaurar la copia (si algo se pierde o cambias de proveedor)

1. Entra como **admin** en la app (nueva o recuperada).
2. Pestaña **⚙️ Usuarios** → tarjeta **💾 Copia de Seguridad**.
3. Clic en **📤 Restaurar copia** → selecciona el archivo `.json` que guardaste.
4. Confirma el aviso.
5. La app te redirige al login. Inicia sesión con las credenciales del backup.

> ⚠ Restaurar **reemplaza todos los datos actuales** por los del archivo.
> Útil para mover la app a otro proveedor sin perder nada.

### Backup adicional en Excel

Si quieres un respaldo legible en hoja de cálculo:
**📋 Historial** → **⬇ Descargar Excel** (admin).

---

## 🆘 Si Railway se cae o quieres mover la app

La app está dentro de un **Dockerfile**, así que puede correr en casi cualquier
proveedor moderno: **Render**, **Fly.io**, **DigitalOcean App Platform**,
o un servidor con Docker.

### Migración rápida a otro proveedor (ej: Render)

1. Crea cuenta en el nuevo proveedor → conéctala con GitHub.
2. Crea un nuevo servicio → "Deploy from GitHub repo" → mismo repositorio.
3. Agrega PostgreSQL como add-on / base de datos.
4. Configura las **mismas 3 variables** del Paso 4 (`SECRET_KEY`,
   `RESEND_API_KEY`, `PDF_FOLDER`).
5. Genera la URL pública.
6. Entra con `admin` / `guardtire2025`.

### Si pierdes la base de datos

**Caso A — tienes el backup `.json`:**
1. Despliega la app nueva siguiendo los pasos del Quickstart.
2. Entra con `admin` / `guardtire2025`.
3. Ve a ⚙️ Usuarios → **📤 Restaurar copia** y carga el archivo.
4. Inicia sesión con las credenciales originales. Listo: usuarios,
   garantías y numeración intactos.

**Caso B — solo tienes el Excel:**
1. La app arranca con un admin nuevo (`admin` / `guardtire2025`).
2. Re-crea los operarios desde ⚙️ Usuarios.
3. Las garantías históricas **viven en tu Excel** para consulta.
4. Las nuevas garantías se numeran desde **501** otra vez.

---

## 🛠️ Problemas comunes

**La app dice "Application failed to respond" o muestra error 500**
→ Ve a Railway → tu servicio → **Deployments** → clic en el último deploy
   → **View Logs**. Casi siempre es una variable de entorno faltante
   o mal escrita.

**Los correos no se envían**
→ Verifica:
1. Que `RESEND_API_KEY` esté bien escrita.
2. Que en Resend → **Domains**, `guardtire.com` esté en verde (verificado).
3. Que el correo destino sea válido.

**No me deja entrar como admin después de subir todo**
→ Si es la primera vez, usa `admin` / `guardtire2025`.
   Si cambiaste la contraseña y la olvidaste, necesitas ayuda técnica para
   resetearla directamente en la base de datos.

**Hice cambios al código en GitHub pero la app sigue igual**
→ Railway re-despliega solo al detectar un push. Espera 2 minutos y
   revisa **Deployments** → debe haber uno nuevo con estado verde.
   Refresca la página con **Ctrl + F5** para evitar caché del navegador.

---

## ⚙️ Configuración técnica (referencia rápida)

Variables de entorno reconocidas por la app:

| Variable | Para qué sirve | Valor por defecto |
|----------|---------------|--------------------|
| `SECRET_KEY` | Clave de sesión Flask | `guardtire-secret-2025` (cámbiala en producción) |
| `DATABASE_URL` | URL de Postgres | `sqlite:///guardtire.db` (solo desarrollo local) |
| `RESEND_API_KEY` | Token de envío de correos | sin valor → no envía |
| `PDF_FOLDER` | Carpeta de PDFs generados | `pdfs` |
| `PORT` | Puerto HTTP | `5000` |

Estructura del proyecto:

```
garantias/
├── app.py              # Backend Flask completo
├── requirements.txt    # Dependencias Python
├── Dockerfile          # Cómo se empaqueta la app
├── README.md           # Este archivo
├── templates/
│   ├── login.html      # Pantalla de login
│   └── dashboard.html  # Aplicación principal
└── static/
    └── logo.png        # Logo en el PDF
```

Ejecutar localmente (necesitas Python 3.11):

```bash
pip install -r requirements.txt
python app.py
# Abrir http://localhost:5000
```

Roles de usuario:

| Rol | Qué puede hacer |
|-----|----------------|
| **admin** | Todo: calculadora, garantías, historial completo (editar/eliminar/exportar Excel), gestión de usuarios, plantilla de correo |
| **operario** | Calculadora, crear garantías, ver historial, descargar PDFs, reenviar correos |
