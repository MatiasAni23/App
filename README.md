# Generación de borradores de contrato

Aplicación FastAPI para cargar contratos desde Google Sheets, generar un DOCX
editable y enviar el PDF final a n8n para su flujo de firma.

## Desarrollo local

```powershell
cd ContratosApp
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

Abra `http://localhost:8000` o `http://localhost:8000/?registro=UUID`.

Para desarrollo local se conserva el OAuth existente con `credentials.json` y
`token.json` junto a `ContratosApp/app.py`. Ambos archivos son privados y están
ignorados por Git.

## Google Sheets y Drive

La hoja debe contener la pestaña `Contratos_Pendientes` con las columnas A:M:
`ID, Fecha, Nombres, Apellidos, DNI, Celular, Email, Ciudad, País, Monto,
Banco, Productos, Estado`.

La aplicación marca `Generado` sólo cuando el DOCX se crea correctamente. n8n
es responsable de cambiar el estado a `Enviado` y posteriormente el flujo de
firma puede cambiarlo a `Firmado`.

## Variables de entorno

Copie `.env.example` como `.env` para desarrollo local si lo necesita. No suba
ningún archivo `.env` ni credenciales al repositorio.

```text
GOOGLE_SERVICE_ACCOUNT_JSON
SPREADSHEET_ID
DRIVE_REVIEW_FOLDER_ID
N8N_ZAPSIGN_WEBHOOK_URL
N8N_WEBHOOK_SECRET
```

En producción, configure `GOOGLE_SERVICE_ACCOUNT_JSON` con el JSON completo de
una Service Account. Comparta la hoja de cálculo y la carpeta de Drive con el
email de esa Service Account; para archivos de Drive se recomienda una Unidad
compartida. En local, si esta variable no existe, la aplicación utiliza el OAuth
existente.

Si cambia los scopes de Google, elimine manualmente `token.json` una vez y vuelva
a autorizar. No lo elimine desde código.

## Despliegue en Vercel

1. Conecte el repositorio a Vercel.
2. Configure **Root Directory** como `ContratosApp`.
3. Añada las variables de entorno indicadas arriba en Vercel.
4. Despliegue. Vercel detectará la instancia `app = FastAPI()` de `app.py`; no
   se requiere Dockerfile ni `vercel.json` para esta estructura.
5. Actualice la URL de Apps Script desde la antigua URL Streamlit a:

   ```text
   https://TU-PROYECTO.vercel.app/?registro=UUID
   ```

## Pruebas

```powershell
cd ContratosApp
python -m unittest discover -s tests
```

Las pruebas no realizan llamadas reales a Google Sheets, Google Drive ni n8n.
