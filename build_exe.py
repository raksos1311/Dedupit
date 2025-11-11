# -*- coding: utf-8 -*-
"""
Script para construir el ejecutable de Dedupper con PyInstaller
"""
import PyInstaller.__main__
import os
import shutil

# Limpiar builds anteriores
if os.path.exists('build'):
    shutil.rmtree('build')
if os.path.exists('dist'):
    shutil.rmtree('dist')

# Construir el ejecutable
PyInstaller.__main__.run([
    'app.py',
    '--name=Dedupper',
    '--onefile',
    '--windowed',
    '--icon=NONE',
    '--add-data=README.md;.',
    '--hidden-import=PIL._tkinter_finder',
    '--collect-all=PIL',
    '--noconfirm',
])

print("\n✅ Ejecutable creado en: dist/Dedupper.exe")
