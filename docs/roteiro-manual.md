# Roteiro de verificação manual da extensão

A extensão do GNOME Shell não tem teste automático. Este roteiro de 15 passos é a
verificação dela. Pré-requisito: `~/tempo/instalar.sh` já rodado e sessão reiniciada
(logout/login). Marque o resultado de cada passo na seção **Registro**, no fim.

## Passos

1. **Relogar.** Saia da sessão e entre de novo.
   - Esperado: o indicador aparece à direita da barra de cima, com ícone de relógio.

2. **Atalho.** Pressione Super+T.
   - Esperado: o menu do indicador abre.

3. **Sem cliente cadastrado.** Com o banco sem clientes, abra o menu: o seletor Cliente mostra "Sem cliente". Clique em Iniciar e depois em Parar.
   - Esperado: o timer começa mesmo sem cliente, a barra mostra `▶ 00:0x · Edição` (a atividade no lugar do cliente), e ao parar a entrada aparece na aba Hoje como "Sem cliente · Edição".

3a. **Cartão flutuante.** Com a tarefa do passo 3 rodando, olhe o canto inferior direito da tela.
   - Antes: no menu da barra, ligue o interruptor "Cartão flutuante" (vem desligado).
   - Esperado: um cartão escuro com borda amarela mostra `00:00:0x` em amarelo subindo a cada segundo e "Sem cliente · Edição" embaixo, por cima de qualquer janela. Arraste ele pelo fundo pra outro canto: ele fica onde você soltou (e lembra no próximo Iniciar). Clique no X: ele some e o interruptor do menu fica desligado. Bloqueie a tela (Super+L) e volte: continua escondido. Ligue o interruptor: ele volta. Abra um vídeo em tela cheia no VLC: o cartão some enquanto o vídeo estiver em tela cheia. Clique em Parar no cartão: o timer para e o cartão some.

3b. **Iniciar pela janela.** Abra o relatório (Abrir relatório ou comando `tempo`), aba Hoje. O cursor já deve estar na caixa "No que você está trabalhando?". Digite "teste pela janela" e aperte Enter.
   - Esperado: o cartão vira um cronômetro `00:00:0x` subindo a cada segundo, com "Sem cliente · Edição · teste pela janela" embaixo e o botão Parar. A barra de cima mostra o mesmo timer. Clique em Parar: a entrada desce pra lista do dia e o cursor volta pra caixa do nome. Com a caixa vazia o botão Iniciar fica desabilitado.

4. **Cadastrar cliente.** No menu, clique em Abrir relatório, vá à aba Cadastros, crie o cliente "Casttema" e feche a janela.
   - Esperado: o cliente é salvo e a janela fecha sem erro.

5. **Iniciar.** No menu, escolha Casttema em Cliente, Edição em Atividade, escreva a descrição "teste" e clique em Iniciar. Tire a captura de tela deste momento e salve como `docs/tela.png`.
   - Esperado: o rótulo da barra mostra `▶ 00:0x · Casttema`, subindo a cada segundo, com o pontinho na cor do cliente. O botão do menu vira Parar e aparece o item "Trocar para …".

6. **Recentes.** Abra o menu.
   - Esperado: a lista Recentes mostra "Casttema · Edição".

7. **Trocar.** Mude Cliente/Atividade no menu e clique em "Trocar para …" (ou inicie outra combinação pelo Recentes). Depois abra a aba Hoje.
   - Esperado: a entrada anterior encerra no mesmo segundo em que a nova começa (o fim da 1ª é igual ao início da 2ª, sem buraco nem sobreposição).

8. **Abrir relatório com a janela já aberta.** Deixe a janela do relatório aberta, coloque outra janela por cima dela (o Terminal, por exemplo) e clique em Abrir relatório no menu.
   - Esperado: a janela do Tempo vem para a frente, sem abrir uma segunda janela.

9. **Horário inválido no diálogo.** Na aba Hoje, clique numa entrada, digite `25:99` no campo Fim e clique em Salvar.
   - Esperado: aparece o aviso "Não salvou: horário inválido, use HH:MM", o diálogo reabre com o que foi digitado e já recebe o foco (dá para corrigir o campo sem clicar na janela antes). Cancele ao terminar.

10. **Reinício do serviço com timer rodando.** Com o timer ainda rodando (do passo 7), ache o PID do serviço no Terminal com `pgrep -f '^(/usr/bin/)?python3 -m tempo\.app'` e rode `kill <PID>` com o número que apareceu. Depois clique em Abrir relatório no menu.
    - Esperado: o serviço volta sozinho pelo D-Bus e a janela abre normalmente. **Não** pode aparecer o diálogo "Entrada ficou aberta": o timer continua rodando, porque o início da sessão é o do login, não o da subida do serviço.

11. **Parar.** Clique em Parar.
    - Esperado: o rótulo some e o ícone de relógio volta.

12. **Serviço fora.** Primeiro, rode `kill <PID>` do serviço (PID achado como no passo 10) e abra o menu.
    - Esperado: abrir o menu reativa o serviço pelo D-Bus, e o indicador **não** fica cinza.

    Para ver o estado cinza, o D-Bus não pode conseguir religar o serviço: renomeie o lançador com `mv ~/.local/bin/tempo ~/.local/bin/tempo.off`, rode `kill <PID>` de novo (o PID muda a cada reativação) e abra o menu.
    - Esperado: o indicador fica cinza em até 5 segundos e o menu mostra "Reconectar ao serviço".

    Restaure o nome com `mv ~/.local/bin/tempo.off ~/.local/bin/tempo` e clique em Reconectar.
    - Esperado: o D-Bus ativa o serviço de novo e o indicador volta ao normal.

13. **Aviso de mais de 12 horas.** Faça este passo depois das 13h (a aba Hoje só edita entradas do dia atual, então o início não pode ir para ontem). Inicie uma entrada, abra a aba Hoje e edite o início dela para 00:00 (não é preciso mudar o relógio do sistema).
    - Esperado: o rótulo da barra mostra o aviso ⚠ (entrada com mais de 12 horas). Pare ou apague a entrada ao terminar.

14. **Entrada esquecida no login.** Inicie um timer, deixe rodando, saia da sessão e entre de novo.
    - Esperado: logo depois do login, a janela do Tempo abre sozinha com a pergunta "Entrada ficou aberta" e as opções Encerrar no início, Encerrar agora e Descartar. Escolha uma e confira na aba Hoje que só aquela entrada mudou.

15. **Validação do atalho nas preferências.** Abra as preferências da extensão (Extensões, Tempo, Configurações). No campo "Abrir menu", digite `<Super>y` e clique em aplicar. Depois digite `t` (sem modificador) e aplique.
    - Esperado: `<Super>y` é aceito e passa a abrir o menu no lugar do Super+T. `t` sem modificador deixa o campo com borda de erro e o atalho anterior continua valendo. Volte o padrão `<Super>t` ao terminar.

## Registro

Os passos 1 a 15 estão **PENDENTES**: aguardam o oguim sair e entrar na sessão para a extensão carregar. Nenhum deles foi executado ainda. Preencha a tabela conforme for executando.

| Data | Versão do GNOME | Passo | Resultado |
| --- | --- | --- | --- |
|  |  | 1 | pendente |
|  |  | 2 | pendente |
|  |  | 3 | pendente |
|  |  | 4 | pendente |
|  |  | 5 | pendente |
|  |  | 6 | pendente |
|  |  | 7 | pendente |
|  |  | 8 | pendente |
|  |  | 9 | pendente |
|  |  | 10 | pendente |
|  |  | 11 | pendente |
|  |  | 12 | pendente |
|  |  | 13 | pendente |
|  |  | 14 | pendente |
|  |  | 15 | pendente |

Depois do passo 5, adicione `docs/tela.png` ao repositório e comite.
