import json
import csv
import os
import requests
import time
from pathlib import Path

def download_comuni_dataset():
    """Scarica un dataset di comuni italiani da una fonte affidabile online"""
    print("Scaricamento del dataset dei comuni italiani...")
    
    # Prova diverse fonti in ordine
    urls = [
        "https://github.com/matteocontrini/comuni-json/raw/master/comuni.json",
        "https://raw.githubusercontent.com/opendatasicilia/comuni-italiani/main/dati/comuni.json"
    ]
    
    for url in urls:
        try:
            print(f"Tentativo download da: {url}")
            response = requests.get(url)
            response.raise_for_status()
            comuni_data = response.json()
            print(f"Dataset scaricato con successo: {len(comuni_data)} comuni")
            return comuni_data
        except Exception as e:
            print(f"Errore durante il download da {url}: {str(e)}")
    
    print("Tutti i tentativi di download sono falliti.")
    return None

def get_cap_from_istat():
    """Ottiene i CAP da un file ISTAT o altre fonti"""
    print("Tentativo di ottenere i CAP da fonti alternative...")
    
    # Le fonti di dati ISTAT spesso cambiano, quindi tentiamo diverse opzioni
    try:
        # Prima tentiamo con il dataset dei CAP di Poste Italiane (se esiste un export pubblico)
        cap_url = "https://raw.githubusercontent.com/Italia/cap/main/data/cap-comuni.csv"
        response = requests.get(cap_url)
        if response.status_code == 200:
            temp_csv = "cap_temp.csv"
            with open(temp_csv, 'wb') as f:
                f.write(response.content)
            
            comune_cap = {}
            encoding_attempts = ['utf-8', 'latin-1', 'iso-8859-1']
            
            for encoding in encoding_attempts:
                try:
                    with open(temp_csv, 'r', encoding=encoding) as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            comune = row.get('comune', '') or row.get('Comune', '') or row.get('COMUNE', '')
                            cap = row.get('cap', '') or row.get('Cap', '') or row.get('CAP', '')
                            
                            if comune and cap:
                                if comune not in comune_cap:
                                    comune_cap[comune] = []
                                if cap not in comune_cap[comune]:
                                    comune_cap[comune].append(cap)
                    break  # Se siamo arrivati qui, la lettura è riuscita
                except UnicodeDecodeError:
                    continue  # Prova la prossima codifica
            
            os.remove(temp_csv)
            
            if comune_cap:
                print(f"CAP ottenuti con successo: {len(comune_cap)} comuni")
                return comune_cap
    except Exception as e:
        print(f"Errore durante l'ottenimento dei CAP: {str(e)}")
    
    # Se non riusciamo a ottenere i CAP da fonti esterne, usiamo un metodo di fallback
    print("Utilizzo il metodo di generazione CAP basato su provincia...")
    return generate_cap_from_province()

def generate_cap_from_province():
    """Genera CAP basati sulle sigle di provincia"""
    # Queste sono associazioni note per le province italiane
    # Notare che questa è solo un'approssimazione per i CAP principali
    province_cap = {
        "AG": "92100", "AL": "15121", "AN": "60121", "AO": "11100", "AR": "52100",
        "AP": "63100", "AT": "14100", "AV": "83100", "BA": "70121", "BT": "76121",
        "BL": "32100", "BN": "82100", "BG": "24121", "BI": "13900", "BO": "40121",
        "BZ": "39100", "BS": "25121", "BR": "72100", "CA": "09121", "CL": "93100",
        "CB": "86100", "CE": "81100", "CT": "95121", "CZ": "88100", "CH": "66100",
        "CO": "22100", "CS": "87100", "CR": "26100", "KR": "88900", "CN": "12100",
        "EN": "94100", "FM": "63900", "FE": "44121", "FI": "50121", "FG": "71121",
        "FC": "47121", "FR": "03100", "GE": "16121", "GO": "34170", "GR": "58100",
        "IM": "18100", "IS": "86170", "SP": "19121", "LT": "04100", "LE": "73100",
        "LC": "23900", "LI": "57121", "LO": "26900", "LU": "55100", "MC": "62100",
        "MN": "46100", "MS": "54100", "MT": "75100", "ME": "98121", "MI": "20121",
        "MO": "41121", "MB": "20900", "NA": "80121", "NO": "28100", "NU": "08100",
        "OR": "09170", "PD": "35121", "PA": "90121", "PR": "43121", "PV": "27100",
        "PG": "06121", "PU": "61121", "PE": "65121", "PC": "29121", "PI": "56121",
        "PT": "51100", "PN": "33170", "PZ": "85100", "PO": "59100", "RG": "97100",
        "RA": "48121", "RC": "89121", "RE": "42121", "RI": "02100", "RN": "47921",
        "RM": "00121", "RO": "45100", "SA": "84121", "SS": "07100", "SV": "17100",
        "SI": "53100", "SR": "96100", "SO": "23100", "TA": "74121", "TE": "64100",
        "TR": "05100", "TO": "10121", "TP": "91100", "TN": "38121", "TV": "31100",
        "TS": "34121", "UD": "33100", "VA": "21100", "VE": "30121", "VB": "28921",
        "VC": "13100", "VR": "37121", "VV": "89900", "VI": "36100", "VT": "01100"
    }

    # Per le città principali, aggiungiamo più CAP
    city_caps = {
        "Roma": ["00118", "00119", "00121", "00122", "00123", "00124", "00125", "00126", "00127", "00128", "00131", "00132", "00133", "00134", "00135", "00136", "00137", "00138", "00139", "00141", "00142", "00143", "00144", "00145", "00146", "00147", "00148", "00149", "00151", "00152", "00153", "00154", "00155", "00156", "00157", "00158", "00159", "00161", "00162", "00163", "00164", "00165", "00166", "00167", "00168", "00169", "00171", "00172", "00173", "00174", "00175", "00176", "00177", "00178", "00179", "00181", "00182", "00183", "00184", "00185", "00186", "00187", "00188", "00189", "00191", "00192", "00193", "00194", "00195", "00196", "00197", "00198", "00199"],
        "Milano": ["20121", "20122", "20123", "20124", "20125", "20126", "20127", "20128", "20129", "20131", "20132", "20133", "20134", "20135", "20136", "20137", "20138", "20139", "20141", "20142", "20143", "20144", "20145", "20146", "20147", "20148", "20149", "20151", "20152", "20153", "20154", "20155", "20156", "20157", "20158", "20159", "20161", "20162"],
        "Napoli": ["80121", "80122", "80123", "80124", "80125", "80126", "80127", "80128", "80129", "80131", "80132", "80133", "80134", "80135", "80136", "80137", "80138", "80139", "80141", "80142", "80143", "80144", "80145", "80146", "80147"],
        "Torino": ["10121", "10122", "10123", "10124", "10125", "10126", "10127", "10128", "10129", "10131", "10132", "10133", "10134", "10135", "10136", "10137", "10138", "10139", "10141", "10142", "10143", "10144", "10145", "10146", "10147", "10148", "10149"]
    }
    
    print(f"Generati CAP per {len(province_cap)} province e {len(city_caps)} città principali")
    
    return {"province": province_cap, "cities": city_caps}

def create_comuni_json(output_path="comuni_italiani.json"):
    """Crea un file JSON con i comuni italiani, province e CAP"""
    # Scarica i dataset
    comuni_data = download_comuni_dataset()
    cap_data = get_cap_from_istat()
    
    if not comuni_data:
        print("Non è stato possibile scaricare il dataset dei comuni. Uscita.")
        return False
    
    # Dizionario risultante
    result = {}
    
    # Determina la struttura del dataset dei comuni
    if isinstance(comuni_data, list) and "nome" in comuni_data[0]:
        # Formato Matteo Contrini
        for comune in comuni_data:
            nome_comune = comune.get('nome', '')
            provincia = comune.get('sigla', '') or comune.get('provincia', {}).get('sigla', '')
            
            if nome_comune and provincia:
                # Trova il CAP per questo comune
                cap_list = []
                
                # Prima controlla nelle città principali
                if nome_comune in cap_data.get('cities', {}):
                    cap_list = cap_data['cities'][nome_comune]
                # Poi controlla la provincia come fallback
                elif provincia in cap_data.get('province', {}):
                    cap_list = [cap_data['province'][provincia]]
                # Se ancora non abbiamo trovato un CAP, usa "00000" come placeholder
                if not cap_list:
                    cap_list = ["00000"]
                
                # Aggiungi il comune al risultato
                result[nome_comune] = {
                    "provincia": provincia,
                    "cap": cap_list
                }
    elif isinstance(comuni_data, list) and "COMUNE" in comuni_data[0]:
        # Altro formato possibile
        for comune in comuni_data:
            nome_comune = comune.get('COMUNE', '')
            provincia = comune.get('SIGLA', '') or comune.get('PROVINCIA', '')
            
            if nome_comune and provincia:
                # Trova il CAP come sopra
                cap_list = []
                
                if nome_comune in cap_data.get('cities', {}):
                    cap_list = cap_data['cities'][nome_comune]
                elif provincia in cap_data.get('province', {}):
                    cap_list = [cap_data['province'][provincia]]
                if not cap_list:
                    cap_list = ["00000"]
                
                result[nome_comune] = {
                    "provincia": provincia,
                    "cap": cap_list
                }
    else:
        print("Formato dati comuni non riconosciuto. Utilizzo della modalità alternativa.")
        # Tenta di estrarre dati dal formato sconosciuto
        try:
            for key, value in comuni_data.items():
                if isinstance(value, dict) and "nome" in value:
                    nome_comune = value.get('nome', '')
                    provincia = value.get('provincia', {}).get('sigla', '') or value.get('sigla', '')
                    
                    if nome_comune and provincia:
                        # Trova il CAP
                        cap_list = []
                        
                        if nome_comune in cap_data.get('cities', {}):
                            cap_list = cap_data['cities'][nome_comune]
                        elif provincia in cap_data.get('province', {}):
                            cap_list = [cap_data['province'][provincia]]
                        if not cap_list:
                            cap_list = ["00000"]
                        
                        result[nome_comune] = {
                            "provincia": provincia,
                            "cap": cap_list
                        }
        except Exception as e:
            print(f"Errore nell'analisi del formato alternativo: {str(e)}")
    
    if not result:
        print("Impossibile estrarre dati dai dataset. Utilizzo dataset di esempio.")
        return create_sample_json(output_path)
    
    # Salva il risultato
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"File '{output_path}' creato con successo con {len(result)} comuni")
        return True
    except Exception as e:
        print(f"Errore durante la scrittura del file: {str(e)}")
        return False

def create_sample_json(output_path="comuni_italiani.json"):
    """Crea un file JSON di esempio con i principali comuni italiani"""
    sample_data = {
        "Roma": {"provincia": "RM", "cap": ["00100", "00118", "00119", "00121", "00122", "00123", "00124", "00125", "00126", "00127", "00128", "00131", "00132", "00133", "00134", "00135", "00136", "00137", "00138", "00139", "00141", "00142", "00143", "00144", "00145", "00146", "00147", "00148", "00149", "00151", "00152", "00153", "00154", "00155", "00156", "00157", "00158", "00159", "00161", "00162", "00163", "00164", "00165", "00166", "00167", "00168", "00169", "00171", "00172", "00173", "00174", "00175", "00176", "00177", "00178", "00179", "00181", "00182", "00183", "00184", "00185", "00186", "00187", "00188", "00189", "00191", "00192", "00193", "00194", "00195", "00196", "00197", "00198", "00199"]},
        "Milano": {"provincia": "MI", "cap": ["20019", "20121", "20122", "20123", "20124", "20125", "20126", "20127", "20128", "20129", "20131", "20132", "20133", "20134", "20135", "20136", "20137", "20138", "20139", "20141", "20142", "20143", "20144", "20145", "20146", "20147", "20148", "20149", "20151", "20152", "20153", "20154", "20155", "20156", "20157", "20158", "20159", "20161", "20162"]},
        "Napoli": {"provincia": "NA", "cap": ["80100", "80121", "80122", "80123", "80124", "80125", "80126", "80127", "80128", "80129", "80131", "80132", "80133", "80134", "80135", "80136", "80137", "80138", "80139", "80141", "80142", "80143", "80144", "80145", "80146", "80147"]},
        "Torino": {"provincia": "TO", "cap": ["10121", "10122", "10123", "10124", "10125", "10126", "10127", "10128", "10129", "10131", "10132", "10133", "10134", "10135", "10136", "10137", "10138", "10139", "10141", "10142", "10143", "10144", "10145", "10146", "10147", "10148", "10149", "10151", "10152", "10153", "10154", "10155", "10156"]},
        "Palermo": {"provincia": "PA", "cap": ["90121", "90122", "90123", "90124", "90125", "90126", "90127", "90128", "90129", "90131", "90132", "90133", "90134", "90135", "90136", "90137", "90138", "90139", "90141", "90142", "90143", "90144", "90145", "90146", "90147", "90148", "90149"]},
        "Bologna": {"provincia": "BO", "cap": ["40121", "40122", "40123", "40124", "40125", "40126", "40127", "40128", "40129", "40131", "40132", "40133", "40134", "40135", "40136", "40137", "40138", "40139", "40141", "40142", "40143", "40144", "40145", "40146"]},
        "Firenze": {"provincia": "FI", "cap": ["50121", "50122", "50123", "50124", "50125", "50126", "50127", "50128", "50129", "50131", "50132", "50133", "50134", "50135", "50136", "50137", "50138", "50139", "50141", "50142", "50143", "50144", "50145"]},
        "Bari": {"provincia": "BA", "cap": ["70121", "70122", "70123", "70124", "70125", "70126", "70127", "70128", "70129", "70131", "70132"]},
        "Catania": {"provincia": "CT", "cap": ["95121", "95122", "95123", "95124", "95125", "95126", "95127", "95128", "95129", "95131"]},
        "Venezia": {"provincia": "VE", "cap": ["30121", "30122", "30123", "30124", "30125", "30126", "30127", "30128", "30129", "30131", "30132", "30133", "30135", "30136"]},
        "Genova": {"provincia": "GE", "cap": ["16121", "16122", "16123", "16124", "16125", "16126", "16127", "16128", "16129", "16131", "16132", "16133", "16134", "16135", "16136", "16137", "16138", "16139", "16141", "16142", "16143", "16144", "16145", "16146", "16147", "16148", "16149", "16151", "16152", "16153", "16154", "16155", "16156", "16157", "16158", "16159", "16161", "16162", "16163", "16164", "16165", "16166", "16167"]},
        "Verona": {"provincia": "VR", "cap": ["37121", "37122", "37123", "37124", "37125", "37126", "37127", "37128", "37129", "37131", "37132", "37133", "37134", "37135", "37136", "37137", "37138", "37139"]},
        "Messina": {"provincia": "ME", "cap": ["98121", "98122", "98123", "98124", "98125", "98126", "98127", "98128", "98129", "98131", "98132"]},
        "Padova": {"provincia": "PD", "cap": ["35121", "35122", "35123", "35124", "35125", "35126", "35127", "35128", "35129", "35131", "35132", "35133", "35134", "35135", "35136", "35137", "35138", "35139", "35141", "35142", "35143"]},
        "Trieste": {"provincia": "TS", "cap": ["34121", "34122", "34123", "34124", "34125", "34126", "34127", "34128", "34129", "34131", "34132", "34133", "34134", "34135", "34136", "34137", "34138", "34139", "34141", "34142", "34143", "34144", "34145", "34146", "34147", "34148", "34149", "34151"]},
        "Brescia": {"provincia": "BS", "cap": ["25121", "25122", "25123", "25124", "25125", "25126", "25127", "25128", "25129", "25131", "25132", "25133", "25134", "25135", "25136"]},
        "Parma": {"provincia": "PR", "cap": ["43121", "43122", "43123", "43124", "43125", "43126"]},
        "Taranto": {"provincia": "TA", "cap": ["74121", "74122", "74123"]}
    }

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)
        
        print(f"File di esempio '{output_path}' creato con successo con {len(sample_data)} comuni")
        return True
    except Exception as e:
        print(f"Errore durante la scrittura del file di esempio: {str(e)}")
        return False

def add_comuni_manually(input_file, output_file=None):
    """Aggiunge manualmente comuni al file JSON esistente"""
    if output_file is None:
        output_file = input_file
        
    try:
        # Carica il file esistente
        with open(input_file, 'r', encoding='utf-8') as f:
            comuni_data = json.load(f)
            
        # Chiedi i dati del nuovo comune
        print("\nAggiunta manuale di un comune")
        print("-----------------------------")
        nome_comune = input("Nome del comune: ")
        provincia = input("Provincia (sigla): ")
        cap = input("CAP principale: ")
        
        # Aggiungi il comune
        comuni_data[nome_comune] = {
            "provincia": provincia,
            "cap": [cap]
        }
        
        # Salva il file aggiornato
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(comuni_data, f, ensure_ascii=False, indent=2)
            
        print(f"Comune '{nome_comune}' aggiunto con successo!")
        return True
    except Exception as e:
        print(f"Errore durante l'aggiunta del comune: {str(e)}")
        return False

def check_json_format(file_path):
    """Verifica che il formato del file JSON sia corretto"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not isinstance(data, dict):
            print("ERRORE: Il file non è un dizionario JSON!")
            return False
            
        # Controlla alcuni comuni casuali
        count = 0
        for comune, info in data.items():
            if not isinstance(info, dict):
                print(f"ERRORE: Il valore per '{comune}' non è un dizionario!")
                return False
                
            if "provincia" not in info:
                print(f"ERRORE: Manca la provincia per '{comune}'!")
                return False
                
            if "cap" not in info:
                print(f"ERRORE: Manca il CAP per '{comune}'!")
                return False
                
            if not isinstance(info["cap"], list):
                print(f"ERRORE: Il CAP per '{comune}' non è una lista!")
                return False
                
            count += 1
            if count >= 10:  # Controlliamo solo i primi 10 comuni
                break
                
        print(f"Il file '{file_path}' ha un formato corretto!")
        print(f"Contiene {len(data)} comuni")
        return True
    except Exception as e:
        print(f"Errore durante la verifica del file: {str(e)}")
        return False

if __name__ == "__main__":
    print("Creazione del database dei comuni italiani")
    print("==========================================")
    print("1. Creazione del file completo (richiede connessione Internet)")
    print("2. Creazione di un file di esempio (offline)")
    print("3. Aggiunta manuale di un comune al file esistente")
    print("4. Verifica formato del file esistente")
    
    choice = input("Seleziona un'opzione (1/2/3/4): ")
    
    if choice == "1":
        create_comuni_json()
    elif choice == "2":
        create_sample_json()
    elif choice == "3":
        file_path = input("Percorso del file JSON esistente: ") or "comuni_italiani.json"
        add_comuni_manually(file_path)
    elif choice == "4":
        file_path = input("Percorso del file JSON da verificare: ") or "comuni_italiani.json"
        check_json_format(file_path)
    else:
        print("Opzione non valida")