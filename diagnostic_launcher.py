"""Lance G-Skol et note le code de sortie, même si le processus disparaît."""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parent
folder = root / 'Diagnostics'
folder.mkdir(exist_ok=True)
logfile = folder / ('surveillance-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.log')
def log(s):
    with logfile.open('a', encoding='utf-8') as f:
        f.write(datetime.now().isoformat(timespec='milliseconds') + ' | ' + s + '\n')
        f.flush()
        os.fsync(f.fileno())
log('SURVEILLANCE DEMARREE')
cmd = [sys.executable, '-u', str(root / 'app.py'), *sys.argv[1:]]
try:
    child = subprocess.Popen(cmd, cwd=str(root))
    log('PROCESSUS G-SKOL DEMARRE pid=' + str(child.pid))
    code = child.wait()
    log('PROCESSUS TERMINE code=' + str(code) + (' (sortie anormale possible)' if code else ' (code normal)'))
except BaseException as e:
    log('ERREUR SURVEILLANCE ' + repr(e))
    raise
