import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import os
import tempfile
import webbrowser
from lxml import etree
import sys
import glob
import copy
import traceback
import re


class ConaiManager:
    def __init__(self, fattura_viewer):
        self.viewer = fattura_viewer
        self.conai_line = None
    
    def has_conai(self):
        """Verifica se esiste una linea CONAI nel documento"""
        if not self.viewer.xml_doc:
            return False, None
        
        root = self.viewer.xml_doc.getroot()
        nsmap = root.nsmap
        ns = {}
        for prefix, uri in nsmap.items():
            if prefix is None:
                ns['p'] = uri
            else:
                ns[prefix] = uri
        
        conai_lines = root.xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee[Descrizione='CONTRIBUTO CONAI ASSOLTO']", namespaces=ns)
        return len(conai_lines) > 0, conai_lines[0] if conai_lines else None
        
    def add_conai(self):
        """Aggiunge una linea CONAI al documento"""
        if not self.viewer.xml_doc:
            return
        
        # Controlla se la linea già esiste
        has_conai, conai_elem = self.has_conai()
        if has_conai:
            self.viewer.log("La linea CONTRIBUTO CONAI ASSOLTO è già presente")
            self.conai_line = conai_elem
            return
        
        # Ottieni il documento e i namespace
        root = self.viewer.xml_doc.getroot()
        nsmap = root.nsmap
        ns = {}
        for prefix, uri in nsmap.items():
            if prefix is None:
                ns['p'] = uri
            else:
                ns[prefix] = uri
        
        # Trova il nodo DatiBeniServizi
        dati_beni = root.xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi", namespaces=ns)[0]
        
        # Rimuovi eventuali linee CONAI esistenti
        existing_conai_lines = dati_beni.xpath("./DettaglioLinee[Descrizione='CONTRIBUTO CONAI ASSOLTO']", namespaces=ns)
        for existing_line in existing_conai_lines:
            dati_beni.remove(existing_line)
        
        # Calcola il nuovo numero di linea
        num_linee = len(dati_beni.xpath("./DettaglioLinee"))
        
        # Crea il nuovo elemento DettaglioLinee per CONAI
        new_line = etree.Element("DettaglioLinee")
        etree.SubElement(new_line, "NumeroLinea").text = str(num_linee + 1)
        etree.SubElement(new_line, "Descrizione").text = "CONTRIBUTO CONAI ASSOLTO"
        etree.SubElement(new_line, "PrezzoUnitario").text = "0.0000000"
        etree.SubElement(new_line, "PrezzoTotale").text = "0.0000000"
        etree.SubElement(new_line, "AliquotaIVA").text = "22.00"
        
        # Assicurati che sia l'ultima linea
        dati_beni.append(new_line)
        
        self.conai_line = new_line
        self.viewer.total_lines += 1
        self.viewer.log("Aggiunta linea CONTRIBUTO CONAI ASSOLTO")
        
    def remove_conai(self):
        """Rimuove la linea CONAI dal documento"""
        if not self.viewer.xml_doc:
            return
        
        # Controlla se la linea esiste
        has_conai, conai_elem = self.has_conai()
        if not has_conai or conai_elem is None:
            self.viewer.log("Nessuna linea CONTRIBUTO CONAI ASSOLTO trovata")
            return
        
        # Rimuovi la linea
        parent = conai_elem.getparent()
        if parent is not None:
            parent.remove(conai_elem)
            self.conai_line = None
            self.viewer.total_lines -= 1
            self.viewer.log("Rimossa linea CONTRIBUTO CONAI ASSOLTO")
    
    def ensure_conai_position(self):
        """Assicura che la linea CONAI sia l'ultima prima del riepilogo"""
        if not self.viewer.xml_doc:
            return
        
        has_conai, conai_elem = self.has_conai()
        if not has_conai or conai_elem is None:
            return
        
        root = self.viewer.xml_doc.getroot()
        nsmap = root.nsmap
        ns = {}
        for prefix, uri in nsmap.items():
            if prefix is None:
                ns['p'] = uri
            else:
                ns[prefix] = uri
        
        # Trova il nodo DatiBeniServizi
        dati_beni = root.xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi", namespaces=ns)[0]
        
        # Trova il riepilogo
        riepilogo = dati_beni.xpath("./DatiRiepilogo")
        if not riepilogo:
            return
        
        # Rimuovi la linea CONAI attuale
        parent = conai_elem.getparent()
        if parent:
            parent.remove(conai_elem)
        
        # Reinseriscila prima del riepilogo
        dati_beni.insert(dati_beni.index(riepilogo[0]), conai_elem)
        self.viewer.log("Riposizionata linea CONAI prima del riepilogo")

class FatturaViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestione Fatture Elettroniche")
        self.geometry("900x600")
        
        self.xml_path = None
        self.xsl_path = None
        self.xsl_files = []
        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        self.xml_doc = None  # Documento XML caricato
        self.edit_widgets = []  # Widget dell'editor
        # Dizionario per memorizzare le modifiche fatte sui campi della linea di dettaglio:
        # chiave: indice della linea, valore: dict {xpath: nuovo_valore}
        self.line_modifications = {}

        # Aggiungi il manager CONAI
        self.conai_manager = ConaiManager(self)

        
        self.create_widgets()
        self.find_xsl_files()



    def indent(self, elem, level=0):
        """ Applica indentazione ricorsiva all'albero XML per una formattazione leggibile. """
        i = "\n" + "  " * level  # Usa due spazi per livello di indentazione
        if len(elem):  # Se ha figli
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "  # Indenta il primo figlio
            for child in elem:
                self.indent(child, level + 1)  # Chiamata ricorsiva su ogni figlio
            if not elem.tail or not elem.tail.strip():
                elem.tail = i  # Indenta dopo l'elemento chiuso
        else:
            if not elem.tail or not elem.tail.strip():
                elem.tail = i  # Indenta dopo elementi senza figli


    def create_widgets(self):
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        left_frame = tk.Frame(main_frame, width=200)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        self.content_frame = tk.Frame(main_frame)
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Label(left_frame, text="File XML:").pack(anchor=tk.W, pady=(0, 5))
        xml_btn = tk.Button(left_frame, text="Seleziona Fattura XML", command=self.select_xml, width=20)
        xml_btn.pack(anchor=tk.W, pady=(0, 15))
        
        tk.Label(left_frame, text="Foglio di stile:").pack(anchor=tk.W, pady=(0, 5))
        self.xsl_var = tk.StringVar()
        self.xsl_dropdown = ttk.Combobox(left_frame, textvariable=self.xsl_var, width=20, state="readonly")
        self.xsl_dropdown["values"] = []
        self.xsl_dropdown.pack(anchor=tk.W, pady=(0, 15))
        self.xsl_dropdown.bind("<<ComboboxSelected>>", self.on_xsl_selected)
        
        view_btn = tk.Button(left_frame, text="Visualizza Fattura", command=self.transform_and_view, 
                             bg="#4CAF50", fg="white", width=20, padx=5, pady=5)
        view_btn.pack(anchor=tk.W, pady=(5, 5))
        
        edit_btn = tk.Button(left_frame, text="Modifica Fattura", command=self.edit_invoice, 
                             bg="#2196F3", fg="white", width=20, padx=5, pady=5)
        edit_btn.pack(anchor=tk.W, pady=(5, 5))
        
        info_frame = tk.LabelFrame(self.content_frame, text="Informazioni sui file")
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(info_frame, text="File XML:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.xml_label = tk.Label(info_frame, text="Nessun file selezionato")
        self.xml_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        tk.Label(info_frame, text="File XSL:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.xsl_label = tk.Label(info_frame, text="Nessun file selezionato")
        self.xsl_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        self.xsl_full_path_label = tk.Label(info_frame, text="", font=("", 8), fg="gray")
        self.xsl_full_path_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        
        self.log_frame = tk.LabelFrame(self.content_frame, text="Log")
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.editor_frame = tk.LabelFrame(self.content_frame, text="Modifica Fattura")
        # L'editor verrà mostrato solo in modalità modifica
        
        self.editor_canvas = tk.Canvas(self.editor_frame)
        editor_scrollbar = ttk.Scrollbar(self.editor_frame, orient="vertical", command=self.editor_canvas.yview)
        self.editor_scrollable_frame = ttk.Frame(self.editor_canvas)
        
        self.editor_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.editor_canvas.configure(scrollregion=self.editor_canvas.bbox("all"))
        )
        
        self.editor_canvas.create_window((0, 0), window=self.editor_scrollable_frame, anchor="nw")
        self.editor_canvas.configure(yscrollcommand=editor_scrollbar.set)
        
        self.editor_canvas.pack(side="left", fill="both", expand=True)
        editor_scrollbar.pack(side="right", fill="y")
        
        self.editor_buttons_frame = tk.Frame(self.editor_frame)
        self.editor_buttons_frame.pack(fill=tk.X, pady=5)
        
        self.save_btn = tk.Button(self.editor_buttons_frame, text="Salva XML", command=self.save_xml,
                                  bg="#FFC107", fg="black", padx=10, pady=5)
        self.save_btn.pack(side=tk.RIGHT, padx=5)
        
        self.cancel_btn = tk.Button(self.editor_buttons_frame, text="Annulla", command=self.cancel_edit,
                                    padx=10, pady=5)
        self.cancel_btn.pack(side=tk.RIGHT, padx=5)
        
        self.log("Applicazione avviata. Seleziona i file per iniziare.")
    
    def find_xsl_files(self):
        try:
            xsl_pattern = os.path.join(self.project_dir, "*.xsl")
            self.xsl_files = glob.glob(xsl_pattern)
            
            xsl_dir = os.path.join(self.project_dir, "xsl")
            if os.path.exists(xsl_dir) and os.path.isdir(xsl_dir):
                xsl_pattern = os.path.join(xsl_dir, "*.xsl")
                self.xsl_files.extend(glob.glob(xsl_pattern))
            
            if self.xsl_files:
                self.xsl_dropdown["values"] = [os.path.basename(f) for f in self.xsl_files]
                self.xsl_dropdown.current(0)
                self.xsl_path = self.xsl_files[0]
                self.update_xsl_labels(self.xsl_files[0])
                self.log(f"Trovati {len(self.xsl_files)} fogli di stile XSL")
        except Exception as e:
            self.log(f"Errore durante la ricerca dei file XSL: {str(e)}")
    
    def select_xml(self):
        filepath = filedialog.askopenfilename(
            title="Seleziona il file XML della fattura",
            filetypes=[("File XML", "*.xml")]
        )
        if filepath:
            self.xml_path = filepath
            self.xml_label.config(text=os.path.basename(filepath))
            self.log(f"File XML selezionato: {filepath}")
            try:
                self.xml_doc = etree.parse(filepath)
                self.log("File XML caricato con successo")
            except Exception as e:
                self.log(f"Errore nel caricamento del file XML: {str(e)}")
                self.xml_doc = None
    
    def on_xsl_selected(self, event):
        selected_index = self.xsl_dropdown.current()
        if selected_index >= 0 and selected_index < len(self.xsl_files):
            self.xsl_path = self.xsl_files[selected_index]
            self.update_xsl_labels(self.xsl_path)
            self.log(f"Foglio di stile selezionato: {self.xsl_path}")
    
    def update_xsl_labels(self, filepath):
        self.xsl_label.config(text=os.path.basename(filepath))
        self.xsl_full_path_label.config(text=filepath)
    
    def transform_and_view(self):
        if not self.xml_path:
            messagebox.showerror("Errore", "Seleziona il file XML della fattura")
            return
        if not self.xsl_path:
            messagebox.showerror("Errore", "Seleziona un foglio di stile XSL")
            return
        try:
            xml_doc = etree.parse(self.xml_path)
            xsl_doc = etree.parse(self.xsl_path)
            transformer = etree.XSLT(xsl_doc)
            result = transformer(xml_doc)
            fd, temp_path = tempfile.mkstemp(suffix='.html')
            with os.fdopen(fd, 'wb') as f:
                f.write(etree.tostring(result, pretty_print=True))
            webbrowser.open('file://' + temp_path)
            self.log("Trasformazione completata. Visualizzazione nel browser.")
        except Exception as e:
            self.log(f"Errore durante la trasformazione: {str(e)}")
            messagebox.showerror("Errore", f"Si è verificato un errore durante la trasformazione:\n{str(e)}")
    
    def edit_invoice(self):
        if not self.xml_path or not self.xml_doc:
            messagebox.showerror("Errore", "Seleziona prima un file XML valido")
            return
        
        for widget in self.edit_widgets:
            if widget.winfo_exists():
                widget.destroy()
        self.edit_widgets = []
        # Reset del dizionario per le modifiche delle linee
        self.line_modifications = {}
        
        self.log_frame.pack_forget()
        self.editor_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log("Scansione documento XML...")
        try:
            root = self.xml_doc.getroot()
            num_elements = len(root.xpath("//*"))
            self.log(f"Documento XML: {self.xml_path}")
            self.log(f"Numero di elementi: {num_elements}")
            ns = root.nsmap
            for prefix, uri in ns.items():
                prefix_str = prefix if prefix is not None else "(default)"
                self.log(f"Namespace {prefix_str}: {uri}")
        except Exception as e:
            self.log(f"Errore nell'analisi del documento XML: {str(e)}")
        
        self.create_edit_fields()
        self.log("Modalità modifica attivata")
    
    def try_find_element(self, path, namespaces):
        try:
            elements = self.xml_doc.getroot().xpath(path, namespaces=namespaces)
            if elements and len(elements) > 0:
                element = elements[0]
                return element, element.text or ""
            else:
                self.log(f"Elemento non trovato con il percorso: {path}")
                return None, ""
        except Exception as e:
            self.log(f"Errore nel trovare il campo {path}: {str(e)}")
            return None, ""
    
    def create_edit_fields(self):

        # All'inizio di create_edit_fields()
        self.adding_normal_line = False
        
        root = self.xml_doc.getroot()
        nsmap = root.nsmap
        self.log(f"Namespace trovati nel file XML: {nsmap}")
        
        main_prefix = None
        main_uri = None
        for prefix, uri in nsmap.items():
            if "fatture" in uri or "ivaservizi" in uri:
                main_prefix = prefix
                main_uri = uri
                break
        
        if main_prefix is None:
            if None in nsmap:
                main_prefix = None
                main_uri = nsmap[None]
            else:
                main_prefix = "p"
                main_uri = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
        
        ns = {}
        for prefix, uri in nsmap.items():
            if prefix is None:
                ns['p'] = uri
            else:
                ns[prefix] = uri
        
        if main_prefix not in ns and main_prefix is not None:
            ns[main_prefix] = main_uri
        
        self.log(f"Namespace mappati: {ns}")
        self.log(f"Namespace principale: {main_prefix} -> {main_uri}")
        
        def get_xpath(path, default_prefix='p'):
            if main_prefix is None:
                return path.replace("/p:", "/p:")
            elif main_prefix != 'p':
                return path.replace("/p:", f"/{main_prefix}:").replace("p:", f"{main_prefix}:")
            else:
                return path
        
        sections = [
            ("Dati Intestazione", [
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/DatiTrasmissione/IdTrasmittente/IdPaese"), "ID Paese"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/DatiTrasmissione/IdTrasmittente/IdCodice"), "ID Codice"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/DatiTrasmissione/ProgressivoInvio"), "Progressivo Invio"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/DatiTrasmissione/FormatoTrasmissione"), "Formato Trasmissione"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/DatiTrasmissione/CodiceDestinatario"), "Codice Destinatario")
            ]),
            ("Cedente/Prestatore", [
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/DatiAnagrafici/IdFiscaleIVA/IdPaese"), "ID Paese"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/DatiAnagrafici/IdFiscaleIVA/IdCodice"), "Partita IVA"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/DatiAnagrafici/Anagrafica/Denominazione"), "Denominazione"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/DatiAnagrafici/RegimeFiscale"), "Regime Fiscale"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/Sede/Indirizzo"), "Indirizzo"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/Sede/CAP"), "CAP"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/Sede/Comune"), "Comune"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/Sede/Provincia"), "Provincia"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/Sede/Nazione"), "Nazione")
            ]),
            ("Cessionario/Committente", [
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/DatiAnagrafici/IdFiscaleIVA/IdPaese"), "ID Paese"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/DatiAnagrafici/IdFiscaleIVA/IdCodice"), "Partita IVA"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/DatiAnagrafici/CodiceFiscale"), "Codice Fiscale"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/DatiAnagrafici/Anagrafica/Denominazione"), "Denominazione"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/Sede/Indirizzo"), "Indirizzo"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/Sede/CAP"), "CAP"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/Sede/Comune"), "Comune"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/Sede/Provincia"), "Provincia"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/Sede/Nazione"), "Nazione")
            ]),
            ("Dati Generali Documento", [
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiGenerali/DatiGeneraliDocumento/TipoDocumento"), "Tipo Documento"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiGenerali/DatiGeneraliDocumento/Divisa"), "Divisa"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiGenerali/DatiGeneraliDocumento/Data"), "Data"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiGenerali/DatiGeneraliDocumento/Numero"), "Numero"),
                (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiGenerali/DatiGeneraliDocumento/ImportoTotaleDocumento"), "Importo Totale")
            ])
        ]
        
        row = 0
        self.edit_widgets = []
        self.edit_fields = {}
        for section_title, fields in sections:
            section_frame = tk.LabelFrame(self.editor_scrollable_frame, text=section_title)
            section_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
            self.edit_widgets.append(section_frame)
            row += 1
            for i, (xpath, label) in enumerate(fields):
                element, value = self.try_find_element(xpath, ns)
                label_widget = tk.Label(section_frame, text=label + ":")
                label_widget.grid(row=i, column=0, sticky="w", padx=5, pady=2)
                entry_widget = tk.Entry(section_frame, width=40)
                entry_widget.insert(0, value)
                entry_widget.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
                self.edit_fields[xpath] = {"widget": entry_widget, "element": element}
                self.edit_widgets.extend([label_widget, entry_widget])
        
        # Gestione dei campi per DettaglioLinee
        self.line_row = row
        self.current_line_index = 0
        
        def get_num_linee():


            try:
                linee = root.xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee", namespaces=ns)
                return len(linee)
            except Exception as e:
                self.log(f"Errore nel contare le linee: {str(e)}")
                return 0

        
        self.total_lines = get_num_linee()
        self.log(f"Trovate {self.total_lines} linee di dettaglio")
    
        #self.save_current_line_data = save_current_line_data
        
        self.update_line_fields = self.update_line_fields
        
        self.update_line_fields()
        row += 1






    # Prima di creare la checkbox CONAI
        has_conai, conai_element = self.conai_manager.has_conai()

        # Variabile per la checkbox
        self.conai_var = tk.BooleanVar()
        self.conai_var.set(has_conai)  # Imposta lo stato iniziale basato sulla presenza della linea CONAI

        # Funzione per gestire il cambio di stato della checkbox
        def toggle_conai():
            if self.conai_var.get():
                # Se la checkbox è selezionata e non c'è già una linea CONAI
                if not self.conai_manager.has_conai()[0]:
                    self.log("Attivazione linea CONTRIBUTO CONAI ASSOLTO")
                    self.conai_manager.add_conai()
            else:
                # Se la checkbox è deselezionata e c'è una linea CONAI
                if self.conai_manager.has_conai()[0]:
                    self.log("Rimozione linea CONTRIBUTO CONAI ASSOLTO")
                    self.conai_manager.remove_conai()
            
            # Aggiorna l'interfaccia dopo la modifica
            self.update_line_fields()
            self.update_nav_buttons()

        # Checkbox per il contributo CONAI
        conai_check = tk.Checkbutton(conai_frame, text="Includi linea CONTRIBUTO CONAI ASSOLTO", 
                                variable=self.conai_var, command=toggle_conai,
                                padx=5, pady=5, font=("", 10, "bold"))
        conai_check.pack(side=tk.LEFT)
        self.edit_widgets.append(conai_check)



        row += 1

        nav_frame = tk.Frame(self.editor_scrollable_frame)
        nav_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10)
        self.edit_widgets.append(nav_frame)
        
        row += 1
        
        
        self.prev_btn = tk.Button(nav_frame, text="◀ Prec", command=self.prev_line)
        self.prev_btn.pack(side=tk.LEFT, padx=5)
        
        self.next_btn = tk.Button(nav_frame, text="Succ ▶", command=self.next_line)
        self.next_btn.pack(side=tk.LEFT, padx=5)
        
        self.line_label = tk.Label(nav_frame, text=f"Linea {self.current_line_index + 1} di {self.total_lines}")
        self.line_label.pack(side=tk.LEFT, padx=10)
        
        add_btn = tk.Button(nav_frame, text="➕ Aggiungi", command=self.add_normal_line, bg="#4CAF50", fg="white")
        add_btn.pack(side=tk.RIGHT, padx=5)
        
        del_btn = tk.Button(nav_frame, text="➖ Elimina", command=self.delete_line, bg="#F44336", fg="white")
        del_btn.pack(side=tk.RIGHT, padx=5)
        
        self.update_nav_buttons()
        
        riepilogo_frame = tk.LabelFrame(self.editor_scrollable_frame, text="Dati Riepilogo")
        riepilogo_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        self.edit_widgets.append(riepilogo_frame)
        row += 1
        
        riepilogo_fields = [
            (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DatiRiepilogo/AliquotaIVA"), "Aliquota IVA"),
            (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DatiRiepilogo/ImponibileImporto"), "Imponibile"),
            (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DatiRiepilogo/Imposta"), "Imposta"),
            (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DatiRiepilogo/EsigibilitaIVA"), "Esigibilità IVA")
        ]
        
        for i, (xpath, label) in enumerate(riepilogo_fields):
            element, value = self.try_find_element(xpath, ns)
            label_widget = tk.Label(riepilogo_frame, text=label + ":")
            label_widget.grid(row=i, column=0, sticky="w", padx=5, pady=2)
            entry_widget = tk.Entry(riepilogo_frame, width=40)
            entry_widget.insert(0, value)
            entry_widget.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
            self.edit_fields[xpath] = {"widget": entry_widget, "element": element}
            self.edit_widgets.extend([label_widget, entry_widget])
        
        pagamento_frame = tk.LabelFrame(self.editor_scrollable_frame, text="Dati Pagamento")
        pagamento_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        self.edit_widgets.append(pagamento_frame)
        row += 1
        
        pagamento_fields = [
            (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiPagamento/CondizioniPagamento"), "Condizioni Pagamento"),
            (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiPagamento/DettaglioPagamento/ModalitaPagamento"), "Modalità Pagamento"),
            (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiPagamento/DettaglioPagamento/DataScadenzaPagamento"), "Data Scadenza"),
            (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiPagamento/DettaglioPagamento/ImportoPagamento"), "Importo Pagamento"),
            (get_xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiPagamento/DettaglioPagamento/CodicePagamento"), "Codice Pagamento")
        ]
        
        for i, (xpath, label) in enumerate(pagamento_fields):
            element, value = self.try_find_element(xpath, ns)
            label_widget = tk.Label(pagamento_frame, text=label + ":")
            label_widget.grid(row=i, column=0, sticky="w", padx=5, pady=2)
            entry_widget = tk.Entry(pagamento_frame, width=40)
            entry_widget.insert(0, value)
            entry_widget.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
            self.edit_fields[xpath] = {"widget": entry_widget, "element": element}
            self.edit_widgets.extend([label_widget, entry_widget])
        
        tree_btn_frame = tk.Frame(self.editor_scrollable_frame)
        tree_btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        self.edit_widgets.append(tree_btn_frame)
        
        tree_btn = tk.Button(tree_btn_frame, text="Visualizza struttura XML completa", 
                             command=self.show_xml_tree, bg="#607D8B", fg="white", padx=10, pady=5)
        tree_btn.pack(pady=5)
        self.edit_widgets.append(tree_btn)
        
        self.editor_scrollable_frame.update_idletasks()
        self.editor_canvas.config(width=self.editor_scrollable_frame.winfo_reqwidth())
    
    def on_line_field_change(self, event, xpath):
        """Salva il nuovo valore per il campo della linea corrente quando perde il focus."""
        if self.current_line_index not in self.line_modifications:
            self.line_modifications[self.current_line_index] = {}
        self.line_modifications[self.current_line_index][xpath] = event.widget.get()
    
    def show_xml_tree(self):
        if not self.xml_doc:
            messagebox.showerror("Errore", "Nessun documento XML caricato")
            return
        tree_window = tk.Toplevel(self)
        tree_window.title("Struttura XML")
        tree_window.geometry("800x600")
        frame = tk.Frame(tree_window)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget = tk.Text(frame, wrap=tk.NONE, yscrollcommand=scrollbar.set)
        text_widget.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        xml_string = etree.tostring(self.xml_doc, pretty_print=True, encoding='utf-8').decode('utf-8')
        text_widget.insert(tk.END, xml_string)
        text_widget.config(state=tk.DISABLED)
    


    def save_xml(self):
        if not self.xml_doc:
            return

        # Salva eventuali modifiche della linea corrente
        if hasattr(self, 'save_current_line_data'):
            self.save_current_line_data()
        
        # Aggiorna i campi generali
        modifiche_effettuate = []
        for xpath, field_data in list(self.edit_fields.items()):
            widget = field_data["widget"]
            element = field_data["element"]
            try:
                new_value = widget.get()
            except (tk.TclError, AttributeError):
                continue
            if element is not None:
                old_value = element.text or ""
                if old_value != new_value:
                    element.text = new_value
                    element_name = element.tag.split('}')[-1]
                    modifiche_effettuate.append((element_name, old_value, new_value))
        
        # Aggiorna anche le modifiche delle linee
        for line_index, line_data in self.line_modifications.items():
            for xpath, new_value in line_data.items():
                elements = self.xml_doc.getroot().xpath(xpath, namespaces=self.xml_doc.getroot().nsmap)
                if elements:
                    elements[0].text = new_value
        
        output_path = filedialog.asksaveasfilename(
            title="Salva XML modificato",
            defaultextension=".xml",
            filetypes=[("File XML", "*.xml")],
            initialfile=os.path.basename(self.xml_path)
        )
        
        if output_path:
            try:

                # Applica indentazione prima di salvare
                self.indent(self.xml_doc.getroot())
                # Genera l'XML formattato usando pretty_print=True
                new_xml = etree.tostring(self.xml_doc, pretty_print=True, encoding="UTF-8", xml_declaration=True).decode("utf-8")
                # Sostituisci eventuali newline multipli tra </DettaglioLinee> e <DatiRiepilogo> (o p:DatiRiepilogo, ecc.) con una newline seguita da 6 spazi
                new_xml = re.sub(r'(</DettaglioLinee>)(\r?\n)+(<(?:\w+:)?DatiRiepilogo>)', r'\1\n      \3', new_xml)
                # Se non c'è nessuna newline, forzala con 6 spazi
                new_xml = re.sub(r'(</DettaglioLinee>)(<(?:\w+:)?DatiRiepilogo>)', r'\1\n      \2', new_xml)



                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(new_xml)
                
                self.log(f"File salvato con successo: {output_path}")
                
                #if modifiche_effettuate:
                #    riepilogo = "Modifiche effettuate:\n\n"
                #    for element_name, old_value, new_value in modifiche_effettuate:
                #        riepilogo += f"• {element_name}: '{old_value}' → '{new_value}'\n"
                #    messagebox.showinfo("Salvataggio completato", f"Il file XML è stato salvato con successo.\n\n{riepilogo}")
                #else:
                #    messagebox.showinfo("Salvataggio completato", "Il file XML è stato salvato, ma nessuna modifica è stata rilevata.")
                

                messagebox.showinfo("Salvataggio completato", f"Il file XML è stato salvato con successo.")
                self.cancel_edit()
                
                #if messagebox.askyesno("Apertura file", "Vuoi caricare il file modificato?"):
                #    self.xml_path = output_path
                #    try:
                #        self.xml_doc = etree.parse(output_path)
                #        self.xml_label.config(text=os.path.basename(output_path))
                #        self.log(f"File XML caricato: {output_path}")
                #    except Exception as e:
                #        self.log(f"Errore nel caricamento del file modificato: {str(e)}")
                #        messagebox.showerror("Errore", f"Errore nel caricamento del file modificato:\n{str(e)}")
            except Exception as e:
                self.log(f"Errore nel salvataggio del file: {str(e)}")
                messagebox.showerror("Errore", f"Errore nel salvataggio del file:\n{str(e)}")






    def cancel_edit(self):
        self.editor_frame.pack_forget()
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log("Modalità modifica disattivata")
    
    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)



    def update_nav_buttons(self):
        self.prev_btn["state"] = "normal" if self.current_line_index > 0 else "disabled"
        self.next_btn["state"] = "normal" if self.current_line_index < self.total_lines - 1 else "disabled"
        self.line_label.config(text=f"Linea {self.current_line_index + 1} di {self.total_lines}")



    def update_line_fields(self):
        """Aggiorna i campi della linea corrente"""
        # All'inizio di update_line_fields()
        if hasattr(self, 'adding_normal_line') and self.adding_normal_line:
            self.log("Aggiungendo una linea normale, ignoro eventuali valori CONAI")

        # Ottieni il namespace
        root = self.xml_doc.getroot()
        nsmap = root.nsmap
        ns = {}
        for prefix, uri in nsmap.items():
            if prefix is None:
                ns['p'] = uri
            else:
                ns[prefix] = uri
                
        # Determina il prefisso del namespace
        main_prefix = None
        for prefix, uri in nsmap.items():
            if "fatture" in uri or "ivaservizi" in uri:
                main_prefix = prefix
                break
        
        # Funzione helper per ottenere il percorso XPath
        def get_xpath(path, default_prefix='p'):
            if main_prefix is None:
                return path.replace("/p:", "/p:")
            elif main_prefix != 'p':
                return path.replace("/p:", f"/{main_prefix}:").replace("p:", f"{main_prefix}:")
            else:
                return path
        
        # Rimuovi i vecchi campi se presenti
        if hasattr(self, 'line_frame') and self.line_frame in self.edit_widgets:
            self.line_frame.destroy()
            self.edit_widgets.remove(self.line_frame)
        
        # Rimuovi i vecchi riferimenti ai campi della linea
        for key in list(self.edit_fields.keys()):
            if "DettaglioLinee" in key:
                del self.edit_fields[key]
        
        # Crea un nuovo frame per la linea corrente
        self.line_frame = tk.LabelFrame(self.editor_scrollable_frame, 
                                    text=f"Dettaglio Linea {self.current_line_index + 1} di {self.total_lines}")
        self.line_frame.grid(row=self.line_row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        self.edit_widgets.append(self.line_frame)
        
        # Riempi con i campi della linea corrente
        idx = self.current_line_index + 1  # XPath usa indici 1-based
        fields = [
            (get_xpath(f"//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee[{idx}]/NumeroLinea"), "Numero Linea"),
            (get_xpath(f"//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee[{idx}]/Descrizione"), "Descrizione"),
            (get_xpath(f"//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee[{idx}]/Quantita"), "Quantità"),
            (get_xpath(f"//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee[{idx}]/UnitaMisura"), "Unità Misura"),
            (get_xpath(f"//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee[{idx}]/PrezzoUnitario"), "Prezzo Unitario"),
            (get_xpath(f"//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee[{idx}]/PrezzoTotale"), "Prezzo Totale"),
            (get_xpath(f"//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee[{idx}]/AliquotaIVA"), "Aliquota IVA")
        ]
        # Teniamo traccia dei widget di quantità e prezzo unitario
        quantita_widget = None
        prezzo_unitario_widget = None
        prezzo_totale_widget = None
        
      
        for i, (xpath, label) in enumerate(fields):
            element, value = self.try_find_element(xpath, ns)

            label_widget = tk.Label(self.line_frame, text=label + ":")
            label_widget.grid(row=i, column=0, sticky="w", padx=5, pady=2)
            
            entry_widget = tk.Entry(self.line_frame, width=40)
                        
            entry_widget.insert(0, value)
            entry_widget.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
            
            self.edit_fields[xpath] = {"widget": entry_widget, "element": element}
            self.edit_widgets.extend([label_widget, entry_widget])


            # Salva riferimento ai widget specifici
            if "Quantita" in xpath:
                quantita_widget = entry_widget
            elif "PrezzoUnitario" in xpath:
                prezzo_unitario_widget = entry_widget
            elif "PrezzoTotale" in xpath:
                prezzo_totale_widget = entry_widget




        # Funzione per calcolare il prezzo totale
        def calculate_total_price(*args):
            try:
                if quantita_widget and prezzo_unitario_widget and prezzo_totale_widget:
                    try:
                        # Converti in float usando il . come separatore decimale
                        quantita = float(quantita_widget.get().replace(',', '.'))
                        prezzo_unitario = float(prezzo_unitario_widget.get().replace(',', '.'))
                        
                        # Calcola il prezzo totale
                        prezzo_totale = quantita * prezzo_unitario
                        
                        # Formatta con 2 decimali (come richiesto dal formato FatturaPA)
                        prezzo_totale_formatted = f"{prezzo_totale:.7f}".replace('.', '.')
                        
                        # Aggiorna il campo del prezzo totale
                        prezzo_totale_widget.delete(0, tk.END)
                        prezzo_totale_widget.insert(0, prezzo_totale_formatted)
                    except (ValueError, AttributeError):
                        # In caso di errore, non fare nulla
                        pass
            except Exception as e:
                self.log(f"Errore nel calcolo del prezzo totale: {str(e)}")
        
        # Configuriamo le StringVar solo dopo aver inserito i valori nei widget
        if quantita_widget and prezzo_unitario_widget:
            # Leggi i valori attuali dai widget
            quantita_corrente = quantita_widget.get()
            prezzo_unitario_corrente = prezzo_unitario_widget.get()
            
            # Configura il tracciamento della modifica per quantità e prezzo unitario
            self.quantita_var = tk.StringVar(value=quantita_corrente)
            self.prezzo_unitario_var = tk.StringVar(value=prezzo_unitario_corrente)
            
            quantita_widget.config(textvariable=self.quantita_var)
            prezzo_unitario_widget.config(textvariable=self.prezzo_unitario_var)
            
            self.quantita_var.trace_add("write", calculate_total_price)
            self.prezzo_unitario_var.trace_add("write", calculate_total_price)


        # Carica eventuali modifiche salvate in precedenza
        if self.current_line_index in self.line_modifications:
            line_data = self.line_modifications[self.current_line_index]
            for xpath, value in line_data.items():
                if xpath in self.edit_fields:
                    self.edit_fields[xpath]["widget"].delete(0, tk.END)
                    self.edit_fields[xpath]["widget"].insert(0, value)
        # Aggiungi qui le nuove righe
        # Aggiorna lo stato della checkbox CONAI
        has_conai, _ = self.conai_manager.has_conai()
        self.conai_var.set(has_conai)
        
        # Assicurati che la linea CONAI sia sempre l'ultima
        if has_conai:
            self.conai_manager.ensure_conai_position()

    def save_current_line_data(self):
        """Salva le modifiche della linea corrente nel dizionario"""
        line_data = {}
        idx = self.current_line_index + 1  # XPath usa indici 1-based
        for xpath, field in self.edit_fields.items():
            # Assicurati di salvare solo i campi della linea corrente
            if f"DettaglioLinee[{idx}]" in xpath:
                line_data[xpath] = field["widget"].get()
        
        # Memorizza i dati solo se ci sono campi da salvare
        if line_data:
            self.line_modifications[self.current_line_index] = line_data
            self.log(f"Salvate modifiche alla linea {self.current_line_index + 1}")


    def add_normal_line(self):
        """Aggiunge una nuova linea di dettaglio normale al documento XML."""
        try:
            # Prima salviamo i dati della linea corrente
            self.save_current_line_data()
            
            if not self.xml_doc:
                self.log("Nessun documento XML caricato")
                return
            
            root = self.xml_doc.getroot()
            nsmap = root.nsmap
            
            # Configura namespace
            ns = {}
            for prefix, uri in nsmap.items():
                if prefix is None:
                    ns['p'] = uri
                else:
                    ns[prefix] = uri
            
            # Trova il nodo DatiBeniServizi
            dati_beni = root.xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi", namespaces=ns)[0]
            linee_esistenti = dati_beni.xpath("./DettaglioLinee")
            
            # Verifica se esiste una linea CONAI
            has_conai, conai_element = self.conai_manager.has_conai()
            
            # Determina dove inserire il nuovo nodo
            if has_conai and conai_element is not None:
                # Inserisci prima della linea CONAI
                insert_index = len(linee_esistenti) - 1
            else:
                # Se non c'è CONAI, inserisci alla fine
                insert_index = len(linee_esistenti)
            
            # Crea una nuova linea normale (mai CONAI)
            new_line = etree.Element("DettaglioLinee")
            
            # Aggiungi gli elementi figlio
            etree.SubElement(new_line, "NumeroLinea").text = str(len(linee_esistenti) + 1)
            etree.SubElement(new_line, "Descrizione").text = "Nuovo articolo"
            etree.SubElement(new_line, "Quantita").text = "1.0000000"
            etree.SubElement(new_line, "UnitaMisura").text = "NR"
            etree.SubElement(new_line, "PrezzoUnitario").text = "0.0000000"
            etree.SubElement(new_line, "PrezzoTotale").text = "0.0000000"
            etree.SubElement(new_line, "AliquotaIVA").text = "22.00"
            
            # Inserisci nel posto corretto
            if has_conai and conai_element is not None:
                dati_beni.insert(dati_beni.index(conai_element), new_line)
            else:
                dati_beni.append(new_line)
            
            # Incrementa il contatore delle linee
            self.total_lines += 1
            
            # Posizionati sulla nuova linea
            self.current_line_index = insert_index
            
            # Aggiorna l'interfaccia
            self.update_line_fields()
            self.update_nav_buttons()
            self.log(f"Aggiunta nuova linea normale")
            
        except Exception as e:
            self.log(f"Errore nell'aggiunta di una nuova linea: {str(e)}")
            self.log(traceback.format_exc())
            messagebox.showerror("Errore", f"Impossibile aggiungere una nuova linea:\n{str(e)}")

    def prev_line(self):
        """Sposta la visualizzazione alla linea precedente."""
        if self.current_line_index > 0:
            # Salva i dati della linea corrente prima di cambiare
            self.save_current_line_data()
            
            # Sposta l'indice alla linea precedente
            self.current_line_index -= 1
            
            # Aggiorna i campi dell'interfaccia
            self.update_line_fields()
            
            # Aggiorna lo stato dei pulsanti di navigazione
            self.update_nav_buttons()


    def next_line(self):
        """Sposta la visualizzazione alla linea successiva."""
        if self.current_line_index < self.total_lines - 1:
            # Salva i dati della linea corrente prima di cambiare
            self.save_current_line_data()
            
            # Sposta l'indice alla linea successiva
            self.current_line_index += 1
            
            # Aggiorna i campi dell'interfaccia
            self.update_line_fields()
            
            # Aggiorna lo stato dei pulsanti di navigazione
            self.update_nav_buttons()

    def delete_line(self):
        """Elimina la linea corrente dal documento XML."""
        if self.total_lines <= 1:
            messagebox.showwarning("Attenzione", "Impossibile eliminare l'unica linea presente")
            return
        
        try:
            root = self.xml_doc.getroot()
            nsmap = root.nsmap
            ns = {}
            for prefix, uri in nsmap.items():
                if prefix is None:
                    ns['p'] = uri
                else:
                    ns[prefix] = uri
            
            # Trova il nodo DatiBeniServizi
            dati_beni = root.xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi", namespaces=ns)[0]
            
            # Trova tutte le linee di dettaglio
            linee = dati_beni.xpath("./DettaglioLinee")
            
            # Rimuovi la linea corrente
            line_to_delete = linee[self.current_line_index]
            dati_beni.remove(line_to_delete)
            
            # Aggiorna il numero totale di linee
            self.total_lines -= 1
            
            # Ricalcola i NumeroLinea
            for i, linea in enumerate(dati_beni.xpath("./DettaglioLinee"), 1):
                numero_linea = linea.find("NumeroLinea")
                if numero_linea is not None:
                    numero_linea.text = str(i)
            
            # Aggiorna l'indice corrente
            if self.current_line_index >= self.total_lines:
                self.current_line_index = max(0, self.total_lines - 1)
            
            # Aggiorna il dizionario delle modifiche
            nuove_modifiche = {}
            for idx, modifiche in self.line_modifications.items():
                if idx < self.current_line_index:
                    nuove_modifiche[idx] = modifiche
                elif idx > self.current_line_index:
                    nuove_modifiche[idx - 1] = modifiche
            
            self.line_modifications = nuove_modifiche
            
            # Assicura che la linea CONAI sia sempre l'ultima
            has_conai, _ = self.conai_manager.has_conai()
            if has_conai:
                self.conai_manager.ensure_conai_position()
            
            # Aggiorna l'interfaccia
            self.update_line_fields()
            self.update_nav_buttons()
            self.log(f"Eliminata linea, ora ci sono {self.total_lines} linee")
        
        except Exception as e:
            self.log(f"Errore nell'eliminazione della linea: {str(e)}")
            messagebox.showerror("Errore", f"Impossibile eliminare la linea:\n{str(e)}")


if __name__ == "__main__":
    app = FatturaViewer()
    app.mainloop()
