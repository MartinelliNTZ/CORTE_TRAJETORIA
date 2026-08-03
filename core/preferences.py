#!/usr/bin/env python3
"""
core/preferences.py
─────────────────────────────────────────────────────────────────────────────
Gerenciador de preferências da aplicação "CORTE DE TRAJETÓRIA".

Salva e restaura as preferências do usuário em um arquivo JSON localizado
dentro da pasta `core/` (core/preferences.json):

  • Arquivos LAS/LAZ carregados          -> "files"
  • Pastas de trajetórias selecionadas   -> "trajectory_dir"
  • Constantes de processamento          -> "constants" (CHUNK_SIZE, TIME_MARGIN)

Quando o aplicativo abre, essas preferências são carregadas automaticamente
e aplicadas aos painéis da interface. Quando o usuário altera qualquer
configuração, o arquivo é salvo novamente.
"""

import json
import os

# Diretório onde este módulo vive (core/)
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PREFERENCES_PATH = os.path.join(CORE_DIR, "preferences.json")

DEFAULT_PREFERENCES = {
    "files": [],
    "trajectory_dir": "",
    "constants": {
        "CHUNK_SIZE": 1_000_000,
        "TIME_MARGIN": 3.0,
        "OUTPUT_FORMAT": "laz",
    },
}


def load_preferences(path: str = PREFERENCES_PATH) -> dict:
    """
    Carrega as preferências salvas no arquivo JSON.

    Se o arquivo não existir, estiver corrompido ou com estrutura inválida,
    retorna um dicionário com os valores padrão (sem nunca lançar exceção).
    """
    if not os.path.isfile(path):
        return dict(DEFAULT_PREFERENCES)

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return dict(DEFAULT_PREFERENCES)

        # Mescla com os padrões para preencher chaves eventualmente ausentes
        merged = dict(DEFAULT_PREFERENCES)
        merged.update(data)

        # Garante a estrutura esperada de cada seção
        if not isinstance(merged["files"], list):
            merged["files"] = []
        if not isinstance(merged["trajectory_dir"], str):
            merged["trajectory_dir"] = ""
        if not isinstance(merged["constants"], dict):
            merged["constants"] = {}
        for key, default_value in DEFAULT_PREFERENCES["constants"].items():
            if key not in merged["constants"]:
                merged["constants"][key] = default_value

        return merged
    except (json.JSONDecodeError, OSError, TypeError):
        return dict(DEFAULT_PREFERENCES)


def save_preferences(preferences: dict, path: str = PREFERENCES_PATH) -> None:
    """
    Salva as preferências no arquivo JSON dentro da pasta core/.

    Em caso de falha de escrita (ex.: permissão negada), apenas registra um
    aviso no console — não derruba a aplicação.
    """
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(preferences, fh, ensure_ascii=False, indent=2)
    except OSError:
        print(f"[preferences] ⚠️  Não foi possível salvar as preferências em {path}")