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

En producción, la aplicación sólo se abre mediante el enlace temporal generado
por Apps Script. Abrir el dominio o `/?registro=UUID` directamente devuelve
403. Para probar el flujo local se debe configurar el mismo secreto en Apps
Script y en el entorno local; la cookie es `Secure`, por lo que el flujo real
debe probarse sobre HTTPS.

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
APP_ACCESS_SECRET
```

`APP_ACCESS_SECRET` debe ser un secreto aleatorio largo. Configure exactamente
el mismo valor como variable de entorno en Vercel y como Script Property en
Apps Script con el nombre `APP_ACCESS_SECRET`. No lo incluya en el código ni
lo envíe al navegador.

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
5. Configure `APP_ACCESS_SECRET` y actualice Apps Script para usar la ruta
    temporal `/access`:

    ```javascript
    function generarTokenAcceso_(registroId, expiracion) {
       const secreto = PropertiesService.getScriptProperties().getProperty('APP_ACCESS_SECRET');
       if (!secreto) throw new Error('Falta Script Property APP_ACCESS_SECRET');
       const firma = Utilities.computeHmacSha256Signature(`${registroId}:${expiracion}`, secreto);
       return firma.map(byte => {
          const valor = byte < 0 ? byte + 256 : byte;
          return ('0' + valor.toString(16)).slice(-2);
       }).join('');
    }

    const expiracion = Math.floor(Date.now() / 1000) + 30 * 60;
    const token = generarTokenAcceso_(registroId, expiracion);
    const baseUrl = CONFIG.STREAMLIT_URL.replace(/\/+$/, '');
    const url = `${baseUrl}/access?` +
       `registro=${encodeURIComponent(registroId)}` +
       `&exp=${expiracion}` +
       `&token=${encodeURIComponent(token)}`;
    ```

    Sustituya con este bloque sólo la construcción de la URL actual. Mantenga
    la creación del UUID y el resto del flujo sin cambios.

## Pruebas

```powershell
cd ContratosApp
python -m unittest discover -s tests
```

Las pruebas no realizan llamadas reales a Google Sheets, Google Drive ni n8n.
# Editor de documentos (ONLYOFFICE)

La edición DOCX es opcional: FastAPI conserva el contrato en Google Drive y
ONLYOFFICE Docs se ejecuta como un servicio externo, nunca dentro de Vercel.
Al generar un contrato asociado a un `registro_id`, la aplicación guarda esa
asociación en Google Drive y ofrece **Abrir en Drive** y **Abrir editor de
documento**. ONLYOFFICE descarga un DOCX mediante una URL temporal firmada y,
cuando informa un guardado (estados 2 o 6), FastAPI descarga la versión editada
y actualiza el mismo archivo de Drive.

Configura en Vercel, sin subir secretos al repositorio:

```text
ONLYOFFICE_DOCUMENT_SERVER_URL=https://tu-document-server
ONLYOFFICE_JWT_SECRET=                 # si el Document Server usa JWT
ONLYOFFICE_JWT_HEADER=AuthorizationJWT # encabezado configurado en Document Server
ONLYOFFICE_URL_SIGNING_SECRET=         # secreto aleatorio largo para URLs temporales
APP_BASE_URL=https://tu-app.vercel.app
```

Si faltan `ONLYOFFICE_DOCUMENT_SERVER_URL`,
`ONLYOFFICE_URL_SIGNING_SECRET` o `APP_BASE_URL`, el editor queda deshabilitado
y el flujo existente de Drive, PDF y n8n continúa funcionando normalmente.
