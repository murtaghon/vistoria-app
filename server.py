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
import os, io, json, tempfile
 
load_dotenv()
 
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
 
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
 
# ─── Prompt de identificação de cômodos ─────────────────
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
 
# ─── Prompt de geração do laudo ─────────────────────────
PROMPT_LAUDO = """
Você é um assistente de vistoria de imóveis. Analise as fotos com cautela e descreva apenas o que é claramente visível.
 
Regras obrigatórias:
- Nunca invente ou suponha materiais, marcas ou detalhes que não estejam claramente visíveis
- Se não tiver certeza sobre um material, use: "aparenta ser", "não identificado com clareza" ou "requer verificação presencial"
- Diferencie com cuidado materiais parecidos: azulejo x papel de parede, porcelanato x cerâmica, inox x cromado
- Ralos embutidos no piso devem ser descritos como "ralo embutido" — nunca assuma o material se não estiver visível
- Descreva o que vê, não o que é comum existir naquele tipo de ambiente
 
As fotos estão organizadas por cômodo conforme indicado.
Para cada cômodo, gere uma seção com:
 
NOME DO CÔMODO EM MAIÚSCULAS
- O que está em bom estado
- O que apresenta problemas ou merece atenção
- O que requer verificação presencial
- Nível de urgência: nenhuma / baixa / média / alta
 
Ao final, escreva:
CONCLUSÃO GERAL
Classificação: 🟢 APROVADO, 🟡 APROVADO COM RESSALVAS ou 🔴 REPROVADO
"""
 
# ─── Rota 1: Identificar cômodos ────────────────────────
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
 
    resposta = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=conteudo
    )
 
    texto = resposta.text.strip()
    # Remove possível markdown
    texto = texto.replace('```json', '').replace('```', '').strip()
 
    try:
        resultado = json.loads(texto)
        return jsonify(resultado)
    except:
        # Se falhar o parse, retorna genérico
        comodos = [f'Ambiente {i+1}' for i in range(len(fotos))]
        return jsonify({'comodos': comodos})
 
# ─── Rota 2: Gerar laudo ────────────────────────────────
@app.route('/gerar-laudo', methods=['POST'])
def gerar_laudo():
 
    if 'fotos' not in request.files:
        return jsonify({'erro': 'Nenhuma foto recebida'}), 400
 
    fotos   = request.files.getlist('fotos')
    comodos = json.loads(request.form.get('comodos', '[]'))
    contexto = request.form.get('contexto', '')
 
    prompt_final = PROMPT_LAUDO
    if contexto:
        prompt_final += f"\n\nInformações adicionais: {contexto}"
 
    # Monta conteúdo agrupando foto com nome do cômodo
    conteudo = [prompt_final]
    for i, foto in enumerate(fotos):
        nome = comodos[i] if i < len(comodos) else f'Ambiente {i+1}'
        conteudo.append(f'\n--- {nome} ---')
        dados = foto.read()
        imagem = types.Part.from_bytes(data=dados, mime_type=foto.content_type)
        conteudo.append(imagem)
 
    resposta = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=conteudo
    )
 
    return jsonify({'laudo': resposta.text})
 
# ─── Rota 3: Revisar laudo ──────────────────────────────
@app.route('/revisar-laudo', methods=['POST'])
def revisar_laudo():
 
    dados       = request.get_json()
    laudo_atual = dados.get('laudo_atual', '')
    pedido      = dados.get('pedido', '')
 
    if not laudo_atual or not pedido:
        return jsonify({'erro': 'Dados incompletos'}), 400
 
    prompt_revisao = f"""
Você é um assistente de vistoria de imóveis.
 
Abaixo está um laudo técnico já gerado. O usuário quer fazer uma alteração específica.
Aplique APENAS a alteração solicitada, mantendo todo o restante exatamente igual.
 
LAUDO ATUAL:
{laudo_atual}
 
ALTERAÇÃO SOLICITADA:
{pedido}
 
Retorne o laudo completo e atualizado.
"""
 
    resposta = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[prompt_revisao]
    )
 
    return jsonify({'laudo': resposta.text})
 
# ─── Rota 4: Gerar PDF com fotos ────────────────────────
@app.route('/gerar-pdf', methods=['POST'])
def gerar_pdf():
 
    laudo   = request.form.get('laudo', '')
    comodos = json.loads(request.form.get('comodos', '[]'))
    fotos   = request.files.getlist('fotos')
 
    if not laudo:
        return jsonify({'erro': 'Laudo vazio'}), 400
 
    # Salva fotos temporariamente
    fotos_temp = []
    for foto in fotos:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        foto.save(tmp.name)
        fotos_temp.append(tmp.name)
 
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
 
    # ── Estilos ──────────────────────────────────────────
    AZUL     = colors.HexColor("#1A2C4E")
    VERDE    = colors.HexColor("#16a34a")
    CINZA    = colors.HexColor("#374151")
    VERDE_CL = colors.HexColor("#22c55e")
 
    def estilo(name, **kw):
        base = dict(fontName='Helvetica', fontSize=11,
                    textColor=CINZA, leading=18)
        base.update(kw)
        return ParagraphStyle(name, **base)
 
    e_titulo   = estilo('titulo',   fontSize=16, fontName='Helvetica-Bold',
                        textColor=VERDE, alignment=TA_CENTER, spaceAfter=8)
    e_secao    = estilo('secao',    fontSize=13, fontName='Helvetica-Bold',
                        textColor=AZUL, spaceBefore=14, spaceAfter=6)
    e_item     = estilo('item',     leftIndent=15, spaceAfter=4)
    e_corpo    = estilo('corpo',    alignment=TA_JUSTIFY, spaceAfter=6)
    e_conclusao= estilo('conclusao',fontSize=12, fontName='Helvetica-Bold',
                        textColor=VERDE, spaceBefore=12, spaceAfter=6)
    e_rodape   = estilo('rodape',   fontSize=8,  textColor=colors.HexColor("#94a3b8"),
                        alignment=TA_CENTER)
 
    story = []
 
    # ── Logo ─────────────────────────────────────────────
    logo_path = os.path.join(os.path.dirname(__file__), 'logo completa 2.png')
    try:
        logo = RLImage(logo_path, width=7*cm, height=3.5*cm)
        story.append(logo)
    except:
        pass
 
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("LAUDO DE VISTORIA", e_titulo))
    story.append(HRFlowable(width="100%", thickness=1.5,
                 color=VERDE_CL, spaceAfter=16))
 
    # ── Agrupa fotos por cômodo ───────────────────────────
    grupos = {}
    for i, caminho in enumerate(fotos_temp):
        nome = comodos[i] if i < len(comodos) else f'Ambiente {i+1}'
        grupos.setdefault(nome, []).append(caminho)
 
    # ── Divide o laudo por seções ─────────────────────────
    secoes_laudo = {}
    secao_atual  = None
    linhas_secao = []
 
    for linha in laudo.split('\n'):
        linha_limpa = linha.strip()
        linha_limpa = linha_limpa.replace('**', '').replace('*', '').replace('##', '').replace('#', '')
 
        if linha_limpa == '':
            if secao_atual and linhas_secao:
                secoes_laudo.setdefault(secao_atual, []).extend(linhas_secao)
                linhas_secao = []
            continue
 
        # Detecta cabeçalho de seção (tudo maiúsculo ou termina com :)
        eh_secao = (linha_limpa.isupper() and len(linha_limpa) > 3) or \
                   (linha_limpa.startswith('---') and linha_limpa.endswith('---'))
 
        if eh_secao:
            if secao_atual and linhas_secao:
                secoes_laudo.setdefault(secao_atual, []).extend(linhas_secao)
                linhas_secao = []
            secao_atual = linha_limpa.strip('-').strip()
        else:
            linhas_secao.append(linha_limpa)
 
    if secao_atual and linhas_secao:
        secoes_laudo.setdefault(secao_atual, []).extend(linhas_secao)
 
    # ── Monta o PDF por cômodo ────────────────────────────
    comodos_vistos = set()
 
    for nome_comodo, caminhos in grupos.items():
        if nome_comodo in comodos_vistos:
            continue
        comodos_vistos.add(nome_comodo)
 
        # Título do cômodo
        story.append(Paragraph(nome_comodo.upper(), e_secao))
        story.append(HRFlowable(width="100%", thickness=0.5,
                     color=colors.HexColor("#e2e8f0"), spaceAfter=10))
 
        # Fotos do cômodo em grid
        imagens_row = []
        for caminho in caminhos:
            try:
                img = RLImage(caminho, width=7.5*cm, height=5.5*cm)
                img.hAlign = 'CENTER'
                imagens_row.append(img)
            except:
                pass
 
        if imagens_row:
            # Máximo 2 fotos por linha
            for i in range(0, len(imagens_row), 2):
                par = imagens_row[i:i+2]
                if len(par) == 1:
                    par.append(Spacer(7.5*cm, 5.5*cm))
                t = Table([par], colWidths=[8.25*cm, 8.25*cm])
                t.setStyle(TableStyle([
                    ('ALIGN',   (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN',  (0,0), (-1,-1), 'MIDDLE'),
                    ('LEFTPADDING',  (0,0), (-1,-1), 4),
                    ('RIGHTPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING',(0,0), (-1,-1), 8),
                ]))
                story.append(t)
 
        story.append(Spacer(1, 0.3*cm))
 
        # Texto da análise — busca seção correspondente
        texto_encontrado = False
        for chave, linhas in secoes_laudo.items():
            if nome_comodo.upper() in chave.upper() or chave.upper() in nome_comodo.upper():
                for l in linhas:
                    if l.startswith('CONCLUSÃO') or l.startswith('🟢') or \
                       l.startswith('🟡') or l.startswith('🔴'):
                        story.append(Paragraph(l, e_conclusao))
                    elif l.startswith('-') or l.startswith('•'):
                        story.append(Paragraph('• ' + l.lstrip('-•').strip(), e_item))
                    elif l.endswith(':') or (l.isupper() and len(l) > 3):
                        story.append(Paragraph(l, e_secao))
                    else:
                        story.append(Paragraph(l, e_corpo))
                texto_encontrado = True
                break
 
        if not texto_encontrado:
            story.append(Paragraph('Análise não encontrada para este cômodo.', e_corpo))
 
        story.append(Spacer(1, 0.5*cm))
 
    # ── Conclusão geral ───────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1,
                 color=VERDE_CL, spaceAfter=12))
 
    for chave, linhas in secoes_laudo.items():
        if 'CONCLUS' in chave.upper():
            story.append(Paragraph('CONCLUSÃO GERAL', e_secao))
            for l in linhas:
                story.append(Paragraph(l, e_conclusao))
 
    # ── Rodapé ───────────────────────────────────────────
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                 color=colors.HexColor("#94a3b8"), spaceAfter=6))
    story.append(Paragraph("VistorIA — Laudos inteligentes para o mercado imobiliário — 2026",
                 e_rodape))
 
    doc.build(story)
 
    # Limpa arquivos temporários
    for caminho in fotos_temp:
        try:
            os.unlink(caminho)
        except:
            pass
 
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf',
                     as_attachment=True,
                     download_name='laudo_vistoria.pdf')
 
if __name__ == '__main__':
    app.run(debug=True, port=5000)
 