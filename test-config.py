import configparser

config = configparser.ConfigParser()
config.read('config.ini')

print("Sezioni trovate:", config.sections())
if 'Network' in config:
    print("IP:", config.get('Network', 'IP'))
    print("Hostname:", config.get('Network', 'Hostname'))
else:
    print("⚠️ Sezione [Network] non trovata nel file config.ini")