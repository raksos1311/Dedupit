# Dedupit
Aplicación liviana para deduplicar archivos, además de algunas otras funcionalidades (Genera miniaturas, revisa tamaños, y prepara previews de carpetas)

## Preview Generator

El generador de previews crea una imagen PNG grande (3000x2000 píxeles) con miniaturas de fotos organizadas en una cuadrícula.

### Características

- **Lienzo**: 3000x2000 píxeles en formato PNG con transparencia
- **Cuadrícula**: 10 columnas × 9 filas = 90 espacios para miniaturas
- **Tamaño de miniaturas**: 260×260 píxeles cada una
- **Encabezado**: 40 píxeles en la parte superior
- **Distribución equidistante**: Las miniaturas se distribuyen uniformemente en el lienzo

### Lógica de Muestreo

El generador ajusta automáticamente el muestreo según la cantidad de fotos:

- **450+ fotos**: Muestra 1 miniatura por cada 5 fotos (mínimo de 90 × 5 = 450)
- **90-449 fotos**: Distribuye las fotos uniformemente para llenar los 90 espacios
- **Menos de 90 fotos**: Muestra todas las fotos y deja espacios vacíos transparentes

### Instalación

```bash
pip install -r requirements.txt
```

### Uso

```bash
# Generar preview en la misma carpeta de fotos
python3 preview_generator.py /ruta/a/carpeta/fotos

# Especificar ruta de salida
python3 preview_generator.py /ruta/a/carpeta/fotos -o /ruta/salida/preview.png
```

### Formatos Soportados

- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- BMP (.bmp)
- TIFF (.tiff)
- WebP (.webp)
