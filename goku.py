"""Desenho do personagem (homenagem ao Goku, feito só com formas do OpenCV) e do Kamehameha."""
import random

import cv2
import numpy as np

# cores em BGR
PELE = (150, 195, 245)
CABELO = (25, 20, 20)
LARANJA = (0, 120, 255)
AZUL = (140, 60, 20)
KI_AURA = (0, 230, 255)
KI_AZUL = (255, 200, 80)
BRANCO = (255, 255, 255)


def _translucido(img, desenhar, alpha):
    """Desenha numa cópia e mistura com a imagem (OpenCV não tem transparência direta)."""
    copia = img.copy()
    desenhar(copia)
    cv2.addWeighted(copia, alpha, img, 1 - alpha, 0, dst=img)


def _esfera_ki(img, c, r):
    _translucido(img, lambda im: cv2.circle(im, c, int(r * 1.8), KI_AZUL, -1), 0.4)
    cv2.circle(img, c, int(r), KI_AZUL, -1, cv2.LINE_AA)
    cv2.circle(img, c, max(1, int(r * 0.55)), BRANCO, -1, cv2.LINE_AA)


def desenhar_raio(img, x, y0, largura):
    """Raio do Kamehameha saindo das mãos (x, y0) até o topo da tela."""
    w = largura + random.randint(-4, 4)  # tremulação
    _translucido(img, lambda im: cv2.rectangle(im, (x - w // 2, 0), (x + w // 2, y0), KI_AZUL, -1), 0.55)
    cv2.rectangle(img, (x - w // 5, 0), (x + w // 5, y0), BRANCO, -1)
    _esfera_ki(img, (x, y0), 10)


def desenhar_goku(img, x, y, acelerando=False, atirando=False):
    """Personagem centrado em (x, y), ~50 px de altura, voando para cima."""
    if acelerando:
        # aura de ki: chama amarela irregular em volta + linhas de velocidade atrás
        pts = []
        for k in range(18):
            ang = 2 * np.pi * k / 18
            alto = np.sin(ang) < 0           # metade de cima tem pontas maiores
            r = (26 if alto else 22) * random.uniform(1.0, 1.35 if alto else 1.1)
            pts.append((x + r * np.cos(ang), y - 2 + r * 1.25 * np.sin(ang)))
        aura = np.array(pts, np.int32)
        _translucido(img, lambda im: cv2.fillPoly(im, [aura], KI_AURA), 0.6)
        cv2.polylines(img, [aura], True, (180, 255, 255), 2, cv2.LINE_AA)
        for _ in range(4):
            lx = x + random.randint(-14, 14)
            ly = y + 28 + random.randint(0, 8)
            cv2.line(img, (lx, ly), (lx, ly + random.randint(14, 32)), BRANCO, 1, cv2.LINE_AA)

    # pernas e botas
    for s in (-1, 1):
        cv2.rectangle(img, (x + s * 1, y + 10), (x + s * 8, y + 20), LARANJA, -1)
        cv2.rectangle(img, (x + s * 1, y + 20), (x + s * 8, y + 25), AZUL, -1)
    # tronco: gi laranja com camiseta azul em V e faixa azul
    cv2.fillPoly(img, [np.array([[x - 11, y - 5], [x + 11, y - 5], [x + 8, y + 10], [x - 8, y + 10]], np.int32)], LARANJA)
    cv2.fillPoly(img, [np.array([[x - 4, y - 5], [x + 4, y - 5], [x, y + 1]], np.int32)], AZUL)
    cv2.rectangle(img, (x - 8, y + 7), (x + 8, y + 10), AZUL, -1)

    # cabeça e cabelo espetado
    cv2.circle(img, (x, y - 12), 7, PELE, -1, cv2.LINE_AA)
    cabelo = [(-8, -11), (-15, -9), (-10, -15), (-14, -22), (-5, -18), (0, -27), (5, -18), (14, -22),
              (10, -15), (15, -9), (8, -11), (5, -15), (-5, -15)]
    cv2.fillPoly(img, [np.array([(x + dx, y + dy) for dx, dy in cabelo], np.int32)], CABELO, cv2.LINE_AA)
    cv2.line(img, (x - 4, y - 12), (x - 2, y - 12), CABELO, 1)   # olhos
    cv2.line(img, (x + 2, y - 12), (x + 4, y - 12), CABELO, 1)

    # braços conforme a pose
    if atirando:
        maos = [(x - 3, y - 27), (x + 3, y - 27)]       # mãos empurradas para frente
    else:
        maos = [(x - 16, y + 6), (x + 16, y + 6)]
    for ombro, mao in zip(((x - 10, y - 4), (x + 10, y - 4)), maos):
        cv2.line(img, ombro, mao, PELE, 4, cv2.LINE_AA)
        punho = (int(ombro[0] + 0.75 * (mao[0] - ombro[0])), int(ombro[1] + 0.75 * (mao[1] - ombro[1])))
        cv2.circle(img, punho, 3, AZUL, -1)              # munhequeira
        cv2.circle(img, mao, 3, PELE, -1)
