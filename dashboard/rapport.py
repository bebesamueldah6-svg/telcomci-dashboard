"""Exports PDF aux couleurs de TelcomCI : « Bilan RH semestriel » et « Fiche entretien ».

Module indépendant de Streamlit : il reçoit des tables pandas et renvoie des octets PDF.
Charte : noir, blanc, orange #FF7900 en accent (inspirée de la charte Orange), police Inter (OFL).
"""
import io
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
import numpy as np                                                 # noqa: E402
import pandas as pd                                                # noqa: E402
from matplotlib import font_manager                                # noqa: E402
from reportlab.lib import colors                                   # noqa: E402
from reportlab.lib.enums import TA_CENTER                          # noqa: E402
from reportlab.lib.pagesizes import A4                             # noqa: E402
from reportlab.lib.styles import ParagraphStyle                    # noqa: E402
from reportlab.lib.units import cm                                 # noqa: E402
from reportlab.pdfbase import pdfmetrics                           # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont                       # noqa: E402
from reportlab.platypus import (Image, KeepTogether, NextPageTemplate, PageBreak, Paragraph,  # noqa: E402
                                Spacer, Table, TableStyle)
from reportlab.platypus.doctemplate import BaseDocTemplate, Frame, PageTemplate  # noqa: E402

# ---------------------------------------------------------------------------
# Charte
# ---------------------------------------------------------------------------
ORANGE, NOIR, GRIS, GRIS_CLAIR, GRIS_FOND = "#FF7900", "#000000", "#8C8C8C", "#D6D6D6", "#F4F4F4"
ORANGE_TEXTE, ROUGE, VERT = "#F16E00", "#CD3C14", "#1E7B4C"
COULEURS_NIVEAU = {"Très élevé": ROUGE, "Élevé": ORANGE, "Modéré": "#FFC08A", "Faible": GRIS_CLAIR}
ICI = Path(__file__).parent
POLICES = ICI / "static" / "polices"
ICONES = ICI / "static" / "icones_png"
AVATARS = ICI / "static" / "avatars_png"

_POLICES = {"Inter": "Inter_400Regular.ttf", "Inter-SemiBold": "Inter_600SemiBold.ttf",
            "Inter-Bold": "Inter_700Bold.ttf", "Inter-ExtraBold": "Inter_800ExtraBold.ttf"}
for nom, fichier in _POLICES.items():
    if (POLICES / fichier).exists() and nom not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(nom, str(POLICES / fichier)))
    if (POLICES / fichier).exists():
        font_manager.fontManager.addfont(str(POLICES / fichier))
POLICE = "Inter" if "Inter" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
POLICE_G = "Inter-Bold" if POLICE == "Inter" else "Helvetica-Bold"
POLICE_XG = "Inter-ExtraBold" if POLICE == "Inter" else "Helvetica-Bold"
plt.rcParams.update({"font.family": "Inter" if POLICE == "Inter" else "DejaVu Sans", "font.size": 9,
                     "axes.edgecolor": GRIS_CLAIR, "axes.labelcolor": "#333333", "xtick.color": "#595959",
                     "ytick.color": "#595959", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 10, "axes.titlelocation": "left"})

S = {
    "titre": ParagraphStyle("titre", fontName=POLICE_XG, fontSize=20, leading=24, textColor=colors.black, spaceAfter=2),
    "sous": ParagraphStyle("sous", fontName=POLICE, fontSize=9.5, leading=13, textColor=colors.HexColor("#6B6B6B"),
                           spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName=POLICE_G, fontSize=12, leading=15, textColor=colors.black, spaceBefore=8,
                         spaceAfter=6),
    "corps": ParagraphStyle("corps", fontName=POLICE, fontSize=9.5, leading=13.5, textColor=colors.HexColor("#262626")),
    "petit": ParagraphStyle("petit", fontName=POLICE, fontSize=8, leading=11, textColor=colors.HexColor("#6B6B6B")),
    "cellule": ParagraphStyle("cellule", fontName=POLICE, fontSize=8.5, leading=11.5, textColor=colors.HexColor("#262626")),
    "cellule_g": ParagraphStyle("cellule_g", fontName=POLICE_G, fontSize=8.5, leading=11.5),
    "kpi_val": ParagraphStyle("kpi_val", fontName=POLICE_XG, fontSize=17, leading=20, alignment=TA_CENTER),
    "kpi_lib": ParagraphStyle("kpi_lib", fontName=POLICE, fontSize=8, leading=10.5, alignment=TA_CENTER,
                              textColor=colors.HexColor(ORANGE_TEXTE)),
    "kpi_delta": ParagraphStyle("kpi_delta", fontName=POLICE_G, fontSize=7.5, leading=10, alignment=TA_CENTER),
}


# ---------------------------------------------------------------------------
# Formats
# ---------------------------------------------------------------------------
def nb(x, d=0):
    return "—" if x is None or pd.isna(x) else f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def pct(x, d=1):
    return "—" if x is None or pd.isna(x) else f"{x * 100:.{d}f} %".replace(".", ",")


def fcfa(x):
    if x is None or pd.isna(x):
        return "—"
    if abs(x) >= 1e9:
        return f"{x / 1e9:.2f} Md".replace(".", ",")
    if abs(x) >= 1e6:
        return f"{x / 1e6:.1f} M".replace(".", ",")
    return f"{x / 1e3:.0f} k"


def _png(fig, largeur_cm, hauteur_cm):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=largeur_cm * cm, height=hauteur_cm * cm)


def _icone(nom, taille=0.9, teinte="sombre"):
    f = ICONES / f"{nom}_{teinte}.png"
    return Image(str(f), width=taille * cm, height=taille * cm) if f.exists() else Spacer(taille * cm, taille * cm)


def _barres_h(serie, titre, fmt, largeur=8.6, hauteur=6.2, surligner="max"):
    serie = serie.sort_values()
    fig, ax = plt.subplots(figsize=(largeur / 2.54, hauteur / 2.54))
    cible = serie.idxmax() if surligner == "max" else None
    couleurs = [ORANGE if k == cible else GRIS_CLAIR for k in serie.index]
    ax.barh(serie.index.astype(str), serie.values, color=couleurs, height=.62)
    for i, v in enumerate(serie.values):
        ax.text(v, i, " " + fmt(v), va="center", fontsize=7.5, color="#333333")
    ax.set_title(titre)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=8)
    ax.set_xlim(0, serie.max() * 1.25 if serie.max() > 0 else 1)
    return _png(fig, largeur, hauteur)


def _courbe(serie, titre, fmt, largeur=8.6, hauteur=5.6):
    fig, ax = plt.subplots(figsize=(largeur / 2.54, hauteur / 2.54))
    x = np.arange(len(serie))
    ax.plot(x, serie.values, color=ORANGE, linewidth=2.4, marker="o", markersize=4.5)
    ax.fill_between(x, serie.values, serie.min() * .96, color=ORANGE, alpha=.08)
    for i, v in enumerate(serie.values):
        ax.annotate(fmt(v), (i, v), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7.2)
    ax.set_xticks(x, serie.index, fontsize=7.5)
    ax.yaxis.set_visible(False)
    ax.spines["left"].set_visible(False)
    marge = (serie.max() - serie.min()) or abs(serie.max()) or 1
    ax.set_ylim(serie.min() - marge * .25, serie.max() + marge * .35)
    ax.set_title(titre)
    return _png(fig, largeur, hauteur)


# ---------------------------------------------------------------------------
# Mise en page : couverture, en-têtes et pieds de page
# ---------------------------------------------------------------------------
def _logo(c, x, y, taille, sur_noir=False):
    c.setFillColor(colors.HexColor("#1F1F1F") if sur_noir else colors.black)
    if sur_noir:
        c.setStrokeColor(colors.HexColor("#4A4A4A"))
        c.setLineWidth(1)
    c.roundRect(x, y, taille, taille, taille * .25, stroke=1 if sur_noir else 0, fill=1)
    c.setFont(POLICE_XG, taille * .44)
    t = c.stringWidth("TC", POLICE_XG, taille * .44)
    c.setFillColor(colors.white)
    c.drawString(x + (taille - t) / 2, y + taille * .32, "T")
    c.setFillColor(colors.HexColor(ORANGE))
    c.drawString(x + (taille - t) / 2 + c.stringWidth("T", POLICE_XG, taille * .44), y + taille * .32, "C")


class _Document(BaseDocTemplate):
    def __init__(self, buf, meta, **kw):
        super().__init__(buf, pagesize=A4, leftMargin=1.7 * cm, rightMargin=1.7 * cm, topMargin=2.3 * cm,
                         bottomMargin=1.8 * cm, title=meta["titre_doc"], author=meta["auteur"], **kw)
        self.meta = meta
        cadre = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="cadre")
        modeles = [PageTemplate(id="couverture", frames=[cadre], onPage=self._couverture),
                   PageTemplate(id="page", frames=[cadre], onPage=self._page)]
        self.addPageTemplates(modeles if meta.get("couverture") else modeles[::-1])

    def _couverture(self, c, doc):
        m, (L, H) = self.meta, A4
        c.saveState()
        c.setFillColor(colors.black)
        c.rect(0, 0, L, H, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor(ORANGE))
        c.setLineWidth(52)
        c.circle(L - 0.6 * cm, 6.2 * cm, 5.6 * cm, stroke=1, fill=0)
        _logo(c, 2 * cm, H - 3.6 * cm, 1.6 * cm, sur_noir=True)
        c.setFillColor(colors.white)
        c.setFont(POLICE_G, 12)
        c.drawString(3.95 * cm, H - 2.85 * cm, "TelcomCI")
        c.setFillColor(colors.HexColor("#BDBDBD"))
        c.setFont(POLICE, 9)
        c.drawString(3.95 * cm, H - 3.35 * cm, "Direction des Ressources Humaines")
        c.setStrokeColor(colors.HexColor(ORANGE))
        c.setLineWidth(1)
        c.roundRect(2 * cm, H - 9.2 * cm, c.stringWidth(m["etiquette"], POLICE_G, 9) + 0.9 * cm, 0.75 * cm, 0.37 * cm)
        c.setFillColor(colors.HexColor(ORANGE))
        c.setFont(POLICE_G, 9)
        c.drawString(2.45 * cm, H - 8.95 * cm, m["etiquette"])
        c.setFillColor(colors.white)
        c.setFont(POLICE_XG, 34)
        for i, ligne in enumerate(m["titre_couverture"]):
            c.setFillColor(colors.white if i == 0 else colors.HexColor(ORANGE))
            c.drawString(2 * cm, H - 11.1 * cm - i * 1.35 * cm, ligne)
        c.setFillColor(colors.HexColor("#D9D9D9"))
        c.setFont(POLICE, 12)
        for i, ligne in enumerate(m["sous_titre"]):
            c.drawString(2 * cm, H - 14.3 * cm - i * 0.62 * cm, ligne)
        c.setFillColor(colors.HexColor("#9A9A9A"))
        c.setFont(POLICE, 8.5)
        for i, ligne in enumerate(m["pied_couverture"]):
            c.drawString(2 * cm, 2.6 * cm - i * 0.48 * cm, ligne)
        c.restoreState()

    def _page(self, c, doc):
        m, (L, H) = self.meta, A4
        c.saveState()
        _logo(c, 1.7 * cm, H - 1.55 * cm, 0.68 * cm)
        c.setFont(POLICE_G, 8.5)
        c.setFillColor(colors.black)
        c.drawString(2.6 * cm, H - 1.2 * cm, m["entete"])
        c.setFont(POLICE, 7.5)
        c.setFillColor(colors.HexColor(GRIS))
        c.drawString(2.6 * cm, H - 1.5 * cm, m["entete_sous"])
        c.drawRightString(L - 1.7 * cm, H - 1.2 * cm, m["confidentialite"])
        c.setStrokeColor(colors.HexColor(ORANGE))
        c.setLineWidth(1.4)
        c.line(1.7 * cm, H - 1.8 * cm, L - 1.7 * cm, H - 1.8 * cm)
        c.setFont(POLICE, 7.5)
        c.setFillColor(colors.HexColor(GRIS))
        c.drawString(1.7 * cm, 1.05 * cm, m["pied"])
        c.setFont(POLICE_G, 8)
        c.setFillColor(colors.black)
        c.drawRightString(L - 1.7 * cm, 1.05 * cm, f"{doc.page - (1 if m.get('couverture') else 0)}")
        c.restoreState()


def _tuiles_kpi(kpis, colonnes=3, largeur=17.6):
    """kpis = [(icône, valeur, libellé, delta texte, delta « bon » ?)]"""
    cellules = []
    for icone, valeur, libelle, delta, bon in kpis:
        coul = VERT if bon is True else ROUGE if bon is False else GRIS
        style_val = S["kpi_val"] if colonnes <= 3 else ParagraphStyle("kv", parent=S["kpi_val"], fontSize=12.5, leading=15)
        bloc = [_icone(icone, 0.85 if colonnes <= 3 else 0.7), Spacer(1, 4), Paragraph(valeur, style_val),
                Paragraph(libelle, S["kpi_lib"])]
        if delta:
            bloc.append(Paragraph(f"<font color='{coul}'>{delta}</font>", S["kpi_delta"]))
        cellules.append(bloc)
    lignes = [cellules[i:i + colonnes] for i in range(0, len(cellules), colonnes)]
    lignes[-1] += [""] * (colonnes - len(lignes[-1]))
    t = Table(lignes, colWidths=[largeur / colonnes * cm] * colonnes)
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#E6E6E6")),
                           ("INNERGRID", (0, 0), (-1, -1), .6, colors.HexColor("#E6E6E6")),
                           ("TOPPADDING", (0, 0), (-1, -1), 10 if colonnes <= 3 else 7),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 10 if colonnes <= 3 else 7),
                           ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return t


def _cases(textes):
    """Liste de cases à cocher dessinées (la police n'a pas le caractère ☐)."""
    case = Table([[""]], colWidths=[0.34 * cm], rowHeights=[0.34 * cm],
                 style=[("BOX", (0, 0), (-1, -1), .8, colors.HexColor("#595959"))])
    t = Table([[case, Paragraph(x, S["cellule"])] for x in textes], colWidths=[0.7 * cm, 16.9 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _messages(messages):
    lignes = []
    for i, (titre, texte) in enumerate(messages, 1):
        pastille = Table([[Paragraph(f"<font color='white'>{i}</font>",
                                     ParagraphStyle("p", fontName=POLICE_XG, fontSize=12, alignment=TA_CENTER))]],
                         colWidths=[0.8 * cm], rowHeights=[0.8 * cm])
        pastille.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                      ("ROUNDEDCORNERS", [11, 11, 11, 11])]))
        lignes.append([pastille, [Paragraph(titre, S["cellule_g"]), Paragraph(texte, S["cellule"])]])
    t = Table(lignes, colWidths=[1.2 * cm, 16.4 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                           ("LINEBELOW", (0, 0), (-1, -2), .5, colors.HexColor("#EEEEEE"))]))
    return t


def _tableau(donnees, entetes, largeurs, couleurs_lignes=None):
    corps = [[Paragraph(f"<font color='white'>{e}</font>", S["cellule_g"]) for e in entetes]]
    corps += [[Paragraph(str(v), S["cellule"]) for v in ligne] for ligne in donnees]
    t = Table(corps, colWidths=[w * cm for w in largeurs], repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), colors.black), ("LINEBELOW", (0, 0), (-1, 0), 2, colors.HexColor(ORANGE)),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
             ("LINEBELOW", (0, 1), (-1, -1), .4, colors.HexColor("#EAEAEA")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    for (ligne, coul) in (couleurs_lignes or []):
        style.append(("BACKGROUND", (0, ligne), (0, ligne), colors.HexColor(coul)))
    t.setStyle(TableStyle(style))
    return t


def _deux(gauche, droite, ecart=0.4):
    t = Table([[gauche, droite]], colWidths=[(17.6 - ecart) / 2 * cm + ecart / 2 * cm] * 2)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _encadre(texte, fond="#FFF4EB", bord="#FFD9B8"):
    t = Table([[Paragraph(texte, S["corps"])]], colWidths=[17.6 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fond)),
                           ("BOX", (0, 0), (-1, -1), .6, colors.HexColor(bord)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                           ("ROUNDEDCORNERS", [6, 6, 6, 6])]))
    return t


# ---------------------------------------------------------------------------
# Bilan RH semestriel
# ---------------------------------------------------------------------------
def _evol(a, b):
    return None if b in (0, None) or pd.isna(b) or pd.isna(a) else a / b - 1


def _delta(a, b, inverse=False, points=False, unite=""):
    if a is None or b is None or pd.isna(a) or pd.isna(b):
        return "", None
    if points:
        d = (a - b) * 100
        if abs(d) < 0.05:
            return "stable vs semestre précédent", None
        dec = 2 if abs(d) < 1 else 1
        txt = f"{'▲' if d > 0 else '▼'} {abs(d):.{dec}f} pt{unite}".replace(".", ",")
    else:
        e = _evol(a, b)
        if e is None:
            return "", None
        d = e
        txt = f"{'▲' if e > 0 else '▼' if e < 0 else '='} {pct(abs(e))}"
    bon = None if d == 0 else ((d > 0) != inverse)
    return txt + " vs semestre précédent", bon


def bilan(df, scores, taux_niveaux, per, prec, coh, coh_prec, contexte, nominatif, dates, jours_ouvres=130,
          ordre_age=None):
    """`df` : toutes les périodes du périmètre ; `scores` : collaborateurs au 31/12/2024 avec niveau de risque."""
    ordre_age = ordre_age or ["<25", "25-29", "30-34", "35-39", "40-44", "45-49", "50+"]
    cur, avant = df[df["periode"] == per], (df[df["periode"] == prec] if prec else df.iloc[:0])
    h = df[(df["jeu"] == "historique")]
    hc, hp = h[h["periode"] == coh], (h[h["periode"] == coh_prec] if coh_prec else h.iloc[:0])
    perimetre = contexte["departement"]
    tous = perimetre.startswith("Tous")
    sc = scores if tous else scores[scores["departement"] == perimetre]
    # périmètre d'un seul département : les répartitions se font par grade
    axe, lib_axe, lib_axe_cap = ("departement", "département", "Département") if tous else ("grade", "grade", "Grade")

    # --- indicateurs
    eff, eff_p = len(cur), len(avant)
    masse, masse_p = cur["salaire_mensuel"].sum(), avant["salaire_mensuel"].sum()
    med, med_p = cur["salaire_mensuel"].median(), avant["salaire_mensuel"].median()
    absn, absn_p = cur["taux_absenteisme"].mean(), avant["taux_absenteisme"].mean()
    dep, dep_p = hc["target"].mean(), hp["target"].mean()
    signales = int(sc["signale"].sum())
    kpis = [("groups", nb(eff), "Effectif", *_delta(eff, eff_p)),
            ("payments", f"{fcfa(masse)} FCFA", "Masse salariale mensuelle", *_delta(masse, masse_p)),
            ("balance", f"{fcfa(med)} FCFA", "Salaire médian", *_delta(med, med_p)),
            ("event_busy", pct(absn, 2), "Taux d'absentéisme", *_delta(absn, absn_p, inverse=True, points=True)),
            ("logout", pct(dep), f"Taux de départ à 6 mois (cohorte {coh})", *_delta(dep, dep_p, inverse=True, points=True)),
            ("gps_fixed", nb(signales), "Collaborateurs à risque élevé ou très élevé",
             f"soit {pct(sc['signale'].mean(), 0)} de l'effectif", None)]

    # --- messages clés
    td = hc[hc[axe] != "Non renseigné"].groupby(axe)["target"].agg(["mean", "size", "sum"])
    td = td[td["size"] >= 20].sort_values("mean", ascending=False)
    sig = sc[sc["signale"]][axe].value_counts()
    sous_ref = (cur["ratio_salaire_reference"] < 0.9)
    messages = [("Un effectif en croissance soutenue",
                 f"{nb(eff)} collaborateurs au {dates[per]}"
                 + (f", soit {pct(_evol(eff, eff_p))} en six mois" if eff_p else "")
                 + f", porté par {nb(cur['arrivee'].sum())} arrivées sur le semestre.")]
    if len(td):
        messages.append((f"{td.index[0]} : le turnover le plus élevé",
                         f"{pct(td.iloc[0]['mean'])} de départs à 6 mois sur la cohorte {coh} ({int(td.iloc[0]['sum'])} sur "
                         f"{int(td.iloc[0]['size'])}), contre {pct(dep)} pour l'ensemble du périmètre."))
    if len(sig):
        messages.append((f"Le risque de départ se concentre dans {sig.index[0]}",
                         f"{sig.iloc[0]} des {signales} collaborateurs signalés ({pct(sig.iloc[0] / max(signales, 1), 0)}). "
                         f"{pct(sous_ref.mean(), 0)} de l'effectif est payé sous 90 % de la référence de son grade, "
                         "l'une des caractéristiques les plus associées aux départs observés."))

    # --- graphiques
    eff_per = df.groupby("periode").size()
    g_eff = _courbe(eff_per, "Effectif par période", nb)
    pyr = cur[cur["genre"].isin(["F", "M"])].groupby(["tranche_age", "genre"]).size().unstack(fill_value=0)
    pyr = pyr.reindex([a for a in ordre_age if a in pyr.index])
    fig, ax = plt.subplots(figsize=(8.6 / 2.54, 6 / 2.54))
    ax.barh(pyr.index, -pyr.get("F", 0), color=ORANGE, height=.65, label="Femmes")
    ax.barh(pyr.index, pyr.get("M", 0), color="#595959", height=.65, label="Hommes")
    lim = max(pyr.max().max(), 1) * 1.25
    ax.set_xlim(-lim, lim)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=8)
    for i, (f_, m_) in enumerate(zip(pyr.get("F", 0), pyr.get("M", 0))):
        ax.text(-f_, i, f"{f_} ", ha="right", va="center", fontsize=7)
        ax.text(m_, i, f" {m_}", ha="left", va="center", fontsize=7)
    ax.axvline(0, color="#BDBDBD", linewidth=.8)
    ax.legend(frameon=False, fontsize=7.5, loc="lower right", ncols=2, bbox_to_anchor=(1, -0.16))
    ax.set_title("Pyramide des âges (femmes · hommes)")
    g_pyr = _png(fig, 8.6, 6)
    g_masse = _barres_h(cur[cur[axe] != "Non renseigné"].groupby(axe)["salaire_mensuel"].sum(),
                        f"Masse salariale mensuelle par {lib_axe} (FCFA)", fcfa, hauteur=7)
    gr = cur.groupby("grade")["salaire_mensuel"]
    fig, ax = plt.subplots(figsize=(8.6 / 2.54, 7 / 2.54))
    x = np.arange(len(gr.median()))
    ax.bar(x, gr.median().values, color=[GRIS_CLAIR] * (len(x) - 1) + [ORANGE], width=.6)
    ax.errorbar(x, gr.median().values, yerr=[gr.median() - gr.quantile(.25), gr.quantile(.75) - gr.median()],
                fmt="none", ecolor="#333333", capsize=3, linewidth=1)
    for i, v in enumerate(gr.median().values):
        ax.text(i, v * .5, fcfa(v), ha="center", fontsize=7.2, color="#262626")
    ax.set_xticks(x, gr.median().index)
    ax.yaxis.set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.set_title("Salaire médian par grade (trait : 1er-3e quartile)")
    g_grade = _png(fig, 8.6, 7)
    fh = cur[cur["genre"].isin(["F", "M"])].groupby(["grade", "genre"])["salaire_mensuel"].median().unstack()
    n_fh = cur[cur["genre"].isin(["F", "M"])].groupby(["grade", "genre"]).size().unstack()
    ecart = (fh["F"] / fh["M"] - 1).where((n_fh["F"] >= 10) & (n_fh["M"] >= 10))
    g_abs_dep = _barres_h(cur[cur[axe] != "Non renseigné"].groupby(axe)["taux_absenteisme"].mean(),
                          f"Taux d'absentéisme par {lib_axe}", lambda v: pct(v, 2), hauteur=7)
    g_abs_per = _courbe(df.groupby("periode")["taux_absenteisme"].mean(), "Taux d'absentéisme par période",
                        lambda v: pct(v, 2), hauteur=7)
    g_dep_coh = _courbe(h.groupby("periode")["target"].mean(), "Taux de départ à 6 mois par cohorte", pct)
    g_dep_dep = _barres_h(td["mean"], f"Taux de départ par {lib_axe} (cohorte {coh})", pct)
    tn = taux_niveaux.reset_index()
    fig, ax = plt.subplots(figsize=(8.6 / 2.54, 6 / 2.54))
    ax.bar(tn["niveau"], tn["taux"], color=[COULEURS_NIVEAU[n] for n in tn["niveau"]], width=.6)
    for i, v in enumerate(tn["taux"]):
        ax.text(i, v, f"{pct(v, 0)}", ha="center", va="bottom", fontsize=8, fontweight="bold")
    ax.yaxis.set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="x", labelsize=8, length=0)
    ax.set_title("Départs réellement observés par niveau de risque")
    g_niv = _png(fig, 8.6, 6)
    g_sig = _barres_h(sig, f"Collaborateurs signalés par {lib_axe}", nb) if len(sig) else Spacer(1, 1)

    # --- plan d'action (règles explicites, partagées avec la page Recommandations du dashboard)
    actions = [(a["priorite"], a["constat"], a["action"], a["indicateur"])
               for a in plan_action(cur, hc, sc, taux_niveaux, axe, lib_axe)]

    # --- assemblage
    meta = {"titre_doc": f"Bilan RH semestriel · TelcomCI · {per}", "auteur": contexte["utilisateur"], "couverture": True,
            "etiquette": "Bilan RH semestriel", "titre_couverture": ["Pilotez vos effectifs.", "Anticipez les départs."],
            "sous_titre": [f"Situation au {dates[per]}", f"Périmètre : {perimetre}"],
            "pied_couverture": [f"Exporté le {datetime.now().strftime('%d/%m/%Y à %H:%M')} par {contexte['utilisateur']} "
                                f"(profil {contexte['role']})",
                                "Diffusion restreinte DRH · données agrégées, aucune donnée individuelle" if nominatif else
                                "Document de comité · données agrégées uniquement",
                                "TelcomCI · Pilotage RH · Projet MDSBDIA · INP-HB Yamoussoukro"],
            "entete": "Bilan RH semestriel", "entete_sous": f"Situation au {dates[per]} · {perimetre}",
            "confidentialite": "Diffusion restreinte DRH" if nominatif else "Document de comité",
            "pied": "TelcomCI · Pilotage RH · données semestrielles juin 2022 – décembre 2024"}
    buf = io.BytesIO()
    doc = _Document(buf, meta)
    e = [NextPageTemplate("page"), PageBreak()]
    e += [Paragraph("Synthèse", S["titre"]), Paragraph(f"Les chiffres clés du semestre et ce qu'il faut en retenir.", S["sous"]),
          _tuiles_kpi(kpis), Spacer(1, 14), Paragraph("Trois messages clés", S["h2"]), _messages(messages),
          Spacer(1, 10), _encadre("<b>Comment lire ce bilan.</b> Les évolutions comparent la situation au "
                                  f"{dates[per]} à celle du semestre précédent. Les départs ne sont connus qu'à six mois : "
                                  f"le taux de départ porte donc sur la cohorte {coh}. Le niveau de risque est un signal "
                                  "statistique à examiner, jamais une prédiction individuelle.")]
    e += [PageBreak(), Paragraph("Effectifs et diversité", S["titre"]),
          Paragraph(f"{nb(eff)} collaborateurs, {pct((cur['genre'] == 'F').mean(), 0)} de femmes, âge moyen "
                    f"{nb(cur['age'].mean(), 1)} ans, ancienneté moyenne {nb(cur['anciennete'].mean(), 1)} ans, "
                    f"{pct((cur['contrat'] == 'CDD').mean(), 0)} de CDD.", S["sous"]),
          _deux(g_eff, g_pyr), Spacer(1, 8),
          _tableau([[d_, nb(n), pct(f_, 0), nb(a_, 1), pct(c_, 0)] for d_, (n, f_, a_, c_) in
                    cur.groupby(axe).agg(n=("id", "size"), f=("genre", lambda s: (s == "F").mean()),
                                                   a=("age", "mean"), c=("contrat", lambda s: (s == "CDD").mean()))
                    .sort_values("n", ascending=False).iterrows()],
                   [lib_axe_cap, "Effectif", "Part de femmes", "Âge moyen", "Part de CDD"], [4.4, 3.3, 3.3, 3.3, 3.3])]
    e += [PageBreak(), Paragraph("Rémunération", S["titre"]),
          Paragraph(f"Masse salariale mensuelle de {fcfa(masse)} FCFA, salaire médian de {fcfa(med)} FCFA. "
                    f"{pct(sous_ref.mean(), 0)} des collaborateurs sont payés sous 90 % de la référence de leur grade.",
                    S["sous"]),
          _deux(g_masse, g_grade), Spacer(1, 8), Paragraph("Écart de salaire médian femmes / hommes par grade", S["h2"]),
          _tableau([[g_, nb(fh.loc[g_, "F"]), nb(fh.loc[g_, "M"]),
                     pct(ecart.get(g_)) if not pd.isna(ecart.get(g_)) else "effectif insuffisant"] for g_ in fh.index],
                   ["Grade", "Médiane femmes (FCFA)", "Médiane hommes (FCFA)", "Écart F/H"], [3, 4.9, 4.9, 4.8]),
          Spacer(1, 4), Paragraph("Écart calculé seulement si au moins 10 femmes et 10 hommes dans le grade. Écart brut : "
                                  "il ne tient pas compte du poste ni de l'ancienneté.", S["petit"])]
    e += [PageBreak(), Paragraph("Absentéisme", S["titre"]),
          Paragraph(f"Taux d'absentéisme de {pct(absn, 2)} (jours d'absence sur 6 mois ÷ {jours_ouvres} jours ouvrés), "
                    f"{nb(cur['abs_non_just_6m'].sum())} jours non justifiés sur le semestre.", S["sous"]),
          _deux(g_abs_dep, g_abs_per)]
    e += [Spacer(1, 10), Paragraph("Turnover et anticipation des départs", S["titre"]),
          Paragraph(f"Taux de départ à 6 mois de {pct(dep)} sur la cohorte {coh}. {signales} collaborateurs en niveau de "
                    "risque élevé ou très élevé au 31/12/2024.", S["sous"]),
          _deux(g_dep_coh, g_dep_dep), Spacer(1, 6), _deux(g_niv, g_sig)]
    e += [PageBreak(), Paragraph("Plan d'action proposé", S["titre"]),
          Paragraph("Recommandations établies à partir de règles explicites appliquées aux indicateurs du semestre. "
                    "Elles sont à discuter avec les managers concernés.", S["sous"]),
          _tableau([[p_, c_, a_, i_] for p_, c_, a_, i_ in actions], ["Priorité", "Constat", "Action proposée",
                                                                       "Indicateur de suivi"], [2.1, 5.6, 6.1, 3.8],
                   couleurs_lignes=[(i + 1, {"Haute": "#FBEAE5", "Moyenne": "#FFF4EB", "Basse": "#F4F4F4",
                                             "Cadre": "#F4F4F4"}[a[0]]) for i, a in enumerate(actions)])]
    e += [Spacer(1, 14), KeepTogether([Paragraph("Méthode et limites", S["h2"]), Paragraph(
        "Données semestrielles TelcomCI de juin 2022 à décembre 2024. Un départ correspond à une sortie dans les six mois "
        "suivant la date de référence ; il est connu jusqu'à la cohorte de juin 2024. Une arrivée correspond à une embauche "
        "dans les six mois précédant la date de référence. Une valeur non renseignée n'est jamais comptée comme une valeur "
        "faible. Les associations présentées ne démontrent aucune causalité. Le niveau de risque provient d'un modèle de "
        "classement validé sur trois cohortes (validation temporelle) ; le genre n'est pas utilisé par ce modèle. Il sert "
        "à prioriser des échanges RH et ne peut fonder aucune décision défavorable (sanction, rémunération, promotion, "
        "formation).", S["corps"])])]
    doc.build(e)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Plan d'action : règles explicites appliquées aux indicateurs (bilan PDF et page Recommandations)
# ---------------------------------------------------------------------------
def plan_action(cur, hc, sc, taux_niveaux, axe="departement", lib_axe="département"):
    """cur : effectif à la date choisie ; hc : cohorte historique (départ connu) ; sc : scores du périmètre.
    Renvoie une liste de dicts : priorite, constat, action, indicateur, page (adresse de la page à ouvrir)."""
    actions = []
    dep = hc["target"].mean()
    td = hc[hc[axe] != "Non renseigné"].groupby(axe)["target"].agg(["mean", "size", "sum"])
    td = td[td["size"] >= 20].sort_values("mean", ascending=False)
    sig = sc[sc["signale"]][axe].value_counts()
    signales = int(sc["signale"].sum())
    for d_, ligne in td.iterrows():
        if ligne["mean"] >= dep + 0.03 and sum(a["priorite"] == "Haute" for a in actions) < 2:
            n_sig = int(sig.get(d_, 0))
            actions.append(dict(priorite="Haute", page="anticipation",
                                constat=f"{d_} : {pct(ligne['mean'])} de départs à 6 mois, "
                                        f"{pct(ligne['mean'] - dep, 1).replace(' %', ' pt')} au-dessus du périmètre",
                                action=f"Entretiens de rétention ciblés sur les {n_sig} collaborateurs signalés "
                                       f"({lib_axe} {d_})", indicateur="Taux de départ de la cohorte suivante"))
    sous_ref = cur["ratio_salaire_reference"] < 0.9
    if sous_ref.mean() > .1:
        n_sr = int((sous_ref & cur["id"].isin(sc[sc["signale"]]["id"])).sum())
        actions.append(dict(priorite="Haute", page="salaires",
                            constat=f"{pct(sous_ref.mean(), 0)} de l'effectif ({nb(sous_ref.sum())}) payé sous 90 % de "
                                    "la référence du grade",
                            action=f"Revue salariale prioritaire, en commençant par les {n_sr} collaborateurs signalés "
                                   "concernés", indicateur="Part sous 90 % de la référence"))
    perf_eng = cur[(cur["performance_actuelle"] >= 4) & (cur["engagement_actuel"] < 3)]
    if len(perf_eng):
        actions.append(dict(priorite="Moyenne", page="performance",
                            constat=f"{len(perf_eng)} profils performants mais peu engagés (performance ≥ 4, "
                                    "engagement < 3)",
                            action="Entretiens de carrière et plan de développement individuel",
                            indicateur="Engagement au semestre suivant"))
    absn = cur["taux_absenteisme"].mean()
    ab = cur[cur[axe] != "Non renseigné"].groupby(axe)["taux_absenteisme"].mean()
    if len(ab) and ab.max() > absn * 1.15:
        actions.append(dict(priorite="Moyenne", page="absences-departement",
                            constat=f"{ab.idxmax()} : absentéisme de {pct(ab.max(), 2)} contre {pct(absn, 2)} en moyenne",
                            action="Analyse des causes avec le manager (absences non justifiées, charge, organisation)",
                            indicateur=f"Taux d'absentéisme du {lib_axe}"))
    fh = cur[cur["genre"].isin(["F", "M"])].groupby(["grade", "genre"])["salaire_mensuel"].median().unstack()
    n_fh = cur[cur["genre"].isin(["F", "M"])].groupby(["grade", "genre"]).size().unstack()
    if {"F", "M"} <= set(fh.columns):
        ec = (fh["F"] / fh["M"] - 1).where((n_fh["F"] >= 10) & (n_fh["M"] >= 10)).dropna()
        if len(ec) and ec.abs().max() > .05:
            g_ = ec.abs().idxmax()
            actions.append(dict(priorite="Moyenne", page="equite-salariale",
                                constat=f"Écart de salaire médian F/H de {pct(ec[g_])} en {g_}",
                                action=f"Audit d'équité salariale du grade {g_} à poste et ancienneté comparables",
                                indicateur="Écart médian F/H"))
    manq = cur["performance_actuelle"].isna().mean()
    if manq > .05:
        actions.append(dict(priorite="Basse", page="qualite-donnees",
                            constat=f"{pct(manq, 0)} des évaluations de performance manquantes",
                            action="Relancer les managers pour compléter les évaluations",
                            indicateur="Taux d'évaluations renseignées"))
    tn = taux_niveaux.reset_index().set_index("niveau")
    if len(tn) and "part_des_departs" in tn:
        part = tn.loc[["Très élevé", "Élevé"], "part_des_departs"].sum()
        actions.append(dict(priorite="Cadre", page="anticipation",
                            constat=f"Les niveaux « très élevé » et « élevé » ({signales} personnes) ont capté "
                                    f"{pct(part, 0)} des départs en validation",
                            action="Limiter l'accompagnement à ce groupe pour concentrer l'effort ; ne jamais fonder une "
                                   "décision défavorable sur le score", indicateur="Part des départs couverte"))
    return actions


# ---------------------------------------------------------------------------
# Fiche entretien (une page, profil DRH)
# ---------------------------------------------------------------------------
def _tranche(age):
    if pd.isna(age):
        return "30_39"
    return "moins30" if age < 30 else "30_39" if age < 40 else "40_49" if age < 50 else "50plus"


def fiche_entretien(p, signaux, nuances, manquants, taux_niveau, reperes, contexte):
    """p : ligne du collaborateur ; signaux / nuances : listes de dicts (famille, intensite, valeur, reference)."""
    fichiers = sorted(AVATARS.glob(f"{p['genre']}_{_tranche(p['age'])}_*.png")) if p["genre"] in ("F", "M") else []
    avatar = (Image(str(fichiers[sum(map(ord, str(p['id']))) % len(fichiers)]), width=2.8 * cm, height=2.8 * cm)
              if fichiers else Spacer(3 * cm, 3 * cm))
    coul = COULEURS_NIVEAU.get(p["niveau_risque"], GRIS_CLAIR)
    meta = {"titre_doc": f"Fiche entretien · {p['id']}", "auteur": contexte["utilisateur"], "couverture": False,
            "entete": "Fiche de préparation d'entretien", "entete_sous": f"Collaborateur {p['id']} · {p['departement']}",
            "confidentialite": "Confidentiel · DRH", "pied": f"TelcomCI · exportée le {datetime.now():%d/%m/%Y à %H:%M} par "
            f"{contexte['utilisateur']} · document à détruire après l'entretien"}
    buf = io.BytesIO()
    doc = _Document(buf, meta)
    identite = [Paragraph(f"<font size=15><b>{p['poste']}</b></font>", S["corps"]), Spacer(1, 3),
                Paragraph(f"{p['id']} · {p['departement']} · {p['grade']} · {p['contrat']}", S["sous"]),
                Table([[Paragraph(f"<font color='{'white' if p['niveau_risque'] == 'Très élevé' else '#222'}'><b>Niveau de "
                                  f"risque : {p['niveau_risque'].lower()}</b></font>", S["cellule"])]],
                      colWidths=[7 * cm], style=[("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(coul)),
                                                 ("ROUNDEDCORNERS", [5, 5, 5, 5])]),
                Spacer(1, 3), Paragraph(f"Sur les cohortes de validation, {pct(taux_niveau, 0)} des personnes de ce niveau "
                                        "sont parties dans les 6 mois : c'est un taux de groupe, il ne dit rien des "
                                        "intentions de cette personne.", S["petit"])]
    haut = Table([[avatar, identite]], colWidths=[3.6 * cm, 14 * cm])
    haut.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    kpis = [("hourglass_bottom", f"{nb(p['anciennete'], 1)} ans", "Ancienneté", "", None),
            ("payments", f"{fcfa(p['salaire_mensuel'])} FCFA", "Salaire mensuel",
             f"{nb(p['ratio_salaire_reference'], 2)} × la référence du grade", None),
            ("upgrade", "Jamais" if p["jamais_promu"] else f"il y a {nb(p['annees_depuis_promotion'], 1)} ans",
             "Dernière promotion", "", None),
            ("event_busy", nb(p["jours_abs_6m"], 1), "Jours d'absence (6 mois)",
             f"dont {nb(p['abs_non_just_6m'], 1)} non justifiés", None),
            ("star", nb(p["performance_actuelle"], 2), "Performance (/5)", f"précédente : {nb(p['performance_precedente'], 2)}",
             None),
            ("mood", nb(p["engagement_actuel"], 2), "Engagement (/5)", f"médiane {p['departement']} : "
             f"{nb(reperes['engagement_median'], 2)}", None)]
    lignes_sig = [[x["famille"], "Augmente le score", x["intensite"], x["valeur"], x["reference"]] for x in signaux]
    lignes_sig += [[x["famille"], "Nuance le signal", x["intensite"], x["valeur"], x["reference"]] for x in nuances]
    a_verifier = [f"{m} : donnée non renseignée" for m in manquants] + [
        "Contexte récent (changement de poste, de manager, situation personnelle) : absent des données",
        "Perception de la rémunération et des perspectives d'évolution", "Charge de travail et relation avec le manager"]
    notes = Table([[""]] * 4, colWidths=[17.6 * cm], rowHeights=[0.7 * cm] * 4)
    notes.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), .5, colors.HexColor("#CFCFCF"))]))
    e = [haut, Spacer(1, 8), _tuiles_kpi(kpis, colonnes=6), Spacer(1, 4),
         Paragraph("Ce qui explique le score", S["h2"]),
         _tableau(lignes_sig or [["—", "Aucun élément ne se distingue nettement", "", "", ""]],
                  ["Élément", "Effet", "Intensité", "Valeur du collaborateur", "Référence"], [4, 3.1, 2.3, 4.1, 4.1]),
         Spacer(1, 8), Paragraph("À vérifier pendant l'entretien", S["h2"]),
         _cases(a_verifier), Spacer(1, 4),
         Paragraph("Notes de l'entretien", S["h2"]), notes, Spacer(1, 6),
         Paragraph("Les effets sont des associations statistiques mesurées par rapport à un collaborateur moyen, pas des "
                   "causes. Le genre n'est pas utilisé par le modèle. Aucune décision défavorable ne peut être fondée sur "
                   "ce score.", S["petit"])]
    doc.build(e)
    return buf.getvalue()
