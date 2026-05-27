
import time
import threading
from playwright.sync_api import sync_playwright
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

busquedas_activas = {}

def buscar_trenes(origen, destino, dia, hora_min, hora_max):
    print("-----------------------------------")
    print(f"Buscando trenes ({hora_min} - {hora_max}) de {origen} a {destino} para el día {dia}...")
    
    # Esta variable la devolveremos al final para que Telegram sepa qué ha pasado
    horas_disponibles = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True) 
        
        # --- NUEVO: LE DAMOS UNA PANTALLA GIGANTE AL BOT ---
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        
        try:
            page.goto("https://www.renfe.com/es/es")
            
            # --- NUEVO: PROTEGEMOS EL CLIC DE LAS COOKIES ---
            try:
                # Le damos solo 3 segundos. Si no puede, que pase de largo.
                page.get_by_role("button", name="Aceptar todas las cookies").click(force=True, timeout=3000)
            except Exception:
                print("Ignorando cookies (no aparecieron o estaban ocultas). Seguimos...")
                
            page.wait_for_timeout(1000)
            
            # 1. ORIGEN (Tu método original, pero forzando el clic)
            page.get_by_role("combobox", name="Origen").click(force=True)
            page.get_by_role("combobox", name="Origen").fill(origen)
            page.wait_for_timeout(1500)
            page.get_by_role("option").first.click(force=True)
            
            # 2. DESTINO (Tu método original)
            page.get_by_role("combobox", name="Destino").click(force=True)
            page.get_by_role("combobox", name="Destino").fill(destino)
            page.wait_for_timeout(1500)
            page.get_by_role("option").first.click(force=True)
            
            # 3. FECHAS (Con el filtro anticolores grises que hicimos)
            page.get_by_text("Fecha ida").click(force=True)
            page.wait_for_timeout(1000) 
            page.get_by_text("Viaje solo ida").click(force=True)
            page.wait_for_timeout(1000) 
            page.locator(f"div.lightpick__day:not(.is-disabled):text-is('{dia}')").first.click(force=True)
            page.wait_for_timeout(1000)
            
            # 4. LIMPIEZA VISUAL (Clic en una esquina vacía para cerrar el calendario)
            page.mouse.click(10, 10)
            page.wait_for_timeout(1000)
            
            # 5. EL CLIC FINAL (Forzado, sin hacer 'hover' para evitar que se atasque)
            boton_buscar = page.get_by_role("button", name="Buscar billete")
            boton_buscar.click(force=True)
            
            print("Esperando resultados...")
            page.wait_for_timeout(8000) 

            # --- LÓGICA DE BÚSQUEDA ---
            horas_procesadas = set() 
            elementos_hora = page.locator('h5[aria-hidden="true"]').all()
            
            for elemento in elementos_hora:
                texto_hora = elemento.inner_text().strip()
                hora_limpia = texto_hora[:5]
                caja_tren = elemento.locator('xpath=ancestor::div[descendant::div[starts-with(@id, "precio-viaje_tren")]][1]')
                
                if caja_tren.count() > 0:
                    hora_salida_real = caja_tren.locator('h5[aria-hidden="true"]').first.inner_text().strip()[:5]
                    
                    if hora_limpia != hora_salida_real:
                        continue
                    if hora_limpia in horas_procesadas:
                        continue
                        
                    horas_procesadas.add(hora_limpia)
                    
                    if hora_min <= hora_limpia <= hora_max:
                        if caja_tren.locator('.precio-final').count() > 0:
                            horas_disponibles.append(hora_limpia)
                            print(f"  -> ¡BINGO! Tren disponible a las {hora_limpia}")
                            
        except Exception as e:
            print(f"Error en la búsqueda: {e}")
            
        finally:
            context.close()
            browser.close()
            
        # Al terminar, la función "escupe" la lista de horas hacia fuera
        return horas_disponibles

# ==========================================
# INTERFAZ INTERACTIVA DE TELEGRAM
# ==========================================
TOKEN = "8680098167:AAHL3p3t4OVZuuGh5ncZQ3lAatpcYjy6VnA"
bot = telebot.TeleBot(TOKEN)

# 1. Cuando el usuario escriba /start, le mostramos los botones
@bot.message_handler(commands=['start'])
def mostrar_menu(message):
    # Creamos un teclado que se adapte a la pantalla del móvil
    teclado = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    
    # Creamos nuestros botones personalizados
    boton_buscar = KeyboardButton("🔍 Buscar Billetes")
    boton_estado = KeyboardButton("📊 Estado del Servidor")
    
    # Los metemos en el teclado (uno debajo del otro)
    teclado.add(boton_buscar)
    teclado.add(boton_estado)
    
    texto_bienvenida = "¡Hola! Soy tu asistente en la nube de Renfe ☁️🚄.\n\nToca un botón para empezar:"
    bot.send_message(message.chat.id, texto_bienvenida, reply_markup=teclado)

# 2. Cuando el usuario toque el botón "Buscar"
# Un pequeño almacén para guardar las respuestas del usuario temporalmente
datos_usuarios = {}

@bot.message_handler(func=lambda message: message.text == "🔍 Buscar Billetes")
def iniciar_entrevista(message):
    chat_id = message.chat.id
    datos_usuarios[chat_id] = {} # Creamos una ficha en blanco para ti
    
    # Teclado con opciones rápidas de estaciones
    teclado = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    teclado.add("Jerez de la Frontera", "San Bernardo", "Cádiz")
    
    msg = bot.send_message(chat_id, "🚉 ¿Desde qué estación sales?", reply_markup=teclado)
    # Mandamos la respuesta al siguiente paso
    bot.register_next_step_handler(msg, preguntar_destino)

def preguntar_destino(message):
    chat_id = message.chat.id
    datos_usuarios[chat_id]['origen'] = message.text # Guardamos el origen
    
    teclado = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    teclado.add("San Bernardo", "Jerez de la Frontera")
    
    msg = bot.send_message(chat_id, "📍 ¿A dónde viajas?", reply_markup=teclado)
    bot.register_next_step_handler(msg, preguntar_dia)

def preguntar_dia(message):
    chat_id = message.chat.id
    datos_usuarios[chat_id]['destino'] = message.text # Guardamos el destino
    
    # Quitamos los botones gigantes para que puedas escribir un número cómodamente
    msg = bot.send_message(chat_id, "📅 ¿Qué día del mes viajas?\n\n(Escribe solo el número, ej: 18)", reply_markup=ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, preguntar_horario)

# --- NUEVO PASO: PREGUNTAR LA HORA ---
def preguntar_horario(message):
    chat_id = message.chat.id
    datos_usuarios[chat_id]['dia'] = message.text # Guardamos el día que nos dio antes
    
    texto = (
        "⏱️ ¿En qué intervalo de horas quieres buscar?\n\n"
        "Escríbelo separado por un guion. Por ejemplo, de 8 de la mañana a 6 de la tarde sería:\n"
        "👉 *08-18*"
    )
    msg = bot.send_message(chat_id, texto, parse_mode="Markdown")
    bot.register_next_step_handler(msg, realizar_busqueda)

def realizar_busqueda(message):
    chat_id = message.chat.id
    
    # 1. Recuperamos los datos anteriores
    origen = datos_usuarios[chat_id]['origen']
    destino = datos_usuarios[chat_id]['destino']
    dia = datos_usuarios[chat_id]['dia']
    
    # 2. Procesamos el texto de las horas (ej: "8-18" o "08-18")
    texto_horario = message.text.replace(" ", "") # Quitamos espacios por si el usuario pone "08 - 18"
    
    try:
        partes = texto_horario.split("-")
        # Esto convierte un "8" en "08:00" automáticamente, para que Renfe lo entienda
        hora_min = f"{int(partes[0]):02d}:00" 
        hora_max = f"{int(partes[1]):02d}:00"
    except Exception:
        # Si el usuario escribe "patata" en vez de números, le ponemos este por defecto para que no explote
        hora_min = "06:00"
        hora_max = "22:00"
        bot.send_message(chat_id, "⚠️ No he entendido el horario. Usaré el horario completo por defecto (06:00 a 22:00).")
    
    # 3. Encendemos el interruptor para este usuario
    busquedas_activas[chat_id] = True
    
    texto_aviso = (
        f"⚙️ ¡Modo Rastreador Activado!\n\n"
        f"📍 De: *{origen}*\n"
        f"📍 A: *{destino}*\n"
        f"📅 Día: *{dia}*\n"
        f"⏱️ Rango: *{hora_min} a {hora_max}*\n\n"
        f"👁️ El bot buscará cada minuto sin descanso hasta encontrar billetes."
    )
    bot.send_message(chat_id, texto_aviso, parse_mode="Markdown")
    
    teclado_parar = ReplyKeyboardMarkup(resize_keyboard=True)
    teclado_parar.add(KeyboardButton("🛑 Parar Búsqueda"))
    bot.send_message(chat_id, "Búsqueda en segundo plano iniciada...", reply_markup=teclado_parar)
    
    # Mandamos al clon a trabajar
    hilo = threading.Thread(target=bucle_rastreador, args=(chat_id, origen, destino, dia, hora_min, hora_max))
    hilo.start()



# --- NUEVO: EL MOTOR QUE NO DUERME ---
def bucle_rastreador(chat_id, origen, destino, dia, hora_min, hora_max):
    # Mientras el interruptor esté encendido, repetimos
    while busquedas_activas.get(chat_id, False):
        try:
            print("Iniciando escaneo...")
            horas = buscar_trenes(origen, destino, dia, hora_min, hora_max)
            
            if horas and len(horas) > 0:
                # ¡BINGO!
                texto_horas = ", ".join(horas)
                bot.send_message(chat_id, f"🚆 **¡BINGO RENFE!**\nHay {len(horas)} tren(es) disponibles.\n🕒 Horas de salida: {texto_horas}", parse_mode="Markdown")
                
                # Apagamos el interruptor porque ya hemos ganado
                busquedas_activas[chat_id] = False
                
                # Le devolvemos el menú normal (creamos el teclado a mano porque estamos en un hilo)
                teclado = ReplyKeyboardMarkup(resize_keyboard=True)
                teclado.add(KeyboardButton("🔍 Buscar Billetes"), KeyboardButton("📊 Estado del Servidor"))
                bot.send_message(chat_id, "Búsqueda finalizada con éxito. ¡Corre a comprar!", reply_markup=teclado)
                break # Rompemos el bucle
                
            else:
                print("No hay trenes. Esperando 1 minuto...")
                # Esperamos 60 segundos, pero comprobando cada segundo si el usuario ha pulsado "Parar"
                for _ in range(60):
                    if not busquedas_activas.get(chat_id, False):
                        break # Si el usuario lo paró, rompemos la espera
                    time.sleep(1)
                    
        except Exception as e:
            print(f"Error temporal en la web: {e}")
            # Si la web falla, esperamos un poco y volvemos a intentarlo
            time.sleep(30)

# 3. Cuando el usuario toque el botón "Estado"
@bot.message_handler(func=lambda message: message.text == "📊 Estado del Servidor")
def boton_estado_tocado(message):
    bot.reply_to(message, "El servidor en la nube está encendido y funcionando perfectamente 🟢.")

@bot.message_handler(func=lambda message: message.text == "🛑 Parar Búsqueda")
def parar_busqueda(message):
    chat_id = message.chat.id
    if busquedas_activas.get(chat_id, False):
        busquedas_activas[chat_id] = False # Apagamos el interruptor
        bot.reply_to(message, "🛑 Búsqueda automática cancelada.")
    else:
        bot.reply_to(message, "No tienes ninguna búsqueda activa.")
    
    mostrar_menu(message) # Volvemos a poner los botones de Buscar y Estado

# ==========================================
# ENCENDIDO DEL MOTOR
# ==========================================
if __name__ == "__main__":
    print("☁️ Servidor iniciado. El bot está escuchando a Telegram...")
    # Esto hace que el programa no se cierre y se quede esperando tus mensajes 24/7
    bot.polling(none_stop=True, skip_pending=True)