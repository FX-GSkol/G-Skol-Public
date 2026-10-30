#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Catalogue central des champs MM3.

Une seule source de vérité pour les champs exploitables par :
- la Vue Tableau ;
- le constructeur de requêtes ;
- les États.

Les champs techniques internes restent hors catalogue utilisateur.
"""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    field_type: str = "text"       # text | numeric | date | binary
    referential: str | None = None
    table: bool = True
    query: bool = True
    report: bool = True


FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("record_number", "N°", "numeric"),
    FieldSpec("mineral_name", "Nom", referential="mineral_name"),
    FieldSpec("mineral_2", "Minéral 2", referential="mineral_name"),
    FieldSpec("mineral_3", "Minéral 3", referential="mineral_name"),
    FieldSpec("mineral_class", "Classe", referential="mineral_class"),
    FieldSpec("chemical_formula", "Formule chimique"),
    FieldSpec("crystal_system", "Système cristallin", referential="crystal_system"),
    FieldSpec("luminescence", "Luminescence", referential="luminescence"),
    FieldSpec("luminescence_intensity", "Intensité", referential="luminescence_intensity"),
    FieldSpec("fluorescence_color", "Couleur fluo", referential="fluorescence_color"),
    FieldSpec("internet_link", "Lien espèce"),
    FieldSpec("site_name", "Site", referential="site_name"),
    FieldSpec("deposit", "Gisement"),
    FieldSpec("category", "Catégorie", referential="category"),
    FieldSpec("site_internet_link", "Lien site"),
    FieldSpec("department", "Département", referential="department"),
    FieldSpec("region", "Région", referential="region"),
    FieldSpec("country", "Pays", referential="country"),
    FieldSpec("growth", "Croissance", referential="growth"),
    FieldSpec("specimen_shape", "Forme", referential="specimen_shape"),
    FieldSpec("specimen_color", "Couleur", referential="specimen_color"),
    FieldSpec("quality", "Qualité", referential="quality"),
    FieldSpec("type_locality", "Localité type", "boolean"),
    FieldSpec("minimum_magnification", "Grossissement mini", "numeric",
              referential="minimum_magnification"),
    FieldSpec("description", "Description"),
    FieldSpec("box_type", "Contenant", referential="box_type"),
    FieldSpec("box_count", "Nombre de pièces", "numeric"),
    FieldSpec("price", "Prix", "numeric"),
    FieldSpec("total_cost", "Coût total", "numeric"),
    FieldSpec("acquisition_date", "Date", "date"),
    FieldSpec("origin", "Origine", referential="origin"),
    FieldSpec("contact", "Contact", referential="contact"),
    FieldSpec("place", "Lieu", referential="place"),
    FieldSpec("record_state", "Etat de la fiche", referential="record_state"),
    # Photo est un champ binaire spécial : visible dans le Tableau, mais pas
    # encore exploitable comme valeur textuelle dans Requêtes/États.
    FieldSpec("photo_data", "Photo", "binary", table=True, query=False, report=False),
)

FIELD_BY_KEY = {field.key: field for field in FIELDS}

TABLE_FIELDS = tuple(field for field in FIELDS if field.table)
QUERY_FIELDS = tuple(field for field in FIELDS if field.query)
REPORT_FIELDS = tuple(field for field in FIELDS if field.report)

TABLE_COLUMNS = tuple((field.label, field.key) for field in TABLE_FIELDS)
QUERY_COLUMNS = tuple((field.label, field.key) for field in QUERY_FIELDS)
REPORT_COLUMNS = tuple((field.label, field.key) for field in REPORT_FIELDS)

NUMERIC_FIELDS = frozenset(field.key for field in FIELDS if field.field_type == "numeric")
DATE_FIELDS = frozenset(field.key for field in FIELDS if field.field_type == "date")
REFERENTIAL_BY_FIELD = {
    field.key: field.referential
    for field in FIELDS
    if field.referential
}


def field_sort_key(value: str) -> str:
    """Clé alphabétique française simple, insensible aux accents et à la casse."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def field_type(field: str) -> str:
    spec = FIELD_BY_KEY.get(str(field or ""))
    return spec.field_type if spec else "text"


def is_numeric(field: str) -> bool:
    return field_type(field) == "numeric"


def is_date(field: str) -> bool:
    return field_type(field) == "date"
