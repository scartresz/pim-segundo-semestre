import requests
import json
import os
import webbrowser
from datetime import datetime


SERVER_BASE_URL = "http://45.185.34.237:5000" 


def limpar_tela():
    
    pass 

def fazer_requisicao(endpoint, method='POST', data=None):
    """Função central para comunicação com o servidor Flask."""
    url = f"{SERVER_BASE_URL}{endpoint}"
    
    
    if data is not None and method == 'POST':
        data['request_time'] = datetime.now().strftime("%d/%m/%Y")

    try:
        if method == 'GET':
            response = requests.get(url, timeout=30)
        elif method == 'POST':
            response = requests.post(url, json=data, timeout=30)
        
        response.raise_for_status() 
        
        return response.json()
    
    except requests.exceptions.ConnectionError:
        print("\n[ERRO DE CONEXÃO] Não foi possível conectar ao servidor.")
        print("Verifique se o servidor está rodando e se o IP/Porta estão corretos.")
        return {"status": "erro", "mensagem": "Erro de conexão com o servidor."}
    except requests.exceptions.Timeout:
        print("\n[ERRO DE CONEXÃO] A requisição excedeu o tempo limite.")
        return {"status": "erro", "mensagem": "Tempo limite excedido."}
    except requests.exceptions.RequestException as e:
        
        print(f"\nErro HTTP {response.status_code}: {response.text[:200]}...") 
        return {"status": "erro", "mensagem": f"Erro HTTP {response.status_code}: Falha ao processar requisição."}

def desenhar_menu(menu_opcoes, titulo="MENU"):
    """Desenha o menu interativo no terminal."""
    print("\n" + "="*50)
    print(f"       {titulo.upper()}")
    print("="*50)
    for key, value in menu_opcoes.items():
        print(f"[{key}] - {value}")
    print("="*50)

def exibir_mensagem(dados_retorno):
    """Exibe mensagens de sucesso ou erro retornadas pelo servidor."""
    status = dados_retorno.get("status")
    mensagem = dados_retorno.get("mensagem", "Ação concluída.")
    
    if status == "sucesso":
        print(f"\n[SUCESSO] {mensagem}")
    elif status == "erro":
        print(f"\n[ERRO] {mensagem}")

def formatar_disciplina_menu(global_key, nome, turma):
    """Formata a exibição da disciplina no menu do professor."""
    
    if not nome:
        nome = global_key.split('_')[0] if '_' in global_key else global_key
        
    return f"{nome} (Turma: {turma})"



SESSAO = {
    "logged_in": False,
    "user_type": None,
    "user_id": None,
    "user_name": None,
    "contexto": {} 
}

def login_client(user_type):
    """Interface de login no cliente, envia credenciais para o servidor."""
    print(f"\n--- LOGIN {user_type.upper()} ---")
    identifier = input(f"{'CPF' if user_type == 'professor' else 'RA' if user_type == 'aluno' else 'Usuário'}: ").strip()
    password = input("Senha: ").strip() 
    
    payload = {
        "user_type": user_type,
        "identifier": identifier,
        "password": password
    }
    
    response = fazer_requisicao('/login', data=payload)
    
    if response and response.get("status") == "sucesso":
        SESSAO["logged_in"] = True
        SESSAO["user_type"] = user_type
        SESSAO["user_id"] = response.get("user_id")
        SESSAO["user_name"] = response.get("nome")
        
        
        if user_type == "professor":
            SESSAO["contexto"]["disciplinas"] = response.get("disciplinas", {})
        elif user_type == "aluno":
             SESSAO["contexto"]["turma"] = response.get("turma")
             
             SESSAO["contexto"]["ra"] = response.get("ra", response.get("user_id")) 
        
        print(f"Login bem-sucedido! Bem-vindo(a), {SESSAO['user_name']}.")
        return True
    else:
        exibir_mensagem(response)
        return False



def menu_administrador_client():
    """Menu Admin: gerencia cadastros."""
    while SESSAO["logged_in"]:
        menu_opcoes = {
            1: "Cadastrar Turma",
            2: "Cadastrar Professor",
            3: "Cadastrar Disciplina",
            4: "Cadastrar Aluno",
            5: "Voltar"
        }
        desenhar_menu(menu_opcoes, f"MENU ADMINISTRADOR - {SESSAO['user_name']}")
        
        try:
            opcao = input("Escolha uma opção: ").strip()
        except EOFError:
            opcao = '5'
        
        if opcao == "1":
            cadastrar_entidade("turma")
        elif opcao == "2":
            cadastrar_entidade("professor")
        elif opcao == "3":
            cadastrar_entidade("disciplina")
        elif opcao == "4":
            cadastrar_entidade("aluno")
        elif opcao == "5":
            break
        else:
            print("Opção inválida!")
            
    deslogar()

def menu_professor_client():
    """Menu Professor: Seleciona disciplina e acessa funcionalidades."""
    disciplinas = SESSAO["contexto"].get("disciplinas", {})
    
    while SESSAO["logged_in"]:
        disc_list_indexed = []
        menu_opcoes = {}
        
        
        for i, (global_key, info) in enumerate(disciplinas.items(), 1):
            disc_list_indexed.append({"global_key": global_key, "nome": info.get("nome"), "turma": info.get("turma")})
            menu_opcoes[i] = formatar_disciplina_menu(global_key, info.get("nome"), info.get("turma"))
        
        menu_opcoes[len(disc_list_indexed) + 1] = "Voltar"
        
        desenhar_menu(menu_opcoes, f"MENU PROFESSOR - {SESSAO['user_name']}")
        
        try:
            escolha = input("Escolha uma disciplina: ").strip()
            if not escolha.isdigit():
                print("Opção inválida!")
                continue
            
            escolha_int = int(escolha)
            
            if escolha_int == len(disc_list_indexed) + 1:
                break
                
            if 1 <= escolha_int <= len(disc_list_indexed):
                disc_selecionada = disc_list_indexed[escolha_int - 1]
                menu_disciplina_professor_client(disc_selecionada)
            else:
                print("Opção inválida!")
                
        except (ValueError, EOFError):
            print("Entrada inválida.")
            continue
            
    deslogar()

def menu_disciplina_professor_client(disc_info):
    """Menu de Ações dentro de uma Disciplina (Professor)."""
    global_disc_key = disc_info["global_key"]
    
    while SESSAO["logged_in"]:
        
        response = fazer_requisicao('/professor/disciplina/menu_data', data={"global_disc_key": global_disc_key})
        
        if response.get("status") == "erro":
            exibir_mensagem(response)
            return

        nome_disciplina = response.get("nome_disciplina", "N/D")
        turma = response.get("turma", "N/D")
        atividades_count = response.get("atividades_count", 0)
        atividades_list = response.get("atividades_list", [])

        print(f"\nDisciplina: {nome_disciplina} | Turma: {turma} ({response.get('alunos_count', 0)} alunos)")
        print("Pesos Fixos: NP1 (35%), NP2 (35%), Atividades (30%)")
        menu_opcoes = {
            1: "Lista de chamada",
            2: "Gerar Tópicos de Aula (IA)",
            3: f"Enviar atividade (Atividades: {atividades_count}/10)",
            4: "Lançar NP1/NP2",
            5: "Corrigir e Atribuir Nota de Atividade",
            6: "Calcular e Atualizar Nota Final do Semestre",
            7: "Ver notas e faltas da turma",
            8: "Voltar"
        }
        desenhar_menu(menu_opcoes, f"AÇÕES - {nome_disciplina}")
        
        try:
            opcao = input("Escolha uma opção: ").strip()
            if opcao == "1":
                lista_chamada_client(global_disc_key, nome_disciplina, turma)
            elif opcao == "2":
                gerar_topicos_ia_client(global_disc_key, nome_disciplina)
            elif opcao == "3":
                enviar_atividade_client(global_disc_key)
            elif opcao == "4":
                lancar_np_grades_client(global_disc_key, nome_disciplina, turma)
            elif opcao == "5":
                corrigir_e_atribuir_nota_atividade_client(global_disc_key, nome_disciplina, atividades_list)
            elif opcao == "6":
                calcular_nota_final_turma_client(global_disc_key)
            elif opcao == "7":
                ver_notas_faltas_turma_client(global_disc_key, nome_disciplina, turma)
            elif opcao == "8":
                break
            else:
                print("Opção inválida!")
        except EOFError:
            break
        except ValueError:
            print("Entrada inválida.")
            continue

def menu_aluno_client():
    """Menu Aluno: Visualiza dados e envia atividades."""
    ra = SESSAO["contexto"].get("ra") 
    
    
    response = fazer_requisicao('/aluno/get_dados', data={"ra": ra})
    
    if response.get("status") == "erro":
        exibir_mensagem(response)
        deslogar()
        return

    aluno_data = response
    aluno_data['ra'] = ra 
    
    while SESSAO["logged_in"]:
        print(f"\nMENU ALUNO - {aluno_data['nome']}")
        menu_opcoes = {
            1: "Ver notas e faltas",
            2: "Ver atividades disponíveis",
            3: "Enviar atividade",
            4: "Voltar"
        }
        desenhar_menu(menu_opcoes, f"MENU ALUNO - {aluno_data['nome']}")

        try:
            opcao = input("Escolha uma opção: ").strip()
            if opcao == "1":
                ver_notas_faltas_aluno_client(aluno_data)
            elif opcao == "2":
                ver_atividades_client(aluno_data)
            elif opcao == "3":
                enviar_atividade_aluno_client(aluno_data)
                
                response = fazer_requisicao('/aluno/get_dados', data={"ra": ra})
                if response.get("status") == "sucesso":
                     aluno_data = response
                     aluno_data['ra'] = ra 
            elif opcao == "4":
                break
            else:
                print("Opção inválida!")
        except EOFError:
            break
        except ValueError:
            print("Entrada inválida.")
            continue

    deslogar()

def deslogar():
    """Limpa o estado da sessão."""
    print("Deslogado com sucesso.")
    SESSAO["logged_in"] = False
    SESSAO["user_type"] = None
    SESSAO["user_id"] = None
    SESSAO["user_name"] = None
    SESSAO["contexto"] = {}
    limpar_tela()



def cadastrar_entidade(entidade):
    """Lida com a entrada de dados para cadastro."""
    print(f"\n--- CADASTRO DE {entidade.upper()} ---")
    payload = {"entidade": entidade}
    
    if entidade == "turma":
        payload["nome_turma"] = input("Nome da turma (ex: 3A, 3B): ").upper().strip()
    
    elif entidade == "professor":
        payload["cpf"] = input("CPF: ").strip()
        payload["nome"] = input("Nome completo: ").strip()
        payload["senha"] = input("Senha: ").strip()

    elif entidade == "disciplina":
        
        response = fazer_requisicao('/admin/get_listas', method='GET')
        if response.get("status") == "erro":
            exibir_mensagem(response)
            return

        turmas = response.get("turmas", [])
        professores = response.get("professores", [])

        if not turmas or not professores:
            print("Erro: Não há turmas ou professores cadastrados.")
            return

        payload["nome_disciplina"] = input("Nome da disciplina: ").strip()
        
  
        while True:
            print("\nTurmas disponíveis:")
            for i, t in enumerate(turmas, 1):
                print(f"{i}. {t}")
            escolha = input("Escolha o número da turma: ")
            if escolha.isdigit() and 1 <= int(escolha) <= len(turmas):
                payload["turma"] = turmas[int(escolha)-1]
                break
            print("Opção inválida!")
            

        while True:
            print("\nProfessores disponíveis:")
            for i, p in enumerate(professores, 1):
                print(f"{i}. {p['nome']} (CPF: {p['cpf']})")
            escolha = input("Escolha o número do professor: ")
            if escolha.isdigit() and 1 <= int(escolha) <= len(professores):
                payload["cpf_professor"] = professores[int(escolha)-1]['cpf']
                break
            print("Opção inválida!")

    elif entidade == "aluno":
      
        response = fazer_requisicao('/admin/get_listas', method='GET')
        if response.get("status") == "erro":
            exibir_mensagem(response)
            return
            
        turmas = response.get("turmas", [])
        if not turmas:
            print("Erro: Não há turmas cadastradas.")
            return

        payload["ra"] = input("RA do aluno: ").upper().strip()
        payload["nome"] = input("Nome do aluno: ").upper().strip()
        payload["senha"] = input("Senha: ").strip()
        

        while True:
            print("\nTurmas disponíveis:")
            for i, t in enumerate(turmas, 1):
                print(f"{i}. {t}")
            escolha = input("Escolha o número da turma: ")
            if escolha.isdigit() and 1 <= int(escolha) <= len(turmas):
                payload["turma"] = turmas[int(escolha)-1]
                break
            print("Opção inválida!")

    if 'turma' in payload and payload['turma']:
        payload['turma'] = payload['turma'].upper()


    response = fazer_requisicao('/admin/cadastrar', data=payload)
    exibir_mensagem(response)



def lista_chamada_client(global_disc_key, nome_disciplina, turma):
    """Interface para o professor fazer a chamada."""
    
  
    response = fazer_requisicao('/professor/get_notas_faltas_turma', data={"global_disc_key": global_disc_key})
    
    if response.get("status") == "erro":
        exibir_mensagem(response)
        return

    alunos = response.get("alunos", [])
    ra_faltosos = []
    
    print(f"\n--- LISTA DE CHAMADA - {nome_disciplina} ({turma}) ---")
    
    for aluno in alunos:
        try:
            resp = input(f"Aluno {aluno['nome']} presente? (S/N): ").strip().upper()
            if resp != "S":
                ra_faltosos.append(aluno['ra'])
        except EOFError:
            break

   
    if ra_faltosos:
        payload = {
            "global_disc_key": global_disc_key,
            "ra_faltosos": ra_faltosos
        }
        response = fazer_requisicao('/professor/lista_chamada', data=payload)
        exibir_mensagem(response)
    else:
        print("Chamada registrada. Nenhuma falta lançada.")

def gerar_topicos_ia_client(global_disc_key, nome_disciplina):
    """Interface para o professor interagir com a IA."""
    print(f"\n--- GERAÇÃO DE CONTEÚDO (IA) - {nome_disciplina} ---")
    
    tema = input("Digite o TEMA principal da aula (ex: 'Romantismo'): ").strip()
    
    if not tema:
        print("[AVISO] Tema não fornecido. Voltando.")
        return
        
    print("Aguarde... a IA está gerando os tópicos.")
    
    payload = {
        "global_disc_key": global_disc_key,
        "tema": tema
    }
    
    response = fazer_requisicao('/professor/gerar_topicos_ia', data=payload)
    
    if response.get("status") == "sucesso":
        print(f"\n--- RESPOSTA DA IA: 5 Tópicos para '{nome_disciplina}' ---")
        print(response.get("conteudo"))
        input("\nPressione ENTER para voltar ao menu da disciplina.")
    else:
        exibir_mensagem(response)


def enviar_atividade_client(global_disc_key):
    """Interface para o professor cadastrar uma nova atividade."""
    print("\n--- CADASTRO DE ATIVIDADE ---")
    nome_atividade = input("Nome da atividade: ").strip()
    link_atividade = input("Cole o link (URL) da atividade (Google Drive/etc): ").strip()
    
    if not nome_atividade or not link_atividade:
        print("Nome e link são obrigatórios.")
        return

    payload = {
        "global_disc_key": global_disc_key,
        "nome_atividade": nome_atividade,
        "link_atividade": link_atividade
    }
    
    response = fazer_requisicao('/professor/enviar_atividade', data=payload)
    exibir_mensagem(response)




def lancar_np_grades_client(global_disc_key, nome_disciplina, turma):
    """Interface para o professor lançar notas NP1/NP2."""
    
    while True:
        print("\nQual nota deseja lançar?")
        print("1. NP1 (35%)")
        print("2. NP2 (35%)")
        escolha = input("Escolha a opção (ou 'V' para voltar): ").strip().upper()
        
        if escolha == 'V':
            return
            
        if escolha == "1":
            tipo_nota = "NP1"
            break
        elif escolha == "2":
            tipo_nota = "NP2"
            break
        else:
            print("Opção inválida! Tente novamente.")


    response = fazer_requisicao('/professor/get_notas_faltas_turma', data={"global_disc_key": global_disc_key})
    
    if response.get("status") == "erro":
        exibir_mensagem(response)
        return

    alunos = response.get("alunos", [])
    lancamentos = {}
    
    print(f"\n--- Lançamento de {tipo_nota} para {nome_disciplina} (Turma {turma}) ---")
    
    for aluno in alunos:
        
        chave_nota_servidor = tipo_nota.lower() 
        nota_atual = aluno[chave_nota_servidor]
        
        while True:
            try:
                nota_input = input(f"Nota de {aluno['nome']} ({tipo_nota}: {nota_atual}). Digite a nota (0-10) ou ENTER para pular: ").strip()
                
                if not nota_input:
                    break 
                
                nota_float = float(nota_input)
                if 0.0 <= nota_float <= 10.0:
                    lancamentos[aluno['ra']] = nota_float
                    break
                else:
                    print("Nota fora do intervalo (0 a 10). Tente novamente.")
            except ValueError:
               
                print("Valor inválido. Digite um número.")
            except EOFError:
                
                print("\nEntrada cancelada (EOF). Pular para o próximo aluno.")
                break

    
    if lancamentos:
        payload = {
            "global_disc_key": global_disc_key,
            "tipo_nota": tipo_nota,
            "lancamentos": lancamentos
        }
        response = fazer_requisicao('/professor/lancar_np_grades', data=payload)
        exibir_mensagem(response)
    else:
        print("Nenhuma nota lançada.")


def corrigir_e_atribuir_nota_atividade_client(global_disc_key, nome_disciplina, atividades_list):
    """Gerencia a correção de atividades enviadas por alunos."""
    
    if not atividades_list:
        print("Nenhuma atividade cadastrada para esta disciplina.")
        return

    while True:
        
        print(f"\n--- Atividades de {nome_disciplina} ---")
        for i, nome_atividade in enumerate(atividades_list, 1):
            print(f"{i}. {nome_atividade}")

        try:
            escolha_atividade = input("Escolha o número da atividade para correção (ou 'V' para voltar): ").strip().upper()
            
            if escolha_atividade == 'V':
                return
                
            if escolha_atividade.isdigit() and 1 <= int(escolha_atividade) <= len(atividades_list):
                nome_atividade = atividades_list[int(escolha_atividade) - 1]
                break
            else:
                print("Opção inválida!")
        except EOFError:
            return
            
    
    response = fazer_requisicao('/professor/get_atividades_entregues', data={"global_disc_key": global_disc_key, "nome_atividade": nome_atividade})
    
    if response.get("status") == "erro":
        exibir_mensagem(response)
        return

    entregas = response.get("entregas", [])
    
    if not entregas:
        print(f"\nNenhuma atividade entregue para '{nome_atividade}' ainda.")
        return
        
    while True:
        
        print(f"\n--- Entregas de '{nome_atividade}' ---")
        entregas_indexed = {}
        for i, entrega in enumerate(entregas, 1):
            nota_str = entrega['nota_atual'] if isinstance(entrega['nota_atual'], str) else f"{entrega['nota_atual']:.2f}"
            print(f"{i}. {entrega['nome']} (Nota Atual: {nota_str})")
            entregas_indexed[i] = entrega
        
        try:
            escolha_aluno = input("\nDigite o número do aluno para abrir o trabalho e atribuir nota (ou 'V' para voltar): ").strip().upper()
            
            if escolha_aluno == 'V':
                break
            
            if escolha_aluno.isdigit():
                escolha_int = int(escolha_aluno)
                if escolha_int in entregas_indexed:
                    entrega_selecionada = entregas_indexed[escolha_int]
                    link = entrega_selecionada["link"]
                    
                    print(f"Abrindo o trabalho de {entrega_selecionada['nome']} no seu navegador...")
                    webbrowser.open(link)
                    
                    while True:
                        try:
                            nota = input(f"Atribuir nota (0-10) para {entrega_selecionada['nome']} na atividade '{nome_atividade}' (ou ENTER p/ pular): ").strip()
                            
                            if not nota:
                                print("Nota não atribuída. Voltando à lista de entregas...")
                                break
                            
                            nota_float = float(nota)
                            if 0.0 <= nota_float <= 10.0:
                                payload = {
                                    "global_disc_key": global_disc_key,
                                    "nome_atividade": nome_atividade,
                                    "ra": entrega_selecionada["ra"],
                                    "nota": nota_float
                                }
                                response = fazer_requisicao('/professor/atribuir_nota_atividade', data=payload)
                                exibir_mensagem(response)
                                
                                
                                response_update = fazer_requisicao('/professor/get_atividades_entregues', data={"global_disc_key": global_disc_key, "nome_atividade": nome_atividade})
                                entregas = response_update.get("entregas", [])
                                break
                            else:
                                print("Nota fora do intervalo (0 a 10).")
                        except ValueError:
                            print("Entrada inválida. Digite um número.")
                else:
                    print("Opção inválida!")
            else:
                print("Opção inválida. Digite o número ou 'V'.")
        except EOFError:
            break

def ver_notas_faltas_turma_client(global_disc_key, nome_disciplina, turma):
    """Exibe notas, médias e faltas detalhadas da turma."""
    
    response = fazer_requisicao('/professor/get_notas_faltas_turma', data={"global_disc_key": global_disc_key})
    
    if response.get("status") == "erro":
        exibir_mensagem(response)
        return

    alunos = response.get("alunos", [])
    
    print(f"\nNotas e faltas da turma {turma} - Disciplina {nome_disciplina}")
    print("="*80)
    
    for aluno in alunos:
        print(f"Nome: {aluno['nome']} | RA: {aluno['ra']}")
        print(f"  NP1: {aluno['np1']} | NP2: {aluno['np2']} | Ativ. Média: {aluno['media_ativ']} | FINAL: {aluno['final']}")
        print(f"  Faltas Totais: {aluno['total_faltas']}")
        
        faltas_data = aluno['faltas_data']
        if faltas_data:
            print("  Detalhes das Faltas:")
            for data, key_disciplina in faltas_data.items():
                
                
                disc_falta_nome = key_disciplina.split('_')[0] if '_' in key_disciplina else key_disciplina
                disc_falta_turma = key_disciplina.split('_')[1] if '_' in key_disciplina and len(key_disciplina.split('_')) > 1 else turma
                
                print(f"    - {data} ({disc_falta_nome} ({disc_falta_turma}))")
        
        print("-" * 80)
        
    input("\nPressione ENTER para voltar.")


def calcular_nota_final_turma_client(global_disc_key):
    """Pede ao servidor para calcular e salvar as notas finais."""
    print("\nIniciando cálculo de notas finais...")
    payload = {"global_disc_key": global_disc_key}
    response = fazer_requisicao('/professor/calcular_nota_final_turma', data=payload)
    exibir_mensagem(response)
    input("Pressione ENTER para continuar.")



def ver_notas_faltas_aluno_client(aluno_data):
    """Exibe notas e faltas do próprio aluno."""
    print("\n--- SUAS NOTAS ---")
    
    
    for disc, notas in aluno_data['notas'].items():
        np1 = notas.get("NP1", "PENDENTE")
        np2 = notas.get("NP2", "PENDENTE")
        media_ativ = notas.get("ATIVIDADES_MEDIA", "PENDENTE")
        final = notas.get("NOTA_FINAL", "N/A")
        print(f"\nDisciplina: {disc}")
        print(f"  NP1: {np1} | NP2: {np2} | Média Ativ: {media_ativ}")
        print(f"  NOTA FINAL: {final}")

 
    print(f"\nFaltas Totais: {aluno_data.get('total_faltas', 0)}")
    
    faltas_data = aluno_data.get('faltas_data', {})
    if faltas_data:
        print("Detalhes das Faltas:")
        for data, key_disciplina in faltas_data.items():
            
           
            disc_falta_nome = key_disciplina.split('_')[0] if '_' in key_disciplina else key_disciplina
            disc_falta_turma = key_disciplina.split('_')[1] if '_' in key_disciplina and len(key_disciplina.split('_')) > 1 else aluno_data['turma']
                
            print(f"  - {data} ({disc_falta_nome} ({disc_falta_turma}))")
            
    input("\nPressione ENTER para voltar.")


def ver_atividades_client(aluno_data):
    """Exibe a lista de atividades disponíveis e o status de entrega."""
    atividades_listadas = []
    
    print("\n--- ATIVIDADES DISPONÍVEIS ---")
    
   
    for ativ in aluno_data.get('atividades_disponiveis', []):
        
        status = "ENTREGUE" if ativ['ja_entregue'] else "PENDENTE"
        
        atividades_listadas.append(ativ)
        print(f"{len(atividades_listadas)}. {ativ['nome']} (Disciplina: {ativ['disciplina_nome']}) - Status: {status}")
    
    if not atividades_listadas:
        print("Nenhuma atividade disponível no momento.")
        input("Pressione ENTER para voltar.")
        return
        
    while True:
        try:
            escolha = input("\nDigite o número da atividade para **abrir no navegador** (ou 'V' para voltar): ").strip().upper()
            
            if escolha == 'V':
                return
                
            if escolha.isdigit():
                escolha_int = int(escolha)
                if 1 <= escolha_int <= len(atividades_listadas):
                    atividade_selecionada = atividades_listadas[escolha_int - 1]
                    link = atividade_selecionada["link"]
                    
                    print(f"Abrindo a atividade '{atividade_selecionada['nome']}' no seu navegador...")
                    webbrowser.open(link)
                    
                    return
                else:
                    print("Opção inválida!")
            else:
                print("Opção inválida. Digite o número ou 'V'.")
        except EOFError:
            return

def enviar_atividade_aluno_client(aluno_data):
    """Interface para o aluno enviar o link de resposta de uma atividade."""
    
    ra = aluno_data['ra'] 
    turma = aluno_data['turma']
    
 
    atividades_pendentes = [
        ativ for ativ in aluno_data.get('atividades_disponiveis', []) 
        if not ativ['ja_entregue']
    ]
    
    if not atividades_pendentes:
        print("Você já entregou todas as atividades disponíveis.")
        return
        
    print(f"\n--- ATIVIDADES PENDENTES ({aluno_data['turma']}) ---")
    
    ativ_indexed = {}
    for i, ativ in enumerate(atividades_pendentes, 1):
        ativ_indexed[i] = ativ
        print(f"{i}. {ativ['nome']} (Disciplina: {ativ['disciplina_nome']})")
    
    while True:
        try:
            escolha = input("Escolha o número da atividade para enviar a resposta (ou 'V' para voltar): ").strip().upper()
            
            if escolha == 'V':
                return
            
            if escolha.isdigit() and int(escolha) in ativ_indexed:
                ativ_selecionada = ativ_indexed[int(escolha)]
                break
            else:
                print("Opção inválida!")
        except EOFError:
            return

    
    print(f"\n--- ENVIO DE ATIVIDADE: {ativ_selecionada['nome']} ---")
    print("Para enviar, cole o link do Google Drive (ou similar).")
    print("Certifique-se de que o acesso esteja liberado para o professor.")
    link_resposta = input("Cole aqui o **link do seu trabalho concluído**: ").strip()
    
    if not link_resposta:
        print("Link não fornecido. Voltando ao menu.")
        return
        
    payload = {
        "ra": ra,
        "turma": turma,
        "global_disc_key": ativ_selecionada["global_disc_key"],
        "nome_atividade": ativ_selecionada["nome"],
        "link_resposta": link_resposta
    }
    
    response = fazer_requisicao('/aluno/enviar_atividade', data=payload)
    exibir_mensagem(response)




def main():
    while True:
        menu_opcoes = {
            1: "Administrador",
            2: "Aluno",
            3: "Professor",
            4: "Sair"
        }
        desenhar_menu(menu_opcoes, "MENU PRINCIPAL")
        
        try:
            opcao = input("Escolha uma opção: ").strip()
        except EOFError:
            opcao = '4'
            
        limpar_tela()
        
        if opcao == "1":
            if login_client("administrador"):
                menu_administrador_client()
        elif opcao == "2":
            if login_client("aluno"):
                menu_aluno_client()
        elif opcao == "3":
            if login_client("professor"):
                menu_professor_client()
        elif opcao == "4":
            print("Encerrando programa...")
            break
        else:
            print("Opção inválida!")

if __name__ == "__main__":
    main()