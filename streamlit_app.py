import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
import io
import base64

# --- CONFIGURACIÓN DE LA APLICACIÓN ---
# Estas variables se cargarán de st.secrets (configuradas en Streamlit Cloud)
# NO MODIFIQUES ESTAS LÍNEAS DIRECTAMENTE AQUÍ.
# Los valores DEBEN ser configurados en la interfaz de secretos de Streamlit Cloud.
SPREADSHEET_NAME = st.secrets["SPREADSHEET_NAME"]
WORKSHEET_NAME = st.secrets["WORKSHEET_NAME"]

# Encabezados de las columnas en tu Google Sheet
# Asegúrate de que estos coincidan EXACTAMENTE con los encabezados de la primera fila de tu hoja.
IMEI_COLUMN_HEADER = 'IMEI'
PDF_URL_COLUMN_HEADER = 'PDF_URL'

# --- FUNCIONES DE LÓGICA DE NEGOCIO ---

@st.cache_data(ttl=600) # Almacena en caché los datos por 10 minutos para reducir llamadas a la API
def get_google_sheet_data():
    """
    Autentica con Google Sheets usando la cuenta de servicio y lee los datos.
    Devuelve un diccionario mapeando IMEI a URL de PDF.
    """
    try:
        # Definir los alcances de la API (lo que la cuenta de servicio puede hacer)
        # Necesario para gspread y Google Drive
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        # Cargar las credenciales de la cuenta de servicio de Streamlit secrets
        # 'gcp_service_account' es el nombre de la clave principal bajo la cual
        # pegaste todo el contenido de tu JSON en Streamlit secrets.
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=scope
        )
        
        # Autorizar el cliente gspread
        client = gspread.authorize(creds)

        # Abrir el spreadsheet por nombre
        spreadsheet = client.open(SPREADSHEET_NAME)
        
        # Seleccionar la hoja de trabajo por nombre
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        
        # Obtener todos los registros como una lista de diccionarios
        # Cada diccionario representa una fila, con los encabezados de columna como claves.
        records = worksheet.get_all_records()
        
        imei_data = {}
        for row in records:
            # Asegúrate de que los encabezados de columna existan en la fila
            imei = str(row.get(IMEI_COLUMN_HEADER))
            pdf_url = row.get(PDF_URL_COLUMN_HEADER)
            
            if imei and pdf_url: # Asegúrate de que ambos valores existan y no estén vacíos
                imei_data[imei.strip()] = pdf_url.strip() # Limpia espacios en blanco
        
        return imei_data

    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: La hoja de cálculo '{SPREADSHEET_NAME}' no fue encontrada.\n"
                 f"Verifica el nombre y que la cuenta de servicio tiene permiso de 'Lector'.")
        return None
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Error: La hoja de trabajo '{WORKSHEET_NAME}' no fue encontrada en '{SPREADSHEET_NAME}'.\n"
                 f"Verifica el nombre de la hoja.")
        return None
    except Exception as e:
        # Captura errores generales, incluyendo problemas de autenticación o formato de secretos
        st.error(f"Ocurrió un error al cargar los datos de Google Sheets: {e}\n"
                 f"Posibles causas:\n"
                 f"- La configuración de 'gcp_service_account' en Streamlit Secrets es incorrecta.\n"
                 f"- La cuenta de servicio no tiene el rol de 'Lector' en el Google Sheet.")
        return None

def download_pdf_as_bytes(pdf_url):
    """Descarga un PDF desde una URL y lo devuelve como bytes."""
    try:
        response = requests.get(pdf_url, stream=True)
        response.raise_for_status() # Lanza un error para códigos de estado HTTP 4xx/5xx
        return response.content # Devuelve el contenido binario del PDF
    except requests.exceptions.RequestException as e:
        st.error(f"Error al descargar el PDF desde: {pdf_url}\nDetalle: {e}")
        return None

def display_pdf_in_streamlit(pdf_bytes):
    """
    Ofrece un botón de descarga para el PDF y opcionalmente lo incrusta.
    """
    if pdf_bytes:
        # Generar un enlace de descarga para el PDF
        # Esto es lo más fiable para proporcionar el PDF al usuario en una app web.
        st.download_button(
            label="Descargar PDF",
            data=pdf_bytes,
            file_name="documento_imei.pdf",
            mime="application/pdf",
            help="Haz clic para descargar el PDF asociado al IMEI."
        )
        
        # Opcional: Incrustar el PDF directamente en la página de Streamlit.
        # Funciona mejor para PDFs pequeños. Para PDFs grandes, la descarga es preferible.
        # Algunos navegadores o PDF pueden tener problemas con esta incrustación.
        try:
            b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="700px" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"No se pudo incrustar el PDF en la página (aún puedes descargarlo).\nDetalle: {e}")
    else:
        st.warning("No hay PDF disponible para mostrar o descargar.")

# --- INTERFAZ DE USUARIO CON STREAMLIT ---

st.set_page_config(page_title="Buscador de IMEI y PDF", layout="centered")

st.title("📱 Buscador de IMEI y Documentos PDF")
st.markdown("---") # Separador visual

st.markdown("""
    Ingresa el número IMEI de 15 dígitos del dispositivo para buscar su documento PDF asociado.
""")

# Campo de entrada para el IMEI
imei_input = st.text_input(
    "IMEI del celular (15 dígitos):", 
    max_chars=15, 
    placeholder="Ej: 123456789012345",
    help="El IMEI debe ser un número de 15 dígitos."
)

# Botón para iniciar la búsqueda
if st.button("🔍 Buscar y Mostrar PDF"):
    if not imei_input:
        st.warning("Por favor, ingresa un IMEI.")
    elif len(imei_input) != 15 or not imei_input.isdigit():
        st.warning("El IMEI debe ser un número de 15 dígitos y contener solo números.")
    else:
        # Cargar los datos de la hoja de Google Sheets
        imei_data_map = get_google_sheet_data()
        
        if imei_data_map:
            pdf_url = imei_data_map.get(imei_input)
            
            if pdf_url:
                st.success(f"IMEI '{imei_input}' encontrado. Intentando descargar el PDF...")
                pdf_bytes = download_pdf_as_bytes(pdf_url)
                display_pdf_in_streamlit(pdf_bytes)
            else:
                st.error(f"No se encontró un documento PDF asociado al IMEI '{imei_input}' en la base de datos.")
        # Si get_google_sheet_data() devuelve None, el error ya se mostró