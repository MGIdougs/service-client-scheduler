import streamlit as st
import pandas as pd
import json
from ortools.sat.python import cp_model


st.title("🎈 Charlotte's Super Scheduler")
st.write(
    "Let's start building! For help and inspiration, head over to [docs.streamlit.io](https://docs.streamlit.io/)."
)

st.text_input("Quel prénom ?", key="name", placeholder="Charlotte")
option = st.selectbox(
    'Quel équipe ?',
     ["Client","Facturation"])
person_name = option+st.session_state.name
if st.session_state.name:
    st.write(f"Nom d'affichage: {person_name}")

model = cp_model.CpModel()

# Dict pour les rôles de chaque équipe:
role_dict = {"Client":["Téléphone","IC","Una"],
             "Facturation":["Téléphone","IC","Slack"]}

with open("employees.json","r") as employee_file:
  employees = json.load(employee_file)

left, right = st.columns(2)

if left.button("Ajouter le collaborateur", icon="➕", use_container_width=True):
    if st.session_state.name:
      left.markdown(f"{st.session_state.name} ({option}) ajouté !")
      employees[person_name] = role_dict[option]
      with open("employees.json","w") as employee_file:
        json.dump(employees, employee_file)
    else:
      left.markdown(f"Il faut donner un nom au collaborateur !")
if right.button("Enlever le collaborateur", icon="➖", use_container_width=True):
  with open("employees.json","r") as employee_file:
    employees = json.load(employee_file)   
  if person_name in employees:
    employees.pop(person_name)
    right.markdown(f"{st.session_state.name} ({option}) enlevé !")
  else:
    right.markdown(f"{st.session_state.name} ({option}) n'est pas dans la liste !")
  with open("employees.json","w") as employee_file:
    json.dump(employees, employee_file)

employees_df=pd.DataFrame([{"Employee":k,"Roles":employees[k]} for k in employees]).set_index("Employee",drop=True)
st.write("Liste des employés: ")
employees_df

#Les horaires sont de 8h30 à 18h le lundi, mardi, mercredi et jeudi ; 8h30 à 17h le vendredi.
days = ["Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday"]

#Le planning fonctionne avec des créneaux de 30 minutes.
shifts = [f"{t//60:02}:{t%60:02}" for t in range(510,1080,30)]
roles = ["Téléphone","IC","Slack","Una"]

schedule = {e:
             {r:
               {d:
                 {s: model.new_bool_var(f"schedule_{e}_{r}_{d}_{s}")
                   for s in shifts}
                 for d in days}
               for r in roles}
             for e in employees}

## Les contraintes !

# Les heures non travaillées dans la journée sont
# - tous les jours entre 12h30 et 13h30
# - le lundi entre 12h et 12h30
# - le mercredi de 17h à 18h
# - le jeudi de 12h à 12h30.

for e in employees:
    for r in roles:
        for d in days:
            for s in shifts:
                if s in ["12:30","13:00"]:
                    model.add(schedule[e][r][d][s] == 0)
                if d in ["Monday","Thursday"] and s==["12:00"]:
                    model.add(schedule[e][r][d][s] == 0)
                if d == "Wednesday" and s in ["17:00","17:30"]:
                    model.add(schedule[e][r][d][s] == 0)
                if d == "Friday" and s in ["17:00","17:30"]:
                    model.add(schedule[e][r][d][s] == 0)

## Les employés ne peuvent pas faire un rôle qu'on ne leur a pas attribué:
for e in employees:
    for r in roles:
        for d in days:
            for s in shifts:
                if r not in employees[e]:
                    model.add(schedule[e][r][d][s] == 0)

## Les employés ne peuvent pas faire deux rôles en même temps
for e in employees:
    for d in days:
        for s in shifts:
            model.add(sum(schedule[e][r][d][s] for r in roles) <= 1)

def get_shifts_for_day(d):
  day_shifts = [s for s in shifts if s not in ["12:30","13:00"]]
  if d in ["Wednesday","Friday"]:
    day_shifts = day_shifts[:-2]
  elif d in ["Monday","Thursday"]:
    day_shifts =  [s for s in day_shifts if s != "12:00"]
  return day_shifts

# Il doit toujours y avoir 4 personnes (les 2 squads confondues)
# au téléphone entre 9h et 12h et entre 14h et 18h
# (sauf le mercredi et le vendredi : jusqu'à 17h)
# Le vendredi : 5 personnes au téléphone

for d in days:
  for s in get_shifts_for_day(d):
    if s in ['09:00', '09:30', '10:00', '10:30', '11:00','11:30']:
      model.add(sum(schedule[e]["Téléphone"][d][s] for e in employees) == 4)
    if s in ['14:00','14:30', '15:00', '15:30','16:00', '16:30', '17:00', '17:30'] :
      if d == "Friday":
        model.add(sum(schedule[e]["Téléphone"][d][s] for e in employees) == 5)
      else:
        model.add(sum(schedule[e]["Téléphone"][d][s] for e in employees) == 4)

# Dans chaque squad, il doit toujours y avoir quelqu'un sur Intercom et
# il doit toujours y avoir quelqu'un sur Slack.
# Il doit y avoir 3 service clients au Una le lundi matin.
for d in days:
  day_shifts = get_shifts_for_day(d)
  #print(d, day_shift)
  for s in day_shifts:
    model.add(sum(schedule[e]["Slack"][d][s] for e in employees) == 1)
    if d == "Monday" and s == "08:30":
      model.add(sum(schedule[e]["Una"][d][s] for e in employees) == 3)
    else:
      model.add(sum(schedule[e]["Una"][d][s] for e in employees) == 1)
    model.add(sum(schedule[e]["IC"][d][s] for e in employees if "Client" in e) == 1)
    model.add(sum(schedule[e]["IC"][d][s] for e in employees if "Facturation" in e) == 1)
# Chaque personne doit avoir une demi-journée sans téléphone par semaine.
# Cette demi-journée ne peut pas être le vendredi après-midi.

# Demi-journée sans téléphone (matin : avant 12h00, après-midi : après 12h00)
# Créons des ensembles de créneaux pour faciliter les calculs

morning_shifts = [s for s in shifts if s in ['09:00', '09:30', '10:00',
                                             '10:30', '11:00','11:30']]
afternoon_shifts = [s for s in shifts if s in ['13:30','14:00','14:30',
                                               '15:00', '15:30','16:00',
                                               '16:30', '17:00', '17:30']]

# Itération sur chaque employé et chaque jour sauf vendredi après-midi
has_morning_without_phone = {}
has_afternoon_without_phone = {}
for e in employees:
    # Une variable booléenne pour indiquer si une demi-journée sans téléphone est respectée
    has_morning_without_phone[e] = {
        d:  model.new_bool_var(f"morning_without_phone_{e}_{d}") for d in days
    }
    has_afternoon_without_phone[e] = {
        d: model.new_bool_var(f"afternoon_without_phone_{e}_{d}") for d in days if d != "Friday"
    }
    for d in days:
        # Contraintes pour le matin : aucune plage horaire avec téléphone
        model.add(
            sum(schedule[e]["Téléphone"][d][s] for s in  get_shifts_for_day(d) if s in morning_shifts) == 0
        ).only_enforce_if(has_morning_without_phone[e][d])
        model.add(
            sum(schedule[e]["Téléphone"][d][s] for s in  get_shifts_for_day(d) if s in morning_shifts) >= 1
        ).only_enforce_if(~has_morning_without_phone[e][d])

        #Contraintes pour l'après-midi : aucune plage horaire avec téléphone, sauf vendredi
        if d != "Friday":
          model.add(
            sum(schedule[e]["Téléphone"][d][s] for s in get_shifts_for_day(d) if s in afternoon_shifts) == 0
          ).only_enforce_if(has_afternoon_without_phone[e][d])
          model.add(
            sum(schedule[e]["Téléphone"][d][s] for s in  get_shifts_for_day(d) if s in afternoon_shifts) >= 1
          ).only_enforce_if(~has_afternoon_without_phone[e][d])


    #La contrainte principale : chaque personne doit avoir au moins une demi-journée sans téléphone
    model.add(
      sum(has_morning_without_phone[e][d] for d in days) +
      sum(has_afternoon_without_phone[e][d] for d in days if d != "Friday") == 1
    )

continuous_shifts = {}
for e in employees:
  continuous_shifts[e] = {}
  for d in days:
    continuous_shifts[e][d] = {}
    for r in roles:
      continuous_shifts[e][d][r] = {}
      for s_idx, s in enumerate([s for s in morning_shifts]):
        if s_idx >= 4:
          model.add( 
              sum(schedule[e][r][d][s] for s in morning_shifts[s_idx-4:s_idx]) <= 3
            )
      for s_idx, s in enumerate([s for s in afternoon_shifts]):
        if d != "Friday":
          if s_idx >= 5:
            model.add( 
                sum(schedule[e][r][d][s] for s in afternoon_shifts[s_idx-5:s_idx]) <= 4
              )
        else:
          if s_idx >= 4:
            model.add( 
                sum(schedule[e][r][d][s] for s in afternoon_shifts[s_idx-4:s_idx]) <= 3
            )   

has_morning_early_phone = {}
has_morning_late_phone = {}
has_afternoon_shift = {}
early_morning_shifts = ["09:00","09:30","10:00"]
late_morning_shifts = ["10:30","11:00","11:30"]
early_afternoon_shifts_redux =  ["14:00","14:30","15:00"]
late_afternoon_shifts_redux = ["15:30","16:00","16:30"]
early_afternoon_shifts =  ["14:00","14:30","15:00","15:30"]
late_afternoon_shifts =  ["16:00","16:30","17:00","17:30"]

for e in employees:
  has_morning_early_phone[e] = {
        d:  model.new_bool_var(f"morning_early_phone_{e}_{d}") for d in days
    }
  has_morning_late_phone[e] = {
        d:  model.new_bool_var(f"morning_late_phone_{e}_{d}") for d in days
  }
  has_afternoon_shift[e] = {
        d:  model.new_bool_var(f"afternoon_shift_{e}_{d}") for d in days
  }
  for d in days:
    model.add(
      sum(schedule[e]["Téléphone"][d][s] for s in early_morning_shifts) == 3
    ).only_enforce_if(has_morning_early_phone[e][d])
    model.add(
      sum(schedule[e]["Téléphone"][d][s] for s in early_morning_shifts) == 0
    ).only_enforce_if(~has_morning_early_phone[e][d])
    model.add(
      sum(schedule[e]["Téléphone"][d][s] for s in late_morning_shifts) == 3
    ).only_enforce_if(has_morning_late_phone[e][d])
    model.add(
      sum(schedule[e]["Téléphone"][d][s] for s in late_morning_shifts) == 0
    ).only_enforce_if(~has_morning_late_phone[e][d])  

#Dans chaque squad, chaque personne doit passer à peu près le même temps
# au téléphone, sur Intercom, sur Slack et sur les tâches.
max_nb_shifts = 100

total_shifts = {e:{r: model.new_int_var(0, max_nb_shifts, f"total_shifts_{e}_{r}") for r in roles} for e in employees}
for e in employees:
  for r in roles:
    model.add(total_shifts[e][r] == sum(schedule[e][r][d][s] for d in days for s in get_shifts_for_day(d)))
min_shifts = model.new_int_var(0, max_nb_shifts, "min_shifts")
model.add_min_equality(min_shifts, [total_shifts[e][r] for e in employees for r in roles])
max_shifts = model.new_int_var(0, max_nb_shifts, "max_shifts")
model.add_max_equality(max_shifts, [total_shifts[e][r] for e in employees for r in roles])
model.minimize(max_shifts - min_shifts)

solver = cp_model.CpSolver()
solver.solve(model)
status = solver.solve(model)
if status == 4:
  st.write("Emploi du temps généré !")
  data_list = []
  for e in employees:
    for d in days:
      for s in shifts:
        role = "📞" if solver.value(schedule[e]["Téléphone"][d][s]) == 1 else "✉️" if solver.value(schedule[e]["IC"][d][s]) == 1 else "🙋" if solver.value(schedule[e]["Slack"][d][s]) == 1 else "❓" if solver.value(schedule[e]["Una"][d][s]) == 1 else "✅" if s in get_shifts_for_day(d) else None
        data_list.append({"employee":e, "day":d, "shift":s,"role":role})
  schedule_df = pd.DataFrame(data_list).sort_values(by=["day","employee"])
  schedule_dict = {}
  for day, day_df in schedule_df.groupby(by="day"):
    shifts_list = []
    for e, employee_df in day_df.groupby(by="employee"):
      day_shifts = employee_df["shift"]
      shift_role = employee_df["role"]
      shifts_dict = {"employee":e}
      for i in range(len(day_shifts)):
        shifts_dict[day_shifts.iloc[i]]= shift_role.iloc[i]
      shifts_list.append(shifts_dict)
    schedule_dict[day] = pd.DataFrame(shifts_list)

  for day in ["Monday","Tuesday","Wednesday","Thursday","Friday"]:
    st.write(day)
    st.write(schedule_dict[day])

  count_dict_list = []
  for employee, employee_df in schedule_df.groupby(by="employee"):
    shift_counts = employee_df["role"].value_counts()
    count_dict = {"employee":employee}
    for role, role_count in zip(shift_counts.index,shift_counts.values):
      count_dict[role] = role_count
    count_dict_list.append(count_dict)
  count_df = pd.DataFrame(count_dict_list)
  st.write("Compte total:")
  st.write(count_df)

else:
  st.write("Pas d'emploi du temps respectant les contraintes 😥")


