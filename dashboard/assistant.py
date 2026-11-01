"""Moteur de questions libres de l'Assistant RH (sans IA externe).

Une question est décomposée en trois morceaux :
  - la MESURE (effectif, taux de départ, salaire moyen, absentéisme…) ;
  - les FILTRES (département, grade, période, genre, contrat, ville, tranche d'âge, cadres) ;
  - la RÉPARTITION éventuelle (« par grade », « par période », « quel département… »).
Le calcul est fait sur les données du dashboard : aucune donnée ne sort de l'application.
"""
import re
import unicodedata
from dataclasses import dataclass, field

import pandas as pd


def normaliser(texte):
    t = unicodedata.normalize("NFD", str(texte).lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t.replace("’", "'")).strip()


# ---------------------------------------------------------------------------
# Mesures : (identifiant, libellé, mots-clés, fonction, format, données de départ ?, page)
# L'ordre compte : la première mesure reconnue l'emporte.
# ---------------------------------------------------------------------------
@dataclass
class Mesure:
    cle: str
    libelle: str
    mots: list
    calcul: object
    format: str
    departs: bool = False         # calculée sur les cohortes historiques (départ à 6 mois connu)
    page: str = ""


MESURES = [
    Mesure("masse", "masse salariale mensuelle", ["masse salariale", "cout salarial", "cout total", "budget salarial",
                                                   "combien coute", "combien ca coute", "masse"],
           lambda d: d["salaire_mensuel"].sum(), "fcfa", page="salaires"),
    Mesure("nb_departs", "nombre de départs à 6 mois", ["nombre de departs", "combien de departs", "combien de personnes sont parties",
                                                        "combien sont partis", "combien ont quitte"],
           lambda d: d["target"].sum(), "n", departs=True, page="analyse-departs"),
    Mesure("taux_depart", "taux de départ à 6 mois", ["taux de depart", "turnover", "depart", "quitt", "partent", "parti",
                                                      "demission", "perd", "fuite", "rotation"],
           lambda d: d["target"].mean(), "pct", departs=True, page="analyse-departs"),
    Mesure("salaire_median", "salaire médian", ["salaire median", "mediane", "median"],
           lambda d: d["salaire_mensuel"].median(), "fcfa", page="salaires"),
    Mesure("salaire", "salaire moyen", ["salaire", "remuneration", "paye", "paie", "gagne", "payes"],
           lambda d: d["salaire_mensuel"].mean(), "fcfa", page="salaires"),
    Mesure("jours_abs", "jours d'absence moyens sur 6 mois", ["jours d'absence", "jours d absence", "nombre de jours"],
           lambda d: d["jours_abs_6m"].mean(), "dec", page="absenteisme"),
    Mesure("absenteisme", "taux d'absentéisme", ["absenteisme", "absence", "absent", "malad"],
           lambda d: d["taux_absenteisme"].mean(), "pct2", page="absenteisme"),
    Mesure("arrivees", "nombre d'arrivées (6 derniers mois)", ["arrivee", "arrive", "recrut", "embauch", "nouveaux", "entrees"],
           lambda d: d["arrivee"].sum(), "n", page="arrivees"),
    Mesure("part_femmes", "part de femmes", ["part de femmes", "% de femmes", "pourcentage de femmes", "proportion de femmes",
                                             "taux de feminisation", "feminisation", "parite"],
           lambda d: (d["genre"] == "F").mean(), "pct", page="diversite"),
    Mesure("performance", "note de performance moyenne", ["performance", "evaluation", "note"],
           lambda d: d["performance_actuelle"].mean(), "dec", page="performance"),
    Mesure("engagement", "engagement moyen", ["engagement", "motivation", "implication"],
           lambda d: d["engagement_actuel"].mean(), "dec", page="performance"),
    Mesure("age", "âge moyen", ["age moyen", "moyenne d'age", "quel age", "age"],
           lambda d: d["age"].mean(), "dec", page="demographie"),
    Mesure("anciennete", "ancienneté moyenne (ans)", ["anciennete moyenne", "anciennete"],
           lambda d: d["anciennete"].mean(), "dec", page="demographie"),
    Mesure("effectif", "effectif", ["effectif", "combien de collaborateurs", "combien de salaries", "combien d'employes",
                                    "combien de personnes", "nombre de collaborateurs", "nombre de salaries", "combien"],
           lambda d: len(d), "n", page="demographie"),
]

# Répartitions : libellé affiché, colonne, mots déclencheurs
REPARTITIONS = [
    ("département", "departement", ["departement", "service", "direction", "dep"]),
    ("grade", "grade", ["grade", "niveau hierarchique", "echelon"]),
    ("période", "periode", ["periode", "semestre", "annee", "temps", "evolution", "evolue", "tendance", "historique"]),
    ("genre", "genre", ["genre", "sexe"]),
    ("contrat", "contrat", ["contrat", "type de contrat"]),
    ("ville", "ville_affectation", ["ville", "site", "region", "localisation"]),
    ("tranche d'âge", "tranche_age", ["tranche d'age", "age", "ages"]),
    ("ancienneté", "tranche_anciennete", ["anciennete"]),
    ("génération", "generation", ["generation"]),
    ("niveau d'études", "niveau_etude", ["niveau d'etude", "diplome", "etudes"]),
    ("performance", "categorie_perf", ["performance", "evaluation"]),
]


@dataclass
class Requete:
    mesure: Mesure | None = None
    filtres: dict = field(default_factory=dict)       # colonne -> valeur (ou liste)
    libelles_filtres: list = field(default_factory=list)
    repartition: tuple | None = None                  # (libellé, colonne)
    sens: str = ""                                    # "max", "min" ou ""
    periode: str | None = None
    remarques: list = field(default_factory=list)


def analyser(question, df, periodes, periodes_hist):
    """Transforme la phrase en requête structurée (mesure, filtres, répartition)."""
    t = " " + normaliser(question) + " "
    r = Requete()

    # --- répartition : « par X », « dans quel(le) X », « quel(le) X a / est », « évolution »
    for lib, col, mots in REPARTITIONS:
        motif = "|".join(re.escape(m) for m in mots)
        if re.search(rf"\bpar (?:{motif})\b", t) or re.search(rf"\b(?:quel|quelle|quels|quelles)s? (?:{motif})\b", t) \
                or re.search(rf"\b(?:dans|selon|suivant) (?:quel|quelle|chaque|les) (?:{motif})", t):
            r.repartition = (lib, col)
            break
    if r.repartition is None and re.search(r"\b(evolu|tendance|au fil|depuis 2022|historique|dans le temps)", t):
        r.repartition = ("période", "periode")
    if r.repartition is None and re.search(r"\bou\b.*\b(le plus|le moins|plus eleve|plus faible|plus fort)", t):
        r.repartition = ("département", "departement")
    if re.search(r"\b(le moins|plus faible|plus bas|minimum|min|dernier|moins eleve)\b", t):
        r.sens = "min"
    elif re.search(r"\b(le plus|plus eleve|plus fort|plus haut|maximum|max|premier)\b", t):
        r.sens = "max"

    # --- mesure (on retire d'abord les morceaux qui décrivent la répartition, ex. « par ancienneté »)
    t_mesure = t
    if r.repartition:
        t_mesure = re.sub(r"\bpar \w+(?: d'\w+)?", " ", t_mesure)
    for m in MESURES:
        if any(re.search(rf"(?<![a-z]){re.escape(mot)}(?!ement)", t_mesure) for mot in m.mots):   # « départ » ≠ « département »
            r.mesure = m
            break

    # --- filtres
    m = re.search(r"\bdep(?:artement)?\s*0?(\d{1,2})\b", t)
    if m:
        dep = f"DEP{int(m.group(1)):02d}"
        if dep in set(df["departement"].astype(str)):
            r.filtres["departement"] = dep
            r.libelles_filtres.append(dep)
            if r.repartition and r.repartition[1] == "departement":
                r.repartition = None
    grades = sorted({f"G{g}" for g in re.findall(r"\bg\s?([1-5])\b", t)})
    if grades:
        r.filtres["grade"] = grades
        r.libelles_filtres.append(" et ".join(grades))
    elif re.search(r"\bcadres?\b", t):
        r.filtres["grade"] = ["G4", "G5"]
        r.libelles_filtres.append("cadres (G4-G5)")
    if re.search(r"\bcdi\b", t) and not re.search(r"\bcdd\b", t):
        r.filtres["contrat"] = "CDI"
        r.libelles_filtres.append("CDI")
    elif re.search(r"\bcdd\b", t) and not re.search(r"\bcdi\b", t):
        r.filtres["contrat"] = "CDD"
        r.libelles_filtres.append("CDD")
    if not (r.mesure and r.mesure.cle == "part_femmes"):
        if re.search(r"\bfemmes?\b", t) and not re.search(r"\bhommes?\b", t):
            r.filtres["genre"] = "F"
            r.libelles_filtres.append("femmes")
        elif re.search(r"\bhommes?\b", t) and not re.search(r"\bfemmes?\b", t):
            r.filtres["genre"] = "M"
            r.libelles_filtres.append("hommes")
    for v in sorted(df["ville_affectation"].dropna().astype(str).unique()):
        if v != "Non renseigné" and re.search(rf"\b{re.escape(normaliser(v))}\b", t):
            r.filtres["ville_affectation"] = v
            r.libelles_filtres.append(v)
            break
    if re.search(r"moins de 25|\bjeunes?\b|<\s?25", t):
        r.filtres["tranche_age"] = "<25"
        r.libelles_filtres.append("moins de 25 ans")
    elif re.search(r"plus de 50|50 ans et plus|\bseniors?\b|50\+", t):
        r.filtres["tranche_age"] = "50+"
        r.libelles_filtres.append("50 ans et plus")
    else:
        m = re.search(r"\b(\d{2})\s?-\s?(\d{2}) ans", t)
        if m and f"{m.group(1)}-{m.group(2)}" in set(df["tranche_age"].astype(str)):
            r.filtres["tranche_age"] = f"{m.group(1)}-{m.group(2)}"
            r.libelles_filtres.append(f"{m.group(1)}-{m.group(2)} ans")

    # --- période
    m1 = re.search(r"\b(20\d\d)\s?s\s?([12])\b", t)
    m2 = re.search(r"\b([12])(?:er|e|eme)? semestre (?:de )?(20\d\d)\b", t)
    if m1 or m2:
        an, sem = (m1.group(1), m1.group(2)) if m1 else (m2.group(2), m2.group(1))
        if f"{an} S{sem}" in periodes:
            r.periode = f"{an} S{sem}"
    else:
        m = re.search(r"\b(20\d\d)\b", t)
        if m:
            cand = [p for p in periodes if p.startswith(m.group(1))]
            if cand:
                r.periode = cand[-1]
                r.remarques.append(f"Pour l'année {m.group(1)}, j'ai pris la situation au {cand[-1]}.")
    return r


# ---------------------------------------------------------------------------
# Calcul
# ---------------------------------------------------------------------------
def _appliquer_filtres(d, filtres):
    for col, val in filtres.items():
        d = d[d[col].astype(str).isin(val)] if isinstance(val, list) else d[d[col].astype(str) == val]
    return d


def calculer(r, df, periodes, periodes_hist, ordres):
    """Renvoie un dict : valeur (ou série), effectifs, période utilisée, comparaison entreprise."""
    m = r.mesure
    base = df[df["jeu"] == "historique"] if m.departs else df
    per = r.periode
    if m.departs:
        if per and per not in periodes_hist:
            r.remarques.append(f"Les départs à 6 mois ne sont pas encore connus pour {per} : "
                               f"j'utilise la dernière cohorte connue ({periodes_hist[-1]}).")
            per = periodes_hist[-1]
        per = per or periodes_hist[-1]
    else:
        per = per or periodes[-1]
    rep = r.repartition
    d = _appliquer_filtres(base, r.filtres)
    if not rep or rep[1] != "periode":
        d = d[d["periode"] == per]
    res = {"periode": per, "n": len(d)}
    if rep:
        col = rep[1]
        g = d[d[col].notna()]
        g = g[g[col].astype(str) != "Non renseigné"]
        cles = g[col].astype(str)
        serie = pd.Series({k: m.calcul(v) for k, v in g.groupby(cles)}, dtype=float)
        tailles = cles.value_counts()
        if col in ordres:
            serie = serie.reindex([x for x in ordres[col] if x in serie.index])
            tailles = tailles.reindex(serie.index)
        res.update(serie=serie.dropna(), tailles=tailles)
    else:
        res["valeur"] = m.calcul(d) if len(d) else float("nan")
        ref = base[base["periode"] == per]
        if r.filtres:
            res["reference"] = m.calcul(ref)
    return res


EXEMPLES = [
    "Taux de départ des CDD par grade",
    "Salaire moyen des femmes à Bouaké",
    "Absentéisme par période dans le DEP04",
    "Combien d'arrivées en 2023 S1 ?",
    "Quelle ville a le salaire moyen le plus élevé ?",
    "Âge moyen des cadres par département",
]
