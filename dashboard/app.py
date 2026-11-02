"""TelcomCI · HR Analytics — dashboard RH sur le modèle « cycle de vie du collaborateur ».

Une page d'accueil et quinze pages thématiques, appliquées aux données TelcomCI.
Lancement local :  streamlit run dashboard/app.py
"""
import base64
import re
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import assistant as moteur
import auth
import exports
import rapport
import qualite
from anticipation import (FAMILLES, ORDRE_NIVEAUX, auc_validation, contributions, courbe_capacite, explication,
                          niveau_depuis_rang, rang_depuis_le_haut, taux_par_niveau, validation_temporelle,
                          variables_modele)
from preparation import JOURS_OUVRES_6M, charger, creer_variables, entrainer_modele

st.set_page_config(page_title="TelcomCI · HR Analytics", page_icon=":material/insights:", layout="wide",
                   initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# Charte graphique : inspirée d'Orange (noir, blanc, orange en accent)
# Les noms historiques (JAUNE…) sont conservés : JAUNE est désormais l'orange de marque.
# ---------------------------------------------------------------------------
ORANGE, NOIR = "#FF7900", "#000000"
JAUNE, JAUNE_CLAIR, GRIS, GRIS_FONCE, GRIS_CLAIR = ORANGE, "#FFC08A", "#9E9E9E", "#333333", "#E0E0E0"
PALETTE = [JAUNE, GRIS, GRIS_FONCE, JAUNE_CLAIR, GRIS_CLAIR]
COULEURS_GENRE = {"F": JAUNE, "M": GRIS, "Non renseigné": GRIS_CLAIR}
COULEURS_NIVEAU = {"Très élevé": "#CD3C14", "Élevé": JAUNE, "Modéré": JAUNE_CLAIR, "Faible": GRIS_CLAIR}
px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = PALETTE

st.markdown(f"""
<style>
  .block-container {{padding-top: 3.2rem; padding-bottom: 2rem;}}
  .titre-page {{font-size: 2rem; font-weight: 800; color: {NOIR}; margin: 0; letter-spacing: -.02em;
               display: inline-block; padding-bottom: 2px;}}
  .titre-page span {{color: {ORANGE}; font-weight: 800; margin-right: .45rem;}}
  .ico {{font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; line-height: 1;
        letter-spacing: normal; text-transform: none; white-space: nowrap; direction: ltr;
        -webkit-font-feature-settings: 'liga'; font-feature-settings: 'liga'; -webkit-font-smoothing: antialiased;}}
  .tuile {{background: #fff; border: 1px solid #E6E6E6; border-radius: 12px; padding: 14px 16px;
          height: 100%; min-height: 96px; position: relative; display: flex; align-items: center; gap: clamp(8px, .9vw, 14px);}}
  .tuile .t-ico {{flex: 0 0 auto; width: clamp(28px, 2.7vw, 48px); height: clamp(28px, 2.7vw, 48px); color: #2B2B2B;
          transition: color .18s ease;}}
  .tuile .t-ico:empty {{display: none;}}
  .tuile .t-ico .ico-svg, .tuile .t-ico .ico-svg svg {{display: block; width: 100%; height: 100%;}}
  .tuile .t-corps {{min-width: 0; flex: 1;}}
  .tuile:hover .t-ico {{color: {ORANGE};}}
  .ico-svg {{display: inline-block; width: 1em; height: 1em; vertical-align: -0.15em;}}
  .ico-svg svg {{width: 100%; height: 100%;}}
  .indic {{display: flex; gap: 0; background: #fff; border: 1px solid #E6E6E6; border-radius: 12px; padding: 18px 8px;
          margin: 8px 0 12px 0; flex-wrap: wrap;}}
  .indic-groupe {{flex: 1 1 0; min-width: 220px; padding: 0 10px;}}
  .indic-groupe + .indic-groupe {{border-left: 1px solid #E6E6E6;}}
  .indic-titre {{text-align: center; font-weight: 700; color: #1A1A1A; margin-bottom: 10px;}}
  .indic-ligne {{display: flex; flex-wrap: wrap; justify-content: space-around; gap: 14px 8px;}}
  .indic[style] .indic-item {{flex: 0 0 calc(100% / var(--par-ligne) - 12px);}}
  .indic-item {{flex: 1 1 120px; text-align: center; padding: 6px 4px; border-radius: 10px; transition: background .18s;}}
  .indic-item:hover {{background: #FFF6EE;}}
  .indic-ico {{width: 58px; height: 58px; margin: 0 auto 8px auto; color: #4A4A4A; transition: color .18s;}}
  .indic-item:hover .indic-ico {{color: {ORANGE};}}
  .indic-ico .ico-svg, .indic-ico .ico-svg svg {{display: block; width: 100%; height: 100%;}}
  .indic-val {{font-weight: 800; color: #1A1A1A; font-size: 1.05rem; line-height: 1.2;}}
  .indic-lib {{color: #F16E00; font-size: .85rem; margin-top: 2px;}}
  .indic-note {{color: #8C8C8C; font-size: .75rem; margin-top: 2px;}}
  .fiche-liste {{display: grid; grid-template-columns: max-content 18px 1fr; gap: 14px 6px; background: #fff;
          border: 1px solid #E6E6E6; border-radius: 12px; padding: 20px 24px; margin: 8px 0;}}
  .fl-lib {{color: #595959;}} .fl-sep {{color: #8C8C8C;}} .fl-val {{font-weight: 700; color: #1A1A1A;}}
  .pastille-note {{width: fit-content; margin: 8px auto 4px auto; padding: 6px 18px; border-radius: 999px;
          background: #FFF1E5; border: 1px solid #FFD0A6; color: #333;}}
  .st-key-parcours {{background:#000; border-radius:14px; padding:16px 20px 12px 20px; margin:6px 0 10px 0;}}
  .pc-haut {{display:flex; justify-content:space-between; align-items:center;}}
  .pc-nom {{color:#FF7900; font-weight:800; font-size:.8rem; letter-spacing:.06em; text-transform:uppercase;}}
  .pc-pas {{color:#BDBDBD; font-size:.8rem;}}
  .pc-puces {{display:flex; gap:6px; flex-wrap:wrap; margin:10px 0 8px 0;}}
  .pc-puce {{border:1px solid #444; color:#9E9E9E; border-radius:999px; padding:2px 10px; font-size:.76rem;}}
  .pc-puce.fait {{border-color:#FF7900; color:#FF7900;}}
  .pc-puce.on {{background:#FF7900; border-color:#FF7900; color:#000; font-weight:700;}}
  .pc-titre {{color:#fff; font-weight:800; font-size:1.1rem;}}
  .pc-texte {{color:#E0E0E0; font-size:.95rem; line-height:1.5; margin-top:2px;}}
  .pc-texte b {{color:#fff;}}
  .st-key-parcours-boutons button[kind="tertiary"] p {{color:#BDBDBD;}}
  .st-key-parcours-boutons button[kind="secondary"] {{background:transparent; border-color:#555;}}
  .st-key-parcours-boutons button[kind="secondary"] p {{color:#fff;}}
  div[class*="st-key-pont-"] {{background:#FFF4EB; border:1px solid #FFD9B8; border-radius:12px; padding:10px 14px;
       margin-top:14px;}}
  .pont {{display:flex; gap:12px; align-items:center; color:#333; font-size:.92rem; line-height:1.45;}}
  .pont .t-svg, .pont svg {{width:26px; height:26px; flex-shrink:0; color:#F16E00;}}
  div[class*="st-key-vers-"] a {{padding:0;}}
  div[class*="st-key-vers-"] a p {{color:#F16E00 !important; font-weight:700; font-size:.85rem;}}
  .pc-lecture {{background:#000; color:#E0E0E0; border-radius:12px; padding:12px 16px; margin-top:12px;
       font-size:.95rem; line-height:1.5;}}
  .pc-lecture b {{color:#FF7900;}}
  .reco-prio {{text-align: center; font-weight: 800; border-radius: 999px; padding: 6px 4px; font-size: .85rem;}}
  .reco-constat {{font-weight: 800; color: #000; font-size: 1.02rem;}}
  .reco-action {{color: #333; margin: 4px 0 2px 0;}}
  .tableau-titre {{font-weight: 800; font-size: 1rem; color: #000; padding-bottom: 4px; margin-bottom: 6px;
          border-bottom: 2px solid {ORANGE}; display: inline-block;}}
  [data-testid="stTable"] table {{border-collapse: separate; border-spacing: 0; border: 1px solid #E6D9C4;
          border-radius: 10px; overflow: hidden; width: 100%;}}
  [data-testid="stTable"] th {{background: {ORANGE} !important; color: #000 !important; font-weight: 800 !important;
          border: none !important;}}
  [data-testid="stTable"] td {{border: none !important; border-bottom: 1px solid #F0E6D6 !important;}}
  [data-testid="stTable"] tbody tr:nth-child(even) td {{background: #FBF5EC;}}
  [data-testid="stTable"] tbody tr:hover td {{background: #FFF1E5;}}
  .st-key-entete {{background: linear-gradient(100deg, #F2F2F2 0%, #FAFAFA 45%, #FFFFFF 100%); border-radius: 16px;
          padding: 14px 18px 8px 18px; margin-bottom: 10px;}}
  .entete-titre {{display: flex; align-items: center; gap: 14px;}}
  .entete-nom {{font-size: clamp(1.45rem, 1.9vw, 2.05rem); font-weight: 700; color: #1A1A1A; letter-spacing: -.02em; line-height: 1.1;
          border-bottom: 3px solid {ORANGE}; padding-bottom: 4px; display: inline-block;}}
  .entete-nom span {{font-weight: 400; color: #8C8C8C; white-space: nowrap;}}
  .st-key-filtre-periode [data-testid="stButtonGroup"] button {{min-height: 1.9rem; padding: 0 .55rem; font-size: .8rem;}}
  .entete-ctx {{color: #6B6B6B; font-size: .82rem; margin-top: 6px;}}
  .entete-ctx b {{display: inline-flex; align-items: center; justify-content: center; min-width: 22px; height: 22px;
          padding: 0 6px; margin-right: 8px; border-radius: 999px; background: #000; color: {ORANGE}; font-size: .75rem;}}
  .st-key-entete-outils {{margin-top: -4px; margin-left: 60px;}}
  .st-key-filtre-periode, .st-key-filtre-dep {{background: #fff; border: 1px solid #E3E3E3; border-radius: 12px;
          padding: 8px 12px 10px 12px;}}
  .filtre-titre {{font-size: .78rem; font-weight: 700; color: #1A1A1A; margin-bottom: 2px;}}
  .st-key-nav-pages div[data-testid="stPageLink"] a, .st-key-nav-pages button {{border: none !important;
          background: transparent !important; color: #595959 !important;}}
  .st-key-nav-pages div[data-testid="stPageLink"] a:hover, .st-key-nav-pages button:hover {{color: {ORANGE} !important;
          background: #FFF1E5 !important;}}
  .st-key-nav-pages span[data-testid="stIconMaterial"] {{font-size: 1.6rem !important;}}
  .tuile .valeur {{color: {NOIR}; font-size: clamp(1.1rem, 1.6vw, 1.85rem); white-space: nowrap; font-weight: 800; line-height: 1.1; letter-spacing: -.02em;}}
  .tuile .libelle {{color: #6B6B6B; font-size: .85rem; margin-top: 2px;}}
  .tuile .delta-pos, .tuile .delta-neg {{display: inline-block; font-size: .75rem; font-weight: 700; border-radius: 999px;
          padding: 1px 8px; margin-top: 6px;}}
  .tuile .delta-pos {{color: #1E7B4C; background: #E6F5EC;}}
  .tuile .delta-neg {{color: #CD3C14; background: #FBEAE5;}}

  .bandeau {{background: {NOIR}; color: #fff; font-weight: 700; border-radius: 12px;
            padding: 14px 6px; text-align: center; font-size: .85rem; word-break: keep-all;}}
  .bandeau .ico, .bandeau .ico-svg {{color: {ORANGE}; font-size: 26px; display: block; margin: 0 auto 4px auto;}}
  button[kind="primary"] {{background: {ORANGE} !important; color: #000 !important; border: none !important;
                           font-weight: 700 !important;}}
  button[kind="primary"]:hover {{background: #000 !important; color: #fff !important;}}
  .note {{color: #8C8C8C; font-size: .78rem;}}
  div[class*="st-key-carte-"] {{border-radius: 12px !important; border-color: #E6E6E6 !important;
      background: #fff;}}
  .st-key-nav-pages div[data-testid="stPageLink"] a, .st-key-nav-pages button {{justify-content: center;
      border: 1px solid #E0E0E0; border-radius: 999px; padding: 2px 0 !important; min-height: 2.1rem !important;
      font-size: 1.05rem !important; background: #fff;}}
  .st-key-nav-pages div[data-testid="stPageLink"] a:hover, .st-key-nav-pages button:hover {{border-color: {ORANGE};
      background: #FFF1E5;}}
  .population {{color: #595959; font-size: .8rem; background: #F7F7F7; border: 1px solid #EEE; border-radius: 999px;
               padding: 5px 14px; margin: -4px 0 12px 0;}}
  .population b {{color: #000;}}
  .avertissement {{background: #FFF4EB; border: 1px solid #FFD9B8; padding: 10px 14px; border-radius: 10px;
                  font-size: .9rem; color: #333;}}
</style>
""", unsafe_allow_html=True)

# Fond des pages : crème chaud ; l'accueil ajoute un grand anneau orange en filigrane (voir p_accueil).
# La page de connexion garde son propre fond.
_FOND_APP = '[data-testid="stApp"], [data-testid="stAppViewContainer"], header[data-testid="stHeader"]'
CREME = "#F3EADC"
FOND_PAGES = f"""{_FOND_APP} {{background: {CREME} !important;}}
  .st-key-entete {{background: #FFFFFF !important; border: 1px solid #E6D9C4;}}
  .population {{background: #FFFFFF !important; border-color: #E6D9C4 !important;}}"""
FOND_ANNEAU = f"""{_FOND_APP} {{background-color: {CREME} !important;
    background-image: radial-gradient(circle at calc(100% + 120px) calc(100% + 120px), transparent 330px,
      rgba(255,121,0,.14) 331px, rgba(255,121,0,.14) 400px, transparent 401px) !important;
    background-attachment: fixed !important;}}
  header[data-testid="stHeader"] {{background: rgba(243,234,220,.92) !important;}}"""
if auth.utilisateur():
    st.markdown(f"<style>{FOND_PAGES}</style>", unsafe_allow_html=True)

# Choix du département en colonne de boutons (pages Profil département et Absences par département)
_CHOIX = 'div[class*="st-key-choix-dep_"]'
_OPTION = f'{_CHOIX} label[data-testid="stRadioOption"]'
st.markdown(f"""<style>
  {_CHOIX} {{background: #FFFFFF; border: 1px solid #E6D9C4; border-radius: 14px;
      padding: 12px 10px 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,.04);}}
  .choix-titre {{text-align: center; font-weight: 800; font-size: .95rem; color: #000; padding-bottom: 8px;
      margin-bottom: 8px; border-bottom: 2px solid {ORANGE};}}
  {_CHOIX} [data-testid="stElementContainer"], {_CHOIX} [data-testid="stRadio"],
  {_CHOIX} [data-testid="stRadio"] > div {{width: 100% !important; max-width: 100% !important;}}
  {_CHOIX} div[role="radiogroup"] {{display: flex; flex-direction: column; gap: 7px; width: 100%;}}
  {_CHOIX} div[role="radiogroup"] > div {{width: 100%;}}
  {_OPTION} {{width: 100%; margin: 0; padding: 7px 10px; justify-content: center; background: #FFFFFF;
      border: 1px solid #E3E3E3; border-radius: 10px; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,.08);
      transition: background .15s, border-color .15s, transform .15s;}}
  {_OPTION} > div {{width: 100%; justify-content: center;}}
  {_OPTION} > div > div:first-child {{display: none;}}
  {_OPTION} p {{font-weight: 600; color: #333; text-align: center; margin: 0;}}
  {_OPTION}:hover {{border-color: {ORANGE}; background: #FFF4EB; transform: translateX(2px);}}
  {_OPTION}[data-selected="true"] {{background: {ORANGE}; border-color: {ORANGE};
      box-shadow: 0 4px 12px rgba(255,121,0,.30);}}
  {_OPTION}[data-selected="true"] p {{color: #000; font-weight: 800;}}
</style>""", unsafe_allow_html=True)

# Mise en avant au survol : l'élément pointé monte légèrement, prend un contour orange et un fond orange pâle
CARTE = 'div[class*="st-key-carte-"]'
st.markdown(f"""<style>
  .tuile, {CARTE} {{transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background .18s ease;}}
  .tuile:hover, {CARTE}:hover {{transform: translateY(-3px); box-shadow: 0 12px 28px rgba(0,0,0,.09);
      border: 1.5px solid {ORANGE} !important;}}
  .tuile:hover {{background: #FFF8F2;}}
  .tuile:hover .icone {{background: {ORANGE}; color: #000;}}
  {CARTE}:hover {{background: #FFFCFA;}}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Données
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Chargement des données RH…")
def donnees():
    df, feats = charger()
    df["periode"] = df["date_reference"].dt.year.astype(str) + " S" + np.where(df["date_reference"].dt.month <= 6, "1", "2")
    df["arrivee"] = (df["anciennete"] < 0.5).astype(int)                 # embauché dans les 6 derniers mois
    annee = df["date_naissance"].dt.year
    df["generation"] = pd.cut(annee, [0, 1964, 1980, 1996, 2100],
                              labels=["Baby-boomers", "Génération X", "Génération Y", "Génération Z"]).astype(str)
    df["cadre"] = df["grade"].isin(["G4", "G5"]).astype(int)
    df["tranche_salaire"] = pd.cut(df["salaire_mensuel"], [0, 400e3, 600e3, 900e3, 1.5e6, 1e9],
                                   labels=["< 400 k", "400-600 k", "600-900 k", "0,9-1,5 M", "> 1,5 M"]).astype(str)
    df["categorie_perf"] = pd.cut(df["performance_actuelle"], [0, 2.5, 3.5, 4.2, 5.01],
                                  labels=["Insuffisante", "Attendue", "Bonne", "Excellente"]).astype(str)
    df["annee_embauche"] = df["date_embauche"].dt.year
    for c in ["tranche_age", "tranche_anciennete"]:
        df[c] = df[c].astype(str)
    return df, feats


@st.cache_resource(show_spinner="Entraînement du modèle…")
def modele_entraine():
    """Modèle du dashboard (genre et source SIRH exclus), entraîné sur tout l'historique."""
    df, feats = donnees()
    fm = variables_modele(feats)
    return entrainer_modele(df, fm), fm


@st.cache_resource(show_spinner="Calcul des scores de risque…")
def modele_risque():
    """Scores et contributions au 31/12/2024."""
    df, _ = donnees()
    modele, fm = modele_entraine()
    act = df[df["jeu"] == "actuel"].reset_index(drop=True).copy()
    act["probabilite"] = modele.predict_proba(act[fm])[:, 1]
    act["rang_haut"] = rang_depuis_le_haut(act["probabilite"])
    act["niveau_risque"] = [niveau_depuis_rang(r) for r in act["rang_haut"]]
    act["signale"] = act["niveau_risque"].isin(["Très élevé", "Élevé"])
    contrib = contributions(modele, act[fm], act[fm])
    fam = contrib.drop(columns="donnees")
    act["facteurs"] = [" · ".join(FAMILLES[f] for f, v in ligne.sort_values(ascending=False).head(3).items() if v > 0.04)
                       for _, ligne in fam.iterrows()]
    return act, contrib


def scores():
    return modele_risque()[0]


@st.cache_data(show_spinner="Validation temporelle du modèle…")
def fiabilite():
    """Taux de départ observés par niveau et courbe de capacité, sur 3 cohortes de validation."""
    df, feats = donnees()
    val = validation_temporelle(df, variables_modele(feats))
    return taux_par_niveau(val), courbe_capacite(val), auc_validation(val)


@st.cache_data(show_spinner="Audit de la qualité des données…")
def audit():
    t, n = qualite.anomalies()
    return {"anomalies": t, "n": n, "libelles": qualite.libelles(), "manquants": qualite.manquants(),
            "coherence": qualite.coherence()}


DF, _ = donnees()
PERIODES = sorted(DF["periode"].unique())
PERIODES_HIST = sorted(DF.loc[DF["jeu"] == "historique", "periode"].unique())
DEPARTEMENTS = sorted(DF["departement"].unique())
DATES_LIB = DF.groupby("periode")["date_reference"].first().dt.strftime("%d/%m/%Y")
ORDRE_AGE = ["<25", "25-29", "30-34", "35-39", "40-44", "45-49", "50+"]
ORDRE_ANC = ["<1 an", "1-2 ans", "2-3 ans", "3-5 ans", "5 ans +"]
ORDRE_SAL = ["< 400 k", "400-600 k", "600-900 k", "0,9-1,5 M", "> 1,5 M"]
ORDRE_PERF = ["Insuffisante", "Attendue", "Bonne", "Excellente"]


# ---------------------------------------------------------------------------
# Outils d'affichage
# ---------------------------------------------------------------------------
def nb(x, d=0):
    if pd.isna(x):
        return "—"
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def pct(x, d=1):
    return "—" if pd.isna(x) else f"{x * 100:.{d}f} %".replace(".", ",")


def fcfa(x):
    if pd.isna(x):
        return "—"
    if abs(x) >= 1e9:
        return f"{x / 1e9:.2f} Md".replace(".", ",")
    if abs(x) >= 1e6:
        return f"{x / 1e6:.1f} M".replace(".", ",")
    return f"{x / 1e3:.0f} k"


ICONES = {"👥": "groups", "🚪": "logout", "🧲": "person_add", "👩": "woman", "👨": "man", "👤": "person",
          "⚥": "wc", "⏳": "hourglass_empty", "💰": "payments", "👩\u200d💼": "badge", "🎂": "cake",
          "🧑\u200d🤝\u200d🧑": "diversity_3", "📅": "event", "🤒": "sick", "⏱️": "schedule", "📊": "bar_chart",
          "🏃": "directions_run", "👔": "work", "📉": "trending_down", "📈": "trending_up", "🏢": "domain",
          "🎯": "target", "📝": "edit_note", "📄": "description", "🗂️": "folder", "🛠️": "build", "🔤": "abc", "🔗": "account_tree"}


ICONES_PLEINES = {"hourglass_empty": "hourglass_bottom", "target": "gps_fixed"}
DOSSIER_ICONES = Path(__file__).with_name("icones")


@st.cache_data
def svg_icone(nom):
    """Icône Material « pleine » (fichier SVG du dossier icones/, licence Apache 2.0), colorée par le CSS."""
    f = DOSSIER_ICONES / f"{ICONES_PLEINES.get(nom, nom)}.svg"
    if not f.exists():
        return ""
    return (f.read_text().replace('width="24" height="24"', 'width="100%" height="100%" fill="currentColor"', 1)
            .replace("<svg ", "<svg aria-hidden='true' ", 1))


def ico(e):
    """Icône pleine à la place d'un emoji (repli sur la police d'icônes au trait si le SVG manque)."""
    nom = ICONES.get(e, e)
    if not nom:
        return ""
    svg = svg_icone(nom)
    return f"<span class='ico-svg'>{svg}</span>" if svg else f"<span class='ico'>{nom}</span>"


@st.dialog("Détail", width="large")
def fenetre_detail(titre, df):
    st.markdown(f"<div class='titre-page' style='font-size:1.5rem'>{titre}</div>", unsafe_allow_html=True)
    st.caption(f"{nb(len(df))} collaborateurs")
    if df.empty:
        st.info("Aucun collaborateur dans cette sélection.")
        return
    cols = st.columns(3)
    for c, (dim, lib) in zip(cols, [("departement", "Département"), ("grade", "Grade"), ("contrat", "Contrat")]):
        t = df[dim].astype(str).value_counts().rename_axis(lib).reset_index(name="Effectif")
        c.dataframe(t, hide_index=True, width="stretch", height=min(38 + 35 * len(t), 300),
                    column_config={"Effectif": st.column_config.ProgressColumn(
                        "Effectif", format="%d", min_value=0, max_value=int(t["Effectif"].max()), color="#FF7900")})
    if auth.peut_voir_nominatif():
        champs = [c for c in ["id", "poste", "departement", "grade", "contrat", "genre", "anciennete"] if c in df.columns]
        liste = df[champs].rename(columns={"id": "Identifiant", "poste": "Poste", "departement": "Département",
                                           "grade": "Grade", "contrat": "Contrat", "genre": "Genre",
                                           "anciennete": "Ancienneté (ans)"})
        st.dataframe(zebre(liste), hide_index=True, width="stretch", height=300,
                     column_config={"Ancienneté (ans)": st.column_config.NumberColumn(format="%.1f")})
        st.download_button("Télécharger la liste (CSV)", liste.to_csv(index=False).encode("utf-8"),
                           f"{titre.lower().replace(' ', '_')}.csv", "text/csv", icon=":material/download:", on_click="ignore")
    else:
        st.info("La liste nominative est réservée au profil DRH.")


_COMPTEUR_DETAILS = [0]
ZEBRE = "#FBF5EC"


def zebre(df, styler=None):
    """Lignes alternées blanc / crème (l'en-tête orange vient du thème : config.toml)."""
    sty = styler if styler is not None else df.style
    return sty.apply(lambda col: [f"background-color: {ZEBRE}" if i % 2 else "background-color: #FFFFFF"
                                  for i in range(len(col))], axis=0)


def titre_tableau(texte, note=None):
    st.markdown(f"<div class='tableau-titre'>{texte}</div>" + (f"<div class='note'>{note}</div>" if note else ""),
                unsafe_allow_html=True)


def barre(nom, maxi, fmt="%.0f"):
    return st.column_config.ProgressColumn(nom, format=fmt, min_value=0, max_value=float(maxi or 1), color="#FF7900")


_COMPTEUR_CARTES = [0]
_DANS_FRAGMENT = [False]


def bloc_local(fn):
    """Fragment : seul ce bloc se recalcule quand on y change un réglage (curseur, choix du département…).
    Les compteurs de clés sont fixés pour rester stables d'une exécution du bloc à l'autre."""
    @st.fragment
    def enveloppe(*args, **kwargs):
        _DANS_FRAGMENT[0] = True
        _COMPTEUR_CARTES[0] = _COMPTEUR_DETAILS[0] = _COMPTEUR_GRAPHIQUES[0] = 10_000
        try:
            return fn(*args, **kwargs)
        finally:
            _DANS_FRAGMENT[0] = False
    enveloppe.__name__ = fn.__name__
    return enveloppe


def carte(parent):
    """Bloc encadré (graphique ou tableau) avec une clé stable, pour le style au survol."""
    _COMPTEUR_CARTES[0] += 1
    return parent.container(border=True, key=f"carte-{_COMPTEUR_CARTES[0]}")


def tuile(col, libelle, valeur, icone="", delta=None, inverse=False, detail=None):
    d = ""
    if delta is not None and not pd.isna(delta):
        bon = (delta >= 0) != inverse
        d = f"<div class='{'delta-pos' if bon else 'delta-neg'}'>{'▲' if delta >= 0 else '▼'} {pct(abs(delta))}</div>"
    col.markdown(f"<div class='tuile'><div class='t-ico'>{ico(icone)}</div><div class='t-corps'>"
                 f"<div class='valeur'>{valeur}</div><div class='libelle'>{libelle}</div>{d}</div></div>",
                 unsafe_allow_html=True)
    if detail is not None:
        _COMPTEUR_DETAILS[0] += 1
        if col.button("Voir le détail", key=f"detail-{_COMPTEUR_DETAILS[0]}", type="tertiary",
                      icon=":material/open_in_full:"):
            fenetre_detail(libelle, detail)


def fig_style(fig, hauteur=290, legende=True):
    fig.update_layout(height=hauteur, margin=dict(l=10, r=10, t=40, b=10), legend_title_text="",
                      showlegend=legende, title_font_size=13, title_x=0.01, title_font_color="#333",
                      separators=", ",                       # virgule décimale, espace pour les milliers
                      legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center"))
    fig.update_layout(font=dict(color="#333"), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      barcornerradius=5, hoverlabel=dict(bgcolor="#000", font_color="#fff", bordercolor="#000"),
                      title_font=dict(size=14, color="#000"))
    fig.update_xaxes(gridcolor="#F0F0F0", linecolor="#E0E0E0", zeroline=False)
    fig.update_yaxes(gridcolor="#F0F0F0", linecolor="#E0E0E0", zeroline=False)
    fig.update_traces(selector=dict(type="bar"), textangle=0, cliponaxis=False)
    # série unique en orange : barres en gris clair, seule la plus haute reste en orange (l'orange sert d'accent)
    if len(fig.data) == 1 and fig.data[0].type in ("bar", "funnel") and fig.data[0].marker.color == ORANGE:
        t = fig.data[0]
        v = pd.to_numeric(pd.Series(t.x if t.orientation == "h" else t.y), errors="coerce")
        if len(v) > 1 and v.notna().any():
            imax = int(v.abs().idxmax())
            t.marker.color = [ORANGE if i == imax else "#D6D6D6" for i in range(len(v))]
            t.textfont = dict(color="#333")
    return fig


# --- Filtrage par clic sur les graphiques -------------------------------------------------------------
DIMENSIONS = {"departement": "Département", "grade": "Grade", "tranche_age": "Tranche d'âge", "contrat": "Contrat",
              "ville_affectation": "Ville", "genre": "Genre", "tranche_anciennete": "Ancienneté",
              "generation": "Génération", "niveau_etude": "Niveau d'études", "categorie_perf": "Performance",
              "tranche_salaire": "Tranche de salaire"}
ALIAS_CLIC = {"Femmes": "F", "Hommes": "M"}
_COMPTEUR_GRAPHIQUES = [0]          # remis à zéro à chaque exécution du script : clés stables d'une exécution à l'autre


def _valeurs_dimensions():
    vals = {c: set(DF[c].dropna().astype(str).unique()) for c in DIMENSIONS if c in DF.columns}
    toutes = [v for vs in vals.values() for v in vs]
    ambigues = {v for v in toutes if toutes.count(v) > 1}          # ex. « Non renseigné » : on ne devine pas
    return {c: vs - ambigues for c, vs in vals.items()}


def clic_graphique(cle_graph):
    """Rappel du clic : la valeur cliquée devient un filtre (période, département, ou autre dimension)."""
    etat = st.session_state.get(cle_graph)
    try:
        points = etat["selection"]["points"]
    except (KeyError, TypeError):
        points = []
    if not points:
        return
    p = points[0]
    cle_page = st.session_state.get("_cle_page", "")
    for brut in (p.get("label"), p.get("x"), p.get("y")):
        if brut is None:
            continue
        v = ALIAS_CLIC.get(str(brut), str(brut))
        if v in st.session_state.get("_periodes_page", []):
            st.session_state[f"per_{cle_page}"] = v
            break
        col = next((c for c, vs in VALEURS_DIM.items() if v in vs), None)
        if col:
            if col == "departement" and st.session_state.get("_dep_page"):
                st.session_state[f"dep_{cle_page}"] = v
            else:
                st.session_state["filtre_clic"] = {"page": cle_page, "col": col, "val": v}
            st.toast(f"Filtre appliqué : {DIMENSIONS.get(col, col)} = {v}", icon=":material/filter_alt:")
            break
    st.session_state["_gen_graph"] = st.session_state.get("_gen_graph", 0) + 1     # efface la sélection affichée


def graphique(conteneur, fig, hauteur=290, legende=True, cliquable=True):
    fig = fig_style(fig, hauteur, legende)
    _COMPTEUR_GRAPHIQUES[0] += 1
    cle = f"g{st.session_state.get('_gen_graph', 0)}-{st.session_state.get('_cle_page', '')}-{_COMPTEUR_GRAPHIQUES[0]}"
    if not cliquable or _DANS_FRAGMENT[0]:      # dans un bloc local, le clic ne peut pas filtrer toute la page
        conteneur.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=cle)
        return
    conteneur.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=cle,
                           on_select=lambda: clic_graphique(cle), selection_mode="points")


VALEURS_DIM = _valeurs_dimensions()


FORMATS_ANNEAU = {
    "n": "%{label}<br>%{value:,.0f} (%{percent:.0%})",
    "pct": "%{label}<br>%{value:.2%}",
    "fcfa": "%{label}<br>%{value:,.0f}",
}


def anneau(df, noms, valeurs, titre, couleurs=None, fmt="n"):
    fig = px.pie(df, names=noms, values=valeurs, hole=0.74, title=titre,
                 color=noms, color_discrete_map=couleurs or {})
    fig.update_traces(texttemplate=FORMATS_ANNEAU[fmt], textposition="outside", sort=False,
                      marker=dict(line=dict(color="#fff", width=3)), textfont=dict(size=11, color="#595959"))
    fig.update_layout(showlegend=False)
    if fmt == "n":                                   # total au centre de l'anneau
        total = (df[valeurs].sum() if isinstance(valeurs, str) else sum(valeurs))
        fig.add_annotation(text=f"<b>{nb(total)}</b>", showarrow=False, font=dict(size=18, color="#000"))
    return fig


def sparkline(serie, hauteur=70):
    serie = serie.fillna(0)
    fig = go.Figure(go.Scatter(x=list(range(len(serie))), y=serie.values, mode="lines",
                               fill="tozeroy", line=dict(color=JAUNE, width=2.5, shape="spline"), fillcolor="rgba(255,121,0,.12)"))
    fig.update_layout(height=hauteur, margin=dict(l=0, r=0, t=0, b=0), xaxis_visible=False, yaxis_visible=False,
                      showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(range=[serie.min() * 0.9, serie.max() * 1.05])
    return fig


def evolution(serie, periode):
    """Variation relative entre la période choisie et la précédente."""
    if periode not in serie.index:
        return None
    i = list(serie.index).index(periode)
    if i == 0 or serie.iloc[i - 1] == 0:
        return None
    return serie.iloc[i] / serie.iloc[i - 1] - 1


def page_courante():
    return next(r for r in REGISTRE_VISIBLE if r["url"] == COURANTE.url_path)


def navigation(conteneur):
    """Liens ◀ 🏠 ▶ (page précédente, accueil, page suivante) et déconnexion."""
    i = next(k for k, p in enumerate(ORDRE) if p.url_path == COURANTE.url_path)
    with conteneur.container(key="nav-pages"):
        c = st.columns(4, gap="small")
        if i > 1:
            c[0].page_link(ORDRE[i - 1], label="\u200b", icon=":material/chevron_left:",
                           help=f"Page précédente : {ORDRE[i - 1].title}")
        c[1].page_link(ORDRE[0], label="\u200b", icon=":material/home:", help="Accueil")
        if i < len(ORDRE) - 1:
            c[2].page_link(ORDRE[i + 1], label="\u200b", icon=":material/chevron_right:",
                           help=f"Page suivante : {ORDRE[i + 1].title}")
        c[3].button("", icon=":material/logout:", key="deconnexion", help="Se déconnecter",
                    on_click=auth.deconnecter, width="stretch")


def population(d, periode):
    """Bandeau « population couverte » : effectif, valeurs non renseignées, couverture des évaluations."""
    cur = d[d["periode"] == periode]
    morceaux = [f"<b>{nb(len(cur))}</b> collaborateurs au {DATES_LIB[periode]}"]
    for col, lib in [("genre", "genre"), ("departement", "département")]:
        n = int((cur[col] == "Non renseigné").sum())
        if n:
            morceaux.append(f"{lib} non renseigné : <b>{n}</b>")
    if len(cur):
        morceaux.append(f"performance renseignée : <b>{pct(cur['performance_actuelle'].notna().mean(), 0)}</b>")
        morceaux.append(f"engagement renseigné : <b>{pct(cur['engagement_actuel'].notna().mean(), 0)}</b>")
    st.markdown("<div class='population'>Population couverte · " + " · ".join(morceaux) + "</div>",
                unsafe_allow_html=True)


LOGO = ("<svg viewBox='0 0 48 48' width='46' height='46' aria-hidden='true'><rect width='48' height='48' rx='12' "
        "fill='#000'/><text x='24' y='31' text-anchor='middle' font-family='Source Sans Pro, sans-serif' "
        "font-size='21' font-weight='800' letter-spacing='-1'><tspan fill='#fff'>T</tspan>"
        "<tspan fill='#FF7900'>C</tspan></text></svg>")


def en_tete(numero, titre, periodes=PERIODES, cle="", avec_departement=True, defaut=None):
    """Bandeau de page : logo, titre et contexte (période, périmètre), filtres, navigation, population couverte."""
    r = page_courante()
    st.session_state["_cle_page"] = cle
    st.session_state["_periodes_page"] = list(periodes or [])
    st.session_state["_dep_page"] = avec_departement
    lire_adresse(cle, periodes, avec_departement)
    with st.container(key="entete"):
        gauche, milieu, droite, nav = st.columns([3.4, 3.3, 1.3, 1.0], vertical_alignment="center")
        navigation(nav)
        zone_titre = gauche.empty()
        with gauche.container(horizontal=True, vertical_alignment="center", gap="small", key="entete-outils"):
            with st.popover("Définitions", icon=":material/info:", type="tertiary"):
                st.markdown(AIDE_COMMUNE)
                if r["url"] in AIDE_PAGES:
                    st.markdown(AIDE_PAGES[r["url"]])
            partage = st.popover("Partager", icon=":material/share:", type="tertiary")
        periode = None
        if periodes:
            defaut = defaut or periodes[-1]
            with milieu.container(key="filtre-periode"):
                st.markdown("<div class='filtre-titre'>Période</div>", unsafe_allow_html=True)
                periode = st.pills("Période", periodes, default=defaut, key=f"per_{cle}", label_visibility="collapsed")
            periode = periode or defaut
        dep = "Tous"
        if avec_departement:
            with droite.container(key="filtre-dep"):
                st.markdown("<div class='filtre-titre'>Département</div>", unsafe_allow_html=True)
                dep = st.selectbox("Département", ["Tous"] + DEPARTEMENTS, key=f"dep_{cle}", label_visibility="collapsed")
    contexte = [r["section"]]
    if periode:
        contexte.append(f"au {DATES_LIB[periode]}")
    if avec_departement:
        contexte.append("tous les départements" if dep == "Tous" else dep)
    zone_titre.markdown(
        f"<div class='entete-titre'>{LOGO}<div><div class='entete-nom'>{r['titre']}"
        f"{f' <span>· {periode}</span>' if periode else ''}</div>"
        f"<div class='entete-ctx'><b>{r['numero']}</b>{' · '.join(contexte)}</div></div></div>",
        unsafe_allow_html=True)
    d = DF if dep == "Tous" else DF[DF["departement"] == dep]
    f = st.session_state.get("filtre_clic")
    if f and f["page"] == cle and f["col"] in d.columns:
        d = d[d[f["col"]].astype(str) == f["val"]]
        st.button(f"{DIMENSIONS.get(f['col'], f['col'])} : {f['val']}", icon=":material/close:", key=f"retirer_{cle}",
                  help="Retirer ce filtre", on_click=retirer_filtre)
    else:
        f = None
    ecrire_adresse(partage, r["url"], periode, periodes, dep, f)
    bandeau_parcours(r["url"])
    if periode:
        population(d, periode)
    else:
        st.write("")
    return d, periode, dep


def retirer_filtre():
    st.session_state.pop("filtre_clic", None)
    st.toast("Filtre retiré", icon=":material/filter_alt_off:")


def lire_adresse(cle, periodes, avec_departement):
    """Lien partagé : à la première exécution d'une page, la période, le département et le filtre
    écrits dans l'adresse sont appliqués aux réglages de la page."""
    if st.session_state.get("_adresse_lue") == cle:
        return
    st.session_state["_adresse_lue"] = cle
    qp = st.query_params
    if periodes and qp.get("periode") in periodes:
        st.session_state[f"per_{cle}"] = qp["periode"]
    if avec_departement and qp.get("departement") in DEPARTEMENTS:
        st.session_state[f"dep_{cle}"] = qp["departement"]
    if ":" in qp.get("filtre", ""):
        col, val = qp["filtre"].split(":", 1)
        if col in DIMENSIONS and val in VALEURS_DIM.get(col, ()):
            st.session_state["filtre_clic"] = {"page": cle, "col": col, "val": val}


def ecrire_adresse(partage, url, periode, periodes, dep, filtre):
    """Les réglages en cours sont recopiés dans l'adresse ; le menu « Partager » affiche le lien à copier."""
    params = {}
    if periode and periodes and periode != periodes[-1]:
        params["periode"] = periode
    if dep != "Tous":
        params["departement"] = dep
    if filtre:
        params["filtre"] = f"{filtre['col']}:{filtre['val']}"
    if dict(st.query_params) != params:
        st.query_params.from_dict(params)
    base = "/".join(str(st.context.url or "").split("/")[:3])
    lien = f"{base}/{url}" + (f"?{urlencode(params)}" if params else "")
    with partage:
        st.markdown("**Lien vers cette vue**")
        st.code(lien, language=None, wrap_lines=True)
        st.caption("Copiez le lien avec l'icône à droite. La personne qui l'ouvre arrive sur cette page, avec la même "
                   "période, le même département et le même filtre, après s'être connectée avec son propre profil.")


AIDE_COMMUNE = """**Comment lire cette page**
- **Période** : situation au 30/06 (S1) ou au 31/12 (S2) de l'année.
- **Départ** : départ dans les 6 mois suivant la date de référence (connu jusqu'à la cohorte 2024 S1).
- **Arrivée** : embauche dans les 6 mois précédant la date de référence.
- **Absentéisme** : jours d'absence sur 6 mois ÷ 130 jours ouvrés.

**Astuce** : cliquez sur une barre ou une part d'un graphique pour filtrer toute la page
(département, grade, âge, contrat, ville…). Le filtre s'affiche sous le titre, cliquez dessus pour le retirer."""

AIDE_PAGES = {
    "vue-ensemble": "**Cette page** : les grands équilibres (effectif, diversité, recrutements, départs) en un coup d'œil.",
    "assistant": "**Cette page** : questions fréquentes de la DRH. Les réponses sont calculées sur les données, sans IA "
                 "externe : aucune donnée ne quitte le dashboard.",
    "recommandations": "**Cette page** : plan d'action établi par des règles explicites (turnover nettement au-dessus "
                       "de la moyenne, salaires sous 90 % de la référence, profils performants peu engagés, "
                       "absentéisme élevé, écart F/H, évaluations manquantes). Identique au bilan PDF.",
    "simulateur": "**Cette page** : coût d'une mesure de rétention contre coût des départs évités, sur un an. "
                  "Le modèle recalcule la probabilité de départ de chaque collaborateur ciblé après l'action ; "
                  "départs attendus = somme des probabilités (deux semestres).",
    "demographie": "**Cette page** : la structure de l'effectif. « Voir le détail » sous une carte ouvre la liste correspondante.",
    "diversite": "**Cette page** : répartition par génération, genre et niveau d'études. Génération Z : nés après 1996.",
    "tendances": "**Cette page** : évolution semestrielle depuis juin 2022. Cliquez sur une période pour la sélectionner.",
    "arrivees": "**Cette page** : profil des personnes embauchées dans les 6 derniers mois.",
    "profil-departement": "**Cette page** : synthèse d'un département comparé à l'entreprise.",
    "fiche-collaborateur": "**Cette page** : réservée au profil DRH. Le score est un signal statistique, pas une prédiction individuelle.",
    "salaires": "**Cette page** : salaires mensuels bruts en FCFA. Médiane par grade avec 1er et 3e quartiles.",
    "equite-salariale": "**Cette page** : écart H − F à grade et département comparables.",
    "absenteisme": "**Cette page** : taux = jours d'absence sur 6 mois ÷ 130 jours ouvrés.",
    "absences-departement": "**Cette page** : jours d'absence détaillés par département, justifiés ou non.",
    "performance": "**Cette page** : dernière évaluation connue (Insuffisante → Excellente).",
    "analyse-departs": "**Cette page** : taux de départ à 6 mois par cohorte historique.",
    "caracteristiques-departs": "**Cette page** : qui sont les personnes parties, comparées à celles restées.",
    "anticipation": "**Cette page** : niveaux de risque issus du modèle (AUC ≈ 0,72 en validation temporelle). "
                    "Cliquez sur une ligne de la liste pour ouvrir la fiche.",
    "qualite-donnees": "**Cette page** : corrections appliquées aux données brutes avant analyse.",
    "exports": "**Cette page** : téléchargement des indicateurs (Excel) et de la synthèse (PDF).",
}


def precedente(periode, liste=PERIODES):
    i = liste.index(periode)
    return liste[i - 1] if i > 0 else None


def cohorte(periode):
    """Le départ à 6 mois n'est connu que pour les périodes historiques."""
    return periode if periode in PERIODES_HIST else PERIODES_HIST[-1]






# ---------------------------------------------------------------------------
# Parcours guidés et ponts entre thèmes : les chiffres clés de l'histoire, à l'échelle de l'entreprise
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def faits():
    """Chiffres clés (dernière date, dernière cohorte connue) utilisés par les parcours et les ponts."""
    per, coh = PERIODES[-1], PERIODES_HIST[-1]
    cur = DF[DF["periode"] == per]
    h = DF[DF["jeu"] == "historique"]
    hc = h[h["periode"] == coh]
    taux_coh = h.groupby("periode")["target"].mean()
    f = dict(per=per, date=DATES_LIB[per], coh=coh, departs=int(hc["target"].sum()), taux=hc["target"].mean(),
             taux_prec=taux_coh.iloc[-2] if len(taux_coh) > 1 else None)
    td = hc[hc["departement"] != "Non renseigné"].groupby("departement")["target"].agg(["mean", "size"])
    td = td[td["size"] >= 20]
    f["dep_max"], f["dep_max_taux"] = td["mean"].idxmax(), td["mean"].max()
    ta = hc.groupby("tranche_anciennete")["target"].mean().reindex(ORDRE_ANC).dropna()
    f["anc_max"], f["anc_max_taux"] = ta.idxmax(), ta.max()
    sous = hc["ratio_salaire_reference"] < .9
    f["dep_sous90"], f["dep_sur90"] = hc.loc[sous, "target"].mean(), hc.loc[~sous, "target"].mean()
    eng = hc["engagement_actuel"] < 3
    f["dep_eng_bas"], f["dep_eng_ok"] = hc.loc[eng, "target"].mean(), hc.loc[hc["engagement_actuel"] >= 3, "target"].mean()
    act, contrib = modele_risque()
    fam = contrib.drop(columns="donnees")
    sig = act.index[act["signale"]]
    top3 = fam.loc[sig].apply(lambda l: l.nlargest(3)[l.nlargest(3) > 0.04].index.tolist(), axis=1)
    freq = pd.Series([x for liste in top3 for x in liste]).value_counts() / max(len(sig), 1)
    f["n_signales"], f["part_eng"], f["part_sal"] = len(sig), freq.get("engagement", 0), freq.get("remuneration", 0)
    par = DF.groupby("periode")
    masse = par["salaire_mensuel"].sum()
    f["masse"], f["masse_hausse"], f["debut"] = masse.iloc[-1], masse.iloc[-1] / masse.iloc[0] - 1, PERIODES[0]
    eff = par.size()
    f["eff_hausse"] = eff.iloc[-1] / eff.iloc[0] - 1
    f["sous90"], f["n_sous90"] = (cur["ratio_salaire_reference"] < .9).mean(), int((cur["ratio_salaire_reference"] < .9).sum())
    fh = cur[cur["genre"].isin(["F", "M"])]
    med = fh.groupby(["grade", "genre"])["salaire_mensuel"].median().unstack()
    n = fh.groupby(["grade", "genre"]).size().unstack()
    ec = (med["F"] / med["M"] - 1).where((n["F"] >= 10) & (n["M"] >= 10)).dropna()
    f["ecart_grade"], f["ecart"] = (ec.abs().idxmax(), ec[ec.abs().idxmax()]) if len(ec) else (None, 0)
    ab = par["taux_absenteisme"].mean()
    f["abs"], f["abs_debut"], f["abs_max_per"], f["abs_max"] = ab.iloc[-1], ab.iloc[0], ab.idxmax(), ab.max()
    abd = cur[cur["departement"] != "Non renseigné"].groupby("departement")["taux_absenteisme"].mean()
    f["abs_dep"], f["abs_dep_taux"] = abd.idxmax(), abd.max()
    q = hc["taux_absenteisme"] >= hc["taux_absenteisme"].quantile(.75)
    f["dep_abs_haut"], f["dep_abs_bas"] = hc.loc[q, "target"].mean(), hc.loc[~q, "target"].mean()
    return f


def _pts(a, b, dec=1):
    return f"{'+' if a - b >= 0 else '−'}{pct(abs(a - b), dec).replace(' %', ' pt')}"


PARCOURS = {
    "departs": dict(
        titre="Pourquoi perd-on des collaborateurs ?", icone="logout",
        resume="Du constat des départs jusqu'aux personnes à accompagner.",
        etapes=[
            ("analyse-departs", "Le constat", lambda f: (
                f"Sur la cohorte {f['coh']}, <b>{f['departs']} collaborateurs</b> sont partis dans les 6 mois, soit "
                f"<b>{pct(f['taux'])}</b>" + (f" ({_pts(f['taux'], f['taux_prec'])} par rapport à la cohorte précédente)"
                                             if f['taux_prec'] is not None else "") +
                f". <b>{f['dep_max']}</b> est le département le plus touché ({pct(f['dep_max_taux'])}).")),
            ("caracteristiques-departs", "Qui part ?", lambda f: (
                f"Les départs sont les plus fréquents chez les collaborateurs de <b>{f['anc_max']}</b> d'ancienneté "
                f"({pct(f['anc_max_taux'])}). Deux signaux ressortent : ceux payés sous 90 % de la référence de leur "
                f"grade partent à <b>{pct(f['dep_sous90'])}</b> (contre {pct(f['dep_sur90'])}), ceux dont l'engagement "
                f"est inférieur à 3 à <b>{pct(f['dep_eng_bas'])}</b> (contre {pct(f['dep_eng_ok'])}).")),
            ("anticipation", "Qui risque de partir ?", lambda f: (
                f"Le modèle confirme ces deux signaux : l'engagement figure parmi les principaux facteurs de "
                f"<b>{pct(f['part_eng'], 0)}</b> des {f['n_signales']} collaborateurs signalés, le positionnement "
                f"salarial de <b>{pct(f['part_sal'], 0)}</b>. Cliquez sur une ligne de la liste pour ouvrir une fiche.")),
            ("recommandations", "Que faire ?", lambda f: (
                "Le plan d'action traduit ces constats : entretiens de rétention dans les départements les plus "
                "touchés, revue salariale ciblée, entretiens de carrière pour les profils performants peu engagés.")),
        ]),
    "salaires": dict(
        titre="Notre politique salariale est-elle juste ?", icone="payments",
        resume="Du coût de la masse salariale à son effet sur les départs.",
        etapes=[
            ("salaires", "Combien et comment ?", lambda f: (
                f"La masse salariale mensuelle atteint <b>{fcfa(f['masse'])} FCFA</b> au {f['date']}, "
                f"<b>{pct(f['masse_hausse'], 0)}</b> depuis {f['debut']}, portée surtout par la hausse de l'effectif "
                f"({pct(f['eff_hausse'], 0)}). Mais <b>{pct(f['sous90'], 0)}</b> des collaborateurs ({nb(f['n_sous90'])}) "
                "sont payés sous 90 % de la référence de leur grade.")),
            ("equite-salariale", "Est-ce équitable ?", lambda f: (
                f"À grade comparable, le plus grand écart de salaire médian femmes / hommes est en "
                f"<b>{f['ecart_grade']}</b> : <b>{pct(f['ecart'], 1)}</b> pour les femmes. "
                "Comparez par département dans cette page." if f['ecart_grade'] else
                "Aucun grade ne présente d'écart notable avec au moins 10 femmes et 10 hommes.")),
            ("anticipation", "Effet sur les départs", lambda f: (
                f"Le salaire sous la référence pèse lourd : ces collaborateurs sont partis à <b>{pct(f['dep_sous90'])}</b> "
                f"contre {pct(f['dep_sur90'])} pour les autres, et le positionnement salarial figure parmi les principaux "
                f"facteurs de <b>{pct(f['part_sal'], 0)}</b> des collaborateurs signalés.")),
            ("recommandations", "Que faire ?", lambda f: (
                "Prioriser la revue salariale sur les collaborateurs sous 90 % de la référence, en commençant par ceux "
                "que le modèle signale.")),
        ]),
    "absences": dict(
        titre="L'absentéisme dérape-t-il ?", icone="event_busy",
        resume="De la tendance aux départements concernés, et au lien avec les départs.",
        etapes=[
            ("absenteisme", "La tendance", lambda f: (
                f"Le taux d'absentéisme est de <b>{pct(f['abs'], 2)}</b> au {f['date']} "
                f"({_pts(f['abs'], f['abs_debut'], 2)} depuis {f['debut']}). Le pic a été atteint en "
                f"{f['abs_max_per']} ({pct(f['abs_max'], 2)}) : la hausse n'est pas continue, à surveiller semestre "
                "par semestre.")),
            ("absences-departement", "Où ?", lambda f: (
                f"<b>{f['abs_dep']}</b> a le taux le plus élevé ({pct(f['abs_dep_taux'], 2)}). Choisissez-le dans la "
                "liste pour voir la part d'absences justifiées et non justifiées.")),
            ("caracteristiques-departs", "Effet sur les départs", lambda f: (
                f"Les collaborateurs les plus absents (quart supérieur) sont partis à <b>{pct(f['dep_abs_haut'])}</b> "
                f"contre {pct(f['dep_abs_bas'])} pour les autres : l'absentéisme est aussi un signal d'alerte.")),
            ("recommandations", "Que faire ?", lambda f: (
                "Analyser les causes avec les managers des départements concernés (absences non justifiées, charge, "
                "organisation) et suivre le taux chaque semestre.")),
        ]),
}


def demarrer_parcours(cle):
    st.session_state["parcours"] = {"cle": cle, "etape": 0}
    st.switch_page(PAGE[PARCOURS[cle]["etapes"][0][0]])


def bandeau_parcours(url):
    """Si un parcours est en cours et que la page affichée en est l'étape courante : lecture et navigation."""
    etat = st.session_state.get("parcours")
    if not etat:
        return
    p = PARCOURS[etat["cle"]]
    etapes = p["etapes"]
    i = etat["etape"]
    if etapes[i][0] != url:
        autres = [k for k, e in enumerate(etapes) if e[0] == url]
        if not autres:
            return
        i = etat["etape"] = autres[0]
    _, titre, texte = etapes[i]
    puces = "".join(f"<span class='pc-puce{' on' if k == i else ' fait' if k < i else ''}'>{k + 1} · {e[1]}</span>"
                    for k, e in enumerate(etapes))
    with st.container(key="parcours"):
        st.markdown(f"<div class='pc-haut'><span class='pc-nom'>Parcours · {p['titre']}</span>"
                    f"<span class='pc-pas'>Étape {i + 1} / {len(etapes)}</span></div>"
                    f"<div class='pc-puces'>{puces}</div>"
                    f"<div class='pc-titre'>{titre}</div><div class='pc-texte'>{texte(faits())}</div>",
                    unsafe_allow_html=True)
        with st.container(horizontal=True, gap="small", key="parcours-boutons"):
            if i > 0 and st.button("Étape précédente", icon=":material/arrow_back:", key="pc-prec"):
                etat["etape"] = i - 1
                st.switch_page(PAGE[etapes[i - 1][0]])
            if i < len(etapes) - 1:
                if st.button(f"Étape suivante : {etapes[i + 1][1]}", icon=":material/arrow_forward:", type="primary",
                             key="pc-suiv"):
                    etat["etape"] = i + 1
                    st.switch_page(PAGE[etapes[i + 1][0]])
            if st.button("Terminer le parcours" if i == len(etapes) - 1 else "Quitter", icon=":material/close:",
                         key="pc-quitter", type="tertiary"):
                st.session_state.pop("parcours", None)
                st.switch_page(ORDRE[0])


def pont(texte, url):
    """Encart « À relier » : rattache le constat de la page à un autre thème, avec un lien."""
    with st.container(key=f"pont-{url}"):
        a, b = st.columns([5, 1.4], vertical_alignment="center")
        a.markdown(f"<div class='pont'>{ico('🔗')}<div><b>À relier</b> · {texte}</div></div>",
                   unsafe_allow_html=True)
        b.page_link(PAGE[url], label=PAGE[url].title, icon=":material/arrow_forward:")


# ---------------------------------------------------------------------------
# 0. Accueil
# ---------------------------------------------------------------------------
def p_accueil():
    """Accueil : les pages disposées autour de l'anneau « cycle de vie », regroupées par domaine (liens natifs)."""
    u = auth.utilisateur()
    st.markdown(f"<style>{FOND_ANNEAU}</style>", unsafe_allow_html=True)
    # sur la page anneau, on navigue uniquement par les titres autour du cercle : la barre du haut est masquée
    st.markdown("<style>[data-testid='stTopNavigation'], header nav, header [data-testid='stNavSection'] "
                "{display:none !important;}</style>", unsafe_allow_html=True)
    h1, h2 = st.columns([3, 1.6], vertical_alignment="center")
    h1.markdown("<div class='acc-marque'><b>TelcomCI</b> HR Analytics</div>"
                "<div class='acc-sous'>Pilotage RH · choisissez un thème autour de l'anneau</div>", unsafe_allow_html=True)
    with h2:
        a, b = st.columns([2.2, 1], vertical_alignment="center")
        a.markdown(f"<div class='acc-user'><b>{u['nom']}</b><br>profil {auth.ROLES[u['role']]['libelle']}</div>",
                   unsafe_allow_html=True)
        b.button("Quitter", key="deco_accueil", icon=":material/logout:", on_click=auth.deconnecter, width="stretch")

    ORANGE, NOIR = "#FF7900", "#000"
    COUL_SECTION = {"Pilotage": "#000", "Effectifs": "#333", "Rémunération": "#595959", "Absentéisme": "#8C8C8C",
                    "Performance": "#B3B3B3", "Turnover": ORANGE, "Données": "#D9D9D9"}
    L, H, cx, cy = 1180, 720, 590, 360
    R, EP, ECART = 150, 30, 7                    # rayon et épaisseur de l'anneau, écart entre domaines (degrés)

    pages = ORDRE[1:]
    infos = REGISTRE_VISIBLE
    replies = st.session_state.setdefault("domaines_replies", set())
    sections = []
    for r in infos:
        if not sections or sections[-1][0] != r["section"]:
            sections.append([r["section"], 0])
        sections[-1][1] += 1
    replie = [nom in replies for nom, _ in sections]
    poids = [max(n, 2) for _, n in sections]      # positions fixes, que le domaine soit replié ou non
    pas = (360 - ECART * len(sections)) / sum(poids)

    def pt(r, a):
        return cx + r * np.cos(np.radians(a)), cy + r * np.sin(np.radians(a))

    def arc(r, a0, a1):
        (x0, y0), (x1, y1) = pt(r, a0), pt(r, a1)
        return f"M {x0:.1f} {y0:.1f} A {r} {r} 0 {1 if a1 - a0 > 180 else 0} 1 {x1:.1f} {y1:.1f}"

    svg, angles, sect_de, centres = [], [], [], []
    a = -90 - (poids[0] * pas) / 2               # le premier domaine (Pilotage) centré en haut
    for k, ((nom, n), w, rep) in enumerate(zip(sections, poids, replie)):
        a0, a1 = a, a + w * pas
        coul = COUL_SECTION.get(nom, "#999")
        if rep:                                   # domaine replié : segment en pointillés
            svg.append(f"<path d='{arc(R, a0, a1)}' fill='none' stroke='{coul}' stroke-width='10' stroke-linecap='round'"
                       f" stroke-dasharray='0.1 16' opacity='.9'/>")
        else:
            svg.append(f"<path d='{arc(R, a0, a1)}' fill='none' stroke='{coul}' stroke-width='{EP}' stroke-linecap='round'/>")
        bas = 0 < ((a0 + a1) / 2) % 360 < 180
        chemin = arc(R + 30, a1, a0).replace(" 0 1 ", " 0 0 ") if bas else arc(R + 30, a0, a1)
        libelle = f"{nom.upper()} +{n}" if rep else nom.upper()
        svg.append(f"<path id='dom{k}' d='{chemin}' fill='none'/>"
                   f"<text font-size='10.5' font-weight='700' letter-spacing='1.2' fill='{ORANGE if nom == 'Turnover' else '#8C8C8C'}'"
                   f" font-family='Inter, sans-serif' dy='{8 if bas else 0}'><textPath href='#dom{k}' startOffset='50%' text-anchor='middle'>"
                   f"{libelle}</textPath></text>")
        centres.append(pt(R + 30, (a0 + a1) / 2))
        for j in range(n):
            angles.append(a0 + (j + .5) * (w * pas) / n)
            sect_de.append(nom)
        a = a1 + ECART
    RX, RY = 345, 300
    for ang, nom in zip(angles, sect_de):
        if nom in replies:
            continue
        (x0, y0), (x1, y1) = pt(R + EP / 2 + 40, ang), (cx + (RX - 8) * np.cos(np.radians(ang)),
                                                       cy + (RY - 8) * np.sin(np.radians(ang)))
        coul = ORANGE if nom == "Turnover" else "#C8C8C8"
        svg.append(f"<line x1='{x0:.1f}' y1='{y0:.1f}' x2='{x1:.1f}' y2='{y1:.1f}' stroke='{coul}' stroke-width='1'/>"
                   f"<circle cx='{x1:.1f}' cy='{y1:.1f}' r='3' fill='{coul}'/>")
    svg.append(f"<circle cx='{cx}' cy='{cy}' r='{R - EP / 2 - 14}' fill='none' stroke='#EEE' stroke-width='1'/>"
               f"<text x='{cx}' y='{cy - 14}' text-anchor='middle' font-size='26' font-weight='800' fill='{NOIR}'"
               " font-family='Inter, sans-serif' letter-spacing='-0.5'>Cycle de vie</text>"
               f"<text x='{cx}' y='{cy + 16}' text-anchor='middle' font-size='26' font-weight='800' fill='{ORANGE}'"
               " font-family='Inter, sans-serif' letter-spacing='-0.5'>du collaborateur</text>"
               f"<text x='{cx}' y='{cy + 44}' text-anchor='middle' font-size='12' fill='#8C8C8C'"
               f" font-family='Inter, sans-serif'>{len(pages)} analyses · {len(sections)} domaines</text>")
    svg = f"<svg width='{L}' height='{H}'>{''.join(svg)}</svg>"

    regles = []
    for i, (ang, nom, info) in enumerate(zip(angles, sect_de, infos)):
        x, y = cx + RX * np.cos(np.radians(ang)), cy + RY * np.sin(np.radians(ang))
        c = np.cos(np.radians(ang))
        t = "translate(-50%,-50%)" if abs(c) < .12 else "translate(0,-50%)" if c > 0 else "translate(-100%,-50%)"
        regles.append(f".st-key-cercle-{i} {{left:{x:.0f}px; top:{y:.0f}px; transform:{t};}}"
                      f".st-key-cercle-{i} div[data-testid='stPageLink'] a::before {{content:'{info['numero']}';}}")
        if nom == "Turnover":
            regles.append(f".st-key-cercle-{i} div[data-testid='stPageLink'] a::before {{background:{ORANGE} !important;"
                          f" color:#000 !important;}}")
    for k, (x, y) in enumerate(centres):
        regles.append(f".st-key-dom-{k} {{left:{x:.0f}px; top:{y:.0f}px; transform:translate(-50%,-50%);}}")
    st.markdown(f"""<style>
  .acc-marque {{font-size: 1.9rem; font-weight: 800; letter-spacing: -.02em; color: #000;}}
  .acc-marque b {{color: {ORANGE};}}
  .acc-sous {{color: #8C8C8C; font-size: .9rem; margin-top: 2px;}}
  .acc-pc-titre {{text-align:center; font-size:1.5rem; font-weight:800; color:#000; letter-spacing:-.01em; margin-top:8px;}}
  div[class*="st-key-acc-pc-"] {{background:#fff; border-radius:14px; border-color:#E6E6E6 !important;
       transition: box-shadow .15s, border-color .15s, transform .15s;}}
  div[class*="st-key-acc-pc-"]:hover {{border-color:{ORANGE} !important; box-shadow:0 8px 22px rgba(0,0,0,.08);
       transform: translateY(-2px);}}
  .acc-pc-ico {{width:40px; height:40px; border-radius:10px; background:#000; color:{ORANGE}; padding:8px;}}
  .acc-pc-q {{font-weight:800; font-size:1.12rem; color:#000; margin-top:10px; line-height:1.25;}}
  .acc-pc-r {{color:#595959; font-size:.88rem; margin-top:4px;}}
  .acc-pc-e {{color:#8C8C8C; font-size:.78rem; margin:10px 0 4px 0;}}
  .acc-user {{text-align: right; color: #595959; font-size: .8rem; line-height: 1.35;}}
  .acc-user b {{color: #000;}}
  .st-key-deco_accueil button {{border-radius: 999px; border-color: #DDD;}}
  .st-key-deco_accueil button:hover {{border-color: #000; color: #000;}}
  .st-key-cercle-zone {{position:relative; width:{L}px; height:{H}px !important; min-height:{H}px !important;
                       margin:0 auto; display:block !important;}}
  .st-key-cercle-svg {{position:absolute; left:0; top:0;}}
  div[class*="st-key-cercle-"]:not(.st-key-cercle-zone):not(.st-key-cercle-svg),
  div[class*="st-key-dom-"] {{position:absolute; width:max-content !important; z-index:2;}}
  div[class*="st-key-dom-"] button {{opacity:0; width:120px; min-height:26px !important; height:26px; padding:0;
       cursor:pointer;}}
  .st-key-cercle-zone div[data-testid="stPageLink"] a {{background:#fff; border:1px solid #E6E6E6; border-radius:999px;
       padding:4px 14px 4px 4px; gap:9px; font-weight:600; transition: background .15s, border-color .15s;}}
  .st-key-cercle-zone div[data-testid="stPageLink"] a span[data-testid="stIconMaterial"] {{color:#8C8C8C;}}
  .st-key-cercle-zone div[data-testid="stPageLink"] a::before {{
       background:#000; color:#fff; font-weight:700; border-radius:50%; width:26px; height:26px; display:inline-flex;
       align-items:center; justify-content:center; font-size:.78rem; flex-shrink:0;}}
  {''.join(regles)}
  .st-key-cercle-zone div[data-testid="stPageLink"] a:hover {{background:{ORANGE}; border-color:{ORANGE};}}
  .st-key-cercle-zone div[data-testid="stPageLink"] a:hover p,
  .st-key-cercle-zone div[data-testid="stPageLink"] a:hover span[data-testid="stIconMaterial"] {{color:#000 !important;}}
  .st-key-cercle-zone div[data-testid="stPageLink"] a:hover::before {{background:#000 !important; color:{ORANGE} !important;}}
</style>""", unsafe_allow_html=True)

    def basculer(nom):
        replies.symmetric_difference_update({nom})

    with st.container(key="cercle-zone"):
        with st.container(key="cercle-svg"):
            st.markdown(svg, unsafe_allow_html=True)
        for k, (nom, _) in enumerate(sections):
            with st.container(key=f"dom-{k}"):
                st.button(nom, key=f"btn-dom-{k}", on_click=basculer, args=(nom,),
                          help=("Déplier" if nom in replies else "Replier") + f" « {nom} »")
        for i, (pg, nom) in enumerate(zip(pages, sect_de)):
            if nom in replies:
                continue
            with st.container(key=f"cercle-{i}"):
                st.page_link(pg, label=pg.title)

    st.markdown("<div class='acc-pc-titre'>Parcours guidés</div><div class='acc-sous' style='text-align:center'>"
                "Trois questions de la DRH, chacune déroulée en quelques pages avec la lecture des chiffres.</div>",
                unsafe_allow_html=True)
    st.write("")
    cols = st.columns(len(PARCOURS))
    for col, (cle, p) in zip(cols, PARCOURS.items()):
        with col.container(border=True, key=f"acc-pc-{cle}"):
            etapes = " → ".join(e[1] for e in p["etapes"])
            st.markdown(f"<div class='acc-pc-ico'>{svg_icone(p['icone'])}</div><div class='acc-pc-q'>{p['titre']}</div>"
                        f"<div class='acc-pc-r'>{p['resume']}</div><div class='acc-pc-e'>{etapes}</div>",
                        unsafe_allow_html=True)
            if st.button("Démarrer", key=f"go-{cle}", icon=":material/play_arrow:", type="primary", width="stretch"):
                demarrer_parcours(cle)
    st.write("")
    act = DF[DF["jeu"] == "actuel"]
    st.markdown(f"<div class='note' style='text-align:center'>Cliquez sur un thème pour ouvrir son tableau de bord.<br>"
                f"Données TelcomCI : {len(act)} collaborateurs au 31/12/2024, historique semestriel depuis juin 2022, "
                f"départs connus jusqu'à la cohorte du 30/06/2024. "
                f"Absentéisme = jours d'absence sur 6 mois ÷ {JOURS_OUVRES_6M} jours ouvrés · "
                f"Départ = départ dans les 6 mois suivant la date de référence · "
                f"Arrivée = embauche dans les 6 mois précédant la date de référence.</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 1. Vue d'ensemble (HR at a Glance)
# ---------------------------------------------------------------------------
def p_vue_ensemble():
    d, per, _ = en_tete(1, "Vue d'ensemble RH", cle="glance")
    cur = d[d["periode"] == per]
    par = d.groupby("periode")
    eff = par.size()

    def ligne(theme, icone, url):
        c = st.columns([1.0, 1.6, 1.6, 2, 1.4])
        c[0].markdown(f"<div class='bandeau' style='margin-top:30px'>{ico(icone)}{theme}</div>", unsafe_allow_html=True)
        with c[0].container(key=f"vers-{url}"):
            st.page_link(PAGE[url], label="Analyser", icon=":material/arrow_forward:", help=PAGE[url].title)
        return c

    # Collaborateurs
    c = ligne("Collaborateurs", "👥", "demographie")
    tuile(c[1], "Effectif", nb(len(cur)), delta=evolution(eff, per))
    c[1].plotly_chart(sparkline(eff), width="stretch", config={"staticPlot": True})
    graphique(c[2], anneau(cur["contrat"].value_counts().reset_index(), "contrat", "count", "Effectif par contrat",
                           {"CDI": JAUNE, "CDD": GRIS}), 200, False)
    g = cur["grade"].value_counts().sort_index().reset_index()
    graphique(c[3], px.bar(g, x="grade", y="count", text="count", title="Effectif par grade",
                           color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 200)
    tuile(c[4], "CDI", nb((cur["contrat"] == "CDI").sum()))
    tuile(c[4], "Ancienneté moyenne (ans)", nb(cur["anciennete"].mean(), 2))

    # Diversité
    c = ligne("Diversité", "🧑‍🤝‍🧑", "diversite")
    fem_cadres = par.apply(lambda x: (x.loc[x["cadre"] == 1, "genre"] == "F").mean())
    tuile(c[1], "% de femmes parmi les cadres (G4-G5)", pct(fem_cadres.get(per)),
          delta=evolution(fem_cadres, per))
    c[1].plotly_chart(sparkline(fem_cadres), width="stretch", config={"staticPlot": True})
    graphique(c[2], anneau(cur["genre"].value_counts().reset_index(), "genre", "count", "Effectif par genre",
                           COULEURS_GENRE), 200, False)
    a = cur["tranche_age"].value_counts().reindex(ORDRE_AGE).fillna(0).reset_index()
    graphique(c[3], px.bar(a, x="tranche_age", y="count", text="count", title="Effectif par tranche d'âge",
                           color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 200)
    tuile(c[4], "Âge moyen", nb(cur["age"].mean(), 1))

    # Recrutements
    c = ligne("Recrutements", "🧲", "arrivees")
    arr = par["arrivee"].sum()
    tuile(c[1], "Arrivées (6 derniers mois)", nb(arr.get(per)), delta=evolution(arr, per))
    c[1].plotly_chart(sparkline(arr), width="stretch", config={"staticPlot": True})
    nv = cur[cur["arrivee"] == 1]
    graphique(c[2], anneau(nv["contrat"].value_counts().reset_index(), "contrat", "count", "Arrivées par contrat",
                           {"CDI": JAUNE, "CDD": GRIS}), 200, False)
    a = nv["tranche_age"].value_counts().reindex(ORDRE_AGE).fillna(0).reset_index()
    graphique(c[3], px.bar(a, x="tranche_age", y="count", text="count", title="Arrivées par tranche d'âge",
                           color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 200)
    graphique(c[4], anneau(nv["genre"].value_counts().reset_index(), "genre", "count", "Arrivées par genre",
                           COULEURS_GENRE), 200, False)

    # Départs
    c = ligne("Départs", "🚪", "analyse-departs")
    coh = cohorte(per)
    h = d[d["jeu"] == "historique"]
    dep = h.groupby("periode")["target"].sum()
    tuile(c[1], f"Départs à 6 mois (cohorte {coh})", nb(dep.get(coh)), delta=evolution(dep, coh), inverse=True)
    c[1].plotly_chart(sparkline(dep), width="stretch", config={"staticPlot": True})
    hc = h[h["periode"] == coh]
    partis = hc[hc["target"] == 1]
    graphique(c[2], anneau(partis["contrat"].value_counts().reset_index(), "contrat", "count", "Départs par contrat",
                           {"CDI": JAUNE, "CDD": GRIS}), 200, False)
    t = hc.groupby("grade")["target"].agg(taux="mean", departs="sum", n="size").reset_index()
    graphique(c[3], px.bar(t, x="grade", y="taux", text=[f"{pct(a)}<br>{int(b)}/{int(n)}" for a, b, n in
                                                          zip(t["taux"], t["departs"], t["n"])],
                           title="Taux de départ par grade", color_discrete_sequence=[JAUNE])
              .update_layout(xaxis_title=None, yaxis_visible=False), 200)
    t = hc.groupby("tranche_anciennete")["target"].agg(taux="mean", departs="sum", n="size").reindex(ORDRE_ANC).reset_index()
    graphique(c[4], px.bar(t, x="tranche_anciennete", y="taux",
                           text=[f"{pct(a, 0)}<br>{int(b)}/{int(n)}" if n == n else "" for a, b, n in
                                 zip(t["taux"], t["departs"], t["n"])],
                           title="Taux de départ par ancienneté", color_discrete_sequence=[JAUNE])
              .update_layout(xaxis_title=None, yaxis_visible=False), 200)
    if per not in PERIODES_HIST:
        st.markdown(f"<div class='note'>Les départs de la période {per} ne sont pas encore connus : "
                    f"les indicateurs de départ portent sur la dernière cohorte connue ({coh}).</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 2. Démographie
# ---------------------------------------------------------------------------
def p_demographie():
    d, per, _ = en_tete(2, "Analyse démographique", cle="demo")
    cur = d[d["periode"] == per]
    coh = cohorte(per)
    hc = d[(d["periode"] == coh) & (d["jeu"] == "historique")]
    c = st.columns([1, 1, 1, 1.2, 1, 1, 1.2])
    tuile(c[0], "Effectif", nb(len(cur)), "👥", detail=cur)
    tuile(c[1], "Arrivées", nb(cur["arrivee"].sum()), "🧲", detail=cur[cur["arrivee"] == 1])
    tuile(c[2], f"Départs ({coh})", nb(hc["target"].sum()), "🚪", detail=hc[hc["target"] == 1])
    g = cur["genre"].value_counts(normalize=True)
    tuile(c[3], "Femmes · Hommes", f"{pct(g.get('F', 0), 0)} · {pct(g.get('M', 0), 0)}", "⚥")
    tuile(c[4], "Ancienneté moy.", nb(cur["anciennete"].mean(), 1), "⏳")
    tuile(c[5], "Âge moyen", nb(cur["age"].mean(), 1), "🎂")
    cad = cur[cur["cadre"] == 1]
    tuile(c[6], "Femmes cadres (G4-G5)", pct((cad["genre"] == "F").mean()), "👩‍💼")
    st.write("")

    c1, c2, c3 = st.columns([1, 1.3, 1.5])
    with carte(c1):
        graphique(st, anneau(cur["contrat"].value_counts().reset_index(), "contrat", "count", "Par type de contrat",
                             {"CDI": JAUNE, "CDD": GRIS}), 240)
    with carte(c2):
        gc = cur.groupby(["grade", "contrat"]).size().reset_index(name="n")
        graphique(st, px.bar(gc, y="grade", x="n", color="contrat", orientation="h", text="n",
                             title="Grade × type de contrat", color_discrete_map={"CDI": JAUNE, "CDD": GRIS},
                             category_orders={"grade": ["G5", "G4", "G3", "G2", "G1"]})
                  .update_layout(xaxis_title=None, yaxis_title=None), 240)
    with carte(c3):
        tv = d[d["jeu"] == "historique"].groupby("periode")["target"].mean().reset_index()
        ab = d.groupby("periode")["taux_absenteisme"].mean().reset_index()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=tv["periode"], y=tv["target"], name="Taux de départ à 6 mois",
                                 mode="lines+markers", line=dict(color=JAUNE, width=3)))
        fig.add_trace(go.Scatter(x=ab["periode"], y=ab["taux_absenteisme"], name="Taux d'absentéisme",
                                 mode="lines+markers", line=dict(color=GRIS, dash="dot")))
        fig.update_layout(title="Départs et absentéisme par période", yaxis_tickformat=".0%")
        graphique(st, fig, 240)

    c1, c2, c3 = st.columns([1, 1.3, 1.5])
    with carte(c1):
        v = cur["ville_affectation"].value_counts().sort_values().reset_index()
        graphique(st, px.bar(v, y="ville_affectation", x="count", orientation="h", text="count", title="Par ville",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_visible=False, yaxis_title=None), 260)
    with carte(c2):
        s = cur["tranche_salaire"].value_counts().reindex(ORDRE_SAL).fillna(0).reset_index()
        fig = px.funnel(s, y="tranche_salaire", x="count", title="Tranches de salaire mensuel (FCFA)",
                        color_discrete_sequence=[JAUNE])
        graphique(st, fig.update_layout(yaxis_title=None), 260)
    with carte(c3):
        a = cur["tranche_anciennete"].value_counts().reindex(ORDRE_ANC).fillna(0).reset_index()
        graphique(st, px.bar(a, x="tranche_anciennete", y="count", text="count", title="Par ancienneté",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 260)


# ---------------------------------------------------------------------------
# 3. Diversité
# ---------------------------------------------------------------------------
def p_diversite():
    d, per, _ = en_tete(3, "Analyse de la diversité", cle="div")
    cur = d[d["periode"] == per]
    c1, c2, c3 = st.columns([1, 1.6, 1.2])
    with carte(c1):
        nv = cur[cur["arrivee"] == 1].groupby(["generation", "genre"]).size().reset_index(name="n")
        graphique(st, px.bar(nv, x="generation", y="n", color="genre", text="n", title="Arrivées par génération",
                             color_discrete_map=COULEURS_GENRE).update_layout(xaxis_title=None, yaxis_visible=False), 230)
    with carte(c2):
        gg = cur.groupby(["grade", "generation"]).size().reset_index(name="n")
        graphique(st, px.bar(gg, x="grade", y="n", color="generation", barmode="group", text="n",
                             title="Grade × génération",
                             color_discrete_map={"Génération Z": GRIS_CLAIR, "Génération Y": JAUNE, "Génération X": GRIS})
                  .update_layout(xaxis_title=None, yaxis_visible=False), 230)
    with carte(c3):
        gr = cur.groupby(["grade", "genre"]).size().reset_index(name="n")
        graphique(st, px.bar(gr, x="grade", y="n", color="genre", text="n", title="Grade × genre",
                             color_discrete_map=COULEURS_GENRE).update_layout(xaxis_title=None, yaxis_visible=False), 230)

    c1, c2, c3, c4 = st.columns([1, 1.3, 1.2, 1.2])
    with carte(c1):
        graphique(st, anneau(cur["niveau_etude"].value_counts().reset_index(), "niveau_etude", "count",
                             "Niveau d'études"), 270)
    with carte(c2):
        vg = cur.groupby(["ville_affectation", "genre"]).size().reset_index(name="n")
        vg["part"] = vg["n"] / vg.groupby("ville_affectation")["n"].transform("sum")
        graphique(st, px.bar(vg, y="ville_affectation", x="part", color="genre", orientation="h",
                             text=vg["part"].map(lambda v: pct(v, 0)), title="Diversité de genre par ville",
                             color_discrete_map=COULEURS_GENRE)
                  .update_layout(xaxis_visible=False, yaxis_title=None), 270)
    with carte(c3):
        fc = d.groupby("periode").apply(lambda x: (x.loc[x["cadre"] == 1, "genre"] == "F").mean()).reset_index(name="p")
        fig = px.area(fc, x="periode", y="p", title="% de femmes parmi les cadres", markers=True,
                      text=fc["p"].map(pct), color_discrete_sequence=[JAUNE])
        graphique(st, fig.update_traces(textposition="top center").update_layout(
            xaxis_title=None, yaxis_title=None, yaxis_tickformat=".0%"), 270)
    with carte(c4):
        ga = cur.groupby(["grade", "tranche_age"]).size().reset_index(name="n")
        graphique(st, px.bar(ga, x="grade", y="n", color="tranche_age", title="Grade × tranche d'âge",
                             category_orders={"tranche_age": ORDRE_AGE},
                             color_discrete_sequence=[GRIS_CLAIR, JAUNE_CLAIR, JAUNE, "#E05A00", GRIS, GRIS_FONCE, "#333"])
                  .update_layout(xaxis_title=None, yaxis_visible=False), 270)


# ---------------------------------------------------------------------------
# 4. Fiche collaborateur
# ---------------------------------------------------------------------------
DOSSIER_AVATARS = Path(__file__).with_name("avatars")


def tranche_avatar(age):
    if pd.isna(age):
        return "30_39"
    return "moins30" if age < 30 else "30_39" if age < 40 else "40_49" if age < 50 else "50plus"


@st.cache_data
def _avatars_disponibles():
    return {(g, t): sorted(DOSSIER_AVATARS.glob(f"{g}_{t}_*.svg"))
            for g in ("F", "M") for t in ("moins30", "30_39", "40_49", "50plus")}


def avatar(genre, identifiant="", age=None, taille=132):
    """Avatar illustré (DiceBear, style Avataaars) choisi selon le genre et la tranche d'âge
    (moins de 30 ans, 30-39, 40-49, 50 et plus) ; dans une tranche, la variante dépend de l'identifiant.
    Genre non renseigné : silhouette neutre."""
    fichiers = _avatars_disponibles().get((genre, tranche_avatar(age))) or []
    if fichiers:
        f = fichiers[sum(map(ord, str(identifiant))) % len(fichiers)]
        donnees_svg = base64.b64encode(f.read_bytes()).decode()      # en image : Streamlit filtre les masques SVG
        return f"<img src='data:image/svg+xml;base64,{donnees_svg}' width='{taille}' height='{taille}' alt=''>"
    return (f"<svg viewBox='0 0 120 120' width='{taille}' height='{taille}' aria-hidden='true'><defs><clipPath id='rond'>"
            f"<circle cx='60' cy='60' r='60'/></clipPath></defs><g clip-path='url(#rond)'>"
            f"<rect width='120' height='120' fill='#FF7900'/>"
            f"<path d='M16 122 C18 99 37 90 60 90 C83 90 102 99 104 122 Z' fill='#2B2B2B'/>"
            f"<circle cx='60' cy='54' r='20' fill='#2B2B2B'/></g></svg>")


def indicateurs(groupes, par_ligne=None):
    """Indicateurs illustrés (icône, valeur, libellé) ; groupes = [(titre ou None, [(icône, valeur, libellé, note)])]."""
    html = "<div class='indic'>" if not par_ligne else f"<div class='indic' style='--par-ligne:{par_ligne}'>"
    for titre, items in groupes:
        html += "<div class='indic-groupe'>" + (f"<div class='indic-titre'>{titre}</div>" if titre else "")
        html += "<div class='indic-ligne'>"
        for icone, valeur, libelle, note in items:
            html += (f"<div class='indic-item'><div class='indic-ico'>{ico(icone)}</div>"
                     f"<div class='indic-val'>{valeur}</div><div class='indic-lib'>{libelle}</div>"
                     + (f"<div class='indic-note'>{note}</div>" if note else "") + "</div>")
        html += "</div></div>"
    st.markdown(html + "</div>", unsafe_allow_html=True)


def liste_alignee(rows):
    """Champs « libellé : valeur » alignés, à la manière d'une fiche (sans tableau)."""
    st.markdown("<div class='fiche-liste'>" + "".join(
        f"<div class='fl-lib'>{a}</div><div class='fl-sep'>:</div><div class='fl-val'>{b}</div>" for a, b in rows)
        + "</div>", unsafe_allow_html=True)


def p_fiche():
    _, _, dep = en_tete(7, "Fiche collaborateur", periodes=None, cle="fiche")
    act, contrib = modele_risque()
    sc = act if dep == "Tous" else act[act["departement"] == dep]
    sc = sc.sort_values("probabilite", ascending=False)
    ids = sc["id"].tolist()
    defaut = ids.index(st.session_state["fiche_id"]) if st.session_state.get("fiche_id") in ids else 0
    choix = st.selectbox("Collaborateur (du score le plus élevé au plus faible)", ids, index=defaut,
                         format_func=lambda i: f"{i} · {sc.loc[sc['id'] == i, 'poste'].iloc[0]} · "
                                               f"{sc.loc[sc['id'] == i, 'departement'].iloc[0]} · "
                                               f"{sc.loc[sc['id'] == i, 'niveau_risque'].iloc[0]}")
    st.session_state["fiche_id"] = choix
    k = act.index[act["id"] == choix][0]
    p = act.loc[k]
    pairs = act[act["departement"] == p["departement"]]
    taux, _, _ = fiabilite()
    tn = taux.loc[p["niveau_risque"]]
    gauche, droite = st.columns([1, 2.6])
    with gauche:
        couleur = COULEURS_NIVEAU[p["niveau_risque"]]
        texte = "white" if p["niveau_risque"] == "Très élevé" else "#222"
        st.markdown(
            f"<div style='background:#fff;border:1px solid #E6E6E6;border-radius:12px;padding:14px;min-height:430px'>"
            f"<div style='background:{couleur};color:{texte};text-align:center;font-weight:700;border-radius:4px;"
            f"padding:4px'>Niveau de risque : {p['niveau_risque'].lower()}</div>"
            f"<div style='display:flex;justify-content:center;margin:16px auto 12px auto'>{avatar(p['genre'], p['id'], p['age'])}</div>"
            f"<b>{p['id']}</b><br><span class='note'>Identifiant</span><br><br>"
            f"<b>{p['poste']}</b><br><span class='note'>Poste</span><br><br>"
            f"<b>{p['departement']}</b> · {p['grade']} · {p['contrat']}<br><span class='note'>Département · grade · contrat</span><br><br>"
            f"<b>Score plus élevé que {nb((1 - p['rang_haut'] - 1 / len(act)) * 100, 1)} %</b><br>"
            f"<span class='note'>des collaborateurs au 31/12/2024</span></div>",
            unsafe_allow_html=True)
        st.write("")
        prete = st.session_state.get("fiche_entretien", (None, None))
        if prete[0] != p["id"]:
            if st.button("Préparer la fiche entretien", icon=":material/description:", width="stretch",
                         help="Une page PDF à imprimer avant un entretien de rétention"):
                with st.spinner("Mise en page de la fiche…"):
                    sig, nua, man = explication(contrib.loc[k], p, act)
                    st.session_state["fiche_entretien"] = (p["id"], rapport.fiche_entretien(
                        p, sig, nua, man, tn["taux"], {"engagement_median": pairs["engagement_actuel"].median()},
                        {"utilisateur": auth.utilisateur()["nom"]}))
                st.rerun()
        else:
            st.download_button("Télécharger la fiche entretien (PDF)", prete[1], f"TelcomCI_fiche_entretien_{p['id']}.pdf",
                               "application/pdf", type="primary", width="stretch", icon=":material/download:",
                               on_click=lambda: st.toast("Fiche entretien téléchargée", icon=":material/check_circle:"))
    with droite:
        o = st.tabs(["Informations", "Poste", "Rémunération", "Absences", "Performance & engagement",
                     "Pourquoi ce signal ?"])

        def lignes(rows):
            st.dataframe(pd.DataFrame(rows, columns=["", "Valeur"]), hide_index=True, width="stretch")
        with o[5]:
            st.markdown(
                f"Lors des validations sur les 3 dernières cohortes, <b>{pct(tn['taux'], 0)}</b> des "
                f"collaborateurs classés « {p['niveau_risque']} » sont effectivement partis dans les 6 mois "
                f"(entre {pct(tn['taux_min'], 0)} et {pct(tn['taux_max'], 0)} selon la cohorte). "
                f"C'est un taux de groupe : il ne dit rien des intentions de cette personne.",
                unsafe_allow_html=True)
            signaux, nuances, manquants = explication(contrib.loc[k], p, act)
            tableau = [(x["famille"], "Augmente le score", x["intensite"], x["valeur"], x["reference"]) for x in signaux]
            tableau += [(x["famille"], "Nuance le signal", x["intensite"], x["valeur"], x["reference"]) for x in nuances]
            if tableau:
                st.table(pd.DataFrame(tableau, columns=["Élément", "Effet sur le score", "Intensité",
                                                        "Valeur du collaborateur", "Référence"]).style.hide(axis="index"))
            else:
                st.markdown("<div class='note'>Aucun élément ne se distingue nettement.</div>", unsafe_allow_html=True)
            verif = [("Donnée non renseignée", f"{m} (n'est pas comptée comme une valeur faible)") for m in manquants]
            verif.append(("Contexte récent", "changement de poste, de manager, situation personnelle : absent des "
                                             "données, seul un échange permet de le connaître"))
            st.markdown("**À vérifier humainement**")
            st.table(pd.DataFrame(verif, columns=["Point", "Détail"]).style.hide(axis="index"))
            st.markdown("<div class='note'>Les effets sont mesurés par rapport à un collaborateur moyen de TelcomCI. "
                        "Ils expliquent le calcul du score ; ce sont des associations statistiques, pas des causes. "
                        "Le genre n'est pas utilisé par ce modèle. Aucune décision défavorable ne peut être fondée "
                        "sur ce score.</div>", unsafe_allow_html=True)
        with o[0]:
            liste_alignee([("Genre", {"F": "Femme", "M": "Homme"}.get(p["genre"], "Non renseigné")),
                           ("Âge", f"{nb(p['age'])} ans"), ("Génération", p["generation"]),
                           ("Niveau d'études", p["niveau_etude"]), ("Ville", p["ville_affectation"]),
                           ("Site", p["code_site"])])
        with o[1]:
            promo = "Jamais promu" if p["jamais_promu"] else f"il y a {nb(p['annees_depuis_promotion'], 1)} ans"
            indicateurs([(None, [("work", p["poste"], "Poste", None),
                                 ("apartment", p["departement"], "Département", None),
                                 ("military_tech", p["grade"], "Grade", "cadre" if p["grade"] in ("G4", "G5") else None),
                                 ("description", p["contrat"], "Contrat", None),
                                 ("hourglass_bottom", f"{nb(p['anciennete'], 1)} ans", "Ancienneté", None),
                                 ("upgrade", promo, "Dernière promotion", None)])], par_ligne=3)
        with o[2]:
            meme_grade = act[act["grade"] == p["grade"]]
            ratio, med = p["ratio_salaire_reference"], meme_grade["ratio_salaire_reference"].median()
            evo = p["taux_evolution_salaire"]
            indicateurs([(None, [
                ("payments", f"{fcfa(p['salaire_mensuel'])} FCFA", "Salaire mensuel", None),
                ("balance", f"{fcfa(p['reference_salaire_grade'])} FCFA", f"Référence du grade {p['grade']}", None),
                ("bar_chart", nb(ratio, 2), "Salaire / référence",
                 f"médiane du grade : {nb(med, 2)}" + (" · en dessous" if ratio < med else " · au-dessus" if ratio > med else "")),
                ("trending_up" if evo > 0 else "trending_down" if evo < 0 else "trending_flat", pct(evo),
                 "Évolution sur 12 mois", None)])])
        with o[3]:
            taux_dep = pairs["taux_absenteisme"].mean()
            indicateurs([("6 derniers mois", [
                            ("event_busy", nb(p["jours_abs_6m"], 1), "Jours d'absence", None),
                            ("sick", nb(p["abs_non_just_6m"], 1), "Jours non justifiés", None),
                            ("repeat", nb(p["nb_abs_6m"]), "Absences distinctes", None)]),
                         ("Comparaison", [
                            ("schedule", pct(p["taux_absenteisme"], 2), "Taux d'absentéisme", None),
                            ("groups", pct(taux_dep, 2), f"Moyenne {p['departement']}", None)])])
            m = pd.DataFrame({"mois": [f"M-{i}" for i in range(5, -1, -1)],
                              "Toutes absences": [p[f"jours_abs_m{i}"] for i in range(6, 0, -1)],
                              "Non justifiées": [p[f"abs_non_just_m{i}"] for i in range(6, 0, -1)]})
            if m[["Toutes absences", "Non justifiées"]].fillna(0).to_numpy().sum() == 0:
                st.markdown("<div class='pastille-note'>Aucune absence sur les 6 derniers mois</div>", unsafe_allow_html=True)
            else:
              with carte(st):
                graphique(st, px.bar(m.melt("mois", var_name="type", value_name="jours"), x="mois", y="jours",
                                     color="type", barmode="group", title="Jours d'absence des 6 derniers mois",
                                     color_discrete_map={"Toutes absences": GRIS, "Non justifiées": JAUNE})
                          .update_layout(xaxis_title=None, yaxis_title="jours"), 260)
        with o[4]:
            cat = p.get("categorie_perf")
            cat = cat if isinstance(cat, str) and cat != "nan" else "non évaluée"
            st.markdown(f"<div class='pastille-note'>Niveau de performance : <b>{cat}</b></div>", unsafe_allow_html=True)
            def fleche(a, b):
                return "" if pd.isna(a) or pd.isna(b) else (" ↗" if a > b else " ↘" if a < b else " →")
            indicateurs([(None, [
                ("star", nb(p["performance_actuelle"], 2) + fleche(p["performance_actuelle"], p["performance_precedente"]),
                 "Performance actuelle", "sur 5"),
                ("history", nb(p["performance_precedente"], 2), "Performance précédente", None),
                ("mood", nb(p["engagement_actuel"], 2) + fleche(p["engagement_actuel"], p["engagement_precedent"]),
                 "Engagement actuel", f"précédent : {nb(p['engagement_precedent'], 2)}"),
                ("groups", nb(pairs["engagement_actuel"].median(), 2), f"Engagement médian {p['departement']}", None)])])


# ---------------------------------------------------------------------------
# 5. Historique et tendances
# ---------------------------------------------------------------------------
def p_tendances():
    d, per, _ = en_tete(5, "Historique et tendances", cle="tend")
    cur = d[d["periode"] == per]
    coh = cohorte(per)
    hc = d[(d["periode"] == coh) & (d["jeu"] == "historique")]
    c1, c2, c3 = st.columns([1, 1.4, 1.4])
    with c1:
        t = st.columns(2)
        tuile(t[0], "Effectif", nb(len(cur)), "👥")
        tuile(t[1], f"Départs ({coh})", nb(hc["target"].sum()), "🚪")
        with carte(st):
            gp = d.groupby(["periode", "genre"]).size().reset_index(name="n")
            graphique(st, px.bar(gp[gp["genre"] != "INCONNU"], x="periode", y="n", color="genre", text="n",
                                 title="Effectif par genre", color_discrete_map=COULEURS_GENRE)
                      .update_layout(xaxis_title=None, yaxis_visible=False), 260)
    with carte(c2):
        dp = d[d["jeu"] == "historique"].groupby("periode")["target"].sum().reset_index()
        fig = px.line(dp, x="periode", y="target", markers=True, text="target", title="Départs à 6 mois par cohorte",
                      color_discrete_sequence=[JAUNE])
        graphique(st, fig.update_traces(textposition="top center", line_width=3)
                  .update_layout(xaxis_title=None, yaxis_title=None), 360)
    with carte(c3):
        eff = d.groupby("periode").size()
        var = eff.pct_change().dropna()
        fig = go.Figure(go.Waterfall(x=list(var.index), y=list(var.values * 100), measure=["relative"] * len(var),
                                     text=[pct(v) for v in var.values], textposition="outside",
                                     increasing=dict(marker_color=JAUNE), decreasing=dict(marker_color=GRIS)))
        fig.update_layout(title="Évolution de l'effectif d'une période à l'autre (%)", yaxis_ticksuffix=" %")
        graphique(st, fig, 360, False)

    c1, c2, c3 = st.columns([1, 1.4, 1.4])
    with carte(c1):
        e = d.groupby("periode").size().reset_index(name="n")
        graphique(st, px.bar(e, x="periode", y="n", text="n", title="Effectif par période",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 280)
    with carte(c2):
        ga = cur.groupby(["grade", "tranche_age"]).size().reset_index(name="n")
        graphique(st, px.bar(ga, x="grade", y="n", color="tranche_age", barmode="group",
                             title=f"Grade × tranche d'âge ({per})", category_orders={"tranche_age": ORDRE_AGE},
                             color_discrete_sequence=[GRIS_CLAIR, JAUNE_CLAIR, JAUNE, "#E05A00", GRIS, GRIS_FONCE, "#333"])
                  .update_layout(xaxis_title=None, yaxis_visible=False), 280)
    with carte(c3):
        dg = d[(d["jeu"] == "historique") & (d["target"] == 1)].groupby(["periode", "genre"]).size() \
            .unstack(fill_value=0).reindex(columns=["F", "M"], fill_value=0)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=dg.index, x=-dg["F"], name="Femmes", orientation="h", marker_color=JAUNE,
                             text=dg["F"], textposition="inside"))
        fig.add_trace(go.Bar(y=dg.index, x=dg["M"], name="Hommes", orientation="h", marker_color=GRIS,
                             text=dg["M"], textposition="inside"))
        fig.update_layout(barmode="relative", title="Départs par genre et par cohorte", xaxis_visible=False)
        graphique(st, fig, 280)


# ---------------------------------------------------------------------------
# 6. Nouveaux arrivants
# ---------------------------------------------------------------------------
def p_arrivees():
    d, per, _ = en_tete(6, "Analyse des nouveaux arrivants", cle="arr")
    cur = d[d["periode"] == per]
    nv = cur[cur["arrivee"] == 1]
    c = st.columns([1, 1.3, 1, 1])
    tuile(c[0], "Arrivées (6 derniers mois)", nb(len(nv)), "🧲", detail=nv)
    tuile(c[1], "Femmes parmi les arrivées", pct((nv["genre"] == "F").mean()), "👩")
    tuile(c[2], "Arrivées par mois", nb(len(nv) / 6, 1), "📅")
    tuile(c[3], "En CDI", pct((nv["contrat"] == "CDI").mean()), "📝")
    st.write("")
    c1, c2, c3 = st.columns([1, 1.6, 1.4])
    with carte(c1):
        graphique(st, anneau(nv["genre"].value_counts().reset_index(), "genre", "count", "Par genre",
                             COULEURS_GENRE), 250)
    with carte(c2):
        a = d.groupby("periode")["arrivee"].sum().reset_index()
        fig = px.line(a, x="periode", y="arrivee", markers=True, text="arrivee", title="Tendance des arrivées",
                      color_discrete_sequence=[JAUNE])
        graphique(st, fig.update_traces(textposition="top center", line_width=3)
                  .update_layout(xaxis_title=None, yaxis_title=None), 250)
    with carte(c3):
        gg = nv.groupby(["grade", "genre"]).size().reset_index(name="n")
        graphique(st, px.bar(gg, y="grade", x="n", color="genre", orientation="h", text="n", title="Par grade",
                             color_discrete_map=COULEURS_GENRE, category_orders={"grade": ["G5", "G4", "G3", "G2", "G1"]})
                  .update_layout(xaxis_visible=False, yaxis_title=None), 250)
    c1, c2, c3 = st.columns([1, 1.6, 1.4])
    with carte(c1):
        a = nv["tranche_age"].value_counts().reindex(ORDRE_AGE).fillna(0).reset_index()
        graphique(st, px.bar(a, x="tranche_age", y="count", text="count", title="Par tranche d'âge",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 280)
    with carte(c2):
        a = d.groupby("periode")["arrivee"].sum()
        p_ = d[d["jeu"] == "historique"].groupby("periode")["target"].sum()
        av = pd.DataFrame({"Arrivées": a, "Départs à 6 mois": p_}).reset_index()
        fig = px.bar(av, x="periode", y="Arrivées", text="Arrivées", title="Arrivées et départs",
                     color_discrete_sequence=[JAUNE])
        fig.add_trace(go.Scatter(x=av["periode"], y=av["Départs à 6 mois"], name="Départs à 6 mois",
                                 mode="lines+markers", line=dict(color=GRIS, width=3)))
        fig.data[0].name, fig.data[0].showlegend = "Arrivées", True
        graphique(st, fig.update_layout(xaxis_title=None, yaxis_title=None), 280)
    with carte(c3):
        t = cur.groupby("departement")["arrivee"].mean().sort_values(ascending=False).head(5).reset_index()
        graphique(st, px.bar(t, x="departement", y="arrivee", text=t["arrivee"].map(pct),
                             title="Top 5 départements : part d'arrivées", color_discrete_sequence=[JAUNE])
                  .update_layout(xaxis_title=None, yaxis_visible=False), 280)


# ---------------------------------------------------------------------------
# 7. Analyse salariale
# ---------------------------------------------------------------------------
def p_salaires():
    d, per, _ = en_tete(7, "Analyse salariale", cle="sal")
    cur = d[d["periode"] == per]
    c = st.columns(4)
    par = d.groupby("periode")
    masse_per, moy_per, med_per = par["salaire_mensuel"].sum(), par["salaire_mensuel"].mean(), par["salaire_mensuel"].median()
    sexe = d[d["genre"].isin(["F", "M"])].groupby(["periode", "genre"])["salaire_mensuel"].mean().unstack()
    tuile(c[0], "Masse salariale mensuelle (FCFA)", fcfa(cur["salaire_mensuel"].sum()), "💰", evolution(masse_per, per))
    tuile(c[1], "Salaire moyen (FCFA)", fcfa(cur["salaire_mensuel"].mean()), "👤", evolution(moy_per, per))
    tuile(c[2], "Salaire moyen · hommes", fcfa(cur.loc[cur["genre"] == "M", "salaire_mensuel"].mean()), "👨",
          evolution(sexe["M"], per) if "M" in sexe else None)
    tuile(c[3], "Salaire moyen · femmes", fcfa(cur.loc[cur["genre"] == "F", "salaire_mensuel"].mean()), "👩",
          evolution(sexe["F"], per) if "F" in sexe else None)
    st.write("")
    with carte(st):
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=masse_per.index, y=masse_per.values, name="Masse salariale mensuelle",
                             marker_color=[JAUNE if p_ == per else "#D6D6D6" for p_ in masse_per.index],
                             text=[fcfa(v) for v in masse_per.values], textposition="inside", insidetextanchor="end",
                             textfont=dict(color=["#000" if p_ == per else "#333" for p_ in masse_per.index])),
                      secondary_y=False)
        fig.add_trace(go.Scatter(x=med_per.index, y=med_per.values, name="Salaire médian", mode="lines+markers+text",
                                 text=[fcfa(v) for v in med_per.values], textposition="top center",
                                 line=dict(color=GRIS_FONCE, width=2.5)), secondary_y=True)
        fig.update_yaxes(visible=False, secondary_y=False, range=[0, masse_per.max() * 1.6])
        ecart = max(med_per.max() - med_per.min(), med_per.max() * .02)
        fig.update_yaxes(visible=False, secondary_y=True, range=[med_per.min() - 3.2 * ecart, med_per.max() + .5 * ecart])
        hausse = masse_per.iloc[-1] / masse_per.iloc[0] - 1 if len(masse_per) > 1 and masse_per.iloc[0] else None
        fig.update_layout(title=f"Évolution de la masse salariale et du salaire médian"
                                + (f" · {pct(hausse, 0)} depuis {masse_per.index[0]}" if hausse is not None else ""))
        graphique(st, fig, 290)
    c1, c2, c3 = st.columns([1.8, 1, 1.3])
    with carte(c1):
        dep = cur.groupby("departement")["salaire_mensuel"].agg(["sum", "mean"]).sort_values("sum", ascending=False)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=dep.index, y=dep["sum"], name="Masse salariale", marker_color=JAUNE,
                             text=[fcfa(v) for v in dep["sum"]]), secondary_y=False)
        fig.add_trace(go.Scatter(x=dep.index, y=dep["mean"], name="Salaire moyen", mode="lines+markers",
                                 line=dict(color=GRIS_FONCE), text=[fcfa(v) for v in dep["mean"]]), secondary_y=True)
        fig.update_layout(title="Répartition des salaires par département")
        graphique(st, fig, 300)
    with c2:
        top = cur.groupby("ville_affectation")["salaire_mensuel"].mean().sort_values(ascending=False)
        tuile(st, f"Salaire moyen le plus élevé · {top.index[0]}", f"{fcfa(top.iloc[0])} FCFA", "🏢")
        st.write("")
        with carte(st):
            v = top.sort_values().reset_index()
            graphique(st, px.bar(v, y="ville_affectation", x="salaire_mensuel", orientation="h",
                                 text=v["salaire_mensuel"].map(fcfa), title="Salaire moyen par ville",
                                 color_discrete_sequence=[JAUNE]).update_layout(xaxis_visible=False, yaxis_title=None), 190)
    with carte(c3):
        g = cur.groupby("grade")["salaire_mensuel"].agg(q1=lambda x: x.quantile(.25), med="median",
                                                         q3=lambda x: x.quantile(.75), n="size").reset_index()
        fig = go.Figure(go.Bar(y=g["grade"], x=g["med"], orientation="h", marker_color=JAUNE,
                               error_x=dict(type="data", symmetric=False, array=g["q3"] - g["med"],
                                            arrayminus=g["med"] - g["q1"], color=GRIS_FONCE, thickness=1.2),
                               text=[f"{fcfa(m)} (n={n})" for m, n in zip(g["med"], g["n"])], textposition="inside",
                               insidetextanchor="start"))
        fig.update_layout(title="Salaire médian par grade (trait : 1er–3e quartile)", yaxis_autorange="reversed")
        graphique(st, fig.update_layout(xaxis_title="FCFA", yaxis_title=None), 300, False)
    c1, c2 = st.columns([1.5, 1.4])
    with carte(c1):
        ag = cur[cur["genre"].isin(["F", "M"])].groupby(["tranche_age", "genre"])["salaire_mensuel"].mean().reset_index()
        ag = ag.sort_values("tranche_age", key=lambda x: x.map({t: i for i, t in enumerate(ORDRE_AGE)}))
        fig = px.line(ag, x="tranche_age", y="salaire_mensuel", color="genre", title="Salaire moyen par âge et par genre",
                      category_orders={"tranche_age": ORDRE_AGE}, color_discrete_map=COULEURS_GENRE, markers=True)
        fig.update_traces(line_width=3)
        graphique(st, fig.update_layout(xaxis_title=None, yaxis_title="FCFA"), 280)
    with carte(c2):
        titre_tableau("Top 10 des postes par salaire moyen", "postes d'au moins 5 collaborateurs")
        t = cur.groupby("poste")["salaire_mensuel"].agg(moyenne="mean", effectif="size")
        t = t[t["effectif"] >= 5].sort_values("moyenne", ascending=False).head(10).reset_index()
        t = t.rename(columns={"poste": "Poste", "moyenne": "Salaire moyen (FCFA)", "effectif": "Effectif"})
        st.dataframe(zebre(t), hide_index=True, width="stretch", height=250,
                     column_config={"Salaire moyen (FCFA)": st.column_config.ProgressColumn(
                         format="%.0f", min_value=0, max_value=float(t["Salaire moyen (FCFA)"].max()), color="#FF7900")})
    f = faits()
    pont(f"les collaborateurs payés sous 90 % de la référence de leur grade sont partis à <b>{pct(f['dep_sous90'])}</b> "
         f"contre {pct(f['dep_sur90'])} pour les autres (cohorte {f['coh']}). Le positionnement salarial figure parmi "
         f"les principaux facteurs de départ de <b>{pct(f['part_sal'], 0)}</b> des collaborateurs signalés.", "anticipation")


# ---------------------------------------------------------------------------
# 8. Écart salarial femmes / hommes
# ---------------------------------------------------------------------------
def p_ecart():
    d, per, _ = en_tete(8, "Écart salarial femmes / hommes", cle="gap")
    cur = d[(d["periode"] == per) & d["genre"].isin(["F", "M"])]
    moy = cur.groupby("genre")["salaire_mensuel"].mean()
    c1, c2, c3 = st.columns([0.9, 1.4, 2])
    with c1:
        tuile(st, "Écart de salaire moyen H − F (FCFA)", nb(moy.get("M", np.nan) - moy.get("F", np.nan)), "⚥")
        st.write("")
        with carte(st):
            nmoy = cur.groupby("genre")["salaire_mensuel"].agg(["mean", "size"]).reset_index()
            graphique(st, px.bar(nmoy, x="genre", y="mean", color="genre", color_discrete_map=COULEURS_GENRE,
                                 text=[f"{fcfa(m)}<br>n={n}" for m, n in zip(nmoy["mean"], nmoy["size"])],
                                 title="Salaire moyen par genre (FCFA)")
                      .update_layout(xaxis_title=None, yaxis_visible=False), 230, False)
    with carte(c2):
        ag = cur.groupby(["tranche_age", "genre"])["salaire_mensuel"].mean().reset_index()
        fig = px.line(ag, x="tranche_age", y="salaire_mensuel", color="genre", markers=True,
                      title="Par tranche d'âge", category_orders={"tranche_age": ORDRE_AGE},
                      color_discrete_map=COULEURS_GENRE)
        graphique(st, fig.update_layout(xaxis_title=None, yaxis_title="FCFA"), 330)
    with carte(c3):
        dg = cur.groupby(["departement", "genre"])["salaire_mensuel"].mean().reset_index()
        graphique(st, px.bar(dg, y="departement", x="salaire_mensuel", color="genre", orientation="h",
                             text=dg["salaire_mensuel"].map(fcfa), title="Par département",
                             color_discrete_map=COULEURS_GENRE)
                  .update_layout(xaxis_visible=False, yaxis_title=None), 330)
    c1, c2, c3 = st.columns([1, 1.4, 2])
    with carte(c1):
        gg = cur.groupby(["grade", "genre"])["salaire_mensuel"].mean().unstack()
        gg["Écart F/H"] = gg["F"] / gg["M"] - 1
        titre_tableau("Salaire moyen par grade", "écart F/H : rouge si les femmes gagnent moins, vert sinon")
        tg = gg.reset_index().rename(columns={"grade": "Grade", "F": "Femmes", "M": "Hommes"})
        sty = zebre(tg).map(lambda v: "color: #CD3C14; font-weight: bold" if v < -0.02 else
                            ("color: #1E7B4C; font-weight: bold" if v > 0.02 else ""), subset=["Écart F/H"])
        st.dataframe(sty, hide_index=True, width="stretch", column_config={
                         "Femmes": barre("Femmes", tg[["Femmes", "Hommes"]].max().max()),
                         "Hommes": barre("Hommes", tg[["Femmes", "Hommes"]].max().max()),
                         "Écart F/H": st.column_config.NumberColumn(format="percent")})
    with carte(c2):
        vg = cur.groupby(["ville_affectation", "genre"])["salaire_mensuel"].mean().reset_index()
        graphique(st, px.bar(vg, x="ville_affectation", y="salaire_mensuel", color="genre", barmode="group",
                             title="Par ville", color_discrete_map=COULEURS_GENRE)
                  .update_layout(xaxis_title=None, yaxis_title="FCFA"), 270)
    with carte(c3):
        piv = cur.groupby(["departement", "grade", "genre"])["salaire_mensuel"].mean().unstack()
        ecart = (piv["F"] - piv["M"]).reset_index(name="ecart").dropna()
        graphique(st, px.bar(ecart, x="departement", y="ecart", color="grade", barmode="group",
                             title="Écart F − H à grade égal, par département (FCFA)",
                             color_discrete_sequence=[GRIS_CLAIR, JAUNE_CLAIR, JAUNE, GRIS, GRIS_FONCE])
                  .update_layout(xaxis_title=None, yaxis_title=None), 270)


# ---------------------------------------------------------------------------
# 9. Évaluation de la performance (Expectation Rating)
# ---------------------------------------------------------------------------
def p_performance():
    d, per, _ = en_tete(9, "Évaluation de la performance", cle="perf")
    cat = st.segmented_control("Niveau de performance", ["Toutes"] + ORDRE_PERF, default="Toutes", key="cat_perf",
                               label_visibility="collapsed") or "Toutes"
    cur = d[d["periode"] == per]
    sel = cur if cat == "Toutes" else cur[cur["categorie_perf"] == cat]
    coh = cohorte(per)
    hc = d[(d["periode"] == coh) & (d["jeu"] == "historique")]
    hs = hc if cat == "Toutes" else hc[hc["categorie_perf"] == cat]
    c1, c2, c3, c4 = st.columns([0.9, 0.9, 1.5, 1.6])
    with c1:
        tuile(st, f"Départs à 6 mois ({coh}) · CDI {nb(hs.loc[hs['contrat'] == 'CDI', 'target'].sum())} · "
                  f"CDD {nb(hs.loc[hs['contrat'] == 'CDD', 'target'].sum())}", nb(hs["target"].sum()), "🚪")
        st.write("")
        tuile(st, "Taux de départ", pct(hs["target"].mean()), "📉")
    with c2:
        tuile(st, "Effectif", nb(len(sel)), "👥")
        st.write("")
        tuile(st, "% de nouveaux arrivants", pct(sel["arrivee"].mean()), "🧲")
    with carte(c3):
        gg = sel.groupby(["grade", "genre"]).size().unstack(fill_value=0).reindex(columns=["F", "M"], fill_value=0)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=gg.index, x=-gg["F"], name="Femmes", orientation="h", marker_color=JAUNE,
                             text=gg["F"], textposition="inside"))
        fig.add_trace(go.Bar(y=gg.index, x=gg["M"], name="Hommes", orientation="h", marker_color=GRIS,
                             text=gg["M"], textposition="inside"))
        fig.update_layout(barmode="relative", title="Effectif par grade et par genre", xaxis_visible=False)
        graphique(st, fig, 260)
    with carte(c4):
        e = sel.groupby("annee_embauche").size().reset_index(name="n")
        fig = px.line(e, x="annee_embauche", y="n", markers=True, text="n", title="Effectif par année d'embauche",
                      color_discrete_sequence=[JAUNE])
        graphique(st, fig.update_traces(textposition="top center", line_width=3)
                  .update_layout(xaxis_title=None, yaxis_title=None), 260)
    c1, c2 = st.columns([1.2, 1.4])
    with carte(c1):
        dg = cur.groupby(["categorie_perf", "genre"]).size().reset_index(name="n")
        dg = dg[dg["categorie_perf"] != "nan"]
        dg["part"] = dg["n"] / dg.groupby("categorie_perf")["n"].transform("sum")
        graphique(st, px.bar(dg, x="categorie_perf", y="part", color="genre", text=dg["part"].map(pct),
                             title="Répartition par genre selon la performance", color_discrete_map=COULEURS_GENRE,
                             category_orders={"categorie_perf": ORDRE_PERF})
                  .update_layout(xaxis_title=None, yaxis_visible=False), 300)
    with carte(c2):
        axe = st.radio("Distribution", ["par ancienneté", "par âge"], horizontal=True, key="axe_perf",
                       label_visibility="collapsed")
        col, ordre = ("tranche_anciennete", ORDRE_ANC) if axe == "par ancienneté" else ("tranche_age", ORDRE_AGE)
        base = cur[(cur["categorie_perf"] != "nan") & (cur[col] != "nan")]
        m = pd.crosstab(base["categorie_perf"], base[col], margins=True, margins_name="Total")
        m.index.name, m.columns.name = "Performance", None
        m = m.reindex([x for x in ORDRE_PERF + ["Total"] if x in m.index])
        m = m[[x for x in ordre + ["Total"] if x in m.columns]]
        vmax = m.iloc[:-1, :-1].values.max() or 1

        def teinte(v):
            return f"background-color: rgba(255,121,0,{0.08 + 0.6 * v / vmax:.2f})"
        st.dataframe(m.style.map(teinte, subset=(m.index[:-1], m.columns[:-1])), width="stretch", height=230)
    st.markdown("<div class='note'>Niveaux de performance (note sur 5) : Insuffisante ≤ 2,5 · Attendue ≤ 3,5 · "
                "Bonne ≤ 4,2 · Excellente au-delà.</div>", unsafe_allow_html=True)
    f = faits()
    pont(f"les collaborateurs dont l'engagement est inférieur à 3 sont partis à <b>{pct(f['dep_eng_bas'])}</b> contre "
         f"{pct(f['dep_eng_ok'])} pour les autres (cohorte {f['coh']}). C'est le premier facteur du modèle de départ, "
         f"présent chez <b>{pct(f['part_eng'], 0)}</b> des collaborateurs signalés.", "anticipation")


# ---------------------------------------------------------------------------
# 10. Absentéisme
# ---------------------------------------------------------------------------
def p_absenteisme():
    d, per, _ = en_tete(10, "Absentéisme", cle="abs")
    cur = d[d["periode"] == per]
    c1, c2 = st.columns([0.9, 3.0])
    with c1:
        abs_per = d.groupby("periode")["taux_absenteisme"].mean()
        abs_g = d[d["genre"].isin(["F", "M"])].groupby(["periode", "genre"])["taux_absenteisme"].mean().unstack()
        tuile(st, "Taux d'absentéisme", pct(cur["taux_absenteisme"].mean(), 2), "👥", evolution(abs_per, per), inverse=True)
        st.write("")
        tuile(st, "Hommes", pct(cur.loc[cur["genre"] == "M", "taux_absenteisme"].mean(), 2), "👨",
              evolution(abs_g["M"], per) if "M" in abs_g else None, inverse=True)
        st.write("")
        tuile(st, "Femmes", pct(cur.loc[cur["genre"] == "F", "taux_absenteisme"].mean(), 2), "👩",
              evolution(abs_g["F"], per) if "F" in abs_g else None, inverse=True)
    with carte(c2):
        tend = abs_g.rename(columns={"F": "Femmes", "M": "Hommes"})
        tend.insert(0, "Ensemble", abs_per)
        fig = go.Figure()
        for nom_, coul, larg in [("Ensemble", JAUNE, 3.2), ("Femmes", "#FFB27A", 2), ("Hommes", GRIS_FONCE, 2)]:
            if nom_ in tend:
                fig.add_trace(go.Scatter(x=tend.index, y=tend[nom_], name=nom_, mode="lines+markers",
                                         line=dict(color=coul, width=larg),
                                         text=[pct(v, 2) for v in tend[nom_]] if nom_ == "Ensemble" else None,
                                         textposition="top center"))
        fig.data[0].mode = "lines+markers+text"
        fig.update_yaxes(tickformat=".1%")
        e_ = evolution(abs_per, per)
        fig.update_layout(title="Tendance du taux d'absentéisme"
                                + (f" · {'+' if (abs_per.iloc[-1] - abs_per.iloc[0]) >= 0 else '−'}"
                                   f"{abs(abs_per.iloc[-1] - abs_per.iloc[0]) * 100:.2f} pt depuis {abs_per.index[0]}"
                                   .replace(".", ",") if len(abs_per) > 1 else ""))
        graphique(st, fig.update_layout(xaxis_title=None), 330)
    c2b, c3, c4 = st.columns([1.4, 1.3, 1.3])
    with carte(c2b):
        ca = cur.groupby(["tranche_age", "contrat"])["taux_absenteisme"].mean().reset_index()
        graphique(st, px.bar(ca, x="tranche_age", y="taux_absenteisme", color="contrat", barmode="group",
                             text=ca["taux_absenteisme"].map(lambda v: pct(v, 1)), title="Contrat × tranche d'âge",
                             category_orders={"tranche_age": ORDRE_AGE}, color_discrete_map={"CDI": JAUNE, "CDD": GRIS})
                  .update_layout(xaxis_title=None, yaxis_visible=False), 330)
    with carte(c3):
        g = cur.groupby("grade")["taux_absenteisme"].mean()
        g.loc["Total"] = cur["taux_absenteisme"].mean()
        g = g.reset_index()
        g["couleur"] = np.where(g["grade"] == "Total", "Total", "Grade")
        graphique(st, px.bar(g, x="grade", y="taux_absenteisme", color="couleur", text=g["taux_absenteisme"].map(pct),
                             title="Par grade", color_discrete_map={"Grade": JAUNE, "Total": GRIS})
                  .update_layout(xaxis_title=None, yaxis_visible=False), 330, False)
    with c4:
        with st.container(key="lien-absences"):
            st.page_link(PAGE["absences-departement"], label="ABSENCES PAR DÉPARTEMENT ➜")
        with carte(st):
            ta = cur.groupby("tranche_anciennete")["taux_absenteisme"].agg(taux="mean", n="size").reindex(ORDRE_ANC).reset_index()
            graphique(st, px.bar(ta, x="tranche_anciennete", y="taux", title="Taux d'absentéisme par ancienneté",
                                 text=[f"{pct(t, 2)}<br>n={int(n)}" if n == n else "" for t, n in zip(ta["taux"], ta["n"])],
                                 color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False),
                      270, False)
    c1, c2, c3 = st.columns([0.9, 2.1, 1.6])
    with carte(c1):
        st.markdown("**Par site**")
        s = cur.groupby("code_site")["taux_absenteisme"].mean().sort_values(ascending=False)
        for site, v in s.items():
            st.markdown(f"<div class='libelle'>{site}</div><div class='valeur' style='color:{JAUNE};font-size:1.3rem;"
                        f"font-weight:700'>{pct(v, 2)}</div>", unsafe_allow_html=True)
    with carte(c2):
        dep = cur.groupby("departement").agg(eff=("id", "size"), taux=("taux_absenteisme", "mean")).sort_values("eff", ascending=False)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=dep.index, y=dep["eff"], name="Effectif", mode="lines+markers+text",
                                 text=dep["eff"], textposition="top center", line=dict(color=JAUNE, width=3)), secondary_y=False)
        fig.add_trace(go.Scatter(x=dep.index, y=dep["taux"], name="Taux d'absentéisme", mode="lines+markers",
                                 line=dict(color=GRIS, dash="dot")), secondary_y=True)
        fig.update_yaxes(tickformat=".1%", secondary_y=True)
        fig.update_layout(title="Effectif et taux d'absentéisme par département")
        graphique(st, fig, 300)
    with carte(c3):
        t = cur.groupby(["departement", "genre"])["taux_absenteisme"].mean().unstack() \
            .reindex(columns=["F", "M"]) * 100
        t.insert(0, "Total", cur.groupby("departement")["taux_absenteisme"].mean() * 100)
        titre_tableau("Taux d'absentéisme par département")
        ta_ = t.reset_index().rename(columns={"departement": "Département", "F": "Femmes", "M": "Hommes"})
        st.dataframe(zebre(ta_), hide_index=True, width="stretch", height=290,
                     column_config={"Total": barre("Total", ta_["Total"].max(), "%.2f %%"),
                                    **{c: st.column_config.NumberColumn(format="%.2f %%") for c in ["Femmes", "Hommes"]}})


# ---------------------------------------------------------------------------
# 11. Absences par département (Leave Analysis)
# ---------------------------------------------------------------------------
def p_absences_dep():
    _, per, _ = en_tete(11, "Absences par département", cle="leave", avec_departement=False)
    _absences_dep_corps(per)


@bloc_local
def _absences_dep_corps(per):
    gauche, droite = st.columns([0.8, 4])
    with gauche:
        with st.container(key="choix-dep_leave"):
            st.markdown("<div class='choix-titre'>Département</div>", unsafe_allow_html=True)
            dep = st.radio("Département", DEPARTEMENTS, key="dep_leave", label_visibility="collapsed")
    cur = DF[(DF["periode"] == per) & (DF["departement"] == dep)]
    with droite:
        c = st.columns(3)
        tuile(c[0], "Jours d'absence moyens (6 mois)", nb(cur["jours_abs_6m"].mean(), 2), "📅")
        tuile(c[1], "Jours non justifiés moyens", nb(cur["abs_non_just_6m"].mean(), 2), "🤒")
        tuile(c[2], "Événements d'absence moyens", nb(cur["nb_abs_6m"].mean(), 2), "🏃")
        st.write("")
        c1, c2, c3 = st.columns([1.2, 1, 1.6])
        with carte(c1):
            ta = cur.groupby("tranche_anciennete")[["jours_abs_6m", "abs_non_just_6m"]].mean().reindex(ORDRE_ANC).reset_index()
            ta = ta.rename(columns={"jours_abs_6m": "Toutes absences", "abs_non_just_6m": "Non justifiées"})
            graphique(st, px.bar(ta.melt("tranche_anciennete", var_name="type", value_name="jours"),
                                 x="tranche_anciennete", y="jours", color="type", barmode="group",
                                 title="Jours moyens par ancienneté",
                                 color_discrete_map={"Toutes absences": JAUNE, "Non justifiées": GRIS})
                      .update_layout(xaxis_title=None, yaxis_title=None), 270)
        with carte(c2):
            g = cur.groupby("grade")["jours_abs_6m"].sum().reset_index()
            graphique(st, anneau(g, "grade", "jours_abs_6m", "Jours d'absence par grade"), 270)
        with carte(c3):
            p = cur.groupby("poste").agg(total=("jours_abs_6m", "sum"), moyen=("jours_abs_6m", "mean")) \
                .sort_values("total", ascending=False).head(10)
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=p.index, y=p["total"], name="Total des jours", marker_color=JAUNE, text=p["total"]),
                          secondary_y=False)
            fig.add_trace(go.Scatter(x=p.index, y=p["moyen"], name="Moyenne par personne", mode="lines+markers",
                                     line=dict(color=GRIS_FONCE)), secondary_y=True)
            fig.update_layout(title="Absences par poste")
            graphique(st, fig, 270)
        with carte(st):
            st.markdown("**Collaborateurs les plus absents** (identifiants anonymisés)")
            if not auth.peut_voir_nominatif():
                st.info("Liste individuelle réservée au profil DRH. Le profil Direction générale consulte les "
                        "indicateurs agrégés ci-dessus.")
                return
            t = cur.sort_values(["jours_abs_6m", "abs_non_just_6m"], ascending=False).head(10)[
                ["id", "poste", "grade", "contrat", "jours_abs_6m", "abs_non_just_6m", "nb_abs_6m"]]
            t = t.rename(columns={"id": "Identifiant", "poste": "Poste", "grade": "Grade", "contrat": "Contrat",
                                  "jours_abs_6m": "Jours d'absence", "abs_non_just_6m": "Non justifiés",
                                  "nb_abs_6m": "Événements"})
            st.dataframe(zebre(t), hide_index=True, width="stretch",
                         column_config={"Jours d'absence": barre("Jours d'absence", t["Jours d'absence"].max(), "%.1f"),
                                        "Non justifiés": st.column_config.NumberColumn(format="%.1f")})


# ---------------------------------------------------------------------------
# 12. Profil des départs (Termination Profile)
# ---------------------------------------------------------------------------
def p_profil_departs():
    d, per, _ = en_tete(12, "Profil des départs", periodes=PERIODES_HIST, cle="term")
    hc = d[d["periode"] == per]
    partis = hc[hc["target"] == 1]
    c = st.columns(3)
    tuile(c[0], "Départs dans les 6 mois", nb(len(partis)), "🚪", detail=partis)
    tuile(c[1], "Dont CDI", nb((partis["contrat"] == "CDI").sum()), "📝")
    tuile(c[2], "Dont femmes", nb((partis["genre"] == "F").sum()), "👩")
    st.write("")
    c1, c2, c3 = st.columns([1.3, 1, 1.3])
    def taux_par(col, ordre=None):
        t = hc.groupby(col)["target"].agg(departs="sum", n="size", taux="mean")
        t = t.reindex(ordre) if ordre else t
        t = t.dropna(subset=["n"]).reset_index()
        t["texte"] = [f"{int(b)} sur {int(n)}<br>{pct(x)}" for b, n, x in zip(t["departs"], t["n"], t["taux"])]
        return t

    with carte(c1):
        a = taux_par("tranche_anciennete", ORDRE_ANC)
        graphique(st, px.bar(a, x="tranche_anciennete", y="taux", text="texte",
                             title="Taux de départ par ancienneté (départs / effectif)",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 250)
    with carte(c2):
        cg = partis.groupby(["contrat", "genre"]).size().reset_index(name="n")
        graphique(st, px.bar(cg, x="contrat", y="n", color="genre", text="n", title="Par contrat",
                             color_discrete_map=COULEURS_GENRE).update_layout(xaxis_title=None, yaxis_visible=False), 250)
    with carte(c3):
        g = taux_par("grade", ["G1", "G2", "G3", "G4", "G5"])
        graphique(st, px.bar(g, x="grade", y="taux", text="texte", title="Taux de départ par grade",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 250)
    c1, c2, c3 = st.columns([1.3, 1, 1.3])
    with carte(c1):
        v = partis.groupby(["ville_affectation", "genre"]).size().reset_index(name="n")
        graphique(st, px.bar(v, x="ville_affectation", y="n", color="genre", text="n", title="Par ville et par genre",
                             color_discrete_map=COULEURS_GENRE).update_layout(xaxis_title=None, yaxis_visible=False), 280)
    with carte(c2):
        graphique(st, anneau(partis["genre"].value_counts().reset_index(), "genre", "count", "Par genre",
                             COULEURS_GENRE).update_traces(hole=0), 280)
    with carte(c3):
        dc = partis.groupby(["departement", "categorie_perf"]).size().reset_index(name="n")
        dc = dc[dc["categorie_perf"] != "nan"]
        graphique(st, px.bar(dc, x="departement", y="n", color="categorie_perf", text="n",
                             title="Par département et niveau de performance",
                             category_orders={"categorie_perf": ORDRE_PERF},
                             color_discrete_map={"Insuffisante": GRIS_FONCE, "Attendue": GRIS,
                                                 "Bonne": JAUNE_CLAIR, "Excellente": JAUNE})
                  .update_layout(xaxis_title=None, yaxis_visible=False), 280)
    st.markdown("<div class='note'>Ces graphiques décrivent les départs observés ; ils ne montrent pas leurs causes. "
                "Le motif de départ (démission, fin de contrat, licenciement…) n'est pas enregistré dans les données : "
                "la répartition par niveau de performance est montrée à titre descriptif. "
                "Les taux portant sur moins de 50 personnes sont peu fiables.</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 13. Analyse des départs (Attrition Analysis)
# ---------------------------------------------------------------------------
def p_analyse_departs():
    d, per, _ = en_tete(13, "Analyse des départs", periodes=PERIODES_HIST, cle="attr")
    h = d[d["jeu"] == "historique"]
    hc = h[h["periode"] == per]
    c = st.columns([1, 1, 1, 1, 2.2])
    tuile(c[0], "Taux de départ", pct(hc["target"].mean()), "🚪", detail=hc[hc["target"] == 1])
    tuile(c[1], "Taux CDI", pct(hc.loc[hc["contrat"] == "CDI", "target"].mean()), "📝")
    tuile(c[2], "Taux CDD", pct(hc.loc[hc["contrat"] == "CDD", "target"].mean()), "⏱️")
    tuile(c[3], "Taux des cadres (G4-G5)", pct(hc.loc[hc["cadre"] == 1, "target"].mean()), "👔")
    prev = precedente(per, PERIODES_HIST)
    with c[4]:
        for lib, p_ in [("Période précédente", prev), ("Période choisie", per)]:
            if p_ is None:
                continue
            x = h[h["periode"] == p_]
            st.markdown(f"<div class='libelle'>{lib} · {p_}</div>", unsafe_allow_html=True)
            k = st.columns(3)
            for col, l, v in zip(k, ["Arrivées", "Départs", "Effectif"],
                                 [x["arrivee"].sum(), x["target"].sum(), len(x)]):
                col.markdown(f"<div>"
                             f"<div class='valeur' style='color:{JAUNE};font-size:1.5rem;font-weight:700'>{nb(v)}</div>"
                             f"<div class='libelle'>{l}</div></div>", unsafe_allow_html=True)
    st.write("")
    c1, c2 = st.columns([1.7, 1.3])
    with carte(c1):
        gp = h[h["genre"].isin(["F", "M"])].groupby(["periode", "genre"])["target"].mean().reset_index()
        fig = px.line(gp, x="periode", y="target", color="genre", markers=True, title="Taux de départ par genre",
                      color_discrete_map=COULEURS_GENRE, line_dash="genre", line_dash_map={"F": "dot", "M": "solid"})
        graphique(st, fig.update_layout(xaxis_title=None, yaxis_title=None, yaxis_tickformat=".0%"), 280)
    with carte(c2):
        dd = hc.groupby("departement")["target"].agg(taux="mean", departs="sum", n="size")
        dd = dd[dd["n"] >= 50].sort_values("taux", ascending=False).head(6).sort_values("taux").reset_index()
        graphique(st, px.bar(dd, y="departement", x="taux", orientation="h",
                             text=[f"{pct(t)} ({int(b)}/{int(n)})" for t, b, n in zip(dd["taux"], dd["departs"], dd["n"])],
                             title="Taux de départ les plus élevés (départements ≥ 50 personnes)",
                             color_discrete_sequence=[JAUNE])
                  .update_layout(xaxis_visible=False, yaxis_title=None), 280)
    with carte(st):
        tc = h.groupby(["periode", "contrat"])["target"].sum().reset_index()
        tc["taux"] = tc["target"] / h.groupby("periode").size().reindex(tc["periode"]).values
        graphique(st, px.bar(tc, x="periode", y="taux", color="contrat", text=tc["taux"].map(pct),
                             title="Tendance du taux de départ, par contrat", color_discrete_map={"CDI": JAUNE, "CDD": GRIS})
                  .update_layout(xaxis_title=None, yaxis_visible=False), 280)
    f = faits()
    pont(f"deux signaux expliquent une grande partie des départs : salaire sous 90 % de la référence du grade "
         f"(<b>{pct(f['dep_sous90'])}</b> de départs contre {pct(f['dep_sur90'])}) et engagement inférieur à 3 "
         f"(<b>{pct(f['dep_eng_bas'])}</b> contre {pct(f['dep_eng_ok'])}).", "anticipation")


# ---------------------------------------------------------------------------
# Anticipation des départs
# ---------------------------------------------------------------------------
@bloc_local
def _bloc_capacite(act, capacite):
    st.markdown("#### 2 · Combien de collaborateurs la DRH peut-elle accompagner ?")
    c1, c2 = st.columns([1, 2])
    with carte(c1):
        n = st.slider("Nombre de collaborateurs accompagnés sur le semestre", 10, 600, 150, 10, key="capacite")
        part = round(n / len(act), 2)
        cap = capacite.loc[max(0.01, min(part, 1.0))]
        prec, couv = cap[("precision", "mean")], cap[("couverture", "mean")]
        attendus = n * prec
        groupe = act.nsmallest(n, "rang_haut")
        st.markdown(
            f"- Part de l'effectif : **{pct(n / len(act))}**\n"
            f"- Seuil correspondant : score ≥ **{nb(groupe['probabilite'].min(), 2)}** (niveaux "
            f"{', '.join(groupe['niveau_risque'].unique())})\n"
            f"- Départs historiquement attendus dans ce groupe : **≈ {nb(attendus)}** "
            f"(entre {nb(n * cap[('precision', 'min')])} et {nb(n * cap[('precision', 'max')])})\n"
            f"- Part de tous les départs couverte : **≈ {pct(couv, 0)}**\n"
            f"- Personnes accompagnées qui ne seraient probablement pas parties : **≈ {nb(n - attendus)}**")
        st.caption("Ces chiffres décrivent le ciblage, pas l'effet de l'accompagnement : sans dispositif d'évaluation, "
                   "on ne peut pas estimer les départs évités.")
    with carte(c2):
        courbe = capacite[("couverture", "mean")].reset_index()
        courbe.columns = ["part", "couverture"]
        courbe["personnes"] = (courbe["part"] * len(act)).round()
        fig = go.Figure()
        fig.add_scatter(x=courbe["personnes"], y=courbe["couverture"], mode="lines", line=dict(color=GRIS_FONCE, width=3),
                        name="Modèle")
        fig.add_scatter(x=courbe["personnes"], y=courbe["part"], mode="lines", line=dict(color=GRIS, dash="dot"),
                        name="Ciblage au hasard")
        fig.add_vline(x=n, line_color=JAUNE, line_width=3)
        fig.update_layout(title="Part des départs couverte selon le nombre de personnes accompagnées",
                          yaxis=dict(tickformat=".0%"), xaxis_title="collaborateurs accompagnés")
        graphique(st, fig, 300)
    rep1, rep2 = st.columns(2)
    with carte(rep1):
        r = groupe["departement"].value_counts().reset_index()
        r["part"] = r["count"] / r["departement"].map(act["departement"].value_counts())
        graphique(st, px.bar(r.sort_values("count"), y="departement", x="count", orientation="h",
                             text=[f"{c} ({pct(p_, 0)} du département)" for c, p_ in zip(r.sort_values('count')['count'], r.sort_values('count')['part'])],
                             title="Groupe accompagné par département", color_discrete_sequence=[JAUNE])
                  .update_layout(xaxis_visible=False, yaxis_title=None), 320, False)
    with carte(rep2):
        r = groupe["poste"].value_counts().head(10).reset_index().sort_values("count")
        graphique(st, px.bar(r, y="poste", x="count", orientation="h", text="count",
                             title="Groupe accompagné : 10 postes les plus représentés", color_discrete_sequence=[GRIS])
                  .update_layout(xaxis_visible=False, yaxis_title=None), 320, False)


def p_anticipation():
    en_tete(15, "Anticipation des départs", periodes=None, cle="antic", avec_departement=False)
    act, contrib = modele_risque()
    taux, capacite, auc = fiabilite()
    st.markdown(
        "<div class='avertissement'><b>Signal statistique à examiner, pas une prédiction individuelle.</b> "
        "Le score classe les collaborateurs selon leur ressemblance avec les profils partis par le passé. "
        f"Sa capacité de classement est modérée (AUC {nb(auc, 2)} en validation). La majorité des personnes "
        "signalées ne partiront pas, et une partie des départs viendra de personnes non signalées. "
        "Le score ne peut fonder aucune décision défavorable.</div>", unsafe_allow_html=True)
    st.write("")

    # 1. Fiabilité des niveaux
    st.markdown("#### 1 · Que valent les niveaux de risque ?")
    st.caption("Taux de départ réellement observés quand le modèle, entraîné sur le passé, a été appliqué aux 3 dernières "
               "cohortes connues (validation temporelle).")
    c1, c2 = st.columns([1.3, 1])
    with carte(c1):
        t = taux.reset_index()
        actuel = act["niveau_risque"].value_counts().reindex(ORDRE_NIVEAUX).fillna(0).astype(int)
        fig = go.Figure(go.Bar(x=t["niveau"], y=t["taux"], marker_color=[COULEURS_NIVEAU[n] for n in t["niveau"]],
                               error_y=dict(type="data", symmetric=False, array=t["taux_max"] - t["taux"],
                                            arrayminus=t["taux"] - t["taux_min"], color=GRIS_FONCE),
                               text=[f"<b>{pct(x, 0)}</b><br>{int(b)} sur {int(n)}" for x, b, n in
                                     zip(t["taux"], t["departs"], t["effectif"])], textposition="inside",
                               insidetextanchor="start", textfont_color="#222"))
        fig.add_hline(y=taux["departs"].sum() / taux["effectif"].sum(), line_dash="dot", line_color=GRIS_FONCE,
                      annotation_text=f"taux moyen {pct(taux['departs'].sum() / taux['effectif'].sum(), 0)}",
                      annotation_position="top right")
        fig.update_layout(title="Taux de départ observé par niveau (trait : écart entre cohortes)",
                          yaxis=dict(tickformat=".0%", range=[0, t["taux_max"].max() * 1.35]))
        graphique(st, fig.update_layout(xaxis_title=None, yaxis_title=None), 320, False)
    with carte(c2):
        lect = pd.DataFrame({
            "Niveau": ORDRE_NIVEAUX,
            "Règle": ["5 % des scores les plus hauts", "5 à 16 %", "16 à 50 %", "Moitié basse"],
            "Au 31/12/2024": actuel.values,
            "Départs observés": [pct(x, 0) for x in taux["taux"]],
            "Départs captés": [pct(x, 0) for x in taux["part_des_departs"]],
        })
        st.dataframe(zebre(lect).map(lambda v: f"background-color:{COULEURS_NIVEAU.get(v, '')};font-weight:bold;"
                                           f"color:{'#fff' if v == 'Très élevé' else '#000'}" if v in COULEURS_NIVEAU else "",
                                           subset=["Niveau"]), hide_index=True, width="stretch")
        st.caption("Lecture : sur 10 collaborateurs « Très élevé », environ "
                   f"{int(round(taux.loc['Très élevé', 'taux'] * 10))} sont partis dans les 6 mois lors des validations ; "
                   f"pour « Faible », moins de 1 sur 10.")

    # Facteurs qui pèsent dans le score, à l'échelle de l'entreprise
    st.markdown("#### Quels facteurs pèsent le plus dans le score ?")
    st.caption("Contributions du modèle par famille de variables, mesurées par rapport à un collaborateur moyen. "
               "Ce sont des associations statistiques, pas des causes ; le genre n'est pas utilisé.")
    fam = contrib.drop(columns="donnees").rename(columns=FAMILLES)
    poids = fam.abs().mean()
    poids = (poids / poids.sum()).sort_values()
    sig_idx = act.index[act["signale"]]
    top3 = fam.loc[sig_idx].apply(lambda l: l.nlargest(3)[l.nlargest(3) > 0.04].index.tolist(), axis=1)
    freq = pd.Series([f for liste in top3 for f in liste]).value_counts() / max(len(sig_idx), 1)
    freq = freq.reindex(poids.index).fillna(0)
    f1, f2 = st.columns(2)
    with carte(f1):
        graphique(st, px.bar(x=poids.values, y=poids.index, orientation="h", text=[pct(v, 0) for v in poids.values],
                             title="Poids moyen de chaque famille dans le score (tout l'effectif)",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_visible=False, yaxis_title=None),
                  300, False, cliquable=False)
    with carte(f2):
        graphique(st, px.bar(x=freq.values, y=freq.index, orientation="h", text=[pct(v, 0) for v in freq.values],
                             title=f"Part des {len(sig_idx)} collaborateurs signalés concernés par chaque famille",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_visible=False, yaxis_title=None),
                  300, False, cliquable=False)
    st.markdown(f"<div class='note'>Lecture : « {freq.idxmax()} » fait partie des principaux signaux pour "
                f"{pct(freq.max(), 0)} des collaborateurs en niveau élevé ou très élevé.</div>", unsafe_allow_html=True)
    st.write("")

    # 2. Capacité d'accompagnement (bloc local : le curseur ne recharge que cette partie)
    _bloc_capacite(act, capacite)

    # 3. Liste (DRH) ou vue agrégée (Direction)
    st.markdown("#### 3 · Qui est concerné ?")
    if not auth.peut_voir_nominatif():
        st.info("La liste nominative est réservée au profil DRH. Vue agrégée par département et par niveau :")
        agg = act.groupby(["departement", "niveau_risque"]).size().unstack(fill_value=0).reindex(columns=ORDRE_NIVEAUX,
                                                                                               fill_value=0)
        agg["Effectif"] = agg.sum(axis=1)
        ag_ = agg.reset_index().rename(columns={"departement": "Département"})
        st.dataframe(zebre(ag_), hide_index=True, width="stretch",
                     column_config={"Très élevé": barre("Très élevé", ag_["Très élevé"].max()),
                                    "Élevé": barre("Élevé", ag_["Élevé"].max())})
        return
    f1, f2, f3 = st.columns([1.4, 1, 1])
    niveaux = f1.pills("Niveaux", ORDRE_NIVEAUX, selection_mode="multi", default=["Très élevé", "Élevé"], key="niv_antic")
    dep = f2.selectbox("Département", ["Tous"] + DEPARTEMENTS, key="dep_antic")
    poste = f3.selectbox("Poste", ["Tous"] + sorted(act["poste"].unique()), key="poste_antic")
    x = act[act["niveau_risque"].isin(niveaux or ORDRE_NIVEAUX)]
    if dep != "Tous":
        x = x[x["departement"] == dep]
    if poste != "Tous":
        x = x[x["poste"] == poste]
    tab = x.sort_values("probabilite", ascending=False)[
        ["id", "niveau_risque", "probabilite", "departement", "poste", "grade", "contrat", "facteurs"]].copy()
    tab["centile"] = ((1 - x.sort_values("probabilite", ascending=False)["rang_haut"] - 1 / len(act)) * 100).values
    sel = st.dataframe(zebre(tab).map(lambda v: f"background-color:{COULEURS_NIVEAU.get(v, '#fff')};"
                                         f"color:{'#fff' if v == 'Très élevé' else '#222'}", subset=["niveau_risque"]),
                 hide_index=True, width="stretch", height=380, on_select="rerun", selection_mode="single-row",
                 key="liste_antic",
                 column_order=["id", "niveau_risque", "centile", "probabilite", "departement", "poste", "grade",
                               "contrat", "facteurs"],
                 column_config={"id": "Identifiant", "niveau_risque": "Niveau",
                                "centile": st.column_config.NumberColumn("Plus élevé que (%)", format="%.1f",
                                                                         help="Part de l'effectif ayant un score plus faible"),
                                "probabilite": st.column_config.ProgressColumn("Probabilité estimée", format="%.2f",
                                                                               min_value=0.0, max_value=1.0, color="#FF7900"),
                                "departement": "Département", "poste": "Poste", "grade": "Grade", "contrat": "Contrat",
                                "facteurs": st.column_config.TextColumn("Principaux signaux", width="large")})
    lignes = sel.selection.rows if sel else []
    if lignes:                                  # clic sur une ligne : ouverture directe de la fiche
        st.session_state["fiche_id"] = tab.iloc[lignes[0]]["id"]
        st.switch_page(PAGE["fiche-collaborateur"])
    st.caption("Cliquez sur une ligne pour ouvrir la fiche du collaborateur.")
    o1, o2, o3 = st.columns([2, 1, 1], vertical_alignment="bottom")
    cible = o1.selectbox("Ouvrir la fiche de", tab["id"].tolist() or ["—"], key="cible_fiche")
    if o2.button("Ouvrir la fiche ➜", width="stretch", disabled=not len(tab)):
        st.session_state["fiche_id"] = cible
        st.switch_page(PAGE["fiche-collaborateur"])
    o3.download_button("Liste (CSV)", tab.to_csv(index=False).encode("utf-8"), "anticipation_departs.csv", "text/csv",
                       width="stretch", icon=":material/download:",
                       on_click=lambda: st.toast("Liste téléchargée", icon=":material/check_circle:"))
    st.caption("Liste confidentielle : données individuelles réservées à la DRH. Le genre n'est pas utilisé par ce modèle.")


# ---------------------------------------------------------------------------
# 15. Profil département
# ---------------------------------------------------------------------------
def p_profil_departement():
    _, per, _ = en_tete(15, "Profil département", cle="pdep", avec_departement=False)
    _profil_departement_corps(per)


@bloc_local
def _profil_departement_corps(per):
    gauche, droite = st.columns([0.8, 4])
    with gauche:
        with st.container(key="choix-dep_profil"):
            st.markdown("<div class='choix-titre'>Département</div>", unsafe_allow_html=True)
            dep = st.radio("Département", DEPARTEMENTS, key="dep_profil", label_visibility="collapsed")
    d = DF[DF["departement"] == dep]
    cur = d[d["periode"] == per]
    entreprise = DF[DF["periode"] == per]
    coh = cohorte(per)
    hc = d[(d["periode"] == coh) & (d["jeu"] == "historique")]
    he = DF[(DF["periode"] == coh) & (DF["jeu"] == "historique")]
    with droite:
        vue = st.segmented_control("Vue", ["Vue d'ensemble", "Analyse des départs", "Prédiction des départs"],
                                   default="Vue d'ensemble", key="vue_pdep", label_visibility="collapsed") or "Vue d'ensemble"
        g, dr = st.columns([1.6, 1])
        with g:
            if vue == "Vue d'ensemble":
                k = st.columns(3)
                tuile(k[0], "Effectif", nb(len(cur)), "👥", detail=cur)
                tuile(k[1], "Arrivées", nb(cur["arrivee"].sum()), "🧲", detail=cur[cur["arrivee"] == 1])
                tuile(k[2], "Taux d'absentéisme", pct(cur["taux_absenteisme"].mean(), 2), "🤒")
                with carte(st):
                    ab = d.groupby("periode")["taux_absenteisme"].mean()
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    fig.add_trace(go.Bar(x=ab.index, y=ab.pct_change(), name="Variation", marker_color=GRIS_CLAIR),
                                  secondary_y=True)
                    fig.add_trace(go.Scatter(x=ab.index, y=ab.values, name="Taux d'absentéisme", mode="lines+markers",
                                             line=dict(color=JAUNE, width=3)), secondary_y=False)
                    fig.update_yaxes(tickformat=".1%", secondary_y=False)
                    fig.update_yaxes(tickformat=".0%", secondary_y=True)
                    fig.update_layout(title="Taux d'absentéisme et variation d'une période à l'autre")
                    graphique(st, fig, 280)
            elif vue == "Analyse des départs":
                k = st.columns(3)
                tuile(k[0], f"Départs ({coh})", nb(hc["target"].sum()), "🚪", detail=hc[hc["target"] == 1])
                tuile(k[1], "Taux de départ", pct(hc["target"].mean()), "📉")
                tuile(k[2], "Taux entreprise", pct(he["target"].mean()), "🏢")
                with carte(st):
                    gg = d[(d["jeu"] == "historique") & (d["target"] == 1)].groupby(["periode", "generation"]).size().reset_index(name="n")
                    graphique(st, px.bar(gg, x="periode", y="n", color="generation", text="n",
                                         title="Départs par génération",
                                         color_discrete_map={"Génération Z": GRIS_CLAIR, "Génération Y": JAUNE,
                                                             "Génération X": GRIS})
                              .update_layout(xaxis_title=None, yaxis_visible=False), 280)
            else:
                sc = scores()
                s = sc[sc["departement"] == dep]
                k = st.columns(3)
                tuile(k[0], "Niveau très élevé ou élevé", nb(s["signale"].sum()), "🎯")
                tuile(k[1], "Part de l'effectif", pct(s["signale"].mean()), "📊")
                tuile(k[2], "Probabilité moyenne", pct(s["probabilite"].mean()), "📈")
                with carte(st):
                    r = s.groupby(["poste", "niveau_risque"]).size().reset_index(name="n")
                    graphique(st, px.bar(r, y="poste", x="n", color="niveau_risque", orientation="h",
                                         title="Niveau de risque par poste",
                                         color_discrete_map=COULEURS_NIVEAU,
                                         category_orders={"niveau_risque": ORDRE_NIVEAUX})
                              .update_layout(xaxis_title=None, yaxis_title=None), 300)
        with carte(dr):
            st.markdown("#### Synthèse")
            effs = entreprise.groupby("departement").size().sort_values(ascending=False)
            rang = list(effs.index).index(dep) + 1 if dep in effs.index else None
            femmes = (cur["genre"] == "F").mean()
            top_poste = cur["poste"].value_counts().index[0] if len(cur) else "—"
            taux_dep, taux_ent = hc["target"].mean(), he["target"].mean()
            abs_d, abs_e = cur["taux_absenteisme"].mean(), entreprise["taux_absenteisme"].mean()
            sal = (cur["ratio_salaire_reference"] < 0.9).mean()
            phrases = [
                f"Avec **{len(cur)} collaborateurs** au {per}, {dep} est le **{rang}ᵉ département** sur {len(effs)} par l'effectif.",
                f"Les femmes représentent **{pct(femmes, 0)}** de l'effectif. Le poste le plus représenté est **{top_poste}**.",
                f"Son taux de départ à 6 mois (cohorte {coh}) est de **{pct(taux_dep)}**, "
                f"{'au-dessus' if taux_dep > taux_ent else 'en dessous'} de la moyenne de l'entreprise ({pct(taux_ent)}).",
                f"Son taux d'absentéisme est de **{pct(abs_d, 2)}**, contre {pct(abs_e, 2)} pour l'entreprise.",
                f"**{pct(sal, 0)}** des collaborateurs sont payés sous 90 % de la référence de leur grade, l'une des "
                f"caractéristiques les plus associées aux départs observés (association, pas causalité).",
            ]
            for ph in phrases:
                st.markdown(ph)


# ---------------------------------------------------------------------------
# Qualité des données
# ---------------------------------------------------------------------------
def p_qualite():
    en_tete(16, "Qualité des données", periodes=None, cle="qual", avec_departement=False)
    a = audit()
    t = a["anomalies"]
    eff = DF.groupby("periode").size()
    st.markdown(
        "<div class='avertissement'><b>Écart avec l'énoncé du projet.</b> L'énoncé décrit TelcomCI comme un opérateur de "
        f"510 collaborateurs répartis dans 10 départements. Les données fournies en comptent <b>{nb(eff.iloc[-1])} au "
        f"{DATES_LIB[eff.index[-1]]}</b> ({nb(eff.iloc[0])} en {eff.index[0]}), chacun avec un identifiant unique. Le "
        "dashboard est fidèle aux données. Les "
        f"<b>{int((DF[DF['periode'] == PERIODES[-1]]['departement'] == 'Non renseigné').sum())} collaborateurs</b> sans "
        "département sont regroupés dans « Non renseigné » plutôt que supprimés, ce qui explique le 11e libellé à côté "
        "des 10 départements.</div>", unsafe_allow_html=True)
    st.write("")
    k = st.columns(4)
    tuile(k[0], "Lignes analysées (historique + 31/12/2024)", nb(a["n"]), "🗂️")
    tuile(k[1], "Corrections de valeurs aberrantes", nb(t.loc[t["Anomalie"].str.startswith(("Salaire nul", "Salaire plus",
                                                                                             "Note", "Embauche")), "Total"].sum()), "🛠️")
    tuile(k[2], "Dates d'absence « du futur » neutralisées",
          nb(t.loc[t["Anomalie"].str.startswith("Dernière absence"), "Total"].sum()), "⏱️")
    tuile(k[3], "Libellés harmonisés", nb(a["libelles"]["Lignes corrigées"].sum()), "🔤")
    st.write("")
    st.markdown("#### Anomalies détectées dans les fichiers bruts et règle appliquée")
    st.dataframe(zebre(t), hide_index=True, width="stretch")
    st.markdown(
        "<div class='avertissement'><b>Point clé :</b> 341 lignes de l'historique avaient une dernière absence datée "
        "<i>après</i> la date de référence, ce qui n'arrive jamais dans les données du 31/12/2024. Utiliser cette date "
        "aurait fait apprendre au modèle une information du futur. Elle est neutralisée, et la récence des absences est "
        "recalculée à partir des absences mois par mois.</div>", unsafe_allow_html=True)
    st.markdown("#### Libellés harmonisés")
    st.dataframe(zebre(a["libelles"]), hide_index=True, width="stretch")
    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.markdown("#### Valeurs manquantes")
        st.dataframe(zebre(a["manquants"]), hide_index=True, width="stretch",
                     column_config={"Manquant (historique)": st.column_config.NumberColumn(format="percent"),
                                    "Manquant (31/12/2024)": st.column_config.NumberColumn(format="percent")})
        st.caption("Une valeur manquante n'est jamais remplacée par une valeur faible : les indicateurs portent sur la "
                   "population renseignée, et la couverture est affichée en tête de chaque page.")
    with c2:
        st.markdown("#### Contrôles de cohérence")
        st.dataframe(zebre(a["coherence"]), hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
def p_exports():
    _, per, dep = en_tete(17, "Exports", cle="exp")
    u = auth.utilisateur()
    nominatif = auth.peut_voir_nominatif()
    d = DF if dep == "Tous" else DF[DF["departement"] == dep]
    act, _ = modele_risque()
    sc = act if dep == "Tous" else act[act["departement"] == dep]
    taux, _, _ = fiabilite()
    contexte = {"periode": per, "departement": "Tous les départements" if dep == "Tous" else dep,
                "utilisateur": u["nom"], "role": auth.ROLES[u["role"]]["libelle"]}
    st.markdown(f"Les exports reprennent la période **{per}** et le périmètre **{contexte['departement']}** choisis "
                f"ci-dessus. Profil **{contexte['role']}** : "
                + ("les exports incluent la liste nominative des scores." if nominatif else
                   "les exports ne contiennent que des données agrégées."))
    c1, c2 = st.columns(2)
    with carte(c1):
        st.markdown("##### Classeur RH (Excel)")
        st.caption("S'ouvre sur une couverture avec sommaire cliquable et un tableau de bord (indicateurs clés et "
                   "graphiques Excel modifiables), puis les données mises en forme : synthèse par période, départements, "
                   "rémunération par grade, turnover, fiabilité des niveaux, anticipation"
                   + (" (agrégée et nominative)" if nominatif else " (agrégée)") + ", qualité des données.")
        if st.button("Préparer le classeur", key="prep_xlsx", width="stretch"):
            with st.spinner("Construction du classeur…"):
                st.session_state["xlsx"] = exports.excel(d, sc, taux, audit(), contexte, nominatif)
            st.toast("Classeur prêt à télécharger", icon=":material/task_alt:")
        if "xlsx" in st.session_state:
            st.download_button("Télécharger le classeur (.xlsx)", st.session_state["xlsx"],
                               f"TelcomCI_RH_{per.replace(' ', '_')}.xlsx", width="stretch", type="primary",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               icon=":material/download:",
                               on_click=lambda: st.toast("Classeur Excel téléchargé", icon=":material/check_circle:"))
    with carte(c2):
        st.markdown("##### Bilan RH semestriel (PDF)")
        st.caption("Rapport de 6 pages pour un comité : couverture, synthèse avec évolutions et trois messages clés, "
                   "effectifs et diversité, rémunération, absentéisme, turnover et anticipation, plan d'action proposé, "
                   "méthode et limites. Aucune donnée individuelle.")
        if st.button("Préparer le bilan", key="prep_pdf", width="stretch"):
            with st.spinner("Mise en page du bilan…"):
                st.session_state["pdf"] = synthese_pdf(d, sc, taux, per, contexte, nominatif)
            st.toast("Bilan prêt à télécharger", icon=":material/task_alt:")
        if "pdf" in st.session_state:
            st.download_button("Télécharger le bilan (.pdf)", st.session_state["pdf"],
                               f"TelcomCI_bilan_RH_{per.replace(' ', '_')}.pdf", "application/pdf",
                               width="stretch", type="primary", icon=":material/download:",
                               on_click=lambda: st.toast("Bilan PDF téléchargé", icon=":material/check_circle:"))


def synthese_pdf(d, sc, taux, per, contexte, nominatif):
    """Bilan RH semestriel (PDF de 6 pages aux couleurs de TelcomCI), voir rapport.py."""
    coh = cohorte(per)
    return rapport.bilan(d, sc, taux, per, precedente(per), coh, precedente(coh, PERIODES_HIST), contexte, nominatif,
                         DATES_LIB.to_dict(), JOURS_OUVRES_6M, ORDRE_AGE)


# ---------------------------------------------------------------------------
# Assistant RH : questions guidées, réponses calculées sur les données (aucune IA externe)
# ---------------------------------------------------------------------------
import unicodedata


def _sans_accents(t):
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def _base_assistant():
    per, coh = PERIODES[-1], PERIODES_HIST[-1]
    cur = DF[DF["periode"] == per]
    h = DF[(DF["periode"] == coh) & (DF["jeu"] == "historique")]
    return per, coh, cur, h


def _barres(serie, titre, fmt=None):
    serie = serie.sort_values()
    fig = px.bar(x=serie.values, y=serie.index.astype(str), orientation="h", title=titre,
                 text=[fmt(v) for v in serie.values] if fmt else serie.values, color_discrete_sequence=[JAUNE])
    return fig.update_layout(xaxis_visible=False, yaxis_title=None)


def r_departs_departement():
    _, coh, _, h = _base_assistant()
    t = h[h["departement"] != "Non renseigné"].groupby("departement")["target"].agg(["mean", "sum", "size"])
    t = t.sort_values("mean", ascending=False)
    top, suiv = t.index[0], t.index[1:3]
    txt = (f"Sur la cohorte **{coh}**, **{top}** a le taux de départ à 6 mois le plus élevé : **{pct(t.iloc[0]['mean'])}** "
           f"({int(t.iloc[0]['sum'])} départs sur {int(t.iloc[0]['size'])} collaborateurs), contre "
           f"**{pct(h['target'].mean())}** pour l'entreprise. Viennent ensuite {suiv[0]} ({pct(t.loc[suiv[0], 'mean'])}) "
           f"et {suiv[1]} ({pct(t.loc[suiv[1], 'mean'])}).")
    return txt, _barres(t["mean"], "Taux de départ à 6 mois par département", pct), "analyse-departs"


def r_ecart_salarial():
    per, _, cur, _ = _base_assistant()
    c = cur[cur["genre"].isin(["F", "M"]) & (cur["departement"] != "Non renseigné")]
    g = c.groupby(["departement", "genre"])["salaire_mensuel"].mean().unstack()
    g["ecart"] = g["M"] - g["F"]
    g["ecart_pct"] = g["ecart"] / g["M"]
    top = g["ecart_pct"].abs().idxmax()
    sens = "en faveur des hommes" if g.loc[top, "ecart"] > 0 else "en faveur des femmes"
    glob = c.groupby("genre")["salaire_mensuel"].mean()
    txt = (f"Au **{DATES_LIB[per]}**, l'écart de salaire moyen le plus marqué est dans **{top}** : "
           f"**{fcfa(abs(g.loc[top, 'ecart']))} FCFA** par mois ({pct(abs(g.loc[top, 'ecart_pct']))}) {sens}. "
           f"À l'échelle de l'entreprise, l'écart H − F est de **{fcfa(glob['M'] - glob['F'])} FCFA**. "
           "Ces écarts bruts ne tiennent pas compte du grade ni de l'ancienneté : la page Équité salariale les compare "
           "à grade égal.")
    return txt, _barres(g["ecart_pct"], "Écart de salaire moyen H − F par département (en % du salaire des hommes)",
                        pct), "equite-salariale"


def r_priorites():
    act, _ = modele_risque()
    n = act["niveau_risque"].value_counts()
    sig = act[act["signale"]]
    dep = sig["departement"].value_counts()
    txt = (f"Au 31/12/2024, le modèle classe **{int(n.get('Très élevé', 0))} collaborateurs** en niveau « très élevé » et "
           f"**{int(n.get('Élevé', 0))}** en niveau « élevé », soit **{pct(act['signale'].mean())}** de l'effectif. "
           f"Ils sont surtout dans **{dep.index[0]}** ({dep.iloc[0]}) et **{dep.index[1]}** ({dep.iloc[1]}).")
    if auth.peut_voir_nominatif():
        top = act.nsmallest(5, "rang_haut")
        txt += "\n\nLes 5 scores les plus élevés : " + ", ".join(f"**{i}** ({p_})" for i, p_ in zip(top["id"], top["poste"])) + "."
    else:
        txt += "\n\nLa liste nominative est réservée au profil DRH."
    txt += "\n\nRappel : c'est un signal statistique à examiner, pas une prédiction individuelle."
    return txt, _barres(dep, "Collaborateurs en niveau élevé ou très élevé, par département"), "anticipation"


def r_effectif():
    eff = DF.groupby("periode").size()
    txt = (f"L'effectif est passé de **{nb(eff.iloc[0])}** collaborateurs au {DATES_LIB[eff.index[0]]} à "
           f"**{nb(eff.iloc[-1])}** au {DATES_LIB[eff.index[-1]]}, soit **{pct(eff.iloc[-1] / eff.iloc[0] - 1, 0)}** "
           f"en deux ans et demi. Sur le dernier semestre, la hausse est de **{pct(eff.iloc[-1] / eff.iloc[-2] - 1)}**.")
    fig = px.line(x=eff.index, y=eff.values, markers=True, title="Effectif par période")
    fig.update_traces(line_color=JAUNE, line_width=3)
    return txt, fig.update_layout(xaxis_title=None, yaxis_title=None), "tendances"


def r_absences():
    per, _, cur, _ = _base_assistant()
    t = cur[cur["departement"] != "Non renseigné"].groupby("departement")["taux_absenteisme"].mean().sort_values(ascending=False)
    txt = (f"Au **{DATES_LIB[per]}**, **{t.index[0]}** a le taux d'absentéisme le plus élevé : **{pct(t.iloc[0], 2)}**, "
           f"contre **{pct(cur['taux_absenteisme'].mean(), 2)}** pour l'entreprise. Le plus faible est **{t.index[-1]}** "
           f"({pct(t.iloc[-1], 2)}).")
    return txt, _barres(t, "Taux d'absentéisme par département", lambda v: pct(v, 2)), "absenteisme"


def r_profils_departs():
    _, coh, _, h = _base_assistant()
    morceaux = []
    for col, lib in [("contrat", "contrat"), ("grade", "grade"), ("tranche_anciennete", "ancienneté")]:
        t = h.groupby(col, observed=True)["target"].mean().sort_values(ascending=False)
        morceaux.append(f"par {lib}, **{t.index[0]}** ({pct(t.iloc[0])})")
    t = h.groupby("tranche_anciennete", observed=True)["target"].mean().reindex(ORDRE_ANC)
    txt = (f"Sur la cohorte **{coh}** (taux moyen {pct(h['target'].mean())}), les taux de départ les plus élevés sont : "
           + " ; ".join(morceaux) + ". Ce sont des associations observées, pas des causes.")
    fig = px.bar(x=t.index, y=t.values, text=[pct(v) for v in t.values], title="Taux de départ par ancienneté",
                 color_discrete_sequence=[JAUNE])
    return txt, fig.update_layout(xaxis_title=None, yaxis_visible=False), "caracteristiques-departs"


def r_masse_salariale():
    per, _, cur, _ = _base_assistant()
    m = cur.groupby("departement")["salaire_mensuel"].sum().sort_values(ascending=False)
    total = cur["salaire_mensuel"].sum()
    txt = (f"Au **{DATES_LIB[per]}**, la masse salariale mensuelle est de **{fcfa(total)} FCFA**, pour un salaire moyen de "
           f"**{fcfa(cur['salaire_mensuel'].mean())} FCFA**. Les trois départements qui pèsent le plus sont "
           + ", ".join(f"**{d_}** ({pct(v / total, 0)})" for d_, v in m.head(3).items()) + ".")
    return txt, _barres(m.head(8), "Masse salariale mensuelle par département (8 premiers)", fcfa), "salaires"


def r_recrutements():
    arr = DF.groupby("periode")["arrivee"].sum()
    dep = DF[DF["jeu"] == "historique"].groupby("periode")["target"].sum()
    t = pd.DataFrame({"Arrivées": arr, "Départs à 6 mois": dep}).reindex(PERIODES)
    der = PERIODES_HIST[-1]
    txt = (f"Sur la cohorte **{der}**, **{int(dep[der])} départs** à 6 mois pour **{int(arr[der])} arrivées** sur le semestre "
           f"précédent. Les arrivées du dernier semestre ({PERIODES[-1]}) sont au nombre de **{int(arr.iloc[-1])}**. "
           "L'effectif augmente : les recrutements font plus que compenser les départs.")
    fig = px.bar(t.reset_index().melt("periode", var_name="type", value_name="n").dropna(), x="periode", y="n", color="type",
                 barmode="group", title="Arrivées et départs par période",
                 color_discrete_map={"Arrivées": JAUNE, "Départs à 6 mois": GRIS_FONCE})
    return txt, fig.update_layout(xaxis_title=None, yaxis_title=None), "arrivees"


QUESTIONS = [
    ("Quel département perd le plus de collaborateurs ?", r_departs_departement,
     ["depart", "perd", "quitt", "turnover", "demission", "partent", "fuite"], ["departement", "service", "ou"]),
    ("Quels profils partent le plus ?", r_profils_departs,
     ["profil", "qui part", "partent le plus", "contrat", "grade", "anciennete", "type"], []),
    ("Qui accompagner en priorité ?", r_priorites,
     ["accompagn", "priorit", "risque", "signal", "anticip", "retenir", "fideli", "prevoir", "predi"], []),
    ("Où l'écart salarial femmes / hommes est-il le plus fort ?", r_ecart_salarial,
     ["ecart", "femme", "homme", "egalite", "equite", "genre", "parite"], ["salai"]),
    ("Quel département est le plus absent ?", r_absences, ["absen", "malad", "conge", "presence"], []),
    ("Combien coûte la masse salariale ?", r_masse_salariale,
     ["masse", "cout", "budget", "paie", "combien coute", "salaire total", "salaire"], []),
    ("Comment évolue l'effectif ?", r_effectif, ["effectif", "evolu", "croissance", "combien de collab", "taille", "grandi"], []),
    ("Les recrutements compensent-ils les départs ?", r_recrutements,
     ["recrut", "arriv", "embauch", "compens", "remplac", "nouveaux"], []),
]


def trouver_question(texte):
    t = _sans_accents(texte)
    scores = []
    for i, (q, _, mots, bonus) in enumerate(QUESTIONS):
        sc = sum(2 for m in mots if m in t) + sum(1 for m in bonus if m in t)
        scores.append((sc, -i))
    meilleur = max(scores)
    return -meilleur[1] if meilleur[0] > 0 else None


FORMATS_MOTEUR = {"n": lambda v: nb(v), "pct": lambda v: pct(v), "pct2": lambda v: pct(v, 2),
                  "fcfa": lambda v: f"{fcfa(v)} FCFA", "dec": lambda v: nb(v, 1)}
ORDRES_MOTEUR = {"tranche_age": ORDRE_AGE, "tranche_anciennete": ORDRE_ANC, "periode": PERIODES,
                 "grade": ["G1", "G2", "G3", "G4", "G5"], "categorie_perf": ORDRE_PERF}


def repondre_moteur(question):
    """Question libre → (texte, graphique, page) calculés sur les données, ou None si la mesure n'est pas reconnue."""
    r = moteur.analyser(question, DF, PERIODES, PERIODES_HIST)
    if r.mesure is None:
        return None
    m, f = r.mesure, FORMATS_MOTEUR[r.mesure.format]
    res = moteur.calculer(r, DF, PERIODES, PERIODES_HIST, ORDRES_MOTEUR)
    pour = f" ({', '.join(r.libelles_filtres)})" if r.libelles_filtres else ""
    compris = [f"**{m.libelle}**"] + ([f"filtre : {', '.join(r.libelles_filtres)}"] if r.libelles_filtres else [])
    if r.repartition:
        compris.append(f"par {r.repartition[0]}")
    if not r.repartition or r.repartition[1] != "periode":
        compris.append(f"au {DATES_LIB[res['periode']]}")
    lignes = ["<span class='note'>J'ai compris : " + " · ".join(compris) + "</span>"]
    fig = None
    if r.repartition:
        serie, tailles = res["serie"], res["tailles"]
        petits = [k for k in serie.index if tailles.get(k, 0) < 5]
        serie = serie.drop(petits)
        if serie.empty:
            return "\n\n".join(lignes + ["Aucun groupe assez grand (au moins 5 collaborateurs) pour répondre."]), None, m.page
        if r.repartition[1] == "periode":
            lignes.append(f"{m.libelle.capitalize()}{pour} : **{f(serie.iloc[0])}** en {serie.index[0]}, "
                          f"**{f(serie.iloc[-1])}** en {serie.index[-1]}.")
            fig = px.line(x=serie.index, y=serie.values, markers=True, title=f"{m.libelle.capitalize()}{pour}",
                          text=[f(v) for v in serie.values])
            fig.update_traces(line_color=JAUNE, line_width=3, textposition="top center")
            fig.update_layout(xaxis_title=None, yaxis_visible=False,
                              yaxis_range=[serie.min() - (serie.max() - serie.min()) * .15 - 1e-9,
                                           serie.max() + (serie.max() - serie.min()) * .25 + 1e-9])
        else:
            haut, bas = serie.idxmax(), serie.idxmin()
            premier, second = (bas, haut) if r.sens == "min" else (haut, bas)
            mot1, mot2 = ("la plus faible", "la plus élevée") if r.sens == "min" else ("la plus élevée", "la plus faible")
            lignes.append(f"**{premier}** a la valeur {mot1} : **{f(serie[premier])}** "
                          f"({nb(tailles[premier])} collaborateurs). **{second}** a la valeur {mot2} : "
                          f"**{f(serie[second])}**.")
            ordonne = r.repartition[1] in ORDRES_MOTEUR
            s_aff = serie if ordonne else serie.sort_values()
            if ordonne:
                fig = px.bar(x=s_aff.index, y=s_aff.values, text=[f(v) for v in s_aff.values],
                             title=f"{m.libelle.capitalize()}{pour} par {r.repartition[0]}", color_discrete_sequence=[JAUNE])
                fig.update_layout(xaxis_title=None, yaxis_visible=False)
            else:
                fig = px.bar(x=s_aff.values, y=s_aff.index, orientation="h", text=[f(v) for v in s_aff.values],
                             title=f"{m.libelle.capitalize()}{pour} par {r.repartition[0]}", color_discrete_sequence=[JAUNE])
                fig.update_layout(xaxis_visible=False, yaxis_title=None)
        if petits:
            lignes.append(f"<span class='note'>Groupes de moins de 5 collaborateurs non affichés : {', '.join(petits)}.</span>")
    else:
        v = res["valeur"]
        if pd.isna(v) or res["n"] == 0:
            lignes.append("Aucun collaborateur ne correspond à ces critères.")
        else:
            phrase = f"{m.libelle.capitalize()}{pour} : **{f(v)}**"
            if m.cle not in ("effectif",):
                phrase += f" (sur {nb(res['n'])} collaborateurs)"
            if "reference" in res and not pd.isna(res["reference"]):
                if m.cle == "effectif" and res["reference"]:
                    phrase += f", soit **{pct(v / res['reference'])}** de l'effectif total ({nb(res['reference'])})"
                else:
                    phrase += f", contre **{f(res['reference'])}** pour l'ensemble de l'entreprise"
            lignes.append(phrase + ".")
            if res["n"] < 10 and m.cle not in ("effectif", "nb_departs", "arrivees"):
                lignes.append("<span class='note'>Attention : moins de 10 collaborateurs concernés, "
                              "résultat à interpréter avec prudence.</span>")
    lignes += [f"<span class='note'>{x}</span>" for x in r.remarques]
    return "\n\n".join(lignes), fig, m.page


def suggestions(question, n=3):
    """Questions les plus proches (catalogue et exemples) pour une phrase non comprise."""
    from difflib import SequenceMatcher
    q = moteur.normaliser(question)
    candidats = [c for c, *_ in QUESTIONS] + moteur.EXEMPLES
    mots = set(q.split())
    def score(c):
        cn = moteur.normaliser(c)
        return SequenceMatcher(None, q, cn).ratio() + 0.15 * len(mots & set(cn.split()))
    return sorted(candidats, key=score, reverse=True)[:n]


def poser(question):
    st.session_state.setdefault("assistant_hist", []).append(question)


def p_assistant():
    en_tete(2, "Assistant RH", periodes=None, cle="assistant", avec_departement=False)
    hist = st.session_state.setdefault("assistant_hist", [])
    hist[:] = [h[0] if isinstance(h, tuple) else h for h in hist]          # ancien format (question, index)
    with st.chat_message("assistant", avatar=":material/insights:"):
        st.markdown("Bonjour. Je réponds à vos questions sur les effectifs, les salaires, l'absentéisme, la performance et "
                    f"les départs, à partir des données au **{DATES_LIB[PERIODES[-1]]}**. Chaque réponse est calculée "
                    "directement sur les données du dashboard, sans service extérieur.\n\n"
                    "Choisissez une question ci-dessous ou écrivez la vôtre en combinant une **mesure** (effectif, taux de "
                    "départ, salaire, absentéisme, arrivées, âge, ancienneté, performance…), des **filtres** (DEP04, G3, "
                    "CDD, femmes, Bouaké, 2023 S1, cadres, moins de 25 ans…) et une **répartition** (par grade, par "
                    "période, quel département…).")
    for i, question in enumerate(hist):
        with st.chat_message("user", avatar=":material/person:"):
            st.markdown(question)
        with st.chat_message("assistant", avatar=":material/insights:"):
            idx = next((k for k, (q, *_) in enumerate(QUESTIONS) if q == question), None)
            reponse = None
            if idx is not None:
                reponse = QUESTIONS[idx][1]()
            else:
                reponse = repondre_moteur(question)
                if reponse is None:
                    idx = trouver_question(question)
                    reponse = QUESTIONS[idx][1]() if idx is not None else None
            if reponse is None:
                st.markdown("Je n'ai pas compris cette question. Vouliez-vous dire :")
                with st.container(horizontal=True):
                    for k, sug in enumerate(suggestions(question)):
                        st.button(sug, key=f"sug-{i}-{k}", on_click=poser, args=(sug,), icon=":material/subdirectory_arrow_right:")
                continue
            texte, fig, page = reponse
            st.markdown(texte, unsafe_allow_html=True)
            if fig is not None:
                with carte(st):
                    graphique(st, fig, 260, False, cliquable=False)
            if page in PAGE:
                st.page_link(PAGE[page], label=f"Ouvrir la page « {PAGE[page].title} »", icon=":material/arrow_forward:")
    st.caption("Questions fréquentes")
    choix = st.pills("Questions proposées", [q for q, *_ in QUESTIONS], key=f"q_assistant_{len(hist)}",
                     label_visibility="collapsed")
    st.caption("Exemples de questions libres")
    exemple = st.pills("Exemples", moteur.EXEMPLES, key=f"ex_assistant_{len(hist)}", label_visibility="collapsed")
    _, c2 = st.columns([6, 1], vertical_alignment="center")
    texte = st.chat_input("Écrivez votre question, par exemple : taux de départ des CDD par grade")
    if hist and c2.button("Effacer", icon=":material/delete_sweep:", width="stretch", type="tertiary"):
        st.session_state["assistant_hist"] = []
        st.rerun()
    question = choix or exemple or texte
    if question:
        hist.append(question)
        st.rerun()


# ---------------------------------------------------------------------------
# Recommandations : plan d'action établi par des règles explicites (identique au bilan PDF)
# ---------------------------------------------------------------------------
COULEURS_PRIORITE = {"Haute": ("#CD3C14", "#FFFFFF"), "Moyenne": ("#FF7900", "#000000"),
                     "Basse": ("#D6D6D6", "#000000"), "Cadre": ("#000000", "#FFFFFF")}


def p_recommandations():
    d, per, dep = en_tete(3, "Recommandations", cle="reco")
    cur = d[d["periode"] == per]
    coh = cohorte(per)
    hc = d[(d["periode"] == coh) & (d["jeu"] == "historique")]
    act, _ = modele_risque()
    taux, _, _ = fiabilite()
    sc = act if dep == "Tous" else act[act["departement"] == dep]
    axe, lib = ("departement", "département") if dep == "Tous" else ("grade", "grade")
    actions = rapport.plan_action(cur, hc, sc, taux, axe, lib)
    st.markdown(
        "<div class='avertissement'><b>Plan d'action proposé.</b> Chaque recommandation découle d'une règle explicite "
        f"appliquée aux indicateurs du {DATES_LIB[per]} (départs : cohorte {coh}). Ce sont des pistes à discuter avec les "
        "managers ; le niveau de risque ne peut fonder aucune décision défavorable. Le même plan figure dans le bilan "
        "PDF (page Exports).</div>", unsafe_allow_html=True)
    st.write("")
    k = st.columns(4)
    for col, (prio, icone) in zip(k, [("Haute", "🎯"), ("Moyenne", "📈"), ("Basse", "📝"), ("Cadre", "🛠️")]):
        tuile(col, f"Priorité {prio.lower()}" if prio != "Cadre" else "Cadre d'usage",
              nb(sum(a["priorite"] == prio for a in actions)), icone)
    st.write("")
    if not actions:
        st.info("Aucune règle ne se déclenche sur ce périmètre et cette période.")
    for i, a in enumerate(actions):
        fond, texte = COULEURS_PRIORITE[a["priorite"]]
        with carte(st):
            g, m, dr = st.columns([0.9, 4.2, 1.6], vertical_alignment="center")
            g.markdown(f"<div class='reco-prio' style='background:{fond};color:{texte}'>{a['priorite']}</div>",
                       unsafe_allow_html=True)
            m.markdown(f"<div class='reco-constat'>{a['constat']}</div>"
                       f"<div class='reco-action'><b>Action :</b> {a['action']}</div>"
                       f"<div class='note'>Indicateur de suivi : {a['indicateur']}</div>", unsafe_allow_html=True)
            if a.get("page") in PAGE:
                dr.page_link(PAGE[a["page"]], label=f"Voir : {PAGE[a['page']].title}", icon=":material/arrow_forward:")



# ---------------------------------------------------------------------------
# Simulateur d'actions : coût d'une mesure de rétention contre coût des départs évités
# ---------------------------------------------------------------------------
CIBLES_SIMU = {
    "Signalés payés sous 90 % de la référence": lambda a: a["signale"] & (a["ratio_salaire_reference"] < .9),
    "Tous les collaborateurs sous 90 % de la référence": lambda a: a["ratio_salaire_reference"] < .9,
    "Tous les collaborateurs signalés": lambda a: a["signale"],
}


@st.cache_data(show_spinner="Simulation…")
def simuler(cible_nom, dep, niveau, gain_eng):
    """Probabilités de départ à 6 mois avant / après l'action, pour chaque collaborateur ciblé, et hausse de salaire."""
    modele, fm = modele_entraine()
    act = modele_risque()[0]
    brut = DF[DF["jeu"] == "actuel"].reset_index(drop=True).copy()
    cible = CIBLES_SIMU[cible_nom](act).fillna(False).values
    if dep != "Tous":
        cible &= (act["departement"] == dep).values
    hausse = np.zeros(len(brut))
    if niveau:
        hausse = np.nan_to_num(np.where(cible, np.maximum(brut["reference_salaire_grade"] * niveau / 100
                                                          - brut["salaire_mensuel"], 0), 0))
        brut["salaire_mensuel"] = brut["salaire_mensuel"] + hausse
    if gain_eng:
        brut.loc[cible, "engagement_actuel"] = (brut.loc[cible, "engagement_actuel"] + gain_eng).clip(upper=5)
    apres = modele.predict_proba(creer_variables(brut)[fm])[:, 1]
    res = act.loc[cible, ["id", "departement", "grade", "poste", "salaire_mensuel", "ratio_salaire_reference",
                          "engagement_actuel", "niveau_risque", "probabilite"]].copy()
    res["apres"] = apres[cible]
    res["hausse"] = hausse[cible]
    return res


def p_simulateur():
    _, _, dep = en_tete(4, "Simulateur d'actions", periodes=None, cle="simu")
    st.markdown("<div class='avertissement'><b>Ordre de grandeur pour arbitrer, pas une promesse.</b> Le modèle "
                "mesure des associations, pas des causes : augmenter un collaborateur ne garantit pas qu'il reste. "
                "Les probabilités sont fiables en volume (366 départs prédits pour 365 observés sur les 3 cohortes de "
                "validation).</div>", unsafe_allow_html=True)
    st.write("")
    g, dr = st.columns([1.05, 2.6], gap="medium")
    with carte(g):
        st.markdown("**1 · Qui cibler ?**")
        cible = st.radio("Cible", list(CIBLES_SIMU), key="simu_cible", label_visibility="collapsed")
        st.markdown("**2 · Quelle action ?**")
        sal = st.toggle("Rattrapage salarial", value=True, key="simu_sal")
        niveau = st.slider("Porter le salaire à (% de la référence du grade)", 85, 100, 90, 5, key="simu_niv",
                           disabled=not sal, format="%d %%")
        eng = st.toggle("Plan d'engagement (carrière, formation, mobilité)", value=False, key="simu_eng")
        gain = st.slider("Gain d'engagement supposé (points sur 5)", 0.25, 1.0, 0.5, 0.25, key="simu_gain",
                         disabled=not eng)
        budget = st.number_input("Budget par personne et par an (FCFA)", 0, 5_000_000, 300_000, 50_000,
                                 key="simu_budget", disabled=not eng)
        st.markdown("**3 · Combien coûte un départ ?**")
        mois = st.slider("Coût d'un départ (mois de salaire du partant)", 3, 12, 6, 1, key="simu_mois",
                         help="Recrutement, intégration, perte de productivité. Hypothèse courante : 6 à 9 mois.")
    res = simuler(cible, dep, niveau if sal else 0, gain if eng else 0.0)
    n = len(res)
    cout_sal = res["hausse"].sum() * 12
    cout_eng = budget * n if eng else 0
    cout = cout_sal + cout_eng
    av, ap = res["probabilite"].sum() * 2, res["apres"].sum() * 2          # deux semestres : horizon d'un an
    evites = av - ap
    cout_dep = (res["probabilite"] * res["salaire_mensuel"].fillna(res["salaire_mensuel"].median())).sum() * 2 * mois
    gain_dep = ((res["probabilite"] - res["apres"]) * res["salaire_mensuel"].fillna(res["salaire_mensuel"].median())).sum() * 2 * mois
    net = gain_dep - cout
    with dr:
        k = st.columns(4)
        tuile(k[0], "Collaborateurs concernés", nb(n), "👥")
        tuile(k[1], "Coût de l'action (FCFA / an)", fcfa(cout), "💰")
        tuile(k[2], f"Départs attendus sur un an · {nb(evites, 1)} évités", f"{nb(av, 0)} → {nb(ap, 0)}", "🚪")
        couleur = "#0A7A3E" if net >= 0 else "#CD3C14"
        tuile(k[3], "Gain net (FCFA / an)", f"<span style='color:{couleur}'>{'+' if net >= 0 else '−'}{fcfa(abs(net))}</span>", "📈")
        st.write("")
        c1, c2 = st.columns(2)
        with carte(c1):
            fig = go.Figure(go.Waterfall(
                x=["Coût des départs<br>sans action", "Départs évités", "Coût de l'action", "Coût total<br>avec action"],
                measure=["absolute", "relative", "relative", "total"], y=[cout_dep, -gain_dep, cout, 0],
                text=[fcfa(cout_dep), "−" + fcfa(gain_dep), "+" + fcfa(cout), fcfa(cout_dep - gain_dep + cout)],
                textposition="outside", connector=dict(line=dict(color="#BDBDBD")),
                increasing=dict(marker_color="#CD3C14"), decreasing=dict(marker_color="#0A7A3E"),
                totals=dict(marker_color=JAUNE)))
            fig.update_layout(title="Sans action / avec action, sur un an (FCFA)", yaxis_visible=False,
                              waterfallgap=.35)
            fig.update_yaxes(range=[0, max(cout_dep, cout_dep - gain_dep + cout) * 1.25])
            graphique(st, fig, 320, False, cliquable=False)
        with carte(c2):
            xs = np.arange(3, 13)
            ys = [gain_dep / mois * m - cout for m in xs]
            fig = go.Figure(go.Bar(x=xs, y=ys, marker_color=[("#0A7A3E" if y >= 0 else "#CD3C14") if m != mois else JAUNE
                                                              for m, y in zip(xs, ys)],
                                   text=[("+" if y >= 0 else "−") + fcfa(abs(y)) for y in ys], textposition="outside"))
            seuil = cout / (gain_dep / mois) if gain_dep > 0 else None
            titre = (f"Gain net selon le coût d'un départ · seuil {nb(seuil, 1)} mois" if seuil and seuil <= 24
                     else "Gain net selon le coût d'un départ")
            fig.update_layout(title=titre, xaxis_title="Coût d'un départ (mois de salaire)", yaxis_visible=False,
                              xaxis=dict(tickmode="linear", dtick=1))
            fig.add_hline(y=0, line_color="#000", line_width=1)
            graphique(st, fig, 320, False, cliquable=False)
        lecture = (f"Pour <b>{fcfa(cout)} FCFA</b> par an, l'action éviterait environ <b>{nb(evites, 0)} départs</b> "
                   f"sur {nb(av, 0)} attendus chez les {nb(n)} collaborateurs ciblés. Avec un départ à {mois} mois de "
                   f"salaire, elle {'rapporte' if net >= 0 else 'coûte'} <b>{fcfa(abs(net))} FCFA</b> de "
                   f"{'plus' if net < 0 else 'gain net'}")
        lecture += (f" ; elle devient rentable si un départ coûte plus de {nb(seuil, 1)} mois de salaire." if seuil and net < 0
                    else ".")
        st.markdown(f"<div class='pc-lecture'>{lecture}</div>", unsafe_allow_html=True)
    if auth.peut_voir_nominatif() and n:
        st.write("")
        titre_tableau("Collaborateurs concernés, par baisse de risque",
                      "réservé au profil DRH · probabilité de départ à 6 mois avant et après l'action")
        t = res.assign(baisse=res["probabilite"] - res["apres"]).sort_values("baisse", ascending=False)
        t = pd.DataFrame({"Identifiant": t["id"], "Département": t["departement"], "Grade": t["grade"],
                          "Poste": t["poste"], "Niveau": t["niveau_risque"],
                          "Risque avant": t["probabilite"], "Risque après": t["apres"],
                          "Hausse mensuelle (FCFA)": t["hausse"].round(0)})
        st.dataframe(zebre(t), hide_index=True, width="stretch", height=320, column_config={
            "Risque avant": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1, color="#CD3C14"),
            "Risque après": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1, color="#FF7900"),
            "Hausse mensuelle (FCFA)": st.column_config.NumberColumn(format="%.0f")})


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
REGISTRE = [
    # (section, titre, fonction, url, icône, réservé au profil nominatif)
    ("Pilotage", "Vue d'ensemble RH", p_vue_ensemble, "vue-ensemble", "dashboard", False),
    ("Pilotage", "Assistant RH", p_assistant, "assistant", "forum", False),
    ("Pilotage", "Recommandations", p_recommandations, "recommandations", "checklist", False),
    ("Pilotage", "Simulateur d'actions", p_simulateur, "simulateur", "calculate", False),
    ("Effectifs", "Analyse démographique", p_demographie, "demographie", "groups", False),
    ("Effectifs", "Diversité", p_diversite, "diversite", "diversity_3", False),
    ("Effectifs", "Historique et tendances", p_tendances, "tendances", "timeline", False),
    ("Effectifs", "Nouveaux arrivants", p_arrivees, "arrivees", "person_add", False),
    ("Effectifs", "Profil département", p_profil_departement, "profil-departement", "corporate_fare", False),
    ("Effectifs", "Fiche collaborateur", p_fiche, "fiche-collaborateur", "badge", True),
    ("Rémunération", "Analyse salariale", p_salaires, "salaires", "payments", False),
    ("Rémunération", "Équité salariale F / H", p_ecart, "equite-salariale", "balance", False),
    ("Absentéisme", "Absentéisme", p_absenteisme, "absenteisme", "event_busy", False),
    ("Absentéisme", "Absences par département", p_absences_dep, "absences-departement", "domain", False),
    ("Performance", "Évaluation de la performance", p_performance, "performance", "trending_up", False),
    ("Turnover", "Analyse des départs", p_analyse_departs, "analyse-departs", "query_stats", False),
    ("Turnover", "Caractéristiques des départs observés", p_profil_departs, "caracteristiques-departs", "logout", False),
    ("Turnover", "Anticipation des départs", p_anticipation, "anticipation", "radar", False),
    ("Données", "Qualité des données", p_qualite, "qualite-donnees", "fact_check", False),
    ("Données", "Exports", p_exports, "exports", "download", False),
]

if not auth.utilisateur():
    # Toutes les adresses mènent à la connexion : un lien partagé (page + réglages) est ainsi conservé,
    # et la page demandée s'ouvre directement une fois connecté.
    connexion = [st.Page(auth.page_connexion, title="Connexion", icon=":material/lock:", url_path="connexion",
                         default=True)]
    connexion += [st.Page(lambda: auth.page_connexion(), title="Connexion", url_path=url) for _, _, _, url, _, _ in REGISTRE]
    connexion += [st.Page(lambda: auth.page_connexion(), title="Connexion", url_path="accueil")]
    st.navigation(connexion, position="hidden").run()
    st.stop()

REGISTRE_VISIBLE = []
for sec, titre, fn, url, icone, reserve in REGISTRE:
    if reserve and not auth.peut_voir_nominatif():
        continue                                  # page absente de la navigation : inaccessible, même par l'URL
    REGISTRE_VISIBLE.append({"numero": len(REGISTRE_VISIBLE) + 1, "section": sec, "titre": titre, "fn": fn,
                             "url": url, "icone": icone})
PAGE = {r["url"]: st.Page(r["fn"], title=r["titre"], icon=f":material/{r['icone']}:", url_path=r["url"])
        for r in REGISTRE_VISIBLE}
ACCUEIL = st.Page(p_accueil, title="Accueil", icon=":material/home:", url_path="accueil", default=True)
ORDRE = [ACCUEIL] + [PAGE[r["url"]] for r in REGISTRE_VISIBLE]
SECTIONS = {"": [ACCUEIL, PAGE["vue-ensemble"], PAGE["assistant"], PAGE["recommandations"], PAGE["simulateur"]]}
for r in REGISTRE_VISIBLE[4:]:
    SECTIONS.setdefault(r["section"], []).append(PAGE[r["url"]])
COURANTE = st.navigation(SECTIONS, position="top")
COURANTE.run()
