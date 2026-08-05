# -*- coding: utf-8 -*-
"""Every user-visible string, in every language the program speaks.

One key, one dict of languages. Code never holds a sentence — it calls
``idioma.t("some.key")``. See ``idioma.py`` for why.

Adding a language
-----------------
Add its code to ``idioma.IDIOMAS`` and a matching entry to every key below.
``testes/t_idioma.py`` will tell you exactly which ones you missed, including
the ones whose ``{placeholders}`` do not match the English original.

Conventions
-----------
* ``{campo}`` placeholders are named, never positional — word order changes
  between languages and positional slots break when it does.
* Keys read like a path: ``card.<n>.<part>``, ``btn.<what>``, ``err.<what>``.
* English first in each entry, because English is the default.
"""

TEXTOS: dict[str, dict[str, str]] = {

    # ---------------------------------------------------------------- janela
    "win.title": {
        "en": "Last.fm scrobbler for the HiBy R1",
        "pt": "Scrobbler do Last.fm para o HiBy R1",
    },
    "win.language": {
        "en": "Language",
        "pt": "Idioma",
    },
    "win.open_log": {
        "en": "Open the log",
        "pt": "Abrir o registro",
    },
    "win.stop": {
        "en": "Stop",
        "pt": "Interromper",
    },
    "win.working": {
        "en": "Working…",
        "pt": "Trabalhando…",
    },
    "win.quit.title": {
        "en": "Quit now?",
        "pt": "Sair agora?",
    },
    "win.quit.body": {
        "en": "Something is still running. Quitting now may leave a step "
              "half-finished on the device.",
        "pt": "Ainda há trabalho em andamento. Sair agora pode deixar uma "
              "etapa pela metade no aparelho.",
    },
    "win.quit.ok": {
        "en": "Quit anyway",
        "pt": "Sair mesmo assim",
    },
    "win.stopping": {
        "en": "Stop requested — finishing the current step first.",
        "pt": "Interrupção pedida — encerrando na próxima etapa segura.",
    },
    "win.unexpected.title": {
        "en": "Something unexpected happened.",
        "pt": "Aconteceu um erro inesperado.",
    },
    "win.unexpected.detail": {
        "en": "{erro}\n\nTechnical details (also in the log file):\n{traco}",
        "pt": "{erro}\n\nDetalhes técnicos (também no arquivo de "
              "registro):\n{traco}",
    },
    "win.unexpected.log": {
        "en": "unexpected failure: {erro}",
        "pt": "falha inesperada: {erro}",
    },
    "win.error.title": {
        "en": "That did not work",
        "pt": "Não deu certo",
    },

    # ------------------------------------------------------------ cartão 0
    "card.intro.title": {
        "en": "How this works",
        "pt": "Como funciona",
    },
    "card.intro.body": {
        "en": "The R1 does not record when a track played — its database only "
              "says what played, and in what order. So a tiny program sits on "
              "the device writing down the time each track shows up in the "
              "history, and the gap between one and the next is how long you "
              "listened. That is what decides what counts: the track has to "
              "have played almost to the end — 90% of it, or 4 minutes, "
              "whichever comes first. Last.fm settles for half; this is "
              "stricter, so a track you walked away from does not go up as if "
              "you had listened to it.\n\n"
              "From there, what was recorded reaches Last.fm two ways, and you "
              "can use both at once:\n"
              "    • by itself, whenever the R1's Wi-Fi is already on (card 4);\n"
              "    • over the cable, from here (card 6).\n\n"
              "The device never switches the radio on by itself. If you never "
              "use Wi-Fi, the queue simply waits for the cable — nothing is "
              "lost.",
        "pt": "O R1 não guarda a hora em que cada faixa tocou — o banco dele só "
              "diz o que tocou e em que ordem. Então um programinha fica no "
              "aparelho anotando a hora em que cada faixa aparece no histórico, "
              "e o intervalo entre uma e outra dá o tempo que você ouviu de "
              "cada uma. É esse tempo que decide o que conta: a faixa tem de "
              "ter tocado quase até o fim — 90% dela, ou 4 minutos, o que "
              "vier antes. O Last.fm se contenta com metade; aqui a régua é "
              "mais alta, para que uma faixa que você largou no meio não suba "
              "como se tivesse sido ouvida.\n\n"
              "Depois disso o que foi anotado chega ao Last.fm de dois jeitos, "
              "e você pode usar os dois ao mesmo tempo:\n"
              "    • sozinho, quando o WiFi do R1 já estiver ligado (cartão 4);\n"
              "    • pelo cabo, a partir daqui (cartão 6).\n\n"
              "O aparelho nunca liga o rádio por conta própria. Se você nunca "
              "usar WiFi, a fila só espera o cabo — nada se perde.",
    },
    "card.intro.cost": {
        "en": "Measured on a real R1: 1 ms of CPU per cycle, one cycle per "
              "minute while idle — 0.0017% of the time, and it spawns no child "
              "processes at all. One Wi-Fi send costs about 0.1% of the "
              "battery. The collector never writes to the player's database: "
              "it opens read-only, and on a copy.",
        "pt": "Custo medido no R1: 1 ms de processador por volta, uma volta por "
              "minuto parado — 0,0017% do tempo, sem criar processo nenhum. Um "
              "envio pelo WiFi custa uns 0,1% de bateria. O coletor não escreve "
              "no banco do player em momento nenhum: abre só para leitura, e "
              "numa cópia.",
    },

    # ------------------------------------------------------------ cartão 1
    "card.api.title": {
        "en": "1. Your Last.fm API key",
        "pt": "1. Sua chave de API do Last.fm",
    },
    "card.api.body": {
        "en": "Last.fm requires every application to have its own key. "
              "Registering is free, takes a minute, and asks for nothing "
              "beyond a name for the application.\n\n"
              "The key stays on this computer only. It is not your password, "
              "and this program never sees your password at any point.",
        "pt": "O Last.fm exige que cada aplicativo tenha a sua própria chave. "
              "Registrar é grátis, leva um minuto e não pede nada além de um "
              "nome para o aplicativo.\n\n"
              "A chave fica só neste computador. Ela não é a sua senha, e o "
              "programa nunca vê a sua senha em momento nenhum.",
    },
    "card.api.open": {
        "en": "Open the registration page",
        "pt": "Abrir a página de registro",
    },
    "card.api.howto": {
        "en": "On that page, fill in the name (something like “my R1 "
              "scrobbler”) and the description. The rest can stay empty. Then "
              "copy the two values it shows you: API key and Shared secret.",
        "pt": "Na página, preencha o nome (algo como “meu scrobbler do R1”) e a "
              "descrição. O resto pode ficar em branco. Depois copie os dois "
              "valores que aparecem: API key e Shared secret.",
    },
    "card.api.key": {
        "en": "API key",
        "pt": "API key",
    },
    "card.api.secret": {
        "en": "Shared secret",
        "pt": "Shared secret",
    },
    "card.api.save": {
        "en": "Save",
        "pt": "Guardar",
    },
    "card.api.bad": {
        "en": "Both values are 32 hexadecimal characters. Check that nothing "
              "was lost while copying — and that you did not swap the API key "
              "with the Shared secret.",
        "pt": "Os dois valores têm 32 caracteres hexadecimais. Confira se não "
              "faltou nada ao copiar — e que você não trocou a API key pelo "
              "Shared secret.",
    },
    "card.api.saved": {
        "en": "Key saved. Now authorise your account in the card below.",
        "pt": "Chave guardada. Agora autorize a conta no cartão abaixo.",
    },
    "card.api.stored": {
        "en": "Key stored on this computer.",
        "pt": "Chave guardada neste computador.",
    },
    "card.api.missing": {
        "en": "No key yet. Without one the program has no way to identify "
              "itself to Last.fm.",
        "pt": "Ainda sem chave. Sem ela o programa não tem como se identificar "
              "ao Last.fm.",
    },

    # ------------------------------------------------------------ cartão 2
    "card.account.title": {
        "en": "2. Your Last.fm account",
        "pt": "2. Sua conta do Last.fm",
    },
    "card.account.authorise": {
        "en": "Authorise in the browser",
        "pt": "Autorizar no navegador",
    },
    "card.account.done": {
        "en": "I authorised it — finish",
        "pt": "Já autorizei — concluir",
    },
    "card.account.signout": {
        "en": "Sign out",
        "pt": "Desconectar",
    },
    "card.account.note": {
        "en": "The browser opens a page on Last.fm itself, where you approve "
              "the access. Your password never passes through here: this "
              "program only receives a session key, which you can revoke at "
              "last.fm → Settings → Applications.",
        "pt": "O navegador abre numa página do próprio Last.fm, onde você "
              "aprova o acesso. Sua senha não passa por aqui: o programa "
              "recebe só uma chave de sessão, que você pode revogar em "
              "last.fm → Configurações → Aplicativos.",
    },
    "card.account.need_api": {
        "en": "Fill in the API key in the card above first — that is what "
              "identifies the application to Last.fm.",
        "pt": "Preencha a chave de API no cartão acima primeiro — é ela que "
              "identifica o aplicativo ao Last.fm.",
    },
    "card.account.connected": {
        "en": "Signed in as {usuario}.",
        "pt": "Conectado como {usuario}.",
    },
    "card.account.unknown_user": {
        "en": "(unknown user)",
        "pt": "(usuário desconhecido)",
    },
    "card.account.none": {
        "en": "No account linked yet.",
        "pt": "Nenhuma conta ligada ainda.",
    },
    "card.account.browser_open": {
        "en": "I opened the Last.fm page in your browser. Approve the access "
              "there and come back here to click “I authorised it”.\n"
              "If it did not open: {url}",
        "pt": "Abri o navegador na página do Last.fm. Aprove o acesso por lá e "
              "volte aqui para clicar em “Já autorizei”.\n"
              "Se não abriu: {url}",
    },
    "card.account.signout.title": {
        "en": "Sign out",
        "pt": "Desconectar",
    },
    "card.account.signout.body": {
        "en": "The session key stored on this computer will be deleted. What "
              "was already sent to Last.fm stays there, and the device's queue "
              "is not touched.",
        "pt": "A chave de sessão guardada neste computador será apagada. O que "
              "já foi enviado ao Last.fm continua lá, e a fila do aparelho não "
              "é tocada.",
    },
    "busy.token": {
        "en": "Asking Last.fm for a token…",
        "pt": "Pedindo um token ao Last.fm…",
    },
    "busy.auth": {
        "en": "Finishing the authorisation…",
        "pt": "Concluindo a autorização…",
    },
    "log.connected": {
        "en": "Last.fm connected as {usuario}.",
        "pt": "Last.fm conectado como {usuario}.",
    },

    # ------------------------------------------------------------ cartão 3
    "card.collector.title": {
        "en": "3. The collector on the device",
        "pt": "3. O coletor no aparelho",
    },
    "card.collector.looking": {
        "en": "Looking for the device…",
        "pt": "Procurando o aparelho…",
    },
    "btn.check": {
        "en": "Check",
        "pt": "Verificar",
    },
    "btn.build": {
        "en": "Build",
        "pt": "Compilar",
    },
    "btn.install": {
        "en": "Install / update",
        "pt": "Instalar / atualizar",
    },
    "btn.remove": {
        "en": "Remove",
        "pt": "Remover",
    },
    "card.collector.every": {
        "en": "Look every",
        "pt": "Olhar a cada",
    },
    "card.collector.playing": {
        "en": "s while playing, and every",
        "pt": "s tocando, e a cada",
    },
    "card.collector.idle": {
        "en": "s while idle.",
        "pt": "s parado.",
    },
    "card.collector.tradeoff": {
        "en": "Longer intervals cost even less, but make the listened time "
              "less precise — and that is what decides what Last.fm accepts. "
              "The values above are a good middle ground.",
        "pt": "Intervalos maiores gastam menos ainda, mas pioram a precisão do "
              "tempo ouvido — e é ele que decide o que o Last.fm aceita. Os "
              "valores acima são um bom meio-termo.",
    },
    "dev.installed": {
        "en": "Collector installed.",
        "pt": "Coletor instalado.",
    },
    "dev.not_installed": {
        "en": "Collector NOT installed yet.",
        "pt": "Coletor ainda NÃO instalado.",
    },
    "dev.running": {
        "en": "Running now.",
        "pt": "Rodando agora.",
    },
    "dev.stopped": {
        "en": "Stopped.",
        "pt": "Parado.",
    },
    "dev.boots": {
        "en": "Starts together with the player.",
        "pt": "Inicia junto com o player.",
    },
    # O aviso que faltava. Sem ele a tela dizia "instalado / parado" e a
    # pessoa ficava tentando descobrir o que tinha feito de errado — quando
    # não era ela: o firmware de fábrica simplesmente não executa o init.sh.
    "dev.sem_boot": {
        "en": "⚠ this firmware will not start it at boot",
        "pt": "⚠ este firmware não o inicia no boot",
    },
    "dev.sem_boot.ajuda": {
        "en": "⚠  Installed, but this firmware will never start it on its own.\n"
              "Nothing in the stock R1 firmware runs /usr/data/init.sh — that "
              "file only gets executed if you have a patched firmware (the "
              "podcast mod ships one). This is not something you did wrong.\n\n"
              "Everything still works — you just have to start it yourself "
              "after each reboot. Click “Start now” above with the cable "
              "plugged in, or run:\n"
              "    adb shell \"setsid /usr/data/scrobble/r1scrobbled "
              "</dev/null >/dev/null 2>&1 &\"\n"
              "Once started it keeps collecting offline, with no cable, until "
              "you power the player off.\n\n"
              "To fix it for good, use “Fix auto-start…” below. It "
              "adds the missing line to your own firmware file, which you "
              "then install from the player’s update menu.",
        "pt": "⚠  Instalado, mas este firmware nunca vai iniciá-lo sozinho.\n"
              "Nada no firmware de fábrica do R1 executa o /usr/data/init.sh — "
              "esse arquivo só roda se você tiver um firmware remendado (o mod "
              "de podcast traz um). Não foi você que fez algo errado.\n\n"
              "Tudo funciona do mesmo jeito — só é preciso iniciá-lo à mão "
              "depois de cada reinício. Clique em “Iniciar agora” aí em cima "
              "com o cabo plugado, ou rode:\n"
              "    adb shell \"setsid /usr/data/scrobble/r1scrobbled "
              "</dev/null >/dev/null 2>&1 &\"\n"
              "Uma vez iniciado ele segue coletando offline, sem cabo, até "
              "você desligar o player.\n\n"
              "Para resolver de vez, use o “Resolver o auto-start…” "
              "aqui embaixo. Ele acrescenta a linha que falta no seu "
              "próprio arquivo de firmware, que você depois instala pelo "
              "menu de atualização do player.",
    },
    # O remendo de firmware, na tela. É a única coisa do programa que pode
    # inutilizar um player, então o texto não economiza: diz o que vai
    # acontecer, o que pode dar errado e qual é o caminho de volta, ANTES de
    # abrir qualquer seletor de arquivo.
    # O curl recém-compilado é experimentado no aparelho antes de substituir o
    # que estava lá. Esta é a mensagem de quando ele não passa.
    # Descartar faixas da fila. Pedido de quem escuta todo dia e envia pelo
    # cabo: sem isto, a única saída para uma faixa indesejada era apagar a
    # fila inteira.
    "btn.queue.discard": {
        "en": "Discard selected",
        "pt": "Descartar as marcadas",
    },
    "fila.nada_marcado.title": {
        "en": "Nothing is selected",
        "pt": "Nada está marcado",
    },
    "fila.nada_marcado.body": {
        "en": "Click the rows you want to discard first. Hold Ctrl to pick "
              "several, or Shift to pick a range.",
        "pt": "Clique antes nas linhas que quer descartar. Segure Ctrl para "
              "escolher várias, ou Shift para escolher um intervalo.",
    },
    "fila.descartar.title": {
        "en": "Discard {n} track(s) from the queue?",
        "pt": "Descartar {n} faixa(s) da fila?",
    },
    "fila.descartar.body": {
        "en": "These will never be sent to Last.fm:{faixas}\n\n"
              "They are marked as already dealt with on the device — the same "
              "thing that stops a sent track from going up twice. Nothing is "
              "removed from the player's own history, and no scrobble already "
              "on your profile is touched.\n\n"
              "This cannot be undone from here.",
        "pt": "Estas nunca serão enviadas ao Last.fm:{faixas}\n\n"
              "Elas ficam anotadas no aparelho como já resolvidas — o mesmo "
              "que impede uma faixa enviada de subir duas vezes. Nada é "
              "apagado do histórico do próprio player, e nenhum scrobble que "
              "já está no seu perfil é tocado.\n\n"
              "Isto não tem volta por aqui.",
    },
    "fila.descartar.ok": {
        "en": "Discard them",
        "pt": "Descartar",
    },
    "fila.descartando": {
        "en": "Discarding…",
        "pt": "Descartando…",
    },
    "fila.descartadas": {
        "en": "{n} track(s) discarded — they will not be sent.",
        "pt": "{n} faixa(s) descartada(s) — não serão enviadas.",
    },
    "ap.curl.ok": {
        "en": "curl runs on the device — installed.",
        "pt": "o curl roda no aparelho — instalado.",
    },
    "ap.err.curl.quebrado.title": {
        "en": "The curl that was built does not run on the R1",
        "pt": "O curl que foi compilado não roda no R1",
    },
    "ap.err.curl.quebrado.body": {
        "en": "It was copied to the device, run there, and it died. Nothing "
              "was replaced — whatever curl you had before is still in "
              "place.\n\nThe device answered:\n    {saida}\n\n"
              "A 139 means it crashed (signal 11). If you edited the build "
              "recipe, note that --disable-threaded-resolver produces exactly "
              "this: it looks like the right fix for the DNS error, and the "
              "resulting binary segfaults on every request. The DNS problem "
              "is already worked around elsewhere — the device resolves the "
              "name itself and hands curl the address.\n\n"
              "Build it again, or keep sending over the cable, which does not "
              "use curl at all.",
        "pt": "Ele foi copiado para o aparelho, executado lá, e morreu. Nada "
              "foi substituído — o curl que você tinha antes continua no "
              "lugar.\n\nO aparelho respondeu:\n    {saida}\n\n"
              "Um 139 quer dizer que ele quebrou (sinal 11). Se você mexeu na "
              "receita de compilação, saiba que o --disable-threaded-resolver "
              "produz exatamente isso: parece a correção certa para o erro de "
              "DNS, e o binário resultante segfaulta em toda requisição. O "
              "problema de DNS já é contornado noutro lugar — o aparelho "
              "resolve o nome sozinho e entrega o endereço ao curl.\n\n"
              "Compile de novo, ou continue enviando pelo cabo, que não usa "
              "curl nenhum.",
    },
    "btn.firmware": {
        "en": "Fix auto-start…",
        "pt": "Resolver o auto-start…",
    },
    "fw.title": {
        "en": "Make the collector start on its own at boot",
        "pt": "Fazer o coletor iniciar sozinho no boot",
    },
    "fw.body": {
        "en": "Your firmware has no way to run anything at boot, so the "
              "collector only runs when you start it. This adds the one "
              "missing line to a copy of your firmware, which you then "
              "install from the player's own update menu.\n\n"
              "WHAT YOU NEED\n"
              "The firmware file for your R1 — an r1.upt, the same file HiBy "
              "publishes for updates. This program does not download it: you "
              "supply it, and nothing is uploaded anywhere.\n\n"
              "WHAT IT CHANGES\n"
              "Exactly one file and one line. It adds, to hiby_player.sh, a "
              "line that runs /usr/data/init.sh before the player starts — "
              "the same hook modded firmwares already ship. Everything else "
              "is copied through untouched, and that is checked: the new "
              "package is unpacked again and all 4,718 files are compared "
              "against the original, contents, permissions and ownership. If "
              "anything but that one file moved, no package is written.\n\n"
              "IT ALSO TURNS ADB ON AT BOOT\n"
              "Stock firmware never starts ADB by itself, which is why this "
              "program cannot see a fresh R1 until you dig out the hidden "
              "developer switch. The patched firmware starts it, so the "
              "cable just works from then on.\n\n"
              "THE RISK, PLAINLY\n"
              "Installing firmware cannot be undone from software. If the "
              "wrong image goes on, the way back is to install a good one "
              "from the player's menu — which needs a player that still "
              "boots. A package from this has been installed on a real R1 "
              "and booted, but that does not make your flash risk-free.\n\n"
              "BEFORE YOU DO IT\n"
              "  • Download and keep the original r1.upt. That file is your "
              "way back, and you want it on your computer before you need "
              "it, not after.\n"
              "  • Charge the player. A firmware install interrupted by a "
              "flat battery is the bad case.\n"
              "  • Do not use the cable for anything else while it installs.\n\n"
              "If you would rather not: “Start now” does the same thing for "
              "one session, every time you plug in, and costs nothing.",
        "pt": "O seu firmware não tem como executar nada no boot, então o "
              "coletor só roda quando você o inicia. Isto acrescenta a linha "
              "que falta a uma cópia do seu firmware, que você depois instala "
              "pelo menu de atualização do próprio player.\n\n"
              "O QUE VOCÊ PRECISA\n"
              "O arquivo de firmware do seu R1 — um r1.upt, o mesmo que a "
              "HiBy publica para atualizações. Este programa não o baixa: "
              "você o fornece, e nada é enviado para lugar nenhum.\n\n"
              "O QUE MUDA\n"
              "Exatamente um arquivo e uma linha. Acrescenta ao "
              "hiby_player.sh uma linha que executa o /usr/data/init.sh antes "
              "de o player subir — o mesmo gancho que os firmwares "
              "modificados já trazem. Todo o resto é copiado sem alteração, e "
              "isso é conferido: o pacote novo é desempacotado de volta e os "
              "4.718 arquivos são comparados com o original, conteúdo, "
              "permissão e dono. Se qualquer coisa além daquele arquivo tiver "
              "mudado, nenhum pacote é gravado.\n\n"
              "ELE TAMBÉM LIGA O ADB NO BOOT\n"
              "O firmware de fábrica nunca inicia o ADB sozinho, e é por isso "
              "que este programa não enxerga um R1 recém-saído da caixa até "
              "você achar o interruptor escondido de desenvolvedor. O "
              "firmware remendado o inicia, e daí em diante o cabo "
              "simplesmente funciona.\n\n"
              "O RISCO, SEM RODEIOS\n"
              "Instalar firmware não tem volta por software. Se a imagem "
              "errada entrar, o caminho de volta é instalar uma boa pelo menu "
              "do player — o que exige um player que ainda ligue. Um pacote "
              "gerado por isto já foi instalado num R1 de verdade e deu boot, "
              "mas isso não torna a sua gravação isenta de risco.\n\n"
              "ANTES DE FAZER\n"
              "  • Baixe e guarde o r1.upt original. Esse arquivo é a sua "
              "volta, e é melhor tê-lo no computador antes de precisar dele.\n"
              "  • Carregue o player. Uma instalação de firmware interrompida "
              "por bateria vazia é o caso ruim.\n"
              "  • Não use o cabo para mais nada durante a instalação.\n\n"
              "Se preferir não mexer: o “Iniciar agora” faz o mesmo por uma "
              "sessão, toda vez que você plugar, e não custa nada.",
    },
    "fw.ok": {
        "en": "I have the original saved — continue",
        "pt": "Tenho o original guardado — continuar",
    },
    "fw.pick": {
        "en": "Choose the stock firmware file (r1.upt)",
        "pt": "Escolha o arquivo de firmware de fábrica (r1.upt)",
    },
    "fw.save": {
        "en": "Where to write the patched firmware",
        "pt": "Onde gravar o firmware remendado",
    },
    "fw.busy": {
        "en": "Patching the firmware — this takes a few minutes…",
        "pt": "Remendando o firmware — isto leva alguns minutos…",
    },
    "fw.done.title": {
        "en": "Patched firmware ready",
        "pt": "Firmware remendado pronto",
    },
    "fw.done": {
        "en": "Written to:\n{caminho}\n\nEvery check passed: exactly one file "
              "differs from your original, it is still owned by root and "
              "executable, and it is valid shell.\n\n"
              "TO INSTALL IT\n"
              "  1. Copy the file to the root of the R1's memory card (not "
              "into a folder).\n"
              "  2. On the player: System → Firmware update (or Local "
              "update), and pick it.\n"
              "  3. Let it finish without touching anything. It reboots on "
              "its own.\n\n"
              "After that the collector starts with the player every time, "
              "and ADB comes up at boot — so this program sees the R1 as "
              "soon as you plug the cable in, with no hidden menus. Set "
              "System → USB working mode → Device and you are done.\n\n"
              "Keep your original r1.upt.",
        "pt": "Gravado em:\n{caminho}\n\nTodas as conferências passaram: "
              "exatamente um arquivo difere do seu original, ele continua "
              "pertencendo ao root e executável, e é shell válido.\n\n"
              "PARA INSTALAR\n"
              "  1. Copie o arquivo para a raiz do cartão de memória do R1 "
              "(não dentro de uma pasta).\n"
              "  2. No player: System → Firmware update (ou Local update), e "
              "escolha-o.\n"
              "  3. Deixe terminar sem mexer em nada. Ele reinicia sozinho.\n\n"
              "Depois disso o coletor sobe junto com o player toda vez, e o "
              "ADB sobe no boot — então este programa enxerga o R1 assim que "
              "você plugar o cabo, sem menu escondido nenhum. Ponha System → "
              "USB working mode → Device e acabou.\n\n"
              "Guarde o seu r1.upt original.",
    },
    "fw.err.title": {
        "en": "The firmware was not patched",
        "pt": "O firmware não foi remendado",
    },
    "fw.err.tools": {
        "en": "This needs Linux tools that are not here: squashfs-tools, "
              "genisoimage and p7zip-full.\n\nOn Windows they live in WSL, "
              "which this program already uses to compile. Install them with:"
              "\n\n    sudo apt install squashfs-tools genisoimage p7zip-full"
              "\n\nThen try again. Nothing was changed.",
        "pt": "Isto precisa de ferramentas de Linux que não estão aqui: "
              "squashfs-tools, genisoimage e p7zip-full.\n\nNo Windows elas "
              "ficam no WSL, que este programa já usa para compilar. Instale "
              "com:\n\n    sudo apt install squashfs-tools genisoimage "
              "p7zip-full\n\nDepois tente de novo. Nada foi alterado.",
    },
    "fw.err.run": {
        "en": "The patcher refused to write a package. Nothing was changed, "
              "and your original file was only read.",
        "pt": "O remendador se recusou a gravar um pacote. Nada foi alterado, "
              "e o seu arquivo original foi apenas lido.",
    },
    "btn.iniciar": {
        "en": "Start now",
        "pt": "Iniciar agora",
    },
    "busy.iniciar": {
        "en": "Starting the collector…",
        "pt": "Iniciando o coletor…",
    },
    "dev.no_boot": {
        "en": "Does NOT start on its own at boot.",
        "pt": "NÃO inicia sozinho no boot.",
    },
    # O motivo vem do daemon, com as palavras dele. Esta mensagem afirmava
    # "este busybox não tem read -t" — e um dos dois motivos que o daemon
    # registra é justamente "'read -t' existe mas não esperou". A tela
    # descartava a resposta e punha um palpite no lugar.
    "dev.no_read_t": {
        "en": "The collector is using sleep instead of waiting on a pipe "
              "(costs a little more CPU).",
        "pt": "O coletor está usando sleep em vez de esperar num fifo (gasta "
              "um pouquinho mais de processador).",
    },
    "dev.no_read_t.why": {
        "en": "The collector is using sleep instead of waiting on a pipe "
              "(costs a little more CPU). The device said: {motivo}",
        "pt": "O coletor está usando sleep em vez de esperar num fifo (gasta "
              "um pouquinho mais de processador). O aparelho disse: {motivo}",
    },
    "dev.counts": {
        "en": "{execucoes} play(s) recorded, {pendentes} still to send.",
        "pt": "{execucoes} execução(ões) anotadas, {pendentes} ainda por enviar.",
    },
    # O número que sobra quando algumas faixas nunca vão subir. Sem esta
    # frase o cartão mostrava "43 ainda por enviar" para sempre, e o envio
    # respondia "não havia nada pendente" — duas verdades que se contradiziam.
    "dev.discarded": {
        "en": " ({descartadas} were skipped or too short to count.)",
        "pt": " ({descartadas} foram puladas ou curtas demais para contar.)",
    },
    "dev.plug_in": {
        "en": "{mensagem}\n\nTwo things are needed, and the first one is "
              "hidden:\n"
              "  1. turn ADB on — System → About, tap it ten times, then "
              "enable the developer/ADB switch that appears;\n"
              "  2. System → USB working mode → Device.",
        "pt": "{mensagem}\n\nDuas coisas são necessárias, e a primeira é "
              "escondida:\n"
              "  1. ligue o ADB — System → About, toque dez vezes, e ligue o "
              "interruptor de desenvolvedor/ADB que aparece;\n"
              "  2. System → USB working mode → Device.",
    },
    # Onde a planilha e o registro vão parar. Sem isto a pessoa procura o
    # arquivo no lugar errado e conclui que o recurso não existe.
    "dev.card": {
        "en": "  Log and spreadsheet on the card: {caminho}",
        "pt": "  Registro e planilha no cartão: {caminho}",
    },
    # Quando há cartão e a planilha ainda não existe. Ela só aparece depois
    # que o coletor anota a primeira faixa, e antes disto a tela dizia
    # "nenhum cartão gravável encontrado" para quem tinha o cartão ali.
    "dev.card.soon": {
        "en": "  Spreadsheet will be written to {caminho} after the first "
              "track is recorded.",
        "pt": "  A planilha será gravada em {caminho} depois que a primeira "
              "faixa for anotada.",
    },
    "dev.card.none": {
        "en": "  No writable memory card found, so no spreadsheet is written "
              "— the queue still works normally.",
        "pt": "  Nenhum cartão de memória gravável encontrado, então não há "
              "planilha — a fila continua funcionando normalmente.",
    },
    "busy.device": {
        "en": "Asking the device…",
        "pt": "Consultando o aparelho…",
    },
    "ver.outdated": {
        "en": "The device is on version {tem} and this program ships {nova}. "
              "Click “Install / update” to switch — the queue, what was "
              "already sent and your key all stay as they are.",
        "pt": "O aparelho está na versão {tem} e este programa traz a {nova}. "
              "Clique em “Instalar / atualizar” para trocar — a fila, o que já "
              "foi enviado e a sua chave ficam como estão.",
    },
    "ver.changes": {
        "en": "\n\nWhat changes: {lista}.",
        "pt": "\n\nO que muda: {lista}.",
    },
    "ver.current": {
        "en": "Version {tem} on the device — that is the newest one.",
        "pt": "Versão {tem} no aparelho — é a mais nova.",
    },
    "busy.build": {
        "en": "Building the device programs…",
        "pt": "Compilando os programas do aparelho…",
    },
    "build.done": {
        "en": "Built for MIPS32 little-endian, statically linked.\n{lista}\n\n"
              "Now click “Install / update”.",
        "pt": "Compilados para MIPS32 little-endian, estáticos.\n{lista}\n\n"
              "Agora clique em “Instalar / atualizar”.",
    },
    "busy.install": {
        "en": "Installing the collector…",
        "pt": "Instalando o coletor…",
    },
    "install.done": {
        "en": "Collector installed and running; it comes up with the player at "
              "every boot. From now on just listen to music — when you want to "
              "send it to Last.fm, plug the cable in and come back here.",
        "pt": "Coletor instalado e rodando; ele sobe junto com o player a cada "
              "boot. A partir de agora é só ouvir música — quando quiser mandar "
              "para o Last.fm, ligue o cabo e volte aqui.",
    },
    "err.intervals.title": {
        "en": "Invalid intervals",
        "pt": "Intervalos inválidos",
    },
    "err.intervals.body": {
        "en": "Both time fields have to be numbers, in seconds.",
        "pt": "Os dois campos de tempo têm de ser números em segundos.",
    },
    "remove.title": {
        "en": "Remove the collector",
        "pt": "Remover o coletor",
    },
    "remove.body": {
        "en": "The collector leaves the device and stops coming up at boot. "
              "And the queue of what was already recorded?",
        "pt": "O coletor sai do aparelho e para de subir no boot. E a fila do "
              "que já foi anotado?",
    },
    "remove.keep": {
        "en": "Keep the queue (recommended)",
        "pt": "Guardar a fila (recomendado)",
    },
    "remove.keep.note": {
        "en": "The file with what you listened to stays on the R1, and can "
              "still be sent later even without the collector installed.",
        "pt": "O arquivo com o que você ouviu continua no R1, e dá para enviar "
              "depois mesmo sem o coletor instalado.",
    },
    "remove.wipe": {
        "en": "Delete the queue as well",
        "pt": "Apagar a fila também",
    },
    "remove.wipe.note": {
        "en": "Everything goes: all of /usr/data/scrobble is removed. What was "
              "already sent to Last.fm stays there — this undoes nothing on "
              "your account.",
        "pt": "Some tudo: /usr/data/scrobble inteiro é removido. O que já foi "
              "enviado ao Last.fm continua lá, isto não desfaz nada na sua "
              "conta.",
    },
    "busy.remove": {
        "en": "Removing the collector…",
        "pt": "Removendo o coletor…",
    },

    # ------------------------------------------------------------ cartão 4
    "card.wifi.title": {
        "en": "4. Send by itself over Wi-Fi (no PC needed)",
        "pt": "4. Enviar sozinho pelo WiFi (sem precisar do PC)",
    },
    "card.wifi.body": {
        "en": "With this on, the R1 checks every twelve minutes: if Wi-Fi is "
              "already up, it sends what it has piled up — you never need the "
              "cable.\n\n"
              "It NEVER switches the radio on by itself. Leaving Wi-Fi on all "
              "the time is expensive (hundreds of milliwatts); riding along "
              "with a Wi-Fi that was already on costs about 0.1% of the "
              "battery per send. If you never turn Wi-Fi on, the queue simply "
              "waits for the cable.",
        "pt": "Com isto ligado, o R1 olha de doze em doze minutos: se o WiFi já "
              "estiver no ar, ele manda o que acumulou e pronto — você nunca "
              "precisa plugar o cabo.\n\n"
              "Ele NUNCA liga o rádio por conta própria. Deixar o WiFi ligado o "
              "tempo todo custa caro (centenas de miliwatts); pegar carona num "
              "WiFi que já estava ligado custa uns 0,1% de bateria por envio. "
              "Se você nunca ligar o WiFi, a fila simplesmente espera o cabo.",
    },
    "card.wifi.now": {
        "en": "Show “now playing” on my profile (live scrobbling)",
        "pt": "Mostrar “tocando agora” no meu perfil (live scrobbling)",
    },
    "card.wifi.now.note": {
        "en": "Makes the track you are playing show up pulsing on your Last.fm "
              "profile, instead of only entering the history when it "
              "ends.\n\n"
              "Measured on the R1: detection costs 10 ms, and the device "
              "spends 2.4 s of CPU per hour on it — nothing. What costs is "
              "having Wi-Fi on, which this feature requires: the radio draws "
              "~50-150 mW against the ~260 mW of the device playing, which "
              "takes 20-40% off the battery life. That bill is Wi-Fi's, not "
              "this feature's.",
        "pt": "Faz a faixa em reprodução aparecer pulsando no seu perfil do "
              "Last.fm, em vez de só entrar no histórico quando termina.\n\n"
              "Medido no R1: a detecção custa 10 ms e o aparelho gasta 2,4 s de "
              "processador por hora com isso — nada. O que pesa é ter o WiFi "
              "ligado, que este recurso exige: o rádio consome ~50-150 mW contra "
              "os ~260 mW do aparelho tocando, o que tira uns 20-40% da "
              "autonomia. Essa conta é do WiFi, não do recurso.",
    },
    "btn.wifi.enable": {
        "en": "Enable Wi-Fi sending",
        "pt": "Ativar envio pelo WiFi",
    },
    "btn.wifi.curl": {
        "en": "Build curl",
        "pt": "Compilar o curl",
    },
    "btn.wifi.cacert": {
        "en": "Download certificates",
        "pt": "Baixar certificados",
    },
    "btn.wifi.test": {
        "en": "Send now (test)",
        "pt": "Enviar agora (teste)",
    },
    "btn.wifi.disable": {
        "en": "Disable",
        "pt": "Desativar",
    },
    "card.wifi.key_note": {
        "en": "The session key is written to the device, at "
              "/usr/data/scrobble/sk, so it can identify itself on its own. It "
              "does not give access to your password, and you can revoke it "
              "whenever you like at last.fm → Settings → Applications. But "
              "anyone with ADB access to the device can read it — if that "
              "bothers you, use cable sending only, which works just as well.",
        "pt": "A chave de sessão fica gravada no aparelho, em "
              "/usr/data/scrobble/sk, para ele poder se identificar sozinho. "
              "Ela não dá acesso à sua senha, e você pode revogá-la quando "
              "quiser em last.fm → Configurações → Aplicativos. Mas quem tiver "
              "ADB no aparelho consegue lê-la — se isso incomodar, use só o "
              "envio pelo cabo, que funciona igual.",
    },
    "wifi.install_first": {
        "en": "Install the collector first.",
        "pt": "Instale o coletor primeiro.",
    },
    "wifi.active": {
        "en": "Wi-Fi sending ACTIVE.",
        "pt": "Envio pelo WiFi ATIVO.",
    },
    "wifi.off_missing": {
        "en": "Wi-Fi sending off — missing {faltando}.",
        "pt": "Envio pelo WiFi desligado — falta {faltando}.",
    },
    "wifi.missing.programs": {
        "en": "the sending programs",
        "pt": "os programas de envio",
    },
    "wifi.missing.key": {
        "en": "the session key",
        "pt": "a chave de sessão",
    },
    "wifi.missing.cacert": {
        "en": "the cacert.pem",
        "pt": "o cacert.pem",
    },
    # O que se mede é a rota padrão no /proc/net/route, e é isso que estas
    # frases dizem. A versão anterior afirmava "o WiFi está desligado", que é
    # uma causa entre várias: o rádio pode estar ligado e sem associar, ou
    # associado e sem endereço. Só a consequência é conhecida.
    "wifi.radio_up": {
        "en": "The R1 has a way out to the network right now.",
        "pt": "O R1 tem saída para a rede agora.",
    },
    "wifi.radio_down": {
        "en": "The R1 has no way out to the network at the moment — Wi-Fi off, "
              "or on but not connected. The queue waits; nothing is lost.",
        "pt": "O R1 está sem saída para a rede no momento — WiFi desligado, ou "
              "ligado e sem conexão. A fila espera; nada é perdido.",
    },
    "wifi.last_send": {
        "en": "Last recorded send: {quando}",
        "pt": "Último envio registrado: {quando}",
    },
    "wifi.need_account": {
        "en": "Authorise your Last.fm account first (card 2).",
        "pt": "Autorize a conta do Last.fm primeiro (cartão 2).",
    },
    "wifi.enabled": {
        "en": "Done. The next time the R1's Wi-Fi is on, it will send by "
              "itself. Use “Send now (test)” to check without waiting the 12 "
              "minutes.",
        "pt": "Pronto. Da próxima vez que o WiFi do R1 estiver ligado, ele "
              "manda sozinho. Use “Enviar agora (teste)” para conferir sem "
              "esperar os 12 minutos.",
    },
    "busy.wifi.enable": {
        "en": "Enabling Wi-Fi sending…",
        "pt": "Ativando o envio pelo WiFi…",
    },
    "wifi.disable.title": {
        "en": "Disable Wi-Fi sending",
        "pt": "Desativar o envio pelo WiFi",
    },
    "wifi.disable.body": {
        "en": "The session key is wiped from the device and it goes back to "
              "just recording. The queue and cable sending keep working "
              "normally.",
        "pt": "A chave de sessão é apagada do aparelho e ele volta a só anotar. "
              "A fila e o envio pelo cabo continuam funcionando normalmente.",
    },
    "busy.wifi.disable": {
        "en": "Disabling…",
        "pt": "Desativando…",
    },
    "wifi.test_result": {
        "en": "The device tried to send just now.\n{saida}",
        "pt": "O aparelho tentou enviar agora.\n{saida}",
    },
    "busy.wifi.test": {
        "en": "Telling the device to send now…",
        "pt": "Mandando o aparelho enviar agora…",
    },
    "now.needs_wifi": {
        "en": "For “now playing” to work, enable Wi-Fi sending first (the "
              "button below) — that is what puts the key and curl on the "
              "device.",
        "pt": "Para o “tocando agora” funcionar, ative primeiro o envio pelo "
              "WiFi (o botão abaixo) — é ele que leva a chave e o curl para o "
              "aparelho.",
    },
    "now.enabled": {
        "en": "\n\n“Now playing” is on. Play a track and it should appear on "
              "your profile within 15 seconds.",
        "pt": "\n\n“Tocando agora” ligado. Toque uma música e ela deve aparecer "
              "no seu perfil em até 15 segundos.",
    },
    "busy.apply": {
        "en": "Applying on the device…",
        "pt": "Aplicando no aparelho…",
    },
    "busy.cacert": {
        "en": "Downloading the certificates…",
        "pt": "Baixando os certificados…",
    },
    "progress.downloading": {
        "en": "downloading",
        "pt": "baixando",
    },
    "progress.certificates": {
        "en": "certificates",
        "pt": "certificados",
    },
    "cacert.installed": {
        "en": "certificates installed",
        "pt": "certificados instalados",
    },

    # ------------------------------------------------------------- o curl
    "curl.missing.title": {
        "en": "curl for the R1 has not been built yet.",
        "pt": "O curl para o R1 ainda não foi compilado.",
    },
    "curl.missing.detail": {
        "en": "It is what lets the device talk to Last.fm on its own. Use the "
              "“Build curl” button — it takes 20 to 30 minutes, once only, and "
              "everything comes from the curl project's official source, "
              "compiled on your own machine.\n\n"
              "In the meantime, cable sending works normally: just fetch the "
              "queue and send from here.\n\n"
              "I looked in:\n{onde}",
        "pt": "Ele é o que permite o aparelho falar com o Last.fm sozinho. Use "
              "o botão “Compilar o curl” — leva de 20 a 30 minutos, uma vez só, "
              "e tudo sai da fonte oficial do projeto curl, compilada na sua "
              "própria máquina.\n\n"
              "Enquanto isso, o envio pelo cabo funciona normalmente: é só "
              "trazer a fila e mandar daqui.\n\n"
              "Procurei em:\n{onde}",
    },
    "curl.again.title": {
        "en": "Build it again?",
        "pt": "Compilar de novo?",
    },
    "curl.again.body": {
        "en": "There is already a curl built at:\n{caminho}\n\nBuilding again "
              "takes 20 to 30 minutes and will replace that file.",
        "pt": "Já existe um curl compilado em:\n{caminho}\n\nCompilar de novo "
              "leva de 20 a 30 minutos e vai substituir esse arquivo.",
    },
    "curl.again.ok": {
        "en": "Build anyway",
        "pt": "Compilar mesmo assim",
    },
    "curl.warn.title": {
        "en": "This takes a while",
        "pt": "Isto demora",
    },
    "curl.warn.body": {
        "en": "I will download the curl and Mbed-TLS sources from both "
              "projects' official sites and build them here on your machine, "
              "for the R1's MIPS.\n\n"
              "It takes 20 to 30 minutes and happens once only — after that "
              "the binary is kept. You can stop at any point with the button "
              "at the bottom.\n\n"
              "Until this is ready, cable sending keeps working normally.",
        "pt": "Vou baixar as fontes do curl e do Mbed-TLS dos sites oficiais "
              "dos dois projetos e compilar aqui na sua máquina, para o MIPS "
              "do R1.\n\n"
              "Leva de 20 a 30 minutos e é uma vez só — depois o binário fica "
              "guardado. Dá para interromper a qualquer momento pelo botão do "
              "rodapé.\n\n"
              "Enquanto isso não estiver pronto, o envio pelo cabo continua "
              "funcionando normalmente.",
    },
    "curl.warn.ok": {
        "en": "Build it",
        "pt": "Compilar",
    },
    "curl.failed.stage": {
        "en": "Stopped at: {etapa}",
        "pt": "Parou em: {etapa}",
    },
    "curl.failed.start": {
        "en": "start",
        "pt": "início",
    },
    "curl.failed.title": {
        "en": "The curl build did not finish.",
        "pt": "A compilação do curl não terminou.",
    },
    "curl.failed.log": {
        "en": "\n\nFull output: {caminho}",
        "pt": "\n\nSaída completa: {caminho}",
    },
    "curl.failed.script": {
        "en": "\n\nThe script is at {caminho} — you can run it by hand and see "
              "where it stopped.",
        "pt": "\n\nO script está em {caminho} — dá para rodá-lo à mão e ver "
              "onde parou.",
    },
    "curl.failed.short": {
        "en": "the build did not finish",
        "pt": "a compilação não terminou",
    },
    "curl.ok.short": {
        "en": "curl built",
        "pt": "curl compilado",
    },
    "curl.ok.body": {
        "en": "curl ready: {caminho}\n\nNow click “Enable Wi-Fi sending”.",
        "pt": "curl pronto: {caminho}\n\nAgora clique em “Ativar envio pelo "
              "WiFi”.",
    },
    "busy.curl": {
        "en": "Building curl (20-30 min)…",
        "pt": "Compilando o curl (20-30 min)…",
    },

    # ------------------------------------------------------------ cartão 5
    "card.queue.title": {
        "en": "5. What the device wrote down",
        "pt": "5. O que o aparelho anotou",
    },
    "btn.queue.fetch": {
        "en": "Fetch the queue from the device",
        "pt": "Trazer a fila do aparelho",
    },
    "card.queue.empty": {
        "en": "Nothing fetched yet.",
        "pt": "Nada trazido ainda.",
    },
    "card.queue.note": {
        "en": "A track makes the list when the gap between its line and the "
              "previous one was long enough for it to play more than half. "
              "Skipped it halfway? The line shows up too early, and it stays "
              "out — the reason appears in the right-hand column.",
        "pt": "Uma faixa entra na lista quando o tempo entre a linha dela e a "
              "anterior deu para ela tocar mais da metade. Pulou no meio? A "
              "linha aparece cedo demais, e ela fica de fora — o motivo aparece "
              "na coluna da direita.",
    },
    "col.when": {"en": "When", "pt": "Quando"},
    "col.artist": {"en": "Artist", "pt": "Artista"},
    "col.track": {"en": "Track", "pt": "Faixa"},
    "col.album": {"en": "Album", "pt": "Álbum"},
    "col.listened": {"en": "Heard", "pt": "Ouviu"},
    "col.state": {"en": "Status", "pt": "Situação"},
    "state.will_send": {"en": "sending", "pt": "vai"},
    "busy.queue": {
        "en": "Fetching the queue from the device…",
        "pt": "Trazendo a fila do aparelho…",
    },

    # ------------------------------------------------------------ cartão 6
    "card.send.title": {
        "en": "6. Send from here, over the cable",
        "pt": "6. Enviar daqui, pelo cabo",
    },
    "btn.send": {
        "en": "Send to Last.fm",
        "pt": "Enviar ao Last.fm",
    },
    "btn.trim": {
        "en": "Trim the queue on the device",
        "pt": "Enxugar a fila no aparelho",
    },
    "send.accepted": {
        "en": "{n} accepted by Last.fm.",
        "pt": "{n} aceita(s) pelo Last.fm.",
    },
    "send.refused": {
        "en": "{n} refused:",
        "pt": "{n} recusada(s):",
    },
    "send.refused.item": {
        "en": "   • {artista} — {faixa}: {motivo}",
        "pt": "   • {artista} — {faixa}: {motivo}",
    },
    "send.refused.more": {
        "en": "   … and {n} more.",
        "pt": "   … e mais {n}.",
    },
    "send.left": {
        "en": "{n} were not sent and are still in the queue.",
        "pt": "{n} não chegaram a ser enviadas e continuam na fila.",
    },
    "send.log": {
        "en": "Last.fm: {n} scrobble(s) accepted.",
        "pt": "Last.fm: {n} scrobble(s) aceitos.",
    },
    "send.progress": {
        "en": "{feito} of {total}",
        "pt": "{feito} de {total}",
    },
    "busy.send": {
        "en": "Sending to Last.fm…",
        "pt": "Enviando ao Last.fm…",
    },
    "busy.mark": {
        "en": "Recording on the device what was sent…",
        "pt": "Marcando no aparelho o que foi enviado…",
    },
    "trim.nothing": {
        "en": "Nothing to trim: the queue only shrinks after some play has "
              "been accepted by Last.fm.",
        "pt": "Não há o que enxugar: a fila só encolhe depois de alguma "
              "execução ter sido aceita pelo Last.fm.",
    },
    "trim.title": {
        "en": "Trim the queue",
        "pt": "Enxugar a fila",
    },
    "trim.body": {
        "en": "The {n} play(s) already accepted by Last.fm will leave the "
              "device's file. A copy of the current file is kept as "
              "fila.tsv.bak, on the R1 itself.",
        "pt": "As {n} execução(ões) já aceitas pelo Last.fm saem do arquivo do "
              "aparelho. Uma cópia do arquivo atual fica em fila.tsv.bak, no "
              "próprio R1.",
    },
    "trim.ok": {
        "en": "Trim",
        "pt": "Enxugar",
    },
    "busy.trim": {
        "en": "Trimming the queue…",
        "pt": "Enxugando a fila…",
    },

    # -------------------------------------------------------------- adb/zig
    "err.adb.title": {
        "en": "adb is not configured",
        "pt": "adb não configurado",
    },
    "err.adb.body": {
        "en": "The Android Platform Tools are what this program uses to talk "
              "to the R1. Download them, unzip them into a folder and put that "
              "folder on your PATH:\n{url}\n\n"
              "On Windows, unzipping into C:\\platform-tools is enough — this "
              "program looks there.",
        "pt": "O Android Platform Tools é como este programa fala com o R1. "
              "Baixe, extraia numa pasta e ponha essa pasta no PATH:\n{url}\n\n"
              "No Windows, extrair em C:\\platform-tools basta — este programa "
              "procura lá.",
    },
    "err.linux.title": {
        "en": "Building needs a Linux environment.",
        "pt": "Compilar precisa de um ambiente Linux.",
    },
    "err.linux.body": {
        "en": "On Windows that means a WSL distribution. In a PowerShell "
              "running as administrator:\n\n"
              "    wsl --install -d Ubuntu\n\n"
              "Then restart the computer and open Ubuntu once, so it can "
              "finish setting itself up.\n\n"
              "Until that exists, cable sending works normally — only "
              "automatic Wi-Fi sending is out.",
        "pt": "No Windows, isso quer dizer uma distribuição do WSL. Num "
              "PowerShell como administrador:\n\n"
              "    wsl --install -d Ubuntu\n\n"
              "Depois reinicie o computador e abra o Ubuntu uma vez, para ele "
              "terminar de se configurar.\n\n"
              "Enquanto isso não existir, o envio pelo cabo funciona "
              "normalmente — só o envio automático pelo WiFi fica de fora.",
    },
    "zig.installing": {
        "en": "Zig is not here yet; installing it first",
        "pt": "O Zig ainda não está aqui; instalando primeiro",
    },
    "zig.downloading": {
        "en": "downloading Zig",
        "pt": "baixando o Zig",
    },
    "zig.installed": {
        "en": "Zig {versao} installed",
        "pt": "Zig {versao} instalado",
    },
    "err.zig.title": {
        "en": "I could not work out which Zig version to download.",
        "pt": "Não consegui descobrir uma versão do Zig para baixar.",
    },
    "err.zig.body": {
        "en": "The ziglang.org version index did not answer, or has no build "
              "for this environment (target: {alvo}).",
        "pt": "O índice de versões do ziglang.org não respondeu, ou não tem "
              "build para este ambiente (alvo: {alvo}).",
    },
    "log.no_cacert_device": {
        "en": "The device has no certificates; fetching the bundle",
        "pt": "O aparelho não tem certificados; buscando o pacote",
    },

    # ------------------------------------------------------------- widgets
    "dlg.ok": {"en": "Continue", "pt": "Continuar"},
    "dlg.cancel": {"en": "Cancel", "pt": "Cancelar"},
    "dlg.confirm": {"en": "Confirm", "pt": "Confirmar"},
    "dlg.close": {"en": "Close", "pt": "Fechar"},
    "dlg.copy": {"en": "Copy", "pt": "Copiar"},
    "dlg.files": {"en": "Files:", "pt": "Arquivos:"},
    "pane.title": {"en": "LIVE LOG", "pt": "REGISTRO AO VIVO"},
    "pane.follow": {"en": "follow", "pt": "acompanhar"},
    "progress.of": {
        "en": "{prefixo}{feito} MB of {total} MB  ({pct}%)",
        "pt": "{prefixo}{feito} MB de {total} MB  ({pct}%)",
    },
    "err.adb.title2": {
        "en": "adb was not found.",
        "pt": "O adb não foi encontrado.",
    },

    # ------------------------------------------------------------------ CLI
    "cli.desc": {
        "en": "Last.fm scrobbler for the HiBy R1 (the plain model).",
        "pt": "Scrobbler do Last.fm para o HiBy R1 (modelo comum).",
    },
    "cli.check.help": {
        "en": "only run the environment checks, in the terminal",
        "pt": "só as verificações do ambiente, no terminal",
    },
    "cli.dry.help": {
        "en": "dry run: show the commands without running them",
        "pt": "modo simulação: mostra os comandos sem executar",
    },
    "cli.lang.help": {
        "en": "interface language (en, pt)",
        "pt": "idioma da interface (en, pt)",
    },
    "cli.check.header": {
        "en": "R1 scrobbler v{versao} — environment checks",
        "pt": "Scrobbler do R1 v{versao} — verificações",
    },
    "cli.api.set": {
        "en": "  Last.fm API key: stored.",
        "pt": "  Chave de API do Last.fm: guardada.",
    },
    "cli.api.unset": {
        "en": "  Last.fm API key: not configured yet (the window explains how "
              "to register your own).",
        "pt": "  Chave de API do Last.fm: ainda não configurada (a interface "
              "explica como registrar a sua).",
    },
    "cli.log_at": {
        "en": "\n  Log: {caminho}",
        "pt": "\n  Registro: {caminho}",
    },
    "cli.no_tk": {
        "en": "error: this Python has no Tkinter.\n"
              "  Windows/macOS: reinstall the official Python from python.org\n"
              "  Debian/Ubuntu: sudo apt install python3-tk\n"
              "  Fedora:        sudo dnf install python3-tkinter",
        "pt": "erro: este Python não tem Tkinter.\n"
              "  Windows/macOS: reinstale o Python oficial de python.org\n"
              "  Debian/Ubuntu: sudo apt install python3-tk\n"
              "  Fedora:        sudo dnf install python3-tkinter",
    },
    "cli.dry_warn": {
        "en": "Dry run: nothing will be written to the device.",
        "pt": "Modo simulação: nada será gravado no aparelho.",
    },
    "cli.interrupted": {
        "en": "\ninterrupted",
        "pt": "\ninterrompido",
    },
    "cli.error": {
        "en": "error: {mensagem}",
        "pt": "erro: {mensagem}",
    },
    "cli.version_line": {
        "en": "R1 scrobbler v{versao}",
        "pt": "Scrobbler do R1 v{versao}",
    },
    "check.ok": {"en": "OK", "pt": "OK"},
    "check.warn": {"en": "WARN", "pt": "AVISO"},
    "check.missing": {"en": "MISSING", "pt": "FALTA"},

    # ------------------------------------------------------------- ambiente
    "env.python": {
        "en": "Python with Tkinter",
        "pt": "Python com Tkinter",
    },
    "env.python.missing": {
        "en": "missing",
        "pt": "ausente",
    },
    "env.python.hint": {
        "en": "Windows/macOS: reinstall Python from python.org.\n"
              "Debian/Ubuntu: sudo apt install python3-tk",
        "pt": "Windows/macOS: reinstale o Python de python.org.\n"
              "Debian/Ubuntu: sudo apt install python3-tk",
    },
    "env.adb": {
        "en": "adb (Android Platform Tools)",
        "pt": "adb (Android Platform Tools)",
    },
    "env.adb.missing": {
        "en": "not found",
        "pt": "não encontrado",
    },
    "env.adb.hint": {
        "en": "Download the Platform Tools, unzip them into a folder and put "
              "that folder on your PATH:\n{url}",
        "pt": "Baixe o Platform Tools, extraia numa pasta e ponha essa pasta "
              "no PATH:\n{url}",
    },
    "env.wsl": {
        "en": "WSL (only needed for building)",
        "pt": "WSL (só para compilar)",
    },
    "env.wsl.ok": {
        "en": "distribution {nome} answers",
        "pt": "distribuição {nome} responde",
    },
    "env.wsl.missing": {
        "en": "not found",
        "pt": "não encontrado",
    },
    "env.wsl.hint": {
        "en": "Only needed to build the device programs, which is what enables "
              "Wi-Fi sending. Without it, cable sending keeps working.\n\n"
              "To install, in a PowerShell running as administrator:\n"
              "    wsl --install -d Ubuntu",
        "pt": "Só faz falta para compilar os programas do aparelho, que é o que "
              "habilita o envio pelo WiFi. Sem ele o envio pelo cabo continua "
              "funcionando.\n\n"
              "Para instalar, num PowerShell como administrador:\n"
              "    wsl --install -d Ubuntu",
    },
    "env.zig": {
        "en": "Zig (only needed for building)",
        "pt": "Zig (só para compilar)",
    },
    "env.zig.present": {
        "en": "present",
        "pt": "presente",
    },
    "env.zig.missing": {
        "en": "not installed",
        "pt": "não instalado",
    },
    "env.zig.hint": {
        "en": "This program downloads and installs Zig by itself when you ask "
              "it to build. It is only needed for Wi-Fi sending and “now "
              "playing”.",
        "pt": "Este programa baixa e instala o Zig sozinho quando você mandar "
              "compilar. Ele só é necessário para o envio pelo WiFi e o "
              "“tocando agora”.",
    },

    # ---------------------------------------------- o que muda entre versões
    # Aparece na tela quando o aparelho está atrasado. Cada linha diz o que o
    # usuário ganha ao atualizar, não o que mudou no código.
    "novidade.14": {
        "en": "the collector now stays out of the player's way when a track "
              "changes, which is when the R1 was rebooting. Skipping through "
              "tracks quickly would freeze the device, and removing the "
              "collector stopped it — that is how this was found. At every "
              "track change it used to copy the player's whole database into "
              "RAM (624 kB on a device with about 1.7 MB free), rewrite the "
              "card's spreadsheet, and run curl (1.6 MB, larger than the free "
              "memory) — all in the same second the player was allocating "
              "buffers for the new track. Now the database is read in place "
              "with no copy, the spreadsheet is rewritten at most once a "
              "minute, the read waits a few seconds for the player to settle, "
              "and each track change reschedules the send instead of firing "
              "it — so skipping five tracks in a row runs curl zero times. "
              "Scrobbles reach your profile about half a minute later than "
              "before, which is cheap next to the device restarting mid-song",
        "pt": "o coletor agora sai da frente do player na troca de faixa, que "
              "era quando o R1 reiniciava. Pular faixas rápido travava o "
              "aparelho, e tirar o coletor resolvia — foi assim que isto foi "
              "encontrado. A cada troca ele copiava o banco inteiro do player "
              "para a RAM (624 kB num aparelho com uns 1,7 MB livres), "
              "reescrevia a planilha do cartão e executava o curl (1,6 MB, "
              "maior que a memória livre) — tudo no mesmo segundo em que o "
              "player pedia os buffers da faixa nova. Agora o banco é lido no "
              "lugar, sem cópia; a planilha é reescrita no máximo uma vez por "
              "minuto; a leitura espera alguns segundos o player assentar; e "
              "cada troca reagenda o envio em vez de dispará-lo — então pular "
              "cinco faixas seguidas não executa o curl nenhuma vez. O "
              "scrobble chega ao perfil meio minuto mais tarde, o que é "
              "barato perto de o aparelho reiniciar no meio da música",
    },
    "novidade.13": {
        "en": "the first track of an album is no longer lost. Starting an "
              "album could put two rows in the player's database before the "
              "collector's first look — it goes to a slow rhythm when the "
              "device is idle — and both got the same timestamp, so the gap "
              "between them was zero and everything but the last one was "
              "thrown away as \"heard nothing\". It showed up as \"scrobbling "
              "now\" and then never went up, which is exactly how it was "
              "reported. Also: an empty mount point is no longer mistaken for "
              "a memory card, so the log and the spreadsheet are never "
              "written where they would vanish from sight the moment a card "
              "is inserted",
        "pt": "a primeira faixa de um álbum deixa de se perder. Começar um "
              "álbum podia pôr duas linhas no banco do player antes da "
              "primeira olhada do coletor — ele cai para um ritmo lento com o "
              "aparelho ocioso —, e as duas levavam o mesmo carimbo de hora: "
              "o espaço entre elas dava zero e tudo menos a última era "
              "descartado como \"não ouviu nada\". Ela aparecia no \"ouvindo "
              "agora\" e nunca subia, que foi exatamente como o problema foi "
              "relatado. Também: um ponto de montagem vazio deixa de ser "
              "confundido com cartão de memória, então o registro e a "
              "planilha nunca são gravados onde sumiriam de vista assim que "
              "um cartão fosse posto",
    },
    "novidade.12": {
        "en": "the collector now finds the player's music database wherever it "
              "is. The player can be told to keep it on the memory card "
              "(`tf_music_db_enable`, on the device's own screen), and from "
              "then on the one in internal memory is never updated again — so "
              "anyone with that turned on saw the program say \"running\" and "
              "collect nothing, forever. It now follows whichever one the "
              "player is actually writing, and says which in the log and on "
              "the card. Also: a track's start time now comes from the "
              "database's own timestamp — the moment the player wrote the row "
              "— instead of the moment the collector noticed. That was losing "
              "up to fifteen seconds off the beginning of every track; "
              "measured on a real device, one track change recovered nine",
        "pt": "o coletor agora encontra o banco de músicas do player onde quer "
              "que ele esteja. Dá para mandar o player guardá-lo no cartão "
              "(`tf_music_db_enable`, na tela do próprio aparelho), e a partir "
              "daí o da memória interna nunca mais é atualizado — então quem "
              "tinha isso ligado via o programa dizer \"rodando\" e não colher "
              "nada, para sempre. Agora ele segue o que o player está de fato "
              "escrevendo, e diz qual é no registro e no cartão. Também: a "
              "hora em que uma faixa começou passa a vir do carimbo do próprio "
              "banco — o instante em que o player gravou a linha — em vez do "
              "instante em que o coletor percebeu. Isso comia até quinze "
              "segundos do começo de cada faixa; medido num aparelho de "
              "verdade, uma troca de faixa recuperou nove",
    },
    "novidade.11": {
        "en": "the time you listened is now MEASURED, not inferred. The "
              "collector counts the seconds audio is actually coming out of "
              "each track, instead of assuming the gap between two history "
              "rows was all music. That gap was never music: pausing made a "
              "track you did finish come out half-listened and get thrown "
              "away, and starting the player with music already on made the "
              "track playing right then go up as a scrobble the moment it "
              "began — showing on your profile as scrobbled and as "
              "\"scrobbling now\" at the same time. Pausing now suspends the "
              "count instead of ending the track, and the track playing when "
              "the collector wakes up is counted from zero. The last track of "
              "a session also stops waiting twelve minutes to be sent",
        "pt": "o tempo ouvido agora é MEDIDO, e não deduzido. O coletor conta "
              "os segundos em que sai som de cada faixa, em vez de supor que "
              "o espaço entre duas linhas do histórico foi tudo música. Esse "
              "espaço nunca foi música: pausar fazia uma faixa que você "
              "terminou sair como meia escuta e ser descartada, e ligar o "
              "player com música tocando fazia a faixa daquele momento subir "
              "como scrobble no instante em que começou — aparecendo no "
              "perfil como scrobbada e como \"ouvindo agora\" ao mesmo "
              "tempo. Pausar agora suspende a contagem em vez de encerrar a "
              "faixa, e a faixa que já estava tocando quando o coletor "
              "acorda é contada do zero. A última faixa de cada sessão também "
              "deixa de esperar doze minutos para ser enviada",
    },
    "novidade.10": {
        "en": "a track now has to be played almost to the end to count — "
              "90% of it, not the half Last.fm settles for. Half meant a track "
              "you walked away from went up as if you had listened to it, and "
              "an integer rounding let even 49.6% through. Also: you can "
              "select rows in the queue and discard them, so a track you do "
              "not want on your profile no longer means wiping the whole "
              "queue",
        "pt": "uma faixa agora precisa ter tocado quase até o fim para contar "
              "— 90% dela, e não a metade com que o Last.fm se contenta. "
              "Metade fazia uma faixa largada no meio subir como se tivesse "
              "sido ouvida, e um arredondamento deixava passar até 49,6%. "
              "Também: dá para marcar linhas da fila e descartá-las, então "
              "uma faixa que você não quer no perfil deixa de exigir apagar a "
              "fila inteira",
    },
    "novidade.9": {
        "en": "three counting bugs found by testing on a real device: a track "
              "that had only just started was credited in full whenever the "
              "collector had been restarted; a five-minute track came out as "
              "one second because the silence marker was being read as an end "
              "time when it actually marks the last thing that happened; and "
              "the send now lands on the cycle after a track closes instead "
              "of fifteen seconds later",
        "pt": "tres erros de contagem achados testando num aparelho de "
              "verdade: uma faixa recem-comecada levava credito integral "
              "sempre que o coletor tinha sido reiniciado; uma faixa de cinco "
              "minutos saia com um segundo, porque o marcador de silencio "
              "estava sendo lido como hora de termino quando ele marca o "
              "ultimo evento; e o envio passa a cair na verificacao seguinte "
              "ao fechamento, em vez de quinze segundos depois",
    },
    "novidade.8": {
        "en": "the listened time is now measured instead of guessed. The "
              "player writes its history row when a track STARTS, not when it "
              "ends — checked live on the device — so the gap between two "
              "rows is how long the FIRST one played. Crediting it to the "
              "second is what made a track that had barely started show up as "
              "played in full, while the one actually listened to showed 0s. "
              "Also: the spreadsheet program now installs with the collector, "
              "so the card's scrobbles.csv no longer depends on turning Wi-Fi "
              "sending on",
        "pt": "o tempo ouvido passa a ser medido, não estimado. O player "
              "grava a linha do histórico quando a faixa COMEÇA, não quando "
              "acaba — conferido ao vivo no aparelho —, então o espaço entre "
              "duas linhas é quanto a PRIMEIRA tocou. Creditá-lo à segunda "
              "era o que fazia uma faixa recém-começada aparecer como ouvida "
              "inteira, enquanto a de fato ouvida ficava com 0s. Também: o "
              "programa da planilha passa a ser instalado junto com o "
              "coletor, então o scrobbles.csv do cartão não depende mais de "
              "ligar o envio por WiFi",
    },
    "novidade.7": {
        "en": "an album listened to while the collector was stopped is no "
              "longer recorded as 0 seconds — the tracks it finds on waking "
              "up now get spread over real times instead of all sharing the "
              "second it happened to look; and when the firmware cannot start "
              "it at boot, the app says so plainly instead of just showing "
              "“installed, stopped”",
        "pt": "um álbum ouvido com o coletor parado deixa de ser registrado "
              "como 0 segundos — as faixas que ele encontra ao acordar passam "
              "a receber horas reais, em vez de todas dividirem o segundo em "
              "que ele por acaso olhou; e quando o firmware não consegue "
              "iniciá-lo no boot, o programa diz isso com todas as letras em "
              "vez de só mostrar “instalado, parado”",
    },
    "novidade.6": {
        "en": "Tidal is scrobbled too — streamed tracks never entered the "
              "player's database, so the scrobbler was blind to them; a log "
              "and a spreadsheet are now written to the memory card; and a "
              "track is sent about 30 seconds after it ends instead of "
              "waiting up to twelve minutes",
        "pt": "o Tidal passa a ser scrobblado — faixas transmitidas nunca "
              "entravam no banco do player, então o scrobbler era cego a "
              "elas; um registro e uma planilha passam a ser gravados no "
              "cartão de memória; e a faixa é enviada uns 30 segundos depois "
              "de acabar, em vez de esperar até doze minutos",
    },
    "novidade.5": {
        "en": "the collector is now started BEFORE the `exit` in init.sh — it "
              "used to be appended at the end of the file, after `exit 0`, and "
              "so never came up at boot; and a missing cacert.pem stopped "
              "being silent",
        "pt": "o coletor passa a ser iniciado ANTES do `exit` do init.sh — "
              "antes ele era acrescentado no fim do arquivo, depois do "
              "`exit 0`, e por isso nunca subia no boot; e a falta do "
              "cacert.pem deixou de ser silenciosa",
    },
    "novidade.4": {
        "en": "the lock file moved out of /usr/data into /tmp — it used to "
              "survive a shutdown and, at the next boot, a reused pid made the "
              "daemon think another instance was running and exit quietly, "
              "leaving the scrobbler dead after every restart",
        "pt": "o arquivo de trava saiu de /usr/data para /tmp — antes ele "
              "sobrevivia ao desligamento e, no boot seguinte, um pid "
              "reaproveitado fazia o daemon achar que já havia outra instância "
              "e sair calado, deixando o scrobbler morto depois de cada "
              "reinício",
    },
    "novidade.3": {
        "en": "having no Wi-Fi no longer counts as a failure, and when it "
              "comes back the queue goes out immediately — before, hours of "
              "travelling without a network could delay the scrobbles for up "
              "to two hours after you got home",
        "pt": "ficar sem WiFi não conta mais como falha, e quando ele volta a "
              "fila sai na hora — antes, horas de viagem sem rede podiam adiar "
              "os scrobbles por até duas horas depois de você chegar em casa",
    },
    "novidade.2": {
        "en": "tells Last.fm which track is playing (\"now playing\"), and the "
              "daemon no longer dies when the shell that started it exits",
        "pt": "avisa o Last.fm da faixa em reprodução (\"tocando agora\"), e o "
              "daemon não morre mais quando o shell que o iniciou termina",
    },
    "novidade.1": {
        "en": "offline collection and automatic Wi-Fi sending",
        "pt": "coleta offline e envio automático pelo WiFi",
    },

    # ------------------------------------------------------------- aparelho
    "ap.err.collector.title": {
        "en": "The collector has not been built yet.",
        "pt": "O coletor ainda não foi compilado.",
    },
    "ap.err.collector.body": {
        "en": "Use the build button before installing: that is what produces "
              "the mipsel binary from collector.c.",
        "pt": "Use o botão de compilar antes de instalar: é ele que gera o "
              "binário mipsel a partir do collector.c.",
    },
    "ap.err.daemon": {
        "en": "I could not find the program's r1scrobbled.sh.",
        "pt": "Não achei o r1scrobbled.sh do programa.",
    },
    "ap.installing": {
        "en": "Installing the collector on the device",
        "pt": "Instalando o coletor no aparelho",
    },
    "ap.installed": {
        "en": "Collector installed at {onde}",
        "pt": "Coletor instalado em {onde}",
    },
    "ap.err.sender.title": {
        "en": "r1send has not been built yet.",
        "pt": "O r1send ainda não foi compilado.",
    },
    "ap.err.sender.body": {
        "en": "It is the program that assembles and signs the batch inside the "
              "device. Use the build button first.",
        "pt": "Ele é o programa que monta e assina o lote dentro do aparelho. "
              "Use o botão de compilar antes.",
    },
    "ap.err.curl.title": {
        "en": "I could not find the static curl for MIPS.",
        "pt": "Não achei o curl estático para MIPS.",
    },
    "ap.err.curl.body": {
        "en": "Use the “Build curl” button on the Wi-Fi sending card — it "
              "takes 20 to 30 minutes and happens once only. A static mipsel "
              "curl you already have works too.",
        "pt": "Use o botão “Compilar o curl” na tela do envio pelo WiFi — leva "
              "de 20 a 30 minutos e é uma vez só. Um curl mipsel estático que "
              "você já tenha também serve.",
    },
    "ap.err.nokey.title": {
        "en": "The Last.fm account still needs authorising.",
        "pt": "Falta autorizar a conta do Last.fm.",
    },
    "ap.err.nokey.body": {
        "en": "Without the session key the device has no way to identify "
              "itself.",
        "pt": "Sem a chave de sessão o aparelho não tem como se identificar.",
    },
    "ap.teaching": {
        "en": "Teaching the device to send on its own",
        "pt": "Ensinando o aparelho a enviar sozinho",
    },
    "ap.err.nocacert.title": {
        "en": "The certificate bundle is missing on the device.",
        "pt": "Falta o pacote de certificados no aparelho.",
    },
    "ap.err.nocacert.body": {
        "en": "Without it the R1 has no way to check that the server really is "
              "Last.fm, and sending never happens — nor does “now "
              "playing”.\n\n"
              "Use the “Download certificates” button, which fetches the "
              "bundle from the curl project and installs it. Then come back "
              "here.",
        "pt": "Sem ele o R1 não tem como conferir que o servidor é mesmo o "
              "Last.fm, e o envio nunca acontece — nem o “tocando agora”.\n\n"
              "Use o botão “Baixar certificados”, que busca o pacote do "
              "projeto curl e o instala. Depois volte aqui.",
    },
    "ap.sending_on": {
        "en": "The device will now send on its own whenever it has Wi-Fi.",
        "pt": "O aparelho passa a mandar sozinho quando pegar WiFi.",
    },
    "ap.now.on": {
        "en": "“Now playing” enabled on the device.",
        "pt": "“Tocando agora” ligado no aparelho.",
    },
    "ap.now.off": {
        "en": "“Now playing” disabled on the device.",
        "pt": "“Tocando agora” desligado no aparelho.",
    },
    "ap.err.cacert.here": {
        "en": "The cacert.pem is not here.",
        "pt": "O cacert.pem não está aqui.",
    },
    "ap.err.cacert.small.title": {
        "en": "The cacert.pem that was downloaded looks too small.",
        "pt": "O cacert.pem baixado parece pequeno demais.",
    },
    "ap.err.cacert.small.body": {
        "en": "{tam} bytes. The root certificate bundle is around 200 kB; "
              "something went wrong in the download.",
        "pt": "{tam} bytes. O pacote de certificados raiz tem uns 200 kB; algo "
              "deu errado no download.",
    },
    "ap.cacert.ok": {
        "en": "cacert.pem installed on the device ({tam} bytes)",
        "pt": "cacert.pem instalado no aparelho ({tam} bytes)",
    },
    "ap.sending_off": {
        "en": "Automatic sending disabled. The device keeps recording, and "
              "cable sending keeps working.",
        "pt": "Envio automático desligado. O aparelho continua anotando, e o "
              "envio pelo cabo continua funcionando.",
    },
    "ap.reply": {
        "en": "Device reply: {saida}",
        "pt": "Resposta do aparelho: {saida}",
    },
    "ap.err.noprogs.title": {
        "en": "The device does not have r1send and curl yet.",
        "pt": "O aparelho ainda não tem o r1send e o curl.",
    },
    "ap.err.noprogs.body": {
        "en": "Use “Enable Wi-Fi sending” first.",
        "pt": "Use “Ativar envio pelo WiFi” primeiro.",
    },
    "ap.err.nosk.title": {
        "en": "The device does not have the session key.",
        "pt": "O aparelho não tem a chave de sessão.",
    },
    "ap.err.nosk.body": {
        "en": "Authorise the account and enable Wi-Fi sending.",
        "pt": "Autorize a conta e ative o envio pelo WiFi.",
    },
    "ap.err.nocacert2.body": {
        "en": "Without it there is no way to check the server really is "
              "Last.fm, and the program will not send your key blind. Use the "
              "“Download certificates” button.",
        "pt": "Sem ele não dá para conferir que o servidor é mesmo o Last.fm, "
              "e o programa não manda a sua chave às cegas. Use o botão "
              "“Baixar certificados”.",
    },
    "ap.err.curlfail.title": {
        "en": "The device could not reach Last.fm.",
        "pt": "O aparelho não conseguiu falar com o Last.fm.",
    },
    "ap.err.curlfail.body": {
        "en": "{saida}\n\nIs the R1's Wi-Fi on and connected? It does not "
              "switch the radio on by itself, on purpose.",
        "pt": "{saida}\n\nO WiFi do R1 está ligado e conectado? Ele não liga o "
              "rádio sozinho de propósito.",
    },
    "ap.nothing_pending": {
        "en": "There was nothing pending — everything in the queue had already "
              "gone.",
        "pt": "Não havia nada pendente — tudo o que estava na fila já foi.",
    },
    "ap.err.unconfirmed": {
        "en": "The send was not confirmed.",
        "pt": "O envio não foi confirmado.",
    },
    "ap.boot.already": {
        "en": "init.sh already starts the collector.",
        "pt": "O init.sh já inicia o coletor.",
    },
    "ap.err.init.title": {
        "en": "init.sh became invalid after adding the collector.",
        "pt": "O init.sh ficou inválido depois de acrescentar o coletor.",
    },
    "ap.err.init.body": {
        "en": "Nothing was started. The file is at {caminho}.\n\n{saida}",
        "pt": "Nada foi iniciado. O arquivo está em {caminho}.\n\n{saida}",
    },
    "ap.boot.on_line": {
        "en": "The collector now starts together with the player (inserted "
              "before the `exit` on line {linha}).",
        "pt": "O coletor passa a iniciar junto com o player (inserido antes do "
              "`exit` da linha {linha}).",
    },
    "ap.boot.on": {
        "en": "The collector now starts together with the player.",
        "pt": "O coletor passa a iniciar junto com o player.",
    },
    "ap.boot.off": {
        "en": "The collector no longer starts with the player.",
        "pt": "O coletor não inicia mais junto com o player.",
    },
    "ap.err.died.title": {
        "en": "The collector was started but did not stay running.",
        "pt": "O coletor foi iniciado mas não continuou rodando.",
    },
    "ap.err.died.body": {
        "en": "Last lines of its log on the device:\n{registro}\n\n"
              "You can investigate by hand with:\n  adb shell sh {daemon}",
        "pt": "Últimas linhas do registro dele no aparelho:\n{registro}\n\n"
              "Dá para investigar à mão com:\n  adb shell sh {daemon}",
    },
    "ap.log.empty": {
        "en": "(the log is empty)",
        "pt": "(o registro está vazio)",
    },
    "ap.started": {
        "en": "Collector started and running.",
        "pt": "Coletor iniciado e rodando.",
    },
    "ap.stopped": {
        "en": "Collector stopped.",
        "pt": "Coletor parado.",
    },
    "ap.removed.all": {
        "en": "Collector folder removed, including the queue and the key.",
        "pt": "Pasta do coletor removida, inclusive a fila e a chave.",
    },
    "ap.removed.kept": {
        "en": "Collector removed, and the session key wiped from the device. "
              "The queue is still at {fila}.",
        "pt": "Coletor removido, e a chave de sessão apagada do aparelho. A "
              "fila continua em {fila}.",
    },
    "ap.err.noqueue.title": {
        "en": "There is no queue on the device yet.",
        "pt": "Não há fila no aparelho ainda.",
    },
    "ap.err.noqueue.body": {
        "en": "The file {fila} does not exist. If the collector was just "
              "installed, play a track and try again.",
        "pt": "O arquivo {fila} não existe. Se o coletor acabou de ser "
              "instalado, toque uma música e tente de novo.",
    },
    "ap.err.pull": {
        "en": "I could not fetch the queue from the device.",
        "pt": "Não consegui trazer a fila do aparelho.",
    },
    "ap.queue.pulled": {
        "en": "Queue fetched: {bytes} bytes",
        "pt": "Fila trazida: {bytes} bytes",
    },
    "ap.marked": {
        "en": "{n} play(s) marked as sent on the device.",
        "pt": "{n} execução(ões) marcadas como enviadas no aparelho.",
    },
    "ap.trimmed": {
        "en": "Queue trimmed on the device; a copy was left as fila.tsv.bak.",
        "pt": "Fila enxugada no aparelho; uma cópia ficou em fila.tsv.bak.",
    },

    # ------------------------------------------------------- cliente Last.fm
    "lfm.err.net.title": {
        "en": "I could not reach Last.fm.",
        "pt": "Não consegui falar com o Last.fm.",
    },
    "lfm.err.net.body": {
        "en": "{metodo}: {motivo}\n\nCheck this computer's internet "
              "connection. Nothing was lost: the queue is still stored and you "
              "can send later.",
        "pt": "{metodo}: {motivo}\n\nConfira a conexão da internet deste "
              "computador. Nada foi perdido: a fila continua guardada e você "
              "pode enviar mais tarde.",
    },
    "lfm.err.http": {
        "en": "Last.fm answered HTTP {status} to {metodo}.",
        "pt": "O Last.fm respondeu HTTP {status} a {metodo}.",
    },
    "lfm.err.empty": {
        "en": "(the reply came back empty)",
        "pt": "(a resposta veio vazia)",
    },
    "lfm.err.notjson": {
        "en": "Last.fm answered something that is not JSON to {metodo}.",
        "pt": "O Last.fm respondeu algo que não é JSON a {metodo}.",
    },
    "lfm.err.nosk": {
        "en": "Last.fm did not return the session key.",
        "pt": "O Last.fm não devolveu a chave de sessão.",
    },

    # ------------------------------------------------------------- compilar
    "cc.err.notarget.title": {
        "en": "This Zig cannot produce a static binary for mipsel.",
        "pt": "Este Zig não consegue produzir um binário estático para mipsel.",
    },
    "cc.err.notarget.body": {
        "en": "None of the known targets worked:\n{alvos}\n\nInstall another "
              "Zig version and try again. The 'zig can provide libc for "
              "related target' lines in the log say which targets this version "
              "accepts.",
        "pt": "Nenhum dos alvos conhecidos funcionou:\n{alvos}\n\nInstale "
              "outra versão do Zig e tente de novo. As linhas 'zig can provide "
              "libc for related target' no registro dizem quais alvos esta "
              "versão aceita.",
    },
    "cc.err.badelf": {
        "en": "The binary that came out is not usable on the R1.",
        "pt": "O binário gerado não serve para o R1.",
    },
    "cc.err.nosource": {
        "en": "I could not find {arquivo}.",
        "pt": "Não achei o {arquivo}.",
    },
    "cc.err.nooutput": {
        "en": "Zig finished without an error, but produced no file.",
        "pt": "O Zig terminou sem erro, mas não gerou o arquivo.",
    },
    "cc.err.failed.title": {
        "en": "{rotulo} did not compile.",
        "pt": "O {rotulo} não compilou.",
    },
    "cc.err.failed.body": {
        "en": "{saida}\n\nThe exact command is in this session's log, and can "
              "be repeated by hand.",
        "pt": "{saida}\n\nO comando exato está no registro desta sessão, e "
              "pode ser repetido à mão.",
    },
    "cc.finding_target": {
        "en": "Working out the mipsel target by compiling and linking a test "
              "program that uses libc.",
        "pt": "Descobrindo o alvo mipsel compilando e ligando um programa de "
              "teste que usa a libc.",
    },
    "cc.target_ok": {
        "en": "Target confirmed (compiles and links static): {alvo}",
        "pt": "Alvo confirmado (compila e liga estático): {alvo}",
    },
    "cc.target_no": {
        "en": "Zig does not serve libc for {alvo}; trying the next one.",
        "pt": "O Zig não serve libc para {alvo}; tentando o próximo.",
    },
    "cc.building": {
        "en": "Building {rotulo} for {alvo}",
        "pt": "Compilando o {rotulo} para {alvo}",
    },
    "cc.flags_warn": {
        "en": "The ELF flags are {tem}; the R1's busybox uses {esperado}. It "
              "will probably still run, but here is the warning.",
        "pt": "Os flags do ELF são {tem}; o busybox do R1 usa {esperado}. "
              "Provavelmente roda, mas fica o aviso.",
    },
    "cc.ready": {
        "en": "{rotulo} ready: {tam} bytes, {bits} bits {endian}, {maquina}, "
              "static",
        "pt": "{rotulo} pronto: {tam} bytes, {bits} bits {endian}, {maquina}, "
              "estático",
    },

    # ------------------------------------------------------------ curlbuild
    "cb.err.tools.title": {
        "en": "Missing build tools: {lista}",
        "pt": "Faltam ferramentas de compilação: {lista}",
    },
    "cb.err.tools.body": {
        "en": "Install them with your system's package manager, for "
              "example:\n    sudo apt install make perl",
        "pt": "Instale-as pelo gerenciador de pacotes do seu sistema, por "
              "exemplo:\n    sudo apt install make perl",
    },
    "cb.err.install.title": {
        "en": "I could not install the build tools: {lista}",
        "pt": "Não consegui instalar as ferramentas de compilação: {lista}",
    },
    "cb.err.install.body": {
        "en": "Open WSL and run:\n"
              "    sudo apt update && sudo apt install -y make perl\n\n{saida}",
        "pt": "Abra o WSL e rode:\n"
              "    sudo apt update && sudo apt install -y make perl\n\n{saida}",
    },
    "cb.err.linux.title": {
        "en": "Building curl needs a Linux environment.",
        "pt": "Compilar o curl precisa de um ambiente Linux.",
    },
    "cb.err.linux.body": {
        "en": "On Windows, set up a usable WSL distribution first.",
        "pt": "No Windows, configure uma distribuição WSL utilizável primeiro.",
    },
    "cb.err.zig.title": {
        "en": "zig is not installed in the build environment.",
        "pt": "O zig não está instalado no ambiente de compilação.",
    },
    "cb.err.zig.body": {
        "en": "Get it from https://ziglang.org/download/ .\n"
              "On Windows it has to live inside WSL.",
        "pt": "Baixe em https://ziglang.org/download/ .\n"
              "No Windows, ele precisa estar dentro do WSL.",
    },
    "cb.err.targz": {
        "en": "I could not convert {arquivo} to .tar.gz.",
        "pt": "Não consegui converter {arquivo} para .tar.gz.",
    },
    "cb.err.home.title": {
        "en": "I could not work out the build environment's home directory.",
        "pt": "Não consegui descobrir a pasta pessoal do ambiente de "
              "compilação.",
    },
    "cb.err.home.body": {
        "en": "The 'cd && pwd' probe did not answer.",
        "pt": "A sondagem 'cd && pwd' não respondeu.",
    },
    "cb.step": {
        "en": "Cross-compiling a static curl for the R1",
        "pt": "Compilação cruzada do curl estático para o R1",
    },
    "cb.warn": {
        "en": "This takes 20 to 30 minutes, and happens once only: the binary "
              "is kept and serves the next installs. The sources come from "
              "curl.se and the Mbed-TLS repository, and what comes out still "
              "goes through the ELF check before reaching the device.",
        "pt": "Isto leva de 20 a 30 minutos, e é uma vez só: o binário fica "
              "guardado e serve para as próximas instalações. As fontes vêm de "
              "curl.se e do repositório do Mbed-TLS, e o que sair ainda passa "
              "pela checagem de ELF antes de ir para o aparelho.",
    },
    "cb.script_at": {
        "en": "Script saved at {caminho} — it can be re-run by hand (it "
              "re-downloads the sources if it needs to).",
        "pt": "Script salvo em {caminho} — dá para rodar de novo à mão (ele "
              "rebaixa as fontes se precisar).",
    },
    "cb.log_at": {
        "en": "Full build output saved at {caminho}",
        "pt": "Saída completa da compilação salva em {caminho}",
    },
    "cb.no_artifact": {
        "en": "the build finished but the binary did not show up",
        "pt": "o build terminou mas o binário não apareceu",
    },
    "cb.stage.copy": {
        "en": "copying the artifact",
        "pt": "cópia do artefato",
    },
    "cb.done": {
        "en": "curl built: {caminho}",
        "pt": "curl compilado: {caminho}",
    },
    "cb.done.note": {
        "en": "Target used: {alvo}. Keep the binary — it serves the next "
              "installs and the program remembers where it is.",
        "pt": "Alvo usado: {alvo}. Guarde o binário — ele serve para as "
              "próximas instalações e o programa lembra o caminho.",
    },

    # ------------------------------------------------------------------ rede
    "net.err.403.title": {
        "en": "GitHub refused the request (403).",
        "pt": "O GitHub recusou a requisição (403).",
    },
    "net.err.403.body": {
        "en": "This is normally the anonymous API rate limit (60 per hour per "
              "IP). Wait a few minutes and try again.\nURL: {url}",
        "pt": "Normalmente é limite de requisições anônimas da API (60 por "
              "hora por IP). Espere alguns minutos e tente de novo.\nURL: {url}",
    },
    "net.err.404.title": {
        "en": "File not found on the server (404).",
        "pt": "Arquivo não encontrado no servidor (404).",
    },
    "net.err.http.title": {
        "en": "The server answered {codigo}.",
        "pt": "O servidor respondeu {codigo}.",
    },
    "net.err.tls.title": {
        "en": "Secure connection (TLS) to the server failed.",
        "pt": "Falha na conexão segura (TLS) com o servidor.",
    },
    "net.err.conn.title": {
        "en": "I could not connect. Check your internet.",
        "pt": "Não consegui conectar. Verifique sua internet.",
    },
    "net.err.url_reason": {
        "en": "URL: {url}\n{motivo}",
        "pt": "URL: {url}\n{motivo}",
    },
    "net.err.url": {
        "en": "URL: {url}",
        "pt": "URL: {url}",
    },
    "net.err.generic": {
        "en": "Network error: {erro}",
        "pt": "Erro de rede: {erro}",
    },
    "net.err.toobig": {
        "en": "The server's reply is larger than expected.",
        "pt": "A resposta do servidor é maior do que o esperado.",
    },
    "net.err.badreply.title": {
        "en": "The server returned a reply I did not understand.",
        "pt": "O servidor devolveu uma resposta que não entendi.",
    },
    "net.err.badreply.body": {
        "en": "URL: {url}\n{erro}",
        "pt": "URL: {url}\n{erro}",
    },
    "net.err.size.title": {
        "en": "{nome}: the downloaded size does not match.",
        "pt": "{nome}: o tamanho baixado não confere.",
    },
    "net.err.size.body": {
        "en": "Expected {esperado} bytes, got {obtido}.\nURL: {url}",
        "pt": "Esperado {esperado} bytes, veio {obtido}.\nURL: {url}",
    },
    "net.err.md5.title": {
        "en": "{nome}: the MD5 does not match — the file is not what the "
              "release declares.",
        "pt": "{nome}: o MD5 não confere — o arquivo não é o que a release "
              "declara.",
    },
    "net.err.sha.title": {
        "en": "{nome}: the SHA256 does not match — the file is not what the "
              "release declares.",
        "pt": "{nome}: o SHA256 não confere — o arquivo não é o que a release "
              "declara.",
    },
    "net.err.digest.body": {
        "en": "Expected {esperado}\nGot      {obtido}\nURL: {url}",
        "pt": "Esperado {esperado}\nObtido   {obtido}\nURL: {url}",
    },

    # ------------------------------------------------------------------- zig
    "zs.err.uname.title": {
        "en": "I could not identify the system where Zig will run.",
        "pt": "Não consegui identificar o sistema onde o Zig vai rodar.",
    },
    "zs.err.uname.body": {
        "en": "The 'uname -s; uname -m' probe did not answer.\n{saida}",
        "pt": "A sondagem 'uname -s; uname -m' não respondeu.\n{saida}",
    },
    "zs.err.os.title": {
        "en": "System not supported for Zig: {sistema}",
        "pt": "Sistema não suportado para o Zig: {sistema}",
    },
    "zs.err.os.body": {
        "en": "This program only knows how to download Zig for Linux and "
              "macOS.",
        "pt": "Este programa só sabe baixar Zig para Linux e macOS.",
    },
    "zs.err.arch.title": {
        "en": "Architecture not recognised: {maquina}",
        "pt": "Arquitetura não reconhecida: {maquina}",
    },
    "zs.err.arch.body": {
        "en": "I do not know which Zig build to download for it.",
        "pt": "Não sei qual build do Zig baixar para ela.",
    },
    "zs.err.index": {
        "en": "The Zig version index came in an unexpected format.",
        "pt": "O índice de versões do Zig veio num formato inesperado.",
    },
    "zs.err.norelease.title": {
        "en": "No Zig version available for {alvo}.",
        "pt": "Nenhuma versão do Zig disponível para {alvo}.",
    },
    "zs.err.norelease.body": {
        "en": "The Zig download index had no build for that platform.",
        "pt": "O índice de downloads do Zig não trouxe nenhum build para essa "
              "plataforma.",
    },
    "zs.err.home.wsl": {
        "en": "The WSL distribution did not answer.",
        "pt": "A distribuição do WSL não respondeu.",
    },
    "zs.err.home.plain": {
        "en": "I could not work out the home directory.",
        "pt": "Não consegui descobrir a pasta pessoal.",
    },
    "zs.err.home.body": {
        "en": "I asked what $HOME is and got no answer.\n{saida}",
        "pt": "Perguntei qual é o $HOME e não veio resposta.\n{saida}",
    },
    "zs.err.xz.title": {
        "en": "xz is missing, and Zig needs it to unpack.",
        "pt": "Falta o xz para descompactar o Zig.",
    },
    "zs.err.xz.body": {
        "en": "Install it with your system's package manager (for example: "
              "sudo apt install xz-utils).",
        "pt": "Instale-o pelo gerenciador de pacotes do seu sistema (por "
              "exemplo: sudo apt install xz-utils).",
    },
    "zs.err.linux.title": {
        "en": "Installing Zig needs a Linux environment.",
        "pt": "Instalar o Zig precisa de um ambiente Linux.",
    },
    "zs.err.linux.body": {
        "en": "On Windows, set up a usable WSL distribution first — Zig has to "
              "live inside it, because that is where the builds run.",
        "pt": "No Windows, configure uma distribuição WSL utilizável primeiro "
              "— o Zig tem de ficar dentro dela, porque é lá que as "
              "compilações rodam.",
    },
    "zs.err.unpack.title": {
        "en": "I could not unpack Zig.",
        "pt": "Não consegui descompactar o Zig.",
    },
    "zs.err.unpack.body": {
        "en": "Destination: {onde}\n\n{saida}",
        "pt": "Destino: {onde}\n\n{saida}",
    },
    "zs.err.nobin.title": {
        "en": "Zig was unpacked but I could not find the executable.",
        "pt": "O Zig foi descompactado mas não achei o executável.",
    },
    "zs.err.nobin.body": {
        "en": "I looked for an executable file called 'zig' inside "
              "{onde}.\n\n{saida}",
        "pt": "Procurei um arquivo executável chamado 'zig' dentro de "
              "{onde}.\n\n{saida}",
    },
    "zs.err.norun.title": {
        "en": "Zig was installed but does not run.",
        "pt": "O Zig foi instalado mas não executa.",
    },
    "zs.err.norun.body": {
        "en": "{onde}/zig version failed.\n\n{saida}",
        "pt": "{onde}/zig version falhou.\n\n{saida}",
    },

    # ------------------------------------------------------------------- adb
    "adb.err.unauth.title": {
        "en": "The device showed up, but did not authorise the connection.",
        "pt": "O aparelho apareceu, mas não autorizou a conexão.",
    },
    "adb.err.unauth.body": {
        "en": "Normally that is an authorisation dialog on the screen. The R1 "
              "does not usually show one — unplug it, plug it back in and try "
              "again. If it persists, run 'adb kill-server' and repeat.",
        "pt": "Normalmente isso é um diálogo de autorização na tela. O R1 não "
              "costuma mostrar um — desconecte, reconecte e tente de novo. Se "
              "persistir, rode 'adb kill-server' e repita.",
    },
    "adb.err.offline.title": {
        "en": "The device is listed as offline.",
        "pt": "O aparelho está listado como offline.",
    },
    # "offline" quase nunca é o cabo, no R1. É o aparelho travado: o adb ainda
    # enxerga o gadget USB, mas nada do outro lado responde. Mandar
    # desconectar e reconectar era o conselho errado, e é o primeiro que
    # alguém tenta — várias vezes, antes de desconfiar do aparelho.
    "adb.err.offline.body": {
        "en": "On the R1 this usually means the player itself has locked up, "
              "not that the cable is loose: adb can still see the USB device, "
              "but nothing behind it answers.\n\n"
              "  1. Hold the power button until the screen goes dark (10 s, "
              "or 20-30 s if it does not react), then turn it back on.\n"
              "  2. If it comes back and adb still says offline, run "
              "'adb kill-server' and try again.\n"
              "  3. Only then suspect the cable or the port.\n\n"
              "Nothing in the queue is lost by a hard reset — it lives on the "
              "device's own storage.",
        "pt": "No R1 isto normalmente quer dizer que o próprio player travou, "
              "e não que o cabo está solto: o adb ainda enxerga o dispositivo "
              "USB, mas nada do outro lado responde.\n\n"
              "  1. Segure o botão de ligar até a tela apagar (10 s, ou 20-30 s "
              "se ele não reagir), e ligue de novo.\n"
              "  2. Se voltar e o adb continuar dizendo offline, rode "
              "'adb kill-server' e tente outra vez.\n"
              "  3. Só então desconfie do cabo ou da porta.\n\n"
              "Nada da fila se perde num reset forçado — ela mora na memória "
              "do próprio aparelho.",
    },
    "adb.err.nodevice": {
        "en": "adb found no device.",
        "pt": "Nenhum aparelho encontrado pelo adb.",
    },
    "adb.err.nolocal": {
        "en": "Local file to send was not found.",
        "pt": "Arquivo local não encontrado para enviar.",
    },
    "adb.err.push": {
        "en": "Failed to send {arquivo} to the device.",
        "pt": "Falha ao enviar {arquivo} para o aparelho.",
    },
    # A ordem aqui não é decorativa: o passo do ADB é o que trava quase todo
    # mundo, e é o menos adivinhável. Uma pessoa passou doze minutos presa
    # nele antes de descobrir sozinha que precisava tocar dez vezes em
    # "About" — e o texto antigo só falava do modo USB, que ela já tinha
    # posto certo.
    "adb.usb_help": {
        "en": "Check that:\n"
              "  • ADB is turned on. This is the one that catches everyone: "
              "on the R1, go to System → About and tap it ten times. A "
              "developer/ADB switch appears — turn it on. Setting the USB "
              "mode alone is not enough;\n"
              "  • on the device, System → USB working mode is set to "
              "\"Device\";\n"
              "  • the R1 is on and connected by the cable;\n"
              "  • the cable carries data (many charge-only cables do not).\n\n"
              "Then click check again.",
        "pt": "Confira se:\n"
              "  • o ADB está ligado. Este é o que pega todo mundo: no R1, vá "
              "em System → About e toque dez vezes. Aparece um interruptor de "
              "desenvolvedor/ADB — ligue-o. Só pôr o modo USB não basta;\n"
              "  • no aparelho, System → USB working mode está em "
              "\"Device\";\n"
              "  • o R1 está ligado e conectado pelo cabo;\n"
              "  • o cabo transmite dados (muitos cabos só carregam).\n\n"
              "Depois clique em verificar de novo.",
    },

    # ---------------------------------------------------------------- runner
    "run.err.notfound.title": {
        "en": "Command not found: {cmd}",
        "pt": "Comando não encontrado: {cmd}",
    },
    "run.err.notfound.body": {
        "en": "The system did not find '{cmd}' on the PATH.\nCommand: {linha}",
        "pt": "O sistema não achou '{cmd}' no PATH.\nComando: {linha}",
    },
    "run.err.perm.title": {
        "en": "No permission to run {cmd}.",
        "pt": "Sem permissão para executar {cmd}.",
    },
    "run.err.exec.title": {
        "en": "I could not run {cmd}: {erro}",
        "pt": "Não consegui executar {cmd}: {erro}",
    },
    "run.err.cmd": {
        "en": "Command: {linha}",
        "pt": "Comando: {linha}",
    },
    "run.err.timeout": {
        "en": "The command took too long and was stopped ({segundos}s).",
        "pt": "O comando demorou demais e foi interrompido ({segundos}s).",
    },
    "run.err.code.title": {
        "en": "The command failed (exit code {codigo}).",
        "pt": "O comando falhou (código {codigo}).",
    },
    "run.err.code.body": {
        "en": "Command: {linha}\n\n{saida}",
        "pt": "Comando: {linha}\n\n{saida}",
    },
    "run.err.nowsl.title": {
        "en": "No usable WSL distribution has been set up.",
        "pt": "Nenhuma distribuição WSL utilizável foi configurada.",
    },
    "run.err.nowsl.body": {
        "en": "Building the device programs needs a real Linux. Everything "
              "else — collecting and sending over the cable — works without "
              "it.",
        "pt": "Compilar os programas do aparelho precisa de um Linux de "
              "verdade. Todo o resto — coletar e enviar pelo cabo — funciona "
              "sem ele.",
    },
    "run.err.script.title": {
        "en": "WSL could not read one of this program's helper scripts.",
        "pt": "O WSL não conseguiu ler um script auxiliar deste programa.",
    },
    "run.err.script.body": {
        "en": "Windows: {janela}\nWSL: {posix}\n\nThis is usually Windows "
              "folder redirection. Run the program from an ordinary folder "
              "(for example inside C:\\Users\\<you>\\r1lastfm) and try again.",
        "pt": "Windows: {janela}\nWSL: {posix}\n\nCostuma ser redirecionamento "
              "de pasta do Windows. Rode o programa de uma pasta comum (por "
              "exemplo dentro de C:\\Users\\<você>\\r1lastfm) e tente de novo.",
    },
    "run.err.wslpath.title": {
        "en": "I could not convert the path to the WSL format.",
        "pt": "Não consegui converter o caminho para o formato do WSL.",
    },
    "run.err.wslpath.body": {
        "en": "Path: {caminho}",
        "pt": "Caminho: {caminho}",
    },

    # ------------------------------------------- registro de rede e download
    "net.cache.checking": {
        "en": "{nome}: already in the cache, checking…",
        "pt": "{nome}: já existe em cache, conferindo…",
    },
    "net.cache.ok": {
        "en": "{nome}: cache valid, download skipped ({bytes} bytes, sha256 "
              "{sha}…)",
        "pt": "{nome}: cache válido, download dispensado ({bytes} bytes, "
              "sha256 {sha}…)",
    },
    "net.cache.bad": {
        "en": "{nome}: the cached file does not match the release. Moved to "
              "{arquivo} and downloading again.",
        "pt": "{nome}: o arquivo em cache não bate com a release. Movido para "
              "{arquivo} e baixando de novo.",
    },
    "net.cache.using": {
        "en": "{nome}: using the cached file ({bytes} bytes)",
        "pt": "{nome}: usando o arquivo em cache ({bytes} bytes)",
    },
    "net.downloading": {
        "en": "Downloading {nome}",
        "pt": "Baixando {nome}",
    },
    "net.speed": {
        "en": "{nome}: {bytes} bytes in {segundos}s ({taxa} MB/s)",
        "pt": "{nome}: {bytes} bytes em {segundos}s ({taxa} MB/s)",
    },
    "net.downloaded": {
        "en": "{nome}: downloaded and verified",
        "pt": "{nome}: baixado e conferido",
    },

    # --------------------------------------------------- registro do zig etc
    "zs.target": {
        "en": "Zig will be installed for {alvo} (where the builds run).",
        "pt": "O Zig será instalado para {alvo} (onde as compilações rodam).",
    },
    "zs.asking": {
        "en": "Asking ziglang.org which versions exist",
        "pt": "Consultando as versões do Zig em ziglang.org",
    },
    "zs.no_sha": {
        "en": "Zig {versao}: no SHA256 in the index; skipping that version.",
        "pt": "Zig {versao}: sem SHA256 no índice; ignorando essa versão.",
    },
    "zs.found": {
        "en": "{n} Zig versions available (newest: {recente}).",
        "pt": "{n} versões do Zig disponíveis (mais recente: {recente}).",
    },
    "zs.already": {
        "en": "Zig {versao} already installed at {onde}",
        "pt": "Zig {versao} já instalado em {onde}",
    },
    "zs.installing_xz": {
        "en": "xz is not installed in the distribution; installing it as root.",
        "pt": "O xz não está instalado na distribuição; instalando como root.",
    },
    "zs.installing": {
        "en": "Installing Zig {versao} ({alvo})",
        "pt": "Instalando o Zig {versao} ({alvo})",
    },
    "zs.sha_note": {
        "en": "The SHA256 below is the one ziglang.org publishes next to the "
              "tarball; the download is refused if it does not match.",
        "pt": "O SHA256 abaixo é o publicado pelo próprio ziglang.org junto do "
              "tarball; o download é recusado se não bater.",
    },
    "zs.copying": {
        "en": "Copying the tarball into WSL",
        "pt": "Copiando o tarball para dentro do WSL",
    },
    "zs.unpacking": {
        "en": "Unpacking (about 50 MB compressed, this can take a minute)",
        "pt": "Descompactando (uns 50 MB comprimidos, pode levar um minuto)",
    },
    "zs.done": {
        "en": "Zig {versao} installed at {onde}",
        "pt": "Zig {versao} instalado em {onde}",
    },
    "zs.odd_path": {
        "en": "Unexpected path; I am not deleting anything.",
        "pt": "Caminho inesperado; não vou apagar nada.",
    },
    "zs.removing": {
        "en": "Removing the Zig this program installed",
        "pt": "Removendo o Zig instalado por este programa",
    },
    "zs.removed": {
        "en": "Removed.",
        "pt": "Removido.",
    },
    "adb.rebooting": {
        "en": "Flushing to disk and rebooting the device",
        "pt": "Gravando em disco e reiniciando o aparelho",
    },
    "adb.reboot_sent": {
        "en": "Reboot command sent. The R1 comes back in ~30 seconds.",
        "pt": "Comando de reinício enviado. O R1 volta em ~30 segundos.",
    },
    "cb.tools_missing": {
        "en": "Build tools missing from the environment: {lista}.",
        "pt": "Faltam ferramentas de compilação no ambiente: {lista}.",
    },
    "cb.tools_installing": {
        "en": "Installing as the distribution's root — no password needed.",
        "pt": "Instalando como root da distribuição — não pede senha.",
    },
    "cb.tools_ok": {
        "en": "Build tools installed.",
        "pt": "Ferramentas de compilação instaladas.",
    },
    "cb.targz_cached": {
        "en": "{arquivo}: a .tar.gz version is already in the cache.",
        "pt": "{arquivo}: já existe uma versão .tar.gz em cache.",
    },
    "cb.converting": {
        "en": "The build environment cannot open {sufixo}. Converting "
              "{arquivo} to .tar.gz right here, with Python's standard library "
              "— nothing needs installing.",
        "pt": "O ambiente de compilação não sabe abrir {sufixo}. Convertendo "
              "{arquivo} para .tar.gz aqui mesmo, com a biblioteca padrão do "
              "Python — nada precisa ser instalado.",
    },
    "cb.converted": {
        "en": "Converted: {arquivo} ({bytes} bytes)",
        "pt": "Convertido: {arquivo} ({bytes} bytes)",
    },
    "cb.crlf_warn": {
        "en": "I could not normalise the scripts' line endings; if the build "
              "complains about 'Illegal option', that is why.",
        "pt": "Não consegui normalizar os fins de linha dos scripts; se a "
              "compilação reclamar de 'Illegal option', é isso.",
    },
    "cb.crlf_fixed": {
        "en": "CRLF line endings fixed in {arquivo}",
        "pt": "Fim de linha CRLF corrigido em {arquivo}",
    },
    "cb.hint.bz2": {
        "en": "tar could not find a .bz2 decompressor. This program converts "
              "the file to .tar.gz by itself — if you are seeing this, the "
              "conversion did not happen; run it again.",
        "pt": "O tar não achou um descompactador de .bz2. Este programa "
              "converte o arquivo para .tar.gz sozinho — se você viu isto, a "
              "conversão não aconteceu; rode de novo.",
    },
    "cb.hint.staticlib": {
        "en": "The linker could not find a static library. Check that the "
              "mbedtls step finished and produced the .a files in prefix/lib.",
        "pt": "O linker não achou uma biblioteca estática. Confira se a etapa "
              "do mbedtls terminou e gerou os .a em prefix/lib.",
    },
    "cb.hint.nocc": {
        "en": "curl's configure could not create a test executable. Look in "
              "config.log for the compiler line — the real reason is there, "
              "and autoconf hides it behind that generic message. If it says "
              "'unable to provide libc', the Zig target is wrong; if it says "
              "something else, try another Zig version.",
        "pt": "O configure do curl não conseguiu criar um executável de teste. "
              "Procure no config.log a linha do compilador — o motivo real "
              "está lá, e o autoconf o esconde atrás dessa mensagem genérica. "
              "Se for 'unable to provide libc', o alvo do Zig está errado; se "
              "for outra coisa, tente outra versão do Zig.",
    },
    "cb.hint.target": {
        "en": "This Zig does not accept the mipsel/musl target. Install "
              "another Zig version.",
        "pt": "Este Zig não aceita o alvo mipsel/musl. Instale outra versão do "
              "Zig.",
    },
    "cb.hint.libpsl": {
        "en": "--without-libpsl is missing from configure (it should already "
              "be there).",
        "pt": "Falta --without-libpsl no configure (deveria já estar lá).",
    },
    "cb.hint.tool": {
        "en": "{ferramenta} is missing from the build environment. This "
              "program installs make and perl by itself; for the rest, inside "
              "WSL:\n    sudo apt install -y {ferramenta}",
        "pt": "Falta o {ferramenta} no ambiente de compilação. Este programa "
              "tenta instalar make e perl sozinho; para o resto, dentro do "
              "WSL:\n    sudo apt install -y {ferramenta}",
    },
    "cb.hint.autotools": {
        "en": "The tarball asked for autotools. Use the official tarball from "
              "curl.se, not a git snapshot.",
        "pt": "O tarball pediu autotools. Use o tarball oficial de curl.se, "
              "não um snapshot do git.",
    },
    "cb.hint.unknown": {
        "en": "No known pattern. The full log is saved; so is the script, and "
              "it re-downloads the sources if you want to run it by hand.",
        "pt": "Sem um padrão conhecido. O log completo está salvo; o script "
              "também, e ele rebaixa as fontes se você quiser rodá-lo à mão.",
    },
    "zs.where_note": {
        "en": "It lives only in that folder: to uninstall, delete it. No "
              "system package was touched.",
        "pt": "Ele fica só nessa pasta: para desinstalar, apague-a. Nenhum "
              "pacote do sistema foi alterado.",
    },

    # ------------------------------------------------- adb: falhas de envio
    "adb.push.readonly": {
        "en": "{pasta} is read-only. The only writable destinations are "
              "/usr/data and the card at /data/mnt/sd_0.",
        "pt": "{pasta} é somente leitura. Os únicos destinos graváveis são "
              "/usr/data e o cartão em /data/mnt/sd_0.",
    },
    "adb.push.nospace": {
        "en": "Out of space. The R1's internal partition runs nearly full "
              "because the music database is rebuilt at every boot.",
        "pt": "Acabou o espaço. A partição interna do R1 vive quase cheia "
              "porque o banco de dados de música é reconstruído a cada boot.",
    },
    "adb.push.nodir": {
        "en": "The destination folder does not exist. Is the card inserted and "
              "mounted at /data/mnt/sd_0?",
        "pt": "A pasta de destino não existe. O cartão está inserido e montado "
              "em /data/mnt/sd_0?",
    },
    "run.cancelled": {
        "en": "Operation cancelled.",
        "pt": "Operação cancelada.",
    },
    "run.warn.invisible": {
        "en": "WSL cannot see {caminho}, nor the folder above it. If the next "
              "command fails, that is why.",
        "pt": "O WSL não enxerga {caminho} nem a pasta acima dele. Se o "
              "próximo comando falhar, é isso.",
    },

    # -------------------------------------------- Last.fm: codigos de erro
    "lfm.code.2": {
        "en": "the service did not accept that operation",
        "pt": "o serviço não aceitou essa operação",
    },
    "lfm.code.3": {
        "en": "no such method in the API",
        "pt": "método inexistente na API",
    },
    "lfm.code.4": {
        "en": "that operation is not allowed with this key",
        "pt": "essa operação não é permitida com esta chave",
    },
    "lfm.code.5": {
        "en": "unsupported response format",
        "pt": "formato de resposta não suportado",
    },
    "lfm.code.6": {
        "en": "a required parameter was missing, or came in wrong",
        "pt": "faltou um parâmetro obrigatório, ou ele veio errado",
    },
    "lfm.code.7": {
        "en": "invalid resource identifier",
        "pt": "identificador de recurso inválido",
    },
    "lfm.code.8": {
        "en": "the operation failed on Last.fm's server; worth retrying",
        "pt": "a operação falhou no servidor do Last.fm; vale tentar de novo",
    },
    "lfm.code.9": {
        "en": "the session expired or was revoked — you need to authorise again",
        "pt": "a sessão expirou ou foi revogada — é preciso autenticar de novo",
    },
    "lfm.code.10": {
        "en": "the API key is invalid",
        "pt": "a chave de API é inválida",
    },
    "lfm.code.11": {
        "en": "the service is temporarily down",
        "pt": "o serviço está fora do ar temporariamente",
    },
    "lfm.code.13": {
        "en": "the request signature does not match",
        "pt": "a assinatura do pedido não confere",
    },
    "lfm.code.14": {
        "en": "the token was not authorised — it still needs approving in the "
              "browser",
        "pt": "o token não foi autorizado — falta aprovar no navegador",
    },
    "lfm.code.16": {
        "en": "the service is unavailable right now; try again shortly",
        "pt": "o serviço está indisponível no momento; tente daqui a pouco",
    },
    "lfm.code.17": {
        "en": "the user needs to allow scrobbling in their account settings",
        "pt": "o usuário precisa liberar o scrobble nas configurações da conta",
    },
    "lfm.code.26": {
        "en": "the API key has been suspended",
        "pt": "a chave de API foi suspensa",
    },
    "lfm.code.29": {
        "en": "request limit exceeded; wait a little",
        "pt": "limite de pedidos excedido; espere um pouco",
    },
    "lfm.code.unknown": {
        "en": "unknown error",
        "pt": "erro desconhecido",
    },
    "lfm.detail": {
        "en": "method: {metodo}\ncode {codigo}: {mensagem}",
        "pt": "método: {metodo}\ncódigo {codigo}: {mensagem}",
    },
    "lfm.retry": {
        "en": "{metodo}: {mensagem} — retrying in {segundos}s "
              "({tentativa}/{total})",
        "pt": "{metodo}: {mensagem} — tentando de novo em {segundos}s "
              "({tentativa}/{total})",
    },
    "lfm.ignore.1": {
        "en": "artist ignored by Last.fm",
        "pt": "artista ignorado pelo Last.fm",
    },
    "lfm.ignore.2": {
        "en": "track ignored by Last.fm",
        "pt": "título ignorado pelo Last.fm",
    },
    "lfm.ignore.3": {
        "en": "timestamp too old (Last.fm refuses more than 14 days back)",
        "pt": "hora antiga demais (o Last.fm recusa mais de 14 dias atrás)",
    },
    "lfm.ignore.4": {
        "en": "timestamp in the future",
        "pt": "hora no futuro",
    },
    "lfm.ignore.5": {
        "en": "daily scrobble limit reached",
        "pt": "limite diário de scrobbles atingido",
    },
    "lfm.ignore.other": {
        "en": "refused (code {codigo})",
        "pt": "recusada (código {codigo})",
    },
    "lfm.unconfirmed": {
        "en": "Last.fm did not confirm this track",
        "pt": "o Last.fm não confirmou esta faixa",
    },
    "lfm.partial": {
        "en": "Last.fm confirmed {confirmadas} of {total} tracks in the batch",
        "pt": "o Last.fm confirmou {confirmadas} de {total} faixas do lote",
    },

    # ------------------------------------------- por que uma faixa fica fora
    "play.no_artist": {
        "en": "no artist or no title",
        "pt": "sem artista ou sem título",
    },
    "play.no_time": {
        "en": "no start time",
        "pt": "sem hora de início",
    },
    "play.too_short": {
        "en": "track too short ({segundos}s, minimum {minimo}s)",
        "pt": "faixa curta demais ({segundos}s, mínimo {minimo}s)",
    },
    "play.too_little": {
        "en": "heard for {ouviu}s of {total}s (needed {precisa}s)",
        "pt": "ouvida por {ouviu}s de {total}s (precisava de {precisa}s)",
    },
    # O player tem uma opção que move o banco de músicas dele para o cartão
    # (`tf_music_db_enable`, na tela do aparelho). Com ela ligada, o banco da
    # memória interna para de ser atualizado. O coletor segue os dois, mas
    # dizer qual está em uso poupa a próxima pessoa de horas de "está rodando
    # e não coleta nada".
    "dev.db.card": {
        "en": "The player is keeping its music database on the memory card.",
        "pt": "O player está guardando o banco de músicas dele no cartão.",
    },
    "fila.playing": {
        "en": "still playing — it goes up on its own when it ends",
        "pt": "ainda tocando — ela sobe sozinha quando terminar",
    },
    "fila.last_of_session": {
        "en": "last of the session: there is no way to know how much played",
        "pt": "última da sessão: não dá para saber quanto tocou",
    },
    "fila.bad_clock": {
        "en": "recorded with the device's clock wrong",
        "pt": "gravada com o relógio do aparelho errado",
    },
    "fila.future": {
        "en": "timestamp in the future",
        "pt": "hora no futuro",
    },
    "fila.too_old": {
        "en": "played {dias} days ago; Last.fm only accepts {limite}",
        "pt": "tocada há {dias} dias; o Last.fm só aceita {limite}",
    },
    "fila.ready": {
        "en": "{n} play(s) ready to send",
        "pt": "{n} execução(ões) prontas para enviar",
    },
    "fila.left_out": {
        "en": "{n} left out",
        "pt": "{n} deixadas de fora",
    },
    # "4 reboot(s) in the queue" nao dizia nada a ninguem — perguntaram o que
    # significava, com razao. O numero e util (cada corte e um ponto em que o
    # tempo ouvido nao pode ser deduzido por cima), mas so se vier explicado.
    "fila.reboots": {
        "en": "the player was restarted {n} time(s) while this queue was "
              "being recorded — listening time is measured separately on each "
              "side of a restart, never across one",
        "pt": "o player foi reiniciado {n} vez(es) enquanto esta fila era "
              "gravada — o tempo ouvido é medido em separado de cada lado de "
              "um reinício, nunca por cima dele",
    },
    "fila.clock_warn": {
        "en": "WARNING: part of the queue was recorded with the clock wrong",
        "pt": "ATENÇÃO: parte da fila foi gravada com o relógio errado",
    },
    "fila.bad_lines": {
        "en": "{n} unreadable line(s)",
        "pt": "{n} linha(s) ilegíveis",
    },

    # ------------------------------------------------- veredito sobre o ELF
    "elf.not_elf": {
        "en": "Not an ELF file.",
        "pt": "Não é um arquivo ELF.",
    },
    "elf.link.unknown": {
        "en": "linkage not analysed (I only parse 32-bit headers)",
        "pt": "ligação não analisada (só analiso cabeçalhos de 32 bits)",
    },
    "elf.link.library": {
        "en": "shared library ({soname})",
        "pt": "biblioteca compartilhada ({soname})",
    },
    "elf.link.static": {
        "en": "static",
        "pt": "estático",
    },
    "elf.link.dynamic": {
        "en": "dynamic (interpreter {interp})",
        "pt": "dinâmico (interpretador {interp})",
    },
    "elf.interp.unnamed": {
        "en": "not stated",
        "pt": "não informado",
    },
    "elf.interp.unknown": {
        "en": "(unknown)",
        "pt": "(desconhecido)",
    },
    "elf.libs.used": {
        "en": "libraries used",
        "pt": "bibliotecas usadas",
    },
    "elf.libs.needed": {
        "en": "libraries required",
        "pt": "bibliotecas exigidas",
    },
    "elf.libs.count": {
        "en": "<{n} library/libraries>",
        "pt": "<{n} biblioteca(s)>",
    },
    "elf.err.read": {
        "en": "I could not read the file: {erro}",
        "pt": "não consegui ler o arquivo: {erro}",
    },
    "elf.err.signature": {
        "en": "The file does not start with the ELF signature (\\x7fELF). "
              "This is not a Linux executable.",
        "pt": "O arquivo não começa com a assinatura ELF (\\x7fELF). Isso não "
              "é um executável Linux.",
    },
    "elf.endian.unknown": {
        "en": "unknown",
        "pt": "desconhecido",
    },
    "elf.err.bits": {
        "en": "It is {bits} bits. The R1 needs a 32-bit binary.",
        "pt": "É {bits} bits. O R1 precisa de um binário de 32 bits.",
    },
    "elf.err.endian": {
        "en": "It is big-endian. The R1 is mipsel — MIPS little-endian. "
              "Generic 'mips' binaries are usually big-endian; look for "
              "'mipsel' or 'mipsle'.",
        "pt": "É big-endian. O R1 é mipsel — MIPS little-endian. Binários "
              "'mips' genéricos costumam ser big-endian; procure 'mipsel' ou "
              "'mipsle'.",
    },
    "elf.err.truncated": {
        "en": "truncated ELF header",
        "pt": "cabeçalho ELF truncado",
    },
    "elf.machine.unknown": {
        "en": "unknown machine ({numero})",
        "pt": "máquina desconhecida ({numero})",
    },
    "elf.err.machine": {
        "en": "The architecture is {maquina}, and the R1 needs MIPS.",
        "pt": "A arquitetura é {maquina}, e o R1 precisa de MIPS.",
    },
    "elf.note.abi": {
        "en": "The ABI is not marked O32. It usually works anyway, but check "
              "that the binary was built for MIPS32.",
        "pt": "A ABI não está marcada como O32. Costuma funcionar mesmo assim, "
              "mas confira se o binário foi feito para MIPS32.",
    },
    "elf.note.library": {
        "en": "It is a shared library rather than a program.",
        "pt": "É uma biblioteca compartilhada, e não um programa.",
    },
    "elf.err.dynamic": {
        "en": "The binary is dynamic: it needs the interpreter {interp} and "
              "the system libraries. The R1 does not have those libraries in "
              "the right version. Use a static build.",
        "pt": "O binário é dinâmico: ele exige o interpretador {interp} e "
              "bibliotecas do sistema. O R1 não tem essas bibliotecas na "
              "versão certa. Use uma build estática (static).",
    },
    "elf.err.needs": {
        "en": "The binary depends on external libraries: {libs}",
        "pt": "O binário depende de bibliotecas externas: {libs}",
    },
    "elf.err.etype": {
        "en": "The ELF type is {tipo}; I expected an executable.",
        "pt": "O tipo ELF é {tipo}; esperava um executável.",
    },
    "elf.note.pie": {
        "en": "It is a static PIE executable — usually works.",
        "pt": "É um executável estático PIE — costuma funcionar.",
    },
    "elf.note.small": {
        "en": "The file is only {bytes} bytes. A static curl with TLS is "
              "usually over 1 MB. Check that TLS is included.",
        "pt": "O arquivo tem só {bytes} bytes. Um curl estático com TLS "
              "costuma passar de 1 MB. Confirme que o TLS está incluído.",
    },
    "elf.ok.library": {
        "en": "Valid: MIPS 32-bit little-endian shared library.",
        "pt": "Válido: biblioteca compartilhada MIPS 32 bits little-endian.",
    },
    "elf.ok.program": {
        "en": "Valid: MIPS 32-bit little-endian, static.",
        "pt": "Válido: MIPS 32 bits little-endian, estático.",
    },
    "elf.note.prefix": {
        "en": "Note: ",
        "pt": "Observação: ",
    },
    "elf.refused": {
        "en": "Refused.",
        "pt": "Recusado.",
    },
    "elf.err.is_library": {
        "en": "This file is a shared library ({soname}), not a program. curl "
              "has to be an executable.",
        "pt": "Este arquivo é uma biblioteca compartilhada ({soname}), não um "
              "programa. O curl tem de ser um executável.",
    },
}
