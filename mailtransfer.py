import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import imaplib
import threading
import email
import time
import re
from queue import Queue
import traceback
import logging

# --- CONFIGURACIÓN DEL LOGGING ---
# Crea un archivo de log que registrará todos los eventos y errores.
logging.basicConfig(
    filename='sincronizacion.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# --- LÓGICA DE SINCRONIZACIÓN ---

def get_message_id_map(connection, log_callback, widgets):
    """
    Analiza una carpeta de correo para obtener un diccionario que mapea
    el Message-ID de cada correo a su UID.

    Este método procesa los correos uno a uno para garantizar la máxima fiabilidad,
    aunque sea más lento que los métodos por lotes.

    :param connection: Conexión imaplib activa.
    :param log_callback: Función para enviar actualizaciones a la GUI.
    :param widgets: Diccionario de widgets de la GUI para el callback.
    :return: Diccionario con {message_id: uid}.
    """
    id_map = {}
    typ, data = connection.uid('search', None, 'ALL')
    if typ != 'OK' or not data[0]:
        return {}
    
    uid_list = data[0].split()
    if not uid_list:
        return {}

    total_uids = len(uid_list)
    log_callback(widgets, f"Análisis Seguro: {total_uids} correos...", "gray")
    logging.info(f"Iniciando análisis de {total_uids} correos.")
    
    for i, uid in enumerate(uid_list):
        if (i + 1) % 50 == 0:  # Actualiza la UI cada 50 correos para no saturar
            log_callback(widgets, f"Análisis Seguro: {i + 1}/{total_uids}...", "gray")
        
        try:
            typ, fetch_data = connection.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])')
            if typ != 'OK' or not fetch_data:
                continue

            # Une la respuesta por si el servidor la envía fragmentada
            full_response_str = b"".join(
                part for part in fetch_data if isinstance(part, bytes)
            ).decode('utf-8', 'ignore')

            if isinstance(fetch_data[0], tuple):
                full_response_str += fetch_data[0][0].decode('utf-8', 'ignore') + fetch_data[0][1].decode('utf-8', 'ignore')
            
            msg_id_match = re.search(r'Message-ID:\s*<(.*?)>', full_response_str, re.IGNORECASE | re.DOTALL)
            if msg_id_match:
                msg_id = msg_id_match.group(1).strip()
                id_map[msg_id] = uid
        except Exception:
            continue
            
    logging.info(f"Análisis completado. Se encontraron {len(id_map)} Message-IDs.")
    return id_map


def list_folders_native(host, user, password, queue):
    """
    Obtiene la lista de carpetas de una cuenta IMAP y la pone en una cola
    para ser leída por el hilo principal de la GUI.
    """
    try:
        with imaplib.IMAP4_SSL(host) as mail:
            mail.login(user, password)
            status, folders_raw = mail.list()
            if status != 'OK':
                queue.put({'status': 'error', 'message': 'El servidor denegó la petición de listar carpetas.'})
                return
            
            folder_names = []
            pattern = re.compile(r'\((.*?)\)\s+"(.*?)"\s+(.*)')
            for folder_info_bytes in folders_raw:
                line = folder_info_bytes.decode('utf-8', 'ignore')
                match = pattern.match(line)
                if match:
                    name = match.group(3).strip().strip('"')
                    if name:  # Evita añadir carpetas raíz sin nombre
                        folder_names.append(name)
            if folder_names:
                queue.put({'status': 'success', 'folders': sorted(list(set(folder_names)))})
            else:
                queue.put({'status': 'error', 'message': "No se encontraron carpetas analizables."})
    except Exception as e:
        queue.put({'status': 'error', 'message': f"Error crítico: {e}"})


def execute_sync_job_native(job_data, log_callback, progress_callback):
    """
    Ejecuta el trabajo de sincronización para una cuenta, usando el modo seleccionado.
    """
    widgets = job_data['widgets']
    # Recoge todos los datos de la GUI
    host1, user1, pass1, host2, user2, pass2 = (widgets[k].get() for k in ["host1", "user1", "pass1", "host2", "user2", "pass2"])
    sync_mode = widgets["sync_mode"].get()
    
    logging.info("="*60)
    logging.info(f"INICIO DE SINCRONIZACIÓN ({sync_mode}): {user1} -> {user2}")
    
    try:
        log_callback(widgets, "Conectando...", "cyan")
        with imaplib.IMAP4_SSL(host1) as source, imaplib.IMAP4_SSL(host2) as dest:
            source.login(user1, pass1)
            logging.info(f"Conexión exitosa al origen: {host1}")
            dest.login(user2, pass2)
            logging.info(f"Conexión exitosa al destino: {host2}")
            log_callback(widgets, "Conexión exitosa.", "cyan")

            selected_folders = job_data.get("selected_folders", [])
            
            # Si no hay carpetas seleccionadas, obtiene todas las del servidor.
            if not selected_folders:
                log_callback(widgets, "Listando todas las carpetas del origen...", "gray")
                logging.info("No se seleccionaron carpetas, procediendo a listar todas.")
                status, folders_raw = source.list()
                if status == 'OK':
                    folders = []
                    pattern = re.compile(r'\((.*?)\)\s+"(.*?)"\s+(.*)')
                    for folder_info_bytes in folders_raw:
                        line = folder_info_bytes.decode('utf-8', 'ignore')
                        match = pattern.match(line)
                        if match:
                            name = match.group(3).strip().strip('"')
                            if name: folders.append(name)
                    selected_folders = sorted(list(set(folders)))
                    logging.info(f"Se encontraron {len(selected_folders)} carpetas para sincronizar.")
                else:
                    log_callback(widgets, "Error: No se pudo obtener la lista de carpetas.", "red")
                    logging.error("Fallo al ejecutar source.list()")
                    return

            # Itera sobre cada carpeta para sincronizarla
            total_folders = len(selected_folders)
            for i, folder_name in enumerate(selected_folders):
                try:
                    log_callback(widgets, f"Carpeta ({i+1}/{total_folders}): {folder_name}", "white")
                    logging.info(f"--- Procesando carpeta: {folder_name} ---")
                    
                    # Crea la carpeta en el destino y se suscribe para que sea visible
                    dest.create(f'"{folder_name}"')
                    dest.subscribe(f'"{folder_name}"')
                    
                    source.select(f'"{folder_name}"', readonly=True)
                    
                    uids_to_fetch = []
                    # Lógica para el modo "Forzar Copia", que es más rápido pero puede duplicar
                    if "Forzar Copia" in sync_mode:
                        log_callback(widgets, "Modo Forzar Copia: Obteniendo todos los correos...", "yellow")
                        logging.info("Modo Forzar Copia. Obteniendo todos los UIDs del origen.")
                        typ, data = source.uid('search', None, 'ALL')
                        if typ == 'OK' and data[0]:
                            uids_to_fetch = data[0].split()
                    else:  # Modo por defecto: "Sincronización Segura"
                        source_id_map = get_message_id_map(source, log_callback, widgets)
                        dest.select(f'"{folder_name}"')
                        dest_id_map = get_message_id_map(dest, log_callback, widgets)
                        missing_message_ids = set(source_id_map.keys()) - set(dest_id_map.keys())
                        uids_to_fetch = [source_id_map[msg_id] for msg_id in missing_message_ids]
                    
                    if not uids_to_fetch:
                        log_callback(widgets, "No hay correos nuevos que copiar.", "green")
                        progress_callback(widgets, 1, 1)
                        logging.info("Carpeta ya sincronizada.")
                        continue
                    
                    log_callback(widgets, f"Copiando {len(uids_to_fetch)} correos...", "cyan")
                    logging.info(f"Se copiarán {len(uids_to_fetch)} correos nuevos.")
                    total_missing = len(uids_to_fetch)
                    progress_callback(widgets, 0, total_missing)
                    
                    # Bucle principal para copiar cada correo
                    for j, uid in enumerate(uids_to_fetch):
                        _, msg_data = source.uid('fetch', uid, '(INTERNALDATE FLAGS RFC822)')
                        if not msg_data or msg_data[0] is None: continue
                        
                        metadata, content = msg_data[0][0].decode('utf-8', 'ignore'), msg_data[0][1]
                        
                        flags_match = re.search(r'FLAGS\s\((.*?)\)', metadata)
                        flags_string = f"({flags_match.group(1)})" if flags_match else None
                        
                        date_match = re.search(r'INTERNALDATE\s"([^"]+)"', metadata)
                        internal_date = imaplib.Time2Internaldate(time.time())
                        if date_match:
                            try:
                                dt = email.utils.parsedate_to_datetime(date_match.group(1))
                                internal_date = imaplib.Time2Internaldate(dt.timestamp())
                            except Exception:
                                pass
                        
                        dest.append(f'"{folder_name}"', flags_string, internal_date, content)
                        progress_callback(widgets, j + 1, total_missing)
                except Exception as e:
                    log_callback(widgets, f"Error en carpeta {folder_name}: {e}", "orange")
                    logging.error(f"FALLO en la carpeta {folder_name}: {e}\n{traceback.format_exc()}")
        
        log_callback(widgets, "¡Sincronización Completada!", "green")
        logging.info("FIN DE SINCRONIZACIÓN.")
    except Exception as e:
        log_callback(widgets, f"Error Crítico: {e}", "red")
        logging.critical(f"FALLO CRÍTICO en la sincronización: {e}\n{traceback.format_exc()}")


# --- CLASE PRINCIPAL DE LA INTERFAZ GRÁFICA ---
class ModernSyncApp(ctk.CTk):
    """
    Clase principal de la aplicación con GUI basada en CustomTkinter.
    """
    def __init__(self):
        """Inicializa la ventana principal y sus componentes."""
        super().__init__()
        self.title("Sincronizador IMAP Avanzado")
        self.geometry("1100x800")
        
        # Establece el tema inicial
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.jobs, self.active_threads = [], []
        self._create_widgets()
        self.add_job_row()

    def _create_widgets(self):
        """Crea todos los widgets de la ventana principal."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.add_button = ctk.CTkButton(controls_frame, text="Añadir Cuenta", command=self.add_job_row)
        self.add_button.pack(side="left", padx=5)
        
        self.sync_all_button = ctk.CTkButton(controls_frame, text="Sincronizar Todo", command=self.start_all_jobs)
        self.sync_all_button.pack(side="left", padx=5)
        
        self.theme_button = ctk.CTkButton(controls_frame, text="Cambiar Tema", command=self.toggle_theme, fg_color="gray", hover_color="#555555")
        self.theme_button.pack(side="right", padx=5)
        
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Cuentas a Sincronizar")
        self.scrollable_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

    def add_job_row(self):
        """Añade una nueva fila de widgets para una nueva cuenta a sincronizar."""
        job_frame = ctk.CTkFrame(self.scrollable_frame)
        job_frame.pack(pady=10, padx=10, fill="x", expand=True)
        
        for i in range(6): job_frame.grid_columnconfigure(i, weight=1 if i % 2 != 0 else 0)
        
        entries = {}
        # Widgets para los datos de la cuenta de origen
        ctk.CTkLabel(job_frame, text="Host Origen").grid(row=0, column=0, padx=(10,2), pady=5, sticky="e")
        entries["host1"] = ctk.CTkEntry(job_frame, placeholder_text="imap.servidor.com"); entries["host1"].grid(row=0, column=1, padx=(0,10), pady=5, sticky="ew")
        ctk.CTkLabel(job_frame, text="Usuario Origen").grid(row=0, column=2, padx=(10,2), pady=5, sticky="e")
        entries["user1"] = ctk.CTkEntry(job_frame, placeholder_text="usuario@dominio.com"); entries["user1"].grid(row=0, column=3, padx=(0,10), pady=5, sticky="ew")
        ctk.CTkLabel(job_frame, text="Pass Origen").grid(row=0, column=4, padx=(10,2), pady=5, sticky="e")
        entries["pass1"] = ctk.CTkEntry(job_frame, show="*"); entries["pass1"].grid(row=0, column=5, padx=(0,10), pady=5, sticky="ew")
        
        # Widgets para los datos de la cuenta de destino
        ctk.CTkLabel(job_frame, text="Host Destino").grid(row=1, column=0, padx=(10,2), pady=5, sticky="e")
        entries["host2"] = ctk.CTkEntry(job_frame, placeholder_text="imap.servidor.com"); entries["host2"].grid(row=1, column=1, padx=(0,10), pady=5, sticky="ew")
        ctk.CTkLabel(job_frame, text="Usuario Destino").grid(row=1, column=2, padx=(10,2), pady=5, sticky="e")
        entries["user2"] = ctk.CTkEntry(job_frame, placeholder_text="usuario@dominio.com"); entries["user2"].grid(row=1, column=3, padx=(0,10), pady=5, sticky="ew")
        ctk.CTkLabel(job_frame, text="Pass Destino").grid(row=1, column=4, padx=(10,2), pady=5, sticky="e")
        entries["pass2"] = ctk.CTkEntry(job_frame, show="*"); entries["pass2"].grid(row=1, column=5, padx=(0,10), pady=5, sticky="ew")
        
        # Widgets para las opciones de sincronización
        options_frame = ctk.CTkFrame(job_frame, fg_color="transparent")
        options_frame.grid(row=2, column=0, columnspan=6, pady=5, padx=10, sticky="ew")
        list_folders_button = ctk.CTkButton(options_frame, text="Listar/Seleccionar Carpetas", width=200)
        list_folders_button.pack(side="left")
        selected_folders_label = ctk.CTkLabel(options_frame, text="Carpetas: Todas", text_color="gray", anchor="w")
        selected_folders_label.pack(side="left", padx=10, fill="x", expand=True)
        
        ctk.CTkLabel(options_frame, text="Modo:").pack(side="left", padx=(10, 5))
        sync_mode_combo = ctk.CTkComboBox(options_frame, values=["Sincronización Segura (lenta)", "Forzar Copia (rápida)"], width=220)
        sync_mode_combo.set("Sincronización Segura (lenta)")
        sync_mode_combo.pack(side="left")
        entries["sync_mode"] = sync_mode_combo
        
        # Widgets para el progreso
        progress_frame = ctk.CTkFrame(job_frame, fg_color="transparent")
        progress_frame.grid(row=3, column=0, columnspan=6, pady=5, padx=10, sticky="ew")
        status_label = ctk.CTkLabel(progress_frame, text="Listo.", anchor="w")
        status_label.pack(side="left", fill="x", expand=True)
        progress_bar = ctk.CTkProgressBar(progress_frame)
        progress_bar.set(0)
        progress_bar.pack(side="right", fill="x")
        
        job_data = {"selected_folders": [], "widgets": {**entries, "progress_bar": progress_bar, "status_label": status_label, "list_folders_button": list_folders_button, "selected_folders_label": selected_folders_label}}
        list_folders_button.configure(command=lambda j=job_data: self.show_folder_selection(j))
        self.jobs.append(job_data)
    
    def show_folder_selection(self, job_data):
        """Abre una ventana emergente para que el usuario seleccione las carpetas."""
        widgets = job_data["widgets"]
        host, user, password = widgets["host1"].get(), widgets["user1"].get(), widgets["pass1"].get()
        if not all([host, user, password]):
            messagebox.showerror("Error", "Rellena los datos de la Cuenta de Origen."); return
        
        popup = ctk.CTkToplevel(self)
        popup.title("Seleccionar Carpetas")
        popup.geometry("400x500")
        popup.transient(self)
        popup.grab_set()
        
        status_label = ctk.CTkLabel(popup, text="Conectando...")
        status_label.pack(pady=20)
        
        q = Queue()
        threading.Thread(target=list_folders_native, args=(host, user, password, q), daemon=True).start()
        
        def check_queue():
            if not q.empty():
                result = q.get()
                status_label.destroy()
                if result['status'] == 'success':
                    self.populate_folder_list(popup, job_data, result['folders'])
                else:
                    messagebox.showerror("Error", result['message'])
                    popup.destroy()
            else:
                popup.after(100, check_queue)
        popup.after(100, check_queue)
    
    def populate_folder_list(self, popup, job_data, folders):
        """Rellena la ventana emergente con la lista de carpetas y checkboxes."""
        button_frame = ctk.CTkFrame(popup, fg_color="transparent")
        button_frame.pack(side="bottom", fill="x", pady=10, padx=10)
        
        scroll_frame = ctk.CTkScrollableFrame(popup, label_text="Carpetas Disponibles")
        scroll_frame.pack(side="top", fill="both", expand=True, padx=10, pady=(10,0))
        
        vars = {folder: tk.BooleanVar(value=(folder in job_data.get("selected_folders", []))) for folder in folders}
        for folder, var in vars.items():
            ctk.CTkCheckBox(scroll_frame, text=folder, variable=var).pack(anchor="w", padx=10, pady=2)
            
        def save():
            job_data["selected_folders"] = [f for f, v in vars.items() if v.get()]
            label = job_data["widgets"]["selected_folders_label"]
            num = len(job_data['selected_folders'])
            label.configure(text=f"Carpetas: {num} seleccionadas" if num > 0 else "Carpetas: Todas")
            popup.destroy()
            
        ctk.CTkButton(button_frame, text="Guardar Selección", command=save).pack()
    
    def start_all_jobs(self):
        """Inicia todos los hilos de sincronización para cada cuenta configurada."""
        self.toggle_buttons_state("disabled")
        self.active_threads = []
        for job in self.jobs:
            self.update_status(job["widgets"], "Iniciando...", "cyan")
            job["widgets"]["progress_bar"].set(0)
            thread = threading.Thread(target=execute_sync_job_native, args=(job, self.update_status, self.update_progress), daemon=True)
            self.active_threads.append(thread)
            thread.start()
        self.after(100, self.check_all_threads_done)
    
    def check_all_threads_done(self):
        """Verifica si todos los hilos de trabajo han terminado."""
        if any(t.is_alive() for t in self.active_threads):
            self.after(200, self.check_all_threads_done)
        else:
            self.toggle_buttons_state("normal")
            logging.info("Todas las tareas han finalizado.")
    
    # --- Funciones de actualización de la GUI ---
    def update_status(self, widgets, message, color): self.after(0, lambda: widgets["status_label"].configure(text=message, text_color=color))
    def update_progress(self, widgets, value, total): self.after(0, lambda: widgets["progress_bar"].set(value / total if total > 0 else 0))
    def toggle_theme(self): ctk.set_appearance_mode("light" if ctk.get_appearance_mode() == "Dark" else "dark")
    def toggle_buttons_state(self, state):
        self.add_button.configure(state=state)
        self.sync_all_button.configure(state=state)
        self.theme_button.configure(state=state)
        for job in self.jobs: 
            job["widgets"]["list_folders_button"].configure(state=state)
            job["widgets"]["sync_mode"].configure(state=state)

if __name__ == "__main__":
    app = ModernSyncApp()
    app.mainloop()