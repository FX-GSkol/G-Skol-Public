#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Petit socle de traduction G-Skol.

Le français reste la langue source. Une chaîne absente du dictionnaire anglais
retombe volontairement sur le français : cela permet de migrer l'interface
écran par écran sans casser l'application.
"""

EN = {
    # Import de fiches externes — CSV / TXT / TSV
    "3. Données détectées dans la source CSV / TXT / TSV": "3. Data detected in the CSV / TXT / TSV source",
    "Données contenant les fiches à ajouter :": "Data containing the records to add:",
    "Choisir un fichier CSV / TXT / TSV…": "Choose a CSV / TXT / TSV file…",
    "Aucun fichier CSV / TXT / TSV sélectionné.": "No CSV / TXT / TSV file selected.",
    "Choisir le fichier CSV / TXT / TSV contenant les fiches à ajouter": "Choose the CSV / TXT / TSV file containing the records to add",
    "Fichiers texte délimités (*.csv *.txt *.tsv);;Tous les fichiers (*.*)": "Delimited text files (*.csv *.txt *.tsv);;All files (*.*)",
    "Classer les champs source par ordre alphabétique (A → Z)": "Sort source fields alphabetically (A → Z)",
    "Fichier": "File", "Édition": "Edit", "Collection": "Collection", "Outils": "Tools", "Aide": "Help",
    "Créer une nouvelle collection…": "Create a new collection…", "Ouvrir une collection…": "Open a collection…",
    "Enregistrer sous…": "Save as…", "Ouvrir une 2e collection…": "Open a second collection…",
    "Activer le double clic sur les fichiers .coldb…": "Enable double-click for .coldb files…", "Quitter": "Exit",
    "Ouvrir les fiches…": "Open records…", "Recherche rapide…": "Quick search…",
    "Requête multicritère…": "Multi-criteria query…", "Vue Tableau…": "Table view…", "États…": "Reports…",
    "Fermer la collection": "Close collection", "Gérer les référentiels…": "Manage reference lists…",
    "Boîte à outils…": "Toolbox…", "À propos de G-Skol": "About G-Skol",
    "Atelier": "Workshop", "Langage": "English", "Aucune collection ouverte": "No collection open",
    "Ouvrez ou créez d'abord une collection avant d'accéder aux fiches.": "Open or create a collection before accessing records.",
    "L’espace quotidien pour saisir, consulter, rechercher et exploiter votre collection.":
        "Your everyday workspace for entering, browsing, searching and using your collection.",
    "Fiches": "Records", "Créer, ouvrir et parcourir les fiches.": "Create, open and browse records.",
    "Requêtes": "Queries", "Construire une requête avec un ou plusieurs critères.": "Build a query using one or more criteria.",
    "États": "Reports", "Créer, consulter et imprimer des états.": "Create, view and print reports.",
    "Statistiques rapides": "Quick statistics", "Répartir les fiches par champ et choisir un graphique.": "Group records by field and choose a chart.",
    "Répartition des fiches par champ": "Record distribution by field",
    "Champ :": "Field:", "Graphique :": "Chart:",
    "Barres horizontales": "Horizontal bars", "Colonnes": "Columns", "Secteurs": "Pie chart",
    "Actualiser": "Refresh", "Fermer": "Close", "(sans valeur)": "(no value)",
    "{records} fiche(s) · {values} valeur(s) distincte(s)": "{records} record(s) · {values} distinct value(s)",
    "{count} fiche(s)  ·  {percent}": "{count} record(s)  ·  {percent}",
    "Vue Tableau": "Table view", "Afficher les fiches en lignes et choisir librement les colonnes.": "Display records as rows and freely choose the columns.",
    "Boîte à outils": "Toolbox", "Effectuer volontairement des opérations globales de maintenance sur la collection.": "Perform deliberate collection-wide maintenance operations.",
    "Import / Export / Sauvegarde-Restauration": "Import / Export / Backup-Restore",
    "<b>Importation : aucune collection à ouvrir au préalable.</b><br>Importer &nbsp;&nbsp;•&nbsp;&nbsp; Exporter &nbsp;&nbsp;•&nbsp;&nbsp; Sauvegarder / Restaurer.":
        "<b>Import: no collection needs to be opened beforehand.</b><br>Import &nbsp;&nbsp;•&nbsp;&nbsp; Export &nbsp;&nbsp;•&nbsp;&nbsp; Backup / Restore.",
    "Créer une nouvelle collection": "Create a new collection", "Ouvrir une collection": "Open a collection",
    "Ouvrir une 2e collection": "Open a second collection",
    "L’espace de préparation et de personnalisation. Les réglages effectués ici seront réutilisés ensuite dans Collection.":
        "The preparation and customization workspace. Settings made here will then be reused in Collection.",
    "Modèles de fiches": "Record templates", "Préparer les modèles de fiches.": "Prepare record templates.",
    "Référentiels": "Reference lists", "Gérer les listes et leurs valeurs.": "Manage lists and their values.",
    "Éditeur d’états": "Report editor", "Personnaliser finement la structure, la présentation et les bandeaux des états.": "Fine-tune report structure, layout and headers.",
    "Paramètres": "Settings", "Adapter G-Skol à votre manière de travailler.": "Adapt G-Skol to the way you work.",
    "Ouvrir": "Open", "Gestion de collections.": "Collection management.",
    "Avertissement": "Warning",
    "G-Skol est un freeware. Vous pouvez l’utiliser, le modifier et le distribuer librement. Cependant, sa commercialisation ou sa vente sont strictement interdites.":
        "G-Skol is freeware. You may use, modify and distribute it freely. However, its commercialization or sale is strictly prohibited.",
    "Langue de l’interface": "Interface language", "Choisissez la langue de G-Skol :": "Choose the G-Skol language:",
    "Français": "Français", "English": "English", "Annuler": "Cancel", "Valider": "OK",

    # Fiche / record window
    "Aperçu temporaire — ": "Temporary preview — ", "Fiches — ": "Records — ",
    "Affichage": "View", "Taille par défaut de la fiche": "Default record window size",
    "Rétablir la taille compacte MM3 et recentrer la fiche sur l’écran actuel.":
        "Restore the compact default size and center the record window on the current screen.",
    "N° de fiche": "Record No.", "État de la fiche": "Record status", "Etat de la fiche": "Record status",
    "Vider la fiche": "Clear record", "Restaurer la fiche": "Restore record",
    "Première": "First", "Précédente": "Previous", "Suivante": "Next", "Dernière": "Last",
    "Créer une nouvelle fiche": "Create new record", "Enregistrer la fiche": "Save record",
    "Fermer la fiche": "Close record",
    "Bandeau": "Header", "Aucune fiche": "No record",
    "Fiche {current} sur {total}": "Record {current} of {total}",
    "Résultat {current} sur {total}": "Result {current} of {total}",
    "Cliquer pour aller directement à un N° de fiche": "Click to go directly to a record No.",
    "Rechercher rapidement une fiche": "Quickly search for a record",
    "Quitter la recherche et revenir à toute la collection": "Exit search and return to the full collection",
    "Effacer le contenu de cette fiche en conservant son N° et la marquer Libre":
        "Clear this record while keeping its No. and marking it Available",
    "Restaurer la fiche telle qu'elle était juste avant le dernier vidage":
        "Restore the record as it was just before it was last cleared",
    # Atelier / record template workshop
    "Modèle de fiche": "Record template", "Atelier - Modèles": "Workshop - Templates",
    "Modèle actif :": "Active template:", "Modèle :": "Template:",
    "Personnalisez ici le modèle de fiche utilisé pour cette collection. Tout enrichissement ou modification sera immédiatement visible.":
        "Customize the record template used for this collection here. Any addition or change will be visible immediately.",
    "Défaire": "Undo", "Refaire": "Redo",
    "Annuler la dernière modification": "Undo the last change",
    "Rétablir la dernière modification annulée": "Redo the last undone change",
    "Tout sélectionner": "Select all", "Tabulation = ordre visuel": "Tab order = visual order",
    "Détacher les champs": "Detach fields", "Détacher la palette des champs": "Detach field palette", "Rattacher la palette des champs": "Dock field palette", "Afficher la palette des champs": "Show field palette", "Ajouter un champ": "Add field",
    "Ajouter un cadre": "Add frame", "Ajouter un cadre Photo": "Add Photo frame",
    "Couleur de la fiche…": "Record color…", "Style par défaut": "Default style",
    "Aperçu en direct de la fiche": "Live record preview",
    "Cliquez un champ pour le sélectionner, déplacez-le à la souris, puis affinez avec les flèches.":
        "Click a field to select it, drag it with the mouse, then fine-tune with the arrow keys.",
    "Champ (glisser pour classer)": "Field (drag to reorder)",
    "Ouvrir un modèle…": "Open a template…", "Aperçu dans la Fiche": "Preview in Record",
    "Enregistrer le modèle": "Save template",
    "Identification": "Identification", "Photo": "Photo", "Localisation": "Location",
    "Aspect": "Appearance", "Acquisition": "Acquisition", "Collection": "Collection",

    # Atelier — infobulles et aide
    "Rétablir l'ordre de tabulation suivant l'ordre des champs dans la fiche": "Restore the tab order to match the visual field order in the record",
    "Place la liste des champs dans une palette flottante et libère la largeur pour la fiche.": "Move the field list to a floating palette and free up width for the record.",
    "Créer un nouveau champ propre à cette collection.": "Create a new field for this collection.",
    "Créer un nouveau cadre graphique libre dans la fiche.": "Create a new free-form frame in the record.",
    "Créer un cadre Photo supplémentaire, indépendant du cadre Photo principal.": "Create an additional Photo frame, independent of the main Photo frame.",
    "Choisir la couleur de fond propre à cette collection.": "Choose the background color for this collection.",
    "Rétablir la couleur de fond MM3 par défaut.": "Restore the default G-Skol background color.",
    "Charger un modèle depuis la bibliothèque Modèles de Fiches": "Load a template from the Record Templates library",
    "Tester ce modèle sur une copie temporaire complète de la collection": "Test this template on a complete temporary copy of the collection",
    "Conserver ce modèle dans la bibliothèque Modèles de Fiches": "Save this template in the Record Templates library",
    "Fermer la palette flottante": "Close the floating palette",
    "La grille n’apparaît qu’en mode construction. Ctrl+clic ou lasso = sélection multiple ; flèches = réglage au pixel. Huit poignées permettent largeur, hauteur ou les deux ; Aligner utilise toujours le bord extrême correspondant.":
        "The grid appears only in design mode. Ctrl+click or lasso = multiple selection; arrow keys = pixel adjustment. Eight handles resize width, height, or both; Align always uses the corresponding outermost edge.",
    # Sélecteur de couleurs commun
    "Couleur de fond de la fiche": "Record background color", "Couleur du texte": "Text color",
    "Choisir une couleur": "Choose a color", "Couleurs de base": "Basic colors",
    "Couleurs personnalisées": "Custom colors", "Choisir une couleur à l’écran": "Pick Screen Color",
    "Ajouter aux couleurs personnalisées": "Add to Custom Colors",
    "Supprimer une couleur personnalisée": "Delete a custom color",
    "Sélectionnez une couleur dans le damier, puis cliquez ici pour libérer sa case.": "Select a color in the grid, then click here to free its slot.",
    "Cliquez sur la couleur personnalisée à supprimer :": "Click the custom color to delete:",
    "Aucune couleur personnalisée n’est mémorisée.": "No custom color is saved.",
    "Le damier des couleurs personnalisées est complet.\n\nSupprimez d’abord une couleur du damier avant d’en ajouter une nouvelle.":
        "The custom color grid is full.\n\nDelete a color from the grid before adding a new one.",
    "Teinte :": "Hue:", "Saturation :": "Saturation:", "Valeur :": "Value:",
    "Rouge :": "Red:", "Vert :": "Green:", "Bleu :": "Blue:", "Transparence :": "Alpha channel:",

    # Import de modèle — tableau de correspondance
    "Correspondance des champs du modèle": "Template field mapping",
    "La colonne « Champ de la collection » contient les vrais champs MM3 de la collection actuelle. Choisissez, si nécessaire, l'emplacement correspondant dans le modèle de fiche ouvert. Un champ sans emplacement reste intact dans la palette. L'application du modèle ne crée aucun champ et ne modifie pas les propriétés métier de la collection.":
        "The ‘Collection field’ column contains the actual fields of the current collection. If necessary, choose the corresponding position in the open record template. A field with no position remains unchanged in the palette. Applying the template does not create fields or change the collection's field properties.",
    "Action": "Action", "Champ de la collection": "Collection field", "Type collection": "Collection type",
    "Emplacement du modèle": "Template position", "Type modèle": "Template type", "Détection MM3": "G-Skol detection",
    "Importer": "Import", "Créer": "Create", "Ne pas importer": "Do not import",
    "Tout importer": "Import all", "Tout ignorer": "Ignore all", "Valider la correspondance": "Confirm mapping",
    "Texte": "Text", "Nombre": "Number", "Bouton On / Off": "On / Off button",
    "Liste / Référentiel": "List / Reference list", "Lien": "Link", "Monétaire": "Currency",
    "Calculé": "Calculated", "Photo / Image": "Photo / Image",
    "Aucun emplacement proposé — le champ restera dans la palette": "No position suggested — the field will remain in the palette",
    "Clé et type identiques reconnus": "Matching key and type recognized",
    "Clé identique reconnue — type métier de la collection conservé": "Matching key recognized — collection field type retained",
    "Libellé et type compatibles reconnus": "Compatible label and type recognized",
    "Libellé identique reconnu — type métier de la collection conservé": "Matching label recognized — collection field type retained",
    "Libellé compatible reconnu — type métier de la collection conservé": "Compatible label recognized — collection field type retained",
    "Champ système MM3 — non importé (valeurs de la collection conservées)": "G-Skol system field — not imported (collection values retained)",
    "Ajout à la palette — à placer par l'utilisateur": "Added to palette — to be positioned by the user",
    "Champ conservé dans la collection — non ajouté au modèle": "Field retained in the collection — not added to the template",
    "Choisissez un emplacement du modèle": "Choose a template position",
    "Correspondance choisie par l'utilisateur": "Mapping selected by the user",

    # Bibliothèque de modèles
    "Modèles de Fiches": "Record Templates", "Ouvrir un modèle": "Open a template",
    "Choisissez un modèle. Double-cliquez sur un modèle pour l’ouvrir directement. Vous pouvez aussi créer, renommer, déplacer ou supprimer vos dossiers et modèles.":
        "Choose a template. Double-click a template to open it directly. You can also create, rename, move or delete your folders and templates.",
    "(racine)": "(root)", "Nouveau dossier…": "New folder…", "Renommer…": "Rename…",
    "Déplacer vers…": "Move to…", "Supprimer…": "Delete…",
    "Nouveau dossier": "New folder", "Nom du nouveau dossier :": "New folder name:",
    "Maître": "Master", "Relié à :": "Linked to:",
    "Modèle natif G-Skol": "Native G-Skol template",
    "Les modèles natifs G-Skol sont protégés. Choisissez un autre dossier pour enregistrer votre modèle personnel.":
        "Native G-Skol templates are protected. Choose another folder to save your personal template.",
    "Le dossier des modèles natifs G-Skol est protégé.": "The native G-Skol template folder is protected.",

    "pièce(s)": "piece(s)", "fiche(s)": "record(s)",
    "Dossier de l’état résumé": "Summary report folder",
    "Dossier de l’état détaillé": "Detailed report folder",
    "Enregistrer dans :": "Save in:",
    "(États résumés)": "(Summary reports)",
    "(États détaillés)": "(Detailed reports)",
    "+ Nouveau dossier ou sous-dossier…": "+ New folder or subfolder…",
    "Enregistrer": "Save", "Annuler": "Cancel",
    "État sauvegardé": "Report saved",
    "« {name} » a été sauvegardé.": "“{name}” has been saved.",

    'Nombre de fiches': 'Number of records',
    'Afficher comme colonne liée': 'Display as linked column',
    'Loupe :': 'Zoom:',
    'Enregistrer l’état': 'Save report',
    'Conserver cet état dans la bibliothèque Modèles d’États': 'Save this report in the Report Templates library',
    'Aperçu avant impression multipage': 'Multipage print preview',
    'Noir et blanc': 'Black and white',
    'Coché : impression en noir et blanc. Décoché : conserver les couleurs de l’état.': 'Checked: print in black and white. Unchecked: keep the report colors.',
    'Cliquez sur un titre pour trier. Déplacez les titres à la souris pour réorganiser les colonnes et redimensionnez-les à la souris.': 'Click a heading to sort. Drag headings to reorder columns and resize them with the mouse.',
    'Modifier le libellé…': 'Edit label…',
    'Mise en forme du total…': 'Format total…',
    'Rétablir le libellé du champ': 'Restore field label',
    'Aucune colonne dans la construction': 'No column in the layout',
    'Mise en forme de l’en-tête…': 'Format header…',
    'Modifier l’en-tête': 'Edit header',
    'Rétablir l’en-tête': 'Restore header',
    'Supprimer l’en-tête': 'Remove header',
    'Rétablir cet en-tête par défaut': 'Restore this header to default',
    'Afficher les totaux du bandeau': 'Show header totals',
    'Choisir les totaux du pied de page…': 'Choose footer totals…',
    'Mise en forme du pied de page…': 'Format footer…',
    'Numérotation des pages…': 'Page numbering…',
    'Supprimer la numérotation des pages': 'Remove page numbering',
    'Vider le pied de page': 'Clear footer',
    'Aperçu': 'Preview',
    'Tirer la poignée droite pour espacer les totaux du bandeau': 'Drag the right handle to adjust spacing between header totals',
    'Tirer la poignée droite pour ajuster la colonne et son en-tête': 'Drag the right handle to resize the column and its header',
    'Tirer la poignée droite pour espacer les totaux du pied de page': 'Drag the right handle to adjust spacing between footer totals',
    'Largeur synchronisée avec le total du bandeau': 'Width synchronized with the header total',
    'Mise en forme…': 'Format…',
    'Rétablir la mise en forme par défaut': 'Restore default formatting',
    'Retirer de la construction': 'Remove from layout',
    'Titre de l’État': 'Report title',
    'Titre :': 'Title:',
    'Police :': 'Font:',
    'Taille :': 'Size:',
    'Style :': 'Style:',
    'Alignement :': 'Alignment:',
    'Couleur texte :': 'Text color:',
    'Couleur fond :': 'Background color:',
    'Gras': 'Bold',
    'Italique': 'Italic',
    'Souligné': 'Underline',
    'Gauche': 'Left',
    'Droite': 'Right',
    'Choisir…': 'Choose…',
    'Rétablir par défaut': 'Restore defaults',
    'Collection « {name} » fermée': 'Collection “{name}” closed',
    'Loupe :': 'Zoom:',
    'Mise en forme': 'Formatting',
    'Mise en forme du total': 'Total formatting',
    'Mise en forme du total du pied de page': 'Footer total formatting',
    'Mise en forme du pied de page': 'Footer formatting',
    'Mise en forme du bandeau': 'Header formatting',
    'Mise en forme de l’en-tête': 'Header formatting',
    'Mise en forme de l’en-tête…': 'Format header…',
    'Libellé du total': 'Total label',
    'Libellé affiché :': 'Displayed label:',
    'Donnée — Police :': 'Data — Font:',
    'Donnée — Taille :': 'Data — Size:',
    'Donnée — Style :': 'Data — Style:',
    'Donnée — Couleur :': 'Data — Color:',
    'Police :': 'Font:',
    'Taille :': 'Size:',
    'Style :': 'Style:',
    'Alignement :': 'Alignment:',
    'Couleur texte :': 'Text color:',
    'Couleur fond :': 'Background color:',
    'Gauche': 'Left',
    'Droite': 'Right',
    'Choisir…': 'Choose…',
    'Gras': 'Bold',
    'Italique': 'Italic',
    'Souligné': 'Underline',
    'Modifier le libellé…': 'Edit label…',
    'Mise en forme du total…': 'Format total…',
    'Rétablir le total par défaut': 'Restore default total',
    "(calculé)": "(calculated)",
}


# G-Skol 1.0.229 — German translation, stage 1: Home and general navigation.
DE = {
    "Fichier": "Datei", "Édition": "Bearbeiten", "Collection": "Sammlung", "Outils": "Werkzeuge", "Aide": "Hilfe",
    "Créer une nouvelle collection…": "Neue Sammlung erstellen…", "Ouvrir une collection…": "Sammlung öffnen…",
    "Enregistrer sous…": "Speichern unter…", "Ouvrir une 2e collection…": "Zweite Sammlung öffnen…",
    "Activer le double clic sur les fichiers .coldb…": "Doppelklick für .coldb-Dateien aktivieren…", "Quitter": "Beenden",
    "Ouvrir les fiches…": "Datensätze öffnen…", "Recherche rapide…": "Schnellsuche…",
    "Requête multicritère…": "Mehrkriterien-Abfrage…", "Vue Tableau…": "Tabellenansicht…", "États…": "Berichte…",
    "Fermer la collection": "Sammlung schließen", "Gérer les référentiels…": "Referenzlisten verwalten…",
    "Boîte à outils…": "Werkzeugkasten…", "À propos de G-Skol": "Über G-Skol",
    "Atelier": "Werkstatt", "Langage": "Deutsch", "Aucune collection ouverte": "Keine Sammlung geöffnet",
    "Ouvrez ou créez d'abord une collection avant d'accéder aux fiches.": "Öffnen oder erstellen Sie zuerst eine Sammlung, bevor Sie auf die Datensätze zugreifen.",
    "L’espace quotidien pour saisir, consulter, rechercher et exploiter votre collection.": "Der tägliche Arbeitsbereich zum Erfassen, Anzeigen, Suchen und Auswerten Ihrer Sammlung.",
    "Fiches": "Datensätze", "Créer, ouvrir et parcourir les fiches.": "Datensätze erstellen, öffnen und durchsuchen.",
    "Requêtes": "Abfragen", "Construire une requête avec un ou plusieurs critères.": "Eine Abfrage mit einem oder mehreren Kriterien erstellen.",
    "États": "Berichte", "Créer, consulter et imprimer des états.": "Berichte erstellen, anzeigen und drucken.",
    "Statistiques rapides": "Schnellstatistik", "Répartir les fiches par champ et choisir un graphique.": "Datensätze nach Feld gruppieren und ein Diagramm auswählen.",
    "Vue Tableau": "Tabellenansicht", "Afficher les fiches en lignes et choisir librement les colonnes.": "Datensätze in Zeilen anzeigen und Spalten frei auswählen.",
    "Boîte à outils": "Werkzeugkasten", "Effectuer volontairement des opérations globales de maintenance sur la collection.": "Globale Wartungsarbeiten an der Sammlung gezielt ausführen.",
    "Import / Export / Sauvegarde-Restauration": "Import / Export / Sicherung-Wiederherstellung",
    "<b>Importation : aucune collection à ouvrir au préalable.</b><br>Importer &nbsp;&nbsp;•&nbsp;&nbsp; Exporter &nbsp;&nbsp;•&nbsp;&nbsp; Sauvegarder / Restaurer.": "<b>Import: Es muss vorher keine Sammlung geöffnet werden.</b><br>Importieren &nbsp;&nbsp;•&nbsp;&nbsp; Exportieren &nbsp;&nbsp;•&nbsp;&nbsp; Sichern / Wiederherstellen.",
    "Créer une nouvelle collection": "Neue Sammlung erstellen", "Ouvrir une collection": "Sammlung öffnen",
    "Ouvrir une 2e collection": "Zweite Sammlung öffnen",
    "L’espace de préparation et de personnalisation. Les réglages effectués ici seront réutilisés ensuite dans Collection.": "Der Arbeitsbereich zur Vorbereitung und Anpassung. Die hier vorgenommenen Einstellungen werden anschließend in der Sammlung verwendet.",
    "Modèles de fiches": "Datensatzvorlagen", "Préparer les modèles de fiches.": "Datensatzvorlagen vorbereiten.",
    "Référentiels": "Referenzlisten", "Gérer les listes et leurs valeurs.": "Listen und ihre Werte verwalten.",
    "Éditeur d’états": "Berichtseditor", "Personnaliser finement la structure, la présentation et les bandeaux des états.": "Struktur, Layout und Kopfbereiche der Berichte detailliert anpassen.",
    "Paramètres": "Einstellungen", "Adapter G-Skol à votre manière de travailler.": "G-Skol an Ihre Arbeitsweise anpassen.",
    "Ouvrir": "Öffnen", "Gestion de collections.": "Sammlungsverwaltung.",
    "Avertissement": "Warnung",
    "G-Skol est un freeware. Vous pouvez l’utiliser, le modifier et le distribuer librement. Cependant, sa commercialisation ou sa vente sont strictement interdites.": "G-Skol ist Freeware. Sie dürfen es frei verwenden, verändern und weitergeben. Eine kommerzielle Vermarktung oder ein Verkauf ist jedoch strengstens untersagt.",
    "Langue de l’interface": "Sprache der Benutzeroberfläche", "Choisissez la langue de G-Skol :": "Wählen Sie die Sprache von G-Skol:",
    "Français": "Français", "English": "English", "Deutsch": "Deutsch", "Annuler": "Abbrechen", "Valider": "OK",
}


# G-Skol 1.0.248 — final German corrections: report header formatting + table exit confirmation.
DE.update({
    'Modifications non enregistrées': 'Nicht gespeicherte Änderungen',
    'Cette vue n’a pas encore été enregistrée.': 'Diese Ansicht wurde noch nicht gespeichert.',
    'Voulez-vous l’enregistrer avant de quitter ?': 'Möchten Sie sie vor dem Verlassen speichern?',
    'Voulez-vous enregistrer ces modifications avant de quitter ?': 'Möchten Sie diese Änderungen vor dem Verlassen speichern?',
    'Enregistrer': 'Speichern',
    'Enregistrer sous…': 'Speichern unter…',
    'Ne pas enregistrer': 'Nicht speichern',
    'Mise en forme du bandeau': 'Formatierung des Kopfbereichs',
    'Mise en forme de l’en-tête': 'Formatierung des Kopfbereichs',
    'Mise en forme de l’en-tête…': 'Kopfbereich formatieren…',
    'Police :': 'Schriftart:',
    'Taille :': 'Größe:',
    'Style :': 'Stil:',
    'Alignement :': 'Ausrichtung:',
    'Couleur texte :': 'Textfarbe:',
    'Couleur fond :': 'Hintergrundfarbe:',
    'Couleur du texte': 'Textfarbe',
    'Couleur du fond': 'Hintergrundfarbe',
    'Gras': 'Fett',
    'Italique': 'Kursiv',
    'Souligné': 'Unterstrichen',
    'Gauche': 'Links',
    'Droite': 'Rechts',
    'Choisir…': 'Auswählen…',
    'Rétablir par défaut': 'Standard wiederherstellen',
    'Annuler': 'Abbrechen',
    'Oui': 'Ja',
    'Non': 'Nein',
    'Afficher toutes les fiches': 'Alle Datensätze anzeigen',
})



# G-Skol 1.0.250 — German: Import / Access creation workflow.
DE.update({
    'Importation': 'Import',
    'Choisissez le type d’importation. G-Skol vous guidera ensuite étape par étape dans le module correspondant.': 'Wählen Sie die Art des Imports. G-Skol führt Sie anschließend Schritt für Schritt durch das entsprechende Modul.',
    'Importation et création d’une collection': 'Importieren und Sammlung erstellen',
    'Créer une nouvelle collection G-Skol depuis une source extérieure.': 'Eine neue G-Skol-Sammlung aus einer externen Quelle erstellen.',
    'Importation de référentiels dans une collection existante': 'Referenzlisten in eine vorhandene Sammlung importieren',
    'Ajouter, compléter ou créer des référentiels dans une collection existante.': 'Referenzlisten in einer vorhandenen Sammlung hinzufügen, ergänzen oder erstellen.',
    'Ajouter des fiches depuis une source extérieure': 'Datensätze aus einer externen Quelle hinzufügen',
    'Ajouter de nouvelles fiches à la suite d’une collection existante sans modifier les fiches déjà présentes.': 'Neue Datensätze zu einer vorhandenen Sammlung hinzufügen, ohne bestehende Datensätze zu ändern.',
    'Importer un modèle G-Skol  (.colmod)': 'Eine G-Skol-Vorlage importieren (.colmod)',
    'Enregistrer dans la bibliothèque un modèle de Fiche ou de Tableau reçu d’un autre utilisateur, sans modifier de collection.': 'Eine von einem anderen Benutzer erhaltene Datensatz- oder Tabellenvorlage in der Bibliothek speichern, ohne eine Sammlung zu ändern.',
    'Retour': 'Zurück',
    'Fermer': 'Schließen',
    'Créez une nouvelle collection G-Skol à partir d’une source externe. Choisissez d’abord le format ; G-Skol analyse ensuite la source avant toute création.': 'Erstellen Sie eine neue G-Skol-Sammlung aus einer externen Quelle. Wählen Sie zuerst das Format; G-Skol analysiert anschließend die Quelle, bevor etwas erstellt wird.',
    'Choisissez une base .accdb ou .mdb. G-Skol peut maintenant en examiner la structure sans importer ni modifier aucune donnée.': 'Wählen Sie eine .accdb- oder .mdb-Datenbank. G-Skol kann ihre Struktur prüfen, ohne Daten zu importieren oder zu ändern.',
    'Choisir une base Access…': 'Access-Datenbank auswählen…',
    'Analyser la base': 'Datenbank analysieren',
    'Aucun fichier Access sélectionné.': 'Keine Access-Datei ausgewählt.',
    'Après analyse, les tables et leurs champs apparaîtront ci-dessous.': 'Nach der Analyse werden die Tabellen und ihre Felder unten angezeigt.',
    'Table / Champ': 'Tabelle / Feld',
    'Type': 'Typ',
    'Lignes': 'Zeilen',
    'Choisir cette table': 'Diese Tabelle auswählen',
    'Aperçu des données…': 'Datenvorschau…',
    'Correspondance des champs…': 'Feldzuordnung…',
    'Sélectionnez une table dans la liste ci-dessus. Les lignes de champs ne sont pas sélectionnables comme source.': 'Wählen Sie eine Tabelle aus der Liste oben. Feldzeilen können nicht als Quelle ausgewählt werden.',
    'Après validation de la table source, l’étape suivante préparera la correspondance entre les champs Access et les champs G-Skol.': 'Nach Bestätigung der Quelltabelle wird im nächsten Schritt die Zuordnung zwischen Access-Feldern und G-Skol-Feldern vorbereitet.',
    'Créer la collection G-Skol et importer…': 'G-Skol-Sammlung erstellen und importieren…',
    'Choisir une base Microsoft Access': 'Microsoft-Access-Datenbank auswählen',
    'Bases Microsoft Access (*.accdb *.mdb);;Tous les fichiers (*.*)': 'Microsoft-Access-Datenbanken (*.accdb *.mdb);;Alle Dateien (*.*)',
    'Base sélectionnée. Cliquez sur « Analyser la base » pour afficher sa structure.': 'Datenbank ausgewählt. Klicken Sie auf „Datenbank analysieren“, um ihre Struktur anzuzeigen.',
    'La base Access sélectionnée est introuvable.': 'Die ausgewählte Access-Datenbank wurde nicht gefunden.',
    'Analyse de la base Access en cours…': 'Access-Datenbank wird analysiert…',
    'Analyse Access impossible': 'Access-Analyse nicht möglich',
    'Analyse terminée : aucune table de données n’a été trouvée.': 'Analyse abgeschlossen: Keine Datentabelle gefunden.',
    'Vous avez sélectionné un champ. Pour l’import, sélectionnez le nom de la table qui contient les fiches.': 'Sie haben ein Feld ausgewählt. Wählen Sie für den Import den Namen der Tabelle aus, die die Datensätze enthält.',
    'nombre inconnu de': 'unbekannte Anzahl',
    'Table source retenue': 'Quelltabelle ausgewählt',
    'La table « {name} » a été retenue comme table des fiches à importer.\n\n': 'Die Tabelle „{name}“ wurde als Tabelle mit den zu importierenden Datensätzen ausgewählt.\n\n',
    '\n\nVous pouvez maintenant préparer la correspondance des champs.': '\n\nSie können jetzt die Feldzuordnung vorbereiten.',
    'Correspondance des champs {source} → G-Skol': 'Feldzuordnung {source} → G-Skol',
    'Table source : <b>{table}</b> — {count} champ(s). Pour chaque champ {source}, choisissez s’il doit être importé, le nom du futur champ G-Skol et son type. Les propositions sont automatiques mais restent entièrement modifiables.': 'Quelltabelle: <b>{table}</b> — {count} Feld(er). Wählen Sie für jedes {source}-Feld, ob es importiert werden soll, den Namen des zukünftigen G-Skol-Feldes und seinen Typ. Die Vorschläge werden automatisch erstellt, können aber vollständig geändert werden.',
    'Cette étape ne crée encore aucune collection et n’importe aucune donnée. Elle prépare seulement la structure de la future collection G-Skol.': 'In diesem Schritt wird noch keine Sammlung erstellt und es werden keine Daten importiert. Er bereitet lediglich die Struktur der zukünftigen G-Skol-Sammlung vor.',
    'Action': 'Aktion',
    'Champ {source}': '{source}-Feld',
    'Type {source}': '{source}-Typ',
    'Champ G-Skol': 'G-Skol-Feld',
    'Type G-Skol': 'G-Skol-Typ',
    'Détection G-Skol': 'G-Skol-Erkennung',
    'Tout importer': 'Alle importieren',
    'Tout ignorer': 'Alle ignorieren',
    'Réinitialiser les propositions': 'Vorschläge zurücksetzen',
    'Aperçu des données — fenêtre flottante': 'Datenvorschau — schwebendes Fenster',
    'Annuler': 'Abbrechen',
    'Valider la correspondance': 'Zuordnung bestätigen',
    'Modifier le libellé…': 'Feldbezeichnung bearbeiten…',
    'Importer': 'Importieren',
    'Ignorer': 'Ignorieren',
    'Correspondance vide': 'Leere Zuordnung',
    'Aucun champ n’est actuellement prévu pour l’import.': 'Derzeit ist kein Feld für den Import vorgesehen.',
    'Correspondance validée': 'Zuordnung bestätigt',
    'Correspondance enregistrée pour cette préparation d’import.\n\n': 'Zuordnung für diese Importvorbereitung gespeichert.\n\n',
    'Aucune collection n’a encore été créée ou modifiée.': 'Es wurde noch keine Sammlung erstellt oder geändert.',
    'Créer la collection G-Skol et importer': 'G-Skol-Sammlung erstellen und importieren',
    'Essai grandeur nature — création de la collection': 'Vollständiger Test — Sammlung erstellen',
    'Source : <b>{source}</b> — {rows} fiche(s), {fields} champ(s).<br><br>G-Skol va créer une <b>nouvelle collection indépendante</b>. Les numéros de fiches G-Skol seront recréés automatiquement à partir de 1 ; un éventuel N° provenant de {kind} restera une donnée utilisateur ordinaire.': 'Quelle: <b>{source}</b> — {rows} Datensatz/Datensätze, {fields} Feld(er).<br><br>G-Skol erstellt eine <b>neue unabhängige Sammlung</b>. Die G-Skol-Datensatznummern werden automatisch ab 1 neu vergeben; eine eventuell aus {kind} stammende Nummer bleibt eine gewöhnliche Benutzerdatenangabe.',
    'Nom de la nouvelle collection': 'Name der neuen Sammlung',
    'Nom de la collection :': 'Sammlungsname:',
    'Le fichier {kind} source reste strictement en lecture seule. En cas de problème, seule la nouvelle collection G-Skol créée par cet essai sera concernée.': 'Die {kind}-Quelldatei bleibt strikt schreibgeschützt. Bei einem Problem ist nur die durch diesen Test neu erstellte G-Skol-Sammlung betroffen.',
    'Créer et importer': 'Erstellen und importieren',
    'Lancer l’import réel ?': 'Tatsächlichen Import starten?',
    'les': 'die',
    'Créer la collection « {collection} » et importer {rows} fiche(s) depuis Access ?<br><br>La base Access ne sera jamais modifiée.': 'Sammlung „{collection}“ erstellen und {rows} Datensatz/Datensätze aus Access importieren?<br><br>Die Access-Datenbank wird niemals verändert.',
    'Oui': 'Ja',
    'Non': 'Nein',
    'Import en cours': 'Import läuft',
    'Import de la base « {source} » en cours…\nCréation de la collection et copie des fiches. Merci de patienter.': 'Datenbank „{source}“ wird importiert…\nSammlung wird erstellt und Datensätze werden kopiert. Bitte warten.',
    'Nom de champ en double': 'Doppelter Feldname',
    'Correspondance incomplète': 'Unvollständige Zuordnung',
    'Le nom MM3 « {target_name} » est utilisé deux fois (lignes {first} et {row}). Choisissez des noms différents.': 'Der G-Skol-Feldname „{target_name}“ wird zweimal verwendet (Zeilen {first} und {row}). Wählen Sie unterschiedliche Namen.',
    '• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• <b>Bouton On / Off</b> désigne un vrai champ à deux états à cliquer ; une liste contenant les textes Oui et Non reste une <b>Liste / Référentiel</b>.<br>• <b>Liste / Référentiel — à paramétrer</b> : le champ sera préparé comme liste ; les liaisons Maître / Relié à pourront être définies ensuite dans l’Atelier.<br>• <b>Calculé — à paramétrer</b> : le champ sera préparé comme calculé, mais sa formule devra être définie dans l’Atelier.<br>• La colonne <b>Détection G-Skol</b> indique la preuve retrouvée dans Access : relation, source de liste ou expression de calcul. Une absence de preuve est affichée « — ».<br>• Un champ source <b>N° / Numéro</b> reste toujours un champ utilisateur ordinaire : il n’a <b>aucune influence</b> sur la numérotation automatique des fiches G-Skol.': '• <b>Doppelklicken Sie auf den Namen eines G-Skol-Feldes, um ihn zu bearbeiten.</b><br>• <b>Ein/Aus-Schaltfläche</b> bezeichnet ein echtes anklickbares Zwei-Zustände-Feld; eine Liste mit den Texten Ja und Nein bleibt eine <b>Liste / Referenz</b>.<br>• <b>Liste / Referenz — zu konfigurieren</b>: Das Feld wird als Liste vorbereitet; Master-/Verknüpft-Beziehungen können anschließend in der Werkstatt definiert werden.<br>• <b>Berechnet — zu konfigurieren</b>: Das Feld wird als berechnet vorbereitet, seine Formel muss jedoch in der Werkstatt definiert werden.<br>• Die Spalte <b>G-Skol-Erkennung</b> zeigt den in Access gefundenen Nachweis: Beziehung, Listenquelle oder Berechnungsausdruck. Fehlt ein Nachweis, wird „—“ angezeigt.<br>• Ein Quellfeld <b>Nr. / Nummer</b> bleibt immer ein gewöhnliches Benutzerfeld und hat <b>keinen Einfluss</b> auf die automatische Nummerierung der G-Skol-Datensätze.',
})

DE.update({
    'Texte': 'Text',
    'Texte long': 'Langtext',
    'Entier long': 'Lange Ganzzahl',
    'Entier': 'Ganzzahl',
    'Octet': 'Byte',
    'Réel simple': 'Einfache Genauigkeit',
    'Réel double': 'Doppelte Genauigkeit',
    'Monétaire': 'Währung',
    'Décimal': 'Dezimal',
    'Date / Heure': 'Datum / Uhrzeit',
    'Oui / Non': 'Ja / Nein',
    'Binaire long': 'Langbinär',
    'Binaire': 'Binär',
    'Lien hypertexte': 'Hyperlink',
    'Pièce jointe': 'Anlage',
    'Liste / Référentiel — reconnu par G-Skol': 'Liste / Referenz — von G-Skol erkannt',
    'Liste / Référentiel': 'Liste / Referenz',
    'Photo / Image': 'Foto / Bild',
    'Lien (Internet ou autre)': 'Link (Internet oder anderer)',
    'Calculé — à paramétrer': 'Berechnet — zu konfigurieren',
    'Import terminé': 'Import abgeschlossen',
    'Import terminé avec succès.\n\n': 'Import erfolgreich abgeschlossen.\n\n',
    'Collection : {name}\n': 'Sammlung: {name}\n',
    'Fiches G-Skol créées : {count}\n': 'Erstellte G-Skol-Datensätze: {count}\n',
    'Champs importés : {count}\n': 'Importierte Felder: {count}\n',
    'Valeurs de listes simples : {count}\n': 'Werte einfacher Listen: {count}\n',
    'Référentiels tabulaires reconnus : {count}\n': 'Erkannte tabellarische Referenzen: {count}\n',
    'Liaisons Maître / Relié à créées : {count}\n': 'Erstellte Master-/Verknüpft-Beziehungen: {count}\n',
    'Valeurs reliées reportées dans les fiches : {count}\n': 'Verknüpfte Werte in Datensätze übernommen: {count}\n',
    'Ordre des fiches : {order}\n\n': 'Reihenfolge der Datensätze: {order}\n\n',
    'Diagnostic Maître/Reliés :\n': 'Master-/Verknüpft-Diagnose:\n',
    'Chronométrage diagnostic :\n': 'Diagnosezeiten:\n',
    'Détail de la lecture Access :\n': 'Details zum Lesen von Access:\n',
    'Pont Access/DAO (processus complet)': 'Access/DAO-Brücke (Gesamtprozess)',
    'dont ouverture de la base Access': 'davon Öffnen der Access-Datenbank',
    'Analyse du résultat XML': 'Analyse des XML-Ergebnisses',
    'Reconstruction des données côté G-Skol': 'Rekonstruktion der Daten in G-Skol',
    'Aucun groupe détecté': 'Keine Gruppe erkannt',
    'Table {name} : {seconds:.2f} s — {rows} ligne(s)': 'Tabelle {name}: {seconds:.2f} s — {rows} Zeile(n)',
    ' — binaires : {seconds:.2f} s / {count} objet(s) / {mb:.1f} Mo': ' — Binärdaten: {seconds:.2f} s / {count} Objekt(e) / {mb:.1f} MB',
    '   • {name} : {seconds:.2f} s — {reads} lecture(s) — type DAO {type}': '   • {name}: {seconds:.2f} s — {reads} Lesevorgang/-vorgänge — DAO-Typ {type}',
    'La nouvelle collection est désormais disponible dans la liste des collections.\nDepuis l’écran d’accueil, cliquez sur « Ouvrir une collection » pour l’ouvrir.\n\n': 'Die neue Sammlung ist jetzt in der Sammlungsliste verfügbar.\nKlicken Sie auf dem Startbildschirm auf „Sammlung öffnen“, um sie zu öffnen.\n\n',
    'Les fiches ont reçu leur propre numérotation G-Skol de 1 à {count}. Le N° Access, s’il a été conservé, reste un champ ordinaire.\n\n': 'Die Datensätze haben eine eigene G-Skol-Nummerierung von 1 bis {count} erhalten. Eine beibehaltene Access-Nr. bleibt ein gewöhnliches Feld.\n\n',
    'Source(s) Photo détectée(s) : {count}.\n': 'Erkannte Fotoquelle(n): {count}.\n',
    'Photos Access importées dans les cadres Photo G-Skol : {count}.\n': 'In G-Skol-Fotorahmen importierte Access-Fotos: {count}.\n',
    'Photos binaires non reconnues : {count}.': 'Nicht erkannte Binärfotos: {count}.',
    'Aucune donnée n’est importée ou modifiée pendant l’analyse.': 'Während der Analyse werden keine Daten importiert oder geändert.',
})


# G-Skol 1.0.251 — finitions allemandes du parcours Import Access.
DE.update({
    "Nom déjà utilisé": "Name bereits verwendet",
    "Le fichier « {name} » existe déjà dans le dossier des collections. Choisissez un autre nom.": "Die Datei „{name}“ ist im Sammlungsordner bereits vorhanden. Wählen Sie einen anderen Namen.",
    "Calculé — reconnu par G-Skol": "Berechnet — von G-Skol erkannt",
    "Calculé — reconnu par MM3": "Berechnet — von G-Skol erkannt",
    "Nombre": "Zahl",
    "Texte": "Text",
    "Monétaire": "Währung",
    "Tri Access du formulaire/requête conservé.": "Access-Sortierreihenfolge des Formulars/der Abfrage beibehalten.",
    "Préparation collection / modèle": "Vorbereitung Sammlung / Vorlage",
    "Lecture groupée Access": "Gebündeltes Lesen aus Access",
    "Création fiches + valeurs + photos": "Erstellung Datensätze + Werte + Fotos",
    "dont traitement photos": "davon Fotoverarbeitung",
    "Listes simples": "Einfache Listen",
    "Référentiels liés + report dans les fiches": "Verknüpfte Referenzlisten + Übernahme in Datensätze",
    "dont écriture tables liées": "davon Schreiben verknüpfter Tabellen",
    "dont report valeurs reliées": "davon Übernahme verknüpfter Werte",
    "La nouvelle collection est désormais disponible dans la liste des collections.\nDepuis l'écran d'accueil, cliquez sur « Ouvrir une collection » pour l'ouvrir.\n\n": "Die neue Sammlung ist jetzt in der Sammlungsliste verfügbar.\nKlicken Sie auf dem Startbildschirm auf „Sammlung öffnen“, um sie zu öffnen.\n\n",
    "Les fiches ont reçu leur propre numérotation G-Skol de 1 à {count}. Le N° Access, s'il a été conservé, reste un champ ordinaire.\n\n": "Die Datensätze haben eine eigene G-Skol-Nummerierung von 1 bis {count} erhalten. Eine beibehaltene Access-Nr. bleibt ein gewöhnliches Feld.\n\n",
})

def tr(text: str, language: str = "fr") -> str:
    lang = str(language or "fr").lower()
    if lang.startswith("en"):
        return EN.get(text, text)
    if lang.startswith("de"):
        if text in DE: return DE[text]
        # A few older screens still hand the translator an English fallback.
        # Resolve it back to the canonical French key, then into German.
        for fr_key, en_value in EN.items():
            if str(en_value) == str(text) and fr_key in DE:
                return DE[fr_key]
        return EN.get(text, text)
    return text


# G-Skol 1.0.17 — création de collection / modèles natifs.
EN.update({
    "Choisir un modèle de collection": "Choose a collection template",
    "Quel type de collection souhaitez-vous créer ?": "What type of collection would you like to create?",
    "Choisissez le modèle le plus proche de votre besoin. Une fois la collection créée, tous ses champs, cadres et photos resteront librement personnalisables dans l’Atelier.": "Choose the template closest to your needs. Once the collection is created, all its fields, frames and photos can be freely customized in the Workshop.",
    "Collection vierge": "Blank collection",
    "Construire librement votre propre modèle de fiche.": "Build your own record template freely.",
    "Minéraux": "Minerals",
    "Sables": "Sands",
    "Fossiles": "Fossils",
    "Timbres": "Stamps",
    "Cartes postales": "Postcards",
    "Monnaies - Médailles - Jetons": "Coins - Medals - Tokens",
    "Objets de collection": "Collectibles",
    "Livres - Documents": "Books - Documents",
    "Étiquettes - Documents graphiques": "Labels - Graphic documents",
    "Vierge": "Blank",
    "--- Créer un référentiel ---": "--- Create a reference list ---",
    "Minéraux / Microminéraux": "Minerals / Microminerals",
    "Espèces, cristallographie, localités, acquisition et photos.": "Species, crystallography, localities, acquisition and photos.",
    "Fossiles": "Fossils",
    "Taxonomie, âge géologique, provenance, préparation et photos.": "Taxonomy, geological age, provenance, preparation and photos.",
    "Sables": "Sands",
    "Site, localisation, identification du sable, acquisition et deux photos.": "Site, location, sand identification, acquisition and two photos.",
    "Timbres": "Stamps",
    "Pays, émission, année, valeur, série, état et catalogue.": "Country, issue, year, value, series, condition and catalogue.",
    "Cartes postales": "Postcards",
    "Lieu, éditeur, période, état, acquisition, recto et verso.": "Place, publisher, period, condition, acquisition, front and back.",
    "Monnaies / Médailles / Jetons": "Coins / Medals / Tokens",
    "Pays, valeur, date, métal, dimensions, référence, avers et revers.": "Country, value, date, metal, dimensions, reference, obverse and reverse.",
    "Objets de collection": "Collectibles",
    "Porte-clés, pin’s, fèves, figurines, capsules et autres objets.": "Key rings, pins, charms, figurines, capsules and other objects.",
    "Livres / Documents": "Books / Documents",
    "Titre, auteur, éditeur, année, édition, référence et état.": "Title, author, publisher, year, edition, reference and condition.",
    "Étiquettes / Documents graphiques": "Labels / Graphic documents",
    "Catégorie, marque, origine, période, thème, dimensions et images.": "Category, brand, origin, period, theme, dimensions and images.",
    "Modèle prévu — disponible dans une prochaine étape": "Planned template — available in a future step",
    "Suivant": "Next",
    "Collection créée": "Collection created",
    "La collection « {name} » a été créée.\n\nVous pouvez maintenant ouvrir l’atelier des fiches.": "The collection “{name}” has been created.\n\nYou can now open the Record Workshop.",
})


EN.update({
    "N°": "No.",
    "Nouvelle fiche": "New record",
    "Aucune fiche": "No record",
    "État de la fiche": "Record status", "Etat de la fiche": "Record status",
    "Minéral 2": "Mineral 2",
    "Minéral 3": "Mineral 3",
    "Classe": "Class",
    "Formule chimique": "Chemical formula",
    "Système cristallin": "Crystal system",
    "Intensité": "Intensity",
    "Couleur fluo": "Fluorescence color",
    "Lien espèce": "Species link",
    "Gisement": "Deposit",
    "Département": "Department",
    "Région": "Region",
    "Pays": "Country",
    "Catégorie": "Category",
    "Lien site": "Site link",
    "Croissance": "Growth",
    "Couleur": "Color",
    "Forme": "Shape",
    "Qualité": "Quality",
    "Grossissement mini": "Minimum magnification",
    "Origine": "Origin",
    "Lieu": "Place",
    "Contenant": "Container",
    "Nombre de pièces": "Number of pieces",
    "Non": "No",
    "Oui": "Yes",
    "Aucune": "None",
})


# G-Skol 1.0.23 — traduction centralisée des valeurs natives/référentiels.
EN.update({
    "Coût total":"Total cost","Libre":"Free","Vérifier":"Check","À vérifier":"Check",
    "Oui":"Yes","Non":"No","Aucune":"None","Inconnu":"Unknown","Inconnue":"Unknown",
    "Très faible":"Very low","Faible":"Low","Moyenne":"Medium","Forte":"Strong","Très forte":"Very strong",
    "Blanc":"White","Bleu":"Blue","Crème":"Cream","Jaune":"Yellow","Orange":"Orange","Rose":"Pink","Rouge":"Red",
    "Vert":"Green","Violet":"Violet","Multicolore":"Multicolor","Brun":"Brown","Saumon":"Salmon","Kaki":"Khaki",
    "Carrière":"Quarry","Baguette":"Rod","Tablette":"Plate","Tabulaire":"Tabular","sur Site":"On site",
    "Normale":"Normal","Épitaxie (espèces différentes)":"Epitaxy (different species)",
    "Interpénétration (espèces identiques)":"Interpenetration (identical species)",
    "Macle (accolées, mêmes espèces)":"Twin (contact, same species)","Spectre":"Spectrum","Antispectre":"Antispectrum",
    "Collecte personnelle":"Personal collection","Achat":"Purchase","Échange":"Exchange","Cadeau":"Gift",
    "Amorphe":"Amorphous","Cubique":"Cubic","Orthorhombique":"Orthorhombic","Tétragonal":"Tetragonal",
    "Triclinique":"Triclinic","Monoclinique":"Monoclinic","Rhomboédrique":"Rhombohedral","Isométrique":"Isometric",
    "Fluorescent":"Fluorescent","Phosphorescence":"Phosphorescence","Fluorescence (UV 365 Nm)":"Fluorescence (UV 365 nm)",
    "Éléments natifs":"Native elements","Halogénures":"Halides","Organique":"Organic",
    "Oxydes, Hydroxydes":"Oxides, Hydroxides","Phosphates, Arséniates, Vanadates":"Phosphates, Arsenates, Vanadates",
    "Sulfures":"Sulfides","Sulfures, Sulfosels":"Sulfides, Sulfosalts",
    "Ouvrir une collection":"Open a collection","Choisissez une collection à ouvrir":"Choose a collection to open",
    "Propriétaire":"Owner","Créée le":"Created on","Ouvrir":"Open","Renommer…":"Rename…","Dupliquer…":"Duplicate…",
    "Supprimer…":"Delete…","Nouveau dossier…":"New folder…","Déplacer vers…":"Move to…","Parcourir…":"Browse…","Fermer":"Close",
    "Collections (racine)":"Collections (root)","Modifier les informations":"Edit information",
    "Propriétaire…":"Owner…","Date de création…":"Creation date…","Description…":"Description…",
    "Nouvelle collection — Informations":"New collection — Information","Nom :":"Name:","Propriétaire :":"Owner:","Description :":"Description:",
    "Créer":"Create",
    "Requête multicritère":"Multicriteria query","Constructeur de requête multicritère":"Multicriteria query builder",
    "Nouvelle requête":"New query","Modèle actif":"Active template","Requête enregistrée :":"Saved query:",
    "Enregistrer la requête…":"Save query…","Ouvrir un modèle…":"Open a template…","Enregistrer ce modèle":"Save this template",
    "Mettre à jour":"Update","Renommer…":"Rename…","Dupliquer…":"Duplicate…","Supprimer…":"Delete…","Dossiers…":"Folders…",
    "Mode de classement :":"Sort mode:","Alphabétique":"Alphabetical","Lien":"Link","Champ":"Field","Comparaison":"Comparison","Valeur":"Value",
    "ET":"AND","OU":"OR","Contient":"Contains","Tous":"All","Commence par":"Starts with","Est exactement":"Is exactly",
    "Est différent de":"Is different from","Se termine par":"Ends with","Est vide":"Is empty","N’est pas vide":"Is not empty",
    "Égal à":"Equals","Différent de":"Different from","Supérieur à":"Greater than","Supérieur ou égal à":"Greater than or equal to",
    "Inférieur à":"Less than","Inférieur ou égal à":"Less than or equal to","Compris entre":"Between",
    "Égal au":"Equals","Différent du":"Different from","Après le":"After","À partir du":"On or after","Avant le":"Before",
    "Jusqu’au":"On or before","Année entière":"Whole year","+ Ajouter un critère":"+ Add criterion","Supprimer":"Delete",
    "Réinitialiser la requête":"Reset query","Exécuter la requête":"Run query","Aucune requête exécutée.":"No query run.",
    "Valeur recherchée…":"Search value…","Aucune valeur nécessaire":"No value needed","Date début…":"Start date…","Date fin…":"End date…",
    "Minimum…":"Minimum…","Maximum…":"Maximum…","Nombre…":"Number…","Date…":"Date…","Et…":"And…",
    "Vue Tableau":"Table view","Choisir les colonnes…":"Choose columns…","Mise en page…":"Page setup…","Imprimer":"Print",
    "Afficher toutes les fiches":"Show all records","Enregistrer la vue…":"Save view…","Ajouter ce filtre":"Add this filter",
    "Effacer les filtres":"Clear filters","Ouvrir la fiche":"Open record","Retour":"Back","Vider":"Clear","Copier la fiche":"Copy record",
    "Coller la fiche":"Paste record","Défaire":"Undo","Refaire":"Redo",
    "Mise à jour des référentiels":"Update reference lists","Ajouter tout":"Add all","Ne rien ajouter":"Add nothing","Afficher les détails":"Show details",
    "Une ligne = une fiche. Cliquez sur un titre pour trier, déplacez ou redimensionnez les colonnes à la souris.":"One row = one record. Click a heading to sort; drag or resize columns with the mouse.",
    "Modèle actif : Vue actuelle":"Active template: Current view",
    "Vue :":"View:","— Vue actuelle —":"— Current view —","Vue actuelle":"Current view",
    "Filtrer :":"Filter:","Tapez une valeur…":"Type a value…","Et…":"And…",
    "Aucun filtre actif":"No active filter",
    "Aucun filtre épinglé — la saisie ci-dessus filtre immédiatement le tableau.":"No pinned filter — the entry above filters the table immediately.",
    "Tri : cliquez sur l'en-tête d'une colonne":"Sort: click a column heading",
    "Double-cliquez une cellule pour la corriger ; N° ouvre la fiche. Flèche BAS valide et passe à la cellule suivante.":"Double-click a cell to edit it; No. opens the record. DOWN ARROW confirms and moves to the next cell.",
    "Tous":"All","Aucune valeur nécessaire":"No value required",
    "Modifications non enregistrées":"Unsaved changes",
    "Cette vue n’a pas encore été enregistrée.":"This view has not been saved yet.",
    "Voulez-vous l’enregistrer avant de quitter ?":"Do you want to save it before leaving?",
    "Voulez-vous enregistrer ces modifications avant de quitter ?":"Do you want to save these changes before leaving?",
    "Enregistrer":"Save","Enregistrer sous…":"Save as…","Ne pas enregistrer":"Don't save",
    "Vider les fiches":"Clear records","Suppression définitive":"Permanent deletion",
    "États":"Reports",
    "Créer et consulter les présentations de la collection : détail des fiches ou synthèse par regroupement.":"Create and view collection reports: individual records or grouped summaries.",
    "Consulter les états enregistrés ou créer une présentation détaillée ou résumée de la collection.":"View saved reports or create a detailed or summary presentation of the collection.",
    "Quel type d’état souhaitez-vous créer ?":"What type of report would you like to create?",
    "État détaillé":"Detailed report",
    "Afficher les fiches une par une, avec les champs choisis.":"Display records one by one, with the selected fields.",
    "État résumé":"Summary report",
    "Regrouper les fiches et afficher uniquement les totaux ou synthèses.":"Group records and display totals or summaries only.",
    "Créer":"Create",
    "États enregistrés":"Saved reports",
    "États détaillés":"Detailed reports",
    "États résumés":"Summary reports",
    "Lignes alternées grisées": "Alternating shaded rows",
    "Bandeau des totaux grisé": "Shaded totals band",
    "En-têtes de colonnes grisés": "Shaded column headers",
    "Griser les en-têtes de colonnes dans l’aperçu et à l’impression": "Shade column headers in preview and print",
    "Afficher ou masquer le fond grisé du bandeau des totaux": "Show or hide the shaded background of the totals band",
    "Afficher ou masquer le grisé d’une ligne de données sur deux": "Show or hide shading on alternating data rows",
    "Griser une ligne de données sur deux dans l’aperçu et à l’impression": "Shade alternating data rows in preview and print",
    "Ouvrir":"Open",
    "Ouvrir un modèle d’État…":"Open a report template…",
    "Modifier":"Edit",
    "Renommer":"Rename",
    "Dupliquer":"Duplicate",
    "Supprimer":"Delete",
    "Dossiers…":"Folders…",
    "Nouveau modèle d’État":"New report template",
    "Modèle":"Template",
    "Construction de l'état résumé":"Summary report layout",
    "Construction de l'état détaillé":"Detailed report layout",
    "Vider la construction":"Clear layout",
    "Source :":"Source:",
    "Toute la collection":"Entire collection",
    "Requête enregistrée :":"Saved query:",
    "Orientation :":"Orientation:",
    "Portrait":"Portrait","Paysage":"Landscape",
    "Glisser un champ vers la construction":"Drag a field to the layout",
    "Total":"Total",
    "Construction de l’état résumé":"Summary report layout",
    "Titre de l'État :":"Report title:",
    "Bandeau :":"Header:",
    "En-tête colonnes :":"Column headers:",
    "Champ maître :":"Master field:",
    "Champs liés :":"Linked fields:",
    "Pied de page :":"Footer:",
    "Haut":"Top","Centré":"Centered","Bas":"Bottom",
    "Éléments de construction":"Layout elements",
    "+ Interligne":"+ Spacing","+ Filet":"+ Rule",
    "N° de page :":"Page number:",
    "Insérer un interligne":"Insert spacing", "Insérer un filet":"Insert a rule",
    "Interligne":"Spacing", "Filet":"Rule",
    "Emplacement :":"Position:", "Hauteur :":"Height:", "Épaisseur :":"Thickness:", "Couleur :":"Color:",
    "Fin":"Thin", "Couleur du filet":"Rule color",
    "Sous le titre":"Below title", "Sous le bandeau":"Below header",
    "Entre les champs maîtres":"Between master fields",
    "Sous les en-têtes de colonnes":"Below column headers",
    "Sous le libellé des colonnes":"Below column labels",
    "Entre les lignes de données":"Between data rows",
    "Entre les données et le filet du pied de page":"Between data and footer rule",
    "Avant le pied de page":"Before footer",
    "Modifier interligne…":"Edit spacing…", "Supprimer interligne":"Delete spacing",
    "Modifier filet…":"Edit rule…", "Supprimer filet":"Delete rule",
    "Retour":"Back","Défaire":"Undo","Refaire":"Redo",
    "Sauvegarder":"Save","Ouvrir un modèle…":"Open a template…",
    "Couleur de fond :":"Background color:",
    "Couleur de fond de l’en-tête":"Column header background color",
    "Position sur la ligne (tous les champs) :":"Position on row (all fields):",
    "Format de date :":"Date format:", "Regroupement date :":"Date grouping:",
    "Numérotation des pages":"Page numbering", "Présentation :":"Display:", "Position :":"Position:",
    "Enregistrer ce modèle":"Save this template",
    "Aperçu":"Preview","Imprimer":"Print","Imprimer le titre":"Print title",
    "Consulter l’état sélectionné":"View the selected report",
    "Ouvrir l’état sélectionné dans son constructeur":"Open the selected report in its builder",
    "Charger un modèle depuis la bibliothèque Modèles d’États":"Load a template from the Report Templates library",
    "Paramètres de G-Skol":"G-Skol settings",
    "Choisissez un champ : G-Skol adapte automatiquement les comparaisons possibles. À partir de la deuxième ligne, utilisez ET pour restreindre le résultat ou OU pour l’élargir.":"Choose a field: G-Skol automatically adapts the available comparisons. From the second row onward, use AND to narrow the result or OR to broaden it.",
    "Valeur recherchée…":"Search value…",
    "Lien":"Link","Champ":"Field","Comparaison":"Comparison","Valeur":"Value",
    "Paramètres généraux — G-Skol":"General settings — G-Skol",
    "Rouvrir la dernière collection au démarrage":"Reopen the last collection at startup",
    "Paramètres de la collection ouverte — Aucune collection ouverte":"Open collection settings — No collection open",
    "Aucune collection ouverte. Ses réglages apparaîtront ici après ouverture.":"No collection is open. Its settings will appear here after it is opened.",
    "Annuler":"Cancel","Enregistrer":"Save",
    "Nom :":"Name:",
    "Le nom et le dossier se modifient depuis « Ouvrir une collection ».":"The name and folder can be changed from “Open a collection”.",
    "Couleur de la fiche et de la collection :":"Record and collection color:",
    "Choisir la couleur…":"Choose color…","Couleur de la collection":"Collection color",
    "À l’ouverture de la Fiche :":"When opening Records:",
    "Dernière fiche consultée":"Last viewed record","Première fiche":"First record",
    "Vidage impossible":"Unable to clear","Suppression impossible":"Unable to delete",
    "Oui":"Yes","Non":"No",
})

EN.update({
    "Supprimer la collection":"Delete collection",
    "Supprimer définitivement la collection":"Permanently delete collection",
    "SUPPRIMER":"DELETE",
    "Annuler":"Cancel",
    "Créer":"Create",
    "Nouvelle collection — Informations":"New collection — Information",
    "Nom :":"Name:",
    "Propriétaire :":"Owner:",
    "Description :":"Description:",
    "Coût total":"Total cost",
    "Epitaxie (espèces différentes)":"Epitaxy (different species)",
    "Macle (accolement mêmes espèces)":"Twin (contact, same species)",
    "Sceptre":"Scepter",
    "Antisceptre":"Antiscepter",
    "Eléments natifs":"Native elements",
    "Rhombohedrique":"Rhombohedral",
    "Rhomboèdrique":"Rhombohedral",
    "Tetragonal":"Tetragonal",
    "Trigonal":"Trigonal",
    "Hexagonal":"Hexagonal",
    "Mine":"Mine",
    "Haldes":"Mine dumps",
    "Fluorescence (UV 365 Nm)":"Fluorescence (UV 365 nm)",
    "Des valeurs présentes dans les fiches ne figurent pas encore dans les référentiels de « {name} ».":"Values present in records are not yet in the reference lists of “{name}”.",
    "Voulez-vous mettre automatiquement à jour les référentiels de cette collection ?":"Do you want to update this collection's reference lists automatically?",
    "Annuler la fermeture de la collection {name}":"Cancel closing collection {name}",
    "Mise à jour impossible":"Update failed",
    "Les référentiels n'ont pas pu être mis à jour.":"The reference lists could not be updated.",
    "Nouvel état de fiche":"New record status",
    "La valeur « {value} » n'existe pas encore dans le référentiel.":"The value “{value}” is not yet in the reference list.",
    "Voulez-vous l'ajouter à la liste des états de fiche ?":"Do you want to add it to the record status list?",
    "OUI":"YES",
    "NON":"NO",
    "Supprimer définitivement la collection « {name} » ?":"Permanently delete collection “{name}”?",
    "Toutes les fiches et tous les référentiels de cette collection seront supprimés.\nCette opération est irréversible.":"All records and reference lists in this collection will be deleted.\nThis operation cannot be undone.",
})


# G-Skol 1.0.276 — valeurs natives canoniques allemandes (sans repli anglais).
_DE_NATIVE_VALUES = {'Aucune': 'Keine', 'Inconnu': 'Unbekannt', 'Inconnue': 'Unbekannt', 'Très faible': 'Sehr schwach', 'Faible': 'Schwach', 'Moyenne': 'Mittel', 'Forte': 'Stark', 'Très forte': 'Sehr stark', 'Blanc': 'Weiß', 'Bleu': 'Blau', 'Crème': 'Creme', 'Jaune': 'Gelb', 'Orange': 'Orange', 'Rose': 'Rosa', 'Rouge': 'Rot', 'Vert': 'Grün', 'Violet': 'Violett', 'Multicolore': 'Mehrfarbig', 'Brun': 'Braun', 'Saumon': 'Lachsrosa', 'Kaki': 'Khaki', 'Oui': 'Ja', 'Non': 'Nein', 'Libre': 'Frei', 'Vérifier': 'Prüfen', 'À vérifier': 'Prüfen', 'Carrière': 'Steinbruch', 'Baguette': 'Stab', 'Tablette': 'Plättchen', 'Tabulaire': 'Tafelig', 'sur Site': 'Vor Ort', 'Normale': 'Normal', 'Épitaxie (espèces différentes)': 'Epitaxie (verschiedene Arten)', 'Interpénétration (espèces identiques)': 'Durchdringung (gleiche Arten)', 'Macle (accolées, mêmes espèces)': 'Kontaktzwilling (gleiche Art)', 'Spectre': 'Szepter', 'Antispectre': 'Antiszepter', 'Collecte personnelle': 'Eigener Fund', 'Achat': 'Kauf', 'Échange': 'Tausch', 'Cadeau': 'Geschenk', 'Amorphe': 'Amorph', 'Cubique': 'Kubisch', 'Orthorhombique': 'Orthorhombisch', 'Tétragonal': 'Tetragonal', 'Triclinique': 'Triklin', 'Monoclinique': 'Monoklin', 'Rhomboédrique': 'Rhomboedrisch', 'Isométrique': 'Isometrisch', 'Éléments natifs': 'Gediegene Elemente', 'Halogénures': 'Halogenide', 'Organique': 'Organisch', 'Oxydes, Hydroxydes': 'Oxide, Hydroxide', 'Phosphates, Arséniates, Vanadates': 'Phosphate, Arsenate, Vanadate', 'Sulfures': 'Sulfide', 'Sulfures, Sulfosels': 'Sulfide, Sulfosalze'}

_EN_CANONICAL={str(v).casefold():str(k) for k,v in EN.items() if str(v) and str(k)!=str(v)}
# Priorités canoniques pour les valeurs métier natives utilisées dans les données
# et dans les critères de requête. Elles évitent les collisions avec les libellés UI.
_EN_CANONICAL.update({
    "yes":"Oui", "no":"Non", "free":"Libre", "check":"Vérifier", "to check":"Vérifier",
    "oxides, hydroxides":"Oxydes, Hydroxydes",
    "native elements":"Éléments natifs",
    "halides":"Halogénures",
    "organic":"Organique",
    "phosphates, arsenates, vanadates":"Phosphates, Arséniates, Vanadates",
    "sulfides":"Sulfures",
    "sulfides, sulfosalts":"Sulfures, Sulfosels",
    "amorphous":"Amorphe", "cubic":"Cubique", "orthorhombic":"Orthorhombique",
    "tetragonal":"Tétragonal", "triclinic":"Triclinique", "monoclinic":"Monoclinique",
    "rhombohedral":"Rhomboédrique", "isometric":"Isométrique",
})
_EN_CANONICAL.update({"free":"Libre","check":"Vérifier","to check":"Vérifier"})
_TOKENS=(("Orthorhombique","Orthorhombic"),("Monoclinique","Monoclinic"),("Rhomboédrique","Rhombohedral"),
         ("Tétragonal","Tetragonal"),("Triclinique","Triclinic"),("Cubique","Cubic"),("Amorphe","Amorphous"),
         ("Isométrique","Isometric"),("Inconnu","Unknown"))

# G-Skol 1.0.277 — compléments des valeurs natives (affichage uniquement).
# Les clés sont les valeurs canoniques historiques stockées dans les collections.
EN.update({
    "Non": "No",
    "Fluorescent": "Fluorescent",
    "Phosphorescence": "Phosphorescence",
    "Fluorescence (UV 365 Nm)": "Fluorescence (UV 365 nm)",
    "Normale": "Normal",
    "Épitaxie (espèces différentes)": "Epitaxy (different species)",
    "Interpénétration (espèces identiques)": "Interpenetration (identical species)",
    "Macle (accolées, mêmes espèces)": "Contact twin (same species)",
    "Spectre": "Scepter",
    "Antispectre": "Antiscepter",
})
_DE_NATIVE_VALUES.update({
    "Non": "Nein",
    "Fluorescent": "Fluoreszierend",
    "Phosphorescence": "Phosphoreszenz",
    "Fluorescence (UV 365 Nm)": "Fluoreszenz (UV 365 nm)",
    "Normale": "Normal",
    "Épitaxie (espèces différentes)": "Epitaxie (verschiedene Arten)",
    "Interpénétration (espèces identiques)": "Durchdringung (gleiche Arten)",
    "Macle (accolées, mêmes espèces)": "Kontaktzwilling (gleiche Art)",
    "Spectre": "Szepter",
    "Antispectre": "Antiszepter",
})

# G-Skol 1.0.278 — graphies canoniques réellement utilisées par le modèle Minéraux.
_DE_NATIVE_VALUES.update({'Epitaxie (espèces différentes)': 'Epitaxie (verschiedene Arten)', 'Macle (accolement mêmes espèces)': 'Kontaktzwilling (gleiche Art)', 'Sceptre': 'Szepter', 'Antisceptre': 'Antiszepter', 'Interpénétration (même espèce)': 'Durchdringung (gleiche Art)', 'Interpénétration (mêmes espèces)': 'Durchdringung (gleiche Arten)'})

def display_native_value(value:str, language:str="fr")->str:
    text=str(value or "")
    if text in {"À vérifier", "A vérifier", "Valider"}: text = "Vérifier"
    lang = str(language or "fr").lower()
    if lang.startswith("de"):
        return str(_DE_NATIVE_VALUES.get(text, DE.get(text, text)))
    if not lang.startswith("en"): return text
    if text in EN: return str(EN[text])
    out=text
    for fr,en in _TOKENS: out=out.replace(fr,en)
    return out
def canonical_native_value(value:str, language:str="fr")->str:
    text=str(value or "").strip()
    if text in {"À vérifier", "A vérifier", "Valider"}: return "Vérifier"
    lang = str(language or "fr").lower()
    if lang.startswith("de"):
        de_reverse = {str(v).casefold(): str(k) for k,v in DE.items() if str(v) and str(k) != str(v)}
        de_reverse.update({str(v).casefold(): str(k) for k,v in _DE_NATIVE_VALUES.items()})
        return de_reverse.get(text.casefold(), text)
    if not lang.startswith("en"): return text
    direct=_EN_CANONICAL.get(text.casefold())
    if direct is not None: return direct
    out=text
    for fr,en in _TOKENS: out=out.replace(en,fr)
    return out
def translate_widget_tree(root, language:str="fr"):
    lang = str(language or "fr").lower()
    if lang.startswith("fr"): return
    try:
        from PySide6.QtWidgets import QLabel,QPushButton,QGroupBox,QCheckBox,QRadioButton,QComboBox,QTabWidget,QTreeWidget
        if hasattr(root, "windowTitle") and hasattr(root, "setWindowTitle"):
            old = str(root.windowTitle() or ""); new = tr(old, language)
            if new != old: root.setWindowTitle(new)
        widgets = [root]
        for cls in (QLabel, QPushButton, QGroupBox, QCheckBox, QRadioButton): widgets.extend(root.findChildren(cls))
        seen=set()
        for w in widgets:
            if id(w) in seen: continue
            seen.add(id(w))
            if hasattr(w,"text"):
                old=str(w.text()); new=tr(old,language)
                if new!=old: w.setText(new)
            if hasattr(w,"toolTip") and hasattr(w,"setToolTip"):
                old=str(w.toolTip() or ""); new=tr(old,language)
                if new!=old: w.setToolTip(new)
        for c in root.findChildren(QComboBox):
            for i in range(c.count()):
                old=str(c.itemText(i)); new=tr(old,language)
                if new!=old: c.setItemText(i,new)
        for tabs in root.findChildren(QTabWidget):
            for i in range(tabs.count()):
                old=str(tabs.tabText(i)); new=tr(old,language)
                if new!=old: tabs.setTabText(i,new)
        for tree in root.findChildren(QTreeWidget):
            h=tree.headerItem()
            if h:
                for i in range(h.columnCount()):
                    old=str(h.text(i)); new=tr(old,language)
                    if new!=old: h.setText(i,new)
    except Exception:
        pass


# G-Skol 1.0.147 — État détaillé : constructeur et aperçu anglais.
EN.update({
    "Libellés de colonne :": "Column labels:",
    "Totaux par valeur maître :": "Totals per master value:",
    "Ajouter un total ▾": "Add a total ▾",
    "Champs complémentaires :": "Additional fields:",
    "Ces totaux sont recalculés séparément pour chaque valeur du champ maître.": "These totals are recalculated separately for each master-field value.",
    "Sauvegarder l’état": "Save report",
    "Nom de l’état :": "Report name:",
    "Trier les groupes :": "Sort groups:",
    "Niveau": "Level",
    "Croissant": "Ascending",
    "Décroissant": "Descending",
    "(vide)": "(empty)",
    "Regroupement :": "Grouping:",
})
EN.update({
    "Aperçu groupé": "Grouped preview",
    "boîte(s)": "box(es)",
    "espèce(s)": "species",
    "Les en-têtes de groupe affichent le nombre de pièces et d’espèces. Les colonnes de détail restent déplaçables et redimensionnables.": "Group headers show the number of pieces and species. Detail columns can still be moved and resized.",
})

# G-Skol 1.0.148 — fin de traduction des commandes de l'état détaillé.
EN.update({
    "Enregistrer les modifications": "Save changes",
    "L’état a été modifié.": "The report has been modified.",
    "Nom de l’état :": "Report name:",
    "Enregistrer les modifications ?": "Save changes?",
    "Oui": "Yes",
    "Non": "No",
    "Annuler": "Cancel",
    "Mise en forme…": "Formatting…",
    "Rétablir la mise en forme par défaut": "Restore default formatting",
    "Retirer de la construction": "Remove from layout",
    "Rétablir la mise en forme de l’en-tête": "Restore default header formatting",
    "Masquer l’en-tête de colonne": "Hide column header",
    "Couleur du texte": "Text color",
    "Couleur du fond": "Background color",
    "Totaux par valeur maître :": "Totals per master value:",
    "Ajouter un total ▾": "Add a total ▾",
    "Champs complémentaires :": "Additional fields:",
})

EN.update({
    "Retirer le champ de la construction": "Remove field from layout",
})

EN.update({
    "Enregistrer l’état": "Save report",
    "Sauvegarder l’état": "Save report",
})

# G-Skol 1.0.168 — Boîte à outils / Toolbox.
EN.update({
    "Ces outils agissent volontairement sur l’ensemble de la collection. G-Skol indique toujours le nombre de fiches concernées avant toute modification.": "These tools deliberately affect the entire collection. G-Skol always shows how many records will be affected before any change is made.",
    "Remplacer une valeur dans toute la collection": "Replace a value throughout the collection",
    "Valeur à remplacer :": "Value to replace:",
    "Nouvelle valeur :": "New value:",
    "Résultat :": "Result:",
    "0 fiche concernée": "0 records affected",
    "{count} fiche(s) concernée(s)": "{count} record(s) affected",
    "Le remplacement porte sur la valeur complète du champ, et non sur une partie du texte.": "The replacement applies to the entire field value, not part of the text.",
    "Défaire": "Undo",
    "Remplacer": "Replace",
    "Compléter les champs vides": "Fill empty fields",
    "Valeur à inscrire :": "Value to enter:",
    "Seules les fiches dont ce champ est vide seront complétées. Les valeurs déjà présentes ne seront jamais modifiées.": "Only records where this field is empty will be filled. Existing values will never be changed.",
    "Compléter": "Fill",
    "Dupliquer la structure de la collection": "Duplicate the collection structure",
    "Crée une collection sœur vide, identique à celle-ci. La Fiche, les paramètres et les référentiels sont conservés, mais les fiches, leurs données et leurs photos ne sont pas copiées. La première fiche créée portera le N° 1.": "Creates an empty sister collection identical to this one. The Record layout, settings and reference lists are kept, but records, their data and photos are not copied. The first record created will be No. 1.",
    "Dupliquer la structure de cette collection": "Duplicate this collection structure",
    "Remplacement": "Replacement",
    "Aucune fiche ne contient cette valeur.": "No record contains this value.",
    "L’ancienne et la nouvelle valeur sont identiques.": "The old and new values are identical.",
    "Confirmer le remplacement": "Confirm replacement",
    "Oui": "Yes", "Non": "No",
    "Champ : {label}\n\n« {old} » sera remplacé par « {new} » dans {count} fiche(s).\n\nVoulez-vous effectuer ce remplacement ?": "Field: {label}\n\n‘{old}’ will be replaced with ‘{new}’ in {count} record(s).\n\nDo you want to perform this replacement?",
    "Remplacement effectué": "Replacement completed",
    "{count} fiche(s) modifiée(s).": "{count} record(s) modified.",
    "Indiquez la valeur à inscrire.": "Enter the value to use.",
    "Aucune fiche ne possède ce champ vide.": "No record has this field empty.",
    "Confirmer le complément": "Confirm fill",
    "Champ : {label}\n\nLa valeur « {value} » sera inscrite uniquement dans {count} fiche(s) où ce champ est vide.\n\nLes fiches déjà renseignées resteront intactes. Voulez-vous continuer ?": "Field: {label}\n\nThe value ‘{value}’ will be entered only in the {count} record(s) where this field is empty.\n\nRecords that already contain a value will remain unchanged. Do you want to continue?",
    "Champs complétés": "Fields filled",
    "{count} fiche(s) complétée(s).": "{count} record(s) filled.",
    "Le dernier complément de champs vides a été annulé.": "The last fill-empty-fields operation has been undone.",
    "{name} - Copie vierge": "{name} - Blank copy",
    "Dupliquer la structure": "Duplicate structure",
    "Nom de la nouvelle collection :": "New collection name:",
    "Le nom de la nouvelle collection est obligatoire.": "The new collection name is required.",
    "Le fichier de la nouvelle collection n'a pas pu être identifié.": "The new collection file could not be identified.",
    "La collection sœur n'a pas pu être créée.\n\n{error}": "The sister collection could not be created.\n\n{error}",
    "Collection sœur créée": "Sister collection created",
    "La collection « {name} » a été créée.\n\nElle conserve la Fiche, ses réglages et les référentiels, mais ne contient aucune fiche. La première fiche créée portera le N° 1.": "The collection ‘{name}’ has been created.\n\nIt keeps the Record layout, its settings and reference lists, but contains no records. The first record created will be No. 1.",
    "Vider la collection": "Empty collection",
    "Vider complètement la collection": "Empty the collection completely",
    '<div align="center"><span style="color:#c00000; font-size:18px; font-weight:700;">ATTENTION</span></div><p><b>Toute cette collection va être entièrement vidée.</b></p><p>{count} fiche(s) ainsi que leurs données et leurs photos seront définitivement supprimées.</p><p>La structure de la Fiche, sa présentation et les référentiels seront conservés.<br>La prochaine fiche créée portera le <b>N° 1</b>.</p><p><b>Travaillez de préférence sur une copie de votre collection ou sur une collection préalablement dupliquée.</b></p>': '<div align="center"><span style="color:#c00000; font-size:18px; font-weight:700;">WARNING</span></div><p><b>This entire collection will be completely emptied.</b></p><p>{count} record(s), together with their data and photos, will be permanently deleted.</p><p>The Record structure, its layout and the reference lists will be kept.<br>The next record created will be <b>No. 1</b>.</p><p><b>Preferably work on a copy of your collection or on a previously duplicated collection.</b></p>',
    "La collection n'a pas pu être vidée.\n\n{error}": "The collection could not be emptied.\n\n{error}",
    "Collection vidée": "Collection emptied",
    "{count} fiche(s) supprimée(s).\n\nLa structure et les référentiels ont été conservés. La prochaine fiche créée portera le N° 1.": "{count} record(s) deleted.\n\nThe structure and reference lists have been kept. The next record created will be No. 1.",
    "Le dernier remplacement a été annulé.": "The last replacement has been undone.",
})

# G-Skol 1.0.171 — Import / first three screens + Access landing panel.
EN.update({
    "Import / Export / Sauvegarde": "Import / Export / Backup",
    "Que voulez-vous faire ? Choisissez d’abord une famille d’opérations. G-Skol vous proposera ensuite les traitements correspondants.": "What would you like to do? First choose an operation category. G-Skol will then show the corresponding options.",
    "Importation": "Import",
    "Exportation": "Export",
    "Sauvegarde / Restauration": "Backup / Restore",
    "Créer ou enrichir une collection à partir de sources extérieures.": "Create or enrich a collection from external sources.",
    "Exporter une collection ou des modèles G-Skol.": "Export a collection or G-Skol templates.",
    "Sauvegarder l’environnement G-Skol ou restaurer une sauvegarde.": "Back up the G-Skol environment or restore a backup.",
    "Choisissez le type d’importation. G-Skol vous guidera ensuite étape par étape dans le module correspondant.": "Choose the type of import. G-Skol will then guide you step by step through the corresponding module.",
    "Importation et création d’une collection": "Import and create a collection",
    "Créer une nouvelle collection G-Skol depuis une source extérieure.": "Create a new G-Skol collection from an external source.",
    "Importation de référentiels dans une collection existante": "Import reference lists into an existing collection",
    "Ajouter, compléter ou créer des référentiels dans une collection existante.": "Add, complete or create reference lists in an existing collection.",
    "Ajouter des fiches depuis une source extérieure": "Add records from an external source",
    "Ajouter de nouvelles fiches à la suite d’une collection existante sans modifier les fiches déjà présentes.": "Add new records to an existing collection without modifying existing records.",
    "Importer un modèle G-Skol  (.colmod)": "Import a G-Skol template (.colmod)",
    "Enregistrer dans la bibliothèque un modèle de Fiche ou de Tableau reçu d’un autre utilisateur, sans modifier de collection.": "Save a Record or Table template received from another user to the library without modifying any collection.",
    "Retour": "Back",
    "Créez une nouvelle collection G-Skol à partir d’une source externe. Choisissez d’abord le format ; G-Skol analyse ensuite la source avant toute création.": "Create a new G-Skol collection from an external source. First choose the format; G-Skol will then analyze the source before creating anything.",
    "Choisissez une base .accdb ou .mdb. G-Skol peut maintenant en examiner la structure sans importer ni modifier aucune donnée.": "Choose an .accdb or .mdb database. G-Skol can examine its structure without importing or modifying any data.",
    "Choisir une base Access…": "Choose an Access database…",
    "Analyser la base": "Analyze database",
    "Aucun fichier Access sélectionné.": "No Access file selected.",
    "Après analyse, les tables et leurs champs apparaîtront ci-dessous.": "After analysis, the tables and their fields will appear below.",
    "Table / Champ": "Table / Field",
    "Type": "Type",
    "Lignes": "Rows",
    "Choisir cette table": "Choose this table",
    "Aperçu des données…": "Data preview…",
    "Correspondance des champs…": "Field mapping…",
    "Sélectionnez une table dans la liste ci-dessus. Les lignes de champs ne sont pas sélectionnables comme source.": "Select a table from the list above. Field rows cannot be selected as the source.",
    "Après validation de la table source, l’étape suivante préparera la correspondance entre les champs Access et les champs G-Skol.": "After confirming the source table, the next step will prepare the mapping between Access fields and G-Skol fields.",
    "Créer la collection G-Skol et importer…": "Create the G-Skol collection and import…",
})

# G-Skol 1.0.172 — parcours complet d'import Microsoft Access.
EN.update({
    "Lancer l’import réel ?": "Start the actual import?",
    "Oui": "Yes", "Non": "No", "les": "the",
    "Créer la collection G-Skol et importer": "Create the G-Skol collection and import",
    "Essai grandeur nature — création de la collection": "Full-scale test — create the collection",
    "Nom de la nouvelle collection": "New collection name",
    "Nom de la collection :": "Collection name:",
    "Créer et importer": "Create and import",
    "Correspondance des champs {source} → G-Skol": "{source} field mapping → G-Skol",
    "Action": "Action", "Champ {source}": "{source} field", "Type {source}": "{source} type",
    "Champ G-Skol": "G-Skol field", "Type G-Skol": "G-Skol type", "Détection G-Skol": "G-Skol detection",
    "Tout importer": "Import all", "Tout ignorer": "Ignore all",
    "Réinitialiser les propositions": "Reset suggestions",
    "Aperçu des données — fenêtre flottante": "Data preview — floating window",
    "Valider la correspondance": "Confirm mapping",
    "Importer": "Import", "Ignorer": "Ignore",
    "Texte": "Text", "Nombre": "Number", "Monétaire": "Currency", "Date": "Date",
    "Bouton On / Off": "On / Off button", "Lien (Internet ou autre)": "Link (Internet or other)",
    "Photo / Image": "Photo / Image",
    "Liste / Référentiel — reconnu par G-Skol": "List / Reference — recognized by G-Skol",
    "Liste / Référentiel — probable / à vérifier": "List / Reference — probable / check",
    "Liste / Référentiel — à paramétrer": "List / Reference — to configure",
    "Calculé — reconnu par G-Skol": "Calculated — recognized by G-Skol",
    "Calculé — probable / à vérifier": "Calculated — probable / check",
    "Calculé — à paramétrer": "Calculated — to configure",
    "Aperçu des données — {table}": "Data preview — {table}",
    "Aperçu des données — <b>{table}</b>": "Data preview — <b>{table}</b>",
    "Fermer": "Close", "Annuler": "Cancel",
    "Choisir une base Microsoft Access": "Choose a Microsoft Access database",
    "Bases Microsoft Access (*.accdb *.mdb);;Tous les fichiers (*.*)": "Microsoft Access databases (*.accdb *.mdb);;All files (*.*)",
    "Le fichier choisi n’est pas une base Access .accdb ou .mdb.": "The selected file is not an Access .accdb or .mdb database.",
    "Base sélectionnée. Cliquez sur « Analyser la base » pour afficher sa structure.": "Database selected. Click ‘Analyze database’ to display its structure.",
    "Aucune donnée n’est importée ou modifiée pendant l’analyse.": "No data is imported or modified during analysis.",
    "La base Access sélectionnée est introuvable.": "The selected Access database cannot be found.",
    "Analyse de la base Access en cours…": "Analyzing the Access database…",
    "L’analyse n’a pas pu être effectuée.": "The analysis could not be completed.",
    "Analyse Access impossible": "Access analysis failed",
    "Analyse terminée : aucune table de données n’a été trouvée.": "Analysis complete: no data table was found.",
    "nombre inconnu de": "unknown number of",
    "Table source retenue": "Source table selected",
    "La table « {name} » a été retenue comme table des fiches à importer.\n\n": "The table ‘{name}’ has been selected as the table containing the records to import.\n\n",
    "\n\nVous pouvez maintenant préparer la correspondance des champs.": "\n\nYou can now prepare the field mapping.",
    "Correspondance validée": "Mapping confirmed",
    "Correspondance enregistrée pour cette préparation d’import.\n\n": "Mapping saved for this import preparation.\n\n",
    "Aucune collection n’a encore été créée ou modifiée.": "No collection has been created or modified yet.",
    "Import de la base « {source} » en cours…\nCréation de la collection et copie des fiches. Merci de patienter.": "Importing database ‘{source}’…\nCreating the collection and copying records. Please wait.",
    "Import en cours": "Import in progress",
    "Import terminé": "Import complete",
    "Import terminé avec succès.\n\n": "Import completed successfully.\n\n",
    "Table source :": "Source table:",
    "Cette étape ne crée encore aucune collection et n'importe aucune donnée. Elle prépare seulement la structure de la future collection G-Skol.": "This step does not create a collection or import any data yet. It only prepares the structure of the future G-Skol collection.",
    "Lecture seule : {count} première(s) ligne(s) affichée(s). Cet aperçu sert à comprendre une base inconnue ; aucune donnée n'est modifiée.": "Read-only: first {count} row(s) displayed. This preview helps you understand an unfamiliar database; no data is modified.",
})
EN.update({
    "Source : <b>{source}</b> — {rows} fiche(s), {fields} champ(s).<br><br>G-Skol va créer une <b>nouvelle collection indépendante</b>. Les numéros de fiches G-Skol seront recréés automatiquement à partir de 1 ; un éventuel N° provenant de {kind} restera une donnée utilisateur ordinaire.": "Source: <b>{source}</b> — {rows} record(s), {fields} field(s).<br><br>G-Skol will create a <b>new independent collection</b>. G-Skol record numbers will be recreated automatically starting at 1; any No. from {kind} will remain ordinary user data.",
    "Le fichier {kind} source reste strictement en lecture seule. En cas de problème, seule la nouvelle collection G-Skol créée par cet essai sera concernée.": "The source {kind} file remains strictly read-only. If a problem occurs, only the new G-Skol collection created by this test will be affected.",
    "Table source : <b>{table}</b> — {count} champ(s). Pour chaque champ {source}, choisissez s’il doit être importé, le nom du futur champ G-Skol et son type. Les propositions sont automatiques mais restent entièrement modifiables.": "Source table: <b>{table}</b> — {count} field(s). For each {source} field, choose whether it should be imported, the name of the future G-Skol field and its type. Suggestions are automatic but remain fully editable.",
    "Cette étape ne crée encore aucune collection et n’importe aucune donnée. Elle prépare seulement la structure de la future collection G-Skol.": "This step does not create a collection or import any data yet. It only prepares the structure of the future G-Skol collection.",
    "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• <b>Bouton On / Off</b> désigne un vrai champ à deux états à cliquer ; une liste contenant les textes Oui et Non reste une <b>Liste / Référentiel</b>.<br>• <b>Liste / Référentiel — à paramétrer</b> : le champ sera préparé comme liste ; les liaisons Maître / Relié à pourront être définies ensuite dans l’Atelier.<br>• <b>Calculé — à paramétrer</b> : le champ sera préparé comme calculé, mais sa formule devra être définie dans l’Atelier.<br>• La colonne <b>Détection G-Skol</b> indique la preuve retrouvée dans Access : relation, source de liste ou expression de calcul. Une absence de preuve est affichée « — ».<br>• Un champ source <b>N° / Numéro</b> reste toujours un champ utilisateur ordinaire : il n’a <b>aucune influence</b> sur la numérotation automatique des fiches G-Skol.": "• <b>Double-click a G-Skol field name to edit it.</b><br>• <b>On / Off button</b> means a true two-state clickable field; a list containing the text Yes and No remains a <b>List / Reference</b>.<br>• <b>List / Reference — to configure</b>: the field will be prepared as a list; Master / Linked relationships can then be defined in the Workshop.<br>• <b>Calculated — to configure</b>: the field will be prepared as calculated, but its formula must be defined in the Workshop.<br>• The <b>G-Skol detection</b> column shows the evidence found in Access: relationship, list source or calculation expression. No evidence is shown as ‘—’.<br>• A source <b>No. / Number</b> field always remains an ordinary user field: it has <b>no effect</b> on automatic G-Skol record numbering.",
    "Lecture seule : {count} première(s) ligne(s) affichée(s). Cet aperçu sert à comprendre une base inconnue ; aucune donnée n’est modifiée.": "Read-only: first {count} row(s) displayed. This preview helps you understand an unfamiliar database; no data is modified.",
})
EN.update({
    "  • calcul reconnu": "  • calculated field recognized",
    "  • référentiel reconnu": "  • reference field recognized",
    "Vous avez sélectionné un champ. Pour l’import, sélectionnez le nom de la table qui contient les fiches.": "You selected a field. For import, select the name of the table containing the records.",
})

# G-Skol 1.0.173 — finitions du parcours Access, sans traduire les valeurs internes des combos.
EN.update({
    "Correspondance vide": "Empty mapping",
    "Aucun champ n’est actuellement prévu pour l’import.": "No field is currently selected for import.",
    "Sélectionnez une table dans la liste ci-dessus. Les lignes de champs ne sont pas sélectionnables comme source.": "Select a table from the list above. Field rows cannot be selected as the source.",
    "Entier long": "Long integer", "Entier": "Integer", "Octet": "Byte",
    "Réel simple": "Single precision", "Réel double": "Double precision",
    "Décimal": "Decimal", "Date / Heure": "Date / Time", "Oui / Non": "Yes / No",
    "Binaire long": "Long binary", "Binaire": "Binary", "Lien hypertexte": "Hyperlink",
    "Pièce jointe": "Attachment", "Texte long": "Long text",
})

# G-Skol 1.0.174 — fin du parcours Access : confirmations et rapport final.
EN.update({
    "Créer la collection « {collection} » et importer {rows} fiche(s) depuis Access ?<br><br>La base Access ne sera jamais modifiée.": "Create the collection ‘{collection}’ and import {rows} record(s) from Access?<br><br>The Access database will never be modified.",
    "✓ Import terminé : {records} fiche(s) créées dans « {name} ». {fields} champ(s) importés ; {values} valeur(s) de listes simples ; {refs} référentiel(s) tabulaire(s) relié(s).": "✓ Import complete: {records} record(s) created in ‘{name}’. {fields} field(s) imported; {values} simple-list value(s); {refs} linked tabular reference list(s).",
    "Tri Access du formulaire/requête conservé.": "Access form/query sort order preserved.",
    "Ordre historique Access (AutoNumber) conservé.": "Historical Access order (AutoNumber) preserved.",
    "Ordre source Access conservé.": "Access source order preserved.",
    "Préparation collection / modèle": "Collection / template preparation",
    "Lecture groupée Access": "Grouped Access read",
    "Création fiches + valeurs + photos": "Record + value + photo creation",
    "dont traitement photos": "including photo processing",
    "Listes simples": "Simple lists",
    "Référentiels liés + report dans les fiches": "Linked reference lists + record backfill",
    "dont écriture tables liées": "including linked-table writing",
    "dont report valeurs reliées": "including linked-value backfill",
    "Pont Access/DAO (processus complet)": "Access/DAO bridge (complete process)",
    "dont ouverture de la base Access": "including opening the Access database",
    "Table {name} : {seconds:.2f} s — {rows} ligne(s)": "Table {name}: {seconds:.2f} s — {rows} row(s)",
    " — binaires : {seconds:.2f} s / {count} objet(s) / {mb:.1f} Mo": " — binaries: {seconds:.2f} s / {count} object(s) / {mb:.1f} MB",
    "   • {name} : {seconds:.2f} s — {reads} lecture(s) — type DAO {type}": "   • {name}: {seconds:.2f} s — {reads} read(s) — DAO type {type}",
    "Analyse du résultat XML": "XML result analysis",
    "Reconstruction des données côté G-Skol": "G-Skol-side data reconstruction",
    "Aucun groupe détecté": "No group detected",
    "Collection : {name}\n": "Collection: {name}\n",
    "Fiches G-Skol créées : {count}\n": "G-Skol records created: {count}\n",
    "Champs importés : {count}\n": "Fields imported: {count}\n",
    "Valeurs de listes simples : {count}\n": "Simple-list values: {count}\n",
    "Référentiels tabulaires reconnus : {count}\n": "Tabular reference lists recognized: {count}\n",
    "Liaisons Maître / Relié à créées : {count}\n": "Master / Linked relationships created: {count}\n",
    "Valeurs reliées reportées dans les fiches : {count}\n": "Linked values backfilled into records: {count}\n",
    "Ordre des fiches : {order}\n\n": "Record order: {order}\n\n",
    "Diagnostic Maître/Reliés :\n": "Master/Linked diagnostic:\n",
    "Chronométrage diagnostic :\n": "Diagnostic timing:\n",
    "Détail de la lecture Access :\n": "Access read details:\n",
    "La nouvelle collection est désormais disponible dans la liste des collections.\nDepuis l'écran d'accueil, cliquez sur « Ouvrir une collection » pour l'ouvrir.\n\n": "The new collection is now available in the collection list.\nFrom the home screen, click ‘Open a collection’ to open it.\n\n",
    "Les fiches ont reçu leur propre numérotation G-Skol de 1 à {count}. Le N° Access, s'il a été conservé, reste un champ ordinaire.\n\n": "The records received their own G-Skol numbering from 1 to {count}. The Access No., if retained, remains an ordinary field.\n\n",
    "Source(s) Photo détectée(s) : {count}.\n": "Photo source(s) detected: {count}.\n",
    "Photos Access importées dans les cadres Photo G-Skol : {count}.\n": "Access photos imported into G-Skol Photo frames: {count}.\n",
    "Photos binaires non reconnues : {count}.": "Unrecognized binary photos: {count}.",
    "\nPremier objet illisible : {signature}": "\nFirst unreadable object: {signature}",
})


# G-Skol 1.0.176 — parcours complet d'import Microsoft Excel .xlsx.
EN.update({
    "Choisissez un classeur .xlsx. G-Skol analyse les feuilles, les en-têtes et les types de cellules sans modifier le fichier source. Les images intégrées au classeur ne sont pas importées dans cette première version.": "Choose an .xlsx workbook. G-Skol analyzes its sheets, headers and cell types without modifying the source file. Images embedded in the workbook are not imported in this first version.",
    "Choisir un fichier Excel…": "Choose an Excel file…",
    "Analyser le classeur": "Analyze workbook",
    "Aucun fichier Excel sélectionné.": "No Excel file selected.",
    "Après analyse, les feuilles et leurs colonnes apparaîtront ci-dessous.": "After analysis, the sheets and their columns will appear below.",
    "Feuille / Colonne": "Sheet / Column", "Type détecté": "Detected type",
    "Choisir cette feuille": "Choose this sheet",
    "Sélectionnez une feuille dans la liste ci-dessus. Les lignes de colonnes ne sont pas sélectionnables comme source.": "Select a sheet from the list above. Column rows cannot be selected as the source.",
    "Après validation de la feuille source, l’étape suivante préparera la correspondance entre les colonnes Excel et les champs G-Skol.": "After confirming the source sheet, the next step will prepare the mapping between Excel columns and G-Skol fields.",
    "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date, Bouton On / Off et Calculé</b> à partir des cellules et formats Excel ; vous pouvez corriger chaque proposition.<br>• Une colonne Excel devient un champ de la collection. Les cellules vides restent vides.<br>• L’ordre des lignes Excel est conservé : première ligne de données → fiche 1, puis 2, 3…<br>• Un champ source <b>N° / Numéro</b> reste une donnée ordinaire et n’influence jamais la numérotation automatique des fiches.": "• <b>Double-click a G-Skol field name to edit it.</b><br>• G-Skol infers <b>Text, Number, Currency, Date, On / Off button and Calculated</b> from Excel cells and formats; you can correct each suggestion.<br>• An Excel column becomes a collection field. Empty cells remain empty.<br>• Excel row order is preserved: first data row → record 1, then 2, 3…<br>• A source <b>No. / Number</b> field remains ordinary data and never affects automatic record numbering.",
    "Choisir un classeur Microsoft Excel": "Choose a Microsoft Excel workbook",
    "Classeurs Excel (*.xlsx);;Tous les fichiers (*.*)": "Excel workbooks (*.xlsx);;All files (*.*)",
    "Import Excel": "Excel import",
    "Le fichier choisi n’est pas un classeur .xlsx.": "The selected file is not an .xlsx workbook.",
    "Classeur sélectionné. Cliquez sur « Analyser le classeur » pour afficher ses feuilles.": "Workbook selected. Click ‘Analyze workbook’ to display its sheets.",
    "Fichier Excel sélectionné : {source}{size}\n": "Selected Excel file: {source}{size}\n",
    "Le fichier Excel sélectionné est introuvable.": "The selected Excel file cannot be found.",
    "Analyse du classeur Excel en cours…": "Analyzing Excel workbook…",
    "Analyse Excel impossible": "Excel analysis failed",
    "{count} colonne(s)": "{count} column(s)",
    "Analyse terminée : {sheets} feuille(s), {fields} colonne(s), {rows} ligne(s) de données au total.": "Analysis complete: {sheets} sheet(s), {fields} column(s), {rows} data row(s) in total.",
    "Booléen": "Boolean",
    "✓ Feuille source retenue : {name} — {rows} ligne(s), {fields} colonne(s){header}": "✓ Source sheet selected: {name} — {rows} row(s), {fields} column(s){header}",
    " — en-têtes ligne {row}.": " — headers on row {row}.",
    "Feuille source validée. L’ordre des lignes sera conservé pour créer les fiches. Cliquez sur « Correspondance des champs… ».": "Source sheet confirmed. Row order will be preserved when creating records. Click ‘Field mapping…’.",
    "✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour la création d'une nouvelle collection puis import des fiches.": "✓ Mapping confirmed: {imported} field(s) will be imported, {ignored} ignored. Ready to create a new collection and import records.",
    "Lancer l’import Excel ?": "Start Excel import?",
    "Créer la collection « {name} » et importer {rows} fiche(s) depuis Excel ?\n\nL’ordre des lignes Excel sera conservé. Le classeur source ne sera jamais modifié.": "Create the collection ‘{name}’ and import {rows} record(s) from Excel?\n\nExcel row order will be preserved. The source workbook will never be modified.",
    "Import du classeur « {source} » en cours…\nCréation de la collection et copie des lignes. Merci de patienter.": "Importing workbook ‘{source}’…\nCreating the collection and copying rows. Please wait.",
    "Import Excel en cours": "Excel import in progress",
    "Import Excel interrompu": "Excel import interrupted",
    "L’import n’a pas été conservé.\n\n": "The import was not kept.\n\n",
    "✓ Import terminé : {records} fiche(s) créées dans « {name} » — ordre des lignes Excel conservé.": "✓ Import complete: {records} record(s) created in ‘{name}’ — Excel row order preserved.",
    "Import Excel terminé": "Excel import complete",
    "Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\nChamps Maîtres détectés : {masters}\nChamps Reliés détectés : {links}\n\nOrdre des fiches : ordre des lignes Excel conservé.": "Import completed successfully.\n\nCollection: {name}\nRecords created: {records}\nFields imported: {fields}\nReference values: {values}\nMaster fields detected: {masters}\nLinked fields detected: {links}\n\nRecord order: Excel row order preserved.",
})


# G-Skol 1.0.179 — parcours complet d'import CSV / TXT / TSV.
EN.update({
    "Choisissez un fichier tabulaire .csv, .txt ou .tsv. G-Skol détecte automatiquement l’encodage et le séparateur (point-virgule, virgule ou tabulation), puis analyse les en-têtes et les types de colonnes sans modifier le fichier source.": "Choose a tabular .csv, .txt or .tsv file. G-Skol automatically detects the encoding and delimiter (semicolon, comma or tab), then analyzes headers and column types without modifying the source file.",
    "Choisir un fichier CSV / TXT / TSV…": "Choose a CSV / TXT / TSV file…",
    "Analyser le fichier": "Analyze file",
    "Aucun fichier CSV / TXT / TSV sélectionné.": "No CSV / TXT / TSV file selected.",
    "Après analyse, les colonnes et le nombre de lignes apparaîtront ci-dessous.": "After analysis, the columns and number of rows will appear below.",
    "Fichier / Colonne": "File / Column", "Type détecté": "Detected type", "Lignes": "Rows",
    "Choisir ce fichier": "Choose this file",
    "Analysez le fichier puis validez-le comme source de la future collection G-Skol.": "Analyze the file, then confirm it as the source for the future G-Skol collection.",
    "Après validation, G-Skol préparera la correspondance entre les colonnes du fichier et les champs G-Skol.": "After confirmation, G-Skol will prepare the mapping between file columns and G-Skol fields.",
    "Choisir un fichier CSV / TXT / TSV": "Choose a CSV / TXT / TSV file",
    "Fichiers tabulaires (*.csv *.txt *.tsv);;CSV (*.csv);;Texte (*.txt);;TSV (*.tsv);;Tous les fichiers (*.*)": "Tabular files (*.csv *.txt *.tsv);;CSV (*.csv);;Text (*.txt);;TSV (*.tsv);;All files (*.*)",
    "Fichier sélectionné. Cliquez sur « Analyser le fichier ».": "File selected. Click ‘Analyze file’.",
    "Fichier sélectionné : {source}{size}\nAucune donnée n’est importée ou modifiée pendant l’analyse.": "Selected file: {source}{size}\nNo data is imported or modified during analysis.",
    "Analyse du fichier en cours…": "Analyzing file…",
    "Analyse terminée : aucune table de données trouvée.": "Analysis complete: no data table found.",
    "Analyse terminée : {columns} colonne(s), {rows} ligne(s) — encodage {encoding} — séparateur : {delimiter}.": "Analysis complete: {columns} column(s), {rows} row(s) — encoding {encoding} — delimiter: {delimiter}.",
    "Fichier analysé. Cliquez sur « Choisir ce fichier » pour le retenir comme source.": "File analyzed. Click ‘Choose this file’ to use it as the source.",
    "✓ Source retenue : {name} — {rows} ligne(s), {columns} colonne(s) — {encoding}, séparateur {delimiter}.": "✓ Source selected: {name} — {rows} row(s), {columns} column(s) — {encoding}, delimiter {delimiter}.",
    "Source validée. L’ordre des lignes sera conservé. Cliquez sur « Correspondance des champs… ».": "Source confirmed. Row order will be preserved. Click ‘Field mapping…’.",
    "Fichier texte": "Text file",
    "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date et Bouton On / Off</b> à partir des valeurs ; vous pouvez corriger chaque proposition.<br>• Le séparateur et l’encodage sont détectés automatiquement puis affichés avant l’import.<br>• Une colonne devient un champ de la collection ; les cellules vides restent vides.<br>• Les fichiers texte ne contiennent pas de vraie information de liste déroulante : vous pouvez choisir manuellement <b>Liste / Référentiel</b> dans la correspondance.<br>• L’ordre des lignes source est conservé : première ligne de données → fiche 1, puis 2, 3…": "• <b>Double-click a G-Skol field name to edit it.</b><br>• G-Skol infers <b>Text, Number, Currency, Date and On / Off button</b> from the values; you can correct each suggestion.<br>• The delimiter and encoding are detected automatically and displayed before import.<br>• A column becomes a collection field; empty cells remain empty.<br>• Text files do not contain true drop-down list metadata: you can manually choose <b>List / Reference</b> in the mapping.<br>• Source row order is preserved: first data row → record 1, then 2, 3…",
    "Lancer l’import {source} ?": "Start the {source} import?",
    "Créer la collection « {name} » et importer {rows} fiche(s) depuis {source} ?\n\nL’ordre des lignes sera conservé. Le fichier source ne sera jamais modifié.": "Create the ‘{name}’ collection and import {rows} record(s) from {source}?\n\nRow order will be preserved. The source file will never be modified.",
    "Import {source} terminé": "{source} import complete",
    "Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\n\nOrdre des fiches : ordre des lignes source conservé.": "Import completed successfully.\n\nCollection: {name}\nRecords created: {records}\nFields imported: {fields}\nReference values: {values}\n\nRecord order: source row order preserved.",
})

EN.update({
"✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour la création de la collection et l’import des lignes.": "✓ Mapping confirmed: {imported} field(s) will be imported, {ignored} ignored. Ready to create the collection and import the rows.",
"Import du fichier « {source} » en cours…\nCréation de la collection et copie des lignes.": "Importing file ‘{source}’…\nCreating the collection and copying rows.",
"Import {source} en cours": "{source} import in progress",
"✓ Import terminé : {records} fiche(s) créées dans « {name} » — ordre des lignes conservé.": "✓ Import complete: {records} record(s) created in ‘{name}’ — row order preserved.",
})

# G-Skol 1.0.180 — parcours d'import ODS.
EN.update({
    "Choisissez un classeur OpenDocument .ods. G-Skol analyse ses feuilles, les en-têtes et les types de cellules sans modifier le fichier source. Les nombres, dates, booléens, montants monétaires et calculs arithmétiques simples sont reconnus.": "Choose an OpenDocument .ods workbook. G-Skol analyzes its sheets, headers and cell types without modifying the source file. Numbers, dates, Boolean values, currency amounts and simple arithmetic calculations are recognized.",
    "Choisir un fichier ODS…": "Choose an ODS file…", "Aucun fichier ODS sélectionné.": "No ODS file selected.",
    "Feuille / Colonne": "Sheet / Column", "Type détecté": "Detected type", "Lignes": "Rows",
    "Analysez le classeur puis choisissez la feuille source de la future collection G-Skol.": "Analyze the workbook, then choose the source sheet for the future G-Skol collection.",
    "Choisir un fichier ODS": "Choose an ODS file", "Classeurs OpenDocument (*.ods);;Tous les fichiers (*.*)": "OpenDocument workbooks (*.ods);;All files (*.*)",
    "Import ODS": "ODS import", "Le classeur choisi doit être au format .ods.": "The selected workbook must be in .ods format.",
    "Fichier sélectionné. Cliquez sur « Analyser le fichier ».": "File selected. Click ‘Analyze file’.",
    "Le classeur sélectionné est introuvable.": "The selected workbook cannot be found.", "Analyse du classeur ODS en cours…": "Analyzing ODS workbook…", "Analyse ODS impossible": "ODS analysis failed",
    "Analyse terminée : {sheets} feuille(s), {fields} colonne(s), {rows} ligne(s) de données au total.": "Analysis complete: {sheets} sheet(s), {fields} column(s), {rows} data row(s) in total.",
    "Sélectionnez une feuille dans la liste ci-dessus.": "Select a sheet from the list above.",
    "✓ Feuille source retenue : {name} — {rows} ligne(s), {fields} colonne(s).": "✓ Source sheet selected: {name} — {rows} row(s), {fields} column(s).",
    "Feuille source validée. L’ordre des lignes sera conservé. Cliquez sur « Correspondance des champs… ».": "Source sheet confirmed. Row order will be preserved. Click ‘Field mapping…’.",
    "✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour la création de la collection et l’import des lignes.": "✓ Mapping confirmed: {imported} field(s) will be imported, {ignored} ignored. Ready to create the collection and import the rows.",
    "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date, Bouton On / Off et Calculé</b> à partir des cellules et formats ODS ; vous pouvez corriger chaque proposition.<br>• Une colonne ODS devient un champ de la collection. Les cellules vides restent vides.<br>• L’ordre des lignes ODS est conservé : première ligne de données → fiche 1, puis 2, 3…<br>• Un champ source <b>N° / Numéro</b> reste une donnée ordinaire et n’influence jamais la numérotation automatique des fiches.": "• <b>Double-click a G-Skol field name to edit it.</b><br>• G-Skol infers <b>Text, Number, Currency, Date, On / Off button and Calculated</b> from ODS cells and formats; you can correct each suggestion.<br>• An ODS column becomes a collection field. Empty cells remain empty.<br>• ODS row order is preserved: first data row → record 1, then 2, 3…<br>• A source <b>No. / Number</b> field remains ordinary data and never affects automatic record numbering.",
    "Nom déjà utilisé": "Name already in use", "Le fichier « {name} » existe déjà.": "The file ‘{name}’ already exists.",
    "Import du fichier « {source} » en cours…\nCréation de la collection et copie des lignes.": "Importing file ‘{source}’…\nCreating the collection and copying rows.",
    "Import {source} interrompu": "{source} import interrupted", "L’import n’a pas été conservé.": "The import was not kept.",
    "✓ Import terminé : {records} fiche(s) créées dans « {name} » — ordre des lignes conservé.": "✓ Import complete: {records} record(s) created in ‘{name}’ — row order preserved.",
})


# G-Skol 1.0.181 — parcours complet d'import DBF.
EN.update({
    "Choisissez un fichier dBASE/FoxPro .dbf. G-Skol lit directement la structure du fichier, les noms de champs et les enregistrements sans modifier la source. Les champs texte, numériques, dates et logiques Oui/Non sont reconnus. Les mémos externes restent signalés lorsqu’ils nécessitent un fichier compagnon .dbt/.fpt.": "Choose a dBASE/FoxPro .dbf file. G-Skol reads the file structure, field names and records directly without modifying the source. Text, numeric, date and Yes/No logical fields are recognized. External memo fields remain flagged when they require a companion .dbt/.fpt file.",
    "Choisir un fichier DBF…": "Choose a DBF file…",
    "Aucun fichier DBF sélectionné.": "No DBF file selected.",
    "Après analyse, les champs et le nombre d’enregistrements apparaîtront ci-dessous.": "After analysis, the fields and number of records will appear below.",
    "Fichier / Champ": "File / Field",
    "Après validation, G-Skol préparera la correspondance entre les champs DBF et les champs G-Skol.": "After confirmation, G-Skol will prepare the mapping between DBF fields and G-Skol fields.",
    "Choisir un fichier DBF": "Choose a DBF file",
    "Fichiers DBF (*.dbf);;Tous les fichiers (*.*)": "DBF files (*.dbf);;All files (*.*)",
    "Le fichier choisi doit être au format .dbf.": "The selected file must be in .dbf format.",
    "Fichier sélectionné : {source}{size}\nAucune donnée n’est importée ou modifiée pendant l’analyse.": "Selected file: {source}{size}\nNo data is imported or modified during analysis.",
    "Fichier prêt à être analysé.": "File ready to be analyzed.",
    "Le fichier sélectionné est introuvable.": "The selected file cannot be found.",
    "Analyse du fichier DBF en cours…": "Analyzing DBF file…",
    "Analyse DBF impossible": "DBF analysis failed",
    "{count} champ(s)": "{count} field(s)",
    "Booléen": "Boolean",
    "Analyse terminée : {fields} champ(s), {rows} ligne(s). Encodage : {enc}. Version DBF : {version}.": "Analysis complete: {fields} field(s), {rows} record(s). Encoding: {enc}. DBF version: {version}.",
    "Sélectionnez le fichier analysé dans la liste ci-dessus.": "Select the analyzed file in the list above.",
    "✓ Source DBF retenue : {name} — {rows} ligne(s), {fields} champ(s).": "✓ DBF source selected: {name} — {rows} record(s), {fields} field(s).",
    "Source validée. L’ordre des enregistrements sera conservé. Cliquez sur « Correspondance des champs… ».": "Source confirmed. Record order will be preserved. Click ‘Field mapping…’.",
    "✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour l’import.": "✓ Mapping confirmed: {imported} field(s) will be imported, {ignored} ignored. Ready to import.",
    "Créer la collection « {name} » et importer {rows} fiche(s) depuis {source} ?\n\nL’ordre des enregistrements sera conservé. Le fichier source ne sera jamais modifié.": "Create the collection ‘{name}’ and import {rows} record(s) from {source}?\n\nRecord order will be preserved. The source file will never be modified.",
    "✓ Import terminé : {records} fiche(s) créées dans « {name} » — ordre conservé.": "✓ Import complete: {records} record(s) created in ‘{name}’ — order preserved.",
    "Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\n\nOrdre des fiches : ordre des enregistrements DBF conservé.": "Import completed successfully.\n\nCollection: {name}\nRecords created: {records}\nFields imported: {fields}\nReference values: {values}\n\nRecord order: DBF record order preserved.",
    "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date et Bouton On / Off</b> à partir des types DBF ; vous pouvez corriger chaque proposition.<br>• Un champ DBF devient un champ de la collection. Les valeurs vides restent vides.<br>• L’ordre des enregistrements DBF est conservé : premier enregistrement → fiche 1, puis 2, 3…<br>• Un champ source <b>N° / Numéro</b> reste une donnée ordinaire et n’influence jamais la numérotation automatique des fiches.": "• <b>Double-click a G-Skol field name to edit it.</b><br>• G-Skol derives <b>Text, Number, Currency, Date and On / Off button</b> from DBF types; you can correct each suggestion.<br>• A DBF field becomes a collection field. Empty values remain empty.<br>• DBF record order is preserved: first record → record 1, then 2, 3…<br>• A source <b>No. / Number</b> field remains ordinary data and never affects automatic record numbering.",
})

# G-Skol 1.0.182 — parcours complet d'import SQLite.
EN.update({
    "Choisissez une base SQLite .db, .sqlite ou .sqlite3. G-Skol ouvre la base strictement en lecture seule, recense ses tables utilisateur, leurs colonnes et leurs types, puis vous laisse choisir la table qui deviendra la source de la nouvelle collection.": "Choose a SQLite .db, .sqlite or .sqlite3 database. G-Skol opens it strictly read-only, lists its user tables, columns and types, then lets you choose the table that will become the source of the new collection.",
    "Choisir une base SQLite…": "Choose a SQLite database…",
    "Analyser la base": "Analyze database",
    "Aucune base SQLite sélectionnée.": "No SQLite database selected.",
    "Après analyse, les tables, colonnes et nombres d’enregistrements apparaîtront ci-dessous.": "After analysis, the tables, columns and record counts will appear below.",
    "Table / Colonne": "Table / Column",
    "Choisir cette table": "Choose this table",
    "Analysez la base puis choisissez la table source de la future collection G-Skol.": "Analyze the database, then choose the source table for the future G-Skol collection.",
    "Après validation, G-Skol préparera la correspondance entre les colonnes SQLite et les champs G-Skol.": "After confirmation, G-Skol will prepare the mapping between SQLite columns and G-Skol fields.",
    "Choisir une base SQLite": "Choose a SQLite database",
    "Bases SQLite (*.db *.sqlite *.sqlite3);;Tous les fichiers (*.*)": "SQLite databases (*.db *.sqlite *.sqlite3);;All files (*.*)",
    "Base sélectionnée : {source}{size}\nOuverture strictement en lecture seule pendant l’analyse.": "Selected database: {source}{size}\nOpened strictly read-only during analysis.",
    "Base sélectionnée. Cliquez sur « Analyser la base ».": "Database selected. Click ‘Analyze database’.",
    "Analyse de la base SQLite en cours…": "Analyzing SQLite database…",
    " — {count} référentiel(s) multi-colonnes reconnu(s).": " — {count} multi-column reference(s) recognized.",
    "Analyse terminée : {tables} table(s), {fields} colonne(s), {rows} ligne(s) au total.{refs}": "Analysis complete: {tables} table(s), {fields} column(s), {rows} row(s) in total.{refs}",
    "Sélectionnez la table contenant les fiches à importer.": "Select the table containing the records to import.",
    " — {count} référentiel(s) associé(s) reconnu(s).": " — {count} associated reference(s) recognized.",
    "✓ Table SQLite retenue : {name} — {rows} ligne(s), {fields} colonne(s){refs}": "✓ SQLite table selected: {name} — {rows} row(s), {fields} column(s){refs}",
    "Table validée. Cliquez sur « Correspondance des champs… ».": "Table confirmed. Click ‘Field mapping…’.",
    "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date, Bouton On / Off, Liste / Référentiel et Calculé</b> à partir des types, relations et données SQLite ; vous pouvez corriger chaque proposition.<br>• Une colonne SQLite devient un champ de la collection. Les valeurs vides restent vides.<br>• Les référentiels multi-colonnes reconnus peuvent créer des champs Maître / Reliés.<br>• L’ordre des lignes SQLite est conservé lors de la création des fiches.<br>• Un champ source <b>N° / Numéro</b> reste une donnée ordinaire et n’influence jamais la numérotation automatique des fiches.": "• <b>Double-click a G-Skol field name to edit it.</b><br>• G-Skol derives <b>Text, Number, Currency, Date, On / Off button, List / Reference and Calculated</b> from SQLite types, relationships and data; you can correct each suggestion.<br>• A SQLite column becomes a collection field. Empty values remain empty.<br>• Recognized multi-column references can create Master / Linked fields.<br>• SQLite row order is preserved when records are created.<br>• A source <b>No. / Number</b> field remains ordinary data and never affects automatic record numbering.",
    "Lancer l’import SQLite ?": "Start the SQLite import?",
    "Créer la collection « {name} » et importer {rows} fiche(s) depuis la table « {table} » ?\n\nLa base SQLite source restera strictement en lecture seule.": "Create the collection ‘{name}’ and import {rows} record(s) from table ‘{table}’?\n\nThe source SQLite database will remain strictly read-only.",
    "Import de « {source} » en cours…\nCréation de la collection et copie des lignes.": "Importing ‘{source}’…\nCreating the collection and copying rows.",
    "Import SQLite en cours": "SQLite import in progress",
    "Import SQLite interrompu": "SQLite import interrupted",
    "L’import n’a pas été conservé.": "The import was not kept.",
    "✓ Import terminé : {records} fiche(s) créées dans « {name} ».": "✓ Import complete: {records} record(s) created in ‘{name}’.",
    "Import SQLite terminé": "SQLite import complete",
    "Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\nChamps Maîtres détectés : {masters}\nChamps Reliés détectés : {links}": "Import completed successfully.\n\nCollection: {name}\nRecords created: {records}\nFields imported: {fields}\nReference values: {values}\nMaster fields detected: {masters}\nLinked fields detected: {links}",
})

# G-Skol 1.0.186 — Export : interface anglaise et extensions G-Skol.
EN.update({
    "Exportation": "Export",
    "Choisissez un dossier puis une collection. L'export crée un fichier transportable sans modifier la collection d'origine.": "Choose a folder, then a collection. Export creates a portable file without modifying the original collection.",
    "Dossier :": "Folder:",
    "Collection :": "Collection:",
    "— Aucun dossier sélectionné —": "— No folder selected —",
    "— Aucune collection sélectionnée —": "— No collection selected —",
    "Exporter une collection complète  (.coldb)": "Export a complete collection  (.coldb)",
    "Exporter une structure de collection  (.colstr)": "Export a collection structure  (.colstr)",
    "Exporter le modèle de Fiche  (.colmod)": "Export the Record template  (.colmod)",
    "Exporter un modèle de Tableau  (.colmod)": "Export a Table template  (.colmod)",
    "Exporter un modèle de Requête  (.colmod)": "Export a Query template  (.colmod)",
    "Exporter un modèle d'État  (.colmod)": "Export a Report template  (.colmod)",
    "Données, photos, référentiels, champs, modèles et réglages de la collection.": "Collection data, photos, reference lists, fields, templates and settings.",
    "Structure, modèles, paramètres et référentiels, sans fiches, données ni photos.": "Structure, templates, settings and reference lists, without records, data or photos.",
    "Exporte uniquement le modèle de Fiche de la collection : disposition, styles, groupes, champs calculés et informations de liaison nécessaires. Aucune fiche ni donnée n'est exportée.": "Exports only the collection's Record template: layout, styles, groups, calculated fields and required link information. No records or data are exported.",
    "Choisit un modèle dans la bibliothèque Modèles de Tableaux et crée une copie échangeable .colmod. Aucune collection ni donnée n'est modifiée.": "Selects a template from the Table Templates library and creates a portable .colmod copy. No collection or data is modified.",
    "Choisit un modèle dans la bibliothèque Modèles de Requêtes et crée une copie échangeable .colmod. Aucune collection ni donnée n'est modifiée.": "Selects a template from the Query Templates library and creates a portable .colmod copy. No collection or data is modified.",
    "Choisit un modèle dans la bibliothèque Modèles d’États et crée une copie échangeable .colmod. Aucune collection ni donnée n'est modifiée.": "Selects a template from the Report Templates library and creates a portable .colmod copy. No collection or data is modified.",
    "La structure exportée reprend le principe déjà utilisé par « Dupliquer la structure de la collection » dans la Boîte à outils.": "The exported structure uses the same principle as “Duplicate collection structure” in the Toolbox.",
    "Retour": "Back",
    "Exportation terminée": "Export complete",
    "Exportation impossible": "Export failed",
    "Modèle non valide": "Invalid template",
    "Le fichier de la collection sélectionnée est introuvable.": "The selected collection file cannot be found.",
    "Exporter la collection complète": "Export the complete collection",
    "Exporter la structure de collection": "Export the collection structure",
    "Fichier G-Skol (*.coldb)": "G-Skol file (*.coldb)",
    "Fichier G-Skol (*.colstr)": "G-Skol file (*.colstr)",
    "Modèle G-Skol (*.colmod)": "G-Skol template (*.colmod)",
    "Exporter le modèle de Fiche": "Export Record template",
    "Exporter un modèle de Tableau": "Export a Table template",
    "Exporter un modèle de Requête": "Export a Query template",
    "Exporter un modèle d'État": "Export a Report template",
})

# G-Skol 1.0.190 — Sauvegarde / Restauration : écran d'accueil et parcours de sauvegarde anglais.
EN.update({
    "Créez ou restaurez une sauvegarde, et gérez séparément les sauvegardes volontaires et les copies temporaires automatiques.": "Create or restore a backup, and manage user-created backups separately from automatic temporary copies.",
    "Créer une sauvegarde complète des collections internes (dossier Workspace)": "Create a complete backup of internally stored collections (Workspace folder)",
    "Sauvegarder une ou plusieurs collections internes (dossier Workspace)": "Back up one or more internal collections (Workspace folder)",
    "Restaurer une sauvegarde": "Restore a backup",
    "La restauration sera disponible après validation de la création et de la vérification des sauvegardes.": "Restore will be available after backup creation and verification have been validated.",
    "Gérer les sauvegardes": "Manage backups",
    "Sauvegarde": "Backup",
    "Ouvrir la sauvegarde": "Open backup",
    "Contenu de la sauvegarde": "Backup contents",
    "Supprimer": "Delete",
    "Confirmer la suppression": "Confirm deletion",
    "Suppression incomplète": "Incomplete deletion",
    "Consulter et supprimer séparément les sauvegardes volontaires utilisateur et les sauvegardes temporaires automatiques.": "View and delete user-created backups and automatic temporary backups separately.",
    "Collection(s) — cochez les fichiers à copier": "Collection(s) — select the files to copy",
    "Fichier source": "Source file",
    "Aucune collection G-Skol dans ce fichier.": "No G-Skol collection was found in this file.",
    "Base non reconnue": "Unrecognized database",
    "Cochez les collections du Workspace à sauvegarder. Vous pourrez ensuite ajouter des bases situées sur une clé USB, un disque externe ou dans un autre dossier.": "Select the Workspace collections to back up. You can then add databases located on a USB drive, an external drive, or in another folder.",
    "Aucune collection trouvée dans Workspace/Collections.": "No collection found in Workspace/Collections.",
    "Pour ajouter des bases situées hors du Workspace, cliquez sur « Parcourir… » en bas de cet écran. Dans l'explorateur, choisissez un ou plusieurs fichiers .coldb avec Ctrl ou Maj. Vous pouvez aussi passer cette étape sans rien ajouter.": "To add databases located outside the Workspace, click ‘Browse…’ at the bottom of this screen. In File Explorer, select one or more .coldb files using Ctrl or Shift. You can also skip this step without adding anything.",
    "Parcourir…": "Browse…",
    "Choisissez maintenant le dossier où placer les copies. G-Skol créera dans ce dossier un nouveau sous-dossier daté contenant les .coldb sélectionnés.": "Now choose the folder where the copies will be stored. G-Skol will create a new dated subfolder there containing the selected .coldb files.",
    "Dossier de destination :": "Destination folder:",
    "Choisir le dossier…": "Choose folder…",
    "Nom du nouveau sous-dossier :": "New subfolder name:",
    "Précédent": "Back",
    "Suivant": "Next",
    "Créer les copies .coldb": "Create .coldb copies",
    "Annuler": "Cancel",
    "1 / 3 — Collections du Workspace": "1 / 3 — Workspace collections",
    "2 / 3 — Bases situées sur un autre support": "2 / 3 — Databases stored elsewhere",
    "3 / 3 — Destination de la sauvegarde": "3 / 3 — Backup destination",
    "Sélection : {workspace_count} fichier(s) du Workspace et {external_count} fichier(s) extérieurs.": "Selection: {workspace_count} Workspace file(s) and {external_count} external file(s).",
    "Créer une sauvegarde": "Create a backup",
    "Nom du dossier daté :": "Dated folder name:",
    "Créer la sauvegarde complète": "Create complete backup",
    "Supprimer la sélection": "Delete selection",
    "Supprimer les sauvegardes sélectionnées": "Delete selected backups",
    "Supprimer les collections sélectionnées": "Delete selected collections",
    "Oui": "Yes",
    "Non": "No",
    "Tout sélectionner": "Select all",
    "Fichier": "File",
    "Date / heure": "Date / time",
    "Taille": "Size",
    "Les sauvegardes volontaires et les copies de sécurité créées automatiquement par G-Skol sont séparées afin d’éviter toute confusion.": "User-created backups and safety copies automatically created by G-Skol are kept separate to avoid confusion.",
})

# G-Skol 1.0.192 — Sauvegarde complète : textes restants du parcours anglais.
EN.update({
    "Sauvegarde complète de tous les fichiers du Workspace, sauf les anciennes sauvegardes. Chaque sauvegarde reprend l'ensemble : elle n'est pas incrémentielle. Les collections sont des .coldb utilisables individuellement.": "Complete backup of all Workspace files, excluding previous backups. Each backup contains the complete set: it is not incremental. Collections are individual .coldb files that can be used separately.",
    "Collections incluses ({count}) :": "Included collections ({count}):",
    "Aucune": "None",
    "Collections ouvertes hors du Workspace (exclues) :": "Collections currently open outside the Workspace (excluded):",
    "Aucune actuellement ouverte. Les collections extérieures fermées ne sont pas recensées.": "None currently open. Closed external collections are not listed.",
    "Choisir le dossier de destination": "Choose destination folder",
    "Sauvegarde vérifiée": "Backup verified",
    "Dossier créé :": "Folder created:",
    "{collections} collection(s), {files} fichier(s) vérifié(s).": "{collections} collection(s), {files} file(s) verified.",
    "Fichiers .coldb individuels :": "Individual .coldb files:",
})

# G-Skol 1.0.195 — parcours de restauration en deux étapes.
EN.update({
    "Choisissez un dossier de sauvegarde G-Skol. G-Skol l’analysera avant d’afficher les collections disponibles.": "Choose a G-Skol backup folder. G-Skol will analyze it before displaying the available collections.",
    "Aucun dossier de sauvegarde sélectionné.": "No backup folder selected.",
    "Suivant": "Next",
    "Taille (Mo)": "Size (MB)",
    "Tout désélectionner": "Deselect all",
    "{count} collection(s) trouvée(s). Cliquez sur Suivant pour choisir celles à restaurer.": "{count} collection(s) found. Click Next to choose which ones to restore.",
    "En cas de renommage, G-Skol ajoute « - Restaurée AAAA-MM-JJ-HHMMSS » au nom du fichier et au nom de la collection. Une collection actuellement ouverte ne peut pas être remplacée : utilisez alors « Conserver les deux ».": "When renaming, G-Skol adds ‘- Restored YYYY-MM-DD-HHMMSS’ to both the file name and the collection name. A collection that is currently open cannot be replaced; use ‘Keep both’ instead.",
    "Restaurée": "Restored",
})


# G-Skol 1.0.201 — restauration : choix interne/externe.
EN.update({
    "Sauvegardes internes (Workspace)": "Internal backups (Workspace)",
    "Choisir dans le Workspace…": "Choose from Workspace…",
    "Sauvegarde stockée ailleurs dans Windows": "Backup stored elsewhere in Windows",
    "Parcourir…": "Browse…",
    "Aucune sauvegarde sélectionnée": "No backup selected",
})


# G-Skol 1.0.207 — accueil anglais, référentiels et édition par clic droit.
EN.update({
    "Modifier le libellé…": "Edit field label…",
    "Ouvrez ou créez d’abord une collection avant d’utiliser la Boîte à outils.": "Open or create a collection before using the Toolbox.",
    "Ouvrez ou créez d'abord une collection avant d'effectuer une recherche.": "Open or create a collection before searching.",
    "Ouvrez ou créez d'abord une collection avant de construire une requête.": "Open or create a collection before building a query.",
    "Ouvrez ou créez d'abord une collection avant d'utiliser les États.": "Open or create a collection before using Reports.",
    "Ouvrez ou créez d'abord une collection avant d'afficher la Vue Tableau.": "Open or create a collection before opening Table view.",
    "Ouvrez d’abord une collection.": "Open a collection first.",
    "Importer des référentiels dans une collection existante": "Import references into an existing collection",
})

# G-Skol 1.0.208 — Workshop warnings + reference-list import localization.
EN.update({
    "Ouvrez ou créez d’abord une collection avant d’utiliser l’Éditeur d’états.": "Open or create a collection before using the Report editor.",
    "Ouvrez ou créez d’abord une collection avant de préparer son modèle de fiche.": "Open or create a collection before preparing its record template.",
    "Ouvrez ou créez d'abord une collection avant de gérer ses référentiels.": "Open or create a collection before managing its reference lists.",
})

# G-Skol 1.0.208 — complete English pass for Workshop guards and reference imports.
EN.update({
    "Importation de référentiels dans une collection existante": "Import reference lists into an existing collection",
    "Importer des référentiels dans une collection existante": "Import reference lists into an existing collection",
    "Ajoutez ou complétez des référentiels dans une collection G-Skol existante, sans créer de fiches. G-Skol reconnaît maintenant les référentiels multi-colonnes provenant d’Access, SQLite, Excel .xlsx, CSV/TXT/TSV, ODS ou DBF. Pour Excel, seules les vraies feuilles relationnelles (une ligne = une valeur Maître et ses données Reliées) sont utilisées ; les feuilles de fiches et les réservoirs de listes indépendantes sont volontairement écartés. Les valeurs existantes sont conservées ; seules les nouvelles valeurs et associations sont ajoutées ou mises à jour.": "Add to or complete reference lists in an existing G-Skol collection without creating records. G-Skol now recognizes multi-column reference lists from Access, SQLite, Excel .xlsx, CSV/TXT/TSV, ODS or DBF. For Excel, only true relational sheets (one row = one Master value and its Linked data) are used; record sheets and independent list reservoirs are intentionally ignored. Existing values are kept; only new values and associations are added or updated.",
    "1. Collection G-Skol de destination": "1. Destination G-Skol collection",
    "Sélectionner une collection…": "Select a collection…",
    "Aucune collection sélectionnée.": "No collection selected.",
    "2. Source des référentiels": "2. Reference-list source",
    "Choisir une base SQLite…": "Choose a SQLite database…",
    "Analyser les référentiels": "Analyze reference lists",
    "Aucune source sélectionnée.": "No source selected.",
    "3. Référentiels à importer — cochez uniquement ceux que vous voulez ajouter ou compléter.": "3. Reference lists to import — check only those you want to add or complete.",
    "Tout cocher": "Check all", "Tout décocher": "Uncheck all",
    "Référentiel / Champ": "Reference list / Field", "Destination G-Skol": "G-Skol destination", "Lignes": "Rows",
    "Choisissez d'abord la collection puis la source contenant les référentiels.": "First choose the collection, then the source containing the reference lists.",
    "Importer / compléter les référentiels…": "Import / complete reference lists…",
    "Aucune collection détectée automatiquement. Utilisez « Sélectionner une collection… ».": "No collection was detected automatically. Use ‘Select a collection…’.",
    "Choisir une collection G-Skol existante": "Choose an existing G-Skol collection",
    "Collection G-Skol invalide": "Invalid G-Skol collection", "Collection G-Skol": "G-Skol collection",
    "Aucune collection n'a été trouvée dans ce fichier.": "No collection was found in this file.",
    "Choisir une base Access…": "Choose an Access database…", "Aucune base Access sélectionnée.": "No Access database selected.",
    "Choisir un fichier Excel…": "Choose an Excel file…", "Aucun fichier Excel sélectionné.": "No Excel file selected.",
    "Choisir un fichier CSV / TXT / TSV…": "Choose a CSV / TXT / TSV file…", "Aucun fichier texte sélectionné.": "No text file selected.",
    "Choisir un fichier ODS…": "Choose an ODS file…", "Aucun fichier ODS sélectionné.": "No ODS file selected.",
    "Choisir un fichier DBF…": "Choose a DBF file…", "Aucun fichier DBF sélectionné.": "No DBF file selected.",
    "Aucune base SQLite sélectionnée.": "No SQLite database selected.", "Choisir une source…": "Choose a source…",
    "Source non sélectionnée.": "No source selected.",
    "Choisir la base Access contenant les référentiels": "Choose the Access database containing the reference lists",
    "Choisir le fichier Excel contenant les référentiels": "Choose the Excel file containing the reference lists",
    "Choisir le fichier CSV / TXT / TSV contenant les référentiels": "Choose the CSV / TXT / TSV file containing the reference lists",
    "Choisir le fichier ODS contenant les référentiels": "Choose the ODS file containing the reference lists",
    "Choisir le fichier DBF contenant les référentiels": "Choose the DBF file containing the reference lists",
    "Choisir la base SQLite contenant les référentiels": "Choose the SQLite database containing the reference lists",
    "Choisir une source contenant les référentiels": "Choose a source containing the reference lists",
    "Source sélectionnée. Cliquez sur « Analyser les référentiels ».": "Source selected. Click ‘Analyze reference lists’.",
    "Aucun référentiel compatible n'a été détecté pour les champs visibles de cette collection.": "No compatible reference list was detected for the visible fields in this collection.",
    "Maître / Reliés proposés par G-Skol": "Master / Linked fields suggested by G-Skol",
    "Maître G-Skol : {name}": "G-Skol Master: {name}",
    "Ne pas importer": "Do not import", "Relié": "Linked", "Maître": "Master", "Créer": "Create",
    "Analyse de la structure Access…\nLecture des tables et des champs uniquement.": "Analyzing Access structure…\nReading tables and fields only.",
    "Analyse des référentiels Access": "Analyzing Access reference lists",
    "Aucun référentiel sélectionné": "No reference list selected", "Cochez au moins un référentiel à importer.": "Check at least one reference list to import.",
    "Importer les référentiels ?": "Import reference lists?", "Import de référentiels en cours": "Importing reference lists",
    "Importer {count} référentiel(s) sélectionné(s) dans « {name} » ?": "Import {count} selected reference list(s) into ‘{name}’?",
    "Les référentiels décochés seront ignorés. Les valeurs existantes seront conservées. Seules les correspondances que vous venez de valider seront utilisées. Les champs marqués « Créer » seront ajoutés explicitement à la collection. Les nouvelles valeurs seront ajoutées et les associations Maître / Relié à seront complétées. Aucune fiche ne sera supprimée.": "Unchecked reference lists will be ignored. Existing values will be kept. Only the mappings you have just confirmed will be used. Fields marked ‘Create’ will be explicitly added to the collection. New values will be added and Master / Linked associations will be completed. No records will be deleted.",
    "Import / complément des référentiels en cours…\nAnalyse des relations et mise à jour de la collection.": "Importing / completing reference lists…\nAnalyzing relationships and updating the collection.",
    "Import de référentiels interrompu": "Reference-list import interrupted", "Import de référentiels terminé": "Reference-list import complete",
    "Correspondance des champs — {table}": "Field mapping — {table}",
    "G-Skol propose les correspondances trouvées. Vérifiez-les avant l'import : un seul champ doit être défini comme Maître ; les autres champs utiles sont Reliés. Dans la liste Champ G-Skol, choisissez un champ existant, « Créer » pour ajouter explicitement le champ à la collection, ou « Ne pas importer » pour ignorer la colonne.": "G-Skol suggests the mappings it found. Check them before importing: exactly one field must be defined as Master; the other useful fields are Linked. In the G-Skol Field list, choose an existing field, ‘Create’ to explicitly add the field to the collection, or ‘Do not import’ to ignore the column.",
    "Colonne Access (nom réel)": "Access column (actual name)", "Rôle": "Role", "Champ G-Skol (libellé actuel)": "G-Skol field (current label)",
    "Valider les correspondances": "Confirm mappings", "Correspondance incomplète": "Incomplete mapping",
    "Choisissez un champ G-Skol destination pour « {src} », « Créer », ou sélectionnez « Ne pas importer ».": "Choose a destination G-Skol field for ‘{src}’, ‘Create’, or select ‘Do not import’.",
    "Le champ G-Skol « {field} » est utilisé plusieurs fois. Choisissez une seule colonne source pour cette destination.": "The G-Skol field ‘{field}’ is used more than once. Choose only one source column for this destination.",
    "Un seul Maître est obligatoire pour ce référentiel.": "Exactly one Master is required for this reference list.",
    " — {count} champ(s) à créer": " — {count} field(s) to create",
    "Correspondance valide : 1 Maître et {count} champ(s) Relié(s){suffix}.": "Valid mapping: 1 Master and {count} Linked field(s){suffix}.",
})
EN.update({
    "✓ Collection sélectionnée : {name} — {file}": "✓ Selected collection: {name} — {file}",
    "  (liste des collections G-Skol détectées)": "  (detected G-Skol collections)",
    "Source : {name}": "Source: {name}",
    "Collections G-Skol (*.coldb);;Tous les fichiers (*.*)": "G-Skol collections (*.coldb);;All files (*.*)",
    "Classeurs Excel (*.xlsx);;Tous les fichiers (*.*)": "Excel workbooks (*.xlsx);;All files (*.*)",
    "Fichiers texte (*.csv *.txt *.tsv);;Tous les fichiers (*.*)": "Text files (*.csv *.txt *.tsv);;All files (*.*)",
    "Classeurs ODS (*.ods);;Tous les fichiers (*.*)": "ODS workbooks (*.ods);;All files (*.*)",
    "Fichiers DBF (*.dbf);;Tous les fichiers (*.*)": "DBF files (*.dbf);;All files (*.*)",
    "Bases SQLite (*.db *.sqlite *.sqlite3);;Tous les fichiers (*.*)": "SQLite databases (*.db *.sqlite *.sqlite3);;All files (*.*)",
})


# G-Skol 1.0.212 — complete English pass: Add records from an external source.
EN.update({
    "Ajouter des fiches depuis une source extérieure": "Add records from an external source",
    "Cette fonction ajoute de nouvelles fiches à la suite des fiches déjà présentes dans la collection G-Skol. Les fiches existantes ne sont jamais modifiées. Sources disponibles : Access, Excel .xlsx et CSV / TXT / TSV ; les autres formats suivront.": "This feature adds new records after the records already present in the G-Skol collection. Existing records are never modified. Available sources: Access, Excel .xlsx and CSV / TXT / TSV; other formats will follow.",
    "1. Collection G-Skol qui recevra les nouvelles fiches": "1. G-Skol collection that will receive the new records",
    "— Aucune collection sélectionnée —": "— No collection selected —",
    "2. Source contenant les fiches à ajouter": "2. Source containing the records to add",
    "Access, Excel .xlsx et CSV / TXT / TSV utilisent le même parcours : analyse, correspondances, sélection des fiches, ajout.": "Access, Excel .xlsx and CSV / TXT / TSV use the same workflow: analysis, mapping, record selection and addition.",
    "Analyser les données": "Analyze data",
    "3. Tables détectées dans la source Access": "3. Tables detected in the Access source",
    "Table / Champ": "Table / Field", "Type": "Type", "Lignes": "Rows",
    "Table contenant les fiches à ajouter :": "Table containing the records to add:",
    "Aucune analyse effectuée.": "No analysis performed.",
    "Correspondance des champs": "Field mapping",
    "4. Correspondance des champs": "4. Field mapping",
    "Pour chaque champ source, choisissez un champ G-Skol existant, « Ne pas importer » ou « Créer un nouveau champ… ». À ce stade, rien n’est créé ni modifié.": "For each source field, choose an existing G-Skol field, ‘Do not import’, or ‘Create a new field…’. At this stage, nothing is created or modified.",
    "Classer les champs G-Skol par ordre alphabétique (A → Z)": "Sort G-Skol fields alphabetically (A → Z)",
    "Champ source": "Source field", "Type du champ": "Field type", "Destination G-Skol / action": "G-Skol destination / action",
    "Choisissez la destination G-Skol de chaque champ source.": "Choose the G-Skol destination for each source field.",
    "Sécurité : les fiches G-Skol existantes ne seront jamais modifiées. Après la correspondance des champs, vous pourrez choisir exactement quelles lignes source seront ajoutées comme nouvelles fiches.": "Safety: existing G-Skol records will never be modified. After field mapping, you can choose exactly which source rows will be added as new records.",
    "Choisir les fiches à ajouter…": "Choose records to add…",
    "Choisir la base Access contenant les fiches à ajouter": "Choose the Access database containing the records to add",
    "✓ Source Access : {name}": "✓ Access source: {name}",
    "Source sélectionnée. Cliquez sur « Analyser les données ».": "Source selected. Click ‘Analyze data’.",
    "— Choisir une table —": "— Choose a table —",
    "Choisissez maintenant la table contenant les fiches à ajouter.": "Now choose the table containing the records to add.",
    "Préparation de la sélection": "Preparing selection",
    "Préparation des fiches Access…": "Preparing Access records…",
    "Sélection des fiches à ajouter": "Select records to add",
    "5. Sélection des fiches à ajouter — une ligne = une nouvelle fiche G-Skol": "5. Select records to add — one row = one new G-Skol record",
    "Toutes les fiches sont incluses au départ. Cliquez sur un en-tête pour trier (▲/▼), sélectionnez une ou plusieurs lignes par glisser, Ctrl ou Maj, puis utilisez le clic droit pour les ajouter ou les retirer de l'import.": "All records are included initially. Click a column header to sort (▲/▼), select one or more rows by dragging, Ctrl or Shift, then right-click to include or exclude them from the import.",
    "Ajouter tout": "Include all", "Supprimer tout": "Exclude all",
    "[donnée binaire]": "[binary data]",
    "{selected} fiche(s) à ajouter sur {total}": "{selected} record(s) to add out of {total}",
    "Ajouter à l'import": "Include in import", "Retirer de l'import": "Exclude from import",
    "Retour à la correspondance": "Back to mapping",
    "Valider la sélection": "Confirm selection",
    "Ajouter les fiches sélectionnées": "Add selected records",
    "Ajout des fiches": "Add records",
    "Aucune fiche n'est sélectionnée pour l'import.": "No record is selected for import.",
    "Confirmer l'ajout": "Confirm addition",
    "{count} nouvelle(s) fiche(s) vont être ajoutée(s) à la collection « {name} ».\n\nLes fiches déjà présentes ne seront pas modifiées. Continuer ?": "{count} new record(s) will be added to the collection “{name}”.\n\nExisting records will not be modified. Continue?",
    "Ajouter les fiches": "Add records",
    "L’import a été interrompu :\n{error}": "The import was interrupted:\n{error}",
    "Ajout terminé": "Addition complete",
    "{added} nouvelle(s) fiche(s) ajoutée(s).\n{photos} photo(s) importée(s).\n\nSauvegarde de sécurité : {backup}": "{added} new record(s) added.\n{photos} photo(s) imported.\n\nSafety backup: {backup}",
    "Ajout des nouvelles fiches…": "Adding new records…",
    "Monétaire": "Currency", "Liste / Référentiel": "List / Reference list",
    "— Ne pas importer —": "— Do not import —", "— Créer un nouveau champ… —": "— Create a new field… —",
})


EN.update({
    "Choisir la base Access contenant les fiches à ajouter": "Choose the Access database containing the records to add",
    "Analyse Access": "Access analysis",
    "{count} champ(s)": "{count} field(s)",
    "Analyse terminée : {tables} table(s), {fields} champ(s). Aucune donnée n'a été importée ni modifiée.": "Analysis complete: {tables} table(s), {fields} field(s). No data has been imported or modified.",
    "Préparation des fiches {kind}…": "Preparing {kind} records…",
    "Sélection des fiches": "Record selection",
})

EN.update({
    "Type détecté/proposé par G-Skol, modifiable ici. Si la destination est un champ G-Skol existant, son type réel reste prioritaire et n'est jamais modifié.": "Type detected/suggested by G-Skol; it can be changed here. If the destination is an existing G-Skol field, its actual type always takes priority and is never modified.",
    "Access consolidé(s)": "consolidated Access",
    "{fields} champ(s) {source} ; {auto} correspondance(s) proposée(s) automatiquement. Pour « Créer… », le type proposé peut être corrigé. Un champ G-Skol existant conserve toujours son type.": "{fields} {source} field(s); {auto} mapping(s) suggested automatically. For ‘Create…’, the suggested type can be changed. An existing G-Skol field always keeps its current type.",
})

# G-Skol 1.0.214 — external-record Excel workflow.
EN.update({
    "3. Feuilles détectées dans la source Excel": "3. Sheets detected in the Excel source",
    "Feuille contenant les fiches à ajouter :": "Sheet containing the records to add:",
    "Choisir un fichier Excel…": "Choose an Excel file…",
    "Aucun fichier Excel sélectionné.": "No Excel file selected.",
    "Choisir le fichier Excel contenant les fiches à ajouter": "Choose the Excel file containing the records to add",
    "✓ Source Excel : {name}": "✓ Excel source: {name}",
    "— Choisir une feuille —": "— Choose a sheet —",
    "Analyse terminée : {sheets} feuille(s), {fields} champ(s). Aucune donnée n'a été importée ni modifiée.": "Analysis complete: {sheets} sheet(s), {fields} field(s). No data has been imported or modified.",
    "Choisissez maintenant la feuille contenant les fiches à ajouter.": "Now choose the sheet containing the records to add.",
})

# G-Skol 1.0.219 — external-record ODS workflow.
EN.update({
    "3. Feuilles détectées dans la source ODS": "3. Sheets detected in the ODS source",
    "Choisir le fichier ODS contenant les fiches à ajouter": "Choose the ODS file containing the records to add",
    "✓ Source ODS : {name}": "✓ ODS source: {name}",
})

# G-Skol 1.0.220 — external-record DBF workflow.
EN.update({
    "3. Données détectées dans la source DBF": "3. Data detected in the DBF source",
    "Données contenant les fiches à ajouter :": "Data containing the records to add:",
    "Choisir le fichier DBF contenant les fiches à ajouter": "Choose the DBF file containing the records to add",
    "✓ Source DBF : {name}": "✓ DBF source: {name}",
    "— Choisir les données —": "— Choose data —",
    "Analyse terminée : {tables} source(s), {fields} champ(s), {rows} ligne(s). Aucune donnée n'a été importée ni modifiée.": "Analysis complete: {tables} source(s), {fields} field(s), {rows} row(s). No data has been imported or modified.",
    "Choisissez les données DBF contenant les fiches à ajouter.": "Choose the DBF data containing the records to add.",
})

# G-Skol 1.0.221 — external-record SQLite workflow.
EN.update({
    "3. Tables détectées dans la source SQLite": "3. Tables detected in the SQLite source",
    "Choisir la base SQLite contenant les fiches à ajouter": "Choose the SQLite database containing the records to add",
    "✓ Source SQLite : {name}": "✓ SQLite source: {name}",
    "Analyse terminée : {tables} table(s), {fields} champ(s), {rows} ligne(s). Aucune donnée n'a été importée ni modifiée.": "Analysis complete: {tables} table(s), {fields} field(s), {rows} row(s). No data has been imported or modified.",
    "Choisissez la table SQLite contenant les fiches à ajouter.": "Choose the SQLite table containing the records to add.",
})

# G-Skol 1.0.224 — model workshop tree.
EN.update({
    "Gestion des modèles de fiches": "Record template manager",
    "Choisissez un modèle à ouvrir ou organisez vos modèles personnels.": "Choose a template to open or organize your personal templates.",
    "Les 10 dossiers maîtres G-Skol et leur modèle maître sont protégés. Vous pouvez y créer des sous-dossiers et des modèles personnels. Vous pouvez aussi créer vos propres dossiers à la racine.": "The 10 G-Skol master folders and their master template are protected. You can create personal subfolders and templates inside them, or create your own folders at the root.",
    "Modèles de fiches": "Record templates", "Type": "Type",
    "Dossier maître": "Master folder", "Dossier personnel": "Personal folder",
    "Modèle maître": "Master template", "Protégé": "Protected", "Modèle personnel": "Personal template",
    "Nouveau modèle…": "New template…", "Nouveau dossier…": "New folder…", "Renommer…": "Rename…", "Déplacer vers…": "Move to…", "Supprimer…": "Delete…",
    "Nouveau dossier": "New folder", "Nom du dossier :": "Folder name:",
    "Nouveau modèle": "New template", "Nom du modèle :": "Template name:",
    "Nom déjà utilisé": "Name already in use", "Un dossier ou modèle porte déjà ce nom.": "A folder or template already has this name.",
    "Renommer": "Rename", "Nouveau nom :": "New name:", "Déplacer vers": "Move to", "Dossier de destination :": "Destination folder:",
    "Un dossier ou modèle porte déjà ce nom dans la destination.": "A folder or template with this name already exists in the destination.",
    "Supprimer": "Delete", "Supprimer définitivement « {0} » ?": "Permanently delete ‘{0}’?",
    "Ce modèle ne contient aucune collection.": "This template contains no collection.",
})

# G-Skol 1.0.226 — access to managed personal record templates from the collection workshop.
EN.update({
    "Ouvrir un modèle": "Open a template",
    "Choisissez un modèle personnel créé dans l’Atelier des modèles, ou ouvrez la bibliothèque classique.": "Choose a personal template created in the Template Workshop, or open the classic library.",
    "Bibliothèque classique…": "Classic library…",
})

# G-Skol 1.0.227 — Atelier : derniers écrans anglais
EN.update({
    "Atelier — Modèles de fiches": "Workshop — Record templates",
    "Que souhaitez-vous modifier ?": "What would you like to edit?",
    "Les deux modules utilisent le même moteur graphique, mais travaillent sur des éléments différents.": "Both modules use the same graphical engine, but work on different items.",
    "Modifier la fiche actuelle de la collection": "Edit the current collection record template",
    "Créer / modifier des modèles adaptés à une collection": "Create / edit templates for a collection",
    "Aucune collection n’est actuellement ouverte.": "No collection is currently open.",
    "Gestion des référentiels": "Reference list manager",
    "Référentiel :": "Reference list:",
    "Ordre des valeurs :": "Value order:",
    "Croissant (A → Z)": "Ascending (A → Z)",
    "Décroissant (Z → A)": "Descending (Z → A)",
    "Personnalisé": "Custom",
    "Trier la liste des référentiels": "Sort reference lists",
    "Nouvelle valeur": "New value",
    "Ajouter": "Add",
    "Ajouter des\nvaleurs…": "Add\nvalues…",
    "Créer un\nréférentiel…": "Create a\nreference list…",
    "Retirer de\nla liste": "Remove from\nlist",
    "Annuler la dernière modification du référentiel": "Undo the last reference-list change",
    "Rétablir la dernière modification annulée": "Redo the last undone change",
    "Créer un nouveau champ Liste dans la palette et importer simultanément son référentiel": "Create a new List field in the palette and import its reference list at the same time",
    "Choisir les données à importer": "Choose data to import",
    "Éditeur d’états": "Report editor",
    "Atelier de conception avancée : choisissez un état existant puis ouvrez-le avec Modifier pour accéder aux réglages fins.": "Advanced design workshop: choose an existing report, then open it with Edit to access fine settings.",
    "Choisissez un état enregistré. Le double-clic ouvre directement son éditeur avancé.": "Choose a saved report. Double-click a report to open its advanced editor directly.",
    "États disponibles dans l’éditeur": "Reports available in the editor",
    "Atelier — Éditeur d’états — {name}": "Workshop — Report editor — {name}",
})

# G-Skol 1.0.231 — German translation, stage 2: Collection/Workshop sub-screens.
DE.update({
    # Reports
    "Consulter les états enregistrés ou créer une présentation détaillée ou résumée de la collection.": "Gespeicherte Berichte anzeigen oder eine detaillierte bzw. zusammengefasste Darstellung der Sammlung erstellen.",
    "Quel type d’état souhaitez-vous créer ?": "Welche Art von Bericht möchten Sie erstellen?",
    "État détaillé": "Detaillierter Bericht", "État résumé": "Zusammengefasster Bericht",
    "Afficher les fiches une par une, avec les champs choisis.": "Datensätze einzeln mit den ausgewählten Feldern anzeigen.",
    "Regrouper les fiches et afficher uniquement les totaux ou synthèses.": "Datensätze gruppieren und nur Summen oder Zusammenfassungen anzeigen.",
    "Créer": "Erstellen", "États enregistrés": "Gespeicherte Berichte", "États détaillés": "Detaillierte Berichte", "États résumés": "Zusammengefasste Berichte",
    "Ouvrir un modèle d’État…": "Berichtsvorlage öffnen…", "Modifier": "Bearbeiten", "Renommer": "Umbenennen", "Dupliquer": "Duplizieren", "Supprimer": "Löschen", "Dossiers…": "Ordner…",
    # Table view
    "Une ligne = une fiche. Cliquez sur un titre pour trier, déplacez ou redimensionnez les colonnes à la souris.": "Eine Zeile = ein Datensatz. Klicken Sie zum Sortieren auf eine Überschrift; Spalten können mit der Maus verschoben oder in der Größe geändert werden.",
    "Choisir les colonnes…": "Spalten auswählen…", "Mise en page…": "Seite einrichten…", "Imprimer": "Drucken",
    "Modèle actif : Vue actuelle": "Aktive Vorlage: Aktuelle Ansicht", "Vue :": "Ansicht:", "— Vue actuelle —": "— Aktuelle Ansicht —",
    "Enregistrer la vue…": "Ansicht speichern…", "Ouvrir un modèle…": "Vorlage öffnen…", "Enregistrer ce modèle": "Diese Vorlage speichern", "Mettre à jour": "Aktualisieren", "Renommer…": "Umbenennen…", "Supprimer…": "Löschen…",
    "Filtrer :": "Filtern:", "Tous": "Alle", "Tapez une valeur…": "Wert eingeben…", "Ajouter ce filtre": "Diesen Filter hinzufügen", "Effacer les filtres": "Filter löschen",
    "Aucun filtre épinglé — la saisie ci-dessus filtre immédiatement le tableau.": "Kein Filter angeheftet — die Eingabe oben filtert die Tabelle sofort.",
    "Tri : cliquez sur l’en-tête d’une colonne": "Sortierung: Klicken Sie auf eine Spaltenüberschrift",
    "Défaire": "Rückgängig", "Refaire": "Wiederholen", "Copier la fiche": "Datensatz kopieren", "Coller la fiche": "Datensatz einfügen", "Vider": "Leeren", "Ouvrir la fiche": "Datensatz öffnen", "Retour": "Zurück",
    # Toolbox
    "Ces outils agissent volontairement sur l’ensemble de la collection. G-Skol indique toujours le nombre de fiches concernées avant toute modification.": "Diese Werkzeuge wirken bewusst auf die gesamte Sammlung. G-Skol zeigt vor jeder Änderung immer die Anzahl der betroffenen Datensätze an.",
    "Remplacer une valeur dans toute la collection": "Einen Wert in der gesamten Sammlung ersetzen", "Champ :": "Feld:", "Valeur à remplacer :": "Zu ersetzender Wert:", "Nouvelle valeur :": "Neuer Wert:", "Résultat :": "Ergebnis:",
    "Le remplacement porte sur la valeur complète du champ, et non sur une partie du texte.": "Die Ersetzung betrifft den vollständigen Feldwert und nicht nur einen Teil des Textes.", "Remplacer": "Ersetzen",
    "Compléter les champs vides": "Leere Felder ausfüllen", "Valeur à inscrire :": "Einzutragender Wert:", "Seules les fiches dont ce champ est vide seront complétées. Les valeurs déjà présentes ne seront jamais modifiées.": "Nur Datensätze mit leerem Feld werden ergänzt. Bereits vorhandene Werte werden niemals geändert.", "Compléter": "Ausfüllen",
    "Dupliquer la structure de la collection": "Sammlungsstruktur duplizieren", "Dupliquer la structure de cette collection": "Struktur dieser Sammlung duplizieren",
    "Crée une collection sœur vide, identique à celle-ci. La Fiche, les paramètres et les référentiels sont conservés, mais les fiches, leurs données et leurs photos ne sont pas copiées. La première fiche créée portera le N° 1.": "Erstellt eine leere Schwestersammlung, die mit dieser identisch ist. Datensatzvorlage, Einstellungen und Referenzlisten bleiben erhalten; Datensätze, deren Daten und Fotos werden nicht kopiert. Der erste neu erstellte Datensatz erhält die Nr. 1.",
    "Fermer": "Schließen",
    # Query
    "Constructeur de requête multicritère": "Mehrkriterien-Abfrage erstellen", "Modèle :": "Vorlage:", "Modèle actif :": "Aktive Vorlage:",
    "Choisissez un champ : G-Skol adapte automatiquement les comparaisons possibles. À partir de la deuxième ligne, utilisez ET pour restreindre le résultat ou OU pour l’élargir.": "Wählen Sie ein Feld: G-Skol passt die möglichen Vergleiche automatisch an. Verwenden Sie ab der zweiten Zeile UND, um das Ergebnis einzuschränken, oder ODER, um es zu erweitern.",
    "Requête enregistrée :": "Gespeicherte Abfrage:", "Enregistrer la requête…": "Abfrage speichern…", "Enregistrer ce modèle": "Diese Vorlage speichern", "Mode de classement :": "Sortiermodus:", "Alphabétique": "Alphabetisch", "Lien": "Verknüpfung", "Champ": "Feld", "Comparaison": "Vergleich", "Valeur": "Wert", "Contient": "Enthält", "+ Ajouter un critère": "+ Kriterium hinzufügen", "Réinitialiser la requête": "Abfrage zurücksetzen", "Exécuter la requête": "Abfrage ausführen",
    # Quick statistics
    "Répartition des fiches par champ": "Verteilung der Datensätze nach Feld", "Graphique :": "Diagramm:", "Barres horizontales": "Horizontale Balken", "Actualiser": "Aktualisieren",
    # Import/export hub
    "Import / Export / Sauvegarde": "Import / Export / Sicherung", "Que voulez-vous faire ? Choisissez d’abord une famille d’opérations. G-Skol vous proposera ensuite les traitements correspondants.": "Was möchten Sie tun? Wählen Sie zuerst eine Vorgangsgruppe. G-Skol zeigt Ihnen anschließend die entsprechenden Funktionen an.",
    "Importation": "Import", "Exportation": "Export", "Sauvegarde / Restauration": "Sicherung / Wiederherstellung", "Créer ou enrichir une collection à partir de sources extérieures.": "Eine Sammlung aus externen Quellen erstellen oder ergänzen.",
    # Workshop chooser
    "Que souhaitez-vous modifier ?": "Was möchten Sie bearbeiten?", "Les deux modules utilisent le même moteur graphique, mais travaillent sur des éléments différents.": "Beide Module verwenden dieselbe Grafik-Engine, bearbeiten jedoch unterschiedliche Elemente.",
    "Modifier la fiche actuelle de la collection": "Aktuellen Datensatz der Sammlung bearbeiten", "Créer / modifier des modèles adaptés à une collection": "Für eine Sammlung geeignete Vorlagen erstellen / bearbeiten",
    # Report editor
    "Atelier de conception avancée : choisissez un état existant puis ouvrez-le avec Modifier pour accéder aux réglages fins.": "Erweiterte Entwurfswerkstatt: Wählen Sie einen vorhandenen Bericht und öffnen Sie ihn mit Bearbeiten, um auf die Feineinstellungen zuzugreifen.",
    "Choisissez un état enregistré. Le double-clic ouvre directement son éditeur avancé.": "Wählen Sie einen gespeicherten Bericht. Ein Doppelklick öffnet direkt den erweiterten Editor.", "États disponibles dans l’éditeur": "Im Editor verfügbare Berichte",
    # Reference lists
    "Gestion des référentiels": "Referenzlistenverwaltung", "Référentiel :": "Referenzliste:", "--- Créer un référentiel ---": "--- Referenzliste erstellen ---", "Ordre des valeurs :": "Reihenfolge der Werte:", "Croissant (A → Z)": "Aufsteigend (A → Z)", "Décroissant (Z → A)": "Absteigend (Z → A)", "Personnalisé": "Benutzerdefiniert", "Nouvelle valeur": "Neuer Wert", "Ajouter": "Hinzufügen", "Ajouter des\nvaleurs…": "Werte\nhinzufügen…", "Créer un\nréférentiel…": "Referenzliste\nerstellen…", "Retirer de\nla liste": "Aus der Liste\nentfernen",
    # Settings
    "Paramètres de G-Skol": "G-Skol-Einstellungen", "Paramètres généraux — G-Skol": "Allgemeine Einstellungen — G-Skol", "Rouvrir la dernière collection au démarrage": "Beim Start die zuletzt verwendete Sammlung wieder öffnen", "Paramètres de la collection ouverte": "Einstellungen der geöffneten Sammlung", "Nom :": "Name:", "Le nom et le dossier se modifient depuis « Ouvrir une collection ».": "Name und Ordner werden über „Sammlung öffnen“ geändert.", "Couleur de la fiche et de la collection :": "Farbe des Datensatzes und der Sammlung:", "Choisir la couleur…": "Farbe auswählen…", "À l’ouverture de la Fiche :": "Beim Öffnen der Datensätze:", "Dernière fiche consultée": "Zuletzt angezeigter Datensatz", "Première fiche": "Erster Datensatz", "Enregistrer": "Speichern",
    "Aucune collection ouverte. Ses réglages apparaîtront ici après ouverture.": "Keine Sammlung geöffnet. Die Einstellungen werden hier nach dem Öffnen angezeigt."
})

# G-Skol 1.0.232 — German translation, stage 4: real Record window system interface.
DE.update({
    "Aperçu temporaire — ": "Temporäre Vorschau — ",
    "Fiches — ": "Datensätze — ",
    "Affichage": "Ansicht",
    "Taille par défaut de la fiche": "Standardgröße des Datensatzfensters",
    "Rétablir la taille compacte MM3 et recentrer la fiche sur l’écran actuel.": "Die kompakte Standardgröße wiederherstellen und das Datensatzfenster auf dem aktuellen Bildschirm zentrieren.",
    "N° de fiche": "Datensatz-Nr.",
    "État de la fiche": "Datensatzstatus", "Etat de la fiche": "Datensatzstatus",
    "Vider la fiche": "Datensatz leeren",
    "Restaurer la fiche": "Datensatz wiederherstellen",
    "Première": "Erster",
    "Précédente": "Zurück",
    "Suivante": "Weiter",
    "Dernière": "Letzter",
    "Créer une nouvelle fiche": "Neuen Datensatz erstellen",
    "Enregistrer la fiche": "Datensatz speichern",
    "Fermer la fiche": "Datensatz schließen",
    "Bandeau": "Kopfbereich",
    "Aucune fiche": "Kein Datensatz",
    "Fiche {current} sur {total}": "Datensatz {current} von {total}",
    "Résultat {current} sur {total}": "Ergebnis {current} von {total}",
    "Cliquer pour aller directement à un N° de fiche": "Klicken, um direkt zu einer Datensatz-Nr. zu wechseln",
    "Rechercher rapidement une fiche": "Datensatz schnell suchen",
    "Quitter la recherche et revenir à toute la collection": "Suche beenden und zur gesamten Sammlung zurückkehren",
    "Effacer le contenu de cette fiche en conservant son N° et la marquer Libre": "Inhalt dieses Datensatzes löschen, seine Nr. beibehalten und ihn als Frei markieren",
    "Restaurer la fiche telle qu'elle était juste avant le dernier vidage": "Den Datensatz auf den Stand unmittelbar vor dem letzten Leeren wiederherstellen",
})


# G-Skol 1.0.235 — German global pass, audit from 1.0.234 screenshots.
DE.update({
    # Generic record/report/table vocabulary
    "N° de fiche":"Datensatz-Nr.", "État de la fiche":"Datensatzstatus", "Etat de la fiche": "Datensatzstatus", "Vérifier":"Prüfen", "Libre":"Frei",
    "Classe":"Klasse", "Contact":"Kontakt", "Date":"Datum", "Département":"Département", "Description":"Beschreibung",
    "Embranchement":"Stamm", "Épaisseur mm":"Dicke mm", "Époque / Série":"Epoche / Serie", "Ère":"Ära", "Espèce":"Art", "Étage":"Stufe",
    "Famille":"Familie", "Genre":"Gattung", "Largeur mm":"Breite mm", "Longueur mm":"Länge mm", "Poids Gr":"Gewicht g",
    "Origine":"Herkunft", "Lieu":"Ort", "Prix":"Preis", "Pays":"Land", "Région":"Region", "Période":"Periode", "Ordre":"Ordnung",
    "Site":"Fundort", "Acquisition":"Erwerb", "Provenance":"Herkunft", "Collection":"Sammlung", "Taxonomie":"Taxonomie",
    "Datation / Spécimen":"Datierung / Exemplar", "Photo":"Foto", "Inconnu":"Unbekannt", "Achat":"Kauf", "Vendeur":"Verkäufer",
    "Nouvelle fiche":"Neuer Datensatz", "New record":"Neuer Datensatz",
    "{count} record(s) affected":"{count} Datensatz/Datensätze betroffen", "{count} fiche(s) concernée(s)":"{count} Datensatz/Datensätze betroffen",
    "{records} fiche(s) · {values} valeur(s) distincte(s)":"{records} Datensatz/Datensätze · {values} verschiedene Werte",
    "{records} record(s) · {values} distinct value(s)":"{records} Datensatz/Datensätze · {values} verschiedene Werte",
    # Report builders
    "Nouveau modèle d’État":"Neue Berichtsvorlage", "New report template":"Neue Berichtsvorlage",
    "Construction de l'état résumé":"Layout des zusammengefassten Berichts", "Summary report layout":"Layout des zusammengefassten Berichts",
    "Construction de l’état résumé":"Layout des zusammengefassten Berichts", "Construction de l'état détaillé":"Layout des detaillierten Berichts", "Detailed report layout":"Layout des detaillierten Berichts",
    "Titre de l’état :":"Berichtstitel:", "Report title:":"Berichtstitel:", "Bandeau :":"Kopfbereich:", "Header:":"Kopfbereich:",
    "Libellés de colonnes :":"Spaltenbeschriftungen:", "Column headers:":"Spaltenbeschriftungen:", "Column labels:":"Spaltenbeschriftungen:",
    "Champ maître :":"Hauptfeld:", "Master field:":"Hauptfeld:", "Champs reliés :":"Verknüpfte Felder:", "Linked fields:":"Verknüpfte Felder:",
    "Totaux par valeur maître :":"Summen je Hauptwert:", "Totals per master value:":"Summen je Hauptwert:",
    "Champs complémentaires :":"Zusätzliche Felder:", "Additional fields:":"Zusätzliche Felder:", "Pied de page :":"Fußzeile:", "Footer:":"Fußzeile:",
    "N° de page :":"Seitennummer:", "Page number:":"Seitennummer:", "Imprimer le titre":"Titel drucken", "Print title":"Titel drucken",
    "Source :":"Quelle:", "Source:":"Quelle:", "Toute la collection":"Gesamte Sammlung", "Entire collection":"Gesamte Sammlung",
    "Orientation :":"Ausrichtung:", "Orientation:":"Ausrichtung:", "Portrait":"Hochformat", "Paysage":"Querformat", "Landscape":"Querformat",
    "Glissez un champ dans la mise en page":"Feld in das Layout ziehen", "Drag a field to the layout":"Feld in das Layout ziehen", "Total":"Summe",
    "Éléments de mise en page":"Layoutelemente", "Layout elements":"Layoutelemente", "+ Interligne":"+ Abstand", "+ Spacing":"+ Abstand", "+ Filet":"+ Linie", "+ Rule":"+ Linie",
    "Effacer la mise en page":"Layout leeren", "Clear layout":"Layout leeren", "Centré":"Zentriert", "Centered":"Zentriert", "Haut":"Oben", "Top":"Oben", "Bas":"Unten", "Bottom":"Unten",
    "Ajouter un total ▾":"Summe hinzufügen ▾", "Add a total ▾":"Summe hinzufügen ▾", "Enregistrer sous…":"Speichern unter…", "Save":"Speichern", "Preview":"Vorschau", "Print":"Drucken",
    "Insérer un interligne":"Abstand einfügen", "Insert spacing":"Abstand einfügen", "Insérer un filet":"Linie einfügen", "Insert a rule":"Linie einfügen", "Position :":"Position:", "Position:":"Position:",
    "Sous le titre":"Unter dem Titel", "Below title":"Unter dem Titel", "Sous le bandeau":"Unter dem Kopfbereich", "Below header":"Unter dem Kopfbereich",
    "Entre les champs maîtres":"Zwischen den Hauptfeldern", "Between master fields":"Zwischen den Hauptfeldern", "Sous les libellés de colonnes":"Unter den Spaltenbeschriftungen", "Below column labels":"Unter den Spaltenbeschriftungen",
    "Entre les lignes de données":"Zwischen den Datenzeilen", "Between data rows":"Zwischen den Datenzeilen", "Entre les données et le filet de pied":"Zwischen Daten und Fußlinie", "Between data and footer rule":"Zwischen Daten und Fußlinie", "Avant le pied de page":"Vor der Fußzeile", "Before footer":"Vor der Fußzeile",
    # Query extras
    "Nouvelle requête":"Neue Abfrage", "Alphabétique inverse":"Alphabetisch umgekehrt", "ET":"UND", "OU":"ODER", "Supprimer":"Löschen",
    "Requête enregistrée « {name} » chargée. Cliquez sur Exécuter la requête.":"Gespeicherte Abfrage „{name}“ geladen. Klicken Sie auf Abfrage ausführen.",
    # Statistics
    "Colonnes":"Säulen", "Columns":"Säulen", "Camembert":"Kreisdiagramm", "Pie chart":"Kreisdiagramm",
    # Import hub / workflows
    "Import":"Import", "Choisissez le type d’import. G-Skol vous guidera ensuite pas à pas dans le module correspondant.":"Wählen Sie die Importart. G-Skol führt Sie anschließend Schritt für Schritt durch das entsprechende Modul.",
    "Importation et création d’une collection":"Importieren und Sammlung erstellen", "Import and create a collection":"Importieren und Sammlung erstellen",
    "Créer une nouvelle collection G-Skol à partir d’une source extérieure.":"Eine neue G-Skol-Sammlung aus einer externen Quelle erstellen.",
    "Importation de référentiels dans une collection existante":"Referenzlisten in eine vorhandene Sammlung importieren", "Import reference lists into an existing collection":"Referenzlisten in eine vorhandene Sammlung importieren",
    "Ajouter des fiches depuis une source extérieure":"Datensätze aus einer externen Quelle hinzufügen", "Add records from an external source":"Datensätze aus einer externen Quelle hinzufügen",
    "Importer un modèle G-Skol (.colmod)":"G-Skol-Vorlage (.colmod) importieren", "Import a G-Skol template (.colmod)":"G-Skol-Vorlage (.colmod) importieren",
    "Importer un modèle G-Skol":"G-Skol-Vorlage importieren", "Modèle :":"Vorlage:", "Parcourir…":"Durchsuchen…", "Choisir le dossier et importer…":"Ordner auswählen und importieren…",
    "Choisissez le modèle reçu. G-Skol reconnaîtra automatiquement s’il s’agit d’un modèle de Fiche, de Tableau, de Requête ou d’État, puis vous proposera la bibliothèque correspondante. Aucune collection ne sera modifiée.":"Wählen Sie die erhaltene Vorlage. G-Skol erkennt automatisch, ob es sich um eine Datensatz-, Tabellen-, Abfrage- oder Berichtsvorlage handelt, und schlägt anschließend die passende Bibliothek vor. Keine Sammlung wird verändert.",
    "Le modèle importé rejoint simplement la bibliothèque correspondante. Pour l’utiliser, ouvrez ensuite une collection et choisissez ce modèle depuis le module correspondant.":"Die importierte Vorlage wird lediglich der entsprechenden Bibliothek hinzugefügt. Um sie zu verwenden, öffnen Sie anschließend eine Sammlung und wählen Sie die Vorlage im entsprechenden Modul aus.",
    "Importation de référentiels dans une collection G-Skol existante":"Referenzlisten in eine vorhandene G-Skol-Sammlung importieren",
    "1. Collection G-Skol de destination":"1. G-Skol-Zielsammlung", "Sélectionner une collection…":"Sammlung auswählen…", "2. Source des référentiels":"2. Quelle der Referenzlisten",
    "3. Référentiels à importer — cochez uniquement ceux que vous voulez ajouter ou compléter.":"3. Zu importierende Referenzlisten — markieren Sie nur diejenigen, die Sie hinzufügen oder ergänzen möchten.",
    "Référentiel / Champ":"Referenzliste / Feld", "Destination G-Skol":"G-Skol-Ziel", "Lignes":"Zeilen", "Tout cocher":"Alle markieren", "Tout décocher":"Alle abwählen",
    "Choisir une base SQLite…":"SQLite-Datenbank auswählen…", "Analyser les référentiels":"Referenzlisten analysieren", "Aucune source sélectionnée.":"Keine Quelle ausgewählt.",
    "Choisissez d’abord la collection, puis la source contenant les référentiels.":"Wählen Sie zuerst die Sammlung und dann die Quelle mit den Referenzlisten.", "Importer / compléter les référentiels…":"Referenzlisten importieren / ergänzen…",
    "Collection G-Skol qui recevra les nouvelles fiches":"G-Skol-Sammlung, die die neuen Datensätze erhält", "Source contenant les fiches à ajouter":"Quelle mit den hinzuzufügenden Datensätzen",
    "Tables détectées dans la source Access":"In der Access-Quelle erkannte Tabellen", "Table contenant les fiches à ajouter :":"Tabelle mit den hinzuzufügenden Datensätzen:", "Aucune analyse effectuée.":"Keine Analyse durchgeführt.",
    "Sélectionner une collection...":"Sammlung auswählen…", "Choisir une base Access...":"Access-Datenbank auswählen…", "Analyser les données":"Daten analysieren",
    "Aucune base Access sélectionnée.":"Keine Access-Datenbank ausgewählt.", "Sécurité : les fiches G-Skol existantes ne seront jamais modifiées. Après la correspondance des champs, vous pourrez choisir exactement quelles lignes source seront ajoutées comme nouvelles fiches.":"Sicherheit: Vorhandene G-Skol-Datensätze werden niemals geändert. Nach der Feldzuordnung können Sie genau auswählen, welche Quellzeilen als neue Datensätze hinzugefügt werden.",
    # Access creation screen
    "Microsoft Access":"Microsoft Access", "Choisir une base Access…":"Access-Datenbank auswählen…", "Analyser la base":"Datenbank analysieren", "Aucun fichier Access sélectionné.":"Keine Access-Datei ausgewählt.",
    "Après analyse, les tables et leurs champs apparaîtront ci-dessous.":"Nach der Analyse werden die Tabellen und ihre Felder unten angezeigt.", "Table / Champ":"Tabelle / Feld", "Type":"Typ", "Lignes":"Zeilen",
    "Choisir cette table":"Diese Tabelle auswählen", "Aperçu des données…":"Datenvorschau…", "Correspondance des champs…":"Feldzuordnung…", "Créer la collection G-Skol et importer…":"G-Skol-Sammlung erstellen und importieren…",
    # Table view residuals
    "151 fiches":"151 Datensätze", "Double-cliquez une cellule pour la corriger ; N° ouvre la fiche. Flèche BAS valide et passe à la cellule suivante.":"Doppelklicken Sie auf eine Zelle, um sie zu bearbeiten; Nr. öffnet den Datensatz. Pfeil NACH UNTEN bestätigt und wechselt zur nächsten Zelle.",
})


# G-Skol 1.0.236 — German global pass 2: residual audit from user screenshots.
DE.update({
    # Record template workshop (legacy English/French literals)
    "Atelier - Modèles":"Werkstatt - Vorlagen", "Workshop - Templates":"Werkstatt - Vorlagen",
    "Modèle actif :":"Aktive Vorlage:", "Active template:":"Aktive Vorlage:",
    "Personnalisez ici le modèle de fiche utilisé pour cette collection. Tout ajout ou modification sera visible immédiatement.":"Passen Sie hier die für diese Sammlung verwendete Datensatzvorlage an. Jede Ergänzung oder Änderung ist sofort sichtbar.",
    "Customize the record template used for this collection here. Any addition or change will be visible immediately.":"Passen Sie hier die für diese Sammlung verwendete Datensatzvorlage an. Jede Ergänzung oder Änderung ist sofort sichtbar.",
    "Champ (glisser pour réordonner)":"Feld (zum Sortieren ziehen)", "Field (drag to reorder)":"Feld (zum Sortieren ziehen)",
    "Aperçu en direct de la fiche":"Live-Vorschau des Datensatzes", "Live record preview":"Live-Vorschau des Datensatzes",
    "Cliquez sur un champ pour le sélectionner, déplacez-le à la souris, puis affinez avec les flèches.":"Klicken Sie auf ein Feld, um es auszuwählen; verschieben Sie es mit der Maus und nehmen Sie die Feinabstimmung mit den Pfeiltasten vor.",
    "Click a field to select it, drag it with the mouse, then fine-tune with the arrow keys.":"Klicken Sie auf ein Feld, um es auszuwählen; verschieben Sie es mit der Maus und nehmen Sie die Feinabstimmung mit den Pfeiltasten vor.",
    "Détacher les champs":"Felder lösen", "Détacher la palette des champs":"Feldpalette lösen", "Rattacher la palette des champs":"Feldpalette andocken", "Afficher la palette des champs":"Feldpalette anzeigen", "Detach fields":"Felder lösen", "+ Ajouter un champ":"+ Feld hinzufügen", "+ Add field":"+ Feld hinzufügen",
    "+ Ajouter un cadre":"+ Rahmen hinzufügen", "+ Add frame":"+ Rahmen hinzufügen", "+ Ajouter un cadre Photo":"+ Fotorahmen hinzufügen", "+ Add Photo frame":"+ Fotorahmen hinzufügen",
    "Tout sélectionner":"Alle auswählen", "Select all":"Alle auswählen", "Ordre de tabulation = ordre visuel":"Tab-Reihenfolge = visuelle Reihenfolge", "Tab order = visual order":"Tab-Reihenfolge = visuelle Reihenfolge",
    "Couleur de la fiche…":"Datensatzfarbe…", "Record color…":"Datensatzfarbe…", "Style par défaut":"Standardstil", "Default style":"Standardstil",
    "Aperçu dans la Fiche":"Vorschau im Datensatz", "Preview in Record":"Vorschau im Datensatz", "Enregistrer le modèle":"Vorlage speichern", "Save template":"Vorlage speichern",
    "La grille apparaît uniquement en mode conception. Ctrl+clic ou lasso = sélection multiple ; flèches = ajustement au pixel. Les huit poignées redimensionnent largeur, hauteur ou les deux ; Aligner utilise toujours le bord extérieur correspondant.":"Das Raster erscheint nur im Entwurfsmodus. Strg+Klick oder Lasso = Mehrfachauswahl; Pfeiltasten = pixelgenaue Anpassung. Die acht Griffe ändern Breite, Höhe oder beides; Ausrichten verwendet immer die entsprechende Außenkante.",
    "The grid appears only in design mode. Ctrl+click or lasso = multiple selection; arrow keys = pixel adjustment. Eight handles resize width, height, or both; Align always uses the corresponding outermost edge.":"Das Raster erscheint nur im Entwurfsmodus. Strg+Klick oder Lasso = Mehrfachauswahl; Pfeiltasten = pixelgenaue Anpassung. Die acht Griffe ändern Breite, Höhe oder beides; Ausrichten verwendet immer die entsprechende Außenkante.",
    "Charger un modèle depuis la bibliothèque Modèles de Fiches":"Eine Vorlage aus der Bibliothek Datensatzvorlagen laden", "Load a template from the Record Templates library":"Eine Vorlage aus der Bibliothek Datensatzvorlagen laden",
    # Reports and preview
    "Berichte — Template:":"Berichte — Vorlage:", "Template:":"Vorlage:", "Active template:":"Aktive Vorlage:",
    "Report title:":"Berichtstitel:", "Column headers:":"Spaltenüberschriften:", "Column labels:":"Spaltenbeschriftungen:", "Linked fields:":"Verknüpfte Felder:",
    "Layout elements":"Layoutelemente", "Clear layout":"Layout leeren", "Save report":"Bericht speichern", "Save":"Speichern", "Preview":"Vorschau", "Print":"Drucken",
    "Charger un modèle depuis la bibliothèque Modèles d’États":"Eine Vorlage aus der Bibliothek Berichtsvorlagen laden", "Load a template from the Report Templates library":"Eine Vorlage aus der Bibliothek Berichtsvorlagen laden",
    "Conserver directement cet état dans la bibliothèque Modèles d’États":"Diesen Bericht direkt in der Bibliothek Berichtsvorlagen speichern",
    "Aperçu":"Vorschau", "Preview — ":"Vorschau — ", "Click a heading to sort. Drag headings to reorder columns and resize them with the mouse.":"Klicken Sie zum Sortieren auf eine Überschrift. Ziehen Sie Überschriften, um Spalten neu anzuordnen, und ändern Sie ihre Größe mit der Maus.",
    "Zoom:":"Zoom:", "Alternating shaded rows":"Abwechselnd schattierte Zeilen", "Shaded totals band":"Schattiertes Summenband", "Edit":"Bearbeiten",
    # Table dialogs / print preview
    "Colonnes à afficher":"Anzuzeigende Spalten", "Cochez les informations que vous souhaitez voir. Le N° de fiche reste toujours affiché.":"Markieren Sie die Informationen, die angezeigt werden sollen. Die Datensatz-Nr. bleibt immer sichtbar.",
    "Tout désélectionner":"Alle abwählen", "Mise en page du Tableau":"Tabellenlayout", "Réglages globaux de présentation. L'alignement d'une colonne se règle directement par clic droit sur son en-tête.":"Globale Darstellungseinstellungen. Die Ausrichtung einer Spalte wird direkt per Rechtsklick auf ihre Überschrift eingestellt.",
    "En-têtes de colonnes":"Spaltenüberschriften", "Données du tableau":"Tabellendaten", "Police :":"Schriftart:", "Taille :":"Größe:", "Gras":"Fett", "Italique":"Kursiv", "Souligné":"Unterstrichen", "Texte":"Text", "Fond":"Hintergrund",
    "Traits":"Linien", "Bordures :":"Rahmen:", "Toutes":"Alle", "Traits lignes :":"Zeilenlinien:", "Traits colonnes :":"Spaltenlinien:", "Impression":"Druck", "Afficher le repère de largeur A4":"A4-Breitenmarkierung anzeigen", "Aperçu dynamique":"Dynamische Vorschau", "Réinitialiser":"Zurücksetzen",
    "Aperçu avant impression — Tableau":"Druckvorschau — Tabelle",
    # Query residuals
    "Constructeur de requête multicritère":"Mehrkriterien-Abfrage erstellen", "Modèle actif :":"Aktive Vorlage:", "Choisissez un champ : G-Skol adapte automatiquement les comparaisons possibles. À partir de la deuxième ligne, utilisez ET pour restreindre le résultat ou OU pour l’élargir.":"Wählen Sie ein Feld: G-Skol passt die möglichen Vergleiche automatisch an. Verwenden Sie ab der zweiten Zeile UND, um das Ergebnis einzuschränken, oder ODER, um es zu erweitern.",
    "Requête enregistrée :":"Gespeicherte Abfrage:", "Enregistrer la requête…":"Abfrage speichern…", "Ouvrir un modèle…":"Vorlage öffnen…", "Enregistrer ce modèle":"Diese Vorlage speichern", "Mettre à jour":"Aktualisieren", "Renommer…":"Umbenennen…", "Dupliquer…":"Duplizieren…", "Dossiers…":"Ordner…", "Mode de classement :":"Sortierung:", "Lien":"Verknüpfung", "Champ":"Feld", "Comparaison":"Vergleich", "Valeur":"Wert", "+ Ajouter un critère":"+ Kriterium hinzufügen", "Réinitialiser la requête":"Abfrage zurücksetzen", "Exécuter la requête":"Abfrage ausführen",
    "Charger un modèle depuis la bibliothèque Modèles de Requêtes":"Eine Vorlage aus der Bibliothek Abfragevorlagen laden",
    # Settings / import residual prose
    "Paramètres de la collection ouverte":"Einstellungen der geöffneten Sammlung", "À l’ouverture de la Fiche :":"Beim Öffnen der Datensätze:",
    "Create a new G-Skol collection from an external source. First choose the format; G-Skol will then analyze the source before creating anything.":"Erstellen Sie eine neue G-Skol-Sammlung aus einer externen Quelle. Wählen Sie zuerst das Format; G-Skol analysiert anschließend die Quelle, bevor etwas erstellt wird.",
    "Choose an .accdb or .mdb database. G-Skol can examine its structure without importing or modifying any data.":"Wählen Sie eine .accdb- oder .mdb-Datenbank. G-Skol kann ihre Struktur untersuchen, ohne Daten zu importieren oder zu verändern.",
    "Select a table from the list above. Field rows cannot be selected as the source.":"Wählen Sie eine Tabelle aus der obigen Liste. Feldzeilen können nicht als Quelle ausgewählt werden.",
    "After confirming the source table, the next step will prepare the mapping between Access fields and G-Skol fields.":"Nach Bestätigung der Quelltabelle wird im nächsten Schritt die Zuordnung zwischen Access-Feldern und G-Skol-Feldern vorbereitet.",
    "Selected collection:":"Ausgewählte Sammlung:", "No collection selected.":"Keine Sammlung ausgewählt.", "No collection selected":"Keine Sammlung ausgewählt", "First choose the collection, then the source containing the reference lists.":"Wählen Sie zuerst die Sammlung und dann die Quelle mit den Referenzlisten.",
})


# G-Skol 1.0.237 — German sweep: remaining FR/EN paths found during full UI review.
DE.update({
    "Create a new G-Skol collection from an external source. First choose the format; G-Skol will then analyze the source before creating anything.": "Erstellen Sie eine neue G-Skol-Sammlung aus einer externen Quelle. Wählen Sie zuerst das Format; G-Skol analysiert anschließend die Quelle, bevor etwas erstellt wird.",
    "Choose an .accdb or .mdb database. G-Skol can examine its structure without importing or modifying any data.": "Wählen Sie eine .accdb- oder .mdb-Datenbank. G-Skol kann ihre Struktur prüfen, ohne Daten zu importieren oder zu verändern.",
    "No Access file selected.": "Keine Access-Datei ausgewählt.",
    "After analysis, tables and their fields will be displayed below.": "Nach der Analyse werden die Tabellen und ihre Felder unten angezeigt.",
    "Select a table from the list above. Field rows cannot be selected as the source.": "Wählen Sie eine Tabelle aus der obigen Liste. Feldzeilen können nicht als Quelle ausgewählt werden.",
    "After confirming the source table, the next step will prepare the mapping between Access fields and G-Skol fields.": "Nach Bestätigung der Quelltabelle wird im nächsten Schritt die Zuordnung zwischen Access- und G-Skol-Feldern vorbereitet.",
    "Ajoutez ou complétez des référentiels dans une collection G-Skol existante, sans créer de fiches. G-Skol reconnaît maintenant les référentiels multi-colonnes provenant d’Access, SQLite, Excel .xlsx, CSV/TXT/TSV, ODS ou DBF. Pour Excel, seules les vraies feuilles relationnelles (une ligne = une valeur Maître et ses données Reliées) sont utilisées ; les feuilles de fiches et les réservoirs de listes indépendantes sont volontairement écartés. Les valeurs existantes sont conservées ; seules les nouvelles valeurs et associations sont ajoutées ou mises à jour.": "Fügen Sie Referenzlisten zu einer bestehenden G-Skol-Sammlung hinzu oder ergänzen Sie sie, ohne Datensätze anzulegen. G-Skol erkennt mehrspaltige Referenzlisten aus Access, SQLite, Excel .xlsx, CSV/TXT/TSV, ODS oder DBF. Bei Excel werden nur echte relationale Tabellenblätter verwendet (eine Zeile = ein Hauptwert mit seinen verknüpften Daten); Datensatzblätter und unabhängige Listenreservoirs werden bewusst ausgeschlossen. Vorhandene Werte bleiben erhalten; nur neue Werte und Verknüpfungen werden hinzugefügt oder aktualisiert.",
    "Selected collection:": "Ausgewählte Sammlung:", "(detected G-Skol collections)": "(erkannte G-Skol-Sammlungen)",
    "First choose the collection, then the source containing the reference lists.": "Wählen Sie zuerst die Sammlung und anschließend die Quelle mit den Referenzlisten.",
    "Drag a field to the layout": "Feld in das Layout ziehen", "Layout elements": "Layoutelemente", "Clear layout": "Layout leeren",
    "Report title:": "Berichtstitel:", "Column labels:": "Spaltenbeschriftungen:", "Column headers:": "Spaltenüberschriften:", "Linked fields:": "Verknüpfte Felder:",
    "Save": "Speichern", "Active template:": "Aktive Vorlage:", "Current view": "Aktuelle Ansicht",
    "Une ligne = une fiche. Cliquez sur un titre pour trier, déplacez ou redimensionnez les colonnes à la souris.": "Eine Zeile = ein Datensatz. Klicken Sie zum Sortieren auf eine Überschrift; verschieben oder skalieren Sie Spalten mit der Maus.",
    "Tous": "Alle", "Tapez une valeur…": "Wert eingeben…", "Ajouter ce filtre": "Diesen Filter hinzufügen", "Effacer les filtres": "Filter löschen",
    "Tri : cliquez sur l'en-tête d'une colonne": "Sortieren: Klicken Sie auf eine Spaltenüberschrift",
    "Choisissez un champ : G-Skol adapte automatiquement les comparaisons possibles. À partir de la deuxième ligne, utilisez ET pour restreindre le résultat ou OU pour l’élargir.": "Wählen Sie ein Feld: G-Skol passt die möglichen Vergleiche automatisch an. Verwenden Sie ab der zweiten Zeile UND, um das Ergebnis einzuschränken, oder ODER, um es zu erweitern.",
    "Ajouter des fiches depuis une source extérieure": "Datensätze aus einer externen Quelle hinzufügen",
    "Cette fonction ajoute de nouvelles fiches à la suite des fiches déjà présentes dans la collection G-Skol. Les fiches existantes ne sont jamais modifiées. Sources disponibles : Access, Excel .xlsx et CSV / TXT / TSV ; les autres formats suivront.": "Diese Funktion fügt neue Datensätze hinter den bereits vorhandenen Datensätzen der G-Skol-Sammlung hinzu. Bestehende Datensätze werden niemals verändert. Verfügbare Quellen: Access, Excel .xlsx und CSV / TXT / TSV; weitere Formate folgen.",
    "1. Collection G-Skol qui recevra les nouvelles fiches": "1. G-Skol-Sammlung, die die neuen Datensätze erhält", "Sélectionner une collection…": "Sammlung auswählen…", "Aucune collection sélectionnée.": "Keine Sammlung ausgewählt.",
    "2. Source contenant les fiches à ajouter": "2. Quelle mit den hinzuzufügenden Datensätzen", "Choisir une base Access…": "Access-Datenbank auswählen…", "Analyser les données": "Daten analysieren", "Aucune base Access sélectionnée.": "Keine Access-Datenbank ausgewählt.",
    "3. Tables détectées dans la source Access": "3. In der Access-Quelle erkannte Tabellen", "Table contenant les fiches à ajouter :": "Tabelle mit den hinzuzufügenden Datensätzen:", "Aucune analyse effectuée.": "Noch keine Analyse durchgeführt.",
    "Sécurité : les fiches G-Skol existantes ne seront jamais modifiées. Après la correspondance des champs, vous pourrez choisir exactement quelles lignes source seront ajoutées comme nouvelles fiches.": "Sicherheit: Vorhandene G-Skol-Datensätze werden niemals verändert. Nach der Feldzuordnung können Sie genau auswählen, welche Quellzeilen als neue Datensätze hinzugefügt werden.",
    "Importer un modèle G-Skol (.colmod)": "G-Skol-Vorlage (.colmod) importieren", "Importer un modèle G-Skol": "G-Skol-Vorlage importieren",
    "Choisissez le modèle reçu. G-Skol reconnaîtra automatiquement s’il s’agit d’un modèle de Fiche, de Tableau, de Requête ou d’État, puis vous proposera la bibliothèque correspondante. Aucune collection ne sera modifiée.": "Wählen Sie die erhaltene Vorlage. G-Skol erkennt automatisch, ob es sich um eine Datensatz-, Tabellen-, Abfrage- oder Berichtsvorlage handelt, und schlägt anschließend die passende Bibliothek vor. Keine Sammlung wird verändert.",
    "Le modèle importé rejoint simplement la bibliothèque correspondante. Pour l’utiliser, ouvrez ensuite une collection et choisissez ce modèle depuis le module correspondant.": "Die importierte Vorlage wird lediglich der entsprechenden Bibliothek hinzugefügt. Um sie zu verwenden, öffnen Sie anschließend eine Sammlung und wählen Sie die Vorlage im entsprechenden Modul aus.",
    "Parcourir…": "Durchsuchen…", "Choisir le dossier et importer…": "Ordner auswählen und importieren…",
    "Département": "Departement", "Vérifier": "Prüfen", "Libre": "Frei",
    "Open or create a collection before using Reports.": "Öffnen oder erstellen Sie eine Sammlung, bevor Sie Berichte verwenden.",
    "Open or create a collection before opening Table view.": "Öffnen oder erstellen Sie eine Sammlung, bevor Sie die Tabellenansicht öffnen.",
    "Open or create a collection before using the Toolbox.": "Öffnen oder erstellen Sie eine Sammlung, bevor Sie den Werkzeugkasten verwenden.",
    "Open or create a collection before building a query.": "Öffnen oder erstellen Sie eine Sammlung, bevor Sie eine Abfrage erstellen.",
    "Open a collection first.": "Öffnen Sie zuerst eine Sammlung.",
})

DE.update({
    "Ouvrez ou créez d'abord une collection avant d'utiliser les États.": "Öffnen oder erstellen Sie eine Sammlung, bevor Sie Berichte verwenden.",
    "Ouvrez ou créez d'abord une collection avant d'afficher la Vue Tableau.": "Öffnen oder erstellen Sie eine Sammlung, bevor Sie die Tabellenansicht öffnen.",
    "Ouvrez ou créez d’abord une collection avant d’utiliser la Boîte à outils.": "Öffnen oder erstellen Sie eine Sammlung, bevor Sie den Werkzeugkasten verwenden.",
    "Ouvrez ou créez d'abord une collection avant de construire une requête.": "Öffnen oder erstellen Sie eine Sammlung, bevor Sie eine Abfrage erstellen.",
    "Ouvrez d’abord une collection.": "Öffnen Sie zuerst eine Sammlung.",
})


# G-Skol 1.0.238 — German global pass from screenshot audit (06/10/2026).
DE.update({
    # Reports / previews / save dialogs
    "Enregistrer les modifications": "Änderungen speichern", "The report has been modified.": "Der Bericht wurde geändert.",
    "L’état a été modifié.": "Der Bericht wurde geändert.", "Report name:": "Berichtsname:", "Nom de l’état :": "Berichtsname:",
    "Save changes?": "Änderungen speichern?", "Enregistrer les modifications ?": "Änderungen speichern?",
    "Yes": "Ja", "No": "Nein", "Grouped preview": "Gruppierte Vorschau", "Aperçu groupé": "Gruppierte Vorschau",
    "Sort groups:": "Gruppen sortieren:", "Trier les groupes :": "Gruppen sortieren:", "Ascending": "Aufsteigend", "Descending": "Absteigend",
    "Alternating shaded rows": "Abwechselnd schattierte Zeilen", "Shaded column headers": "Schattierte Spaltenüberschriften",
    "Shaded totals band": "Schattiertes Summenband", "Save report": "Bericht speichern",
    # Import hub / create collection
    "Choose the type of import. G-Skol will then guide you step by step through the corresponding module.": "Wählen Sie die Importart. G-Skol führt Sie anschließend Schritt für Schritt durch das entsprechende Modul.",
    "Import a G-Skol template (.colmod)": "G-Skol-Vorlage (.colmod) importieren",
    # Reference-list import
    "No source selected.": "Keine Quelle ausgewählt.", "Source selected. Click ‘Analyze reference lists’.": "Quelle ausgewählt. Klicken Sie auf „Referenzlisten analysieren“.",
    "Choose the Access database containing the reference lists": "Access-Datenbank mit den Referenzlisten auswählen",
    "Reference-list import complete": "Import der Referenzlisten abgeschlossen", "Importing reference lists": "Referenzlisten werden importiert",
    "Import reference lists?": "Referenzlisten importieren?", "Confirm mappings": "Zuordnungen bestätigen",
    "Field mapping — Gisements": "Feldzuordnung — Gisements", "Field mapping": "Feldzuordnung", "4. Field mapping": "4. Feldzuordnung",
    "Access column (actual name)": "Access-Spalte (tatsächlicher Name)", "Role": "Rolle", "G-Skol field (current label)": "G-Skol-Feld (aktuelle Bezeichnung)",
    "Master": "Hauptfeld", "Linked": "Verknüpft", "Do not import": "Nicht importieren",
    # Add-record import workflow
    "Selected collection:": "Ausgewählte Sammlung:", "Access source:": "Access-Quelle:",
    "3. Sheets detected in the ODS source": "3. In der ODS-Quelle erkannte Tabellenblätter",
    "Sheet containing the records to add:": "Tabellenblatt mit den hinzuzufügenden Datensätzen:",
    "Choose an ODS file…": "ODS-Datei auswählen…", "No ODS file selected.": "Keine ODS-Datei ausgewählt.",
    "— Choose a table —": "— Tabelle auswählen —",
    "Analysis complete:": "Analyse abgeschlossen:",
    "Source field": "Quellfeld", "Field type": "Feldtyp", "G-Skol destination / action": "G-Skol-Ziel / Aktion",
    "Sort source fields alphabetically (A → Z)": "Quellfelder alphabetisch sortieren (A → Z)",
    "Choose records to add…": "Datensätze zum Hinzufügen auswählen…", "Select records to add": "Datensätze zum Hinzufügen auswählen",
    "5. Select records to add — one row = one new G-Skol record": "5. Hinzuzufügende Datensätze auswählen — eine Zeile = ein neuer G-Skol-Datensatz",
    "Include all": "Alle einschließen", "Exclude all": "Alle ausschließen", "Import": "Importieren", "[binary data]": "[Binärdaten]",
    "Back to mapping": "Zurück zur Zuordnung", "Add selected records": "Ausgewählte Datensätze hinzufügen",
    "Confirm addition": "Hinzufügen bestätigen", "Add records": "Datensätze hinzufügen", "Addition complete": "Hinzufügen abgeschlossen",
    "Safety backup:": "Sicherungskopie:",
    # Table view residuals
    "Active template:": "Aktive Vorlage:", "Current view": "Aktuelle Ansicht", "{count} fiches": "{count} Datensätze",
    "Copier la fiche": "Datensatz kopieren", "Coller la fiche": "Datensatz einfügen", "Vider": "Leeren", "Supprimer": "Löschen",
    "Charger un modèle depuis la bibliothèque Modèles de Tableaux": "Eine Vorlage aus der Bibliothek Tabellenvorlagen laden",
})


# G-Skol 1.0.239 — German: native collection-template chooser.
DE.update({
    "Choisir un modèle de collection": "Sammlungsvorlage auswählen",
    "Quel type de collection souhaitez-vous créer ?": "Welche Art von Sammlung möchten Sie erstellen?",
    "Choisissez le modèle le plus proche de votre besoin. Une fois la collection créée, tous ses champs, cadres et photos resteront librement personnalisables dans l’Atelier.": "Wählen Sie die Vorlage, die Ihren Anforderungen am besten entspricht. Nach dem Erstellen der Sammlung können alle Felder, Rahmen und Fotos in der Werkstatt frei angepasst werden.",
    "Collection vierge": "Leere Sammlung",
    "Construire librement votre propre modèle de fiche.": "Erstellen Sie Ihre eigene Datensatzvorlage frei.",
    "Minéraux": "Mineralien",
    "Minéraux / Microminéraux": "Mineralien / Mikromineralien",
    "Espèces, cristallographie, localités, acquisition et photos.": "Arten, Kristallographie, Fundorte, Erwerb und Fotos.",
    "Fossiles": "Fossilien",
    "Taxonomie, âge géologique, provenance, préparation et photos.": "Taxonomie, geologisches Alter, Herkunft, Präparation und Fotos.",
    "Sables": "Sande",
    "Site, localisation, identification du sable, acquisition et deux photos.": "Fundstelle, Ort, Sandbestimmung, Erwerb und zwei Fotos.",
    "Timbres": "Briefmarken",
    "Pays, émission, année, valeur, série, état et catalogue.": "Land, Ausgabe, Jahr, Wert, Serie, Zustand und Katalog.",
    "Cartes postales": "Postkarten",
    "Lieu, éditeur, période, état, acquisition, recto et verso.": "Ort, Verlag, Zeitraum, Zustand, Erwerb, Vorder- und Rückseite.",
    "Monnaies / Médailles / Jetons": "Münzen / Medaillen / Marken",
    "Pays, valeur, date, métal, dimensions, référence, avers et revers.": "Land, Wert, Datum, Metall, Abmessungen, Referenz, Vorder- und Rückseite.",
    "Objets de collection": "Sammelobjekte",
    "Porte-clés, pin’s, fèves, figurines, capsules et autres objets.": "Schlüsselanhänger, Pins, Figuren, Kapseln und andere Objekte.",
    "Livres / Documents": "Bücher / Dokumente",
    "Titre, auteur, éditeur, année, édition, référence et état.": "Titel, Autor, Verlag, Jahr, Ausgabe, Referenz und Zustand.",
    "Étiquettes / Documents graphiques": "Etiketten / Grafische Dokumente",
    "Catégorie, marque, origine, période, thème, dimensions et images.": "Kategorie, Marke, Herkunft, Zeitraum, Thema, Abmessungen und Bilder.",
    "Modèle prévu — disponible dans une prochaine étape": "Vorlage vorgesehen — in einem späteren Schritt verfügbar",
    "Suivant": "Weiter",
    "Collection créée": "Sammlung erstellt",
    "La collection « {name} » a été créée.\n\nVous pouvez maintenant ouvrir l’atelier des fiches.": "Die Sammlung „{name}“ wurde erstellt.\n\nSie können jetzt die Datensatz-Werkstatt öffnen.",
})

# G-Skol 1.0.240 — German screenshot audit + official-template pass.
DE.update({
    "Copier les cellules":"Zellen kopieren",
    "(sans valeur)":"(kein Wert)", "(no value)":"(kein Wert)", "(vide)":"(leer)", "(empty)":"(leer)",
    "Noir et blanc":"Schwarzweiß", "Black and white":"Schwarzweiß",
    "Enregistrer sous — Modèles d’états":"Speichern unter — Berichtsvorlagen",
    "Modèles d’états":"Berichtsvorlagen", "Modèles d’États":"Berichtsvorlagen",
    "Nom du modèle :":"Vorlagenname:", "Dossier sélectionné :":"Ausgewählter Ordner:",
    "Nouveau dossier…":"Neuer Ordner…", "Renommer…":"Umbenennen…", "Supprimer…":"Löschen…",
    "Enregistrer":"Speichern", "Save this report in the Report Templates library":"Diesen Bericht in der Bibliothek Berichtsvorlagen speichern",
    "Épaisseur mm":"Dicke mm", "Epaisseur mm":"Dicke mm", "Total cost":"Gesamtkosten", "Coût total":"Gesamtkosten",
})


# G-Skol 1.0.241 — German residual UI pass from screenshot audit (06/10/2026).
DE.update({
    "Nouvelle collection — Informations": "Neue Sammlung — Informationen", "Nom :": "Name:", "Propriétaire :": "Eigentümer:", "Description :": "Beschreibung:",
    "Créer": "Erstellen", "Création impossible": "Erstellung nicht möglich",
    "Supprimer la collection": "Sammlung löschen", "Supprimer définitivement la collection « {name} » ?": "Sammlung „{name}“ endgültig löschen?",
    "Toutes les fiches et tous les référentiels de cette collection seront supprimés.\nCette opération est irréversible.": "Alle Datensätze und Referenzlisten dieser Sammlung werden gelöscht.\nDieser Vorgang kann nicht rückgängig gemacht werden.", "SUPPRIMER": "LÖSCHEN",
    "Non classées": "Nicht klassifiziert",
    "Personnalisez ici le modèle de fiche utilisé pour cette collection. Tout enrichissement ou modification sera immédiatement visible.": "Passen Sie hier die für diese Sammlung verwendete Datensatzvorlage an. Jede Ergänzung oder Änderung ist sofort sichtbar.",
    "Champ (glisser pour classer)": "Feld (zum Sortieren ziehen)", "Cliquez sur un champ pour le sélectionner, déplacez-le à la souris, puis affinez avec les flèches du clavier.": "Klicken Sie auf ein Feld, um es auszuwählen, verschieben Sie es mit der Maus und nehmen Sie die Feinjustierung anschließend mit den Pfeiltasten vor.",
    "Tabulation = ordre visuel": "Tabulator = visuelle Reihenfolge", "Ajouter un champ": "Feld hinzufügen", "Ajouter un cadre": "Rahmen hinzufügen", "Ajouter un cadre Photo": "Fotorahmen hinzufügen", "Tout sélectionner": "Alle auswählen", "Couleur de la fiche…": "Datensatzfarbe…", "Style standard": "Standardstil",
    "Lignes alternées grisées": "Abwechselnd schattierte Zeilen", "En-têtes de colonnes grisés": "Schattierte Spaltenüberschriften", "Bandeau des totaux grisé": "Schattiertes Summenband",
    "Croissant": "Aufsteigend", "Décroissant": "Absteigend", "(vide)": "(leer)",
    "Cliquez sur un titre pour trier. Déplacez les titres à la souris pour réorganiser les colonnes et redimensionnez-les à la souris.": "Klicken Sie zum Sortieren auf eine Überschrift. Ziehen Sie Überschriften, um Spalten neu anzuordnen, und ändern Sie ihre Größe mit der Maus.",
    "Enregistrer l’état": "Bericht speichern", "Enregistrer sous…": "Speichern unter…", "Conserver cet état dans la bibliothèque Modèles d’États": "Diesen Bericht in der Bibliothek der Berichtsvorlagen speichern",
    "Ajouter une photo…": "Foto hinzufügen…", "Coller une photo": "Foto einfügen", "Supprimer la photo…": "Foto entfernen…",
    "Commence par": "Beginnt mit", "Est exactement": "Ist genau", "Est différent de": "Ist ungleich", "Se termine par": "Endet mit", "Est vide": "Ist leer", "N’est pas vide": "Ist nicht leer",
    "Égal à": "Gleich", "Différent de": "Ungleich", "Supérieur à": "Größer als", "Supérieur ou égal à": "Größer oder gleich", "Inférieur à": "Kleiner als", "Inférieur ou égal à": "Kleiner oder gleich", "Compris entre": "Zwischen",
    "Requête enregistrée « {name} » chargée. Cliquez sur Exécuter la requête.": "Gespeicherte Abfrage „{name}“ geladen. Klicken Sie auf „Abfrage ausführen“.",
    "Aucune requête exécutée.": "Keine Abfrage ausgeführt.", "Saisissez au moins un critère complet avant d’exécuter la requête.": "Geben Sie mindestens ein vollständiges Kriterium ein, bevor Sie die Abfrage ausführen.",
    "No": "Nein", "Yes": "Ja", "Black and white": "Schwarzweiß",
})

# G-Skol 1.0.243 — residual menus, report dialogs and tooltip audit (FR/EN/DE).
EN.update({
    "Supprimer définitivement le champ de la collection…": "Permanently delete the field from the collection…",
    "Copier": "Copy", "Coller": "Paste", "Annuler": "Undo", "Rétablir": "Redo", "Couper": "Cut", "Tout sélectionner": "Select All",
    "Remplacer la photo…": "Replace photo…", "Copier la photo": "Copy photo", "Ouvrir le lien": "Open link",
    "Copier la ou les fiches sélectionnées (Ctrl+C)": "Copy the selected record(s) (Ctrl+C)",
    "Supprimer définitivement les fiches Libres et vides situées en fin de collection": "Permanently delete empty Free records at the end of the collection",
    "Mise en forme…": "Formatting…", "Rétablir la mise en forme par défaut": "Restore default formatting", "Retirer de la construction": "Remove from layout",
    "Mise en forme de l’en-tête…": "Format header…", "Modifier l’en-tête « {0} »…": "Edit header “{0}”…", "Supprimer l’en-tête « {0} »": "Remove header “{0}”", "Rétablir la mise en forme de l’en-tête": "Restore this header to default",
    "Titre de l’État": "Report title", "Titre :": "Title:", "Police :": "Font:", "Taille :": "Size:", "Style :": "Style:", "Alignement :": "Alignment:", "Couleur du texte :": "Text color:", "Couleur de fond :": "Background color:", "Choisir…": "Choose…", "Rétablir par défaut": "Restore defaults",
})
DE.update({
    "Supprimer définitivement le champ de la collection…": "Feld endgültig aus der Sammlung löschen…",
    "Copier": "Kopieren", "Coller": "Einfügen", "Annuler": "Rückgängig", "Rétablir": "Wiederholen", "Couper": "Ausschneiden", "Tout sélectionner": "Alles auswählen", "Supprimer": "Löschen",
    "Remplacer la photo…": "Foto ersetzen…", "Copier la photo": "Foto kopieren", "Ouvrir le lien": "Link öffnen",
    "Copier la ou les fiches sélectionnées (Ctrl+C)": "Ausgewählte Datensätze kopieren (Strg+C)",
    "Supprimer définitivement les fiches Libres et vides situées en fin de collection": "Leere freie Datensätze am Ende der Sammlung endgültig löschen",
    "Mise en forme…": "Formatierung…", "Formatting…": "Formatierung…", "Rétablir la mise en forme par défaut": "Standardformatierung wiederherstellen", "Restore default formatting": "Standardformatierung wiederherstellen", "Retirer de la construction": "Aus Layout entfernen", "Remove from layout": "Aus Layout entfernen",
    "Mise en forme de l’en-tête…": "Kopfzeile formatieren…", "Format header…": "Kopfzeile formatieren…", "Modifier l’en-tête « {0} »…": "Kopfzeile „{0}“ bearbeiten…", "Supprimer l’en-tête « {0} »": "Kopfzeile „{0}“ entfernen", "Rétablir la mise en forme de l’en-tête": "Standardformatierung dieser Kopfzeile wiederherstellen",
    "Titre de l’État": "Berichtstitel", "Report title": "Berichtstitel", "Titre :": "Titel:", "Title:": "Titel:", "Police :": "Schriftart:", "Font:": "Schriftart:", "Taille :": "Größe:", "Size:": "Größe:", "Style :": "Stil:", "Style:": "Stil:", "Alignement :": "Ausrichtung:", "Alignment:": "Ausrichtung:", "Couleur du texte :": "Textfarbe:", "Text color:": "Textfarbe:", "Couleur de fond :": "Hintergrundfarbe:", "Background color:": "Hintergrundfarbe:", "Choisir…": "Auswählen…", "Choose…": "Auswählen…", "Rétablir par défaut": "Standard wiederherstellen", "Restore defaults": "Standard wiederherstellen",
    "Yes": "Ja", "No": "Nein",
})


# G-Skol 1.0.245 — German residual audit from screenshots (06/10/2026).
EN.update({
    "Conserver cette requête dans la bibliothèque Modèles de Requêtes": "Save this query in the Query Templates library",
    "Conserver cette vue dans la bibliothèque Modèles de Tableaux": "Save this view in the Table Templates library",
    "Coller la fiche copiée dans la ligne sélectionnée ; si plusieurs fiches ont été copiées, elles sont toutes ajoutées comme nouvelles fiches (Ctrl+V)": "Paste the copied record into the selected row; if several records were copied, they are all added as new records (Ctrl+V)",
    "Vider la ou les fiches sélectionnées et les passer à l'état Libre": "Clear the selected record(s) and set them to Free",
})
DE.update({
    "Template": "Vorlage", "Active template:": "Aktive Vorlage:", "Drag a field to the layout": "Feld in das Layout ziehen", "Layout elements": "Layoutelemente",
    "Show header totals": "Summen des Kopfbereichs anzeigen", "Choose footer totals…": "Summen für die Fußzeile auswählen…", "Format footer…": "Fußzeile formatieren…", "Clear footer": "Fußzeile leeren", "Page numbering…": "Seitennummerierung…",
    "Afficher les totaux du bandeau": "Summen des Kopfbereichs anzeigen", "Choisir les totaux du pied de page…": "Summen für die Fußzeile auswählen…", "Mise en forme du pied de page…": "Fußzeile formatieren…", "Vider le pied de page": "Fußzeile leeren", "Numérotation des pages…": "Seitennummerierung…",
    "Glisser un champ vers la construction": "Feld in das Layout ziehen", "Éléments de construction": "Layoutelemente",
    "Conserver cette requête dans la bibliothèque Modèles de Requêtes": "Diese Abfrage in der Bibliothek Abfragevorlagen speichern",
    "Conserver cette vue dans la bibliothèque Modèles de Tableaux": "Diese Ansicht in der Bibliothek Tabellenvorlagen speichern",
    "Coller la fiche copiée dans la ligne sélectionnée ; si plusieurs fiches ont été copiées, elles sont toutes ajoutées comme nouvelles fiches (Ctrl+V)": "Den kopierten Datensatz in die ausgewählte Zeile einfügen; wurden mehrere Datensätze kopiert, werden sie alle als neue Datensätze hinzugefügt (Strg+V)",
    "Vider la ou les fiches sélectionnées et les passer à l'état Libre": "Ausgewählte Datensätze leeren und auf Frei setzen",
    "{count} fiches": "{count} Datensätze", "{count} fiche": "{count} Datensatz",
})


# G-Skol 1.0.246 — restoration and DE/EN translation of Table/Query tooltips.
EN.update({
    "Annuler la dernière modification du Tableau (Ctrl+Z)": "Undo the last Table change (Ctrl+Z)",
    "Rétablir la dernière modification annulée (Ctrl+Y)": "Redo the last undone Table change (Ctrl+Y)",
    "Monter la requête sélectionnée": "Move the selected query up",
    "Descendre la requête sélectionnée": "Move the selected query down",
})
DE.update({
    "Charger un modèle depuis la bibliothèque Modèles de Tableaux": "Eine Vorlage aus der Bibliothek Tabellenvorlagen laden",
    "Charger un modèle depuis la bibliothèque Modèles de Requêtes": "Eine Vorlage aus der Bibliothek Abfragevorlagen laden",
    "Copier la ou les fiches sélectionnées (Ctrl+C)": "Ausgewählte Datensätze kopieren (Strg+C)",
    "Annuler la dernière modification du Tableau (Ctrl+Z)": "Letzte Änderung der Tabellenansicht rückgängig machen (Strg+Z)",
    "Rétablir la dernière modification annulée (Ctrl+Y)": "Zuletzt rückgängig gemachte Änderung wiederholen (Strg+Y)",
    "Monter la requête sélectionnée": "Ausgewählte Abfrage nach oben verschieben",
    "Descendre la requête sélectionnée": "Ausgewählte Abfrage nach unten verschieben",
    "Enregistrer ce modèle": "Diese Vorlage speichern",
    "Mettre à jour": "Aktualisieren",
})


# G-Skol 1.0.247 — German residual dynamic UI pass.
DE.update({
    "Oui": "Ja", "Non": "Nein",
    "Vue résultat de la requête": "Abfrageergebnis",
    "Requête :": "Abfrage:", "fiche": "Datensatz", "fiches": "Datensätze",
    "Ouvrir une vue enregistrée": "Gespeicherte Ansicht öffnen",
    "Ouvrir une requête enregistrée": "Gespeicherte Abfrage öffnen",
    "Ouvrez un dossier, puis double-cliquez sur la sauvegarde.": "Öffnen Sie einen Ordner und doppelklicken Sie anschließend auf die gespeicherte Ansicht.",
    "Dossiers et sauvegardes de cette collection": "Ordner und gespeicherte Ansichten dieser Sammlung",
    "Sans dossier": "Ohne Ordner", "— Nouvelle requête —": "— Neue Abfrage —",
    "Nouveau : disponible après Aperçu. Existant : disponible après modification.": "Neu: nach der Vorschau verfügbar. Vorhanden: nach einer Änderung verfügbar.",
    "Aperçu avant impression multipage": "Mehrseitige Druckvorschau",
    "Multipage print preview": "Mehrseitige Druckvorschau",
    "Conserver cette vue dans la bibliothèque Modèles de Tableaux": "Diese Ansicht in der Bibliothek der Tabellenvorlagen speichern",
})


# G-Skol 1.0.252 — traduction allemande complète du parcours Import Excel .xlsx.
DE.update({
    "Choisissez un classeur .xlsx. G-Skol analyse les feuilles, les en-têtes et les types de cellules sans modifier le fichier source. Les images intégrées au classeur ne sont pas importées dans cette première version.": "Wählen Sie eine .xlsx-Arbeitsmappe. G-Skol analysiert die Tabellenblätter, Überschriften und Zelltypen, ohne die Quelldatei zu verändern. In die Arbeitsmappe eingebettete Bilder werden in dieser Version nicht importiert.",
    "Choisir un fichier Excel…": "Excel-Datei auswählen…",
    "Analyser le classeur": "Arbeitsmappe analysieren",
    "Aucun fichier Excel sélectionné.": "Keine Excel-Datei ausgewählt.",
    "Après analyse, les feuilles et leurs colonnes apparaîtront ci-dessous.": "Nach der Analyse werden die Tabellenblätter und ihre Spalten unten angezeigt.",
    "Feuille / Colonne": "Tabellenblatt / Spalte", "Type détecté": "Erkannter Typ", "Lignes": "Zeilen",
    "Choisir cette feuille": "Dieses Tabellenblatt auswählen",
    "Aperçu des données…": "Datenvorschau…", "Correspondance des champs…": "Feldzuordnung…",
    "Sélectionnez une feuille dans la liste ci-dessus. Les lignes de colonnes ne sont pas sélectionnables comme source.": "Wählen Sie ein Tabellenblatt aus der obigen Liste. Spaltenzeilen können nicht als Quelle ausgewählt werden.",
    "Après validation de la feuille source, l’étape suivante préparera la correspondance entre les colonnes Excel et les champs G-Skol.": "Nach Bestätigung des Quellblatts wird im nächsten Schritt die Zuordnung zwischen den Excel-Spalten und den G-Skol-Feldern vorbereitet.",
    "Créer la collection G-Skol et importer…": "G-Skol-Sammlung erstellen und importieren…",
    "Choisir un classeur Microsoft Excel": "Microsoft-Excel-Arbeitsmappe auswählen",
    "Classeurs Excel (*.xlsx);;Tous les fichiers (*.*)": "Excel-Arbeitsmappen (*.xlsx);;Alle Dateien (*.*)",
    "Import Excel": "Excel-Import", "Le fichier choisi n’est pas un classeur .xlsx.": "Die ausgewählte Datei ist keine .xlsx-Arbeitsmappe.",
    "Classeur sélectionné. Cliquez sur « Analyser le classeur » pour afficher ses feuilles.": "Arbeitsmappe ausgewählt. Klicken Sie auf „Arbeitsmappe analysieren“, um die Tabellenblätter anzuzeigen.",
    "Fichier Excel sélectionné : {source}{size}\n": "Ausgewählte Excel-Datei: {source}{size}\n",
    "Aucune donnée n’est importée ou modifiée pendant l’analyse.": "Während der Analyse werden keine Daten importiert oder geändert.",
    "Le fichier Excel sélectionné est introuvable.": "Die ausgewählte Excel-Datei wurde nicht gefunden.",
    "Analyse du classeur Excel en cours…": "Excel-Arbeitsmappe wird analysiert…", "L’analyse n’a pas pu être effectuée.": "Die Analyse konnte nicht durchgeführt werden.",
    "Analyse Excel impossible": "Excel-Analyse nicht möglich", "{count} colonne(s)": "{count} Spalte(n)",
    "Analyse terminée : {sheets} feuille(s), {fields} colonne(s), {rows} ligne(s) de données au total.": "Analyse abgeschlossen: {sheets} Tabellenblatt/-blätter, {fields} Spalte(n), insgesamt {rows} Datenzeile(n).",
    "✓ Feuille source retenue : {name} — {rows} ligne(s), {fields} colonne(s){header}": "✓ Quellblatt ausgewählt: {name} — {rows} Zeile(n), {fields} Spalte(n){header}",
    " — en-têtes ligne {row}.": " — Überschriften in Zeile {row}.",
    "Feuille source validée. L’ordre des lignes sera conservé pour créer les fiches. Cliquez sur « Correspondance des champs… ».": "Quellblatt bestätigt. Die Reihenfolge der Zeilen wird beim Erstellen der Datensätze beibehalten. Klicken Sie auf „Feldzuordnung…“.",
    "✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour la création d'une nouvelle collection puis import des fiches.": "✓ Zuordnung bestätigt: {imported} Feld(er) werden importiert, {ignored} ignoriert. Bereit zum Erstellen einer neuen Sammlung und zum Importieren der Datensätze.",
    "Nom déjà utilisé": "Name bereits verwendet", "Le fichier « {name} » existe déjà.": "Die Datei „{name}“ ist bereits vorhanden. Wählen Sie einen anderen Namen.",
    "Lancer l’import Excel ?": "Excel-Import starten?",
    "Créer la collection « {name} » et importer {rows} fiche(s) depuis Excel ?\n\nL’ordre des lignes Excel sera conservé. Le classeur source ne sera jamais modifié.": "Die Sammlung „{name}“ erstellen und {rows} Datensatz/Datensätze aus Excel importieren?\n\nDie Reihenfolge der Excel-Zeilen wird beibehalten. Die Quellarbeitsmappe wird niemals verändert.",
    "Import du classeur « {source} » en cours…\nCréation de la collection et copie des lignes. Merci de patienter.": "Arbeitsmappe „{source}“ wird importiert…\nDie Sammlung wird erstellt und die Zeilen werden kopiert. Bitte warten.",
    "Import Excel en cours": "Excel-Import läuft", "Import Excel interrompu": "Excel-Import abgebrochen", "L’import n’a pas été conservé.\n\n": "Der Import wurde nicht gespeichert.\n\n",
    "✓ Import terminé : {records} fiche(s) créées dans « {name} » — ordre des lignes Excel conservé.": "✓ Import abgeschlossen: {records} Datensatz/Datensätze in „{name}“ erstellt — Reihenfolge der Excel-Zeilen beibehalten.",
    "Import Excel terminé": "Excel-Import abgeschlossen",
    "Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\nChamps Maîtres détectés : {masters}\nChamps Reliés détectés : {links}\n\nOrdre des fiches : ordre des lignes Excel conservé.": "Import erfolgreich abgeschlossen.\n\nSammlung: {name}\nErstellte Datensätze: {records}\nImportierte Felder: {fields}\nReferenzwerte: {values}\nErkannte Master-Felder: {masters}\nErkannte verknüpfte Felder: {links}\n\nDatensatzreihenfolge: Reihenfolge der Excel-Zeilen beibehalten.",
    "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date, Bouton On / Off et Calculé</b> à partir des cellules et formats Excel ; vous pouvez corriger chaque proposition.<br>• Une colonne Excel devient un champ de la collection. Les cellules vides restent vides.<br>• L’ordre des lignes Excel est conservé : première ligne de données → fiche 1, puis 2, 3…<br>• Un champ source <b>N° / Numéro</b> reste une donnée ordinaire et n’influence jamais la numérotation automatique des fiches.": "• <b>Doppelklicken Sie auf den Namen eines G-Skol-Feldes, um ihn zu bearbeiten.</b><br>• G-Skol leitet <b>Text, Zahl, Währung, Datum, Ein/Aus-Schaltfläche und Berechnet</b> aus Excel-Zellen und -Formaten ab; Sie können jeden Vorschlag korrigieren.<br>• Eine Excel-Spalte wird zu einem Feld der Sammlung. Leere Zellen bleiben leer.<br>• Die Reihenfolge der Excel-Zeilen wird beibehalten: erste Datenzeile → Datensatz 1, dann 2, 3…<br>• Ein Quellfeld <b>Nr. / Nummer</b> bleibt eine gewöhnliche Angabe und beeinflusst niemals die automatische Nummerierung der Datensätze.",
    "Texte": "Text", "Nombre": "Zahl", "Monétaire": "Währung", "Date": "Datum", "Bouton On / Off": "Ein/Aus-Schaltfläche", "Lien (Internet ou autre)": "Link (Internet oder anderer)", "Photo / Image": "Foto / Bild",
    "Liste / Référentiel — reconnu par G-Skol": "Liste / Referenz — von G-Skol erkannt", "Liste / Référentiel — reconnu par MM3": "Liste / Referenz — von G-Skol erkannt",
    "Liste / Référentiel — probable / à vérifier": "Liste / Referenz — wahrscheinlich / zu prüfen", "Liste / Référentiel — à paramétrer": "Liste / Referenz — zu konfigurieren",
    "Calculé — reconnu par G-Skol": "Berechnet — von G-Skol erkannt", "Calculé — reconnu par MM3": "Berechnet — von G-Skol erkannt", "Calculé — probable / à vérifier": "Berechnet — wahrscheinlich / zu prüfen", "Calculé — à paramétrer": "Berechnet — zu konfigurieren",
})


# G-Skol 1.0.253 — traduction allemande complète du parcours Import CSV / TXT / TSV.
DE.update({
    "Choisissez un fichier tabulaire .csv, .txt ou .tsv. G-Skol détecte automatiquement l’encodage et le séparateur (point-virgule, virgule ou tabulation), puis analyse les en-têtes et les types de colonnes sans modifier le fichier source.": "Wählen Sie eine tabellarische .csv-, .txt- oder .tsv-Datei. G-Skol erkennt automatisch die Zeichenkodierung und das Trennzeichen (Semikolon, Komma oder Tabulator) und analysiert anschließend die Überschriften und Spaltentypen, ohne die Quelldatei zu verändern.",
    "Choisir un fichier CSV / TXT / TSV…": "CSV-/TXT-/TSV-Datei auswählen…",
    "Analyser le fichier": "Datei analysieren",
    "Aucun fichier CSV / TXT / TSV sélectionné.": "Keine CSV-/TXT-/TSV-Datei ausgewählt.",
    "Après analyse, les colonnes et le nombre de lignes apparaîtront ci-dessous.": "Nach der Analyse werden die Spalten und die Anzahl der Zeilen unten angezeigt.",
    "Fichier / Colonne": "Datei / Spalte", "Type détecté": "Erkannter Typ", "Lignes": "Zeilen",
    "Choisir ce fichier": "Diese Datei auswählen",
    "Analysez le fichier puis validez-le comme source de la future collection G-Skol.": "Analysieren Sie die Datei und bestätigen Sie sie anschließend als Quelle der zukünftigen G-Skol-Sammlung.",
    "Après validation, G-Skol préparera la correspondance entre les colonnes du fichier et les champs G-Skol.": "Nach der Bestätigung bereitet G-Skol die Zuordnung zwischen den Dateispalten und den G-Skol-Feldern vor.",
    "Choisir un fichier CSV / TXT / TSV": "CSV-/TXT-/TSV-Datei auswählen",
    "Fichiers tabulaires (*.csv *.txt *.tsv);;CSV (*.csv);;Texte (*.txt);;TSV (*.tsv);;Tous les fichiers (*.*)": "Tabellarische Dateien (*.csv *.txt *.tsv);;CSV (*.csv);;Text (*.txt);;TSV (*.tsv);;Alle Dateien (*.*)",
    "Fichier sélectionné. Cliquez sur « Analyser le fichier ».": "Datei ausgewählt. Klicken Sie auf „Datei analysieren“.",
    "Fichier sélectionné : {source}{size}\nAucune donnée n’est importée ou modifiée pendant l’analyse.": "Ausgewählte Datei: {source}{size}\nWährend der Analyse werden keine Daten importiert oder geändert.",
    "Analyse du fichier en cours…": "Datei wird analysiert…",
    "Analyse terminée : aucune table de données trouvée.": "Analyse abgeschlossen: Keine Datentabelle gefunden.",
    "Analyse terminée : {columns} colonne(s), {rows} ligne(s) — encodage {encoding} — séparateur : {delimiter}.": "Analyse abgeschlossen: {columns} Spalte(n), {rows} Zeile(n) — Zeichenkodierung {encoding} — Trennzeichen: {delimiter}.",
    "Fichier analysé. Cliquez sur « Choisir ce fichier » pour le retenir comme source.": "Datei analysiert. Klicken Sie auf „Diese Datei auswählen“, um sie als Quelle zu verwenden.",
    "✓ Source retenue : {name} — {rows} ligne(s), {columns} colonne(s) — {encoding}, séparateur {delimiter}.": "✓ Quelle ausgewählt: {name} — {rows} Zeile(n), {columns} Spalte(n) — {encoding}, Trennzeichen {delimiter}.",
    "Source validée. L’ordre des lignes sera conservé. Cliquez sur « Correspondance des champs… ».": "Quelle bestätigt. Die Reihenfolge der Zeilen wird beibehalten. Klicken Sie auf „Feldzuordnung…“.",
    "Fichier texte": "Textdatei",
    "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date et Bouton On / Off</b> à partir des valeurs ; vous pouvez corriger chaque proposition.<br>• Le séparateur et l’encodage sont détectés automatiquement puis affichés avant l’import.<br>• Une colonne devient un champ de la collection ; les cellules vides restent vides.<br>• Les fichiers texte ne contiennent pas de vraie information de liste déroulante : vous pouvez choisir manuellement <b>Liste / Référentiel</b> dans la correspondance.<br>• L’ordre des lignes source est conservé : première ligne de données → fiche 1, puis 2, 3…": "• <b>Doppelklicken Sie auf den Namen eines G-Skol-Feldes, um ihn zu bearbeiten.</b><br>• G-Skol leitet <b>Text, Zahl, Währung, Datum und Ein/Aus-Schaltfläche</b> aus den Werten ab; Sie können jeden Vorschlag korrigieren.<br>• Trennzeichen und Zeichenkodierung werden automatisch erkannt und vor dem Import angezeigt.<br>• Eine Spalte wird zu einem Feld der Sammlung; leere Zellen bleiben leer.<br>• Textdateien enthalten keine echten Dropdown-Listen-Metadaten: Sie können in der Zuordnung manuell <b>Liste / Referenz</b> auswählen.<br>• Die Reihenfolge der Quellzeilen wird beibehalten: erste Datenzeile → Datensatz 1, dann 2, 3…",
    "Lancer l’import {source} ?": "{source}-Import starten?",
    "Créer la collection « {name} » et importer {rows} fiche(s) depuis {source} ?\n\nL’ordre des lignes sera conservé. Le fichier source ne sera jamais modifié.": "Die Sammlung „{name}“ erstellen und {rows} Datensatz/Datensätze aus {source} importieren?\n\nDie Reihenfolge der Zeilen wird beibehalten. Die Quelldatei wird niemals verändert.",
    "Import {source} terminé": "{source}-Import abgeschlossen",
    "Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\n\nOrdre des fiches : ordre des lignes source conservé.": "Import erfolgreich abgeschlossen.\n\nSammlung: {name}\nErstellte Datensätze: {records}\nImportierte Felder: {fields}\nReferenzwerte: {values}\n\nDatensatzreihenfolge: Reihenfolge der Quellzeilen beibehalten.",
    "✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour la création de la collection et l’import des lignes.": "✓ Zuordnung bestätigt: {imported} Feld(er) werden importiert, {ignored} ignoriert. Bereit zum Erstellen der Sammlung und zum Importieren der Zeilen.",
    "Import du fichier « {source} » en cours…\nCréation de la collection et copie des lignes.": "Datei „{source}“ wird importiert…\nDie Sammlung wird erstellt und die Zeilen werden kopiert.",
    "Import {source} en cours": "{source}-Import läuft",
    "✓ Import terminé : {records} fiche(s) créées dans « {name} » — ordre des lignes conservé.": "✓ Import abgeschlossen: {records} Datensatz/Datensätze in „{name}“ erstellt — Reihenfolge der Zeilen beibehalten.",
    "point-virgule": "Semikolon", "virgule": "Komma", "tabulation": "Tabulator", "barre verticale |": "senkrechter Strich |",
    "Fichier texte : valeurs numériques reconnues": "Textdatei: numerische Werte erkannt",
    "Fichier texte : colonne monétaire reconnue": "Textdatei: Währungsspalte erkannt",
    "Fichier texte : colonne monétaire reconnue par son libellé": "Textdatei: Währungsspalte anhand ihrer Bezeichnung erkannt",
    "Fichier texte : valeurs monétaires reconnues": "Textdatei: Währungswerte erkannt",
    "Fichier texte : dates reconnues": "Textdatei: Datumswerte erkannt",
    "Fichier texte : valeurs booléennes reconnues": "Textdatei: boolesche Werte erkannt",
    "Fichier texte : contenu mixte ou texte": "Textdatei: gemischter Inhalt oder Text",
})


# G-Skol 1.0.256 — traduction allemande complète du parcours Import ODS.
DE.update({
    "Choisissez un classeur OpenDocument .ods. G-Skol analyse ses feuilles, les en-têtes et les types de cellules sans modifier le fichier source. Les nombres, dates, booléens, montants monétaires et calculs arithmétiques simples sont reconnus.": "Wählen Sie eine OpenDocument-.ods-Arbeitsmappe. G-Skol analysiert ihre Tabellenblätter, Überschriften und Zelltypen, ohne die Quelldatei zu verändern. Zahlen, Datumswerte, boolesche Werte, Währungsbeträge und einfache arithmetische Berechnungen werden erkannt.",
    "Choisir un fichier ODS…": "ODS-Datei auswählen…",
    "Aucun fichier ODS sélectionné.": "Keine ODS-Datei ausgewählt.",
    "Feuille / Colonne": "Tabellenblatt / Spalte",
    "Type détecté": "Erkannter Typ",
    "Lignes": "Zeilen",
    "Analysez le classeur puis choisissez la feuille source de la future collection G-Skol.": "Analysieren Sie die Arbeitsmappe und wählen Sie anschließend das Quelltabellenblatt für die zukünftige G-Skol-Sammlung aus.",
    "Choisir un fichier ODS": "ODS-Datei auswählen",
    "Classeurs OpenDocument (*.ods);;Tous les fichiers (*.*)": "OpenDocument-Arbeitsmappen (*.ods);;Alle Dateien (*.*)",
    "Import ODS": "ODS-Import",
    "Le classeur choisi doit être au format .ods.": "Die ausgewählte Arbeitsmappe muss im .ods-Format vorliegen.",
    "Fichier sélectionné. Cliquez sur « Analyser le fichier ».": "Datei ausgewählt. Klicken Sie auf „Datei analysieren“.",
    "Le classeur sélectionné est introuvable.": "Die ausgewählte Arbeitsmappe wurde nicht gefunden.",
    "Analyse du classeur ODS en cours…": "ODS-Arbeitsmappe wird analysiert…",
    "Analyse ODS impossible": "ODS-Analyse fehlgeschlagen",
    "Analyse terminée : {sheets} feuille(s), {fields} colonne(s), {rows} ligne(s) de données au total.": "Analyse abgeschlossen: {sheets} Tabellenblatt/-blätter, {fields} Spalte(n), insgesamt {rows} Datenzeile(n).",
    "Sélectionnez une feuille dans la liste ci-dessus.": "Wählen Sie ein Tabellenblatt aus der obigen Liste.",
    "✓ Feuille source retenue : {name} — {rows} ligne(s), {fields} colonne(s).": "✓ Quelltabellenblatt ausgewählt: {name} — {rows} Zeile(n), {fields} Spalte(n).",
    "Feuille source validée. L’ordre des lignes sera conservé. Cliquez sur « Correspondance des champs… ».": "Quelltabellenblatt bestätigt. Die Reihenfolge der Zeilen wird beibehalten. Klicken Sie auf „Feldzuordnung…“.",
    "✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour la création de la collection et l’import des lignes.": "✓ Zuordnung bestätigt: {imported} Feld(er) werden importiert, {ignored} ignoriert. Bereit zum Erstellen der Sammlung und Importieren der Zeilen.",
    "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date, Bouton On / Off et Calculé</b> à partir des cellules et formats ODS ; vous pouvez corriger chaque proposition.<br>• Une colonne ODS devient un champ de la collection. Les cellules vides restent vides.<br>• L’ordre des lignes ODS est conservé : première ligne de données → fiche 1, puis 2, 3…<br>• Un champ source <b>N° / Numéro</b> reste une donnée ordinaire et n’influence jamais la numérotation automatique des fiches.": "• <b>Doppelklicken Sie auf den Namen eines G-Skol-Feldes, um ihn zu bearbeiten.</b><br>• G-Skol leitet <b>Text, Zahl, Währung, Datum, Ein/Aus-Schaltfläche und Berechnet</b> aus ODS-Zellen und -Formaten ab; Sie können jeden Vorschlag korrigieren.<br>• Eine ODS-Spalte wird zu einem Sammlungsfeld. Leere Zellen bleiben leer.<br>• Die ODS-Zeilenreihenfolge bleibt erhalten: erste Datenzeile → Datensatz 1, dann 2, 3…<br>• Ein Quellfeld <b>Nr. / Nummer</b> bleibt ein gewöhnliches Datenfeld und beeinflusst niemals die automatische Nummerierung der Datensätze.",
    "Nom déjà utilisé": "Name bereits verwendet",
    "Le fichier « {name} » existe déjà.": "Die Datei „{name}“ ist bereits vorhanden.",
    "Import du fichier « {source} » en cours…\nCréation de la collection et copie des lignes.": "Datei „{source}“ wird importiert…\nSammlung wird erstellt und Zeilen werden kopiert.",
    "Import {source} interrompu": "{source}-Import abgebrochen",
    "L’import n’a pas été conservé.": "Der Import wurde nicht beibehalten.",
    "✓ Import terminé : {records} fiche(s) créées dans « {name} » — ordre des lignes conservé.": "✓ Import abgeschlossen: {records} Datensatz/Datensätze in „{name}“ erstellt — Reihenfolge der Zeilen beibehalten."
})


# G-Skol 1.0.259 — DBF: dictionnaire effectivement utilisé par les fenêtres.
# G-Skol 1.0.258 — Import DBF allemand.
DE.update({'Choisissez un fichier dBASE/FoxPro .dbf. G-Skol lit directement la structure du fichier, les noms de champs et les enregistrements sans modifier la source. Les champs texte, numériques, dates et logiques Oui/Non sont reconnus. Les mémos externes restent signalés lorsqu’ils nécessitent un fichier compagnon .dbt/.fpt.': 'Wählen Sie eine dBASE/FoxPro-.dbf-Datei. G-Skol liest Dateistruktur, Feldnamen und Datensätze direkt, ohne die Quelle zu verändern. Text-, Zahlen-, Datums- und Ja/Nein-Felder werden erkannt. Externe Memofelder werden gekennzeichnet, wenn eine zugehörige .dbt/.fpt-Datei erforderlich ist.', 'Choisir un fichier DBF…': 'DBF-Datei auswählen…', 'Aucun fichier DBF sélectionné.': 'Keine DBF-Datei ausgewählt.', 'Après analyse, les champs et le nombre d’enregistrements apparaîtront ci-dessous.': 'Nach der Analyse werden die Felder und die Anzahl der Datensätze unten angezeigt.', 'Fichier / Champ': 'Datei / Feld', 'Après validation, G-Skol préparera la correspondance entre les champs DBF et les champs G-Skol.': 'Nach der Bestätigung bereitet G-Skol die Zuordnung zwischen DBF-Feldern und G-Skol-Feldern vor.', 'Choisir un fichier DBF': 'DBF-Datei auswählen', 'Fichiers DBF (*.dbf);;Tous les fichiers (*.*)': 'DBF-Dateien (*.dbf);;Alle Dateien (*.*)', 'Le fichier choisi doit être au format .dbf.': 'Die ausgewählte Datei muss das Format .dbf haben.', 'Fichier sélectionné : {source}{size}\nAucune donnée n’est importée ou modifiée pendant l’analyse.': 'Ausgewählte Datei: {source}{size}\nWährend der Analyse werden keine Daten importiert oder verändert.', 'Fichier prêt à être analysé.': 'Datei bereit zur Analyse.', 'Le fichier sélectionné est introuvable.': 'Die ausgewählte Datei wurde nicht gefunden.', 'Analyse du fichier DBF en cours…': 'DBF-Datei wird analysiert…', 'Analyse DBF impossible': 'DBF-Analyse fehlgeschlagen', '{count} champ(s)': '{count} Feld(er)', 'Booléen': 'Boolesch', 'Analyse terminée : {fields} champ(s), {rows} ligne(s). Encodage : {enc}. Version DBF : {version}.': 'Analyse abgeschlossen: {fields} Feld(er), {rows} Datensatz/Datensätze. Kodierung: {enc}. DBF-Version: {version}.', 'Sélectionnez le fichier analysé dans la liste ci-dessus.': 'Wählen Sie die analysierte Datei aus der obigen Liste.', '✓ Source DBF retenue : {name} — {rows} ligne(s), {fields} champ(s).': '✓ DBF-Quelle ausgewählt: {name} — {rows} Datensatz/Datensätze, {fields} Feld(er).', 'Source validée. L’ordre des enregistrements sera conservé. Cliquez sur « Correspondance des champs… ».': 'Quelle bestätigt. Die Reihenfolge der Datensätze bleibt erhalten. Klicken Sie auf „Feldzuordnung…“.', '✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour l’import.': '✓ Zuordnung bestätigt: {imported} Feld(er) werden importiert, {ignored} ignoriert. Bereit zum Import.', 'Créer la collection « {name} » et importer {rows} fiche(s) depuis {source} ?\n\nL’ordre des enregistrements sera conservé. Le fichier source ne sera jamais modifié.': 'Sammlung „{name}“ erstellen und {rows} Datensatz/Datensätze aus {source} importieren?\n\nDie Reihenfolge der Datensätze bleibt erhalten. Die Quelldatei wird niemals verändert.', '✓ Import terminé : {records} fiche(s) créées dans « {name} » — ordre conservé.': '✓ Import abgeschlossen: {records} Datensatz/Datensätze in „{name}“ erstellt — Reihenfolge beibehalten.', 'Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\n\nOrdre des fiches : ordre des enregistrements DBF conservé.': 'Import erfolgreich abgeschlossen.\n\nSammlung: {name}\nErstellte Datensätze: {records}\nImportierte Felder: {fields}\nReferenzwerte: {values}\n\nDatensatzreihenfolge: DBF-Reihenfolge beibehalten.', '• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date et Bouton On / Off</b> à partir des types DBF ; vous pouvez corriger chaque proposition.<br>• Un champ DBF devient un champ de la collection. Les valeurs vides restent vides.<br>• L’ordre des enregistrements DBF est conservé : premier enregistrement → fiche 1, puis 2, 3…<br>• Un champ source <b>N° / Numéro</b> reste une donnée ordinaire et n’influence jamais la numérotation automatique des fiches.': '• <b>Doppelklicken Sie auf einen G-Skol-Feldnamen, um ihn zu bearbeiten.</b><br>• G-Skol leitet <b>Text, Zahl, Währung, Datum und Ein/Aus-Schaltfläche</b> aus den DBF-Feldtypen ab; Sie können jeden Vorschlag korrigieren.<br>• Ein DBF-Feld wird zu einem Sammlungsfeld. Leere Werte bleiben leer.<br>• Die DBF-Datensatzreihenfolge bleibt erhalten: erster Datensatz → Datensatz 1, dann 2, 3…<br>• Ein Quellfeld <b>Nr. / Nummer</b> bleibt ein gewöhnliches Datenfeld und beeinflusst niemals die automatische Datensatznummerierung.', 'DBF : champ texte DBF': 'DBF: Textfeld', 'DBF : champ numérique DBF à 2 décimales identifié comme monétaire': 'DBF: Zahlenfeld mit zwei Dezimalstellen als Währung erkannt', 'DBF : champ numérique DBF': 'DBF: Zahlenfeld', 'DBF : champ monétaire DBF': 'DBF: Währungsfeld', 'DBF : champ logique DBF': 'DBF: logisches Feld', 'DBF : date DBF': 'DBF: Datumsfeld', 'DBF : mémo/objet DBF (fichier compagnon éventuel)': 'DBF: Memo-/Objektfeld (ggf. Begleitdatei erforderlich)', 'DBF : champ date DBF': 'DBF: Datumsfeld', 'DBF : champ mémo/objet DBF (fichier compagnon éventuel)': 'DBF: Memo-/Objektfeld (ggf. Begleitdatei erforderlich)', 'Import DBF terminé': 'DBF-Import abgeschlossen', 'Import DBF': 'DBF-Import', 'Import DBF en cours': 'DBF-Import läuft', 'Démarrer l’import DBF ?': 'DBF-Import starten?'})


# G-Skol 1.0.260 — SQLite import German translation.
DE.update({'Choisissez une base SQLite .db, .sqlite ou .sqlite3. G-Skol ouvre la base strictement en lecture seule, recense ses tables utilisateur, leurs colonnes et leurs types, puis vous laisse choisir la table qui deviendra la source de la nouvelle collection.': 'Wählen Sie eine SQLite-Datenbank (.db, .sqlite oder .sqlite3). G-Skol öffnet sie ausschließlich schreibgeschützt, zeigt Benutzertabellen, Spalten und Datentypen an und lässt Sie die Quelltabelle für die neue Sammlung auswählen.', 'Choisir une base SQLite…': 'SQLite-Datenbank auswählen…', 'Analyser la base': 'Datenbank analysieren', 'Aucune base SQLite sélectionnée.': 'Keine SQLite-Datenbank ausgewählt.', 'Après analyse, les tables, colonnes et nombres d’enregistrements apparaîtront ci-dessous.': 'Nach der Analyse werden Tabellen, Spalten und Datensatzanzahlen unten angezeigt.', 'Table / Colonne': 'Tabelle / Spalte', 'Choisir cette table': 'Diese Tabelle auswählen', 'Analysez la base puis choisissez la table source de la future collection G-Skol.': 'Analysieren Sie die Datenbank und wählen Sie anschließend die Quelltabelle für die neue G-Skol-Sammlung.', 'Après validation, G-Skol préparera la correspondance entre les colonnes SQLite et les champs G-Skol.': 'Nach der Bestätigung bereitet G-Skol die Zuordnung zwischen SQLite-Spalten und G-Skol-Feldern vor.', 'Choisir une base SQLite': 'SQLite-Datenbank auswählen', 'Bases SQLite (*.db *.sqlite *.sqlite3);;Tous les fichiers (*.*)': 'SQLite-Datenbanken (*.db *.sqlite *.sqlite3);;Alle Dateien (*.*)', 'Base sélectionnée : {source}{size}\nOuverture strictement en lecture seule pendant l’analyse.': 'Ausgewählte Datenbank: {source}{size}\nWährend der Analyse ausschließlich schreibgeschützt geöffnet.', 'Base sélectionnée. Cliquez sur « Analyser la base ».': 'Datenbank ausgewählt. Klicken Sie auf „Datenbank analysieren“.', 'Analyse de la base SQLite en cours…': 'SQLite-Datenbank wird analysiert…', ' — {count} référentiel(s) multi-colonnes reconnu(s).': ' — {count} mehrspaltige Referenzliste(n) erkannt.', 'Analyse terminée : {tables} table(s), {fields} colonne(s), {rows} ligne(s) au total.{refs}': 'Analyse abgeschlossen: {tables} Tabelle(n), {fields} Spalte(n), insgesamt {rows} Datensatz/Datensätze.{refs}', 'Sélectionnez la table contenant les fiches à importer.': 'Wählen Sie die Tabelle mit den zu importierenden Datensätzen.', ' — {count} référentiel(s) associé(s) reconnu(s).': ' — {count} zugehörige Referenzliste(n) erkannt.', '✓ Table SQLite retenue : {name} — {rows} ligne(s), {fields} colonne(s){refs}': '✓ SQLite-Tabelle ausgewählt: {name} — {rows} Datensatz/Datensätze, {fields} Spalte(n){refs}', 'Table validée. Cliquez sur « Correspondance des champs… ».': 'Tabelle bestätigt. Klicken Sie auf „Feldzuordnung…“.', '• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date, Bouton On / Off, Liste / Référentiel et Calculé</b> à partir des types, relations et données SQLite ; vous pouvez corriger chaque proposition.<br>• Une colonne SQLite devient un champ de la collection. Les valeurs vides restent vides.<br>• Les référentiels multi-colonnes reconnus peuvent créer des champs Maître / Reliés.<br>• L’ordre des lignes SQLite est conservé lors de la création des fiches.<br>• Un champ source <b>N° / Numéro</b> reste une donnée ordinaire et n’influence jamais la numérotation automatique des fiches.': '• <b>Doppelklicken Sie auf einen G-Skol-Feldnamen, um ihn zu bearbeiten.</b><br>• G-Skol erkennt <b>Text, Zahl, Währung, Datum, Ein/Aus-Schaltfläche, Liste / Referenzliste und Berechnet</b> anhand der SQLite-Typen, Beziehungen und Daten; alle Vorschläge können korrigiert werden.<br>• Jede SQLite-Spalte wird zu einem Sammlungsfeld. Leere Werte bleiben leer.<br>• Erkannte mehrspaltige Referenzlisten können Haupt- und verknüpfte Felder erzeugen.<br>• Die SQLite-Zeilenreihenfolge bleibt beim Erstellen der Datensätze erhalten.<br>• Ein Quellfeld <b>Nr. / Nummer</b> bleibt ein normales Datenfeld und beeinflusst niemals die automatische Nummerierung.', 'Lancer l’import SQLite ?': 'SQLite-Import starten?', 'Créer la collection « {name} » et importer {rows} fiche(s) depuis la table « {table} » ?\n\nLa base SQLite source restera strictement en lecture seule.': 'Sammlung „{name}“ erstellen und {rows} Datensatz/Datensätze aus Tabelle „{table}“ importieren?\n\nDie SQLite-Quelldatenbank bleibt ausschließlich schreibgeschützt.', 'Import de « {source} » en cours…\nCréation de la collection et copie des lignes.': '„{source}“ wird importiert…\nSammlung wird erstellt und Zeilen werden kopiert.', 'Import SQLite en cours': 'SQLite-Import läuft', 'Import SQLite interrompu': 'SQLite-Import unterbrochen', 'L’import n’a pas été conservé.': 'Der Import wurde nicht übernommen.', '✓ Import terminé : {records} fiche(s) créées dans « {name} ».': '✓ Import abgeschlossen: {records} Datensatz/Datensätze in „{name}“ erstellt.', 'Import SQLite terminé': 'SQLite-Import abgeschlossen', 'Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\nChamps Maîtres détectés : {masters}\nChamps Reliés détectés : {links}': 'Import erfolgreich abgeschlossen.\n\nSammlung: {name}\nErstellte Datensätze: {records}\nImportierte Felder: {fields}\nReferenzwerte: {values}\nErkannte Hauptfelder: {masters}\nErkannte verknüpfte Felder: {links}', 'SQLite : type texte SQLite': 'SQLite: Texttyp', 'SQLite : type numérique SQLite': 'SQLite: Zahlentyp', 'SQLite : type entier SQLite': 'SQLite: Ganzzahltyp', 'SQLite : type date SQLite': 'SQLite: Datumstyp'})

# G-Skol 1.0.263 — Dialog Sammlung öffnen (DE).
DE.update({'Choisissez une collection à ouvrir': 'Wählen Sie eine Sammlung zum Öffnen', 'Collection': 'Sammlung', 'Taille (Mo)': 'Größe (MB)', 'Propriétaire': 'Eigentümer', 'Créée le': 'Erstellt am', 'Description': 'Beschreibung', 'Collections (racine)': 'Sammlungen (Stammverzeichnis)', 'Déplacer vers…': 'Verschieben nach…', 'Ouvrir une collection': 'Sammlung öffnen', 'Ouvrir': 'Öffnen', 'Renommer…': 'Umbenennen…', 'Dupliquer…': 'Duplizieren…', 'Supprimer…': 'Löschen…', 'Nouveau dossier…': 'Neuer Ordner…', 'Parcourir…': 'Durchsuchen…', 'Fermer': 'Schließen'})

# G-Skol 1.0.264 — Export allemand : traductions canoniques réutilisables.
DE.update({'Exportation': 'Export',
 "Choisissez un dossier puis une collection. L'export crée un fichier transportable sans modifier la collection d'origine.": 'Wählen '
                                                                                                                             'Sie '
                                                                                                                             'zuerst '
                                                                                                                             'einen '
                                                                                                                             'Ordner '
                                                                                                                             'und '
                                                                                                                             'dann '
                                                                                                                             'eine '
                                                                                                                             'Sammlung. '
                                                                                                                             'Beim '
                                                                                                                             'Export '
                                                                                                                             'wird '
                                                                                                                             'eine '
                                                                                                                             'übertragbare '
                                                                                                                             'Datei '
                                                                                                                             'erstellt, '
                                                                                                                             'ohne '
                                                                                                                             'die '
                                                                                                                             'ursprüngliche '
                                                                                                                             'Sammlung '
                                                                                                                             'zu '
                                                                                                                             'verändern.',
 'Dossier :': 'Ordner:',
 'Collection :': 'Sammlung:',
 '— Aucun dossier sélectionné —': '— Kein Ordner ausgewählt —',
 '— Aucune collection sélectionnée —': '— Keine Sammlung ausgewählt —',
 'Exporter une collection complète  (.coldb)': 'Vollständige Sammlung exportieren  (.coldb)',
 'Exporter une structure de collection  (.colstr)': 'Sammlungsstruktur exportieren  (.colstr)',
 'Exporter le modèle de Fiche  (.colmod)': 'Datensatzvorlage exportieren  (.colmod)',
 'Exporter un modèle de Tableau  (.colmod)': 'Tabellenvorlage exportieren  (.colmod)',
 'Exporter un modèle de Requête  (.colmod)': 'Abfragevorlage exportieren  (.colmod)',
 "Exporter un modèle d'État  (.colmod)": 'Berichtsvorlage exportieren  (.colmod)',
 'Données, photos, référentiels, champs, modèles et réglages de la collection.': 'Sammlungsdaten, Fotos, Referenzlisten, '
                                                                                 'Felder, Vorlagen und Einstellungen.',
 'Structure, modèles, paramètres et référentiels, sans fiches, données ni photos.': 'Struktur, Vorlagen, Einstellungen und '
                                                                                    'Referenzlisten, ohne Datensätze, Daten '
                                                                                    'oder Fotos.',
 "Exporte uniquement le modèle de Fiche de la collection : disposition, styles, groupes, champs calculés et informations de liaison nécessaires. Aucune fiche ni donnée n'est exportée.": 'Exportiert '
                                                                                                                                                                                          'nur '
                                                                                                                                                                                          'die '
                                                                                                                                                                                          'Datensatzvorlage '
                                                                                                                                                                                          'der '
                                                                                                                                                                                          'Sammlung: '
                                                                                                                                                                                          'Layout, '
                                                                                                                                                                                          'Stile, '
                                                                                                                                                                                          'Gruppen, '
                                                                                                                                                                                          'berechnete '
                                                                                                                                                                                          'Felder '
                                                                                                                                                                                          'und '
                                                                                                                                                                                          'erforderliche '
                                                                                                                                                                                          'Verknüpfungsinformationen. '
                                                                                                                                                                                          'Es '
                                                                                                                                                                                          'werden '
                                                                                                                                                                                          'keine '
                                                                                                                                                                                          'Datensätze '
                                                                                                                                                                                          'oder '
                                                                                                                                                                                          'Daten '
                                                                                                                                                                                          'exportiert.',
 "Choisit un modèle dans la bibliothèque Modèles de Tableaux et crée une copie échangeable .colmod. Aucune collection ni donnée n'est modifiée.": 'Wählt '
                                                                                                                                                  'eine '
                                                                                                                                                  'Vorlage '
                                                                                                                                                  'aus '
                                                                                                                                                  'der '
                                                                                                                                                  'Bibliothek '
                                                                                                                                                  'der '
                                                                                                                                                  'Tabellenvorlagen '
                                                                                                                                                  'und '
                                                                                                                                                  'erstellt '
                                                                                                                                                  'eine '
                                                                                                                                                  'übertragbare '
                                                                                                                                                  '.colmod-Kopie. '
                                                                                                                                                  'Sammlungen '
                                                                                                                                                  'und '
                                                                                                                                                  'Daten '
                                                                                                                                                  'bleiben '
                                                                                                                                                  'unverändert.',
 "Choisit un modèle dans la bibliothèque Modèles de Requêtes et crée une copie échangeable .colmod. Aucune collection ni donnée n'est modifiée.": 'Wählt '
                                                                                                                                                  'eine '
                                                                                                                                                  'Vorlage '
                                                                                                                                                  'aus '
                                                                                                                                                  'der '
                                                                                                                                                  'Bibliothek '
                                                                                                                                                  'der '
                                                                                                                                                  'Abfragevorlagen '
                                                                                                                                                  'und '
                                                                                                                                                  'erstellt '
                                                                                                                                                  'eine '
                                                                                                                                                  'übertragbare '
                                                                                                                                                  '.colmod-Kopie. '
                                                                                                                                                  'Sammlungen '
                                                                                                                                                  'und '
                                                                                                                                                  'Daten '
                                                                                                                                                  'bleiben '
                                                                                                                                                  'unverändert.',
 "Choisit un modèle dans la bibliothèque Modèles d’États et crée une copie échangeable .colmod. Aucune collection ni donnée n'est modifiée.": 'Wählt '
                                                                                                                                              'eine '
                                                                                                                                              'Vorlage '
                                                                                                                                              'aus '
                                                                                                                                              'der '
                                                                                                                                              'Bibliothek '
                                                                                                                                              'der '
                                                                                                                                              'Berichtsvorlagen '
                                                                                                                                              'und '
                                                                                                                                              'erstellt '
                                                                                                                                              'eine '
                                                                                                                                              'übertragbare '
                                                                                                                                              '.colmod-Kopie. '
                                                                                                                                              'Sammlungen '
                                                                                                                                              'und '
                                                                                                                                              'Daten '
                                                                                                                                              'bleiben '
                                                                                                                                              'unverändert.',
 'La structure exportée reprend le principe déjà utilisé par « Dupliquer la structure de la collection » dans la Boîte à outils.': 'Die '
                                                                                                                                   'exportierte '
                                                                                                                                   'Struktur '
                                                                                                                                   'folgt '
                                                                                                                                   'demselben '
                                                                                                                                   'Prinzip '
                                                                                                                                   'wie '
                                                                                                                                   '„Sammlungsstruktur '
                                                                                                                                   'duplizieren“ '
                                                                                                                                   'im '
                                                                                                                                   'Werkzeugkasten.',
 'Retour': 'Zurück',
 'Exportation terminée': 'Export abgeschlossen',
 'Exportation impossible': 'Export fehlgeschlagen',
 'Modèle non valide': 'Ungültige Vorlage',
 'Le fichier de la collection sélectionnée est introuvable.': 'Die Datei der ausgewählten Sammlung wurde nicht gefunden.',
 'Exporter la collection complète': 'Vollständige Sammlung exportieren',
 'Exporter la structure de collection': 'Sammlungsstruktur exportieren',
 'Fichier G-Skol (*.coldb)': 'G-Skol-Datei (*.coldb)',
 'Fichier G-Skol (*.colstr)': 'G-Skol-Datei (*.colstr)',
 'Modèle G-Skol (*.colmod)': 'G-Skol-Vorlage (*.colmod)',
 'Exporter le modèle de Fiche': 'Datensatzvorlage exportieren',
 'Exporter un modèle de Tableau': 'Tabellenvorlage exportieren',
 'Exporter un modèle de Requête': 'Abfragevorlage exportieren',
 "Exporter un modèle d'État": 'Berichtsvorlage exportieren',
 'Nouveau dossier': 'Neuer Ordner',
 'Nom du nouveau dossier :': 'Name des neuen Ordners:',
 'Choisissez un modèle. Double-cliquez sur un modèle pour l’ouvrir directement. Vous pouvez aussi créer, renommer, déplacer ou supprimer vos dossiers et modèles.': 'Wählen '
                                                                                                                                                                    'Sie '
                                                                                                                                                                    'eine '
                                                                                                                                                                    'Vorlage. '
                                                                                                                                                                    'Mit '
                                                                                                                                                                    'einem '
                                                                                                                                                                    'Doppelklick '
                                                                                                                                                                    'öffnen '
                                                                                                                                                                    'Sie '
                                                                                                                                                                    'sie '
                                                                                                                                                                    'direkt. '
                                                                                                                                                                    'Ordner '
                                                                                                                                                                    'und '
                                                                                                                                                                    'Vorlagen '
                                                                                                                                                                    'können '
                                                                                                                                                                    'erstellt, '
                                                                                                                                                                    'umbenannt, '
                                                                                                                                                                    'verschoben '
                                                                                                                                                                    'oder '
                                                                                                                                                                    'gelöscht '
                                                                                                                                                                    'werden.',
 'Confirmer l’enregistrement': 'Speichern bestätigen',
 'Voulez-vous le remplacer ?': 'Möchten Sie die Datei ersetzen?',
 'Exporter un modèle d’État': 'Berichtsvorlage exportieren',
 'Modèles de Tableaux': 'Tabellenvorlagen',
 'Modèles de Requêtes': 'Abfragevorlagen',
 'Modèles d’États': 'Berichtsvorlagen',
 'Choisir un modèle': 'Vorlage auswählen',
 'Ouvrir un modèle': 'Vorlage öffnen'})

# G-Skol 1.0.267 — Sicherung / Wiederherstellung (deutsch)
DE.update({'Sauvegarde / Restauration': 'Sicherung / Wiederherstellung', 'Créez ou restaurez une sauvegarde, et gérez séparément les sauvegardes volontaires et les copies temporaires automatiques.': 'Erstellen oder stellen Sie eine Sicherung wieder her. Verwalten Sie manuelle Sicherungen getrennt von automatischen temporären Kopien.', 'Créer une sauvegarde complète des collections internes (dossier Workspace)': 'Vollständige Sicherung der internen Sammlungen erstellen (Workspace-Ordner)', 'Sauvegarder une ou plusieurs collections internes (dossier Workspace)': 'Eine oder mehrere interne Sammlungen sichern (Workspace-Ordner)', 'Restaurer une sauvegarde': 'Sicherung wiederherstellen', 'Gérer les sauvegardes': 'Sicherungen verwalten', 'Consulter et supprimer séparément les sauvegardes volontaires utilisateur et les sauvegardes temporaires automatiques.': 'Manuelle Sicherungen und automatische temporäre Sicherungen getrennt anzeigen und löschen.', 'Créer une sauvegarde': 'Sicherung erstellen', 'Sauvegarde vérifiée': 'Sicherung überprüft', 'Dossier créé :': 'Ordner erstellt:', 'Fichiers .coldb individuels :': 'Einzelne .coldb-Dateien:', '{collections} collection(s), {files} fichier(s) vérifié(s).': '{collections} Sammlung(en), {files} Datei(en) überprüft.', 'Collection(s) — cochez les fichiers à copier': 'Sammlung(en) — zu kopierende Dateien auswählen', 'Fichier source': 'Quelldatei', 'Choisir le dossier de destination': 'Zielordner auswählen', 'Tout sélectionner': 'Alle auswählen', 'Tout désélectionner': 'Alle abwählen', 'Ouvrir la sauvegarde': 'Sicherung öffnen', 'Supprimer les sauvegardes sélectionnées': 'Ausgewählte Sicherungen löschen', 'Sauvegarde': 'Sicherung', 'Date / heure': 'Datum / Uhrzeit', 'Taille': 'Größe', 'Les sauvegardes volontaires et les copies de sécurité créées automatiquement par G-Skol sont séparées afin d’éviter toute confusion.': 'Manuelle Sicherungen und automatisch von G-Skol erstellte Sicherheitskopien werden zur besseren Übersicht getrennt verwaltet.', 'Sauvegardes volontaires utilisateur — {count} élément(s) — {size}': 'Manuelle Sicherungen — {count} Einträge — {size}', 'Supprimer les collections sélectionnées': 'Ausgewählte Sammlungen löschen', 'Contenu de la sauvegarde': 'Sicherungsinhalt', 'Confirmer la suppression': 'Löschen bestätigen', 'Suppression définitive': 'Endgültig löschen', 'Restaurer la sélection': 'Auswahl wiederherstellen', 'Restauration terminée': 'Wiederherstellung abgeschlossen', 'Choisir depuis le Workspace…': 'Aus Workspace auswählen…', 'Sauvegardes internes (Workspace)': 'Interne Sicherungen (Workspace)', 'Sauvegardes stockées ailleurs dans Windows': 'Anderswo in Windows gespeicherte Sicherungen', 'Aucun dossier de sauvegarde sélectionné.': 'Kein Sicherungsordner ausgewählt.', 'Choisissez un dossier de sauvegarde G-Skol. G-Skol l’analysera avant d’afficher les collections disponibles.': 'Wählen Sie einen G-Skol-Sicherungsordner. G-Skol analysiert ihn und zeigt danach die verfügbaren Sammlungen an.', 'Collection': 'Sammlung', 'Destination': 'Ziel', 'En cas de conflit': 'Bei Namenskonflikt', 'Remplacer': 'Ersetzen', 'Conserver les deux': 'Beide behalten', 'Créer les copies .coldb': ' .coldb-Kopien erstellen', 'Choisir un dossier…': 'Ordner auswählen…', 'Dossier de destination :': 'Zielordner:', 'Nom du nouveau sous-dossier :': 'Name des neuen Unterordners:', 'Collections ouvertes hors du Workspace (exclues) :': 'Außerhalb des Workspace geöffnete Sammlungen (ausgeschlossen):', 'Aucune actuellement ouverte. Les collections extérieures fermées ne sont pas recensées.': 'Derzeit keine geöffnet. Geschlossene externe Sammlungen werden nicht aufgelistet.', '1 / 3 — Collections du Workspace': '1 / 3 — Workspace-Sammlungen', '2 / 3 — Bases stockées ailleurs': '2 / 3 — Extern gespeicherte Datenbanken', '3 / 3 — Destination de la sauvegarde': '3 / 3 — Sicherungsziel', 'Créer la sauvegarde complète': 'Vollständige Sicherung erstellen', 'Parcourir…': 'Durchsuchen…', 'Suivant': 'Weiter', 'Précédent': 'Zurück', 'Retour': 'Zurück', 'Fermer': 'Schließen', 'Supprimer': 'Löschen', 'Annuler': 'Abbrechen', 'Oui': 'Ja', 'Non': 'Nein', 'Sauvegardes temporaires automatiques (avant ajout ou import)': 'Automatische temporäre Sicherungen (vor Hinzufügen oder Import)', 'Choisir un ou plusieurs fichiers .coldb extérieurs': 'Eine oder mehrere externe .coldb-Dateien auswählen'})

DE.update({"Sauvegardes volontaires utilisateur":"Manuelle Sicherungen", "élément(s)":"Einträge"})

# G-Skol 1.0.268 — vollständiger deutscher Sicherungs-/Wiederherstellungsdurchgang
DE.update({'2 / 3 — Bases situées sur un autre support': '2 / 3 — Extern gespeicherte Datenbanken',
 'Aucun conflit': 'Kein Konflikt',
 'Aucune': 'Keine',
 'Aucune sauvegarde sélectionnée': 'Keine Sicherung ausgewählt',
 'Choisir dans le Workspace…': 'Aus Workspace auswählen…',
 'Choisir le dossier de sauvegarde à restaurer': 'Wiederherzustellenden Sicherungsordner auswählen',
 'Choisir le dossier…': 'Ordner auswählen…',
 'Choisir un ou plusieurs fichiers .coldb extérieurs': 'Eine oder mehrere externe .coldb-Dateien auswählen',
 'Choisissez maintenant le dossier où placer les copies. G-Skol créera dans ce dossier un nouveau sous-dossier daté contenant les .coldb sélectionnés.': 'Wählen '
                                                                                                                                                         'Sie '
                                                                                                                                                         'den '
                                                                                                                                                         'Zielordner '
                                                                                                                                                         'für '
                                                                                                                                                         'die '
                                                                                                                                                         'Kopien. '
                                                                                                                                                         'G-Skol '
                                                                                                                                                         'erstellt '
                                                                                                                                                         'darin '
                                                                                                                                                         'einen '
                                                                                                                                                         'neuen '
                                                                                                                                                         'datierten '
                                                                                                                                                         'Unterordner '
                                                                                                                                                         'mit '
                                                                                                                                                         'den '
                                                                                                                                                         'ausgewählten '
                                                                                                                                                         '.coldb-Dateien.',
 'Cochez les collections du Workspace à sauvegarder. Vous pourrez ensuite ajouter des bases situées sur une clé USB, un disque externe ou dans un autre dossier.': 'Wählen '
                                                                                                                                                                   'Sie '
                                                                                                                                                                   'die '
                                                                                                                                                                   'zu '
                                                                                                                                                                   'sichernden '
                                                                                                                                                                   'Workspace-Sammlungen '
                                                                                                                                                                   'aus. '
                                                                                                                                                                   'Anschließend '
                                                                                                                                                                   'können '
                                                                                                                                                                   'Sie '
                                                                                                                                                                   'Datenbanken '
                                                                                                                                                                   'von '
                                                                                                                                                                   'USB-Sticks, '
                                                                                                                                                                   'externen '
                                                                                                                                                                   'Laufwerken '
                                                                                                                                                                   'oder '
                                                                                                                                                                   'anderen '
                                                                                                                                                                   'Ordnern '
                                                                                                                                                                   'hinzufügen.',
 'Collections incluses ({count}) :': 'Enthaltene Sammlungen ({count}):',
 'Collections sauvegardées': 'Sammlungen gesichert',
 'En cas de renommage, G-Skol ajoute « - Restaurée » (puis « - 2 », « - 3 »… en cas de doublon) au nom du fichier et au nom de la collection. Une collection actuellement ouverte ne peut pas être remplacée : utilisez alors « Conserver les deux ».': 'Beim '
                                                                                                                                                                                                                                                        'Umbenennen '
                                                                                                                                                                                                                                                        'ergänzt '
                                                                                                                                                                                                                                                        'G-Skol '
                                                                                                                                                                                                                                                        '„- '
                                                                                                                                                                                                                                                        'Wiederhergestellt“ '
                                                                                                                                                                                                                                                        '(bei '
                                                                                                                                                                                                                                                        'Namensgleichheit '
                                                                                                                                                                                                                                                        '„- '
                                                                                                                                                                                                                                                        '2“, '
                                                                                                                                                                                                                                                        '„- '
                                                                                                                                                                                                                                                        '3“ '
                                                                                                                                                                                                                                                        'usw.) '
                                                                                                                                                                                                                                                        'im '
                                                                                                                                                                                                                                                        'Datei- '
                                                                                                                                                                                                                                                        'und '
                                                                                                                                                                                                                                                        'Sammlungsnamen. '
                                                                                                                                                                                                                                                        'Eine '
                                                                                                                                                                                                                                                        'derzeit '
                                                                                                                                                                                                                                                        'geöffnete '
                                                                                                                                                                                                                                                        'Sammlung '
                                                                                                                                                                                                                                                        'kann '
                                                                                                                                                                                                                                                        'nicht '
                                                                                                                                                                                                                                                        'ersetzt '
                                                                                                                                                                                                                                                        'werden; '
                                                                                                                                                                                                                                                        'wählen '
                                                                                                                                                                                                                                                        'Sie '
                                                                                                                                                                                                                                                        'dann '
                                                                                                                                                                                                                                                        '„Beide '
                                                                                                                                                                                                                                                        'behalten“.',
 'La restauration a été interrompue :': 'Die Wiederherstellung wurde unterbrochen:',
 'Nom du dossier daté :': 'Name des datierten Ordners:',
 'Nom du nouveau sous-dossier :': 'Name des neuen Unterordners:',
 "Pour ajouter des bases situées hors du Workspace, cliquez sur « Parcourir… » en bas de cet écran. Dans l'explorateur, choisissez un ou plusieurs fichiers .coldb avec Ctrl ou Maj. Vous pouvez aussi passer cette étape sans rien ajouter.": 'Um '
                                                                                                                                                                                                                                               'Datenbanken '
                                                                                                                                                                                                                                               'außerhalb '
                                                                                                                                                                                                                                               'des '
                                                                                                                                                                                                                                               'Workspace '
                                                                                                                                                                                                                                               'hinzuzufügen, '
                                                                                                                                                                                                                                               'klicken '
                                                                                                                                                                                                                                               'Sie '
                                                                                                                                                                                                                                               'unten '
                                                                                                                                                                                                                                               'auf '
                                                                                                                                                                                                                                               '„Durchsuchen…“. '
                                                                                                                                                                                                                                               'Wählen '
                                                                                                                                                                                                                                               'Sie '
                                                                                                                                                                                                                                               'im '
                                                                                                                                                                                                                                               'Datei-Explorer '
                                                                                                                                                                                                                                               'eine '
                                                                                                                                                                                                                                               'oder '
                                                                                                                                                                                                                                               'mehrere '
                                                                                                                                                                                                                                               '.coldb-Dateien '
                                                                                                                                                                                                                                               'mit '
                                                                                                                                                                                                                                               'Strg '
                                                                                                                                                                                                                                               'oder '
                                                                                                                                                                                                                                               'Umschalt. '
                                                                                                                                                                                                                                               'Sie '
                                                                                                                                                                                                                                               'können '
                                                                                                                                                                                                                                               'diesen '
                                                                                                                                                                                                                                               'Schritt '
                                                                                                                                                                                                                                               'auch '
                                                                                                                                                                                                                                               'überspringen.',
 'Restauration incomplète': 'Wiederherstellung unvollständig',
 'Restaurée': 'Wiederhergestellt',
 'SUPPRIMER': 'LÖSCHEN',
 'Sauvegarde complète': 'Vollständige Sicherung',
 "Sauvegarde complète de tous les fichiers du Workspace, sauf les anciennes sauvegardes. Chaque sauvegarde reprend l'ensemble : elle n'est pas incrémentielle. Les collections sont des .coldb utilisables individuellement.": 'Vollständige '
                                                                                                                                                                                                                               'Sicherung '
                                                                                                                                                                                                                               'aller '
                                                                                                                                                                                                                               'Workspace-Dateien '
                                                                                                                                                                                                                               'ohne '
                                                                                                                                                                                                                               'frühere '
                                                                                                                                                                                                                               'Sicherungen. '
                                                                                                                                                                                                                               'Jede '
                                                                                                                                                                                                                               'Sicherung '
                                                                                                                                                                                                                               'enthält '
                                                                                                                                                                                                                               'den '
                                                                                                                                                                                                                               'gesamten '
                                                                                                                                                                                                                               'Bestand '
                                                                                                                                                                                                                               'und '
                                                                                                                                                                                                                               'ist '
                                                                                                                                                                                                                               'nicht '
                                                                                                                                                                                                                               'inkrementell. '
                                                                                                                                                                                                                               'Sammlungen '
                                                                                                                                                                                                                               'sind '
                                                                                                                                                                                                                               'eigenständig '
                                                                                                                                                                                                                               'verwendbare '
                                                                                                                                                                                                                               '.coldb-Dateien.',
 'Sauvegarde de plusieurs collections': 'Sicherung mehrerer Sammlungen',
 'Sauvegarde stockée ailleurs dans Windows': 'Anderswo in Windows gespeicherte Sicherung',
 'Suppression incomplète': 'Löschung unvollständig',
 'Sélection : {workspace_count} fichier(s) du Workspace et {external_count} fichier(s) extérieurs.': 'Auswahl: '
                                                                                                     '{workspace_count} '
                                                                                                     'Workspace-Datei(en) '
                                                                                                     'und '
                                                                                                     '{external_count} '
                                                                                                     'externe '
                                                                                                     'Datei(en).',
 '{count} collection(s) trouvée(s). Sélectionnez celles à restaurer.': '{count} Sammlung(en) gefunden. Wählen Sie '
                                                                       'die wiederherzustellenden Sammlungen aus.'})

DE.update({'Aucune collection .coldb valide n’a été trouvée dans ce dossier.': 'In '
                                                                     'diesem '
                                                                     'Ordner '
                                                                     'wurde '
                                                                     'keine '
                                                                     'gültige '
                                                                     '.coldb-Sammlung '
                                                                     'gefunden.',
 'Aucune sélection': 'Keine Auswahl',
 'La collection « {name} » est actuellement ouverte. Fermez-la ou choisissez « Conserver les deux ».': 'Die '
                                                                                                       'Sammlung '
                                                                                                       '„{name}“ '
                                                                                                       'ist '
                                                                                                       'derzeit '
                                                                                                       'geöffnet. '
                                                                                                       'Schließen '
                                                                                                       'Sie '
                                                                                                       'sie '
                                                                                                       'oder '
                                                                                                       'wählen '
                                                                                                       'Sie '
                                                                                                       '„Beide '
                                                                                                       'behalten“.',
 'Restaurer': 'Wiederherstellen',
 'Sélectionnez au moins une collection à restaurer.': 'Wählen Sie mindestens '
                                                      'eine Sammlung zur '
                                                      'Wiederherstellung aus.',
 '{count} collection(s) restaurée(s) dans le Workspace.': '{count} '
                                                          'Sammlung(en) im '
                                                          'Workspace '
                                                          'wiederhergestellt.',
 '{count} collection(s) trouvée(s). Cliquez sur Suivant pour choisir celles à restaurer.': '{count} '
                                                                                           'Sammlung(en) '
                                                                                           'gefunden. '
                                                                                           'Klicken '
                                                                                           'Sie '
                                                                                           'auf '
                                                                                           '„Weiter“, '
                                                                                           'um '
                                                                                           'die '
                                                                                           'wiederherzustellenden '
                                                                                           'Sammlungen '
                                                                                           'auszuwählen.'})

# G-Skol 1.0.269 — sauvegarde : messages dynamiques et noms de dossiers.
DE.update({
    "Emplacement final :": "Endgültiger Speicherort:",
    "Nom du dossier daté :": "Name des datierten Ordners:",
    "{count} fichier(s) .coldb créé(s) et vérifié(s) dans :": "{count} .coldb-Datei(en) erstellt und überprüft in:",
})

# 1.0.271 — Kontextmenüs des Datensatz-Ateliers (DE)
DE.update({
    'Liaisons de champs': 'Feldverknüpfungen',
    'Désactiver Maître': 'Masterfeld deaktivieren',
    'Définir comme Maître': 'Als Masterfeld festlegen',
    'Relié à…': 'Verknüpfen mit…',
    'Délier': 'Verknüpfung lösen',
    'Délier de…': 'Verknüpfung lösen von…',
    'Aucun champ Maître': 'Kein Masterfeld',
    'Aligner': 'Ausrichten',
    'Taille': 'Größe',
    'Champs complets': 'Ganze Felder',
    'Libellés': 'Beschriftungen',
    'Données': 'Daten',
    'Gauche': 'Links',
    'Centre': 'Zentriert',
    'Droite': 'Rechts',
    'Haut': 'Oben',
    'Bas': 'Unten',
    'Sur la grille': 'Am Raster ausrichten',
    'Au contenu': 'An Inhalt anpassen',
    'Au plus grand': 'An größtes anpassen',
    'Au plus petit': 'An kleinstes anpassen',
    'Au plus large': 'An breitestes anpassen',
    'Au plus étroit': 'An schmalstes anpassen',
    'Mise en forme': 'Formatierung',
    'Libellé': 'Beschriftung',
    'Donnée': 'Datenwert',
    'Police et taille…': 'Schriftart und -größe…',
    'Couleur du texte…': 'Textfarbe…',
    'Gras': 'Fett',
    'Italique': 'Kursiv',
    'Souligné': 'Unterstrichen',
    'Style par défaut': 'Standardstil',
    'Dupliquer le champ': 'Feld duplizieren',
    'Modifier le champ…': 'Feld bearbeiten…',
    'Effacer de la fiche': 'Aus dem Datensatz entfernen',
    'Retire le champ de la fiche sans supprimer sa définition ni ses données.': 'Entfernt das Feld aus dem Datensatz, ohne seine Definition oder Daten zu löschen.',
    'Aligner les cadres Photo': 'Fotorahmen ausrichten',
    'Taille des cadres Photo': 'Größe der Fotorahmen',
    'Couleur de fond…': 'Hintergrundfarbe…',
    'Couleur du cadre…': 'Rahmenfarbe…',
    'Épaisseur du cadre': 'Rahmenstärke',
    'Aucun cadre': 'Kein Rahmen',
    'Titre du cadre': 'Rahmentitel',
    'Modifier le texte…': 'Text bearbeiten…',
    'Couleur…': 'Farbe…',
    'Style du titre par défaut': 'Standardstil des Titels',
    'Dupliquer le cadre Photo': 'Fotorahmen duplizieren',
    'Supprimer le cadre Photo…': 'Fotorahmen löschen…',
    'Supprimer le cadre…': 'Rahmen löschen…',
})

# G-Skol 1.0.273 — Ateliers / Zuordnung der Vorlagenfelder
DE.update({'Correspondance des champs du modèle': 'Zuordnung der Vorlagenfelder', "La colonne « Champ de la collection » contient les vrais champs MM3 de la collection actuelle. Choisissez, si nécessaire, l'emplacement correspondant dans le modèle de fiche ouvert. Un champ sans emplacement reste intact dans la palette. L'application du modèle ne crée aucun champ et ne modifie pas les propriétés métier de la collection.": 'Die Spalte „Sammlungsfeld“ enthält die tatsächlichen Felder der aktuellen Sammlung. Wählen Sie bei Bedarf die entsprechende Position in der geöffneten Datensatzvorlage. Ein Feld ohne Position bleibt in der Palette unverändert. Die Anwendung der Vorlage erstellt keine Felder und ändert keine Feldeigenschaften der Sammlung.', 'Action': 'Aktion', 'Champ de la collection': 'Sammlungsfeld', 'Type collection': 'Sammlungstyp', 'Emplacement du modèle': 'Vorlagenposition', 'Type modèle': 'Vorlagentyp', 'Détection MM3': 'G-Skol-Erkennung', 'Aucun emplacement proposé — le champ restera dans la palette': 'Keine Position vorgeschlagen — das Feld bleibt in der Palette', 'Clé et type identiques reconnus': 'Übereinstimmender Schlüssel und Typ erkannt', 'Clé identique reconnue — type métier de la collection conservé': 'Übereinstimmender Schlüssel erkannt — Feldtyp der Sammlung bleibt erhalten', 'Libellé et type compatibles reconnus': 'Passende Bezeichnung und Typ erkannt', 'Libellé compatible reconnu — type métier de la collection conservé': 'Passende Bezeichnung erkannt — Feldtyp der Sammlung bleibt erhalten', 'Champ système MM3 — non importé (valeurs de la collection conservées)': 'G-Skol-Systemfeld — nicht importiert (Sammlungswerte bleiben erhalten)', "Ajout à la palette — à placer par l'utilisateur": 'Zur Palette hinzugefügt — vom Benutzer zu platzieren', 'Champ conservé dans la collection — non ajouté au modèle': 'Feld bleibt in der Sammlung — nicht zur Vorlage hinzugefügt', 'Choisissez un emplacement du modèle': 'Wählen Sie eine Vorlagenposition', "Correspondance choisie par l'utilisateur": 'Vom Benutzer gewählte Zuordnung', 'Importer': 'Importieren', 'Créer': 'Erstellen', 'Ne pas importer': 'Nicht importieren', 'Tout importer': 'Alle importieren', 'Tout ignorer': 'Alle ignorieren', 'Valider la correspondance': 'Zuordnung bestätigen', 'Texte': 'Text', 'Nombre': 'Zahl', 'Date': 'Datum', 'Bouton On / Off': 'Ein/Aus-Schalter', 'Liste / Référentiel': 'Liste / Referenz', 'Lien': 'Link', 'Monétaire': 'Währung', 'Calculé': 'Berechnet', 'Photo / Image': 'Foto / Bild', 'État détaillé': 'Detaillierter Bericht', 'Ce modèle utilise l’ancien constructeur détaillé ; sa reprise sera ajoutée ultérieurement.': 'Diese Vorlage verwendet den bisherigen Konstruktor für detaillierte Berichte. Die Unterstützung wird später ergänzt.'})
DE.update({'ordre croissant': 'aufsteigende Reihenfolge', 'ordre décroissant': 'absteigende Reihenfolge', 'ordre personnalisé': 'benutzerdefinierte Reihenfolge', "Référentiel « {label} » — {mode_label}. Une valeur retirée reste présente dans les fiches qui l'utilisent déjà.": 'Referenzliste „{label}“ — {mode_label}. Ein entfernter Wert bleibt in den Datensätzen erhalten, in denen er bereits verwendet wird.'})
