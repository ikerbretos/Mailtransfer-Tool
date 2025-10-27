# Mailtransfer-Tool
Herramienta de escritorio para migrar cuentas de correo IMAP. Ejecuta múltiples tareas en hilos. Incluye modo seguro para evitar duplicados y modo rápido de copia forzada. Conserva metadatos (fechas, flags) de los correos.
Aquí tienes una descripción de la herramienta, tanto en inglés como en español, optimizada para el `README.md` de tu repositorio de GitHub.

-----

# (English) IMAP Mail Migrator Tool

A modern, multi-threaded desktop application for migrating and synchronizing email accounts via IMAP, built with Python and CustomTkinter.

This tool is designed to help users migrate their email from one hosting provider to another (or back up an account) by copying messages over IMAP, preserving original dates and read/unread status.


## Key Features

  * **Modern, Cross-Platform GUI:** Built with [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (supports dark/light modes).
  * **Multi-Job Processing:** Add multiple account migration jobs (e.g., *work@a.com* -\> *work@b.com*, *personal@a.com* -\> *personal@b.com*) and run them all simultaneously.
  * **Non-Blocking Interface:** Uses Python's `threading` library so the UI never freezes during long synchronization processes.
  * **Selective Folder Migration:** A built-in folder browser connects to the source account, allowing you to select exactly which folders to copy. If none are selected, it migrates all of them.
  * **Intelligent "Safe Sync" Mode:**
      * This is the default and recommended mode.
      * It prevents duplicates by comparing the `Message-ID` of every email in the source and destination folders.
      * It only copies emails that are missing from the destination, making it safe to re-run or resume an interrupted migration.
  * **Fast "Force Copy" Mode:**
      * A faster, "dumb" mode that simply fetches all messages from the source and appends them to the destination.
      * **Warning:** This mode **will create duplicates** if run more than once on the same folder.
  * **Preserves Metadata:** Correctly migrates original email reception dates (`INTERNALDATE`) and flags (`\Seen`, `\Answered`, `\Flagged`, etc.).
  * **Detailed Logging:** Automatically creates a `sincronizacion.log` file to track every action and error, making troubleshooting easy.

## Requirements

  * Python 3.x
  * `customtkinter`

<!-- end list -->

```bash
pip install customtkinter
```

## How to Use

1.  Run the `mailtransfer.py` script: `python mailtransfer.py`
2.  Fill in the **Source** (Host, User, Pass) and **Destination** (Host, User, Pass) account details.
3.  (Optional) Click **"List/Select Folders"** to connect to the source account and choose specific folders.
4.  Choose your desired **Mode** ("Safe Sync" is recommended).
5.  Click **"Add Account"** if you need to migrate another account at the same time.
6.  Click **"Sincronizar Todo" (Sync All)** to begin the process.

-----

<br>

# (Español) Herramienta de Migración de Correo IMAP

Una aplicación de escritorio moderna y multihilo para migrar y sincronizar cuentas de correo electrónico vía IMAP, creada con Python y CustomTkinter.

Esta herramienta está diseñada para ayudar a usuarios a migrar sus correos de un proveedor de hosting a otro (o para hacer copias de seguridad) copiando mensajes vía IMAP, conservando las fechas originales y el estado de leído/no leído.


## Características Principales

  * **GUI Moderna y Multiplataforma:** Creada con [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (soporta modo claro/oscuro).
  * **Procesamiento Multitarea:** Añade múltiples tareas de migración (ej. *trabajo@a.com* -\> *trabajo@b.com*, *personal@a.com* -\> *personal@b.com*) y ejecútalas todas simultáneamente.
  * **Interfaz sin Bloqueos:** Utiliza la librería `threading` de Python para que la interfaz nunca se congele durante sincronizaciones largas.
  * **Migración Selectiva de Carpetas:** Un selector de carpetas se conecta a la cuenta de origen, permitiéndote elegir exactamente qué carpetas copiar. Si no se selecciona ninguna, migra todas.
  * **Modo "Sincronización Segura" (Inteligente):**
      * Es el modo por defecto y recomendado.
      * Evita duplicados comparando el `Message-ID` de cada correo en la carpeta de origen y la de destino.
      * Solo copia correos que faltan en el destino, lo que lo hace seguro para reanudar migraciones interrumpidas o ejecutarlo varias veces.
  * **Modo "Forzar Copia" (Rápido):**
      * Un modo "tonto" y más rápido que simplemente copia todos los mensajes del origen al destino.
      * **Aviso:** Este modo **creará duplicados** si se ejecuta más de una vez sobre la misma carpeta.
  * **Conserva Metadatos:** Migra correctamente las fechas de recepción originales (`INTERNALDATE`) y los *flags* (estados como `\Seen` -leído-, `\Answered` -respondido-, etc.).
  * **Registro Detallado:** Crea automáticamente un archivo `sincronizacion.log` para rastrear cada acción y error, facilitando la depuración.

## Requisitos

  * Python 3.x
  * `customtkinter`

<!-- end list -->

```bash
pip install customtkinter
```

## Cómo Usar

1.  Ejecuta el script `mailtransfer.py`: `python mailtransfer.py`
2.  Rellena los datos de la cuenta de **Origen** (Host, Usuario, Pass) y **Destino** (Host, Usuario, Pass).
3.  (Opcional) Haz clic en **"Listar/Seleccionar Carpetas"** para conectarte a la cuenta de origen y elegir carpetas específicas.
4.  Elige el **Modo** deseado ("Sincronización Segura" es el recomendado).
5.  Haz clic en **"Añadir Cuenta"** si necesitas migrar otra cuenta al mismo tiempo.
6.  Haz clic en **"Sincronizar Todo"** para comenzar el proceso.
