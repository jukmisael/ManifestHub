#!/usr/bin/env python3
"""
Script para atualizar manifests usando a API do steamcmd.net
Atualiza arquivos .lua com base nos dados mais recentes da API
"""

import os
import json
import requests
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

def make_steamcmd_request(app_id: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
    """Faz requisição para a API do steamcmd.net com retry"""
    url = f"https://api.steamcmd.net/v1/info/{app_id}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data
                else:
                    print(f"API retornou status não-sucesso para AppID {app_id}: {data.get('status')}")
                    return None
            elif response.status_code == 404:
                print(f"AppID {app_id} não encontrado na API")
                return None
            else:
                print(f"Erro HTTP {response.status_code} para AppID {app_id}")
                
        except requests.exceptions.RequestException as e:
            print(f"Erro na requisição para AppID {app_id} (tentativa {attempt + 1}): {e}")
            
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # Backoff exponencial
    
    return None

def parse_lua_file(file_path: str) -> Tuple[List[str], List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Analisa arquivo .lua e extrai informações
    
    Returns:
        Tuple contendo:
        - app_ids: Lista de todos os AppIDs encontrados no arquivo
        - depot_entries: Lista de (depot_id, hash) das linhas addappid
        - manifest_entries: Lista de (depot_id, manifest_id) das linhas setManifestid
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extrai todos os AppIDs (linhas addappid com apenas um parâmetro)
    app_id_matches = re.findall(r'addappid\((\d+)\)(?!,)', content)
    app_ids = list(set(app_id_matches))  # Remove duplicatas
    
    # Extrai entradas de depot (addappid com 3 parâmetros)
    depot_pattern = r'addappid\((\d+),\s*[01],\s*"([^"]+)"\)'
    depot_entries = re.findall(depot_pattern, content)
    
    # Extrai entradas de manifest (setManifestid)
    manifest_pattern = r'setManifestid\((\d+),\s*"([^"]+)"\)'
    manifest_entries = re.findall(manifest_pattern, content)
    
    return app_ids, depot_entries, manifest_entries

def get_depot_manifest_mapping(api_data: Dict[str, Any]) -> Dict[str, str]:
    """Extrai mapeamento depot_id -> manifest_id dos dados da API"""
    mapping = {}
    
    app_data = list(api_data.get('data', {}).values())
    if not app_data:
        return mapping
    
    app_info = app_data[0]
    depots = app_info.get('depots', {})
    
    for depot_id, depot_info in depots.items():
        if isinstance(depot_info, dict):
            manifests = depot_info.get('manifests', {})
            if isinstance(manifests, dict):
                public_manifest = manifests.get('public', {})
                if isinstance(public_manifest, dict):
                    gid = public_manifest.get('gid')
                    if gid:
                        mapping[depot_id] = str(gid)
    
    return mapping

def update_lua_content(content: str, depot_manifest_mapping: Dict[str, str]) -> Tuple[str, int]:
    """Atualiza o conteúdo do arquivo .lua com novos manifest IDs
    
    Returns:
        Tuple contendo:
        - content: Conteúdo atualizado
        - updates_count: Número de atualizações realizadas
    """
    updates_count = 0
    
    def replace_manifest(match):
        nonlocal updates_count
        depot_id = match.group(1)
        old_manifest_id = match.group(2)
        
        new_manifest_id = depot_manifest_mapping.get(depot_id)
        if new_manifest_id and new_manifest_id != old_manifest_id:
            updates_count += 1
            print(f"  Atualizando depot {depot_id}: {old_manifest_id} -> {new_manifest_id}")
            return f'setManifestid({depot_id},"{new_manifest_id}")'
        
        return match.group(0)  # Sem mudança
    
    # Substitui todas as ocorrências de setManifestid
    updated_content = re.sub(
        r'setManifestid\((\d+),\s*"([^"]+)"\)',
        replace_manifest,
        content
    )
    
    return updated_content, updates_count

def update_lua_file(file_path: str) -> bool:
    """Atualiza um arquivo .lua específico
    
    Returns:
        True se o arquivo foi atualizado, False caso contrário
    """
    print(f"Processando arquivo: {file_path}")
    
    try:
        # Analisa o arquivo atual
        app_ids, depot_entries, manifest_entries = parse_lua_file(file_path)
        
        if not app_ids:
            print(f"  Erro: Nenhum AppID encontrado no arquivo {file_path}")
            return False
        
        print(f"  AppIDs encontrados: {app_ids}")
        print(f"  Depots encontrados: {len(depot_entries)}")
        print(f"  Manifests atuais: {len(manifest_entries)}")
        
        # Combina dados de manifests de todos os AppIDs
        combined_depot_manifest_mapping = {}
        
        for app_id in app_ids:
            print(f"  Buscando dados para AppID {app_id}...")
            
            # Busca dados na API
            api_data = make_steamcmd_request(app_id)
            if not api_data:
                print(f"    Aviso: Não foi possível obter dados da API para AppID {app_id}")
                continue
            
            # Extrai mapeamento depot -> manifest
            depot_manifest_mapping = get_depot_manifest_mapping(api_data)
            
            if depot_manifest_mapping:
                print(f"    Encontrados {len(depot_manifest_mapping)} manifests para AppID {app_id}")
                combined_depot_manifest_mapping.update(depot_manifest_mapping)
            else:
                print(f"    Nenhum manifest encontrado para AppID {app_id}")
        
        if not combined_depot_manifest_mapping:
            print(f"  Aviso: Nenhum manifest encontrado na API para nenhum dos AppIDs")
            return False
        
        print(f"  Total de manifests disponíveis: {len(combined_depot_manifest_mapping)}")
        
        # Lê conteúdo atual
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Atualiza conteúdo
        updated_content, updates_count = update_lua_content(original_content, combined_depot_manifest_mapping)
        
        if updates_count > 0:
            # Salva arquivo atualizado
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            print(f"  ✓ Arquivo atualizado com {updates_count} mudanças")
            return True
        else:
            print(f"  ✓ Arquivo já está atualizado")
            return False
            
    except Exception as e:
        print(f"  Erro ao processar arquivo {file_path}: {e}")
        return False

def find_lua_files() -> List[str]:
    """Encontra todos os arquivos .lua no repositório"""
    lua_files = []
    
    # Procura arquivos .lua em todo o repositório
    for root, dirs, files in os.walk('.'):
        # Pula diretórios .git e scripts
        dirs[:] = [d for d in dirs if not d.startswith('.git') and d != 'scripts']
        
        for file in files:
            if file.endswith('.lua') and re.match(r'^\d+\.lua$', file):
                lua_files.append(os.path.join(root, file))
    
    return sorted(lua_files)

def get_recently_updated_branches() -> List[str]:
    """Obtém lista de branches que foram atualizadas recentemente"""
    # Garante que o diretório data existe
    os.makedirs('data', exist_ok=True)
    
    # Verifica se existe arquivo de log de branches atualizadas
    log_file = 'data/updated_branches.log'
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    else:
        print(f"Arquivo {log_file} não encontrado. Criando arquivo vazio.")
        # Cria arquivo vazio
        with open(log_file, 'w') as f:
            pass
    
    return []

def main():
    """Função principal"""
    try:
        print("Iniciando atualização de manifests...")
        
        # Encontra arquivos .lua
        lua_files = find_lua_files()
        
        if not lua_files:
            print("Nenhum arquivo .lua encontrado.")
            return
        
        print(f"Encontrados {len(lua_files)} arquivos .lua")
        
        # Obtém branches recentemente atualizadas para priorizar
        recently_updated = get_recently_updated_branches()
        
        # Separa arquivos por prioridade
        priority_files = []
        other_files = []
        
        for lua_file in lua_files:
            file_name = os.path.basename(lua_file)
            
            # Para arquivos com múltiplos AppIDs, verifica se algum está na lista de atualizados
            try:
                app_ids, _, _ = parse_lua_file(lua_file)
                is_priority = any(app_id in recently_updated for app_id in app_ids)
                
                if is_priority:
                    priority_files.append(lua_file)
                else:
                    other_files.append(lua_file)
            except Exception as e:
                print(f"Erro ao analisar {lua_file}: {e}")
                other_files.append(lua_file)  # Adiciona aos outros em caso de erro
        
        print(f"Arquivos prioritários (branches atualizadas): {len(priority_files)}")
        print(f"Outros arquivos: {len(other_files)}")
        
        # Processa arquivos prioritários primeiro
        total_updated = 0
        processed_files = priority_files + other_files
        
        for i, lua_file in enumerate(processed_files, 1):
            print(f"\n[{i}/{len(processed_files)}] {lua_file}")
            
            if update_lua_file(lua_file):
                total_updated += 1
            
            # Pequena pausa para evitar sobrecarga da API
            time.sleep(0.5)
        
        print(f"\n=== RESUMO DA ATUALIZAÇÃO ===")
        print(f"Arquivos processados: {len(processed_files)}")
        print(f"Arquivos atualizados: {total_updated}")
        print(f"Arquivos já atualizados: {len(processed_files) - total_updated}")
        
        print("Atualização de manifests concluída!")
        
    except Exception as e:
        print(f"Erro durante a atualização: {e}")
        raise

if __name__ == '__main__':
    main()