"""Connexion simple par mot de passe, avec deux rôles de démonstration.

Les comptes sont lus dans les secrets Streamlit s'ils existent, sinon dans dashboard/comptes_demo.toml.
Ce fichier ne contient que des empreintes salées (jamais de mot de passe en clair) :

    [comptes.drh]
    role = "drh"
    nom = "Direction des Ressources Humaines"
    sel = "…"
    empreinte = "…"        # PBKDF2-SHA256(mot de passe, sel)

Générer une empreinte :  python dashboard/auth.py <mot_de_passe>
"""
import hashlib
import hmac
import tomllib
from pathlib import Path
import secrets
import sys
import time

import streamlit as st

ROLES = {
    "drh": {"libelle": "DRH", "nominatif": True,
            "description": "Accès complet, y compris aux données individuelles (fiche collaborateur, listes nominatives)."},
    "direction": {"libelle": "Direction générale", "nominatif": False,
                  "description": "Indicateurs agrégés uniquement : aucune donnée individuelle."},
}
ITERATIONS = 200_000
DUREE_SESSION = 2 * 3600          # secondes
ESSAIS_MAX, BLOCAGE = 5, 60       # tentatives avant blocage, durée du blocage (s)


def empreinte(mot_de_passe, sel):
    return hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode(), bytes.fromhex(sel), ITERATIONS).hex()


COMPTES_DEMO = Path(__file__).with_name("comptes_demo.toml")


def comptes():
    """Secrets Streamlit en priorité ; à défaut, comptes de démonstration (empreintes uniquement)."""
    try:
        return {k: dict(v) for k, v in st.secrets["comptes"].items()}
    except Exception:
        pass
    try:
        with open(COMPTES_DEMO, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def verifier(identifiant, mot_de_passe):
    compte = comptes().get(identifiant.strip().lower())
    if not compte or compte.get("role") not in ROLES:
        hmac.compare_digest("a", "b")          # temps de réponse comparable, que le compte existe ou non
        return None
    if hmac.compare_digest(empreinte(mot_de_passe, compte["sel"]), compte["empreinte"]):
        return {"identifiant": identifiant.strip().lower(), "role": compte["role"],
                "nom": compte.get("nom", ROLES[compte["role"]]["libelle"]), "depuis": time.time()}
    return None


def utilisateur():
    """Utilisateur connecté (ou None si absent ou session expirée)."""
    u = st.session_state.get("utilisateur")
    if u and time.time() - u["depuis"] > DUREE_SESSION:
        st.session_state.pop("utilisateur", None)
        st.session_state["session_expiree"] = True
        return None
    return u


def peut_voir_nominatif():
    u = utilisateur()
    return bool(u and ROLES[u["role"]]["nominatif"])


def deconnecter():
    for cle in list(st.session_state.keys()):
        del st.session_state[cle]


CSS_CONNEXION = """<style>
header[data-testid="stHeader"] {background: transparent;}
.block-container {padding-top: 1.5rem !important; padding-bottom: 0 !important; max-width: 1300px;}
.cx-panneau {background: #000; border-radius: 18px; padding: 48px 46px; min-height: 86vh; color: #fff;
  display: flex; flex-direction: column; justify-content: space-between; position: relative; overflow: hidden;}
.cx-panneau:after {content: ""; position: absolute; right: -120px; bottom: -120px; width: 380px; height: 380px;
  border-radius: 50%; border: 46px solid #FF7900; opacity: .9; z-index: 0;}
.cx-marque {font-size: 1.35rem; font-weight: 700; letter-spacing: -.01em;}
.cx-marque b {color: #FF7900;}
.cx-contenu {position: relative; z-index: 1;}
.cx-pastille {display: inline-block; color: #FF7900; border: 1px solid #FF7900; padding: 4px 12px;
  border-radius: 999px; font-size: .78rem; font-weight: 600; margin-bottom: 18px;}
.cx-accroche {font-size: 2.5rem; line-height: 1.15; font-weight: 800; letter-spacing: -.02em; margin: 0 0 14px;}
.cx-accroche span {color: #FF7900;}
.cx-sous {color: #CCC; font-size: 1rem; max-width: 460px; line-height: 1.55;}
.cx-chiffres {display: flex; gap: 40px; margin-top: 34px;}
.cx-v {display: inline-block; font-size: 1.75rem; font-weight: 800; line-height: 1.1; padding-bottom: 8px;
  background: linear-gradient(#FF7900, #FF7900) bottom left / 34px 3px no-repeat;}
.cx-l {font-size: .8rem; color: #AAA; margin-top: 8px;}
.cx-pied {color: #999; font-size: .78rem; position: relative; z-index: 1; background: #000;
  padding: 4px 8px 4px 0; width: fit-content;}
.cx-titre {font-size: 2rem; font-weight: 800; color: #000; letter-spacing: -.02em;}
.cx-st {color: #6B6B6B; font-size: .95rem; margin: .3rem 0 1.4rem;}
.cx-droits {background: #FFF4EB; border: 1px solid #FFD9B8; border-radius: 10px; padding: 10px 14px;
  color: #555; font-size: .85rem; margin: -.2rem 0 1rem;}
.cx-legal {color: #999; font-size: .78rem; text-align: center; margin-top: 1.6rem;}
button[data-testid^="stBaseButton-primary"], button[data-testid^="stBaseButton-primary"] p {
  background: #FF7900 !important; border-color: #FF7900 !important; color: #000 !important; font-weight: 700;}
button[data-testid^="stBaseButton-primary"]:hover, button[data-testid^="stBaseButton-primary"]:hover p {
  background: #000 !important; border-color: #000 !important; color: #fff !important;}
@media (max-width: 760px) {.cx-panneau {display: none;}}
</style>"""

PROFILS = {":material/badge: DRH": "drh", ":material/apartment: Direction générale": "direction"}


def identifiant_du_role(role):
    """Premier compte configuré pour ce rôle (les identifiants peuvent différer selon les secrets)."""
    return next((ident for ident, c in comptes().items() if c.get("role") == role), None)


def page_connexion():
    st.markdown(CSS_CONNEXION, unsafe_allow_html=True)
    gauche, _, droite = st.columns([1.15, .12, .85], vertical_alignment="center")
    with gauche:
        st.markdown("""<div class='cx-panneau'>
<div class='cx-marque'><b>TelcomCI</b> HR Analytics</div>
<div class='cx-contenu'><div class='cx-pastille'>Direction des Ressources Humaines</div>
<div class='cx-accroche'>Pilotez vos effectifs.<br><span>Anticipez les départs.</span></div>
<div class='cx-sous'>Effectifs, masse salariale, absentéisme, performance et turnover réunis dans un seul tableau de bord, mis à jour chaque semestre.</div>
<div class='cx-chiffres'><div><div class='cx-v'>1 507</div><div class='cx-l'>collaborateurs</div></div>
<div><div class='cx-v'>10</div><div class='cx-l'>départements</div></div>
<div><div class='cx-v'>17</div><div class='cx-l'>analyses</div></div></div></div>
<div class='cx-pied'>Données au 31/12/2024 · Projet MDSBDIA · INP-HB Yamoussoukro</div></div>""", unsafe_allow_html=True)
    with droite:
        st.markdown("<div class='cx-titre'>Connexion</div><div class='cx-st'>Accès réservé · choisissez votre profil</div>",
                    unsafe_allow_html=True)
        if st.session_state.pop("session_expiree", False):
            st.info("Votre session a expiré. Merci de vous reconnecter.")
        if not comptes():
            st.error("Aucun compte n'est configuré. Ajoutez la section [comptes] dans les secrets de l'application "
                     "(voir dashboard/README.md).")
            return
        choix = st.segmented_control("Profil", list(PROFILS), default=list(PROFILS)[0], key="profil_connexion",
                                     label_visibility="collapsed", width="stretch") or list(PROFILS)[0]
        role = PROFILS[choix]
        st.markdown(f"<div class='cx-droits'><b>{ROLES[role]['libelle']}</b> · {ROLES[role]['description']}</div>",
                    unsafe_allow_html=True)
        bloque_jusqua = st.session_state.get("bloque_jusqua", 0)
        with st.form("connexion", border=False):
            mdp = st.text_input("Mot de passe", type="password", placeholder="Votre mot de passe",
                                autocomplete="current-password")
            envoye = st.form_submit_button("Se connecter", type="primary", icon=":material/login:", width="stretch")
        if envoye:
            if time.time() < bloque_jusqua:
                st.error(f"Trop de tentatives. Réessayez dans {int(bloque_jusqua - time.time())} secondes.")
            else:
                with st.spinner("Connexion…"):
                    ident = identifiant_du_role(role)
                    u = verifier(ident, mdp) if ident else None
                if u:
                    st.session_state.pop("essais", None)
                    st.session_state["utilisateur"] = u
                    st.rerun()
                essais = st.session_state.get("essais", 0) + 1
                st.session_state["essais"] = essais
                if essais >= ESSAIS_MAX:
                    st.session_state["bloque_jusqua"] = time.time() + BLOCAGE
                    st.session_state["essais"] = 0
                    st.error(f"Trop de tentatives. Connexion bloquée pendant {BLOCAGE} secondes.")
                else:
                    st.error("Mot de passe incorrect.")
        st.markdown(f"<div class='cx-legal'>Session de {DUREE_SESSION // 3600} h · {ESSAIS_MAX} tentatives maximum</div>",
                    unsafe_allow_html=True)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage : python dashboard/auth.py <mot_de_passe>")
    sel = secrets.token_hex(16)
    print(f'sel = "{sel}"\nempreinte = "{empreinte(sys.argv[1], sel)}"')
