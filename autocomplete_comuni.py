import os
import json
import threading
from tkinter import StringVar, Button, Entry, Frame, Toplevel, Listbox, Scrollbar, SINGLE, END

class AutocompleteComune:
    """
    Widget personalizzato per l'autocompletamento dei comuni italiani 
    utilizzando Entry + Listbox per massima flessibilità.
    """
    def __init__(self, parent, comune_var, provincia_var, cap_var, width=30):
        self.parent = parent
        self.comune_var = comune_var
        self.provincia_var = provincia_var
        self.cap_var = cap_var
        self.width = width
        
        # Frame contenitore per il widget di autocompletamento
        self.frame = Frame(parent)
        
        # Entry field per l'input
        self.comune_entry = Entry(self.frame, width=width, textvariable=comune_var)
        self.comune_entry.pack(side="left", fill="x", expand=True)
        
        # Pulsante per attivare la ricerca
        self.search_button = Button(self.frame, text="🔍", command=self.toggle_dropdown, width=2)
        self.search_button.pack(side="right")
        
        # Stato del dropdown
        self.dropdown_visible = False
        self.dropdown_window = None
        self.listbox = None
        self.scrollbar = None
        
        # Timer per debounce
        self.update_timer_id = None
        
        # Carica il database dei comuni
        self.comuni_data = {}
        self.thread_lock = threading.Lock()
        
        # Crea subito un database di esempio
        self.create_sample_database()
        
        # Avvia il caricamento del database completo in un thread separato
        threading.Thread(target=self.load_comuni_database, daemon=True).start()
        
        # Collegamento eventi base
        self.comune_entry.bind("<KeyRelease>", self.on_keyrelease)
        
        # Navigazione con frecce
        self.comune_entry.bind("<Down>", self.on_down_arrow)
        self.comune_entry.bind("<Up>", self.on_up_arrow)
        self.comune_entry.bind("<Return>", self.on_entry_return)
        self.comune_entry.bind("<Escape>", lambda e: self.hide_dropdown())
        
        # Traccia cambiamenti nella variabile
        self.comune_var.trace_add('write', self.on_variable_change)
    
    def load_comuni_database(self):
        """Carica il database dei comuni da file locale"""
        try:
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
            
            return sorted(suggestions)[:100]  # Limitiamo a 100 risultati
    
    def on_keyrelease(self, event):
        """Gestisce l'evento di rilascio tasto nella casella di ricerca"""
        # Ignora i tasti di navigazione
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Tab', 'Escape', 'Return'):
            return
        
        # Cancella eventuali timer di aggiornamento esistenti
        if hasattr(self, 'update_timer_id') and self.update_timer_id:
            self.parent.after_cancel(self.update_timer_id)
        
        # Ottieni il testo corrente
        text = self.comune_var.get()
        
        # Se il testo è troppo breve, chiudi il dropdown
        if len(text) < 2:
            self.hide_dropdown()
            return
            
        # Imposta un timer per l'aggiornamento dell'autocompletamento
        self.update_timer_id = self.parent.after(300, self.update_suggestions)
    
    def on_variable_change(self, *args):
        """Chiamata quando cambia il valore della variabile del comune"""
        # Controlla se il valore corrisponde a un comune nel database
        comune = self.comune_var.get()
        
        # Aggiorna i campi provincia e CAP
        if comune:
            self.aggiorna_provincia_cap(comune)
    
    def update_suggestions(self):
        """Aggiorna i suggerimenti e mostra il dropdown"""
        text = self.comune_var.get()
        suggestions = self.get_suggestions(text)
        
        # Se non ci sono suggerimenti o il testo è troppo breve, nascondi il dropdown
        if not suggestions or len(text) < 2:
            self.hide_dropdown()
            return
        
        # Mostra il dropdown con i suggerimenti
        self.show_dropdown(suggestions)
    
    def show_dropdown(self, suggestions=None):
        """Mostra il dropdown con i suggerimenti"""
        if suggestions is None:
            text = self.comune_var.get()
            suggestions = self.get_suggestions(text)
        
        # Se non ci sono suggerimenti, non fare nulla
        if not suggestions:
            return
        
        # Se il dropdown è già visibile, aggiorna solo il contenuto
        if self.dropdown_visible and self.dropdown_window and self.listbox:
            self.listbox.delete(0, END)
            for item in suggestions:
                self.listbox.insert(END, item)
            return
        
        # Altrimenti crea un nuovo dropdown
        try:
            # Chiudi qualsiasi dropdown esistente
            self.hide_dropdown()
            
            # Crea una nuova finestra per il dropdown
            self.dropdown_window = Toplevel(self.parent)
            self.dropdown_window.overrideredirect(True)  # Rimuove la decorazione
            
            # Posiziona la finestra sotto il campo di input
            x = self.comune_entry.winfo_rootx()
            y = self.comune_entry.winfo_rooty() + self.comune_entry.winfo_height()
            
            # Calcola la larghezza in base alla larghezza dell'entry
            width = self.comune_entry.winfo_width()
            
            self.dropdown_window.geometry(f"{width}x200+{x}+{y}")
            
            # Crea una listbox con scrollbar
            listbox_frame = Frame(self.dropdown_window)
            listbox_frame.pack(fill="both", expand=True)
            
            self.listbox = Listbox(listbox_frame, selectmode=SINGLE, height=10)
            self.scrollbar = Scrollbar(listbox_frame, orient="vertical", command=self.listbox.yview)
            self.listbox.config(yscrollcommand=self.scrollbar.set)
            
            self.scrollbar.pack(side="right", fill="y")
            self.listbox.pack(side="left", fill="both", expand=True)
            
            # Popola la listbox
            for item in suggestions:
                self.listbox.insert(END, item)
            
            # Collegamento eventi per la listbox
            self.listbox.bind("<ButtonRelease-1>", self.on_selection)
            self.listbox.bind("<Return>", self.on_selection)
            self.listbox.bind("<Double-1>", self.on_selection)
            self.listbox.bind("<Escape>", lambda e: self.hide_dropdown())
            
            # Gestione navigazione frecce nella listbox
            self.listbox.bind("<Up>", self.on_listbox_up)
            self.listbox.bind("<Down>", self.on_listbox_down)
            self.listbox.bind("<Key>", self.on_listbox_key)
            
            # Gestione della rotellina del mouse
            self.listbox.bind("<MouseWheel>", self.on_mousewheel)
            
            # Configura la chiusura automatica quando il focus va altrove
            self.dropdown_window.bind("<FocusOut>", self.check_dropdown_focus_out)
            # Importante: dobbiamo monitorare il focus su tutti i componenti interessati
            self.listbox.bind("<FocusOut>", self.check_listbox_focus_out)
            
            # Aggiorna lo stato
            self.dropdown_visible = True
            
            # Dopo un breve ritardo, seleziona il primo elemento
            self.parent.after(50, self.select_first_item)
            
            print(f"[AutocompleteComune] Mostrati {len(suggestions)} suggerimenti")
        except Exception as e:
            print(f"[AutocompleteComune] Errore nella creazione del dropdown: {str(e)}")
            import traceback
            traceback.print_exc()
            self.dropdown_visible = False
    
    def hide_dropdown(self):
        """Nasconde il dropdown"""
        if self.dropdown_visible and self.dropdown_window:
            try:
                self.dropdown_window.destroy()
            except:
                pass
            self.dropdown_window = None
            self.listbox = None
            self.scrollbar = None
            self.dropdown_visible = False
    
    def select_first_item(self):
        """Seleziona il primo elemento della listbox"""
        if self.dropdown_visible and self.listbox and self.listbox.size() > 0:
            self.listbox.selection_clear(0, END)
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self.listbox.see(0)
    
    def on_selection(self, event):
        """Gestisce la selezione di un comune dalla lista"""
        if not self.listbox:
            return
            
        # Ottieni il comune selezionato
        selection = self.listbox.curselection()
        if selection:
            comune = self.listbox.get(selection[0])
            
            # Imposta il valore nel campo
            self.comune_var.set(comune)
            
            # Aggiorna provincia e CAP
            self.aggiorna_provincia_cap(comune)
            
            # Chiudi il dropdown
            self.hide_dropdown()
            
            # Sposta il focus sul campo di input
            self.comune_entry.focus_set()
            
            print(f"[AutocompleteComune] Selezionato: {comune}")
    
    def check_dropdown_focus_out(self, event):
        """Gestisce l'evento di perdita del focus dalla finestra dropdown"""
        # Usa un breve ritardo per permettere che il focus passi ad altri widget nel dropdown
        self.parent.after(150, self.check_focus_state)
    
    def check_listbox_focus_out(self, event):
        """Gestisce l'evento di perdita del focus dalla listbox"""
        # Usa un breve ritardo per permettere che il focus passi ad altri widget
        self.parent.after(150, self.check_focus_state)
    
    def check_focus_state(self):
        """Verifica lo stato del focus e decide se chiudere il dropdown"""
        if not self.dropdown_visible:
            return
            
        try:
            # Ottieni il widget che ha il focus
            focused_widget = self.parent.focus_get()
            
            # Se il focus è nel dropdown o nel campo di input, non chiudere
            if ((self.dropdown_window and focused_widget == self.dropdown_window) or
                (self.listbox and focused_widget == self.listbox) or
                (self.scrollbar and focused_widget == self.scrollbar) or
                focused_widget == self.comune_entry):
                return
                
            # Controlla anche i widget figli
            try:
                if focused_widget and focused_widget.master:
                    if (focused_widget.master == self.dropdown_window or
                        focused_widget.master == self.listbox or
                        focused_widget.master == self.scrollbar):
                        return
            except:
                pass
                
            # Se siamo qui, il focus è altrove - chiudi il dropdown
            self.hide_dropdown()
        except Exception as e:
            print(f"[AutocompleteComune] Errore nel controllo del focus: {str(e)}")
    
    def on_down_arrow(self, event):
        """Gestisce la pressione della freccia giù nel campo di input"""
        if not self.dropdown_visible:
            # Se il dropdown non è visibile, mostralo
            self.update_suggestions()
            
            # Dopo un breve ritardo, seleziona il primo elemento
            self.parent.after(50, self.select_first_item)
        elif self.listbox:
            # Se il dropdown è visibile, seleziona il primo elemento
            if self.listbox.size() > 0:
                # Sposta il focus alla listbox e seleziona il primo elemento
                self.listbox.focus_set()
                self.listbox.selection_clear(0, END)
                self.listbox.selection_set(0)
                self.listbox.activate(0)
                self.listbox.see(0)
        
        # Impedisci l'elaborazione standard dell'evento
        return "break"
    
    def on_up_arrow(self, event):
        """Gestisce la pressione della freccia su nel campo di input"""
        if self.dropdown_visible and self.listbox and self.listbox.size() > 0:
            # Sposta il focus alla listbox e seleziona l'ultimo elemento
            self.listbox.focus_set()
            last_index = self.listbox.size() - 1
            self.listbox.selection_clear(0, END)
            self.listbox.selection_set(last_index)
            self.listbox.activate(last_index)
            self.listbox.see(last_index)
        
        # Impedisci l'elaborazione standard dell'evento
        return "break"
    
    def on_listbox_up(self, event):
        """Gestisce la pressione della freccia su nella listbox"""
        # Ottieni l'indice corrente
        selection = self.listbox.curselection()
        if selection:
            current_index = selection[0]
            
            # Se siamo già in cima, riporta il focus al campo di input
            if current_index == 0:
                self.comune_entry.focus_set()
                self.listbox.selection_clear(0, END)
                return "break"
            
            # Altrimenti seleziona l'elemento precedente
            new_index = current_index - 1
            self.listbox.selection_clear(0, END)
            self.listbox.selection_set(new_index)
            self.listbox.activate(new_index)
            self.listbox.see(new_index)
            return "break"
        else:
            # Se non c'è selezione, seleziona il primo elemento
            if self.listbox.size() > 0:
                self.listbox.selection_set(0)
                self.listbox.activate(0)
                self.listbox.see(0)
            return "break"
    
    def on_listbox_down(self, event):
        """Gestisce la pressione della freccia giù nella listbox"""
        # Ottieni l'indice corrente
        selection = self.listbox.curselection()
        if selection:
            current_index = selection[0]
            last_index = self.listbox.size() - 1
            
            # Se siamo già in fondo, non fare nulla di particolare
            if current_index == last_index:
                return "break"
            
            # Altrimenti seleziona l'elemento successivo
            new_index = current_index + 1
            self.listbox.selection_clear(0, END)
            self.listbox.selection_set(new_index)
            self.listbox.activate(new_index)
            self.listbox.see(new_index)
            return "break"
        else:
            # Se non c'è selezione, seleziona il primo elemento
            if self.listbox.size() > 0:
                self.listbox.selection_set(0)
                self.listbox.activate(0)
                self.listbox.see(0)
            return "break"
    
    def on_listbox_key(self, event):
        """Gestisce gli eventi tastiera nella listbox"""
        key = event.keysym
        
        # Lascia che le frecce su/giù siano gestite dai metodi specifici
        if key in ('Up', 'Down'):
            return
        
        # Per Enter, elabora la selezione
        if key == 'Return':
            self.on_selection(event)
            return "break"
        
        # Per Escape, chiudi il dropdown
        if key == 'Escape':
            self.hide_dropdown()
            self.comune_entry.focus_set()
            return "break"
        
        # Per i tasti Home e End, sincronizza la selezione con l'elemento attivo
        if key in ('Home', 'End'):
            self.parent.after(10, self.sync_active_selection)
        
        # Per qualsiasi altro tasto, passa l'input al campo di input
        if len(key) == 1 and key.isalnum() or key in ('space', 'BackSpace'):
            # Riporta il focus al campo di input
            self.comune_entry.focus_set()
            
            # Se è un carattere stampabile, inseriscilo nel campo
            if len(key) == 1 and key.isalnum():
                current_text = self.comune_var.get()
                cursor_pos = self.comune_entry.index("insert")
                new_text = current_text[:cursor_pos] + key + current_text[cursor_pos:]
                self.comune_var.set(new_text)
                self.comune_entry.icursor(cursor_pos + 1)
            
            # Se è spazio, inserisci uno spazio
            elif key == 'space':
                current_text = self.comune_var.get()
                cursor_pos = self.comune_entry.index("insert")
                new_text = current_text[:cursor_pos] + ' ' + current_text[cursor_pos:]
                self.comune_var.set(new_text)
                self.comune_entry.icursor(cursor_pos + 1)
            
            # Se è backspace, cancella il carattere prima del cursore
            elif key == 'BackSpace':
                current_text = self.comune_var.get()
                cursor_pos = self.comune_entry.index("insert")
                if cursor_pos > 0:
                    new_text = current_text[:cursor_pos-1] + current_text[cursor_pos:]
                    self.comune_var.set(new_text)
                    self.comune_entry.icursor(cursor_pos - 1)
            
            return "break"
    
    def sync_active_selection(self):
        """Sincronizza l'elemento selezionato con l'elemento attivo"""
        if self.listbox:
            try:
                active_index = self.listbox.index("active")
                self.listbox.selection_clear(0, END)
                self.listbox.selection_set(active_index)
                self.listbox.see(active_index)
            except:
                pass
    
    def on_entry_return(self, event):
        """Gestisce la pressione di Invio nel campo di input"""
        if self.dropdown_visible and self.listbox:
            # Se ci sono elementi selezionati nella listbox
            selection = self.listbox.curselection()
            if selection:
                # Usa l'elemento selezionato
                self.on_selection(event)
            else:
                # Se non c'è selezione ma ci sono elementi, seleziona il primo
                if self.listbox.size() > 0:
                    self.listbox.selection_set(0)
                    self.on_selection(event)
        
        # Impedisci l'elaborazione standard dell'evento
        return "break"
    
    def on_mousewheel(self, event):
        """Gestisce la rotellina del mouse nella listbox"""
        # Scorri la listbox in base alla direzione della rotellina
        if self.listbox:
            # Direzione dello scrolling (dipende dalla piattaforma)
            direction = -1 if event.delta > 0 else 1
            self.listbox.yview_scroll(direction, "units")
        
        # Impedisci la propagazione dell'evento
        return "break"
    
    def toggle_dropdown(self):
        """Apre o chiude il dropdown quando si preme il pulsante"""
        if self.dropdown_visible:
            self.hide_dropdown()
        else:
            self.update_suggestions()
            
            # Sposta il focus sul campo
            self.comune_entry.focus_set()
    
    def aggiorna_provincia_cap(self, comune):
        """Aggiorna i campi provincia e CAP in base al comune selezionato"""
        with self.thread_lock:
            if comune in self.comuni_data:
                # Imposta la provincia
                if 'provincia' in self.comuni_data[comune]:
                    self.provincia_var.set(self.comuni_data[comune]['provincia'])
                
                # Imposta il CAP (prende il primo disponibile per semplicità)
                if 'cap' in self.comuni_data[comune] and self.comuni_data[comune]['cap']:
                    self.cap_var.set(self.comuni_data[comune]['cap'][0])
                    
                return True
        
        return False