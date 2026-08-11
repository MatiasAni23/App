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

## Nota sobre la migración

La app conserva los placeholders y el formato de fecha del notebook original. Se corrigió el componente de fecha del nombre de archivo, que antes fijaba el año `2026`: ahora usa la fecha elegida. El sufijo contractual `acuerdo 2026` se mantiene por compatibilidad y está centralizado en `SUFIJO_CONTRACTUAL` dentro de `generador.py`.
