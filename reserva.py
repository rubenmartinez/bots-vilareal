from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from datetime import time, datetime, date, timedelta
import pushover
from time import sleep
import logging
import yaml


with open("/home/rmartinez/NODROPBOX/bot-vilarealsport.yaml", 'r') as stream:
    try:
        config = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)
        exit()

logging.basicConfig(filename='/home/rmartinez/var/log/vilareal-reserva.log',
	                level=logging.DEBUG,
	                format="'%(asctime)s - %(levelname)s - %(message)s'")

logging.info("vilareal-reserva START")

LOGGING_TRIES=3
DAYS_AHEAD=2

RESERVA_WAIT_TILL=time(21,0,2)

target_classes = {0: 'T190000', 1: 'T200000', 2: 'T190000', 3: 'T194500', 4: 'T193000', 5: 'T113000'}
target_date=date.today() + timedelta(days=DAYS_AHEAD)
target_time = target_classes.get(target_date.weekday())

if (target_time == None):
	logging.info("No target time defined for date "+str(target_date)+". Exiting")
	exit()

locator = target_date.strftime("%Y%m%d") + target_time
url_fecha = "https://deporsite.net/smevila-real/reserva-clases?fecha=" + target_date.strftime("%Y-%m-%d") 

pushover.init(config["pushover"]["appId"])
pushoverList = (pushover.Client(config["pushover"]["ruben"]), pushover.Client(config["pushover"]["laura"]))
#pushoverList = (pushover.Client(config["pushover"]["ruben"]),)

def sendMessageToList(message, pushoverList, **kwargs):
	for client in pushoverList:
		client.send_message(message, **kwargs)

try:
	chrome_options = Options()
	chrome_options.add_argument("--start-maximized")
	driver = webdriver.Chrome("/usr/local/bin/chromedriver", chrome_options=chrome_options)
	#driver.maximize_window() -- not working when laptod lid is closed ¿?¿? using options instead

	for i in range(LOGGING_TRIES):
		driver.get("https://deporsite.net/smevila-real/login")

		wait = WebDriverWait(driver, 600)
		name_xpath = "//input[@id='email']"
		name_input = wait.until(EC.presence_of_element_located((By.XPATH, name_xpath)))
		name_input.send_keys(config["site"]["user"])

		pass_input = driver.find_element_by_id('password')
		pass_input.send_keys(config["site"]["password"])

		send_button = driver.find_element_by_id('enviarFormulario')
		send_button.click()

		logging.info("logging in, try #" + str(i+1))

		wait = WebDriverWait(driver, 240)
		try:
			activats_link = wait.until(EC.presence_of_element_located((By.LINK_TEXT, 'ACTIVITATS DIRIGIDES')))
		except Exception as e:
			logging.exception("Exception occurred while waiting for 'ACTIVITATS DIRIGIDES'")
			continue
		
		logging.info("logged in, going to activats dirigides")
		activats_link.click()
		break
	else:
		raise Exception('No login possible after ' + LOGGING_TRIES + ' tries')

	if target_date.weekday() < date.today().weekday():
		driver.get(url_fecha)

	wait = WebDriverWait(driver, 240)
	logging.info("Locator is: " + locator)
	activitat_xpath = "//div[@data-codeactividad='{}']".format(locator)
	activitat_div = wait.until(EC.presence_of_element_located((By.XPATH, activitat_xpath)))

#driver.execute_script("document.querySelectorAll('label.boxed')[1].click()")

	logging.info("Inside reserva-clases?fecha=" + target_date.strftime("%Y-%m-%d"))
	activitat_div.click()

	wait = WebDriverWait(driver, 240)
	reservar_link = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "btn-reservar")))
	logging.info("About to click reservar")
	reservar_link.click()

	wait = WebDriverWait(driver, 240)
	pagar_reservar_link = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "btn-pagar-reservar")))
	logging.info("Prepared to click pagar-reservar")

	now_datetime = datetime.now()
	wait_datetime = now_datetime.replace(hour=RESERVA_WAIT_TILL.hour, minute=RESERVA_WAIT_TILL.minute, second=RESERVA_WAIT_TILL.second)
	wait_seconds = (wait_datetime - now_datetime).seconds
	if wait_seconds > 0:
		logging.info("Waiting " + str(wait_seconds) + " seconds till " + str(RESERVA_WAIT_TILL))
		sleep(wait_seconds)
	else:
		logging_info("No need to wait, already passed " + str(RESERVA_WAIT_TILL))

	pagar_reservar_link.click()

	nombre_actividad = driver.find_element_by_class_name("nombre-actividad").text
	fecha_hora = driver.find_element_by_class_name("fecha-hora").text
	espacio = driver.find_element_by_class_name("espacio").text

	logging.info(",".join((nombre_actividad, fecha_hora, espacio)))

	wait = WebDriverWait(driver, 300)
	texto_confirmacion = wait.until(EC.presence_of_element_located((By.ID, "texto-confirmacion")))

	notif_subject = nombre_actividad + ": " + texto_confirmacion.text
	notif_text = nombre_actividad + "\n" + fecha_hora + "\n" + espacio

	mis_reservas_url="https://deporsite.net/smevila-real/usuario/gestorreservas/home"
	sendMessageToList(notif_text, pushoverList, title=notif_subject, url=mis_reservas_url)
	driver.close()

except Exception as e:
	logging.exception("Exception occurred")
	if ("nombre_actividad" in vars()):
		notif_text = "Error reservando actividad " + nombre_actividad
	else:
		notif_text = "Error reservando actividad"
	logging.debug("Sending pushover message: "+notif_text)
	sendMessageToList(notif_text, pushoverList, url=url_fecha)

