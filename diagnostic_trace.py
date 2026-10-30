"""Diagnostic non intrusif des transitions d'interface G-Skol (version de test)."""
import faulthandler
import os
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / 'Diagnostics'
_lock = threading.RLock()
_file = None

def log(message):
    with _lock:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with (LOG_DIR / ('session-' + str(os.getpid()) + '.log')).open('a', encoding='utf-8') as f:
                f.write(datetime.now().isoformat(timespec='milliseconds') + ' | ' + str(message) + '\n')
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            pass

def start():
    global _file
    log('DEMARRAGE | pid=' + str(os.getpid()) + ' | python=' + sys.version.split()[0])
    try:
        _file = (LOG_DIR / ('fatal-' + str(os.getpid()) + '.log')).open('a', encoding='utf-8')
        faulthandler.enable(file=_file, all_threads=True)
        log('FAULTHANDLER ACTIVE')
    except Exception as exc:
        log('FAULTHANDLER INDISPONIBLE: ' + repr(exc))
    old_hook = sys.excepthook
    def hook(tp, value, tb):
        log('EXCEPTION PYTHON: ' + ''.join(traceback.format_exception(tp, value, tb))[-8000:])
        old_hook(tp, value, tb)
    sys.excepthook = hook
    def heartbeat():
        while True:
            time.sleep(10)
            log('PROCESSUS ACTIF')
    threading.Thread(target=heartbeat, daemon=True, name='gskol-diagnostic-heartbeat').start()

def instrument_main_window(cls):
    methods = ['show_collection_space', 'show_workshop_space', 'open_records',
               '_create_record_window', '_open_current_collection_workshop',
               '_open_master_model_workshop', 'open_collection', 'open_collection_file',
               'close_collection', 'closeEvent']
    for name in methods:
        original = getattr(cls, name, None)
        if not callable(original):
            continue
        def make_wrapper(fn, label):
            def wrapper(self, *args, **kwargs):
                log('DEBUT ' + label)
                try:
                    result = fn(self, *args, **kwargs)
                    log('FIN ' + label)
                    return result
                except BaseException:
                    log('ERREUR ' + label + '\n' + traceback.format_exc()[-8000:])
                    raise
            return wrapper
        setattr(cls, name, make_wrapper(original, name))
