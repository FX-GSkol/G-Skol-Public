# -*- coding: utf-8 -*-
"""Assistant simple pour preparer la version et le texte de l'A propos avant compilation."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "core" / "version.py"
ISS_FILE = ROOT / "G-Skol.iss"
MAIN_FILE = ROOT / "ui" / "main_window.py"

for path in (VERSION_FILE, ISS_FILE, MAIN_FILE):
    if not path.is_file():
        print(f"Fichier introuvable : {path}")
        sys.exit(1)

version_text = VERSION_FILE.read_text(encoding="utf-8-sig")
m = re.search(r'^APP_VERSION\s*=\s*[\"\']([^\"\']*)[\"\']', version_text, re.M)
current = m.group(1) if m else "20.35.1"
print("=" * 58)
print("PERSONNALISER LA VERSION DE G-SKOL")
print("Ce programme ne fabrique pas les executables ; il prepare les fichiers.")
print("=" * 58)
new_version = input(f"Numero de version [{current}] : ").strip() or current
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,39}", new_version):
    print("Numero invalide. Utilise lettres, chiffres, points, tirets ou +.")
    sys.exit(2)

# The default empty tagline keeps the existing translated phrase.
old_tag = re.search(r'^ABOUT_TAGLINE\s*=\s*[\"\'](.*?)[\"\']\s*$', version_text, re.M)
current_tag = old_tag.group(1) if old_tag else ""
print("\nTexte supplementaire de l'A propos (facultatif).")
print("Laisser vide conserve le texte habituel traduit selon la langue de G-Skol.")
print("Si tu saisis un texte, il sera affiche tel quel dans les trois langues.")
tagline = input(f"Texte [{current_tag}] : ").strip()
if not tagline:
    tagline = ""
# Escape as a Python string literal, safely handling accents and quotes.
import json
quoted_tag = json.dumps(tagline, ensure_ascii=False)
if re.search(r'^APP_VERSION\s*=.*$', version_text, re.M):
    version_text = re.sub(r'^APP_VERSION\s*=.*$', f'APP_VERSION = {json.dumps(new_version)}', version_text, count=1, flags=re.M)
else:
    print("APP_VERSION introuvable dans core/version.py")
    sys.exit(3)
if re.search(r'^ABOUT_TAGLINE\s*=.*$', version_text, re.M):
    version_text = re.sub(r'^ABOUT_TAGLINE\s*=.*$', f'ABOUT_TAGLINE = {quoted_tag}', version_text, count=1, flags=re.M)
else:
    version_text = version_text.rstrip() + f'\nABOUT_TAGLINE = {quoted_tag}\n'

iss_text = ISS_FILE.read_text(encoding="utf-8-sig")
if not re.search(r'^#define AppVersion ".*"\s*$', iss_text, re.M):
    print('Ligne #define AppVersion introuvable dans G-Skol.iss')
    sys.exit(4)
iss_text = re.sub(r'^#define AppVersion ".*"\s*$', f'#define AppVersion "{new_version}"', iss_text, count=1, flags=re.M)

# Write only after all expected lines were found.
VERSION_FILE.write_text(version_text, encoding="utf-8")
ISS_FILE.write_text('\ufeff' + iss_text, encoding="utf-8")
print("\nPersonnalisation enregistree :")
print(f" - Version affichee dans G-Skol : {new_version}")
print(f" - Version indiquee dans l'installateur : {new_version}")
print(" - Texte A propos : " + (tagline if tagline else "texte habituel conserve"))
print("\nTu peux maintenant lancer CREER-G-SKOL-PORTABLE.bat, puis CREER-G-SKOL-INSTALLATEUR.bat.")
