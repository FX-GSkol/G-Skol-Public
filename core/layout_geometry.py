#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Géométrie commune Atelier/Fiche — 018.4.4.1.2.7.1."""

BLOCK_ORDER = ("Bandeau", "Identification", "Localisation", "Aspect", "Acquisition", "Collection")

# Structure générale identique à la vraie Fiche.
BLOCK_GRID = {
    "Bandeau":       (0, 0, 1, 3),
    "Identification":(1, 0, 1, 2),
    "Photo":         (1, 2, 1, 1),
    "Localisation":  (2, 0, 1, 3),
    "Aspect":        (3, 0, 1, 2),
    "Acquisition":   (3, 2, 1, 1),
    "Collection":    (4, 0, 1, 3),
}

# Coordonnées de construction par défaut dans chaque bloc.
# Ce sont des coordonnées relatives au canevas du groupe.
DEFAULT_FIELD_GEOMETRY = {
    # Bandeau
    "record_number": (18, 10, 170, 31),
    "mineral_name":  (200, 10, 360, 31),
    "record_state":  (570, 10, 250, 31),
    "mineral_2":     (18, 48, 390, 31),
    "mineral_3":     (420, 48, 400, 31),

    # Identification
    "mineral_class":            (12, 12, 360, 31),
    "chemical_formula":         (385, 12, 390, 31),
    "crystal_system":           (12, 49, 360, 31),
    "luminescence":             (385, 49, 390, 31),
    "luminescence_intensity":   (12, 86, 360, 31),
    "fluorescence_color":       (385, 86, 390, 31),
    "internet_link":            (12, 123, 763, 31),

    # Photo: gérée comme cadre spécial dans la maquette
    "photo_data":               (0, 0, 300, 170),

    # Localisation
    "site_name":          (12, 12, 520, 31),
    "deposit":            (545, 12, 420, 31),
    "category":           (12, 49, 520, 31),
    "site_internet_link": (545, 49, 420, 31),
    "department":         (12, 86, 520, 31),
    "region":             (545, 86, 420, 31),
    "country":            (12, 123, 520, 31),

    # Aspect
    "growth":                (12, 12, 360, 31),
    "specimen_shape":        (385, 12, 390, 31),
    "specimen_color":        (12, 49, 360, 31),
    "quality":               (385, 49, 390, 31),
    "type_locality":         (12, 86, 360, 31),
    "minimum_magnification": (385, 86, 390, 31),
    "description":           (12, 123, 763, 72),

    # Acquisition
    "acquisition_date": (12, 12, 270, 31),
    "origin":           (12, 49, 270, 31),
    "contact":          (12, 86, 270, 31),
    "place":            (12, 123, 270, 31),

    # Collection
    "box_type":   (12, 12, 250, 31),
    "box_count":  (275, 12, 180, 31),
    "price":      (12, 49, 250, 31),
    "total_cost": (275, 49, 180, 31),
}

BLOCK_MIN_HEIGHT = {
    "Bandeau": 95,
    "Identification": 170,
    "Localisation": 170,
    "Aspect": 210,
    "Acquisition": 170,
    "Collection": 95,
}
