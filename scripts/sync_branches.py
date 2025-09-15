#!/usr/bin/env python3
"""
Script para sincronizar branches dos forks mais recentes
Compara datas de commits e sincroniza branches atualizadas
"""

import os
import json
import subprocess
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple

def load_recent_forks(filename: str) -> List[Dict[str, Any]]:
    """Carrega os dados dos forks mais recentes"""
    # Garante que o diretório data existe
    os.makedirs('data', exist_ok=True)
    
    filepath = os.path.join('data', filename)
    
    if not os.path.exists(filepath):
        print(f"Arquivo {filepath} não encontrado. Criando estrutura vazia.")
        # Cria arquivo vazio com estrutura básica
        empty_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_recent_forks': 0,
            'recent_forks': []
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(empty_data, f, indent=2, ensure_ascii=False)
        return []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('recent_forks', [])

def run_git_command(command: List[str], capture_output: bool = True) -> Tuple[int, str, str]:
    """Executa comando git e retorna código de saída, stdout e stderr"""
    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=True,
            timeout=300  # 5 minutos timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "Timeout: Comando git demorou mais de 5 minutos"
    except Exception as e:
        return 1, "", str(e)

def add_remote(fork_name: str, clone_url: str) -> bool:
    """Adiciona um fork como remote temporário"""
    remote_name = f"fork_{fork_name.replace('/', '_').replace('-', '_')}"
    
    print(f"Adicionando remote: {remote_name} -> {clone_url}")
    
    # Remove remote se já existir
    run_git_command(['git', 'remote', 'remove', remote_name])
    
    # Adiciona novo remote
    returncode, stdout, stderr = run_git_command(['git', 'remote', 'add', remote_name, clone_url])
    
    if returncode != 0:
        print(f"Erro ao adicionar remote {remote_name}: {stderr}")
        return False
    
    return True

def fetch_remote(remote_name: str) -> bool:
    """Faz fetch básico do remote especificado (apenas refs)"""
    print(f"Fazendo fetch básico do remote: {remote_name}")
    
    # Fetch apenas as refs sem baixar objetos desnecessários
    returncode, stdout, stderr = run_git_command(['git', 'fetch', remote_name, '--dry-run'])
    
    if returncode != 0:
        print(f"Erro ao verificar remote {remote_name}: {stderr}")
        return False
    
    # Fetch real apenas das refs
    returncode, stdout, stderr = run_git_command(['git', 'fetch', remote_name, '+refs/heads/*:refs/remotes/' + remote_name + '/*', '--depth=1'])
    
    if returncode != 0:
        print(f"Erro ao fazer fetch do remote {remote_name}: {stderr}")
        return False
    
    return True

def fetch_specific_branch(remote_name: str, branch_name: str) -> bool:
    """Faz fetch de uma branch específica do remote"""
    print(f"Fazendo fetch da branch {branch_name} do remote {remote_name}")
    
    returncode, stdout, stderr = run_git_command([
        'git', 'fetch', remote_name, 
        f'{branch_name}:refs/remotes/{remote_name}/{branch_name}',
        '--depth=1'
    ])
    
    if returncode != 0:
        print(f"Erro ao fazer fetch da branch {branch_name}: {stderr}")
        return False
    
    return True

def get_remote_branches(remote_name: str) -> List[Tuple[str, str]]:
    """Obtém lista de branches do remote com suas datas de commit"""
    command = [
        'git', 'for-each-ref',
        '--sort=-committerdate',
        f'refs/remotes/{remote_name}',
        '--format=%(committerdate:iso8601)%09%(refname:short)'
    ]
    
    returncode, stdout, stderr = run_git_command(command)
    
    if returncode != 0:
        print(f"Erro ao listar branches do remote {remote_name}: {stderr}")
        return []
    
    branches = []
    for line in stdout.split('\n'):
        if line.strip():
            parts = line.split('\t')
            if len(parts) >= 2:
                date_str = parts[0]
                branch_ref = parts[1]
                # Remove o prefixo do remote do nome da branch
                branch_name = branch_ref.replace(f'{remote_name}/', '')
                branches.append((branch_name, date_str))
    
    return branches

def get_local_branch_date(branch_name: str) -> str:
    """Obtém a data do último commit da branch local"""
    command = [
        'git', 'log', '-1',
        '--format=%ci',
        branch_name
    ]
    
    returncode, stdout, stderr = run_git_command(command)
    
    if returncode != 0:
        # Branch não existe localmente
        return ""
    
    return stdout.strip()

def parse_git_date(date_str: str) -> datetime:
    """Converte string de data do git para objeto datetime"""
    try:
        # Remove timezone info para comparação simples
        date_clean = re.sub(r'\s[+-]\d{4}$', '', date_str)
        return datetime.strptime(date_clean, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            # Formato ISO
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            return datetime.min

def is_branch_updated(remote_branch_date: str, local_branch_date: str) -> bool:
    """Verifica se a branch do remote é mais recente que a local"""
    if not local_branch_date:
        # Branch não existe localmente, considerar como atualizada
        return True
    
    remote_dt = parse_git_date(remote_branch_date)
    local_dt = parse_git_date(local_branch_date)
    
    return remote_dt > local_dt

def sync_branch(remote_name: str, branch_name: str) -> bool:
    """Sincroniza uma branch específica do remote"""
    print(f"Sincronizando branch: {branch_name} do remote {remote_name}")
    
    # Verifica se a branch local existe
    returncode, _, _ = run_git_command(['git', 'show-ref', '--verify', '--quiet', f'refs/heads/{branch_name}'])
    branch_exists_locally = returncode == 0
    
    if branch_exists_locally:
        # Branch existe, fazer merge
        # Primeiro, checkout para a branch
        returncode, stdout, stderr = run_git_command(['git', 'checkout', branch_name])
        if returncode != 0:
            print(f"Erro ao fazer checkout da branch {branch_name}: {stderr}")
            return False
        
        # Fazer pull do remote
        returncode, stdout, stderr = run_git_command(['git', 'pull', remote_name, branch_name])
        if returncode != 0:
            print(f"Erro ao fazer pull da branch {branch_name}: {stderr}")
            return False
    else:
        # Branch não existe localmente, criar nova
        returncode, stdout, stderr = run_git_command([
            'git', 'checkout', '-b', branch_name, f'{remote_name}/{branch_name}'
        ])
        if returncode != 0:
            print(f"Erro ao criar branch {branch_name}: {stderr}")
            return False
    
    print(f"Branch {branch_name} sincronizada com sucesso")
    return True

def remove_remote(remote_name: str) -> None:
    """Remove o remote temporário"""
    print(f"Removendo remote temporário: {remote_name}")
    run_git_command(['git', 'remote', 'remove', remote_name])

def sync_fork(fork_data: Dict[str, Any]) -> List[str]:
    """Sincroniza todas as branches atualizadas de um fork"""
    fork_name = fork_data['full_name']
    clone_url = fork_data['clone_url']
    
    print(f"\n=== Sincronizando fork: {fork_name} ===")
    
    remote_name = f"fork_{fork_name.replace('/', '_').replace('-', '_')}"
    updated_branches = []
    
    try:
        # Adiciona remote
        if not add_remote(fork_name, clone_url):
            return updated_branches
        
        # Primeiro, faz um fetch básico apenas para obter as refs
        print(f"Obtendo lista de branches do fork {fork_name}...")
        returncode, stdout, stderr = run_git_command(['git', 'ls-remote', '--heads', remote_name])
        
        if returncode != 0:
            print(f"Erro ao listar branches remotas: {stderr}")
            return updated_branches
        
        # Processa a saída do ls-remote para encontrar branches AppID
        remote_branches = []
        for line in stdout.split('\n'):
            if line.strip():
                parts = line.split('\t')
                if len(parts) >= 2:
                    commit_hash = parts[0]
                    ref = parts[1]
                    branch_name = ref.replace('refs/heads/', '')
                    
                    # Filtra apenas branches que são AppIDs (numéricas)
                    if re.match(r'^\d+$', branch_name):
                        remote_branches.append(branch_name)
        
        if not remote_branches:
            print(f"Nenhuma branch AppID encontrada no fork {fork_name}")
            return updated_branches
        
        print(f"Encontradas {len(remote_branches)} branches AppID no fork")
        
        # Para cada branch AppID, faz fetch seletivo e verifica se precisa sincronizar
        for branch_name in remote_branches:
            print(f"Verificando branch {branch_name}...")
            
            # Faz fetch seletivo apenas desta branch
            if not fetch_specific_branch(remote_name, branch_name):
                continue
            
            # Obtém data da branch remota
            returncode, stdout, stderr = run_git_command([
                'git', 'log', '-1', '--format=%ci', f'{remote_name}/{branch_name}'
            ])
            
            if returncode != 0:
                print(f"Erro ao obter data da branch {branch_name}: {stderr}")
                continue
            
            remote_date = stdout.strip()
            local_date = get_local_branch_date(branch_name)
            
            if is_branch_updated(remote_date, local_date):
                print(f"Branch {branch_name} está atualizada no fork (remote: {remote_date}, local: {local_date or 'não existe'})")
                
                if sync_branch(remote_name, branch_name):
                    updated_branches.append(branch_name)
                else:
                    print(f"Falha ao sincronizar branch {branch_name}")
            else:
                print(f"Branch {branch_name} já está atualizada localmente")
    
    finally:
        # Remove remote temporário
        remove_remote(remote_name)
    
    return updated_branches

def main():
    """Função principal"""
    try:
        print("Iniciando sincronização de branches dos forks...")
        
        # Carrega forks mais recentes
        recent_forks = load_recent_forks('LastPushAt_Forks_SteamCracks_ManifestHub.json')
        
        if not recent_forks:
            print("Nenhum fork recente encontrado.")
            return
        
        print(f"Processando {len(recent_forks)} forks recentes...")
        
        all_updated_branches = []
        
        # Processa cada fork
        for fork_data in recent_forks:
            updated_branches = sync_fork(fork_data)
            all_updated_branches.extend(updated_branches)
        
        # Volta para a branch main/master
        run_git_command(['git', 'checkout', 'main'])
        
        # Salva log de branches atualizadas
        if all_updated_branches:
            os.makedirs('data', exist_ok=True)
            log_file = 'data/updated_branches.log'
            with open(log_file, 'w') as f:
                for branch in sorted(set(all_updated_branches)):
                    f.write(f"{branch}\n")
            print(f"Log de branches atualizadas salvo em {log_file}")
        
        print(f"\n=== RESUMO DA SINCRONIZAÇÃO ===")
        print(f"Total de branches atualizadas: {len(all_updated_branches)}")
        if all_updated_branches:
            print("Branches atualizadas:")
            for branch in sorted(set(all_updated_branches)):
                print(f"  - {branch}")
        
        print("Sincronização concluída!")
        
    except Exception as e:
        print(f"Erro durante a sincronização: {e}")
        raise

if __name__ == '__main__':
    main()