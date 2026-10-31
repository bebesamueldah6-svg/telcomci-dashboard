"""Module d'anticipation des départs : niveaux de risque, taux observés, capacité et explications.

Principes (cadrage DRH) :
- jamais de classification « partira / ne partira pas » : quatre niveaux relatifs ;
- chaque niveau est accompagné du taux de départ RÉELLEMENT observé en validation temporelle
  (modèle entraîné sur le passé, appliqué à la période suivante), pas d'une formule codée en dur ;
- les explications distinguent les signaux qui augmentent le score et ceux qui le nuancent,
  avec la valeur du collaborateur et une référence explicite ;
- le genre et la source SIRH sont exclus du modèle du dashboard : ils ne doivent pas peser
  sur un signal individuel présenté à la DRH.
"""
import numpy as np
import pandas as pd

from preparation import entrainer_modele

EXCLUES = ["genre", "source_sirh"]
NIVEAUX = [("Très élevé", 0.05), ("Élevé", 0.16), ("Modéré", 0.50), ("Faible", 1.00)]
ORDRE_NIVEAUX = [n for n, _ in NIVEAUX]
N_PERIODES_VALIDATION = 3


def variables_modele(feats):
    return [f for f in feats if f not in EXCLUES]


def niveau_depuis_rang(rang_haut):
    """rang_haut : position relative depuis le haut (0 = score le plus élevé, 1 = le plus faible)."""
    for nom, seuil in NIVEAUX:
        if rang_haut <= seuil:
            return nom
    return NIVEAUX[-1][0]


def rang_depuis_le_haut(scores):
    s = pd.Series(scores)
    return ((s.rank(ascending=False, method="first") - 1) / len(s)).values


# ---------------------------------------------------------------------------
# Validation temporelle
# ---------------------------------------------------------------------------
def validation_temporelle(df, feats):
    """Entraîne sur les dates passées, score la date suivante, pour les 3 dernières cohortes connues.

    Renvoie un DataFrame (une ligne par collaborateur validé) : date, probabilité, rang, niveau, départ réel.
    """
    hist = df[df["jeu"] == "historique"]
    dates = sorted(hist["date_reference"].unique())
    lignes = []
    for d in dates[-N_PERIODES_VALIDATION:]:
        passe = hist[hist["date_reference"] < d]
        val = hist[hist["date_reference"] == d]
        modele = entrainer_modele(passe.assign(jeu="historique"), feats)
        p = modele.predict_proba(val[feats])[:, 1]
        r = rang_depuis_le_haut(p)
        lignes.append(pd.DataFrame({"date": d, "probabilite": p, "rang": r,
                                    "niveau": [niveau_depuis_rang(x) for x in r],
                                    "depart": val["target"].astype(int).values}))
    return pd.concat(lignes, ignore_index=True)


def taux_par_niveau(val):
    """Taux de départ observé par niveau, toutes périodes de validation confondues."""
    t = val.groupby("niveau")["depart"].agg(effectif="size", departs="sum").reindex(ORDRE_NIVEAUX)
    t["taux"] = t["departs"] / t["effectif"]
    t["part_des_departs"] = t["departs"] / t["departs"].sum()
    par_periode = val.groupby(["date", "niveau"])["depart"].mean().unstack().reindex(columns=ORDRE_NIVEAUX)
    t["taux_min"] = par_periode.min()
    t["taux_max"] = par_periode.max()
    return t


def courbe_capacite(val):
    """Pour chaque part de l'effectif accompagnée (les scores les plus élevés), précision et couverture moyennes.

    precision = part des personnes accompagnées qui sont effectivement parties ;
    couverture = part de tous les départs qui se trouvaient dans le groupe accompagné.
    """
    parts = np.round(np.arange(0.01, 1.001, 0.01), 2)
    res = []
    for d, g in val.groupby("date"):
        g = g.sort_values("probabilite", ascending=False)
        cum = g["depart"].cumsum().values
        n, total = len(g), g["depart"].sum()
        for s in parts:
            k = max(1, int(round(s * n)))
            res.append((d, s, cum[k - 1] / k, cum[k - 1] / total))
    r = pd.DataFrame(res, columns=["date", "part", "precision", "couverture"])
    return r.groupby("part")[["precision", "couverture"]].agg(["mean", "min", "max"])


def auc_validation(val):
    from sklearn.metrics import roc_auc_score
    return float(np.mean([roc_auc_score(g["depart"], g["probabilite"]) for _, g in val.groupby("date")]))


# ---------------------------------------------------------------------------
# Explications individuelles
# ---------------------------------------------------------------------------
FAMILLES = {
    "remuneration": "Positionnement salarial dans le grade",
    "evolution_salaire": "Évolution du salaire sur 12 mois",
    "engagement": "Engagement",
    "performance": "Performance",
    "absences": "Absences des 6 derniers mois",
    "carriere": "Ancienneté et promotion",
    "contexte": "Contexte d'emploi (poste, site, contrat, département)",
}


def famille(nom):
    """Rattache une variable transformée du modèle à une famille explicable (ou None)."""
    n = nom.split("__", 1)[1]
    if n.startswith("missingindicator_"):
        return "donnees"
    if n in ("ratio_salaire_reference", "ratio_carre", "ratio_sous_90pct", "salaire_mensuel",
             "reference_salaire_grade", "salaire_12m_avant"):
        return "remuneration"
    if n == "taux_evolution_salaire":
        return "evolution_salaire"
    if n.startswith(("engagement", "eng_carre", "eng_sous_3", "evolution_engagement")):
        return "engagement"
    if n.startswith(("performance", "evolution_performance", "ecart_perf_engagement")):
        return "performance"
    if n.startswith(("jours_abs", "nb_abs", "abs_non_just", "log_", "tendance_absence", "mois_avec_absence",
                     "mois_depuis_derniere_abs")):
        return "absences"
    if n in ("anciennete", "annees_depuis_promotion", "jamais_promu", "age", "age_embauche"):
        return "carriere"
    if n == "eng_x_ratio":
        return "interaction"
    return "contexte"


def contributions(modele, X, reference):
    """Contributions par famille au log-odds, centrées sur le collaborateur moyen de `reference`.

    Une contribution positive signifie « ce trait rapproche le score du haut de la distribution »
    par rapport à un collaborateur moyen ; ce n'est pas une cause.
    """
    pre, lr = modele[0], modele[-1]

    def brut(df):
        Z = pre.transform(df)
        Z = Z.toarray() if hasattr(Z, "toarray") else Z
        return Z * lr.coef_[0]

    c = brut(X) - brut(reference).mean(axis=0)
    noms = pre.get_feature_names_out()
    fam = [famille(n) for n in noms]
    out = pd.DataFrame(0.0, index=range(len(X)), columns=list(FAMILLES) + ["donnees"])
    for j, f in enumerate(fam):
        if f == "interaction":              # engagement × rémunération : réparti à parts égales
            out["engagement"] += c[:, j] / 2
            out["remuneration"] += c[:, j] / 2
        else:
            out[f] += c[:, j]
    return out


def _fmt(x, d=2, suffixe=""):
    return "non renseigné" if pd.isna(x) else f"{x:,.{d}f}{suffixe}".replace(",", " ").replace(".", ",")


def valeur_et_reference(fam, ligne, ref):
    """Texte « valeur du collaborateur » et « référence » pour une famille."""
    meme_dep = ref[ref["departement"] == ligne["departement"]]
    if fam == "remuneration":
        meme_grade = ref[ref["grade"] == ligne["grade"]]
        return (f"{_fmt(ligne['ratio_salaire_reference'])} × la référence du grade",
                f"médiane du grade {ligne['grade']} : {_fmt(meme_grade['ratio_salaire_reference'].median())}")
    if fam == "evolution_salaire":
        v = ligne["taux_evolution_salaire"]
        return ("non renseignée" if pd.isna(v) else _fmt(v * 100, 1, " %"),
                f"médiane de l'entreprise : {_fmt(ref['taux_evolution_salaire'].median() * 100, 1, ' %')}")
    if fam == "engagement":
        return (f"{_fmt(ligne['engagement_actuel'])} / 5",
                f"médiane du département : {_fmt(meme_dep['engagement_actuel'].median())}")
    if fam == "performance":
        return (f"{_fmt(ligne['performance_actuelle'])} / 5",
                f"médiane du département : {_fmt(meme_dep['performance_actuelle'].median())}")
    if fam == "absences":
        return (f"{_fmt(ligne['jours_abs_6m'], 0)} jours (dont {_fmt(ligne['abs_non_just_6m'], 0)} non justifiés)",
                f"moyenne du département : {_fmt(meme_dep['jours_abs_6m'].mean(), 1)} jours")
    if fam == "carriere":
        promo = "jamais promu" if ligne["jamais_promu"] else f"promu il y a {_fmt(ligne['annees_depuis_promotion'], 1)} ans"
        return (f"{_fmt(ligne['anciennete'], 1)} ans d'ancienneté, {promo}",
                f"ancienneté médiane : {_fmt(ref['anciennete'].median(), 1)} ans")
    if fam == "contexte":
        return (f"{ligne['poste']} · {ligne['contrat']} · site {ligne['code_site']} · {ligne['departement']}",
                "comparé à l'ensemble des postes, contrats, sites et départements")
    return ("", "")


def intensite(c):
    a = abs(c)
    return "forte" if a >= 0.30 else "modérée" if a >= 0.12 else "faible"


def explication(contrib_ligne, ligne, ref, n_signaux=4, n_nuances=2, seuil=0.04):
    """Liste des signaux (augmentent le score) et des nuances (le diminuent), avec valeur et référence."""
    c = contrib_ligne.drop("donnees")
    signaux, nuances = [], []
    for fam, v in c.sort_values(ascending=False).items():
        if v > seuil and len(signaux) < n_signaux:
            val, refe = valeur_et_reference(fam, ligne, ref)
            signaux.append({"famille": FAMILLES[fam], "contribution": v, "intensite": intensite(v),
                            "valeur": val, "reference": refe})
    for fam, v in c.sort_values().items():
        if v < -seuil and len(nuances) < n_nuances:
            val, refe = valeur_et_reference(fam, ligne, ref)
            nuances.append({"famille": FAMILLES[fam], "contribution": v, "intensite": intensite(v),
                            "valeur": val, "reference": refe})
    manquants = [lib for col, lib in [("engagement_actuel", "engagement"), ("performance_actuelle", "performance"),
                                      ("salaire_12m_avant", "salaire d'il y a 12 mois"),
                                      ("date_embauche", "date d'embauche")] if pd.isna(ligne[col])]
    return signaux, nuances, manquants
