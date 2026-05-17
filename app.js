// ─── Estado global — fora do DOMContentLoaded para ser acessível em funções onclick ───
let fotosArquivos  = []
let fotosURLs      = []
let comodosPorFoto = []
let laudoAtual     = ''

// ─── Funções globais — chamadas pelo onclick no HTML ───────────────────────────
function confirmarFoto(index) {
    const input    = document.getElementById(`comodo-input-${index}`)
    const novoNome = input.value.trim() || comodosPorFoto[index].comodo

    comodosPorFoto[index].comodo     = novoNome
    comodosPorFoto[index].confirmado = true

    document.getElementById(`comodo-label-${index}`).textContent   = novoNome
    document.getElementById(`comodo-label-${index}`).style.display = 'block'
    document.getElementById(`tag-${index}`).style.display          = 'block'
    document.getElementById(`card-${index}`).classList.add('card-confirmado')
    input.style.display = 'none'
}

function editarFoto(index) {
    const label = document.getElementById(`comodo-label-${index}`)
    const input = document.getElementById(`comodo-input-${index}`)

    label.style.display = 'none'
    input.style.display = 'block'
    input.focus()

    input.onkeydown = function(e) {
        if (e.key === 'Enter') confirmarFoto(index)
    }
}

// ─── Tudo que depende do DOM ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {

    // Verifica se está logado
    const token = localStorage.getItem('token')
    const nome  = localStorage.getItem('nome')

    if (!token) {
        window.location.href = 'login.html'
        return
    }

    // Mostra nome e logout
    document.getElementById('nome-usuario').textContent = 'Olá, ' + nome
    document.getElementById('btn-logout').addEventListener('click', function() {
        localStorage.removeItem('token')
        localStorage.removeItem('nome')
        window.location.href = 'login.html'
    })

    // ─── Elementos da página ───────────────────────────────
    const inputFotos   = document.getElementById('input-fotos')
    const btnGerar     = document.getElementById('btn-gerar')
    const btnConfirmar = document.getElementById('btn-confirmar')
    const btnAlteracao = document.getElementById('btn-alteracao')
    const btnPdf       = document.getElementById('btn-pdf')

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

        btnGerar.textContent = '⏳ Identificando cômodos...'
        btnGerar.disabled    = true
        btnGerar.style.backgroundColor = '#166a34'

        const formData = new FormData()
        fotosArquivos.forEach(f => formData.append('fotos', f))

        const contexto = document.getElementById('contexto').value
        if (contexto.trim()) formData.append('contexto', contexto)

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

            document.getElementById('etapa-upload').style.display    = 'none'
            document.getElementById('etapa-validacao').style.display = 'flex'

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

    // ─── ETAPA 2: Confirmar todos e gerar laudo ─────────────
    btnConfirmar.addEventListener('click', function() {

        comodosPorFoto.forEach(function(item) {
            if (!item.confirmado) confirmarFoto(item.index)
        })

        btnConfirmar.textContent = '⏳ Gerando laudo...'
        btnConfirmar.disabled    = true

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

        // Salva o laudo no banco e guarda o ID
        const endereco = document.getElementById('endereco').value || 'Endereço não informado'
        fetch('http://127.0.0.1:5000/salvar-laudo', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({ laudo: laudoAtual, endereco: endereco })
        })
        .then(r => r.json())
        .then(function(dados) {
            if (dados.laudo_id) {
                window.laudoIdAtual = dados.laudo_id
            }
        })

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

        const formData = new FormData()
        formData.append('laudo', laudoAtual)
        formData.append('comodos', JSON.stringify(comodosPorFoto.map(c => c.comodo)))
        fotosArquivos.forEach(f => formData.append('fotos', f))

        if (window.laudoIdAtual) {
            formData.append('laudo_id', window.laudoIdAtual)
        }

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

}) // fecha DOMContentLoaded