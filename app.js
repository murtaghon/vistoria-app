// ─── Elementos da página ───────────────────────────────
const inputFotos   = document.getElementById('input-fotos')
const btnGerar     = document.getElementById('btn-gerar')
const btnConfirmar = document.getElementById('btn-confirmar')
const btnAlteracao = document.getElementById('btn-alteracao')
const btnPdf       = document.getElementById('btn-pdf')
 
// ─── Estado global ──────────────────────────────────────
let fotosArquivos   = []   // arquivos originais
let fotosURLs       = []   // URLs temporárias para preview
let comodosPorFoto  = []   // [{index, comodo, confirmado}]
let laudoAtual      = ''
 
// ─── ETAPA 1: Preview das fotos ─────────────────────────
inputFotos.addEventListener('change', function() {
    fotosArquivos = Array.from(this.files)
    fotosURLs     = fotosArquivos.map(f => URL.createObjectURL(f))
 
    const previa = document.getElementById('previa-fotos')
    previa.innerHTML = ''
 
    fotosURLs.forEach(function(url) {
        const img = document.createElement('img')
        img.src = url
        previa.appendChild(img)
    })
})
 
// ─── ETAPA 1: Clique em Gerar Laudo ─────────────────────
btnGerar.addEventListener('click', function() {
 
    document.getElementById('mensagem-erro').textContent = ''
 
    if (fotosArquivos.length === 0) {
        document.getElementById('mensagem-erro').textContent =
            '⚠️ Selecione pelo menos uma foto antes de gerar o laudo.'
        return
    }
 
    btnGerar.textContent  = '⏳ Identificando cômodos...'
    btnGerar.disabled     = true
    btnGerar.style.backgroundColor = '#166a34'
 
    // Monta o FormData com as fotos
    const formData = new FormData()
    fotosArquivos.forEach(f => formData.append('fotos', f))
 
    const contexto = document.getElementById('contexto').value
    if (contexto.trim()) formData.append('contexto', contexto)
 
    // Chama o servidor para identificar os cômodos
    fetch('http://127.0.0.1:5000/identificar-comodos', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(function(dados) {
 
        if (!dados.comodos) {
            mostrarErro('⚠️ Erro ao identificar os cômodos.')
            resetarBtnGerar()
            return
        }
 
        comodosPorFoto = dados.comodos.map((c, i) => ({
            index: i,
            comodo: c,
            confirmado: false
        }))
 
        // Vai para etapa 2
        document.getElementById('etapa-upload').style.display     = 'none'
        document.getElementById('etapa-validacao').style.display  = 'flex'
 
        montarCardsValidacao()
    })
    .catch(function() {
        mostrarErro('⚠️ Erro ao conectar com o servidor.')
        resetarBtnGerar()
    })
})
 
// ─── ETAPA 2: Montar cards de validação ─────────────────
function montarCardsValidacao() {
    const container = document.getElementById('cards-validacao')
    container.innerHTML = ''
 
    comodosPorFoto.forEach(function(item) {
        const card = document.createElement('div')
        card.classList.add('card-validacao')
        card.id = `card-${item.index}`
 
        card.innerHTML = `
            <img src="${fotosURLs[item.index]}" alt="Foto ${item.index + 1}">
            <div class="card-info">
                <label>Foto ${item.index + 1} — A IA identificou como:</label>
                <strong id="comodo-label-${item.index}">${item.comodo}</strong>
                <input
                    class="card-input"
                    id="comodo-input-${item.index}"
                    type="text"
                    value="${item.comodo}"
                    placeholder="Nome do cômodo"
                    style="display:none"
                >
                <div class="card-acoes">
                    <button class="btn-confirmar-foto" onclick="confirmarFoto(${item.index})">✅ Correto</button>
                    <button class="btn-editar-foto" onclick="editarFoto(${item.index})">✏️ Corrigir</button>
                </div>
                <span class="tag-confirmado" id="tag-${item.index}" style="display:none">✅ Confirmado</span>
            </div>
        `
        container.appendChild(card)
    })
}
 
// ─── ETAPA 2: Confirmar foto ────────────────────────────
function confirmarFoto(index) {
    // Pega o valor atual do input (caso tenha sido editado)
    const input = document.getElementById(`comodo-input-${index}`)
    const novoNome = input.value.trim() || comodosPorFoto[index].comodo
 
    comodosPorFoto[index].comodo      = novoNome
    comodosPorFoto[index].confirmado  = true
 
    // Atualiza visual do card
    document.getElementById(`comodo-label-${index}`).textContent = novoNome
    input.style.display = 'none'
    document.getElementById(`comodo-label-${index}`).style.display = 'block'
    document.getElementById(`tag-${index}`).style.display = 'block'
    document.getElementById(`card-${index}`).classList.add('card-confirmado')
}
 
// ─── ETAPA 2: Editar foto ───────────────────────────────
function editarFoto(index) {
    const label = document.getElementById(`comodo-label-${index}`)
    const input = document.getElementById(`comodo-input-${index}`)
 
    label.style.display = 'none'
    input.style.display = 'block'
    input.focus()
 
    // Confirma ao pressionar Enter
    input.onkeydown = function(e) {
        if (e.key === 'Enter') confirmarFoto(index)
    }
}
 
// ─── ETAPA 2: Confirmar todos e gerar laudo ─────────────
btnConfirmar.addEventListener('click', function() {
 
    // Confirma automaticamente os que ainda não foram confirmados
    comodosPorFoto.forEach(function(item) {
        if (!item.confirmado) confirmarFoto(item.index)
    })
 
    btnConfirmar.textContent = '⏳ Gerando laudo...'
    btnConfirmar.disabled    = true
 
    // Monta o FormData com fotos e cômodos confirmados
    const formData = new FormData()
    fotosArquivos.forEach(f => formData.append('fotos', f))
 
    const comodos = comodosPorFoto.map(c => c.comodo)
    formData.append('comodos', JSON.stringify(comodos))
 
    const contexto = document.getElementById('contexto').value
    if (contexto.trim()) formData.append('contexto', contexto)
 
    fetch('http://127.0.0.1:5000/gerar-laudo', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(function(dados) {
        if (!dados.laudo) {
            alert('Erro ao gerar o laudo.')
            btnConfirmar.textContent = '✅ Confirmar e Gerar Laudo'
            btnConfirmar.disabled    = false
            return
        }
 
        laudoAtual = dados.laudo
 
        // Vai para etapa 3
        document.getElementById('etapa-validacao').style.display = 'none'
        document.getElementById('etapa-revisao').style.display   = 'flex'
 
        document.getElementById('laudo-texto').textContent = laudoAtual
        document.getElementById('etapa-revisao').scrollIntoView({ behavior: 'smooth' })
    })
    .catch(function() {
        alert('Erro ao conectar com o servidor.')
        btnConfirmar.textContent = '✅ Confirmar e Gerar Laudo'
        btnConfirmar.disabled    = false
    })
})
 
// ─── ETAPA 3: Solicitar alteração ───────────────────────
btnAlteracao.addEventListener('click', function() {
 
    const pedido = document.getElementById('pedido-alteracao').value
 
    if (!pedido.trim()) {
        alert('Descreva o que deseja alterar no laudo.')
        return
    }
 
    btnAlteracao.textContent = '⏳ Atualizando laudo...'
    btnAlteracao.disabled    = true
 
    fetch('http://127.0.0.1:5000/revisar-laudo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ laudo_atual: laudoAtual, pedido: pedido })
    })
    .then(r => r.json())
    .then(function(dados) {
        if (dados.laudo) {
            laudoAtual = dados.laudo
            document.getElementById('laudo-texto').textContent = laudoAtual
            document.getElementById('pedido-alteracao').value  = ''
        }
        btnAlteracao.textContent = '✏️ Solicitar Alteração'
        btnAlteracao.disabled    = false
    })
    .catch(function() {
        alert('Erro ao conectar com o servidor.')
        btnAlteracao.textContent = '✏️ Solicitar Alteração'
        btnAlteracao.disabled    = false
    })
})
 
// ─── ETAPA 3: Gerar PDF ─────────────────────────────────
btnPdf.addEventListener('click', function() {
 
    btnPdf.textContent = '⏳ Gerando PDF...'
    btnPdf.disabled    = true
 
    // Monta FormData com laudo + fotos + cômodos para o PDF
    const formData = new FormData()
    formData.append('laudo', laudoAtual)
    formData.append('comodos', JSON.stringify(comodosPorFoto.map(c => c.comodo)))
    fotosArquivos.forEach(f => formData.append('fotos', f))
 
    fetch('http://127.0.0.1:5000/gerar-pdf', {
        method: 'POST',
        body: formData
    })
    .then(r => r.blob())
    .then(function(blob) {
        const url  = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href     = url
        link.download = 'laudo_vistoria.pdf'
        link.click()
        btnPdf.textContent = '📄 Gerar PDF Final'
        btnPdf.disabled    = false
    })
    .catch(function() {
        alert('Erro ao gerar o PDF.')
        btnPdf.textContent = '📄 Gerar PDF Final'
        btnPdf.disabled    = false
    })
})
 
// ─── Helpers ────────────────────────────────────────────
function mostrarErro(msg) {
    document.getElementById('mensagem-erro').textContent = msg
}
 
function resetarBtnGerar() {
    btnGerar.textContent = 'Gerar Laudo'
    btnGerar.disabled    = false
    btnGerar.style.backgroundColor = '#22c55e'
}
 