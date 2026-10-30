# Dashboard RH TelcomCI

**Version Power BI (publiée) :** [ouvrir le rapport](https://app.powerbi.com/view?r=eyJrIjoiMGEyYzkyNjUtZjg0Yy00YmI5LThiYjktYmY4YjJiNTRjMGIzIiwidCI6IjFiMWY3NzkzLWU3NjUtNDhjYy04NmZmLTYzNGUwN2Q1NjhlNCJ9)

**Version Streamlit** : décrite ci-dessous, déployable sur Streamlit Community Cloud.

Dashboard interactif Streamlit pour la Direction des Ressources Humaines. Il permet de suivre les effectifs, la masse salariale, l'absentéisme, la performance, l'engagement et le turnover, et il identifie les collaborateurs à risque de départ.

## Contenu

Le dashboard suit la logique « cycle de vie du collaborateur » : une page d'accueil avec le sommaire, puis 15 pages thématiques. Chaque page a ses segments **Période** (photographies semestrielles) et **Département**.

| # | Page | Ce qu'on y suit |
|---|---|---|
| 1 | Vue d'ensemble RH | Collaborateurs, diversité, recrutements et départs, avec tendances |
| 2 | Analyse démographique | Effectif, arrivées, départs, genre, âge, ancienneté, contrats, villes, tranches de salaire |
| 3 | Analyse de la diversité | Générations, niveau d'études, grade × genre, femmes cadres, diversité par ville |
| 4 | Fiche collaborateur | Profil individuel, rémunération, absences, performance, niveau et facteurs de risque |
| 5 | Historique et tendances | Effectif et départs par période, évolution de l'effectif, départs par genre |
| 6 | Nouveaux arrivants | Arrivées par genre, grade, âge, tendance, arrivées et départs, top départements |
| 7 | Analyse salariale | Masse salariale, salaires moyens par genre, département, grade, ville, âge, top postes |
| 8 | Écart salarial F / H | Écart par âge, département, grade et ville, écart à grade égal |
| 9 | Évaluation de la performance | Niveaux de performance, répartition par genre, ancienneté et âge |
| 10 | Absentéisme | Taux global, par genre, contrat, âge, grade, ancienneté, site et département |
| 11 | Absences par département | Jours d'absence et non justifiés par ancienneté, grade, poste, collaborateurs les plus absents |
| 12 | Profil des départs | Départs par ancienneté, contrat, grade, genre, ville, département et performance |
| 13 | Analyse des départs | Taux de départ global, CDI/CDD, cadres, tendances, comparaison avec la période précédente |
| 14 | Prédiction des départs | Liste filtrable des scores de risque au 31/12/2024, avec facteurs et export CSV |
| 15 | Profil département | Vue d'ensemble, départs et prédiction pour un département, avec synthèse rédigée |

Adaptations aux données TelcoPeople : pas de noms (identifiants anonymisés), pas de pays ni de type de départ, données semestrielles et non mensuelles. Les « Business Units » sont remplacées par les départements, et le motif de départ par le niveau de performance.

**Définitions**
- *Taux d'absentéisme* = jours d'absence sur 6 mois ÷ 130 jours ouvrés.
- *Taux de départ* = part des collaborateurs partis dans les 6 mois suivant la date de référence. Il n'est connu que pour les photographies historiques (juin 2022 à juin 2024).
- *Collaborateurs signalés* = les 16 % de scores de risque les plus élevés, même règle que la soumission finale du challenge.

## Fichiers

```
dashboard/
├── app.py             # interface Streamlit
├── preparation.py     # nettoyage, variables et modèle (identiques au notebook 12)
├── requirements.txt   # dépendances
└── README.md
.streamlit/config.toml # thème (à la racine du dépôt)
data/raw/              # telcopeople_train.csv, telcopeople_test.csv
```

Le modèle de risque est une régression logistique régularisée avec interactions, réentraînée au démarrage sur l'historique (quelques secondes, mise en cache ensuite). Aucun fichier de modèle n'est donc nécessaire.

## Lancer en local

Depuis la racine du dépôt :

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

## Déployer en ligne (Streamlit Community Cloud, gratuit)

1. Pousser le dépôt sur GitHub. Les dossiers `dashboard/`, `data/raw/` et `.streamlit/` doivent y figurer.
2. Se connecter sur https://share.streamlit.io avec le compte GitHub qui a accès au dépôt.
3. Cliquer sur **Create app**, puis **Deploy a public app from GitHub**.
4. Renseigner :
   - **Repository** : `cephasbrou7/TelcoPeople`
   - **Branch** : la branche qui contient le dashboard (par exemple `main` après fusion)
   - **Main file path** : `dashboard/app.py`
5. Optionnel : choisir une adresse personnalisée (par exemple `telcomci-rh.streamlit.app`).
6. Cliquer sur **Deploy**. Le premier démarrage prend 2 à 3 minutes, le temps d'installer les dépendances.

Le fichier `dashboard/requirements.txt` est détecté automatiquement, car il se trouve dans le même dossier que `app.py`.

> ⚠️ Les données du challenge sont alors publiques via l'application. Si l'école l'exige, déployer en mode privé (option disponible dans les paramètres de l'application sur Streamlit Cloud) et partager l'accès aux membres du jury.
