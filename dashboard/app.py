"""TelcomCI · HR Analytics — dashboard RH sur le modèle « cycle de vie du collaborateur ».

Une page d'accueil et quinze pages thématiques, appliquées aux données TelcoPeople.
Lancement local :  streamlit run dashboard/app.py
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from preparation import JOURS_OUVRES_6M, TAUX_SIGNALEMENT, charger, entrainer_modele, facteurs_individuels

st.set_page_config(page_title="TelcomCI · HR Analytics", page_icon="🟡", layout="wide",
                   initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# Charte graphique : jaune et gris
# ---------------------------------------------------------------------------
JAUNE, JAUNE_CLAIR, GRIS, GRIS_FONCE, GRIS_CLAIR = "#F2C811", "#F7E08A", "#A6A6A6", "#5F5F5F", "#E3E3E3"
PALETTE = [JAUNE, GRIS, GRIS_FONCE, JAUNE_CLAIR, GRIS_CLAIR]
COULEURS_GENRE = {"F": JAUNE, "M": GRIS, "INCONNU": GRIS_CLAIR}
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
  section[data-testid="stSidebar"], div[data-testid="stSidebarCollapsedControl"],
  button[data-testid="stExpandSidebarButton"] {{display: none !important;}}
  .st-key-nav-pages button {{padding: 2px 0 !important; min-height: 2.1rem !important; font-size: 1.05rem !important;}}
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
def scores():
    df, feats = donnees()
    modele = entrainer_modele(df, feats)
    act = df[df["jeu"] == "actuel"].copy()
    act["probabilite"] = modele.predict_proba(act[feats])[:, 1]
    rang = act["probabilite"].rank(pct=True)
    act["niveau_risque"] = np.where(rang > 1 - TAUX_SIGNALEMENT, "Élevé", np.where(rang > 0.6, "Modéré", "Faible"))
    act["signale"] = rang > 1 - TAUX_SIGNALEMENT
    act["facteurs"] = facteurs_individuels(modele, act[feats])
    return act


DF, _ = donnees()
PERIODES = sorted(DF["periode"].unique())
PERIODES_HIST = sorted(DF.loc[DF["jeu"] == "historique", "periode"].unique())
DEPARTEMENTS = sorted(DF["departement"].unique())
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


def navigation(conteneur):
    """Boutons ◀ 🏠 ▶ : page précédente, accueil, page suivante (comme les icônes du rapport Power BI)."""
    i = NOMS.index(st.session_state["page"])
    with conteneur.container(key="nav-pages"):
        c = st.columns(3, gap="small")
        c[0].button("◀", key="nav_prec", help="Page précédente", width="stretch", disabled=i <= 1,
                    on_click=aller_a, args=(NOMS[max(i - 1, 0)],))
        c[1].button("🏠", key="nav_accueil", help="Accueil", width="stretch", on_click=aller_a, args=(NOMS[0],))
        c[2].button("▶", key="nav_suiv", help="Page suivante", width="stretch", disabled=i >= len(NOMS) - 1,
                    on_click=aller_a, args=(NOMS[min(i + 1, len(NOMS) - 1)],))


def en_tete(numero, titre, periodes=PERIODES, cle="", avec_departement=True, defaut=None):
    """Titre de page + segments Période / Département + navigation, à la manière des en-têtes Power BI."""
    gauche, milieu, droite, nav = st.columns([3, 3, 1.3, 0.9])
    navigation(nav)
    gauche.markdown(f"<div class='titre-page'><span>{numero}</span>{titre}</div>", unsafe_allow_html=True)
    periode = None
    if periodes:
        defaut = defaut or periodes[-1]
        periode = milieu.pills("Période", periodes, default=defaut, key=f"per_{cle}", label_visibility="collapsed")
        periode = periode or defaut
    dep = "Tous"
    if avec_departement:
        dep = droite.selectbox("Département", ["Tous"] + DEPARTEMENTS, key=f"dep_{cle}")
    d = DF if dep == "Tous" else DF[DF["departement"] == dep]
    st.write("")
    return d, periode, dep


def precedente(periode, liste=PERIODES):
    i = liste.index(periode)
    return liste[i - 1] if i > 0 else None


def cohorte(periode):
    """Le départ à 6 mois n'est connu que pour les périodes historiques."""
    return periode if periode in PERIODES_HIST else PERIODES_HIST[-1]


def aller_a(page):
    st.session_state["page"] = page
    st.query_params["page"] = str(NOMS.index(page))



# ---------------------------------------------------------------------------
# 0. Accueil
# ---------------------------------------------------------------------------
def p_accueil():
    """Accueil : les 15 pages disposées autour du cercle « cycle de vie », chacune cliquable."""
    st.markdown("<div class='titre-page'><span>TelcomCI</span>HR Analytics</div>", unsafe_allow_html=True)

    L, H, cx, cy = 1020, 640, 510, 320            # zone de dessin (px) et centre du cercle

    def arc(r, a0, a1, couleur, epaisseur):
        """Arc de cercle SVG lisse entre deux angles (degrés, 0 = droite, sens horaire)."""
        x0, y0 = cx + r * np.cos(np.radians(a0)), cy + r * np.sin(np.radians(a0))
        x1, y1 = cx + r * np.cos(np.radians(a1)), cy + r * np.sin(np.radians(a1))
        grand = 1 if (a1 - a0) % 360 > 180 else 0
        return (f"<path d='M {x0:.1f} {y0:.1f} A {r} {r} 0 {grand} 1 {x1:.1f} {y1:.1f}' fill='none' "
                f"stroke='{couleur}' stroke-width='{epaisseur}' stroke-linecap='butt'/>")

    svg = (f"<svg width='{L}' height='{H}' style='position:absolute;left:0;top:0'>"
           + arc(172, 150, 70, GRIS_FONCE, 40)        # grand arc gris foncé
           + arc(141, 230, 140, GRIS, 34)             # arc gris moyen
           + arc(113, 320, 230, JAUNE, 30)            # arc jaune intérieur
           + f"<text x='{cx}' y='{cy - 6}' text-anchor='middle' font-size='22' font-weight='700' fill='{GRIS_FONCE}'"
             " font-family='sans-serif'>Cycle de vie</text>"
           + f"<text x='{cx}' y='{cy + 22}' text-anchor='middle' font-size='22' font-weight='700' fill='{GRIS_FONCE}'"
             " font-family='sans-serif'>du collaborateur</text></svg>")

    etiquettes = []
    noms = NOMS[1:]
    # 1 en haut ; 2 à 8 descendent à droite ; 9 à 15 remontent à gauche (comme le rapport Power BI)
    angles = [-90] + [-66 + 24 * k for k in range(7)] + [102 + 24 * k for k in range(7)]
    for i, nom in enumerate(noms):
        numero, titre = nom.split(" · ", 1)
        angle = angles[i]
        x = cx + 255 * np.cos(np.radians(angle))
        y = cy + (-292 if i == 0 else 268 * np.sin(np.radians(angle)))
        droite = np.cos(np.radians(angle)) > 0
        decalage = ("translate(-50%,-50%)" if i == 0                  # 1 centré au-dessus du cercle
                    else "translate(0,-50%)" if droite else "translate(-100%,-50%)")
        etiquettes.append(
            f"<a class='acc-lien' href='?page={i + 1}' target='_self' "
            f"style='left:{x:.0f}px;top:{y:.0f}px;transform:{decalage}'>"
            f"<span class='acc-num'>{numero}</span><span class='acc-titre'>{titre}</span></a>")

    st.markdown(f"""
<style>
  .acc-zone {{position:relative; width:{L}px; height:{H}px; margin:0 auto;}}
  .acc-defile {{overflow-x:auto;}}
  .acc-lien {{position:absolute; display:flex; align-items:center; gap:6px; text-decoration:none !important;
             white-space:nowrap; transition: transform .15s;}}
  .acc-num {{background:radial-gradient(circle at 35% 30%, #FFF6C2, {JAUNE} 60%); color:#333; font-weight:700;
            border-radius:50%; width:30px; height:30px; display:flex; align-items:center; justify-content:center;
            box-shadow:0 1px 3px rgba(0,0,0,.35); font-size:.9rem;}}
  .acc-titre {{background:#fff; color:#222; font-weight:600; padding:5px 11px; border-radius:3px;
              box-shadow:2px 3px 6px rgba(0,0,0,.18); font-size:.93rem;}}
  .acc-lien:hover .acc-titre {{background:{JAUNE}; color:#222;}}
  .acc-lien:hover .acc-num {{box-shadow:0 0 0 3px rgba(242,200,17,.45);}}
</style>
<div class='acc-defile'><div class='acc-zone'>{svg}{''.join(etiquettes)}</div></div>
""", unsafe_allow_html=True)

    act = DF[DF["jeu"] == "actuel"]
    st.markdown(f"<div class='note' style='text-align:center'>Cliquez sur un thème pour ouvrir son tableau de bord. "
                f"Sur chaque page, les boutons ◀ 🏠 ▶ en haut à droite permettent de naviguer.<br>"
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
    t = hc.groupby("grade")["target"].mean().reset_index()
    graphique(c[3], px.bar(t, x="grade", y="target", text=t["target"].map(pct), title="Taux de départ par grade",
                           color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 200)
    t = hc.groupby("tranche_anciennete")["target"].mean().reindex(ORDRE_ANC).reset_index()
    graphique(c[4], px.bar(t, x="tranche_anciennete", y="target", text=t["target"].map(lambda v: pct(v, 0)),
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
    _, _, dep = en_tete(4, "Fiche collaborateur", periodes=None, cle="fiche")
    sc = scores()
    if dep != "Tous":
        sc = sc[sc["departement"] == dep]
    sc = sc.sort_values("probabilite", ascending=False)
    choix = st.selectbox("Collaborateur (du risque le plus élevé au plus faible)", sc["id"].tolist(),
                         format_func=lambda i: f"{i} · {sc.loc[sc['id'] == i, 'poste'].iloc[0]} · "
                                               f"{sc.loc[sc['id'] == i, 'departement'].iloc[0]}")
    p = sc[sc["id"] == choix].iloc[0]
    tout = scores()
    pairs = tout[tout["departement"] == p["departement"]]
    gauche, droite = st.columns([1, 2.6])
    with gauche:
        couleur = {"Élevé": "#c0392b", "Modéré": JAUNE, "Faible": "#4f8a5b"}[p["niveau_risque"]]
        st.markdown(
            f"<div style='background:{JAUNE_CLAIR};border-radius:6px;padding:14px;min-height:430px'>"
            f"<div style='background:{couleur};color:white;text-align:center;font-weight:700;border-radius:4px;"
            f"padding:4px'>Risque {p['niveau_risque'].lower()}</div>"
            f"<div style='font-size:4rem;text-align:center'>{'👩' if p['genre'] == 'F' else '👨'}</div>"
            f"<b>{p['id']}</b><br><span class='note'>Identifiant</span><br><br>"
            f"<b>{p['poste']}</b><br><span class='note'>Poste</span><br><br>"
            f"<b>{p['departement']}</b><br><span class='note'>Département</span><br><br>"
            f"<b>{int((tout['probabilite'] < p['probabilite']).mean() * 100)} %</b><br>"
            f"<span class='note'>de l'effectif a un risque plus faible</span></div>", unsafe_allow_html=True)
    with droite:
        o = st.tabs(["Informations", "Poste", "Rémunération", "Absences", "Performance & engagement", "Facteurs de risque"])
        def lignes(rows):
            st.dataframe(pd.DataFrame(rows, columns=["", "Valeur"]), hide_index=True, width="stretch")
        with o[0]:
            lignes([("Genre", p["genre"]), ("Âge", f"{nb(p['age'])} ans"), ("Génération", p["generation"]),
                    ("Niveau d'études", p["niveau_etude"]), ("Ville", p["ville_affectation"]), ("Site", p["code_site"])])
        with o[1]:
            lignes([("Poste", p["poste"]), ("Département", p["departement"]), ("Grade", p["grade"]),
                    ("Contrat", p["contrat"]), ("Ancienneté", f"{nb(p['anciennete'], 1)} ans"),
                    ("Dernière promotion", "Jamais" if p["jamais_promu"] else f"il y a {nb(p['annees_depuis_promotion'], 1)} ans")])
        with o[2]:
            lignes([("Salaire mensuel", f"{nb(p['salaire_mensuel'])} FCFA"),
                    ("Référence du grade", f"{nb(p['reference_salaire_grade'])} FCFA"),
                    ("Salaire / référence", nb(p["ratio_salaire_reference"], 2)),
                    ("Évolution sur 12 mois", pct(p["taux_evolution_salaire"])),
                    (f"Ratio moyen {p['departement']}", nb(pairs["ratio_salaire_reference"].mean(), 2))])
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
                    (f"Engagement moyen {p['departement']}", nb(pairs["engagement_actuel"].mean(), 2))])
        with o[5]:
            st.markdown(f"**Probabilité estimée de départ dans les 6 mois : {pct(p['probabilite'])}**")
            for f in (p["facteurs"].split(" · ") if p["facteurs"] else ["Aucun facteur aggravant marqué"]):
                st.markdown(f"- {f}")
            st.markdown("<div class='note'>Outil de priorisation des entretiens, pas une décision. "
                        "Données individuelles à traiter de façon confidentielle.</div>", unsafe_allow_html=True)


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
        g = cur.groupby("grade")["salaire_mensuel"].mean().reset_index()
        graphique(st, anneau(g, "grade", "salaire_mensuel", "Salaire moyen par grade (FCFA)", fmt="fcfa"), 300, False)
    c1, c2 = st.columns([1.5, 1.4])
    with c1.container(border=True):
        ag = cur[cur["genre"].isin(["F", "M"])].groupby(["tranche_age", "genre"])["salaire_mensuel"].mean().reset_index()
        fig = px.area(ag, x="tranche_age", y="salaire_mensuel", color="genre", title="Salaire moyen par âge et par genre",
                      category_orders={"tranche_age": ORDRE_AGE}, color_discrete_map=COULEURS_GENRE, markers=True)
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
            graphique(st, anneau(moy.reset_index(), "genre", "salaire_mensuel", "Salaire moyen par genre (FCFA)",
                                 COULEURS_GENRE, fmt="fcfa"), 230, False)
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
        st.button("ABSENCES PAR DÉPARTEMENT ➜", width="stretch", type="primary", on_click=aller_a,
                  args=(NOMS[11],))
        with st.container(border=True):
            ta = cur.groupby("tranche_anciennete")["taux_absenteisme"].mean().reindex(ORDRE_ANC).reset_index()
            graphique(st, anneau(ta, "tranche_anciennete", "taux_absenteisme", "Taux d'absentéisme par ancienneté", fmt="pct"), 270, False)
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
    with c1.container(border=True):
        a = partis["tranche_anciennete"].value_counts().reindex(ORDRE_ANC).fillna(0).reset_index()
        graphique(st, px.bar(a, x="tranche_anciennete", y="count", text="count", title="Par ancienneté",
                             color_discrete_sequence=[JAUNE]).update_layout(xaxis_title=None, yaxis_visible=False), 250)
    with c2.container(border=True):
        cg = partis.groupby(["contrat", "genre"]).size().reset_index(name="n")
        graphique(st, px.bar(cg, x="contrat", y="n", color="genre", text="n", title="Par contrat",
                             color_discrete_map=COULEURS_GENRE).update_layout(xaxis_title=None, yaxis_visible=False), 250)
    with c3.container(border=True):
        g = partis["grade"].value_counts().reindex(["G1", "G2", "G3", "G4", "G5"]).fillna(0).reset_index()
        graphique(st, px.funnel(g, y="grade", x="count", title="Par grade", color_discrete_sequence=[JAUNE])
                  .update_layout(yaxis_title=None), 250)
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
    st.markdown("<div class='note'>Le motif de départ (démission, licenciement…) n'est pas enregistré dans les données : "
                "la répartition par niveau de performance le remplace.</div>", unsafe_allow_html=True)


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
                col.markdown(f"<div style='border-left:3px solid {JAUNE};padding-left:8px'>"
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
        dd = hc.groupby("departement")["target"].mean().sort_values(ascending=False).head(6).sort_values().reset_index()
        graphique(st, px.bar(dd, y="departement", x="target", orientation="h", text=dd["target"].map(pct),
                             title="Départements avec le plus de départs", color_discrete_sequence=[JAUNE])
                  .update_layout(xaxis_visible=False, yaxis_title=None), 280)
    with st.container(border=True):
        tc = h.groupby(["periode", "contrat"])["target"].sum().reset_index()
        tc["taux"] = tc["target"] / h.groupby("periode").size().reindex(tc["periode"]).values
        graphique(st, px.bar(tc, x="periode", y="taux", color="contrat", text=tc["taux"].map(pct),
                             title="Tendance du taux de départ, par contrat", color_discrete_map={"CDI": JAUNE, "CDD": GRIS})
                  .update_layout(xaxis_title=None, yaxis_visible=False), 280)


# ---------------------------------------------------------------------------
# 14. Prédiction des départs
# ---------------------------------------------------------------------------
def p_prediction():
    gauche, droite, nav = st.columns([3, 1.4, 0.9])
    navigation(nav)
    gauche.markdown("<div class='titre-page'><span>14</span>Prédiction des départs</div>", unsafe_allow_html=True)
    droite.button("PRÉDICTION PAR DÉPARTEMENT ➜", type="primary", width="stretch", on_click=aller_a, args=(NOMS[15],))
    st.write("")
    sc = scores()
    f, t = st.columns([1, 4])
    with f.container(border=True):
        niveaux = st.pills("Niveau de risque", ["Faible", "Modéré", "Élevé"], selection_mode="multi",
                           default=["Élevé"], key="niv")
        pmin, pmax = float(sc["probabilite"].min()), float(sc["probabilite"].max())
        plage = st.slider("Probabilité de départ", 0.0, round(pmax + 0.01, 2), (0.0, round(pmax + 0.01, 2)), 0.01)
        dep = st.selectbox("Département", ["Tous"] + DEPARTEMENTS, key="dep_pred")
        anc = st.selectbox("Ancienneté", ["Toutes"] + ORDRE_ANC, key="anc_pred")
        gen = st.selectbox("Genre", ["Tous", "F", "M"], key="gen_pred")
        gra = st.selectbox("Grade", ["Tous", "G1", "G2", "G3", "G4", "G5"], key="gra_pred")
        site = st.selectbox("Site", ["Tous"] + sorted(sc["code_site"].unique()), key="site_pred")
    x = sc[sc["probabilite"].between(*plage)]
    if niveaux:
        x = x[x["niveau_risque"].isin(niveaux)]
    for v, col in [(dep, "departement"), (anc, "tranche_anciennete"), (gen, "genre"), (gra, "grade"), (site, "code_site")]:
        if v not in ("Tous", "Toutes"):
            x = x[x[col] == v]
    with t:
        k = st.columns(3)
        tuile(k[0], "Collaborateurs affichés", nb(len(x)), "👥")
        tuile(k[1], "Probabilité moyenne", pct(x["probabilite"].mean()), "📈")
        tuile(k[2], "Masse salariale concernée (FCFA)", fcfa(x["salaire_mensuel"].sum()), "💰")
        st.write("")
        tab = x.sort_values("probabilite", ascending=False)[
            ["id", "probabilite", "niveau_risque", "departement", "poste", "grade", "genre", "tranche_anciennete",
             "salaire_mensuel", "facteurs"]]
        st.dataframe(tab.style.map(lambda v: f"background-color:{ {'Élevé': JAUNE, 'Modéré': JAUNE_CLAIR}.get(v, GRIS_CLAIR)}",
                                   subset=["niveau_risque"]),
                     hide_index=True, width="stretch", height=480, column_config={
                         "id": "Identifiant", "probabilite": st.column_config.NumberColumn("Probabilité", format="%.2f"),
                         "niveau_risque": "Niveau", "departement": "Département", "poste": "Poste", "grade": "Grade",
                         "genre": "Genre", "tranche_anciennete": "Ancienneté",
                         "salaire_mensuel": st.column_config.NumberColumn("Salaire (FCFA)", format="%.0f"),
                         "facteurs": st.column_config.TextColumn("Principaux facteurs", width="large")})
        st.download_button("⬇️ Exporter la liste (CSV)", tab.to_csv(index=False).encode("utf-8"),
                           "prediction_departs.csv", "text/csv")
    st.markdown(f"<div class='note'>Régression logistique avec interactions, entraînée sur les 5 cohortes historiques. "
                f"Niveau « Élevé » = les {pct(TAUX_SIGNALEMENT, 0)} de scores les plus hauts de l'entreprise.</div>",
                unsafe_allow_html=True)


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
                tuile(k[0], "Collaborateurs signalés", nb(s["signale"].sum()), "🎯")
                tuile(k[1], "Part signalée", pct(s["signale"].mean()), "📊")
                tuile(k[2], "Probabilité moyenne", pct(s["probabilite"].mean()), "📈")
                with st.container(border=True):
                    r = s.groupby(["poste", "niveau_risque"]).size().reset_index(name="n")
                    graphique(st, px.bar(r, y="poste", x="n", color="niveau_risque", orientation="h",
                                         title="Niveau de risque par poste",
                                         color_discrete_map={"Élevé": JAUNE, "Modéré": JAUNE_CLAIR, "Faible": GRIS_CLAIR},
                                         category_orders={"niveau_risque": ["Élevé", "Modéré", "Faible"]})
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
                f"**{pct(sal, 0)}** des collaborateurs sont payés sous 90 % de la référence de leur grade, "
                f"premier facteur de départ identifié par le modèle.",
            ]
            for ph in phrases:
                st.markdown(ph)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
PAGES = {
    "🏠 Accueil": p_accueil,
    "1 · Vue d'ensemble RH": p_vue_ensemble,
    "2 · Analyse démographique": p_demographie,
    "3 · Analyse de la diversité": p_diversite,
    "4 · Fiche collaborateur": p_fiche,
    "5 · Historique et tendances": p_tendances,
    "6 · Nouveaux arrivants": p_arrivees,
    "7 · Analyse salariale": p_salaires,
    "8 · Écart salarial F / H": p_ecart,
    "9 · Évaluation de la performance": p_performance,
    "10 · Absentéisme": p_absenteisme,
    "11 · Absences par département": p_absences_dep,
    "12 · Profil des départs": p_profil_departs,
    "13 · Analyse des départs": p_analyse_departs,
    "14 · Prédiction des départs": p_prediction,
    "15 · Profil département": p_profil_departement,
}
NOMS = list(PAGES)

demande = st.query_params.get("page")
if demande is not None and demande.isdigit() and int(demande) < len(NOMS):
    st.session_state["page"] = NOMS[int(demande)]          # lien direct ou clic depuis l'accueil
elif "page" not in st.session_state:
    st.session_state["page"] = NOMS[0]
PAGES[st.session_state["page"]]()
