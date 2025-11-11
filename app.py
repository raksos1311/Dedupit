# app.py - Dedupper: Detector de Archivos Duplicados + Generador de Miniaturas
import os
import hashlib
import threading
from collections import defaultdict
from flask import Flask, render_template_string, request, jsonify
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import time as time_module

# --- Configuración ---
app = Flask(__name__)
MAX_SIZE = 1280

# Versión del código (incrementar manualmente o usar timestamp)
import time
VERSION = str(int(time.time()))  # Timestamp como versión única

# --- Variables globales ---
procesando = False
detener_flag = False
escaneo_completo = False  # Indica si el escaneo terminó (para habilitar/deshabilitar Dedup all!)
estado_actual = {
    "mensaje": "Esperando orden...",
    "detalles": [],
    "resumen": {},
    "duplicados": []  # Lista de grupos duplicados
}

# --- Funciones de utilidad ---
def log_status(msg):
    """Registra mensajes en el log visible"""
    estado_actual["detalles"].append(msg)
    if len(estado_actual["detalles"]) > 500:
        estado_actual["detalles"].pop(0)
    print(msg)


def hash_file(ruta):
    """
    Genera hash MD5 de un archivo leyendo en chunks.
    Evita cargar archivos grandes en memoria.
    """
    md5 = hashlib.md5()
    try:
        with open(ruta, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
        return md5.hexdigest()
    except Exception as e:
        # No usar log_status aquí porque puede ser llamado desde multiprocessing
        return None


def hash_file_wrapper(ruta):
    """
    Wrapper para hash_file que retorna tupla (ruta, hash).
    Usado por multiprocessing.Pool.map()
    """
    hash_resultado = hash_file(ruta)
    return (ruta, hash_resultado)


def agrupar_por_tamaño(carpeta_base, recursivo=True):
    """
    Escanea archivos y los agrupa por tamaño.
    Retorna diccionario: {tamaño_bytes: [lista_rutas]}
    """
    grupos_tamaño = defaultdict(list)
    total_archivos = 0
    
    log_status(f"📂 Escaneando carpeta: {carpeta_base}")
    
    if recursivo:
        for root, _, files in os.walk(carpeta_base):
            if detener_flag:
                break
            for nombre in files:
                ruta = os.path.join(root, nombre)
                try:
                    tamaño = os.path.getsize(ruta)
                    grupos_tamaño[tamaño].append(ruta)
                    total_archivos += 1
                except Exception as e:
                    log_status(f"⚠️ Error al leer {ruta}: {e}")
    else:
        try:
            files = [f for f in os.listdir(carpeta_base) 
                    if os.path.isfile(os.path.join(carpeta_base, f))]
            for nombre in files:
                ruta = os.path.join(carpeta_base, nombre)
                try:
                    tamaño = os.path.getsize(ruta)
                    grupos_tamaño[tamaño].append(ruta)
                    total_archivos += 1
                except Exception as e:
                    log_status(f"⚠️ Error al leer {ruta}: {e}")
        except Exception as e:
            log_status(f"❌ Error al listar carpeta {carpeta_base}: {e}")
    
    log_status(f"✅ Escaneados {total_archivos} archivos")
    return grupos_tamaño


def filtrar_grupos_candidatos(grupos_tamaño):
    """
    Filtra y retorna solo los grupos con 2+ archivos.
    Descarta archivos únicos por tamaño.
    """
    candidatos = {tamaño: rutas for tamaño, rutas in grupos_tamaño.items() 
                  if len(rutas) > 1}
    
    total_candidatos = sum(len(rutas) for rutas in candidatos.values())
    log_status(f"🔍 Encontrados {len(candidatos)} grupos candidatos ({total_candidatos} archivos)")
    
    return candidatos


def verificar_duplicados_por_hash(grupos_candidatos):
    """
    Calcula MD5 de archivos candidatos y agrupa por hash usando multiprocessing.
    Retorna lista de grupos duplicados: [{hash, tamaño, archivos: [rutas]}]
    Actualiza estado_actual["duplicados"] cada 30 segundos para permitir eliminación progresiva.
    """
    global escaneo_completo
    duplicados = []
    total_grupos = len(grupos_candidatos)
    grupo_actual = 0
    ultimo_update = time_module.time()
    
    # Determinar número de workers (usar múltiplos de cores para I/O bound)
    num_workers = os.cpu_count() * 2 if os.cpu_count() else 8
    log_status(f"⚙️ Usando {num_workers} workers (threads) para cálculo paralelo de hashes")
    log_status(f"📊 Total de grupos a procesar: {total_grupos}")
    
    for tamaño, rutas in grupos_candidatos.items():
        if detener_flag:
            break
        
        grupo_actual += 1
        num_archivos = len(rutas)
        progreso_pct = (grupo_actual / total_grupos) * 100
        
        # Log cada 100 grupos o en grupos grandes
        if grupo_actual % 100 == 0 or num_archivos > 10:
            log_status(f"🔎 Verificando grupo {grupo_actual}/{total_grupos} ({progreso_pct:.1f}%) - {num_archivos} archivos de {tamaño} bytes")
        
        # Agrupar por hash dentro de este grupo de tamaño usando ThreadPoolExecutor
        grupos_hash = defaultdict(list)
        
        try:
            # Calcular hashes en paralelo con threads (mejor para I/O bound como lectura de archivos)
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Enviar todos los trabajos
                futures = {executor.submit(hash_file_wrapper, ruta): ruta for ruta in rutas}
                
                # Procesar resultados a medida que se completan
                from concurrent.futures import as_completed
                for idx, future in enumerate(as_completed(futures)):
                    if detener_flag:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    
                    try:
                        ruta, hash_md5 = future.result()
                        if hash_md5:
                            grupos_hash[hash_md5].append(ruta)
                        else:
                            log_status(f"⚠️ No se pudo calcular hash de: {ruta}")
                    except Exception as e:
                        log_status(f"⚠️ Error procesando {futures[future]}: {e}")
                    
                    # Log progreso cada 50 archivos procesados
                    if (idx + 1) % 50 == 0 and num_archivos > 100:
                        log_status(f"   ⏳ Procesados {idx + 1}/{num_archivos} archivos del grupo {grupo_actual}")
                    
                    # Pequeña pausa cada 100 archivos para permitir que Flask responda
                    if (idx + 1) % 100 == 0:
                        time_module.sleep(0.01)
        
        except Exception as e:
            log_status(f"❌ Error en procesamiento paralelo: {e}")
            # Fallback a procesamiento secuencial
            log_status(f"🔄 Usando método secuencial como respaldo...")
            for ruta in rutas:
                if detener_flag:
                    break
                hash_md5 = hash_file(ruta)
                if hash_md5:
                    grupos_hash[hash_md5].append(ruta)
        
        # Solo reportar grupos con 2+ archivos del mismo hash
        for hash_md5, archivos_duplicados in grupos_hash.items():
            if len(archivos_duplicados) > 1:
                duplicados.append({
                    "hash": hash_md5,
                    "tamaño": tamaño,
                    "archivos": archivos_duplicados,
                    "count": len(archivos_duplicados)
                })
                log_status(f"⚠️ Duplicados encontrados: {len(archivos_duplicados)} archivos con hash {hash_md5[:8]}...")
        
        # Actualizar estado cada 30 segundos para permitir eliminación progresiva
        ahora = time_module.time()
        if ahora - ultimo_update >= 30:
            estado_actual["duplicados"] = duplicados.copy()
            estado_actual["resumen"] = {
                "grupos_duplicados": len(duplicados),
                "archivos_duplicados": sum(g["count"] for g in duplicados)
            }
            log_status(f"📊 Actualización parcial: {len(duplicados)} grupos encontrados hasta ahora")
            ultimo_update = ahora
    
    return duplicados


def eliminar_duplicados_grupo(hash_grupo):
    """
    Elimina duplicados de un grupo específico, dejando solo el primero.
    Retorna bytes liberados y cantidad eliminada.
    """
    # Buscar el grupo en estado_actual["duplicados"]
    grupo = None
    for g in estado_actual["duplicados"]:
        if g["hash"] == hash_grupo:
            grupo = g
            break
    
    if not grupo or len(grupo["archivos"]) < 2:
        return {"ok": False, "error": "Grupo no encontrado o sin duplicados"}
    
    archivos = grupo["archivos"]
    tamaño = grupo["tamaño"]
    
    # Mantener el primero, eliminar el resto
    archivo_conservado = archivos[0]
    archivos_a_eliminar = archivos[1:]
    
    eliminados = 0
    errores = []
    
    for ruta in archivos_a_eliminar:
        try:
            os.remove(ruta)
            eliminados += 1
            log_status(f"🗑️ Eliminado: {ruta}")
        except PermissionError:
            errores.append(f"Sin permisos: {ruta}")
            log_status(f"❌ Sin permisos para eliminar: {ruta}")
        except Exception as e:
            errores.append(f"Error en {ruta}: {e}")
            log_status(f"❌ Error al eliminar {ruta}: {e}")
    
    bytes_liberados = eliminados * tamaño
    mb_liberados = bytes_liberados / (1024 * 1024)
    
    # Actualizar el grupo en estado_actual
    grupo["archivos"] = [archivo_conservado]
    grupo["count"] = 1
    grupo["eliminados"] = eliminados
    grupo["mb_liberados"] = mb_liberados
    
    log_status(f"✅ Grupo deduplicado: {eliminados} archivos eliminados, {mb_liberados:.2f} MB recuperados")
    
    return {
        "ok": True,
        "eliminados": eliminados,
        "mb_liberados": mb_liberados,
        "errores": errores,
        "conservado": archivo_conservado
    }


def buscar_duplicados(carpeta_base, recursivo=True):
    """
    Función principal: busca duplicados en la carpeta especificada.
    Pipeline completo: escaneo → agrupación por tamaño → verificación MD5
    """
    global procesando, detener_flag, escaneo_completo
    procesando = True
    detener_flag = False
    escaneo_completo = False  # Marcar que el escaneo está en progreso
    estado_actual["duplicados"].clear()
    estado_actual["resumen"].clear()
    
    log_status("🚀 Iniciando búsqueda de duplicados...")
    
    # Etapa 1: Agrupar por tamaño
    grupos_tamaño = agrupar_por_tamaño(carpeta_base, recursivo)
    
    if detener_flag:
        log_status("🟥 Proceso detenido por el usuario.")
        procesando = False
        return
    
    # Etapa 2: Filtrar grupos con 2+ archivos
    candidatos = filtrar_grupos_candidatos(grupos_tamaño)
    
    if not candidatos:
        log_status("✅ No se encontraron archivos candidatos a duplicados.")
        estado_actual["resumen"] = {
            "total_archivos": sum(len(rutas) for rutas in grupos_tamaño.values()),
            "grupos_duplicados": 0,
            "archivos_duplicados": 0
        }
        procesando = False
        return
    
    if detener_flag:
        log_status("🟥 Proceso detenido por el usuario.")
        procesando = False
        return
    
    # Etapa 3: Verificar por hash MD5
    duplicados = verificar_duplicados_por_hash(candidatos)
    
    estado_actual["duplicados"] = duplicados
    
    # Resumen final
    total_archivos_duplicados = sum(grupo["count"] for grupo in duplicados)
    estado_actual["resumen"] = {
        "total_archivos": sum(len(rutas) for rutas in grupos_tamaño.values()),
        "grupos_duplicados": len(duplicados),
        "archivos_duplicados": total_archivos_duplicados
    }
    
    if detener_flag:
        log_status("🟥 Proceso detenido por el usuario.")
    else:
        log_status(f"✅ Búsqueda completada: {len(duplicados)} grupos de duplicados encontrados.")
    
    procesando = False
    detener_flag = False
    escaneo_completo = True  # Marcar que el escaneo terminó (habilitar Dedup all!)


# --- Funciones de Miniaturas ---
def procesar_miniaturas_no_recursivo(carpeta_base, eliminar_originales):
    """
    Genera miniaturas solo en la carpeta especificada (sin subcarpetas).
    """
    global procesando, detener_flag
    procesando = True
    detener_flag = False
    estado_actual["resumen"].clear()
    estado_actual["duplicados"].clear()

    log_status("🖼️ Iniciando generación de miniaturas (modo no recursivo)...")

    try:
        imagenes = [f for f in os.listdir(carpeta_base) 
                   if os.path.isfile(os.path.join(carpeta_base, f)) and 
                   f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'))]
        
        if not imagenes:
            log_status("⚠️ No se encontraron imágenes en la carpeta.")
            procesando = False
            return

        carpeta_originales = os.path.join(carpeta_base, "Originales")
        os.makedirs(carpeta_originales, exist_ok=True)
        revisadas = 0
        generadas = 0

        log_status(f"📂 Procesando: {carpeta_base} ({len(imagenes)} archivos)")

        for nombre in imagenes:
            if detener_flag:
                log_status("🟥 Proceso detenido")
                procesando = False
                return

            ruta = os.path.join(carpeta_base, nombre)
            original_destino = os.path.join(carpeta_originales, nombre)
            
            try:
                with Image.open(ruta) as img:
                    w, h = img.size
                    revisadas += 1
                    if max(w, h) <= MAX_SIZE:
                        log_status(f"Omitida: {nombre} ({w}x{h})")
                    else:
                        ratio = MAX_SIZE / max(w, h)
                        new_w, new_h = int(w * ratio), int(h * ratio)
                        img = img.resize((new_w, new_h), Image.LANCZOS)
                        if not os.path.exists(original_destino):
                            os.rename(ruta, original_destino)
                        img.save(ruta, quality=95)
                        generadas += 1
                        log_status(f"Miniatura creada: {nombre} ({w}x{h} → {new_w}x{new_h})")
            except Exception as e:
                log_status(f"Error con {ruta}: {e}")

        if eliminar_originales and os.path.exists(carpeta_originales):
            try:
                for f in os.listdir(carpeta_originales):
                    os.remove(os.path.join(carpeta_originales, f))
                os.rmdir(carpeta_originales)
                log_status(f"Eliminada carpeta Originales")
            except Exception as e:
                log_status(f"Error al eliminar carpeta Originales: {e}")

        log_status(f"✅ Proceso completado — Revisadas: {revisadas}, Miniaturas: {generadas}")
        
    except Exception as e:
        log_status(f"❌ Error: {e}")
    
    procesando = False
    detener_flag = False


def procesar_miniaturas(carpeta_base, eliminar_originales):
    """
    Genera miniaturas de imágenes en la carpeta especificada (recursivo).
    Adapta imágenes grandes a MAX_SIZE y guarda originales.
    """
    global procesando, detener_flag
    procesando = True
    detener_flag = False
    estado_actual["resumen"].clear()
    estado_actual["duplicados"].clear()

    log_status("🖼️ Iniciando generación de miniaturas (modo recursivo)...")

    for root, _, files in os.walk(carpeta_base):
        if detener_flag:
            log_status("🟥 Detención en curso…")
            break

        imagenes = [f for f in files if f.lower().endswith(
            ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'))]
        if not imagenes:
            continue

        carpeta_originales = os.path.join(root, "Originales")
        os.makedirs(carpeta_originales, exist_ok=True)
        revisadas = 0
        generadas = 0

        log_status(f"📂 Revisando carpeta: {root} ({len(imagenes)} archivos)")
        estado_actual["resumen"][root] = {"revisadas": 0, "miniaturas": 0}

        for nombre in imagenes:
            if detener_flag:
                log_status(f"🟥 Detenido en carpeta {root}")
                procesando = False
                return

            ruta = os.path.join(root, nombre)
            original_destino = os.path.join(carpeta_originales, nombre)
            try:
                with Image.open(ruta) as img:
                    w, h = img.size
                    revisadas += 1
                    if max(w, h) <= MAX_SIZE:
                        log_status(f"Omitida: {nombre} ({w}x{h})")
                    else:
                        ratio = MAX_SIZE / max(w, h)
                        new_w, new_h = int(w * ratio), int(h * ratio)
                        img = img.resize((new_w, new_h), Image.LANCZOS)
                        if not os.path.exists(original_destino):
                            os.rename(ruta, original_destino)
                        img.save(ruta, quality=95)
                        generadas += 1
                        log_status(f"Miniatura creada: {nombre} ({w}x{h} → {new_w}x{new_h})")

                estado_actual["resumen"][root] = {
                    "revisadas": revisadas,
                    "miniaturas": generadas
                }

            except Exception as e:
                log_status(f"Error con {ruta}: {e}")

        if eliminar_originales and os.path.exists(carpeta_originales):
            try:
                for f in os.listdir(carpeta_originales):
                    os.remove(os.path.join(carpeta_originales, f))
                os.rmdir(carpeta_originales)
                log_status(f"Eliminada carpeta Originales en {root}")
            except Exception as e:
                log_status(f"Error al eliminar carpeta Originales en {root}: {e}")

        log_status(f"✅ Carpeta procesada: {root} — Revisadas: {revisadas}, Miniaturas: {generadas}")

    if detener_flag:
        log_status("🟥 Proceso detenido por el usuario.")
    else:
        log_status("✅ Proceso de miniaturas completado correctamente.")

    procesando = False
    detener_flag = False


# --- Funciones Nuevas ---
def generar_preview_html(carpeta_base, recursivo=False):
    """
    Genera un HTML con vista previa de 1 de cada 5 imágenes en la carpeta.
    Puede ser recursivo o no según el parámetro.
    Genera el HTML en la carpeta base con el nombre 'preview.html'.
    """
    global procesando, detener_flag
    procesando = True
    detener_flag = False
    
    modo = "recursivo" if recursivo else "no recursivo"
    log_status(f"🖼️ Iniciando generación de preview HTML (modo {modo})...")
    log_status(f"📂 Carpeta objetivo: {carpeta_base}")
    
    try:
        # Recolectar todas las imágenes (recursivo o no)
        imagenes_por_carpeta = {}  # {carpeta: [archivos]}
        total_archivos = 0
        
        if recursivo:
            log_status("🔄 Modo recursivo: escaneando subcarpetas...")
            for root, dirs, files in os.walk(carpeta_base):
                if detener_flag:
                    break
                
                imagenes = [f for f in files if f.lower().endswith(
                    ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff'))]
                
                if imagenes:
                    imagenes.sort()
                    imagenes_por_carpeta[root] = imagenes
                    total_archivos += len(imagenes)
                    log_status(f"📁 {root}: {len(imagenes)} imágenes")
        else:
            log_status("📂 Modo no recursivo: solo carpeta raíz...")
            archivos = [f for f in os.listdir(carpeta_base) 
                       if os.path.isfile(os.path.join(carpeta_base, f)) and 
                       f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff'))]
            
            if archivos:
                archivos.sort()
                imagenes_por_carpeta[carpeta_base] = archivos
                total_archivos = len(archivos)
        
        if not imagenes_por_carpeta:
            log_status("⚠️ No se encontraron imágenes.")
            procesando = False
            return
        
        log_status(f"� Total de imágenes encontradas: {total_archivos}")
        
        # Generar HTML con secciones por carpeta
        html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Preview - """ + os.path.basename(carpeta_base) + """</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            background: #1a1a1a; 
            color: #eee; 
            margin: 2em; 
        }
        h1 { 
            color: #17a2b8; 
            border-bottom: 2px solid #17a2b8; 
            padding-bottom: 0.5em; 
        }
        h2 {
            color: #6f42c1;
            margin-top: 2em;
            padding: 0.5em;
            background: #2a2a2a;
            border-left: 4px solid #6f42c1;
        }
        .stats { 
            background: #2a2a2a; 
            padding: 1em; 
            border-radius: 0.5em; 
            margin-bottom: 2em; 
        }
        .gallery { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 1.5em; 
            margin-top: 1em;
            margin-bottom: 2em;
        }
        .item { 
            background: #2a2a2a; 
            padding: 1em; 
            border-radius: 0.5em; 
            text-align: center; 
        }
        .item img { 
            max-width: 100%; 
            height: auto; 
            border-radius: 0.3em; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.3); 
        }
        .item .filename { 
            margin-top: 0.5em; 
            font-size: 0.85em; 
            color: #17a2b8; 
            word-break: break-all; 
        }
        .item .info { 
            margin-top: 0.3em; 
            font-size: 0.75em; 
            color: #888; 
        }
        .item .path {
            margin-top: 0.2em;
            font-size: 0.7em;
            color: #666;
        }
    </style>
</head>
<body>
    <h1>🖼️ Preview: """ + os.path.basename(carpeta_base) + """</h1>
    <div class="stats">
        <strong>📂 Carpeta base:</strong> """ + carpeta_base + """<br>
        <strong>🔄 Modo:</strong> """ + modo + """<br>
        <strong>📊 Total de imágenes:</strong> """ + str(total_archivos) + """<br>
        <strong>� Carpetas procesadas:</strong> """ + str(len(imagenes_por_carpeta)) + """
    </div>
"""
        
        # Procesar cada carpeta
        total_muestreadas = 0
        for carpeta, archivos in sorted(imagenes_por_carpeta.items()):
            if detener_flag:
                log_status("🟥 Proceso detenido por el usuario.")
                procesando = False
                return
            
            # Seleccionar 1 de cada 5 imágenes
            imagenes_seleccionadas = [archivos[i] for i in range(0, len(archivos), 5)]
            total_muestreadas += len(imagenes_seleccionadas)
            
            # Título de la sección (solo si es recursivo)
            if recursivo:
                carpeta_relativa = os.path.relpath(carpeta, carpeta_base)
                if carpeta_relativa == ".":
                    carpeta_relativa = "(raíz)"
                html_content += f"""
    <h2>📁 {carpeta_relativa}</h2>
    <div style="color: #888; font-size: 0.9em; margin-bottom: 0.5em;">
        {len(archivos)} imágenes | Muestreadas: {len(imagenes_seleccionadas)} (1 de cada 5)
    </div>
    <div class="gallery">
"""
            else:
                html_content += f"""
    <div style="color: #888; font-size: 0.9em; margin-bottom: 0.5em;">
        🔍 Muestreadas: {len(imagenes_seleccionadas)} de {len(archivos)} (1 de cada 5)
    </div>
    <div class="gallery">
"""
            
            # Agregar imágenes de esta carpeta
            for nombre in imagenes_seleccionadas:
                ruta_completa = os.path.join(carpeta, nombre)
                try:
                    # Obtener dimensiones de la imagen
                    with Image.open(ruta_completa) as img:
                        w, h = img.size
                        tamaño_kb = os.path.getsize(ruta_completa) / 1024
                        
                        # Calcular ruta relativa para la imagen
                        if recursivo:
                            ruta_relativa = os.path.relpath(ruta_completa, carpeta_base)
                        else:
                            ruta_relativa = nombre
                        
                        html_content += f"""
        <div class="item">
            <img src="{ruta_relativa}" alt="{nombre}">
            <div class="filename">📄 {nombre}</div>
            <div class="info">{w} x {h} px | {tamaño_kb:.1f} KB</div>
        </div>
"""
                        log_status(f"✅ Procesada: {nombre} ({w}x{h})")
                except Exception as e:
                    log_status(f"⚠️ Error al procesar {nombre}: {e}")
            
            html_content += """
    </div>
"""
        
        html_content += f"""
    <div style="margin-top: 2em; padding-top: 1em; border-top: 1px solid #444; text-align: center; color: #888; font-size: 0.9em;">
        📸 Preview generado por Dedupper | Total muestreadas: {total_muestreadas} de {total_archivos}
    </div>
</body>
</html>
"""
        
        # Guardar HTML en la carpeta base
        ruta_html = os.path.join(carpeta_base, "preview.html")
        with open(ruta_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        log_status(f"✅ Preview HTML generado exitosamente: {ruta_html}")
        log_status(f"📋 Total muestreadas: {total_muestreadas} de {total_archivos} imágenes")
        log_status(f"💡 Abre el archivo en tu navegador para ver las miniaturas.")
        
    except Exception as e:
        log_status(f"❌ Error al generar preview: {e}")
    
    procesando = False
    detener_flag = False


def analizar_imagenes(carpeta_base):
    """
    Analiza imágenes de manera recursiva y genera estadísticas detalladas.
    Agrupa por tamaño de archivo, resolución, y detecta imágenes < 1280px.
    Retorna información por carpeta para identificar cuáles recuperar.
    """
    global procesando, detener_flag
    procesando = True
    detener_flag = False
    
    log_status("📊 Iniciando análisis de imágenes...")
    log_status(f"📂 Carpeta base: {carpeta_base}")
    
    # Estructuras de datos para estadísticas
    stats_por_carpeta = {}
    stats_tamaño = defaultdict(list)  # {tamaño_kb: [rutas]}
    stats_resolucion = defaultdict(list)  # {resolución: [rutas]}
    imagenes_pequenas = []  # Imágenes con max(w,h) < 1280
    total_imagenes = 0
    
    try:
        # Escanear recursivamente
        for root, dirs, files in os.walk(carpeta_base):
            if detener_flag:
                log_status("🟥 Análisis detenido por el usuario.")
                procesando = False
                return
            
            # Filtrar solo imágenes
            imagenes = [f for f in files if f.lower().endswith(
                ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff'))]
            
            if not imagenes:
                continue
            
            log_status(f"📁 Analizando: {root} ({len(imagenes)} imágenes)")
            
            # Inicializar stats para esta carpeta
            carpeta_stats = {
                "total": len(imagenes),
                "pequenas": 0,
                "resoluciones": defaultdict(int),
                "tamanos": defaultdict(int)
            }
            
            for nombre in imagenes:
                if detener_flag:
                    break
                
                ruta = os.path.join(root, nombre)
                try:
                    # Obtener tamaño de archivo
                    tamaño_bytes = os.path.getsize(ruta)
                    tamaño_kb = tamaño_bytes / 1024
                    tamaño_mb = tamaño_kb / 1024
                    
                    # Categorizar tamaño (rangos en MB)
                    if tamaño_mb < 0.1:
                        categoria_tamaño = "< 100 KB"
                    elif tamaño_mb < 0.5:
                        categoria_tamaño = "100-500 KB"
                    elif tamaño_mb < 1:
                        categoria_tamaño = "0.5-1 MB"
                    elif tamaño_mb < 5:
                        categoria_tamaño = "1-5 MB"
                    elif tamaño_mb < 10:
                        categoria_tamaño = "5-10 MB"
                    else:
                        categoria_tamaño = "> 10 MB"
                    
                    stats_tamaño[categoria_tamaño].append(ruta)
                    carpeta_stats["tamanos"][categoria_tamaño] += 1
                    
                    # Obtener resolución
                    with Image.open(ruta) as img:
                        w, h = img.size
                        resolucion = f"{w}x{h}"
                        max_dimension = max(w, h)
                        
                        stats_resolucion[resolucion].append(ruta)
                        carpeta_stats["resoluciones"][resolucion] += 1
                        
                        # Verificar si es pequeña (< 1280px en dimensión mayor)
                        if max_dimension < 1280:
                            imagenes_pequenas.append({
                                "ruta": ruta,
                                "carpeta": root,
                                "nombre": nombre,
                                "resolucion": resolucion,
                                "tamaño_kb": tamaño_kb
                            })
                            carpeta_stats["pequenas"] += 1
                    
                    total_imagenes += 1
                    
                except Exception as e:
                    log_status(f"⚠️ Error al analizar {ruta}: {e}")
            
            # Guardar stats de esta carpeta
            stats_por_carpeta[root] = carpeta_stats
        
        # Calcular porcentaje de imágenes pequeñas
        porcentaje_pequenas = (len(imagenes_pequenas) / total_imagenes * 100) if total_imagenes > 0 else 0
        
        # Generar reporte en el log
        log_status("\n" + "="*80)
        log_status("📊 REPORTE DE ANÁLISIS DE IMÁGENES")
        log_status("="*80)
        log_status(f"\n📈 ESTADÍSTICAS GENERALES:")
        log_status(f"   Total de imágenes analizadas: {total_imagenes}")
        log_status(f"   Imágenes < 1280px (dimensión mayor): {len(imagenes_pequenas)} ({porcentaje_pequenas:.1f}%)")
        
        log_status(f"\n📦 DISTRIBUCIÓN POR TAMAÑO DE ARCHIVO:")
        for categoria in sorted(stats_tamaño.keys()):
            cantidad = len(stats_tamaño[categoria])
            porcentaje = (cantidad / total_imagenes * 100) if total_imagenes > 0 else 0
            log_status(f"   {categoria:15} : {cantidad:5} imágenes ({porcentaje:5.1f}%)")
        
        log_status(f"\n📐 TOP 10 RESOLUCIONES MÁS COMUNES:")
        resoluciones_ordenadas = sorted(stats_resolucion.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        for resolucion, rutas in resoluciones_ordenadas:
            cantidad = len(rutas)
            porcentaje = (cantidad / total_imagenes * 100) if total_imagenes > 0 else 0
            log_status(f"   {resolucion:20} : {cantidad:5} imágenes ({porcentaje:5.1f}%)")
        
        log_status(f"\n📁 ANÁLISIS POR CARPETA:")
        for carpeta in sorted(stats_por_carpeta.keys()):
            stats = stats_por_carpeta[carpeta]
            if stats["pequenas"] > 0:
                porcentaje_pequenas_carpeta = (stats["pequenas"] / stats["total"] * 100)
                log_status(f"\n   📂 {carpeta}")
                log_status(f"      Total: {stats['total']} | Pequeñas (<1280px): {stats['pequenas']} ({porcentaje_pequenas_carpeta:.1f}%)")
                
                # Mostrar distribución de tamaños en esta carpeta
                if stats["tamanos"]:
                    log_status(f"      Tamaños: {dict(stats['tamanos'])}")
                
                # Mostrar top 3 resoluciones en esta carpeta
                top_res = sorted(stats["resoluciones"].items(), key=lambda x: x[1], reverse=True)[:3]
                if top_res:
                    res_str = ", ".join([f"{res}({cnt})" for res, cnt in top_res])
                    log_status(f"      Top resoluciones: {res_str}")
        
        if imagenes_pequenas:
            log_status(f"\n⚠️ CARPETAS CON IMÁGENES PEQUEÑAS (POSIBLE DAÑO):")
            carpetas_afectadas = set([img["carpeta"] for img in imagenes_pequenas])
            for carpeta in sorted(carpetas_afectadas):
                imgs_carpeta = [img for img in imagenes_pequenas if img["carpeta"] == carpeta]
                log_status(f"   📁 {carpeta} → {len(imgs_carpeta)} imagen(es) afectada(s)")
        
        log_status("\n" + "="*80)
        log_status("✅ Análisis completado exitosamente.")
        log_status("="*80 + "\n")
        
        # Actualizar resumen en estado_actual para la UI
        estado_actual["resumen"] = {
            "total_imagenes": total_imagenes,
            "imagenes_pequenas": len(imagenes_pequenas),
            "porcentaje_pequenas": f"{porcentaje_pequenas:.1f}%",
            "carpetas_analizadas": len(stats_por_carpeta),
            "carpetas_afectadas": len(set([img["carpeta"] for img in imagenes_pequenas]))
        }
        
        # ============ GENERAR HTML CON EL REPORTE ============
        log_status("📄 Generando reporte HTML...")
        try:
            # Calcular estadísticas por carpeta para el HTML
            carpetas_con_datos = []
            for carpeta in sorted(stats_por_carpeta.keys()):
                stats = stats_por_carpeta[carpeta]
                if stats["total"] > 0:
                    # Calcular estadísticas de tamaño y resolución
                    imgs_carpeta = [img for img in imagenes_pequenas if img["carpeta"] == carpeta]
                    
                    # Stats de tamaño (en KB)
                    tamanos_kb = [img["tamaño_kb"] for img in imgs_carpeta] if imgs_carpeta else []
                    if tamanos_kb:
                        max_tamaño = max(tamanos_kb)
                        min_tamaño = min(tamanos_kb)
                        # Moda de tamaño (categoría más común)
                        moda_tamaño = max(stats["tamanos"].items(), key=lambda x: x[1])[0] if stats["tamanos"] else "N/A"
                    else:
                        max_tamaño = min_tamaño = moda_tamaño = "N/A"
                    
                    # Stats de resolución
                    if stats["resoluciones"]:
                        # Resolución más común (moda)
                        moda_resolucion = max(stats["resoluciones"].items(), key=lambda x: x[1])[0]
                        # Min y max resolución (por área de píxeles)
                        resoluciones_list = [(res, cnt) for res, cnt in stats["resoluciones"].items()]
                        resoluciones_con_area = []
                        for res, cnt in resoluciones_list:
                            try:
                                w, h = map(int, res.split('x'))
                                area = w * h
                                resoluciones_con_area.append((res, area, cnt))
                            except:
                                pass
                        
                        if resoluciones_con_area:
                            resoluciones_con_area.sort(key=lambda x: x[1])
                            min_resolucion = resoluciones_con_area[0][0]
                            max_resolucion = resoluciones_con_area[-1][0]
                        else:
                            min_resolucion = max_resolucion = "N/A"
                    else:
                        moda_resolucion = min_resolucion = max_resolucion = "N/A"
                    
                    carpetas_con_datos.append({
                        "nombre": carpeta,
                        "total": stats["total"],
                        "afectadas": stats["pequenas"],
                        "porcentaje_afectadas": (stats["pequenas"] / stats["total"] * 100) if stats["total"] > 0 else 0,
                        "max_tamaño": f"{max_tamaño:.1f} KB" if isinstance(max_tamaño, (int, float)) else max_tamaño,
                        "min_tamaño": f"{min_tamaño:.1f} KB" if isinstance(min_tamaño, (int, float)) else min_tamaño,
                        "moda_tamaño": moda_tamaño,
                        "max_resolucion": max_resolucion,
                        "min_resolucion": min_resolucion,
                        "moda_resolucion": moda_resolucion
                    })
            
            # Generar HTML
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Análisis de Imágenes - {os.path.basename(carpeta_base)}</title>
    <style>
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: #1a1a1a; 
            color: #eee; 
            margin: 2em; 
            line-height: 1.6;
        }}
        h1 {{ 
            color: #fd7e14; 
            border-bottom: 3px solid #fd7e14; 
            padding-bottom: 0.5em; 
        }}
        h2 {{
            color: #17a2b8;
            margin-top: 2em;
            border-left: 4px solid #17a2b8;
            padding-left: 0.5em;
        }}
        .summary {{ 
            background: linear-gradient(135deg, #2a2a2a 0%, #1a1a1a 100%); 
            padding: 1.5em; 
            border-radius: 0.5em; 
            margin-bottom: 2em;
            border: 1px solid #444;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1em;
            margin-top: 1em;
        }}
        .summary-item {{
            background: #333;
            padding: 1em;
            border-radius: 0.3em;
            text-align: center;
        }}
        .summary-item .value {{
            font-size: 2em;
            font-weight: bold;
            color: #fd7e14;
        }}
        .summary-item .label {{
            font-size: 0.9em;
            color: #aaa;
            margin-top: 0.3em;
        }}
        table {{ 
            width: 100%; 
            border-collapse: collapse; 
            margin-top: 1em;
            background: #2a2a2a;
        }}
        th {{ 
            background: #fd7e14; 
            color: #000; 
            padding: 0.8em; 
            text-align: left; 
            font-weight: bold;
        }}
        td {{ 
            padding: 0.8em; 
            border-bottom: 1px solid #444; 
        }}
        tr:hover {{ 
            background: #333; 
        }}
        .afectada {{
            background: #dc3545;
            color: #fff;
            padding: 0.2em 0.5em;
            border-radius: 0.3em;
            font-weight: bold;
            display: inline-block;
        }}
        .ok {{
            background: #28a745;
            color: #fff;
            padding: 0.2em 0.5em;
            border-radius: 0.3em;
            font-weight: bold;
            display: inline-block;
        }}
        .warning {{
            background: #ffc107;
            color: #000;
            padding: 0.2em 0.5em;
            border-radius: 0.3em;
            font-weight: bold;
            display: inline-block;
        }}
        .stats-mini {{
            font-size: 0.85em;
            color: #17a2b8;
        }}
        .footer {{
            margin-top: 3em;
            padding-top: 1em;
            border-top: 1px solid #444;
            text-align: center;
            color: #888;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <h1>📊 Análisis de Imágenes</h1>
    
    <div class="summary">
        <h2 style="margin-top: 0; border: none;">📈 Resumen General</h2>
        <strong>📂 Carpeta Base:</strong> {carpeta_base}<br>
        <div class="summary-grid">
            <div class="summary-item">
                <div class="value">{total_imagenes}</div>
                <div class="label">Total Imágenes</div>
            </div>
            <div class="summary-item">
                <div class="value">{len(imagenes_pequenas)}</div>
                <div class="label">Imágenes Afectadas</div>
            </div>
            <div class="summary-item">
                <div class="value">{porcentaje_pequenas:.1f}%</div>
                <div class="label">% Afectadas</div>
            </div>
            <div class="summary-item">
                <div class="value">{len(stats_por_carpeta)}</div>
                <div class="label">Carpetas Analizadas</div>
            </div>
        </div>
    </div>
    
    <h2>📁 Análisis por Carpeta</h2>
    <table>
        <thead>
            <tr>
                <th>Carpeta</th>
                <th>Total</th>
                <th>Afectadas</th>
                <th>Tamaño (KB)</th>
                <th>Resolución</th>
            </tr>
        </thead>
        <tbody>
"""
            
            # Agregar filas de carpetas
            for carpeta_data in carpetas_con_datos:
                # Badge de estado
                if carpeta_data["afectadas"] == 0:
                    badge = '<span class="ok">✓ OK</span>'
                elif carpeta_data["porcentaje_afectadas"] > 50:
                    badge = f'<span class="afectada">⚠ {carpeta_data["afectadas"]} ({carpeta_data["porcentaje_afectadas"]:.1f}%)</span>'
                else:
                    badge = f'<span class="warning">⚠ {carpeta_data["afectadas"]} ({carpeta_data["porcentaje_afectadas"]:.1f}%)</span>'
                
                html_content += f"""
            <tr>
                <td><strong>{carpeta_data["nombre"]}</strong></td>
                <td>{carpeta_data["total"]}</td>
                <td>{badge}</td>
                <td>
                    <span class="stats-mini">Max:</span> {carpeta_data["max_tamaño"]}<br>
                    <span class="stats-mini">Min:</span> {carpeta_data["min_tamaño"]}<br>
                    <span class="stats-mini">Moda:</span> {carpeta_data["moda_tamaño"]}
                </td>
                <td>
                    <span class="stats-mini">Max:</span> {carpeta_data["max_resolucion"]}<br>
                    <span class="stats-mini">Min:</span> {carpeta_data["min_resolucion"]}<br>
                    <span class="stats-mini">Moda:</span> {carpeta_data["moda_resolucion"]}
                </td>
            </tr>
"""
            
            html_content += """
        </tbody>
    </table>
    
    <div class="footer">
        📊 Reporte generado por Dedupper - Analizador de Imágenes<br>
        Imágenes afectadas: Dimensión mayor < 1280px
    </div>
</body>
</html>
"""
            
            # Guardar HTML
            ruta_html = os.path.join(carpeta_base, "analisis_imagenes.html")
            with open(ruta_html, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            log_status(f"✅ Reporte HTML generado: {ruta_html}")
            
        except Exception as e:
            log_status(f"❌ Error al generar HTML: {e}")
        
    except Exception as e:
        log_status(f"❌ Error durante el análisis: {e}")
    
    procesando = False
    detener_flag = False


# --- HTML de la interfaz web ---
HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>Dedupper v""" + VERSION + """</title>
<style>
body { font-family: sans-serif; background: #111; color: #eee; margin: 2em; }
input[type=text] { width: 80%; padding: .4em; background: #222; color: #eee; border: 1px solid #555; border-radius: .4em; }
.btn-group { margin: 1em 0; }
button { padding: .5em 1em; margin: .5em; background: #28a745; color: #fff; border: none; border-radius: .4em; cursor: pointer; font-size: 1em; }
button:hover { background: #218838; }
button.miniaturas { background: #007bff; }
button.miniaturas:hover { background: #0056b3; }
button.preview { background: #6f42c1; }
button.preview:hover { background: #5a32a3; }
button.analizador { background: #fd7e14; }
button.analizador:hover { background: #e8590c; }
button.detener { background: #dc3545; }
button.detener:hover { background: #c82333; }
label { margin-left: 1em; }
pre { background: #000; color: #0f0; padding: 1em; height: 300px; overflow-y: scroll; border-radius: .4em; font-size: .9em; }
.resumen { background: #222; padding: 1em; margin: 1em 0; border-radius: .4em; }
.duplicados { background: #1a1a1a; padding: 1em; margin: 1em 0; border-radius: .4em; max-height: 400px; overflow-y: auto; }
.grupo-duplicado { background: #2a2a2a; padding: .8em; margin: .5em 0; border-left: 4px solid #ffc107; border-radius: .3em; position: relative; }
.grupo-duplicado.deduped { border-left-color: #28a745; opacity: 0.7; }
.grupo-duplicado .hash { color: #ffc107; font-family: monospace; font-size: .9em; }
.grupo-duplicado .archivo { color: #17a2b8; margin: .3em 0; padding-left: 1em; }
.grupo-duplicado .archivo a { color: #17a2b8; text-decoration: none; }
.grupo-duplicado .archivo a:hover { color: #20c997; text-decoration: underline; }
.grupo-duplicado .tamaño { color: #888; font-size: .85em; }
.grupo-duplicado .btn-dedup { background: #ffc107; color: #000; padding: .3em .8em; border: none; border-radius: .3em; cursor: pointer; font-weight: bold; margin-top: .5em; display: inline-block; text-align: center; }
.grupo-duplicado .btn-dedup:hover { background: #ffcd39; }
.grupo-duplicado .btn-dedup:disabled { background: #666; color: #999; cursor: not-allowed; }
.grupo-duplicado .btn-dedup .btn-text { display: block; font-size: 1em; }
.grupo-duplicado .btn-dedup .btn-subtext { display: block; font-size: 0.7em; font-weight: normal; opacity: 0.8; }
.mensaje-exito { background: #28a745; color: #fff; padding: .5em; margin: .5em 0; border-radius: .3em; font-weight: bold; }
.archivo-checkbox { margin-right: .5em; cursor: pointer; }
</style>
<script>
async function buscarDuplicados(){
  const carpeta = document.getElementById('carpeta').value;
  const recursivo = document.getElementById('recursivo').checked;
  document.getElementById('log').textContent = 'Buscando duplicados...';
  await fetch('/buscar_duplicados?v=""" + VERSION + """', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({carpeta: carpeta, recursivo: recursivo})
  });
  actualizar();
}

async function generarMiniaturas(){
  const carpeta = document.getElementById('carpeta').value;
  const eliminar = document.getElementById('eliminar').checked;
  const recursivo = document.getElementById('recursivo').checked;
  document.getElementById('log').textContent = 'Generando miniaturas...';
  await fetch('/generar_miniaturas?v=""" + VERSION + """', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({carpeta: carpeta, eliminar: eliminar, recursivo: recursivo})
  });
  actualizar();
}

async function generarPreview(){
  const carpeta = document.getElementById('carpeta').value;
  const recursivo = document.getElementById('recursivo').checked;
  document.getElementById('log').textContent = 'Generando preview HTML...';
  await fetch('/generar_preview?v=""" + VERSION + """', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({carpeta: carpeta, recursivo: recursivo})
  });
  actualizar();
}

async function analizarImagenes(){
  const carpeta = document.getElementById('carpeta').value;
  document.getElementById('log').textContent = 'Analizando imágenes...';
  await fetch('/analizar_imagenes?v=""" + VERSION + """', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({carpeta: carpeta})
  });
  actualizar();
}

async function dedupTodos(){
  const grupos = document.querySelectorAll('.grupo-duplicado:not(.deduped)');
  if (grupos.length === 0) {
    return;
  }
  
  let totalEliminados = 0;
  let totalMB = 0;
  
  // Obtener todos los hashes de grupos pendientes
  const data = await (await fetch('/estado?v=""" + VERSION + """')).json();
  const gruposPendientes = data.duplicados.filter(g => g.count > 1);
  
  // Procesar cada grupo
  for (const grupo of gruposPendientes) {
    // Verificar si hay checkboxes marcados en este grupo
    const checkboxesMarcados = document.querySelectorAll(`.archivo-checkbox[data-hash="${grupo.hash}"]:checked`);
    
    if (checkboxesMarcados.length > 0) {
      // Si hay checkboxes marcados, eliminar solo esos archivos
      const rutasSeleccionadas = Array.from(checkboxesMarcados).map(cb => 
        cb.dataset.ruta.replace(/\\\\\\\\/g, '\\\\').replace(/\\\\'/g, "'")
      );
      
      const res = await fetch('/eliminar_seleccionados?v=""" + VERSION + """', {
        method:'POST', 
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({rutas: rutasSeleccionadas, hash: grupo.hash})
      });
      const result = await res.json();
      
      if (result.ok) {
        totalEliminados += result.eliminados;
      }
    } else {
      // Si no hay checkboxes marcados, usar lógica automática (dejar primero, eliminar resto)
      const res = await fetch('/eliminar_grupo?v=""" + VERSION + """', {
        method:'POST', 
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({hash: grupo.hash})
      });
      const result = await res.json();
      
      if (result.ok) {
        totalEliminados += result.eliminados;
        totalMB += result.mb_liberados;
      }
    }
  }
  
  // Actualizar interfaz
  actualizar();
}

async function limpiar(){
  await fetch('/limpiar?v=""" + VERSION + """', {method:'POST'});
  document.getElementById('log').textContent = '';
  document.getElementById('resumen').innerHTML = 'Sin datos aún...';
  document.getElementById('duplicados').innerHTML = '<div style="color: #888;">No se han detectado duplicados aún...</div>';
  document.getElementById('status').textContent = 'Esperando...';
}

async function limpiarDedupeados(){
  // Llamar endpoint para filtrar grupos ya dedupeados
  const res = await fetch('/limpiar_dedupeados?v=""" + VERSION + """', {method:'POST'});
  const data = await res.json();
  
  if (data.ok) {
    actualizar();
  }
}

async function dedupGrupoSeleccionados(hash){
  // Obtener checkboxes seleccionados de este grupo
  const checkboxes = document.querySelectorAll(`.archivo-checkbox[data-hash="${hash}"]:checked`);
  
  if (checkboxes.length === 0) {
    return; // No hay nada seleccionado
  }
  
  // Extraer rutas de archivos seleccionados
  const rutasSeleccionadas = Array.from(checkboxes).map(cb => cb.dataset.ruta.replace(/\\\\\\\\/g, '\\\\').replace(/\\\\'/g, "'"));
  
  // Enviar petición para eliminar solo los seleccionados
  const res = await fetch('/eliminar_seleccionados?v=""" + VERSION + """', {
    method:'POST', 
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({rutas: rutasSeleccionadas, hash: hash})
  });
  const data = await res.json();
  
  if (data.ok) {
    actualizar();
  } else {
    console.error('Error al deduplicar seleccionados:', data.error);
  }
}

async function abrirArchivo(event, ruta){
  event.preventDefault();
  event.stopPropagation();
  
  // Enviar petición para abrir el archivo en el explorador
  const res = await fetch('/abrir_archivo?v=""" + VERSION + """', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ruta: ruta})
  });
  
  const data = await res.json();
  if (!data.ok) {
    alert('Error al abrir archivo: ' + data.error);
  }
  
  return false;
}

async function detener(){
  await fetch('/detener?v=""" + VERSION + """', {method:'POST'});
}

async function actualizar(){
  const res = await fetch('/estado?v=""" + VERSION + """');
  const data = await res.json();
  document.getElementById('status').textContent = data.mensaje;
  document.getElementById('log').textContent = data.detalles.join('\\n');
  
  // Habilitar/deshabilitar botón "Dedup all!" según estado del escaneo
  const btnDedupAll = document.getElementById('btnDedupAll');
  const statusEscaneo = document.getElementById('statusEscaneo');
  if (btnDedupAll) {
    const hayDuplicados = data.duplicados && data.duplicados.length > 0;
    
    if (data.escaneo_completo && hayDuplicados) {
      // Escaneo terminado Y hay duplicados → HABILITAR
      btnDedupAll.disabled = false;
      btnDedupAll.style.background = '#ffc107';
      btnDedupAll.style.color = '#000';
      btnDedupAll.style.cursor = 'pointer';
      btnDedupAll.title = 'Eliminar todos los duplicados (respeta checkboxes marcados)';
      if (statusEscaneo) statusEscaneo.textContent = '✅ (escaneo completo)';
    } else if (!data.escaneo_completo) {
      // Escaneo en progreso → DESHABILITAR
      btnDedupAll.disabled = true;
      btnDedupAll.style.background = '#666';
      btnDedupAll.style.color = '#999';
      btnDedupAll.style.cursor = 'not-allowed';
      btnDedupAll.title = 'Disponible cuando termine el escaneo. Usa "Dedup it!" por grupos mientras tanto.';
      if (statusEscaneo) statusEscaneo.textContent = '⏳ (escaneo en progreso...)';
    } else {
      // Escaneo terminado pero sin duplicados → DESHABILITAR
      btnDedupAll.disabled = true;
      btnDedupAll.style.background = '#666';
      btnDedupAll.style.color = '#999';
      btnDedupAll.style.cursor = 'not-allowed';
      btnDedupAll.title = 'No hay duplicados para eliminar';
      if (statusEscaneo) statusEscaneo.textContent = '(sin duplicados)';
    }
  }
  
  // Mostrar resumen
  let resumenHTML = '';
  if (data.resumen && Object.keys(data.resumen).length > 0) {
    resumenHTML = `
      <div><strong>Total de archivos escaneados:</strong> ${data.resumen.total_archivos || 0}</div>
      <div><strong>Grupos de duplicados:</strong> ${data.resumen.grupos_duplicados || 0}</div>
      <div><strong>Archivos duplicados:</strong> ${data.resumen.archivos_duplicados || 0}</div>
    `;
  } else {
    resumenHTML = 'Sin datos aún...';
  }
  document.getElementById('resumen').innerHTML = resumenHTML;
  
  // GUARDAR estado de checkboxes ANTES de actualizar HTML
  const checkboxesAnteriores = {};
  document.querySelectorAll('.archivo-checkbox').forEach(cb => {
    const key = cb.dataset.hash + '::' + cb.dataset.ruta;
    checkboxesAnteriores[key] = cb.checked;
  });
  
  // Verificar si hay cambios en los datos antes de actualizar
  const duplicadosStr = JSON.stringify(data.duplicados || []);
  if (window._lastDuplicadosStr === duplicadosStr) {
    // No hay cambios, solo restaurar checkboxes (por si acaso)
    document.querySelectorAll('.archivo-checkbox').forEach(cb => {
      const key = cb.dataset.hash + '::' + cb.dataset.ruta;
      if (checkboxesAnteriores[key] && !cb.checked) {
        cb.checked = true;
      }
    });
  } else {
    // HAY cambios, actualizar TODO el HTML
    window._lastDuplicadosStr = duplicadosStr;
    
    // Mostrar duplicados
    let duplicadosHTML = '';
    if (data.duplicados && data.duplicados.length > 0) {
      for (const grupo of data.duplicados) {
        const esDeduplicado = grupo.count === 1;
        const claseExtra = esDeduplicado ? 'deduped' : '';
        
        duplicadosHTML += `
          <div class="grupo-duplicado ${claseExtra}">
            <div class="hash">Hash: ${grupo.hash}</div>
            <div class="tamaño">Tamaño: ${grupo.tamaño} bytes | Archivos: ${grupo.count}</div>
        `;
        
        for (const archivo of grupo.archivos) {
          const archivoEscapado = archivo.replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
          duplicadosHTML += `
            <div class="archivo">
              <input type="checkbox" class="archivo-checkbox" data-hash="${grupo.hash}" data-ruta="${archivoEscapado}">
              📄 <a href="javascript:void(0)" onclick="abrirArchivo(event, '${archivoEscapado}')">${archivo}</a>
            </div>`;
        }
        
        if (esDeduplicado && grupo.eliminados) {
          duplicadosHTML += `<div class="mensaje-exito">✅ Duplicados eliminados. ${grupo.mb_liberados.toFixed(2)} MB recuperados!</div>`;
        } else if (!esDeduplicado) {
          duplicadosHTML += `
            <button class="btn-dedup" onclick="dedupGrupoSeleccionados('${grupo.hash}')">
              <span class="btn-text">🗑️ Dedup it!</span>
              <span class="btn-subtext">seleccionados</span>
            </button>`;
        }
        
        duplicadosHTML += `</div>`;
      }
    } else {
      duplicadosHTML = '<div style="color: #888;">No se han detectado duplicados aún...</div>';
    }
    document.getElementById('duplicados').innerHTML = duplicadosHTML;
    
    // RESTAURAR estado de checkboxes DESPUÉS de actualizar HTML
    document.querySelectorAll('.archivo-checkbox').forEach(cb => {
      const key = cb.dataset.hash + '::' + cb.dataset.ruta;
      if (checkboxesAnteriores[key]) {
        cb.checked = true;
      }
    });
  }
  
  // Scroll automático al final del log
  const logElement = document.getElementById('log');
  if (logElement) {
    logElement.scrollTop = logElement.scrollHeight;
  }
  
  setTimeout(actualizar, 500);  // Actualizar cada 500ms para mejor respuesta
}
window.onload = actualizar;
</script>
</head>
<body>
<h2>🔍 Dedupper - Detector de Duplicados + Generador de Miniaturas <small style="color: #666; font-size: 0.6em;">v""" + VERSION + """</small></h2>
<p>Selecciona una carpeta y elige una operación:</p>
<div style="margin-bottom: 1em;">
  <input type="text" id="carpeta" placeholder="Ruta de la carpeta (ej: C:\\Users\\Usuario\\Documents)" style="width: 100%; padding: .4em; background: #222; color: #eee; border: 1px solid #555; border-radius: .4em;">
</div>
<div class="btn-group">
  <button onclick="buscarDuplicados()">🔍 Buscar Duplicados</button>
  <button class="miniaturas" onclick="generarMiniaturas()">🖼️ Generar Miniaturas</button>
  <button class="preview" onclick="generarPreview()">📸 Preview Generator</button>
  <button class="analizador" onclick="analizarImagenes()">📊 Analizador</button>
  <button class="detener" onclick="detener()">⏹️ Detener</button>
  <button onclick="limpiar()" style="background: #6c757d;">🔄 Limpiar</button>
</div>
<div>
  <label><input type="checkbox" id="recursivo" checked> Incluir subcarpetas</label>
  <label><input type="checkbox" id="eliminar"> Eliminar Originales (Miniaturas)</label>
</div>
<h3 id="status">Esperando...</h3>
<div class="resumen" id="resumen">Sin datos aún...</div>
<div style="display: flex; justify-content: space-between; align-items: center;">
  <h3>📋 Duplicados Encontrados <small style="color: #888; font-size: 0.6em;" id="statusEscaneo">(sin escaneo activo)</small></h3>
  <div style="display: flex; gap: 0.5em;">
    <button id="btnCleanDedupped" onclick="limpiarDedupeados()" style="background: #17a2b8; color: #fff; padding: .5em 1em; font-weight: bold; cursor: pointer;" title="Eliminar de la lista los grupos ya procesados">🧹 Clean dedupped</button>
    <button id="btnDedupAll" onclick="dedupTodos()" style="background: #666; color: #999; padding: .5em 1em; font-weight: bold; cursor: not-allowed;" title="Inicia un escaneo primero" disabled>🗑️ Dedup all!</button>
  </div>
</div>
<div class="duplicados" id="duplicados">
  <div style="color: #888;">No se han detectado duplicados aún...</div>
</div>
<h3>📜 Log de Actividad</h3>
<pre id="log"></pre>
</body>
</html>
"""


# --- Rutas Flask ---
@app.route("/")
def index():
    response = app.make_response(render_template_string(HTML))
    # Deshabilitar caché completamente
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route("/estado")
def estado():
    estado_con_flags = estado_actual.copy()
    estado_con_flags["escaneo_completo"] = escaneo_completo
    response = jsonify(estado_con_flags)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


@app.route("/buscar_duplicados", methods=["POST"])
def ejecutar_buscar_duplicados():
    global procesando
    if procesando:
        return jsonify({"ok": False, "error": "Ya hay un proceso en ejecución"})
    
    data = request.get_json()
    carpeta = data.get("carpeta")
    recursivo = data.get("recursivo", True)
    
    if not carpeta or not os.path.exists(carpeta):
        return jsonify({"ok": False, "error": "Carpeta no válida"})
    
    estado_actual["mensaje"] = "Iniciando búsqueda de duplicados..."
    estado_actual["detalles"].clear()
    
    # Ejecutar en un hilo separado
    threading.Thread(target=buscar_duplicados, args=(carpeta, recursivo), daemon=True).start()
    
    return jsonify({"ok": True})


@app.route("/generar_miniaturas", methods=["POST"])
def ejecutar_generar_miniaturas():
    global procesando
    if procesando:
        return jsonify({"ok": False, "error": "Ya hay un proceso en ejecución"})
    
    data = request.get_json()
    carpeta = data.get("carpeta")
    eliminar = data.get("eliminar", False)
    recursivo = data.get("recursivo", True)
    
    if not carpeta or not os.path.exists(carpeta):
        return jsonify({"ok": False, "error": "Carpeta no válida"})
    
    estado_actual["mensaje"] = "Iniciando generación de miniaturas..."
    estado_actual["detalles"].clear()
    
    # Ejecutar en un hilo separado (ahora respeta el flag recursivo)
    if recursivo:
        threading.Thread(target=procesar_miniaturas, args=(carpeta, eliminar), daemon=True).start()
    else:
        # Para modo no recursivo, crear una versión simplificada
        threading.Thread(target=procesar_miniaturas_no_recursivo, args=(carpeta, eliminar), daemon=True).start()
    
    return jsonify({"ok": True})


@app.route("/eliminar_grupo", methods=["POST"])
def eliminar_grupo():
    data = request.get_json()
    hash_grupo = data.get("hash")
    
    if not hash_grupo:
        return jsonify({"ok": False, "error": "Hash no proporcionado"})
    
    resultado = eliminar_duplicados_grupo(hash_grupo)
    return jsonify(resultado)


@app.route("/eliminar_seleccionados", methods=["POST"])
def eliminar_seleccionados():
    """Elimina solo los archivos seleccionados manualmente por el usuario"""
    data = request.get_json()
    rutas_seleccionadas = data.get("rutas", [])
    hash_grupo = data.get("hash")
    
    if not rutas_seleccionadas:
        return jsonify({"ok": False, "error": "No hay archivos seleccionados"})
    
    # Buscar el grupo en el estado actual
    grupo_encontrado = None
    for grupo in estado_actual["duplicados"]:
        if grupo["hash"] == hash_grupo:
            grupo_encontrado = grupo
            break
    
    if not grupo_encontrado:
        return jsonify({"ok": False, "error": "Grupo no encontrado"})
    
    # Eliminar archivos seleccionados
    eliminados = 0
    errores = 0
    
    for ruta in rutas_seleccionadas:
        if os.path.exists(ruta):
            try:
                os.remove(ruta)
                eliminados += 1
                log_status(f"🗑️ Eliminado: {os.path.basename(ruta)}")
            except Exception as e:
                errores += 1
                log_status(f"❌ Error al eliminar {ruta}: {e}")
        else:
            log_status(f"⚠️ Archivo no existe: {ruta}")
    
    # Actualizar el estado del grupo
    if eliminados > 0:
        # Eliminar las rutas del grupo
        grupo_encontrado["archivos"] = [a for a in grupo_encontrado["archivos"] if a not in rutas_seleccionadas]
        grupo_encontrado["count"] = len(grupo_encontrado["archivos"])
        
        # Si solo queda 1 archivo, marcar como resuelto
        if grupo_encontrado["count"] <= 1:
            grupo_encontrado["eliminados"] = eliminados
            mb_liberados = (eliminados * grupo_encontrado["tamaño"]) / (1024 * 1024)
            grupo_encontrado["mb_liberados"] = mb_liberados
            log_status(f"✅ Grupo resuelto: {eliminados} archivo(s) eliminado(s), {mb_liberados:.2f} MB recuperados")
    
    return jsonify({"ok": True, "eliminados": eliminados, "errores": errores})


@app.route("/abrir_archivo", methods=["POST"])
def abrir_archivo():
    data = request.get_json()
    ruta = data.get("ruta")
    
    if not ruta or not os.path.exists(ruta):
        return jsonify({"ok": False, "error": "Archivo no encontrado"})
    
    try:
        # Abrir el archivo con la aplicación predeterminada del sistema
        os.startfile(ruta)
        return jsonify({"ok": True})
    except Exception as e:
        log_status(f"❌ Error al abrir archivo {ruta}: {e}")
        return jsonify({"ok": False, "error": str(e)})


@app.route("/limpiar", methods=["POST"])
def limpiar():
    """Limpia todo el estado actual"""
    global estado_actual, escaneo_completo
    estado_actual["mensaje"] = "Esperando orden..."
    estado_actual["detalles"].clear()
    estado_actual["resumen"].clear()
    estado_actual["duplicados"].clear()
    escaneo_completo = False  # Resetear a False (esperar nuevo escaneo)
    return jsonify({"ok": True})


@app.route("/limpiar_dedupeados", methods=["POST"])
def limpiar_dedupeados():
    """Elimina de la lista los grupos que ya han sido dedupeados (count == 1)"""
    global estado_actual
    
    # Filtrar solo grupos con 2+ archivos (eliminar los ya procesados)
    grupos_activos = [g for g in estado_actual["duplicados"] if g.get("count", 0) > 1]
    eliminados = len(estado_actual["duplicados"]) - len(grupos_activos)
    
    estado_actual["duplicados"] = grupos_activos
    
    # Actualizar resumen
    if estado_actual["resumen"]:
        estado_actual["resumen"]["grupos_duplicados"] = len(grupos_activos)
        estado_actual["resumen"]["archivos_duplicados"] = sum(g["count"] for g in grupos_activos)
    
    log_status(f"🧹 Limpieza: {eliminados} grupo(s) dedupeado(s) eliminado(s) de la lista")
    
    return jsonify({"ok": True, "eliminados": eliminados})


@app.route("/generar_preview", methods=["POST"])
def ejecutar_generar_preview():
    global procesando
    if procesando:
        return jsonify({"ok": False, "error": "Ya hay un proceso en ejecución"})
    
    data = request.get_json()
    carpeta = data.get("carpeta")
    recursivo = data.get("recursivo", False)
    
    if not carpeta or not os.path.exists(carpeta):
        return jsonify({"ok": False, "error": "Carpeta no válida"})
    
    estado_actual["mensaje"] = "Generando preview HTML..."
    estado_actual["detalles"].clear()
    
    # Ejecutar en un hilo separado con parámetro recursivo
    threading.Thread(target=generar_preview_html, args=(carpeta, recursivo), daemon=True).start()
    
    return jsonify({"ok": True})


@app.route("/analizar_imagenes", methods=["POST"])
def ejecutar_analizar_imagenes():
    global procesando
    if procesando:
        return jsonify({"ok": False, "error": "Ya hay un proceso en ejecución"})
    
    data = request.get_json()
    carpeta = data.get("carpeta")
    
    if not carpeta or not os.path.exists(carpeta):
        return jsonify({"ok": False, "error": "Carpeta no válida"})
    
    estado_actual["mensaje"] = "Analizando imágenes..."
    estado_actual["detalles"].clear()
    
    # Ejecutar en un hilo separado
    threading.Thread(target=analizar_imagenes, args=(carpeta,), daemon=True).start()
    
    return jsonify({"ok": True})


@app.route("/detener", methods=["POST"])
def detener():
    global detener_flag
    detener_flag = True
    log_status("🟥 Solicitud de detención recibida...")
    return jsonify({"ok": True})


if __name__ == "__main__":
    # Limpiar estado al iniciar
    estado_actual["mensaje"] = "Esperando orden..."
    estado_actual["detalles"].clear()
    estado_actual["resumen"].clear()
    estado_actual["duplicados"].clear()
    
    print("🌐 Servidor Dedupper iniciado en http://localhost:5000")
    print("📌 Estado limpio - Sin resultados previos cargados")
    app.run(host="0.0.0.0", port=5000, debug=False)
