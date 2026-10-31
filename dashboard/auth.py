"""Connexion simple par mot de passe, avec deux rôles de démonstration.

Les comptes sont lus dans les secrets Streamlit (jamais dans le dépôt) :

    [comptes.drh]
    role = "drh"
    nom = "Direction des Ressources Humaines"
    sel = "…"
    empreinte = "…"        # PBKDF2-SHA256(mot de passe, sel)

Générer une empreinte :  python dashboard/auth.py <mot_de_passe>
"""
import hashlib
import hmac
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


def comptes():
    try:
        return {k: dict(v) for k, v in st.secrets["comptes"].items()}
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


def page_connexion():
    gauche, centre, droite = st.columns([1, 1.25, 1])
    with centre:
        st.markdown("<div style='height:6vh'></div>", unsafe_allow_html=True)
        st.markdown("<div class='titre-page'><span>TelcoPeople</span>HR Analytics</div>", unsafe_allow_html=True)
        st.markdown("<div class='note' style='margin:.4rem 0 1rem'>Tableau de bord de pilotage RH · accès réservé</div>",
                    unsafe_allow_html=True)
        if st.session_state.pop("session_expiree", False):
            st.info("Votre session a expiré. Merci de vous reconnecter.")
        if not comptes():
            st.error("Aucun compte n'est configuré. Ajoutez la section [comptes] dans les secrets de l'application "
                     "(voir dashboard/README.md).")
            return
        bloque_jusqua = st.session_state.get("bloque_jusqua", 0)
        with st.form("connexion", border=True):
            ident = st.text_input("Identifiant", autocomplete="username")
            mdp = st.text_input("Mot de passe", type="password", autocomplete="current-password")
            envoye = st.form_submit_button("Se connecter", type="primary", width="stretch")
        if envoye:
            if time.time() < bloque_jusqua:
                st.error(f"Trop de tentatives. Réessayez dans {int(bloque_jusqua - time.time())} secondes.")
            else:
                u = verifier(ident, mdp)
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
                    st.error("Identifiant ou mot de passe incorrect.")
        st.markdown("<div class='note' style='margin-top:.8rem'>Deux profils de démonstration : <b>DRH</b> "
                    "(accès aux données individuelles) et <b>Direction générale</b> (indicateurs agrégés).</div>",
                    unsafe_allow_html=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage : python dashboard/auth.py <mot_de_passe>")
    sel = secrets.token_hex(16)
    print(f'sel = "{sel}"\nempreinte = "{empreinte(sys.argv[1], sel)}"')
