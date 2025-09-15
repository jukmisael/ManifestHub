#!/usr/bin/env python3
"""
Script de manutenção para o sistema ManifestHub
Realiza limpeza, validação e otimização do sistema
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

# Adiciona o diretório scripts ao path para importar utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import load_config, setup_logging, ensure_data_directory, get_file_size_mb, format_duration, print_summary

def cleanup_logs(config: Dict[str, Any], days: int = 30) -> Dict[str, Any]:
    """Remove logs antigos e otimiza arquivos de log"""
    logger = setup_logging(config)
    logger.info(f"Iniciando limpeza de logs (mantendo últimos {days} dias)")
    
    stats = {
        'files_cleaned': 0,
        'space_freed_mb': 0,
        'errors': 0
    }
    
    # Diretórios para limpar
    log_dirs = ['logs', 'data']
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    for log_dir in log_dirs:
        if not os.path.exists(log_dir):
            continue
            
        for root, dirs, files in os.walk(log_dir):
            for file in files:
                file_path = os.path.join(root, file)
                
                try:
                    # Verifica idade do arquivo
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_mtime < cutoff_date:
                        # Arquivos muito antigos
                        if file.endswith(('.log', '.tmp')):
                            file_size = get_file_size_mb(file_path)
                            os.remove(file_path)
                            stats['files_cleaned'] += 1
                            stats['space_freed_mb'] += file_size
                            logger.info(f"Removido arquivo antigo: {file_path}")
                        
                        # Compacta arquivos JSON antigos
                        elif file.endswith('.json') and not file.endswith('.gz'):
                            subprocess.run(['gzip', file_path], check=True)
                            logger.info(f"Compactado arquivo: {file_path}")
                            
                except Exception as e:
                    logger.error(f"Erro ao processar {file_path}: {e}")
                    stats['errors'] += 1
    
    # Limpa logs de branches atualizadas
    data_dir = ensure_data_directory(config)
    branches_log = os.path.join(data_dir, 'updated_branches.log')
    
    if os.path.exists(branches_log):
        try:
            temp_file = branches_log + '.tmp'
            lines_kept = 0
            
            with open(branches_log, 'r', encoding='utf-8') as infile, \
                 open(temp_file, 'w', encoding='utf-8') as outfile:
                
                for line in infile:
                    if '\t' in line:
                        timestamp_str = line.split('\t', 1)[0]
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            if timestamp > cutoff_date:
                                outfile.write(line)
                                lines_kept += 1
                        except ValueError:
                            outfile.write(line)  # Mantém linhas com formato inválido
                            lines_kept += 1
            
            os.replace(temp_file, branches_log)
            logger.info(f"Log de branches otimizado: {lines_kept} entradas mantidas")
            
        except Exception as e:
            logger.error(f"Erro ao otimizar log de branches: {e}")
            stats['errors'] += 1
    
    return stats

def validate_data_integrity(config: Dict[str, Any]) -> Dict[str, Any]:
    """Valida integridade dos arquivos de dados"""
    logger = setup_logging(config)
    logger.info("Iniciando validação de integridade dos dados")
    
    stats = {
        'files_checked': 0,
        'files_valid': 0,
        'files_invalid': 0,
        'files_repaired': 0,
        'errors': []
    }
    
    data_dir = ensure_data_directory(config)
    
    # Arquivos críticos para validar
    critical_files = [
        config.get('cache', {}).get('forks_file', 'jukmisael_ManifestHub_Forks_mescled.json'),
        config.get('cache', {}).get('recent_forks_file', 'LastPushAt_Forks_SteamCracks_ManifestHub.json')
    ]
    
    for filename in critical_files:
        file_path = os.path.join(data_dir, filename)
        stats['files_checked'] += 1
        
        if not os.path.exists(file_path):
            error_msg = f"Arquivo crítico não encontrado: {file_path}"
            logger.warning(error_msg)
            stats['errors'].append(error_msg)
            stats['files_invalid'] += 1
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validações específicas
            if 'forks' in filename:
                if not isinstance(data, dict) or 'forks' not in data:
                    raise ValueError("Estrutura de dados inválida para arquivo de forks")
                
                if not isinstance(data['forks'], list):
                    raise ValueError("Lista de forks inválida")
                
                # Verifica se tem timestamp
                if 'timestamp' not in data:
                    data['timestamp'] = datetime.utcnow().isoformat()
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    stats['files_repaired'] += 1
                    logger.info(f"Adicionado timestamp ao arquivo: {file_path}")
            
            stats['files_valid'] += 1
            logger.info(f"Arquivo válido: {file_path}")
            
        except (json.JSONDecodeError, ValueError) as e:
            error_msg = f"Arquivo inválido {file_path}: {e}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)
            stats['files_invalid'] += 1
        
        except Exception as e:
            error_msg = f"Erro ao validar {file_path}: {e}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)
            stats['files_invalid'] += 1
    
    # Valida arquivos .lua
    lua_files = []
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if not d.startswith('.git') and d != 'scripts']
        for file in files:
            if file.endswith('.lua') and file[:-4].isdigit():
                lua_files.append(os.path.join(root, file))
    
    lua_errors = 0
    for lua_file in lua_files[:10]:  # Valida apenas os primeiros 10 para não demorar muito
        stats['files_checked'] += 1
        try:
            with open(lua_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Validações básicas
            if 'addappid(' not in content:
                raise ValueError("Arquivo .lua não contém addappid")
            
            stats['files_valid'] += 1
            
        except Exception as e:
            error_msg = f"Arquivo .lua inválido {lua_file}: {e}"
            logger.warning(error_msg)
            lua_errors += 1
    
    if lua_errors > 0:
        stats['errors'].append(f"{lua_errors} arquivos .lua com problemas")
    
    return stats

def generate_maintenance_report(config: Dict[str, Any]) -> Dict[str, Any]:
    """Gera relatório de manutenção do sistema"""
    logger = setup_logging(config)
    logger.info("Gerando relatório de manutenção")
    
    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'system_info': {},
        'data_stats': {},
        'git_stats': {},
        'recommendations': []
    }
    
    # Informações do sistema
    data_dir = ensure_data_directory(config)
    
    # Estatísticas de dados
    forks_file = os.path.join(data_dir, config.get('cache', {}).get('forks_file', 'jukmisael_ManifestHub_Forks_mescled.json'))
    recent_forks_file = os.path.join(data_dir, config.get('cache', {}).get('recent_forks_file', 'LastPushAt_Forks_SteamCracks_ManifestHub.json'))
    
    if os.path.exists(forks_file):
        report['data_stats']['forks_file_size_mb'] = get_file_size_mb(forks_file)
        report['data_stats']['forks_file_age_hours'] = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(forks_file))).total_seconds() / 3600
    
    if os.path.exists(recent_forks_file):
        report['data_stats']['recent_forks_file_size_mb'] = get_file_size_mb(recent_forks_file)
    
    # Conta arquivos .lua
    lua_count = 0
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if not d.startswith('.git')]
        lua_count += sum(1 for f in files if f.endswith('.lua') and f[:-4].isdigit())
    
    report['data_stats']['lua_files_count'] = lua_count
    
    # Estatísticas do Git
    try:
        result = subprocess.run(['git', 'count-objects', '-v'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'size-pack' in line:
                    size_kb = int(line.split()[1])
                    report['git_stats']['repository_size_mb'] = size_kb / 1024
    except Exception:
        pass
    
    # Recomendações
    if report['data_stats'].get('forks_file_age_hours', 0) > 48:
        report['recommendations'].append("Arquivo de forks está desatualizado (>48h)")
    
    if report['git_stats'].get('repository_size_mb', 0) > 1000:
        report['recommendations'].append("Repositório está grande (>1GB), considere limpeza")
    
    if lua_count == 0:
        report['recommendations'].append("Nenhum arquivo .lua encontrado")
    
    # Salva relatório
    report_file = os.path.join(data_dir, 'maintenance_report.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Relatório salvo em: {report_file}")
    
    return report

def main():
    """Função principal"""
    parser = argparse.ArgumentParser(description='Script de manutenção do ManifestHub')
    parser.add_argument('--cleanup-logs', action='store_true', help='Limpa logs antigos')
    parser.add_argument('--validate-data', action='store_true', help='Valida integridade dos dados')
    parser.add_argument('--generate-report', action='store_true', help='Gera relatório de manutenção')
    parser.add_argument('--days', type=int, default=30, help='Dias para manter logs (padrão: 30)')
    
    args = parser.parse_args()
    
    if not any([args.cleanup_logs, args.validate_data, args.generate_report]):
        parser.print_help()
        return
    
    config = load_config()
    logger = setup_logging(config)
    
    start_time = datetime.now()
    
    try:
        if args.cleanup_logs:
            print("Executando limpeza de logs...")
            cleanup_stats = cleanup_logs(config, args.days)
            print_summary("LIMPEZA DE LOGS", {
                'Arquivos removidos': cleanup_stats['files_cleaned'],
                'Espaço liberado (MB)': f"{cleanup_stats['space_freed_mb']:.2f}",
                'Erros': cleanup_stats['errors']
            })
        
        if args.validate_data:
            print("Validando integridade dos dados...")
            validation_stats = validate_data_integrity(config)
            print_summary("VALIDAÇÃO DE DADOS", {
                'Arquivos verificados': validation_stats['files_checked'],
                'Arquivos válidos': validation_stats['files_valid'],
                'Arquivos inválidos': validation_stats['files_invalid'],
                'Arquivos reparados': validation_stats['files_repaired'],
                'Erros encontrados': len(validation_stats['errors'])
            })
            
            if validation_stats['errors']:
                print("\nErros encontrados:")
                for error in validation_stats['errors']:
                    print(f"  - {error}")
        
        if args.generate_report:
            print("Gerando relatório de manutenção...")
            report = generate_maintenance_report(config)
            print_summary("RELATÓRIO DE MANUTENÇÃO", {
                'Arquivos .lua': report['data_stats'].get('lua_files_count', 0),
                'Tamanho do repositório (MB)': f"{report['git_stats'].get('repository_size_mb', 0):.2f}",
                'Recomendações': len(report['recommendations'])
            })
            
            if report['recommendations']:
                print("\nRecomendações:")
                for rec in report['recommendations']:
                    print(f"  - {rec}")
        
        duration = (datetime.now() - start_time).total_seconds()
        print(f"\nManutenção concluída em {format_duration(duration)}")
        
    except Exception as e:
        logger.error(f"Erro durante manutenção: {e}")
        raise

if __name__ == '__main__':
    main()