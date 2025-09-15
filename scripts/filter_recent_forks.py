#!/usr/bin/env python3
"""
Script para filtrar os 5 forks mais recentes baseado no pushed_at
Filtra a partir do arquivo de forks completo e salva os mais recentes
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any

def load_forks_data(filename: str) -> Dict[str, Any]:
    """Carrega os dados dos forks do arquivo JSON"""
    # Garante que o diretório data existe
    os.makedirs('data', exist_ok=True)
    
    filepath = os.path.join('data', filename)
    
    if not os.path.exists(filepath):
        print(f"Arquivo {filepath} não encontrado. Criando estrutura vazia.")
        # Cria arquivo vazio com estrutura básica
        empty_data = {
            'timestamp': datetime.now(datetime.timezone.utc).isoformat(),
            'total_forks': 0,
            'forks': []
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(empty_data, f, indent=2, ensure_ascii=False)
        return empty_data
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def parse_datetime(date_string: str) -> datetime:
    """Converte string de data ISO para objeto datetime"""
    # Remove o 'Z' se presente e adiciona timezone info
    if date_string.endswith('Z'):
        date_string = date_string[:-1] + '+00:00'
    
    try:
        return datetime.fromisoformat(date_string)
    except ValueError:
        # Fallback para formato alternativo
        return datetime.strptime(date_string.replace('Z', ''), '%Y-%m-%dT%H:%M:%S')

def filter_recent_forks(forks_data: List[Dict[str, Any]], top_count: int = 5) -> List[Dict[str, Any]]:
    """Filtra os forks mais recentes baseado no pushed_at"""
    print(f"Filtrando os {top_count} forks mais recentes...")
    
    # Filtra forks que têm pushed_at válido
    valid_forks = []
    for fork in forks_data:
        if fork.get('pushed_at'):
            try:
                fork['_parsed_pushed_at'] = parse_datetime(fork['pushed_at'])
                valid_forks.append(fork)
            except (ValueError, TypeError) as e:
                print(f"Erro ao processar data do fork {fork.get('full_name', 'unknown')}: {e}")
                continue
    
    print(f"Forks válidos para análise: {len(valid_forks)}")
    
    # Ordena por pushed_at (mais recente primeiro)
    sorted_forks = sorted(valid_forks, key=lambda x: x['_parsed_pushed_at'], reverse=True)
    
    # Pega os top N mais recentes
    recent_forks = sorted_forks[:top_count]
    
    # Remove o campo temporário _parsed_pushed_at
    for fork in recent_forks:
        fork.pop('_parsed_pushed_at', None)
    
    return recent_forks

def save_recent_forks(recent_forks: List[Dict[str, Any]], filename: str) -> None:
    """Salva os forks mais recentes em arquivo JSON"""
    os.makedirs('data', exist_ok=True)
    
    # Prepara dados de saída com informações adicionais
    output_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'total_recent_forks': len(recent_forks),
        'recent_forks': recent_forks
    }
    
    filepath = os.path.join('data', filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"Forks recentes salvos em {filepath}")

def print_recent_forks_summary(recent_forks: List[Dict[str, Any]]) -> None:
    """Imprime um resumo dos forks mais recentes"""
    print("\n=== FORKS MAIS RECENTES ===")
    for i, fork in enumerate(recent_forks, 1):
        print(f"{i}. {fork['full_name']}")
        print(f"   URL: {fork['clone_url']}")
        print(f"   Último push: {fork['pushed_at']}")
        print(f"   Branches padrão: {fork.get('default_branch', 'main')}")
        print(f"   Tamanho: {fork.get('size', 0)} KB")
        print()

def main():
    """Função principal"""
    try:
        print("Iniciando filtragem dos forks mais recentes...")
        
        # Carrega dados dos forks
        forks_data = load_forks_data('jukmisael_ManifestHub_Forks_mescled.json')
        
        print(f"Total de forks carregados: {forks_data.get('total_forks', len(forks_data.get('forks', [])))}")
        
        # Filtra os forks mais recentes
        recent_forks = filter_recent_forks(forks_data.get('forks', []), top_count=5)
        
        if not recent_forks:
            print("Nenhum fork recente encontrado.")
            return
        
        # Salva os forks mais recentes
        save_recent_forks(recent_forks, 'LastPushAt_Forks_SteamCracks_ManifestHub.json')
        
        # Imprime resumo
        print_recent_forks_summary(recent_forks)
        
        print(f"Filtragem concluída! {len(recent_forks)} forks mais recentes identificados.")
        
    except Exception as e:
        print(f"Erro durante a filtragem: {e}")
        raise

if __name__ == '__main__':
    main()