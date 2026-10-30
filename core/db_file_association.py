"""Candidature MM3 dans « Ouvrir avec » et association facultative des .coldb Windows."""
from __future__ import annotations

from pathlib import Path
import sys


def register_db_association(app_path: Path, *, make_default: bool = False) -> bool:
    """Enregistre MM3 dans HKCU ; ne change le défaut que sur demande explicite."""
    if sys.platform != 'win32':
        raise OSError('L’association des fichiers .coldb est réservée à Windows.')
    import winreg

    app_path = Path(app_path).resolve()
    if getattr(sys, 'frozen', False):
        executable = Path(sys.executable).resolve()
        command = f'"{executable}" "%1"'
        icon = str(executable) + ',0'
    else:
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        executable = pythonw if pythonw.is_file() else Path(sys.executable)
        command = f'"{executable}" "{app_path}" "%1"'
        icon_path = app_path.parent / 'assets' / 'G-Skol.ico'
        icon = f'"{icon_path}",0' if icon_path.is_file() else str(executable) + ',0'

    def value(path, name, data, kind=winreg.REG_SZ):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            winreg.SetValueEx(key, name, 0, kind, data)

    value(r'Software\Classes\MM3.Collection', '', 'Collection G-Skol')
    value(r'Software\Classes\MM3.Collection\DefaultIcon', '', icon)
    value(r'Software\Classes\MM3.Collection\shell\open\command', '', command)
    value(r'Software\Classes\.coldb\OpenWithProgids', 'MM3.Collection', b'', winreg.REG_NONE)
    capabilities = r'Software\MM3\Capabilities'
    value(capabilities, 'ApplicationName', 'G-Skol')
    value(capabilities, 'ApplicationDescription', 'G-Skol — Gestion de collections')
    value(capabilities + r'\FileAssociations', '.coldb', 'MM3.Collection')
    value(r'Software\RegisteredApplications', 'G-Skol', capabilities)
    value(r'Software\Classes\Applications\G-Skol.exe\shell\open\command', '', command)
    value(r'Software\Classes\Applications\G-Skol.exe\SupportedTypes', '.coldb', '')
    if make_default:
        value(r'Software\Classes\.coldb', '', 'MM3.Collection')
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except (AttributeError, OSError):
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.coldb\UserChoice') as key:
            chosen, _kind = winreg.QueryValueEx(key, 'ProgId')
            return str(chosen) != 'MM3.Collection'
    except FileNotFoundError:
        return False
