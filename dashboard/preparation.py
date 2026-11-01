"""Chargement, nettoyage et modèle de risque pour le dashboard RH TelcomCI.

Reprend exactement le nettoyage et les variables du notebook 12_modele_final_v2.ipynb.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"

J = [f"jours_abs_m{i}" for i in range(1, 7)]
N = [f"nb_abs_m{i}" for i in range(1, 7)]
A = [f"abs_non_just_m{i}" for i in range(1, 7)]
JOURS_OUVRES_6M = 130          # environ 21,7 jours ouvrés par mois
TAUX_SIGNALEMENT = 0.16        # taux retenu pour la soumission finale

DATES = ["date_reference", "date_naissance", "date_embauche",
         "date_derniere_promotion", "date_derniere_absence"]


def nettoyer(df):
    df = df.copy()
    for c in DATES:
        df[c] = pd.to_datetime(df[c], format="mixed", dayfirst=True, errors="coerce")
    df["salaire_mensuel"] = pd.to_numeric(
        df["salaire_mensuel"].astype(str).str.replace("FCFA", "", regex=False).str.replace(" ", "", regex=False),
        errors="coerce")
    df["ville_affectation"] = df["ville_affectation"].fillna("INCONNU").str.strip().str.title()
    df["departement"] = df["departement"].fillna("INCONNU").str.strip().str.upper().str.replace("DEPT", "DEP", regex=False)
    df["contrat"] = df["contrat"].fillna("INCONNU").str.strip().str.upper().str.replace(".", "", regex=False)
    df["niveau_etude"] = (df["niveau_etude"].fillna("INCONNU").str.strip().str.upper()
                          .str.replace(" ", "", regex=False).str.replace("BAC2", "BAC+2", regex=False)
                          .replace({"BAC+2": "Bac+2", "BAC+3": "Bac+3", "BAC+5": "Bac+5", "DOCTORAT": "Doctorat"}))
    for c in ["genre", "grade", "code_site", "source_sirh"]:
        df[c] = df[c].fillna("INCONNU").astype(str).str.strip().str.upper()
    df["poste"] = df["poste"].fillna("INCONNU").astype(str).str.strip()     # intitulés déjà corrects : conservés

    df.loc[df["salaire_mensuel"] <= 0, "salaire_mensuel"] = np.nan
    ratio = df["salaire_mensuel"] / df["reference_salaire_grade"]
    df.loc[ratio > 4, "salaire_mensuel"] = df.loc[ratio > 4, "salaire_mensuel"] / 10
    for c in ["performance_actuelle", "performance_precedente", "engagement_actuel", "engagement_precedent"]:
        df.loc[(df[c] < 1) | (df[c] > 5), c] = np.nan
    df.loc[df["date_embauche"] > df["date_reference"], "date_embauche"] = pd.NaT
    df.loc[df["date_derniere_absence"] > df["date_reference"], "date_derniere_absence"] = pd.NaT
    return df


def creer_variables(df):
    df = df.copy()
    ref = df["date_reference"]
    df["age"] = (ref - df["date_naissance"]).dt.days / 365.25
    df["anciennete"] = (ref - df["date_embauche"]).dt.days / 365.25
    df["age_embauche"] = df["age"] - df["anciennete"]
    df["annees_depuis_promotion"] = (ref - df["date_derniere_promotion"]).dt.days / 365.25
    df["jamais_promu"] = df["date_derniere_promotion"].isna().astype(int)
    df["ratio_salaire_reference"] = df["salaire_mensuel"] / df["reference_salaire_grade"]
    df["taux_evolution_salaire"] = df["salaire_mensuel"] / df["salaire_12m_avant"] - 1
    df["engagement_moyen"] = df[["engagement_actuel", "engagement_precedent"]].mean(axis=1)
    df["performance_moyenne"] = df[["performance_actuelle", "performance_precedente"]].mean(axis=1)
    df["evolution_engagement"] = df["engagement_actuel"] - df["engagement_precedent"]
    df["evolution_performance"] = df["performance_actuelle"] - df["performance_precedente"]
    df["ecart_perf_engagement"] = df["performance_actuelle"] - df["engagement_actuel"]
    df["engagement_manquant"] = df["engagement_actuel"].isna().astype(int)
    df["performance_manquante"] = df["performance_actuelle"].isna().astype(int)
    df["jours_abs_6m"] = df[J].sum(axis=1)
    df["nb_abs_6m"] = df[N].sum(axis=1)
    df["abs_non_just_6m"] = df[A].sum(axis=1)
    df["jours_abs_3m"] = df[J[:3]].sum(axis=1)
    df["tendance_absence"] = df["jours_abs_3m"] - df[J[3:]].sum(axis=1)
    df["mois_avec_absence"] = (df[J] > 0).sum(axis=1)
    presence = df[J].values > 0
    df["mois_depuis_derniere_abs"] = np.where(presence.any(axis=1), presence.argmax(axis=1), 6)
    # Interactions (logistique)
    e = df["engagement_moyen"].fillna(3.5)
    r = df["ratio_salaire_reference"].fillna(1).clip(0.5, 1.6)
    df["eng_x_ratio"] = e * r
    df["ratio_carre"] = (r - 1) ** 2
    df["eng_carre"] = (e - 3.5) ** 2
    df["ratio_sous_90pct"] = (r < 0.9).astype(int)
    df["eng_sous_3"] = (e < 3).astype(int)
    df["log_jours_abs"] = np.log1p(df["jours_abs_6m"])
    df["log_abs_non_just"] = np.log1p(df["abs_non_just_6m"])
    return df


INTERACTIONS = ["eng_x_ratio", "ratio_carre", "eng_carre", "ratio_sous_90pct", "eng_sous_3",
                "log_jours_abs", "log_abs_non_just"]
A_RETIRER = ["target", "id", "jeu"] + DATES


def charger():
    """Renvoie (données nettoyées train + test empilées, liste des variables du modèle)."""
    train = pd.read_csv(DATA / "telcopeople_train.csv").assign(jeu="historique")
    test = pd.read_csv(DATA / "telcopeople_test.csv").assign(jeu="actuel")
    df = creer_variables(nettoyer(pd.concat([train, test], ignore_index=True)))
    df["taux_absenteisme"] = df["jours_abs_6m"] / JOURS_OUVRES_6M
    df["tranche_age"] = pd.cut(df["age"], [0, 25, 30, 35, 40, 45, 50, 70],
                               labels=["<25", "25-29", "30-34", "35-39", "40-44", "45-49", "50+"], right=False)
    df["tranche_anciennete"] = pd.cut(df["anciennete"], [0, 1, 2, 3, 5, 20],
                                      labels=["<1 an", "1-2 ans", "2-3 ans", "3-5 ans", "5 ans +"], right=False)
    # Affichage : une catégorie manquante s'appelle « Non renseigné » (simple libellé, sans effet sur le modèle)
    for c in ["genre", "departement", "contrat", "niveau_etude", "ville_affectation", "poste", "grade",
              "code_site", "source_sirh"]:
        df[c] = df[c].replace({"INCONNU": "Non renseigné", "Inconnu": "Non renseigné"})
    feats = [c for c in df.columns if c not in A_RETIRER + ["taux_absenteisme", "tranche_age", "tranche_anciennete"]]
    return df, feats


LIBELLES = {
    "ratio_salaire_reference": "Salaire bas par rapport au grade",
    "engagement_moyen": "Engagement faible",
    "engagement_actuel": "Engagement actuel faible",
    "eng_x_ratio": "Cumul engagement faible et salaire bas",
    "eng_sous_3": "Engagement inférieur à 3",
    "ratio_sous_90pct": "Salaire sous 90 % de la référence",
    "ecart_perf_engagement": "Performant mais désengagé",
    "annees_depuis_promotion": "Longtemps sans promotion",
    "jours_abs_6m": "Absences élevées",
    "log_jours_abs": "Absences élevées",
    "abs_non_just_6m": "Absences non justifiées",
    "log_abs_non_just": "Absences non justifiées",
    "jours_abs_3m": "Absences récentes",
    "taux_evolution_salaire": "Évolution salariale",
    "contrat": "Type de contrat",
    "code_site": "Site d'affectation",
    "departement": "Département",
    "poste": "Métier",
    "grade": "Grade",
    "genre": "Genre",
    "ville_affectation": "Ville",
    "niveau_etude": "Niveau d'études",
    "source_sirh": "Source SIRH",
    "nb_abs_6m": "Absences fréquentes",
    "mois_avec_absence": "Absences répétées",
    "tendance_absence": "Absences en hausse",
    "mois_depuis_derniere_abs": "Absence récente",
    "eng_carre": "Engagement atypique",
    "ratio_carre": "Salaire atypique pour le grade",
    "evolution_engagement": "Engagement en baisse",
    "performance_actuelle": "Performance",
    "jamais_promu": "Jamais promu",
    "anciennete": "Ancienneté",
    "age": "Âge",
}


def entrainer_modele(df, feats):
    """Régression logistique avec interactions, entraînée sur l'historique (C = 0,01)."""
    hist = df[df["jeu"] == "historique"]
    cats = [c for c in feats if not pd.api.types.is_numeric_dtype(df[c])]
    nums = [c for c in feats if c not in cats]
    pre = ColumnTransformer([
        ("num", Pipeline([("imputation", SimpleImputer(strategy="median", add_indicator=True)),
                          ("standardisation", StandardScaler())]), nums),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=15), cats),
    ])
    modele = make_pipeline(pre, LogisticRegression(C=0.01, max_iter=5000))
    modele.fit(hist[feats], hist["target"].astype(int))
    return modele


def facteurs_individuels(modele, X, n=3):
    """Pour chaque salarié, les n facteurs RH explicites qui augmentent le plus son risque.

    Contributions au log-odds de la logistique, regroupées par libellé métier. Seules les variables
    présentes dans LIBELLES sont affichées ; le score, lui, utilise toutes les variables.
    """
    pre, lr = modele[0], modele[-1]
    Z = pre.transform(X)
    Z = Z.toarray() if hasattr(Z, "toarray") else Z
    contrib = Z * lr.coef_[0]
    noms = pre.get_feature_names_out()
    racines = []
    for nom in noms:
        nom = nom.split("__", 1)[1]
        if nom.startswith("missingindicator_"):
            racines.append(None)        # donnée manquante : pas un facteur RH à présenter
            continue
        if nom.startswith(("jours_abs_m", "nb_abs_m")):
            nom = "jours_abs_3m"
        elif nom.startswith("abs_non_just_m"):
            nom = "abs_non_just_6m"
        base = next((v for v in ["departement", "code_site", "contrat", "poste", "grade", "genre",
                                 "ville_affectation", "niveau_etude", "source_sirh"] if nom.startswith(v + "_")), nom)
        racines.append(LIBELLES.get(base))   # variables techniques (taille du département, etc.) : non affichées
    garder = [i for i, r in enumerate(racines) if r is not None]
    contrib_df = (pd.DataFrame(contrib[:, garder], columns=[racines[i] for i in garder])
                  .T.groupby(level=0).sum().T)
    resultat = []
    for _, ligne in contrib_df.iterrows():
        top = ligne[ligne > 0].sort_values(ascending=False).head(n)
        resultat.append(" · ".join(top.index))
    return resultat
