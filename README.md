# Dedupper - Detector de Archivos Duplicados + Generador de Miniaturas

Aplicación web Flask para detectar y eliminar archivos duplicados, y generar miniaturas de imágenes.

## 🚀 Inicio Rápido

```powershell
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
python app.py

# Abrir en navegador
# http://localhost:5000
```

## 🔧 Funcionalidades

### 1. Detector de Duplicados 🔍
- Escanea carpetas (recursivo o no)
- Agrupa archivos por tamaño
- Calcula MD5 solo de candidatos (eficiente)
- Muestra grupos de duplicados con links clickeables
- Botón "Dedup it!" elimina duplicados conservando el primero
- Reporta espacio recuperado en MB

### 2. Generador de Miniaturas 🖼️
- Procesa imágenes grandes (>1280px)
- Redimensiona manteniendo proporción
- Guarda originales en carpeta "Originales"
- Opción de eliminar originales después

## 📋 Uso

1. **Pegar ruta**: Usa el botón 📋 para pegar desde portapapeles
2. **Elegir modo**: Marca/desmarca "Incluir subcarpetas"
3. **Ejecutar**: Click en "Buscar Duplicados" o "Generar Miniaturas"
4. **Revisar**: Click en rutas de archivos para abrirlos
5. **Deduplicar**: Click en "Dedup it!" para eliminar duplicados de un grupo
6. **Limpiar**: Botón 🔄 para resetear resultados

## ⚠️ Importante: Caché del Navegador

### Problema
Los navegadores cachean agresivamente el HTML/JS, lo que puede mostrar versiones antiguas después de actualizar el código.

### Solución Implementada
El código usa **versionado automático por timestamp**:
- Cada reinicio del servidor genera una nueva versión única
- El número de versión se muestra en el título y header
- Todas las peticiones incluyen parámetro `?v={timestamp}`
- Headers HTTP deshabilitan caché explícitamente

### Si Aún Ves Versión Antigua
1. **Ctrl + Shift + R** (hard refresh en Chrome/Edge)
2. **Cerrar y reabrir el navegador completamente**
3. **Modo incógnito** (Ctrl + Shift + N)
4. **Simple Browser de VS Code** (mejor para desarrollo)

### Verificar Versión Actual
Mira el número de versión en:
- Título de la página del navegador
- Header principal (pequeño, gris, al lado del título)

## 🛠️ Desarrollo

### Estructura del Código
```
app.py
├── Variables globales (estado_actual, procesando, VERSION)
├── Funciones de utilidad (log_status, hash_file)
├── Funciones de deduplicación (agrupar_por_tamaño, verificar_duplicados_por_hash)
├── Funciones de miniaturas (procesar_miniaturas, procesar_miniaturas_no_recursivo)
├── HTML embebido (con versionado dinámico)
└── Rutas Flask (/estado, /buscar_duplicados, /generar_miniaturas, etc.)
```

### Estilo de Código (Heredado de GetIt)
- Comentarios en español
- Section markers: `# --- Nombre de Sección ---`
- Estado global con diccionarios
- Threading daemon para operaciones largas
- Flags de detención (`detener_flag`)
- Logging detallado con `log_status()`

### Testing Rápido
```powershell
# Crear carpeta de prueba con duplicados
New-Item -ItemType Directory -Path "test_dupes"
"contenido" | Out-File "test_dupes/file1.txt"
Copy-Item "test_dupes/file1.txt" "test_dupes/file2.txt"

# Buscar duplicados en test_dupes
# Debería encontrar 1 grupo con 2 archivos
```

## 📝 Logs

Los logs se guardan en `Logs/log-YYYYMMDD_HHMMSS.txt` (pendiente de implementar).

## ⚡ Performance

- **Eficiencia**: Solo calcula MD5 de archivos con mismo tamaño
- **Memory-safe**: Lee archivos en chunks de 8KB
- **Thread-safe**: Operaciones largas no bloquean la UI
- **Cancelable**: Flag de detención respetado en loops

## ⚠️ Known Limitations

### 🔒 Windows Session Lock Issue

**DO NOT lock your Windows session** while a scan is in progress.

**Problem:** The process may hang because Windows suspends I/O operations when the session is locked, especially with:
- Network drives (`\\server\...`)
- External USB devices
- Files in user profile (`C:\Users\...`)

**Recommendations:**
- ✅ Keep session active during long scans
- ✅ Use "Stop" button before locking
- ✅ Use screensaver without lock (screen off only)
- ✅ For very long scans, avoid network/USB folders

**Workaround:** If you need to lock, run scans on:
- Local secondary drives (D:\, E:\, etc.)
- Folders outside your user profile

**Technical Cause:** `ThreadPoolExecutor` with blocking I/O gets stuck when Windows suspends file read operations during session lock. This is a known limitation that will be addressed in v1.1.0.

**See:** `ANALISIS_BLOQUEO_SESION.md` for detailed technical analysis.

## 🐛 Troubleshooting

### "Ya hay un proceso en ejecución"
- Click en "Detener" primero
- O click en "Limpiar" para resetear estado

### Links de archivos no abren
- Verifica permisos de archivos
- Algunos archivos pueden estar en uso

### Error de permisos al eliminar
- Cierra aplicaciones que usen los archivos
- Ejecuta como administrador si es necesario

### Process hangs after locking Windows session
- See "Windows Session Lock Issue" above
- Restart Dedupper.exe if already hung
- Avoid locking during future scans

## 📄 Licencia

Proyecto de desarrollo interno.
