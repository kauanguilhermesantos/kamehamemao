# Kamehamemão — Jogo de Controle com as Mãos (MediaPipe + OpenCV)

Jogo controlado pelo corpo diante da webcam. Você controla um lutador de cabelo espetado (homenagem ao
Goku): desvia de asteroides, coleta estrelas, dispara o Kamehameha e, a cada 5 níveis, enfrenta o boss
**Haroldo** (homenagem ao Piccolo, com o rosto do professor). Tudo é desenhado com formas do OpenCV, sem
imagens oficiais. A única imagem usada é `boss.png` (o rosto do boss).

---

## 1. Instalação e execução

Requisitos: Windows, Python 3.12 ou 3.13 e uma webcam.

```powershell
# uma vez
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt

# para jogar
.\.venv\Scripts\python main.py

# testes da lógica (sem webcam)
.\.venv\Scripts\python test_jogo.py
```

Na primeira execução, o jogo baixa sozinho os modelos `pose_landmarker_lite.task` (corpo) e
`hand_landmarker.task` (mãos), que ficam salvos na pasta do projeto.

---

## 2. Como jogar (gestos)

| Gesto | Ação | Onde vale |
|---|---|---|
| Levantar as duas mãos acima do nariz por **1 s** | começar / reiniciar | tela inicial e game over |
| Esticar um braço para o lado (passar da linha azul) | voar para aquele lado; mais esticado = mais rápido | partida |
| Fechar a mão **direita** | acelerar para frente (aura de ki); abrir = voltar para baixo | partida |
| Fechar a mão **esquerda** | disparar o **Kamehameha** (recarga de 4 s) | partida |
| Juntar as mãos na frente do peito (palma com palma) por **1 s** | fechar o jogo | qualquer tela |
| Tecla **Q** / **ESC** ou fechar a janela | fechar o jogo | qualquer tela |

O rodapé da janela mostra, em tempo real: FPS, tempo de processamento, direção lida (`dir`, de -1 a +1) e
o estado de cada mão (`D:` direita e `E:` esquerda, aberta ou fechada). Use isso para conferir se os gestos
estão sendo reconhecidos.

**Dicas:** fique de frente para a câmera, com os ombros, o nariz e as mãos dentro do quadro. Deixe as mãos
com a palma virada para a câmera, para os dedos aparecerem bem.

---

## 3. Funcionamento geral (pipeline)

A cada quadro, `main.py` executa:

1. **Captura**: lê um quadro da webcam (pedido em 640×480) com `cv2.VideoCapture` e **espelha** a imagem
   (efeito espelho: sua mão direita aparece do lado direito da tela).
2. **Mãos**: o *Hand Landmarker* do MediaPipe roda na imagem em resolução cheia (dedos são pequenos e
   precisam de mais pixels) e devolve **21 pontos por mão**, até 2 mãos.
3. **Corpo**: a imagem é reduzida para **480×360** (a resolução do jogo) e o *Pose Landmarker* devolve
   **33 pontos do corpo**. O jogo usa: nariz (0), ombros (11, 12), cotovelos (13, 14) e pulsos (15, 16).
   Só entram pontos com visibilidade ≥ 0,5 (`VIS_MIN`).
4. **Gestos**: os pontos viram comandos (direção, acelerar, Kamehameha, começar, sair), como explicado na seção 4.
5. **Lógica**: `Jogo.atualizar()` move o personagem, cria e move os itens, testa colisões, cuida do boss,
   dos níveis e da pontuação.
6. **Desenho**: a webcam escurecida (45% do brilho) vira o fundo. Por cima vão o esqueleto (cinza), as linhas
   azuis, os pulsos (verde), os itens, o boss, o personagem e o placar. O resultado aparece numa janela
   OpenCV ampliada em 1,5×.

O passo de tempo `dt` é o tempo real entre quadros, **limitado a 0,1 s**. Assim, um travamento não faz os
objetos "teleportarem". Todos os movimentos são em pixels por segundo, então o jogo roda na mesma velocidade
com qualquer FPS.

---

## 4. Cálculos dos gestos

### 4.1 Direção lateral (braço esticado)

Função `calcular_direcao()` em `jogo.py`. Tudo é medido em **larguras de ombro**, então funciona igual perto
ou longe da câmera.

1. `largura` = distância horizontal entre os dois ombros (em pixels).
2. As **linhas azuis** ficam do lado de fora de cada ombro, a `ZONA_MORTA × largura` (0,35 ×).
   Entre as duas linhas fica a "caixa": mão dentro dela não move nada (braços relaxados).
3. Para cada pulso que passou da linha:

   ```
   força = (distância além da linha ÷ largura)
   ```

   positiva se a mão está à direita e negativa se está à esquerda.
4. `direção = soma das forças ÷ ALCANCE` (0,6), limitada a **-1 … +1**.
   Os dois braços esticados se anulam (direção 0).

Exemplo com ombros a 80 px de distância: a linha azul fica a 0,35 × 80 = **28 px** do ombro, e a velocidade
máxima chega com a mão a 28 + 0,6 × 80 = **76 px** do ombro.

O personagem não "pula" para a direção. A velocidade é suavizada:

```
vx = vx + (direção × VEL_MAX − vx) × (1 − e^(−10·dt))        VEL_MAX = 420 px/s
```

Ele fica entre x = 20 e x = largura − 20. Ao bater na borda, a velocidade zera.
Se faltar um ombro na imagem, a direção é 0 (o personagem para).

### 4.2 Qual mão é a direita e qual é a esquerda

Função `separar_maos()`. O rótulo "Left/Right" do MediaPipe **não é usado**, porque ele se mostrou instável.
A decisão é pela **posição na imagem espelhada**:

- **2 mãos detectadas:** a que está mais à direita na tela é a sua mão direita.
- **1 mão detectada:** se ela está à direita do nariz, é a direita; senão, é a esquerda.
  Sem nariz visível, o centro da imagem é usado.

### 4.3 Mão fechada (punho)

Funções `dedos_esticados()` e `mao_fechada()`. Para cada um dos 4 dedos (indicador, médio, anelar e mínimo;
o polegar fica de fora), o jogo compara duas distâncias até o pulso (ponto 0):

```
dedo esticado  ⇔  dist(ponta do dedo, pulso) > dist(junta do meio, pulso)
pontas: 8, 12, 16, 20     juntas do meio: 6, 10, 14, 18
```

**Mão fechada = pelo menos 3 dos 4 dedos dobrados.** Como é uma comparação entre distâncias da própria mão,
não depende do tamanho da mão na imagem.

- Mão **direita** fechada → `acelerando`.
- Mão **esquerda** fechada → `kame` (Kamehameha).

### 4.4 Começar / reiniciar

Os dois pulsos (Pose) visíveis e **acima do nariz**, segurados por **1 s**. Uma barra verde mostra o progresso.
Se a pose for desfeita antes, a contagem zera.

### 4.5 Sair do jogo (mãos juntas no peito)

Função `gesto_sair()`. Basta **um** dos dois detectores reconhecer, e ambos exigem as mãos **abaixo do nariz**
(para não confundir com o gesto de começar):

1. **Pose:** distância entre os dois pulsos < **0,6 × largura dos ombros**.
2. **Detector de mãos:** distância entre os pulsos das duas mãos < **1,5 × tamanho da mão**, sendo
   tamanho da mão = distância do pulso (ponto 0) até a base do dedo médio (ponto 9). Serve para quando o
   Pose perde os pulsos com as mãos coladas.

O gesto precisa ser segurado por `TEMPO_SAIR` = **1 s** (barra vermelha "Saindo..."). Separar as mãos cancela.

---

## 5. Mecânicas do jogo

### 5.1 Personagem

- Fica numa base a **80% da altura** da tela (y = 288 px).
- **Acelerar** (mão direita fechada): sobe a `VEL_SUBIR` = 220 px/s, até y = 40 (topo).
  Ao abrir a mão, volta para a base a `VEL_DESCER` = 140 px/s. Enquanto acelera, aparecem a aura de ki
  amarela e as linhas de velocidade.
- **Colisão:** um item encosta no personagem quando a distância entre os centros é menor que
  `raio do item + 18 px`.
- **Vidas:** começa com **3**. Ao levar dano, fica **1 s invulnerável** (piscando).

### 5.2 Itens que caem

A cada intervalo, nasce um item no topo, em posição horizontal aleatória:

| Item | Chance | Tamanho (raio) | Efeito ao encostar |
|---|---|---|---|
| Estrela | 30% | 13 px | +10 pontos |
| Asteroide | 70% | 16 a 28 px (sorteado) | −1 vida |

Cada asteroide sorteia o próprio visual: contorno irregular (9 a 13 vértices), tom de cinza amarronzado,
2 a 4 crateras e uma rotação própria (até 2,5 rad/s). A colisão usa um círculo com o raio do asteroide.

### 5.3 Kamehameha

- Dispara **no instante em que a mão esquerda fecha** (transição de aberta para fechada). Segurar a mão
  fechada não repete o disparo: é preciso abrir e fechar de novo.
- Só dispara se não estiver em recarga: **recarga de 4 s** (`ESPERA_KAME`). O status aparece no canto
  ("pronto" / "recarregando Xs").
- O raio dura **1,2 s** (`TEMPO_RAIO`), tem **34 px** de largura e sobe do personagem até o topo da tela.
- **O que o raio atinge:** todo item que está **acima do personagem** e cuja distância horizontal até ele é
  menor que `raio do item + 17 px` (metade da largura do raio).
  - Asteroides são destruídos e valem **+3 pontos** cada.
  - Os poderes do boss também são destruídos (sem pontos).
  - Estrelas não são afetadas.

### 5.4 Níveis

O nível depende **só do tempo de partida sobrevivido**:

```
nível = 1 + ⌊tempo ÷ 15 s⌋
```

O relógio só corre durante a partida, e **fica parado durante a luta contra o boss**. A cada nível:

```
intervalo entre itens = max(0,30 s ; 0,95 − 0,08 × nível)
velocidade de queda   = sorteio entre (110 + 25 × nível) e (160 + 25 × nível) px/s
```

| Nível | Tempo | Novo item a cada | Velocidade de queda |
|---|---|---|---|
| 1 | 0 a 15 s | 0,87 s | 135 a 185 px/s |
| 2 | 15 a 30 s | 0,79 s | 160 a 210 px/s |
| 3 | 30 a 45 s | 0,71 s | 185 a 235 px/s |
| 5 | 60 s (+ boss) | 0,55 s | 235 a 285 px/s |
| 9 | ~2 min | 0,30 s (mínimo) | 335 a 385 px/s |

A frequência para de subir no nível 9. A velocidade continua subindo sempre.
A proporção de estrelas (30%), a velocidade do personagem e a recarga do Kamehameha não mudam com o nível.

### 5.5 Boss Haroldo

**Quando aparece:** ao chegar nos níveis **5, 10, 15...** (`BOSS_A_CADA = 5`). As pedras na tela somem e
aparece "BOSS: HAROLDO CHEGOU!".

**Durante a luta:**
- O **nível fica travado** e o relógio para. **Não caem pedras**, só estrelas.
- O boss anda de um lado para o outro no topo (centro do rosto em y = 78) e quica nas bordas.
- Ele lança **esferas roxas** (raio 8 px) das mãos, **mirando na posição atual do personagem**.
  Cada esfera que encosta tira **1 vida**.
- Encostar no boss também tira vida, mas o personagem não consegue subir acima do corpo dele
  (fica abaixo de y = 207).

**Como derrotar:** com o Kamehameha. O raio acerta o boss quando a distância horizontal entre os dois é
menor que `32 + 17 = 49 px`. **Cada disparo tira 5 de vida** (`DANO_KAME`) e conta **uma vez só**, mesmo que o
raio continue passando por ele durante os 1,2 s.

**Cada boss é mais forte** (n = 1º, 2º, 3º... boss):

```
vida             = 20 + 10 × (n − 1)
intervalo de tiro = max(0,6 s ; 1,6 − 0,25 × n)
velocidade do tiro = 170 + 30 × n  px/s
velocidade lateral = 80 + 30 × n  px/s
tiros por vez    = 1 (1º boss)  ou  3 em leque de ±0,3 rad (a partir do 2º)
```

| Boss | Nível | Vida | Kamehamehas | Tiro a cada | Tiros por vez |
|---|---|---|---|---|---|
| 1º | 5 | 20 | 4 | 1,35 s | 1 |
| 2º | 10 | 30 | 6 | 1,10 s | 3 |
| 3º | 15 | 40 | 8 | 0,85 s | 3 |
| 4º+ | 20+ | 50+ | 10+ | 0,60 s | 3 |

**Ao derrotar:** +**50 × n** pontos, musiquinha de vitória e a mensagem
"HAROLDO DERROTADO! / PARABENS! / VOCE GANHOU 10 NO TRABALHO!" por 4 s. O relógio volta a andar e o resto
do nível segue normalmente.

**Visual:** `boss.png` é recortado em círculo, recebe um leve tom verde e vira a cabeça de um corpo no estilo
Piccolo: orelhas pontudas, antenas, gi azul com emblema "H", faixa roxa, braços rosa e verdes com munhequeiras
vermelhas, energia roxa nas mãos e aura roxa. Ao levar dano, o rosto pisca em vermelho. Para trocar a foto,
substitua `boss.png` por uma imagem quadrada com o rosto centralizado. Sem o arquivo, aparece uma cabeça
verde com "?".

### 5.6 Pontuação

| Evento | Pontos |
|---|---|
| Cada segundo sobrevivido | +2 |
| Estrela coletada | +10 |
| Asteroide que passa sem te acertar | +1 |
| Asteroide destruído pelo Kamehameha | +3 |
| Boss derrotado | +50 × número do boss |

O **recorde** é salvo em `recorde.txt` quando a partida termina com pontuação maior que a anterior
(aparece "NOVO RECORDE!"). Apague o arquivo para zerar.

### 5.7 Telas

- **Tela inicial:** título, recorde, instruções dos gestos e barra do gesto de começar.
- **Partida:** placar (pontos, nível, recorde), vidas, status do Kamehameha e avisos do boss.
- **Game over:** pontuação, recorde, "NOVO RECORDE!" (se for o caso) e barra do gesto de reiniciar.

### 5.8 Sons

Bipes do Windows (`winsound`), tocados em segundo plano para não travar o jogo: estrela, dano, Kamehameha,
início, game over, novo recorde, chegada do boss, acerto no boss e boss derrotado. Em outros sistemas, o jogo
fica mudo.

---

## 6. Métricas (ao fechar o jogo)

Ao sair, o terminal mostra um relatório e abre três gráficos (FPS, latência e deslocamento por quadro):

| Métrica | Como é calculada |
|---|---|
| **FPS** | média móvel exponencial: `fps = 0,9 × fps + 0,1 × (1 ÷ tempo do quadro)`; relatório mostra média, mínimo e máximo |
| **Latência de processamento** | do quadro lido até a imagem pronta (mãos + Pose + jogo + desenho); média e percentil 95 |
| **Latência ponta a ponta** | do pedido do quadro à webcam até a imagem aparecer na janela; média e percentil 95 |
| **Taxa de detecção** | % de quadros com pelo menos 1 pulso detectado (Pose) e % com os 2 |
| **Estabilidade (jitter)** | mediana do deslocamento do personagem por quadro, em pixels; desvio padrão do FPS |
| **Resultado** | pontuação final, recorde, estrelas, pedras esquivadas e pedras destruídas pelo Kamehameha |

---

## 7. Configurações

**`main.py`** (câmera e modelos):

| Constante | Valor | O que faz |
|---|---|---|
| `MODELO` | `"lite"` | modelo do Pose: `lite` (rápido), `full` ou `heavy` (preciso) |
| `LARGURA, ALTURA` | 480, 360 | resolução do jogo |
| `VIS_MIN` | 0,5 | visibilidade mínima de um ponto do corpo |
| `CAMERA` | 0 | índice da webcam (troque para 1, 2... se tiver mais de uma) |
| `ESCALA_JANELA` | 1,5 | ampliação da janela |

**`jogo.py`** (jogabilidade):

| Constante | Valor | O que faz |
|---|---|---|
| `VIDAS` | 3 | vidas por partida |
| `VEL_MAX` | 420 px/s | velocidade lateral máxima |
| `ZONA_MORTA` | 0,35 | distância da linha azul ao ombro (em larguras de ombro) |
| `ALCANCE` | 0,6 | esticada extra até a velocidade máxima |
| `VEL_SUBIR` / `VEL_DESCER` | 220 / 140 px/s | subida ao acelerar / volta à base |
| `TEMPO_SAIR` | 1 s | tempo segurando o gesto de sair |
| `TEMPO_RAIO` | 1,2 s | duração do Kamehameha |
| `ESPERA_KAME` | 4 s | recarga do Kamehameha |
| `LARGURA_RAIO` | 34 px | largura do raio |
| `BOSS_A_CADA` | 5 | boss a cada quantos níveis (use 1 para testar rápido) |
| `BOSS_R` / `BOSS_Y` | 32 / 78 px | tamanho e altura do rosto do boss |
| `DANO_KAME` | 5 | vida que cada Kamehameha tira do boss |

Vida, velocidade e tiros de cada boss ficam em `Jogo._criar_boss()` e `Jogo._atualizar_boss()`.
Cores ficam no topo de `goku.py` e `boss.py`, no formato do OpenCV: **(azul, verde, vermelho)**.
Textos na tela devem ser escritos **sem acento** (a fonte do OpenCV não desenha acentos).

---

## 8. Arquivos e como cada um funciona

### Como os arquivos se conectam

```
main.py  ──(webcam + MediaPipe → gestos)──►  jogo.py (classe Jogo: regras do jogo)
                                                 │
                         ┌───────────────────────┼───────────────────────┐
                         ▼                       ▼                       ▼
                     goku.py                 boss.py                 sons.py
               (desenha o personagem)   (desenha o boss)        (toca os efeitos)
```

`main.py` é o único arquivo que mexe com a câmera e o MediaPipe. Ele transforma o que a câmera vê em
comandos simples (direção, acelerar, Kamehameha, começar, sair) e entrega para o `Jogo`. O `jogo.py` não sabe
nada de câmera: só recebe esses comandos, aplica as regras e desenha usando `goku.py` e `boss.py`.
Por isso a lógica pode ser testada sem webcam (`test_jogo.py`).

### `main.py`: câmera, MediaPipe e laço principal

| Parte | O que faz |
|---|---|
| Constantes do topo | configurações (modelo, resolução, câmera, janela) e endereços dos modelos |
| `NARIZ, OMBRO_E, ...` e `OSSOS` | índices dos pontos do corpo usados e as ligações do esqueleto desenhado |
| `baixar_modelo()` | baixa um modelo `.task` se ainda não existir; grava primeiro num `.part` e renomeia no fim, para não deixar arquivo corrompido se a internet cair |
| `criar_detector_maos()` | cria o Hand Landmarker (até 2 mãos, modo vídeo) |
| `criar_landmarker()` | cria o Pose Landmarker (1 pessoa, modo vídeo) |
| `jogar()` | **laço principal**, executado a cada quadro: (1) lê e espelha a imagem; (2) detecta as mãos na resolução cheia; (3) reduz para 480×360 e detecta o corpo; (4) filtra os pontos pela visibilidade; (5) calcula os gestos com as funções de `jogo.py` (`calcular_direcao`, `separar_maos`, `mao_fechada`, `gesto_sair`) e o gesto de começar; (6) calcula `dt` e o FPS; (7) chama `jogo.atualizar()`; (8) desenha o fundo, o esqueleto, as linhas azuis e os pulsos, depois `jogo.desenhar()` e `jogo.hud()`; (9) mostra a janela e guarda as métricas; (10) sai com Q/ESC, janela fechada ou gesto de sair |
| `relatorio()` | ao fechar, calcula e imprime as métricas (seção 6) e mostra os gráficos com matplotlib |
| `main()` | baixa os modelos, cria o `Jogo` e os detectores, roda `jogar()` e no fim `relatorio()` |

### `jogo.py`: regras do jogo

**Funções soltas (cálculos e gestos):**

| Função | O que faz |
|---|---|
| `nova_forma_pedra()` | sorteia o visual de um asteroide (contorno, cor, crateras, giro) |
| `desenhar_pedra()` | desenha o asteroide: sombra, corpo deslocado (luz de cima), crateras que giram junto e contorno |
| `dedos_esticados()` | diz quais dos 4 dedos estão esticados (seção 4.3) |
| `mao_fechada()` | punho = 3 ou mais dedos dobrados |
| `gesto_sair()` | mãos juntas no peito pelo Pose ou pelo detector de mãos (seção 4.5) |
| `separar_maos()` | decide qual mão é a direita e qual é a esquerda pela posição (seção 4.2) |
| `calcular_direcao()` | transforma a posição dos braços em direção de -1 a +1 (seção 4.1) |
| `ler_recorde()` / `salvar_recorde()` | lê e grava `recorde.txt`; se o arquivo faltar ou estiver estragado, o recorde é 0 |

**Classe `Jogo` (o estado e as regras):**

| Método | O que faz |
|---|---|
| `__init__()` | guarda o tamanho da tela, carrega o recorde e começa na tela inicial |
| `reiniciar()` | zera tudo para uma nova partida: posição, vidas, pontos, itens, tempo, Kamehameha, boss |
| `nivel` | calcula o nível a partir do tempo (seção 5.4) |
| `contar_sair()` | soma o tempo do gesto de sair; devolve `True` quando completa 1 s |
| `atualizar()` | **coração do jogo**, chamado a cada quadro. Na tela inicial ou no game over, só conta o gesto de começar/reiniciar. Na partida: move o personagem para os lados, dispara o Kamehameha se a mão esquerda acabou de fechar, sobe ou desce conforme a mão direita, soma pontos, chama o boss quando chega a hora (e para o relógio), cria itens novos, move todos os itens, testa raio e colisões, remove o que saiu da tela e verifica o game over (salvando o recorde) |
| `_criar_boss()` | cria o boss com vida e velocidade conforme o número dele, limpa as pedras e mostra o aviso |
| `_atualizar_boss()` | move o boss, faz ele atirar mirando no personagem, aplica o dano do Kamehameha (1 vez por disparo), trata a derrota (pontos e mensagem de vitória) e o dano por encostar |
| `_levar_dano()` | tira 1 vida e dá 1 s de invulnerabilidade (se não estiver invulnerável) |
| `_avisar()` | agenda uma mensagem grande no meio da tela por alguns segundos |
| `desenhar()` | desenha os itens, o boss, o raio e o personagem (piscando se invulnerável) |
| `hud()` | desenha os textos: rodapé, barra de sair, tela inicial, placar, status do Kamehameha, avisos e game over |
| `_texto()` / `_barra()` | ajudantes: texto centralizado e barra de progresso dos gestos |

### `goku.py`: desenho do personagem

| Função | O que faz |
|---|---|
| `_translucido()` | desenha numa cópia da imagem e mistura com a original (é assim que se faz transparência no OpenCV) |
| `_esfera_ki()` | esfera de energia azul com brilho |
| `desenhar_raio()` | o raio do Kamehameha: faixa azul translúcida, núcleo branco e esfera na origem, tremulando |
| `desenhar_goku()` | o personagem (~50 px): pernas, botas, gi laranja com camiseta azul, faixa, cabeça, cabelo espetado e braços. Ao acelerar, desenha antes a aura amarela irregular e as linhas de velocidade. Ao disparar, os braços vão para frente |

### `boss.py`: desenho do boss

| Função | O que faz |
|---|---|
| `_rosto()` | carrega `boss.png` uma vez, redimensiona, aplica o tom verde e cria a máscara circular (fica guardado em cache) |
| `desenhar_boss()` | o boss inteiro: aura roxa, braços rosa e verdes com munhequeiras, gi azul com emblema "H", faixa roxa, energia nas mãos, orelhas, antenas, a foto recortada em círculo (vermelha se levou dano) e a barra de vida com "HAROLDO vida/máximo" |
| `desenhar_poder()` | esfera roxa que o boss lança |

### `sons.py`: efeitos sonoros

`SONS` é um dicionário com cada som como uma sequência de notas (frequência em Hz, duração em ms).
`tocar(nome)` toca o som numa *thread* separada, porque `winsound.Beep` trava enquanto toca e o jogo
congelaria. Se `winsound` não existir (outro sistema), `ATIVO` é falso e nada toca.

### `test_jogo.py`: testes automáticos

Testa a lógica sem câmera, usando mãos e pontos falsos: direção dos braços, mão fechada, separação
direita/esquerda, gesto de sair, movimento e bordas, acelerar, estrelas e pedras, game over e recorde
(num arquivo temporário, sem mexer no recorde real), Kamehameha (disparo ao fechar, não repetir, recarga),
boss (aparece no nível 5, trava o nível, atira, perde 5 por disparo, morre e libera o nível) e o poder do
boss tirando vida. Os sons ficam desligados durante os testes. Rode com
`.\.venv\Scripts\python test_jogo.py`; se tudo passar, aparece `OK`.

### Outros arquivos

| Arquivo | O que é |
|---|---|
| `boss.png` | foto do rosto do boss (quadrada) |
| `requirements.txt` | dependências: mediapipe, opencv-python, numpy, matplotlib |
| `recorde.txt` | recorde salvo (criado pelo jogo) |
| `pose_landmarker_lite.task`, `hand_landmarker.task` | modelos do MediaPipe (baixados pelo jogo) |
| `jogo_controle_maos.ipynb` | notebook original do Colab, que deu origem ao projeto |

---

## 9. Problemas comuns

| Problema | Solução |
|---|---|
| "Não foi possível abrir a webcam" | feche outros programas que usam a câmera; ou troque `CAMERA` para 1 |
| Personagem não anda | os dois ombros precisam aparecer na câmera; passe a mão da linha azul |
| Precisa esticar demais o braço | diminua `ZONA_MORTA` e/ou `ALCANCE` |
| Personagem anda sozinho | aumente `ZONA_MORTA` |
| Mão fechada não é reconhecida | aproxime-se da câmera e vire a palma para ela; confira `D:`/`E:` no rodapé |
| Gesto de sair não funciona | o nariz precisa aparecer; aumente o `0.6` ou o `1.5` em `gesto_sair()` |
| Jogo lento (FPS baixo) | são 2 modelos por quadro; mantenha `MODELO = "lite"` e feche outros programas |
| Quer testar o boss sem esperar 1 minuto | `BOSS_A_CADA = 1` (volte para 5 depois) |
