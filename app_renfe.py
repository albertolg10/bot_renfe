
import tkinter as tk
from tkinter import messagebox
import threading
import time
from playwright.sync_api import sync_playwright
from plyer import notification

import urllib.request
import urllib.parse


def enviar_telegram(mensaje):
    # ¡Pon tus datos reales aquí entre las comillas!
    TOKEN = "8680098167:AAHL3p3t4OVZuuGh5ncZQ3lAatpcYjy6VnA"
    CHAT_ID = "7894349301"
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    datos = urllib.parse.urlencode({'chat_id': CHAT_ID, 'text': mensaje}).encode('utf-8')
    
    try:
        urllib.request.urlopen(url, data=datos)
        print("📱 ¡Mensaje enviado a tu Telegram!")
    except Exception as e:
        print(f"⚠️ Error al enviar Telegram: {e}")

bot_activo = False

def enviar_notificacion(titulo, mensaje):
    notification.notify(title=titulo, message=mensaje, app_name='Renfe Tracker', timeout=10)

def alertar_en_interfaz(origen, destino, cantidad, texto_horas):
    def mostrar_popup():
        ventana.deiconify()
        ventana.attributes('-topmost', True)
        
        etiqueta_estado.config(text=f"¡ÉXITO! {cantidad} trenes encontrados", fg="blue")
        mensaje = f"¡Se han encontrado {cantidad} trenes con plazas de {origen} a {destino}!\n\n🕒 Horas de salida: {texto_horas}\n\nEl bot se ha detenido. ¡Corre a la web de Renfe!"
        messagebox.showinfo("¡Billetes Disponibles!", mensaje)
        
        ventana.attributes('-topmost', False)
        detener_busqueda()

    ventana.after(0, mostrar_popup)

def buscar_trenes(origen, destino, dia, hora_min, hora_max):
    print("-----------------------------------")
    print(f"Buscando trenes ({hora_min} - {hora_max}) de {origen} a {destino} para el día {dia}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True) 
        context = browser.new_context()
        page = context.new_page()
        
        try:
            page.goto("https://www.renfe.com/es/es")
            page.get_by_role("button", name="Aceptar todas las cookies").click()
            
            page.get_by_role("combobox", name="Origen").click()
            page.get_by_role("combobox", name="Origen").fill(origen)
            page.wait_for_timeout(1000)
            page.get_by_role("option").first.click()
            
            page.get_by_role("combobox", name="Destino").click()
            page.get_by_role("combobox", name="Destino").fill(destino)
            page.wait_for_timeout(1000)
            page.get_by_role("option").first.click()
            
            page.get_by_text("Fecha ida").click()
            page.wait_for_timeout(1000) 
            page.get_by_text("Viaje solo ida").click()
            page.wait_for_timeout(1000) 
            
            page.get_by_text(dia, exact=True).first.click() 
            
            print("Preparando el botón de búsqueda...")
            
            # --- SIMULAR COMPORTAMIENTO HUMANO ---
            print("Haciendo scroll hacia arriba con la rueda del ratón...")
            
            # 1. Hacemos un clic "tonto" en la esquina superior izquierda
            page.mouse.click(10, 10)
            page.wait_for_timeout(500)
            
            # 2. Simulamos girar la rueda del ratón hacia arriba de forma brusca
            page.mouse.wheel(0, -2000)
            page.wait_for_timeout(1000)
            
            print("Buscando el botón...")
            boton_buscar = page.get_by_role("button", name="Buscar billete")
            
            # 3. Nos ponemos encima con el ratón como un humano
            boton_buscar.hover()
            page.wait_for_timeout(800)
            
            # 4. Hacemos el clic normal
            boton_buscar.click()
            # -------------------------------------

            print("Esperando resultados...")
            page.wait_for_timeout(8000) 



            
            # --- NUEVA LÓGICA: SOLO SALIDAS (ADIÓS LLEGADAS) ---
            horas_disponibles = [] # NUEVO: Creamos una lista vacía para guardar las horas
            horas_procesadas = set() 
            
            elementos_hora = page.locator('h5[aria-hidden="true"]').all()
            
            for elemento in elementos_hora:
                texto_hora = elemento.inner_text().strip()
                hora_limpia = texto_hora[:5]
                
                # Subimos hacia la caja principal del tren
                caja_tren = elemento.locator('xpath=ancestor::div[descendant::div[starts-with(@id, "precio-viaje_tren")]][1]')
                
                if caja_tren.count() > 0:
                    # TRUCO MÁGICO: Buscamos la PRIMERA hora que aparece dentro de esta caja
                    # En Renfe, la primera siempre es la de salida. La segunda es la de llegada.
                    hora_salida_real = caja_tren.locator('h5[aria-hidden="true"]').first.inner_text().strip()[:5]
                    
                    # Si la hora que estamos leyendo NO es la de salida, es la de llegada. ¡Fuera!
                    if hora_limpia != hora_salida_real:
                        continue
                        
                    # Si es la de salida, comprobamos si ya la hicimos (para evitar duplicados de la versión móvil)
                    if hora_limpia in horas_procesadas:
                        continue
                        
                    # La guardamos en la memoria
                    horas_procesadas.add(hora_limpia)
                    
                    print(f"Revisando tren de las: {hora_limpia}")
                    
                    if hora_min <= hora_limpia <= hora_max:
                        if caja_tren.locator('.precio-final').count() > 0:
                            horas_disponibles.append(hora_limpia)
                            print(f"  -> ¡BINGO! Tren disponible a las {hora_limpia}")
                            
                        elif caja_tren.locator('[title="Tren Completo"]').count() > 0:
                            print(f"  -> Tren en tu horario, pero está COMPLETO.")
                            
                        elif caja_tren.locator('.plazas-h').count() > 0:
                            print(f"  -> Tren en tu horario, pero solo tiene plaza H (discapacitados).")
                            
                        else:
                            print(f"  -> Tren en tu horario, pero sin plazas normales.")

            # --- FINAL DE LA LÓGICA DE BÚSQUEDA ---


            if len(horas_disponibles) > 0:
                # Unimos todas las horas de la lista separadas por comas
                texto_horas = ", ".join(horas_disponibles)
                cantidad = len(horas_disponibles)
                
                print(f"¡Éxito! Trenes disponibles a las: {texto_horas}")
                
                # --- NUEVO: AVISO POR TELEGRAM ---
                mensaje_movil = f"🚆 ¡BINGO RENFE!\nHay {cantidad} tren(es) de {origen} a {destino}.\n🕒 Horas de salida: {texto_horas}"
                enviar_telegram(mensaje_movil)
                # ---------------------------------
                
                # Notificación de Windows
                enviar_notificacion("¡Billetes Disponibles!", f"Horas disponibles: {texto_horas}")
                
                # Interfaz gráfica (mantenemos 'cantidad' como número para que no falle tu función)
                alertar_en_interfaz(origen, destino, cantidad, texto_horas)
                
            else:
                print("No hay trenes disponibles en ese horario.")
                ventana.after(0, lambda: etiqueta_estado.config(text=f"Última comprobación: Sin trenes en tu horario. Buscando...", fg="orange"))


        except Exception as e:
            print(f"Error en la búsqueda: {e}")
            ventana.after(0, lambda: etiqueta_estado.config(text="Error de conexión. Reintentando...", fg="red"))
            
        finally:
            context.close()
            browser.close()

def ciclo_bot(origen, destino, dia, hora_min, hora_max):
    global bot_activo
    while bot_activo:
        buscar_trenes(origen, destino, dia, hora_min, hora_max)
        
        for _ in range(120):
            if not bot_activo:
                break
            time.sleep(1)

def iniciar_busqueda():
    global bot_activo
    if bot_activo: return

    origen = entrada_origen.get()
    destino = entrada_destino.get()
    dia = entrada_dia.get()
    hora_min = entrada_hora_min.get()
    hora_max = entrada_hora_max.get()

    if not origen or not destino or not dia or not hora_min or not hora_max:
        messagebox.showwarning("Faltan datos", "Por favor, rellena todos los campos.")
        return

    bot_activo = True
    etiqueta_estado.config(text="Estado: Iniciando navegador oculto...", fg="green")
    boton_iniciar.config(state=tk.DISABLED)
    boton_detener.config(state=tk.NORMAL)

    hilo = threading.Thread(target=ciclo_bot, args=(origen, destino, dia, hora_min, hora_max))
    hilo.start()

def detener_busqueda():
    global bot_activo
    bot_activo = False
    etiqueta_estado.config(text="Estado: Detenido", fg="red")
    boton_iniciar.config(state=tk.NORMAL)
    boton_detener.config(state=tk.DISABLED)

# ==========================================
# INTERFAZ GRÁFICA
# ==========================================
ventana = tk.Tk()
ventana.title("🚂 Buscador de Renfe V2")
ventana.geometry("380x480") # Ventana un poco más alta
ventana.config(padx=20, pady=20)

tk.Label(ventana, text="Configura tu Viaje", font=("Arial", 14, "bold")).pack(pady=10)

tk.Label(ventana, text="Estación Origen:").pack()
entrada_origen = tk.Entry(ventana, width=30)
entrada_origen.pack(pady=5)
entrada_origen.insert(0, "")

tk.Label(ventana, text="Estación Destino:").pack()
entrada_destino = tk.Entry(ventana, width=30)
entrada_destino.pack(pady=5)
entrada_destino.insert(0, "")

tk.Label(ventana, text="Día del mes:").pack()
entrada_dia = tk.Entry(ventana, width=10)
entrada_dia.pack(pady=5)

# --- NUEVOS CAMPOS DE HORARIO ---
marco_horas = tk.Frame(ventana)
marco_horas.pack(pady=10)

tk.Label(marco_horas, text="Desde las").pack(side=tk.LEFT)
entrada_hora_min = tk.Entry(marco_horas, width=6)
entrada_hora_min.pack(side=tk.LEFT, padx=5)
entrada_hora_min.insert(0, "06:00")

tk.Label(marco_horas, text="hasta las").pack(side=tk.LEFT)
entrada_hora_max = tk.Entry(marco_horas, width=6)
entrada_hora_max.pack(side=tk.LEFT, padx=5)
entrada_hora_max.insert(0, "22:00")
# --------------------------------

boton_iniciar = tk.Button(ventana, text="Iniciar Búsqueda", bg="lightgreen", command=iniciar_busqueda)
boton_iniciar.pack(pady=10)

boton_detener = tk.Button(ventana, text="Detener", bg="salmon", state=tk.DISABLED, command=detener_busqueda)
boton_detener.pack()

etiqueta_estado = tk.Label(ventana, text="Estado: Detenido", fg="red", font=("Arial", 10, "bold"))
etiqueta_estado.pack(pady=15)

ventana.mainloop()
