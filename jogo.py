import math
import os
import random

import cv2
import numpy as np

import sons
from boss import desenhar_boss, desenhar_poder
from goku import desenhar_goku, desenhar_raio

VIDAS = 3
ARQUIVO_RECORDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recorde.txt")
VEL_MAX = 420      # velocidade lateral máxima do personagem (px/s)
ZONA_MORTA = 0.35  # mão até 35% da largura de ombros para fora do ombro não move (braço relaxado)
ALCANCE = 0.6      # quanto além da zona morta a mão precisa ir para a velocidade máxima

VEL_SUBIR = 220    # px/s subindo com as duas mãos fechadas
VEL_DESCER = 140   # px/s voltando para a base ao abrir as mãos
TEMPO_SAIR = 1.0   # segundos com as mãos juntas no peito para fechar o jogo

TEMPO_RAIO = 1.2   # duração do raio
ESPERA_KAME = 4.0   # recarga depois de disparar
LARGURA_RAIO = 34   # px

BOSS_A_CADA = 5     # boss no nível 5, 10, 15...
BOSS_R = 32         # raio do rosto do boss (px)
BOSS_Y = 78         # altura do centro do rosto do boss
BOSS_BASE = BOSS_Y + BOSS_R + 70   # abaixo do corpo e da barra de vida: o Goku não sobe além disso
DANO_KAME = 5       # vida que cada Kamehameha tira do boss


def nova_forma_pedra():
    """Sorteia o visual de um asteroide: contorno irregular, cor, crateras e rotação."""
    n = random.randint(9, 13)
    tom = random.randint(-15, 15)
    return {
        "forma": [random.uniform(0.72, 1.08) for _ in range(n)],   # raio de cada vértice (x r)
        "cor": (95 + tom, 105 + tom, 120 + tom),                      # cinza amarronzado (BGR)
        "crateras": [(random.uniform(-0.45, 0.45), random.uniform(-0.45, 0.45), random.uniform(0.15, 0.28))
                     for _ in range(random.randint(2, 4))],           # (dx, dy, raio) em fração de r
        "ang": random.uniform(0, 2 * math.pi),
        "giro": random.uniform(-2.5, 2.5),                            # rad/s
    }


def desenhar_pedra(img, c, it):
    r, ang, cor = it["r"], it["ang"], it["cor"]
    n = len(it["forma"])
    pts = [(c[0] + r * f * math.cos(ang + 2 * math.pi * k / n), c[1] + r * f * math.sin(ang + 2 * math.pi * k / n))
           for k, f in enumerate(it["forma"])]
    contorno = np.array(pts, np.int32)
    escuro = tuple(int(v * 0.55) for v in cor)
    claro = tuple(min(255, int(v * 1.45)) for v in cor)
    cv2.fillPoly(img, [contorno], escuro)                            # sombra (lado de baixo/direita)
    cv2.fillPoly(img, [(contorno - [2, 2]).astype(np.int32)], cor)   # corpo deslocado = luz vindo de cima
    for dx, dy, cr in it["crateras"]:                                # crateras giram junto com a pedra
        px = c[0] + r * (dx * math.cos(ang) - dy * math.sin(ang))
        py = c[1] + r * (dx * math.sin(ang) + dy * math.cos(ang))
        raio = max(2, int(r * cr))
        cv2.circle(img, (int(px), int(py)), raio, escuro, -1)
        cv2.circle(img, (int(px) + 1, int(py) + 1), raio, claro, 1)
    cv2.polylines(img, [contorno], True, claro, 1, cv2.LINE_AA)


def dedos_esticados(pts):
    """pts: 21 pontos (x, y) do Hand Landmarker. Devolve [indicador, médio, anelar, mínimo] (polegar fora):
    esticado = ponta do dedo mais longe do pulso do que a junta do meio."""
    def dist(i):
        return math.hypot(pts[i][0] - pts[0][0], pts[i][1] - pts[0][1])
    return [dist(ponta) > dist(junta) for ponta, junta in ((8, 6), (12, 10), (16, 14), (20, 18))]


def mao_fechada(pts):
    """Punho: pelo menos 3 dos 4 dedos dobrados."""
    return dedos_esticados(pts).count(False) >= 3


def gesto_sair(pulsos, ombros, nariz_y, maos_px):
    """Mãos juntas na frente do peito (palma com palma). Basta um dos dois detectores reconhecer:

    1. Pose: os 2 pulsos a menos de 0.6 largura de ombros um do outro, abaixo do nariz.
    2. Detector de mãos (pontos em pixels): pulsos a menos de 1.5x o tamanho da mão
       (pulso -> base do dedo médio), abaixo do nariz.
    Não depende de saber qual mão é a direita.
    """
    if nariz_y is None:
        return False
    if len(pulsos) >= 2 and len(ombros) >= 2:
        larg = abs(ombros[0][0] - ombros[1][0])
        (x1, y1), (x2, y2) = pulsos[:2]
        if math.hypot(x1 - x2, y1 - y2) < 0.6 * larg and y1 > nariz_y and y2 > nariz_y:
            return True
    if len(maos_px) >= 2:
        a, b = maos_px[:2]
        tam = (math.dist(a[0], a[9]) + math.dist(b[0], b[9])) / 2
        if math.dist(a[0], b[0]) < 1.5 * tam and a[0][1] > nariz_y and b[0][1] > nariz_y:
            return True
    return False


def separar_maos(maos, centro_x):
    """Decide qual mão é a direita pela POSIÇÃO na imagem espelhada (sua direita aparece à direita),
    sem confiar no rótulo do MediaPipe. Com 2 mãos: a mais à direita é a direita.
    Com 1 mão: compara com o centro do corpo (centro_x). Devolve (direita, esquerda); None se faltar."""
    if len(maos) >= 2:
        a, b = sorted(maos[:2], key=lambda m: m[0][0])
        return b, a
    if len(maos) == 1:
        return (maos[0], None) if maos[0][0][0] > centro_x else (None, maos[0])
    return None, None


def calcular_direcao(pulsos, ombros):
    """De -1 (esquerda) a 1 (direita): quanto cada mão passa para fora do ombro do mesmo lado da tela.

    Medido em larguras de ombro, então funciona perto ou longe da câmera. Dois braços esticados se anulam.
    """
    if len(ombros) < 2 or not pulsos:
        return 0.0
    esq, dir_ = min(o[0] for o in ombros), max(o[0] for o in ombros)
    larg = max(dir_ - esq, 1)
    d = 0.0
    for x, _ in pulsos:
        if x > dir_:
            d += max(0.0, (x - dir_) / larg - ZONA_MORTA)
        elif x < esq:
            d -= max(0.0, (esq - x) / larg - ZONA_MORTA)
    return max(-1.0, min(1.0, d / ALCANCE))


def ler_recorde():
    try:
        with open(ARQUIVO_RECORDE) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def salvar_recorde(valor):
    try:
        with open(ARQUIVO_RECORDE, "w") as f:
            f.write(str(valor))
    except OSError as e:
        print("Não foi possível salvar o recorde:", e)


class Jogo:
    """Jogo em coordenadas de pixel. O Goku segue as mãos; pedras tiram vida, estrelas dão pontos.

    Começa na tela inicial: o jogador levanta as duas mãos acima do nariz por 1 s para começar.
    """

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.recorde = ler_recorde()
        self.inicio = True
        self.t_sair = 0.0
        self.reiniciar()

    def contar_sair(self, gesto, dt):
        """Soma o tempo do gesto de sair (vale em qualquer tela). True = hora de fechar."""
        self.t_sair = self.t_sair + dt if gesto else 0.0
        return self.t_sair >= TEMPO_SAIR

    def reiniciar(self):
        self.x, self.y = self.w / 2, self.h * 0.8
        self.vx = 0.0
        self.acelerando = False
        self.pontos = 0.0
        self.vidas = VIDAS
        self.itens = []
        self.t_spawn = 0.8
        self.tempo = 0.0
        self.invuln = 0.0
        self.fim = False
        self.novo_recorde = False
        self.seguro = 0.0       # tempo segurando o gesto de início/reinício
        self.esquivadas = 0
        self.estrelas = 0
        self.esq_antes = False  # mão esquerda estava fechada no quadro anterior
        self.raio_t = 0.0       # tempo restante do raio
        self.kame_espera = 0.0  # recarga
        self.destruidas = 0
        self.raio_acertou = False   # o raio atual já tirou vida do boss (1 acerto por disparo)
        self.boss = None
        self.proximo_boss = BOSS_A_CADA
        self.bosses_derrotados = 0
        self.aviso, self.aviso_t, self.aviso_topo = [], 0.0, 210 # mensagem grande temporária no meio da tela

    @property
    def nivel(self):
        return 1 + int(self.tempo // 15)

    def _avisar(self, linhas, segundos=2.5, topo=210):
        """linhas: [(texto, tamanho, cor BGR), ...] mostradas a partir da altura `topo` por alguns segundos."""
        self.aviso, self.aviso_t, self.aviso_topo = linhas, segundos, topo

    def _levar_dano(self):
        if self.invuln > 0:
            return
        self.vidas -= 1
        self.invuln = 1.0
        if self.vidas > 0:
            sons.tocar("dano")

    def _criar_boss(self):
        n = self.proximo_boss // BOSS_A_CADA      # 1º, 2º, 3º boss... cada um mais forte
        vida = 20 + 10 * (n - 1)
        self.boss = {"x": self.w / 2, "vida": vida, "vida_max": vida, "vx": 80 + 30 * n,
                     "t_tiro": 2.0, "n": n, "flash": 0.0}
        self.itens = [it for it in self.itens if it["tipo"] == "estrela"]   # limpa as pedras
        self._avisar([("BOSS: HAROLDO CHEGOU!", 0.8, (60, 60, 255))])
        sons.tocar("boss")

    def _atualizar_boss(self, dt):
        b = self.boss
        # anda de um lado para o outro
        b["x"] += b["vx"] * dt
        margem = BOSS_R + 24   # ombreiras e mãos passam do rosto
        if not margem <= b["x"] <= self.w - margem:
            b["x"] = min(max(b["x"], margem), self.w - margem)
            b["vx"] = -b["vx"]
        b["flash"] = max(0.0, b["flash"] - dt)

        # lança poderes mirando no Goku (a partir do 2º boss, em leque de 3)
        b["t_tiro"] -= dt
        if b["t_tiro"] <= 0:
            n = b["n"]
            b["t_tiro"] = max(0.6, 1.6 - 0.25 * n)
            origem_y = BOSS_Y + BOSS_R + 28          # altura das mãos do boss
            ang = math.atan2(self.y - origem_y, self.x - b["x"])
            vel = 170 + 30 * n
            for desvio in ((0.0,) if n == 1 else (-0.3, 0.0, 0.3)):
                self.itens.append({"tipo": "poder", "x": b["x"], "y": origem_y, "r": 8,
                                   "vx": vel * math.cos(ang + desvio), "vy": vel * math.sin(ang + desvio)})

        # Kamehameha acerta o boss (uma vez por disparo)
        if self.raio_t > 0 and not self.raio_acertou and abs(b["x"] - self.x) < BOSS_R + LARGURA_RAIO / 2:
            self.raio_acertou = True
            b["vida"] -= DANO_KAME
            b["flash"] = 0.3
            if b["vida"] <= 0:
                self.pontos += 50 * b["n"]
                self.bosses_derrotados += 1
                self.boss = None
                self.proximo_boss += BOSS_A_CADA
                self._avisar([("HAROLDO DERROTADO!", 0.7, (60, 60, 255)),
                              ("PARABENS!", 1.3, (0, 215, 255)),
                              ("VOCE GANHOU 10 NO TRABALHO!", 0.65, (0, 215, 255))], 4.0, topo=110)
                sons.tocar("boss_morto")
                return
            sons.tocar("acerto")

        # encostar no boss machuca
        if math.hypot(b["x"] - self.x, BOSS_Y - self.y) < BOSS_R + 18:
            self._levar_dano()

    def atualizar(self, direcao, dt, gesto, acelerando=False, kame=False):
        """direcao: de -1 (esquerda) a 1 (direita), vinda de calcular_direcao().
        acelerando: mão direita fechada -> o personagem sobe.
        kame: mão esquerda fechada -> dispara o Kamehameha no momento em que fecha."""
        # --- tela inicial: gesto para começar ---
        if self.inicio:
            self.seguro = self.seguro + dt if gesto else 0.0
            if self.seguro >= 1.0:
                self.inicio = False
                self.reiniciar()
                sons.tocar("inicio")
            return

        # --- tela de game over: gesto de reinício ---
        if self.fim:
            self.seguro = self.seguro + dt if gesto else 0.0
            if self.seguro >= 1.0:
                self.reiniciar()
                sons.tocar("inicio")
            return

        # --- movimento lateral: braço esticado = acelera para aquele lado (suavizado) ---
        a = 1 - math.exp(-dt * 10)
        self.vx += (direcao * VEL_MAX - self.vx) * a
        self.x += self.vx * dt
        if not 20 <= self.x <= self.w - 20:
            self.x = min(max(self.x, 20), self.w - 20)
            self.vx = 0.0

        # --- Kamehameha: dispara quando a mão esquerda FECHA (segurar fechada não repete) ---
        self.kame_espera = max(0.0, self.kame_espera - dt)
        self.raio_t = max(0.0, self.raio_t - dt)
        if kame and not self.esq_antes and self.raio_t == 0 and self.kame_espera == 0:
            self.raio_t, self.kame_espera = TEMPO_RAIO, ESPERA_KAME
            self.raio_acertou = False
            sons.tocar("kame")
        self.esq_antes = kame

        # --- acelerar: mãos fechadas sobem o personagem; abertas, ele volta para a base ---
        self.acelerando = acelerando
        topo = BOSS_BASE + 27 if self.boss else 40   # com boss, não sobe por cima dele
        if acelerando:
            self.y = max(topo, self.y - VEL_SUBIR * dt)
        else:
            self.y = min(self.h * 0.8, max(topo, self.y + VEL_DESCER * dt))

        self.pontos += dt * 2
        self.invuln = max(0.0, self.invuln - dt)
        self.aviso_t = max(0.0, self.aviso_t - dt)

        # --- boss a cada 5 níveis: o nível só avança depois de derrotá-lo ---
        if self.boss is None and self.nivel >= self.proximo_boss:
            self._criar_boss()
        if self.boss:
            self._atualizar_boss(dt)
        else:
            self.tempo += dt   # relógio dos níveis parado durante a luta

        # --- obstáculos e estrelas (durante o boss, só estrelas) ---
        self.t_spawn -= dt
        if self.t_spawn <= 0:
            self.t_spawn = max(0.30, 0.95 - 0.08 * self.nivel)
            estrela = random.random() < 0.30
            if estrela or not self.boss:   # durante o boss não caem pedras
                r = 13 if estrela else random.randint(16, 28)
                item = {
                    "tipo": "estrela" if estrela else "pedra",
                    "x": random.uniform(r, self.w - r), "y": -r, "r": r,
                    "vy": random.uniform(110, 160) + 25 * self.nivel,
                }
                if not estrela:
                    item.update(nova_forma_pedra())
                self.itens.append(item)

        restantes = []
        for it in self.itens:
            it["x"] += it.get("vx", 0.0) * dt
            it["y"] += it["vy"] * dt
            it["ang"] = it.get("ang", 0.0) + it.get("giro", 0.0) * dt
            perigo = it["tipo"] in ("pedra", "poder")
            no_raio = abs(it["x"] - self.x) < it["r"] + LARGURA_RAIO / 2 and it["y"] < self.y
            if self.raio_t > 0 and perigo and no_raio:   # o raio destrói pedras e poderes do boss
                if it["tipo"] == "pedra":
                    self.destruidas += 1
                    self.pontos += 3
                continue
            colidiu = math.hypot(it["x"] - self.x, it["y"] - self.y) < it["r"] + 18
            if colidiu and it["tipo"] == "estrela":
                self.pontos += 10
                self.estrelas += 1
                sons.tocar("estrela")
                continue
            if colidiu and perigo and self.invuln <= 0:
                self._levar_dano()
                continue
            fora = it["y"] - it["r"] > self.h or it["y"] < -3 * it["r"] or not -it["r"] < it["x"] < self.w + it["r"]
            if fora:
                if it["tipo"] == "pedra":
                    self.esquivadas += 1
                    self.pontos += 1
                continue
            restantes.append(it)
        self.itens = restantes

        if self.vidas <= 0:
            self.fim = True
            self.seguro = 0.0
            self.novo_recorde = int(self.pontos) > self.recorde
            if self.novo_recorde:
                self.recorde = int(self.pontos)
                salvar_recorde(self.recorde)
                sons.tocar("recorde")
            else:
                sons.tocar("fim")

    # ---------------- Desenho ----------------
    def desenhar(self, img):
        if self.inicio:
            return
        for it in self.itens:
            c = (int(it["x"]), int(it["y"]))
            if it["tipo"] == "pedra":
                desenhar_pedra(img, c, it)
            elif it["tipo"] == "poder":
                desenhar_poder(img, c, it["r"])
            else:
                pts = []
                for k in range(10):
                    ang = -math.pi / 2 + k * math.pi / 5
                    rr = it["r"] if k % 2 == 0 else it["r"] * 0.45
                    pts.append([c[0] + rr * math.cos(ang), c[1] + rr * math.sin(ang)])
                cv2.fillPoly(img, [np.array(pts, np.int32)], (0, 220, 255))

        if self.boss and not self.fim:
            b = self.boss
            desenhar_boss(img, b["x"], BOSS_Y, BOSS_R, b["vida"], b["vida_max"], b["flash"])

        piscar = self.invuln > 0 and int(self.invuln * 10) % 2 == 0
        if not piscar and not self.fim:
            x, y = int(self.x), int(self.y)
            if self.raio_t > 0:
                desenhar_raio(img, x, y - 30, LARGURA_RAIO)
            desenhar_goku(img, x, y, self.acelerando, self.raio_t > 0)

    def _texto(self, img, txt, y, escala, cor, esp=1):
        """Texto centralizado na horizontal."""
        (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, escala, esp)
        cv2.putText(img, txt, ((self.w - tw) // 2, y), cv2.FONT_HERSHEY_SIMPLEX, escala, cor, esp)

    def _barra(self, img, y):
        if self.seguro > 0:
            barra = int(200 * min(self.seguro, 1.0))
            cv2.rectangle(img, (self.w // 2 - 100, y), (self.w // 2 + 100, y + 12), (255, 255, 255), 1)
            cv2.rectangle(img, (self.w // 2 - 100, y), (self.w // 2 - 100 + barra, y + 12), (0, 255, 0), -1)

    def hud(self, img, extra):
        cv2.putText(img, extra, (10, self.h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 255, 200), 1)
        if self.t_sair > 0:
            self._texto(img, "Saindo... (separe as maos para cancelar)", self.h - 50, 0.5, (80, 80, 255))
            barra = int(200 * min(self.t_sair / TEMPO_SAIR, 1.0))
            y = self.h - 42
            cv2.rectangle(img, (self.w // 2 - 100, y), (self.w // 2 + 100, y + 10), (255, 255, 255), 1)
            cv2.rectangle(img, (self.w // 2 - 100, y), (self.w // 2 - 100 + barra, y + 10), (60, 60, 255), -1)

        if self.inicio:
            self._texto(img, "JOGO DAS MAOS", 60, 1.2, (0, 220, 255), 3)
            self._texto(img, f"Recorde: {self.recorde}", 95, 0.7, (255, 255, 255), 2)
            self._texto(img, "Estique um braco para o lado -> voa para aquele lado", 128, 0.48, (255, 255, 255))
            self._texto(img, "Feche a mao DIREITA -> acelera para frente", 157, 0.48, (0, 200, 255))
            self._texto(img, "Feche a mao ESQUERDA -> Kamehameha!", 186, 0.48, (255, 200, 80))
            self._texto(img, "Levante as duas maos acima do nariz", 230, 0.55, (255, 255, 255))
            self._texto(img, "por 1 segundo para comecar", 250, 0.55, (255, 255, 255))
            self._barra(img, 262)
            self._texto(img, "Para sair: junte as maos no peito (palma com palma)", 300, 0.45, (180, 180, 255))
            return

        nivel = f"{self.nivel} BOSS" if self.boss else str(self.nivel)
        cv2.putText(img, f"Pontos: {int(self.pontos)}   Nivel: {nivel}   Recorde: {self.recorde}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(img, f"Vidas: {max(self.vidas, 0)}", (10, 52),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 255), 2)
        if not self.fim:
            if self.kame_espera > 0:
                status, cor = f"Kamehameha: recarregando {math.ceil(self.kame_espera)}s", (160, 160, 160)
            else:
                status, cor = "Kamehameha: pronto", (255, 200, 80)
            cv2.putText(img, status, (10, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor, 1)
            if self.aviso_t > 0:
                altura = sum(int(32 * tam) + 12 for _, tam, _ in self.aviso)
                topo = self.aviso_topo
                faixa = img[max(topo - 8, 0):topo + altura + 4]   # caixa escura atrás do texto
                faixa[:] = (faixa * 0.35).astype(np.uint8)
                y = topo
                for texto, tam, cor in self.aviso:
                    y += int(32 * tam)
                    self._texto(img, texto, y, tam, cor, 3 if tam > 1 else 2)
                    y += 12
            elif self.raio_t > TEMPO_RAIO - 0.8:
                self._texto(img, "KAMEHAMEHA!", 205, 1.2, (255, 230, 150), 3)
        if self.fim:
            self._texto(img, "GAME OVER", self.h // 2 - 20, 1.2, (0, 0, 255), 3)
            if self.novo_recorde:
                self._texto(img, "NOVO RECORDE!", self.h // 2 - 60, 0.9, (0, 220, 255), 2)
            self._texto(img, f"Pontos {int(self.pontos)}  Recorde {self.recorde}", self.h // 2 + 15, 0.7, (255, 255, 255), 2)
            self._texto(img, "Levante as duas maos acima do nariz p/ reiniciar", self.h // 2 + 45, 0.5, (255, 255, 255))
            self._barra(img, self.h // 2 + 60)
