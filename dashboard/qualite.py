"""Audit de qualité des données : ce qui a été détecté dans les fichiers bruts et la règle appliquée."""
import numpy as np
import pandas as pd

from preparation import DATA, DATES, charger


def _brut():
    train = pd.read_csv(DATA / "telcopeople_train.csv").assign(jeu="Historique")
    test = pd.read_csv(DATA / "telcopeople_test.csv").assign(jeu="31/12/2024")
    df = pd.concat([train, test], ignore_index=True)
    for c in DATES:
        df[c + "_dt"] = pd.to_datetime(df[c], format="mixed", dayfirst=True, errors="coerce")
    df["salaire_num"] = pd.to_numeric(df["salaire_mensuel"].astype(str).str.replace("FCFA", "", regex=False)
                                      .str.replace(" ", "", regex=False), errors="coerce")
    return df


def anomalies():
    """Tableau des anomalies : description, règle appliquée, nombre de lignes par jeu."""
    b = _brut()
    ratio = b["salaire_num"] / b["reference_salaire_grade"]
    hors_echelle = lambda c: (b[c] < 1) | (b[c] > 5)
    regles = [
        ("Salaire nul ou négatif", (b["salaire_num"] <= 0), "Mis à « non renseigné »"),
        ("Salaire plus de 4 fois la référence du grade (zéro en trop)", ratio > 4, "Divisé par 10"),
        ("Salaire saisi en texte (« FCFA », espaces)", b["salaire_mensuel"].astype(str).str.contains(r"[^\d.]", regex=True),
         "Converti en nombre"),
        ("Note de performance hors de l'échelle 1-5",
         hors_echelle("performance_actuelle") | hors_echelle("performance_precedente"), "Mise à « non renseigné »"),
        ("Note d'engagement hors de l'échelle 1-5",
         hors_echelle("engagement_actuel") | hors_echelle("engagement_precedent"), "Mise à « non renseigné »"),
        ("Embauche postérieure à la date de référence", b["date_embauche_dt"] > b["date_reference_dt"],
         "Date mise à « non renseignée »"),
        ("Dernière absence postérieure à la date de référence (information du futur)",
         b["date_derniere_absence_dt"] > b["date_reference_dt"],
         "Date neutralisée ; récence recalculée depuis les absences mensuelles"),
        ("Dates au format mixte (jj/mm/aaaa et aaaa-mm-jj)",
         b["date_naissance"].astype(str).str.contains("/") | b["date_embauche"].astype(str).str.contains("/"),
         "Lecture des deux formats"),
    ]
    lignes = []
    for desc, masque, regle in regles:
        masque = masque.fillna(False)
        lignes.append({"Anomalie": desc, "Règle appliquée": regle,
                       "Historique": int(masque[b["jeu"] == "Historique"].sum()),
                       "31/12/2024": int(masque[b["jeu"] == "31/12/2024"].sum())})
    t = pd.DataFrame(lignes)
    t["Total"] = t["Historique"] + t["31/12/2024"]
    return t, len(b)


def libelles():
    """Variantes d'écriture harmonisées : exemples réels de corrections appliquées."""
    b = _brut()
    df, _ = charger()                       # même ordre de lignes que les fichiers bruts
    out = []
    for col in ["departement", "contrat", "niveau_etude", "ville_affectation", "genre"]:
        paires = pd.DataFrame({"brut": b[col].astype(object).where(b[col].notna(), "(vide)").astype(str),
                               "propre": df[col].astype(str)})
        corrigees = paires[paires["brut"] != paires["propre"]].drop_duplicates()
        exemples = ", ".join(f"« {r.brut} » → {r.propre}" for r in corrigees.head(4).itertuples())
        out.append({"Variable": col, "Variantes brutes": b[col].dropna().nunique(),
                    "Valeurs finales": df[col].nunique(),
                    "Lignes corrigées": int((paires["brut"] != paires["propre"]).sum()),
                    "Exemples de corrections": exemples or "aucune"})
    return pd.DataFrame(out)


def manquants():
    """Taux de valeurs manquantes après nettoyage, par variable utile."""
    df, _ = charger()
    cols = {"genre": "Genre", "departement": "Département", "niveau_etude": "Niveau d'études",
            "salaire_mensuel": "Salaire mensuel", "salaire_12m_avant": "Salaire il y a 12 mois",
            "reference_salaire_grade": "Référence salariale du grade",
            "performance_actuelle": "Performance actuelle", "performance_precedente": "Performance précédente",
            "engagement_actuel": "Engagement actuel", "engagement_precedent": "Engagement précédent",
            "date_derniere_promotion": "Date de dernière promotion", "date_embauche": "Date d'embauche"}
    lignes = []
    for c, lib in cols.items():
        s = df[c]
        manque = s.isna() | (s.astype(str) == "Non renseigné")
        act = manque[df["jeu"] == "actuel"]
        lignes.append({"Variable": lib, "Manquant (historique)": manque[df["jeu"] == "historique"].mean(),
                       "Manquant (31/12/2024)": act.mean(), "Nombre au 31/12/2024": int(act.sum())})
    t = pd.DataFrame(lignes)
    t.loc[t["Variable"] == "Date de dernière promotion", "Variable"] = "Date de dernière promotion (absente = jamais promu)"
    return t


def coherence():
    """Contrôles de cohérence : les sous-groupes recomposent-ils le total ?"""
    df, _ = charger()
    act = df[df["jeu"] == "actuel"]
    total = len(act)
    controles = []
    for col, lib in [("genre", "Genre"), ("departement", "Département"), ("contrat", "Contrat"), ("grade", "Grade")]:
        connus = (act[col] != "Non renseigné").sum()
        controles.append({"Contrôle": f"{lib} : somme des catégories = effectif total",
                          "Résultat": "OK" if act[col].value_counts().sum() == total else "Écart",
                          "Détail": f"{connus} renseignés + {total - connus} « Non renseigné » = {total}"})
    ids = df["id"].is_unique
    controles.append({"Contrôle": "Identifiants uniques", "Résultat": "OK" if ids else "Écart",
                      "Détail": f"{df['id'].nunique()} identifiants pour {len(df)} lignes"})
    j = [f"jours_abs_m{i}" for i in range(1, 7)]
    a = [f"abs_non_just_m{i}" for i in range(1, 7)]
    inc = (df[a].values > df[j].values).sum()
    controles.append({"Contrôle": "Jours non justifiés ≤ jours d'absence (chaque mois)",
                      "Résultat": "OK" if inc == 0 else "Écart", "Détail": f"{inc} incohérences"})
    tx = df[df["jeu"] == "historique"].groupby("date_reference")["target"].mean()
    controles.append({"Contrôle": "Stabilité du taux de départ entre cohortes",
                      "Résultat": "OK" if tx.max() - tx.min() < 0.03 else "À surveiller",
                      "Détail": f"de {tx.min() * 100:.1f} % à {tx.max() * 100:.1f} %".replace(".", ",")})
    cle = df["date_naissance"].astype(str) + "|" + df["date_embauche"].astype(str)
    controles.append({"Contrôle": "Suivi individuel d'une période à l'autre",
                      "Résultat": "Impossible",
                      "Détail": f"pas d'identifiant stable : {cle.nunique()} profils distincts pour {len(df)} lignes"})
    return pd.DataFrame(controles)
