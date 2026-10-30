"""Dashboard RH TelcomCI — effectifs, masse salariale, absentéisme, performance, turnover et risque de départ.

Lancement local :  streamlit run dashboard/app.py
"""
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from preparation import (JOURS_OUVRES_6M, TAUX_SIGNALEMENT, charger, entrainer_modele,
                         facteurs_individuels)

st.set_page_config(page_title="TelcomCI · Pilotage RH", page_icon="📊", layout="wide")

BLEU, ORANGE, VERT, ROUGE, GRIS = "#2f5d8a", "#d0753b", "#4f8a5b", "#b8433b", "#8a8f98"
px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = [BLEU, ORANGE, VERT, "#7a5a9a", "#c9a227", GRIS, ROUGE]


# ---------------------------------------------------------------------------
# Données et modèle (mis en cache)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Chargement des données RH…")
def donnees():
    return charger()


@st.cache_resource(show_spinner="Entraînement du modèle de risque…")
def modele_et_scores():
    df, feats = donnees()
    modele = entrainer_modele(df, feats)
    actuel = df[df["jeu"] == "actuel"].copy()
    actuel["probabilite"] = modele.predict_proba(actuel[feats])[:, 1]
    actuel["rang_risque"] = actuel["probabilite"].rank(ascending=False, method="first")
    seuil_rang = int(round(TAUX_SIGNALEMENT * len(actuel)))
    actuel["signale"] = actuel["rang_risque"] <= seuil_rang
    actuel["niveau_risque"] = pd.cut(actuel["probabilite"].rank(pct=True), [0, 0.6, 1 - TAUX_SIGNALEMENT, 1],
                                     labels=["Faible", "Modéré", "Élevé"])
    actuel["facteurs"] = facteurs_individuels(modele, actuel[feats])
    return actuel


df, FEATS = donnees()
# Libellé semestriel (fin juin = S1, fin décembre = S2) : trié correctement et jamais interprété comme une date
df["periode"] = df["date_reference"].dt.year.astype(str) + " S" + np.where(df["date_reference"].dt.month <= 6, "1", "2")


def afficher(conteneur, fig):
    """Affiche un graphique Plotly avec des étiquettes de barres lisibles."""
    fig.update_traces(selector=dict(type="bar"), textangle=0, textposition="outside", cliponaxis=False)
    fig.update_layout(margin=dict(t=50, r=20), legend_title_text="")
    conteneur.plotly_chart(fig, width="stretch")


def millions(x):
    return f"{x / 1e6:,.1f} M".replace(",", " ").replace(".", ",")


def pct(x, d=1):
    return f"{x * 100:.{d}f} %".replace(".", ",")


# ---------------------------------------------------------------------------
# Filtres
# ---------------------------------------------------------------------------
st.sidebar.title("🎛️ Filtres")
st.sidebar.caption("Les filtres s'appliquent à tous les onglets.")


def filtre(label, col):
    options = sorted(df[col].dropna().unique())
    return st.sidebar.multiselect(label, options, placeholder="Tous")


f_dep = filtre("Département", "departement")
f_site = filtre("Site", "code_site")
f_ville = filtre("Ville", "ville_affectation")
f_contrat = filtre("Contrat", "contrat")
f_grade = filtre("Grade", "grade")

masque = pd.Series(True, index=df.index)
for valeurs, col in [(f_dep, "departement"), (f_site, "code_site"), (f_ville, "ville_affectation"),
                     (f_contrat, "contrat"), (f_grade, "grade")]:
    if valeurs:
        masque &= df[col].isin(valeurs)
d = df[masque]

if d.empty:
    st.warning("Aucun collaborateur ne correspond à ces filtres.")
    st.stop()

dates = sorted(d["date_reference"].unique())
DATE_ACTUELLE, DATE_PRECEDENTE = dates[-1], dates[-2] if len(dates) > 1 else dates[-1]
hist = d[d["jeu"] == "historique"]          # dates où le départ à 6 mois est connu
act = d[d["date_reference"] == DATE_ACTUELLE]
prec = d[d["date_reference"] == DATE_PRECEDENTE]
lbl = lambda t: pd.Timestamp(t).strftime("%d/%m/%Y")

st.sidebar.divider()
st.sidebar.markdown(
    f"**Photographie actuelle :** {lbl(DATE_ACTUELLE)}  \n"
    f"**Historique :** {lbl(dates[0])} → {lbl(hist['date_reference'].max())}  \n"
    f"**Collaborateurs sélectionnés :** {len(act)}"
)
st.sidebar.caption(
    "Taux d'absentéisme = jours d'absence sur 6 mois ÷ "
    f"{JOURS_OUVRES_6M} jours ouvrés. Taux de départ = part des collaborateurs partis "
    "dans les 6 mois suivant la date de référence."
)

# ---------------------------------------------------------------------------
# En-tête et indicateurs clés
# ---------------------------------------------------------------------------
st.title("📊 TelcomCI · Pilotage des ressources humaines")
st.caption(f"Situation au {lbl(DATE_ACTUELLE)}, variations par rapport au {lbl(DATE_PRECEDENTE)}")

k = st.columns(6)
k[0].metric("Effectif", f"{len(act):,}".replace(",", " "), f"{len(act) - len(prec):+d}")
masse, masse_p = act["salaire_mensuel"].sum(), prec["salaire_mensuel"].sum()
masse_txt = f"{masse / 1e9:.2f} Md".replace(".", ",") if masse >= 1e9 else f"{masse / 1e6:.0f} M"
k[1].metric("Masse salariale (FCFA)", masse_txt, pct(masse / masse_p - 1) if masse_p else None,
            help="Somme des salaires mensuels de base")
k[2].metric("Salaire moyen (FCFA)", f"{act['salaire_mensuel'].mean() / 1e3:,.0f} k".replace(",", " "))
abs_a, abs_p = act["taux_absenteisme"].mean(), prec["taux_absenteisme"].mean()
k[3].metric("Taux d'absentéisme", pct(abs_a, 2), f"{(abs_a - abs_p) * 100:+.2f} pt".replace(".", ","),
            delta_color="inverse")
k[4].metric("Engagement moyen", f"{act['engagement_actuel'].mean():.2f} / 5".replace(".", ","),
            f"{act['engagement_actuel'].mean() - prec['engagement_actuel'].mean():+.2f}".replace(".", ","))
der_hist = hist[hist["date_reference"] == hist["date_reference"].max()]
k[5].metric("Taux de départ à 6 mois", pct(der_hist["target"].mean()) if len(der_hist) else "—",
            help=f"Dernière cohorte connue : {lbl(hist['date_reference'].max())}")

onglets = st.tabs(["👥 Effectifs", "💰 Masse salariale", "🩺 Absentéisme",
                   "⭐ Performance & engagement", "🚪 Turnover", "🎯 Risque de départ",
                   "🪪 Fiche collaborateur"])

# ---------------------------------------------------------------------------
# 1. Effectifs
# ---------------------------------------------------------------------------
with onglets[0]:
    c1, c2 = st.columns(2)
    evo = d.groupby("periode").size().reset_index(name="effectif")
    fig = px.bar(evo, x="periode", y="effectif", text="effectif", title="Évolution de l'effectif")
    fig.update_traces(marker_color=BLEU).update_xaxes(title=None)
    afficher(c1, fig)

    dep = act.groupby("departement").size().sort_values().reset_index(name="effectif")
    fig = px.bar(dep, x="effectif", y="departement", orientation="h", text="effectif",
                 title=f"Effectif par département au {lbl(DATE_ACTUELLE)}")
    fig.update_traces(marker_color=BLEU).update_yaxes(title=None)
    afficher(c2, fig)

    c1, c2, c3 = st.columns(3)
    pyr = act.groupby(["tranche_age", "genre"], observed=True).size().reset_index(name="n")
    pyr.loc[pyr["genre"] == "M", "n"] *= -1
    fig = px.bar(pyr[pyr["genre"].isin(["M", "F"])], x="n", y="tranche_age", color="genre", orientation="h",
                 title="Pyramide des âges", color_discrete_map={"M": BLEU, "F": ORANGE})
    fig.update_layout(barmode="relative", xaxis_title="effectif (H à gauche, F à droite)", yaxis_title=None)
    fig.update_xaxes(tickvals=[-200, -100, 0, 100, 200], ticktext=["200", "100", "0", "100", "200"])
    afficher(c1, fig)

    gr = act.groupby(["grade", "contrat"]).size().reset_index(name="effectif")
    fig = px.bar(gr, x="grade", y="effectif", color="contrat", title="Grade et type de contrat")
    afficher(c2, fig)

    an = act["tranche_anciennete"].value_counts().sort_index().reset_index()
    fig = px.bar(an, x="tranche_anciennete", y="count", title="Ancienneté", text="count")
    fig.update_traces(marker_color=VERT).update_layout(xaxis_title=None, yaxis_title="effectif")
    afficher(c3, fig)

    c1, c2 = st.columns(2)
    ville = act["ville_affectation"].value_counts().reset_index()
    fig = px.pie(ville, names="ville_affectation", values="count", hole=0.5, title="Répartition par ville")
    afficher(c1, fig)
    postes = act["poste"].value_counts().head(12).sort_values().reset_index()
    fig = px.bar(postes, x="count", y="poste", orientation="h", title="12 métiers les plus représentés")
    fig.update_traces(marker_color=BLEU).update_layout(xaxis_title="effectif", yaxis_title=None)
    afficher(c2, fig)

# ---------------------------------------------------------------------------
# 2. Masse salariale
# ---------------------------------------------------------------------------
with onglets[1]:
    c1, c2 = st.columns(2)
    ms = d.groupby("periode").agg(masse=("salaire_mensuel", "sum"),
                                         moyen=("salaire_mensuel", "mean")).reset_index()
    ms["masse_M"] = ms["masse"] / 1e6
    fig = px.line(ms, x="periode", y="masse_M", markers=True,
                  title="Masse salariale mensuelle (millions FCFA)")
    fig.update_traces(line_color=BLEU).update_xaxes(title=None).update_yaxes(title=None)
    afficher(c1, fig)

    md = act.groupby("departement")["salaire_mensuel"].sum().sort_values().reset_index()
    md["part"] = md["salaire_mensuel"] / md["salaire_mensuel"].sum()
    md["M"] = md["salaire_mensuel"] / 1e6
    fig = px.bar(md, x="M", y="departement", orientation="h", text=md["part"].map(lambda v: pct(v, 0)),
                 title="Masse salariale par département (M FCFA)")
    fig.update_traces(marker_color=ORANGE).update_layout(xaxis_title=None, yaxis_title=None)
    afficher(c2, fig)

    c1, c2 = st.columns(2)
    fig = px.box(act, x="grade", y="salaire_mensuel", points=False, title="Distribution des salaires par grade",
                 category_orders={"grade": sorted(act["grade"].unique())})
    fig.update_traces(marker_color=BLEU).update_layout(yaxis_title="FCFA", xaxis_title=None)
    afficher(c1, fig)

    sous = act["ratio_salaire_reference"] < 0.9
    fig = px.histogram(act, x="ratio_salaire_reference", nbins=50, range_x=[0.5, 1.6],
                       title="Salaire ÷ référence du grade")
    fig.add_vline(x=0.9, line_dash="dash", line_color=ROUGE, annotation_text="seuil 90 %")
    fig.update_traces(marker_color=GRIS).update_layout(xaxis_title="ratio", yaxis_title="effectif")
    afficher(c2, fig)
    st.info(f"**{sous.sum()} collaborateurs ({pct(sous.mean())})** sont payés à moins de 90 % de la "
            "référence de leur grade. C'est le premier facteur de départ identifié par le modèle.")

    evo_s = act["taux_evolution_salaire"].dropna()
    c1, c2, c3 = st.columns(3)
    c1.metric("Augmentation médiane sur 12 mois", pct(evo_s.median()))
    c2.metric("Augmentation inférieure à 3 %", pct((evo_s < 0.03).mean()),
              help="Parmi les collaborateurs dont le salaire d'il y a 12 mois est connu")
    c3.metric("Jamais promus", pct(act["jamais_promu"].mean()))

    # Écart salarial femmes / hommes à grade égal
    genre = act[act["genre"].isin(["F", "M"])]
    if genre["genre"].nunique() == 2:
        gap = genre.groupby(["grade", "genre"])["salaire_mensuel"].mean().unstack()
        gap["ecart"] = gap["F"] / gap["M"] - 1
        c1, c2 = st.columns([2, 1])
        fig = px.bar(genre.groupby(["grade", "genre"])["salaire_mensuel"].mean().reset_index(),
                     x="grade", y="salaire_mensuel", color="genre", barmode="group",
                     title="Salaire moyen par grade et par genre",
                     color_discrete_map={"M": BLEU, "F": ORANGE})
        fig.update_layout(yaxis_title="FCFA", xaxis_title=None)
        afficher(c1, fig)
        global_gap = genre.loc[genre["genre"] == "F", "salaire_mensuel"].mean() / genre.loc[genre["genre"] == "M", "salaire_mensuel"].mean() - 1
        c2.metric("Écart global F / H", pct(global_gap),
                  help="Salaire moyen des femmes rapporté à celui des hommes, tous grades confondus")
        c2.metric("Écart moyen à grade égal", pct(gap["ecart"].mean()),
                  help="Moyenne des écarts F / H calculés grade par grade : neutralise l'effet de structure")
        c2.caption("L'écart à grade égal compare des postes comparables. S'il était nettement plus faible "
                   "que l'écart global, la différence viendrait surtout de la répartition des femmes et "
                   "des hommes entre les grades.")

# ---------------------------------------------------------------------------
# 3. Absentéisme
# ---------------------------------------------------------------------------
with onglets[2]:
    c1, c2 = st.columns(2)
    ab = d.groupby("periode").agg(taux=("taux_absenteisme", "mean"),
                                         non_just=("abs_non_just_6m", "sum"),
                                         total=("jours_abs_6m", "sum")).reset_index()
    ab["part_non_justifiee"] = ab["non_just"] / ab["total"]
    fig = px.line(ab, x="periode", y="taux", markers=True, title="Taux d'absentéisme (6 mois glissants)")
    fig.update_traces(line_color=ROUGE).update_yaxes(tickformat=".1%", title=None).update_xaxes(title=None)
    afficher(c1, fig)
    fig = px.bar(ab, x="periode", y="part_non_justifiee", title="Part des jours d'absence non justifiés")
    fig.update_traces(marker_color=ORANGE).update_yaxes(tickformat=".0%", title=None).update_xaxes(title=None)
    afficher(c2, fig)

    c1, c2 = st.columns(2)
    abd = act.groupby("departement")["taux_absenteisme"].mean().sort_values().reset_index()
    fig = px.bar(abd, x="taux_absenteisme", y="departement", orientation="h",
                 title=f"Absentéisme par département au {lbl(DATE_ACTUELLE)}")
    fig.update_traces(marker_color=ROUGE).update_xaxes(tickformat=".1%", title=None).update_yaxes(title=None)
    afficher(c1, fig)

    mois = pd.DataFrame({"mois": [f"M-{i}" for i in range(5, -1, -1)],
                         "jours": [act[f"jours_abs_m{i}"].sum() for i in range(6, 0, -1)],
                         "non justifiés": [act[f"abs_non_just_m{i}"].sum() for i in range(6, 0, -1)]})
    fig = px.bar(mois.melt("mois", var_name="type", value_name="jours d'absence"), x="mois",
                 y="jours d'absence", color="type", barmode="group",
                 title="Jours d'absence par mois (les 6 derniers mois)",
                 color_discrete_map={"jours": GRIS, "non justifiés": ROUGE})
    afficher(c2, fig)

    c1, c2, c3 = st.columns(3)
    c1.metric("Collaborateurs absents au moins une fois", pct((act["jours_abs_6m"] > 0).mean()))
    c2.metric("Absentéisme concentré", pct(act["jours_abs_6m"].nlargest(max(1, len(act) // 10)).sum()
                                          / max(1, act["jours_abs_6m"].sum()), 0),
              help="Part des jours d'absence portée par les 10 % de collaborateurs les plus absents")
    c3.metric("Jours non justifiés", pct(act["abs_non_just_6m"].sum() / max(1, act["jours_abs_6m"].sum())))

# ---------------------------------------------------------------------------
# 4. Performance et engagement
# ---------------------------------------------------------------------------
with onglets[3]:
    c1, c2 = st.columns(2)
    pe = d.groupby("periode")[["performance_actuelle", "engagement_actuel"]].mean().reset_index()
    fig = px.line(pe.melt("periode", var_name="indicateur", value_name="note"), x="periode",
                  y="note", color="indicateur", markers=True, title="Notes moyennes (échelle 1 à 5)")
    fig.update_xaxes(title=None)
    afficher(c1, fig)
    fig = px.density_heatmap(act, x="performance_actuelle", y="engagement_actuel", nbinsx=16, nbinsy=16,
                             color_continuous_scale="Blues", title="Performance × engagement")
    afficher(c2, fig)

    c1, c2 = st.columns(2)
    ped = act.groupby("departement")[["performance_actuelle", "engagement_actuel"]].mean().reset_index()
    fig = px.scatter(ped, x="performance_actuelle", y="engagement_actuel", text="departement",
                     title="Départements : performance et engagement moyens")
    fig.update_traces(textposition="top center", marker=dict(size=12, color=BLEU))
    afficher(c1, fig)
    desengages = act[(act["performance_actuelle"] >= 4) & (act["engagement_actuel"] < 3)]
    c2.metric("Talents à risque", len(desengages),
              help="Performance ≥ 4 et engagement < 3 : profils performants mais désengagés")
    c2.metric("Engagement non renseigné", pct(act["engagement_actuel"].isna().mean()))
    c2.metric("Engagement en baisse", pct((act["evolution_engagement"] < 0).mean()),
              help="Parmi les collaborateurs ayant deux mesures successives")

# ---------------------------------------------------------------------------
# 5. Turnover
# ---------------------------------------------------------------------------
with onglets[4]:
    if hist.empty:
        st.info("Pas d'historique de départs pour cette sélection.")
    else:
        st.caption("Les départs sont connus pour les photographies historiques (6 mois de recul nécessaires).")
        c1, c2 = st.columns(2)
        tv = hist.groupby("periode")["target"].agg(["mean", "sum"]).reset_index()
        fig = px.bar(tv, x="periode", y="mean", text=tv["sum"].astype(str) + " départs",
                     title="Taux de départ à 6 mois par cohorte")
        fig.update_traces(marker_color=ROUGE).update_yaxes(tickformat=".0%", title=None).update_xaxes(title=None)
        afficher(c1, fig)
        td = hist.groupby("departement")["target"].mean().sort_values().reset_index()
        fig = px.bar(td, x="target", y="departement", orientation="h", title="Taux de départ par département")
        fig.add_vline(x=hist["target"].mean(), line_dash="dash", line_color=GRIS)
        fig.update_traces(marker_color=ROUGE).update_xaxes(tickformat=".0%", title=None).update_yaxes(title=None)
        afficher(c2, fig)

        c1, c2 = st.columns(2)
        eng = hist.groupby(pd.cut(hist["engagement_actuel"], [1, 2.5, 3, 3.5, 4, 4.5, 5.01]),
                           observed=True)["target"].mean().reset_index()
        eng["engagement_actuel"] = eng["engagement_actuel"].astype(str)
        fig = px.bar(eng, x="engagement_actuel", y="target", title="Départ selon l'engagement")
        fig.update_traces(marker_color=BLEU).update_yaxes(tickformat=".0%", title=None).update_xaxes(title="engagement")
        afficher(c1, fig)
        sal = hist.groupby(pd.cut(hist["ratio_salaire_reference"], [0, 0.8, 0.9, 1, 1.1, 1.2, 5]),
                           observed=True)["target"].mean().reset_index()
        sal["ratio_salaire_reference"] = sal["ratio_salaire_reference"].astype(str)
        fig = px.bar(sal, x="ratio_salaire_reference", y="target", title="Départ selon salaire ÷ référence du grade")
        fig.update_traces(marker_color=ORANGE).update_yaxes(tickformat=".0%", title=None).update_xaxes(title="ratio")
        afficher(c2, fig)

        c1, c2 = st.columns(2)
        tp = hist.groupby("poste")["target"].agg(["mean", "size"]).query("size >= 40").sort_values("mean").tail(12).reset_index()
        fig = px.bar(tp, x="mean", y="poste", orientation="h", title="Métiers les plus exposés (effectif ≥ 40)")
        fig.update_traces(marker_color=ROUGE).update_xaxes(tickformat=".0%", title=None).update_yaxes(title=None)
        afficher(c1, fig)
        ta = hist.groupby("tranche_anciennete", observed=True)["target"].mean().reset_index()
        fig = px.bar(ta, x="tranche_anciennete", y="target", title="Départ selon l'ancienneté")
        fig.update_traces(marker_color=VERT).update_yaxes(tickformat=".0%", title=None).update_xaxes(title=None)
        afficher(c2, fig)

# ---------------------------------------------------------------------------
# 6. Risque de départ (modèle)
# ---------------------------------------------------------------------------
with onglets[5]:
    scores = modele_et_scores()
    sc = scores[scores.index.isin(act.index)]
    st.markdown(
        f"Score de risque de départ dans les 6 mois pour les collaborateurs présents au **{lbl(DATE_ACTUELLE)}**. "
        f"Les **{pct(TAUX_SIGNALEMENT, 0)}** de scores les plus élevés de l'entreprise sont signalés "
        "(même règle que la soumission du challenge). "
        "Le score est un outil de **priorisation** des entretiens, pas une prédiction certaine : "
        "dans les données historiques, environ un collaborateur signalé sur quatre est effectivement parti."
    )
    if sc.empty:
        st.info("Aucun collaborateur actuel dans cette sélection.")
    else:
        c = st.columns(3)
        c[0].metric("Collaborateurs signalés", int(sc["signale"].sum()))
        c[1].metric("Part de la sélection", pct(sc["signale"].mean()))
        c[2].metric("Masse salariale exposée", f"{millions(sc.loc[sc['signale'], 'salaire_mensuel'].sum())} FCFA")

        c1, c2 = st.columns(2)
        rd = sc.groupby("departement")["signale"].agg(["mean", "sum"]).sort_values("mean").reset_index()
        fig = px.bar(rd, x="mean", y="departement", orientation="h", text=rd["sum"].astype(int),
                     title="Part de collaborateurs signalés par département")
        fig.update_traces(marker_color=ROUGE).update_xaxes(tickformat=".0%", title=None).update_yaxes(title=None)
        afficher(c1, fig)
        fig = px.histogram(sc, x="probabilite", color="niveau_risque", nbins=40,
                           title="Distribution des scores", labels={"niveau_risque": "Niveau de risque"},
                           color_discrete_map={"Faible": VERT, "Modéré": "#c9a227", "Élevé": ROUGE},
                           category_orders={"niveau_risque": ["Faible", "Modéré", "Élevé"]})
        fig.update_layout(xaxis_title="probabilité estimée de départ", yaxis_title="effectif")
        afficher(c2, fig)

        st.subheader("Liste prioritaire d'entretiens")
        seuls = st.toggle("Afficher uniquement les collaborateurs signalés", value=True)
        tab = sc[sc["signale"]] if seuls else sc
        tab = tab.sort_values("probabilite", ascending=False)[
            ["id", "departement", "poste", "grade", "contrat", "anciennete", "engagement_actuel",
             "ratio_salaire_reference", "jours_abs_6m", "probabilite", "niveau_risque", "facteurs"]]
        st.dataframe(
            tab, hide_index=True, width="stretch",
            column_config={
                "id": "Identifiant", "departement": "Département", "poste": "Poste", "grade": "Grade",
                "contrat": "Contrat",
                "anciennete": st.column_config.NumberColumn("Ancienneté (ans)", format="%.1f"),
                "engagement_actuel": st.column_config.NumberColumn("Engagement", format="%.2f"),
                "ratio_salaire_reference": st.column_config.NumberColumn("Salaire / réf.", format="%.2f"),
                "jours_abs_6m": st.column_config.NumberColumn("Jours d'absence (6 m)"),
                "probabilite": st.column_config.ProgressColumn("Risque", format="%.2f", min_value=0, max_value=float(scores["probabilite"].max())),
                "niveau_risque": "Niveau",
                "facteurs": st.column_config.TextColumn("Principaux facteurs", width="large"),
            })
        st.download_button("⬇️ Télécharger la liste (CSV)", tab.to_csv(index=False).encode("utf-8"),
                           "liste_prioritaire_entretiens.csv", "text/csv")
        st.caption("Modèle : régression logistique régularisée avec interactions, entraînée sur les cinq "
                   "photographies historiques (voir le notebook 12_modele_final_v2).")


# ---------------------------------------------------------------------------
# 7. Fiche collaborateur
# ---------------------------------------------------------------------------
with onglets[6]:
    scores = modele_et_scores()
    sc = scores[scores.index.isin(act.index)].sort_values("probabilite", ascending=False)
    if sc.empty:
        st.info("Aucun collaborateur actuel dans cette sélection.")
    else:
        choix = st.selectbox(
            "Collaborateur (trié du risque le plus élevé au plus faible)", sc["id"].tolist(),
            format_func=lambda i: f"{i} · {sc.loc[sc['id'] == i, 'poste'].iloc[0]} · "
                                  f"{sc.loc[sc['id'] == i, 'departement'].iloc[0]}")
        p = sc[sc["id"] == choix].iloc[0]
        pairs = act[act["departement"] == p["departement"]]
        percentile = (scores["probabilite"] < p["probabilite"]).mean()

        g, dcol = st.columns([1, 2])
        with g:
            couleur = {"Élevé": ROUGE, "Modéré": "#c9a227", "Faible": VERT}[p["niveau_risque"]]
            st.markdown(
                f"<div style='background:{couleur};color:white;padding:14px 18px;border-radius:10px'>"
                f"<div style='font-size:0.85rem;opacity:.9'>Risque de départ à 6 mois</div>"
                f"<div style='font-size:2rem;font-weight:700'>{p['niveau_risque']}</div>"
                f"<div style='font-size:0.9rem'>Plus risqué que {int(percentile * 100)} % de l'effectif"
                f"{' · signalé' if p['signale'] else ''}</div></div>", unsafe_allow_html=True)
            st.markdown("")
            st.markdown(f"**{p['poste']}**  \n{p['departement']} · {p['code_site']} · {p['ville_affectation']}")
            st.markdown(
                f"Grade **{p['grade']}** · Contrat **{p['contrat']}** · {p['niveau_etude']}  \n"
                f"Âge **{p['age']:.0f} ans** · Ancienneté **{p['anciennete']:.1f} ans**".replace(".", ",")
                if pd.notna(p["anciennete"]) else f"Grade **{p['grade']}** · Contrat **{p['contrat']}**")
            st.markdown("**Principaux facteurs de risque**")
            for f in (p["facteurs"].split(" · ") if p["facteurs"] else ["Aucun facteur aggravant marqué"]):
                st.markdown(f"- {f}")

        with dcol:
            def comparer(col):
                return p[col], pairs[col].mean()
            lignes = [
                ("Salaire / référence du grade", *comparer("ratio_salaire_reference"), "{:.2f}"),
                ("Engagement actuel", *comparer("engagement_actuel"), "{:.2f}"),
                ("Évolution de l'engagement", *comparer("evolution_engagement"), "{:+.2f}"),
                ("Performance actuelle", *comparer("performance_actuelle"), "{:.2f}"),
                ("Jours d'absence (6 mois)", *comparer("jours_abs_6m"), "{:.0f}"),
                ("Dont non justifiés", *comparer("abs_non_just_6m"), "{:.0f}"),
                ("Années depuis la promotion", *comparer("annees_depuis_promotion"), "{:.1f}"),
            ]
            fmt = lambda v, f: "—" if pd.isna(v) else f.format(v).replace(".", ",")
            st.dataframe(pd.DataFrame(
                [{"Indicateur": n, "Collaborateur": fmt(v, f), f"Moyenne {p['departement']}": fmt(m, f)}
                 for n, v, m, f in lignes]), hide_index=True, width="stretch")
            mois = pd.DataFrame({"mois": [f"M-{i}" for i in range(5, -1, -1)],
                                 "toutes absences": [p[f"jours_abs_m{i}"] for i in range(6, 0, -1)],
                                 "non justifiées": [p[f"abs_non_just_m{i}"] for i in range(6, 0, -1)]})
            fig = px.bar(mois.melt("mois", var_name="type", value_name="jours"), x="mois", y="jours",
                         color="type", barmode="group", title="Jours d'absence des 6 derniers mois",
                         color_discrete_map={"toutes absences": GRIS, "non justifiées": ROUGE})
            fig.update_layout(height=280)
            afficher(dcol, fig)
        st.caption("Le niveau de risque est une aide à la priorisation des entretiens, pas une décision. "
                   "À utiliser dans le respect de la confidentialité des données individuelles.")
