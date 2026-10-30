# G-Skol 6.1 — Contrôles avant publication

**Projet :** G-Skol — Gestion de collections  
**Auteur :** FX — © 2026 FX  
**Licence du code original :** GNU GPL v3 (voir [LICENSE](LICENSE))  
**État :** dépôt GitHub privé — publication publique non encore autorisée

Ce document suit les vérifications préparatoires à la mise en ligne publique de G-Skol. Les cases cochées correspondent aux contrôles déjà effectués ; elles ne constituent pas une garantie juridique générale.

## Contrôles effectués

- [x] Dépôt GitHub créé, avec branche `main` et fichier `LICENSE`.
- [x] Choix de la licence GNU GPL v3 confirmé par l'auteur.
- [x] Version affichée et scripts de fabrication actualisés pour **G-Skol 6.1**.
- [x] Fabrication automatisée GitHub Actions exécutée avec succès.
- [x] Versions Windows **portable** et **installable** fabriquées et testées.
- [x] Dix bases de modèles officiels examinées : aucune fiche de collection personnelle enregistrée dans les tables contrôlées.
- [x] Origine des icônes et logos G-Skol clarifiée : créations générées avec l'assistance de ChatGPT, sélectionnées par l'auteur.
- [x] Fichier `.gitignore` vérifié : exclusion des collections `.coldb`, des dossiers `Diagnostics/`, `build/`, `dist/` et des fichiers journaux.
- [x] Absence du dossier `Diagnostics/` constatée dans l'arborescence actuelle du dépôt GitHub.
- [x] `README.md` mis à jour pour la version 6.1.

## Vérifications restant à effectuer

- [ ] Confirmer que l'auteur détient les droits nécessaires sur **tous** les fichiers sources et ressources inclus dans le dépôt.
- [ ] Vérifier les conditions de réutilisation et de redistribution des données de référence du modèle **Minéraux / IMA**. Le référentiel a été compilé et enrichi par FX à partir de sources en ligne ; son origine ne suffit pas à établir les droits de redistribution de toutes les données.
- [ ] Inventorier les composants tiers réellement distribués avec les exécutables Windows (notamment Python, PySide6/Qt, shiboken6 et leurs dépendances) et préparer les notices de licence nécessaires.
- [ ] Vérifier les conditions applicables à **PyInstaller** et **Inno Setup** dans le processus de distribution.
- [ ] Examiner les éventuelles ressources graphiques anciennes ou inutilisées et confirmer leurs droits.
- [ ] Contrôler les scripts d'installation, les associations de fichiers et les références résiduelles aux anciens noms du projet ; préserver la compatibilité lorsqu'elle est intentionnelle.
- [ ] Vérifier qu'aucun fichier personnel, journal ou secret n'est suivi par Git, y compris dans l'historique si nécessaire. Le fichier `.gitignore` ne retire pas les fichiers déjà enregistrés dans des commits.
- [ ] Effectuer une dernière vérification du dépôt et de la documentation avant de passer de **privé** à **public**.
- [ ] Vérifier les critères de **SignPath Foundation** et préparer la demande de signature après publication publique, si les conditions sont remplies.

## Situation actuelle

Le dépôt GitHub existe et les distributions Windows de G-Skol 6.1 ont été construites et testées. **Le dépôt doit rester privé jusqu'à la clôture des contrôles en attente.** Aucune signature numérique Windows n'a encore été obtenue.

Ce document est une liste de suivi interne ; il pourra être retiré du dépôt public ou archivé une fois la préparation terminée.
