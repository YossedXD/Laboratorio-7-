# Laboratorio 7
 
 # Punto 1. Aplicación de Análisis de Sentimientos en Paralelo — Explicación Completa (README Markdown)
 Objetivo General

Este módulo implementa un analizador de sentimientos concurrente, capaz de procesar múltiples comentarios en paralelo utilizando:

ThreadPoolExecutor

Mutex (Lock) para evitar race conditions

Diccionarios simples de emociones

Streamlit para interfaz

Estructura reproducible para Docker

La aplicación analiza sentimientos “Positivo / Negativo / Neutro” a partir de palabras clave, demostrando procesamiento en paralelo real.

Arquitectura del Sistema


flowchart LR
    A[Usuario escribe comentarios] --> B[Interfaz Streamlit]
    B --> C[process_batch()]
    C --> D{ThreadPoolExecutor}
    D -->|Hilo 1| E[(worker 1)]
    D -->|Hilo 2| F[(worker 2)]
    D -->|Hilo N| G[(worker N)]
    
    E --> H[(Lista compartida results)]
    F --> H
    G --> H

    H --> I[Mostrar resultados]

   
