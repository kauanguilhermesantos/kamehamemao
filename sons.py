"""Efeitos sonoros com winsound (já vem no Python do Windows). Em outro sistema, fica mudo."""
import threading

try:
    import winsound
except ImportError:
    winsound = None

ATIVO = winsound is not None

# cada som é uma sequência de (frequência em Hz, duração em ms)
SONS = {
    "estrela": [(1320, 60)],
    "dano": [(180, 220)],
    "inicio": [(523, 90), (659, 90), (784, 140)],
    "fim": [(600, 180), (450, 180), (300, 350)],
    "kame": [(300, 50), (400, 50), (520, 50), (700, 450)],
    "recorde": [(523, 100), (659, 100), (784, 100), (1047, 300)],
    "boss": [(220, 250), (180, 250), (150, 500)],
    "acerto": [(900, 50), (600, 80)],
    "boss_morto": [(392, 120), (523, 120), (659, 120), (784, 120), (1047, 400)],
}


def _tocar(notas):
    for freq, dur in notas:
        winsound.Beep(freq, dur)


def tocar(nome):
    # Beep bloqueia enquanto toca; numa thread o jogo não congela
    if ATIVO:
        threading.Thread(target=_tocar, args=(SONS[nome],), daemon=True).start()
