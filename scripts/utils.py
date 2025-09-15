#!/usr/bin/env python3
"""
Utilitários compartilhados para o sistema de sincronização ManifestHub
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from pathlib import Path

def load_config(config_path: str = "config/settings.json") -> Dict[str, Any]:
    """Carrega configurações do arquivo JSON"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Arquivo de configuração {config_path} não encontrado. Usando configurações padrão.")
        return get_default_config()
    except json.JSONDecodeError as e:
        print(f"Erro ao ler configurações: {e}. Usando configurações padrão.")
        return get_default_config()

def get_default_config() -> Dict[str, Any]:
    """Retorna configurações padrão"""
    return {
        "github": {
            "repository": "jukmisael/ManifestHub",
            "max_forks_to_track": 5,
            "api_timeout": 30,
            "rate_limit_delay": 1
        },
        "steamcmd": {
            "api_base_url": "https://api.steamcmd.net/v1/info",
            "request_timeout": 30,
            "max_retries": 3,
            "retry_delay": 2
        },
        "cache": {
            "forks_cache_hours": 24,
            "data_directory": "data",
            "forks_file": "jukmisael_ManifestHub_Forks_mescled.json",
            "recent_forks_file": "LastPushAt_Forks_SteamCracks_ManifestHub.json",
            "updated_branches_log": "updated_branches.log"
        },
        "git": {
            "remote_prefix": "fork_",
            "command_timeout": 300,
            "default_branch": "main"
        },
        "sync": {
            "max_concurrent_forks": 3,
            "branch_pattern": "^\\d+$",
            "skip_branches": ["main", "master", "develop", "dev"]
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": "logs/manifest_sync.log"
        }
    }

def setup_logging(config: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """Configura sistema de logging"""
    if config is None:
        config = load_config()
    
    log_config = config.get('logging', {})
    
    # Cria diretório de logs se não existir
    log_file = log_config.get('file', 'logs/manifest_sync.log')
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Configura logging
    logging.basicConfig(
        level=getattr(logging, log_config.get('level', 'INFO')),
        format=log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('ManifestHub')

def ensure_data_directory(config: Optional[Dict[str, Any]] = None) -> str:
    """Garante que o diretório de dados existe"""
    if config is None:
        config = load_config()
    
    data_dir = config.get('cache', {}).get('data_directory', 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def is_cache_valid(file_path: str, max_age_hours: int = 24) -> bool:
    """Verifica se um arquivo de cache ainda é válido"""
    if not os.path.exists(file_path):
        return False
    
    file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(file_path))
    return file_age < timedelta(hours=max_age_hours)

def save_json_data(data: Any, file_path: str, add_timestamp: bool = True) -> None:
    """Salva dados em arquivo JSON"""
    # Garante que o diretório existe
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Adiciona timestamp se solicitado
    if add_timestamp and isinstance(data, dict):
        data['timestamp'] = datetime.now(timezone.utc).isoformat()
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_json_data(file_path: str) -> Optional[Dict[str, Any]]:
    """Carrega dados de arquivo JSON"""
    if not os.path.exists(file_path):
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Erro ao carregar {file_path}: {e}")
        return None

def log_updated_branches(branches: list, config: Optional[Dict[str, Any]] = None) -> None:
    """Registra branches que foram atualizadas"""
    if config is None:
        config = load_config()
    
    data_dir = ensure_data_directory(config)
    log_file = os.path.join(data_dir, config.get('cache', {}).get('updated_branches_log', 'updated_branches.log'))
    
    timestamp = datetime.now(timezone.utc).isoformat()
    
    with open(log_file, 'a', encoding='utf-8') as f:
        for branch in branches:
            f.write(f"{timestamp}\t{branch}\n")

def get_recently_updated_branches(hours: int = 24, config: Optional[Dict[str, Any]] = None) -> list:
    """Obtém lista de branches atualizadas recentemente"""
    if config is None:
        config = load_config()
    
    data_dir = ensure_data_directory(config)
    log_file = os.path.join(data_dir, config.get('cache', {}).get('updated_branches_log', 'updated_branches.log'))
    
    if not os.path.exists(log_file):
        return []
    
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent_branches = set()
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '\t' in line:
                    timestamp_str, branch = line.split('\t', 1)
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        if timestamp > cutoff_time:
                            recent_branches.add(branch)
                    except ValueError:
                        continue
    except IOError:
        return []
    
    return list(recent_branches)

def cleanup_old_logs(days: int = 30, config: Optional[Dict[str, Any]] = None) -> None:
    """Remove logs antigos"""
    if config is None:
        config = load_config()
    
    data_dir = ensure_data_directory(config)
    log_file = os.path.join(data_dir, config.get('cache', {}).get('updated_branches_log', 'updated_branches.log'))
    
    if not os.path.exists(log_file):
        return
    
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
    temp_file = log_file + '.tmp'
    
    try:
        with open(log_file, 'r', encoding='utf-8') as infile, \
             open(temp_file, 'w', encoding='utf-8') as outfile:
            
            for line in infile:
                line = line.strip()
                if '\t' in line:
                    timestamp_str = line.split('\t', 1)[0]
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        if timestamp > cutoff_time:
                            outfile.write(line + '\n')
                    except ValueError:
                        # Mantém linhas com formato inválido
                        outfile.write(line + '\n')
        
        # Substitui arquivo original
        os.replace(temp_file, log_file)
        
    except IOError as e:
        print(f"Erro ao limpar logs: {e}")
        # Remove arquivo temporário se existir
        if os.path.exists(temp_file):
            os.remove(temp_file)

def get_file_size_mb(file_path: str) -> float:
    """Retorna o tamanho do arquivo em MB"""
    if not os.path.exists(file_path):
        return 0.0
    return os.path.getsize(file_path) / (1024 * 1024)

def format_duration(seconds: float) -> str:
    """Formata duração em segundos para string legível"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def print_summary(title: str, stats: Dict[str, Any]) -> None:
    """Imprime resumo formatado"""
    print(f"\n{'=' * len(title)}")
    print(title)
    print(f"{'=' * len(title)}")
    
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    print()