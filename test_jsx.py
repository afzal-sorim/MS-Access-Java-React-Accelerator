import glob, os
files = glob.glob('C:/Users/Afzal/ZCodeProject/converter/outputs/*/frontend/src/pages/*.jsx')
files.sort(key=os.path.getmtime, reverse=True)
if files:
    with open(files[0], 'r') as f:
        print('Latest file:', files[0])
        content = f.read()
        idx = content.find('className="exact-layout-container"')
        if idx != -1:
            print(content[idx:idx+500])
