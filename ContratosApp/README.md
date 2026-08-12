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

## Nota sobre la migración

La app conserva los placeholders y el formato de fecha del notebook original. Se corrigió el componente de fecha del nombre de archivo, que antes fijaba el año `2026`: ahora usa la fecha elegida. El sufijo contractual `acuerdo 2026` se mantiene por compatibilidad y está centralizado en `SUFIJO_CONTRACTUAL` dentro de `generador.py`.
