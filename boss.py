"""Desenho do boss: o rosto de boss.png (recortado em círculo) num corpo no estilo Piccolo,
feito só com formas do OpenCV, e dos poderes que ele lança."""
import os
import random

import cv2
import numpy as np

ARQUIVO_FOTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boss.png")
_cache = {}

# cores em BGR
VERDE = (60, 175, 70)
VERDE_ESCURO = (30, 110, 40)
ROSA = (170, 120, 245)
AZUL_GI = (110, 45, 25)
FAIXA = (150, 50, 125)
VERMELHO = (40, 40, 210)
AURA = (200, 40, 160)


def _rosto(diametro):
    """Foto redimensionada, levemente esverdeada (namekuseijin), + máscara circular.
    Carregada uma vez por tamanho. None se não houver foto."""
    if diametro not in _cache:
        foto = cv2.imread(ARQUIVO_FOTO)
        if foto is None:
            _cache[diametro] = None
        else:
            foto = cv2.resize(foto, (diametro, diametro), interpolation=cv2.INTER_AREA)
            foto = cv2.addWeighted(foto, 0.72, np.full_like(foto, VERDE), 0.28, 0)
            mascara = np.zeros((diametro, diametro), np.uint8)
            cv2.circle(mascara, (diametro // 2, diametro // 2), diametro // 2 - 1, 255, -1, cv2.LINE_AA)
            _cache[diametro] = (foto, mascara)
    return _cache[diametro]


def _translucido(img, desenhar, alpha):
    copia = img.copy()
    desenhar(copia)
    cv2.addWeighted(copia, alpha, img, 1 - alpha, 0, dst=img)


def _poly(img, pts, cor):
    cv2.fillPoly(img, [np.array(pts, np.int32)], cor, cv2.LINE_AA)


def _p(x, y):
    return int(x), int(y)


def desenhar_boss(img, x, y, r, vida, vida_max, flash=0.0):
    """Boss estilo Piccolo com o rosto da foto (centro da cabeça em x, y): orelhas pontudas, antenas,
    gi azul com emblema, faixa roxa e braços rosa/verde. Barra de vida embaixo.
    flash > 0 = acabou de levar dano."""
    x, y = int(x), int(y)
    ombro_y = y + r - 2

    # aura roxa tremulando atrás de tudo
    pts = []
    for k in range(22):
        ang = 2 * np.pi * k / 22
        alto = np.sin(ang) < 0
        rr = random.uniform(1.0, 1.3 if alto else 1.08)
        pts.append((x + 62 * rr * np.cos(ang), y + 22 + 80 * rr * np.sin(ang)))
    _translucido(img, lambda im: _poly(im, pts, AURA), 0.3)

    # braços: ombro rosa listrado de verde, antebraço verde, munhequeira vermelha, mão verde
    maos = [(x - 38, ombro_y + 32), (x + 38, ombro_y + 32)]
    for s, mao in zip((-1, 1), maos):
        cotovelo = (x + s * 34, ombro_y + 16)
        cv2.line(img, cotovelo, mao, VERDE, 8, cv2.LINE_AA)
        cv2.ellipse(img, (x + s * 27, ombro_y + 7), (10, 12), s * 20, 0, 360, ROSA, -1, cv2.LINE_AA)
        for k in range(3):   # listras verdes no ombro
            yy = ombro_y + 1 + 5 * k
            cv2.line(img, (x + s * 20, yy), (x + s * 34, yy + 2), VERDE, 1, cv2.LINE_AA)
        punho = _p(cotovelo[0] + 0.7 * (mao[0] - cotovelo[0]), cotovelo[1] + 0.7 * (mao[1] - cotovelo[1]))
        cv2.circle(img, punho, 5, VERMELHO, -1, cv2.LINE_AA)
        cv2.circle(img, mao, 6, VERDE, -1, cv2.LINE_AA)

    # gi azul (tronco + parte de baixo), faixa roxa com nó
    _poly(img, [(x - 22, ombro_y), (x + 22, ombro_y), (x + 18, ombro_y + 36), (x - 18, ombro_y + 36)], AZUL_GI)
    _poly(img, [(x - 18, ombro_y + 42), (x + 18, ombro_y + 42), (x + 24, ombro_y + 54), (x - 24, ombro_y + 54)], AZUL_GI)
    cv2.rectangle(img, (x - 19, ombro_y + 34), (x + 19, ombro_y + 43), FAIXA, -1)
    _poly(img, [(x + 6, ombro_y + 41), (x + 13, ombro_y + 52), (x + 2, ombro_y + 52)], FAIXA)
    # emblema redondo no peito com "H" de Haroldo
    centro = (x, ombro_y + 17)
    cv2.circle(img, centro, 10, VERMELHO, -1, cv2.LINE_AA)
    cv2.circle(img, centro, 8, (235, 235, 235), -1, cv2.LINE_AA)
    cv2.putText(img, "H", (x - 5, ombro_y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 30, 20), 2, cv2.LINE_AA)

    # energia roxa nas mãos (de onde saem os tiros)
    for mao in maos:
        _translucido(img, lambda im, m=mao: cv2.circle(im, m, 11, AURA, -1), 0.5)
        cv2.circle(img, mao, 4, (255, 200, 255), -1, cv2.LINE_AA)

    # orelhas pontudas e antenas
    for s in (-1, 1):
        orelha = [(x + s * r * 0.85, y - r * 0.25), (x + s * r * 1.65, y - r * 0.85), (x + s * r * 0.95, y + r * 0.3)]
        _poly(img, orelha, VERDE)
        cv2.polylines(img, [np.array(orelha, np.int32)], True, VERDE_ESCURO, 1, cv2.LINE_AA)
        antena = np.array([_p(x + s * r * 0.25, y - r * 0.9), _p(x + s * r * 0.3, y - r * 1.35),
                           _p(x + s * r * 0.55, y - r * 1.65)], np.int32)
        cv2.polylines(img, [antena], False, VERDE, 3, cv2.LINE_AA)
        cv2.circle(img, _p(x + s * r * 0.55, y - r * 1.65), 3, VERDE, -1, cv2.LINE_AA)

    # cabeça: contorno verde (branco quando leva dano) + foto
    cv2.circle(img, (x, y), r + 2, (255, 255, 255) if flash > 0 else VERDE_ESCURO, 3, cv2.LINE_AA)
    rosto = _rosto(2 * r)
    x0, y0 = x - r, y - r
    h, w = img.shape[:2]
    if rosto is not None and x0 >= 0 and y0 >= 0 and x0 + 2 * r <= w and y0 + 2 * r <= h:
        foto, mascara = rosto
        if flash > 0:  # pisca em vermelho ao ser atingido
            foto = cv2.addWeighted(foto, 0.4, np.full_like(foto, (0, 0, 255)), 0.6, 0)
        area = img[y0:y0 + 2 * r, x0:x0 + 2 * r]
        area[mascara > 0] = foto[mascara > 0]
    else:  # sem boss.png: cabeça verde com "?"
        cv2.circle(img, (x, y), r, VERDE, -1)
        cv2.putText(img, "?", (x - 12, y + 14), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 255), 3)

    # barra de vida (embaixo do corpo)
    bw = 2 * r + 30
    bx, by = x - bw // 2, ombro_y + 60
    cheio = int(bw * max(vida, 0) / vida_max)
    cv2.rectangle(img, (bx, by), (bx + bw, by + 8), (40, 40, 40), -1)
    cv2.rectangle(img, (bx, by), (bx + cheio, by + 8), (0, 0, 230), -1)
    cv2.rectangle(img, (bx, by), (bx + bw, by + 8), (255, 255, 255), 1)
    cv2.putText(img, f"HAROLDO  {max(vida, 0)}/{vida_max}", (bx, by + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)


def desenhar_poder(img, c, r):
    """Esfera de energia roxa lançada pelo boss."""
    copia = img.copy()
    cv2.circle(copia, c, int(r * 1.8), (200, 40, 160), -1)
    cv2.addWeighted(copia, 0.45, img, 0.55, 0, dst=img)
    cv2.circle(img, c, r, (230, 60, 200), -1, cv2.LINE_AA)
    cv2.circle(img, c, max(2, r // 2), (255, 220, 255), -1, cv2.LINE_AA)
