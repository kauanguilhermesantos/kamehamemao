"""Kamehamemão — Jogo de Controle com as Mãos (MediaPipe Pose + OpenCV) — versão local.

Rode:  python main.py      (tecla Q ou ESC para sair; as métricas aparecem no final)
"""
import os
import time
import urllib.request

import cv2
import matplotlib.pyplot as plt
import mediapipe as mp
import numpy as np

from jogo import ZONA_MORTA, Jogo, calcular_direcao, gesto_sair, mao_fechada, separar_maos
 
# ---------------- Configuração ----------------
MODELO = "lite"        # "lite" (mais rápido), "full" ou "heavy" (mais preciso)
LARGURA, ALTURA = 480, 360   # resolução usada no jogo
VIS_MIN = 0.5          # visibilidade mínima de um landmark para ser usado
CAMERA = 0             # índice da webcam (troque para 1, 2... se tiver mais de uma)
ESCALA_JANELA = 1.5    # aumenta a janela exibida sem custar processamento

# ---------------- Modelo ----------------
URL = (f"https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
       f"pose_landmarker_{MODELO}/float16/latest/pose_landmarker_{MODELO}.task")
PASTA = os.path.dirname(os.path.abspath(__file__))
CAMINHO_MODELO = os.path.join(PASTA, f"pose_landmarker_{MODELO}.task")
URL_MAOS = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
            "hand_landmarker/float16/latest/hand_landmarker.task")
CAMINHO_MAOS = os.path.join(PASTA, "hand_landmarker.task")   # detecta dedos -> mão aberta/fechada

# Índices dos landmarks do MediaPipe Pose
NARIZ, OMBRO_E, OMBRO_D, COTOVELO_E, COTOVELO_D, PULSO_E, PULSO_D = 0, 11, 12, 13, 14, 15, 16
OSSOS = [(OMBRO_E, OMBRO_D), (OMBRO_E, COTOVELO_E), (COTOVELO_E, PULSO_E),
         (OMBRO_D, COTOVELO_D), (COTOVELO_D, PULSO_D)]


def baixar_modelo(url=URL, caminho=CAMINHO_MODELO):
    if not os.path.exists(caminho):
        print("Baixando modelo:", url)
        urllib.request.urlretrieve(url, caminho + ".part")
        os.replace(caminho + ".part", caminho)  # evita arquivo corrompido se o download cair
    print("Modelo pronto:", caminho)


def criar_detector_maos():
    opcoes = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=CAMINHO_MAOS),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return mp.tasks.vision.HandLandmarker.create_from_options(opcoes)


def criar_landmarker():
    opcoes = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=CAMINHO_MODELO),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return mp.tasks.vision.PoseLandmarker.create_from_options(opcoes)


def jogar(landmarker, detector_maos, jogo, M):
    cap = cv2.VideoCapture(CAMERA)
    if not cap.isOpened():
        raise SystemExit(f"Não foi possível abrir a webcam {CAMERA}. Verifique se outra aplicação está usando-a.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    janela = "Kamehamemao  (Q/ESC para sair)"  # sem acento: o título do OpenCV no Windows não mostra "ã"
    cv2.namedWindow(janela, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(janela, int(LARGURA * ESCALA_JANELA), int(ALTURA * ESCALA_JANELA))

    t_ant, fps, ts_ant = None, 0.0, 0
    try:
        while True:
            t_cap = time.perf_counter()
            ok, frame = cap.read()
            if not ok:
                print("Falha ao ler a webcam.")
                break
            t0 = time.perf_counter()

            frame = cv2.flip(frame, 1)                       # efeito espelho
            ts = max(int(time.perf_counter() * 1000), ts_ant + 1)  # timestamps crescentes
            ts_ant = ts

            # --- Hand Landmarker na resolução cheia (dedos pequenos precisam de mais pixels) ---
            rgb_cheio = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res_maos = detector_maos.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_cheio), ts)
            maos = [[(p.x, p.y) for p in mao] for mao in res_maos.hand_landmarks]

            frame = cv2.resize(frame, (LARGURA, ALTURA))

            # --- MediaPipe Pose: 33 landmarks ---
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = landmarker.detect_for_video(mp_img, ts)

            # --- processamento das coordenadas ---
            pulsos, nariz_y, pontos_corpo = [], None, {}
            if res.pose_landmarks:
                lms = res.pose_landmarks[0]
                for i in (NARIZ, OMBRO_E, OMBRO_D, COTOVELO_E, COTOVELO_D, PULSO_E, PULSO_D):
                    lm = lms[i]
                    if lm.visibility is None or lm.visibility >= VIS_MIN:
                        pontos_corpo[i] = (int(lm.x * LARGURA), int(lm.y * ALTURA))
                pulsos = [pontos_corpo[i] for i in (PULSO_E, PULSO_D) if i in pontos_corpo]
                if NARIZ in pontos_corpo:
                    nariz_y = pontos_corpo[NARIZ][1]

            ombros = [pontos_corpo[i] for i in (OMBRO_E, OMBRO_D) if i in pontos_corpo]
            direcao = calcular_direcao(pulsos, ombros)

            # --- mãos: direita/esquerda pela posição em relação ao nariz (não pelo rótulo do MediaPipe) ---
            centro_x = pontos_corpo[NARIZ][0] / LARGURA if NARIZ in pontos_corpo else 0.5
            mao_dir, mao_esq = separar_maos(maos, centro_x)
            acelerando = mao_dir is not None and mao_fechada(mao_dir)   # mão direita fechada = acelerar
            kame = mao_esq is not None and mao_fechada(mao_esq)         # mão esquerda fechada = Kamehameha

            # gesto de reinício: as duas mãos acima do nariz
            gesto = len(pulsos) == 2 and nariz_y is not None and all(p[1] < nariz_y for p in pulsos)

            # --- jogo ---
            agora = time.perf_counter()
            dt = 0.033 if t_ant is None else min(agora - t_ant, 0.1)
            if t_ant is not None:
                inst = 1.0 / max(agora - t_ant, 1e-6)
                fps = inst if fps == 0 else 0.9 * fps + 0.1 * inst
            t_ant = agora
            jogo.atualizar(direcao, dt, gesto, acelerando, kame)
            maos_px = [[(x * LARGURA, y * ALTURA) for x, y in m] for m in maos]
            sair = jogo.contar_sair(gesto_sair(pulsos, ombros, nariz_y, maos_px), dt)

            # --- renderização ---
            tela = (frame * 0.45).astype(np.uint8)           # webcam escurecida como fundo
            for a, b in OSSOS:
                if a in pontos_corpo and b in pontos_corpo:
                    cv2.line(tela, pontos_corpo[a], pontos_corpo[b], (120, 120, 120), 2)
            if len(ombros) == 2:  # linhas azuis: passar a mão delas move a nave
                esq, dir_ = sorted(o[0] for o in ombros)
                folga = int((dir_ - esq) * ZONA_MORTA)
                for x in (esq - folga, dir_ + folga):
                    cv2.line(tela, (x, 0), (x, ALTURA), (255, 200, 0), 1)
            for i in (PULSO_E, PULSO_D):
                if i in pontos_corpo:
                    cv2.circle(tela, pontos_corpo[i], 9, (0, 255, 0), -1)
            jogo.desenhar(tela)

            lat_py = (time.perf_counter() - t0) * 1000
            lat_total = M["lat_total"][-1] if M["lat_total"] else 0.0
            def estado(m):
                return "-" if m is None else "fechada" if mao_fechada(m) else "aberta"
            jogo.hud(tela, f"FPS {fps:.0f} | {lat_py:.0f} ms | dir {direcao:+.1f} | "
                           f"D: {estado(mao_dir)}  E: {estado(mao_esq)}")
            cv2.imshow(janela, tela)
            tecla = cv2.waitKey(1) & 0xFF

            # --- métricas ---
            M["t"].append(agora)
            M["fps"].append(fps)
            M["lat_py"].append(lat_py)
            M["lat_total"].append((time.perf_counter() - t_cap) * 1000)  # captura -> imagem exibida
            M["detectou"].append(len(pulsos) > 0)
            M["ambas"].append(len(pulsos) == 2)
            M["pos"].append((jogo.x, jogo.y))

            fechou = cv2.getWindowProperty(janela, cv2.WND_PROP_VISIBLE) < 1
            if tecla in (ord("q"), ord("Q"), 27) or fechou or sair:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


def relatorio(M, jogo):
    n = len(M["t"])
    if n < 5:
        print("Poucos quadros registrados. Jogue por alguns segundos antes de sair.")
        return
    fps = np.array(M["fps"][5:]) if n > 10 else np.array(M["fps"])
    lat_py = np.array(M["lat_py"])
    lat_tot = np.array(M["lat_total"])
    det = np.mean(M["detectou"]) * 100
    amb = np.mean(M["ambas"]) * 100
    pos = np.array(M["pos"])
    desloc = np.linalg.norm(np.diff(pos, axis=0), axis=1)
    # estabilidade: oscilação (jitter) do objeto nos quadros em que ele quase não se move
    jitter = np.median(desloc)

    print("=" * 52)
    print(f"Quadros processados ........ {n}")
    print(f"FPS medio .................. {fps.mean():.1f}  (min {fps.min():.1f} / max {fps.max():.1f})")
    print(f"Latencia de processamento .. {lat_py.mean():.0f} ms (p95 {np.percentile(lat_py, 95):.0f} ms)  [Pose + jogo + render]")
    print(f"Latencia ponta a ponta ..... {lat_tot.mean():.0f} ms (p95 {np.percentile(lat_tot, 95):.0f} ms)  [captura da webcam -> imagem exibida]")
    print(f"Taxa de deteccao (>=1 mao) . {det:.1f}% dos quadros")
    print(f"Deteccao das 2 maos ........ {amb:.1f}% dos quadros")
    print(f"Estabilidade (jitter med.) . {jitter:.2f} px/quadro  |  desvio do FPS: {fps.std():.1f}")
    print(f"Pontuacao final ............ {int(jogo.pontos)}  (recorde {jogo.recorde}) | estrelas {jogo.estrelas} | pedras esquivadas {jogo.esquivadas} | destruidas pelo Kamehameha {jogo.destruidas}")
    print("=" * 52)
    print("Obs.: 'taxa de acerto' de movimentos exige um conjunto de testes rotulado")
    print("(ex.: pedir 20x 'mao direita para a esquerda' e contar quantos o jogo reconheceu).")

    t = np.array(M["t"]) - M["t"][0]
    fig, ax = plt.subplots(1, 3, figsize=(16, 3.8))
    ax[0].plot(t, M["fps"]); ax[0].set_title("FPS ao longo do tempo"); ax[0].set_xlabel("s"); ax[0].set_ylabel("FPS")
    ax[1].plot(t, M["lat_py"], label="processamento")
    ax[1].plot(t, M["lat_total"], label="ponta a ponta", alpha=0.7)
    ax[1].set_title("Latencia"); ax[1].set_xlabel("s"); ax[1].set_ylabel("ms"); ax[1].legend()
    ax[2].plot(t[1:], desloc); ax[2].set_title("Deslocamento do objeto por quadro (estabilidade)"); ax[2].set_xlabel("s"); ax[2].set_ylabel("px")
    plt.tight_layout(); plt.show()


def main():
    baixar_modelo()
    baixar_modelo(URL_MAOS, CAMINHO_MAOS)
    jogo = Jogo(LARGURA, ALTURA)
    M = {"t": [], "fps": [], "lat_py": [], "lat_total": [], "detectou": [], "ambas": [], "pos": []}
    with criar_landmarker() as landmarker, criar_detector_maos() as detector_maos:
        jogar(landmarker, detector_maos, jogo, M)
    relatorio(M, jogo)


if __name__ == "__main__":
    main()
