# G-Skol 6.1 — Composants tiers et licences

**Projet :** G-Skol — Gestion de collections  
**Auteur du projet :** FX — © 2026 FX  
**Licence du code original de G-Skol :** GNU GPL v3 (voir [`LICENSE`](LICENSE))  
**Statut :** inventaire préparatoire au 28 octobre 2026 — vérifications complémentaires nécessaires avant publication des exécutables.

Ce document distingue les composants **intégrés ou susceptibles d'être intégrés** aux distributions Windows des **outils employés uniquement pour leur fabrication**. Il ne remplace pas les textes de licence et notices qui doivent éventuellement accompagner les fichiers distribués.

## Composants de l'application

| Composant | Rôle | Licence ou régime connu | État |
| --- | --- | --- | --- |
| **Python 3.11** | Interpréteur utilisé par l'application et embarqué par PyInstaller | Python Software Foundation License, compatible avec la GPL | Vérifier la notice et les composants effectivement embarqués |
| **PySide6 / Qt for Python** | Interface graphique | Options open source **LGPL v3 / GPL v2 / GPL v3**, selon les composants | Compatible en principe avec le choix GPL v3 ; vérifier modules et obligations de distribution |
| **shiboken6** | Composant technique de PySide6 | Consulter la licence fournie avec la version exacte installée | Licence et version à relever dans la distribution |
| **Qt 6 et ses modules** | Bibliothèques graphiques utilisées par PySide6 | Licences open source Qt (LGPL v3 et, pour certains modules, GPL v3) et licences propres à certains composants tiers | Inventorier les DLL/modules réellement inclus et leurs notices |
| **SQLite** | Moteur de base de données (via Python) | Cœur SQLite placé dans le domaine public | Vérifier la provenance des éventuelles bibliothèques embarquées |

Le fichier `requirements.txt` de G-Skol déclare `PySide6>=6.8` : il ne fixe donc pas une version exacte. Les licences des versions et modules **réellement inclus dans chaque exécutable** doivent être contrôlées lors de la fabrication.

## Outils de fabrication

| Outil | Utilisation | Conditions principales |
| --- | --- | --- |
| **PyInstaller** | Création de l'exécutable Windows | GPL v2 ou ultérieure avec **exception de distribution du bootloader** ; cette exception permet de distribuer les applications produites. Les notices pertinentes restent à examiner. |
| **Inno Setup** | Création de l'installateur Windows | Outil soumis à ses propres conditions de licence. Les auteurs sollicitent l'achat d'une licence pour les usages commerciaux répondant à leurs critères ; consulter les conditions en vigueur. |
| **GitHub Actions** | Fabrication automatisée des deux distributions | Service et actions de fabrication : vérifier leurs versions et conditions indépendamment des licences du logiciel distribué. |

## Données et ressources du projet

- **Modèles officiels** : les dix bases SQLite du dossier `ModelesOfficiels` ont fait l'objet d'un contrôle de contenu préparatoire ; cela ne constitue pas une validation générale des droits de redistribution.
- **Référentiel Minéraux / IMA** : compilation et enrichissements réalisés par FX à partir de sources en ligne, notamment l'IMA. Les conditions de réutilisation et de redistribution des données d'origine restent à vérifier séparément.
- **Icônes et logos G-Skol** : créations réalisées avec l'assistance de ChatGPT et sélectionnées par FX ; vérifier l'absence d'éléments tiers incorporés.
- **Importations Microsoft Access** : certaines fonctions dépendent de composants Windows/Access présents sur le poste utilisateur ; ne pas supposer qu'ils sont redistribués avec G-Skol sans vérification du paquet.

## Contrôles restant à effectuer avant publication publique

- [ ] Relever les versions **exactes** de Python, PySide6, shiboken6, Qt et PyInstaller utilisées pour fabriquer la version publiée.
- [ ] Examiner le contenu du ZIP portable et de l'installateur, notamment les DLL, plugins Qt, fichiers de licence et notices des dépendances transitives.
- [ ] Fournir les textes de licence, notices de copyright et informations nécessaires au respect de la GPL/LGPL et des licences des composants tiers ; vérifier les obligations applicables à la redistribution de Qt.
- [ ] Confirmer les droits de redistribution des données de référence Minéraux / IMA et des éventuelles autres ressources externes.
- [ ] Vérifier les conditions applicables à la version exacte d'Inno Setup utilisée pour la fabrication.
- [ ] Contrôler que les sources correspondant aux exécutables publiés sont disponibles et que les procédures de fabrication sont documentées.

**Important :** ce document est un inventaire technique, pas une certification de conformité juridique. Il ne faut pas considérer ces contrôles comme terminés du seul fait de son ajout au dépôt.

## Sources officielles

- [Qt — Licences du framework](https://doc.qt.io/qt-6/licensing.html)
- [Qt for Python — Projet PySide6 et options de licence](https://github.com/qtproject/pyside-pyside-setup/blob/dev/README.pyside6_essentials.md)
- [Qt — Obligations GPL et LGPL](https://www.qt.io/development/open-source-lgpl-obligations)
- [Python — Historique et licence](https://docs.python.org/3/license.html)
- [SQLite — Domaine public](https://www.sqlite.org/copyright.html)
- [PyInstaller — Licence et exception du bootloader](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt)
- [Inno Setup — Conditions de licence](https://jrsoftware.org/files/is/license.txt)
- [Inno Setup — Informations sur les licences commerciales](https://jrsoftware.org/isorder.php)
