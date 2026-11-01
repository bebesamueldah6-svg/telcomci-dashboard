"""Prototype v3 — nouveau système de design, appliqué à la Vue d'ensemble.

Navigation par domaines en haut de page, une couleur par domaine, phrase « À retenir »,
dénominateurs et couverture des données visibles. Les autres pages sont des emplacements.
Lancement : streamlit run dashboard/prototype_v3.py
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from preparation import JOURS_OUVRES_6M, charger

st.set_page_config(page_title="TelcomCI · Pilotage RH", page_icon=":material/diversity_3:", layout="wide")

# ---------------------------------------------------------------------------
# Système de design
# ---------------------------------------------------------------------------
ENCRE, TEXTE_2, FOND, CARTE, BORD = "#1B2A41", "#5B6472", "#F6F4F0", "#FFFFFF", "#E5E0D8"
DOMAINES = {
    "effectifs":    {"nom": "Effectifs",     "couleur": "#2B6CB0", "clair": "#E3EDF8", "icone": "groups"},
    "remuneration": {"nom": "Rémunération",  "couleur": "#946200", "clair": "#F6ECD9", "icone": "payments"},
    "absenteisme":  {"nom": "Absentéisme",   "couleur": "#B4472C", "clair": "#F7E3DD", "icone": "event_busy"},
    "performance":  {"nom": "Performance",   "couleur": "#2F7A4F", "clair": "#E0F0E6", "icone": "trending_up"},
    "turnover":     {"nom": "Turnover",      "couleur": "#6B4C9A", "clair": "#ECE5F4", "icone": "logout"},
}
POLICE = "Manrope, Arial, sans-serif"

st.markdown(f"""
<style>
.stApp {{background: {FOND};}}
.block-container {{padding-top: 4.2rem; max-width: 1380px;}}
.ms {{font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; line-height: 1;
     letter-spacing: normal; text-transform: none; display: inline-block; white-space: nowrap;
     -webkit-font-feature-settings: 'liga'; font-feature-settings: 'liga'; vertical-align: middle;}}
h1.titre {{font-size: 1.9rem; font-weight: 800; color: {ENCRE}; margin: 0; letter-spacing: -.02em;}}
.sous-titre {{color: {TEXTE_2}; font-size: .95rem; margin-top: 2px;}}

/* Phrase « À retenir » */
.retenir {{background: {CARTE}; border: 1px solid {BORD}; border-radius: 10px;
          padding: 16px 20px; color: {ENCRE}; font-size: 1.04rem; line-height: 1.55;}}
.retenir .etiquette {{font-size: .72rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase;
                     color: {TEXTE_2}; margin-bottom: 4px;}}

/* Cartes de domaine */
div[class*="st-key-carte-"] {{background: {CARTE}; border: 1px solid {BORD}; border-radius: 12px;
                             padding: 14px 16px 6px 16px; box-shadow: 0 1px 2px rgba(27,42,65,.05);
                             transition: box-shadow .15s, transform .15s;}}
div[class*="st-key-carte-"]:hover {{box-shadow: 0 6px 18px rgba(27,42,65,.10); transform: translateY(-2px);}}
.dom-tete {{display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: .9rem;}}
.dom-pastille {{width: 30px; height: 30px; border-radius: 8px; display: flex; align-items: center;
               justify-content: center; font-size: 19px;}}
.dom-valeur {{font-size: 2rem; font-weight: 800; color: {ENCRE}; letter-spacing: -.02em; margin-top: 8px;
             line-height: 1.1;}}
.dom-libelle {{color: {TEXTE_2}; font-size: .82rem; min-height: 1.3em; white-space: nowrap; overflow: hidden;
               text-overflow: ellipsis;}}
.delta {{font-size: .8rem; font-weight: 700; padding: 1px 7px; border-radius: 20px; display: inline-block;
        margin-top: 6px;}}
.delta-bon {{background: #E3F2E8; color: #1F6B3F;}} .delta-mauvais {{background: #FBE6E1; color: #A3361C;}}
.delta-neutre {{background: #EEF0F3; color: {TEXTE_2};}}
.dom-detail {{color: {TEXTE_2}; font-size: .8rem; border-top: 1px dashed {BORD}; padding-top: 6px; margin-top: 2px;
              min-height: 3.5em; line-height: 1.45;}}
.dom-detail b {{color: {ENCRE};}}
{''.join(f'.st-key-carte-{k} {{border-top: 4px solid {v["couleur"]} !important;}}' for k, v in DOMAINES.items())}

div[data-testid="stColumn"]:has(div[class*="st-key-carte-"]) > div,
div[class*="st-key-carte-"] {{height: 100%;}}
div[class*="st-key-carte-"] div[data-testid="stPageLink"] {{margin-top: auto;}}

/* Panneaux */
div[class*="st-key-panneau-"] {{background: {CARTE}; border: 1px solid {BORD}; border-radius: 12px; padding: 16px 18px;}}
.panneau-titre {{font-weight: 700; color: {ENCRE}; font-size: 1rem;}}
.panneau-sous {{color: {TEXTE_2}; font-size: .8rem; margin-bottom: 4px;}}
.alerte {{display: flex; gap: 10px; padding: 9px 0; border-bottom: 1px solid {BORD}; align-items: flex-start;}}
.alerte:last-child {{border-bottom: none;}}
.alerte .ms {{font-size: 20px; margin-top: 1px;}}
.alerte-texte {{font-size: .88rem; color: {ENCRE}; line-height: 1.4;}}
.alerte-texte small {{color: {TEXTE_2};}}
.qualite {{display: flex; flex-wrap: wrap; gap: 8px 18px; font-size: .8rem; color: {TEXTE_2};
          background: {CARTE}; border: 1px solid {BORD}; border-radius: 10px; padding: 10px 16px;}}
.qualite b {{color: {ENCRE};}}
.qualite .ms {{font-size: 16px; margin-right: 3px;}}
div[data-testid="stPageLink"] a {{font-size: .82rem; font-weight: 700;}}
</style>
""", unsafe_allow_html=True)


def icone(nom, couleur=ENCRE, taille=None):
    t = f"font-size:{taille}px;" if taille else ""
    return f"<span class='ms' style='color:{couleur};{t}'>{nom}</span>"


def nb(x, d=0):
    return "—" if pd.isna(x) else f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def pct(x, d=1):
    return "—" if pd.isna(x) else f"{x * 100:.{d}f} %".replace(".", ",")


def fcfa(x):
    if pd.isna(x):
        return "—"
    if abs(x) >= 1e9:
        return f"{x / 1e9:.2f} Md".replace(".", ",")
    return f"{x / 1e6:.0f} M" if abs(x) >= 1e6 else f"{x / 1e3:.0f} k"


def theme(fig, hauteur=260):
    fig.update_layout(
        height=hauteur, margin=dict(l=4, r=8, t=8, b=4), plot_bgcolor=CARTE, paper_bgcolor=CARTE,
        font=dict(family=POLICE, color=ENCRE, size=12), separators=", ", hoverlabel=dict(font_family=POLICE),
        legend=dict(orientation="h", y=1.12, x=0, title_text="", font_size=12), bargap=0.35)
    fig.update_xaxes(showgrid=False, linecolor=BORD, tickfont_color=TEXTE_2)
    fig.update_yaxes(gridcolor="#EFEBE5", zeroline=False, tickfont_color=TEXTE_2)
    return fig


def sparkline(valeurs, couleur, clair, mise_en_avant=None):
    v = pd.Series(valeurs).astype(float)
    fig = go.Figure(go.Scatter(y=v.values, mode="lines", line=dict(color=couleur, width=2.2),
                               fill="tozeroy", fillcolor=clair, hoverinfo="skip"))
    if mise_en_avant is not None:
        fig.add_trace(go.Scatter(x=[mise_en_avant], y=[v.iloc[mise_en_avant]], mode="markers",
                                 marker=dict(color=couleur, size=8, line=dict(color="white", width=2)), hoverinfo="skip"))
    lo, hi = v.min(), v.max()
    marge = (hi - lo) * 0.25 or abs(hi) * 0.05 or 1
    fig.update_layout(height=58, margin=dict(l=0, r=0, t=4, b=0), showlegend=False,
                      xaxis_visible=False, yaxis=dict(visible=False, range=[lo - marge, hi + marge]),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


# ---------------------------------------------------------------------------
# Données
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Chargement des données RH…")
def donnees():
    df, _ = charger()
    df["periode"] = df["date_reference"].dt.year.astype(str) + " S" + np.where(df["date_reference"].dt.month <= 6, "1", "2")
    df["arrivee"] = (df["anciennete"] < 0.5).astype(int)
    df["sous_90"] = (df["ratio_salaire_reference"] < 0.9).astype(int)
    return df


DF = donnees()
PERIODES = sorted(DF["periode"].unique())
HIST = sorted(DF.loc[DF["jeu"] == "historique", "periode"].unique())
DATES = DF.groupby("periode")["date_reference"].first()


def libelle_date(p):
    return DATES[p].strftime("%d/%m/%Y")


# ---------------------------------------------------------------------------
# Vue d'ensemble
# ---------------------------------------------------------------------------
def vue_ensemble():
    t, f1, f2 = st.columns([1.5, 2.9, 1.2], vertical_alignment="bottom")
    t.markdown(f"<h1 class='titre'>Vue d'ensemble RH</h1>"
               f"<div class='sous-titre'>TelcomCI · Direction RH</div>", unsafe_allow_html=True)
    per = f1.segmented_control("Période", PERIODES, default=PERIODES[-1], key="per_ve") or PERIODES[-1]
    dep = f2.selectbox("Département", ["Tous les départements"] + sorted(DF["departement"].unique()), key="dep_ve")
    d = DF if dep.startswith("Tous") else DF[DF["departement"] == dep]
    i = PERIODES.index(per)
    prec = PERIODES[i - 1] if i > 0 else None
    cur, avant = d[d["periode"] == per], (d[d["periode"] == prec] if prec else None)
    coh = per if per in HIST else HIST[-1]
    coh_prec = HIST[HIST.index(coh) - 1] if HIST.index(coh) > 0 else None
    hc = d[d["periode"] == coh]
    par = d.groupby("periode")

    # Séries par période
    eff = par.size().reindex(PERIODES)
    masse = par["salaire_mensuel"].sum().reindex(PERIODES)
    absent = par["taux_absenteisme"].mean().reindex(PERIODES)
    perf = par["performance_actuelle"].mean().reindex(PERIODES)
    depart = d[d["jeu"] == "historique"].groupby("periode")["target"].mean().reindex(HIST)

    # Valeurs
    v_eff, v_masse, v_abs = len(cur), cur["salaire_mensuel"].sum(), cur["taux_absenteisme"].mean()
    v_perf, couv_perf = cur["performance_actuelle"].mean(), cur["performance_actuelle"].notna().mean()
    v_dep, n_dep, n_coh = hc["target"].mean(), int(hc["target"].sum()), len(hc)
    arrivees = int(cur["arrivee"].sum())
    sous90 = cur["sous_90"].mean()
    nonjust = cur["abs_non_just_6m"].sum() / max(cur["jours_abs_6m"].sum(), 1)

    def delta(v, ref, fmt, sens_bon=+1, points=False):
        if ref is None or pd.isna(ref) or pd.isna(v):
            return "<span class='delta delta-neutre'>première période</span>"
        diff = (v - ref) * 100 if points else (v / ref - 1 if ref else np.nan)
        if pd.isna(diff) or abs(diff) < (0.05 if points else 0.0005):
            return f"<span class='delta delta-neutre'>stable vs {fmt}</span>"
        classe = "delta-neutre" if sens_bon == 0 else ("delta-bon" if (diff > 0) == (sens_bon > 0) else "delta-mauvais")
        txt = (f"{diff:+.2f} pt" if points else f"{diff * 100:+.1f} %").replace(".", ",")
        return f"<span class='delta {classe}'>{txt} vs {fmt}</span>"

    # ------------------------------------------------------------- À retenir
    evol = (v_eff / len(avant) - 1) if avant is not None and len(avant) else None
    tendance_dep = ""
    if coh_prec:
        ecart = v_dep - d[d["periode"] == coh_prec]["target"].mean()
        tendance_dep = ("en hausse" if ecart > 0.005 else "en baisse" if ecart < -0.005 else "stable") + \
                       f" par rapport à la cohorte {coh_prec}"
    phrase = (f"Au <b>{libelle_date(per)}</b>, {'TelcoPeople' if dep.startswith('Tous') else dep} compte "
              f"<b>{nb(v_eff)} collaborateurs</b>"
              + (f" ({pct(evol)} en six mois, dont {arrivees} arrivées récentes)" if evol is not None else "")
              + f". Sur la dernière cohorte connue ({coh}), <b>{n_dep} collaborateurs sur {nb(n_coh)}</b> "
              f"sont partis dans les six mois, soit {pct(v_dep)}, {tendance_dep}. "
              f"Avec un engagement faible, un salaire inférieur à 90 % de la référence du grade est l'une des deux "
              f"caractéristiques les plus associées aux départs observés : c'est le cas de <b>{pct(sous90, 0)}</b> "
              f"des collaborateurs.")
    st.markdown(f"<div class='retenir'><div class='etiquette'>{icone('lightbulb', ENCRE, 15)} À retenir</div>{phrase}</div>",
                unsafe_allow_html=True)
    st.write("")

    # ------------------------------------------------------------- Cartes de domaine
    cartes = [
        ("effectifs", nb(v_eff), "collaborateurs", delta(v_eff, len(avant) if avant is not None else None, prec),
         eff, f"<b>{arrivees}</b> arrivées sur les 6 derniers mois"),
        ("remuneration", fcfa(v_masse), "FCFA · masse salariale mensuelle",
         delta(v_masse, avant["salaire_mensuel"].sum() if avant is not None else None, prec, sens_bon=0),
         masse, f"<b>{pct(sous90, 0)}</b> payés sous 90 % de leur grade"),
        ("absenteisme", pct(v_abs, 2), "taux d'absentéisme (6 mois)",
         delta(v_abs, avant["taux_absenteisme"].mean() if avant is not None else None, prec, -1, points=True),
         absent, f"<b>{pct(nonjust, 0)}</b> des jours non justifiés"),
        ("performance", f"{nb(v_perf, 2)} / 5", "note moyenne de performance",
         delta(v_perf, avant["performance_actuelle"].mean() if avant is not None else None, prec),
         perf, f"évaluation renseignée pour <b>{pct(couv_perf, 0)}</b> des collaborateurs"),
        ("turnover", pct(v_dep), "taux de départ à 6 mois",
         delta(v_dep, d[d["periode"] == coh_prec]["target"].mean() if coh_prec else None, coh_prec, -1, points=True),
         depart, f"<b>{n_dep}</b> départs sur <b>{nb(n_coh)}</b> · cohorte {coh}"),
    ]
    cols = st.columns(5, gap="small")
    for col, (cle, valeur, libelle, dlt, serie, detail) in zip(cols, cartes):
        dom = DOMAINES[cle]
        with col.container(key=f"carte-{cle}"):
            st.markdown(
                f"<div class='dom-tete' style='color:{dom['couleur']}'>"
                f"<span class='dom-pastille' style='background:{dom['clair']}'>{icone(dom['icone'], dom['couleur'])}</span>"
                f"{dom['nom']}</div><div class='dom-valeur'>{valeur}</div>"
                f"<div class='dom-libelle'>{libelle}</div>{dlt}", unsafe_allow_html=True)
            pos = list(serie.index).index(per if cle != "turnover" else coh) if (per if cle != "turnover" else coh) in serie.index else None
            st.plotly_chart(sparkline(serie, dom["couleur"], dom["clair"], pos), width="stretch",
                            config={"staticPlot": True}, key=f"spark-{cle}")
            st.markdown(f"<div class='dom-detail'>{detail}</div>", unsafe_allow_html=True)
            st.page_link(PAGES_DOMAINE[cle], label=f"Explorer {dom['nom'].lower()}", icon=":material/arrow_forward:")
    st.write("")

    # ------------------------------------------------------------- Graphiques + alertes
    g, a = st.columns([1.55, 1], gap="medium")
    with g.container(key="panneau-flux"):
        st.markdown("<div class='panneau-titre'>Arrivées et départs par semestre</div>"
                    "<div class='panneau-sous'>Arrivées : embauchés dans les 6 mois précédant la date. "
                    "Départs : partis dans les 6 mois suivant la date, pas encore connus pour la dernière période.</div>",
                    unsafe_allow_html=True)
        arr = par["arrivee"].sum().reindex(PERIODES)
        dps = d[d["jeu"] == "historique"].groupby("periode")["target"].sum().reindex(PERIODES)
        fig = go.Figure()
        fig.add_bar(x=PERIODES, y=arr, name="Arrivées", marker_color=DOMAINES["effectifs"]["couleur"],
                    text=arr.map(nb), textposition="outside", cliponaxis=False)
        fig.add_bar(x=PERIODES, y=dps, name="Départs dans les 6 mois", marker_color=DOMAINES["turnover"]["couleur"],
                    text=dps.map(lambda v: "non connu" if pd.isna(v) else nb(v)), textposition="outside",
                    cliponaxis=False)
        if dps.isna().iloc[-1]:
            fig.add_annotation(x=PERIODES[-1], y=arr.iloc[-1], yshift=34, xshift=18, text="départs<br>pas encore connus",
                               showarrow=False, font=dict(size=10, color=TEXTE_2))
        fig.update_layout(barmode="group", yaxis=dict(range=[0, max(arr.max(), dps.max()) * 1.35]))
        st.plotly_chart(theme(fig, 300), width="stretch", config={"displayModeBar": False})

    with a.container(key="panneau-alertes"):
        st.markdown("<div class='panneau-titre'>Points d'attention</div>"
                    "<div class='panneau-sous'>Signaux à examiner, calculés sur la sélection</div>", unsafe_allow_html=True)
        alertes = []
        if dep.startswith("Tous"):
            tx = DF[DF["periode"] == coh].groupby("departement")["target"].agg(["mean", "sum", "size"])
            tx = tx[tx["size"] >= 50]
            haut = tx[tx["mean"] > v_dep * 1.25].sort_values("mean", ascending=False)
            for nom, r in haut.head(2).iterrows():
                alertes.append(("turnover", f"<b>{nom}</b> : taux de départ de {pct(r['mean'])} "
                                            f"<small>({int(r['sum'])} sur {int(r['size'])}, moyenne {pct(v_dep)})</small>"))
            ab = cur.groupby("departement")["taux_absenteisme"].agg(["mean", "size"])
            ab = ab[ab["size"] >= 50].sort_values("mean", ascending=False)
            if len(ab):
                alertes.append(("absenteisme", f"<b>{ab.index[0]}</b> : absentéisme le plus élevé, {pct(ab['mean'].iloc[0], 2)} "
                                               f"<small>(moyenne {pct(v_abs, 2)})</small>"))
        alertes.append(("remuneration", f"<b>{nb(cur['sous_90'].sum())} collaborateurs</b> payés sous 90 % "
                                        f"de la référence de leur grade"))
        talents = cur[(cur["performance_actuelle"] >= 4) & (cur["engagement_actuel"] < 3)]
        alertes.append(("performance", f"<b>{len(talents)} profils performants mais peu engagés</b> "
                                       f"<small>(performance ≥ 4 et engagement &lt; 3)</small>"))
        manq = cur["performance_actuelle"].isna().sum()
        if manq:
            alertes.append(("donnees", f"<b>{manq} évaluations de performance manquantes</b> "
                                       f"<small>(non comptées comme faibles)</small>"))
        html = ""
        for cle, texte in alertes:
            dom = DOMAINES.get(cle, {"couleur": TEXTE_2, "icone": "database"})
            html += f"<div class='alerte'>{icone(dom['icone'], dom['couleur'])}<div class='alerte-texte'>{texte}</div></div>"
        st.markdown(html, unsafe_allow_html=True)

    # ------------------------------------------------------------- Départements
    st.write("")
    with st.container(key="panneau-departements"):
        st.markdown(f"<div class='panneau-titre'>Départements · effectif et taux de départ</div>"
                    f"<div class='panneau-sous'>Effectif au {libelle_date(per)} · taux de départ de la cohorte {coh} "
                    f"(nombre de départs / effectif de la cohorte)</div>", unsafe_allow_html=True)
        tb = DF[DF["periode"] == per].groupby("departement").size().rename("eff").to_frame()
        tc = DF[DF["periode"] == coh].groupby("departement")["target"].agg(["mean", "sum", "size"])
        tb = tb.join(tc).sort_values("eff")
        moy = DF[DF["periode"] == coh]["target"].mean()
        c1, c2 = st.columns(2, gap="medium")
        fig = go.Figure(go.Bar(y=tb.index, x=tb["eff"], orientation="h", text=tb["eff"], textposition="outside",
                               marker_color=[DOMAINES["effectifs"]["couleur"] if (dep.startswith("Tous") or i == dep)
                                             else "#C9D8EA" for i in tb.index], cliponaxis=False))
        c1.plotly_chart(theme(fig, 330).update_layout(xaxis_visible=False), width="stretch", config={"displayModeBar": False})
        couleurs = ["#D9D6D1" if n < 50 else DOMAINES["turnover"]["couleur"] if m > moy else "#C7B8DD"
                    for m, n in zip(tb["mean"], tb["size"].fillna(0))]
        fig = go.Figure(go.Bar(y=tb.index, x=tb["mean"], orientation="h", marker_color=couleurs, cliponaxis=False,
                               text=[f"{pct(m)}  ({int(s)}/{int(n)})" if not pd.isna(m) else "" for m, s, n in
                                     zip(tb["mean"], tb["sum"], tb["size"])], textposition="outside"))
        fig.add_vline(x=moy, line_dash="dot", line_color=TEXTE_2, annotation_position="bottom right",
                      annotation_text=f"moyenne {pct(moy)}", annotation_font_color=TEXTE_2, annotation_font_size=11)
        c2.plotly_chart(theme(fig, 330).update_layout(xaxis=dict(visible=False, range=[0, tb["mean"].max() * 1.6])),
                        width="stretch", config={"displayModeBar": False})
        st.markdown(f"<div class='panneau-sous'>Violet foncé : au-dessus de la moyenne · violet clair : en dessous · "
                    f"gris : moins de 50 collaborateurs, taux trop instable pour être interprété.</div>",
                    unsafe_allow_html=True)

    # ------------------------------------------------------------- Qualité des données
    st.write("")
    act = DF[DF["jeu"] == "actuel"]
    st.markdown(
        f"<div class='qualite'>"
        f"<span>{icone('update', TEXTE_2)}Données au <b>{libelle_date(PERIODES[-1])}</b></span>"
        f"<span>{icone('history', TEXTE_2)}Départs connus jusqu'à la cohorte <b>{HIST[-1]}</b></span>"
        f"<span>{icone('fact_check', TEXTE_2)}Performance renseignée : <b>{pct(act['performance_actuelle'].notna().mean(), 0)}</b></span>"
        f"<span>{icone('fact_check', TEXTE_2)}Engagement renseigné : <b>{pct(act['engagement_actuel'].notna().mean(), 0)}</b></span>"
        f"<span>{icone('help', TEXTE_2)}Genre inconnu : <b>{(act['genre'] == 'INCONNU').sum()}</b> · "
        f"département inconnu : <b>{(act['departement'] == 'INCONNU').sum()}</b></span>"
        f"<span>{icone('info', TEXTE_2)}Absentéisme = jours d'absence ÷ {JOURS_OUVRES_6M} jours ouvrés</span>"
        f"</div>", unsafe_allow_html=True)


def a_venir(nom):
    def page():
        st.markdown(f"<h1 class='titre'>{nom}</h1><div class='sous-titre'>Page en cours de migration vers le "
                    f"nouveau design.</div>", unsafe_allow_html=True)
    return page


# ---------------------------------------------------------------------------
# Navigation par domaines (barre en haut)
# ---------------------------------------------------------------------------
P = lambda fn, titre, icon, **kw: st.Page(fn, title=titre, icon=f":material/{icon}:", **kw)
accueil = P(vue_ensemble, "Vue d'ensemble", "dashboard", url_path="vue-ensemble", default=True)
pages = {
    "": [accueil],
    "Effectifs": [P(a_venir("Synthèse des effectifs"), "Synthèse", "groups", url_path="effectifs"),
                  P(a_venir("Démographie et diversité"), "Démographie et diversité", "diversity_3", url_path="demographie"),
                  P(a_venir("Nouveaux arrivants"), "Nouveaux arrivants", "person_add", url_path="arrivees"),
                  P(a_venir("Départements"), "Départements", "corporate_fare", url_path="departements"),
                  P(a_venir("Fiche collaborateur"), "Fiche collaborateur", "badge", url_path="fiche")],
    "Rémunération": [P(a_venir("Analyse salariale"), "Analyse salariale", "payments", url_path="salaires"),
                     P(a_venir("Équité salariale"), "Équité salariale", "balance", url_path="equite")],
    "Absentéisme": [P(a_venir("Absentéisme"), "Vue générale", "event_busy", url_path="absenteisme"),
                    P(a_venir("Absences par département"), "Par département", "domain", url_path="absences-departement")],
    "Performance": [P(a_venir("Performance"), "Évaluation de la performance", "trending_up", url_path="performance")],
    "Turnover": [P(a_venir("Analyse des départs"), "Analyse des départs", "query_stats", url_path="departs"),
                 P(a_venir("Caractéristiques des départs observés"), "Caractéristiques des départs", "logout",
                   url_path="caracteristiques-departs"),
                 P(a_venir("Anticipation des départs"), "Anticipation des départs", "radar", url_path="anticipation")],
}
PAGES_DOMAINE = {"effectifs": pages["Effectifs"][0], "remuneration": pages["Rémunération"][0],
                 "absenteisme": pages["Absentéisme"][0], "performance": pages["Performance"][0],
                 "turnover": pages["Turnover"][0]}
st.navigation(pages, position="top").run()
