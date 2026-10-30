# Dashboard RH TelcomCI

**Version Power BI (publiée) :** [ouvrir le rapport](https://app.powerbi.com/view?r=eyJrIjoiMGEyYzkyNjUtZjg0Yy00YmI5LThiYjktYmY4YjJiNTRjMGIzIiwidCI6IjFiMWY3NzkzLWU3NjUtNDhjYy04NmZmLTYzNGUwN2Q1NjhlNCJ9)

**Version Streamlit** : décrite ci-dessous, déployable sur Streamlit Community Cloud.

Dashboard interactif Streamlit pour la Direction des Ressources Humaines. Il permet de suivre les effectifs, la masse salariale, l'absentéisme, la performance, l'engagement et le turnover, et il identifie les collaborateurs à risque de départ.

## Contenu

| Onglet | Ce qu'on y suit |
|---|---|
| 👥 Effectifs | Évolution par semestre, répartition par département, pyramide des âges, grades, contrats, ancienneté, villes, métiers |
| 💰 Masse salariale | Évolution, répartition par département, salaires par grade, positionnement salaire / référence du grade, écart salarial femmes / hommes |
| 🩺 Absentéisme | Taux d'absentéisme, part des absences non justifiées, détail par département et par mois |
| ⭐ Performance & engagement | Évolution des notes, croisement performance × engagement, « talents à risque » |
| 🚪 Turnover | Taux de départ à 6 mois par cohorte, département, engagement, salaire, métier et ancienneté |
| 🎯 Risque de départ | Score de risque au 31/12/2024, liste prioritaire d'entretiens avec les principaux facteurs, export CSV |
| 🪪 Fiche collaborateur | Profil individuel : niveau de risque, facteurs, comparaison à la moyenne du département, absences mois par mois |

Les filtres de la barre latérale (département, site, ville, contrat, grade) s'appliquent à tous les onglets.

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
