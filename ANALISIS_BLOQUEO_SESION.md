# 🔍 Análisis: Cuelgue al Bloquear Sesión de Windows

## 📋 Problema Reportado
El script se cuelga cuando se bloquea la sesión de Windows, mientras que otros servicios (como FTP) siguen funcionando normalmente.

## 🔎 Causas Identificadas

### 1. **ThreadPoolExecutor con I/O en Sesión Bloqueada** ⚠️ CAUSA PRINCIPAL
**Ubicación:** `verificar_duplicados_por_hash()` - Línea 153

```python
with ThreadPoolExecutor(max_workers=num_workers) as executor:
    futures = {executor.submit(hash_file_wrapper, ruta): ruta for ruta in rutas}
    for idx, future in enumerate(as_completed(futures)):
        # ... procesamiento ...
```

**Problema:**
- Cuando bloqueas la sesión, Windows suspende ciertas operaciones de I/O de aplicaciones de usuario
- `ThreadPoolExecutor` está leyendo archivos en disco en paralelo
- Si los archivos están en unidades de red, dispositivos USB, o ciertas rutas del perfil de usuario, el acceso se puede suspender/ralentizar extremadamente
- El `as_completed()` se queda esperando indefinidamente a que los futures terminen
- Los threads worker quedan bloqueados en operaciones de lectura de disco

### 2. **Daemon Threads que No Se Limpian Correctamente** ⚠️
**Ubicación:** Línea 849

```python
threading.Thread(target=buscar_duplicados, args=(carpeta, recursivo), daemon=True).start()
```

**Problema:**
- Los threads con `daemon=True` se terminan abruptamente cuando el proceso principal termina
- PERO cuando la sesión se bloquea, no se terminan, quedan en estado zombie
- Si el thread está en mitad de una operación de I/O bloqueante, se queda pegado ahí

### 3. **Flask en Modo Debug=False sin Timeout** ⚠️
**Ubicación:** Línea 1013

```python
app.run(host="0.0.0.0", port=5000, debug=False)
```

**Problema:**
- Flask usa el servidor Werkzeug development server
- No tiene timeouts configurados para requests
- Al bloquear sesión, el servidor puede quedar esperando respuestas de los threads que nunca llegan

### 4. **Falta de Signal Handlers** ⚠️
**Problema:**
- No hay manejo de señales del sistema (SIGTERM, SIGHUP, etc.)
- Cuando Windows bloquea la sesión, puede enviar señales que el script no maneja
- El proceso queda en estado indefinido

## 📊 Comparación con FTP Server

### ¿Por qué FTP sigue funcionando?
Los servidores FTP profesionales:
1. **Usan I/O asíncrono no bloqueante**
2. **Tienen timeouts configurados en todas las operaciones**
3. **Se ejecutan como servicios del sistema** (no como aplicaciones de usuario)
4. **Manejan señales del sistema correctamente**
5. **No dependen de la sesión de usuario para I/O**

### Dedupper actual:
1. ❌ I/O bloqueante (lectura de archivos sincrónica)
2. ❌ Sin timeouts
3. ❌ Aplicación de usuario (no servicio)
4. ❌ Sin manejo de señales
5. ❌ Depende de la sesión activa para acceso a disco

## 🧪 Escenarios Específicos

### Escenario A: Archivos Locales (C:\Users\...)
- **Impacto:** ALTO
- **Razón:** Windows suspende acceso a perfiles de usuario al bloquear
- **Resultado:** ThreadPoolExecutor se cuelga esperando lectura de archivos

### Escenario B: Archivos en Red (\\servidor\...)
- **Impacto:** CRÍTICO
- **Razón:** Credenciales de red se suspenden al bloquear sesión
- **Resultado:** Timeout infinito en lecturas de red

### Escenario C: Discos Externos USB
- **Impacto:** CRÍTICO
- **Razón:** Windows puede suspender alimentación USB al bloquear
- **Resultado:** Dispositivo inaccesible, lecturas colgadas

### Escenario D: Discos Locales Secundarios (D:\, E:\...)
- **Impacto:** BAJO-MEDIO
- **Razón:** Acceso generalmente no se suspende, pero puede ralentizarse
- **Resultado:** Script continúa pero muy lento

## 🔬 Evidencia Técnica

### Punto de Bloqueo Probable
```python
def hash_file(ruta):
    md5 = hashlib.md5()
    try:
        with open(ruta, 'rb') as f:  # ← AQUÍ SE CUELGA
            for chunk in iter(lambda: f.read(8192), b''):  # ← O AQUÍ
                md5.update(chunk)
        return md5.hexdigest()
```

**Razón:** El `open()` o `read()` se bloquea indefinidamente esperando I/O del sistema operativo que nunca llega.

### Comportamiento del ThreadPoolExecutor
```python
for idx, future in enumerate(as_completed(futures)):  # ← ESPERA INFINITA
    ruta, hash_md5 = future.result()  # ← Nunca retorna
```

**Razón:** `as_completed()` espera a que TODOS los futures terminen. Si uno se cuelga, todo se cuelga.

## ✅ ¿Es un Problema Real?

### Sí, ES un problema si:
- ✅ Los usuarios van a ejecutar scans largos (horas) en laptops
- ✅ Se usan archivos de red o USB
- ✅ Se espera que funcione como servicio/background
- ✅ Los usuarios bloquean pantalla frecuentemente (seguridad corporativa)

### No es problema si:
- ❌ Solo se usa en sesiones activas (usuario presente)
- ❌ Scans cortos (minutos, no horas)
- ❌ Solo archivos locales en discos internos
- ❌ Uso casual/personal sin requisitos de uptime

## 🛠️ Soluciones Posibles

### Solución 1: Timeouts en I/O (FÁCIL) ⭐
```python
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Lectura de archivo excedió timeout")

def hash_file_with_timeout(ruta, timeout=30):
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    try:
        return hash_file(ruta)
    finally:
        signal.alarm(0)
```

**Ventaja:** Fácil de implementar  
**Desventaja:** `signal.alarm()` no funciona en Windows 😢

### Solución 2: Usar multiprocessing con timeout (MEDIO) ⭐⭐
```python
from multiprocessing import Process, Queue
import queue

def hash_with_timeout(ruta, timeout=30):
    q = Queue()
    p = Process(target=lambda: q.put(hash_file(ruta)))
    p.start()
    p.join(timeout)
    
    if p.is_alive():
        p.terminate()
        return None
    
    try:
        return q.get_nowait()
    except queue.Empty:
        return None
```

**Ventaja:** Funciona en Windows  
**Desventaja:** Overhead de procesos, más complejo

### Solución 3: Modo Servicio de Windows (DIFÍCIL) ⭐⭐⭐
Convertir en servicio de Windows con `pywin32`:
- Se ejecuta en sesión del sistema
- No se afecta por bloqueo de usuario
- Requiere instalación con permisos de admin

### Solución 4: Documentar Limitación (MUY FÁCIL) ⭐
Agregar en README:
> ⚠️ **Limitación:** No bloquear la sesión de Windows durante scans largos. El proceso se puede colgar debido a suspensión de I/O del sistema operativo.

### Solución 5: Detectar Sesión Bloqueada y Pausar (MEDIO) ⭐⭐
```python
import ctypes
import win32ts

def is_session_locked():
    session_id = win32ts.WTSGetActiveConsoleSessionId()
    session_info = win32ts.WTSQuerySessionInformation(
        win32ts.WTS_CURRENT_SERVER_HANDLE,
        session_id,
        win32ts.WTSSessionInfo
    )
    return session_info['State'] == win32ts.WTSDisconnected
```

## 📝 Recomendaciones

### Para v1.0.0 (ACTUAL) - Sin Cambios
**Acción:** Solo documentar la limitación

**Agregar a LEEME.txt y README.md:**
```
⚠️ LIMITACIÓN CONOCIDA: Bloqueo de Sesión
────────────────────────────────────────────────────────────────
Si bloqueas tu sesión de Windows mientras el escaneo está en progreso,
el proceso puede colgarse debido a la suspensión de operaciones de I/O
del sistema operativo (especialmente con archivos en red o USB).

RECOMENDACIONES:
• No bloquees la sesión durante scans largos
• Si debes bloquear, detén el scan primero (botón "Detener")
• Para scans muy largos, considera ejecutar en máquina virtual
  o servidor que no se bloquee automáticamente
• Evita escanear unidades de red o USB si planeas bloquear

ALTERNATIVA:
Usa el modo de pantalla en blanco o screensaver que no bloquee
la sesión (solo apague pantalla).
```

### Para v1.1.0 (FUTURO) - Con Fix Parcial
**Acción:** Implementar Solución 2 (multiprocessing con timeout)

**Ventajas:**
- Detecta archivos colgados y los skippea
- Mejora robustez general
- No requiere cambios arquitectónicos mayores

**Tiempo estimado:** 4-6 horas desarrollo + testing

### Para v2.0.0 (FUTURO) - Fix Completo
**Acción:** Convertir en servicio de Windows o usar I/O asíncrono

**Ventajas:**
- Solución permanente
- Mejor para uso profesional/corporativo
- No se afecta por bloqueo de sesión

**Tiempo estimado:** 2-3 días desarrollo + testing

## 🎯 Decisión para ESTE Release (v1.0.0)

### Veredicto: **DOCUMENTAR, NO ARREGLAR** ✅

**Razones:**
1. **Scope Creep:** Arreglarlo ahora retrasa el launch
2. **Complejidad:** Requiere refactoring significativo
3. **Caso de Uso:** La mayoría de usuarios no bloquearán durante scans largos
4. **Workaround Disponible:** Simplemente no bloquear sesión
5. **Low Priority:** No afecta funcionalidad core si se usa correctamente

**Acción Inmediata:**
- Actualizar documentación con la limitación
- Agregar nota en LEEME.txt
- Incluir en "Known Issues" de RELEASE_NOTES.md
- Marcar como mejora para v1.1.0 en roadmap

## 📈 Tracking

- **Issue ID:** [pendiente]
- **Priority:** P2 (Medium)
- **Milestone:** v1.1.0
- **Effort:** Medium (4-6 hours)
- **Status:** Documented, Not Fixed

---

**Fecha de Análisis:** 10/Nov/2025  
**Analista:** GitHub Copilot  
**Versión Afectada:** v1.0.0  
**Estado:** Análisis Completo ✅
