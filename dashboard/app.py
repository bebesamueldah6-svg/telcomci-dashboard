"""TelcoPeople · HR Analytics — dashboard RH sur le modèle « cycle de vie du collaborateur ».

Une page d'accueil et quinze pages thématiques, appliquées aux données TelcoPeople.
Lancement local :  streamlit run dashboard/app.py
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import auth
import exports
import qualite
from anticipation import (FAMILLES, ORDRE_NIVEAUX, auc_validation, contributions, courbe_capacite, explication,
                          niveau_depuis_rang, rang_depuis_le_haut, taux_par_niveau, validation_temporelle,
                          variables_modele)
from preparation import JOURS_OUVRES_6M, charger, entrainer_modele

st.set_page_config(page_title="TelcoPeople · HR Analytics", page_icon="🟡", layout="wide",
                   initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# Charte graphique : jaune et gris
# ---------------------------------------------------------------------------
JAUNE, JAUNE_CLAIR, GRIS, GRIS_FONCE, GRIS_CLAIR = "#F2C811", "#F7E08A", "#A6A6A6", "#5F5F5F", "#E3E3E3"
PALETTE = [JAUNE, GRIS, GRIS_FONCE, JAUNE_CLAIR, GRIS_CLAIR]
COULEURS_GENRE = {"F": JAUNE, "M": GRIS, "Non renseigné": GRIS_CLAIR}
COULEURS_NIVEAU = {"Très élevé": "#B03A2E", "Élevé": JAUNE, "Modéré": JAUNE_CLAIR, "Faible": GRIS_CLAIR}
px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = PALETTE

st.markdown(f"""
<style>
  .block-container {{padding-top: 3.2rem; padding-bottom: 2rem;}}
  .titre-page {{font-size: 2rem; font-weight: 600; color: #333; margin: 0;
               border-bottom: 3px solid {JAUNE}; display: inline-block; padding-bottom: 2px;}}
  .titre-page span {{color: #B8860B; font-weight: 700; margin-right: .4rem;}}
  .tuile {{background: #fff; border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,.18);
          padding: 10px 14px; height: 100%; min-height: 92px;}}
  .tuile .valeur {{color: {JAUNE}; font-size: 1.9rem; font-weight: 700; line-height: 1.1;
                   text-shadow: 0 0 1px #c9a200;}}
  .tuile .libelle {{color: #555; font-size: .85rem;}}
  .tuile .delta-pos {{color: #2e8b57; font-size: .8rem; font-weight: 600;}}
  .tuile .delta-neg {{color: #c0392b; font-size: .8rem; font-weight: 600;}}
  .tuile .icone {{font-size: 1.5rem; float: right; opacity: .55;}}
  .bandeau {{background: {JAUNE}; color: #222; font-weight: 700; border-radius: 4px;
            padding: 8px 4px; text-align: center; font-size: .85rem; word-break: keep-all;}}
  button[kind="primary"] {{background: {JAUNE} !important; color: #222 !important; border: none !important;
                           font-weight: 700 !important;}}
  .note {{color: #777; font-size: .78rem;}}
  div[data-testid="stVerticalBlockBorderWrapper"] {{box-shadow: 0 1px 4px rgba(0,0,0,.10);}}
  .st-key-nav-pages div[data-testid="stPageLink"] a, .st-key-nav-pages button {{justify-content: center;
      border: 1px solid #ddd; border-radius: 6px; padding: 2px 0 !important; min-height: 2.1rem !important;
      font-size: 1.05rem !important; background: #fff;}}
  .population {{color: #555; font-size: .8rem; background: #FAFAF7; border: 1px solid #EEE; border-radius: 6px;
               padding: 5px 10px; margin: -4px 0 10px 0;}}
  .population b {{color: #222;}}
  .avertissement {{background: #FFF8E1; border: 1px solid #F1E3A6; padding: 10px 14px; border-radius: 4px;
                  font-size: .9rem; color: #333;}}
</style>
""", unsafe_allow_html=True)


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


@st.cache_resource(show_spinner="Calcul des scores de risque…")
def modele_risque():
    """Modèle du dashboard (genre et source SIRH exclus), scores et contributions au 31/12/2024."""
    df, feats = donnees()
    fm = variables_modele(feats)
    modele = entrainer_modele(df, fm)
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


def tuile(col, libelle, valeur, icone="", delta=None, inverse=False):
    d = ""
    if delta is not None and not pd.isna(delta):
        bon = (delta >= 0) != inverse
        d = f"<div class='{'delta-pos' if bon else 'delta-neg'}'>{'▲' if delta >= 0 else '▼'} {pct(abs(delta))}</div>"
    col.markdown(f"<div class='tuile'><span class='icone'>{icone}</span><div class='valeur'>{valeur}</div>"
                 f"<div class='libelle'>{libelle}</div>{d}</div>", unsafe_allow_html=True)


def fig_style(fig, hauteur=290, legende=True):
    fig.update_layout(height=hauteur, margin=dict(l=10, r=10, t=40, b=10), legend_title_text="",
                      showlegend=legende, title_font_size=13, title_x=0.01, title_font_color="#333",
                      separators=", ",                       # virgule décimale, espace pour les milliers
                      legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center"))
    fig.update_traces(selector=dict(type="bar"), textangle=0, cliponaxis=False)
    return fig


def graphique(conteneur, fig, hauteur=290, legende=True):
    conteneur.plotly_chart(fig_style(fig, hauteur, legende), width="stretch", config={"displayModeBar": False})


FORMATS_ANNEAU = {
    "n": "%{label}<br>%{value:,.0f} (%{percent:.0%})",
    "pct": "%{label}<br>%{value:.2%}",
    "fcfa": "%{label}<br>%{value:,.0f}",
}


def anneau(df, noms, valeurs, titre, couleurs=None, fmt="n"):
    fig = px.pie(df, names=noms, values=valeurs, hole=0.6, title=titre,
                 color=noms, color_discrete_map=couleurs or {})
    fig.update_traces(texttemplate=FORMATS_ANNEAU[fmt], textposition="outside", sort=False)
    fig.update_layout(showlegend=False)
    return fig


def sparkline(serie, hauteur=70):
    serie = serie.fillna(0)
    fig = go.Figure(go.Scatter(x=list(range(len(serie))), y=serie.values, mode="lines",
                               fill="tozeroy", line=dict(color=JAUNE, width=2), fillcolor="rgba(242,200,17,.35)"))
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


def en_tete(numero, titre, periodes=PERIODES, cle="", avec_departement=True, defaut=None):
    """Titre (numéro et intitulé du registre), segments Période / Département, navigation, population couverte."""
    r = page_courante()
    gauche, milieu, droite, nav = st.columns([3, 3, 1.3, 1.2])
    navigation(nav)
    gauche.markdown(f"<div class='titre-page'><span>{r['numero']}</span>{r['titre']}</div>"
                    f"<div class='note'>{r['section']}</div>", unsafe_allow_html=True)
    periode = None
    if periodes:
        defaut = defaut or periodes[-1]
        periode = milieu.pills("Période", periodes, default=defaut, key=f"per_{cle}", label_visibility="collapsed")
        periode = periode or defaut
    dep = "Tous"
    if avec_departement:
        dep = droite.selectbox("Département", ["Tous"] + DEPARTEMENTS, key=f"dep_{cle}")
    d = DF if dep == "Tous" else DF[DF["departement"] == dep]
    if periode:
        population(d, periode)
    else:
        st.write("")
    return d, periode, dep


def precedente(periode, liste=PERIODES):
    i = liste.index(periode)
    return liste[i - 1] if i > 0 else None


def cohorte(periode):
    """Le départ à 6 mois n'est connu que pour les périodes historiques."""
    return periode if periode in PERIODES_HIST else PERIODES_HIST[-1]





# ---------------------------------------------------------------------------
# 0. Accueil
# ---------------------------------------------------------------------------
def p_accueil():
    """Accueil : les pages disposées autour du cercle, chacune cliquable (liens de navigation natifs)."""
    u = auth.utilisateur()
    # sur la page anneau, on navigue uniquement par les titres autour du cercle : la barre du haut est masquée
    st.markdown("<style>[data-testid='stTopNavigation'], header nav, header [data-testid='stNavSection'] "
                "{display:none !important;}</style>", unsafe_allow_html=True)
    h1, h2 = st.columns([4, 1.2], vertical_alignment="center")
    h1.markdown("<div class='titre-page'><span>TelcoPeople</span>HR Analytics</div>", unsafe_allow_html=True)
    with h2:
        st.markdown(f"<div class='note' style='text-align:right'>Connecté : <b>{u['nom']}</b><br>"
                    f"profil {auth.ROLES[u['role']]['libelle']}</div>", unsafe_allow_html=True)
        st.button("Se déconnecter", key="deco_accueil", on_click=auth.deconnecter, width="stretch")

    L, H, cx, cy = 1040, 700, 520, 345

    def arc(r, a0, a1, couleur, epaisseur):
        x0, y0 = cx + r * np.cos(np.radians(a0)), cy + r * np.sin(np.radians(a0))
        x1, y1 = cx + r * np.cos(np.radians(a1)), cy + r * np.sin(np.radians(a1))
        grand = 1 if (a1 - a0) % 360 > 180 else 0
        return (f"<path d='M {x0:.1f} {y0:.1f} A {r} {r} 0 {grand} 1 {x1:.1f} {y1:.1f}' fill='none' "
                f"stroke='{couleur}' stroke-width='{epaisseur}'/>")

    svg = (f"<svg width='{L}' height='{H}'>"
           + arc(172, 150, 70, GRIS_FONCE, 40) + arc(141, 230, 140, GRIS, 34) + arc(113, 320, 230, JAUNE, 30)
           + f"<text x='{cx}' y='{cy - 6}' text-anchor='middle' font-size='22' font-weight='700' fill='{GRIS_FONCE}'"
             " font-family='sans-serif'>Cycle de vie</text>"
           + f"<text x='{cx}' y='{cy + 22}' text-anchor='middle' font-size='22' font-weight='700' fill='{GRIS_FONCE}'"
             " font-family='sans-serif'>du collaborateur</text></svg>")

    pages = ORDRE[1:]
    m = len(pages) - 1
    n_droite = (m + 1) // 2
    angles = [-90] + list(np.linspace(-64, 78, n_droite)) + list(np.linspace(102, 244, m - n_droite))
    regles = []
    for i, angle in enumerate(angles):
        x = cx + 258 * np.cos(np.radians(angle))
        y = cy + (-312 if i == 0 else 290 * np.sin(np.radians(angle)))
        t = ("translate(-50%,-50%)" if i == 0 else "translate(0,-50%)" if np.cos(np.radians(angle)) > 0
             else "translate(-100%,-50%)")
        regles.append(f".st-key-cercle-{i} {{left:{x:.0f}px; top:{y:.0f}px; transform:{t};}}")
    st.markdown(f"""<style>
  .st-key-cercle-zone {{position:relative; width:{L}px; height:{H}px !important; min-height:{H}px !important;
                       margin:0 auto; display:block !important; counter-reset: numero;}}
  .st-key-cercle-svg {{position:absolute; left:0; top:0;}}
  div[class*="st-key-cercle-"]:not(.st-key-cercle-zone):not(.st-key-cercle-svg) {{position:absolute;
       width:max-content !important; z-index:2;}}
  .st-key-cercle-zone div[data-testid="stPageLink"] a {{background:#fff; box-shadow:2px 3px 6px rgba(0,0,0,.18);
       border-radius:3px; padding:4px 11px 4px 4px; gap:8px; font-weight:600;}}
  .st-key-cercle-zone div[data-testid="stPageLink"] a::before {{counter-increment: numero; content: counter(numero);
       background:radial-gradient(circle at 35% 30%, #FFF6C2, {JAUNE} 60%); color:#333; font-weight:700;
       border-radius:50%; width:28px; height:28px; display:inline-flex; align-items:center; justify-content:center;
       box-shadow:0 1px 3px rgba(0,0,0,.35); font-size:.85rem; flex-shrink:0;}}
  .st-key-cercle-zone div[data-testid="stPageLink"] a:hover {{background:{JAUNE};}}
  {''.join(regles)}
</style>""", unsafe_allow_html=True)
    with st.container(key="cercle-zone"):
        with st.container(key="cercle-svg"):
            st.markdown(svg, unsafe_allow_html=True)
        for i, pg in enumerate(pages):
            with st.container(key=f"cercle-{i}"):
                st.page_link(pg, label=pg.title)

    act = DF[DF["jeu"] == "actuel"]
    st.markdown(f"<div class='note' style='text-align:center'>Cliquez sur un thème pour ouvrir son tableau de bord.<br>"
                f"Données TelcoPeople : {len(act)} collaborateurs au 31/12/2024, historique semestriel depuis juin 2022, "
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

    def ligne(theme, icone):
        c = st.columns([1.0, 1.6, 1.6, 2, 1.4])
        c[0].markdown(f"<div class='bandeau' style='margin-top:30px'>{icone}<br>{theme}</div>", unsafe_allow_html=True)
        return c

    # Collaborateurs
    c = ligne("Collaborateurs", "👥")
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
    c = ligne("Diversité", "🧑‍🤝‍🧑")
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
    c = ligne("Recrutements", "🧲")
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
    c = ligne("Départs", "🚪")
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
    tuile(c[0], "Effectif", nb(len(cur)), "👥")
    tuile(c[1], "Arrivées", nb(cur["arrivee"].sum()), "🧲")
    tuile(c[2], f"Départs ({coh})", nb(hc["target"].sum()), "🚪")
    g = cur["genre"].value_counts(normalize=True)
    tuile(c[3], "Femmes · Hommes", f"{pct(g.get('F', 0), 0)} · {pct(g.get('M', 0), 0)}", "⚥")
    tuile(c[4], "Ancienneté moy.", nb(cur["anciennete"].mean(), 1), "⏳")
    tuile(c[5], "Âge moyen", nb(cur["age"].mean(), 1), "🎂")
    cad = cur[cur["cadre"] == 1]
    tuile(c[6], "Femmes cadres (G4-G5)", pct((cad["genre"] == "F").mean()), "👩‍💼")
    st.write("")

    c1, c2, c3 = st.columns([1, 1.3, 1.5])
    with c1.container(border=True):
        graphique(st, anneau(cur["contrat"].value_counts().reset_index(), "contrat", "count", "Par type de contrat",
                             {"CDI": JAUNE, "CDD": GRIS}), 240)
    with c2.container(border=True):
        gc = cur.groupby(["grade", "contrat"]).size().reset_index(name="n")
        graphique(st, px.bar(gc, y="grade", x="n", color="contrat", orientation="h", text="n",
                             title="Grade × type de contrat", color_discrete_map={"CDI": JAUNE, "CDD": GRIS},
                             category_orders={"grade": ["G5", "G4", "G3", "G2", "G1"]})
                  .update_layout(xaxis_title=None, yaxis_title=None), 240)
    with c3.container(border=True):
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
    with c1.container(border=True):
        v = cur["ville_affectation"].value_counts().sort_values().reset_index()
        graphique(st, px.bar(v, y="ville_affectation", x="count", orientation="h", text="count", title="Par ville",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_visible=False, yaxis_title=None), 260)
    with c2.container(border=True):
        s = cur["tranche_salaire"].value_counts().reindex(ORDRE_SAL).fillna(0).reset_index()
        fig = px.funnel(s, y="tranche_salaire", x="count", title="Tranches de salaire mensuel (FCFA)",
                        color_discrete_sequence=[JAUNE])
        graphique(st, fig.update_layout(yaxis_title=None), 260)
    with c3.container(border=True):
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
    with c1.container(border=True):
        nv = cur[cur["arrivee"] == 1].groupby(["generation", "genre"]).size().reset_index(name="n")
        graphique(st, px.bar(nv, x="generation", y="n", color="genre", text="n", title="Arrivées par génération",
                             color_discrete_map=COULEURS_GENRE).update_layout(xaxis_title=None, yaxis_visible=False), 230)
    with c2.container(border=True):
        gg = cur.groupby(["grade", "generation"]).size().reset_index(name="n")
        graphique(st, px.bar(gg, x="grade", y="n", color="generation", barmode="group", text="n",
                             title="Grade × génération",
                             color_discrete_map={"Génération Z": GRIS_CLAIR, "Génération Y": JAUNE, "Génération X": GRIS})
                  .update_layout(xaxis_title=None, yaxis_visible=False), 230)
    with c3.container(border=True):
        gr = cur.groupby(["grade", "genre"]).size().reset_index(name="n")
        graphique(st, px.bar(gr, x="grade", y="n", color="genre", text="n", title="Grade × genre",
                             color_discrete_map=COULEURS_GENRE).update_layout(xaxis_title=None, yaxis_visible=False), 230)

    c1, c2, c3, c4 = st.columns([1, 1.3, 1.2, 1.2])
    with c1.container(border=True):
        graphique(st, anneau(cur["niveau_etude"].value_counts().reset_index(), "niveau_etude", "count",
                             "Niveau d'études"), 270)
    with c2.container(border=True):
        vg = cur.groupby(["ville_affectation", "genre"]).size().reset_index(name="n")
        vg["part"] = vg["n"] / vg.groupby("ville_affectation")["n"].transform("sum")
        graphique(st, px.bar(vg, y="ville_affectation", x="part", color="genre", orientation="h",
                             text=vg["part"].map(lambda v: pct(v, 0)), title="Diversité de genre par ville",
                             color_discrete_map=COULEURS_GENRE)
                  .update_layout(xaxis_visible=False, yaxis_title=None), 270)
    with c3.container(border=True):
        fc = d.groupby("periode").apply(lambda x: (x.loc[x["cadre"] == 1, "genre"] == "F").mean()).reset_index(name="p")
        fig = px.area(fc, x="periode", y="p", title="% de femmes parmi les cadres", markers=True,
                      text=fc["p"].map(pct), color_discrete_sequence=[JAUNE])
        graphique(st, fig.update_traces(textposition="top center").update_layout(
            xaxis_title=None, yaxis_title=None, yaxis_tickformat=".0%"), 270)
    with c4.container(border=True):
        ga = cur.groupby(["grade", "tranche_age"]).size().reset_index(name="n")
        graphique(st, px.bar(ga, x="grade", y="n", color="tranche_age", title="Grade × tranche d'âge",
                             category_orders={"tranche_age": ORDRE_AGE},
                             color_discrete_sequence=[GRIS_CLAIR, JAUNE_CLAIR, JAUNE, "#D4AC0D", GRIS, GRIS_FONCE, "#333"])
                  .update_layout(xaxis_title=None, yaxis_visible=False), 270)


# ---------------------------------------------------------------------------
# 4. Fiche collaborateur
# ---------------------------------------------------------------------------
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
            f"<div style='background:#FAFAF7;border:1px solid #EEE;border-radius:6px;padding:14px;min-height:430px'>"
            f"<div style='background:{couleur};color:{texte};text-align:center;font-weight:700;border-radius:4px;"
            f"padding:4px'>Niveau de risque : {p['niveau_risque'].lower()}</div>"
            f"<div style='font-size:3.2rem;text-align:center;margin:8px 0'>{ {'F': '👩', 'M': '👨'}.get(p['genre'], '👤') }</div>"
            f"<b>{p['id']}</b><br><span class='note'>Identifiant</span><br><br>"
            f"<b>{p['poste']}</b><br><span class='note'>Poste</span><br><br>"
            f"<b>{p['departement']}</b> · {p['grade']} · {p['contrat']}<br><span class='note'>Département · grade · contrat</span><br><br>"
            f"<b>Score plus élevé que {nb((1 - p['rang_haut'] - 1 / len(act)) * 100, 1)} %</b><br>"
            f"<span class='note'>des collaborateurs au 31/12/2024</span></div>",
            unsafe_allow_html=True)
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
            st.markdown("<div class='note'>Les effets sont mesurés par rapport à un collaborateur moyen de TelcoPeople. "
                        "Ils expliquent le calcul du score ; ce sont des associations statistiques, pas des causes. "
                        "Le genre n'est pas utilisé par ce modèle. Aucune décision défavorable ne peut être fondée "
                        "sur ce score.</div>", unsafe_allow_html=True)
        with o[0]:
            lignes([("Genre", p["genre"]), ("Âge", f"{nb(p['age'])} ans"), ("Génération", p["generation"]),
                    ("Niveau d'études", p["niveau_etude"]), ("Ville", p["ville_affectation"]), ("Site", p["code_site"])])
        with o[1]:
            lignes([("Poste", p["poste"]), ("Département", p["departement"]), ("Grade", p["grade"]),
                    ("Contrat", p["contrat"]), ("Ancienneté", f"{nb(p['anciennete'], 1)} ans"),
                    ("Dernière promotion", "Jamais" if p["jamais_promu"] else f"il y a {nb(p['annees_depuis_promotion'], 1)} ans")])
        with o[2]:
            meme_grade = act[act["grade"] == p["grade"]]
            lignes([("Salaire mensuel", f"{nb(p['salaire_mensuel'])} FCFA"),
                    ("Référence du grade", f"{nb(p['reference_salaire_grade'])} FCFA"),
                    ("Salaire / référence", nb(p["ratio_salaire_reference"], 2)),
                    (f"Médiane du grade {p['grade']} (salaire / référence)", nb(meme_grade["ratio_salaire_reference"].median(), 2)),
                    ("Évolution sur 12 mois", pct(p["taux_evolution_salaire"]))])
        with o[3]:
            m = pd.DataFrame({"mois": [f"M-{i}" for i in range(5, -1, -1)],
                              "Toutes absences": [p[f"jours_abs_m{i}"] for i in range(6, 0, -1)],
                              "Non justifiées": [p[f"abs_non_just_m{i}"] for i in range(6, 0, -1)]})
            graphique(st, px.bar(m.melt("mois", var_name="type", value_name="jours"), x="mois", y="jours",
                                 color="type", barmode="group", title="Jours d'absence des 6 derniers mois",
                                 color_discrete_map={"Toutes absences": GRIS, "Non justifiées": JAUNE}), 300)
        with o[4]:
            lignes([("Performance actuelle", nb(p["performance_actuelle"], 2)),
                    ("Performance précédente", nb(p["performance_precedente"], 2)),
                    ("Engagement actuel", nb(p["engagement_actuel"], 2)),
                    ("Engagement précédent", nb(p["engagement_precedent"], 2)),
                    (f"Engagement médian {p['departement']}", nb(pairs["engagement_actuel"].median(), 2))])


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
        with st.container(border=True):
            gp = d.groupby(["periode", "genre"]).size().reset_index(name="n")
            graphique(st, px.bar(gp[gp["genre"] != "INCONNU"], x="periode", y="n", color="genre", text="n",
                                 title="Effectif par genre", color_discrete_map=COULEURS_GENRE)
                      .update_layout(xaxis_title=None, yaxis_visible=False), 260)
    with c2.container(border=True):
        dp = d[d["jeu"] == "historique"].groupby("periode")["target"].sum().reset_index()
        fig = px.line(dp, x="periode", y="target", markers=True, text="target", title="Départs à 6 mois par cohorte",
                      color_discrete_sequence=[JAUNE])
        graphique(st, fig.update_traces(textposition="top center", line_width=3)
                  .update_layout(xaxis_title=None, yaxis_title=None), 360)
    with c3.container(border=True):
        eff = d.groupby("periode").size()
        var = eff.pct_change().dropna()
        fig = go.Figure(go.Waterfall(x=list(var.index), y=list(var.values * 100), measure=["relative"] * len(var),
                                     text=[pct(v) for v in var.values], textposition="outside",
                                     increasing=dict(marker_color=JAUNE), decreasing=dict(marker_color=GRIS)))
        fig.update_layout(title="Évolution de l'effectif d'une période à l'autre (%)", yaxis_ticksuffix=" %")
        graphique(st, fig, 360, False)

    c1, c2, c3 = st.columns([1, 1.4, 1.4])
    with c1.container(border=True):
        e = d.groupby("periode").size().reset_index(name="n")
        graphique(st, px.bar(e, x="periode", y="n", text="n", title="Effectif par période",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 280)
    with c2.container(border=True):
        ga = cur.groupby(["grade", "tranche_age"]).size().reset_index(name="n")
        graphique(st, px.bar(ga, x="grade", y="n", color="tranche_age", barmode="group",
                             title=f"Grade × tranche d'âge ({per})", category_orders={"tranche_age": ORDRE_AGE},
                             color_discrete_sequence=[GRIS_CLAIR, JAUNE_CLAIR, JAUNE, "#D4AC0D", GRIS, GRIS_FONCE, "#333"])
                  .update_layout(xaxis_title=None, yaxis_visible=False), 280)
    with c3.container(border=True):
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
    tuile(c[0], "Arrivées (6 derniers mois)", nb(len(nv)), "🧲")
    tuile(c[1], "Femmes parmi les arrivées", pct((nv["genre"] == "F").mean()), "👩")
    tuile(c[2], "Arrivées par mois", nb(len(nv) / 6, 1), "📅")
    tuile(c[3], "En CDI", pct((nv["contrat"] == "CDI").mean()), "📝")
    st.write("")
    c1, c2, c3 = st.columns([1, 1.6, 1.4])
    with c1.container(border=True):
        graphique(st, anneau(nv["genre"].value_counts().reset_index(), "genre", "count", "Par genre",
                             COULEURS_GENRE), 250)
    with c2.container(border=True):
        a = d.groupby("periode")["arrivee"].sum().reset_index()
        fig = px.line(a, x="periode", y="arrivee", markers=True, text="arrivee", title="Tendance des arrivées",
                      color_discrete_sequence=[JAUNE])
        graphique(st, fig.update_traces(textposition="top center", line_width=3)
                  .update_layout(xaxis_title=None, yaxis_title=None), 250)
    with c3.container(border=True):
        gg = nv.groupby(["grade", "genre"]).size().reset_index(name="n")
        graphique(st, px.bar(gg, y="grade", x="n", color="genre", orientation="h", text="n", title="Par grade",
                             color_discrete_map=COULEURS_GENRE, category_orders={"grade": ["G5", "G4", "G3", "G2", "G1"]})
                  .update_layout(xaxis_visible=False, yaxis_title=None), 250)
    c1, c2, c3 = st.columns([1, 1.6, 1.4])
    with c1.container(border=True):
        a = nv["tranche_age"].value_counts().reindex(ORDRE_AGE).fillna(0).reset_index()
        graphique(st, px.bar(a, x="tranche_age", y="count", text="count", title="Par tranche d'âge",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 280)
    with c2.container(border=True):
        a = d.groupby("periode")["arrivee"].sum()
        p_ = d[d["jeu"] == "historique"].groupby("periode")["target"].sum()
        av = pd.DataFrame({"Arrivées": a, "Départs à 6 mois": p_}).reset_index()
        fig = px.bar(av, x="periode", y="Arrivées", text="Arrivées", title="Arrivées et départs",
                     color_discrete_sequence=[JAUNE])
        fig.add_trace(go.Scatter(x=av["periode"], y=av["Départs à 6 mois"], name="Départs à 6 mois",
                                 mode="lines+markers", line=dict(color=GRIS, width=3)))
        fig.data[0].name, fig.data[0].showlegend = "Arrivées", True
        graphique(st, fig.update_layout(xaxis_title=None, yaxis_title=None), 280)
    with c3.container(border=True):
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
    tuile(c[0], "Masse salariale mensuelle (FCFA)", fcfa(cur["salaire_mensuel"].sum()), "💰")
    tuile(c[1], "Salaire moyen (FCFA)", fcfa(cur["salaire_mensuel"].mean()), "👤")
    tuile(c[2], "Salaire moyen · hommes", fcfa(cur.loc[cur["genre"] == "M", "salaire_mensuel"].mean()), "👨")
    tuile(c[3], "Salaire moyen · femmes", fcfa(cur.loc[cur["genre"] == "F", "salaire_mensuel"].mean()), "👩")
    st.write("")
    c1, c2, c3 = st.columns([1.8, 1, 1.3])
    with c1.container(border=True):
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
        st.markdown(f"<div class='tuile'><div class='libelle'>Ville au salaire moyen le plus élevé</div>"
                    f"<div style='font-size:1.2rem;color:#555'>{top.index[0]}</div>"
                    f"<div class='valeur'>{nb(top.iloc[0])}</div><div class='libelle'>FCFA par mois</div></div>",
                    unsafe_allow_html=True)
        st.write("")
        with st.container(border=True):
            v = top.sort_values().reset_index()
            graphique(st, px.bar(v, y="ville_affectation", x="salaire_mensuel", orientation="h",
                                 text=v["salaire_mensuel"].map(fcfa), title="Salaire moyen par ville",
                                 color_discrete_sequence=[JAUNE]).update_layout(xaxis_visible=False, yaxis_title=None), 190)
    with c3.container(border=True):
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
    with c1.container(border=True):
        ag = cur[cur["genre"].isin(["F", "M"])].groupby(["tranche_age", "genre"])["salaire_mensuel"].mean().reset_index()
        fig = px.line(ag, x="tranche_age", y="salaire_mensuel", color="genre", title="Salaire moyen par âge et par genre",
                      category_orders={"tranche_age": ORDRE_AGE}, color_discrete_map=COULEURS_GENRE, markers=True)
        fig.update_traces(line_width=3)
        graphique(st, fig.update_layout(xaxis_title=None, yaxis_title="FCFA"), 280)
    with c2.container(border=True):
        st.markdown("**Top 10 des postes par salaire moyen**")
        t = cur.groupby("poste")["salaire_mensuel"].agg(moyenne="mean", effectif="size")
        t = t[t["effectif"] >= 5].sort_values("moyenne", ascending=False).head(10).reset_index()
        st.dataframe(t.rename(columns={"poste": "Poste", "moyenne": "Salaire moyen (FCFA)", "effectif": "Effectif"}),
                     hide_index=True, width="stretch", height=250,
                     column_config={"Salaire moyen (FCFA)": st.column_config.NumberColumn(format="%.0f")})


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
        with st.container(border=True):
            nmoy = cur.groupby("genre")["salaire_mensuel"].agg(["mean", "size"]).reset_index()
            graphique(st, px.bar(nmoy, x="genre", y="mean", color="genre", color_discrete_map=COULEURS_GENRE,
                                 text=[f"{fcfa(m)}<br>n={n}" for m, n in zip(nmoy["mean"], nmoy["size"])],
                                 title="Salaire moyen par genre (FCFA)")
                      .update_layout(xaxis_title=None, yaxis_visible=False), 230, False)
    with c2.container(border=True):
        ag = cur.groupby(["tranche_age", "genre"])["salaire_mensuel"].mean().reset_index()
        fig = px.line(ag, x="tranche_age", y="salaire_mensuel", color="genre", markers=True,
                      title="Par tranche d'âge", category_orders={"tranche_age": ORDRE_AGE},
                      color_discrete_map=COULEURS_GENRE)
        graphique(st, fig.update_layout(xaxis_title=None, yaxis_title="FCFA"), 330)
    with c3.container(border=True):
        dg = cur.groupby(["departement", "genre"])["salaire_mensuel"].mean().reset_index()
        graphique(st, px.bar(dg, y="departement", x="salaire_mensuel", color="genre", orientation="h",
                             text=dg["salaire_mensuel"].map(fcfa), title="Par département",
                             color_discrete_map=COULEURS_GENRE)
                  .update_layout(xaxis_visible=False, yaxis_title=None), 330)
    c1, c2, c3 = st.columns([1, 1.4, 2])
    with c1.container(border=True):
        gg = cur.groupby(["grade", "genre"])["salaire_mensuel"].mean().unstack()
        gg["Écart F/H"] = gg["F"] / gg["M"] - 1
        st.markdown("**Par grade**")
        st.dataframe(gg.reset_index().rename(columns={"F": "Femmes", "M": "Hommes"}), hide_index=True,
                     width="stretch", column_config={
                         "Femmes": st.column_config.NumberColumn(format="%.0f"),
                         "Hommes": st.column_config.NumberColumn(format="%.0f"),
                         "Écart F/H": st.column_config.NumberColumn(format="percent")})
    with c2.container(border=True):
        vg = cur.groupby(["ville_affectation", "genre"])["salaire_mensuel"].mean().reset_index()
        graphique(st, px.bar(vg, x="ville_affectation", y="salaire_mensuel", color="genre", barmode="group",
                             title="Par ville", color_discrete_map=COULEURS_GENRE)
                  .update_layout(xaxis_title=None, yaxis_title="FCFA"), 270)
    with c3.container(border=True):
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
        st.markdown(f"<div class='tuile'><div class='libelle'><b>Départs ({coh})</b></div>"
                    f"<div class='libelle'>CDI</div><div class='valeur'>{nb(hs.loc[hs['contrat'] == 'CDI', 'target'].sum())}</div>"
                    f"<div class='libelle'>CDD</div><div class='valeur'>{nb(hs.loc[hs['contrat'] == 'CDD', 'target'].sum())}</div>"
                    f"<div class='libelle'>Taux</div><div class='valeur'>{pct(hs['target'].mean())}</div></div>",
                    unsafe_allow_html=True)
    with c2:
        tuile(st, "Effectif", nb(len(sel)), "👥")
        st.write("")
        tuile(st, "% de nouveaux arrivants", pct(sel["arrivee"].mean()), "🧲")
    with c3.container(border=True):
        gg = sel.groupby(["grade", "genre"]).size().unstack(fill_value=0).reindex(columns=["F", "M"], fill_value=0)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=gg.index, x=-gg["F"], name="Femmes", orientation="h", marker_color=JAUNE,
                             text=gg["F"], textposition="inside"))
        fig.add_trace(go.Bar(y=gg.index, x=gg["M"], name="Hommes", orientation="h", marker_color=GRIS,
                             text=gg["M"], textposition="inside"))
        fig.update_layout(barmode="relative", title="Effectif par grade et par genre", xaxis_visible=False)
        graphique(st, fig, 260)
    with c4.container(border=True):
        e = sel.groupby("annee_embauche").size().reset_index(name="n")
        fig = px.line(e, x="annee_embauche", y="n", markers=True, text="n", title="Effectif par année d'embauche",
                      color_discrete_sequence=[JAUNE])
        graphique(st, fig.update_traces(textposition="top center", line_width=3)
                  .update_layout(xaxis_title=None, yaxis_title=None), 260)
    c1, c2 = st.columns([1.2, 1.4])
    with c1.container(border=True):
        dg = cur.groupby(["categorie_perf", "genre"]).size().reset_index(name="n")
        dg = dg[dg["categorie_perf"] != "nan"]
        dg["part"] = dg["n"] / dg.groupby("categorie_perf")["n"].transform("sum")
        graphique(st, px.bar(dg, x="categorie_perf", y="part", color="genre", text=dg["part"].map(pct),
                             title="Répartition par genre selon la performance", color_discrete_map=COULEURS_GENRE,
                             category_orders={"categorie_perf": ORDRE_PERF})
                  .update_layout(xaxis_title=None, yaxis_visible=False), 300)
    with c2.container(border=True):
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
            return f"background-color: rgba(242,200,17,{0.15 + 0.85 * v / vmax:.2f})"
        st.dataframe(m.style.map(teinte, subset=(m.index[:-1], m.columns[:-1])), width="stretch", height=230)
    st.markdown("<div class='note'>Niveaux de performance (note sur 5) : Insuffisante ≤ 2,5 · Attendue ≤ 3,5 · "
                "Bonne ≤ 4,2 · Excellente au-delà.</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 10. Absentéisme
# ---------------------------------------------------------------------------
def p_absenteisme():
    d, per, _ = en_tete(10, "Absentéisme", cle="abs")
    cur = d[d["periode"] == per]
    c1, c2, c3, c4 = st.columns([0.9, 1.4, 1.3, 1.3])
    with c1:
        tuile(st, "Taux d'absentéisme", pct(cur["taux_absenteisme"].mean(), 2), "👥")
        st.write("")
        tuile(st, "Hommes", pct(cur.loc[cur["genre"] == "M", "taux_absenteisme"].mean(), 2), "👨")
        st.write("")
        tuile(st, "Femmes", pct(cur.loc[cur["genre"] == "F", "taux_absenteisme"].mean(), 2), "👩")
    with c2.container(border=True):
        ca = cur.groupby(["tranche_age", "contrat"])["taux_absenteisme"].mean().reset_index()
        graphique(st, px.bar(ca, x="tranche_age", y="taux_absenteisme", color="contrat", barmode="group",
                             text=ca["taux_absenteisme"].map(lambda v: pct(v, 1)), title="Contrat × tranche d'âge",
                             category_orders={"tranche_age": ORDRE_AGE}, color_discrete_map={"CDI": JAUNE, "CDD": GRIS})
                  .update_layout(xaxis_title=None, yaxis_visible=False), 330)
    with c3.container(border=True):
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
        with st.container(border=True):
            ta = cur.groupby("tranche_anciennete")["taux_absenteisme"].agg(taux="mean", n="size").reindex(ORDRE_ANC).reset_index()
            graphique(st, px.bar(ta, x="tranche_anciennete", y="taux", title="Taux d'absentéisme par ancienneté",
                                 text=[f"{pct(t, 2)}<br>n={int(n)}" if n == n else "" for t, n in zip(ta["taux"], ta["n"])],
                                 color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False),
                      270, False)
    c1, c2, c3 = st.columns([0.9, 2.1, 1.6])
    with c1.container(border=True):
        st.markdown("**Par site**")
        s = cur.groupby("code_site")["taux_absenteisme"].mean().sort_values(ascending=False)
        for site, v in s.items():
            st.markdown(f"<div class='libelle'>{site}</div><div class='valeur' style='color:{JAUNE};font-size:1.3rem;"
                        f"font-weight:700'>{pct(v, 2)}</div>", unsafe_allow_html=True)
    with c2.container(border=True):
        dep = cur.groupby("departement").agg(eff=("id", "size"), taux=("taux_absenteisme", "mean")).sort_values("eff", ascending=False)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=dep.index, y=dep["eff"], name="Effectif", mode="lines+markers+text",
                                 text=dep["eff"], textposition="top center", line=dict(color=JAUNE, width=3)), secondary_y=False)
        fig.add_trace(go.Scatter(x=dep.index, y=dep["taux"], name="Taux d'absentéisme", mode="lines+markers",
                                 line=dict(color=GRIS, dash="dot")), secondary_y=True)
        fig.update_yaxes(tickformat=".1%", secondary_y=True)
        fig.update_layout(title="Effectif et taux d'absentéisme par département")
        graphique(st, fig, 300)
    with c3.container(border=True):
        t = cur.groupby(["departement", "genre"])["taux_absenteisme"].mean().unstack() \
            .reindex(columns=["F", "M"]) * 100
        t.insert(0, "Total", cur.groupby("departement")["taux_absenteisme"].mean() * 100)
        st.dataframe(t.reset_index().rename(columns={"departement": "Département", "F": "Femmes", "M": "Hommes"}),
                     hide_index=True, width="stretch", height=290,
                     column_config={c: st.column_config.NumberColumn(format="%.2f %%")
                                    for c in ["Total", "Femmes", "Hommes"]})


# ---------------------------------------------------------------------------
# 11. Absences par département (Leave Analysis)
# ---------------------------------------------------------------------------
def p_absences_dep():
    _, per, _ = en_tete(11, "Absences par département", cle="leave", avec_departement=False)
    gauche, droite = st.columns([0.8, 4])
    with gauche:
        st.markdown("<div class='bandeau'>Département</div>", unsafe_allow_html=True)
        dep = st.radio("Département", DEPARTEMENTS, key="dep_leave", label_visibility="collapsed")
    cur = DF[(DF["periode"] == per) & (DF["departement"] == dep)]
    with droite:
        c = st.columns(3)
        tuile(c[0], "Jours d'absence moyens (6 mois)", nb(cur["jours_abs_6m"].mean(), 2), "📅")
        tuile(c[1], "Jours non justifiés moyens", nb(cur["abs_non_just_6m"].mean(), 2), "🤒")
        tuile(c[2], "Événements d'absence moyens", nb(cur["nb_abs_6m"].mean(), 2), "🏃")
        st.write("")
        c1, c2, c3 = st.columns([1.2, 1, 1.6])
        with c1.container(border=True):
            ta = cur.groupby("tranche_anciennete")[["jours_abs_6m", "abs_non_just_6m"]].mean().reindex(ORDRE_ANC).reset_index()
            ta = ta.rename(columns={"jours_abs_6m": "Toutes absences", "abs_non_just_6m": "Non justifiées"})
            graphique(st, px.bar(ta.melt("tranche_anciennete", var_name="type", value_name="jours"),
                                 x="tranche_anciennete", y="jours", color="type", barmode="group",
                                 title="Jours moyens par ancienneté",
                                 color_discrete_map={"Toutes absences": JAUNE, "Non justifiées": GRIS})
                      .update_layout(xaxis_title=None, yaxis_title=None), 270)
        with c2.container(border=True):
            g = cur.groupby("grade")["jours_abs_6m"].sum().reset_index()
            graphique(st, anneau(g, "grade", "jours_abs_6m", "Jours d'absence par grade"), 270)
        with c3.container(border=True):
            p = cur.groupby("poste").agg(total=("jours_abs_6m", "sum"), moyen=("jours_abs_6m", "mean")) \
                .sort_values("total", ascending=False).head(10)
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=p.index, y=p["total"], name="Total des jours", marker_color=JAUNE, text=p["total"]),
                          secondary_y=False)
            fig.add_trace(go.Scatter(x=p.index, y=p["moyen"], name="Moyenne par personne", mode="lines+markers",
                                     line=dict(color=GRIS_FONCE)), secondary_y=True)
            fig.update_layout(title="Absences par poste")
            graphique(st, fig, 270)
        with st.container(border=True):
            st.markdown("**Collaborateurs les plus absents** (identifiants anonymisés)")
            if not auth.peut_voir_nominatif():
                st.info("Liste individuelle réservée au profil DRH. Le profil Direction générale consulte les "
                        "indicateurs agrégés ci-dessus.")
                return
            t = cur.sort_values(["jours_abs_6m", "abs_non_just_6m"], ascending=False).head(10)[
                ["id", "poste", "grade", "contrat", "jours_abs_6m", "abs_non_just_6m", "nb_abs_6m"]]
            st.dataframe(t.rename(columns={"id": "Identifiant", "poste": "Poste", "grade": "Grade", "contrat": "Contrat",
                                           "jours_abs_6m": "Jours d'absence", "abs_non_just_6m": "Non justifiés",
                                           "nb_abs_6m": "Événements"}), hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# 12. Profil des départs (Termination Profile)
# ---------------------------------------------------------------------------
def p_profil_departs():
    d, per, _ = en_tete(12, "Profil des départs", periodes=PERIODES_HIST, cle="term")
    hc = d[d["periode"] == per]
    partis = hc[hc["target"] == 1]
    c = st.columns(3)
    tuile(c[0], "Départs dans les 6 mois", nb(len(partis)), "🚪")
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

    with c1.container(border=True):
        a = taux_par("tranche_anciennete", ORDRE_ANC)
        graphique(st, px.bar(a, x="tranche_anciennete", y="taux", text="texte",
                             title="Taux de départ par ancienneté (départs / effectif)",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 250)
    with c2.container(border=True):
        cg = partis.groupby(["contrat", "genre"]).size().reset_index(name="n")
        graphique(st, px.bar(cg, x="contrat", y="n", color="genre", text="n", title="Par contrat",
                             color_discrete_map=COULEURS_GENRE).update_layout(xaxis_title=None, yaxis_visible=False), 250)
    with c3.container(border=True):
        g = taux_par("grade", ["G1", "G2", "G3", "G4", "G5"])
        graphique(st, px.bar(g, x="grade", y="taux", text="texte", title="Taux de départ par grade",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 250)
    c1, c2, c3 = st.columns([1.3, 1, 1.3])
    with c1.container(border=True):
        v = partis.groupby(["ville_affectation", "genre"]).size().reset_index(name="n")
        graphique(st, px.bar(v, x="ville_affectation", y="n", color="genre", text="n", title="Par ville et par genre",
                             color_discrete_map=COULEURS_GENRE).update_layout(xaxis_title=None, yaxis_visible=False), 280)
    with c2.container(border=True):
        graphique(st, anneau(partis["genre"].value_counts().reset_index(), "genre", "count", "Par genre",
                             COULEURS_GENRE).update_traces(hole=0), 280)
    with c3.container(border=True):
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
    tuile(c[0], "Taux de départ", pct(hc["target"].mean()), "🚪")
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
    with c1.container(border=True):
        gp = h[h["genre"].isin(["F", "M"])].groupby(["periode", "genre"])["target"].mean().reset_index()
        fig = px.line(gp, x="periode", y="target", color="genre", markers=True, title="Taux de départ par genre",
                      color_discrete_map=COULEURS_GENRE, line_dash="genre", line_dash_map={"F": "dot", "M": "solid"})
        graphique(st, fig.update_layout(xaxis_title=None, yaxis_title=None, yaxis_tickformat=".0%"), 280)
    with c2.container(border=True):
        dd = hc.groupby("departement")["target"].agg(taux="mean", departs="sum", n="size")
        dd = dd[dd["n"] >= 50].sort_values("taux", ascending=False).head(6).sort_values("taux").reset_index()
        graphique(st, px.bar(dd, y="departement", x="taux", orientation="h",
                             text=[f"{pct(t)} ({int(b)}/{int(n)})" for t, b, n in zip(dd["taux"], dd["departs"], dd["n"])],
                             title="Taux de départ les plus élevés (départements ≥ 50 personnes)",
                             color_discrete_sequence=[JAUNE])
                  .update_layout(xaxis_visible=False, yaxis_title=None), 280)
    with st.container(border=True):
        tc = h.groupby(["periode", "contrat"])["target"].sum().reset_index()
        tc["taux"] = tc["target"] / h.groupby("periode").size().reindex(tc["periode"]).values
        graphique(st, px.bar(tc, x="periode", y="taux", color="contrat", text=tc["taux"].map(pct),
                             title="Tendance du taux de départ, par contrat", color_discrete_map={"CDI": JAUNE, "CDD": GRIS})
                  .update_layout(xaxis_title=None, yaxis_visible=False), 280)


# ---------------------------------------------------------------------------
# Anticipation des départs
# ---------------------------------------------------------------------------
def p_anticipation():
    en_tete(15, "Anticipation des départs", periodes=None, cle="antic", avec_departement=False)
    act, _ = modele_risque()
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
    with c1.container(border=True):
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
    with c2.container(border=True):
        lect = pd.DataFrame({
            "Niveau": ORDRE_NIVEAUX,
            "Règle": ["5 % des scores les plus hauts", "5 à 16 %", "16 à 50 %", "Moitié basse"],
            "Au 31/12/2024": actuel.values,
            "Départs observés": [pct(x, 0) for x in taux["taux"]],
            "Départs captés": [pct(x, 0) for x in taux["part_des_departs"]],
        })
        st.dataframe(lect, hide_index=True, width="stretch")
        st.caption("Lecture : sur 10 collaborateurs « Très élevé », environ "
                   f"{int(round(taux.loc['Très élevé', 'taux'] * 10))} sont partis dans les 6 mois lors des validations ; "
                   f"pour « Faible », moins de 1 sur 10.")

    # 2. Capacité d'accompagnement
    st.markdown("#### 2 · Combien de collaborateurs la DRH peut-elle accompagner ?")
    c1, c2 = st.columns([1, 2])
    with c1.container(border=True):
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
    with c2.container(border=True):
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
    with rep1.container(border=True):
        r = groupe["departement"].value_counts().reset_index()
        r["part"] = r["count"] / r["departement"].map(act["departement"].value_counts())
        graphique(st, px.bar(r.sort_values("count"), y="departement", x="count", orientation="h",
                             text=[f"{c} ({pct(p_, 0)} du département)" for c, p_ in zip(r.sort_values('count')['count'], r.sort_values('count')['part'])],
                             title="Groupe accompagné par département", color_discrete_sequence=[JAUNE])
                  .update_layout(xaxis_visible=False, yaxis_title=None), 320, False)
    with rep2.container(border=True):
        r = groupe["poste"].value_counts().head(10).reset_index().sort_values("count")
        graphique(st, px.bar(r, y="poste", x="count", orientation="h", text="count",
                             title="Groupe accompagné : 10 postes les plus représentés", color_discrete_sequence=[GRIS])
                  .update_layout(xaxis_visible=False, yaxis_title=None), 320, False)

    # 3. Liste (DRH) ou vue agrégée (Direction)
    st.markdown("#### 3 · Qui est concerné ?")
    if not auth.peut_voir_nominatif():
        st.info("La liste nominative est réservée au profil DRH. Vue agrégée par département et par niveau :")
        agg = act.groupby(["departement", "niveau_risque"]).size().unstack(fill_value=0).reindex(columns=ORDRE_NIVEAUX,
                                                                                               fill_value=0)
        agg["Effectif"] = agg.sum(axis=1)
        st.dataframe(agg.reset_index().rename(columns={"departement": "Département"}), hide_index=True, width="stretch")
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
    st.dataframe(tab.style.map(lambda v: f"background-color:{COULEURS_NIVEAU.get(v, '#fff')};"
                                         f"color:{'#fff' if v == 'Très élevé' else '#222'}", subset=["niveau_risque"]),
                 hide_index=True, width="stretch", height=380,
                 column_order=["id", "niveau_risque", "centile", "probabilite", "departement", "poste", "grade",
                               "contrat", "facteurs"],
                 column_config={"id": "Identifiant", "niveau_risque": "Niveau",
                                "centile": st.column_config.NumberColumn("Plus élevé que (%)", format="%.1f",
                                                                         help="Part de l'effectif ayant un score plus faible"),
                                "probabilite": st.column_config.NumberColumn("Probabilité estimée", format="%.2f"),
                                "departement": "Département", "poste": "Poste", "grade": "Grade", "contrat": "Contrat",
                                "facteurs": st.column_config.TextColumn("Principaux signaux", width="large")})
    o1, o2, o3 = st.columns([2, 1, 1], vertical_alignment="bottom")
    cible = o1.selectbox("Ouvrir la fiche de", tab["id"].tolist() or ["—"], key="cible_fiche")
    if o2.button("Ouvrir la fiche ➜", width="stretch", disabled=not len(tab)):
        st.session_state["fiche_id"] = cible
        st.switch_page(PAGE["fiche-collaborateur"])
    o3.download_button("⬇️ Liste (CSV)", tab.to_csv(index=False).encode("utf-8"), "anticipation_departs.csv",
                       "text/csv", width="stretch")
    st.caption("Liste confidentielle : données individuelles réservées à la DRH. Le genre n'est pas utilisé par ce modèle.")


# ---------------------------------------------------------------------------
# 15. Profil département
# ---------------------------------------------------------------------------
def p_profil_departement():
    _, per, _ = en_tete(15, "Profil département", cle="pdep", avec_departement=False)
    gauche, droite = st.columns([0.8, 4])
    with gauche:
        st.markdown("<div class='bandeau'>Département</div>", unsafe_allow_html=True)
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
                tuile(k[0], "Effectif", nb(len(cur)), "👥")
                tuile(k[1], "Arrivées", nb(cur["arrivee"].sum()), "🧲")
                tuile(k[2], "Taux d'absentéisme", pct(cur["taux_absenteisme"].mean(), 2), "🤒")
                with st.container(border=True):
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
                tuile(k[0], f"Départs ({coh})", nb(hc["target"].sum()), "🚪")
                tuile(k[1], "Taux de départ", pct(hc["target"].mean()), "📉")
                tuile(k[2], "Taux entreprise", pct(he["target"].mean()), "🏢")
                with st.container(border=True):
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
                with st.container(border=True):
                    r = s.groupby(["poste", "niveau_risque"]).size().reset_index(name="n")
                    graphique(st, px.bar(r, y="poste", x="n", color="niveau_risque", orientation="h",
                                         title="Niveau de risque par poste",
                                         color_discrete_map=COULEURS_NIVEAU,
                                         category_orders={"niveau_risque": ORDRE_NIVEAUX})
                              .update_layout(xaxis_title=None, yaxis_title=None), 300)
        with dr.container(border=True):
            st.markdown("#### 📄 Synthèse")
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
    k = st.columns(4)
    tuile(k[0], "Lignes analysées (historique + 31/12/2024)", nb(a["n"]), "🗂️")
    tuile(k[1], "Corrections de valeurs aberrantes", nb(t.loc[t["Anomalie"].str.startswith(("Salaire nul", "Salaire plus",
                                                                                             "Note", "Embauche")), "Total"].sum()), "🛠️")
    tuile(k[2], "Dates d'absence « du futur » neutralisées",
          nb(t.loc[t["Anomalie"].str.startswith("Dernière absence"), "Total"].sum()), "⏱️")
    tuile(k[3], "Libellés harmonisés", nb(a["libelles"]["Lignes corrigées"].sum()), "🔤")
    st.write("")
    st.markdown("#### Anomalies détectées dans les fichiers bruts et règle appliquée")
    st.dataframe(t, hide_index=True, width="stretch")
    st.markdown(
        "<div class='avertissement'><b>Point clé :</b> 341 lignes de l'historique avaient une dernière absence datée "
        "<i>après</i> la date de référence, ce qui n'arrive jamais dans les données du 31/12/2024. Utiliser cette date "
        "aurait fait apprendre au modèle une information du futur. Elle est neutralisée, et la récence des absences est "
        "recalculée à partir des absences mois par mois.</div>", unsafe_allow_html=True)
    st.markdown("#### Libellés harmonisés")
    st.dataframe(a["libelles"], hide_index=True, width="stretch")
    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.markdown("#### Valeurs manquantes")
        st.dataframe(a["manquants"], hide_index=True, width="stretch",
                     column_config={"Manquant (historique)": st.column_config.NumberColumn(format="percent"),
                                    "Manquant (31/12/2024)": st.column_config.NumberColumn(format="percent")})
        st.caption("Une valeur manquante n'est jamais remplacée par une valeur faible : les indicateurs portent sur la "
                   "population renseignée, et la couverture est affichée en tête de chaque page.")
    with c2:
        st.markdown("#### Contrôles de cohérence")
        st.dataframe(a["coherence"], hide_index=True, width="stretch")


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
    with c1.container(border=True):
        st.markdown("##### 📊 Classeur Excel")
        st.caption("Lisez-moi et définitions · synthèse par période · départements · rémunération par grade · "
                   "turnover par cohorte · fiabilité des niveaux · anticipation" + (" (agrégée et nominative)" if nominatif
                                                                                     else " (agrégée)")
                   + " · qualité des données · dictionnaire.")
        if st.button("Préparer le classeur", key="prep_xlsx", width="stretch"):
            st.session_state["xlsx"] = exports.excel(d, sc, taux, audit(), contexte, nominatif)
        if "xlsx" in st.session_state:
            st.download_button("⬇️ Télécharger le classeur (.xlsx)", st.session_state["xlsx"],
                               f"TelcoPeople_RH_{per.replace(' ', '_')}.xlsx", width="stretch", type="primary",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with c2.container(border=True):
        st.markdown("##### 📄 Synthèse PDF")
        st.caption("Deux pages pour un comité : à retenir, indicateurs clés, points d'attention, fiabilité des niveaux "
                   "de risque, tableau des départements, méthode et limites. Aucune donnée individuelle.")
        if st.button("Préparer la synthèse", key="prep_pdf", width="stretch"):
            st.session_state["pdf"] = synthese_pdf(d, sc, taux, per, contexte, nominatif)
        if "pdf" in st.session_state:
            st.download_button("⬇️ Télécharger la synthèse (.pdf)", st.session_state["pdf"],
                               f"TelcoPeople_synthese_RH_{per.replace(' ', '_')}.pdf", "application/pdf",
                               width="stretch", type="primary")


def synthese_pdf(d, sc, taux, per, contexte, nominatif):
    cur = d[d["periode"] == per]
    coh = cohorte(per)
    hc = d[(d["periode"] == coh) & (d["jeu"] == "historique")]
    prec = precedente(per)
    avant = d[d["periode"] == prec] if prec else None
    evol = (len(cur) / len(avant) - 1) if avant is not None and len(avant) else None
    synthese = (f"Au {DATES_LIB[per]}, le périmètre compte {nb(len(cur))} collaborateurs"
                + (f" ({pct(evol)} en six mois)" if evol is not None else "") + ". "
                f"Sur la dernière cohorte connue ({coh}), {int(hc['target'].sum())} collaborateurs sur {nb(len(hc))} sont "
                f"partis dans les six mois ({pct(hc['target'].mean())}). Le taux d'absentéisme est de "
                f"{pct(cur['taux_absenteisme'].mean(), 2)}. {pct((cur['ratio_salaire_reference'] < 0.9).mean(), 0)} des "
                f"collaborateurs sont payés sous 90 % de la référence de leur grade, l'une des caractéristiques les plus "
                f"associées aux départs observés, avec un engagement faible.")
    kpis = [("Effectif", nb(len(cur)), f"au {DATES_LIB[per]}"),
            ("Masse salariale mensuelle", f"{fcfa(cur['salaire_mensuel'].sum())} FCFA", "salaires de base"),
            ("Salaire médian", f"{nb(cur['salaire_mensuel'].median())} FCFA", ""),
            ("Taux d'absentéisme", pct(cur["taux_absenteisme"].mean(), 2), f"jours d'absence ÷ {JOURS_OUVRES_6M} jours ouvrés"),
            ("Performance moyenne", f"{nb(cur['performance_actuelle'].mean(), 2)} / 5",
             f"renseignée pour {pct(cur['performance_actuelle'].notna().mean(), 0)} de l'effectif"),
            ("Taux de départ à 6 mois", pct(hc["target"].mean()), f"cohorte {coh} : {int(hc['target'].sum())} sur {nb(len(hc))}"),
            ("Niveau de risque très élevé ou élevé", nb(sc["signale"].sum()), "au 31/12/2024")]
    alertes = [f"{nb((cur['ratio_salaire_reference'] < 0.9).sum())} collaborateurs payés sous 90 % de la référence de leur grade.",
               f"{len(cur[(cur['performance_actuelle'] >= 4) & (cur['engagement_actuel'] < 3)])} profils performants mais "
               f"peu engagés (performance ≥ 4 et engagement < 3).",
               f"{int(cur['performance_actuelle'].isna().sum())} évaluations de performance manquantes."]
    niveaux = pd.DataFrame({"part": ["5 %", "11 %", "34 %", "50 %"], "taux": [pct(x, 0) for x in taux["taux"]],
                            "fourchette": [f"{pct(a, 0)} à {pct(b, 0)}" for a, b in zip(taux["taux_min"], taux["taux_max"])]},
                           index=ORDRE_NIVEAUX)
    t = DF[DF["periode"] == per].groupby("departement").agg(Effectif=("id", "size"),
                                                            Absentéisme=("taux_absenteisme", "mean"))
    td = DF[DF["periode"] == coh].groupby("departement")["target"].agg(["sum", "size", "mean"])
    t = t.join(td).reset_index().sort_values("Effectif", ascending=False)
    deps = pd.DataFrame({"Département": t["departement"], "Effectif": t["Effectif"].map(nb),
                         "Absentéisme": t["Absentéisme"].map(lambda v: pct(v, 2)),
                         f"Départs {coh}": [f"{int(a)} sur {int(n)}" if n == n else "—" for a, n in zip(t["sum"], t["size"])],
                         "Taux de départ": t["mean"].map(pct)})
    return exports.pdf(synthese, kpis, alertes, niveaux, deps, contexte, nominatif)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
REGISTRE = [
    # (section, titre, fonction, url, icône, réservé au profil nominatif)
    ("Pilotage", "Vue d'ensemble RH", p_vue_ensemble, "vue-ensemble", "dashboard", False),
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
    st.navigation([st.Page(auth.page_connexion, title="Connexion", icon=":material/lock:", url_path="connexion")],
                  position="hidden").run()
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
SECTIONS = {"": [ACCUEIL, PAGE["vue-ensemble"]]}
for r in REGISTRE_VISIBLE[1:]:
    SECTIONS.setdefault(r["section"], []).append(PAGE[r["url"]])
COURANTE = st.navigation(SECTIONS, position="top")
COURANTE.run()
