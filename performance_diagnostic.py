"""Mesures non intrusives de la première ouverture Fiche (Core 20.24)."""
from __future__ import annotations
import os
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from PySide6.QtCore import QObject, QEvent, QTimer
from PySide6.QtWidgets import QPushButton

LOG = Path(__file__).resolve().parent / 'Diagnostics' / ('performance-' + str(os.getpid()) + '.log')

def write(message):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open('a', encoding='utf-8') as f:
            f.write(datetime.now().isoformat(timespec='milliseconds') + ' | ' + message + '\n')
    except Exception:
        pass

class FirstPaintWatcher(QObject):
    def __init__(self, window, start):
        super().__init__(window)
        self.start = start
        self.done = False

    def eventFilter(self, obj, event):
        if not self.done and event.type() == QEvent.Type.Paint and obj is self.parent():
            self.done = True
            write('PREMIER PAINT FICHE : %.3f s depuis clic Ouvrir' % (time.perf_counter()-self.start))
        return False

def install(main_cls, record_cls):
    write('=== DIAGNOSTIC PERFORMANCE 2.3.24.6.20.35 ===')
    # Sous-étapes : mesures cumulées pour distinguer chargement SQL, UI, modèle et affichage.
    for name in ('_preload_opening_referentials', '_build_ui', 'apply_collection_model',
                 'reload_records', '_refresh_display', '_restore_window_geometry'):
        original = getattr(record_cls, name, None)
        if not callable(original):
            continue
        def wrap(fn, label):
            @wraps(fn)
            def timed(self, *args, **kwargs):
                t = time.perf_counter()
                try:
                    return fn(self, *args, **kwargs)
                finally:
                    elapsed = time.perf_counter()-t
                    if label != '_refresh_display' or not getattr(self, '_perf_refresh_logged', False):
                        write('ETAPE %-34s %.3f s' % (label, elapsed))
                        if label == '_refresh_display':
                            self._perf_refresh_logged = True
            return timed
        setattr(record_cls, name, wrap(original, name))

    # Chronométrage détaillé des accès aux gestionnaires pendant la construction.
    from core.model_manager import ModelManager
    from core.record_manager import RecordManager
    from core.referential_manager import ReferentialManager
    for cls, method_names in (
        (ModelManager, ('field_masters', 'field_links', 'collection_preferences')),
        (RecordManager, ()),
        (ReferentialManager, ('ensure_defaults',)),
    ):
        for method_name in method_names:
            fn = getattr(cls, method_name, None)
            if not callable(fn):
                continue
            def manager_wrapper(original, label):
                @wraps(original)
                def measured(self, *args, **kwargs):
                    start = time.perf_counter()
                    try:
                        return original(self, *args, **kwargs)
                    finally:
                        write('GESTIONNAIRE %-36s %.3f s' % (label, time.perf_counter() - start))
                return measured
            setattr(cls, method_name, manager_wrapper(fn, cls.__name__ + '.' + method_name))

    original_create = main_cls._create_record_window
    @wraps(original_create)
    def create(self, *args, **kwargs):
        t = time.perf_counter()
        try:
            return original_create(self, *args, **kwargs)
        finally:
            write('CONSTRUCTION RecordWindow : %.3f s' % (time.perf_counter()-t))
    main_cls._create_record_window = create

    original_open = main_cls.open_records
    @wraps(original_open)
    def open_records(self, *args, **kwargs):
        start = time.perf_counter()
        write('CLIC OUVRIR FICHE | collection=%s' % str((self.collection or {}).get('name', '?')))
        previous = getattr(self, 'record_window', None)
        try:
            return original_open(self, *args, **kwargs)
        finally:
            elapsed = time.perf_counter()-start
            window = getattr(self, 'record_window', None)
            write('FIN open_records : %.3f s | %s' % (elapsed, 'réutilisation' if previous is not None and window is previous else 'création'))
            if window is not None:
                watcher = FirstPaintWatcher(window, start)
                window._gskol_perf_paint_watcher = watcher
                window.installEventFilter(watcher)
                QTimer.singleShot(0, lambda s=start: write('BOUCLE QT DISPONIBLE : %.3f s depuis clic' % (time.perf_counter()-s)))


    # 20.33 : traçage de la fermeture de la fenêtre Fiche (bouton et croix).
    # Ne modifie ni les validations, ni la sauvegarde, ni la décision de Qt.
    def trace_step(label, fn):
        @wraps(fn)
        def measured(self, *args, **kwargs):
            start = time.perf_counter()
            write('FERMETURE FICHE DEBUT %s' % label)
            try:
                return fn(self, *args, **kwargs)
            finally:
                write('FERMETURE FICHE FIN %-45s %.3f s' %
                      (label, time.perf_counter() - start))
        return measured

    for method_name in ('_confirm_referentials_in_batch_before_close',
                        '_confirm_unsaved_changes', '_save_window_geometry',
                        '_invalidate_restore'):
        original = getattr(record_cls, method_name, None)
        if callable(original):
            setattr(record_cls, method_name, trace_step(method_name, original))

    original_preferences = ModelManager.set_collection_preferences
    ModelManager.set_collection_preferences = trace_step(
        'ModelManager.set_collection_preferences', original_preferences)

    original_close_event = record_cls.closeEvent
    @wraps(original_close_event)
    def traced_close_event(self, event):
        start = time.perf_counter()
        write('FERMETURE FICHE closeEvent DEBUT | preview=%s | dirty=%s | visible=%s' %
              (getattr(self, 'preview_mode', '?'), getattr(self, 'dirty', '?'), self.isVisible()))
        try:
            return original_close_event(self, event)
        finally:
            write('FERMETURE FICHE closeEvent FIN %.3f s | accepte=%s | visible=%s' %
                  (time.perf_counter() - start, event.isAccepted(), self.isVisible()))
    record_cls.closeEvent = traced_close_event

    class CloseButtonWatcher(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.MouseButtonRelease:
                write('FERMETURE FICHE CLIC bouton Fermer la fiche | mouse release')
            return False

    original_build_ui = record_cls._build_ui
    @wraps(original_build_ui)
    def traced_build_ui(self, *args, **kwargs):
        result = original_build_ui(self, *args, **kwargs)
        for button in self.findChildren(QPushButton):
            if 'fermer la fiche' in button.text().casefold() or 'close record' in button.text().casefold() or 'close the record' in button.text().casefold() or 'kartei schließen' in button.text().casefold():
                watcher = CloseButtonWatcher(button)
                button._gskol_close_perf_watcher = watcher
                button.installEventFilter(watcher)
                write('FERMETURE FICHE bouton surveille | libelle=%r' % button.text())
        return result
    record_cls._build_ui = traced_build_ui
