"""Exports professionnels : classeur Excel structuré et synthèse PDF.

Les exports respectent le rôle : la Direction générale ne reçoit que des agrégats.
"""
import io
from datetime import datetime

import numpy as np
import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ENCRE, CLAIR = "1B2A41", "EEF1F5"


# ---------------------------------------------------------------------------
# Tables agrégées
# ---------------------------------------------------------------------------
def indicateurs_par_periode(df):
    g = df.groupby("periode")
    t = pd.DataFrame({
        "Effectif": g.size(),
        "Arrivées (6 mois précédents)": g["arrivee"].sum(),
        "Masse salariale mensuelle (FCFA)": g["salaire_mensuel"].sum(),
        "Salaire médian (FCFA)": g["salaire_mensuel"].median(),
        "Taux d'absentéisme": g["taux_absenteisme"].mean(),
        "Performance moyenne (/5)": g["performance_actuelle"].mean(),
        "Performance renseignée": g["performance_actuelle"].apply(lambda s: s.notna().mean()),
        "Engagement moyen (/5)": g["engagement_actuel"].mean(),
    })
    h = df[df["jeu"] == "historique"].groupby("periode")["target"]
    t["Départs dans les 6 mois"] = h.sum()
    t["Taux de départ à 6 mois"] = h.mean()
    return t.reset_index().rename(columns={"periode": "Période"})


def par_departement(cur):
    g = cur.groupby("departement")
    return pd.DataFrame({
        "Effectif": g.size(),
        "Part de femmes": g["genre"].apply(lambda s: (s == "F").mean()),
        "Âge moyen": g["age"].mean(),
        "Ancienneté moyenne (ans)": g["anciennete"].mean(),
        "Part de CDD": g["contrat"].apply(lambda s: (s == "CDD").mean()),
        "Masse salariale (FCFA)": g["salaire_mensuel"].sum(),
        "Taux d'absentéisme": g["taux_absenteisme"].mean(),
        "Performance moyenne (/5)": g["performance_actuelle"].mean(),
        "Engagement moyen (/5)": g["engagement_actuel"].mean(),
    }).reset_index().rename(columns={"departement": "Département"})


def remuneration_par_grade(cur):
    g = cur.groupby("grade")["salaire_mensuel"]
    t = pd.DataFrame({"Effectif": g.size(), "Masse salariale (FCFA)": g.sum(), "Moyenne (FCFA)": g.mean(),
                      "1er quartile": g.quantile(.25), "Médiane": g.median(), "3e quartile": g.quantile(.75),
                      "Part sous 90 % de la référence": cur.groupby("grade")["ratio_salaire_reference"].apply(
                          lambda s: (s < 0.9).mean())})
    fh = cur[cur["genre"].isin(["F", "M"])].groupby(["grade", "genre"])["salaire_mensuel"].median().unstack()
    n = cur[cur["genre"].isin(["F", "M"])].groupby(["grade", "genre"]).size().unstack()
    t["Écart médian F/H"] = np.where((n["F"] >= 10) & (n["M"] >= 10), fh["F"] / fh["M"] - 1, np.nan)
    return t.reset_index().rename(columns={"grade": "Grade"})


def turnover(df):
    h = df[df["jeu"] == "historique"]
    t = h.groupby(["periode", "departement"])["target"].agg(["size", "sum", "mean"]).reset_index()
    t.columns = ["Cohorte", "Département", "Effectif de la cohorte", "Départs dans les 6 mois", "Taux de départ"]
    return t


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------
def _mise_en_forme(ws, df, formats):
    entete = PatternFill("solid", fgColor=ENCRE)
    fin = Side(style="thin", color="D9DDE3")
    for j, col in enumerate(df.columns, start=1):
        c = ws.cell(row=1, column=j)
        c.fill, c.font = entete, Font(bold=True, color="FFFFFF")
        c.alignment = Alignment(wrap_text=True, vertical="center")
        largeur = max(len(str(col)), *(len(str(v)) for v in df[col].head(200))) if len(df) else len(str(col))
        ws.column_dimensions[get_column_letter(j)].width = min(max(12, largeur * 1.1), 60)
        fmt = next((f for motif, f in formats if motif(col)), None)
        for i in range(2, len(df) + 2):
            cell = ws.cell(row=i, column=j)
            cell.border = Border(bottom=fin)
            if fmt:
                cell.number_format = fmt
            if i % 2 == 0:
                cell.fill = PatternFill("solid", fgColor="F7F8FA")
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "B2"
    if len(df):
        ws.auto_filter.ref = ws.dimensions


FORMATS = [
    (lambda c: "Taux" in c or "Part" in c or "Écart" in c or "renseignée" in c or "Couverture" in c or "observé" in c,
     "0.0%"),
    (lambda c: "FCFA" in c or "quartile" in c or "Médiane" in c, "#,##0"),
    (lambda c: "/5" in c or "moyen" in c.lower() or "Probabilité" in c, "0.00"),
    (lambda c: True, "#,##0"),
]


def excel(df, scores, taux_niveaux, qualite, contexte, nominatif):
    """Construit le classeur. `contexte` : dict(periode, departement, utilisateur, role)."""
    cur = df[df["periode"] == contexte["periode"]]
    feuilles = {}
    lisez = [("Rapport", "Pilotage RH TelcomCI : export des indicateurs"),
             ("Exporté le", datetime.now().strftime("%d/%m/%Y %H:%M")),
             ("Par", f"{contexte['utilisateur']} (profil {contexte['role']})"),
             ("Période de référence", contexte["periode"]),
             ("Périmètre", contexte["departement"]),
             ("Confidentialité", "Document interne. " + ("Contient des données individuelles : diffusion restreinte à la DRH."
                                                        if nominatif else "Données agrégées uniquement.")),
             ("Départ", "Départ dans les 6 mois suivant la date de référence ; inconnu pour la dernière période."),
             ("Absentéisme", "Jours d'absence sur 6 mois ÷ 130 jours ouvrés."),
             ("Arrivée", "Embauche dans les 6 mois précédant la date de référence."),
             ("Niveaux de risque", "Très élevé = 5 % des scores les plus hauts ; Élevé = 5 à 16 % ; Modéré = 16 à 50 % ; "
                                   "Faible = moitié basse. Signal statistique à examiner, jamais une décision."),
             ("Données manquantes", "Une valeur non renseignée n'est jamais comptée comme une valeur faible.")]
    feuilles["Lisez-moi"] = pd.DataFrame(lisez, columns=["Élément", "Valeur"])
    feuilles["Synthèse par période"] = indicateurs_par_periode(df)
    feuilles["Départements"] = par_departement(cur)
    feuilles["Rémunération par grade"] = remuneration_par_grade(cur)
    feuilles["Turnover par cohorte"] = turnover(df)
    t = taux_niveaux.reset_index().rename(columns={
        "niveau": "Niveau", "effectif": "Effectif en validation", "departs": "Départs observés",
        "taux": "Taux de départ observé", "part_des_departs": "Part des départs", "taux_min": "Taux observé min",
        "taux_max": "Taux observé max"})
    feuilles["Niveaux de risque (validation)"] = t
    agg = scores.groupby(["departement", "niveau_risque"]).size().unstack(fill_value=0)
    agg = agg.reindex(columns=["Très élevé", "Élevé", "Modéré", "Faible"], fill_value=0)
    agg["Effectif"] = agg.sum(axis=1)
    agg["Part Très élevé + Élevé"] = (agg["Très élevé"] + agg["Élevé"]) / agg["Effectif"]
    feuilles["Anticipation par département"] = agg.reset_index().rename(columns={"departement": "Département"})
    if nominatif:
        nomi = scores.sort_values("probabilite", ascending=False)[
            ["id", "departement", "poste", "grade", "contrat", "niveau_risque", "probabilite", "facteurs"]]
        feuilles["Anticipation nominative"] = nomi.rename(columns={
            "id": "Identifiant", "departement": "Département", "poste": "Poste", "grade": "Grade",
            "contrat": "Contrat", "niveau_risque": "Niveau", "probabilite": "Probabilité estimée",
            "facteurs": "Principaux signaux"})
    feuilles["Qualité · anomalies"] = qualite["anomalies"]
    feuilles["Qualité · manquants"] = qualite["manquants"].rename(columns={
        "Manquant (historique)": "Part manquante (historique)", "Manquant (31/12/2024)": "Part manquante (31/12/2024)"})
    dico = [(f, "") for f in list(feuilles) + ["Dictionnaire"]]
    feuilles["Dictionnaire"] = pd.DataFrame(dico, columns=["Feuille", "Contenu"])
    feuilles["Dictionnaire"]["Contenu"] = [
        "Contexte, définitions et confidentialité de l'export",
        "Indicateurs clés pour chaque photographie semestrielle",
        f"Indicateurs par département au {contexte['periode']}",
        f"Distribution des salaires par grade au {contexte['periode']} (écart F/H si ≥ 10 personnes de chaque genre)",
        "Effectif, départs et taux de départ par cohorte et département",
        "Taux de départ réellement observés par niveau de risque (validation temporelle sur 3 cohortes)",
        "Répartition des collaborateurs au 31/12/2024 par niveau de risque",
    ] + (["Liste nominative des scores (profil DRH uniquement)"] if nominatif else []) + [
        "Anomalies détectées dans les données brutes et règles appliquées",
        "Taux de valeurs manquantes par variable",
        "Description des feuilles",
    ]

    sortie = io.BytesIO()
    with pd.ExcelWriter(sortie, engine="openpyxl") as xl:
        for nom, t in feuilles.items():
            t.to_excel(xl, sheet_name=nom[:31], index=False)
            _mise_en_forme(xl.sheets[nom[:31]], t, [] if nom in ("Lisez-moi", "Dictionnaire") else FORMATS)
        xl.sheets["Lisez-moi"].column_dimensions["B"].width = 110
    return sortie.getvalue()


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def pdf(synthese, kpis, alertes, niveaux, departements, contexte, nominatif):
    """Synthèse exécutive de 2 pages. `kpis` : liste (libellé, valeur, détail)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    encre = colors.HexColor("#" + ENCRE)
    st_titre = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=18, leading=23, textColor=encre, spaceAfter=2)
    st_sous = ParagraphStyle("s", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#5B6472"), spaceAfter=10)
    st_h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=12, textColor=encre, spaceBefore=12, spaceAfter=6)
    st_p = ParagraphStyle("p", fontName="Helvetica", fontSize=10, leading=14, textColor=encre)
    st_n = ParagraphStyle("n", fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor("#5B6472"))

    def tableau(lignes, largeurs, entete=True):
        t = Table(lignes, colWidths=largeurs, hAlign="LEFT")
        style = [("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("TEXTCOLOR", (0, 0), (-1, -1), encre),
                 ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9DDE3")),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
        if entete:
            style += [("BACKGROUND", (0, 0), (-1, 0), encre), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                      ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9)]
        t.setStyle(TableStyle(style))
        return t

    def pied(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#5B6472"))
        conf = "Diffusion restreinte DRH" if nominatif else "Document interne · données agrégées"
        canvas.drawString(2 * cm, 1.2 * cm, f"TelcoPeople · Pilotage RH · {conf} · exporté le "
                                             f"{datetime.now().strftime('%d/%m/%Y')} par {contexte['utilisateur']}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
        canvas.setStrokeColor(encre)
        canvas.setLineWidth(3)
        canvas.line(2 * cm, A4[1] - 1.4 * cm, A4[0] - 2 * cm, A4[1] - 1.4 * cm)
        canvas.restoreState()

    sortie = io.BytesIO()
    doc = SimpleDocTemplate(sortie, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm,
                            bottomMargin=2 * cm, title="Synthèse RH TelcomCI", author=contexte["utilisateur"])
    elems = [Paragraph("Synthèse RH · TelcomCI", st_titre),
             Paragraph(f"Période : {contexte['periode']} · Périmètre : {contexte['departement']}", st_sous),
             Paragraph("À retenir", st_h), Paragraph(synthese, st_p),
             Paragraph("Indicateurs clés", st_h),
             tableau([["Indicateur", "Valeur", "Précision"]] + [list(k) for k in kpis], [6 * cm, 3.5 * cm, 7.5 * cm]),
             Paragraph("Points d'attention", st_h)]
    for a in alertes:
        elems.append(Paragraph("• " + a, st_p))
    elems += [Paragraph("Anticipation des départs : fiabilité par niveau", st_h),
              Paragraph("Taux de départ réellement observés lorsque le modèle, entraîné sur le passé, a été appliqué "
                        "aux trois dernières cohortes connues. Ce sont des taux de groupe, pas des certitudes individuelles.",
                        st_n), Spacer(1, 4),
              tableau([["Niveau", "Part de l'effectif", "Taux de départ observé", "Fourchette selon la cohorte"]] +
                      [[r.Index, r.part, r.taux, r.fourchette] for r in niveaux.itertuples()],
                      [3.5 * cm, 3.5 * cm, 4.5 * cm, 5.5 * cm]),
              Paragraph("Départements", st_h),
              tableau([list(departements.columns)] + departements.astype(str).values.tolist(),
                      [3.2 * cm, 2.4 * cm, 3.2 * cm, 3.4 * cm, 4.8 * cm]),
              Spacer(1, 10),
              Paragraph("Méthode et limites : données semestrielles TelcoPeople (juin 2022 à décembre 2024). "
                        "Départs connus jusqu'à la cohorte de juin 2024. Les associations statistiques présentées ne "
                        "démontrent aucune causalité. Le score de risque est un outil de priorisation des échanges RH ; "
                        "il ne peut fonder aucune décision défavorable (sanction, rémunération, promotion, formation).", st_n)]
    doc.build(elems, onFirstPage=pied, onLaterPages=pied)
    return sortie.getvalue()
