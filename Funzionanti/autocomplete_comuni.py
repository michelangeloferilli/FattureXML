import os
import json
import threading
from tkinter import ttk, StringVar, Button, Frame

class AutocompleteComune:
    """
    Widget per l'autocompletamento dei comuni italiani usando Combobox.
    Versione semplificata per garantire la digitazione fluida.
    """
    def __init__(self, parent, comune_var, provincia_var, cap_var, width=30):
        self.parent = parent
        self.comune_var = comune_var
        self.provincia_var = provincia_var
        self.cap_var = cap_var
        self.width = width
        
        # Frame contenitore per il widget di autocompletamento
        self.frame = Frame(parent)
        
        # Crea una nuova variabile per il combobox
        self.combobox_var = StringVar()
        self.combobox_var.set(comune_var.get())  # Inizializza con il valore corrente
        
        # Crea il combobox per l'autocomplete
        self.comune_combobox = ttk.Combobox(self.frame, textvariable=self.combobox_var, width=width, 
                                           postcommand=self.on_dropdown_requested)
        self.comune_combobox.pack(side="left", fill="x", expand=True)
        
        # Configura il combobox per permettere input liberi
        self.comune_combobox['state'] = 'normal'
        
        # Pulsante per attivare la ricerca
        self.search_button = Button(self.frame, text="🔍", command=self.on_search_click, width=2)
        self.search_button.pack(side="right")
        
        # Collegamento eventi
        self.comune_combobox.bind("<KeyRelease>", self.on_keyrelease)
        self.comune_combobox.bind("<<ComboboxSelected>>", self.on_comune_selected)
        
        # Variabile per tenere traccia del timer di debounce
        self.update_timer_id = None
        
        # Carica il database dei comuni
        self.comuni_data = {}
        self.thread_lock = threading.Lock()
        
        # Crea subito un database di esempio (come fallback)
        self.create_sample_database()
        
        # Avvia il caricamento del database completo in un thread separato
        threading.Thread(target=self.load_comuni_database, daemon=True).start()
        
        # Sincronizza le due variabili
        def update_comune_var(*args):
            val = self.combobox_var.get()
            self.comune_var.set(val)
        
        self.combobox_var.trace_add('write', update_comune_var)
    
    def load_comuni_database(self):
        """Carica il database dei comuni da file locale"""
        try:
            # Prima controlla se esiste un file locale
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "comuni_italiani.json")
            
            if os.path.exists(db_path):
                print(f"[AutocompleteComune] Trovato database locale: {db_path}")
                with open(db_path, 'r', encoding='utf-8') as f:
                    with self.thread_lock:
                        self.comuni_data = json.load(f)
                    print(f"[AutocompleteComune] Caricati {len(self.comuni_data)} comuni dal database locale")
        except Exception as e:
            print(f"[AutocompleteComune] Errore nel caricamento del database comuni: {str(e)}")
    
    def create_sample_database(self):
        """Crea un database di esempio con alcuni comuni principali"""
        sample_data = {
            "Roma": {"provincia": "RM", "cap": ["00100"]},
            "Milano": {"provincia": "MI", "cap": ["20121"]},
            "Napoli": {"provincia": "NA", "cap": ["80100"]},
            "Torino": {"provincia": "TO", "cap": ["10121"]},
            "Palermo": {"provincia": "PA", "cap": ["90121"]},
            "Genova": {"provincia": "GE", "cap": ["16121"]},
            "Bologna": {"provincia": "BO", "cap": ["40121"]},
            "Firenze": {"provincia": "FI", "cap": ["50121"]},
            "Bari": {"provincia": "BA", "cap": ["70121"]},
            "Catania": {"provincia": "CT", "cap": ["95121"]}
        }
        
        with self.thread_lock:
            self.comuni_data = sample_data
            print(f"[AutocompleteComune] Creato database di esempio con {len(self.comuni_data)} comuni")
    
    def get_suggestions(self, text_to_search=""):
        """Ottiene suggerimenti in base al testo inserito"""
        with self.thread_lock:
            if not text_to_search:
                # Se non c'è testo, ritorna tutti i comuni (fino a un massimo)
                return sorted(list(self.comuni_data.keys()))[:100]
            
            text_lower = text_to_search.lower()
            # Cerca comuni che iniziano con il testo inserito
            suggestions = [comune for comune in self.comuni_data.keys() 
                          if comune.lower().startswith(text_lower)]
            
            # Se non ci sono abbastanza risultati, cerca anche quelli che contengono il testo
            if len(suggestions) < 10:
                additional = [comune for comune in self.comuni_data.keys() 
                             if comune.lower().find(text_lower) != -1 and comune not in suggestions]
                suggestions.extend(additional[:10-len(suggestions)])
            
            return sorted(suggestions)
    
    def on_dropdown_requested(self):
        """Chiamato prima che il dropdown venga mostrato"""
        # Aggiorna la lista dei suggerimenti in base al testo corrente
        text = self.combobox_var.get()
        suggestions = self.get_suggestions(text)
        self.comune_combobox['values'] = suggestions
        print(f"[AutocompleteComune] Dropdown richiesto per '{text}': {len(suggestions)} suggerimenti")
    
    def on_keyrelease(self, event):
        """Gestisce l'evento di rilascio tasto nella casella di ricerca con debounce"""
        # Ignora la navigazione con cursore
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Escape'):
            return
        
        # Cancella eventuali timer di aggiornamento esistenti
        if hasattr(self, 'update_timer_id') and self.update_timer_id:
            self.parent.after_cancel(self.update_timer_id)
        
        # Ottieni il testo corrente
        text = self.combobox_var.get()
        
        # Se il testo è troppo breve, non aggiornare a meno che non sia vuoto
        if 0 < len(text) < 2:
            return
            
        # Imposta un timer per l'aggiornamento dell'autocompletamento
        self.update_timer_id = self.parent.after(300, self.update_suggestions)
    
    def update_suggestions(self):
        """Aggiorna i suggerimenti e attiva l'autocompletamento"""
        try:
            # Aggiorna la lista dei suggerimenti
            text = self.combobox_var.get()
            suggestions = self.get_suggestions(text)
            
            # Aggiorna i valori del combobox
            self.comune_combobox['values'] = suggestions
            
            # Apri il dropdown se ci sono suggerimenti
            if suggestions and (len(text) >= 2 or text == ""):
                self.comune_combobox.event_generate('<Down>')
            
            print(f"[AutocompleteComune] Aggiornati {len(suggestions)} suggerimenti per '{text}'")
        except Exception as e:
            print(f"[AutocompleteComune] Errore nell'aggiornamento dei suggerimenti: {str(e)}")
    
    def on_search_click(self):
        """Gestisce il click sul pulsante di ricerca"""
        print("[AutocompleteComune] Pulsante di ricerca cliccato")
        
        # Cancella eventuali timer pendenti
        if hasattr(self, 'update_timer_id') and self.update_timer_id:
            self.parent.after_cancel(self.update_timer_id)
            self.update_timer_id = None
        
        # Se il dropdown è già aperto, chiudilo
        try:
            if self.comune_combobox.winfo_ismapped():
                self.comune_combobox.event_generate('<Escape>')
                return
        except:
            pass
        
        # Altrimenti aprilo
        self.update_suggestions()
    
    def on_comune_selected(self, event):
        """Gestisce l'evento di selezione di un comune dal combobox"""
        comune = self.combobox_var.get()
        self.aggiorna_provincia_cap(comune)
        print(f"[AutocompleteComune] Selezionato comune: {comune}")
    
    def aggiorna_provincia_cap(self, comune):
        """Aggiorna i campi provincia e CAP in base al comune selezionato"""
        with self.thread_lock:
            if comune in self.comuni_data:
                # Imposta la provincia
                if 'provincia' in self.comuni_data[comune]:
                    self.provincia_var.set(self.comuni_data[comune]['provincia'])
                    print(f"[AutocompleteComune] Provincia impostata: {self.comuni_data[comune]['provincia']}")
                
                # Imposta il CAP (prende il primo disponibile per semplicità)
                if 'cap' in self.comuni_data[comune] and self.comuni_data[comune]['cap']:
                    self.cap_var.set(self.comuni_data[comune]['cap'][0])
                    print(f"[AutocompleteComune] CAP impostato: {self.comuni_data[comune]['cap'][0]}")
                    
                return True
        
        return False