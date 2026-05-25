

from playwright.sync_api import sync_playwright
from plyer import notification
import time

def enviar_notificacion(titulo, mensaje):
    """Manda una notificación de escritorio al ordenador"""
    notification.notify(
        title=titulo,
        message=mensaje,
        app_name='Renfe Tracker',
        timeout=10
    )

def buscar_trenes():
    print("-----------------------------------")
    print("Iniciando búsqueda de trenes...")
    
    with sync_playwright() as p:
        # AHORA MISMO SE VE EL NAVEGADOR (headless=False)
        # Cuando veas que funciona perfecto, cámbialo a headless=True para que lo haga en la sombra
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context()
        page = context.new_page()
        
        try:
            print("Entrando a Renfe...")
            page.goto("https://www.renfe.com/es/es")
            
            print("Aceptando cookies...")
            page.get_by_role("button", name="Aceptar todas las cookies").click()
            
            print("Rellenando origen y destino...")
            page.get_by_role("combobox", name="Origen").click()
            page.get_by_role("combobox", name="Origen").fill("jer")
            page.get_by_role("option", name="JEREZ DE LA FRONTERA").click()
            
            page.get_by_role("combobox", name="Destino").click()
            page.get_by_role("combobox", name="Destino").fill("san b")
            page.get_by_role("option", name="SAN BERNARDO").click()
            
            print("Seleccionando fecha (día 8)...")
            page.get_by_text("Fecha ida").click()
            page.wait_for_timeout(1000) 
            
            page.get_by_text("Viaje solo ida").click()
            page.wait_for_timeout(1000) 
            
            # Seleccionamos el día 8 (volvemos a usar .first)
            page.get_by_text("8", exact=True).first.click() 
            
            # EL TRUCO DEL RATÓN: 
            # Localizamos el botón de buscar pero NO hacemos clic todavía.
            boton_buscar = page.get_by_role("button", name="Buscar billete")
            
            print("Moviendo el ratón al botón de buscar...")
            # Movemos el cursor del ratón encima del botón. Esto "saca" el foco del calendario 
            # de forma natural y obliga a la web a guardar la fecha sin cancelarla.
            boton_buscar.hover() 
            
            # Le damos 1.5 segundos para que la animación del calendario termine de cerrarse
            page.wait_for_timeout(1500) 
            
            print("Buscando billetes...")
            # Ahora sí, hacemos clic
            boton_buscar.click()

            # Esperamos 8 segundos a que cargue la lista de trenes 
            print("Esperando a que carguen los resultados...")
            page.wait_for_timeout(8000) 
            
            # --- LA MAGIA OCURRE AQUÍ ---
            # Contamos cuántos trenes tienen la clase "precio-final"
            trenes_disponibles = page.locator(".precio-final").count()
            
            if trenes_disponibles > 0:
                print(f"¡Éxito! Hay {trenes_disponibles} trenes con plazas disponibles.")
                enviar_notificacion("¡Billetes de Renfe disponibles!", "Corre a la web de Renfe a comprar tu billete.")
            else:
                print("Todos los trenes están Completos o con plazas H. Seguiremos buscando...")
                
        except Exception as e:
            print(f"Ocurrió un error: {e}")
            
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    while True:
        buscar_trenes()
        print("Esperando 2 minutos para la próxima comprobación...")
        time.sleep(120)
