# G-Skol — Gestion de collections

**Version : 6.1 (octobre 2026)**  
**Auteur : FX — © 2026 FX**  
**Licence : GNU GPL v3 — voir [LICENSE](LICENSE)**

G-Skol est un logiciel gratuit et open source pour Windows, destiné à la gestion de collections : minéraux, fossiles, sables, monnaies, timbres, livres et autres collections personnalisées.

Il permet de créer et organiser des fiches, d'utiliser des modèles de collections, de gérer des référentiels, d'importer des données provenant de différents formats et de produire des états imprimables.

## Fonctionnalités principales

- Création et gestion de collections au format `.coldb`.
- Modèles officiels et modèles personnalisables.
- Atelier de conception des fiches.
- Gestion des référentiels et des champs liés.
- Importation depuis Access, Excel, CSV, ODS, DBF et SQLite.
- Recherches multicritères et affichage en tableau.
- Création d'états résumés et détaillés.
- Exportation, sauvegarde et restauration des collections.
- Interface disponible en français, anglais et allemand.

## Versions Windows

G-Skol est proposé sous deux formes :

- **Version portable** : utilisation sans installation, notamment depuis une clé USB.
- **Version installable** : installation classique sous Windows.

Les deux versions ont été testées avec succès.

Les collections personnelles sont enregistrées séparément du programme, dans le Workspace ou dans les dossiers choisis par l'utilisateur.

## Démarrage depuis les sources

1. Installer Python 3.11 (64 bits).
2. Ouvrir un terminal dans le dossier du projet.
3. Installer les dépendances :

   ```powershell
   py -3.11 -m pip install -r requirements.txt
   ```

4. Lancer G-Skol avec `run.bat` ou :

   ```powershell
   py -3.11 app.py
   ```

Certaines fonctions d'importation Microsoft Access nécessitent les composants Windows/Access appropriés.

## Fabrication des distributions

Le dépôt comprend les scripts nécessaires à la fabrication :

- `CREER-G-SKOL-PORTABLE.bat` : version portable.
- `CREER-G-SKOL-INSTALLATEUR.bat` : installateur Windows.
- `G-Skol.iss` : configuration de l'installateur Inno Setup.
- `G-Skol.spec` : configuration PyInstaller.

Des workflows GitHub Actions permettent également de fabriquer automatiquement les distributions Windows.

Les exécutables ne disposent pas encore d'une signature numérique. Une demande de signature auprès de SignPath Foundation est prévue.

## Modèles officiels

Le modèle officiel Minéraux est fourni sans le référentiel scientifique initial issu de l'IMA ni les enrichissements provenant de sources tierces, retirés par précaution concernant leurs droits de redistribution. Les utilisateurs peuvent renseigner leurs propres données minéralogiques. Les précisions figurent dans le document SOURCES-DONNEES.md.

## Licence et contributions

Le code original de G-Skol est distribué sous licence **GNU General Public License version 3 (GPL v3)**.

Cette licence autorise l'utilisation, l'étude, la modification et la redistribution du logiciel, y compris à des fins commerciales, sous réserve du respect de ses conditions.

Les licences et droits applicables aux composants tiers et aux données de référence doivent également être respectés.

© 2026 FX.
