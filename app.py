"""
detector_emociones.py
Detector simple de emociones (Felicidad, Tristeza, Furia) usando MediaPipe Face Mesh,
Streamlit, hilos, semáforos y mutex.
"""

import streamlit as st
import cv2
import mediapipe as mp
import threading
import time
import math
from threading import Semaphore, Lock

# ============================
# Configuración MediaPipe
# ============================
mp_face = mp.solutions.face_mesh
mp_dibujo = mp.solutions.drawing_utils

# ============================
# Variables compartidas
# ============================
compartido = {
    "frame": None,
    "frame_anotado": None,
    "texto_emocion": "",
    "activo": False
}

frames_disponibles = Semaphore(0)
candado = Lock()

# ============================
# Parámetros / Umbrales (ajustables)
# ============================
UMBRAL_SONRISA_AMP = 0.38    # ancho relativo de la boca -> felicidad
UMBRAL_BOCAPERTURA = 0.06   # apertura relativa de boca (muy abierta)
UMBRAL_CEJAS_BAJAS = 0.025  # cejas bajas respecto ojos -> furia
UMBRAL_BOCACURVA = -0.015   # pendiente negativa pronunciada -> tristeza

# ============================
# Hilo de cámara
# ============================
def hilo_camara(indice_cam=0):
    cam = cv2.VideoCapture(indice_cam, cv2.CAP_DSHOW)
    if not cam.isOpened():
        with candado:
            compartido["texto_emocion"] = "ERROR: No se pudo abrir la cámara."
            compartido["activo"] = False
        return

    while True:
        with candado:
            if not compartido["activo"]:
                break

        ok, frame = cam.read()
        if not ok:
            continue

        # espejo para interacción natural
        frame = cv2.flip(frame, 1)

        with candado:
            compartido["frame"] = frame

        # señalizamos que hay un frame disponible
        try:
            frames_disponibles.release()
        except:
            pass

        time.sleep(0.01)

    cam.release()

# ============================
# Funciones auxiliares
# ============================
def distancia(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def normalizar(valor, ref):
    """Divide y evita cero"""
    return valor / (ref + 1e-8)

# ============================
# Clasificador heurístico de emociones
# (usa landmarks del Face Mesh)
# ============================
def clasificar_emocion(landmarks, ancho_img, alto_img):
    """
    landmarks: lista de (x,y) en pixeles para los 468 puntos del Face Mesh
    Devuelve: "Felicidad", "Tristeza", "Furia" o "Neutral"
    """

    # --- Puntos usados (indices comunes en Face Mesh) ---
    # Es posible afinar estos índices si la version de FaceMesh cambia.
    # Nosotros usamos:
    # 61 (boca izquierda), 291 (boca derecha), 13 (labio superior), 14 (labio inferior)
    # 33 (ojo izquierdo externo), 263 (ojo derecho externo) -> para ancho de cara (normalizar)
    # 159 (párpado superior izquierdo), 145 (párpado inferior izquierdo)
    # 386 (párpado superior derecho), 374 (párpado inferior derecho)
    # 105 (ceja izquierda interna aproximada), 334 (ceja derecha interna aproximada)
    # 0 (nariz punta) como referencia opcional

    # Convierte índices con seguridad (si faltan, devuelve neutral)
    def p(i):
        if i < 0 or i >= len(landmarks):
            return None
        return landmarks[i]

    p_boca_izq = p(61)
    p_boca_der = p(291)
    p_labio_sup = p(13)
    p_labio_inf = p(14)
    p_ojoi_sup = p(159)
    p_ojoi_inf = p(145)
    p_ojod_sup = p(386)
    p_ojod_inf = p(374)
    p_ceja_izq = p(105)
    p_ceja_der = p(334)
    p_cara_izq = p(33)
    p_cara_der = p(263)

    mandatos = [p_boca_izq, p_boca_der, p_labio_sup, p_labio_inf,
                p_ojoi_sup, p_ojoi_inf, p_ojod_sup, p_ojod_inf,
                p_ceja_izq, p_ceja_der, p_cara_izq, p_cara_der]

    if any(x is None for x in mandatos):
        return "Neutral"

    # --- Medidas en pixeles ---
    boca_ancho = distancia(p_boca_izq, p_boca_der)
    boca_apertura = distancia(p_labio_sup, p_labio_inf)

    # ancho de cara como referencia para normalizar (distancia entre sienes)
    ancho_cara = distancia(p_cara_izq, p_cara_der)

    boca_ancho_rel = normalizar(boca_ancho, ancho_cara)
    boca_apertura_rel = normalizar(boca_apertura, ancho_cara)

    # cejas vs ojos: si la ceja está muy cerca (en Y) del párpado superior -> ceja baja
    # medimos distancia vertical entre ceja interna y párpado superior (normalizada)
    ceja_izq_vs_ojo = (p_ceja_izq[1] - p_ojoi_sup[1]) / (ancho_cara + 1e-8)
    ceja_der_vs_ojo = (p_ceja_der[1] - p_ojod_sup[1]) / (ancho_cara + 1e-8)
    cejas_prom = (ceja_izq_vs_ojo + ceja_der_vs_ojo) / 2.0

    # pendiente entre esquinas de la boca y el centro (para detectar curvatura hacia abajo -> tristeza)
    # centro aproximado de la boca:
    boca_centro_x = (p_boca_izq[0] + p_boca_der[0]) / 2
    boca_centro_y = (p_labio_sup[1] + p_labio_inf[1]) / 2
    # pendiente: (y_corner - y_center) / (x_corner - x_center) ; usamos la media de las dos esquinas
    pendiente_izq = (p_boca_izq[1] - boca_centro_y) / ((p_boca_izq[0] - boca_centro_x) + 1e-8)
    pendiente_der = (p_boca_der[1] - boca_centro_y) / ((p_boca_der[0] - boca_centro_x) + 1e-8)
    pendiente_prom = (pendiente_izq + pendiente_der) / 2.0

    # --- Reglas heurísticas ---
    # 1) Felicidad: boca relativamente ancha y curvada hacia arriba (boca_ancho_rel alto)
    if boca_ancho_rel > UMBRAL_SONRISA_AMP and boca_apertura_rel > UMBRAL_BOCAPERTURA * 0.6:
        return "Felicidad "

    # 2) Furia: cejas bajas (cejas_prom pequeña o negativa) y ojos algo entrecerrados (apertura ocular pequeña)
    # calculamos apertura ocular relativa
    ojo_izq_ap = normalizar(distancia(p_ojoi_sup, p_ojoi_inf), ancho_cara)
    ojo_der_ap = normalizar(distancia(p_ojod_sup, p_ojod_inf), ancho_cara)
    ojo_ap_prom = (ojo_izq_ap + ojo_der_ap) / 2.0

    if cejas_prom < UMBRAL_CEJAS_BAJAS and ojo_ap_prom < 0.085:
        return "Furia "

    # 3) Tristeza: curvatura de la boca hacia abajo (pendiente promedio negativa pronunciada)
    if pendiente_prom < UMBRAL_BOCACURVA:
        return "Tristeza "

    return "Neutral"

# ============================
# Hilo de procesamiento
# ============================
def hilo_procesamiento():
    face_mesh = mp_face.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.5
    )

    while True:
        # esperamos un frame disponible
        frames_disponibles.acquire()

        with candado:
            if not compartido["activo"]:
                frames_disponibles.release()
                break
            frame = compartido["frame"].copy() if compartido["frame"] is not None else None

        if frame is None:
            continue

        alto, ancho, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resultados = face_mesh.process(rgb)

        anotado = frame.copy()
        texto = "Sin cara detectada"

        if resultados.multi_face_landmarks:
            # tomamos la primer cara detectada
            for face_landmarks in resultados.multi_face_landmarks:
                # dibujar mesh
                mp_dibujo.draw_landmarks(anotado, face_landmarks, mp_face.FACEMESH_TESSELATION,
                                         mp_dibujo.DrawingSpec(color=(0,255,0), thickness=1, circle_radius=1),
                                         mp_dibujo.DrawingSpec(color=(0,128,255), thickness=1))

                # convertir a lista de (x,y) en pixeles
                lm = []
                for lm_point in face_landmarks.landmark:
                    lm.append((int(lm_point.x * ancho), int(lm_point.y * alto)))

                emocion = clasificar_emocion(lm, ancho, alto)
                texto = f"Emoción: {emocion}"

                # dibujar texto encima de la cara
                cv2.putText(anotado, emocion, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0), 2, cv2.LINE_AA)

        with candado:
            compartido["frame_anotado"] = anotado
            compartido["texto_emocion"] = texto

    face_mesh.close()

# ============================
# Interfaz Streamlit
# ============================
def main():
    st.set_page_config(page_title="Detector de Emociones (Simple)")
    st.title("Detector de Emociones: Felicidad / Tristeza / Furia")

    boton_iniciar = st.button("Iniciar")
    boton_detener = st.button("Detener")

    zona_video = st.empty()
    zona_texto = st.empty()

    if boton_iniciar:
        with candado:
            if not compartido["activo"]:
                compartido["activo"] = True
                t_cam = threading.Thread(target=hilo_camara, daemon=True)
                t_proc = threading.Thread(target=hilo_procesamiento, daemon=True)
                t_cam.start()
                t_proc.start()

    if boton_detener:
        with candado:
            compartido["activo"] = False

    try:
        while True:
            with candado:
                activo = compartido["activo"]
                anotado = compartido["frame_anotado"]
                texto = compartido["texto_emocion"]

            if anotado is not None:
                rgb = cv2.cvtColor(anotado, cv2.COLOR_BGR2RGB)
                zona_video.image(rgb, channels="RGB")
            else:
                zona_video.text("No hay imagen aún. Pulsa Iniciar.")

            zona_texto.markdown(f"**{texto}**")

            if not activo:
                break

            time.sleep(0.05)
    except Exception as e:
        st.error(f"Error en UI: {e}")
    finally:
        with candado:
            compartido["activo"] = False
        st.write("Aplicación finalizada.")

if __name__ == "__main__":
    main()