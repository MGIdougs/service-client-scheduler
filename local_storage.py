import streamlit as st
import json
import io
from typing import Dict, Any, Optional

# Clé pour le stockage des employés dans session_state de Streamlit
EMPLOYEES_KEY = "employees"

# Fonction pour afficher l'interface d'import/export des données
def load_from_local_storage():
    """Affiche des boutons pour importer/exporter les données"""
    with st.expander("Gérer vos données (Importer / Exporter)", expanded=True):
        # Interface plus directe et plus visible
        col1, col2 = st.columns(2)
        
        # Gestion de l'EXPORT
        with col1:
            st.subheader("Exporter les données")
            if EMPLOYEES_KEY in st.session_state and st.session_state[EMPLOYEES_KEY]:
                employees_json = json.dumps(st.session_state[EMPLOYEES_KEY], indent=2)
                st.download_button(
                    label="Télécharger en JSON",
                    data=employees_json,
                    file_name="employees_data.json",
                    mime="application/json",
                    use_container_width=True,
                    key="download_btn"
                )
                st.caption(f"{len(st.session_state[EMPLOYEES_KEY])} collaborateurs disponibles pour export")
            else:
                st.warning("Aucune donnée à exporter", icon="⚠️")
        
        # Gestion de l'IMPORT
        with col2:
            st.subheader("Importer des données")
            uploaded_file = st.file_uploader(
                "Sélectionnez votre fichier JSON", 
                type="json", 
                key="uploader",
                help="Format attendu: fichier JSON contenant les collaborateurs et leurs rôles"
            )
            
            if uploaded_file is not None:
                # Bouton pour confirmer l'import
                if st.button("Confirmer l'import", key="confirm_import", type="primary", use_container_width=True):
                    try:
                        # Réinitialiser le curseur de lecture
                        uploaded_file.seek(0)
                        
                        # Lire et parser le contenu JSON
                        employees_data = json.load(uploaded_file)
                        
                        # Vérifier que le format est correct
                        if not isinstance(employees_data, dict):
                            st.error("Format invalide: les données doivent être un dictionnaire de collaborateurs", icon="❌")
                            return
                            
                        # Sauvegarder explicitement dans session_state
                        st.session_state[EMPLOYEES_KEY] = employees_data
                        
                        # Message de succès
                        st.success(f"Import réussi : {len(employees_data)} collaborateurs chargés.", icon="✅")
                        
                        # Forcer le rechargement
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors de l'import : {e}", icon="❌")

# Fonction pour sauvegarder les données dans session_state
def save_to_local_storage(key: str, value: Any) -> None:
    """Sauvegarde les données dans session_state"""
    # Sauvegarder simplement dans session_state
    st.session_state[key] = value

# Fonction pour vider la session
def clear_local_storage(key: Optional[str] = None) -> None:
    """Vide les données en session"""
    if key:
        # Supprimer uniquement la clé spécifiée
        if key in st.session_state:
            del st.session_state[key]
    else:
        # Réinitialiser toutes les données de session
        for k in list(st.session_state.keys()):
            if k != "_":
                del st.session_state[k]

# Fonction pour initialiser les données
def initialize_data(initial_data: Optional[Dict] = None) -> Dict:
    """Initialise les données depuis session_state ou avec les données initiales"""
    # Si déjà initialisé dans cette session
    if EMPLOYEES_KEY in st.session_state:
        return st.session_state[EMPLOYEES_KEY]
    
    # Sinon, utiliser les données initiales
    st.session_state[EMPLOYEES_KEY] = initial_data or {}
    return st.session_state[EMPLOYEES_KEY]
