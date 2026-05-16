from google import genai
from google.genai import types
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from dotenv import load_dotenv
from PIL import Image as PILImage
import os, io, json, tempfile

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

PROMPT_IDENTIFICAR = """
Você é um assistente de vistoria de imóveis.

Analise cada foto enviada e identifique qual cômodo ou área do imóvel ela representa.

Responda APENAS com um JSON válido, sem texto adicional, sem markdown, sem explicações.
O JSON deve ter exatamente este formato:
{"comodos": ["Nome do Cômodo 1", "Nome do Cômodo 2", "Nome do Cômodo 3"]}

Exemplos de nomes: "Sala de Estar", "Quarto Principal", "Banheiro Social", "Cozinha", "Área de Serviço", "Varanda", "Corredor"

Se não conseguir identificar, use "Área não identificada".
A lista deve ter exatamente o mesmo número de itens que o número de fotos enviadas.
"""

PROMPT_LAUDO = """
Você é um perito técnico de vistoria de imóveis com experiência em engenharia civil e avaliação patrimonial.

Gere um laudo técnico de vistoria completo, detalhado e profissional com base nas fotos fornecidas.

REGRAS OBRIGATÓRIAS:
- Descreva apenas o que é claramente visível nas imagens
- Nunca invente materiais, marcas ou condições não visíveis
- Use terminologia técnica da construção civil
- Quando houver dúvida sobre um material, use: "aparenta ser", "requer verificação presencial" ou "não identificado com clareza nas imagens"
- Diferencie com precisão: azulejo x porcelanato x cerâmica x revestimento vinílico x papel de parede
- Diferencie: inox x cromado x escovado x pintado
- Use APENAS texto simples. NUNCA use asteriscos, hashtags ou qualquer marcação markdown.

ESTRUTURA OBRIGATÓRIA — siga exatamente este formato para cada cômodo:

NOME DO COMODO EM MAIUSCULAS

REVESTIMENTOS:
- Piso: descreva material, padrão, estado de conservação, anomalias visíveis
- Paredes: descreva revestimento, pintura, estado, anomalias
- Teto: descreva acabamento, pintura, estado, anomalias

ESQUADRIAS E VEDACOES:
- Portas: material, estado, ferragens
- Janelas: material, estado, vedação aparente
- Box/Divisórias: se houver

INSTALACOES APARENTES:
- Elétrica: tomadas, interruptores, pontos de luz visíveis
- Hidráulica: torneiras, ralos, sifões, registros visíveis
- Louças e metais: estado de conservação

ANOMALIAS IDENTIFICADAS:
- Descrição técnica, localização, possível causa e urgência: BAIXO / MEDIO / ALTO / CRITICO

ITENS QUE REQUEREM VERIFICACAO PRESENCIAL:
- Liste tudo que não foi possível avaliar pelas imagens

CLASSIFICACAO DO AMBIENTE: BOM ESTADO / REGULAR / RUIM

Após todos os cômodos, inclua:

CONCLUSAO GERAL DA VISTORIA

RESUMO EXECUTIVO:
Parágrafo técnico resumindo o estado geral.

PRINCIPAIS ANOMALIAS:
- Liste as anomalias mais relevantes

RECOMENDACOES TECNICAS:
- Liste ações recomendadas em ordem de prioridade

CLASSIFICACAO GERAL: APROVADO / APROVADO COM RESSALVAS / REPROVADO
"""

@app.route('/identificar-comodos', methods=['POST'])
def identificar_comodos():
    if 'fotos' not in request.files:
        return jsonify({'erro': 'Nenhuma foto recebida'}), 400

    fotos = request.files.getlist('fotos')
    conteudo = [PROMPT_IDENTIFICAR]

    for foto in fotos:
        dados = foto.read()
        imagem = types.Part.from_bytes(data=dados, mime_type=foto.content_type)
        conteudo.append(imagem)

    resposta = client.models.generate_content(model='gemini-2.5-flash', contents=conteudo)
    texto = resposta.text.strip().replace('```json', '').replace('```', '').strip()

    try:
        return jsonify(json.loads(texto))
    except:
        return jsonify({'comodos': [f'Ambiente {i+1}' for i in range(len(fotos))]})


@app.route('/gerar-laudo', methods=['POST'])
def gerar_laudo():
    if 'fotos' not in request.files:
        return jsonify({'erro': 'Nenhuma foto recebida'}), 400

    fotos    = request.files.getlist('fotos')
    comodos  = json.loads(request.form.get('comodos', '[]'))
    contexto = request.form.get('contexto', '')

    prompt_final = PROMPT_LAUDO
    if contexto:
        prompt_final += f"\n\nInformações adicionais: {contexto}"

    conteudo = [prompt_final]
    for i, foto in enumerate(fotos):
        nome = comodos[i] if i < len(comodos) else f'Ambiente {i+1}'
        conteudo.append(f'\nCOMODO: {nome.upper()}\n')
        dados = foto.read()
        conteudo.append(types.Part.from_bytes(data=dados, mime_type=foto.content_type))

    resposta = client.models.generate_content(model='gemini-2.5-flash', contents=conteudo)
    return jsonify({'laudo': resposta.text})


@app.route('/revisar-laudo', methods=['POST'])
def revisar_laudo():
    dados       = request.get_json()
    laudo_atual = dados.get('laudo_atual', '')
    pedido      = dados.get('pedido', '')

    if not laudo_atual or not pedido:
        return jsonify({'erro': 'Dados incompletos'}), 400

    prompt = f"""Você é um perito de vistoria de imóveis.
Aplique APENAS a alteração solicitada no laudo abaixo, mantendo o restante exatamente igual.
Use apenas texto simples sem markdown.

LAUDO ATUAL:
{laudo_atual}

ALTERAÇÃO SOLICITADA:
{pedido}

Retorne o laudo completo e atualizado."""

    resposta = client.models.generate_content(model='gemini-2.5-flash', contents=[prompt])
    return jsonify({'laudo': resposta.text})


@app.route('/gerar-pdf', methods=['POST'])
def gerar_pdf():
    laudo   = request.form.get('laudo', '')
    comodos = json.loads(request.form.get('comodos', '[]'))
    fotos   = request.files.getlist('fotos')

    if not laudo:
        return jsonify({'erro': 'Laudo vazio'}), 400

    # Salva fotos corrigindo orientação EXIF
    fotos_temp = []
    for foto in fotos:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        try:
            img = PILImage.open(foto)
            exif = img._getexif()
            if exif:
                orientacao = exif.get(274)
                rotacoes = {3: 180, 6: 270, 8: 90}
                if orientacao in rotacoes:
                    img = img.rotate(rotacoes[orientacao], expand=True)
            img.save(tmp.name, 'JPEG')
        except:
            foto.seek(0)
            foto.save(tmp.name)
        fotos_temp.append(tmp.name)

    # Agrupa fotos por cômodo
    grupos = {}
    for i, caminho in enumerate(fotos_temp):
        nome = comodos[i] if i < len(comodos) else f'Ambiente {i+1}'
        grupos.setdefault(nome, []).append(caminho)

    # Parser do laudo — divide em seções
    comodos_upper = [c.upper() for c in comodos]
    secoes_laudo  = {}
    secao_atual   = None
    linhas_secao  = []

    SECOES_CONTEUDO = [
        'REVESTIMENTOS:', 'ESQUADRIAS E VEDACOES:', 'INSTALACOES APARENTES:',
        'ANOMALIAS IDENTIFICADAS:', 'ITENS QUE REQUEREM VERIFICACAO PRESENCIAL:',
        'CLASSIFICACAO DO AMBIENTE:',
        'RESUMO EXECUTIVO:', 'PRINCIPAIS ANOMALIAS:', 'RECOMENDACOES TECNICAS:',
        'CLASSIFICACAO GERAL:'
    ]

    MARCADORES_CONCLUSAO = [
        'CONCLUSAO GERAL', 'CONCLUSÃO GERAL', 'CONCLUSAO FINAL',
        'CONCLUSÃO FINAL', 'CONSIDERACOES FINAIS', 'CONSIDERAÇÕES FINAIS'
    ]

    for linha in laudo.split('\n'):
        l = linha.strip().replace('**','').replace('*','').replace('##','').replace('#','')

        if not l:
            if secao_atual is not None and linhas_secao:
                secoes_laudo.setdefault(secao_atual, []).extend(linhas_secao)
                linhas_secao = []
                # Adiciona linha em branco para preservar formatação
                secoes_laudo.setdefault(secao_atual, []).append('')
            continue

        l_upper = l.upper()

        eh_conclusao = any(m in l_upper for m in MARCADORES_CONCLUSAO)
        # Evita falso positivo: linhas com '-' nunca são cabeçalho
        eh_comodo = (
            not l.startswith('-') and
            not l.startswith('•') and
            any(c in l_upper or l_upper in c for c in comodos_upper)
        )
        eh_secao_conteudo = any(l_upper.startswith(s) for s in SECOES_CONTEUDO)
        eh_titulo = (
            l.isupper() and len(l) > 3 and
            not l.startswith('-') and not l.startswith('•') and
            not eh_secao_conteudo
        )

        # Depois da conclusão, não quebra mais em seções
        em_conclusao = secao_atual == 'CONCLUSAO GERAL'

        if not em_conclusao and (eh_conclusao or eh_comodo or eh_titulo):
            if secao_atual is not None and linhas_secao:
                secoes_laudo.setdefault(secao_atual, []).extend(linhas_secao)
                linhas_secao = []
            secao_atual = 'CONCLUSAO GERAL' if eh_conclusao else l
        else:
            if secao_atual is not None:
                linhas_secao.append(l)

    if secao_atual is not None and linhas_secao:
        secoes_laudo.setdefault(secao_atual, []).extend(linhas_secao)

    # DEBUG
    print("\n=== DEBUG PDF ===")
    print("CÔMODOS:", comodos)
    print("SEÇÕES:", list(secoes_laudo.keys()))
    print("=================\n")
    for chave in secoes_laudo.keys():
        if 'CONCLUS' in chave.upper():
            print("CONCLUSAO ENCONTRADA:", chave)
            break
    else:
        print("CONCLUSAO NAO ENCONTRADA — chaves disponíveis:", list(secoes_laudo.keys()))



    # Monta o PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    AZUL  = colors.HexColor("#1A2C4E")
    AZUL2 = colors.HexColor("#2563EB")
    VERDE = colors.HexColor("#16a34a")
    VCLR  = colors.HexColor("#22c55e")
    CINZA = colors.HexColor("#374151")
    CINZL = colors.HexColor("#64748b")
    BRNCO = colors.white
    VERM  = colors.HexColor("#dc2626")
    AMRLO = colors.HexColor("#d97706")

    def E(name, **kw):
        b = dict(fontName='Helvetica', fontSize=10, textColor=CINZA, leading=16)
        b.update(kw)
        return ParagraphStyle(name, **b)

    eH1  = E('H1', fontSize=18, fontName='Helvetica-Bold', textColor=AZUL,  alignment=TA_CENTER, spaceAfter=4)
    eCOM = E('COM', fontSize=13, fontName='Helvetica-Bold', textColor=BRNCO, alignment=TA_LEFT)
    eSEC = E('SEC', fontSize=10, fontName='Helvetica-Bold', textColor=AZUL2, spaceAfter=4, spaceBefore=10)
    eITM = E('ITM', leftIndent=15, spaceAfter=3)
    eCRP = E('CRP', alignment=TA_JUSTIFY, spaceAfter=6)
    eALT = E('ALT', leftIndent=15, spaceAfter=3, textColor=VERM)
    eMED = E('MED', leftIndent=15, spaceAfter=3, textColor=AMRLO)
    eCON = E('CON', fontSize=11, fontName='Helvetica-Bold', textColor=VERDE, spaceAfter=6, spaceBefore=8)
    eRDP = E('RDP', fontSize=8, textColor=CINZL, alignment=TA_CENTER)

    def cabecalho_bloco(texto):
        t = Table([[Paragraph(texto, eCOM)]], colWidths=[17*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), AZUL),
            ('TOPPADDING',    (0,0),(-1,-1), 10),
            ('BOTTOMPADDING', (0,0),(-1,-1), 10),
            ('LEFTPADDING',   (0,0),(-1,-1), 14),
            ('RIGHTPADDING',  (0,0),(-1,-1), 14),
        ]))
        return t

    def renderizar_linhas(linhas):
        for l in linhas:
            if not l.strip():
                story.append(Spacer(1, 0.1*cm))
            elif any(l.upper().startswith(s) for s in [
                'REVESTIMENTO', 'ESQUADRIA', 'INSTALAC', 'ANOMALIA',
                'ITENS QUE', 'CLASSIFICAC', 'RESUMO', 'PRINCIPAL', 'RECOMENDAC'
            ]):
                story.append(Paragraph(l, eSEC))
                story.append(HRFlowable(width="100%", thickness=0.3,
                             color=colors.HexColor("#e2e8f0"), spaceAfter=4))
            elif 'ALTO' in l.upper() or 'CRITICO' in l.upper():
                story.append(Paragraph('⚠ ' + l.lstrip('-•').strip(), eALT))
            elif 'MEDIO' in l.upper() or 'MÉDIO' in l.upper():
                story.append(Paragraph('⚡ ' + l.lstrip('-•').strip(), eMED))
            elif l.startswith('-') or l.startswith('•'):
                story.append(Paragraph('• ' + l.lstrip('-•').strip(), eITM))
            elif 'APROVADO' in l.upper() or 'REPROVADO' in l.upper():
                story.append(Paragraph(l, eCON))
            elif l.isupper() and len(l) > 3:
                story.append(Paragraph(l, eSEC))
            else:
                story.append(Paragraph(l, eCRP))

    story = []

    # Logo
    logo_path = os.path.join(os.path.dirname(__file__), 'logo completa 2.png')
    try:
        story.append(RLImage(logo_path, width=7*cm, height=3.5*cm))
    except:
        pass

    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("LAUDO DE VISTORIA", eH1))
    story.append(HRFlowable(width="100%", thickness=1.5, color=VCLR, spaceAfter=16))

    comodos_vistos = set()

    for nome_comodo, caminhos in grupos.items():
        if nome_comodo in comodos_vistos:
            continue
        comodos_vistos.add(nome_comodo)

        story.append(cabecalho_bloco(nome_comodo.upper()))
        story.append(Spacer(1, 0.3*cm))

        # Fotos em grid
        imgs = []
        for c in caminhos:
            try:
                imgs.append(RLImage(c, width=7.5*cm, height=5.5*cm))
            except:
                pass

        for i in range(0, len(imgs), 2):
            par = imgs[i:i+2]
            if len(par) == 1:
                par.append(Spacer(7.5*cm, 5.5*cm))
            t = Table([par], colWidths=[8.25*cm, 8.25*cm])
            t.setStyle(TableStyle([
                ('ALIGN',        (0,0),(-1,-1), 'CENTER'),
                ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
                ('LEFTPADDING',  (0,0),(-1,-1), 4),
                ('RIGHTPADDING', (0,0),(-1,-1), 4),
                ('BOTTOMPADDING',(0,0),(-1,-1), 8),
            ]))
            story.append(t)

        story.append(Spacer(1, 0.3*cm))

        # Texto da análise
        encontrou = False
        for chave, linhas in secoes_laudo.items():
            if (nome_comodo.upper() in chave.upper() or
                chave.upper() in nome_comodo.upper()):
                renderizar_linhas(linhas)
                encontrou = True
                break

        if not encontrou:
            story.append(Paragraph('Análise não localizada para este cômodo.', eCRP))

        story.append(Spacer(1, 0.6*cm))

    # Conclusão
    story.append(HRFlowable(width="100%", thickness=1.5, color=VCLR, spaceAfter=12))
    story.append(cabecalho_bloco('CONCLUSÃO GERAL DA VISTORIA'))
    story.append(Spacer(1, 0.4*cm))

    for chave, linhas in secoes_laudo.items():
        if 'CONCLUS' in chave.upper() or 'CONSIDERAC' in chave.upper():
            print("RENDERIZANDO CONCLUSAO — linhas:", len(linhas))
            for l in linhas:
                print("  LINHA:", repr(l[:80]))
            renderizar_linhas(linhas)
            break
    else:
        print("CONCLUSAO NAO RENDERIZADA")

    # Rodapé
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                 color=colors.HexColor("#94a3b8"), spaceAfter=6))
    story.append(Paragraph(
        "VistorIA — Laudos inteligentes para o mercado imobiliário — 2026", eRDP))

    doc.build(story)

    for c in fotos_temp:
        try:
            os.unlink(c)
        except:
            pass

    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf',
                     as_attachment=True,
                     download_name='laudo_vistoria.pdf')


if __name__ == '__main__':
    app.run(debug=True, port=5000)