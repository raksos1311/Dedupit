# 📦 Dedupper v1.0.0 - Release Notes

## 🎉 Distribución Completa

**Fecha de Release:** 10 de Noviembre, 2025  
**Versión:** 1.0.0  
**Plataforma:** Windows x64  
**Tamaño del Paquete:** 19.9 MB

---

## 📥 Archivos de Distribución

### Paquete Principal
- **`Dedupper-v1.0.0-Windows-x64.zip`** (19.9 MB)
  - Ejecutable standalone completo
  - No requiere instalación de Python
  - No requiere dependencias adicionales
  - Listo para ejecutar

### Contenido del Paquete
```
Dedupper-v1.0.0-Windows-x64/
├── Dedupper.exe      (20.1 MB) - Ejecutable principal
├── README.md         (4.1 KB)  - Documentación en inglés
├── LEEME.txt         (7.9 KB)  - Documentación en español
└── LICENCIA.txt      (2.7 KB)  - MIT License + Disclaimer
```

---

## ✨ Características Principales

### 🔍 Detección Inteligente
- ✅ Detección por tamaño de archivo (primera pasada)
- ✅ Verificación por hash MD5 (segunda pasada)
- ✅ Procesamiento paralelo con ThreadPoolExecutor
- ✅ Workers: 2× número de núcleos CPU
- ✅ Archivos grandes sin problemas (lectura en chunks de 8KB)

### 🚀 Performance
- ✅ Procesamiento paralelo ultrarrápido
- ✅ Actualización progresiva cada 30 segundos
- ✅ No bloquea la interfaz durante el escaneo
- ✅ Puedes eliminar archivos mientras sigue escaneando
- ✅ Manejo eficiente de datasets grandes (testeado con 38,269 grupos)

### 🎯 Eliminación Flexible
- ✅ **Eliminación selectiva**: Marca archivos específicos con checkboxes
- ✅ **Eliminación por grupo**: Botón "Dedup it!" por cada grupo
- ✅ **Eliminación masiva inteligente**: Botón "Dedup all!"
  - Si no hay checkboxes marcados: mantiene el primer archivo de cada grupo
  - Si hay checkboxes: respeta las selecciones del usuario
- ✅ **Limpieza visual**: Botón "Clean dedupped" oculta grupos procesados
- ✅ **Protección**: Botón "Dedup all!" bloqueado durante escaneo

### 🖼️ Características Adicionales
- ✅ Generación de miniaturas para archivos de imagen
- ✅ Logs en tiempo real con timestamps
- ✅ Archivos clickeables (se abren con programa predeterminado)
- ✅ Sistema anti-cache robusto
- ✅ Interfaz web responsive
- ✅ Mensajes de feedback visual (bordes verdes, íconos, etc.)

---

## 💻 Requisitos del Sistema

- **OS:** Windows 10/11 (64-bit)
- **RAM:** 4 GB mínimo (8 GB recomendado para datasets grandes)
- **Espacio:** Variable según tamaño del análisis
- **Permisos:** Lectura/escritura en carpetas a analizar

---

## 🚀 Instalación y Uso Rápido

### Instalación
1. Descomprimir `Dedupper-v1.0.0-Windows-x64.zip`
2. Ejecutar `Dedupper.exe` (doble clic)
3. El navegador se abre automáticamente en `http://localhost:5000`

### Uso Básico
1. Pegar ruta de carpeta en el campo de texto
2. Marcar "Incluir subcarpetas" si se desea
3. Click en "Buscar Duplicados"
4. Esperar resultados (actualización cada 30 segundos)
5. Seleccionar archivos a conservar (checkboxes)
6. Eliminar con botones disponibles

---

## ⚠️ Advertencias Importantes

❗ **Los archivos eliminados NO van a la papelera de reciclaje**  
❗ **La eliminación es PERMANENTE e irreversible**  
❗ **Los checkboxes marcan archivos A CONSERVAR** (no a eliminar)  
❗ **Revisar cuidadosamente antes de eliminar**  
❗ **Hacer backup de datos críticos antes de usar**  

---

## 🐛 Problemas Conocidos

### Crítico: Cuelgue al Bloquear Sesión de Windows 🔒

**Síntoma:** El proceso se cuelga si bloqueas tu sesión de Windows durante un scan.

**Causa:** `ThreadPoolExecutor` con I/O bloqueante se queda esperando cuando Windows suspende operaciones de lectura de archivos al bloquear la sesión.

**Impacto:**
- 🔴 **CRÍTICO** con archivos en red (`\\servidor\...`)
- 🔴 **CRÍTICO** con dispositivos USB externos
- 🟠 **ALTO** con archivos en perfil usuario (`C:\Users\...`)
- 🟢 **BAJO** con discos locales secundarios (`D:\`, `E:\`, etc.)

**Workaround:**
- ✅ NO bloquees la sesión durante scans largos
- ✅ Usa botón "Detener" antes de bloquear
- ✅ Usa screensaver sin bloqueo (solo apaga pantalla)
- ✅ Escanea solo discos locales secundarios si necesitas bloquear

**Estado:** Documentado, no corregido en v1.0.0  
**Roadmap:** Fix programado para v1.1.0 (multiprocessing con timeout)  
**Análisis Técnico:** Ver `ANALISIS_BLOQUEO_SESION.md`

### No Críticos
- El navegador puede no abrirse automáticamente en algunos sistemas
  - **Solución:** Abrir manualmente `http://localhost:5000`

- Cache del navegador puede causar problemas visuales
  - **Solución:** Presionar `Ctrl+F5` para recargar sin cache

### Limitaciones
- Solo Windows x64 (esta versión)
- Puerto 5000 debe estar disponible
- Requiere permisos de lectura/escritura en carpetas objetivo

---

## 📊 Estadísticas de Build

- **Lenguaje:** Python 3.13.9
- **Framework:** Flask 3.0.0
- **Imágenes:** Pillow 10.1.0
- **Builder:** PyInstaller 6.16.0
- **Líneas de Código:** ~1,400 (sin contar dependencias)
- **Módulos Incluidos:** 124 archivos Python
- **DLLs Incluidas:** Python313.dll + dependencias PIL
- **Tiempo de Build:** ~3 minutos

---

## 📝 Changelog

### v1.0.0 (10/Nov/2025)
- ✅ Primera versión estable completa
- ✅ Procesamiento paralelo optimizado con ThreadPoolExecutor
- ✅ Interfaz web completa con Flask
- ✅ Sistema de eliminación selectiva y masiva
- ✅ Actualización progresiva en tiempo real
- ✅ Botón de limpieza de grupos procesados
- ✅ Generación de miniaturas para imágenes
- ✅ Logs detallados con timestamps
- ✅ Sistema anti-cache robusto
- ✅ Protección contra eliminación accidental durante escaneo
- ✅ Documentación completa en español e inglés

---

## 🔧 Para Desarrolladores

### Código Fuente
- **Repositorio Git:** Disponible en tag `v1.0.0-release`
- **Branch:** `master`
- **Commits:** 2 commits totales

### Rebuilding
```bash
# Instalar dependencias
pip install -r requirements.txt
pip install pyinstaller

# Construir ejecutable
python build_exe.py

# El resultado estará en: dist/Dedupper.exe
```

### Estructura del Código
- **Convenciones:** Código en español (estilo GetIt)
- **Secciones:** Marcadas con `# --- Nombre ---`
- **Estado Global:** Diccionario `estado_actual`
- **Thread-safe:** Funciones dedicadas para modificar estado
- **Logging:** Timestamps detallados para debugging

---

## 📄 Licencia

**MIT License** con disclaimer de responsabilidad

- ✅ Uso comercial permitido
- ✅ Modificación permitida
- ✅ Distribución permitida
- ✅ Uso privado permitido
- ⚠️ Sin garantía
- ⚠️ Sin responsabilidad del autor

Ver `LICENCIA.txt` para texto completo.

---

## 🆘 Soporte

Para reportar bugs o sugerir mejoras:
- 📧 Email: [pendiente]
- 🌐 GitHub Issues: [pendiente]
- 📝 Documentación: Ver `README.md` y `LEEME.txt`

---

## 🎯 Roadmap Futuro (Posibles Mejoras)

### v1.1.0 (Próxima versión - Prioridad Alta)
- [ ] **FIX: Cuelgue al bloquear sesión** 🔒
  - Implementar multiprocessing con timeout para I/O
  - Detectar archivos colgados y skipearlos
  - Tiempo estimado: 4-6 horas
  - Issue: Ver `ANALISIS_BLOQUEO_SESION.md`

### v1.2.0 (Mejoras de UX)
- [ ] Modo de análisis sin eliminación (solo reporte)
- [ ] Exportar lista de duplicados a CSV/JSON
- [ ] Filtros por tipo de archivo
- [ ] Búsqueda por nombre de archivo
- [ ] Ordenamiento de resultados

### v2.0.0 (Arquitectura)
- [ ] **Modo servicio de Windows** (solución permanente para session lock)
- [ ] Soporte para Linux y macOS
- [ ] Interfaz de línea de comandos (CLI)
- [ ] API REST para integración
- [ ] Comparación de contenido por similitud (no solo hash exacto)
- [ ] Configuración de puerto personalizado

---

## 🙏 Agradecimientos

Desarrollado con:
- ❤️ Python 3.13
- ⚡ Flask 3.0
- 🖼️ Pillow 10.1
- 📦 PyInstaller 6.16
- 🎨 Convenciones de código del proyecto GetIt

---

## 📊 Resumen de Tags Git

```
v1.0.0          - Código fuente inicial
v1.0.0-release  - Build ejecutable completo
```

---

**¡Gracias por usar Dedupper!** 🎉

*Proyecto completado el 10 de Noviembre de 2025*
