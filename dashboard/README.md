# Dashboard RH TelcoPeople

**Version Power BI (publiée) :** [ouvrir le rapport](https://app.powerbi.com/view?r=eyJrIjoiMGEyYzkyNjUtZjg0Yy00YmI5LThiYjktYmY4YjJiNTRjMGIzIiwidCI6IjFiMWY3NzkzLWU3NjUtNDhjYy04NmZmLTYzNGUwN2Q1NjhlNCJ9)

**Version Streamlit** : décrite ci-dessous, déployable sur Streamlit Community Cloud.

Dashboard interactif Streamlit pour la Direction des Ressources Humaines. Il permet de suivre les effectifs, la masse salariale, l'absentéisme, la performance, l'engagement et le turnover, et il identifie les collaborateurs à risque de départ.

## Contenu

Navigation en haut de page par domaine. L'accueil présente toutes les pages autour du cercle « cycle de vie du collaborateur ». Chaque page indique la **population couverte** (effectif, valeurs non renseignées, couverture des évaluations).

| Domaine | Pages |
|---|---|
| Pilotage | Vue d'ensemble RH |
| Effectifs | Analyse démographique · Diversité · Historique et tendances · Nouveaux arrivants · Profil département · Fiche collaborateur (DRH uniquement) |
| Rémunération | Analyse salariale · Équité salariale F / H |
| Absentéisme | Absentéisme · Absences par département |
| Performance | Évaluation de la performance |
| Turnover | Analyse des départs · Caractéristiques des départs observés · Anticipation des départs |
| Données | Qualité des données · Exports |

### Anticipation des départs

- Quatre niveaux relatifs : **Très élevé** (5 % des scores les plus hauts), **Élevé** (5 à 16 %), **Modéré** (16 à 50 %), **Faible** (moitié basse). Jamais de prédiction « partira / ne partira pas ».
- Pour chaque niveau, le **taux de départ réellement observé** en validation temporelle (modèle entraîné sur le passé, appliqué aux 3 dernières cohortes connues) : environ 30 %, 22 %, 12 % et 4 %.
- **Capacité d'accompagnement** : pour N collaborateurs accompagnés, départs historiquement attendus dans le groupe, part des départs couverte, personnes accompagnées qui ne seraient probablement pas parties.
- **Explication individuelle** (fiche collaborateur) : ce qui augmente le score, ce qui le nuance, avec la valeur du collaborateur face à une référence explicite, et ce qu'il faut vérifier humainement.
- Le **genre** et la source SIRH sont exclus du modèle du dashboard (aucune perte de performance : AUC 0,718 contre 0,719).
- Le score ne peut fonder aucune décision défavorable (sanction, rémunération, promotion, formation).

### Définitions

- *Taux d'absentéisme* = jours d'absence sur 6 mois ÷ 130 jours ouvrés.
- *Taux de départ* = part des collaborateurs partis dans les 6 mois suivant la date de référence. Il n'est connu que pour les photographies historiques (juin 2022 à juin 2024).
- *Arrivée* = embauche dans les 6 mois précédant la date de référence.
- Une valeur **non renseignée** n'est jamais comptée comme une valeur faible.

## Connexion et rôles

L'application demande une connexion. Deux profils de démonstration :

| Profil | Accès |
|---|---|
| **DRH** | Toutes les pages, y compris la fiche collaborateur, la liste nominative d'anticipation et les exports nominatifs |
| **Direction générale** | Indicateurs agrégés uniquement : pas de fiche collaborateur, pas de liste nominative, exports agrégés |

Les restrictions sont appliquées côté serveur : une page réservée n'existe pas dans la navigation du profil Direction, même en tapant son adresse. La session expire après 2 heures, et 5 tentatives échouées bloquent la connexion pendant 60 secondes.

### Configurer les comptes (secrets)

Les mots de passe ne sont jamais stockés dans le dépôt. Seule une empreinte (PBKDF2-SHA256 salé) est placée dans les **secrets** Streamlit.

1. Générer l'empreinte d'un mot de passe : `python dashboard/auth.py "mot de passe choisi"`
2. Sur Streamlit Cloud : application → **Settings** → **Secrets**, coller :

```toml
[comptes.drh]
role = "drh"
nom = "Direction des Ressources Humaines"
sel = "…"
empreinte = "…"

[comptes.direction]
role = "direction"
nom = "Direction générale"
sel = "…"
empreinte = "…"
```

3. En local : mettre le même contenu dans `.streamlit/secrets.toml` (exclu du dépôt par `.gitignore`).

### Dépôt privé

La connexion ne protège les données que si le dépôt GitHub est **privé** : sinon les fichiers CSV restent téléchargeables directement sur GitHub. GitHub → dépôt → **Settings** → **General** → **Danger Zone** → **Change visibility** → **Private**. Streamlit Community Cloud continue de déployer depuis un dépôt privé.

## Fichiers

```
dashboard/
├── app.py             # interface : navigation, pages, rôles
├── preparation.py     # nettoyage, variables et modèle (identiques au notebook de modélisation)
├── anticipation.py    # niveaux de risque, validation temporelle, capacité, explications
├── qualite.py         # audit de qualité des données
├── auth.py            # connexion, rôles, génération des empreintes
├── exports.py         # classeur Excel et synthèse PDF
├── requirements.txt   # dépendances
└── README.md
.streamlit/config.toml # thème
data/raw/              # telcopeople_train.csv, telcopeople_test.csv
```

Le modèle est réentraîné au démarrage (quelques secondes, mis en cache ensuite) : aucun fichier de modèle n'est nécessaire.

## Lancer en local

Depuis la racine du dépôt, après avoir créé `.streamlit/secrets.toml` :

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

## Déployer sur Streamlit Community Cloud

1. Sur https://share.streamlit.io : **Create app** → dépôt, branche `main`, fichier `dashboard/app.py`.
2. Avant ou juste après le déploiement : **Settings** → **Secrets** → coller les comptes (voir ci-dessus).
3. Les mises à jour poussées sur `main` sont redéployées automatiquement.
