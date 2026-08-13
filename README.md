# Gestión de Contratos

Aplicación local para crear contratos Word editables a partir de una plantilla `.docx`.

## Requisitos

- Python 3.11 o superior

## Instalación en Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Ejecutar

Desde la carpeta `ContratosApp`:

```powershell
streamlit run app.py
```

## Plantillas

Coloque sus plantillas Word en la carpeta `plantillas/` para seleccionarlas desde la aplicación. También puede cargar una plantilla `.docx` de forma puntual; esta tendrá prioridad sobre cualquier plantilla guardada.

El contrato se genera en memoria, no altera la plantilla original y se descarga como Word completamente editable.

## Pruebas

```powershell
python -m unittest discover -s tests
```

## Integración con Google Drive

La aplicación convierte cada DOCX generado en un Google Docs editable dentro de
la carpeta de revisión. El DOCX sigue disponible como descarga de respaldo.

1. En Google Cloud, habilite **Google Drive API**.
2. Cree un cliente OAuth de tipo **Desktop app**.
3. Descargue el archivo de credenciales y nómbrelo `credentials.json`.
4. Colóquelo en `ContratosApp/credentials.json` (junto a `app.py`).
5. Revise `DRIVE_REVIEW_FOLDER_ID` en `config.py`. Inicialmente reutiliza la
   carpeta configurada en el notebook original.
6. Instale dependencias y ejecute la comprobación:

   ```powershell
   python test_drive.py
   ```

   La primera vez se abrirá el navegador para autorizar la cuenta corporativa;
   se generará `token.json` localmente.
7. Ejecute la app con `streamlit run app.py`.

`credentials.json`, `token.json`, `client_secret*.json` y `.env` son privados:
**no deben subirse a Git**. Si los scopes cambian en el futuro, elimine sólo el
archivo local `token.json` y autorice nuevamente.

### Despliegue en Streamlit Community Cloud

El navegador OAuth de escritorio se usa solo localmente. Primero ejecute
`python test_drive.py` para crear y autorizar `token.json`. Luego, en **App
settings → Secrets** de Streamlit Community Cloud, agregue:

```toml
# Pegue aquí el contenido completo de token.json, sin subirlo a Git.
GOOGLE_OAUTH_TOKEN = '''PEGAR_AQUI_EL_CONTENIDO_DE_token.json'''

# Opcional: carpeta de pruebas distinta para la app desplegada.
DRIVE_REVIEW_FOLDER_ID = "ID_DE_LA_CARPETA_DE_DRIVE"
```

La app desplegada utiliza ese token para la cuenta corporativa ya autorizada.
Todos los documentos creados usarán dicha cuenta. Si el token se revoca, vuelva
a autorizar en local y reemplace el secreto `GOOGLE_OAUTH_TOKEN`.

## Integración con Google Sheets

1. Habilite **Google Sheets API** además de Google Drive API en el mismo
   proyecto de Google Cloud.
2. Configure el ID del archivo de Google Sheets en `SPREADSHEET_ID`: puede
   hacerlo en `config.py` para local o como Secret/variable de entorno en
   Streamlit Community Cloud.
3. La pestaña debe llamarse `Contratos_Pendientes` y usar las columnas A:M:
   `ID, Fecha, Nombres, Apellidos, DNI, Celular, Email, Ciudad, País, Monto,
   Banco, Productos, Estado`.
4. Para abrir un registro desde Apps Script use:

   ```text
   https://tu-app.streamlit.app/?registro=UUID
   ```

   La app sólo recibe el UUID, carga una vez los datos y deja el formulario
   editable. Sin `registro`, el ingreso manual y el pegado desde Excel siguen
   funcionando normalmente.
5. Después de crear correctamente el DOCX, la app cambia el estado de
   `Pendiente` a `Generado`. Si falla el DOCX, el estado no se modifica.

El OAuth ahora requiere los scopes de Drive y Sheets. **Una sola vez**, elimine
manualmente `token.json`, ejecute `python test_drive.py` y autorice de nuevo.
No elimine el token desde el código ni suba `credentials.json`/`token.json` a Git.

Para Streamlit Cloud, actualice el Secret `GOOGLE_OAUTH_TOKEN` con el nuevo
contenido de `token.json` tras autorizar nuevamente y agregue:

```toml
SPREADSHEET_ID = "ID_DE_TU_GOOGLE_SHEETS"
```

## Nota sobre la migración

La app conserva los placeholders y el formato de fecha del notebook original. Se corrigió el componente de fecha del nombre de archivo, que antes fijaba el año `2026`: ahora usa la fecha elegida. El sufijo contractual `acuerdo 2026` se mantiene por compatibilidad y está centralizado en `SUFIJO_CONTRACTUAL` dentro de `generador.py`.
