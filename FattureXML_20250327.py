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
        # Dizionario per memorizzare le modifiche sui campi della linea di dettaglio:
        # chiave: indice della linea, valore: dict {xpath: nuovo_valore}
        self.line_modifications = {}
        

        # Inizializza le variabili per le linee
        self.normal_lines = []
        self.conai_line = None
        self.total_lines = 0
        self.current_line_index = 0        
        # Definizione statica del namespace:
        # Anche se nel file XML gli elementi non mostrano il prefisso, questi sono comunque in questo namespace.
        self.NS = {"p": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"}
        
        self.create_widgets()
        self.find_xsl_files()

    def indent(self, elem, level=0):
        """Applica indentazione ricorsiva all'albero XML per una formattazione leggibile."""
        i = "\n" + "  " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            for child in elem:
                self.indent(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if not elem.tail or not elem.tail.strip():
                elem.tail = i

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
        # L'editor viene mostrato solo in modalità modifica
        
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
        self.line_modifications = {}
        
        self.log_frame.pack_forget()
        self.editor_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log("Scansione documento XML...")
        try:
            root = self.xml_doc.getroot()
            num_elements = len(root.xpath("//*", namespaces=self.NS))
            self.log(f"Documento XML: {self.xml_path}")
            self.log(f"Numero di elementi: {num_elements}")
            self.log(f"Namespace utilizzato: {self.NS}")
        except Exception as e:
            self.log(f"Errore nell'analisi del documento XML: {str(e)}")
        
        self.create_edit_fields()

        # Dopo aver creato i campi, inizializza i totali
        self.update_riepilogo_totals()        
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
        root = self.xml_doc.getroot()
        ns = self.NS
        
        sections = [
            ("Dati Intestazione", [
                ("//p:FatturaElettronica/FatturaElettronicaHeader/DatiTrasmissione/IdTrasmittente/IdPaese", "ID Paese"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/DatiTrasmissione/IdTrasmittente/IdCodice", "ID Codice"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/DatiTrasmissione/ProgressivoInvio", "Progressivo Invio"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/DatiTrasmissione/FormatoTrasmissione", "Formato Trasmissione"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/DatiTrasmissione/CodiceDestinatario", "Codice Destinatario")
            ]),
            ("Cedente/Prestatore", [
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/DatiAnagrafici/IdFiscaleIVA/IdPaese", "ID Paese"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/DatiAnagrafici/IdFiscaleIVA/IdCodice", "Partita IVA"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/DatiAnagrafici/Anagrafica/Denominazione", "Denominazione"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/DatiAnagrafici/RegimeFiscale", "Regime Fiscale"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/Sede/Indirizzo", "Indirizzo"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/Sede/CAP", "CAP"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/Sede/Comune", "Comune"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/Sede/Provincia", "Provincia"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore/Sede/Nazione", "Nazione")
            ]),
            ("Cessionario/Committente", [
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/DatiAnagrafici/IdFiscaleIVA/IdPaese", "ID Paese"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/DatiAnagrafici/IdFiscaleIVA/IdCodice", "Partita IVA"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/DatiAnagrafici/CodiceFiscale", "Codice Fiscale"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/DatiAnagrafici/Anagrafica/Denominazione", "Denominazione"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/Sede/Indirizzo", "Indirizzo"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/Sede/CAP", "CAP"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/Sede/Comune", "Comune"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/Sede/Provincia", "Provincia"),
                ("//p:FatturaElettronica/FatturaElettronicaHeader/CessionarioCommittente/Sede/Nazione", "Nazione")
            ]),
            ("Dati Generali Documento", [
                ("//p:FatturaElettronica/FatturaElettronicaBody/DatiGenerali/DatiGeneraliDocumento/TipoDocumento", "Tipo Documento"),
                ("//p:FatturaElettronica/FatturaElettronicaBody/DatiGenerali/DatiGeneraliDocumento/Divisa", "Divisa"),
                ("//p:FatturaElettronica/FatturaElettronicaBody/DatiGenerali/DatiGeneraliDocumento/Data", "Data"),
                ("//p:FatturaElettronica/FatturaElettronicaBody/DatiGenerali/DatiGeneraliDocumento/Numero", "Numero"),
                ("//p:FatturaElettronica/FatturaElettronicaBody/DatiGenerali/DatiGeneraliDocumento/ImportoTotaleDocumento", "Importo Totale")
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
                element, value = self.try_find_element(xpath, self.NS)
                label_widget = tk.Label(section_frame, text=label + ":")
                label_widget.grid(row=i, column=0, sticky="w", padx=5, pady=2)
                entry_widget = tk.Entry(section_frame, width=40)
                entry_widget.insert(0, value)
                entry_widget.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
                self.edit_fields[xpath] = {"widget": entry_widget, "element": element}
                self.edit_widgets.extend([label_widget, entry_widget])
        
        # Aggiorna i dati delle linee
        self.refresh_lines_data()
        
        # Gestione dei campi per DettaglioLinee
        self.line_row = row
        self.current_line_index = 0
        
        if not hasattr(self, 'total_lines') or self.total_lines == 0:
            self.total_lines = len(self.normal_lines)
        
        self.log(f"Trovate {self.total_lines} linee di dettaglio normali")
        
        self.update_line_fields()
        row += 1

        # Checkbox per la linea CONAI
        conai_frame = tk.Frame(self.editor_scrollable_frame)
        conai_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        self.edit_widgets.append(conai_frame)

        self.conai_var = tk.BooleanVar()
        self.conai_var.set(self.conai_line is not None)

        conai_check = tk.Checkbutton(conai_frame, text="Includi linea CONTRIBUTO CONAI ASSOLTO", 
                                    variable=self.conai_var, command=self.toggle_conai,
                                    padx=5, pady=5, font=("", 10, "bold"))
        conai_check.pack(side=tk.LEFT)
        self.edit_widgets.append(conai_check)

        row += 1

        nav_frame = tk.Frame(self.editor_scrollable_frame)
        nav_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10)
        self.edit_widgets.append(nav_frame)
        
        row += 1
        
        def prev_line():
            if self.current_line_index > 0:
                self.save_current_line_data()
                self.current_line_index -= 1
                self.update_line_fields()
                self.update_nav_buttons()
        
        def next_line():
            if self.current_line_index < self.total_lines - 1:
                self.save_current_line_data()
                self.current_line_index += 1
                self.update_line_fields()
                self.update_nav_buttons()

        self.prev_btn = tk.Button(nav_frame, text="◀ Prec", command=prev_line)
        self.prev_btn.pack(side=tk.LEFT, padx=5)
        
        self.next_btn = tk.Button(nav_frame, text="Succ ▶", command=next_line)
        self.next_btn.pack(side=tk.LEFT, padx=5)
        
        self.line_label = tk.Label(nav_frame, text=f"Linea {self.current_line_index + 1} di {self.total_lines}")
        self.line_label.pack(side=tk.LEFT, padx=10)
        
        add_btn = tk.Button(nav_frame, text="➕ Aggiungi", command=self.add_line, bg="#4CAF50", fg="white")
        add_btn.pack(side=tk.RIGHT, padx=5)
        
        del_btn = tk.Button(nav_frame, text="➖ Elimina", command=self.delete_line, bg="#F44336", fg="white")
        del_btn.pack(side=tk.RIGHT, padx=5)

        recalc_btn = tk.Button(nav_frame, text="🔄 Ricalcola Totali", 
                            command=self.update_riepilogo_totals, 
                            bg="#FFA500", fg="white")
        recalc_btn.pack(side=tk.RIGHT, padx=5)
        self.edit_widgets.append(recalc_btn)
                
        
        self.update_nav_buttons()
        
        riepilogo_frame = tk.LabelFrame(self.editor_scrollable_frame, text="Dati Riepilogo")
        riepilogo_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        self.edit_widgets.append(riepilogo_frame)
        row += 1
        
        riepilogo_fields = [
            ("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DatiRiepilogo/AliquotaIVA", "Aliquota IVA"),
            ("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DatiRiepilogo/ImponibileImporto", "Imponibile"),
            ("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DatiRiepilogo/Imposta", "Imposta"),
            ("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DatiRiepilogo/EsigibilitaIVA", "Esigibilità IVA")
        ]
        
        for i, (xpath, label) in enumerate(riepilogo_fields):
            element, value = self.try_find_element(xpath, self.NS)
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
            ("//p:FatturaElettronica/FatturaElettronicaBody/DatiPagamento/CondizioniPagamento", "Condizioni Pagamento"),
            ("//p:FatturaElettronica/FatturaElettronicaBody/DatiPagamento/DettaglioPagamento/ModalitaPagamento", "Modalità Pagamento"),
            ("//p:FatturaElettronica/FatturaElettronicaBody/DatiPagamento/DettaglioPagamento/DataScadenzaPagamento", "Data Scadenza"),
            ("//p:FatturaElettronica/FatturaElettronicaBody/DatiPagamento/DettaglioPagamento/ImportoPagamento", "Importo Pagamento"),
            ("//p:FatturaElettronica/FatturaElettronicaBody/DatiPagamento/DettaglioPagamento/CodicePagamento", "Codice Pagamento")
        ]
        
        for i, (xpath, label) in enumerate(pagamento_fields):
            element, value = self.try_find_element(xpath, self.NS)
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

        if hasattr(self, 'save_current_line_data'):
            self.save_current_line_data()
        
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
        
        for line_index, line_data in self.line_modifications.items():
            for xpath, new_value in line_data.items():
                elements = self.xml_doc.getroot().xpath(xpath, namespaces=self.NS)
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
                self.indent(self.xml_doc.getroot())
                new_xml = etree.tostring(self.xml_doc, pretty_print=True, encoding="UTF-8", xml_declaration=True).decode("utf-8")
                new_xml = re.sub(r'(</DettaglioLinee>)(\r?\n)+(<(?:\w+:)?DatiRiepilogo>)', r'\1\n      \3', new_xml)
                new_xml = re.sub(r'(</DettaglioLinee>)(<(?:\w+:)?DatiRiepilogo>)', r'\1\n      \2', new_xml)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(new_xml)
                
                self.log(f"File salvato con successo: {output_path}")
                messagebox.showinfo("Salvataggio completato", f"Il file XML è stato salvato con successo.")
                self.cancel_edit()
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
    


    def add_conai_line(self):
        try:
            # Verifica se la linea CONAI esiste già
            self.refresh_lines_data()
            if self.conai_line is not None:
                self.log("La linea CONTRIBUTO CONAI ASSOLTO è già presente")
                return
            
            # Ottieni il nodo DatiBeniServizi
            dati_beni = self.xml_doc.getroot().xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi", namespaces=self.NS)[0]
            
            # Crea la linea CONAI
            conai_line = etree.Element("DettaglioLinee")
            etree.SubElement(conai_line, "NumeroLinea").text = "0"  # Sarà aggiornato dopo
            etree.SubElement(conai_line, "Descrizione").text = "CONTRIBUTO CONAI ASSOLTO"
            etree.SubElement(conai_line, "PrezzoUnitario").text = "0.0000000"
            etree.SubElement(conai_line, "PrezzoTotale").text = "0.0000000"
            etree.SubElement(conai_line, "AliquotaIVA").text = "22.00"
            
            # Inserisci prima di DatiRiepilogo se esiste
            riepilogo = dati_beni.xpath("./DatiRiepilogo", namespaces=self.NS)
            if riepilogo:
                dati_beni.insert(dati_beni.index(riepilogo[0]), conai_line)
            else:
                dati_beni.append(conai_line)
            
            # Aggiorna i numeri delle linee
            self.update_line_numbers()
            
            # Aggiorna i dati e l'interfaccia
            self.refresh_lines_data()
            self.update_line_fields()
            self.update_nav_buttons()
            
            self.log("Aggiunta linea CONTRIBUTO CONAI ASSOLTO")
        except Exception as e:
            self.log(f"Errore nell'aggiunta della linea CONAI: {str(e)}")
            traceback.print_exc()
            
    def remove_conai_line(self):
        try:
            # Verifica se la linea CONAI esiste
            self.refresh_lines_data()
            if self.conai_line is None:
                self.log("Nessuna linea CONTRIBUTO CONAI ASSOLTO trovata")
                return
            
            # Rimuovi la linea CONAI
            parent = self.conai_line.getparent()
            parent.remove(self.conai_line)
            
            # Aggiorna i numeri delle linee
            self.update_line_numbers()
            
            # Aggiorna i dati e l'interfaccia
            self.refresh_lines_data()
            self.update_line_fields()
            self.update_nav_buttons()
            
            self.log("Rimossa linea CONTRIBUTO CONAI ASSOLTO")
        except Exception as e:
            self.log(f"Errore nella rimozione della linea CONAI: {str(e)}")
            traceback.print_exc()
        self.update_riepilogo_totals()

    def update_nav_buttons(self):
        self.prev_btn["state"] = "normal" if self.current_line_index > 0 else "disabled"
        self.next_btn["state"] = "normal" if self.current_line_index < self.total_lines - 1 else "disabled"
        self.line_label.config(text=f"Linea {self.current_line_index + 1} di {self.total_lines}")


    def update_line_fields(self):
        # Rimuovi il vecchio frame se esiste
        if hasattr(self, 'line_frame') and self.line_frame in self.edit_widgets:
            self.line_frame.destroy()
            self.edit_widgets.remove(self.line_frame)

        # Rimuovi vecchi campi delle linee di dettaglio
        for key in list(self.edit_fields.keys()):
            if "DettaglioLinee" in key:
                del self.edit_fields[key]
        
        # Aggiorna i dati delle linee dal documento XML
        self.refresh_lines_data()
        
        # Crea il nuovo frame
        self.line_frame = tk.LabelFrame(self.editor_scrollable_frame, 
                                    text=f"Dettaglio Linea {self.current_line_index + 1} di {self.total_lines}")
        self.line_frame.grid(row=self.line_row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        self.edit_widgets.append(self.line_frame)
        
        # Se non ci sono linee normali, mostra un messaggio
        if self.total_lines == 0:
            tk.Label(self.line_frame, text="Nessuna linea di dettaglio presente").grid(row=0, column=0)
            return
        
        # Ottieni la linea corrente (solo dalle linee normali)
        current_line = self.normal_lines[self.current_line_index]
        
        # Definisci i campi da mostrare
        fields = [
            ("NumeroLinea", "Numero Linea"),
            ("Descrizione", "Descrizione"),
            ("Quantita", "Quantità"),
            ("UnitaMisura", "Unità Misura"),
            ("PrezzoUnitario", "Prezzo Unitario"),
            ("PrezzoTotale", "Prezzo Totale"),
            ("AliquotaIVA", "Aliquota IVA")
        ]
        
        # Variabili per tenere traccia dei widget specifici
        quantita_widget = None
        prezzo_unitario_widget = None
        prezzo_totale_widget = None
        
        # Funzione di validazione per campi numerici
        def validate_numeric_field(field_name, text):
            # Permette stringa vuota (per cancellare tutto)
            if text == "":
                return True
            
            # Permette solo numeri e un singolo punto
            if not all(c.isdigit() or c == '.' for c in text):
                return False
            
            # Controlla che ci sia al massimo un punto
            if text.count('.') > 1:
                return False
            
            # Se contiene un punto, controlla le regole per la parte decimale
            if '.' in text:
                integer_part, decimal_part = text.split('.')
                
                # Per Quantita e PrezzoUnitario, limita la parte intera a 15 cifre
                if field_name != "PrezzoTotale" and len(integer_part) > 15:
                    return False
                    
                # Non blocca la digitazione in corso nella parte decimale
                if len(decimal_part) > 7:
                    return False
            else:
                # Se non c'è il punto, controlla solo la parte intera per Quantita e PrezzoUnitario
                if field_name != "PrezzoTotale" and len(text) > 15:
                    return False
                
            return True
        
        # Funzione per formattare il campo quando perde il focus
        def format_numeric_field(event):
            widget = event.widget
            field_name = widget.field_name if hasattr(widget, 'field_name') else ""
            current_value = widget.get().replace(',', '.')
            
            try:
                # Se il campo è vuoto, imposta 0
                if not current_value:
                    formatted_value = "0.0000000"
                    widget.delete(0, tk.END)
                    widget.insert(0, formatted_value)
                    widget.config(bg="white")
                    return
                
                # Separa parte intera e decimale
                if '.' in current_value:
                    integer_part, decimal_part = current_value.split('.')
                else:
                    integer_part, decimal_part = current_value, ""
                
                # Rimuovi zeri iniziali dalla parte intera (tranne lo zero da solo)
                if integer_part != "0":
                    integer_part = integer_part.lstrip("0") or "0"
                
                # Formatta con esattamente 7 decimali
                decimal_part = (decimal_part + "0000000")[:7]
                
                # Ricostruisci il valore formattato
                formatted_value = f"{integer_part}.{decimal_part}"
                
                # Aggiorna il campo
                widget.delete(0, tk.END)
                widget.insert(0, formatted_value)
                widget.config(bg="white")  # Resetta lo sfondo
                
                # Scatena il calcolo del prezzo totale se applicabile
                if widget in [quantita_widget, prezzo_unitario_widget]:
                    calculate_total_price()
                    
            except Exception as e:
                # In caso di errore, evidenzia il campo
                widget.config(bg="#ffcccc")  # Sfondo rosso chiaro
                self.log(f"Errore nella formattazione del campo: {str(e)}")
        
        # Crea i campi
        for i, (field_name, label) in enumerate(fields):
            element = current_line.find(field_name)
            value = element.text if element is not None else ""
            
            label_widget = tk.Label(self.line_frame, text=label + ":")
            label_widget.grid(row=i, column=0, sticky="w", padx=5, pady=2)
            
            entry_widget = tk.Entry(self.line_frame, width=40)
            
            # Applica validazione per campi numerici
            if field_name in ["Quantita", "PrezzoUnitario", "PrezzoTotale"]:
                # Salva il nome del campo nel widget per poterlo recuperare nel validatore
                entry_widget.field_name = field_name
                
                # Crea un validatore specifico per questo campo
                vcmd = self.register(lambda text, fname=field_name: validate_numeric_field(fname, text))
                entry_widget.config(validate="key", validatecommand=(vcmd, '%P'))
                entry_widget.bind("<FocusOut>", format_numeric_field)
                
                # Formatta il valore iniziale
                if value:
                    try:
                        # Converte il valore esistente nel formato corretto
                        if '.' in value:
                            int_part, dec_part = value.split('.')
                            # Rimuovi zeri iniziali dalla parte intera (tranne lo zero da solo)
                            if int_part != "0":
                                int_part = int_part.lstrip("0") or "0"
                            # Formatta con esattamente 7 decimali
                            dec_part = (dec_part + "0000000")[:7]
                            value = f"{int_part}.{dec_part}"
                        else:
                            value = f"{value.lstrip('0') or '0'}.0000000"
                    except:
                        value = "0.0000000"
            
            entry_widget.insert(0, value)
            entry_widget.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
            
            # Memorizza il riferimento al campo e all'elemento XML
            field_key = f"current_line.{field_name}"
            self.edit_fields[field_key] = {"widget": entry_widget, "element": element}
            self.edit_widgets.extend([label_widget, entry_widget])
            
            # Salva i riferimenti ai widget specifici
            if field_name == "Quantita":
                quantita_widget = entry_widget
            elif field_name == "PrezzoUnitario":
                prezzo_unitario_widget = entry_widget
            elif field_name == "PrezzoTotale":
                prezzo_totale_widget = entry_widget
                # Il prezzo totale viene calcolato automaticamente, quindi possiamo disabilitarlo
                # entry_widget.config(state="readonly", readonlybackground="#f0f0f0")
        
        # Configura il calcolo automatico del prezzo totale
        if quantita_widget and prezzo_unitario_widget and prezzo_totale_widget:
            def calculate_total_price(*args):
                try:
                    quantita_str = quantita_widget.get().replace(',', '.')
                    prezzo_unitario_str = prezzo_unitario_widget.get().replace(',', '.')
                    
                    # Verifica che i valori non siano vuoti
                    if quantita_str and prezzo_unitario_str:
                        quantita = float(quantita_str)
                        prezzo_unitario = float(prezzo_unitario_str)
                        prezzo_totale = quantita * prezzo_unitario
                        
                        # Formatta il risultato con 7 decimali
                        prezzo_totale_formatted = f"{prezzo_totale:.7f}"
                        
                        # Aggiorna il campo prezzo totale
                        prezzo_totale_widget.delete(0, tk.END)
                        prezzo_totale_widget.insert(0, prezzo_totale_formatted)

                        # Aggiorna anche l'elemento XML corrispondente
                        for field_key, field_data in self.edit_fields.items():
                            if field_key == "current_line.PrezzoTotale" and field_data["element"] is not None:
                                field_data["element"].text = prezzo_totale_formatted
                                break
                        
                        # AGGIUNGI QUESTA RIGA: Aggiorna i totali nel riepilogo
                        self.after(100, self.update_riepilogo_totals)  # Usa after per evitare problemi di timing
                                                
                except (ValueError, AttributeError) as e:
                    # In caso di errore nel parsing dei numeri, non fare nulla
                    self.log(f"Errore nel calcolo del prezzo totale: {str(e)}")
            
            # Crea variabili StringVar per tracciare le modifiche
            self.quantita_var = tk.StringVar(value=quantita_widget.get())
            self.prezzo_unitario_var = tk.StringVar(value=prezzo_unitario_widget.get())
            
            # Collega le variabili ai widget
            quantita_widget.config(textvariable=self.quantita_var)
            prezzo_unitario_widget.config(textvariable=self.prezzo_unitario_var)
            
            # Aggiungi tracciatori di modifica
            self.quantita_var.trace_add("write", calculate_total_price)
            self.prezzo_unitario_var.trace_add("write", calculate_total_price)
            
            # Calcola il prezzo totale iniziale
            calculate_total_price()

    def save_current_line_data(self):
        line_data = {}
        
        # Assicurati che ci siano linee normali
        if self.total_lines <= 0 or self.current_line_index >= self.total_lines:
            return
        
        # Ottieni il riferimento alla linea corrente
        current_line = self.normal_lines[self.current_line_index]
        
        # Raccogli i valori dai campi di input
        for field_key, field_data in list(self.edit_fields.items()):
            if field_key.startswith("current_line."):
                field_name = field_key.split(".")[1]
                widget = field_data["widget"]
                element = field_data["element"]
                
                try:
                    value = widget.get()
                    
                    # Formatta i campi numerici prima del salvataggio
                    if field_name in ["Quantita", "PrezzoUnitario", "PrezzoTotale"]:
                        # Assicura che il valore sia nel formato corretto (15 cifre intere, 7 decimali)
                        if value:
                            if '.' in value:
                                int_part, dec_part = value.split('.')
                                # Limita la parte intera a 15 cifre
                                if field_name != "PrezzoTotale":
                                    int_part = int_part[-15:] if len(int_part) > 15 else int_part
                                # Assicura esattamente 7 decimali
                                dec_part = (dec_part + "0000000")[:7]
                                value = f"{int_part}.{dec_part}"
                            else:
                                # Se non c'è punto, aggiungi 7 zeri dopo il punto
                                value = f"{value}.0000000"
                    
                    # Aggiorna l'elemento XML
                    if element is not None:
                        element.text = value
                        self.log(f"Aggiornato campo {field_name}: {value}")
                    
                except Exception as e:
                    self.log(f"Errore nel salvataggio del campo {field_name}: {str(e)}")
        
        # Aggiorna i numeri delle linee
        self.update_line_numbers()
        
        # Aggiorna i totali nel riepilogo
        self.update_riepilogo_totals()

    def delete_line(self):
        # Aggiorna i dati delle linee per avere informazioni aggiornate
        self.refresh_lines_data()
        
        if self.total_lines <= 0:
            messagebox.showwarning("Attenzione", "Nessuna linea da eliminare")
            return
        
        try:
            # Verifica se l'indice è valido
            if self.current_line_index < 0 or self.current_line_index >= self.total_lines:
                self.log(f"Indice linea non valido: {self.current_line_index}")
                return
                
            # Ottieni la linea da eliminare (tra le linee normali)
            line_to_delete = self.normal_lines[self.current_line_index]
            
            # Elimina la linea
            parent = line_to_delete.getparent()
            parent.remove(line_to_delete)
            
            # Aggiorna i numeri delle linee
            self.update_line_numbers()
            
            # Aggiorna i dati e l'interfaccia
            self.refresh_lines_data()
            
            # Aggiusta l'indice corrente se necessario
            if self.current_line_index >= self.total_lines:
                self.current_line_index = max(0, self.total_lines - 1)
            
            self.update_line_fields()
            self.update_nav_buttons()
            
            self.log(f"Eliminata linea, ora ci sono {self.total_lines} linee normali")
        except Exception as e:
            self.log(f"Errore nell'eliminazione della linea: {str(e)}")
            traceback.print_exc()
            messagebox.showerror("Errore", f"Impossibile eliminare la linea:\n{str(e)}")
        self.update_riepilogo_totals()
            
    def add_line(self):
        try:
            # Ottieni il nodo padre
            dati_beni = self.xml_doc.getroot().xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi", namespaces=self.NS)[0]
            
            # Crea una nuova linea
            new_line = etree.Element("DettaglioLinee")
            etree.SubElement(new_line, "NumeroLinea").text = "0"  # Sarà aggiornato dopo
            etree.SubElement(new_line, "Descrizione").text = "Nuovo articolo"
            etree.SubElement(new_line, "Quantita").text = "1.0000000"
            etree.SubElement(new_line, "UnitaMisura").text = "NR"
            etree.SubElement(new_line, "PrezzoUnitario").text = "0.0000000"
            etree.SubElement(new_line, "PrezzoTotale").text = "0.0000000"
            etree.SubElement(new_line, "AliquotaIVA").text = "22.00"
            
            # Aggiorna i dati delle linee per avere informazioni aggiornate
            self.refresh_lines_data()
            
            # Decide dove inserire la linea:
            # 1. Se c'è una linea CONAI, inserisci prima della linea CONAI
            # 2. Se non c'è una linea CONAI, inserisci prima di DatiRiepilogo
            # 3. Altrimenti, inserisci alla fine di DatiBeniServizi
            
            if self.conai_line is not None:
                dati_beni.insert(dati_beni.index(self.conai_line), new_line)
                self.log("Inserita nuova linea prima della linea CONAI")
            else:
                riepilogo = dati_beni.xpath("./DatiRiepilogo", namespaces=self.NS)
                if riepilogo:
                    dati_beni.insert(dati_beni.index(riepilogo[0]), new_line)
                    self.log("Inserita nuova linea prima di DatiRiepilogo")
                else:
                    dati_beni.append(new_line)
                    self.log("Inserita nuova linea alla fine di DatiBeniServizi")
            
            # Aggiorna i numeri delle linee
            self.update_line_numbers()
            
            # Aggiorna i dati e l'interfaccia
            self.refresh_lines_data()
            
            # Posizionati sulla nuova linea
            # Dato che la linea è stata aggiunta alla fine delle linee normali
            self.current_line_index = self.total_lines - 1
            
            self.update_line_fields()
            self.update_nav_buttons()
            
            self.log(f"Aggiunta nuova linea in posizione {self.current_line_index + 1}")
        except Exception as e:
            self.log(f"Errore nell'aggiunta di una nuova linea: {str(e)}")
            traceback.print_exc()
            messagebox.showerror("Errore", f"Impossibile aggiungere una nuova linea:\n{str(e)}")
        self.update_riepilogo_totals()

            
    def update_line_numbers(self):
        try:
            # Ottieni tutte le linee di dettaglio
            linee = self.xml_doc.getroot().xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee", namespaces=self.NS)
            
            # Aggiorna il numero di ogni linea
            for i, linea in enumerate(linee, 1):  # inizia da 1
                numero_linea = linea.find("NumeroLinea")
                if numero_linea is not None:
                    numero_linea.text = str(i)
                else:
                    etree.SubElement(linea, "NumeroLinea").text = str(i)
            
            self.log(f"Numeri delle linee aggiornati (1-{len(linee)})")
        except Exception as e:
            self.log(f"Errore nell'aggiornamento dei numeri delle linee: {str(e)}")
            traceback.print_exc()


    def refresh_lines_data(self):
        """
        Aggiorna i dati delle linee dal documento XML, escludendo la linea CONAI
        """
        try:
            root = self.xml_doc.getroot()
            all_lines = root.xpath("//p:FatturaElettronica/FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee", namespaces=self.NS)
            
            # Dividi tra linee normali e linea CONAI
            self.normal_lines = []
            self.conai_line = None
            
            for line in all_lines:
                descr = line.find("Descrizione")
                if descr is not None and descr.text and "CONTRIBUTO CONAI ASSOLTO" in descr.text.upper():
                    self.conai_line = line
                else:
                    self.normal_lines.append(line)
            
            self.total_lines = len(self.normal_lines)
            
            # Aggiorna lo stato della checkbox CONAI solo se esiste
            if hasattr(self, 'conai_var'):
                self.conai_var.set(self.conai_line is not None)
            
            # Assicurati che l'indice corrente sia valido
            if self.current_line_index >= self.total_lines:
                self.current_line_index = max(0, self.total_lines - 1)
            self.log(f"Aggiornati dati: {self.total_lines} linee normali, CONAI: {'presente' if self.conai_line is not None else 'assente'}")    
        except Exception as e:
            self.log(f"Errore nell'aggiornamento dei dati delle linee: {str(e)}")
            traceback.print_exc()

    def toggle_conai(self):
        """Gestisce l'attivazione/disattivazione della linea CONAI tramite checkbox"""
        if self.conai_var.get():
            self.log("Attivazione linea CONTRIBUTO CONAI ASSOLTO")
            self.add_conai_line()
        else:
            self.log("Rimozione linea CONTRIBUTO CONAI ASSOLTO")
            self.remove_conai_line()

    def update_riepilogo_totals(self):
        """
        Aggiorna automaticamente i totali nei dati di riepilogo basati sulle linee di dettaglio.
        """
        try:
            # Calcola la somma dei prezzi totali di tutte le linee
            total_amount = 0.0
            
            # Aggiorna i dati per assicurarci di avere le informazioni più recenti
            self.refresh_lines_data()
            
            # Somma i prezzi totali di tutte le linee normali
            for line in self.normal_lines:
                prezzo_totale_elem = line.find("PrezzoTotale")
                if prezzo_totale_elem is not None and prezzo_totale_elem.text:
                    try:
                        total_amount += float(prezzo_totale_elem.text)
                        self.log(f"Aggiunto prezzo: {prezzo_totale_elem.text}, totale parziale: {total_amount}")
                    except ValueError:
                        self.log(f"Errore nel convertire il prezzo totale: {prezzo_totale_elem.text}")
            
            # Formatta l'importo totale con 2 decimali
            total_amount_formatted = f"{total_amount:.2f}"
            self.log(f"Imponibile calcolato: {total_amount_formatted}")
            
            # Aggiorna direttamente nei campi dell'interfaccia se esistono
            for xpath, field_data in self.edit_fields.items():
                if "ImponibileImporto" in xpath and field_data["widget"].winfo_exists():
                    field_data["widget"].delete(0, tk.END)
                    field_data["widget"].insert(0, total_amount_formatted)
                    self.log(f"Aggiornato campo UI imponibile: {total_amount_formatted}")
                    
                    # Aggiorna anche l'elemento XML
                    if field_data["element"] is not None:
                        field_data["element"].text = total_amount_formatted
                        self.log(f"Aggiornato elemento XML imponibile: {total_amount_formatted}")
            
            # Calcola anche l'imposta e il totale documento
            aliquota_iva = 22.0  # Valore predefinito se non troviamo l'elemento
            
            # Cerca l'aliquota IVA nel documento
            for xpath, field_data in self.edit_fields.items():
                if "AliquotaIVA" in xpath and "DatiRiepilogo" in xpath and field_data["widget"].winfo_exists():
                    try:
                        aliquota_iva = float(field_data["widget"].get())
                        self.log(f"Trovata aliquota IVA: {aliquota_iva}%")
                        break
                    except ValueError:
                        pass
            
            # Calcola l'imposta
            imposta = total_amount * (aliquota_iva / 100.0)
            imposta_formatted = f"{imposta:.2f}"
            
            # Aggiorna il campo imposta nell'interfaccia
            for xpath, field_data in self.edit_fields.items():
                if "Imposta" in xpath and field_data["widget"].winfo_exists():
                    field_data["widget"].delete(0, tk.END)
                    field_data["widget"].insert(0, imposta_formatted)
                    self.log(f"Aggiornato campo UI imposta: {imposta_formatted}")
                    
                    # Aggiorna anche l'elemento XML
                    if field_data["element"] is not None:
                        field_data["element"].text = imposta_formatted
                        self.log(f"Aggiornato elemento XML imposta: {imposta_formatted}")
            
            # Calcola e aggiorna l'importo totale documento
            importo_totale = total_amount + imposta
            importo_totale_formatted = f"{importo_totale:.2f}"
            
            for xpath, field_data in self.edit_fields.items():
                if "ImportoTotaleDocumento" in xpath and field_data["widget"].winfo_exists():
                    field_data["widget"].delete(0, tk.END)
                    field_data["widget"].insert(0, importo_totale_formatted)
                    self.log(f"Aggiornato campo UI importo totale: {importo_totale_formatted}")
                    
                    # Aggiorna anche l'elemento XML
                    if field_data["element"] is not None:
                        field_data["element"].text = importo_totale_formatted
                        self.log(f"Aggiornato elemento XML importo totale: {importo_totale_formatted}")
            
            # Aggiorna anche il campo ImportoPagamento nei dati pagamento
            for xpath, field_data in self.edit_fields.items():
                if "ImportoPagamento" in xpath and field_data["widget"].winfo_exists():
                    field_data["widget"].delete(0, tk.END)
                    field_data["widget"].insert(0, importo_totale_formatted)
                    self.log(f"Aggiornato campo UI importo pagamento: {importo_totale_formatted}")
                    
                    # Aggiorna anche l'elemento XML
                    if field_data["element"] is not None:
                        field_data["element"].text = importo_totale_formatted
                        self.log(f"Aggiornato elemento XML importo pagamento: {importo_totale_formatted}")
            
        except Exception as e:
            self.log(f"Errore nell'aggiornamento dei totali: {str(e)}")
            traceback.print_exc() 
            
            
if __name__ == "__main__":
    app = FatturaViewer()
    app.mainloop()
