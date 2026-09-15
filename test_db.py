import sqlite3, json
conn = sqlite3.connect('C:/Users/Afzal/ZCodeProject/converter/jobs_v2.db')
c = conn.cursor()
c.execute("SELECT extraction_payload FROM jobs WHERE id = '751569c5'")
row = c.fetchone()
if row and row[0]:
    data = json.loads(row[0])
    for f in data.get('forms', []):
        if 'UVIS' in f.get('name', ''):
            print('Form:', f.get('name'), 'Section Colors:', f.get('section_colors'))
else:
    print('Job not found or no payload')
