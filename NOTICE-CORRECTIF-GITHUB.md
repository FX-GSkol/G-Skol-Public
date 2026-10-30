# Correctif de fabrication pour GitHub — G-Skol 20.35

Cette copie ne modifie pas le Core 20.35 validé.

## Changements
- `CREER-G-SKOL-PORTABLE.bat` ne lit plus `../Workspace` : aucune bibliothèque privée n’est aspirée automatiquement.
- `gskol_copy_library.py` accepte uniquement un répertoire explicitement déclaré `--public`.
- `G-Skol.iss` annonce la version `20.35` et rend facultative la bibliothèque supplémentaire.
- Les dix bases de `ModelesOfficiels/` restent intégrées au programme.

## Bibliothèque supplémentaire
Si nécessaire, créer `BibliothequePublique/Modèles de Fiches/` dans la copie locale **après avoir vérifié les droits et les données**. Ne jamais y placer les modèles personnels. Si le dossier est absent, la compilation peut se poursuivre sans bibliothèque supplémentaire ; certaines fonctions d'initialisation des modèles devront être testées sur un Windows propre.

## Avant publication publique ou demande SignPath
- Vérifier l'origine et les droits de redistribution des données des modèles officiels.
- Tester la fabrication sur Windows avec Python 3.11, PyInstaller et Inno Setup.
- Tester le premier lancement portable et installé, notamment la création du Workspace et la disponibilité des modèles.
- Vérifier les obligations de licence PySide6/Qt et des autres composants.
- Préparer un processus de compilation reproductible et contrôlé pour SignPath.

**Ne pas rendre le dépôt public ni soumettre SignPath avant ces contrôles.**
