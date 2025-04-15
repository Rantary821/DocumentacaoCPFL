from flask import Flask, render_template, request, send_file
from datetime import datetime
import pdfkit
import os
import requests
import xml.etree.ElementTree as ET
from babel.dates import format_date
import zipfile
import io
import shutil
import subprocess

app = Flask(__name__)

# Configurações de caminhos
WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
SOFFICE_PATH = r"C:\Program Files\LibreOffice\program\soffice.exe"
config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

os.makedirs('gerados', exist_ok=True)

def converter_docx_para_pdf(input_path, output_dir):
    try:
        subprocess.run([
            SOFFICE_PATH,
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', output_dir,
            input_path
        ], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print("Erro ao converter com LibreOffice:", e)
        return False

@app.route('/')
def formulario():
    return render_template('form.html')

@app.route('/gerar', methods=['POST'])
def gerar_tudo_zip():
    # Dados do formulário
    nome = request.form['nome']
    cpf = request.form['cpf_cnpj']
    cep = request.form['cep'].replace("-", "").strip()
    numero = request.form['numero']
    endereco = request.form['endereco']
    cidade_form = request.form['cidade']
    uc = request.form['codigo_uc']
    qtd_modulos = int(request.form['mod_quantidade'])
    pot_modulo = float(request.form['mod_potencia'])
    qtd_inversores = int(request.form['inv_quantidade'])
    pot_inversor = float(request.form['inv_potencia'])
    inv_fabricante = request.form['inv_fabricante']
    inv_modelo = request.form['inv_modelo']

    # Consulta ViaCEP
    try:
        via_cep = requests.get(f'https://viacep.com.br/ws/{cep}/json/').json()
        cidade = via_cep.get("localidade", cidade_form)
        uf = via_cep.get("uf", "XX")
    except:
        cidade = cidade_form
        uf = "XX"

    cep_formatado = f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep
    endereco_completo = f"{endereco}, {numero}, {cep_formatado}"
    endereco_uc = f"{endereco}, {numero}, {cidade}-{uf} – {cep_formatado}"
    data_formatada = format_date(datetime.today(), format="d 'de' MMMM 'de' y", locale='pt_BR')
    data_local = f"{cidade}-{uf} {data_formatada}"
    potencia_modulos = round((qtd_modulos * pot_modulo) / 1000, 2)
    potencia_inversores = round((qtd_inversores * pot_inversor) / 1000, 2)
    potencia_utilizada = min(potencia_modulos, potencia_inversores)

    # Responsável técnico
    try:
        tree = ET.parse('responsavel.xml')
        root = tree.getroot()
        responsavel_nome = root.findtext('nome', 'NOME TÉCNICO')
        responsavel_email = root.findtext('email', 'email@dominio.com')
        responsavel_telefone = root.findtext('telefone', '(00) 00000-0000')
    except:
        responsavel_nome = "NOME TÉCNICO"
        responsavel_email = "email@dominio.com"
        responsavel_telefone = "(00) 00000-0000"

    logo_path = os.path.abspath("static/logo.png")

    # === GERA PROCURAÇÃO ===
    html_proc = render_template(
        "modelo_procuracao.html",
        nome=nome,
        cpf=cpf,
        endereco=endereco_completo,
        endereco_uc=endereco_uc,
        cidade=cidade,
        uc=uc,
        data=data_local,
        logo_path=logo_path
    )
    proc_path = "gerados/procuracao.pdf"
    pdfkit.from_string(html_proc, proc_path, configuration=config, options={
        'enable-local-file-access': None,
        'quiet': ''
    })

    # === GERA ANEXO E.1 ===
    template_docx = "anexo_e1_template.docx"
    temp_dir = "temp_anexo"
    os.makedirs(temp_dir, exist_ok=True)

    with zipfile.ZipFile(template_docx, 'r') as zin:
        zin.extractall(temp_dir)

    doc_xml_path = os.path.join(temp_dir, "word", "document.xml")
    with open(doc_xml_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Substituições dinâmicas
    content = content.replace("Informar nome do consumidor", nome)
    content = content.replace("000.000.000-00", cpf)
    content = content.replace("0000", uc)
    content = content.replace("Endereço do consumidor", endereco_uc)
    content = content.replace("Cidade/UF", f"{cidade}-{uf}")
    content = content.replace("55555", str(potencia_utilizada))

    content = content.replace("Fabricante: Informar", f"Fabricante: {inv_fabricante}")
    content = content.replace("Modelo: Informar", f"Modelo: {inv_modelo}")
    content = content.replace("Quantidade instalada: Informar", f"Quantidade instalada: {qtd_inversores}")
    content = content.replace("Tensão nominal de conexão à rede: Informar", "Tensão nominal de conexão à rede: 110/220")
    content = content.replace("Potência nominal de conexão à rede: Informar", f"Potência nominal de conexão à rede: {potencia_inversores} kW")

    # Marcações de checkbox
    content = content.replace("☐ 4.4", "☒ 4.4")
    content = content.replace("☐ 4.6", "☒ 4.6")
    for opcional in ["4.1", "4.2", "4.3", "4.5", "4.5.1", "4.5.2", "4.5.3"]:
        content = content.replace(f"☐ {opcional}", f"☐ {opcional}")  # mantém desmarcado

    content = content.replace("☐ Solar fotovoltaica", "☒ Solar fotovoltaica")
    content = content.replace("☐ Empregando conversor eletrônico/inversor", "☒ Empregando conversor eletrônico/inversor")
    content = content.replace("☐ Autoconsumo local", "☒ Autoconsumo local")

    # Informações finais
    content = content.replace("Informar (Descrição do Sistema de Armazenamento - “bateria”)", "")
    content = content.replace("Informar", nome, 1)
    content = content.replace("Informar", f"{responsavel_telefone} / {responsavel_email}", 1)
    content = content.replace("São José do Rio Preto-SP 14 de abril de 2025", data_local)
    content = content.replace("Inserir", "")

    with open(doc_xml_path, 'w', encoding='utf-8') as f:
        f.write(content)

    docx_editado_path = "gerados/anexo_e1_editado.docx"
    with zipfile.ZipFile(docx_editado_path, 'w') as zout:
        for root_dir, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root_dir, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zout.write(file_path, arcname)

    shutil.rmtree(temp_dir)

    pdf_e1_path = "gerados/anexo_e1_editado.pdf"
    convertido = converter_docx_para_pdf(docx_editado_path, "gerados")
    if not convertido or not os.path.exists(pdf_e1_path):
        return "Erro ao converter Anexo E.1 com LibreOffice", 500

    # === ZIP FINAL ===
    nome_cliente = nome.lower().strip().replace(" ", "_")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zipf:
        zipf.write(proc_path, arcname="procuracao.pdf")
        zipf.write(pdf_e1_path, arcname="anexo_e1.pdf")

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name=f"{nome_cliente}_cpfl.zip",
        mimetype="application/zip"
    )

if __name__ == '__main__':
    app.run(debug=True)
