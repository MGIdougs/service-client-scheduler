import streamlit as st
import pandas as pd
import json
from ortools.sat.python import cp_model
from streamlit_local_storage import LocalStorage
from typing import Dict, Any, Optional

# Initialiser le module de stockage local
local_storage = LocalStorage()

# Clé pour le stockage des employés
EMPLOYEES_KEY = "employees"

# Fonction pour sauvegarder dans localStorage et session_state
def save_to_local_storage(key: str, value: Any) -> None:
    """Sauvegarde les données dans localStorage et session_state"""
    # Sauvegarder dans session_state
    st.session_state[key] = value
    
    # Sauvegarder dans localStorage aussi
    local_storage.setItem(key, value)

# Fonction pour initialiser les données
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




st.title("🎈 Charlotte's Super Scheduler")
st.write(
    "Le planning du service client !"
)

st.text_input("Quel prénom ?", key="name", placeholder="Charlotte")
option = st.selectbox(
    'Quel équipe ?',
    ["Client", "Facturation"])
person_name = option+st.session_state.name
if st.session_state.name:
    st.write(f"Nom d'affichage: {person_name}")

model = cp_model.CpModel()

# Dict pour les rôles de chaque équipe:
role_dict = {"Client": ["Téléphone", "IC_Client", "Slack/tâches"],
             "Facturation": ["Téléphone", "IC_Factu", "Slack/tâches"]}

# Initialiser les données si ce n'est pas déjà fait
# Si aucune donnée n'est présente dans st.session_state, utiliser un dictionnaire vide par défaut
employees = initialize_data({})

left, right = st.columns(2)

if left.button("Ajouter le collaborateur", icon="➕", use_container_width=True):
    if st.session_state.name:
        left.markdown(f"{st.session_state.name} ({option}) ajouté !")
        employees[person_name] = role_dict[option]
        # Save to localStorage instead of JSON file
        st.session_state['employees'] = employees
        save_to_local_storage('employees', employees)
    else:
        left.markdown(f"Il faut donner un nom au collaborateur !")
if right.button("Enlever le collaborateur", icon="➖", use_container_width=True):
    if person_name in employees:
        employees.pop(person_name)
        right.markdown(f"{st.session_state.name} ({option}) enlevé !")
        # Save updated employees to localStorage
        st.session_state['employees'] = employees
        save_to_local_storage('employees', employees)
    else:
        right.markdown(
            f"{st.session_state.name} ({option}) n'est pas dans la liste !")

st.write("Liste des employés: ")
if employees:
    # Créer un DataFrame seulement si le dictionnaire n'est pas vide
    employees_df = pd.DataFrame([{"Employee": k, "Roles": employees[k]} 
                               for k in employees]).set_index("Employee", drop=True)
    st.write(employees_df)
else:
    st.info("Aucun employé n'a été ajouté. Utilisez le formulaire ci-dessus pour ajouter des employés ou importez des données.")

# Les horaires sont de 8h30 à 18h le lundi, mardi, mercredi et jeudi ; 8h30 à 17h le vendredi.
days = ["Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday"]

# Le planning fonctionne avec des créneaux de 30 minutes.
shifts = [f"{t//60:02}:{t%60:02}" for t in range(510, 1080, 30)]
roles = set(role_dict["Client"] + role_dict["Facturation"])

schedule = {e:
            {r:
             {d:
              {s: model.new_bool_var(f"schedule_{e}_{r}_{d}_{s}")
               for s in shifts}
              for d in days}
             for r in roles}
            for e in employees}

# Les contraintes !

# Les heures non travaillées dans la journée sont
# - tous les jours entre 12h30 et 13h30
# - le lundi entre 12h et 12h30
# - le mercredi de 17h à 18h
# - le jeudi de 12h à 12h30.
st.write("Liste des contraintes:")
for e in employees:
    for r in roles:
        for d in days:
            for s in shifts:
                if s in ["12:30", "13:00"]:
                    model.add(schedule[e][r][d][s] == 0)
                if d in ["Monday", "Thursday"] and s == ["12:00"]:
                    model.add(schedule[e][r][d][s] == 0)
                if d == "Wednesday" and s in ["17:00", "17:30"]:
                    model.add(schedule[e][r][d][s] == 0)
                if d == "Friday" and s in ["17:00", "17:30"]:
                    model.add(schedule[e][r][d][s] == 0)

# Les employés ne peuvent pas faire un rôle qu'on ne leur a pas attribué:
for e in employees:
    for r in roles:
        for d in days:
            for s in shifts:
                if r not in employees[e]:
                    model.add(schedule[e][r][d][s] == 0)

# Les employés ne peuvent pas faire deux rôles en même temps
for e in employees:
    for d in days:
        for s in shifts:
            model.add(sum(schedule[e][r][d][s] for r in roles) <= 1)


def get_shifts_for_day(d):
    day_shifts = [s for s in shifts if s not in ["12:30", "13:00"]]
    if d in ["Wednesday", "Friday"]:
        day_shifts = day_shifts[:-2]
    elif d in ["Monday", "Thursday"]:
        day_shifts = [s for s in day_shifts if s != "12:00"]
    return day_shifts

# Il doit toujours y avoir 4 personnes (les 2 squads confondues)
# au téléphone entre 9h et 12h et entre 14h et 18h
# (sauf le mercredi et le vendredi : jusqu'à 17h)
# Le vendredi : 5 personnes au téléphone


if st.checkbox("Il doit toujours y avoir 4 personnes au téléphone aux heures d'ouverture du standard", value=True):
    for d in days:
        for s in get_shifts_for_day(d):
            if s in ['09:00', '09:30', '10:00', '10:30', '11:00', '11:30']:
                model.add(sum(schedule[e]["Téléphone"][d][s]
                          for e in employees) == 4)
            elif s in ['14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00', '17:30']:
                if d != "Friday":
                    model.add(sum(schedule[e]["Téléphone"][d][s]
                              for e in employees) == 4)
                elif s in ['15:30', '16:00', '16:30', '17:00', '17:30']:
                    model.add(sum(schedule[e]["Téléphone"][d][s]
                              for e in employees) == 5)
                else:
                    model.add(sum(schedule[e]["Téléphone"][d][s]
                              for e in employees) == 4)
            elif s in ['13:30', '08:30']:
                model.add(sum(schedule[e]["Téléphone"][d][s]
                          for e in employees) == 0)

# Dans chaque squad, il doit toujours y avoir quelqu'un sur Intercom 
if st.checkbox("Dans chaque squad, il doit toujours y avoir quelqu'un sur Intercom", value=True):
    for d in days:
        day_shifts = get_shifts_for_day(d)
        # print(d, day_shift)
        for s in day_shifts:
            model.add(sum(schedule[e]["IC_Client"][d][s]
                      for e in employees if "Client" in e) == 1)
            model.add(sum(schedule[e]["IC_Factu"][d][s]
                      for e in employees if "Facturation" in e) == 1)


# Pour chaque squad, il doit toujours y avoir maximum 1 personne sur Slack/tâches.
if st.checkbox("Pour chaque squad, il doit toujours y avoir maximum 1 personne sur slack", value=True):
    for d in days:
        day_shifts = get_shifts_for_day(d)
        # print(d, day_shift)
        for s in day_shifts:
            model.add(sum(schedule[e]["Slack/tâches"][d][s] 
                          for e in employees
                          if 'Facturation' in e) <= 1)
            model.add(sum(schedule[e]["Slack/tâches"][d][s] 
                          for e in employees
                          if 'Client' in e) <= 1)
            
# Pour chaque squad, chaque personne doit avoir au moins 1 créneau Slack/tâches
has_Slack_tasks = {}
if st.checkbox("Pour chaque squad, chaque personne doit avoir au moins 1 créneau Slack/tâches", value=True):
    for e in employees:
        for d in days:
            day_shifts = get_shifts_for_day(d)
            has_Slack_tasks[e] = {
                d: {}
            }
            for s in day_shifts:
                has_Slack_tasks[e][d][s] = schedule[e]["Slack/tâches"][d][s]
                # La contrainte principale : chaque personne doit avoir au moins 1 créneau Slack/tâches
            model.add(
                sum(has_Slack_tasks[e][d][s] for s in day_shifts) > 0
            )
        

# Chaque personne doit avoir une demi-journée sans téléphone par semaine.
# Cette demi-journée ne peut pas être le vendredi après-midi.

# Demi-journée sans téléphone (matin : avant 12h00, après-midi : après 12h00)
morning_shifts = [s for s in shifts if s in ['09:00', '09:30', '10:00',
                                             '10:30', '11:00', '11:30']]
afternoon_shifts = [s for s in shifts if s in ['13:30', '14:00', '14:30',
                                               '15:00', '15:30', '16:00',
                                               '16:30', '17:00', '17:30']]
has_morning_without_phone = {}
has_afternoon_without_phone = {}
if nophone := st.checkbox("Chaque personne doit avoir une demi-journée sans téléphone par semaine. Cette demi-journée ne peut pas être le vendredi après-midi.", value=True):

    # Itération sur chaque employé et chaque jour sauf vendredi après-midi

    for e in employees:
        # Une variable booléenne pour indiquer si une demi-journée sans téléphone est respectée
        has_morning_without_phone[e] = {
            d:  model.new_bool_var(f"morning_without_phone_{e}_{d}") for d in days
        }
        has_afternoon_without_phone[e] = {
            d: model.new_bool_var(f"afternoon_without_phone_{e}_{d}") for d in days
        }
        for d in days:
            # Contraintes pour le matin : aucune plage horaire avec téléphone
            model.add(
                sum(schedule[e]["Téléphone"][d][s]
                    for s in get_shifts_for_day(d) if s in morning_shifts) == 0
            ).only_enforce_if(has_morning_without_phone[e][d])
            model.add(
                sum(schedule[e]["Téléphone"][d][s]
                    for s in get_shifts_for_day(d) if s in morning_shifts) >= 1
            ).only_enforce_if(~has_morning_without_phone[e][d])

            # Contraintes pour l'après-midi : aucune plage horaire avec téléphone, sauf vendredi
            if d != "Friday":
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in get_shifts_for_day(d) if s in afternoon_shifts) == 0
                ).only_enforce_if(has_afternoon_without_phone[e][d])
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in get_shifts_for_day(d) if s in afternoon_shifts) >= 1
                ).only_enforce_if(~has_afternoon_without_phone[e][d])

        # La contrainte principale : chaque personne doit avoir au moins une demi-journée sans téléphone
        model.add(
            sum(has_morning_without_phone[e][d] for d in days) +
            sum(has_afternoon_without_phone[e][d]
                for d in days if d != "Friday") >= 1
        )

# Pour chaque squad, il doit y avoir au moins 2 créneaux Slack/tâches par demi-journée.
if st.checkbox("Pour chaque squad, il doit y avoir au moins 2 créneaux Slack/tâches par demi-journée", value=True):
    for d in days:

        model.add(sum(
            schedule[e]["Slack/tâches"][d][morning_shift] 
            for e in employees 
            if 'Facturation' in e
            for morning_shift in morning_shifts
        ) >= 4)
        
        model.add(sum(
            schedule[e]["Slack/tâches"][d][morning_shift] 
            for e in employees 
            if 'Client' in e
            for morning_shift in morning_shifts
        ) >= 4)



        model.add(sum(
            schedule[e]["Slack/tâches"][d][afternoon_shift] 
            for e in employees 
            if 'Facturation' in e
            for afternoon_shift in afternoon_shifts
        ) >= 4)

        model.add(sum(
            schedule[e]["Slack/tâches"][d][afternoon_shift] 
            for e in employees 
            if 'Client' in e
            for afternoon_shift in afternoon_shifts
        ) >= 4)



if st.checkbox("Dans chaque squad, chaque personne doit passer à peu près le même temps au téléphone, sur Intercom, sur Slack/tâches et sur les tâches.", value=True):

    max_nb_shifts = 100
    # il faut prendre en compte les équipes !
    total_shifts = {}
    min_shifts = {}
    max_shifts = {}
    for team in ["Facturation", "Client"]:
        for r in [r for r in role_dict[team]]:
            # print(team,r)
            # print(r not in total_shifts)
            if r not in total_shifts:
                total_shifts[r] = {}
            for e in [c for c in employees if team in c]:
                # print(team,r,e)
                total_shifts[r][e] = model.new_int_var(
                    0, max_nb_shifts, f"total_shifts_c_{e}_{r}")
                # pprint(total_shifts)
                model.add(total_shifts[r][e] == sum(schedule[e][r][d][s]
                          for d in days for s in get_shifts_for_day(d)))
            min_shifts[r] = model.new_int_var(
                0, max_nb_shifts, f"min_shifts_c_{r}")
            model.add_min_equality(min_shifts[r], [total_shifts[r][e] for e in [
                                   c for c in employees if team in c]])
            max_shifts[r] = model.new_int_var(
                0, max_nb_shifts, f"max_shifts_c_{r}")
            model.add_max_equality(max_shifts[r], [total_shifts[r][e] for e in [
                                   c for c in employees if team in c]])
            model.add(max_shifts[r] - min_shifts[r] <= 2)


if st.checkbox("Pas + de 3 créneaux à la suite pour chaque rôle sauf Téléphone, maximum 4 créneaux.", value=True):
    continuous_shifts = {}
    for e in employees:
        continuous_shifts[e] = {}
        for d in days:
            continuous_shifts[e][d] = {}
            for r in roles:
                if r != "Téléphone":
                    continuous_shifts[e][d][r] = {}
                    for s_idx, s in enumerate([s for s in morning_shifts]):
                        if s_idx < 4:
                            model.add(
                                sum(schedule[e][r][d][s]
                                    for s in morning_shifts[s_idx:s_idx+4]) <= 2
                            )
                    for s_idx, s in enumerate([s for s in afternoon_shifts]):
                        if s_idx < 5:
                            model.add(
                                sum(schedule[e][r][d][s]
                                    for s in afternoon_shifts[s_idx:s_idx+5]) <= 4
                            )

if st.checkbox("Organisation du téléphone en 'créneaux' de 1h30 le matin / 2h l'après-midi.", value=nophone, disabled=not nophone):
    has_morning_early_phone = {}
    early_morning_shifts = ["09:00", "09:30", "10:00"]
    late_morning_shifts = ["10:30", "11:00", "11:30"]
    early_afternoon_shifts_redux = ["14:00", "14:30", "15:00"]
    late_afternoon_shifts_redux = ["15:30", "16:00", "16:30"]
    early_afternoon_shifts = ["14:00", "14:30", "15:00", "15:30"]
    late_afternoon_shifts = ["16:00", "16:30", "17:00", "17:30"]
    for e in employees:
        has_morning_early_phone[e] = {
            d:  model.new_bool_var(f"morning_early_phone_{e}_{d}") for d in days
        }
        for d in days:
            model.add(
                sum(schedule[e]["Téléphone"][d][s]
                    for s in early_morning_shifts) == 3
            ).only_enforce_if(has_morning_early_phone[e][d]).only_enforce_if(~has_morning_without_phone[e][d])
            model.add(
                sum(schedule[e]["Téléphone"][d][s]
                    for s in early_morning_shifts) == 0
            ).only_enforce_if(~has_morning_early_phone[e][d])
            model.add(
                sum(schedule[e]["Téléphone"][d][s]
                    for s in late_morning_shifts) == 3
            ).only_enforce_if(~has_morning_early_phone[e][d]).only_enforce_if(~has_morning_without_phone[e][d])
            model.add(
                sum(schedule[e]["Téléphone"][d][s]
                    for s in late_morning_shifts) == 0
            ).only_enforce_if(has_morning_early_phone[e][d])
            if d in ["Monday", "Tuesday", "Thursday"]:
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in early_afternoon_shifts) == 4
                ).only_enforce_if(has_morning_early_phone[e][d]).only_enforce_if(~has_afternoon_without_phone[e][d])
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in early_afternoon_shifts) == 0
                ).only_enforce_if(~has_morning_early_phone[e][d])
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in late_afternoon_shifts) == 4
                ).only_enforce_if(~has_morning_early_phone[e][d]).only_enforce_if(~has_afternoon_without_phone[e][d])
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in late_afternoon_shifts) == 0
                ).only_enforce_if(has_morning_early_phone[e][d])
            elif d == "Wednesday":
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in early_afternoon_shifts_redux) == 3
                ).only_enforce_if(has_morning_early_phone[e][d]).only_enforce_if(~has_afternoon_without_phone[e][d])
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in early_afternoon_shifts_redux) == 0
                ).only_enforce_if(~has_morning_early_phone[e][d])
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in late_afternoon_shifts_redux) == 3
                ).only_enforce_if(~has_morning_early_phone[e][d]).only_enforce_if(~has_afternoon_without_phone[e][d])
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in late_afternoon_shifts_redux) == 0
                ).only_enforce_if(has_morning_early_phone[e][d])
            elif d == "Friday":
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in early_afternoon_shifts_redux) == 3
                ).only_enforce_if(has_morning_early_phone[e][d]).only_enforce_if(~has_afternoon_without_phone[e][d])
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in early_afternoon_shifts_redux) == 0
                ).only_enforce_if(~has_morning_early_phone[e][d])
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in late_afternoon_shifts_redux) == 3
                ).only_enforce_if(~has_morning_early_phone[e][d]).only_enforce_if(~has_afternoon_without_phone[e][d])
                model.add(
                    sum(schedule[e]["Téléphone"][d][s]
                        for s in late_afternoon_shifts_redux) == 0
                ).only_enforce_if(has_morning_early_phone[e][d])


solver = cp_model.CpSolver()
solver.solve(model)
status = solver.solve(model)
print(status)
if status == 4:
    st.write("Emploi du temps généré !")
    data_list = []
    for e in employees:
        for d in days:
            for s in shifts:
                role = "📞" if solver.value(schedule[e]["Téléphone"][d][s]) == 1 else "✉️" if (solver.value(schedule[e]["IC_Client"][d][s]) == 1 or solver.value(
                    schedule[e]["IC_Factu"][d][s]) == 1) else "🙋/✅" if solver.value(schedule[e]["Slack/tâches"][d][s]) == 1 else "✅" if s in get_shifts_for_day(d) else None
                data_list.append(
                    {"employee": e, "day": d, "shift": s, "role": role})
    schedule_df = pd.DataFrame(data_list).sort_values(by=["day", "employee"])
    schedule_dict = {}
    for day, day_df in schedule_df.groupby(by="day"):
        shifts_list = []
        for e, employee_df in day_df.groupby(by="employee"):
            day_shifts = employee_df["shift"]
            shift_role = employee_df["role"]
            shifts_dict = {"employee": e}
            for i in range(len(day_shifts)):
                shifts_dict[day_shifts.iloc[i]] = shift_role.iloc[i]
            shifts_list.append(shifts_dict)
        schedule_dict[day] = pd.DataFrame(shifts_list)

    st.write("Planning global :")
    pivot_data = schedule_df.pivot_table(
        index=['day', 'shift'],
        columns='employee',
        values='role',
        aggfunc='first'
    ).reset_index()
    custom_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    pivot_data['day'] = pd.Categorical(
        pivot_data['day'], categories=custom_order, ordered=True)
    pivot_data = pivot_data.sort_values(by=['day', 'shift'])
    st.write(pivot_data)

    st.write("Planning par jour:")
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
        st.write(day)
        st.write(schedule_dict[day])

    count_dict_list = []
    for employee, employee_df in schedule_df.groupby(by="employee"):
        shift_counts = employee_df["role"].value_counts()
        count_dict = {"employee": employee}
        for role, role_count in zip(shift_counts.index, shift_counts.values):
            count_dict[role] = role_count
        count_dict_list.append(count_dict)
    count_df = pd.DataFrame(count_dict_list)
    st.write("Compte total:")
    st.write(count_df)

else:
    st.write("Pas d'emploi du temps respectant les contraintes 😥")
