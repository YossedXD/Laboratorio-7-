# Usar Python oficial
FROM python:3.10

# Crear carpeta de trabajo
WORKDIR /app

# Copiar archivos
COPY requirements.txt .
COPY app.py .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Exponer puerto de Streamlit
EXPOSE 8501

# Comando para ejecutar la app
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
