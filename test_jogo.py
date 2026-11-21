"""Testes rápidos da lógica do jogo (sem webcam). Rode: python test_jogo.py"""
import os
import tempfile

import jogo as modulo
import sons
from jogo import Jogo, VIDAS, calcular_direcao, gesto_sair, mao_fechada, separar_maos

sons.ATIVO = False  # testes em silêncio
modulo.ARQUIVO_RECORDE = os.path.join(tempfile.mkdtemp(), "recorde.txt")  # não mexe no recorde real

OMBROS = [(200, 150), (280, 150)]  # largura de ombros = 80 px


def novo_jogo():
    j = Jogo(480, 360)
    j.inicio = False
    j.t_spawn = 99  # sem itens aleatórios
    return j


def segurar_gesto(j):
    for _ in range(11):
        j.atualizar(0.0, 0.1, True)  # 1,1 s segurando o gesto


def test_direcao_pelos_bracos():
    assert calcular_direcao([(190, 250), (290, 250)], OMBROS) == 0.0   # braços relaxados
    assert calcular_direcao([(420, 150)], OMBROS) == 1.0               # braço direito esticado
    assert calcular_direcao([(60, 150)], OMBROS) == -1.0               # braço esquerdo esticado
    assert calcular_direcao([(60, 150), (420, 150)], OMBROS) == 0.0    # os dois se anulam
    assert 0 < calcular_direcao([(350, 150)], OMBROS) < 1              # meio esticado = mais devagar
    assert calcular_direcao([(420, 150)], OMBROS[:1]) == 0.0           # sem os 2 ombros, não move


def test_nave_anda_para_o_lado_e_para_na_borda():
    j = novo_jogo()
    x0 = j.x
    for _ in range(10):
        j.atualizar(1.0, 0.033, False)
    assert j.x > x0
    for _ in range(200):
        j.atualizar(-1.0, 0.033, False)
    assert j.x == 20 and j.vx == 0.0


def test_estrela_da_pontos_e_pedra_tira_vida():
    j = novo_jogo()
    j.itens = [{"tipo": "estrela", "x": j.x, "y": j.y, "r": 13, "vy": 0}]
    j.atualizar(0.0, 0.01, False)
    assert j.estrelas == 1 and j.pontos >= 10

    j.itens = [{"tipo": "pedra", "x": j.x, "y": j.y, "r": 20, "vy": 0}]
    j.atualizar(0.0, 0.01, False)
    assert j.vidas == VIDAS - 1


def test_game_over_salva_recorde_e_reinicia():
    j = novo_jogo()
    j.vidas, j.pontos = 1, 42
    j.itens = [{"tipo": "pedra", "x": j.x, "y": j.y, "r": 20, "vy": 0}]
    j.atualizar(0.0, 0.01, False)
    assert j.fim and j.novo_recorde and j.recorde == 42
    assert Jogo(480, 360).recorde == 42  # recorde lido do arquivo numa nova partida
    segurar_gesto(j)
    assert not j.fim and j.vidas == VIDAS


def test_tela_inicial_comeca_com_gesto():
    j = Jogo(480, 360)
    j.atualizar(1.0, 0.1, False)
    assert j.inicio and j.x == 240  # na tela inicial a nave não se move
    segurar_gesto(j)
    assert not j.inicio


def mao_com(esticados, x=0.0):
    """Mão falsa com pulso em (x, 0) e [indicador, médio, anelar, mínimo] esticados (True) ou dobrados."""
    pts = [(x, 0.0)] * 21
    for k, ((ponta, junta), est) in enumerate(zip(((8, 6), (12, 10), (16, 14), (20, 18)), esticados)):
        pts[junta] = (x + k * 0.02, -0.10)
        pts[ponta] = (x + k * 0.02, -0.16 if est else -0.05)
    return pts


ABERTA, PUNHO = [True] * 4, [False] * 4


def mao_px(x, y):
    """Mão falsa em pixels: pulso em (x, y), base do dedo médio (ponto 9) 30 px acima."""
    pts = [(x, y)] * 21
    pts[9] = (x, y - 30)
    return pts


def test_gesto_sair_maos_juntas_no_peito():
    nariz = 100
    # pelo Pose
    assert gesto_sair([(235, 200), (250, 205)], OMBROS, nariz, [])           # juntas no peito
    assert not gesto_sair([(235, 60), (250, 60)], OMBROS, nariz, [])         # juntas acima do nariz (começar)
    assert not gesto_sair([(190, 250), (290, 250)], OMBROS, nariz, [])       # braços relaxados
    # pelo detector de mãos (quando o Pose não pega os pulsos)
    assert gesto_sair([], [], nariz, [mao_px(230, 200), mao_px(260, 200)])   # 30 px < 1.5 x 30
    assert not gesto_sair([], [], nariz, [mao_px(150, 200), mao_px(330, 200)])
    assert not gesto_sair([], [], nariz, [mao_px(230, 60), mao_px(260, 60)])  # acima do nariz
    assert not gesto_sair([(235, 200), (250, 205)], OMBROS, None, [])        # sem nariz não decide


def test_separar_maos_pela_posicao():
    esq, dir_ = mao_com(ABERTA, x=0.3), mao_com(PUNHO, x=0.7)
    assert separar_maos([dir_, esq], 0.5) == (dir_, esq)     # ordem da lista não importa
    assert separar_maos([esq, dir_], 0.5) == (dir_, esq)
    assert separar_maos([dir_], 0.5) == (dir_, None)         # uma mão: lado do nariz decide
    assert separar_maos([esq], 0.5) == (None, esq)
    assert separar_maos([], 0.5) == (None, None)


def test_kamehameha_ao_fechar_a_mao_esquerda():
    j = novo_jogo()
    j.itens = [{"tipo": "pedra", "x": j.x + 10, "y": 50, "r": 20, "vy": 0},
               {"tipo": "pedra", "x": j.x + 150, "y": 50, "r": 20, "vy": 0}]   # fora do raio
    j.atualizar(0.0, 0.1, False, kame=True)
    assert j.raio_t > 0 and j.destruidas == 1 and len(j.itens) == 1


def test_kamehameha_nao_repete_segurando_e_respeita_recarga():
    j = novo_jogo()
    j.atualizar(0.0, 0.1, False, kame=True)
    for _ in range(50):                                 # 5 s segurando fechada
        j.atualizar(0.0, 0.1, False, kame=True)
    assert j.raio_t == 0                                # não disparou de novo
    j.atualizar(0.0, 0.1, False, kame=False)            # abriu
    j.atualizar(0.0, 0.1, False, kame=True)             # fechou de novo, recarga já passou
    assert j.raio_t > 0
    j.atualizar(0.0, 0.1, False, kame=False)
    j.atualizar(0.0, 0.1, False, kame=True)             # fechou durante a recarga
    assert j.kame_espera > 0 and j.raio_t < 1.2         # não reiniciou o raio


def test_sair_precisa_segurar_1s_e_cancela():
    j = novo_jogo()
    for _ in range(7):
        assert not j.contar_sair(True, 0.1)
    assert not j.contar_sair(False, 0.1)   # separou as mãos: zera
    assert j.t_sair == 0.0
    assert not any(j.contar_sair(True, 0.1) for _ in range(9))
    assert j.contar_sair(True, 0.11)       # completou 1 s


def mao_falsa(dobrados):
    """21 pontos: pulso em (0, 0), dedos apontando para cima; dedos 'dobrados' têm a ponta abaixo da junta."""
    pts = [(0.0, 0.0)] * 21
    for k, (ponta, junta) in enumerate(((8, 6), (12, 10), (16, 14), (20, 18))):
        pts[junta] = (k * 0.02, -0.10)
        pts[ponta] = (k * 0.02, -0.05 if k < dobrados else -0.16)
    return pts


def test_mao_fechada():
    assert mao_fechada(mao_falsa(4))        # punho
    assert mao_fechada(mao_falsa(3))        # quase punho
    assert not mao_fechada(mao_falsa(0))    # mão aberta
    assert not mao_fechada(mao_falsa(2))


def test_acelerar_sobe_e_soltar_volta():
    j = novo_jogo()
    base = j.y
    for _ in range(10):
        j.atualizar(0.0, 0.05, False, acelerando=True)
    assert j.y < base and j.acelerando
    for _ in range(200):
        j.atualizar(0.0, 0.05, False, acelerando=True)
    assert j.y == 40                        # não passa do topo
    for _ in range(200):
        j.atualizar(0.0, 0.05, False)
    assert j.y == base and not j.acelerando


def jogo_no_boss():
    j = novo_jogo()
    j.tempo = 4 * 15          # entra no nível 5
    j.atualizar(0.0, 0.01, False)
    return j


def test_boss_aparece_no_nivel_5_e_trava_o_nivel():
    j = jogo_no_boss()
    assert j.boss is not None and j.nivel == 5
    t = j.tempo
    for _ in range(100):
        j.invuln = 9          # imortal para o teste
        j.atualizar(0.0, 0.1, False)
    assert j.tempo == t and j.boss is not None          # 10 s depois: nível parado, boss vivo
    assert any(it["tipo"] == "poder" for it in j.itens)  # o boss atirou
    assert not any(it["tipo"] == "pedra" for it in j.itens)


def test_kamehameha_tira_5_por_disparo_e_mata_o_boss():
    j = jogo_no_boss()
    vida = j.boss["vida"]
    for disparo in range(vida // 5):
        j.boss["x"], j.kame_espera, j.raio_t = j.x, 0.0, 0.0
        j.atualizar(0.0, 0.01, False, kame=True)             # fecha a mão esquerda
        j.atualizar(0.0, 0.01, False, kame=True)             # raio continua: não acerta 2x
        if j.boss:
            assert j.boss["vida"] == vida - 5 * (disparo + 1)
        j.atualizar(0.0, 0.01, False, kame=False)
    assert j.boss is None and j.bosses_derrotados == 1 and j.proximo_boss == 10
    t = j.tempo
    j.atualizar(0.0, 0.1, False)
    assert j.tempo > t                                       # nível volta a andar


def test_poder_do_boss_tira_vida():
    j = novo_jogo()
    j.itens = [{"tipo": "poder", "x": j.x, "y": j.y, "r": 8, "vx": 0, "vy": 0}]
    j.atualizar(0.0, 0.01, False)
    assert j.vidas == VIDAS - 1


if __name__ == "__main__":
    test_boss_aparece_no_nivel_5_e_trava_o_nivel()
    test_kamehameha_tira_5_por_disparo_e_mata_o_boss()
    test_poder_do_boss_tira_vida()
    test_mao_fechada()
    test_acelerar_sobe_e_soltar_volta()
    test_gesto_sair_maos_juntas_no_peito()
    test_separar_maos_pela_posicao()
    test_kamehameha_ao_fechar_a_mao_esquerda()
    test_kamehameha_nao_repete_segurando_e_respeita_recarga()
    test_sair_precisa_segurar_1s_e_cancela()
    test_direcao_pelos_bracos()
    test_nave_anda_para_o_lado_e_para_na_borda()
    test_estrela_da_pontos_e_pedra_tira_vida()
    test_game_over_salva_recorde_e_reinicia()
    test_tela_inicial_comeca_com_gesto()
    print("OK")
