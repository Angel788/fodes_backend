import httpx
import re
import hashlib
from bs4 import BeautifulSoup
from typing import List
from pydantic import BaseModel
from urllib.parse import urlparse, urljoin

class Materia(BaseModel):
    grupo: str
    materia: str
    creditos: str
    profesor: str
    lunes: str
    martes: str
    miercoles: str
    jueves: str
    viernes: str

class ResultadoValidacion(BaseModel):
    valido: bool
    boletaCoincide: bool
    periodoVigente: bool
    esEscom: bool
    pk: str
    boletaSAES: str
    periodo: str
    nombre: str
    programa: str
    materias: List[Materia]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept-Language': 'es-MX,es;q=0.9',
}

async def scrape_datos_horario(url_saes: str):
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url_saes, headers=HEADERS, follow_redirects=False)
        
        if 300 <= resp.status_code < 400:
            location = resp.headers.get("location")
            if location:
                location = urljoin(url_saes, location)
                resp = await client.get(location, headers=HEADERS, cookies=resp.cookies)

        soup = BeautifulSoup(resp.text, 'html.parser')
        datos1_div = soup.find(id="Datos1")
        if not datos1_div:
            raise Exception("No se encontró el contenedor #Datos1")
            
        tds = datos1_div.find_all('td')
        datos1_text = " ".join([td.get_text(strip=True) for td in tds])
        datos1_text = re.sub(r'\s+', ' ', datos1_text).strip()

        periodo_match = re.search(r'Periodo escolar:\s*([0-9A-Z]+)', datos1_text, re.IGNORECASE)
        boleta_match = re.search(r'Boleta:\s*([0-9]+)', datos1_text, re.IGNORECASE)
        nombre_match = re.search(r'Nombre del estudiante:\s*(.+?)(?=\s*Programa\s*acad)', datos1_text, re.IGNORECASE)
        programa_match = re.search(r'Programa acad[eé]mico:\s*(.+?)(?=\s*(?:Boleta|Periodo|$))', datos1_text, re.IGNORECASE)

        if not (periodo_match and boleta_match and nombre_match and programa_match):
            raise Exception('No se pudieron extraer los datos del comprobante SAES.')

        materias = []
        datos2_table = soup.find(id="Datos2")
        if datos2_table:
            for row in datos2_table.find_all('tr'):
                tds = row.find_all('td')
                if len(tds) >= 9 and "Materia" not in tds[1].get_text():
                    materias.append(Materia(
                        grupo=tds[0].get_text(strip=True),
                        materia=tds[1].get_text(strip=True),
                        creditos=tds[2].get_text(strip=True),
                        profesor=tds[3].get_text(strip=True),
                        lunes=tds[4].get_text(strip=True),
                        martes=tds[5].get_text(strip=True),
                        miercoles=tds[6].get_text(strip=True),
                        jueves=tds[7].get_text(strip=True),
                        viernes=tds[8].get_text(strip=True),
                    ))

        return {
            "periodo": periodo_match.group(1).strip(),
            "boleta": boleta_match.group(1).strip(),
            "nombre": nombre_match.group(1).strip(),
            "programa": programa_match.group(1).strip(),
            "materias": materias
        }

async def validar_desde_url(id: str, url_saes: str) -> ResultadoValidacion:
    """
    Validación de boleta contra SAES.
    id: boleta del usuario
    url_saes: URL de validación obtenida del QR
    """
    try:
        url_obj = urlparse(url_saes)
    except:
        raise Exception('URL inválida.')

    if url_obj.netloc != 'www.saes.escom.ipn.mx':
        raise Exception('La URL no es de SAES ESCOM.')

    datos = await scrape_datos_horario(url_saes)

    try:
        anio_ingreso = int(datos["boleta"][:4])
        anio_periodo = int(datos["periodo"][:4])
        # Determinar si es periodo 1 (Ago-Dic) o 2 (Ene-Jun)
        # SAES suele usar formato YYYY/1 o YYYY1. Asumimos el primer dígito después del año.
        periodo_tipo = int(datos["periodo"][4]) if len(datos["periodo"]) > 4 else 1
    except:
        raise Exception('Formato de periodo o boleta inválido en SAES.')
        
    # Límite de 6 años (12 semestres)
    anio_limite = anio_ingreso + 6
    
    # Cálculo aproximado de semestre
    # (Anio_actual - Anio_ingreso) * 2 + (1 si es periodo 1, 0 si es periodo 2, etc dependiendo de como ingrese)
    # Simplificado para ESCOM:
    semestre = (anio_periodo - anio_ingreso) * 2 + (1 if periodo_tipo == 1 else 2)

    boleta_coincide = datos["boleta"] == id
    periodo_vigente = (anio_ingreso > 0 and anio_periodo >= anio_ingreso and anio_periodo <= anio_limite)
    es_escom = (len(datos["boleta"]) >= 6 and datos["boleta"][4:6] == '63')

    pk = hashlib.sha256((datos["boleta"] + datos["periodo"]).encode()).hexdigest()[:16]

    es_valido = boleta_coincide and periodo_vigente and es_escom
    
    if not es_valido:
        reasons = []
        if not boleta_coincide: reasons.append("La boleta no coincide")
        if not periodo_vigente: reasons.append("El periodo no es vigente o excede los 6 años")
        if not es_escom: reasons.append("No es una boleta de ESCOM")
        raise Exception(f"Validación rechazada: {', '.join(reasons)}")

    return ResultadoValidacion(
        valido=True,
        boletaCoincide=boleta_coincide,
        periodoVigente=periodo_vigente,
        esEscom=es_escom,
        pk=pk,
        boletaSAES=datos["boleta"],
        periodo=datos["periodo"],
        nombre=datos["nombre"],
        programa=datos["programa"],
        materias=datos["materias"]
    )
