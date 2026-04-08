import os
from dotenv import load_dotenv

# Esto calcula la ruta absoluta de la carpeta raíz de tu proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Esto une la ruta raíz con el nombre del archivo .env
env_path = os.path.join(BASE_DIR, '.env')

# Forzamos a dotenv a leer específicamente ese archivo
load_dotenv(dotenv_path=env_path)

# Ahora sí, extraemos la clave
SECRET_KEY = os.getenv("SECRET_KEY")
print(BASE_DIR, SECRET_KEY)

ALGORITHM = "HS256"
