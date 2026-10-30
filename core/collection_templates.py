#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Modèles de départ MM3 — génération initiale uniquement."""

from __future__ import annotations

import copy
from pathlib import Path

MINERALS_VISIBLE_FIELDS = {'site_internet_link', 'category', 'record_number', 'crystal_system', 'mineral_3', 'country', 'box_count', 'growth', 'luminescence_intensity', 'minimum_magnification', 'price', 'mineral_class', 'chemical_formula', 'specimen_shape', 'contact', 'internet_link', 'department', 'type_locality', 'mineral_name', 'record_state', 'luminescence', 'region', 'site_name', 'quality', 'origin', 'description', 'mineral_2', 'place', 'fluorescence_color', 'acquisition_date', 'box_type', 'specimen_color', 'total_cost', 'photo_data', 'deposit'}
MINERALS_VISUAL_POSITIONS = {'acquisition_date': (883, 679), 'box_count': (7, 931), 'box_type': (43, 981), 'category': (611, 522), 'chemical_formula': (404, 232), 'contact': (883, 753), 'country': (36, 592), 'crystal_system': (18, 268), 'department': (36, 522), 'deposit': (47, 482), 'description': (22, 790), 'fluorescence_color': (442, 306), 'growth': (22, 679), 'internet_link': (22, 343), 'luminescence': (422, 268), 'luminescence_intensity': (47, 306), 'mineral_2': (211, 92), 'mineral_3': (217, 125), 'mineral_class': (47, 232), 'mineral_name': (210, 42), 'minimum_magnification': (518, 679), 'origin': (883, 715), 'photo_data': (0, 0), 'place': (883, 790), 'price': (474, 932), 'quality': (472, 750), 'record_number': (22, 44), 'record_state': (714, 43), 'region': (36, 557), 'site_internet_link': (611, 593), 'site_name': (36, 449), 'specimen_color': (22, 714), 'specimen_shape': (22, 750), 'total_cost': (474, 981), 'type_locality': (611, 450)}
MINERALS_VISUAL_SIZES = {'acquisition_date': (440, 36), 'box_count': (276, 36), 'box_type': (392, 36), 'category': (518, 36), 'chemical_formula': (428, 36), 'contact': (440, 36), 'country': (506, 36), 'crystal_system': (389, 36), 'department': (506, 36), 'deposit': (494, 36), 'description': (812, 72), 'fluorescence_color': (390, 36), 'growth': (389, 36), 'internet_link': (810, 36), 'luminescence': (410, 36), 'luminescence_intensity': (360, 36), 'mineral_2': (399, 36), 'mineral_3': (393, 36), 'mineral_class': (360, 36), 'mineral_name': (400, 36), 'minimum_magnification': (315, 36), 'origin': (440, 36), 'photo_data': (300, 170), 'place': (440, 36), 'price': (250, 36), 'quality': (360, 36), 'record_number': (169, 31), 'record_state': (332, 36), 'region': (506, 36), 'site_internet_link': (518, 36), 'site_name': (506, 36), 'specimen_color': (389, 36), 'specimen_shape': (389, 36), 'total_cost': (246, 36), 'type_locality': (518, 36)}
MINERALS_TAB_ORDER = ['record_number', 'mineral_name', 'record_state', 'mineral_2', 'mineral_3', 'mineral_class', 'chemical_formula', 'crystal_system', 'luminescence', 'luminescence_intensity', 'fluorescence_color', 'internet_link', 'site_name', 'type_locality', 'deposit', 'department', 'category', 'region', 'country', 'site_internet_link', 'growth', 'minimum_magnification', 'acquisition_date', 'specimen_color', 'origin', 'specimen_shape', 'quality', 'contact', 'description', 'place', 'box_count', 'price', 'box_type', 'total_cost', 'photo_data']
MINERALS_FIELD_STYLES = {'chemical_formula': {'label': {'x': 0, 'width': 156, 'align': 'right'}, 'data': {'x': 156, 'width': 272, 'color': '#000000'}}, 'luminescence': {'label': {'x': 0, 'width': 138, 'align': 'right'}, 'data': {'x': 138, 'width': 272, 'color': '#000000'}}, 'fluorescence_color': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 118, 'width': 272, 'color': '#000000'}}, 'crystal_system': {'label': {'x': 0, 'width': 147, 'align': 'right'}, 'data': {'x': 147, 'width': 242, 'color': '#000000'}}, 'luminescence_intensity': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 118, 'width': 242, 'color': '#000000'}}, 'mineral_class': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 118, 'width': 242, 'color': '#000000'}}, 'internet_link': {'label': {'x': 0, 'width': 150, 'align': 'left'}, 'data': {'x': 118, 'width': 692, 'color': '#000000'}}, 'mineral_2': {'label': {'align': 'right', 'x': 0, 'width': 118}, 'data': {'x': 117, 'width': 282, 'color': '#000000'}}, 'mineral_3': {'label': {'align': 'right', 'x': 0, 'width': 118}, 'data': {'x': 111, 'width': 282, 'color': '#000000'}}, 'mineral_name': {'label': {'align': 'right', 'x': 0, 'width': 118, 'family': 'Segoe UI', 'size': 9, 'bold': True, 'italic': False, 'underline': False}, 'data': {'x': 118, 'width': 282, 'family': 'Segoe UI', 'size': 9, 'bold': True, 'italic': False, 'underline': False, 'align': 'left', 'color': '#000000'}}, 'record_state': {'label': {'x': 0, 'width': 126}, 'data': {'x': 143, 'width': 189, 'align': 'center', 'bold': True, 'color': '#000000'}}, 'site_name': {'label': {'x': 0, 'width': 107, 'align': 'right'}, 'data': {'x': 104, 'width': 401, 'color': '#000000'}}, 'deposit': {'label': {'x': 0, 'width': 94, 'align': 'right'}, 'data': {'x': 93, 'width': 401, 'color': '#000000'}}, 'country': {'label': {'x': 0, 'width': 107, 'align': 'right'}, 'data': {'x': 104, 'width': 401, 'color': '#000000'}}, 'department': {'label': {'x': 0, 'width': 111, 'align': 'right'}, 'data': {'x': 104, 'width': 401, 'color': '#000000'}}, 'region': {'label': {'x': 0, 'width': 103, 'align': 'right'}, 'data': {'x': 104, 'width': 401, 'color': '#000000'}}, 'place': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 118, 'width': 322, 'color': '#000000'}}, 'origin': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 118, 'width': 322, 'color': '#000000'}}, 'contact': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 118, 'width': 322, 'color': '#000000'}}, 'acquisition_date': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 118, 'width': 322, 'color': '#000000'}}, 'specimen_shape': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 117, 'width': 272, 'color': '#000000'}}, 'specimen_color': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 117, 'width': 272, 'color': '#000000'}}, 'growth': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 117, 'width': 272, 'color': '#000000'}}, 'minimum_magnification': {'label': {'x': 0, 'width': 167}, 'data': {'x': 167, 'width': 149, 'color': '#000000'}}, 'quality': {'label': {'x': 0, 'width': 88, 'align': 'right'}, 'data': {'x': 88, 'width': 272, 'color': '#000000'}}, 'site_internet_link': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 117, 'width': 401, 'color': '#000000'}}, 'type_locality': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 117, 'width': 401, 'color': '#000000'}}, 'category': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 117, 'width': 401, 'color': '#000000'}}, 'description': {'label': {'align': 'right', 'x': 0, 'width': 118}, 'data': {'x': 118, 'width': 694, 'color': '#000000'}}, 'total_cost': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 118, 'width': 128, 'align': 'right', 'color': '#000000'}}, 'box_count': {'label': {'x': 0, 'width': 151, 'align': 'right'}, 'data': {'x': 150, 'width': 126, 'align': 'center', 'color': '#000000'}}, 'box_type': {'label': {'x': 0, 'width': 115, 'align': 'right'}, 'data': {'x': 114, 'width': 278, 'align': 'left', 'color': '#000000'}}, 'price': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'x': 118, 'width': 132, 'align': 'right', 'color': '#000000'}}, 'record_number': {'data': {'color': '#000000'}}}
MINERALS_GROUP_STYLES = {'__mm3_layout__': {'model_kind': 'minerals', 'field_space': 'sheet_absolute_v1'}, 'Identification': {'geometry': {'x': 0, 'y': 135, 'w': 620, 'h': 161}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': 0}}, 'Photo': {'geometry': {'x': 620, 'y': 135, 'w': 220, 'h': 161}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': 0}}, 'Collection': {'geometry': {'x': 0, 'y': 632, 'w': 983, 'h': 113}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': 14}}, 'Aspect': {'geometry': {'x': 0, 'y': 457, 'w': 620, 'h': 175}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': 0}}, 'Acquisition': {'geometry': {'x': 620, 'y': 457, 'w': 362, 'h': 175}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': 0}}, 'Localisation': {'geometry': {'x': 0, 'y': 296, 'w': 981, 'h': 161}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': 0}}, 'Bandeau': {'geometry': {'x': 0, 'y': 0, 'w': 983, 'h': 135}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': 0}}}
MINERALS_SHEET_BACKGROUND = '#D0D0D0'
MINERALS_CUSTOM_LABELS = {'mineral_name': 'Espèce', 'box_count': 'Nombre de pièces', 'box_type': 'Contenant'}


# 23.9.2.5 — le prototype Minéraux reprend les deux champs ajoutés dans
# l'Atelier utilisateur, avec leur géométrie réelle. Les clés sont recréées
# par collection ; les constantes utilisent donc un nom symbolique CUSTOM:.
MINERALS_CUSTOM_SPECS = [
    ("Dureté", "text", "Identification", "JJ/MM/AAAA"),
    ("Variété de", "text", "Identification", "JJ/MM/AAAA"),
]
MINERALS_VISUAL_POSITIONS.update({
    'chemical_formula': (7, 269), 'crystal_system': (7, 307),
    'CUSTOM:Dureté': (7, 344), 'CUSTOM:Variété de': (7, 382),
    'luminescence': (572, 276), 'luminescence_intensity': (592, 328),
    'fluorescence_color': (592, 381), 'internet_link': (161, 426),
    'site_name': (36, 515), 'type_locality': (611, 517), 'deposit': (47, 549),
    'department': (36, 589), 'category': (611, 589), 'region': (36, 624),
    'country': (36, 658), 'site_internet_link': (611, 660),
    'growth': (22, 746), 'minimum_magnification': (518, 746),
    'specimen_color': (22, 781), 'specimen_shape': (22, 817), 'quality': (472, 817),
    'description': (22, 857), 'acquisition_date': (883, 746), 'origin': (883, 782),
    'contact': (883, 819), 'place': (883, 857), 'box_count': (7, 997),
    'price': (474, 999), 'box_type': (43, 1047), 'total_cost': (474, 1047),
    'mineral_class': (7, 232),
})
MINERALS_VISUAL_SIZES.update({
    'mineral_class': (538, 36), 'chemical_formula': (538, 36),
    'crystal_system': (538, 36), 'CUSTOM:Dureté': (538, 36),
    'CUSTOM:Variété de': (538, 36), 'luminescence': (418, 36),
    'luminescence_intensity': (399, 36), 'fluorescence_color': (399, 36),
})
MINERALS_FIELD_STYLES.update({
    'mineral_class': {'label': {'x': 0, 'width': 182, 'align': 'left'}, 'data': {'x': 158, 'width': 379, 'color': '#000000'}},
    'chemical_formula': {'label': {'x': 0, 'width': 182, 'align': 'left'}, 'data': {'x': 158, 'width': 379, 'color': '#000000'}},
    'crystal_system': {'label': {'x': 0, 'width': 182, 'align': 'left'}, 'data': {'x': 158, 'width': 379, 'color': '#000000'}},
    'CUSTOM:Dureté': {'label': {'x': 0, 'width': 182, 'align': 'left'}, 'data': {'x': 158, 'width': 379}},
    'CUSTOM:Variété de': {'label': {'x': 0, 'width': 182, 'align': 'left'}, 'data': {'x': 158, 'width': 379}},
})
MINERALS_GROUP_STYLES = {
    '__mm3_layout__': {'model_kind': 'minerals', 'field_space': 'sheet_absolute_v1'},
    'Identification': {'geometry': {'x': 0, 'y': 135, 'w': 724, 'h': 206}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': -28}},
    'Photo': {'geometry': {'x': 739, 'y': 135, 'w': 220, 'h': 161}, 'geometry_space': 'atelier_px', 'position': {'dx': 119, 'dy': -28}},
    'Collection': {'geometry': {'x': 0, 'y': 680, 'w': 983, 'h': 113}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': -945}},
    'Aspect': {'geometry': {'x': 0, 'y': 505, 'w': 620, 'h': 175}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': -478}},
    'Acquisition': {'geometry': {'x': 620, 'y': 505, 'w': 362, 'h': 175}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': -478}},
    'Localisation': {'geometry': {'x': 0, 'y': 344, 'w': 981, 'h': 161}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': -139}},
    'Bandeau': {'geometry': {'x': 0, 'y': 0, 'w': 983, 'h': 135}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': 0}},
}
MINERALS_TAB_ORDER = [
    'record_number', 'mineral_name', 'record_state', 'mineral_2', 'mineral_3',
    'mineral_class', 'chemical_formula', 'crystal_system', 'CUSTOM:Dureté',
    'CUSTOM:Variété de', 'luminescence', 'luminescence_intensity', 'internet_link',
    'fluorescence_color', 'site_name', 'type_locality', 'deposit', 'department',
    'category', 'region', 'country', 'site_internet_link', 'growth', 'specimen_color',
    'specimen_shape', 'description', 'minimum_magnification', 'quality',
    'acquisition_date', 'origin', 'contact', 'place', 'box_count', 'price',
    'box_type', 'total_cost', 'photo_data',
]



def ensure_minerals_legacy_fields(manager, collection_id: int) -> bool:
    """23.9.3.1.1 — ajoute sans doublon Dureté / Variété de aux anciens Minéraux.

    La migration ne modifie jamais la mise en page existante : tout champ créé
    est immédiatement retiré de la Fiche et reste disponible dans la palette.
    """
    cid = int(collection_id)
    styles = manager.group_styles(cid)
    meta = styles.get("__mm3_layout__", {}) if isinstance(styles, dict) else {}
    model_kind = str(meta.get("model_kind", "") or "").strip().lower()

    visible_before = set(manager.visible_fields(cid))
    looks_like_minerals = (
        model_kind == "minerals"
        or {"mineral_name", "mineral_class", "crystal_system"}.issubset(visible_before)
    )
    if not looks_like_minerals:
        return False

    existing = {
        str(row.get("label", "") or "").strip().casefold(): dict(row)
        for row in manager.custom_fields(cid)
    }
    created_keys = []
    for label, field_type, group, date_format in MINERALS_CUSTOM_SPECS:
        if label.casefold() in existing:
            continue
        info = manager.create_custom_field(
            cid, label, field_type,
            initial_group=group, date_format=date_format
        )
        created_keys.append(str(info["field_key"]))

    if not created_keys:
        return False

    # create_custom_field rend le champ visible par défaut : pour une ancienne
    # fiche, on respecte la règle MM3 "palette d'abord, placement par l'utilisateur".
    visible_after = set(manager.visible_fields(cid))
    visible_after.difference_update(created_keys)
    manager.set_visible_fields(cid, visible_after)
    return True

def apply_minerals_template(manager, collection_id: int) -> None:
    cid = int(collection_id)
    custom = {}
    for label, field_type, group, date_format in MINERALS_CUSTOM_SPECS:
        info = manager.create_custom_field(
            cid, label, field_type, initial_group=group, date_format=date_format
        )
        custom[label] = info["field_key"]

    def real_key(key):
        key = str(key)
        return custom[key[7:]] if key.startswith("CUSTOM:") else key

    visible = {real_key(k) for k in MINERALS_VISIBLE_FIELDS}
    visible.update(custom.values())
    manager.set_visible_fields(cid, visible)
    manager.set_custom_labels(cid, dict(MINERALS_CUSTOM_LABELS))
    manager.set_field_placement(cid, {
        custom['Dureté']: ('Identification', 0),
        custom['Variété de']: ('Identification', 1),
    })
    manager.set_visual_positions(cid, {real_key(k): v for k, v in MINERALS_VISUAL_POSITIONS.items()})
    manager.set_visual_sizes(cid, {real_key(k): v for k, v in MINERALS_VISUAL_SIZES.items()})
    manager.set_tab_order(cid, [real_key(k) for k in MINERALS_TAB_ORDER])
    manager.set_sheet_background(cid, MINERALS_SHEET_BACKGROUND)
    manager.set_field_styles(cid, {real_key(k): v for k, v in MINERALS_FIELD_STYLES.items()})
    manager.set_group_styles(cid, dict(MINERALS_GROUP_STYLES))



SANDS_SAVED_ROWS = {'acquisition_date': {'visible': 1, 'custom_label': None, 'block_name': 'Acquisition', 'position': 0, 'visual_x': 1029, 'visual_y': 710, 'visual_w': 340, 'visual_h': 33}, 'box_count': {'visible': 1, 'custom_label': None, 'block_name': 'Collection', 'position': 2, 'visual_x': 496, 'visual_y': 849, 'visual_w': 256, 'visual_h': 36}, 'box_type': {'visible': 1, 'custom_label': None, 'block_name': 'Collection', 'position': 0, 'visual_x': 72, 'visual_y': 849, 'visual_w': 365, 'visual_h': 36}, 'category': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 12, 'visual_y': 49, 'visual_w': 520, 'visual_h': 31}, 'chemical_formula': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 385, 'visual_y': 12, 'visual_w': 390, 'visual_h': 31}, 'contact': {'visible': 1, 'custom_label': None, 'block_name': 'Acquisition', 'position': 2, 'visual_x': 1029, 'visual_y': 788, 'visual_w': 340, 'visual_h': 33}, 'country': {'visible': 1, 'custom_label': None, 'block_name': 'Localisation', 'position': 4, 'visual_x': 83, 'visual_y': 246, 'visual_w': 582, 'visual_h': 36}, 'crystal_system': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 12, 'visual_y': 49, 'visual_w': 360, 'visual_h': 31}, 'CUSTOM:Stock échange': {'visible': 1, 'custom_label': None, 'block_name': 'Collection', 'position': 5, 'visual_x': 42, 'visual_y': 925, 'visual_w': 396, 'visual_h': 36}, 'CUSTOM:Quantité (en Gr)': {'visible': 1, 'custom_label': None, 'block_name': 'Collection', 'position': 1, 'visual_x': 29, 'visual_y': 886, 'visual_w': 408, 'visual_h': 36}, 'CUSTOM:Localisation précise': {'visible': 1, 'custom_label': None, 'block_name': 'Localisation', 'position': 5, 'visual_x': 712, 'visual_y': 246, 'visual_w': 593, 'visual_h': 36}, 'CUSTOM:Type de sable': {'visible': 1, 'custom_label': None, 'block_name': 'Identification', 'position': 0, 'visual_x': 429, 'visual_y': 417, 'visual_w': 544, 'visual_h': 33}, 'CUSTOM:Granulométrie': {'visible': 1, 'custom_label': None, 'block_name': 'Identification', 'position': 2, 'visual_x': 419, 'visual_y': 496, 'visual_w': 554, 'visual_h': 36}, 'CUSTOM:Nature dominante': {'visible': 1, 'custom_label': None, 'block_name': 'Identification', 'position': 3, 'visual_x': 388, 'visual_y': 536, 'visual_w': 586, 'visual_h': 36}, 'CUSTOM:Couleur dominante': {'visible': 1, 'custom_label': None, 'block_name': 'Identification', 'position': 1, 'visual_x': 379, 'visual_y': 454, 'visual_w': 593, 'visual_h': 36}, 'CUSTOM:Magnétisme': {'visible': 1, 'custom_label': None, 'block_name': 'Identification', 'position': 5, 'visual_x': 429, 'visual_y': 617, 'visual_w': 544, 'visual_h': 33}, 'CUSTOM:Composition': {'visible': 1, 'custom_label': None, 'block_name': 'Identification', 'position': 4, 'visual_x': 429, 'visual_y': 576, 'visual_w': 544, 'visual_h': 33}, 'CUSTOM:Commune': {'visible': 1, 'custom_label': None, 'block_name': 'Localisation', 'position': 1, 'visual_x': 764, 'visual_y': 167, 'visual_w': 542, 'visual_h': 36}, 'department': {'visible': 1, 'custom_label': 'Département / Province', 'block_name': 'Localisation', 'position': 2, 'visual_x': 7, 'visual_y': 207, 'visual_w': 658, 'visual_h': 36}, 'deposit': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 545, 'visual_y': 12, 'visual_w': 420, 'visual_h': 31}, 'description': {'visible': 1, 'custom_label': 'Description / observations', 'block_name': 'Aspect', 'position': 0, 'visual_x': 365, 'visual_y': 661, 'visual_w': 621, 'visual_h': 126}, 'fluorescence_color': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 385, 'visual_y': 86, 'visual_w': 390, 'visual_h': 31}, 'growth': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 12, 'visual_y': 12, 'visual_w': 360, 'visual_h': 31}, 'internet_link': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 12, 'visual_y': 123, 'visual_w': 763, 'visual_h': 31}, 'luminescence': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 385, 'visual_y': 49, 'visual_w': 390, 'visual_h': 31}, 'luminescence_intensity': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 12, 'visual_y': 86, 'visual_w': 360, 'visual_h': 31}, 'mineral_2': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 18, 'visual_y': 48, 'visual_w': 390, 'visual_h': 31}, 'mineral_3': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 420, 'visual_y': 48, 'visual_w': 400, 'visual_h': 31}, 'mineral_class': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 12, 'visual_y': 12, 'visual_w': 360, 'visual_h': 31}, 'mineral_name': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 200, 'visual_y': 10, 'visual_w': 360, 'visual_h': 31}, 'minimum_magnification': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 385, 'visual_y': 86, 'visual_w': 390, 'visual_h': 31}, 'origin': {'visible': 1, 'custom_label': None, 'block_name': 'Acquisition', 'position': 1, 'visual_x': 1029, 'visual_y': 747, 'visual_w': 340, 'visual_h': 33}, 'photo_data': {'visible': 1, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 28, 'visual_y': 350, 'visual_w': 455, 'visual_h': 205}, 'place': {'visible': 1, 'custom_label': None, 'block_name': 'Acquisition', 'position': 3, 'visual_x': 1029, 'visual_y': 828, 'visual_w': 340, 'visual_h': 33}, 'price': {'visible': 1, 'custom_label': None, 'block_name': 'Collection', 'position': 3, 'visual_x': 599, 'visual_y': 886, 'visual_w': 153, 'visual_h': 36}, 'quality': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 385, 'visual_y': 49, 'visual_w': 390, 'visual_h': 31}, 'record_number': {'visible': 1, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 28, 'visual_y': 81, 'visual_w': 200, 'visual_h': 33}, 'record_state': {'visible': 1, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 1049, 'visual_y': 81, 'visual_w': 290, 'visual_h': 33}, 'region': {'visible': 1, 'custom_label': None, 'block_name': 'Localisation', 'position': 3, 'visual_x': 764, 'visual_y': 206, 'visual_w': 542, 'visual_h': 36}, 'site_internet_link': {'visible': 1, 'custom_label': None, 'block_name': 'Localisation', 'position': 6, 'visual_x': 201, 'visual_y': 310, 'visual_w': 932, 'visual_h': 36}, 'site_name': {'visible': 1, 'custom_label': None, 'block_name': 'Localisation', 'position': 0, 'visual_x': 83, 'visual_y': 168, 'visual_w': 582, 'visual_h': 36}, 'specimen_color': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 12, 'visual_y': 49, 'visual_w': 360, 'visual_h': 31}, 'specimen_shape': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 385, 'visual_y': 12, 'visual_w': 390, 'visual_h': 31}, 'total_cost': {'visible': 1, 'custom_label': None, 'block_name': 'Collection', 'position': 4, 'visual_x': 562, 'visual_y': 925, 'visual_w': 189, 'visual_h': 36}, 'type_locality': {'visible': 0, 'custom_label': None, 'block_name': None, 'position': None, 'visual_x': 12, 'visual_y': 86, 'visual_w': 360, 'visual_h': 31}}
SANDS_SAVED_FIELD_STYLES = {'record_number': {'data': {'color': '#000000'}}, 'site_name': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 464}}, 'site_internet_link': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 814}}, 'department': {'label': {'x': 0, 'width': 194, 'align': 'right'}, 'data': {'color': '#000000', 'x': 194, 'width': 464}}, 'region': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 424}}, 'country': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 464}}, 'description': {'label': {'x': 0, 'width': 217}, 'data': {'color': '#000000', 'x': 211, 'width': 410}}, 'box_type': {'label': {'x': 0, 'width': 100}, 'data': {'color': '#000000', 'x': 99, 'width': 267}}, 'box_count': {'label': {'x': 0, 'width': 160, 'align': 'right'}, 'data': {'color': '#000000', 'x': 156, 'width': 100, 'align': 'center'}}, 'price': {'label': {'x': 0, 'width': 57, 'align': 'right'}, 'data': {'color': '#000000', 'x': 53, 'width': 100, 'align': 'center'}}, 'total_cost': {'label': {'x': 0, 'width': 93, 'align': 'right'}, 'data': {'color': '#000000', 'x': 89, 'width': 100, 'align': 'center'}}, 'acquisition_date': {'data': {'color': '#000000'}}, 'origin': {'data': {'color': '#000000'}}, 'contact': {'data': {'color': '#000000'}}, 'place': {'data': {'color': '#000000'}}, 'record_state': {'data': {'color': '#000000'}}, 'photo_data': {'data': {'color': '#000000'}}, 'CUSTOM:Stock échange': {'label': {'x': 0, 'width': 129}, 'data': {'color': '#000000', 'x': 129, 'width': 267}}, 'CUSTOM:Quantité (en Gr)': {'label': {'x': 0, 'width': 142}, 'data': {'color': '#000000', 'x': 142, 'width': 267}}, 'CUSTOM:Localisation précise': {'label': {'x': 0, 'width': 169, 'align': 'right'}, 'data': {'color': '#000000', 'x': 169, 'width': 424}}, 'CUSTOM:Type de sable': {'data': {'color': '#000000'}}, 'CUSTOM:Granulométrie': {'label': {'x': 0, 'width': 128}, 'data': {'color': '#000000', 'x': 128, 'width': 426}}, 'CUSTOM:Nature dominante': {'label': {'x': 0, 'width': 160}, 'data': {'color': '#000000', 'x': 160, 'width': 426}}, 'CUSTOM:Couleur dominante': {'label': {'x': 0, 'width': 167}, 'data': {'color': '#000000', 'x': 167, 'width': 426}}, 'CUSTOM:Magnétisme': {'data': {'color': '#000000'}}, 'CUSTOM:Composition': {'data': {'color': '#000000'}}, 'CUSTOM:Commune': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 424}}}
SANDS_SAVED_GROUP_STYLES = {'__mm3_layout__': {'model_kind': 'sands', 'field_space': 'sheet_absolute_v1'}, 'Bandeau': {'geometry': {'x': 12, 'y': 27, 'w': 976, 'h': 71}, 'geometry_space': 'atelier_px', 'position': {'dx': 12, 'dy': 20}, 'title': {'text': 'Bandeau', 'bold': True}}, 'Localisation': {'geometry': {'x': 3, 'y': 98, 'w': 992, 'h': 156}, 'geometry_space': 'atelier_px', 'position': {'dx': 3, 'dy': -554}, 'title': {'text': 'Localisation', 'bold': True}}, 'Photo': {'geometry': {'x': 9, 'y': 269, 'w': 259, 'h': 195}, 'geometry_space': 'atelier_px', 'position': {'dx': -620, 'dy': 134}, 'title': {'text': 'Photo du site', 'bold': True}}, 'Identification': {'geometry': {'x': 268, 'y': 269, 'w': 463, 'h': 311}, 'geometry_space': 'atelier_px', 'position': {'dx': 268, 'dy': 134}, 'title': {'text': 'Identification du sable', 'bold': True}}, 'Acquisition': {'geometry': {'x': 731, 'y': 464, 'w': 259, 'h': 164}, 'geometry_space': 'atelier_px', 'position': {'dx': 119, 'dy': -486}, 'title': {'text': 'Acquisition', 'bold': True}}, 'Aspect': {'geometry': {'x': 12, 'y': 865, 'w': 976, 'h': 52}, 'geometry_space': 'atelier_px', 'position': {'dx': 12, 'dy': -193}, 'title': {'text': 'Observations', 'bold': True}, 'frame_deleted': True}, 'Collection': {'geometry': {'x': 10, 'y': 580, 'w': 559, 'h': 121}, 'geometry_space': 'atelier_px', 'position': {'dx': 10, 'dy': -1155}, 'title': {'text': 'Collection', 'bold': True}}, 'photo_slot_2': {'custom_group': True, 'custom_photo': True, 'frame_deleted': False, 'geometry': {'x': 738, 'y': 269, 'w': 259, 'h': 195}, 'geometry_space': 'atelier_px', 'position': {'dx': 228, 'dy': -63}, 'title': {'text': 'Photo du sable', 'bold': True}}}
SANDS_SHEET_BACKGROUND = '#FFF0BF'
SANDS_CUSTOM_SPECS = [('Stock échange', 'list', 'Collection', 'JJ/MM/AAAA'), ('Quantité (en Gr)', 'numeric', 'Collection', 'JJ/MM/AAAA'), ('Localisation précise', 'text', 'Localisation', 'JJ/MM/AAAA'), ('Type de sable', 'list', 'Identification', 'JJ/MM/AAAA'), ('Granulométrie', 'list', 'Identification', 'JJ/MM/AAAA'), ('Nature dominante', 'list', 'Identification', 'JJ/MM/AAAA'), ('Couleur dominante', 'list', 'Identification', 'JJ/MM/AAAA'), ('Magnétisme', 'list', 'Identification', 'JJ/MM/AAAA'), ('Composition', 'text', 'Identification', 'JJ/MM/AAAA'), ('Commune', 'list', 'Localisation', 'JJ/MM/AAAA')]
SANDS_REFERENTIAL_SEEDS = {}
SANDS_SAVED_TAB_ORDER = ['record_number', 'record_state', 'site_name', 'CUSTOM:Commune', 'department', 'region', 'country', 'CUSTOM:Localisation précise', 'site_internet_link', 'CUSTOM:Type de sable', 'CUSTOM:Couleur dominante', 'CUSTOM:Granulométrie', 'CUSTOM:Nature dominante', 'CUSTOM:Composition', 'CUSTOM:Magnétisme', 'description', 'acquisition_date', 'origin', 'contact', 'place', 'box_type', 'CUSTOM:Quantité (en Gr)', 'box_count', 'price', 'total_cost', 'CUSTOM:Stock échange', 'photo_data']

def apply_sands_template(manager, collection_id: int) -> None:
    """Modèle Sables = disposition compactée et enregistrée dans 03-sables test."""
    cid = int(collection_id)
    custom = {}
    for label, field_type, group, date_format in SANDS_CUSTOM_SPECS:
        info = manager.create_custom_field(
            cid, label, field_type, initial_group=group, date_format=date_format
        )
        custom[label] = info["field_key"]

    def real_key(key):
        key = str(key)
        return custom[key[7:]] if key.startswith("CUSTOM:") else key

    visible = {
        real_key(k) for k, row in SANDS_SAVED_ROWS.items()
        if int(row.get("visible") or 0) == 1
    }
    manager.set_visible_fields(cid, visible)

    labels, placement, positions, sizes = {}, {}, {}, {}
    for sk, row in SANDS_SAVED_ROWS.items():
        k = real_key(sk)
        if row.get("custom_label"):
            labels[k] = row["custom_label"]
        if row.get("block_name") is not None and row.get("position") is not None:
            placement[k] = (row["block_name"], int(row["position"]))
        if row.get("visual_x") is not None and row.get("visual_y") is not None:
            positions[k] = (int(row["visual_x"]), int(row["visual_y"]))
        if row.get("visual_w") is not None and row.get("visual_h") is not None:
            sizes[k] = (int(row["visual_w"]), int(row["visual_h"]))

    if labels: manager.set_custom_labels(cid, labels)
    if placement: manager.set_field_placement(cid, placement)
    if positions: manager.set_visual_positions(cid, positions)
    if sizes: manager.set_visual_sizes(cid, sizes)

    manager.set_field_styles(
        cid, {real_key(k): v for k, v in SANDS_SAVED_FIELD_STYLES.items()}
    )
    manager.set_group_styles(cid, dict(SANDS_SAVED_GROUP_STYLES))
    manager.set_sheet_background(cid, SANDS_SHEET_BACKGROUND)

    # Reprendre exactement l'ordre de tabulation enregistré dans l'Atelier.
    # "position" est locale à chaque cadre et ne doit jamais servir d'ordre global.
    manager.set_tab_order(cid, [real_key(k) for k in SANDS_SAVED_TAB_ORDER])

    try:
        import sqlite3
        from datetime import datetime
        with sqlite3.connect(str(manager.database_path)) as db:
            now = datetime.now().isoformat(timespec="seconds")
            for label, values in SANDS_REFERENTIAL_SEEDS.items():
                code = custom.get(label)
                row = db.execute(
                    "SELECT id FROM referential_definitions "
                    "WHERE collection_id=? AND code=?", (cid, code)
                ).fetchone() if code else None
                if not row:
                    continue
                for order, value in enumerate(values):
                    db.execute(
                        "INSERT OR IGNORE INTO referential_values("
                        "definition_id,value,sort_order,is_active,created_at,updated_at"
                        ") VALUES(?,?,?,?,?,?)",
                        (int(row[0]), value, order, 1, now, now),
                    )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Modèle type FOSSILES — socle volontairement simple et personnalisable.
# Il ne cherche pas à couvrir toute la paléontologie : il fournit seulement
# les rubriques de départ les plus courantes.
# ---------------------------------------------------------------------------

FOSSILS_CUSTOM_SPECS = [
    ("Nom / Taxon", "text", "Identification", "JJ/MM/AAAA"),
    ("Embranchement", "list", "Identification", "JJ/MM/AAAA"),
    ("Classe", "list", "Identification", "JJ/MM/AAAA"),
    ("Ordre", "list", "Identification", "JJ/MM/AAAA"),
    ("Famille", "list", "Identification", "JJ/MM/AAAA"),
    ("Genre", "list", "Identification", "JJ/MM/AAAA"),
    ("Espèce", "list", "Identification", "JJ/MM/AAAA"),
    ("Ère", "list", "Aspect", "JJ/MM/AAAA"),
    ("Période", "list", "Aspect", "JJ/MM/AAAA"),
    ("Époque / Série", "list", "Aspect", "JJ/MM/AAAA"),
    ("Étage", "list", "Aspect", "JJ/MM/AAAA"),
    ("Formation géologique", "list", "Localisation", "JJ/MM/AAAA"),
    ("Commune", "list", "Localisation", "JJ/MM/AAAA"),
    ("Préparation", "text", "Aspect", "JJ/MM/AAAA"),
    ("État de conservation", "list", "Aspect", "JJ/MM/AAAA"),
    ("Dimensions", "text", "Aspect", "JJ/MM/AAAA"),
]

FOSSILS_VISIBLE_STANDARD = {
    "record_number", "record_state", "site_name", "department", "region", "country",
    "description", "acquisition_date", "origin", "contact", "place",
    "box_type", "price", "photo_data",
}

FOSSILS_CUSTOM_LABELS = {
    "site_name": "Site",
    "description": "Description",
    "box_type": "Lieu de stockage",
    "price": "Prix",
}

FOSSILS_GROUP_STYLES = {
    "__mm3_layout__": {
        "model_kind": "fossils",
        "field_space": "sheet_absolute_v1",
    },
    "Bandeau": {
        "geometry": {"x": 0, "y": 0, "w": 983, "h": 135},
        "geometry_space": "atelier_px",
        "position": {"dx": 0, "dy": 0},
    },
    "Identification": {
        "title": {"text": "Taxonomie"},
        "geometry": {"x": 0, "y": 135, "w": 700, "h": 285},
        "geometry_space": "atelier_px",
        "position": {"dx": 0, "dy": 0},
    },
    "Photo": {
        "geometry": {"x": 700, "y": 135, "w": 283, "h": 285},
        "geometry_space": "atelier_px",
        "position": {"dx": 0, "dy": 0},
    },
    "Localisation": {
        "title": {"text": "Provenance"},
        "geometry": {"x": 0, "y": 420, "w": 983, "h": 205},
        "geometry_space": "atelier_px",
        "position": {"dx": 0, "dy": 0},
    },
    "Aspect": {
        "title": {"text": "Datation / Spécimen"},
        "geometry": {"x": 0, "y": 625, "w": 620, "h": 270},
        "geometry_space": "atelier_px",
        "position": {"dx": 0, "dy": 0},
    },
    "Acquisition": {
        "geometry": {"x": 620, "y": 625, "w": 363, "h": 270},
        "geometry_space": "atelier_px",
        "position": {"dx": 0, "dy": 0},
    },
    "Collection": {
        "geometry": {"x": 0, "y": 895, "w": 983, "h": 115},
        "geometry_space": "atelier_px",
        "position": {"dx": 0, "dy": 0},
    },
}

FOSSILS_SHEET_BACKGROUND = "#D0D0D0"

FOSSILS_POSITIONS = {
    "record_number": (28, 82),
    "record_state": (720, 82),

    "CUSTOM:Nom / Taxon": (20, 175),
    "CUSTOM:Embranchement": (20, 215),
    "CUSTOM:Classe": (355, 215),
    "CUSTOM:Ordre": (20, 255),
    "CUSTOM:Famille": (355, 255),
    "CUSTOM:Genre": (20, 295),
    "CUSTOM:Espèce": (355, 295),

    "site_name": (20, 460),
    "CUSTOM:Commune": (510, 460),
    "department": (20, 500),
    "region": (510, 500),
    "country": (20, 540),
    "CUSTOM:Formation géologique": (510, 540),

    "CUSTOM:Ère": (20, 665),
    "CUSTOM:Période": (315, 665),
    "CUSTOM:Époque / Série": (20, 705),
    "CUSTOM:Étage": (315, 705),
    "CUSTOM:Préparation": (20, 745),
    "CUSTOM:État de conservation": (315, 745),
    "CUSTOM:Dimensions": (20, 785),
    "description": (20, 825),

    "acquisition_date": (650, 665),
    "origin": (650, 705),
    "contact": (650, 745),
    "place": (650, 785),
    "price": (650, 825),

    "box_type": (28, 935),
}

FOSSILS_SIZES = {
    "record_number": (320, 36),
    "record_state": (235, 36),

    "CUSTOM:Nom / Taxon": (650, 36),
    "CUSTOM:Embranchement": (320, 36),
    "CUSTOM:Classe": (320, 36),
    "CUSTOM:Ordre": (320, 36),
    "CUSTOM:Famille": (320, 36),
    "CUSTOM:Genre": (320, 36),
    "CUSTOM:Espèce": (320, 36),

    "site_name": (455, 36),
    "CUSTOM:Commune": (445, 36),
    "department": (455, 36),
    "region": (445, 36),
    "country": (455, 36),
    "CUSTOM:Formation géologique": (445, 36),

    "CUSTOM:Ère": (275, 36),
    "CUSTOM:Période": (275, 36),
    "CUSTOM:Époque / Série": (275, 36),
    "CUSTOM:Étage": (275, 36),
    "CUSTOM:Préparation": (275, 36),
    "CUSTOM:État de conservation": (275, 36),
    "CUSTOM:Dimensions": (570, 36),
    "description": (570, 56),

    "acquisition_date": (300, 36),
    "origin": (300, 36),
    "contact": (300, 36),
    "place": (300, 36),
    "price": (300, 36),

    "box_type": (455, 36),
}

FOSSILS_TAB_ORDER = [
    "record_number", "record_state",
    "CUSTOM:Nom / Taxon", "CUSTOM:Embranchement", "CUSTOM:Classe",
    "CUSTOM:Ordre", "CUSTOM:Famille", "CUSTOM:Genre", "CUSTOM:Espèce",
    "site_name", "CUSTOM:Commune", "department", "region", "country",
    "CUSTOM:Formation géologique",
    "CUSTOM:Ère", "CUSTOM:Période", "CUSTOM:Époque / Série", "CUSTOM:Étage",
    "CUSTOM:Préparation", "CUSTOM:État de conservation", "CUSTOM:Dimensions",
    "description",
    "acquisition_date", "origin", "contact", "place", "price",
    "box_type", "photo_data",
]


def apply_fossils_template(manager, collection_id: int) -> None:
    """Crée le modèle type Fossiles, simple et entièrement personnalisable."""
    cid = int(collection_id)
    custom = {}
    for label, field_type, group, date_format in FOSSILS_CUSTOM_SPECS:
        info = manager.create_custom_field(
            cid, label, field_type, initial_group=group, date_format=date_format
        )
        custom[label] = info["field_key"]

    def real_key(key):
        key = str(key)
        return custom[key[7:]] if key.startswith("CUSTOM:") else key

    visible = set(FOSSILS_VISIBLE_STANDARD)
    visible.update(custom.values())
    manager.set_visible_fields(cid, visible)

    manager.set_custom_labels(cid, dict(FOSSILS_CUSTOM_LABELS))

    placement = {}
    for label, _field_type, group, _date_format in FOSSILS_CUSTOM_SPECS:
        placement[custom[label]] = (group, 0)
    manager.set_field_placement(cid, placement)

    manager.set_visual_positions(
        cid, {real_key(k): v for k, v in FOSSILS_POSITIONS.items()}
    )
    manager.set_visual_sizes(
        cid, {real_key(k): v for k, v in FOSSILS_SIZES.items()}
    )
    manager.set_tab_order(
        cid, [real_key(k) for k in FOSSILS_TAB_ORDER]
    )
    manager.set_sheet_background(cid, FOSSILS_SHEET_BACKGROUND)

    # Données noires par défaut. Les libellés restent au style MM3 standard.
    styles = {}
    for key in visible:
        styles[str(key)] = {"data": {"color": "#000000"}}
    manager.set_field_styles(cid, styles)
    manager.set_group_styles(cid, dict(FOSSILS_GROUP_STYLES))


# ---------------------------------------------------------------------------
# Modèle type TIMBRES
# ---------------------------------------------------------------------------
STAMPS_CUSTOM_SPECS = [
    ("Pays / Territoire", "list", "Identification", "JJ/MM/AAAA"),
    ("Émission", "text", "Identification", "JJ/MM/AAAA"),
    ("Valeur faciale", "text", "Identification", "JJ/MM/AAAA"),
    ("Devise", "list", "Identification", "JJ/MM/AAAA"),
    ("Année", "numeric", "Identification", "JJ/MM/AAAA"),
    ("Date d'émission", "date", "Identification", "JJ/MM/AAAA"),
    ("Série", "text", "Identification", "JJ/MM/AAAA"),
    ("N° dans la série", "numeric", "Identification", "JJ/MM/AAAA"),

    ("Sujet / Thème", "list", "Aspect", "JJ/MM/AAAA"),
    ("Couleur dominante", "list", "Aspect", "JJ/MM/AAAA"),
    ("Dentelure", "text", "Aspect", "JJ/MM/AAAA"),
    ("Filigrane", "text", "Aspect", "JJ/MM/AAAA"),
    ("Procédé d'impression", "list", "Aspect", "JJ/MM/AAAA"),
    ("Format", "text", "Aspect", "JJ/MM/AAAA"),

    ("Catalogue", "list", "Localisation", "JJ/MM/AAAA"),
    ("Référence catalogue", "text", "Localisation", "JJ/MM/AAAA"),
    ("Cote", "currency", "Localisation", "JJ/MM/AAAA"),
    ("Variété", "text", "Localisation", "JJ/MM/AAAA"),

    ("Neuf / Oblitéré", "list", "Collection", "JJ/MM/AAAA"),
    ("Qualité / État", "list", "Collection", "JJ/MM/AAAA"),
    ("Gomme", "list", "Collection", "JJ/MM/AAAA"),
    ("Centrage", "list", "Collection", "JJ/MM/AAAA"),
    ("Oblitération", "text", "Collection", "JJ/MM/AAAA"),
    ("Emplacement", "text", "Collection", "JJ/MM/AAAA"),
    ("Quantité", "numeric", "Collection", "JJ/MM/AAAA"),
]

STAMPS_VISIBLE_STANDARD = {
    "record_number", "record_state", "photo_data", "description",
    "acquisition_date", "origin", "contact", "price",
}

STAMPS_CUSTOM_LABELS = {
    "description": "Notes",
    "origin": "Provenance",
    "contact": "Contact",
    "price": "Prix d'achat",
}

STAMPS_GROUP_STYLES = {
    "__mm3_layout__": {"model_kind": "stamps", "field_space": "sheet_absolute_v1"},
    "Bandeau": {
        "geometry": {"x": 0, "y": 0, "w": 983, "h": 110},
        "geometry_space": "atelier_px", "position": {"dx": 0, "dy": 0},
    },
    "Identification": {
        "title": {"text": "Identification"},
        "geometry": {"x": 0, "y": 110, "w": 690, "h": 250},
        "geometry_space": "atelier_px", "position": {"dx": 0, "dy": 0},
    },
    "Photo": {
        "title": {"text": "Timbre — Recto"},
        "geometry": {"x": 690, "y": 110, "w": 293, "h": 250},
        "geometry_space": "atelier_px", "position": {"dx": 0, "dy": 0},
    },
    "Aspect": {
        "title": {"text": "Description"},
        "geometry": {"x": 0, "y": 360, "w": 550, "h": 250},
        "geometry_space": "atelier_px", "position": {"dx": 0, "dy": 0},
    },
    "Localisation": {
        "title": {"text": "Catalogue"},
        "geometry": {"x": 550, "y": 360, "w": 433, "h": 250},
        "geometry_space": "atelier_px", "position": {"dx": 0, "dy": 0},
    },
    "Acquisition": {
        "title": {"text": "Acquisition"},
        "geometry": {"x": 0, "y": 610, "w": 430, "h": 220},
        "geometry_space": "atelier_px", "position": {"dx": 0, "dy": 0},
    },
    "Collection": {
        "title": {"text": "Collection / État"},
        "geometry": {"x": 430, "y": 610, "w": 553, "h": 300},
        "geometry_space": "atelier_px", "position": {"dx": 0, "dy": 0},
    },
}

STAMPS_SHEET_BACKGROUND = "#D8E0E1"

STAMPS_POSITIONS = {
    "record_number": (25, 60), "record_state": (720, 60),
    "CUSTOM:Pays / Territoire": (20, 145), "CUSTOM:Émission": (350, 145),
    "CUSTOM:Valeur faciale": (20, 185), "CUSTOM:Devise": (350, 185),
    "CUSTOM:Année": (20, 225), "CUSTOM:Date d'émission": (350, 225),
    "CUSTOM:Série": (20, 265), "CUSTOM:N° dans la série": (350, 265),

    "CUSTOM:Sujet / Thème": (20, 400), "CUSTOM:Couleur dominante": (285, 400),
    "CUSTOM:Dentelure": (20, 440), "CUSTOM:Filigrane": (285, 440),
    "CUSTOM:Procédé d'impression": (20, 480), "CUSTOM:Format": (285, 480),
    "description": (20, 525),

    "CUSTOM:Catalogue": (570, 400), "CUSTOM:Référence catalogue": (570, 440),
    "CUSTOM:Cote": (570, 480), "CUSTOM:Variété": (570, 520),

    "acquisition_date": (20, 650), "origin": (20, 690),
    "contact": (20, 730), "price": (20, 770),

    "CUSTOM:Neuf / Oblitéré": (450, 650), "CUSTOM:Qualité / État": (720, 650),
    "CUSTOM:Gomme": (450, 690), "CUSTOM:Centrage": (720, 690),
    "CUSTOM:Oblitération": (450, 730), "CUSTOM:Emplacement": (450, 770),
    "CUSTOM:Quantité": (720, 770),
}

STAMPS_SIZES = {
    "record_number": (300, 36), "record_state": (235, 36),
    "CUSTOM:Pays / Territoire": (310, 36), "CUSTOM:Émission": (310, 36),
    "CUSTOM:Valeur faciale": (310, 36), "CUSTOM:Devise": (310, 36),
    "CUSTOM:Année": (310, 36), "CUSTOM:Date d'émission": (310, 36),
    "CUSTOM:Série": (310, 36), "CUSTOM:N° dans la série": (310, 36),

    "CUSTOM:Sujet / Thème": (245, 36), "CUSTOM:Couleur dominante": (245, 36),
    "CUSTOM:Dentelure": (245, 36), "CUSTOM:Filigrane": (245, 36),
    "CUSTOM:Procédé d'impression": (245, 36), "CUSTOM:Format": (245, 36),
    "description": (510, 56),

    "CUSTOM:Catalogue": (390, 36), "CUSTOM:Référence catalogue": (390, 36),
    "CUSTOM:Cote": (390, 36), "CUSTOM:Variété": (390, 36),

    "acquisition_date": (390, 36), "origin": (390, 36),
    "contact": (390, 36), "price": (390, 36),

    "CUSTOM:Neuf / Oblitéré": (250, 36), "CUSTOM:Qualité / État": (240, 36),
    "CUSTOM:Gomme": (250, 36), "CUSTOM:Centrage": (240, 36),
    "CUSTOM:Oblitération": (510, 36), "CUSTOM:Emplacement": (250, 36),
    "CUSTOM:Quantité": (240, 36),
}

STAMPS_TAB_ORDER = [
    "record_number", "record_state",
    "CUSTOM:Pays / Territoire", "CUSTOM:Émission", "CUSTOM:Valeur faciale",
    "CUSTOM:Devise", "CUSTOM:Année", "CUSTOM:Date d'émission",
    "CUSTOM:Série", "CUSTOM:N° dans la série",
    "CUSTOM:Sujet / Thème", "CUSTOM:Couleur dominante", "CUSTOM:Dentelure",
    "CUSTOM:Filigrane", "CUSTOM:Procédé d'impression", "CUSTOM:Format",
    "description", "CUSTOM:Catalogue", "CUSTOM:Référence catalogue",
    "CUSTOM:Cote", "CUSTOM:Variété",
    "acquisition_date", "origin", "contact", "price",
    "CUSTOM:Neuf / Oblitéré", "CUSTOM:Qualité / État", "CUSTOM:Gomme",
    "CUSTOM:Centrage", "CUSTOM:Oblitération", "CUSTOM:Emplacement",
    "CUSTOM:Quantité", "photo_data",
]


def apply_stamps_template(manager, collection_id: int) -> None:
    """Crée le modèle type Timbres, volontairement simple et personnalisable."""
    cid = int(collection_id)
    custom = {}
    for label, field_type, group, date_format in STAMPS_CUSTOM_SPECS:
        info = manager.create_custom_field(
            cid, label, field_type, initial_group=group, date_format=date_format
        )
        custom[label] = info["field_key"]

    def real_key(key):
        key = str(key)
        return custom[key[7:]] if key.startswith("CUSTOM:") else key

    visible = set(STAMPS_VISIBLE_STANDARD)
    visible.update(custom.values())
    manager.set_visible_fields(cid, visible)
    manager.set_custom_labels(cid, dict(STAMPS_CUSTOM_LABELS))

    placement = {
        custom[label]: (group, 0)
        for label, _field_type, group, _date_format in STAMPS_CUSTOM_SPECS
    }
    manager.set_field_placement(cid, placement)
    manager.set_visual_positions(cid, {real_key(k): v for k, v in STAMPS_POSITIONS.items()})
    manager.set_visual_sizes(cid, {real_key(k): v for k, v in STAMPS_SIZES.items()})
    manager.set_tab_order(cid, [real_key(k) for k in STAMPS_TAB_ORDER])
    manager.set_sheet_background(cid, STAMPS_SHEET_BACKGROUND)

    styles = {str(key): {"data": {"color": "#000000"}} for key in visible}
    manager.set_field_styles(cid, styles)
    manager.set_group_styles(cid, dict(STAMPS_GROUP_STYLES))


# ---------------------------------------------------------------------------
# Modèle type CARTES POSTALES
# ---------------------------------------------------------------------------
POSTCARDS_CUSTOM_SPECS = [('Pays', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Région / Département', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Commune', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Lieu / Site représenté', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Titre / Légende', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Type de carte', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Époque / Année estimée', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Éditeur', 'list', 'Localisation', 'JJ/MM/AAAA'),
 ('Imprimeur', 'list', 'Localisation', 'JJ/MM/AAAA'),
 ('Photographe / Illustrateur', 'text', 'Localisation', 'JJ/MM/AAAA'),
 ('Série', 'text', 'Localisation', 'JJ/MM/AAAA'),
 ('N° de série / Référence', 'text', 'Localisation', 'JJ/MM/AAAA'),
 ('Sujet / Thème', 'list', 'Aspect', 'JJ/MM/AAAA'),
 ('Technique', 'list', 'Aspect', 'JJ/MM/AAAA'),
 ('Couleur / Noir et blanc', 'list', 'Aspect', 'JJ/MM/AAAA'),
 ('Format', 'text', 'Aspect', 'JJ/MM/AAAA'),
 ('Particularités', 'text', 'Aspect', 'JJ/MM/AAAA'),
 ('Circulée / Non circulée', 'list', 'Identification', 'JJ/MM/AAAA'),
 ("Date d'envoi", 'date', 'Identification', 'JJ/MM/AAAA'),
 ("Lieu d'envoi", 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Destination', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Cachet postal', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Timbre présent', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Texte manuscrit', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Qualité / État', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Coins', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Plis', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Taches', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('État du dos', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Restauration', 'text', 'Collection', 'JJ/MM/AAAA'),
 ('Emplacement', 'text', 'Collection', 'JJ/MM/AAAA'),
 ('Quantité', 'numeric', 'Collection', 'JJ/MM/AAAA'),
 ('Notes', 'text', 'Collection', 'JJ/MM/AAAA'),
 ("Date d'acquisition", 'date', 'Acquisition', 'JJ/MM/AAAA'),
 ('Provenance', 'text', 'Acquisition', 'JJ/MM/AAAA'),
 ('Contact', 'text', 'Acquisition', 'JJ/MM/AAAA'),
 ("Prix d'achat", 'currency', 'Acquisition', 'JJ/MM/AAAA')]

POSTCARDS_VISIBLE_STANDARD = {
    "record_number", "record_state", "photo_data", "description",
    "acquisition_date", "origin", "contact", "price",
}
POSTCARDS_CUSTOM_LABELS = {
    "description": "Notes", "origin": "Provenance", "contact": "Contact",
    "price": "Prix d'achat",
}
POSTCARDS_SHEET_BACKGROUND = '#e7dfcf'

POSTCARDS_GROUP_STYLES = {'__mm3_layout__': {'model_kind': 'postcards', 'field_space': 'sheet_absolute_v1'},
 'Bandeau': {'geometry': {'x': 0, 'y': 0, 'w': 984, 'h': 76}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': 0}},
 'Identification': {'title': {'text': 'Identification'},
                    'geometry': {'x': 0, 'y': 100, 'w': 690, 'h': 178},
                    'geometry_space': 'atelier_px',
                    'position': {'dx': 0, 'dy': -25},
                    'border_width': 2,
                    'border': '#b5afa3'},
 'Photo': {'title': {'text': 'Carte postale — Recto'},
           'geometry': {'x': 738, 'y': 100, 'w': 249, 'h': 198},
           'geometry_space': 'atelier_px',
           'position': {'dx': 118, 'dy': -25}},
 'photo_slot_2': {'custom_group': True,
                  'custom_photo': True,
                  'frame_deleted': False,
                  'title': {'text': 'Carte postale — Verso'},
                  'geometry': {'x': 738, 'y': 305, 'w': 249, 'h': 198},
                  'geometry_space': 'atelier_px',
                  'position': {'dx': 38, 'dy': -50}},
 'Localisation': {'title': {'text': 'Édition'},
                  'geometry': {'x': 0, 'y': 305, 'w': 352, 'h': 213},
                  'geometry_space': 'atelier_px',
                  'position': {'dx': 0, 'dy': -22},
                  'border': '#bdb7aa',
                  'border_width': 2,
                  'background': '#faf2e1'},
 'Aspect': {'title': {'text': 'Description'},
            'geometry': {'x': 357, 'y': 305, 'w': 333, 'h': 213},
            'geometry_space': 'atelier_px',
            'position': {'dx': 357, 'dy': -224},
            'border': '#b5afa3',
            'border_width': 2,
            'background': '#faf2e1'},
 'Circulation': {'custom_group': True,
                 'title': {'text': 'Circulation'},
                 'geometry': {'x': 0, 'y': 520, 'w': 526, 'h': 226},
                 'geometry_space': 'atelier_px',
                 'position': {'dx': 0, 'dy': -70},
                 'background': '#b5afa3'},
 'Collection': {'title': {'text': 'État / Collection'},
                'geometry': {'x': 528, 'y': 520, 'w': 459, 'h': 226},
                'geometry_space': 'atelier_px',
                'position': {'dx': 528, 'dy': -245},
                'background': '#b5afa3'},
 'Acquisition': {'title': {'text': 'Acquisition'},
                 'geometry': {'x': 0, 'y': 751, 'w': 986, 'h': 87},
                 'geometry_space': 'atelier_px',
                 'position': {'dx': -620, 'dy': 226},
                 'border': '#b5afa3'}}
POSTCARDS_POSITIONS = {'record_number': (25, 49),
 'record_state': (719, 49),
 'CUSTOM:Pays': (67, 197),
 'CUSTOM:Région / Département': (0, 238),
 'CUSTOM:Commune': (67, 279),
 'CUSTOM:Lieu / Site représenté': (4, 319),
 'CUSTOM:Type de carte': (554, 197),
 'CUSTOM:Titre / Légende': (546, 238),
 'CUSTOM:Époque / Année estimée': (472, 279),
 'CUSTOM:Éditeur': (100, 500),
 'CUSTOM:Imprimeur': (100, 540),
 'CUSTOM:Photographe / Illustrateur': (10, 581),
 'CUSTOM:Série': (100, 619),
 'CUSTOM:N° de série / Référence': (22, 660),
 'CUSTOM:Sujet / Thème': (565, 503),
 'CUSTOM:Technique': (565, 543),
 'CUSTOM:Couleur / Noir et blanc': (497, 583),
 'CUSTOM:Format': (565, 622),
 'CUSTOM:Particularités': (565, 662),
 'CUSTOM:Circulée / Non circulée': (11, 782),
 "CUSTOM:Date d'envoi": (415, 782),
 "CUSTOM:Lieu d'envoi": (83, 822),
 'CUSTOM:Destination': (415, 822),
 'CUSTOM:Cachet postal': (83, 862),
 'CUSTOM:Timbre présent': (403, 862),
 'CUSTOM:Texte manuscrit': (47, 962),
 'CUSTOM:Qualité / État': (729, 776),
 'CUSTOM:Coins': (1058, 776),
 'CUSTOM:Plis': (729, 817),
 'CUSTOM:Taches': (1058, 817),
 'CUSTOM:État du dos': (729, 857),
 'CUSTOM:Restauration': (1058, 857),
 'CUSTOM:Emplacement': (729, 897),
 'CUSTOM:Quantité': (1058, 897),
 'description': (729, 962),
 'acquisition_date': (53, 1101),
 'origin': (354, 1101),
 'contact': (696, 1101),
 'price': (1031, 1101),
 'photo_data': (0, 0)}
POSTCARDS_SIZES = {'record_number': (300, 36),
 'record_state': (235, 36),
 'CUSTOM:Pays': (392, 36),
 'CUSTOM:Région / Département': (458, 36),
 'CUSTOM:Commune': (392, 36),
 'CUSTOM:Lieu / Site représenté': (454, 36),
 'CUSTOM:Type de carte': (394, 36),
 'CUSTOM:Titre / Légende': (403, 36),
 'CUSTOM:Époque / Année estimée': (476, 36),
 'CUSTOM:Éditeur': (376, 36),
 'CUSTOM:Imprimeur': (376, 36),
 'CUSTOM:Photographe / Illustrateur': (467, 36),
 'CUSTOM:Série': (376, 36),
 'CUSTOM:N° de série / Référence': (454, 36),
 'CUSTOM:Sujet / Thème': (376, 36),
 'CUSTOM:Technique': (376, 36),
 'CUSTOM:Couleur / Noir et blanc': (444, 36),
 'CUSTOM:Format': (376, 36),
 'CUSTOM:Particularités': (376, 36),
 'CUSTOM:Circulée / Non circulée': (372, 36),
 "CUSTOM:Date d'envoi": (300, 36),
 "CUSTOM:Lieu d'envoi": (300, 36),
 'CUSTOM:Destination': (300, 36),
 'CUSTOM:Cachet postal': (300, 36),
 'CUSTOM:Timbre présent': (312, 36),
 'CUSTOM:Texte manuscrit': (481, 56),
 'CUSTOM:Qualité / État': (300, 36),
 'CUSTOM:Coins': (300, 36),
 'CUSTOM:Plis': (300, 36),
 'CUSTOM:Taches': (300, 36),
 'CUSTOM:État du dos': (300, 36),
 'CUSTOM:Restauration': (300, 36),
 'CUSTOM:Emplacement': (300, 36),
 'CUSTOM:Quantité': (300, 36),
 'description': (450, 56),
 'acquisition_date': (247, 36),
 'origin': (290, 36),
 'contact': (281, 36),
 'price': (300, 36),
 'photo_data': (300, 170)}
POSTCARDS_TAB_ORDER = ['record_number',
 'record_state',
 'CUSTOM:Pays',
 'CUSTOM:Région / Département',
 'CUSTOM:Commune',
 'CUSTOM:Lieu / Site représenté',
 'CUSTOM:Type de carte',
 'CUSTOM:Titre / Légende',
 'CUSTOM:Époque / Année estimée',
 'CUSTOM:Éditeur',
 'CUSTOM:Imprimeur',
 'CUSTOM:Photographe / Illustrateur',
 'CUSTOM:Série',
 'CUSTOM:N° de série / Référence',
 'CUSTOM:Sujet / Thème',
 'CUSTOM:Technique',
 'CUSTOM:Couleur / Noir et blanc',
 'CUSTOM:Format',
 'CUSTOM:Particularités',
 'CUSTOM:Circulée / Non circulée',
 "CUSTOM:Date d'envoi",
 "CUSTOM:Lieu d'envoi",
 'CUSTOM:Destination',
 'CUSTOM:Cachet postal',
 'CUSTOM:Timbre présent',
 'CUSTOM:Texte manuscrit',
 'CUSTOM:Qualité / État',
 'CUSTOM:Coins',
 'CUSTOM:Plis',
 'CUSTOM:Taches',
 'CUSTOM:État du dos',
 'CUSTOM:Restauration',
 'CUSTOM:Emplacement',
 'CUSTOM:Quantité',
 'CUSTOM:Notes',
 "CUSTOM:Date d'acquisition",
 'CUSTOM:Provenance',
 'CUSTOM:Contact',
 "CUSTOM:Prix d'achat",
 'photo_data']
POSTCARDS_FIELD_STYLES = {'CUSTOM:Pays': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 115, 'width': 276}},
 "CUSTOM:Lieu d'envoi": {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 182}},
 'contact': {'label': {'x': 0, 'width': 99, 'align': 'right'}, 'data': {'color': '#000000', 'x': 99, 'width': 182}},
 'CUSTOM:Lieu / Site représenté': {'label': {'x': 0, 'width': 178, 'align': 'right'}, 'data': {'color': '#000000', 'x': 178, 'width': 276}},
 'CUSTOM:Commune': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 115, 'width': 276}},
 'CUSTOM:Titre / Légende': {'label': {'x': 0, 'width': 129, 'align': 'right'}, 'data': {'color': '#000000', 'x': 126, 'width': 276}},
 'CUSTOM:Qualité / État': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 182}},
 'CUSTOM:Format': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 258}},
 'CUSTOM:Type de carte': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 276}},
 'CUSTOM:Couleur / Noir et blanc': {'label': {'x': 0, 'width': 186, 'align': 'right'}, 'data': {'color': '#000000', 'x': 186, 'width': 258}},
 'description': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 332}},
 'price': {'label': {'align': 'right'}, 'data': {'color': '#000000'}},
 'CUSTOM:Cachet postal': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 182}},
 'CUSTOM:Restauration': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 182}},
 'CUSTOM:Emplacement': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 182}},
 'CUSTOM:Circulée / Non circulée': {'label': {'x': 0, 'width': 190, 'align': 'right'}, 'data': {'color': '#000000', 'x': 190, 'width': 182}},
 'acquisition_date': {'label': {'x': 0, 'width': 65, 'align': 'right'}, 'data': {'color': '#000000', 'x': 65, 'width': 182}},
 'record_state': {'label': {'color': '#aa0000'},
                  'data': {'color': '#aa0000', 'family': 'Segoe UI', 'size': 9, 'bold': True, 'italic': False, 'underline': False, 'align': 'left'}},
 'CUSTOM:Coins': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 182}},
 'CUSTOM:Particularités': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 258}},
 'CUSTOM:Taches': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 182}},
 'origin': {'label': {'x': 0, 'width': 108, 'align': 'right'}, 'data': {'color': '#000000', 'x': 108, 'width': 182}},
 'CUSTOM:Destination': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 182}},
 'CUSTOM:Imprimeur': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 258}},
 'CUSTOM:Époque / Année estimée': {'label': {'x': 0, 'width': 203, 'align': 'right'}, 'data': {'color': '#000000', 'x': 200, 'width': 276}},
 'CUSTOM:Quantité': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 182}},
 'CUSTOM:Technique': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 258}},
 'CUSTOM:Région / Département': {'label': {'x': 0, 'width': 182, 'align': 'right'}, 'data': {'color': '#000000', 'x': 182, 'width': 276}},
 'CUSTOM:Éditeur': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 258}},
 'record_number': {'label': {'color': '#aa0000'}, 'data': {'color': '#aa0000'}},
 'CUSTOM:Série': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 258}},
 'CUSTOM:Sujet / Thème': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 258}},
 'CUSTOM:Timbre présent': {'label': {'x': 0, 'width': 131, 'align': 'right'}, 'data': {'color': '#000000', 'x': 131, 'width': 182}},
 "CUSTOM:Date d'envoi": {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 182}},
 'CUSTOM:Plis': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 182}},
 'CUSTOM:N° de série / Référence': {'label': {'x': 0, 'width': 196, 'align': 'right'}, 'data': {'color': '#000000', 'x': 196, 'width': 258}},
 'CUSTOM:État du dos': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 182}},
 'CUSTOM:Photographe / Illustrateur': {'label': {'x': 0, 'width': 208, 'align': 'right'}, 'data': {'color': '#000000', 'x': 208, 'width': 258}},
 'CUSTOM:Texte manuscrit': {'label': {'x': 0, 'width': 139, 'align': 'right'}, 'data': {'color': '#000000', 'x': 139, 'width': 342}},
 'photo_data': {'data': {'color': '#000000'}}}

def apply_postcards_template(manager, collection_id: int) -> None:
    cid = int(collection_id)
    custom = {}
    for label, field_type, group, date_format in POSTCARDS_CUSTOM_SPECS:
        info = manager.create_custom_field(cid, label, field_type, initial_group=group, date_format=date_format)
        custom[label] = info["field_key"]
    def real_key(key):
        key = str(key)
        return custom[key[7:]] if key.startswith("CUSTOM:") else key
    visible = set(POSTCARDS_VISIBLE_STANDARD); visible.update(custom.values())
    manager.set_visible_fields(cid, visible)
    manager.set_custom_labels(cid, dict(POSTCARDS_CUSTOM_LABELS))
    placement = {custom[label]: (group, 0) for label, _t, group, _d in POSTCARDS_CUSTOM_SPECS}
    manager.set_field_placement(cid, placement)
    manager.set_visual_positions(cid, {real_key(k): v for k, v in POSTCARDS_POSITIONS.items()})
    manager.set_visual_sizes(cid, {real_key(k): v for k, v in POSTCARDS_SIZES.items()})
    manager.set_tab_order(cid, [real_key(k) for k in POSTCARDS_TAB_ORDER])
    manager.set_sheet_background(cid, POSTCARDS_SHEET_BACKGROUND)
    from core.field_catalog import FIELDS
    out_styles = {}
    for spec in FIELDS:
        key = str(spec.key)
        if key not in visible and key not in {"record_number", "record_state", "photo_data"}:
            out_styles[key] = {"field_deleted": True}
    for k, style in POSTCARDS_FIELD_STYLES.items():
        out_styles[real_key(k)] = dict(style)
    for key in visible:
        st = dict(out_styles.get(str(key), {}))
        data = dict(st.get("data", {})); data["color"] = "#000000"; st["data"] = data
        out_styles[str(key)] = st
    manager.set_field_styles(cid, out_styles)
    manager.set_group_styles(cid, dict(POSTCARDS_GROUP_STYLES))


# --- Modèle type Monnaies / Médailles / Jetons ---
COINS_CUSTOM_SPECS = [('Nature', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Pays / Territoire', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Autorité / Émetteur', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Dénomination / Type', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Valeur faciale', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Devise', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Année / Date', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Atelier de frappe', 'list', 'Identification', 'JJ/MM/AAAA'),
 ("Marque d'atelier", 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Métal / Alliage', 'list', 'Aspect', 'JJ/MM/AAAA'),
 ('Poids', 'numeric', 'Aspect', 'JJ/MM/AAAA'),
 ('Diamètre', 'numeric', 'Aspect', 'JJ/MM/AAAA'),
 ('Épaisseur', 'numeric', 'Aspect', 'JJ/MM/AAAA'),
 ('Forme', 'list', 'Aspect', 'JJ/MM/AAAA'),
 ('Tranche', 'text', 'Aspect', 'JJ/MM/AAAA'),
 ('Axe', 'text', 'Aspect', 'JJ/MM/AAAA'),
 ('Légende avers', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Légende revers', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Sujet / Motif', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Catalogue', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Référence catalogue', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Tirage', 'numeric', 'Identification', 'JJ/MM/AAAA'),
 ('Rareté', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('État / Grade', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Patine', 'text', 'Collection', 'JJ/MM/AAAA'),
 ('Défauts', 'text', 'Collection', 'JJ/MM/AAAA'),
 ('Nettoyé / Restauré', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Authenticité', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Emplacement', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Quantité', 'numeric', 'Collection', 'JJ/MM/AAAA'),
 ('Notes', 'text', 'Collection', 'JJ/MM/AAAA'),
 ("Date d'acquisition", 'date', 'Acquisition', 'JJ/MM/AAAA'),
 ('Provenance', 'text', 'Acquisition', 'JJ/MM/AAAA'),
 ('Contact', 'text', 'Acquisition', 'JJ/MM/AAAA'),
 ("Prix d'achat", 'currency', 'Acquisition', 'JJ/MM/AAAA')]
COINS_VISIBLE_STANDARD = {'record_state', 'origin', 'record_number', 'contact', 'acquisition_date', 'description', 'price', 'photo_data'}
COINS_CUSTOM_LABELS = {"description": "Notes", "origin": "Provenance", "price": "Prix d'achat"}
COINS_SHEET_BACKGROUND = '#d9d9d4'
COINS_GROUP_STYLES = {'__mm3_layout__': {'model_kind': 'coins', 'field_space': 'sheet_absolute_v1'},
 'Bandeau': {'geometry': {'x': 0, 'y': 0, 'w': 1000, 'h': 90}, 'geometry_space': 'atelier_px', 'position': {'dx': 0, 'dy': 0}},
 'Identification': {'title': {'text': 'Identification'},
                    'geometry': {'x': 0, 'y': 100, 'w': 700, 'h': 245},
                    'geometry_space': 'atelier_px',
                    'position': {'dx': 0, 'dy': 0},
                    'border': '#888885',
                    'border_width': 2,
                    'background': '#f3f3ed'},
 'Photo': {'title': {'text': 'Avers'},
           'geometry': {'x': 715, 'y': 100, 'w': 270, 'h': 225},
           'geometry_space': 'atelier_px',
           'position': {'dx': 0, 'dy': 0}},
 'photo_slot_2': {'custom_group': True,
                  'custom_photo': True,
                  'frame_deleted': False,
                  'title': {'text': 'Revers'},
                  'geometry': {'x': 715, 'y': 335, 'w': 270, 'h': 225},
                  'geometry_space': 'atelier_px',
                  'position': {'dx': 0, 'dy': 0}},
 'Aspect': {'title': {'text': 'Caractéristiques'},
            'geometry': {'x': 0, 'y': 352, 'w': 310, 'h': 253},
            'geometry_space': 'atelier_px',
            'position': {'dx': 0, 'dy': 25},
            'border_width': 2,
            'border': '#888885',
            'background': '#cbcbc6'},
 'Description monnaie': {'custom_group': True,
                         'title': {'text': 'Description'},
                         'geometry': {'x': 320, 'y': 352, 'w': 380, 'h': 253},
                         'geometry_space': 'atelier_px',
                         'position': {'dx': 0, 'dy': -3},
                         'border_width': 2,
                         'border': '#888885',
                         'background': '#cbcbc6'},
 'Référence': {'custom_group': True,
               'title': {'text': 'Référence'},
               'geometry': {'x': 0, 'y': 612, 'w': 490, 'h': 231},
               'geometry_space': 'atelier_px',
               'position': {'dx': 0, 'dy': -52},
               'border_width': 2,
               'border': '#888885'},
 'Collection': {'title': {'text': 'État / Collection'},
                'geometry': {'x': 505, 'y': 613, 'w': 490, 'h': 231},
                'geometry_space': 'atelier_px',
                'position': {'dx': 505, 'dy': -156},
                'border_width': 2,
                'border': '#888885'},
 'Acquisition': {'title': {'text': 'Acquisition'},
                 'geometry': {'x': 0, 'y': 848, 'w': 995, 'h': 84},
                 'geometry_space': 'atelier_px',
                 'position': {'dx': -618, 'dy': 521},
                 'border_width': 2,
                 'border': '#888885'},
 'Localisation': {'geometry': {'x': 0, 'y': 618, 'w': 997, 'h': 46},
                  'geometry_space': 'atelier_px',
                  'position': {'dx': 0, 'dy': 291},
                  'frame_deleted': True}}
COINS_POSITIONS = {'record_number': (25, 49),
 'record_state': (700, 49),
 'CUSTOM:Nature': (64, 208),
 'CUSTOM:Autorité / Émetteur': (17, 249),
 'CUSTOM:Valeur faciale': (64, 289),
 'CUSTOM:Année / Date': (64, 329),
 "CUSTOM:Marque d'atelier": (39, 368),
 'CUSTOM:Pays / Territoire': (533, 208),
 'CUSTOM:Dénomination / Type': (489, 249),
 'CUSTOM:Devise': (546, 289),
 'CUSTOM:Atelier de frappe': (524, 329),
 'CUSTOM:Métal / Alliage': (18, 539),
 'CUSTOM:Poids': (36, 581),
 'CUSTOM:Diamètre': (36, 621),
 'CUSTOM:Épaisseur': (36, 661),
 'CUSTOM:Forme': (36, 701),
 'CUSTOM:Tranche': (36, 740),
 'CUSTOM:Axe': (36, 781),
 'CUSTOM:Légende avers': (500, 539),
 'CUSTOM:Légende revers': (507, 581),
 'CUSTOM:Sujet / Motif': (510, 621),
 'CUSTOM:Catalogue': (528, 661),
 'CUSTOM:Référence catalogue': (460, 701),
 'CUSTOM:Tirage': (539, 740),
 'CUSTOM:Rareté': (131, 910),
 'CUSTOM:État / Grade': (117, 949),
 'CUSTOM:Patine': (131, 990),
 'CUSTOM:Défauts': (131, 1031),
 'description': (131, 1092),
 'CUSTOM:Nettoyé / Restauré': (776, 910),
 'CUSTOM:Authenticité': (817, 949),
 'CUSTOM:Emplacement': (817, 990),
 'CUSTOM:Quantité': (817, 1031),
 'acquisition_date': (51, 1232),
 'origin': (329, 1232),
 'contact': (668, 1232),
 'price': (1040, 1232),
 'photo_data': (0, 0)}
COINS_SIZES = {'record_number': (300, 36),
 'record_state': (257, 36),
 'CUSTOM:Nature': (379, 36),
 'CUSTOM:Autorité / Émetteur': (426, 36),
 'CUSTOM:Valeur faciale': (379, 36),
 'CUSTOM:Année / Date': (379, 36),
 "CUSTOM:Marque d'atelier": (404, 36),
 'CUSTOM:Pays / Territoire': (399, 36),
 'CUSTOM:Dénomination / Type': (443, 36),
 'CUSTOM:Devise': (386, 36),
 'CUSTOM:Atelier de frappe': (408, 36),
 'CUSTOM:Métal / Alliage': (383, 36),
 'CUSTOM:Poids': (365, 36),
 'CUSTOM:Diamètre': (365, 36),
 'CUSTOM:Épaisseur': (365, 36),
 'CUSTOM:Forme': (365, 36),
 'CUSTOM:Tranche': (365, 36),
 'CUSTOM:Axe': (365, 36),
 'CUSTOM:Légende avers': (425, 35),
 'CUSTOM:Légende revers': (418, 36),
 'CUSTOM:Sujet / Motif': (415, 36),
 'CUSTOM:Catalogue': (397, 36),
 'CUSTOM:Référence catalogue': (465, 36),
 'CUSTOM:Tirage': (386, 36),
 'CUSTOM:Rareté': (424, 36),
 'CUSTOM:État / Grade': (438, 36),
 'CUSTOM:Patine': (424, 36),
 'CUSTOM:Défauts': (424, 36),
 'description': (424, 56),
 'CUSTOM:Nettoyé / Restauré': (512, 36),
 'CUSTOM:Authenticité': (472, 36),
 'CUSTOM:Emplacement': (472, 36),
 'CUSTOM:Quantité': (472, 36),
 'acquisition_date': (232, 36),
 'origin': (290, 36),
 'contact': (368, 36),
 'price': (300, 36),
 'photo_data': (300, 170)}
COINS_TAB_ORDER = ['record_number',
 'record_state',
 'CUSTOM:Nature',
 'CUSTOM:Autorité / Émetteur',
 'CUSTOM:Valeur faciale',
 'CUSTOM:Année / Date',
 "CUSTOM:Marque d'atelier",
 'CUSTOM:Pays / Territoire',
 'CUSTOM:Dénomination / Type',
 'CUSTOM:Devise',
 'CUSTOM:Atelier de frappe',
 'CUSTOM:Métal / Alliage',
 'CUSTOM:Poids',
 'CUSTOM:Diamètre',
 'CUSTOM:Épaisseur',
 'CUSTOM:Forme',
 'CUSTOM:Tranche',
 'CUSTOM:Axe',
 'CUSTOM:Légende avers',
 'CUSTOM:Légende revers',
 'CUSTOM:Sujet / Motif',
 'CUSTOM:Catalogue',
 'CUSTOM:Référence catalogue',
 'CUSTOM:Tirage',
 'CUSTOM:Rareté',
 'CUSTOM:État / Grade',
 'CUSTOM:Patine',
 'CUSTOM:Défauts',
 'description',
 'CUSTOM:Nettoyé / Restauré',
 'CUSTOM:Authenticité',
 'CUSTOM:Emplacement',
 'CUSTOM:Quantité',
 'acquisition_date',
 'origin',
 'contact',
 'price',
 'photo_data']
COINS_FIELD_STYLES = {'price': {'label': {'align': 'right'}, 'data': {'color': '#000000'}},
 'CUSTOM:Rareté': {'label': {'x': 0, 'width': 97, 'align': 'right'}, 'data': {'color': '#000000', 'x': 92, 'width': 332}},
 'photo_data': {'data': {'color': '#000000'}},
 'CUSTOM:Nature': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 261}},
 'CUSTOM:Pays / Territoire': {'label': {'x': 0, 'width': 131, 'align': 'right'}, 'data': {'color': '#000000', 'x': 131, 'width': 268}},
 'CUSTOM:Valeur faciale': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 261}},
 'CUSTOM:Devise': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 268}},
 'CUSTOM:État / Grade': {'label': {'x': 0, 'width': 110, 'align': 'right'}, 'data': {'color': '#000000', 'x': 106, 'width': 332}},
 'acquisition_date': {'label': {'align': 'right', 'x': 0, 'width': 68}, 'data': {'color': '#000000', 'x': 68, 'width': 164}},
 'CUSTOM:Catalogue': {'label': {'x': 0, 'width': 104, 'align': 'right'}, 'data': {'color': '#000000', 'x': 97, 'width': 300}},
 'CUSTOM:Référence catalogue': {'label': {'x': 0, 'width': 172, 'align': 'right'}, 'data': {'color': '#000000', 'x': 165, 'width': 300}},
 'description': {'label': {'x': 0, 'width': 93, 'align': 'right'}, 'data': {'color': '#000000', 'x': 92, 'width': 332}},
 'CUSTOM:Sujet / Motif': {'label': {'x': 0, 'width': 122, 'align': 'right'}, 'data': {'color': '#000000', 'x': 115, 'width': 300}},
 'CUSTOM:Légende avers': {'label': {'x': 0, 'width': 132, 'align': 'right'}, 'data': {'color': '#000000', 'x': 125, 'width': 300}},
 'CUSTOM:Patine': {'label': {'x': 0, 'width': 99, 'align': 'right'}, 'data': {'color': '#000000', 'x': 92, 'width': 332}},
 'CUSTOM:Épaisseur': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 247}},
 'CUSTOM:Défauts': {'label': {'x': 0, 'width': 100, 'align': 'right'}, 'data': {'color': '#000000', 'x': 92, 'width': 332}},
 'CUSTOM:Tranche': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 247}},
 'CUSTOM:Métal / Alliage': {'label': {'x': 0, 'width': 136, 'align': 'right'}, 'data': {'color': '#000000', 'x': 136, 'width': 247}},
 'CUSTOM:Atelier de frappe': {'label': {'x': 0, 'width': 140, 'align': 'right'}, 'data': {'color': '#000000', 'x': 140, 'width': 268}},
 'contact': {'label': {'align': 'right', 'x': 0, 'width': 90}, 'data': {'color': '#000000', 'x': 90, 'width': 278}},
 'CUSTOM:Forme': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 247}},
 'CUSTOM:Authenticité': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 354}},
 'CUSTOM:Légende revers': {'label': {'x': 0, 'width': 125, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 300}},
 'CUSTOM:Axe': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 247}},
 'origin': {'label': {'x': 0, 'width': 108, 'align': 'right'}, 'data': {'color': '#000000', 'x': 108, 'width': 182}},
 'CUSTOM:Emplacement': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 354}},
 'CUSTOM:Année / Date': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 261}},
 'CUSTOM:Autorité / Émetteur': {'label': {'x': 0, 'width': 165, 'align': 'right'}, 'data': {'color': '#000000', 'x': 165, 'width': 261}},
 'CUSTOM:Dénomination / Type': {'label': {'x': 0, 'width': 175, 'align': 'right'}, 'data': {'color': '#000000', 'x': 175, 'width': 268}},
 'CUSTOM:Quantité': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 354}},
 'record_state': {'label': {'color': '#aa0000', 'x': 0, 'width': 118},
                  'data': {'color': '#aa0000',
                           'family': 'Segoe UI',
                           'size': 9,
                           'bold': True,
                           'italic': False,
                           'underline': False,
                           'align': 'left',
                           'x': 118,
                           'width': 139}},
 'CUSTOM:Tirage': {'label': {'x': 0, 'width': 93, 'align': 'right'}, 'data': {'color': '#000000', 'x': 86, 'width': 300}},
 'CUSTOM:Diamètre': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 247}},
 'CUSTOM:Nettoyé / Restauré': {'label': {'x': 0, 'width': 158, 'align': 'right'}, 'data': {'color': '#000000', 'x': 158, 'width': 354}},
 "CUSTOM:Marque d'atelier": {'label': {'x': 0, 'width': 143, 'align': 'right'}, 'data': {'color': '#000000', 'x': 143, 'width': 261}},
 'record_number': {'label': {'color': '#aa0000'}, 'data': {'color': '#aa0000'}},
 'CUSTOM:Poids': {'label': {'x': 0, 'width': 118, 'align': 'right'}, 'data': {'color': '#000000', 'x': 118, 'width': 247}}}

def apply_coins_template(manager, collection_id: int) -> None:
    cid = int(collection_id)
    custom = {}
    for label, field_type, group, date_format in COINS_CUSTOM_SPECS:
        info = manager.create_custom_field(cid, label, field_type, initial_group=group, date_format=date_format)
        custom[label] = info["field_key"]
    def real_key(key):
        key = str(key)
        return custom[key[7:]] if key.startswith("CUSTOM:") else key
    visible = set(COINS_VISIBLE_STANDARD); visible.update(custom.values())
    manager.set_visible_fields(cid, visible)
    manager.set_custom_labels(cid, dict(COINS_CUSTOM_LABELS))
    manager.set_field_placement(cid, {custom[label]: (group, 0) for label, _t, group, _d in COINS_CUSTOM_SPECS})
    manager.set_visual_positions(cid, {real_key(k): v for k, v in COINS_POSITIONS.items()})
    manager.set_visual_sizes(cid, {real_key(k): v for k, v in COINS_SIZES.items()})
    manager.set_tab_order(cid, [real_key(k) for k in COINS_TAB_ORDER])
    manager.set_sheet_background(cid, COINS_SHEET_BACKGROUND)
    from core.field_catalog import FIELDS
    styles = {}
    for spec in FIELDS:
        key = str(spec.key)
        if key not in visible and key not in {"record_number", "record_state", "photo_data"}:
            styles[key] = {"field_deleted": True}
    for pseudo_key, style in COINS_FIELD_STYLES.items():
        styles[real_key(pseudo_key)] = copy.deepcopy(style)
    manager.set_field_styles(cid, styles)
    manager.set_group_styles(cid, copy.deepcopy(COINS_GROUP_STYLES))

OBJECTS_CUSTOM_SPECS = [("Type d'objet", 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Désignation', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Marque / Fabricant', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Série / Collection', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Référence / Modèle', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Pays / Origine', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Période / Année', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Matière', 'list', 'Aspect', 'JJ/MM/AAAA'),
 ('Couleur', 'list', 'Aspect', 'JJ/MM/AAAA'),
 ('Dimensions', 'text', 'Aspect', 'JJ/MM/AAAA'),
 ('Poids', 'numeric', 'Aspect', 'JJ/MM/AAAA'),
 ('Sujet / Thème', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Marquage / Inscription', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Particularités', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('État', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Complet', 'list', 'Collection', 'JJ/MM/AAAA'),
 ("Emballage d'origine", 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Rareté', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Emplacement', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Quantité', 'numeric', 'Collection', 'JJ/MM/AAAA'),
 ('Notes', 'text', 'Collection', 'JJ/MM/AAAA'),
 ("Date d'acquisition", 'date', 'Acquisition', 'JJ/MM/AAAA'),
 ('Provenance', 'text', 'Acquisition', 'JJ/MM/AAAA'),
 ('Contact', 'list', 'Acquisition', 'JJ/MM/AAAA'),
 ("Prix d'achat", 'currency', 'Acquisition', 'JJ/MM/AAAA')]
OBJECTS_VISIBLE_STANDARD = {'record_state', 'record_number'}
OBJECTS_CUSTOM_LABELS = {}
OBJECTS_SHEET_BACKGROUND = '#E2DED3'
OBJECTS_GROUP_STYLES = {'__mm3_layout__': {'model_kind': 'objects', 'field_space': 'sheet_absolute_v1'},
 'Bandeau': {'geometry': {'x': 0, 'y': 0, 'w': 697, 'h': 90},
             'geometry_space': 'atelier_px',
             'position': {'dx': 0, 'dy': 0}},
 'Identification': {'title': {'text': 'Identification'},
                    'geometry': {'x': 0, 'y': 100, 'w': 697, 'h': 170},
                    'geometry_space': 'atelier_px',
                    'position': {'dx': 0, 'dy': -25},
                    'border_width': 2,
                    'border': '#8c8a83',
                    'background': '#f9f5e8'},
 'Photo': {'title': {'text': 'Objet — Vue 1'},
           'geometry': {'x': 708, 'y': 0, 'w': 280, 'h': 205},
           'geometry_space': 'atelier_px',
           'position': {'dx': 708, 'dy': 0}},
 'photo_slot_2': {'custom_group': True,
                  'custom_photo': True,
                  'frame_deleted': False,
                  'title': {'text': 'Objet — Vue 2'},
                  'geometry': {'x': 708, 'y': 231, 'w': 280, 'h': 205},
                  'geometry_space': 'atelier_px',
                  'position': {'dx': 1, 'dy': 230}},
 'Aspect': {'title': {'text': 'Caractéristiques'},
            'geometry': {'x': 0, 'y': 278, 'w': 331, 'h': 172},
            'geometry_space': 'atelier_px',
            'position': {'dx': 0, 'dy': -47},
            'border': '#8c8a83',
            'border_width': 2,
            'background': '#c7c4bb'},
 'Description objet': {'custom_group': True,
                       'title': {'text': 'Description'},
                       'geometry': {'x': 340, 'y': 278, 'w': 359, 'h': 172},
                       'geometry_space': 'atelier_px',
                       'position': {'dx': -5, 'dy': -42},
                       'border_width': 2,
                       'border': '#8c8a83',
                       'background': '#c7c4bb'},
 'Collection': {'title': {'text': 'État / Collection'},
                'geometry': {'x': 0, 'y': 457, 'w': 985, 'h': 190},
                'geometry_space': 'atelier_px',
                'position': {'dx': 0, 'dy': -108},
                'border_width': 2,
                'border': '#8c8a83',
                'background': '#f9f5e8'},
 'Acquisition': {'title': {'text': 'Acquisition'},
                 'geometry': {'x': 0, 'y': 657, 'w': 985, 'h': 86},
                 'geometry_space': 'atelier_px',
                 'position': {'dx': -620, 'dy': 332},
                 'border_width': 2,
                 'border': '#8c8a83'},
 'Localisation': {'frame_deleted': True}}
OBJECTS_POSITIONS = {'CUSTOM:Poids': (8, 561),
 "CUSTOM:Type d'objet": (68, 203),
 'CUSTOM:Série / Collection': (515, 242),
 'CUSTOM:Marquage / Inscription': (490, 481),
 'CUSTOM:Période / Année': (42, 324),
 'CUSTOM:Matière': (8, 440),
 'CUSTOM:Dimensions': (19, 521),
 'CUSTOM:Provenance': (393, 972),
 'CUSTOM:Pays / Origine': (544, 282),
 'CUSTOM:Notes': (47, 812),
 "CUSTOM:Emballage d'origine": (951, 703),
 'CUSTOM:État': (49, 703),
 'CUSTOM:Marque / Fabricant': (22, 242),
 'CUSTOM:Contact': (724, 971),
 'CUSTOM:Couleur': (8, 481),
 'CUSTOM:Référence / Modèle': (21, 282),
 'CUSTOM:Quantité': (1000, 744),
 'CUSTOM:Emplacement': (496, 743),
 'CUSTOM:Rareté': (31, 743),
 'CUSTOM:Désignation': (544, 203),
 'CUSTOM:Sujet / Thème': (546, 440),
 "CUSTOM:Date d'acquisition": (8, 969),
 'CUSTOM:Complet': (503, 703),
 "CUSTOM:Prix d'achat": (1035, 968),
 'CUSTOM:Particularités': (546, 521),
 'record_number': (25, 49),
 'record_state': (601, 49)}
OBJECTS_SIZES = {'CUSTOM:Poids': (435, 36),
 "CUSTOM:Type d'objet": (418, 36),
 'CUSTOM:Série / Collection': (418, 36),
 'CUSTOM:Marquage / Inscription': (464, 36),
 'CUSTOM:Période / Année': (444, 36),
 'CUSTOM:Matière': (435, 36),
 'CUSTOM:Dimensions': (424, 36),
 'CUSTOM:Provenance': (300, 36),
 'CUSTOM:Pays / Origine': (389, 36),
 'CUSTOM:Notes': (594, 56),
 "CUSTOM:Emballage d'origine": (347, 36),
 'CUSTOM:État': (243, 36),
 'CUSTOM:Marque / Fabricant': (464, 36),
 'CUSTOM:Contact': (265, 36),
 'CUSTOM:Couleur': (435, 36),
 'CUSTOM:Référence / Modèle': (465, 36),
 'CUSTOM:Quantité': (300, 36),
 'CUSTOM:Emplacement': (368, 36),
 'CUSTOM:Rareté': (261, 36),
 'CUSTOM:Désignation': (389, 36),
 'CUSTOM:Sujet / Thème': (408, 36),
 "CUSTOM:Date d'acquisition": (332, 36),
 'CUSTOM:Complet': (361, 36),
 "CUSTOM:Prix d'achat": (300, 36),
 'CUSTOM:Particularités': (408, 36),
 'record_number': (300, 36),
 'record_state': (261, 36)}
OBJECTS_TAB_ORDER = ['record_number',
 'record_state',
 "CUSTOM:Type d'objet",
 'CUSTOM:Marque / Fabricant',
 'CUSTOM:Référence / Modèle',
 'CUSTOM:Période / Année',
 'CUSTOM:Désignation',
 'CUSTOM:Série / Collection',
 'CUSTOM:Pays / Origine',
 'CUSTOM:Matière',
 'CUSTOM:Couleur',
 'CUSTOM:Dimensions',
 'CUSTOM:Poids',
 'CUSTOM:Sujet / Thème',
 'CUSTOM:Marquage / Inscription',
 'CUSTOM:Particularités',
 'CUSTOM:État',
 'CUSTOM:Complet',
 "CUSTOM:Emballage d'origine",
 'CUSTOM:Rareté',
 'CUSTOM:Emplacement',
 'CUSTOM:Quantité',
 'CUSTOM:Notes',
 "CUSTOM:Date d'acquisition",
 'CUSTOM:Provenance',
 'CUSTOM:Contact',
 "CUSTOM:Prix d'achat"]
OBJECTS_FIELD_STYLES = {'CUSTOM:Quantité': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                     'data': {'color': '#000000', 'x': 118, 'width': 182}},
 "CUSTOM:Date d'acquisition": {'label': {'x': 0, 'width': 150}, 'data': {'color': '#000000', 'x': 150, 'width': 182}},
 'CUSTOM:Matière': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                    'data': {'color': '#000000', 'x': 118, 'width': 317}},
 'CUSTOM:Période / Année': {'label': {'x': 0, 'width': 144, 'align': 'right'},
                            'data': {'color': '#000000', 'x': 144, 'width': 300}},
 "CUSTOM:Type d'objet": {'label': {'x': 0, 'width': 118, 'align': 'right'},
                         'data': {'color': '#000000', 'x': 118, 'width': 300}},
 'CUSTOM:Série / Collection': {'label': {'x': 0, 'width': 147, 'align': 'right'},
                               'data': {'color': '#000000', 'x': 147, 'width': 271}},
 'CUSTOM:Complet': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                    'data': {'color': '#000000', 'x': 118, 'width': 243}},
 'CUSTOM:Rareté': {'label': {'x': 0, 'width': 79, 'align': 'right'},
                   'data': {'color': '#000000', 'x': 79, 'width': 182, 'align': 'left'}},
 'CUSTOM:Sujet / Thème': {'label': {'x': 0, 'width': 118}, 'data': {'color': '#000000', 'x': 118, 'width': 290}},
 'CUSTOM:Couleur': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                    'data': {'color': '#000000', 'x': 118, 'width': 317}},
 'CUSTOM:Poids': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                  'data': {'color': '#000000', 'x': 118, 'width': 317}},
 "CUSTOM:Prix d'achat": {'label': {'align': 'right'}, 'data': {'color': '#000000'}},
 'CUSTOM:Marque / Fabricant': {'label': {'x': 0, 'width': 164, 'align': 'right'},
                               'data': {'color': '#000000', 'x': 164, 'width': 300}},
 'CUSTOM:Désignation': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                        'data': {'color': '#000000', 'x': 118, 'width': 271}},
 'CUSTOM:Référence / Modèle': {'label': {'x': 0, 'width': 165, 'align': 'right'},
                               'data': {'color': '#000000', 'x': 165, 'width': 300}},
 'record_number': {'label': {'color': '#aa0000'}, 'data': {'color': '#aa0000'}},
 "CUSTOM:Emballage d'origine": {'label': {'x': 0, 'width': 167, 'align': 'right'},
                                'data': {'color': '#000000', 'x': 165, 'width': 182}},
 'CUSTOM:Emplacement': {'label': {'x': 0, 'width': 125, 'align': 'right'},
                        'data': {'color': '#000000', 'x': 125, 'width': 243}},
 'CUSTOM:Particularités': {'label': {'x': 0, 'width': 118}, 'data': {'color': '#000000', 'x': 118, 'width': 290}},
 'CUSTOM:Provenance': {'label': {'align': 'right'}, 'data': {'color': '#000000'}},
 'CUSTOM:Marquage / Inscription': {'label': {'x': 0, 'width': 189},
                                   'data': {'color': '#000000', 'x': 174, 'width': 290}},
 'CUSTOM:Dimensions': {'label': {'x': 0, 'width': 107, 'align': 'right'},
                       'data': {'color': '#000000', 'x': 107, 'width': 317}},
 'photo_data': {'data': {'color': '#000000'}},
 'CUSTOM:Pays / Origine': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                           'data': {'color': '#000000', 'x': 118, 'width': 271}},
 'CUSTOM:État': {'label': {'x': 0, 'width': 61, 'align': 'right'}, 'data': {'color': '#000000', 'x': 61, 'width': 182}},
 'CUSTOM:Contact': {'label': {'x': 0, 'width': 83, 'align': 'right'},
                    'data': {'color': '#000000', 'x': 83, 'width': 182}},
 'CUSTOM:Notes': {'label': {'x': 0, 'width': 69, 'align': 'right'},
                  'data': {'color': '#000000', 'x': 62, 'width': 532, 'align': 'left'}},
 'record_state': {'label': {'color': '#aa0000', 'x': 0, 'width': 129},
                  'data': {'color': '#aa0000',
                           'x': 129,
                           'width': 132,
                           'family': 'Segoe UI',
                           'size': 9,
                           'bold': True,
                           'italic': False,
                           'underline': False,
                           'align': 'left'}}}

def apply_objects_template(manager, collection_id: int) -> None:
    cid = int(collection_id)
    custom = {}
    for label, field_type, group, date_format in OBJECTS_CUSTOM_SPECS:
        info = manager.create_custom_field(cid, label, field_type, initial_group=group, date_format=date_format)
        custom[label] = info["field_key"]
    def real_key(key):
        key = str(key)
        return custom[key[7:]] if key.startswith("CUSTOM:") else key
    visible = set(OBJECTS_VISIBLE_STANDARD); visible.update(custom.values())
    manager.set_visible_fields(cid, visible)
    manager.set_custom_labels(cid, dict(OBJECTS_CUSTOM_LABELS))
    manager.set_field_placement(cid, {custom[label]: (group, 0) for label, _t, group, _d in OBJECTS_CUSTOM_SPECS})
    manager.set_visual_positions(cid, {real_key(k): v for k, v in OBJECTS_POSITIONS.items()})
    manager.set_visual_sizes(cid, {real_key(k): v for k, v in OBJECTS_SIZES.items()})
    manager.set_tab_order(cid, [real_key(k) for k in OBJECTS_TAB_ORDER])
    manager.set_sheet_background(cid, OBJECTS_SHEET_BACKGROUND)
    from core.field_catalog import FIELDS
    styles = {}
    for spec in FIELDS:
        key = str(spec.key)
        if key not in visible and key not in {"record_number", "record_state", "photo_data"}:
            styles[key] = {"field_deleted": True}
    for key, value in OBJECTS_FIELD_STYLES.items():
        styles[real_key(key)] = copy.deepcopy(value)
    for key in visible:
        styles.setdefault(str(key), {}).setdefault("data", {}).setdefault("color", "#000000")
    manager.set_field_styles(cid, styles)
    manager.set_group_styles(cid, copy.deepcopy(OBJECTS_GROUP_STYLES))


# --- Modèle type : Livres / Documents ---
BOOKS_CUSTOM_SPECS = [('Éditeur', 'list', 'Identification', 'JJ/MM/AAAA'),
 ("Date d'acquisition", 'date', 'Acquisition', 'JJ/MM/AAAA'),
 ('Dimensions', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Tome / Volume', 'text', 'Identification', 'JJ/MM/AAAA'),
 ("Lieu d'édition", 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Notes', 'text', 'Collection', 'JJ/MM/AAAA'),
 ('Dédicace / Signature', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Année', 'numeric', 'Identification', 'JJ/MM/AAAA'),
 ("Prix d'achat", 'currency', 'Acquisition', 'JJ/MM/AAAA'),
 ('Contact', 'list', 'Acquisition', 'JJ/MM/AAAA'),
 ('État', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Sous-titre', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Sujet / Thème', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Emplacement', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Illustrations', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Nombre de pages', 'numeric', 'Identification', 'JJ/MM/AAAA'),
 ('ISBN / Référence', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Auteur / Créateur', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Format', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Collection / Série', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Langue', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Titre', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Reliure / Support', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Édition / Tirage', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Type de document', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Provenance', 'text', 'Acquisition', 'JJ/MM/AAAA'),
 ('Complet', 'list', 'Collection', 'JJ/MM/AAAA')]
BOOKS_VISIBLE_STANDARD = {"record_number", "record_state", "photo_data"}
BOOKS_CUSTOM_LABELS = {}
BOOKS_SHEET_BACKGROUND = '#DDE8D8'
BOOKS_GROUP_STYLES = {'__mm3_layout__': {'model_kind': 'books', 'field_space': 'sheet_absolute_v1'},
 'Bandeau': {'geometry': {'x': 0, 'y': 0, 'w': 690, 'h': 90},
             'geometry_space': 'atelier_px',
             'position': {'dx': 0, 'dy': 0}},
 'Identification': {'title': {'text': 'Identification'},
                    'geometry': {'x': 0, 'y': 100, 'w': 690, 'h': 164},
                    'geometry_space': 'atelier_px',
                    'position': {'dx': 0, 'dy': -25},
                    'border_width': 2,
                    'background': '#f2feec',
                    'border': '#a5ada1'},
 'Photo': {'title': {'text': 'Couverture'},
           'geometry': {'x': 705, 'y': 0, 'w': 280, 'h': 205},
           'geometry_space': 'atelier_px',
           'position': {'dx': 0, 'dy': 0},
           'frame_deleted': False},
 'photo_slot_2': {'custom_group': True,
                  'custom_photo': True,
                  'frame_deleted': False,
                  'title': {'text': 'Dos / Détail'},
                  'geometry': {'x': 705, 'y': 227, 'w': 280, 'h': 205},
                  'geometry_space': 'atelier_px',
                  'position': {'dx': 0, 'dy': 12}},
 'Édition': {'custom_group': True,
             'title': {'text': 'Édition / Références'},
             'geometry': {'x': 0, 'y': 273, 'w': 690, 'h': 159},
             'geometry_space': 'atelier_px',
             'position': {'dx': 0, 'dy': -7},
             'border_width': 2,
             'border': '#a5ada1',
             'background': '#cbd5c6'},
 'Description document': {'custom_group': True,
                          'title': {'text': 'Description'},
                          'geometry': {'x': 0, 'y': 441, 'w': 985, 'h': 108},
                          'geometry_space': 'atelier_px',
                          'position': {'dx': 0, 'dy': -59},
                          'background': '#cbd5c6',
                          'border_width': 2,
                          'border': '#a5ada1'},
 'Collection': {'title': {'text': 'État / Collection'},
                'geometry': {'x': 0, 'y': 559, 'w': 985, 'h': 149},
                'geometry_space': 'atelier_px',
                'position': {'dx': 0, 'dy': 34},
                'border_width': 2,
                'border': '#a5ada1',
                'background': '#f2feec'},
 'Acquisition': {'title': {'text': 'Acquisition'},
                 'geometry': {'x': 0, 'y': 719, 'w': 985, 'h': 90},
                 'geometry_space': 'atelier_px',
                 'position': {'dx': -620, 'dy': 394},
                 'border_width': 2,
                 'border': '#a5ada1'},
 'Aspect': {'frame_deleted': True},
 'Localisation': {'frame_deleted': True}}
BOOKS_POSITIONS = {'CUSTOM:Éditeur': (60, 431),
 "CUSTOM:Date d'acquisition": (24, 1067),
 'CUSTOM:Dimensions': (57, 707),
 'CUSTOM:Tome / Volume': (43, 550),
 "CUSTOM:Lieu d'édition": (531, 431),
 'CUSTOM:Notes': (79, 931),
 'CUSTOM:Dédicace / Signature': (24, 862),
 'CUSTOM:Année': (60, 471),
 "CUSTOM:Prix d'achat": (1090, 1074),
 'CUSTOM:Contact': (710, 1071),
 'CUSTOM:État': (79, 822),
 'CUSTOM:Sous-titre': (75, 250),
 'CUSTOM:Sujet / Thème': (901, 707),
 'CUSTOM:Emplacement': (554, 865),
 'CUSTOM:Illustrations': (467, 707),
 'CUSTOM:Nombre de pages': (433, 661),
 'CUSTOM:ISBN / Référence': (28, 510),
 'CUSTOM:Auteur / Créateur': (44, 282),
 'CUSTOM:Format': (901, 662),
 'CUSTOM:Collection / Série': (503, 510),
 'CUSTOM:Langue': (75, 314),
 'CUSTOM:Titre': (75, 218),
 'CUSTOM:Reliure / Support': (31, 662),
 'CUSTOM:Édition / Tirage': (508, 471),
 'CUSTOM:Type de document': (29, 186),
 'CUSTOM:Provenance': (367, 1069),
 'CUSTOM:Complet': (554, 822),
 'record_number': (19, 44),
 'record_state': (632, 44),
 'photo_data': (0, 0)}
BOOKS_SIZES = {'CUSTOM:Éditeur': (394, 36),
 "CUSTOM:Date d'acquisition": (321, 36),
 'CUSTOM:Dimensions': (353, 36),
 'CUSTOM:Tome / Volume': (411, 36),
 "CUSTOM:Lieu d'édition": (411, 36),
 'CUSTOM:Notes': (940, 36),
 'CUSTOM:Dédicace / Signature': (442, 36),
 'CUSTOM:Année': (394, 36),
 "CUSTOM:Prix d'achat": (254, 36),
 'CUSTOM:Contact': (371, 36),
 'CUSTOM:État': (386, 36),
 'CUSTOM:Sous-titre': (618, 36),
 'CUSTOM:Sujet / Thème': (443, 36),
 'CUSTOM:Emplacement': (396, 36),
 'CUSTOM:Illustrations': (392, 36),
 'CUSTOM:Nombre de pages': (425, 36),
 'CUSTOM:ISBN / Référence': (426, 36),
 'CUSTOM:Auteur / Créateur': (649, 36),
 'CUSTOM:Format': (443, 36),
 'CUSTOM:Collection / Série': (439, 36),
 'CUSTOM:Langue': (618, 36),
 'CUSTOM:Titre': (618, 36),
 'CUSTOM:Reliure / Support': (379, 36),
 'CUSTOM:Édition / Tirage': (433, 36),
 'CUSTOM:Type de document': (664, 36),
 'CUSTOM:Provenance': (326, 36),
 'CUSTOM:Complet': (396, 36),
 'record_number': (300, 36),
 'record_state': (281, 36),
 'photo_data': (300, 170)}
BOOKS_TAB_ORDER = ['record_number',
 'record_state',
 'CUSTOM:Type de document',
 'CUSTOM:Titre',
 'CUSTOM:Sous-titre',
 'CUSTOM:Auteur / Créateur',
 'CUSTOM:Langue',
 'CUSTOM:Éditeur',
 "CUSTOM:Lieu d'édition",
 'CUSTOM:Année',
 'CUSTOM:Édition / Tirage',
 'CUSTOM:ISBN / Référence',
 'CUSTOM:Collection / Série',
 'CUSTOM:Tome / Volume',
 'CUSTOM:Reliure / Support',
 'CUSTOM:Nombre de pages',
 'CUSTOM:Format',
 'CUSTOM:Dimensions',
 'CUSTOM:Illustrations',
 'CUSTOM:Sujet / Thème',
 'CUSTOM:État',
 'CUSTOM:Complet',
 'CUSTOM:Dédicace / Signature',
 'CUSTOM:Emplacement',
 'CUSTOM:Notes',
 "CUSTOM:Date d'acquisition",
 'CUSTOM:Provenance',
 'CUSTOM:Contact',
 "CUSTOM:Prix d'achat"]
BOOKS_FIELD_STYLES = {"CUSTOM:Date d'acquisition": {'label': {'x': 0, 'width': 154, 'align': 'right'},
                               'data': {'color': '#000000', 'x': 154, 'width': 167}},
 'CUSTOM:Format': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                   'data': {'color': '#000000', 'x': 118, 'width': 325}},
 'CUSTOM:Sujet / Thème': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                          'data': {'color': '#000000', 'x': 118, 'width': 325}},
 'photo_data': {'data': {'color': '#000000'}},
 'CUSTOM:Dédicace / Signature': {'label': {'x': 0, 'width': 174, 'align': 'right'},
                                 'data': {'color': '#000000', 'x': 174, 'width': 268}},
 'CUSTOM:Provenance': {'label': {'x': 0, 'width': 111, 'align': 'right'},
                       'data': {'color': '#000000', 'x': 111, 'width': 215}},
 'CUSTOM:État': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                 'data': {'color': '#000000', 'x': 118, 'width': 268}},
 'CUSTOM:Emplacement': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                        'data': {'color': '#000000', 'x': 118, 'width': 278}},
 'CUSTOM:Notes': {'data': {'color': '#000000'}},
 'CUSTOM:Nombre de pages': {'label': {'x': 0, 'width': 151, 'align': 'right'},
                            'data': {'color': '#000000', 'x': 151, 'width': 274}},
 'CUSTOM:Année': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                  'data': {'color': '#000000', 'x': 118, 'width': 276}},
 'CUSTOM:Reliure / Support': {'label': {'x': 0, 'width': 144, 'align': 'right'},
                              'data': {'color': '#000000', 'x': 144, 'width': 235}},
 "CUSTOM:Prix d'achat": {'label': {'align': 'right', 'x': 0, 'width': 118},
                         'data': {'color': '#000000', 'x': 118, 'width': 136}},
 'CUSTOM:ISBN / Référence': {'label': {'x': 0, 'width': 150, 'align': 'right'},
                             'data': {'color': '#000000', 'x': 150, 'width': 276}},
 'CUSTOM:Contact': {'label': {'x': 0, 'width': 85, 'align': 'right'},
                    'data': {'color': '#000000', 'x': 85, 'width': 286}},
 'CUSTOM:Complet': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                    'data': {'color': '#000000', 'x': 118, 'width': 278}},
 "CUSTOM:Lieu d'édition": {'label': {'x': 0, 'width': 118, 'align': 'right'},
                           'data': {'color': '#000000', 'x': 118, 'width': 293}},
 'CUSTOM:Auteur / Créateur': {'label': {'x': 0, 'width': 149, 'align': 'right'},
                              'data': {'color': '#000000', 'x': 149, 'width': 500}},
 'record_number': {'label': {'color': '#aa0000'}, 'data': {'color': '#aa0000'}},
 'CUSTOM:Illustrations': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                          'data': {'color': '#000000', 'x': 118, 'width': 274}},
 'CUSTOM:Sous-titre': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                       'data': {'color': '#000000', 'x': 118, 'width': 500}},
 'CUSTOM:Édition / Tirage': {'label': {'x': 0, 'width': 140, 'align': 'right'},
                             'data': {'color': '#000000', 'x': 140, 'width': 293}},
 'CUSTOM:Éditeur': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                    'data': {'color': '#000000', 'x': 118, 'width': 276}},
 'CUSTOM:Type de document': {'label': {'x': 0, 'width': 164, 'align': 'right'},
                             'data': {'color': '#000000', 'x': 164, 'width': 500}},
 'CUSTOM:Titre': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                  'data': {'color': '#000000', 'x': 118, 'width': 500}},
 'record_state': {'label': {'color': '#aa0000'},
                  'data': {'color': '#aa0000',
                           'family': 'Segoe UI',
                           'size': 9,
                           'bold': True,
                           'italic': False,
                           'underline': False,
                           'align': 'left'}},
 'CUSTOM:Langue': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                   'data': {'color': '#000000', 'x': 118, 'width': 500}},
 'CUSTOM:Dimensions': {'label': {'x': 0, 'width': 118, 'align': 'right'},
                       'data': {'color': '#000000', 'x': 118, 'width': 235}},
 'CUSTOM:Tome / Volume': {'label': {'x': 0, 'width': 135, 'align': 'right'},
                          'data': {'color': '#000000', 'x': 135, 'width': 276}},
 'CUSTOM:Collection / Série': {'label': {'x': 0, 'width': 146, 'align': 'right'},
                               'data': {'color': '#000000', 'x': 146, 'width': 293}}}

def apply_books_template(manager, collection_id: int) -> None:
    cid = int(collection_id)
    custom = {}
    for label, field_type, group, date_format in BOOKS_CUSTOM_SPECS:
        info = manager.create_custom_field(cid, label, field_type, initial_group=group, date_format=date_format)
        custom[label] = info["field_key"]
    def real_key(key):
        key = str(key)
        return custom[key[7:]] if key.startswith("CUSTOM:") else key
    visible = set(BOOKS_VISIBLE_STANDARD); visible.update(custom.values())
    manager.set_visible_fields(cid, visible)
    manager.set_custom_labels(cid, dict(BOOKS_CUSTOM_LABELS))
    manager.set_field_placement(cid, {custom[label]: (group, 0) for label, _t, group, _d in BOOKS_CUSTOM_SPECS})
    manager.set_visual_positions(cid, {real_key(k): v for k, v in BOOKS_POSITIONS.items()})
    manager.set_visual_sizes(cid, {real_key(k): v for k, v in BOOKS_SIZES.items()})
    manager.set_tab_order(cid, [real_key(k) for k in BOOKS_TAB_ORDER])
    manager.set_sheet_background(cid, BOOKS_SHEET_BACKGROUND)
    from core.field_catalog import FIELDS
    styles = {}
    for spec in FIELDS:
        key = str(spec.key)
        if key not in visible and key not in {"record_number", "record_state", "photo_data"}:
            styles[key] = {"field_deleted": True}
    for key, value in BOOKS_FIELD_STYLES.items():
        styles[real_key(key)] = copy.deepcopy(value)
    for key in visible:
        styles.setdefault(str(key), {}).setdefault("data", {}).setdefault("color", "#000000")
    manager.set_field_styles(cid, styles)
    manager.set_group_styles(cid, copy.deepcopy(BOOKS_GROUP_STYLES))

# --- Modèle type : Étiquettes / Documents graphiques ---
LABELS_CUSTOM_SPECS = [('Type de document', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Désignation / Titre', 'text', 'Identification', 'JJ/MM/AAAA'),
 ('Marque / Émetteur', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Produit / Sujet', 'list', 'Identification', 'JJ/MM/AAAA'),
 ('Pays', 'list', 'Origine / Édition', 'JJ/MM/AAAA'),
 ('Région / Ville', 'list', 'Origine / Édition', 'JJ/MM/AAAA'),
 ('Période', 'text', 'Origine / Édition', 'JJ/MM/AAAA'),
 ('Année', 'numeric', 'Origine / Édition', 'JJ/MM/AAAA'),
 ('Imprimeur / Fabricant', 'list', 'Origine / Édition', 'JJ/MM/AAAA'),
 ('Série / Référence', 'text', 'Origine / Édition', 'JJ/MM/AAAA'),
 ('Support / Matière', 'list', 'Description graphique', 'JJ/MM/AAAA'),
 ("Technique d'impression", 'list', 'Description graphique', 'JJ/MM/AAAA'),
 ('Dimensions', 'text', 'Description graphique', 'JJ/MM/AAAA'),
 ('Forme', 'list', 'Description graphique', 'JJ/MM/AAAA'),
 ('Couleurs dominantes', 'text', 'Description graphique', 'JJ/MM/AAAA'),
 ('Langue', 'list', 'Description graphique', 'JJ/MM/AAAA'),
 ('Sujet / Thème', 'list', 'Description graphique', 'JJ/MM/AAAA'),
 ('Particularités', 'text', 'Description graphique', 'JJ/MM/AAAA'),
 ('État', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Rareté', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Emplacement', 'list', 'Collection', 'JJ/MM/AAAA'),
 ('Notes', 'text', 'Collection', 'JJ/MM/AAAA'),
 ("Date d'acquisition", 'date', 'Acquisition', 'JJ/MM/AAAA'),
 ('Provenance', 'text', 'Acquisition', 'JJ/MM/AAAA'),
 ('Contact', 'list', 'Acquisition', 'JJ/MM/AAAA'),
 ("Prix d'achat", 'currency', 'Acquisition', 'JJ/MM/AAAA')]
LABELS_VISIBLE_STANDARD = {"record_number", "record_state", "photo_data"}
LABELS_CUSTOM_LABELS = {}
LABELS_SHEET_BACKGROUND = "#E8DFF0"
LABELS_GROUP_STYLES = {'__mm3_layout__': {'model_kind': 'labels', 'field_space': 'sheet_absolute_v1'},
 'Bandeau': {'geometry': {'x': 0, 'y': 0, 'w': 690, 'h': 90},
             'geometry_space': 'atelier_px',
             'position': {'dx': 0, 'dy': 0}},
 'Identification': {'title': {'text': 'Identification'},
                    'geometry': {'x': 0, 'y': 100, 'w': 690, 'h': 185},
                    'geometry_space': 'atelier_px',
                    'position': {'dx': 0, 'dy': 0}},
 'Photo': {'title': {'text': 'Recto'},
           'geometry': {'x': 705, 'y': 0, 'w': 280, 'h': 205},
           'geometry_space': 'atelier_px',
           'position': {'dx': 0, 'dy': 0},
           'frame_deleted': False},
 'photo_slot_2': {'custom_group': True,
                  'custom_photo': True,
                  'frame_deleted': False,
                  'title': {'text': 'Verso / Détail'},
                  'geometry': {'x': 705, 'y': 215, 'w': 280, 'h': 205},
                  'geometry_space': 'atelier_px',
                  'position': {'dx': 0, 'dy': 0}},
 'Origine / Édition': {'custom_group': True,
                       'title': {'text': 'Origine / Édition'},
                       'geometry': {'x': 0, 'y': 295, 'w': 690, 'h': 200},
                       'geometry_space': 'atelier_px',
                       'position': {'dx': 0, 'dy': 0}},
 'Description graphique': {'custom_group': True,
                           'title': {'text': 'Description'},
                           'geometry': {'x': 0, 'y': 505, 'w': 985, 'h': 155},
                           'geometry_space': 'atelier_px',
                           'position': {'dx': 0, 'dy': 0}},
 'Collection': {'title': {'text': 'État / Collection'},
                'geometry': {'x': 0, 'y': 670, 'w': 985, 'h': 135},
                'geometry_space': 'atelier_px',
                'position': {'dx': 0, 'dy': 0}},
 'Acquisition': {'title': {'text': 'Acquisition'},
                 'geometry': {'x': 0, 'y': 815, 'w': 985, 'h': 90},
                 'geometry_space': 'atelier_px',
                 'position': {'dx': 0, 'dy': 0}},
 'Aspect': {'frame_deleted': True},
 'Localisation': {'frame_deleted': True}}
LABELS_POSITIONS = {'record_number': (20, 44),
 'record_state': (410, 44),
 'CUSTOM:Type de document': (25, 135),
 'CUSTOM:Désignation / Titre': (25, 175),
 'CUSTOM:Marque / Émetteur': (25, 215),
 'CUSTOM:Produit / Sujet': (25, 255),
 'CUSTOM:Pays': (20, 335),
 'CUSTOM:Région / Ville': (355, 335),
 'CUSTOM:Période': (20, 375),
 'CUSTOM:Année': (355, 375),
 'CUSTOM:Imprimeur / Fabricant': (20, 415),
 'CUSTOM:Série / Référence': (355, 415),
 'CUSTOM:Support / Matière': (20, 545),
 "CUSTOM:Technique d'impression": (340, 545),
 'CUSTOM:Dimensions': (665, 545),
 'CUSTOM:Forme': (20, 585),
 'CUSTOM:Couleurs dominantes': (340, 585),
 'CUSTOM:Langue': (665, 585),
 'CUSTOM:Sujet / Thème': (20, 625),
 'CUSTOM:Particularités': (340, 625),
 'CUSTOM:État': (20, 710),
 'CUSTOM:Rareté': (340, 710),
 'CUSTOM:Emplacement': (665, 710),
 'CUSTOM:Notes': (20, 755),
 "CUSTOM:Date d'acquisition": (15, 850),
 'CUSTOM:Provenance': (257, 850),
 'CUSTOM:Contact': (499, 850),
 "CUSTOM:Prix d'achat": (741, 850),
 'photo_data': (0, 0)}
LABELS_SIZES = {'record_number': (300, 36),
 'record_state': (260, 36),
 'CUSTOM:Type de document': (640, 36),
 'CUSTOM:Désignation / Titre': (640, 36),
 'CUSTOM:Marque / Émetteur': (640, 36),
 'CUSTOM:Produit / Sujet': (640, 36),
 'CUSTOM:Pays': (300, 36),
 'CUSTOM:Région / Ville': (300, 36),
 'CUSTOM:Période': (300, 36),
 'CUSTOM:Année': (300, 36),
 'CUSTOM:Imprimeur / Fabricant': (300, 36),
 'CUSTOM:Série / Référence': (300, 36),
 'CUSTOM:Support / Matière': (300, 36),
 "CUSTOM:Technique d'impression": (300, 36),
 'CUSTOM:Dimensions': (300, 36),
 'CUSTOM:Forme': (300, 36),
 'CUSTOM:Couleurs dominantes': (300, 36),
 'CUSTOM:Langue': (300, 36),
 'CUSTOM:Sujet / Thème': (300, 36),
 'CUSTOM:Particularités': (625, 36),
 'CUSTOM:État': (300, 36),
 'CUSTOM:Rareté': (300, 36),
 'CUSTOM:Emplacement': (300, 36),
 'CUSTOM:Notes': (940, 36),
 "CUSTOM:Date d'acquisition": (300, 36),
 'CUSTOM:Provenance': (300, 36),
 'CUSTOM:Contact': (300, 36),
 "CUSTOM:Prix d'achat": (300, 36),
 'photo_data': (300, 170)}
LABELS_TAB_ORDER = ['record_number',
 'record_state',
 'CUSTOM:Type de document',
 'CUSTOM:Désignation / Titre',
 'CUSTOM:Marque / Émetteur',
 'CUSTOM:Produit / Sujet',
 'CUSTOM:Pays',
 'CUSTOM:Région / Ville',
 'CUSTOM:Période',
 'CUSTOM:Année',
 'CUSTOM:Imprimeur / Fabricant',
 'CUSTOM:Série / Référence',
 'CUSTOM:Support / Matière',
 "CUSTOM:Technique d'impression",
 'CUSTOM:Dimensions',
 'CUSTOM:Forme',
 'CUSTOM:Couleurs dominantes',
 'CUSTOM:Langue',
 'CUSTOM:Sujet / Thème',
 'CUSTOM:Particularités',
 'CUSTOM:État',
 'CUSTOM:Rareté',
 'CUSTOM:Emplacement',
 'CUSTOM:Notes',
 "CUSTOM:Date d'acquisition",
 'CUSTOM:Provenance',
 'CUSTOM:Contact',
 "CUSTOM:Prix d'achat"]

def apply_labels_template(manager, collection_id: int) -> None:
    cid = int(collection_id)
    custom = {}
    for label, field_type, group, date_format in LABELS_CUSTOM_SPECS:
        info = manager.create_custom_field(cid, label, field_type, initial_group=group, date_format=date_format)
        custom[label] = info["field_key"]
    def real_key(key):
        key = str(key)
        return custom[key[7:]] if key.startswith("CUSTOM:") else key
    visible = set(LABELS_VISIBLE_STANDARD); visible.update(custom.values())
    manager.set_visible_fields(cid, visible)
    manager.set_custom_labels(cid, dict(LABELS_CUSTOM_LABELS))
    manager.set_field_placement(cid, {custom[label]: (group, 0) for label, _t, group, _d in LABELS_CUSTOM_SPECS})
    manager.set_visual_positions(cid, {real_key(k): v for k, v in LABELS_POSITIONS.items()})
    manager.set_visual_sizes(cid, {real_key(k): v for k, v in LABELS_SIZES.items()})
    manager.set_tab_order(cid, [real_key(k) for k in LABELS_TAB_ORDER])
    manager.set_sheet_background(cid, LABELS_SHEET_BACKGROUND)
    from core.field_catalog import FIELDS
    styles = {}
    for spec in FIELDS:
        key = str(spec.key)
        if key not in visible and key not in {"record_number", "record_state", "photo_data"}:
            styles[key] = {"field_deleted": True}
    for key in visible:
        styles.setdefault(str(key), {}).setdefault("data", {})["color"] = "#000000"
    manager.set_field_styles(cid, styles)
    manager.set_group_styles(cid, copy.deepcopy(LABELS_GROUP_STYLES))



# 11.4.32 — Modèles types officiels fournis par l'utilisateur.
OFFICIAL_TEMPLATE_FILES = {
    "blank": "blank.db", "minerals": "minerals.db", "fossils": "fossils.db",
    "geology_samples": "geology_samples.db", "stamps": "stamps.db",
    "postcards": "postcards.db", "coins": "coins.db", "objects": "objects.db",
    "books": "books.db", "labels": "labels.db",
}

def _official_templates_folder() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ModelesOfficiels"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Le dossier des modèles types officiels est introuvable.")


# G-Skol 1.0.17 — traduction de la COPIE d'un modèle natif dans une nouvelle
# collection. Le modèle officiel source reste inchangé.
_NATIVE_EN_LABELS = {
    # Champs système / Minéraux
    "N°": "No.", "N° de fiche": "Record No.", "État de la fiche": "Record status", "Etat de la fiche": "Record status",
    "Nom": "Name", "Espèce": "Species", "Classe": "Class",
    "Formule chimique": "Chemical formula", "Système cristallin": "Crystal system",
    "Dureté": "Hardness", "Variété de": "Variety of", "Localité type": "Type locality",
    "Localité Type": "Type locality", "LT": "TL", "Luminescence": "Luminescence",
    "Intensité": "Intensity", "Couleur Fluo": "Fluorescence color", "Couleur fluo": "Fluorescence color",
    "Minéral 2": "Mineral 2", "Minéral 3": "Mineral 3", "Site1": "Site", "Site": "Site",
    "Gisement": "Deposit", "Département": "Department", "Région": "Region", "Pays": "Country",
    "Catégorie": "Category", "Lien espèce": "Species link", "Lien site": "Site link",
    "Commune": "Municipality", "Croissance": "Growth", "Couleur": "Color", "Forme": "Shape",
    "Qualité": "Quality", "Grossissement mini": "Minimum magnification",
    "Description": "Description", "Date": "Date", "Origine": "Origin", "Contact": "Contact",
    "Lieu": "Place", "Contenant": "Container", "Nombre de pièces": "Number of pieces",
    "Prix": "Price", "Coût total": "Total cost", "Photo": "Photo",

    # Libellés communs aux autres modèles officiels
    "Notes": "Notes", "Provenance": "Provenance", "Quantité": "Quantity",
    "Objet — Vue 1": "Object — View 1", "Timbre — Recto": "Stamp — Front",
    "Recto": "Front", "Couverture": "Cover", "Avers": "Obverse",
    "Carte postale — Recto": "Postcard — Front", "Photo du site": "Site photo",
    "Emplacement": "Location", "Rareté": "Rarity", "État": "Condition",
    "Prix d'achat": "Purchase price", "Date d'acquisition": "Acquisition date",
    "Sujet / Thème": "Subject / Theme", "Particularités": "Distinctive features",
    "Année": "Year", "Format": "Format", "Série": "Series", "Devise": "Currency",

    # Cartes postales
    "Coins": "Corners", "N° de série / Référence": "Series No. / Reference",
    "Région / Département": "Region / Department", "Qualité / État": "Quality / Condition",
    "Couleur / Noir et blanc": "Color / Black and white", "Type de carte": "Postcard type",
    "Circulée / Non circulée": "Used / Unused", "Timbre présent": "Stamp present",
    "Éditeur": "Publisher", "Taches": "Stains", "Lieu d'envoi": "Place sent from",
    "Date d'envoi": "Date sent", "Imprimeur": "Printer", "Cachet postal": "Postmark",
    "Lieu / Site représenté": "Place / Site depicted", "Titre / Légende": "Title / Caption",
    "Restauration": "Restoration", "Destination": "Destination", "Plis": "Creases",
    "État du dos": "Back condition", "Technique": "Technique",
    "Époque / Année estimée": "Period / Estimated year", "Texte manuscrit": "Handwritten text",
    "Photographe / Illustrateur": "Photographer / Illustrator",

    # Étiquettes et documents graphiques
    "Type de document": "Document type", "Langue": "Language", "Support / Matière": "Medium / Material",
    "Période": "Period", "Série / Référence": "Series / Reference", "Désignation / Titre": "Designation / Title",
    "Région / Ville": "Region / City", "Technique d'impression": "Printing technique",
    "Dimensions": "Dimensions", "Imprimeur / Fabricant": "Printer / Manufacturer",
    "Marque / Émetteur": "Brand / Issuer", "Produit / Sujet": "Product / Subject",
    "Couleurs dominantes": "Dominant colors",

    # Fossiles
    "Étage": "Stage", "Embranchement": "Phylum", "Ère": "Era", "Largeur mm": "Width mm",
    "Poids Gr": "Weight g", "Famille": "Family", "Formation géologique": "Geological formation",
    "Ordre": "Order", "Epaisseur mm": "Thickness mm", "Épaisseur mm": "Thickness mm",
    "Genre": "Genus", "Longueur mm": "Length mm", "État de conservation": "Condition",
    "Préparation": "Preparation", "Époque / Série": "Epoch / Series", "Nom / Taxon": "Name / Taxon",
    "Lieu de stockage": "Storage location",

    # Livres / Documents
    "Tome / Volume": "Volume", "Lieu d'édition": "Place of publication", "Dédicace / Signature": "Dedication / Signature",
    "Sous-titre": "Subtitle", "Illustrations": "Illustrations", "Nombre de pages": "Number of pages",
    "ISBN / Référence": "ISBN / Reference", "Auteur / Créateur": "Author / Creator",
    "Collection / Série": "Collection / Series", "Titre": "Title", "Reliure / Support": "Binding / Medium",
    "Édition / Tirage": "Edition / Printing", "Complet": "Complete",

    # Monnaies
    "Marque d'atelier": "Mint mark", "Pays / Territoire": "Country / Territory",
    "Dénomination / Type": "Denomination / Type", "Diamètre": "Diameter", "État / Grade": "Condition / Grade",
    "Axe": "Die axis", "Poids": "Weight", "Tranche": "Edge", "Légende revers": "Reverse legend",
    "Autorité / Émetteur": "Authority / Issuer", "Nettoyé / Restauré": "Cleaned / Restored",
    "Épaisseur": "Thickness", "Défauts": "Defects", "Atelier de frappe": "Mint",
    "Tirage": "Mintage", "Catalogue": "Catalogue", "Référence catalogue": "Catalogue reference",
    "Patine": "Patina", "Nature": "Nature", "Légende avers": "Obverse legend",
    "Année / Date": "Year / Date", "Sujet / Motif": "Subject / Motif", "Valeur faciale": "Face value",
    "Métal / Alliage": "Metal / Alloy", "Authenticité": "Authenticity",

    # Objets de collection
    "Type d'objet": "Object type", "Série / Collection": "Series / Collection",
    "Marquage / Inscription": "Marking / Inscription", "Période / Année": "Period / Year",
    "Matière": "Material", "Pays / Origine": "Country / Origin", "Emballage d'origine": "Original packaging",
    "Marque / Fabricant": "Brand / Manufacturer", "Référence / Modèle": "Reference / Model",
    "Désignation": "Designation",

    # Sables / échantillons géologiques
    "Couleur dominante": "Dominant color", "Stock échange": "Exchange stock",
    "Quantité (en Gr)": "Quantity (g)", "Type de sable": "Sand type",
    "Localisation précise": "Precise location", "Granulométrie": "Grain size",
    "Magnétisme": "Magnetism", "Nature dominante": "Dominant nature", "Composition": "Composition",
    "Département / Province": "Department / Province", "Description / observations": "Description / observations",

    # Timbres
    "Réf. catalogue": "Catalogue ref.", "N° dans la série": "No. in series", "Date d'émission": "Issue date",
    "Gomme": "Gum", "Neuf / Oblitéré": "Mint / Used", "Procédé d'impression": "Printing process",
    "Centrage": "Centering", "Variété": "Variety", "Oblitération": "Cancellation",
    "Dentelure": "Perforation", "Filigrane": "Watermark", "Émission": "Issue", "Cote": "Catalogue value",
}

_NATIVE_EN_GROUPS = {
    "Bandeau": "Header", "Identification": "Identification", "Photo": "Photo",
    "Localisation": "Location", "Aspect": "Appearance", "Acquisition": "Acquisition", "Collection": "Collection",
    "Carte postale — Recto": "Postcard — Front", "Carte postale — Verso": "Postcard — Back",
    "Édition": "Publishing", "Description": "Description", "Circulation": "Circulation", "État / Collection": "Condition / Collection",
    "Recto": "Front", "Verso / Détail": "Back / Detail", "Origine / Édition": "Origin / Publishing",
    "Taxonomie": "Taxonomy", "Provenance": "Provenance", "Datation / Spécimen": "Dating / Specimen",
    "Couverture": "Cover", "Dos / Détail": "Spine / Detail", "Édition / Références": "Publishing / References",
    "Avers": "Obverse", "Revers": "Reverse", "Caractéristiques": "Characteristics", "Référence": "Reference",
    "Objet — Vue 1": "Object — View 1", "Objet — Vue 2": "Object — View 2",
    "Timbre — Recto": "Stamp — Front", "Timbre -- Verso": "Stamp — Back", "Catalogue": "Catalogue", "Collection / État": "Collection / Condition",
    "Identification du sable": "Sand identification", "Photo du site": "Site photo", "Photo du sable": "Sand photo",
    "Observations": "Observations",
}


# G-Skol 1.0.233 — German display labels for native/master record templates.
_NATIVE_DE_LABELS = {
    "N°":"Nr.", "N° de fiche":"Datensatz-Nr.", "État de la fiche":"Datensatzstatus", "Etat de la fiche": "Datensatzstatus",
    "Nom":"Name", "Espèce":"Art", "Classe":"Klasse", "Formule chimique":"Chemische Formel",
    "Système cristallin":"Kristallsystem", "Dureté":"Härte", "Variété de":"Varietät von",
    "Localité type":"Typlokalität", "Localité Type":"Typlokalität", "LT":"TL",
    "Luminescence":"Lumineszenz", "Intensité":"Intensität", "Couleur Fluo":"Fluoreszenzfarbe",
    "Couleur fluo":"Fluoreszenzfarbe", "Minéral 2":"Mineral 2", "Minéral 3":"Mineral 3",
    "Site1":"Fundort", "Site":"Fundort", "Gisement":"Lagerstätte", "Département":"Département",
    "Région":"Region", "Pays":"Land", "Catégorie":"Kategorie", "Lien espèce":"Art-Link",
    "Lien site":"Fundort-Link", "Commune":"Gemeinde", "Croissance":"Wachstum", "Couleur":"Farbe",
    "Forme":"Form", "Qualité":"Qualität", "Grossissement mini":"Mindestvergrößerung",
    "Description":"Beschreibung", "Date":"Datum", "Origine":"Herkunft", "Contact":"Kontakt",
    "Lieu":"Ort", "Contenant":"Behälter", "Nombre de pièces":"Stückzahl", "Prix":"Preis",
    "Coût total":"Gesamtkosten", "Photo":"Foto", "Notes":"Notizen", "Provenance":"Herkunft",
    "Quantité":"Menge", "Emplacement":"Standort", "Rareté":"Seltenheit", "État":"Zustand",
    "Prix d'achat":"Kaufpreis", "Date d'acquisition":"Erwerbsdatum", "Sujet / Thème":"Motiv / Thema",
    "Particularités":"Besonderheiten", "Année":"Jahr", "Format":"Format", "Série":"Serie",
    "Devise":"Währung", "Coins":"Ecken", "N° de série / Référence":"Serien-Nr. / Referenz",
    "Région / Département":"Region / Département", "Qualité / État":"Qualität / Zustand",
    "Couleur / Noir et blanc":"Farbe / Schwarzweiß", "Type de carte":"Postkartentyp",
    "Circulée / Non circulée":"Gelaufen / Ungelaufen", "Timbre présent":"Briefmarke vorhanden",
    "Éditeur":"Verlag", "Taches":"Flecken", "Lieu d'envoi":"Absendeort", "Date d'envoi":"Versanddatum",
    "Imprimeur":"Druckerei", "Cachet postal":"Poststempel", "Lieu / Site représenté":"Dargestellter Ort / Standort",
    "Titre / Légende":"Titel / Bildunterschrift", "Restauration":"Restaurierung", "Destination":"Zielort",
    "Plis":"Knicke", "État du dos":"Zustand der Rückseite", "Technique":"Technik",
    "Époque / Année estimée":"Epoche / Geschätztes Jahr", "Texte manuscrit":"Handschriftlicher Text",
    "Photographe / Illustrateur":"Fotograf / Illustrator", "Type de document":"Dokumenttyp",
    "Langue":"Sprache", "Support / Matière":"Träger / Material", "Période":"Zeitraum",
    "Série / Référence":"Serie / Referenz", "Désignation / Titre":"Bezeichnung / Titel",
    "Région / Ville":"Region / Stadt", "Technique d'impression":"Drucktechnik", "Dimensions":"Abmessungen",
    "Imprimeur / Fabricant":"Druckerei / Hersteller", "Marque / Émetteur":"Marke / Herausgeber",
    "Produit / Sujet":"Produkt / Thema", "Couleurs dominantes":"Vorherrschende Farben",
    "Étage":"Stufe", "Embranchement":"Stamm", "Ère":"Ära", "Largeur mm":"Breite mm",
    "Poids Gr":"Gewicht g", "Famille":"Familie", "Formation géologique":"Geologische Formation",
    "Ordre":"Ordnung", "Epaisseur mm":"Dicke mm", "Épaisseur mm":"Dicke mm", "Genre":"Gattung",
    "Longueur mm":"Länge mm", "État de conservation":"Erhaltungszustand", "Préparation":"Präparation",
    "Époque / Série":"Epoche / Serie", "Nom / Taxon":"Name / Taxon", "Lieu de stockage":"Aufbewahrungsort",
    "Tome / Volume":"Band", "Lieu d'édition":"Erscheinungsort", "Dédicace / Signature":"Widmung / Signatur",
    "Sous-titre":"Untertitel", "Illustrations":"Abbildungen", "Nombre de pages":"Seitenzahl",
    "ISBN / Référence":"ISBN / Referenz", "Auteur / Créateur":"Autor / Urheber",
    "Collection / Série":"Sammlung / Serie", "Titre":"Titel", "Reliure / Support":"Einband / Träger",
    "Édition / Tirage":"Ausgabe / Auflage", "Complet":"Vollständig", "Marque d'atelier":"Münzzeichen",
    "Pays / Territoire":"Land / Gebiet", "Dénomination / Type":"Nennwert / Typ", "Diamètre":"Durchmesser",
    "État / Grade":"Zustand / Erhaltungsgrad", "Axe":"Stempelstellung", "Poids":"Gewicht", "Tranche":"Rand",
    "Légende revers":"Rückseitenlegende", "Autorité / Émetteur":"Autorität / Herausgeber",
    "Nettoyé / Restauré":"Gereinigt / Restauriert", "Épaisseur":"Dicke", "Défauts":"Fehler",
    "Atelier de frappe":"Prägestätte", "Tirage":"Auflage", "Catalogue":"Katalog",
    "Référence catalogue":"Katalogreferenz", "Patine":"Patina", "Nature":"Art",
    "Légende avers":"Vorderseitenlegende", "Année / Date":"Jahr / Datum", "Sujet / Motif":"Thema / Motiv",
    "Valeur faciale":"Nennwert", "Métal / Alliage":"Metall / Legierung", "Authenticité":"Echtheit",
    "Type d'objet":"Objekttyp", "Série / Collection":"Serie / Sammlung", "Marquage / Inscription":"Markierung / Inschrift",
    "Période / Année":"Zeitraum / Jahr", "Matière":"Material", "Pays / Origine":"Land / Herkunft",
    "Emballage d'origine":"Originalverpackung", "Marque / Fabricant":"Marke / Hersteller",
    "Référence / Modèle":"Referenz / Modell", "Désignation":"Bezeichnung",
    "Couleur dominante":"Vorherrschende Farbe", "Stock échange":"Tauschbestand", "Quantité (en Gr)":"Menge (g)",
    "Type de sable":"Sandtyp", "Localisation précise":"Genauer Fundort", "Granulométrie":"Korngröße",
    "Magnétisme":"Magnetismus", "Nature dominante":"Vorherrschende Art", "Composition":"Zusammensetzung",
    "Département / Province":"Département / Provinz", "Description / observations":"Beschreibung / Beobachtungen",
    "Réf. catalogue":"Katalogref.", "N° dans la série":"Nr. in der Serie", "Date d'émission":"Ausgabedatum",
    "Gomme":"Gummierung", "Neuf / Oblitéré":"Postfrisch / Gestempelt", "Procédé d'impression":"Druckverfahren",
    "Centrage":"Zentrierung", "Variété":"Varietät", "Oblitération":"Stempelung", "Dentelure":"Zähnung",
    "Filigrane":"Wasserzeichen", "Émission":"Ausgabe", "Cote":"Katalogwert",
}
_NATIVE_DE_GROUPS = {
    "Bandeau":"Kopfbereich", "Identification":"Identifikation", "Photo":"Foto", "Localisation":"Fundort",
    "Aspect":"Erscheinungsbild", "Acquisition":"Erwerb", "Collection":"Sammlung",
    "Carte postale — Recto":"Postkarte — Vorderseite", "Carte postale — Verso":"Postkarte — Rückseite",
    "Édition":"Veröffentlichung", "Description":"Beschreibung", "Circulation":"Postlauf",
    "État / Collection":"Zustand / Sammlung", "Recto":"Vorderseite", "Verso / Détail":"Rückseite / Detail",
    "Origine / Édition":"Herkunft / Ausgabe", "Taxonomie":"Taxonomie", "Provenance":"Herkunft",
    "Datation / Spécimen":"Datierung / Exemplar", "Couverture":"Umschlag", "Dos / Détail":"Rücken / Detail",
    "Édition / Références":"Ausgabe / Referenzen", "Avers":"Vorderseite", "Revers":"Rückseite",
    "Caractéristiques":"Merkmale", "Référence":"Referenz", "Objet — Vue 1":"Objekt — Ansicht 1",
    "Objet — Vue 2":"Objekt — Ansicht 2", "Timbre — Recto":"Briefmarke — Vorderseite",
    "Timbre -- Verso":"Briefmarke — Rückseite", "Catalogue":"Katalog", "Collection / État":"Sammlung / Zustand",
    "Identification du sable":"Sandbestimmung", "Photo du site":"Fundortfoto", "Photo du sable":"Sandfoto",
    "Observations":"Beobachtungen",
}


def translate_created_native_collection(manager, collection_id: int, language: str) -> bool:
    """Traduit uniquement la copie créée depuis un modèle natif."""
    lang = str(language or "fr").lower()
    if not (lang.startswith("en") or lang.startswith("de")):
        return False
    label_map = _NATIVE_DE_LABELS if lang.startswith("de") else _NATIVE_EN_LABELS
    group_map = _NATIVE_DE_GROUPS if lang.startswith("de") else _NATIVE_EN_GROUPS
    cid = int(collection_id)
    labels = manager.custom_labels(cid)

    # Champs standard : le catalogue est la source de vérité.
    from core.field_catalog import FIELD_BY_KEY
    for key in manager.all_model_keys(cid):
        key = str(key)
        spec = FIELD_BY_KEY.get(key)
        if spec is not None:
            raw_label = str(labels.get(key) or spec.label)
            labels[key] = label_map.get(raw_label, label_map.get(str(spec.label), raw_label))

    # Champs personnalisés officiels : leur libellé est stocké dans la collection.
    try:
        import sqlite3
        with sqlite3.connect(str(manager.db_path)) as con:
            rows = con.execute(
                "SELECT field_key,label FROM collection_custom_fields WHERE collection_id=?",
                (cid,)
            ).fetchall()
            for key, label in rows:
                nl = label_map.get(str(label), str(label))
                if nl != str(label):
                    con.execute(
                        "UPDATE collection_custom_fields SET label=? WHERE collection_id=? AND field_key=?",
                        (nl, cid, key)
                    )
            con.commit()
        if hasattr(manager, "_custom_fields_read_cache"):
            manager._custom_fields_read_cache.pop(cid, None)
    except Exception:
        pass

    manager.set_custom_labels(cid, labels)

    # Les identifiants internes de groupes restent français/stables ; seul le titre visible change.
    styles = manager.group_styles(cid)
    for name, st0 in list(styles.items()):
        if name == "__mm3_layout__" or not isinstance(st0, dict):
            continue
        st = dict(st0)
        title = dict(st.get("title") or {})
        raw_title = str(title.get("text") or "").strip()
        source_title = raw_title or str(name)
        english = group_map.get(source_title, group_map.get(str(name)))
        if english:
            title["text"] = english
            st["title"] = title
            styles[name] = st
    manager.set_group_styles(cid, styles)
    return True


def apply_official_template_database(manager, collection_id: int, model_key: str) -> bool:
    """Copie exacte du modèle type officiel, sans recopier aucune fiche."""
    import sqlite3
    filename = OFFICIAL_TEMPLATE_FILES.get(str(model_key))
    if not filename:
        return False
    source_path = _official_templates_folder() / filename
    if not source_path.is_file():
        raise FileNotFoundError(f"Modèle type officiel absent : {filename}")
    cid = int(collection_id)
    src = sqlite3.connect(str(source_path)); src.row_factory = sqlite3.Row
    dst = sqlite3.connect(str(manager.db_path)); dst.row_factory = sqlite3.Row
    dst.execute("PRAGMA foreign_keys=ON")
    try:
        row = src.execute("SELECT id FROM collections ORDER BY id LIMIT 1").fetchone()
        if row is None:
            raise ValueError(f"Le modèle officiel {filename} ne contient aucune collection.")
        scid = int(row["id"])
        relevant = ("collection_model_fields","collection_custom_fields","collection_model_appearance",
                    "collection_field_masters","collection_field_links","collection_reference_data",
                    "referential_definitions","referential_values")
        src_tables = {str(r["name"]): str(r["sql"] or "") for r in src.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall()}
        for table in relevant:
            sql = src_tables.get(table)
            if sql:
                dst.execute(sql.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1))
        try:
            ids=[r[0] for r in dst.execute("SELECT id FROM referential_definitions WHERE collection_id=?",(cid,)).fetchall()]
            if ids:
                dst.executemany("DELETE FROM referential_values WHERE definition_id=?",[(i,) for i in ids])
            dst.execute("DELETE FROM referential_definitions WHERE collection_id=?",(cid,))
        except sqlite3.OperationalError:
            pass
        for table in ("collection_reference_data","collection_field_links","collection_field_masters",
                      "collection_model_appearance","collection_model_fields","collection_custom_fields"):
            if table in src_tables:
                try: dst.execute(f"DELETE FROM {table} WHERE collection_id=?",(cid,))
                except sqlite3.OperationalError: pass
        def copy_collection_table(table):
            if table not in src_tables: return
            cols=[str(r[1]) for r in src.execute(f"PRAGMA table_info({table})").fetchall()]
            if "collection_id" not in cols: return
            rows=src.execute(f"SELECT {', '.join(cols)} FROM {table} WHERE collection_id=?",(scid,)).fetchall()
            if not rows: return
            idx=cols.index("collection_id"); vals=[]
            for r in rows:
                d=list(r); d[idx]=cid; vals.append(tuple(d))
            q=','.join('?' for _ in cols)
            dst.executemany(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({q})",vals)
        for table in ("collection_custom_fields","collection_model_fields","collection_model_appearance",
                      "collection_field_masters","collection_field_links","collection_reference_data"):
            copy_collection_table(table)
        if "referential_definitions" in src_tables:
            def_cols=[str(r[1]) for r in src.execute("PRAGMA table_info(referential_definitions)").fetchall()]
            # Les modèles officiels et les collections utilisateur peuvent provenir
            # de générations MM3 différentes. On complète d'abord le schéma cible,
            # puis on ne copie que les colonnes réellement communes.
            dst_def_cols={str(r[1]) for r in dst.execute("PRAGMA table_info(referential_definitions)").fetchall()}
            migrations={
                "sort_mode": "ALTER TABLE referential_definitions ADD COLUMN sort_mode TEXT NOT NULL DEFAULT 'custom'",
                "created_at": "ALTER TABLE referential_definitions ADD COLUMN created_at TEXT NOT NULL DEFAULT ''",
                "updated_at": "ALTER TABLE referential_definitions ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''",
            }
            for col, sql in migrations.items():
                if col not in dst_def_cols:
                    dst.execute(sql)
                    dst_def_cols.add(col)
            defs=src.execute(f"SELECT {', '.join(def_cols)} FROM referential_definitions WHERE collection_id=? ORDER BY id",(scid,)).fetchall()
            id_map={}
            for r in defs:
                data=dict(r); old_id=int(data.pop('id')); data['collection_id']=cid
                cols=[c for c in data if c in dst_def_cols]
                q=','.join('?' for _ in cols)
                cur=dst.execute(f"INSERT INTO referential_definitions ({', '.join(cols)}) VALUES ({q})",tuple(data[c] for c in cols))
                id_map[old_id]=int(cur.lastrowid)
            if id_map and "referential_values" in src_tables:
                vcols=[str(r[1]) for r in src.execute("PRAGMA table_info(referential_values)").fetchall()]
                icols=[c for c in vcols if c!='id']; q=','.join('?' for _ in icols)
                for old_id,new_id in id_map.items():
                    rows=src.execute(f"SELECT {', '.join(icols)} FROM referential_values WHERE definition_id=? ORDER BY id",(old_id,)).fetchall()
                    vals=[]
                    for r in rows:
                        data=dict(r); data['definition_id']=new_id; vals.append(tuple(data[c] for c in icols))
                    if vals: dst.executemany(f"INSERT INTO referential_values ({', '.join(icols)}) VALUES ({q})",vals)
        dst.commit()
        if hasattr(manager,"_custom_fields_read_cache"):
            manager._custom_fields_read_cache.pop(cid,None)
        return True
    finally:
        src.close(); dst.close()
