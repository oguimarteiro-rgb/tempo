# Roteiro de verificação manual da extensão

A extensão do GNOME Shell não tem teste automático. Este roteiro de 10 passos é a
verificação dela. Pré-requisito: `~/tempo/instalar.sh` já rodado e sessão reiniciada
(logout/login). Marque o resultado de cada passo na seção **Registro**, no fim.

## Passos

1. **Relogar.** Saia da sessão e entre de novo.
   - Esperado: o indicador aparece à direita da barra de cima, com ícone de relógio.

2. **Atalho.** Pressione Super+T.
   - Esperado: o menu do indicador abre.

3. **Sem cliente cadastrado.** Com o banco sem clientes, clique em Iniciar.
   - Esperado: aparece uma notificação pedindo para cadastrar um cliente, e nenhum timer começa.

4. **Cadastrar cliente.** No menu, clique em Abrir relatório, vá à aba Cadastros, crie o cliente "Casttema" e feche a janela.
   - Esperado: o cliente é salvo e a janela fecha sem erro.

5. **Iniciar.** No menu, escolha Casttema em Cliente, Edição em Atividade, escreva a descrição "teste" e clique em Iniciar. Tire a captura de tela deste momento e salve como `docs/tela.png`.
   - Esperado: o rótulo da barra mostra `▶ 00:0x · Casttema`, subindo a cada segundo, com o pontinho na cor do cliente. O botão do menu vira Parar e aparece o item "Trocar para …".

6. **Recentes.** Abra o menu.
   - Esperado: a lista Recentes mostra "Casttema · Edição".

7. **Trocar.** Mude Cliente/Atividade no menu e clique em "Trocar para …" (ou inicie outra combinação pelo Recentes). Depois abra a aba Hoje.
   - Esperado: a entrada anterior encerra no mesmo segundo em que a nova começa (o fim da 1ª é igual ao início da 2ª, sem buraco nem sobreposição).

8. **Parar.** Clique em Parar.
   - Esperado: o rótulo some e o ícone de relógio volta.

9. **Serviço fora.** Rode `pkill -f tempo.app` no Terminal e faça uma ação no indicador (por exemplo, abrir o menu).
   - Esperado: o indicador fica cinza em até 5 segundos e o menu mostra "Reconectar ao serviço". Ao clicar nele, o D-Bus ativa o serviço de novo e o indicador volta ao normal.

10. **Entrada esquecida.** Inicie uma entrada, abra a aba Hoje e edite o início dela para 13 horas atrás (não é preciso mudar o relógio do sistema).
    - Esperado: o rótulo da barra mostra o aviso ⚠ (entrada com mais de 12 horas). Pare ou apague a entrada ao terminar.

11. **Validação do atalho nas preferências.** Abra as preferências da extensão (Extensões, Tempo, Configurações). No campo "Abrir menu", digite `<Super>y` e clique em aplicar. Depois digite `t` (sem modificador) e aplique.
    - Esperado: `<Super>y` é aceito e passa a abrir o menu no lugar do Super+T. `t` sem modificador deixa o campo com borda de erro e o atalho anterior continua valendo. Volte o padrão `<Super>t` ao terminar.

## Registro

Os passos 1 a 10 (e a validação do atalho, passo 11) estão **PENDENTES**: aguardam o oguim sair e entrar na sessão para a extensão carregar. Nenhum deles foi executado ainda. Preencha a tabela conforme for executando.

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

Depois do passo 5, adicione `docs/tela.png` ao repositório e comite.
