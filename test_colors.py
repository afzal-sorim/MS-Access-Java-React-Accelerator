import json
with open('C:/Users/Afzal/ZCodeProject/converter/outputs/5f05efff/.extract/extraction.json', 'r') as f:
    data = json.load(f)
for frm in data.get('forms', []):
    if 'UVIS' in frm.get('name', ''):
        print('Form:', frm['name'], 'BackColor:', frm.get('back_color'))
        for ctrl in frm.get('controls', [])[:5]:
            print(f"  {ctrl.get('name')}: BackColor={ctrl.get('back_color')} ForeColor={ctrl.get('fore_color')}")
