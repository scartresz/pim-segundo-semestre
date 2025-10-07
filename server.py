from flask import Flask, request, jsonify
import os
import json
import hashlib
import webbrowser 
import google.genai as genai 
from functools import wraps
from datetime import datetime

import ctypes
import os 

DLL_PATH = os.path.join(os.getcwd(), 'laelaelaas.dll') 

try:
    laelaelaas_dll = ctypes.CDLL(DLL_PATH)
    
    laelaelaas_dll.SomeFunction.restype = ctypes.c_double 
    laelaelaas_dll.SomeFunction.argtypes = [
        ctypes.POINTER(ctypes.c_double), 
        ctypes.c_int
    ]
    
    DLL_CARREGADO_COM_SUCESSO = True
    print(f"DLL '{os.path.basename(DLL_PATH)}' carregado com sucesso.")

except Exception as e:
    laelaelaas_dll = None
    DLL_CARREGADO_COM_SUCESSO = False
    print(f"AVISO: Não foi possível carregar aelaelaas.dll. O cálculo de média será feito em Python. Erro: {e}")



app = Flask(__name__)

DATABASE_FILE = "dados.json"

PESO_NP1 = 0.35
PESO_NP2 = 0.35
PESO_ATIVIDADES = 0.30


def carregar_dados():
    default_data = {"alunos": {}, "professores": {}, "disciplinas": {}, "turmas": {}}
    
    if os.path.exists(DATABASE_FILE) and os.path.getsize(DATABASE_FILE) > 0:
        try:
            with open(DATABASE_FILE, "r", encoding="utf-8") as arquivo:
                data = json.load(arquivo)
                return data if data else default_data 
        except json.JSONDecodeError:
            print("Aviso: Arquivo de dados JSON corrompido. Inicializando com estrutura padrão.")
        except Exception as e:
            print(f"Erro ao carregar dados: {e}")

    return default_data

def salvar_dados(dados):
    try:
        with open(DATABASE_FILE, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"ERRO CRÍTICO ao salvar dados: {e}")

def hash_senha(senha):
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.json:
            return jsonify({"status": "erro", "mensagem": "Requisição inválida. Nenhum dado JSON recebido."}), 400
        return f(*args, **kwargs)
    return decorated_function


def calcular_nota_final(ra, global_disc_key, dados):
    
    disc_data = dados["disciplinas"].get(global_disc_key)
    if not disc_data:
        print(f"Erro: Disciplina {global_disc_key} não encontrada.")
        return 
        
    disc_name = disc_data.get('nome') 
    turma = disc_data.get('turma')

    if not disc_name:
        disc_name = global_disc_key.split('_')[0] if '_' in global_disc_key else global_disc_key
        disc_data['nome'] = disc_name 

    atividades_disc = disc_data.get("atividades", {})
    notas_atividades_aluno = []
    
    for info_ativ in atividades_disc.values():
        nota = info_ativ.get("notas", {}).get(ra)
        notas_atividades_aluno.append(nota if nota is not None else 0.0)

    num_atividades_cadastradas = len(notas_atividades_aluno)
    
    if num_atividades_cadastradas > 0:
        
        if DLL_CARREGADO_COM_SUCESSO:
            try:
                array_type = ctypes.c_double * num_atividades_cadastradas
                c_array = array_type(*notas_atividades_aluno)
                
                media_atividades = laelaelaas_dll.SomeFunction(c_array, num_atividades_cadastradas)
                print(f"[C-DLL SUCESSO] Média das atividades para {ra} calculada em C: {media_atividades}")
                
            except Exception as e:
                soma_notas = sum(notas_atividades_aluno)
                media_atividades = soma_notas / num_atividades_cadastradas
                print(f"[FALLBACK PY] ERRO de execução no DLL para {ra}. Usando Python. Detalhe: {e}")

        else:
            soma_notas = sum(notas_atividades_aluno)
            media_atividades = soma_notas / num_atividades_cadastradas
            print(f"[FALLBACK PY] DLL não estava carregado. Usando Python para {ra}: {media_atividades}")
    
    else:
        media_atividades = 0.0
        print(f"[CÁLCULO] Nenhuma atividade. Média = 0.0")
    
    notas_aluno = dados["alunos"].get(ra, {}).get("notas", {}).get(disc_name, {})
    
    np1 = notas_aluno.get("NP1", 0.0) 
    np2 = notas_aluno.get("NP2", 0.0)
    
    nota_final = (np1 * PESO_NP1) + \
                 (np2 * PESO_NP2) + \
                 (media_atividades * PESO_ATIVIDADES)

    if disc_name not in dados["alunos"][ra]["notas"]:
         dados["alunos"][ra]["notas"][disc_name] = {}

    dados["alunos"][ra]["notas"][disc_name]["ATIVIDADES_MEDIA"] = round(media_atividades, 2)
    dados["alunos"][ra]["notas"][disc_name]["NOTA_FINAL"] = round(nota_final, 2)
    
    if turma in dados["turmas"] and ra in dados["turmas"][turma]["alunos"]:
        if disc_name not in dados["turmas"][turma]["alunos"][ra]["notas"]:
            dados["turmas"][turma]["alunos"][ra]["notas"][disc_name] = {}
            
        dados["turmas"][turma]["alunos"][ra]["notas"][disc_name]["ATIVIDADES_MEDIA"] = round(media_atividades, 2)
        dados["turmas"][turma]["alunos"][ra]["notas"][disc_name]["NOTA_FINAL"] = round(nota_final, 2)


@app.route('/admin/get_listas', methods=['GET'])
def admin_get_listas():
    dados = carregar_dados()
    
    professores = [{"cpf": cpf, "nome": info["nome"]} for cpf, info in dados["professores"].items()]
    
    return jsonify({
        "status": "sucesso", 
        "turmas": list(dados["turmas"].keys()),
        "professores": professores
    })

@app.route('/admin/cadastrar', methods=['POST'])
@login_required
def admin_cadastrar():
    dados = carregar_dados()
    payload = request.json
    entidade = payload.get("entidade")
    
    if entidade == "turma":
        nome_turma = payload.get("nome_turma", "").upper().strip()
        if not nome_turma:
            return jsonify({"status": "erro", "mensagem": "Nome da turma não pode ser vazio."})
            
        if nome_turma in dados["turmas"]:
            return jsonify({"status": "erro", "mensagem": "Essa turma já está cadastrada!"})
            
        dados["turmas"][nome_turma] = {"disciplinas": {}, "alunos": {}, "presenca": {}}
        salvar_dados(dados)
        return jsonify({"status": "sucesso", "mensagem": f"Turma '{nome_turma}' cadastrada com sucesso!"})

    elif entidade == "professor":
        cpf = payload.get("cpf", "").strip()
        nome = payload.get("nome", "").strip()
        senha = payload.get("senha", "")
        
        if cpf in dados["professores"]:
            return jsonify({"status": "erro", "mensagem": "Professor já cadastrado!"})
            
        dados["professores"][cpf] = {"nome": nome, "senha": hash_senha(senha)}
        salvar_dados(dados)
        return jsonify({"status": "sucesso", "mensagem": f"Professor '{nome}' cadastrado com sucesso!"})

    elif entidade == "disciplina":
        nome_disc = payload.get("nome_disciplina", "").upper().strip()
        turma = payload.get("turma", "").upper().strip()
        cpf_prof = payload.get("cpf_professor", "").strip()
        
        if not all([nome_disc, turma, cpf_prof]):
             return jsonify({"status": "erro", "mensagem": "Dados de disciplina incompletos."})
        
        global_disc_key = f"{nome_disc}_{turma}"
        
        if global_disc_key in dados["disciplinas"]:
            return jsonify({"status": "erro", "mensagem": f"Disciplina '{nome_disc}' já existe na turma '{turma}'!"})
            
        info_prof = dados["professores"].get(cpf_prof)
        if not info_prof:
             return jsonify({"status": "erro", "mensagem": "Professor não encontrado."})

        dados["disciplinas"][global_disc_key] = {
            "nome": nome_disc, 
            "professor": {"cpf": cpf_prof, "nome": info_prof["nome"]},
            "turma": turma,
            "atividades": {},
        }
        dados["turmas"][turma]["disciplinas"][global_disc_key] = {
            "nome": nome_disc, 
            "professor": {"cpf": cpf_prof, "nome": info_prof["nome"]},
            "atividades": {}
        }
        salvar_dados(dados)
        return jsonify({"status": "sucesso", "mensagem": f"Disciplina '{nome_disc}' cadastrada na turma '{turma}' com o professor '{info_prof['nome']}'."})

    elif entidade == "aluno":
        ra = payload.get("ra", "").upper().strip()
        nome = payload.get("nome", "").upper().strip()
        senha = payload.get("senha", "")
        turma = payload.get("turma", "").upper().strip()
        
        if ra in dados["alunos"]:
            return jsonify({"status": "erro", "mensagem": "Aluno já cadastrado!"})
            
        if turma not in dados["turmas"]:
             return jsonify({"status": "erro", "mensagem": "Turma não encontrada."})

        aluno_data = {
            "nome": nome,
            "senha": hash_senha(senha),
            "turma": turma,
            "faltas": {}, 
            "notas": {}, 
            "atividades_enviadas": {}
        }
        
        dados["alunos"][ra] = aluno_data
        
        dados["turmas"][turma]["alunos"][ra] = {k: aluno_data[k] for k in ["nome", "faltas", "notas", "atividades_enviadas"]}

        salvar_dados(dados)
        return jsonify({"status": "sucesso", "mensagem": f"Aluno '{nome}' cadastrado na turma '{turma}'."})

    else:
        return jsonify({"status": "erro", "mensagem": "Entidade de cadastro inválida."})

@app.route('/login', methods=['POST'])
@login_required
def login_route():
    payload = request.json
    user_type = payload.get("user_type")
    identifier = payload.get("identifier")
    password = payload.get("password")
    
    if user_type == "administrador":
        if identifier == "admin" and password == "admin123":
            return jsonify({
                "status": "sucesso", 
                "user_id": "admin",
                "nome": "ADMINISTRADOR",
                "mensagem": "Acesso de administrador concedido."
            })
        else:
            return jsonify({"status": "erro", "mensagem": "Acesso negado!"})

    dados = carregar_dados()
    
    if user_type == "professor":
        cpf = identifier.strip()
        if cpf not in dados["professores"]:
            return jsonify({"status": "erro", "mensagem": "CPF não encontrado! Solicite seu cadastro ao Administrador."})
        if dados["professores"][cpf]["senha"] != hash_senha(password):
            return jsonify({"status": "erro", "mensagem": "Senha incorreta!"})
        
        nome = dados["professores"][cpf]["nome"]
        disciplinas_do_prof = {}
        
        for global_key, info in dados["disciplinas"].items():
            if isinstance(info, dict) and info.get("professor", {}).get("cpf") == cpf:
                disciplinas_do_prof[global_key] = {
                    "nome": info.get("nome"), 
                    "turma": info.get("turma")
                }
                
        return jsonify({
            "status": "sucesso", 
            "user_id": cpf,
            "nome": nome,
            "disciplinas": disciplinas_do_prof
        })

    elif user_type == "aluno":
        ra = identifier.upper().strip()
        if ra not in dados["alunos"]:
            return jsonify({"status": "erro", "mensagem": "RA não encontrado! Solicite seu cadastro ao Administrador."})
        if dados["alunos"][ra]["senha"] != hash_senha(password):
            return jsonify({"status": "erro", "mensagem": "Senha incorreta!"})
        
        aluno = dados["alunos"][ra]
        return jsonify({
            "status": "sucesso", 
            "user_id": ra,
            "ra": ra, 
            "nome": aluno["nome"],
            "turma": aluno["turma"]
        })

    return jsonify({"status": "erro", "mensagem": "Tipo de usuário inválido."})


@app.route('/professor/disciplina/menu_data', methods=['POST'])
@login_required
def professor_disciplina_menu_data():
    payload = request.json
    global_disc_key = payload.get('global_disc_key')
    dados = carregar_dados()

    disc_data = dados["disciplinas"].get(global_disc_key)
    if not disc_data:
        return jsonify({"status": "erro", "mensagem": "Disciplina não encontrada."})

    turma_nome = disc_data.get("turma")
    turma_data = dados["turmas"].get(turma_nome, {})
    
    atividades_disc = disc_data.get("atividades", {})
    
    atividades_list = list(atividades_disc.keys())
    
    disc_name = disc_data.get("nome")
    if not disc_name:
        disc_name = global_disc_key.split('_')[0] if '_' in global_disc_key else global_disc_key

    return jsonify({
        "status": "sucesso",
        "nome_disciplina": disc_name,
        "turma": turma_nome,
        "alunos_count": len(turma_data.get("alunos", {})),
        "atividades_count": len(atividades_list),
        "atividades_list": atividades_list
    })

@app.route('/professor/lista_chamada', methods=['POST'])
@login_required
def professor_lista_chamada():
    payload = request.json
    global_disc_key = payload.get('global_disc_key')
    ra_faltosos = payload.get('ra_faltosos', [])
    dados = carregar_dados()
    
    disc_data = dados["disciplinas"].get(global_disc_key)
    if not disc_data:
        return jsonify({"status": "erro", "mensagem": "Disciplina não encontrada."})
    
    turma = disc_data.get("turma")
    
    hoje = datetime.now().strftime("%d/%m/%Y")
    
    for ra in ra_faltosos:
        
        if ra in dados["alunos"]:
            if isinstance(dados["alunos"][ra].get("faltas"), int):
                 dados["alunos"][ra]["faltas"] = {}
                 
            dados["alunos"][ra]["faltas"][hoje] = global_disc_key
             
        if ra in dados["turmas"][turma]["alunos"]:
             if isinstance(dados["turmas"][turma]["alunos"][ra].get("faltas"), int):
                dados["turmas"][turma]["alunos"][ra]["faltas"] = {}
                
             dados["turmas"][turma]["alunos"][ra]["faltas"][hoje] = global_disc_key
             
    salvar_dados(dados)
    return jsonify({"status": "sucesso", "mensagem": "Chamada registrada!"})

@app.route('/professor/gerar_topicos_ia', methods=['POST'])
@login_required
def professor_gerar_topicos_ia():
    payload = request.json
    global_disc_key = payload.get('global_disc_key')
    tema = payload.get('tema')
    dados = carregar_dados()
    
    disciplina = dados["disciplinas"].get(global_disc_key, {}).get("nome")
    if not disciplina:
        disciplina = global_disc_key.split('_')[0] if '_' in global_disc_key else global_disc_key

    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("[ERRO DE CHAVE] A chave GEMINI_API_KEY não está definida no ambiente do servidor.")
            
        client = genai.Client(api_key=api_key) 
        
        prompt = f"Gere 5 tópicos de aula curtos e didáticos sobre o tema '{tema}' para a disciplina de {disciplina}. Liste apenas os 5 tópicos numerados."
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return jsonify({"status": "sucesso", "conteudo": response.text})
        
    except Exception as e:
        return jsonify({
            "status": "erro", 
            "mensagem": f"[ERRO NA IA]: Não foi possível gerar o conteúdo. Detalhe: {e}"
        })

@app.route('/professor/enviar_atividade', methods=['POST'])
@login_required
def professor_enviar_atividade():
    payload = request.json
    global_disc_key = payload.get('global_disc_key')
    nome_atividade = payload.get("nome_atividade")
    link_atividade = payload.get("link_atividade")
    
    dados = carregar_dados()
    disc_data = dados["disciplinas"].get(global_disc_key)
    
    if not disc_data:
        return jsonify({"status": "erro", "mensagem": "Disciplina não encontrada."})
    
    turma = disc_data.get("turma")
    
    atividades_disc = disc_data.get("atividades", {})
    num_atividades = len(atividades_disc)

    if num_atividades >= 10:
        return jsonify({"status": "erro", "mensagem": "Limite de 10 atividades por disciplina atingido."})

    atividade_data = {
        "link": link_atividade, 
        "respostas": {},
        "notas": {}
    }
    
    dados["disciplinas"][global_disc_key]["atividades"][nome_atividade] = atividade_data
    dados["turmas"][turma]["disciplinas"][global_disc_key]["atividades"][nome_atividade] = atividade_data
    
    salvar_dados(dados)
    return jsonify({
        "status": "sucesso", 
        "mensagem": f"Atividade '{nome_atividade}' enviada. Esta é a atividade número {num_atividades + 1} de 10."
    })

@app.route('/professor/lancar_np_grades', methods=['POST'])
@login_required
def professor_lancar_np_grades():
    payload = request.json
    global_disc_key = payload.get('global_disc_key')
    tipo_nota = payload.get("tipo_nota")
    lancamentos = payload.get("lancamentos", {}) 
    
    dados = carregar_dados()
    disc_data = dados["disciplinas"].get(global_disc_key)
    
    if not disc_data:
        return jsonify({"status": "erro", "mensagem": "Disciplina não encontrada."})
    
    disc_name = disc_data.get("nome")
    turma = disc_data.get("turma")
    
    if not disc_name:
        disc_name = global_disc_key.split('_')[0] if '_' in global_disc_key else global_disc_key
    
    for ra, nota_float in lancamentos.items():
        
        if disc_name not in dados["alunos"][ra]["notas"]:
            dados["alunos"][ra]["notas"][disc_name] = {}
        dados["alunos"][ra]["notas"][disc_name][tipo_nota] = nota_float
        
        if disc_name not in dados["turmas"][turma]["alunos"][ra]["notas"]:
            dados["turmas"][turma]["alunos"][ra]["notas"][disc_name] = {}
        dados["turmas"][turma]["alunos"][ra]["notas"][disc_name][tipo_nota] = nota_float
        
    salvar_dados(dados)
    return jsonify({"status": "sucesso", "mensagem": f"Lançamento de {tipo_nota} concluído!"})

@app.route('/professor/get_atividades_entregues', methods=['POST'])
@login_required
def professor_get_atividades_entregues():
    payload = request.json
    global_disc_key = payload.get('global_disc_key')
    nome_atividade = payload.get('nome_atividade')
    dados = carregar_dados()
    
    disc_data = dados["disciplinas"].get(global_disc_key)
    if not disc_data:
        return jsonify({"status": "erro", "mensagem": "Disciplina não encontrada."})
        
    turma = disc_data.get("turma")
    atividade = dados["turmas"][turma]["disciplinas"][global_disc_key]["atividades"].get(nome_atividade)
    
    if not atividade:
        return jsonify({"status": "erro", "mensagem": "Atividade não encontrada."})
        
    respostas = atividade.get("respostas", {})
    notas_atividade = atividade.get("notas", {})
    alunos_turma = dados["turmas"][turma]["alunos"]
    
    entregas_listadas = []

    for ra, link in respostas.items():
        aluno_nome = alunos_turma.get(ra, {}).get("nome", ra)
        nota_atual = notas_atividade.get(ra, "PENDENTE")
        
        entregas_listadas.append({
            "ra": ra, 
            "nome": aluno_nome, 
            "link": link, 
            "nota_atual": nota_atual
        })

    return jsonify({"status": "sucesso", "entregas": entregas_listadas})

@app.route('/professor/atribuir_nota_atividade', methods=['POST'])
@login_required
def professor_atribuir_nota_atividade():
    payload = request.json
    global_disc_key = payload.get('global_disc_key')
    nome_atividade = payload.get('nome_atividade')
    ra = payload.get('ra')
    nota_float = payload.get('nota')
    
    dados = carregar_dados()
    disc_data = dados["disciplinas"].get(global_disc_key)
    
    if not disc_data:
        return jsonify({"status": "erro", "mensagem": "Disciplina não encontrada."})
        
    turma = disc_data.get("turma")

    dados["disciplinas"][global_disc_key]["atividades"][nome_atividade]["notas"][ra] = nota_float
    dados["turmas"][turma]["disciplinas"][global_disc_key]["atividades"][nome_atividade]["notas"][ra] = nota_float

    salvar_dados(dados)
    return jsonify({"status": "sucesso", "mensagem": f"Nota {nota_float} salva para o aluno {ra}."})

@app.route('/professor/get_notas_faltas_turma', methods=['POST'])
@login_required
def professor_get_notas_faltas_turma():
    payload = request.json
    global_disc_key = payload.get('global_disc_key')
    dados = carregar_dados()
    
    disc_data = dados["disciplinas"].get(global_disc_key)
    if not disc_data:
        return jsonify({"status": "erro", "mensagem": "Disciplina não encontrada."})
        
    disc_name = disc_data.get("nome")
    turma = disc_data.get("turma")
    
    if not disc_name:
        disc_name = global_disc_key.split('_')[0] if '_' in global_disc_key else global_disc_key

    alunos_turma = dados["turmas"][turma]["alunos"]
    
    alunos_list = []
    
    for ra, info in alunos_turma.items():
        faltas_raw = info.get("faltas", {})
        
        if isinstance(faltas_raw, int):
            total_faltas = faltas_raw
            faltas_data = {} 
            info["faltas"] = faltas_data
            dados["alunos"][ra]["faltas"] = faltas_data 
            
            dados["turmas"][turma]["alunos"][ra]["faltas"] = faltas_data 
            
            salvar_dados(dados) 
        else:
            faltas_data = faltas_raw
            total_faltas = len(faltas_data)
        
        notas = info["notas"].get(disc_name, {})
        
        alunos_list.append({
            "ra": ra,
            "nome": info["nome"],
            "faltas_data": faltas_data, 
            "total_faltas": total_faltas, 
            "np1": notas.get("NP1", "S/D"),
            "np2": notas.get("NP2", "S/D"),
            "media_ativ": notas.get("ATIVIDADES_MEDIA", "S/D"),
            "final": notas.get("NOTA_FINAL", "S/D")
        })
        
    return jsonify({
        "status": "sucesso",
        "disciplina": disc_name,
        "turma": turma,
        "alunos": alunos_list
    })

@app.route('/professor/calcular_nota_final_turma', methods=['POST'])
@login_required
def professor_calcular_nota_final_turma():
    payload = request.json
    global_disc_key = payload.get('global_disc_key')
    dados = carregar_dados()
    
    disc_data = dados["disciplinas"].get(global_disc_key)
    if not disc_data:
        return jsonify({"status": "erro", "mensagem": "Disciplina não encontrada."})
        
    turma = disc_data.get("turma")
    alunos_turma = dados["turmas"][turma]["alunos"].keys()
    
    for ra in alunos_turma:
        calcular_nota_final(ra, global_disc_key, dados)

    salvar_dados(dados)
    return jsonify({"status": "sucesso", "mensagem": "Cálculo das notas finais do semestre concluído!"})


@app.route('/aluno/get_dados', methods=['POST'])
@login_required
def aluno_get_dados():
    payload = request.json
    ra = payload.get('ra')
    dados = carregar_dados()
    
    aluno = dados["alunos"].get(ra)
    if not aluno:
        return jsonify({"status": "erro", "mensagem": "Aluno não encontrado."})
        
    turma = aluno["turma"]
    turma_data = dados["turmas"].get(turma, {})
    disciplinas_turma = turma_data.get("disciplinas", {})
    
    atividades_disponiveis = []
    atividades_entregues = aluno.get("atividades_enviadas", {})
    
    for global_disc_key, disc_info in disciplinas_turma.items():
        disc_name = disc_info.get("nome")
        
        if not disc_name:
            disc_name = global_disc_key.split('_')[0] if '_' in global_disc_key else global_disc_key
            
        atividades = disc_info.get("atividades", {})
        
        for nome_atividade, info_ativ in atividades.items():
            
            ja_entregue = nome_atividade in atividades_entregues
            
            atividades_disponiveis.append({
                "global_disc_key": global_disc_key,
                "disciplina_nome": disc_name,
                "nome": nome_atividade,
                "link": info_ativ.get('link', 'Link Indisponível'),
                "ja_entregue": ja_entregue
            })

    faltas_raw = aluno.get("faltas", {})

    if isinstance(faltas_raw, int):
        total_faltas = faltas_raw
        faltas_data = {} 
        
        aluno["faltas"] = faltas_data 
        dados["alunos"][ra]["faltas"] = faltas_data
        
        turma_aluno_data = dados["turmas"][turma]["alunos"][ra]
        if isinstance(turma_aluno_data.get("faltas"), int):
             dados["turmas"][turma]["alunos"][ra]["faltas"] = faltas_data

        salvar_dados(dados) 
    else:
        faltas_data = faltas_raw
        total_faltas = len(faltas_data)
    
    aluno_response = {
        "status": "sucesso",
        "nome": aluno["nome"],
        "turma": turma,
        "faltas_data": faltas_data, 
        "total_faltas": total_faltas, 
        "notas": aluno["notas"],
        "atividades_disponiveis": atividades_disponiveis
    }
    
    return jsonify(aluno_response)

@app.route('/aluno/enviar_atividade', methods=['POST'])
@login_required
def aluno_enviar_atividade():
    payload = request.json
    ra = payload.get('ra')
    turma = payload.get('turma')
    global_disc_key = payload.get('global_disc_key')
    nome_atividade = payload.get('nome_atividade')
    link_resposta = payload.get('link_resposta')
    
    dados = carregar_dados()
    disc_data = dados["disciplinas"].get(global_disc_key)
    
    if not disc_data:
        return jsonify({"status": "erro", "mensagem": "Disciplina não encontrada."})

    disc_name = disc_data.get("nome")
    
    if not disc_name:
        disc_name = global_disc_key.split('_')[0] if '_' in global_disc_key else global_disc_key
    
    atividade_turma = dados["turmas"][turma]["disciplinas"][global_disc_key]["atividades"].get(nome_atividade)
    if atividade_turma:
        atividade_turma["respostas"][ra] = link_resposta
    else:
        return jsonify({"status": "erro", "mensagem": "Atividade não encontrada na turma."})
        
    dados["alunos"][ra]["atividades_enviadas"][nome_atividade] = {
        "disciplina": disc_name, 
        "resposta": link_resposta, 
        "global_disc_key": global_disc_key
    }
    
    salvar_dados(dados)
    return jsonify({"status": "sucesso", "mensagem": f"Atividade '{nome_atividade}' enviada com sucesso!"})


if __name__ == '__main__':
    print("--- SERVIDOR ESCOLAR INICIADO ---")
    print(f"Banco de Dados: {DATABASE_FILE}")
    app.run(host='0.0.0.0', port=5000, debug=True)