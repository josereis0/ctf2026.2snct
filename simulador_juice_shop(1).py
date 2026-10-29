#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIMULADOR "SUCO SHOP" + CTF — Oficina Elas Hackeiam (23ª SNCT · UABJ/UFRPE)
==========================================================================
Uma lojinha de sucos FALSA, feita com falhas de propósito.

ENCONTRO 1 — as 3 missões dos slides (endereço: http://localhost:3000)
  Missão 1 — achar o placar escondido   (#/score-board)
  Missão 2 — entrar como admin          (admin@juice-sh.op / admin123)
  Missão 3 — abrir a área restrita      (#/administration)
  Bônus    — ver a cesta de outra pessoa (trocar o "bid" no F12)

ENCONTRO 2 — CTF em equipes, no estilo CTFd (endereço: http://localhost:3000/ctf)
  /ctf              página das equipes (cadastro, desafios, envio de flags)
  /ctf/telao        ranking ao vivo para projetar
  /ctf/professora   painel da professora (iniciar, congelar, encerrar, resolução)
  /ctf/resolucao    resolução comentada (liberada pela professora no fim)

COMO USAR (só precisa do Python 3, nada mais):
  1. Dê dois cliques neste arquivo — ou, no terminal:  python simulador_juice_shop.py
  2. O navegador abre sozinho. A janela preta mostra os endereços e a SENHA DO PAINEL.
  3. Os outros computadores do laboratório usam o endereço "Outros computadores".
  4. Para desligar: feche a janela preta (ou Ctrl+C).
  O placar do CTF fica salvo no arquivo "ctf_progresso.json", ao lado deste arquivo.

Tudo é inventado e roda só neste computador/rede do laboratório.
Nenhum site real é acessado.
"""

import base64
import html
import json
import random
import re
import secrets
import socket
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

PORTA = 3000
PASTA = Path(__file__).resolve().parent
ARQUIVO_CTF = PASTA / "ctf_progresso.json"

# ============================================================== DADOS DA LOJA
USUARIOS = [
    {"id": 1, "email": "admin@juice-sh.op", "senha": "admin123", "papel": "admin", "bid": 1},
    {"id": 2, "email": "ana.lima@suco-shop.br", "senha": "Girassol-Trem-Cafe-Azul", "papel": "cliente", "bid": 2},
    {"id": 3, "email": "bia.souza@suco-shop.br", "senha": "Lua-Cadeira-Rio-Verde", "papel": "cliente", "bid": 3},
    {"id": 4, "email": "carla.melo@suco-shop.br", "senha": "Pipoca-Nuvem-Sino-Mar", "papel": "cliente", "bid": 4},
    # CTF: senha descoberta por OSINT (página "Sobre nós")
    {"id": 5, "email": "duda@suco-shop.br", "senha": "pipoca2009", "papel": "atendente", "bid": 5,
     "recado": "Recado da gerência para Duda: SNCT{osint_revela_senhas}"},
]

PRODUTOS = [
    {"id": 1, "nome": "Suco de Maçã (1000 ml)", "preco": 1.99, "emoji": "🍎"},
    {"id": 2, "nome": "Suco de Laranja (1000 ml)", "preco": 2.99, "emoji": "🍊"},
    {"id": 3, "nome": "Suco de Banana (1000 ml)", "preco": 1.99, "emoji": "🍌"},
    {"id": 4, "nome": "Vitamina de Morango", "preco": 3.49, "emoji": "🍓"},
    {"id": 5, "nome": "Suco de Uva Integral", "preco": 4.99, "emoji": "🍇",
     # CTF: nota interna em base64 que a vitrine não mostra
     "nota_interna": base64.b64encode(b"SNCT{base64_nao_e_segredo}").decode()},
    {"id": 6, "nome": "Água de Coco", "preco": 2.49, "emoji": "🥥"},
    {"id": 7, "nome": "Suco Verde Detox", "preco": 3.99, "emoji": "🥬"},
    {"id": 8, "nome": "Limonada Suíça", "preco": 2.79, "emoji": "🍋"},
]

AVALIACOES = {
    1: [{"autor": "admin@juice-sh.op", "texto": "Um dos meus favoritos! Recomendo muito."},
        {"autor": "ana.lima@suco-shop.br", "texto": "Gostoso, mas podia ser mais gelado."}],
    2: [{"autor": "bia.souza@suco-shop.br", "texto": "Laranja de verdade, sem açúcar. Amei!"}],
    3: [{"autor": "carla.melo@suco-shop.br", "texto": "Perfeito depois da academia."}],
    4: [{"autor": "admin@juice-sh.op", "texto": "Novidade da loja! Provem!"}],
    5: [], 6: [{"autor": "ana.lima@suco-shop.br", "texto": "Refrescante."}], 7: [], 8: [],
}

CESTAS = {
    1: [{"produto": "Suco de Maçã (1000 ml)", "qtd": 2}],
    2: [{"produto": "Água de Coco", "qtd": 3}, {"produto": "Limonada Suíça", "qtd": 1}],
    3: [{"produto": "Suco de Laranja (1000 ml)", "qtd": 1}, {"produto": "Vitamina de Morango", "qtd": 2}],
    4: [{"produto": "Suco Verde Detox", "qtd": 5}],
    5: [{"produto": "Suco de Banana (1000 ml)", "qtd": 1}],
}


def cifra_cesar(texto, passo=3):
    saida = []
    for ch in texto:
        if "a" <= ch <= "z":
            saida.append(chr((ord(ch) - 97 + passo) % 26 + 97))
        elif "A" <= ch <= "Z":
            saida.append(chr((ord(ch) - 65 + passo) % 26 + 65))
        else:
            saida.append(ch)
    return "".join(saida)


BILHETE_CIFRADO = cifra_cesar("SNCT{cesar_anda_tres_casas}")

# Pedidos para o desafio "Rastrear pedido" (o servidor não confere de quem é)
PEDIDOS = {}
_status = ["Entregue", "Saiu para entrega", "Em separação", "Entregue", "Aguardando pagamento", "Entregue"]
_clientes = ["A***a L.", "B***a S.", "Você", "C***a M.", "R***o T.", "J***a P.", "P***a G.", "M***s V.",
             "L***a F.", "T***s R.", "D***a F.", "S***a C."]
for _n in range(1, 13):
    PEDIDOS[_n] = {"pedido": _n, "cliente": _clientes[_n - 1], "status": _status[_n % len(_status)],
                   "itens": random.Random(_n).randint(1, 5), "observacao": ""}
PEDIDOS[3]["observacao"] = "Este é o seu pedido. Obrigada pela compra!"
PEDIDOS[7]["observacao"] = "Entregar na portaria. Senha do interfone: SNCT{idor_pedido_alheio}"

# ============================================================== PÁGINAS DA LOJA
INDEX_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Suco Shop — simulador da oficina</title>
<link rel="stylesheet" href="/style.css">
</head>
<body>
<!-- Nota da equipe de desenvolvimento: lembrar de apagar antes de publicar!
     SNCT{codigo_fonte_conta_segredos} -->
<header>
  <a href="#/" class="logo">🧃 Suco Shop <small>simulador</small></a>
  <nav>
    <a href="#/">Início</a>
    <a href="#/sobre">Sobre nós</a>
    <a href="#/rastrear">Rastrear pedido</a>
    <a href="#/login" id="link-conta">Conta</a>
    <a href="#/basket">Cesta</a>
  </nav>
</header>
<div id="avisos"></div>
<main id="app"></main>
<div id="modal" class="escondido"></div>
<footer>Loja FALSA para treino de segurança · Oficina Elas Hackeiam · 23ª SNCT UABJ/UFRPE</footer>
<script src="/main.js"></script>
</body>
</html>
"""

STYLE_CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:#303030;color:#eee}
header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;background:#546e7a;padding:12px 24px}
header a{color:#fff;text-decoration:none;margin-left:20px;font-weight:600}
.logo{font-size:22px;margin-left:0!important}.logo small{font-size:12px;opacity:.7}
main{max-width:1100px;margin:24px auto;padding:0 16px;min-height:70vh}
footer{text-align:center;font-size:12px;opacity:.6;padding:16px}
h1{font-weight:500}
.grade{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px}
.card{background:#424242;border-radius:8px;padding:16px;text-align:center;cursor:pointer;transition:.15s}
.card:hover{transform:translateY(-3px);background:#4d4d4d}
.emoji{font-size:64px}.preco{color:#ffb74d;font-weight:700}
.caixa{background:#424242;border-radius:8px;padding:24px;max-width:520px;margin:auto}
label{display:block;margin-top:12px;font-size:14px}
input{width:100%;padding:10px;margin-top:4px;border-radius:4px;border:1px solid #777;background:#333;color:#fff;font-size:16px}
button{margin-top:16px;padding:10px 20px;border:0;border-radius:4px;background:#64b5f6;color:#000;font-weight:700;cursor:pointer;font-size:15px}
.erro{color:#ff8a80;margin-top:12px}
.recado{background:#1565c0;padding:12px;border-radius:6px;margin-top:12px}
table{width:100%;border-collapse:collapse;background:#424242;border-radius:8px;overflow:hidden}
th,td{padding:10px;border-bottom:1px solid #555;text-align:left}
th{background:#37474f}
.ok{color:#69f0ae;font-weight:700}.pendente{color:#bbb}
.estrelas{color:#ffd54f}
#avisos{position:sticky;top:0;z-index:10}
.aviso{background:#2e7d32;color:#fff;padding:14px 24px;display:flex;justify-content:space-between;align-items:center;font-size:16px;border-bottom:1px solid #1b5e20}
.aviso button{margin:0;background:#1b5e20;color:#fff}
#modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center}
#modal.escondido{display:none}
.janela{background:#424242;border-radius:8px;padding:24px;max-width:520px;width:90%}
.review{border-top:1px solid #555;padding:8px 0;font-size:14px}.review b{color:#90caf9}
.negado{background:#b71c1c;padding:24px;border-radius:8px}
.equipe{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px}
.pessoa{background:#424242;border-radius:8px;padding:16px}.pessoa .emoji{font-size:48px}
"""

# O main.js fica num arquivo separado de propósito: as alunas vão abrir
# F12 -> Fontes -> main.js e procurar "score" e "admin".
MAIN_JS = r"""
// ===== Suco Shop — código do navegador =====
// Mapa de TODAS as páginas da loja (até as que não têm botão no menu!)
const rotas = {
  '':               paginaInicio,
  'sobre':          paginaSobre,
  'rastrear':       paginaRastrear,
  'login':          paginaLogin,
  'basket':         paginaCesta,
  'score-board':    paginaPlacar,     // placar de desafios (escondido do menu)
  'administration': paginaAdmin       // área do administrador (escondida do menu)
};

const DESAFIOS = [
  {id:'placar', nome:'Placar escondido', estrelas:1, dica:'Ache a página que não aparece no menu.'},
  {id:'senha',  nome:'Senha do admin',   estrelas:2, dica:'Entre na conta do administrador.'},
  {id:'admin',  nome:'Área restrita',    estrelas:2, dica:'Abra a página de administração.'},
  {id:'cesta',  nome:'Cesta de outra pessoa (bônus)', estrelas:2, dica:'Veja a cesta de outro cliente.'}
];

function resolvidos(){ try{return JSON.parse(localStorage.getItem('desafios')||'[]')}catch(e){return []} }
function resolver(id){
  const r = resolvidos();
  if (r.includes(id)) return;
  r.push(id); localStorage.setItem('desafios', JSON.stringify(r));
  const d = DESAFIOS.find(x=>x.id===id);
  const div = document.createElement('div');
  div.className = 'aviso';
  div.innerHTML = '<span>🎉 Você resolveu um desafio: <b></b></span><button>OK</button>';
  div.querySelector('b').textContent = d.nome;
  div.querySelector('button').onclick = () => div.remove();
  document.getElementById('avisos').appendChild(div);
}
function usuario(){ try{return JSON.parse(localStorage.getItem('usuario')||'null')}catch(e){return null} }
const app = () => document.getElementById('app');
function el(tag, txt){ const e=document.createElement(tag); if(txt!==undefined) e.textContent=txt; return e; }

async function paginaInicio(){
  app().innerHTML = '<h1>Todos os produtos</h1><div class="grade" id="grade"></div>';
  const resp = await fetch('/rest/products');
  const produtos = await resp.json();
  for (const p of produtos){
    const c = el('div'); c.className='card';
    c.innerHTML = '<div class="emoji"></div><div class="nome"></div><div class="preco"></div>';
    c.querySelector('.emoji').textContent = p.emoji;
    c.querySelector('.nome').textContent = p.nome;
    c.querySelector('.preco').textContent = 'R$ ' + p.preco.toFixed(2).replace('.',',');
    c.onclick = () => abrirProduto(p);
    document.getElementById('grade').appendChild(c);
  }
}

async function abrirProduto(p){
  const resp = await fetch('/rest/products/' + p.id + '/reviews');
  const avaliacoes = await resp.json();
  const m = document.getElementById('modal');
  m.innerHTML = '<div class="janela"><div class="emoji"></div><h2></h2><h3>Avaliações</h3><div id="revs"></div><button id="fechar">Fechar</button></div>';
  m.querySelector('.emoji').textContent = p.emoji;
  m.querySelector('h2').textContent = p.nome;
  const revs = m.querySelector('#revs');
  if (!avaliacoes.length) revs.appendChild(el('p','Ainda sem avaliações.'));
  for (const a of avaliacoes){
    const r = el('div'); r.className='review';
    r.appendChild(el('b', a.autor)); r.appendChild(el('div', a.texto));
    revs.appendChild(r);
  }
  m.querySelector('#fechar').onclick = () => m.classList.add('escondido');
  m.onclick = (e) => { if (e.target===m) m.classList.add('escondido'); };
  m.classList.remove('escondido');
}

function paginaSobre(){
  app().innerHTML = `
    <h1>Sobre nós</h1>
    <p>A Suco Shop nasceu em Belo Jardim com uma missão: suco de verdade, sem enrolação. Conheça a equipe!</p>
    <div class="equipe">
      <div class="pessoa"><div class="emoji">👩‍💼</div><h3>Rita Andrade</h3><p>Fundadora. Prova todos os sabores antes de irem para a vitrine.</p></div>
      <div class="pessoa"><div class="emoji">👩‍🍳</div><h3>Luana Costa</h3><p>Chef dos sucos. Inventou a Limonada Suíça da casa.</p></div>
      <div class="pessoa"><div class="emoji">🎧</div><h3>Duda Ferreira</h3><p>Atendimento (duda@suco-shop.br). Nasceu em 2009 e é apaixonada pela gatinha Pipoca, que aparece em todas as fotos dela! 🐱</p></div>
    </div>`;
}

function paginaRastrear(){
  app().innerHTML = `
    <div class="caixa">
      <h1>Rastrear pedido</h1>
      <p>Seu último pedido é o <b>nº 3</b>.</p>
      <label>Número do pedido<input id="num" value="3"></label>
      <button id="ver">Rastrear</button>
      <div id="res"></div>
    </div>`;
  document.getElementById('ver').onclick = async () => {
    const n = document.getElementById('num').value.trim();
    const resp = await fetch('/rest/track/' + encodeURIComponent(n));
    const res = document.getElementById('res'); res.innerHTML = '';
    if (!resp.ok){ res.appendChild(el('p','Pedido não encontrado.')); return; }
    const p = await resp.json();
    res.appendChild(el('p', 'Pedido nº ' + p.pedido + ' · cliente: ' + p.cliente));
    res.appendChild(el('p', 'Situação: ' + p.status + ' · itens: ' + p.itens));
    if (p.observacao){ const o = el('p', 'Observação: ' + p.observacao); o.className='recado'; res.appendChild(o); }
  };
}

function paginaLogin(){
  const u = usuario();
  if (u){
    app().innerHTML = '<div class="caixa"><h1>Minha conta</h1><p>Conectada como <b id="quem"></b></p><div id="recado"></div><button id="sair">Sair</button></div>';
    document.getElementById('quem').textContent = u.email;
    if (u.recado){ const r = el('div', u.recado); r.className='recado'; document.getElementById('recado').appendChild(r); }
    document.getElementById('sair').onclick = () => {
      localStorage.removeItem('usuario'); sessionStorage.removeItem('bid'); location.hash='#/login'; render();
    };
    return;
  }
  app().innerHTML = `
    <div class="caixa">
      <h1>Login</h1>
      <label>E-mail<input id="email" autocomplete="off"></label>
      <label>Senha<input id="senha" type="password"></label>
      <button id="entrar">Entrar</button>
      <div class="erro" id="erro"></div>
    </div>`;
  document.getElementById('entrar').onclick = entrar;
  document.getElementById('senha').onkeydown = (e) => { if (e.key==='Enter') entrar(); };
}

async function entrar(){
  const email = document.getElementById('email').value.trim();
  const senha = document.getElementById('senha').value;
  const resp = await fetch('/rest/user/login', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({email, password: senha})
  });
  if (!resp.ok){
    document.getElementById('erro').textContent = 'E-mail ou senha inválidos.';
    return;
  }
  const dados = await resp.json();
  localStorage.setItem('usuario', JSON.stringify(dados));
  localStorage.setItem('meuBid', String(dados.bid));
  sessionStorage.setItem('bid', String(dados.bid));   // número da cesta desta pessoa
  if (dados.papel === 'admin') resolver('senha');
  location.hash = '#/login';
  render();
}

async function paginaCesta(){
  const u = usuario();
  if (!u){ app().innerHTML = '<div class="caixa"><h1>Cesta</h1><p>Faça login para ver sua cesta.</p></div>'; return; }
  const bid = sessionStorage.getItem('bid') || String(u.bid);
  // FALHA DE PROPÓSITO: o servidor entrega qualquer cesta, sem conferir a dona.
  const resp = await fetch('/rest/basket/' + encodeURIComponent(bid));
  app().innerHTML = '<h1>Sua cesta</h1><table id="tab"><tr><th>Produto</th><th>Quantidade</th></tr></table><p id="info"></p>';
  if (!resp.ok){ document.getElementById('info').textContent = 'Cesta não encontrada.'; return; }
  const cesta = await resp.json();
  for (const item of cesta.itens){
    const tr = el('tr'); tr.appendChild(el('td', item.produto)); tr.appendChild(el('td', String(item.qtd)));
    document.getElementById('tab').appendChild(tr);
  }
  document.getElementById('info').textContent = 'Cesta nº ' + cesta.bid + ' · dona: ' + cesta.dona;
  if (String(cesta.bid) !== localStorage.getItem('meuBid')) resolver('cesta');
}

function paginaPlacar(){
  resolver('placar');
  const r = resolvidos();
  app().innerHTML = '<h1>Placar de desafios</h1><table id="tab"><tr><th>Desafio</th><th>Dificuldade</th><th>Descrição</th><th>Situação</th></tr></table>' +
    '<p style="margin-top:24px"><button id="zerar">Zerar progresso deste computador</button></p>';
  for (const d of DESAFIOS){
    const tr = el('tr');
    tr.appendChild(el('td', d.nome));
    const e = el('td', '★'.repeat(d.estrelas)); e.className='estrelas'; tr.appendChild(e);
    tr.appendChild(el('td', d.dica));
    const s = el('td', r.includes(d.id) ? '✔ resolvido' : 'pendente'); s.className = r.includes(d.id)?'ok':'pendente';
    tr.appendChild(s);
    document.getElementById('tab').appendChild(tr);
  }
  document.getElementById('zerar').onclick = () => {
    if (confirm('Apagar o progresso e sair da conta neste computador?')){
      localStorage.removeItem('desafios'); localStorage.removeItem('usuario'); localStorage.removeItem('meuBid');
      sessionStorage.clear(); location.hash='#/'; render();
    }
  };
}

async function paginaAdmin(){
  const u = usuario();
  if (!u || u.papel !== 'admin'){
    app().innerHTML = '<div class="negado"><h1>403 — Acesso negado</h1><p>Só o administrador pode ver esta página.</p></div>';
    return;
  }
  resolver('admin');
  const resp = await fetch('/api/Users', {headers:{'Authorization':'Bearer ' + u.token}});
  const usuarios = await resp.json();
  app().innerHTML = '<h1>Administração</h1><h2>Clientes cadastrados</h2><table id="tab"><tr><th>#</th><th>E-mail</th><th>Papel</th></tr></table>';
  for (const x of usuarios){
    const tr = el('tr'); tr.appendChild(el('td', String(x.id))); tr.appendChild(el('td', x.email)); tr.appendChild(el('td', x.papel));
    document.getElementById('tab').appendChild(tr);
  }
}

function render(){
  const caminho = location.hash.replace(/^#\/?/, '').split('?')[0];
  const u = usuario();
  document.getElementById('link-conta').textContent = u ? 'Conta (' + u.email.split('@')[0] + ')' : 'Conta';
  (rotas[caminho] || paginaInicio)();
}
window.addEventListener('hashchange', render);
render();
"""

PAGINA_SIMPLES = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITULO__</title>
<link rel="stylesheet" href="/style.css"></head><body>
<header><a href="/#/" class="logo">🧃 Suco Shop <small>simulador</small></a><nav><a href="/#/">Voltar à loja</a></nav></header>
<main>__CORPO__</main>
<footer>Loja FALSA para treino de segurança · Oficina Elas Hackeiam · 23ª SNCT UABJ/UFRPE</footer>
__SCRIPT__</body></html>"""


def pagina(titulo, corpo, script=""):
    return (PAGINA_SIMPLES.replace("__TITULO__", titulo).replace("__CORPO__", corpo)
            .replace("__SCRIPT__", script))


ROBOTS_TXT = "User-agent: *\nDisallow: /backup-secreto\n"

PAGINA_BACKUP = pagina("Backup antigo", """
<div class="caixa" style="max-width:720px">
<h1>📁 /backup-secreto</h1>
<p>Arquivos esquecidos do site antigo:</p>
<table>
<tr><th>Arquivo</th><th>Conteúdo</th></tr>
<tr><td>lista_de_compras.txt</td><td>laranja, maçã, gelo, canudos</td></tr>
<tr><td>lembrete.txt</td><td>Robôs não entram aqui... certo? SNCT{robots_txt_nao_e_cadeado}</td></tr>
<tr><td>bilhete.txt</td><td><code>__CIFRADO__</code><br><small>(Ass.: J. César)</small></td></tr>
</table>
</div>""".replace("__CIFRADO__", BILHETE_CIFRADO))

PAGINA_EMAIL = pagina("Caixa de entrada", """
<div class="caixa" style="max-width:640px">
<p style="opacity:.7">De: Suco Shop Prêmios &lt;premios@sucoshop-premios.xyz&gt;<br>Para: voce@email.com<br>Assunto: 🎁 VOCÊ GANHOU 1 ANO DE SUCO GRÁTIS!!!</p>
<h1>Parabéns, cliente especial!</h1>
<p>Você foi sorteada para ganhar <b>1 ano de suco grátis</b>. Mas corra: o prêmio expira em <b>15 minutos</b>!</p>
<p>Clique no botão abaixo e confirme seu CPF e o código que enviaremos ao seu celular.</p>
<p><a id="botao" style="display:inline-block;background:#2e7d32;color:#fff;padding:14px 28px;border-radius:6px;text-decoration:none;font-weight:700"
 href="http://sucoshop-premios.xyz/resgatar?codigo=SNCT{passe_o_mouse_antes_de_clicar}">RESGATAR NA SUCO SHOP OFICIAL</a></p>
<p style="font-size:12px;opacity:.6">Suco Shop · Belo Jardim · Não responda este e-mail.</p>
</div>""", """<script>
document.getElementById('botao').addEventListener('click', function(e){
  e.preventDefault();
  alert('Opa! Você clicou num link de golpe. Na vida real, NUNCA clique antes de conferir para onde ele leva.');
});
</script>""")

PAGINA_OFERTAS = pagina("Ofertas", """
<div class="caixa">
<h1>🎟️ Ofertas da semana</h1>
<p><b>Cupom VIP</b> — 1 ano de sucos com 50% de desconto.</p>
<p class="preco" style="font-size:28px">R$ 99,90</p>
<p>Seu saldo na carteira: <b>R$ 0,50</b></p>
<form method="POST" action="/ofertas/comprar">
  <input type="hidden" name="produto" value="cupom-vip">
  <input type="hidden" name="preco" value="99.90">
  <button type="submit">Comprar Cupom VIP</button>
</form>
</div>""")

PAGINA_COFRE = pagina("Cofre", """
<div class="caixa">
<h1>🔐 Cofre da Suco Shop</h1>
<p>Digite o PIN de 4 números para abrir o cofre.</p>
<label>PIN<input id="pin" maxlength="4" autocomplete="off"></label>
<button id="abrir">Abrir cofre</button>
<p id="msg" class="erro"></p>
</div>""", '<script src="/cofre.js"></script>')

COFRE_JS = r"""
// ===== Cofre da Suco Shop =====
// O PIN é conferido aqui mesmo, no navegador. (Será que isso é seguro?)
const PIN_CODIFICADO = "MjAyNg==";   // guardado "disfarçado" para ninguém ver ;)

async function conferirPin(){
  const pin = document.getElementById('pin').value.trim();
  const msg = document.getElementById('msg');
  if (btoa(pin) !== PIN_CODIFICADO){ msg.textContent = 'PIN errado.'; return; }
  const resp = await fetch('/rest/cofre', {method:'POST', headers:{'Content-Type':'application/json'},
                                            body: JSON.stringify({pin})});
  const dados = await resp.json();
  msg.className = 'ok';
  msg.textContent = dados.mensagem;
}
document.getElementById('abrir').onclick = conferirPin;
"""

# ============================================================== DESAFIOS DO CTF
# Dificuldade crescente: 100 (aquecimento) -> 200 -> 300 -> 400 (desafio final).
DESAFIOS_CTF = [
    {"id": "lei", "nome": "Número da lei", "categoria": "Aquecimento", "pontos": 100,
     "descricao": "Qual é o número da lei brasileira (de 2012) que tornou crime invadir celular ou computador de outra pessoa? "
                  "Envie no formato <code>SNCT{numero}</code>, só com algarismos.",
     "dica": "Ela ganhou o apelido de uma atriz. Lembrem do Encontro 1!", "custo": 25,
     "flag": "SNCT{12737}", "aceitar": ["12.737", "12737/2012", "12.737/2012", "snct{12.737}"],
     "passos": ["Lembrar do slide da lei no Encontro 1: Lei 12.737/2012, a “Lei Carolina Dieckmann”.",
                "Enviar só os algarismos: SNCT{12737}."],
     "licao": "Invadir dispositivo sem autorização é crime. Hackers éticas só testam com permissão."},

    {"id": "isca", "nome": "Isca no anzol", "categoria": "Golpes", "pontos": 100,
     "descricao": "A loja recebeu este e-mail: <a href='/promo-email.html' target='_blank'>abrir e-mail</a>. "
                  "O botão diz “Suco Shop oficial”... mas para onde ele leva DE VERDADE? A flag está no endereço de destino.",
     "dica": "Não clique! Passe o mouse em cima do botão e olhe o canto de baixo da tela — ou clique com o botão direito → Inspecionar.",
     "custo": 25, "flag": "SNCT{passe_o_mouse_antes_de_clicar}",
     "passos": ["Abrir o e-mail e passar o mouse sobre o botão, sem clicar.",
                "No canto inferior do navegador aparece o endereço real: sucoshop-premios.xyz/resgatar?codigo=SNCT{...}.",
                "Outra forma: botão direito → Inspecionar e ler o atributo href do link."],
     "licao": "O texto de um link pode mentir; o endereço não. Antes de clicar, confira o destino."},

    {"id": "comentario", "nome": "Bilhete no código", "categoria": "Web", "pontos": 100,
     "descricao": "Programadores às vezes deixam bilhetes dentro do código da página e esquecem de apagar. "
                  "Investiguem o código da <a href='/' target='_blank'>página inicial da loja</a>.",
     "dica": "Aperte Ctrl+U na loja para ver o código-fonte. Comentários começam com &lt;!--", "custo": 25,
     "flag": "SNCT{codigo_fonte_conta_segredos}",
     "passos": ["Abrir a loja e apertar Ctrl+U (ver código-fonte).",
                "Logo no começo há um comentário <!-- ... --> com a flag."],
     "licao": "Tudo o que vai para o navegador pode ser lido por qualquer pessoa. Segredo não vai no código da página."},

    {"id": "robots", "nome": "Robôs fofoqueiros", "categoria": "Web", "pontos": 100,
     "descricao": "Os sites usam um arquivo para avisar aos robôs do Google quais páginas eles NÃO devem visitar. "
                  "E se uma hacker resolver visitar justamente essas páginas?",
     "dica": "O arquivo se chama robots.txt e fica na raiz do site: localhost:3000/robots.txt", "custo": 25,
     "flag": "SNCT{robots_txt_nao_e_cadeado}",
     "passos": ["Abrir localhost:3000/robots.txt.",
                "Ele “proíbe” a página /backup-secreto. Abrir localhost:3000/backup-secreto.",
                "A flag está no arquivo lembrete.txt da lista."],
     "licao": "O robots.txt é um pedido educado, não uma tranca. Páginas sensíveis precisam de senha de verdade."},

    {"id": "duda", "nome": "A senha da Duda", "categoria": "Senhas", "pontos": 200,
     "descricao": "A atendente Duda usa uma senha “fácil de lembrar”. Descubram qual é usando só o que a própria loja "
                  "publica sobre ela, façam login como Duda e leiam o recado na conta dela.",
     "dica": "Leiam a página “Sobre nós”. A senha é o nome do bichinho + o ano de nascimento, tudo em minúsculas.",
     "custo": 50, "flag": "SNCT{osint_revela_senhas}",
     "passos": ["Na loja, abrir “Sobre nós”: Duda Ferreira, e-mail duda@suco-shop.br, nasceu em 2009, gata chamada Pipoca.",
                "Em Conta, entrar com duda@suco-shop.br e a senha pipoca2009.",
                "Na página da conta aparece o recado com a flag."],
     "licao": "Informações públicas (redes sociais, “sobre mim”) viram pistas de senha. Isso se chama OSINT."},

    {"id": "base64", "nome": "Nota interna", "categoria": "Criptografia", "pontos": 200,
     "descricao": "Os produtos da loja carregam uma “nota interna” que a vitrine não mostra. "
                  "Ela está disfarçada, mas disfarce não é cadeado.",
     "dica": "F12 → Rede → recarregue a loja → clique no pedido “products” → Resposta. "
             "O texto termina em “=”: é base64. No Console, digite atob('cole_o_texto_aqui').", "custo": 50,
     "flag": "SNCT{base64_nao_e_segredo}",
     "passos": ["Abrir a loja com o F12 na aba Rede e recarregar a página.",
                "Clicar no pedido “products” e olhar a Resposta: o Suco de Uva tem o campo nota_interna = U05DVHti...",
                "No Console, digitar atob('U05DVHtiYXNlNjRfbmFvX2Vfc2VncmVkb30=') e apertar Enter."],
     "licao": "Base64 é só outra forma de escrever, não é criptografia. Qualquer pessoa desfaz."},

    {"id": "cookie", "nome": "Clube do Suco", "categoria": "Web", "pontos": 200,
     "descricao": "O <a href='/clube' target='_blank'>Clube do Suco</a> é só para sócias. "
                  "O site decide quem é sócia de um jeito bem ingênuo...",
     "dica": "F12 → Aplicativo → Cookies → localhost:3000. Existe um cookie chamado “socio”. Troquem o valor e recarreguem.",
     "custo": 50, "flag": "SNCT{cookie_nao_e_cracha}",
     "passos": ["Abrir localhost:3000/clube: aparece “acesso negado”.",
                "F12 → Aplicativo (Application) → Cookies → localhost:3000: o cookie socio vale “nao”.",
                "Dar dois cliques no valor, trocar por “sim” e recarregar a página (F5)."],
     "licao": "Cookies ficam com a usuária e podem ser editados. O servidor não pode confiar neles para dar permissão."},

    {"id": "cesar", "nome": "Bilhete do imperador", "categoria": "Criptografia", "pontos": 300,
     "descricao": "No backup esquecido (aquele dos robôs) há um bilhete cifrado, assinado por “J. César”. "
                  "Um imperador romano escondia mensagens trocando cada letra por outra. Decifrem!",
     "dica": "Cada letra andou 3 casas para frente no alfabeto. Voltem 3: V→S, Q→N, F→C, W→T.", "custo": 75,
     "flag": "SNCT{cesar_anda_tres_casas}",
     "passos": ["Abrir localhost:3000/backup-secreto e copiar o bilhete: " + BILHETE_CIFRADO + ".",
                "Perceber que VQFW corresponde a SNCT: cada letra avançou 3 casas (cifra de César).",
                "Voltar 3 casas em cada letra (chaves e _ não mudam): SNCT{cesar_anda_tres_casas}."],
     "licao": "Cifras antigas caem em segundos. Hoje usamos criptografia moderna, com chaves longas."},

    {"id": "pedido", "nome": "Pedido alheio", "categoria": "Web", "pontos": 300,
     "descricao": "Em “Rastrear pedido”, a loja diz que o seu pedido é o nº 3. Será que dá para ver os pedidos "
                  "de outras pessoas? Um deles guarda um recado com a flag.",
     "dica": "Troquem o número e rastreiem de novo: 1, 2, 4, 5... O servidor não confere de quem é o pedido.",
     "custo": 75, "flag": "SNCT{idor_pedido_alheio}",
     "passos": ["Abrir “Rastrear pedido” na loja (com F12 → Rede aberto, dá para ver o pedido /rest/track/3).",
                "Trocar o número e rastrear de novo, um por um.",
                "O pedido nº 7 tem a observação com a flag."],
     "licao": "Isso se chama IDOR: o sistema entrega dados só pelo número, sem checar a dona. "
              "Defesa: o servidor confere em cada pedido se aquela pessoa pode ver aquilo."},

    {"id": "preco", "nome": "Preço camarada", "categoria": "Web", "pontos": 300,
     "descricao": "Em <a href='/ofertas' target='_blank'>Ofertas</a> existe um Cupom VIP de R$ 99,90 e vocês só têm "
                  "R$ 0,50 na carteira. Comprem mesmo assim!",
     "dica": "F12 → Elementos: procurem o formulário. O preço está num campo escondido (type=\"hidden\"). "
             "Deem dois cliques no value e troquem para 0.", "custo": 75,
     "flag": "SNCT{nunca_confie_no_navegador}",
     "passos": ["Abrir localhost:3000/ofertas e apertar F12 → Elementos (Elements).",
                "Achar <input type=\"hidden\" name=\"preco\" value=\"99.90\"> dentro do formulário.",
                "Trocar o value para 0 (ou 0.50), sair do campo e clicar em Comprar."],
     "licao": "Qualquer coisa que vem do navegador pode ser alterada. O preço tem que ser decidido pelo servidor."},

    {"id": "cofre", "nome": "O cofre", "categoria": "Desafio final", "pontos": 400,
     "descricao": "O <a href='/cofre' target='_blank'>cofre da loja</a> pede um PIN de 4 números. "
                  "Tentar no chute levaria horas... mas o próprio site revela como confere o PIN.",
     "dica": "F12 → Fontes → cofre.js. O PIN está guardado em base64. No Console: atob('MjAyNg==').", "custo": 100,
     "flag": "SNCT{elas_abriram_o_cofre}",
     "passos": ["Abrir localhost:3000/cofre e o F12 → Fontes (Sources) → cofre.js.",
                "Ler: o PIN é comparado com PIN_CODIFICADO = \"MjAyNg==\" (base64).",
                "No Console, atob('MjAyNg==') devolve 2026. Digitar 2026 no cofre e abrir."],
     "licao": "Juntou tudo: ler o código do navegador + desfazer base64. Verificação de senha nunca fica no navegador."},
]
DESAFIO_POR_ID = {d["id"]: d for d in DESAFIOS_CTF}
FLAG_COFRE = DESAFIO_POR_ID["cofre"]["flag"]

# ============================================================== ESTADO DO CTF
TRAVA = threading.Lock()


def estado_novo(pin=None):
    return {"pin": pin or "%04d" % secrets.randbelow(10000), "inicio": None, "duracao_min": 50,
            "encerrado": False, "congelado_em": None, "resolucao": False,
            "equipes": {}, "feed": [], "primeiras": {}}


def carregar_estado():
    try:
        dados = json.loads(ARQUIVO_CTF.read_text(encoding="utf-8"))
        base = estado_novo(dados.get("pin"))
        base.update(dados)
        return base
    except (OSError, ValueError):
        return estado_novo()


CTF = carregar_estado()


def salvar_estado():
    try:
        ARQUIVO_CTF.write_text(json.dumps(CTF, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass  # sem permissão de escrita: o placar fica só na memória


def fase_atual(agora=None):
    agora = agora or time.time()
    if not CTF["inicio"]:
        return "aguardando"
    if CTF["encerrado"] or agora >= CTF["inicio"] + CTF["duracao_min"] * 60:
        return "encerrado"
    return "andamento"


def segundos_restantes():
    if not CTF["inicio"]:
        return CTF["duracao_min"] * 60
    return max(0, int(CTF["inicio"] + CTF["duracao_min"] * 60 - time.time())) if not CTF["encerrado"] else 0


def pontos_da_equipe(eq, ate=None):
    total, ultimo = 0, 0
    for did, ts in eq["resolvidos"].items():
        if ate is None or ts <= ate:
            total += DESAFIO_POR_ID[did]["pontos"]
            ultimo = max(ultimo, ts)
    for did, ts in eq["dicas"].items():
        if ate is None or ts <= ate:
            total -= DESAFIO_POR_ID[did]["custo"]
    return total, ultimo


def ranking(ate=None):
    linhas = []
    for nome, eq in CTF["equipes"].items():
        pts, ultimo = pontos_da_equipe(eq, ate)
        qtd = sum(1 for ts in eq["resolvidos"].values() if ate is None or ts <= ate)
        linhas.append({"nome": nome, "pontos": pts, "resolvidos": qtd, "ultimo": ultimo or 9e18})
    linhas.sort(key=lambda x: (-x["pontos"], x["ultimo"], x["nome"]))
    for i, l in enumerate(linhas, 1):
        l["pos"] = i
        del l["ultimo"]
    return linhas


def equipe_pelo_token(token):
    for nome, eq in CTF["equipes"].items():
        if token and eq["token"] == token:
            return nome, eq
    return None, None


def normalizar(s):
    return re.sub(r"\s+", "", str(s)).lower()


def flag_correta(d, enviada):
    e = normalizar(enviada)
    alvo = d["flag"].lower()
    aceitas = {alvo, alvo[5:-1]} | {normalizar(a) for a in d.get("aceitar", [])}
    return e in aceitas


# ============================================================== PÁGINAS DO CTF
CTF_CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:#1d0f36;color:#f3ecfc}
a{color:#ffc7e3}
header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;padding:14px 28px;
 background:linear-gradient(90deg,#5b2bb5,#c2287a)}
header h1{margin:0;font-size:24px}
.relogio{font-size:28px;font-weight:800;background:#2a1250;padding:6px 18px;border-radius:999px;font-variant-numeric:tabular-nums}
.selo{background:#f2a93b;color:#2a1250;font-weight:800;padding:6px 14px;border-radius:999px}
main{max-width:1200px;margin:24px auto;padding:0 16px}
.caixa{background:#2c1952;border-radius:16px;padding:28px;max-width:520px;margin:40px auto}
input{width:100%;padding:12px;border-radius:8px;border:2px solid #5b2bb5;background:#1d0f36;color:#fff;font-size:17px;margin-top:6px}
button{margin-top:14px;padding:12px 22px;border:0;border-radius:8px;background:#f2a93b;color:#2a1250;font-weight:800;cursor:pointer;font-size:16px}
button.sec{background:#5b2bb5;color:#fff}
.erro{color:#ff9eb3;margin-top:10px}.certo{color:#69f0ae;margin-top:10px;font-weight:700}
h2.cat{margin:28px 0 12px;font-size:20px;letter-spacing:2px;text-transform:uppercase;color:#f2a93b}
.grade{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:16px}
.des{border-radius:16px;padding:18px;cursor:pointer;color:#fff;min-height:120px;display:flex;flex-direction:column;justify-content:space-between;transition:.15s}
.des:hover{transform:translateY(-3px)}
.des .pts{font-size:30px;font-weight:800}.des .nome{font-weight:700;font-size:17px}.des .solves{font-size:13px;opacity:.85}
.p100{background:#0e7c80}.p200{background:#2563c9}.p300{background:#c2287a}.p400{background:#5b2bb5;border:3px solid #f2a93b}
.des.feito{background:#2e7d32!important;border:none}
.layout{display:grid;grid-template-columns:1fr 300px;gap:28px}
@media(max-width:900px){.layout{grid-template-columns:1fr}}
.lado{background:#2c1952;border-radius:16px;padding:18px;align-self:start}
.lado ol{padding-left:22px;margin:0}.lado li{padding:6px 0;border-bottom:1px solid #3d2470}
.eu{color:#f2a93b;font-weight:800}
#modal{position:fixed;inset:0;background:rgba(0,0,0,.7);display:none;align-items:center;justify-content:center;padding:16px}
.janela{background:#2c1952;border-radius:16px;padding:28px;max-width:620px;width:100%;max-height:90vh;overflow:auto}
.janela .topo{display:flex;justify-content:space-between;align-items:center}
.dica{background:#3d2470;border-left:5px solid #f2a93b;padding:12px;border-radius:8px;margin-top:12px}
code{background:#1d0f36;padding:2px 6px;border-radius:4px}
.aviso{background:#3d2470;border-radius:12px;padding:16px;text-align:center;font-size:18px}
"""

CTF_HTML = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CTF Elas Hackeiam</title>
<link rel="stylesheet" href="/ctf/estilo.css"></head><body>
<header><h1>🚩 CTF Elas Hackeiam</h1><div style="display:flex;gap:12px;align-items:center">
<span id="equipe" class="selo" style="display:none"></span><span class="relogio" id="relogio">--:--</span></div></header>
<main id="app"></main>
<div id="modal"><div class="janela" id="janela"></div></div>
<script src="/ctf/ctf.js"></script></body></html>"""

CTF_JS = r"""
let TOKEN = localStorage.getItem('ctf_token') || '';
let ESTADO = null;
const $ = (id) => document.getElementById(id);
function el(tag, txt, cls){ const e=document.createElement(tag); if(txt!==undefined) e.textContent=txt; if(cls) e.className=cls; return e; }
function relogio(s){ const m=Math.floor(s/60), r=s%60; return String(m).padStart(2,'0')+':'+String(r).padStart(2,'0'); }
async function api(caminho, corpo){
  const op = {headers:{'X-Equipe': TOKEN, 'Content-Type':'application/json'}};
  if (corpo){ op.method='POST'; op.body=JSON.stringify(corpo); }
  const r = await fetch(caminho, op); return r.json();
}

function telaCadastro(){
  $('app').innerHTML = `
   <div class="caixa"><h2>Cadastro da equipe</h2>
   <p>Escolham o nome da equipe (uma cientista que vocês admiram!).</p>
   <input id="nome" maxlength="30" placeholder="Ex.: Equipe Ada Lovelace">
   <p style="font-size:14px;opacity:.8;margin-bottom:0">Já cadastraram em outro computador? Digitem o nome e o código da equipe:</p>
   <input id="codigo" maxlength="6" placeholder="Código (só se já tiverem equipe)">
   <button id="cad">Entrar no CTF</button><div class="erro" id="erro"></div></div>`;
  $('cad').onclick = async () => {
    const r = await api('/ctf/api/equipe', {nome:$('nome').value, codigo:$('codigo').value});
    if (r.erro){ $('erro').textContent = r.erro; return; }
    TOKEN = r.token; localStorage.setItem('ctf_token', TOKEN);
    alert('Equipe cadastrada! Anotem o código da equipe: ' + r.codigo + '\n(serve para entrar de outro computador)');
    atualizar();
  };
}

function telaDesafios(){
  const e = ESTADO;
  if (!$('grade-wrap')){
    $('app').innerHTML = '<div class="layout"><div id="grade-wrap"></div><div class="lado"><h3 style="margin-top:0">🏆 Ranking</h3><ol id="rank"></ol><p id="congel" style="font-size:13px;opacity:.8"></p></div></div>';
  }
  const wrap = $('grade-wrap'); wrap.innerHTML = '';
  if (e.fase === 'aguardando'){ wrap.appendChild(el('div','Equipe cadastrada! Aguardem a professora iniciar a competição...','aviso')); }
  if (e.fase === 'encerrado'){ wrap.appendChild(el('div','⏰ Tempo esgotado! A competição terminou. Olhem o telão para a resolução comentada.','aviso')); }
  const cats = [];
  for (const d of e.desafios){ if (!cats.includes(d.categoria)) cats.push(d.categoria); }
  for (const c of cats){
    wrap.appendChild(el('h2', c, 'cat'));
    const g = el('div', undefined, 'grade');
    for (const d of e.desafios.filter(x=>x.categoria===c)){
      const card = el('div', undefined, 'des p'+d.pontos + (d.resolvido?' feito':''));
      card.appendChild(el('div', d.resolvido ? '✔ ' + d.pontos : String(d.pontos), 'pts'));
      card.appendChild(el('div', d.nome, 'nome'));
      card.appendChild(el('div', d.resolucoes + (d.resolucoes===1?' equipe resolveu':' equipes resolveram'), 'solves'));
      card.onclick = () => abrir(d.id);
      g.appendChild(card);
    }
    wrap.appendChild(g);
  }
}

function abrir(id){
  const d = ESTADO.desafios.find(x=>x.id===id);
  const j = $('janela'); j.innerHTML = '';
  const topo = el('div', undefined, 'topo');
  topo.appendChild(el('h2', d.nome)); topo.appendChild(el('span', d.pontos + ' pts', 'selo'));
  j.appendChild(topo);
  const desc = el('p'); desc.innerHTML = d.descricao; j.appendChild(desc);
  if (d.dica){ const dc = el('div', '💡 ' + d.dica, 'dica'); j.appendChild(dc); }
  if (d.resolvido){
    j.appendChild(el('p', '✔ Sua equipe já resolveu este desafio!', 'certo'));
  } else if (ESTADO.fase === 'andamento'){
    const inp = el('input'); inp.placeholder = 'SNCT{...}'; inp.id = 'flag'; j.appendChild(inp);
    const b = el('button', 'Enviar flag'); j.appendChild(b);
    const msg = el('div'); j.appendChild(msg);
    const enviar = async () => {
      const r = await api('/ctf/api/flag', {id:d.id, flag:inp.value});
      msg.className = r.certo ? 'certo' : 'erro'; msg.textContent = r.mensagem;
      if (r.certo){ await atualizar(); setTimeout(fechar, 1500); }
    };
    b.onclick = enviar; inp.onkeydown = (ev) => { if (ev.key==='Enter') enviar(); };
    if (!d.dica){
      const bd = el('button', 'Ver dica (−' + d.custo + ' pts)', 'sec'); bd.style.marginLeft='10px';
      bd.onclick = async () => {
        if (!confirm('A dica custa ' + d.custo + ' pontos. Querem mesmo?')) return;
        await api('/ctf/api/dica', {id:d.id}); await atualizar(); abrir(d.id);
      };
      j.appendChild(bd);
    }
  }
  const f = el('button', 'Fechar', 'sec'); f.style.marginLeft='10px'; f.onclick = fechar; j.appendChild(f);
  $('modal').style.display = 'flex';
  setTimeout(()=>{ const i=$('flag'); if(i) i.focus(); }, 50);
}
function fechar(){ $('modal').style.display = 'none'; }
$('modal').onclick = (e) => { if (e.target.id==='modal') fechar(); };

async function atualizar(){
  ESTADO = await api('/ctf/api/estado');
  $('relogio').textContent = ESTADO.fase==='aguardando' ? 'aguardando' : (ESTADO.fase==='encerrado' ? 'fim' : relogio(ESTADO.restante));
  if (!ESTADO.equipe){ $('equipe').style.display='none'; if (!$('nome')) telaCadastro(); return; }
  $('equipe').style.display=''; $('equipe').textContent = ESTADO.equipe.nome + ' · ' + ESTADO.equipe.pontos + ' pts · código ' + ESTADO.equipe.codigo;
  if ($('modal').style.display !== 'flex') telaDesafios();
  const p = await api('/ctf/api/placar');
  const ol = $('rank'); if (!ol) return; ol.innerHTML = '';
  for (const l of p.ranking){
    const li = el('li', l.nome + ' — ' + l.pontos + ' pts'); if (l.nome===ESTADO.equipe.nome) li.className='eu'; ol.appendChild(li);
  }
  $('congel').textContent = p.congelado ? '❄️ Placar congelado: o resultado final será revelado no fim!' : '';
}
atualizar();
setInterval(() => { if (ESTADO && ESTADO.fase==='andamento' && ESTADO.restante>0){ ESTADO.restante--; $('relogio').textContent = relogio(ESTADO.restante); } }, 1000);
setInterval(atualizar, 5000);
"""

TELAO_HTML = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Telão — CTF Elas Hackeiam</title>
<link rel="stylesheet" href="/ctf/estilo.css"><style>
body{font-size:24px}.t{display:grid;grid-template-columns:1.4fr 1fr;gap:32px;padding:32px}
.linha{display:flex;justify-content:space-between;align-items:center;background:#2c1952;border-radius:16px;padding:18px 26px;margin-bottom:12px;font-size:32px}
.linha .pos{font-weight:800;color:#f2a93b;width:70px}.linha .n{flex:1;font-weight:700}.linha .pt{font-weight:800}
.ouro{background:linear-gradient(90deg,#f2a93b,#ffd27a);color:#2a1250}.ouro .pos{color:#2a1250}
.feed div{background:#2c1952;border-radius:12px;padding:12px 16px;margin-bottom:10px}
.grande{font-size:64px}</style></head><body>
<header><h1 style="font-size:36px">🚩 CTF Elas Hackeiam · 23ª SNCT</h1><span class="relogio grande" id="relogio">--:--</span></header>
<div class="t"><div><h2>🏆 Ranking ao vivo <span id="cong" style="font-size:22px"></span></h2><div id="rank"></div></div>
<div><h2>⚡ Últimas resoluções</h2><div class="feed" id="feed"></div>
<p style="opacity:.8">Entrem em: <b id="end"></b></p></div></div>
<script>
const $=(i)=>document.getElementById(i);
function relogio(s){const m=Math.floor(s/60),r=s%60;return String(m).padStart(2,'0')+':'+String(r).padStart(2,'0');}
let rest=0, fase='aguardando';
$('end').textContent = location.host + '/ctf';
async function at(){
  const p = await (await fetch('/ctf/api/placar')).json();
  fase=p.fase; rest=p.restante;
  $('relogio').textContent = fase==='aguardando'?'em breve':(fase==='encerrado'?'FIM':relogio(rest));
  $('cong').textContent = p.congelado ? '❄️ congelado' : '';
  const r=$('rank'); r.innerHTML='';
  if (!p.ranking.length) r.innerHTML='<div class="linha">Nenhuma equipe ainda...</div>';
  p.ranking.forEach((l,i)=>{
    const d=document.createElement('div'); d.className='linha'+(i===0&&l.pontos>0?' ouro':'');
    const a=document.createElement('span'); a.className='pos'; a.textContent=l.pos+'º';
    const b=document.createElement('span'); b.className='n'; b.textContent=l.nome;
    const c=document.createElement('span'); c.className='pt'; c.textContent=l.pontos+' pts';
    d.append(a,b,c); r.appendChild(d);
  });
  const f=$('feed'); f.innerHTML='';
  p.feed.forEach(x=>{const d=document.createElement('div'); d.textContent=(x.primeira?'⭐ ':'✔ ')+x.equipe+' resolveu “'+x.desafio+'” (+'+x.pontos+')'+(x.primeira?' — primeira!':''); f.appendChild(d);});
}
at(); setInterval(at, 4000);
setInterval(()=>{ if(fase==='andamento'&&rest>0){rest--; $('relogio').textContent=relogio(rest);} },1000);
</script></body></html>"""

PROF_HTML = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Painel da professora — CTF</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/ctf/estilo.css"><style>
.bts button{margin-right:8px}table{width:100%;border-collapse:collapse;margin-top:16px}
th,td{padding:8px;border-bottom:1px solid #3d2470;text-align:left}th{color:#f2a93b}
.status{font-size:20px;background:#2c1952;border-radius:12px;padding:16px;margin:16px 0}</style></head><body>
<header><h1>👩‍🏫 Painel da professora</h1><span class="relogio" id="relogio">--:--</span></header>
<main>
<div id="login" class="caixa"><h2>Senha do painel</h2><p>Ela aparece na janela preta do simulador.</p>
<input id="pin" type="password" maxlength="4"><button id="ok">Entrar</button><div class="erro" id="erro"></div></div>
<div id="painel" style="display:none">
<div class="status" id="status"></div>
<div class="bts">
 <label style="display:inline-block;width:240px">Duração (minutos)<input id="min" type="number" value="50" min="5" max="180"></label><br>
 <button id="iniciar">▶ Iniciar competição</button>
 <button id="congelar" class="sec">❄️ Congelar placar</button>
 <button id="descongelar" class="sec">☀️ Descongelar</button>
 <button id="encerrar" class="sec">⏹ Encerrar agora</button>
 <button id="resolucao">📖 Liberar resolução</button>
</div>
<p>Links: <a href="/ctf/telao" target="_blank">abrir telão</a> · <a href="/ctf/resolucao" target="_blank">abrir resolução</a></p>
<h2>Equipes</h2><table id="tab"></table>
<p style="margin-top:40px"><button id="zerar" class="sec">🗑 Zerar CTF (apaga equipes e pontos)</button></p>
</div></main>
<script>
const $=(i)=>document.getElementById(i);
let PIN = sessionStorage.getItem('pin')||'';
function relogio(s){const m=Math.floor(s/60),r=s%60;return String(m).padStart(2,'0')+':'+String(r).padStart(2,'0');}
async function acao(a, extra){
  const r = await (await fetch('/ctf/api/prof',{method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify(Object.assign({pin:PIN, acao:a}, extra||{}))})).json();
  if (r.erro){ $('erro').textContent=r.erro; $('login').style.display=''; $('painel').style.display='none'; return; }
  $('login').style.display='none'; $('painel').style.display='';
  const nomes={aguardando:'Aguardando início',andamento:'Em andamento',encerrado:'Encerrada'};
  $('status').textContent = 'Situação: '+nomes[r.fase]+' · duração '+r.duracao_min+' min · equipes: '+r.equipes.length+
     (r.congelado?' · placar CONGELADO':'')+(r.resolucao?' · resolução LIBERADA':'');
  $('relogio').textContent = r.fase==='andamento'?relogio(r.restante):(r.fase==='encerrado'?'fim':'--:--');
  const t=$('tab'); t.innerHTML='<tr><th>#</th><th>Equipe</th><th>Código</th><th>Pontos</th><th>Resolvidos</th><th>Dicas</th><th></th></tr>';
  r.equipes.forEach(e=>{
    const tr=document.createElement('tr');
    [e.pos,e.nome,e.codigo,e.pontos,e.resolvidos.join(', ')||'—',e.dicas.join(', ')||'—'].forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.appendChild(td);});
    const td=document.createElement('td'); const b=document.createElement('button'); b.textContent='remover'; b.className='sec'; b.style.margin='0';
    b.onclick=()=>{ if(confirm('Remover a equipe '+e.nome+'?')) acao('remover_equipe',{equipe:e.nome}); };
    td.appendChild(b); tr.appendChild(td); t.appendChild(tr);
  });
}
$('ok').onclick=()=>{ PIN=$('pin').value; sessionStorage.setItem('pin',PIN); acao('ver'); };
$('iniciar').onclick=()=>{ if(confirm('Iniciar a competição agora? O cronômetro começa a contar.')) acao('iniciar',{minutos:Number($('min').value)}); };
$('congelar').onclick=()=>acao('congelar');
$('descongelar').onclick=()=>acao('descongelar');
$('encerrar').onclick=()=>{ if(confirm('Encerrar a competição agora?')) acao('encerrar'); };
$('resolucao').onclick=()=>acao('resolucao');
$('zerar').onclick=()=>{ if(confirm('Apagar TODAS as equipes e pontos?')) acao('zerar'); };
if (PIN) acao('ver');
setInterval(()=>{ if($('painel').style.display!=='none') acao('ver'); }, 5000);
</script></body></html>"""


def pagina_resolucao():
    if not CTF["resolucao"]:
        corpo = ("<div class='caixa'><h2>📖 Resolução comentada</h2>"
                 "<p>A resolução será liberada pela professora quando a competição terminar. Segurem a curiosidade!</p></div>")
    else:
        partes = ["<h1 style='margin-top:0'>📖 Resolução comentada dos enigmas</h1>"]
        for d in DESAFIOS_CTF:
            passos = "".join("<li>%s</li>" % html.escape(p) for p in d["passos"])
            partes.append(
                "<div class='caixa' style='max-width:none;margin:20px 0'>"
                "<div style='display:flex;justify-content:space-between;align-items:center'><h2 style='margin:0'>%s</h2>"
                "<span class='selo'>%s · %d pts</span></div><ol>%s</ol>"
                "<p><b>Flag:</b> <code>%s</code></p><p><b>Lição:</b> %s</p></div>"
                % (html.escape(d["nome"]), html.escape(d["categoria"]), d["pontos"], passos,
                   html.escape(d["flag"]), html.escape(d["licao"])))
        corpo = "".join(partes)
    return ("<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Resolução — CTF</title>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<link rel='stylesheet' href='/ctf/estilo.css'><style>body{font-size:20px}li{margin:6px 0}</style></head><body>"
            "<header><h1>🚩 CTF Elas Hackeiam</h1></header><main>" + corpo + "</main></body></html>")


# ============================================================== SERVIDOR
TOKENS = {}  # token de login da loja -> usuário


class Loja(BaseHTTPRequestHandler):
    server_version = "SucoShop/2.0"

    def log_message(self, fmt, *args):
        if "/ctf/api/" in (fmt % args):
            return  # não poluir a janela com as atualizações automáticas do CTF
        sys.stdout.write("  pedido: %s\n" % (fmt % args))

    def _enviar(self, codigo, corpo, tipo="application/json; charset=utf-8", extras=None):
        if not isinstance(corpo, (bytes, bytearray)):
            corpo = (json.dumps(corpo, ensure_ascii=False) if tipo.startswith("application/json") else corpo).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extras or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _html(self, texto, codigo=200, extras=None):
        return self._enviar(codigo, texto, "text/html; charset=utf-8", extras)

    def _corpo(self):
        tamanho = int(self.headers.get("Content-Length", "0") or 0)
        return self.rfile.read(min(tamanho, 100_000)) if tamanho else b""

    def _json(self):
        try:
            return json.loads(self._corpo() or b"{}")
        except ValueError:
            return {}

    def _cookies(self):
        bruto = self.headers.get("Cookie", "")
        res = {}
        for parte in bruto.split(";"):
            if "=" in parte:
                k, v = parte.strip().split("=", 1)
                res[k] = v
        return res

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        caminho = self.path.split("?")[0]
        # ---- loja
        if caminho in ("/", "/index.html"):
            return self._html(INDEX_HTML)
        if caminho == "/main.js":
            return self._enviar(200, MAIN_JS, "application/javascript; charset=utf-8")
        if caminho == "/style.css":
            return self._enviar(200, STYLE_CSS, "text/css; charset=utf-8")
        if caminho == "/rest/products":
            return self._enviar(200, PRODUTOS)
        m = re.fullmatch(r"/rest/products/(\d+)/reviews", caminho)
        if m:
            return self._enviar(200, AVALIACOES.get(int(m.group(1)), []))
        m = re.fullmatch(r"/rest/basket/(\d+)", caminho)
        if m:
            # FALHA DE PROPÓSITO (controle de acesso quebrado): não confere a dona da cesta.
            bid = int(m.group(1))
            if bid not in CESTAS:
                return self._enviar(404, {"erro": "cesta não encontrada"})
            dona = next(u["email"] for u in USUARIOS if u["bid"] == bid)
            return self._enviar(200, {"bid": bid, "dona": dona, "itens": CESTAS[bid]})
        m = re.fullmatch(r"/rest/track/(\d+)", caminho)
        if m:
            # FALHA DE PROPÓSITO (IDOR): qualquer pessoa vê qualquer pedido.
            n = int(m.group(1))
            return self._enviar(200, PEDIDOS[n]) if n in PEDIDOS else self._enviar(404, {"erro": "não encontrado"})
        if caminho == "/api/Users":
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer ") or auth[7:] not in TOKENS:
                return self._enviar(401, {"erro": "faça login"})
            return self._enviar(200, [{"id": u["id"], "email": u["email"], "papel": u["papel"]} for u in USUARIOS])
        if caminho == "/robots.txt":
            return self._enviar(200, ROBOTS_TXT, "text/plain; charset=utf-8")
        if caminho in ("/backup-secreto", "/backup-secreto/"):
            return self._html(PAGINA_BACKUP)
        if caminho == "/promo-email.html":
            return self._html(PAGINA_EMAIL)
        if caminho == "/clube":
            if self._cookies().get("socio", "").lower() == "sim":
                return self._html(pagina("Clube do Suco", "<div class='caixa'><h1>🥤 Bem-vinda ao Clube do Suco!</h1>"
                                         "<p>Sua carteirinha de sócia: <b>SNCT{cookie_nao_e_cracha}</b></p></div>"))
            return self._html(pagina("Clube do Suco", "<div class='caixa negado'><h1>🚫 Clube do Suco</h1>"
                                     "<p>Área exclusiva para sócias. Você ainda não é sócia.</p></div>"),
                              extras=[("Set-Cookie", "socio=nao; Path=/")])
        if caminho == "/ofertas":
            return self._html(PAGINA_OFERTAS)
        if caminho == "/cofre":
            return self._html(PAGINA_COFRE)
        if caminho == "/cofre.js":
            return self._enviar(200, COFRE_JS, "application/javascript; charset=utf-8")
        # ---- CTF
        if caminho in ("/ctf", "/ctf/"):
            return self._html(CTF_HTML)
        if caminho == "/ctf/estilo.css":
            return self._enviar(200, CTF_CSS, "text/css; charset=utf-8")
        if caminho == "/ctf/ctf.js":
            return self._enviar(200, CTF_JS, "application/javascript; charset=utf-8")
        if caminho == "/ctf/telao":
            return self._html(TELAO_HTML)
        if caminho == "/ctf/professora":
            return self._html(PROF_HTML)
        if caminho == "/ctf/resolucao":
            with TRAVA:
                return self._html(pagina_resolucao())
        if caminho == "/ctf/api/estado":
            return self._api_estado()
        if caminho == "/ctf/api/placar":
            return self._api_placar()
        if caminho == "/favicon.ico":
            return self._enviar(204, b"", "image/x-icon")
        return self._enviar(404, {"erro": "não encontrado"})

    # ------------------------------------------------------------------ POST
    def do_POST(self):
        caminho = self.path.split("?")[0]
        if caminho == "/rest/user/login":
            dados = self._json()
            email = str(dados.get("email", "")).strip().lower()
            senha = str(dados.get("password", ""))
            for u in USUARIOS:
                ok = u["senha"] == senha or (u["id"] == 5 and u["senha"] == senha.lower())
                if u["email"] == email and ok:
                    token = "tok-%d-%d" % (u["id"], len(TOKENS) + 1)
                    TOKENS[token] = u
                    resp = {"token": token, "email": u["email"], "papel": u["papel"], "bid": u["bid"]}
                    if u.get("recado"):
                        resp["recado"] = u["recado"]
                    return self._enviar(200, resp)
            return self._enviar(401, {"erro": "E-mail ou senha inválidos."})
        if caminho == "/ofertas/comprar":
            campos = parse_qs(self._corpo().decode("utf-8", "replace"))
            try:
                preco = float(campos.get("preco", ["99.90"])[0].replace(",", "."))
            except ValueError:
                preco = 99.90
            if preco <= 0.50:
                corpo = ("<div class='caixa'><h1>✅ Compra aprovada!</h1><p>Você pagou R$ %.2f pelo Cupom VIP.</p>"
                         "<p>Código do cupom: <b>SNCT{nunca_confie_no_navegador}</b></p></div>" % preco)
            else:
                corpo = ("<div class='caixa negado'><h1>Saldo insuficiente</h1><p>O Cupom VIP custa R$ %.2f "
                         "e você só tem R$ 0,50.</p><p><a href='/ofertas'>Voltar</a></p></div>" % preco)
            return self._html(pagina("Ofertas", corpo))
        if caminho == "/rest/cofre":
            dados = self._json()
            if str(dados.get("pin", "")).strip() == "2026":
                return self._enviar(200, {"mensagem": "Cofre aberto! Lá dentro tem um bilhete: " + FLAG_COFRE})
            return self._enviar(403, {"mensagem": "PIN errado."})
        if caminho == "/ctf/api/equipe":
            return self._api_equipe()
        if caminho == "/ctf/api/flag":
            return self._api_flag()
        if caminho == "/ctf/api/dica":
            return self._api_dica()
        if caminho == "/ctf/api/prof":
            return self._api_prof()
        return self._enviar(404, {"erro": "não encontrado"})

    # ------------------------------------------------------------------ API CTF
    def _equipe(self):
        return equipe_pelo_token(self.headers.get("X-Equipe", ""))

    def _api_estado(self):
        with TRAVA:
            nome, eq = self._equipe()
            fase = fase_atual()
            res = {"fase": fase, "restante": segundos_restantes(), "resolucao": CTF["resolucao"], "equipe": None,
                   "desafios": []}
            if eq:
                pts, _ = pontos_da_equipe(eq)
                res["equipe"] = {"nome": nome, "codigo": eq["codigo"], "pontos": pts}
                if fase != "aguardando":
                    for d in DESAFIOS_CTF:
                        res["desafios"].append({
                            "id": d["id"], "nome": d["nome"], "categoria": d["categoria"], "pontos": d["pontos"],
                            "descricao": d["descricao"], "custo": d["custo"],
                            "dica": d["dica"] if d["id"] in eq["dicas"] else None,
                            "resolvido": d["id"] in eq["resolvidos"],
                            "resolucoes": sum(1 for e in CTF["equipes"].values() if d["id"] in e["resolvidos"]),
                        })
            return self._enviar(200, res)

    def _api_placar(self):
        with TRAVA:
            congelado = CTF["congelado_em"] is not None
            feed = [f for f in CTF["feed"] if not congelado or f["ts"] <= CTF["congelado_em"]][-8:][::-1]
            return self._enviar(200, {"fase": fase_atual(), "restante": segundos_restantes(), "congelado": congelado,
                                      "ranking": ranking(CTF["congelado_em"]),
                                      "feed": [{k: f[k] for k in ("equipe", "desafio", "pontos", "primeira")} for f in feed]})

    def _api_equipe(self):
        dados = self._json()
        nome = re.sub(r"\s+", " ", str(dados.get("nome", ""))).strip()[:30]
        codigo = str(dados.get("codigo", "")).strip().upper()
        if not nome:
            return self._enviar(200, {"erro": "Digitem o nome da equipe."})
        with TRAVA:
            if nome in CTF["equipes"]:
                eq = CTF["equipes"][nome]
                if codigo and codigo == eq["codigo"]:
                    return self._enviar(200, {"token": eq["token"], "codigo": eq["codigo"]})
                return self._enviar(200, {"erro": "Esse nome já existe. Para entrar de outro computador, digitem também o código da equipe."})
            if len(CTF["equipes"]) >= 60:
                return self._enviar(200, {"erro": "Limite de equipes atingido."})
            eq = {"token": secrets.token_hex(16), "codigo": "".join(random.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(4)),
                  "resolvidos": {}, "dicas": {}, "criada": time.time()}
            CTF["equipes"][nome] = eq
            salvar_estado()
            return self._enviar(200, {"token": eq["token"], "codigo": eq["codigo"]})

    def _api_flag(self):
        dados = self._json()
        with TRAVA:
            nome, eq = self._equipe()
            if not eq:
                return self._enviar(200, {"certo": False, "mensagem": "Equipe não encontrada. Recarreguem a página."})
            if fase_atual() != "andamento":
                return self._enviar(200, {"certo": False, "mensagem": "A competição não está valendo agora."})
            d = DESAFIO_POR_ID.get(str(dados.get("id")))
            if not d:
                return self._enviar(200, {"certo": False, "mensagem": "Desafio inexistente."})
            if d["id"] in eq["resolvidos"]:
                return self._enviar(200, {"certo": True, "mensagem": "Vocês já tinham resolvido este!"})
            if not flag_correta(d, dados.get("flag", "")):
                return self._enviar(200, {"certo": False, "mensagem": "Ainda não... confiram a flag e tentem de novo."})
            agora = time.time()
            eq["resolvidos"][d["id"]] = agora
            primeira = d["id"] not in CTF["primeiras"]
            if primeira:
                CTF["primeiras"][d["id"]] = nome
            CTF["feed"].append({"equipe": nome, "desafio": d["nome"], "pontos": d["pontos"], "primeira": primeira, "ts": agora})
            CTF["feed"] = CTF["feed"][-100:]
            salvar_estado()
            extra = " Vocês foram a PRIMEIRA equipe! ⭐" if primeira else ""
            return self._enviar(200, {"certo": True, "mensagem": "🎉 Flag correta! +%d pontos.%s" % (d["pontos"], extra)})

    def _api_dica(self):
        dados = self._json()
        with TRAVA:
            nome, eq = self._equipe()
            d = DESAFIO_POR_ID.get(str(dados.get("id")))
            if not eq or not d or fase_atual() != "andamento":
                return self._enviar(200, {"erro": "Agora não dá."})
            if d["id"] not in eq["dicas"] and d["id"] not in eq["resolvidos"]:
                eq["dicas"][d["id"]] = time.time()
                salvar_estado()
            return self._enviar(200, {"dica": d["dica"]})

    def _api_prof(self):
        dados = self._json()
        with TRAVA:
            if str(dados.get("pin", "")) != CTF["pin"]:
                return self._enviar(200, {"erro": "Senha errada. Confira na janela preta do simulador."})
            acao = dados.get("acao")
            if acao == "iniciar":
                try:
                    CTF["duracao_min"] = max(5, min(180, int(dados.get("minutos", 50))))
                except (TypeError, ValueError):
                    pass
                CTF["inicio"], CTF["encerrado"], CTF["congelado_em"] = time.time(), False, None
            elif acao == "congelar" and CTF["congelado_em"] is None:
                CTF["congelado_em"] = time.time()
            elif acao == "descongelar":
                CTF["congelado_em"] = None
            elif acao == "encerrar" and CTF["inicio"]:
                CTF["encerrado"] = True
            elif acao == "resolucao":
                CTF["resolucao"] = True
            elif acao == "remover_equipe":
                CTF["equipes"].pop(str(dados.get("equipe")), None)
            elif acao == "zerar":
                pin = CTF["pin"]
                CTF.clear()
                CTF.update(estado_novo(pin))
            salvar_estado()
            rk = {l["nome"]: l for l in ranking()}
            equipes = []
            for n, eq in CTF["equipes"].items():
                equipes.append({"nome": n, "codigo": eq["codigo"], "pontos": rk[n]["pontos"], "pos": rk[n]["pos"],
                                "resolvidos": [DESAFIO_POR_ID[i]["nome"] for i in eq["resolvidos"]],
                                "dicas": [DESAFIO_POR_ID[i]["nome"] for i in eq["dicas"]]})
            equipes.sort(key=lambda e: e["pos"])
            return self._enviar(200, {"fase": fase_atual(), "restante": segundos_restantes(),
                                      "duracao_min": CTF["duracao_min"], "congelado": CTF["congelado_em"] is not None,
                                      "resolucao": CTF["resolucao"], "equipes": equipes})


def ip_na_rede():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # não envia nada; só descobre o IP local
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def main():
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else PORTA
    try:
        servidor = ThreadingHTTPServer(("0.0.0.0", porta), Loja)
    except OSError:
        print("\nA porta %d já está em uso (talvez o simulador já esteja aberto em outra janela)." % porta)
        print("Feche a outra janela ou rode:  python simulador_juice_shop.py 3001")
        input("\nAperte Enter para sair...")
        return
    salvar_estado()
    ip = ip_na_rede()
    print("=" * 66)
    print("  SUCO SHOP + CTF — simulador da oficina Elas Hackeiam")
    print("=" * 66)
    print("  LOJA (Encontro 1)")
    print("    Neste computador:     http://localhost:%d" % porta)
    print("    Outros computadores:  http://%s:%d" % (ip, porta))
    print("  CTF (Encontro 2)")
    print("    Equipes:              http://%s:%d/ctf" % (ip, porta))
    print("    Telão (projetar):     http://localhost:%d/ctf/telao" % porta)
    print("    Painel da professora: http://localhost:%d/ctf/professora" % porta)
    print("    SENHA DO PAINEL:      %s" % CTF["pin"])
    print("  Para desligar: feche esta janela (ou aperte Ctrl+C).")
    print("=" * 66)
    print("  Abaixo aparecem os pedidos feitos à loja:\n")
    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:%d" % porta)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nSimulador desligado. Até a próxima!")


if __name__ == "__main__":
    main()
