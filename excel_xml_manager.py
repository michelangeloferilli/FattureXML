import os
import tkinter as tk
from tkinter import filedialog, messagebox
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from lxml import etree
import re
import traceback
from openpyxl.utils import get_column_letter
import datetime

class ExcelXmlManager:
    """
    Classe per gestire l'interscambio di dati tra file XML delle fatture elettroniche
    e file Excel, permettendo di mantenere la struttura del file XML anche quando
    il modello originale non è più disponibile.
    """
    
    def __init__(self, parent, ns):
        """
        Inizializza il manager XML-Excel
        
        Args:
            parent: Riferimento alla classe principale per i log
            ns: Namespace XML da utilizzare
        """
        self.parent = parent
        self.NS = ns
        self.excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FattureXML.xlsx")
        self.sheet_name = "dati"
        self.tag_column = "A"
        self.value_column = "B"
        self.description_column = "C"
    
    def log(self, message):
        """
        Utilizza il metodo di log del parent se disponibile
        """
        if hasattr(self.parent, 'log') and callable(self.parent.log):
            self.parent.log(message)
        else:
            print(message)
    
    def export_xml_to_excel(self, xml_doc, excel_path=None):
        """
        Esporta tutti i dati dal file XML a un foglio Excel
        
        Args:
            xml_doc: Documento XML da esportare
            excel_path: Percorso del file Excel (opzionale)
        
        Returns:
            bool: True se l'operazione ha successo, False altrimenti
        """
        if excel_path:
            self.excel_path = excel_path
        
        try:
            # Controlla se il file Excel esiste
            if os.path.exists(self.excel_path):
                # Apri il workbook esistente
                wb = openpyxl.load_workbook(self.excel_path)
                self.log(f"File Excel esistente aperto: {self.excel_path}")
                
                # Controlla se il foglio dati esiste e rimuovilo
                if self.sheet_name in wb.sheetnames:
                    sheet = wb[self.sheet_name]
                    wb.remove(sheet)
                    self.log(f"Foglio '{self.sheet_name}' esistente rimosso")
            else:
                # Crea un nuovo workbook
                wb = openpyxl.Workbook()
                self.log(f"Nuovo file Excel creato")
                
                # Rimuovi il foglio di default
                default_sheet = wb.active
                wb.remove(default_sheet)
            
            # Crea un nuovo foglio dati
            sheet = wb.create_sheet(title=self.sheet_name)
            
            # Formattazione intestazioni
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            
            # Definisci l'intestazione
            sheet[f"{self.tag_column}1"] = "Tag XML"
            sheet[f"{self.value_column}1"] = "Valore"
            sheet[f"{self.description_column}1"] = "Descrizione"
            
            # Applica stile alle intestazioni
            for col in [self.tag_column, self.value_column, self.description_column]:
                cell = sheet[f"{col}1"]
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
            
            # Estrai tutti i nodi XML e i relativi valori
            root = xml_doc.getroot()
            rows = self._extract_nodes(root, "", 2)
            
            # Scrivi nel foglio Excel
            for tag_path, value, description, row in rows:
                sheet[f"{self.tag_column}{row}"] = tag_path
                sheet[f"{self.value_column}{row}"] = value
                sheet[f"{self.description_column}{row}"] = description
            
            # Imposta larghezza colonne
            sheet.column_dimensions[self.tag_column].width = 60
            sheet.column_dimensions[self.value_column].width = 30
            sheet.column_dimensions[self.description_column].width = 30
            
            # Salva il file Excel
            wb.save(self.excel_path)
            
            self.log(f"Esportazione XML in Excel completata. Righe scritte: {len(rows)}")
            return True
        
        except Exception as e:
            self.log(f"Errore nell'esportazione XML in Excel: {str(e)}")
            traceback.print_exc()
            return False
    
    def _extract_nodes(self, node, parent_path, start_row):
        """
        Estrae ricorsivamente tutti i nodi XML
        
        Args:
            node: Nodo XML corrente
            parent_path: Percorso XML del nodo padre
            start_row: Riga di partenza in Excel
        
        Returns:
            list: Lista di tuple (percorso_tag, valore, descrizione, riga)
        """
        rows = []
        current_row = start_row
        
        # Ottieni il nome del tag senza il namespace
        tag = self._get_tag_name(node)
        
        # Costruisci il percorso completo
        current_path = f"{parent_path}/{tag}" if parent_path else tag
        
        # Se il nodo ha un testo, aggiungerlo ai risultati
        text = node.text if node.text and node.text.strip() else ""
        
        # Determina la descrizione in base al tag
        description = self._get_description_for_tag(tag)
        
        # Aggiungi questo nodo solo se ha un valore o è un nodo importante
        if text or not len(node) or tag in ["DettaglioLinee", "DatiRiepilogo"]:
            rows.append((current_path, text, description, current_row))
            current_row += 1
        
        # Aggiungi gli attributi se presenti
        for attr_name, attr_value in node.attrib.items():
            attr_path = f"{current_path}/@{attr_name}"
            attr_desc = f"Attributo di {tag}"
            rows.append((attr_path, attr_value, attr_desc, current_row))
            current_row += 1
        
        # Processa i nodi figli
        for child_node in node:
            # Gestione speciale per i nodi ripetuti come DettaglioLinee
            child_tag = self._get_tag_name(child_node)
            
            if child_tag == "DettaglioLinee":
                # Aggiungi un indicatore di indice al percorso
                numero_linea = child_node.find("NumeroLinea")
                index = numero_linea.text if numero_linea is not None else "?"
                child_path = f"{current_path}[{index}]"
            elif node.xpath(f"count(./{child_tag})", namespaces=self.NS) > 1:
                # Per altri nodi ripetuti, aggiungi un indice progressivo
                siblings = node.xpath(f"./{child_tag}", namespaces=self.NS)
                index = siblings.index(child_node) + 1
                child_path = f"{current_path}[{index}]"
            else:
                # Per nodi non ripetuti, usa il percorso normale
                child_path = current_path
            
            # Estrai i nodi figli ricorsivamente
            child_rows = self._extract_nodes(child_node, child_path, current_row)
            rows.extend(child_rows)
            
            # Aggiorna la riga corrente
            if child_rows:
                current_row = max([r[3] for r in child_rows]) + 1
        
        return rows
    
    def _get_tag_name(self, node):
        """
        Estrae il nome del tag senza namespace
        
        Args:
            node: Nodo XML
        
        Returns:
            str: Nome del tag
        """
        tag = node.tag
        if "}" in tag:
            return tag.split("}")[1]
        return tag
    
    def _get_description_for_tag(self, tag):
        """
        Restituisce una descrizione per il tag XML
        
        Args:
            tag: Nome del tag XML
        
        Returns:
            str: Descrizione del tag
        """
        descriptions = {
            "FatturaElettronica": "Documento principale della fattura elettronica",
            "FatturaElettronicaHeader": "Intestazione della fattura",
            "DatiTrasmissione": "Dati trasmissione verso SDI",
            "IdTrasmittente": "Identificativo del trasmittente",
            "IdPaese": "Codice ISO del paese",
            "IdCodice": "Codice identificativo fiscale",
            "ProgressivoInvio": "Numero progressivo di invio",
            "FormatoTrasmissione": "Formato trasmissione (FPR12, FPA12)",
            "CodiceDestinatario": "Codice destinatario SDI",
            "CedentePrestatore": "Fornitore",
            "CessionarioCommittente": "Cliente",
            "DatiAnagrafici": "Dati anagrafici",
            "IdFiscaleIVA": "Identificativo fiscale IVA",
            "CodiceFiscale": "Codice fiscale",
            "Anagrafica": "Dati anagrafici",
            "Denominazione": "Denominazione o ragione sociale",
            "Nome": "Nome persona fisica",
            "Cognome": "Cognome persona fisica",
            "RegimeFiscale": "Regime fiscale",
            "Sede": "Sede legale o amministrativa",
            "Indirizzo": "Indirizzo",
            "NumeroCivico": "Numero civico",
            "CAP": "Codice Avviamento Postale",
            "Comune": "Comune",
            "Provincia": "Provincia (sigla)",
            "Nazione": "Nazione (codice ISO)",
            "FatturaElettronicaBody": "Corpo della fattura",
            "DatiGenerali": "Dati generali del documento",
            "DatiGeneraliDocumento": "Dati generali documento",
            "TipoDocumento": "Tipo documento (TD01, TD02, ...)",
            "Divisa": "Valuta del documento",
            "Data": "Data del documento",
            "Numero": "Numero del documento",
            "ImportoTotaleDocumento": "Importo totale del documento",
            "DatiBeniServizi": "Dati relativi ai beni/servizi",
            "DettaglioLinee": "Dettaglio linee del documento",
            "NumeroLinea": "Numero progressivo della linea",
            "Descrizione": "Descrizione della linea",
            "Quantita": "Quantità",
            "UnitaMisura": "Unità di misura",
            "PrezzoUnitario": "Prezzo unitario",
            "PrezzoTotale": "Prezzo totale",
            "AliquotaIVA": "Aliquota IVA",
            "DatiRiepilogo": "Dati di riepilogo",
            "ImponibileImporto": "Imponibile",
            "Imposta": "Imposta",
            "EsigibilitaIVA": "Esigibilità IVA",
            "DatiPagamento": "Dati del pagamento",
            "CondizioniPagamento": "Condizioni di pagamento",
            "DettaglioPagamento": "Dettaglio del pagamento",
            "ModalitaPagamento": "Modalità di pagamento",
            "DataScadenzaPagamento": "Data scadenza pagamento",
            "ImportoPagamento": "Importo del pagamento"
        }
        
        return descriptions.get(tag, "")
    
    def import_excel_to_xml(self, template_xml_path=None, output_xml_path=None):
        """
        Crea un nuovo XML a partire dai dati in Excel
        
        Args:
            template_xml_path: Percorso di un file XML modello (opzionale)
            output_xml_path: Percorso di output del nuovo XML (opzionale)
        
        Returns:
            bool, str: (Successo, Percorso del file creato)
        """
        try:
            # Se non è specificato un percorso di output, chiedi all'utente
            if not output_xml_path:
                output_xml_path = filedialog.asksaveasfilename(
                    title="Salva il nuovo file XML",
                    defaultextension=".xml",
                    filetypes=[("File XML", "*.xml")]
                )
                if not output_xml_path:
                    self.log("Operazione di creazione XML annullata dall'utente")
                    return False, ""
            
            # Leggi il file Excel
            if not os.path.exists(self.excel_path):
                self.log(f"File Excel non trovato: {self.excel_path}")
                messagebox.showerror("Errore", f"File Excel non trovato: {self.excel_path}")
                return False, ""
            
            wb = openpyxl.load_workbook(self.excel_path)
            
            # Verifica che il foglio dati esista
            if self.sheet_name not in wb.sheetnames:
                self.log(f"Foglio '{self.sheet_name}' non trovato nel file Excel")
                messagebox.showerror("Errore", f"Foglio '{self.sheet_name}' non trovato nel file Excel")
                return False, ""
            
            sheet = wb[self.sheet_name]
            
            # Estrai la struttura XML dal foglio Excel
            xml_structure = self._extract_excel_data(sheet)
            
            # Decidi come creare l'XML
            if template_xml_path and os.path.exists(template_xml_path):
                # Se è fornito un template, usalo come base
                success, xml_doc = self._update_xml_from_excel(template_xml_path, xml_structure)
            else:
                # Altrimenti crea un nuovo XML da zero
                success, xml_doc = self._create_xml_from_excel(xml_structure)
            
            if not success:
                return False, ""
            
            # Applica indentazione per una migliore leggibilità
            self._indent_xml(xml_doc.getroot())
            
            # Salva il file XML
            xml_string = etree.tostring(xml_doc, pretty_print=True, encoding="UTF-8", 
                                        xml_declaration=True).decode("utf-8")
            
            # Migliora formattazione per nodi ripetuti
            xml_string = re.sub(r'(</DettaglioLinee>)(\r?\n)+(<(?:\w+:)?DatiRiepilogo>)', 
                               r'\1\n      \3', xml_string)
            xml_string = re.sub(r'(</DettaglioLinee>)(<(?:\w+:)?DatiRiepilogo>)', 
                               r'\1\n      \2', xml_string)
            
            with open(output_xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_string)
            
            self.log(f"File XML creato con successo: {output_xml_path}")
            return True, output_xml_path
        
        except Exception as e:
            self.log(f"Errore nella creazione del file XML: {str(e)}")
            traceback.print_exc()
            messagebox.showerror("Errore", f"Errore nella creazione del file XML:\n{str(e)}")
            return False, ""
    
    def _extract_excel_data(self, sheet):
        """
        Estrae dati dal foglio Excel
        
        Args:
            sheet: Foglio Excel
        
        Returns:
            dict: Struttura XML estratta
        """
        xml_data = {}
        
        # Cicla su tutte le righe a partire dalla seconda (la prima è l'intestazione)
        for row in range(2, sheet.max_row + 1):
            tag_path = sheet[f"{self.tag_column}{row}"].value
            value = sheet[f"{self.value_column}{row}"].value
            
            if tag_path:
                # Gestione dei valori vuoti
                if value is None:
                    value = ""
                
                # Gestione date
                if isinstance(value, datetime.datetime):
                    value = value.strftime("%Y-%m-%d")
                
                # Aggiungi alla struttura XML
                xml_data[tag_path] = str(value)
        
        return xml_data
    
    def _update_xml_from_excel(self, template_path, xml_structure):
        """
        Aggiorna un XML esistente con i dati da Excel
        
        Args:
            template_path: Percorso del file XML modello
            xml_structure: Struttura XML estratta da Excel
        
        Returns:
            bool, etree.ElementTree: (Successo, Documento XML)
        """
        try:
            # Leggi il template XML
            xml_doc = etree.parse(template_path)
            root = xml_doc.getroot()
            
            # Aggiorna ogni elemento in base al percorso XPath
            for path, value in xml_structure.items():
                # Gestione attributi
                if "/@" in path:
                    # È un attributo
                    element_path, attr_name = path.split("/@")
                    element_path = self._normalize_xpath(element_path)
                    
                    elements = root.xpath(element_path, namespaces=self.NS)
                    if elements:
                        elements[0].set(attr_name, value)
                else:
                    # È un elemento
                    normalized_path = self._normalize_xpath(path)
                    
                    # Verifica se l'elemento esiste
                    elements = root.xpath(normalized_path, namespaces=self.NS)
                    if elements:
                        elements[0].text = value
            
            return True, xml_doc
        
        except Exception as e:
            self.log(f"Errore nell'aggiornamento XML dal template: {str(e)}")
            traceback.print_exc()
            return False, None
    
    def _create_xml_from_excel(self, xml_structure):
        """
        Crea un nuovo XML da zero basandosi sui dati di Excel
        
        Args:
            xml_structure: Struttura XML estratta da Excel
        
        Returns:
            bool, etree.ElementTree: (Successo, Documento XML)
        """
        try:
            # Questo metodo è più complesso perché dobbiamo ricostruire 
            # tutta la struttura XML dai percorsi
            ns_uri = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
            nsmap = {None: ns_uri}
            
            # Trovo il nodo radice
            root_element = next(iter(xml_structure.keys())).split('/')[0]
            root = etree.Element(f"{{{ns_uri}}}{root_element}", nsmap=nsmap)
            
            # Crea un documento
            xml_doc = etree.ElementTree(root)
            
            # Costruisci l'albero XML
            for path, value in sorted(xml_structure.items()):
                self._ensure_path_exists(root, path, value, ns_uri)
            
            return True, xml_doc
        
        except Exception as e:
            self.log(f"Errore nella creazione XML da zero: {str(e)}")
            traceback.print_exc()
            return False, None
    
    def _ensure_path_exists(self, root, path, value, ns_uri):
        """
        Assicura che un percorso esista nell'XML, creandolo se necessario
        
        Args:
            root: Elemento radice XML
            path: Percorso XPath dell'elemento
            value: Valore da assegnare
            ns_uri: URI del namespace
        """
        # Gestione attributi
        if "/@" in path:
            element_path, attr_name = path.split("/@")
            
            # Assicura che l'elemento esista
            element = self._ensure_element_path(root, element_path, ns_uri)
            
            # Imposta l'attributo
            if element is not None:
                element.set(attr_name, value)
        else:
            # Elemento normale
            element = self._ensure_element_path(root, path, ns_uri)
            
            # Imposta il valore
            if element is not None:
                element.text = value
    
    def _ensure_element_path(self, root, path, ns_uri):
        """
        Assicura che un percorso di elementi esista, creandolo se necessario
        
        Args:
            root: Elemento radice XML
            path: Percorso dell'elemento
            ns_uri: URI del namespace
        
        Returns:
            etree.Element: L'elemento alla fine del percorso
        """
        segments = path.split("/")
        
        # Ignora il primo segmento (è la radice)
        current = root
        
        for i in range(1, len(segments)):
            segment = segments[i]
            
            # Gestione indici per elementi ripetuti
            if "[" in segment:
                tag_name, index_str = segment.split("[")
                index = int(index_str.rstrip("]"))
                
                # Crea il tag con namespace
                tag_with_ns = f"{{{ns_uri}}}{tag_name}"
                
                # Trova tutti gli elementi con questo tag
                elements = current.findall(tag_with_ns)
                
                # Se non ci sono abbastanza elementi, creane di nuovi
                while len(elements) < index:
                    new_elem = etree.SubElement(current, tag_with_ns)
                    elements.append(new_elem)
                
                # Usa l'elemento all'indice specificato
                current = elements[index - 1]
            else:
                # Crea il tag con namespace
                tag_with_ns = f"{{{ns_uri}}}{segment}"
                
                # Cerca l'elemento
                found = current.find(tag_with_ns)
                
                # Se non esiste, crealo
                if found is None:
                    current = etree.SubElement(current, tag_with_ns)
                else:
                    current = found
        
        return current
    
    def _normalize_xpath(self, path):
        """
        Normalizza un percorso XPath per l'uso con lxml
        
        Args:
            path: Percorso XPath da normalizzare
        
        Returns:
            str: Percorso XPath normalizzato
        """
        # Gestisci eventuali indici
        parts = path.split('/')
        normalized_parts = []
        
        for part in parts:
            if part:
                if "[" in part:
                    tag_name, index_str = part.split("[")
                    index = int(index_str.rstrip("]"))
                    normalized_parts.append(f"*[local-name()='{tag_name}'][{index}]")
                else:
                    normalized_parts.append(f"*[local-name()='{part}']")
        
        return "//" + "/".join(normalized_parts)
    
    def _indent_xml(self, elem, level=0):
        """
        Applica indentazione per formattare l'XML in modo leggibile
        
        Args:
            elem: Elemento XML
            level: Livello di indentazione
        """
        i = "\n" + "  " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            for child in elem:
                self._indent_xml(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if not elem.tail or not elem.tail.strip():
                elem.tail = i