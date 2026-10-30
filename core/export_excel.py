"""Exportation XLSX en lecture seule, sans dépendance externe."""
import sqlite3
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape
from core.field_catalog import FIELDS


def _col(n):
    s = ''
    while n:
        n, r = divmod(n-1, 26)
        s = chr(65+r) + s
    return s


def _cell(value, address, bold=False):
    if value is None or isinstance(value, bytes):
        value = ''
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{address}"' + (' s="1"' if bold else '') + f'><v>{value}</v></c>'
    text = escape(str(value), {'"': '&quot;'})
    return f'<c r="{address}" t="inlineStr"' + (' s="1"' if bold else '') + f'><is><t xml:space="preserve">{text}</t></is></c>'


def export_collection_xlsx(source, collection_id, destination):
    """Une ligne par fiche, champs standard et personnalisés, sans photos."""
    source, destination = Path(source), Path(destination)
    con = sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        columns = {r['name'] for r in con.execute('PRAGMA table_info(records)')}
        # Source de vérité : le modèle enregistré DANS la collection.
        # Ne jamais rapprocher des champs par leur libellé : "Site", "Site4"
        # et "Site1" peuvent correspondre à des clés différentes.
        catalog = {f.key: f.label for f in FIELDS}
        custom_labels = {}
        if 'collection_custom_fields' in tables:
            custom_labels = {r['field_key']: r['label'] for r in con.execute(
                'SELECT field_key,label FROM collection_custom_fields WHERE collection_id=?', (collection_id,))}
        model = []
        if 'collection_model_fields' in tables:
            model = list(con.execute(
                'SELECT field_key,custom_label,visible,position FROM collection_model_fields '
                'WHERE collection_id=? ORDER BY CASE WHEN position IS NULL THEN 1 ELSE 0 END, position, field_key',
                (collection_id,)))
        fields = [('record_number', 'N° de fiche (G-Skol)')]
        selected = {'record_number'}
        if model:
            for m in model:
                key = m['field_key']
                if not m['visible'] or key in selected or key in ('photo_data', 'photo_format'):
                    continue
                if key not in columns and key not in custom_labels:
                    continue
                label = m['custom_label'] or custom_labels.get(key) or catalog.get(key) or key
                fields.append((key, label))
                selected.add(key)
            # Conserver aussi les champs personnalisés historiques non référencés
            # par le modèle (ils peuvent contenir des données).
            for key, label in custom_labels.items():
                if key not in selected:
                    fields.append((key, label))
                    selected.add(key)
        else:
            for f in FIELDS:
                if f.key in columns and f.key not in selected and f.key not in ('photo_data', 'photo_format'):
                    fields.append((f.key, f.label))
                    selected.add(f.key)
            for key, label in custom_labels.items():
                if key not in selected:
                    fields.append((key, label))
                    selected.add(key)
        # Les champs standard cachés ne doivent pas générer de colonnes
        # parasites ; les champs personnalisés sont lus par leur clé exacte.
        standard = [(k,v) for k,v in fields if k in columns]
        custom = [(k,v) for k,v in fields if k not in columns]
        if not fields:
            raise ValueError('Aucun champ disponible pour cet export.')
        headers, seen = [], set()
        for key, label in fields:
            label = str(label or key).strip()
            if label.casefold() in seen:
                label += ' (' + key + ')'
            seen.add(label.casefold())
            headers.append(label)
        values = {}
        if custom and 'record_custom_values' in tables:
            for r in con.execute('SELECT v.record_id,v.field_key,v.value FROM record_custom_values v '
                                 'JOIN records r ON r.id=v.record_id WHERE r.collection_id=?', (collection_id,)):
                values[(r['record_id'],r['field_key'])] = r['value']
        def xmlrow(rownum, data, bold=False):
            return f'<row r="{rownum}">' + ''.join(_cell(v, f'{_col(i)}{rownum}', bold) for i,v in enumerate(data,1)) + '</row>'
        sql_cols = ','.join('"'+k.replace('"','""')+'"' for k in ['id']+[k for k,_ in standard])
        rows = [xmlrow(1, headers, True)]
        count = 0
        for r in con.execute(f'SELECT {sql_cols} FROM records WHERE collection_id=? ORDER BY record_number', (collection_id,)):
            count += 1
            data = [r[key] if key in columns else values.get((r['id'],key),'') for key,_ in fields]
            rows.append(xmlrow(count+1, data))
        area = f'A1:{_col(len(fields))}{count+1}'
        sheet = ('<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                 '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
                 '<sheetData>'+''.join(rows)+'</sheetData><autoFilter ref="'+area+'"/></worksheet>')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
            z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
            z.writestr('xl/workbook.xml','<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Fiches" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
            z.writestr('xl/styles.xml','<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font/><font><b/></font></fonts><fills count="1"><fill><patternFill patternType="none"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0"/></cellXfs></styleSheet>')
            z.writestr('xl/worksheets/sheet1.xml',sheet)
        return count
    finally:
        con.close()
