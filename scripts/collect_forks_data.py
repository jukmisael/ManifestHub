#!/usr/bin/env python3
"""
Script para coletar dados de forks do repositório ManifestHub
Coleta informações de todos os forks e salva em arquivo JSON
"""

import os
import json
import requests
import time
from datetime import datetime, timezone
from typing import List, Dict, Any

def get_github_token() -> str:
    """Obtém o token do GitHub das variáveis de ambiente"""
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        raise ValueError("GITHUB_TOKEN não encontrado nas variáveis de ambiente")
    return token

def make_github_request(url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """Faz uma requisição para a API do GitHub com tratamento de rate limit"""
    response = requests.get(url, headers=headers)
    
    # Verifica rate limit
    if response.status_code == 403 and 'rate limit' in response.text.lower():
        reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
        wait_time = max(0, reset_time - int(time.time()) + 10)
        print(f"Rate limit atingido. Aguardando {wait_time} segundos...")
        time.sleep(wait_time)
        response = requests.get(url, headers=headers)
    
    response.raise_for_status()
    return response.json()

def get_repository_info(token: str) -> Dict[str, Any]:
    """Obtém informações básicas do repositório principal"""
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    url = 'https://api.github.com/repos/jukmisael/ManifestHub'
    return make_github_request(url, headers)

def collect_all_forks(token: str, forks_count: int) -> List[Dict[str, Any]]:
    """Coleta todos os forks do repositório"""
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    all_forks = []
    per_page = 100
    total_pages = (forks_count + per_page - 1) // per_page
    
    print(f"Coletando {forks_count} forks em {total_pages} páginas...")
    
    for page in range(1, total_pages + 1):
        print(f"Processando página {page}/{total_pages}")
        
        url = f'https://api.github.com/repos/jukmisael/ManifestHub/forks?sort=pushed&per_page={per_page}&page={page}'
        forks_data = make_github_request(url, headers)
        
        if not forks_data:
            break
            
        all_forks.extend(forks_data)
        
        # Pequena pausa para evitar rate limiting
        time.sleep(0.1)
    
    return all_forks

def save_forks_data(forks_data: List[Dict[str, Any]], filename: str) -> None:
    """Salva os dados dos forks em arquivo JSON"""
    os.makedirs('data', exist_ok=True)
    
    # Adiciona timestamp aos dados
    output_data = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'total_forks': len(forks_data),
        'forks': forks_data
    }
    
    filepath = os.path.join('data', filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"Dados salvos em {filepath}")

def main():
    """Função principal"""
    try:
        print("Iniciando coleta de dados dos forks...")
        
        # Obtém token do GitHub
        token = get_github_token()
        
        # Obtém informações do repositório principal
        print("Obtendo informações do repositório principal...")
        repo_info = get_repository_info(token)
        forks_count = repo_info.get('forks_count', 0)
        
        print(f"Repositório: {repo_info['full_name']}")
        print(f"Total de forks: {forks_count}")
        
        if forks_count == 0:
            print("Nenhum fork encontrado.")
            return
        
        # Coleta todos os forks
        all_forks = collect_all_forks(token, forks_count)
        
        # Salva os dados
        save_forks_data(all_forks, 'jukmisael_ManifestHub_Forks_mescled.json')
        
        print(f"Coleta concluída! {len(all_forks)} forks coletados.")
        
    except Exception as e:
        print(f"Erro durante a coleta: {e}")
        raise

if __name__ == '__main__':
    main()