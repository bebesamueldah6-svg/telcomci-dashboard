"""Exports professionnels : classeur Excel structuré et synthèse PDF.

Les exports respectent le rôle : la Direction générale ne reçoit que des agrégats.
"""
import io
from datetime import datetime

import numpy as np
import pandas as pd
from pathlib import Path

from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.drawing.image import Image as XLImage
from openpyxl.formatting.rule import CellIsRule, DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from PIL import Image, ImageDraw, ImageFont

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
# Excel : couverture, tableau de bord avec graphiques natifs, feuilles de données mises en forme
# ---------------------------------------------------------------------------
ORANGE, NOIR, FOND = "FF7900", "000000", "F7F7F7"
LIGNE_ENTETE = 4                      # les tableaux commencent sous un bandeau titre (lignes 1 à 3)
COULEURS_NIVEAU = {"Très élevé": "CD3C14", "Élevé": "FF7900", "Modéré": "FFC08A", "Faible": "E0E0E0"}
POLICES = Path(__file__).parent / "static" / "polices"


def _logo_png(taille=150):
    """Logo « TC » (carré noir, T blanc, C orange) en image pour Excel."""
    img = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, taille - 1, taille - 1], radius=int(taille * .24), fill=(0, 0, 0, 255))
    try:
        police = ImageFont.truetype(str(POLICES / "Inter_800ExtraBold.ttf"), int(taille * .46))
    except OSError:
        police = ImageFont.load_default()
    lt, lc = d.textlength("T", font=police), d.textlength("C", font=police)
    x0, y0 = (taille - lt - lc) / 2, taille * .22
    d.text((x0, y0), "T", font=police, fill=(255, 255, 255, 255))
    d.text((x0 + lt, y0), "C", font=police, fill=(255, 121, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return XLImage(buf)


def _bandeau(ws, titre, description, largeur_colonnes):
    ws.sheet_view.showGridLines = False
    ws["A1"] = titre
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color=NOIR)
    ws["A2"] = description
    ws["A2"].font = Font(name="Calibri", size=10, color="6B6B6B")
    ws["A3"] = "← Retour au sommaire"
    ws["A3"].hyperlink = "#'Couverture'!A1"
    ws["A3"].font = Font(name="Calibri", size=9, color=ORANGE, underline="single")
    for j in range(1, max(largeur_colonnes, 1) + 1):
        ws.cell(row=3, column=j).border = Border(bottom=Side(style="medium", color=ORANGE))


def _mise_en_forme(ws, df, formats):
    entete = PatternFill("solid", fgColor=NOIR)
    fin = Side(style="thin", color="E6E6E6")
    l0 = LIGNE_ENTETE
    for j, col in enumerate(df.columns, start=1):
        c = ws.cell(row=l0, column=j)
        c.fill, c.font = entete, Font(name="Calibri", bold=True, color="FFFFFF")
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = Border(bottom=Side(style="thick", color=ORANGE))
        largeur = max(len(str(col)), *(len(str(v)) for v in df[col].head(200))) if len(df) else len(str(col))
        ws.column_dimensions[get_column_letter(j)].width = min(max(12, largeur * 1.1), 60)
        fmt = next((f for motif, f in formats if motif(col)), None)
        for i in range(l0 + 1, len(df) + l0 + 1):
            cell = ws.cell(row=i, column=j)
            cell.border = Border(bottom=fin)
            cell.font = Font(name="Calibri", size=10)
            if fmt:
                cell.number_format = fmt
            if (i - l0) % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=FOND)
        if fmt == "0.0%" and len(df) > 1:          # barres orange dans les cellules de taux et de parts
            plage = f"{get_column_letter(j)}{l0 + 1}:{get_column_letter(j)}{len(df) + l0}"
            ws.conditional_formatting.add(plage, DataBarRule(start_type="num", start_value=0, end_type="max",
                                                             color=ORANGE, showValue=True))
    ws.row_dimensions[l0].height = 34
    ws.freeze_panes = ws.cell(row=l0 + 1, column=2)
    if len(df):
        ws.auto_filter.ref = f"A{l0}:{get_column_letter(len(df.columns))}{len(df) + l0}"


FORMATS = [
    (lambda c: "Taux" in c or "Part" in c or "Écart" in c or "renseignée" in c or "Couverture" in c or "observé" in c,
     "0.0%"),
    (lambda c: "FCFA" in c or "quartile" in c or "Médiane" in c, "#,##0"),
    (lambda c: "/5" in c or "moyen" in c.lower() or "Probabilité" in c, "0.00"),
    (lambda c: True, "#,##0"),
]


def _etiquettes(format_axe):
    """Étiquettes de données : la valeur seule (sans nom de série ni de catégorie)."""
    e = DataLabelList()
    e.showVal, e.showSerName, e.showCatName, e.showLegendKey, e.showPercent = True, False, False, False, False
    e.numFmt = format_axe
    return e


def _serie_couleur(graphique, couleurs):
    for serie, coul in zip(graphique.series, couleurs):
        serie.graphicalProperties.solidFill = coul
        serie.graphicalProperties.line.solidFill = coul


def _graphique_barres(ws_donnees, col, n, titre, format_axe="#,##0", horizontal=False, couleur=ORANGE):
    g = BarChart()
    g.type = "bar" if horizontal else "col"
    g.title, g.style, g.legend = titre, 2, None
    g.height, g.width = 7.2, 12.5
    l0 = LIGNE_ENTETE
    g.add_data(Reference(ws_donnees, min_col=col, min_row=l0, max_row=l0 + n), titles_from_data=True)
    g.set_categories(Reference(ws_donnees, min_col=1, min_row=l0 + 1, max_row=l0 + n))
    g.y_axis.numFmt, g.y_axis.majorGridlines = format_axe, None
    g.y_axis.delete = False
    g.x_axis.delete = False
    g.gapWidth = 60
    g.dataLabels = _etiquettes(format_axe)
    _serie_couleur(g, [couleur])
    return g


def _graphique_courbe(ws_donnees, col, n, titre, format_axe):
    g = LineChart()
    g.title, g.style, g.legend = titre, 2, None
    g.height, g.width = 7.2, 12.5
    l0 = LIGNE_ENTETE
    g.add_data(Reference(ws_donnees, min_col=col, min_row=l0, max_row=l0 + n), titles_from_data=True)
    g.set_categories(Reference(ws_donnees, min_col=1, min_row=l0 + 1, max_row=l0 + n))
    g.y_axis.numFmt, g.y_axis.majorGridlines = format_axe, None
    g.y_axis.delete = False
    g.x_axis.delete = False
    s = g.series[0]
    s.graphicalProperties.line.solidFill, s.graphicalProperties.line.width = ORANGE, 32000
    s.marker.symbol, s.marker.size = "circle", 7
    s.marker.graphicalProperties.solidFill = ORANGE
    s.marker.graphicalProperties.line.solidFill = ORANGE
    s.smooth = False
    g.dataLabels = _etiquettes(format_axe)
    g.dataLabels.position = "t"
    return g


def _couverture(ws, contexte, nominatif, sommaire):
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 38
    ws.column_dimensions["C"].width = 90
    for r in range(1, 10):
        for c in range(1, 8):
            ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=NOIR)
    logo = _logo_png(84)
    ws.add_image(logo, "B2")
    ws["C2"] = "TelcomCI · Direction des Ressources Humaines"
    ws["C2"].font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    ws["C4"] = "Pilotez vos effectifs."
    ws["C4"].font = Font(name="Calibri", size=24, bold=True, color="FFFFFF")
    ws["C5"] = "Anticipez les départs."
    ws["C5"].font = Font(name="Calibri", size=24, bold=True, color=ORANGE)
    ws["C7"] = f"Classeur RH · période {contexte['periode']} · {contexte['departement']}"
    ws["C7"].font = Font(name="Calibri", size=11, color="D9D9D9")
    ws["C8"] = (f"Exporté le {datetime.now():%d/%m/%Y à %H:%M} par {contexte['utilisateur']} (profil {contexte['role']}) · "
                + ("diffusion restreinte DRH : contient des données individuelles" if nominatif else
                   "données agrégées uniquement"))
    ws["C8"].font = Font(name="Calibri", size=9, color="9A9A9A")
    for r in (4, 5):
        ws.row_dimensions[r].height = 32
    ws["B11"] = "Sommaire"
    ws["B11"].font = Font(name="Calibri", size=14, bold=True)
    ws["B11"].border = Border(bottom=Side(style="medium", color=ORANGE))
    ws["C11"].border = Border(bottom=Side(style="medium", color=ORANGE))
    for k, (nom, contenu) in enumerate(sommaire, start=12):
        c = ws.cell(row=k, column=2, value=f"→ {nom}")
        c.hyperlink = f"#'{nom}'!A1"
        c.font = Font(name="Calibri", size=11, color=ORANGE, bold=True, underline="single")
        d = ws.cell(row=k, column=3, value=contenu)
        d.font = Font(name="Calibri", size=10, color="404040")
        for col in (2, 3):
            ws.cell(row=k, column=col).border = Border(bottom=Side(style="thin", color="EEEEEE"))
        ws.row_dimensions[k].height = 20


def _tableau_de_bord(ws, cur, sc, kpis, feuilles_ws, n_periodes, n_deps):
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Tableau de bord"
    ws["A1"].font = Font(name="Calibri", size=16, bold=True)
    ws["A2"] = "Indicateurs clés de la période et graphiques Excel (modifiables)."
    ws["A2"].font = Font(name="Calibri", size=10, color="6B6B6B")
    ws["A3"] = "← Retour au sommaire"
    ws["A3"].hyperlink = "#'Couverture'!A1"
    ws["A3"].font = Font(name="Calibri", size=9, color=ORANGE, underline="single")
    for j in range(1, 19):
        ws.column_dimensions[get_column_letter(j)].width = 11
        ws.cell(row=3, column=j).border = Border(bottom=Side(style="medium", color=ORANGE))
    # tuiles : 6 indicateurs, chacun sur 3 colonnes fusionnées (valeur ligne 5, libellé ligne 6)
    for k, (libelle, valeur, fmt) in enumerate(kpis):
        c0 = 1 + 3 * k
        for r in (5, 6):
            ws.merge_cells(start_row=r, start_column=c0, end_row=r, end_column=c0 + 2)
        v = ws.cell(row=5, column=c0, value=valeur)
        v.number_format, v.font = fmt, Font(name="Calibri", size=20, bold=True)
        v.alignment = Alignment(horizontal="center", vertical="center")
        lb = ws.cell(row=6, column=c0, value=libelle)
        lb.font, lb.alignment = Font(name="Calibri", size=9, color="F16E00"), Alignment(horizontal="center", wrap_text=True)
        bord = Side(style="thin", color="E0E0E0")
        for r in (5, 6):
            for c in range(c0, c0 + 3):
                ws.cell(row=r, column=c).border = Border(top=bord if r == 5 else None, bottom=bord if r == 6 else None,
                                                         left=bord if c == c0 else None, right=bord if c == c0 + 2 else None)
    ws.row_dimensions[5].height, ws.row_dimensions[6].height = 36, 30
    syn, dep = feuilles_ws["Synthèse par période"], feuilles_ws["Départements"]
    col = {nom: j for j, nom in enumerate([c.value for c in syn[LIGNE_ENTETE]], start=1)}
    cold = {nom: j for j, nom in enumerate([c.value for c in dep[LIGNE_ENTETE]], start=1)}
    ws.add_chart(_graphique_barres(syn, col["Effectif"], n_periodes, "Effectif par période"), "A8")
    ws.add_chart(_graphique_courbe(syn, col["Taux de départ à 6 mois"], n_periodes - 1,
                                   "Taux de départ à 6 mois par cohorte", "0.0%"), "J8")
    ws.add_chart(_graphique_barres(dep, cold["Taux d'absentéisme"], n_deps, "Taux d'absentéisme par département",
                                   "0.00%", horizontal=True, couleur="595959"), "A24")
    ws.add_chart(_graphique_barres(dep, cold["Masse salariale (FCFA)"], n_deps, "Masse salariale par département",
                                   '#,##0,," M"', horizontal=True), "J24")


def excel(df, scores, taux_niveaux, qualite, contexte, nominatif):
    """Construit le classeur. `contexte` : dict(periode, departement, utilisateur, role)."""
    cur = df[df["periode"] == contexte["periode"]]
    perimetre = contexte["departement"]
    sc = scores if perimetre.startswith("Tous") else scores[scores["departement"] == perimetre]
    feuilles = {}
    lisez = [("Rapport", "Pilotage RH TelcomCI : export des indicateurs"),
             ("Exporté le", datetime.now().strftime("%d/%m/%Y %H:%M")),
             ("Par", f"{contexte['utilisateur']} (profil {contexte['role']})"),
             ("Période de référence", contexte["periode"]),
             ("Périmètre", perimetre),
             ("Confidentialité", "Document interne. " + ("Contient des données individuelles : diffusion restreinte à la DRH."
                                                        if nominatif else "Données agrégées uniquement.")),
             ("Départ", "Départ dans les 6 mois suivant la date de référence ; inconnu pour la dernière période."),
             ("Absentéisme", "Jours d'absence sur 6 mois ÷ 130 jours ouvrés."),
             ("Arrivée", "Embauche dans les 6 mois précédant la date de référence."),
             ("Niveaux de risque", "Très élevé = 5 % des scores les plus hauts ; Élevé = 5 à 16 % ; Modéré = 16 à 50 % ; "
                                   "Faible = moitié basse. Signal statistique à examiner, jamais une décision."),
             ("Données manquantes", "Une valeur non renseignée n'est jamais comptée comme une valeur faible.")]
    feuilles["Lisez-moi"] = (pd.DataFrame(lisez, columns=["Élément", "Valeur"]), "Contexte, définitions et confidentialité")
    feuilles["Synthèse par période"] = (indicateurs_par_periode(df), "Indicateurs clés pour chaque photographie semestrielle")
    feuilles["Départements"] = (par_departement(cur), f"Indicateurs par département au {contexte['periode']}")
    feuilles["Rémunération par grade"] = (remuneration_par_grade(cur), "Distribution des salaires par grade "
                                          "(écart F/H si au moins 10 personnes de chaque genre)")
    feuilles["Turnover par cohorte"] = (turnover(df), "Effectif, départs et taux de départ par cohorte et département")
    t = taux_niveaux.reset_index().rename(columns={
        "niveau": "Niveau", "effectif": "Effectif en validation", "departs": "Départs observés",
        "taux": "Taux de départ observé", "part_des_departs": "Part des départs", "taux_min": "Taux observé min",
        "taux_max": "Taux observé max"})
    feuilles["Niveaux de risque (validation)"] = (t, "Taux de départ réellement observés par niveau de risque "
                                                     "(validation temporelle sur 3 cohortes)")
    agg = sc.groupby(["departement", "niveau_risque"]).size().unstack(fill_value=0)
    agg = agg.reindex(columns=["Très élevé", "Élevé", "Modéré", "Faible"], fill_value=0)
    agg["Effectif"] = agg.sum(axis=1)
    agg["Part Très élevé + Élevé"] = (agg["Très élevé"] + agg["Élevé"]) / agg["Effectif"]
    feuilles["Anticipation par département"] = (agg.reset_index().rename(columns={"departement": "Département"}),
                                                "Répartition des collaborateurs au 31/12/2024 par niveau de risque")
    if nominatif:
        nomi = sc.sort_values("probabilite", ascending=False)[
            ["id", "departement", "poste", "grade", "contrat", "niveau_risque", "probabilite", "facteurs"]]
        feuilles["Anticipation nominative"] = (nomi.rename(columns={
            "id": "Identifiant", "departement": "Département", "poste": "Poste", "grade": "Grade",
            "contrat": "Contrat", "niveau_risque": "Niveau", "probabilite": "Probabilité estimée",
            "facteurs": "Principaux signaux"}), "Liste nominative des scores : profil DRH uniquement, diffusion restreinte")
    feuilles["Qualité · anomalies"] = (qualite["anomalies"], "Anomalies détectées dans les données brutes et règles "
                                                             "appliquées")
    feuilles["Qualité · manquants"] = (qualite["manquants"].rename(columns={
        "Manquant (historique)": "Part manquante (historique)", "Manquant (31/12/2024)": "Part manquante (31/12/2024)"}),
        "Taux de valeurs manquantes par variable")

    h = df[(df["jeu"] == "historique")]
    derniere_coh = h["periode"].max() if len(h) else None
    kpis = [("Effectif", len(cur), "#,##0"),
            ("Masse salariale mensuelle (FCFA)", float(cur["salaire_mensuel"].sum()), '#,##0,," M"'),
            ("Salaire médian (FCFA)", float(cur["salaire_mensuel"].median()), "#,##0"),
            ("Taux d'absentéisme", float(cur["taux_absenteisme"].mean()), "0.00%"),
            (f"Taux de départ à 6 mois ({derniere_coh})",
             float(h[h["periode"] == derniere_coh]["target"].mean()) if derniere_coh else None, "0.0%"),
            ("Collaborateurs à risque élevé ou très élevé", int(sc["signale"].sum()), "#,##0")]

    sortie = io.BytesIO()
    with pd.ExcelWriter(sortie, engine="openpyxl") as xl:
        wb = xl.book
        wb.create_sheet("Couverture")
        wb.create_sheet("Tableau de bord")
        ws_par_nom = {}
        for nom, (t, description) in feuilles.items():
            t.to_excel(xl, sheet_name=nom[:31], index=False, startrow=LIGNE_ENTETE - 1)
            ws = xl.sheets[nom[:31]]
            _bandeau(ws, nom, description, len(t.columns))
            _mise_en_forme(ws, t, [] if nom == "Lisez-moi" else FORMATS)
            ws.sheet_properties.tabColor = NOIR
            ws_par_nom[nom] = ws
        ws_par_nom["Lisez-moi"].column_dimensions["B"].width = 110
        if nominatif:                                  # couleur du niveau de risque dans la liste nominative
            ws = ws_par_nom["Anticipation nominative"]
            n = len(feuilles["Anticipation nominative"][0])
            for niveau, coul in COULEURS_NIVEAU.items():
                ws.conditional_formatting.add(f"F{LIGNE_ENTETE + 1}:F{LIGNE_ENTETE + n}", CellIsRule(
                    operator="equal", formula=[f'"{niveau}"'], fill=PatternFill("solid", fgColor=coul),
                    font=Font(color="FFFFFF" if niveau == "Très élevé" else "000000", bold=True)))
            ws.conditional_formatting.add(f"G{LIGNE_ENTETE + 1}:G{LIGNE_ENTETE + n}", DataBarRule(
                start_type="num", start_value=0, end_type="num", end_value=1, color=ORANGE, showValue=True))
        sommaire = [("Tableau de bord", "Indicateurs clés et graphiques")] + [(n, d) for n, (_, d) in feuilles.items()]
        _couverture(wb["Couverture"], contexte, nominatif, sommaire)
        _tableau_de_bord(wb["Tableau de bord"], cur, sc, kpis, ws_par_nom, len(feuilles["Synthèse par période"][0]),
                         len(feuilles["Départements"][0]))
        wb["Couverture"].sheet_properties.tabColor = ORANGE
        wb["Tableau de bord"].sheet_properties.tabColor = ORANGE
        wb.move_sheet("Couverture", offset=-wb.index(wb["Couverture"]))
        wb.move_sheet("Tableau de bord", offset=1 - wb.index(wb["Tableau de bord"]))
        wb.active = 0
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
        canvas.drawString(2 * cm, 1.2 * cm, f"TelcomCI · Pilotage RH · {conf} · exporté le "
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
              Paragraph("Méthode et limites : données semestrielles TelcomCI (juin 2022 à décembre 2024). "
                        "Départs connus jusqu'à la cohorte de juin 2024. Les associations statistiques présentées ne "
                        "démontrent aucune causalité. Le score de risque est un outil de priorisation des échanges RH ; "
                        "il ne peut fonder aucune décision défavorable (sanction, rémunération, promotion, formation).", st_n)]
    doc.build(elems, onFirstPage=pied, onLaterPages=pied)
    return sortie.getvalue()
