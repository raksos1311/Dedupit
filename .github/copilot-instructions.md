# Dedupper - AI Coding Agent Instructions

## Project Overview
Dedupper es una aplicación web Flask para detectar y administrar archivos duplicados en carpetas locales.  
**Arquitectura**: Flask web app (localhost:5000) con interfaz HTML/Jinja2, detección por tamaño + MD5 hash.

**Main File**: Flask app principal (ref base: `ref_minlotweb1_1.py`)  
**Stack**: Python 3.10+, Flask, hashlib (sin dependencias complejas)

## Core Functionality
**Flujo de detección de duplicados**:
1. **Input**: Ruta base + checkbox "incluir subcarpetas"
2. **Etapa 1 - Filtrado por tamaño**: Agrupar archivos por bytes, solo grupos con 2+ archivos continúan
3. **Etapa 2 - Hash MD5**: Calcular MD5 de candidatos, comparar dentro de cada grupo
4. **Output**: Tabla HTML con nombre/ruta/tamaño/hash + checkbox por archivo
5. **Etapa 3 - Eliminación**: Borrar archivos seleccionados, confirmar y refrescar

## Code Style Conventions (Inherited from GetIt Project)
Estas convenciones provienen del proyecto GetIt y deben mantenerse:

- **Comentarios en español**: Todo el código interno usa español (variables, comentarios, logs)
- **Global state management**: Uso de diccionarios globales para tracking de estado (ej: `file_status_tracker`, `multipart_files` en GetIt)
- **Section markers**: Código dividido por secciones con `# --- Nombre de Sección ---`
- **Thread-safe updates**: Siempre usar funciones dedicadas para modificar estado compartido (ej: `update_file_status()` en GetIt) - nunca modificación directa desde threads
- **Functional style**: Preferir funciones con estado global sobre clases cuando sea práctico
- **Color coding**: Definir constantes de color UI al inicio como `COLOR_*`
- **Detailed logging**: Sistema de logs con timestamps en `Logs/log-YYYYMMDD_HHMMSS.txt` para debugging

## Key Functions to Implement

### 1. Core Deduplication Logic
```python
def find_duplicates(base_path, recursive=True):
    """
    Retorna lista de grupos duplicados.
    1. Escanear archivos y agrupar por tamaño
    2. Calcular MD5 solo para grupos con 2+ archivos
    3. Retornar diccionario: {hash: [paths]}
    """

def hash_file(path):
    """Genera hash MD5 de un archivo (leer en chunks para archivos grandes)"""

def delete_files(list_of_paths):
    """Elimina archivos seleccionados y retorna count exitosos/fallidos"""
```

### 2. Flask Routes Structure
```python
@app.route('/')  # Formulario principal
@app.route('/duplicates', methods=['GET', 'POST'])  # Búsqueda y eliminación
```

### 3. State Tracking (si se necesita async/progress)
Si se implementa tracking de progreso, usar patrón de GetIt:

```python
scan_tracker = {
    "scan_id": {
        "status_msg": "│ Escaneando archivos...",
        "stage": "scanning",  # scanning/hashing/done
        "files_processed": 0,
        "total_files": 0
    }
}
```

### 4. Threading Patterns (Optional - For Large Scans)
Si el escaneo toma mucho tiempo, considerar:
- **Daemon thread** para escaneo async
- **Event objects**: `threading.Event()` para cancelación
- **Progress tracking**: Actualizar contador de archivos procesados

### 5. HTML Interface Guidelines
- **Form principal**: Input text (ruta), checkbox (recursivo), botón "Buscar"
- **Tabla resultados**: Usar Jinja2 template, columnas: checkbox | nombre | ruta | tamaño | hash
- **Botón eliminar**: POST a `/duplicates` con lista de paths seleccionados
- **Confirmación**: Mostrar mensaje con count de archivos eliminados

### 6. File I/O Best Practices
```python
# Leer archivos en chunks para MD5 (evitar memory issues con archivos grandes)
def hash_file(path):
    md5 = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5.update(chunk)
    return md5.hexdigest()

# Manejo de errores al eliminar
try:
    os.remove(path)
except PermissionError:
    # Log y continuar con siguiente archivo
    pass
```

### 7. UI Color Coding (Web Interface)
Si se implementa feedback visual en HTML:
- **Verde**: Archivos escaneados con éxito
- **Amarillo**: Grupos duplicados detectados
- **Rojo**: Errores de acceso/eliminación
- **Naranja**: Advertencias (permisos, archivos en uso)

**Iconos útiles**: � (escaneando), ⚠️ (duplicado), ✅ (eliminado), ❌ (error)

## Development Workflows

### Initial Setup
```powershell
# Instalar dependencias (Flask mínimo)
pip install flask

# O si existe requirements.txt
pip install -r requirements.txt

# Ejecutar aplicación Flask
python app.py  # o el archivo principal Flask
# Acceder en: http://localhost:5000
```

### Adding New Features
Patrón para extender funcionalidad:
1. **Nueva ruta Flask**: Agregar `@app.route()` decorator
2. **Template Jinja2**: Crear HTML en `templates/` (si se separa del main)
3. **Función helper**: Agregar en sección `# --- Helper Functions ---`
4. **Logging**: Usar `app.logger.info()` para debugging

### Debugging
- **Session logs**: `Logs/log-YYYYMMDD_HHMMSS.txt` para traces detallados
- **Console logging**: `log_to_session(msg, type)` para eventos en tiempo real
- **Estado tracker**: Widget/panel que muestra estado por entidad

## Configuration Management
- **Flask config**: Usar `app.config[]` para parámetros (puerto, debug mode)
- **Ruta default**: Considerar guardar última ruta escaneada en session/cookie
- **Environment vars**: `.env` para configuración de producción (si se deploya)

## Common Pitfalls to Avoid
1. **Archivos grandes**: NO cargar archivos completos en memoria - usar chunks para MD5
2. **Permisos de archivos**: Manejar `PermissionError` al leer/eliminar archivos
3. **Paths absolutos vs relativos**: Normalizar rutas con `os.path.abspath()`
4. **Confirmación de eliminación**: SIEMPRE mostrar preview antes de borrar
5. **Flask debug mode**: Desactivar en producción (`debug=False`)
6. **Encoding de paths**: Manejar rutas con caracteres especiales/unicode

## Integration Points
- **File System**: `os.walk()` para escaneo recursivo, `os.path.getsize()` para tamaño
- **Hashing**: `hashlib.md5()` para checksums (leer en chunks de 8KB)
- **Flask Templates**: Jinja2 para renderizar tablas HTML dinámicas
- **Static Files**: CSS opcional en `static/` para mejorar UI

## Testing Checklist
Cuando se implemente funcionalidad:
- [ ] Escaneo de carpeta sin subcarpetas
- [ ] Escaneo recursivo (incluir subcarpetas)
- [ ] Detección correcta de duplicados (mismo tamaño + hash)
- [ ] Manejo de archivos sin permisos de lectura
- [ ] Eliminación de archivos seleccionados
- [ ] Manejo de archivos en uso (Windows locks)
- [ ] Rutas con espacios y caracteres especiales
- [ ] Archivos grandes (>100MB) sin memory issues

## Quick File Discovery
```powershell
# Buscar entry points y funciones clave Flask
Select-String -Path *.py -Pattern "@app.route|def find_duplicates|def hash_file|def delete_files" -SimpleMatch -List

# Listar templates HTML
Get-ChildItem -Path templates -Filter *.html -ErrorAction SilentlyContinue

# Ver estructura del proyecto
tree /F /A
```

## Expected Project Structure
```
Dedupper/
├── app.py                  # Main Flask application
├── templates/              # Jinja2 templates (opcional)
│   ├── index.html         # Formulario principal
│   └── results.html       # Tabla de duplicados
├── static/                 # CSS/JS (opcional)
├── Logs/                   # Session logs
├── requirements.txt        # Python dependencies
└── .gitignore
```

## Project Status
**Estado actual**: Proyecto en desarrollo inicial basado en especificación.  
**Base de referencia**: `ref_minlotweb1_1.py` (estructura Flask).  
**Próximos pasos**: Implementar `find_duplicates()`, rutas Flask, y templates HTML.

---

**Nota**: Este archivo se actualizará conforme se desarrolle el proyecto. Mantener sincronizado con cambios arquitectónicos importantes.