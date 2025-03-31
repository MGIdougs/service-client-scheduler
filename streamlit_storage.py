import streamlit as st
import json
from typing import Dict, Any, Optional
from streamlit_local_storage import LocalStorage

# Clé pour le stockage des employés
EMPLOYEES_KEY = "employees"

# Initialiser le localStorage
local_storage = LocalStorage()

def load_from_local_storage():
    """Affiche l'interface pour charger, exporter et importer les données"""
    with st.expander("Gestion des données", expanded=True):
        # Affichage d'une information sur la persistance des données
        st.info("📝 Les données sont stockées dans votre navigateur et persistent entre les sessions.")
        
        # Créer une mise en page à trois colonnes
        col1, col2, col3 = st.columns(3)
        
        # Charger depuis localStorage
        with col1:
            st.subheader("🔄 Charger")
            if st.button("Charger du navigateur", use_container_width=True, key="load_btn"):
                # Tenter de récupérer les données du localStorage
                employees_data = local_storage.getItem(EMPLOYEES_KEY)
                
                if employees_data:
                    # Convertir la chaîne JSON en objet Python si nécessaire
                    if isinstance(employees_data, str):
                        employees_data = json.loads(employees_data)
                    
                    # Mettre à jour session_state
                    st.session_state[EMPLOYEES_KEY] = employees_data
                    st.success(f"Données chargées : {len(employees_data)} collaborateurs", icon="✅")
                    st.rerun()
                else:
                    st.warning("Aucune donnée trouvée dans le navigateur", icon="⚠️")
        
        # Export vers JSON
        with col2:
            st.subheader("💾 Exporter")
            if EMPLOYEES_KEY in st.session_state and st.session_state[EMPLOYEES_KEY]:
                employees_json = json.dumps(st.session_state[EMPLOYEES_KEY], indent=2)
                st.download_button(
                    label=f"Télécharger ({len(st.session_state[EMPLOYEES_KEY])} collaborateurs)",
                    data=employees_json,
                    file_name="employees_data.json",
                    mime="application/json",
                    use_container_width=True,
                    key="download_btn"
                )
                st.caption("Fichier JSON pour sauvegarde externe")
            else:
                st.info("Aucune donnée à exporter")
        
        # Import depuis JSON
        with col3:
            st.subheader("📁 Importer")
            uploaded_file = st.file_uploader(
                "Fichier JSON", 
                type="json", 
                key="uploader",
                help="Format: JSON avec dictionnaire de collaborateurs"
            )
            
            if uploaded_file is not None:
                # Créer un aperçu du contenu du fichier
                try:
                    # Lire le fichier
                    uploaded_file.seek(0)
                    preview_data = json.load(uploaded_file)
                    nb_employes = len(preview_data) if isinstance(preview_data, dict) else 0
                    uploaded_file.seek(0)  # Réinitialiser pour lecture future
                    
                    # Afficher un aperçu
                    st.caption(f"Fichier prêt : {nb_employes} collaborateurs")
                    
                    # Bouton pour confirmer l'import
                    if st.button("Confirmer l'import", key="confirm_import", type="primary", use_container_width=True):
                        try:
                            # Réinitialiser la position du curseur
                            uploaded_file.seek(0)
                            
                            # Charger le contenu
                            employees_data = json.load(uploaded_file)
                            
                            # Vérifier le format
                            if not isinstance(employees_data, dict):
                                st.error("Format invalide", icon="❌")
                                return
                            
                            # Mettre à jour session_state
                            st.session_state[EMPLOYEES_KEY] = employees_data
                            
                            # Mettre à jour localStorage aussi
                            local_storage.setItem(EMPLOYEES_KEY, employees_data)
                            
                            # Message de succès
                            st.success(f"Import réussi : {len(employees_data)} collaborateurs", icon="✅")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}", icon="❌")
                except Exception as e:
                    st.warning(f"Erreur de lecture : {str(e)}")

def save_to_local_storage(key: str, value: Any) -> None:
    """Sauvegarde les données dans localStorage et session_state"""
    # Sauvegarder dans session_state
    st.session_state[key] = value
    
    # Sauvegarder dans localStorage aussi
    local_storage.setItem(key, value)

def clear_local_storage(key: Optional[str] = None) -> None:
    """Vide les données du localStorage et de session_state"""
    if key:
        # Supprimer uniquement la clé spécifiée
        if key in st.session_state:
            del st.session_state[key]
        local_storage.removeItem(key)
    else:
        # Réinitialiser toutes les données
        for k in list(st.session_state.keys()):
            if k != "_":
                del st.session_state[k]
        local_storage.clear()

def initialize_data(initial_data: Optional[Dict] = None) -> Dict:
    """Initialise les données depuis localStorage ou session_state, ou utilise les données par défaut"""
    # Vérifier si les données sont dans session_state
    if EMPLOYEES_KEY in st.session_state and st.session_state[EMPLOYEES_KEY]:
        return st.session_state[EMPLOYEES_KEY]
    
    # Si non, essayer de récupérer depuis localStorage
    employees_data = local_storage.getItem(EMPLOYEES_KEY)
    
    if employees_data:
        # Convertir la chaîne JSON en objet Python si nécessaire
        if isinstance(employees_data, str):
            employees_data = json.loads(employees_data)
        
        # Mettre dans session_state et retourner
        st.session_state[EMPLOYEES_KEY] = employees_data
        return employees_data
    
    # Si toujours rien, utiliser les données initiales
    st.session_state[EMPLOYEES_KEY] = initial_data or {}
    return st.session_state[EMPLOYEES_KEY]
