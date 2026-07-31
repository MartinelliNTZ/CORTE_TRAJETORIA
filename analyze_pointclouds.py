#!/usr/bin/env python3
"""
Analisa nuvens de pontos .laz/.las:
- Conta total de pontos
- Calcula média de cada atributo numérico (de chunk attrs)
- Atributos de texto: média=0.0 mas nota se existe (raros, simulado para comuns)

Dependências:
pip install laspy[lazrs] numpy

Uso:
python analyze_pointclouds.py

NÃO modifica/salva nada!
"""

import os
import glob
import numpy as np
import laspy

def analyze_laz(filepath):
    print(f"\n{'='*80}")
    print(f"{os.path.basename(filepath):^80}")
    print(f"{'='*80}")
    
    with laspy.open(filepath) as reader:
        total_points = int(reader.header.point_count)
        print(f"Total de pontos: {total_points:,}")
        
        if total_points == 0:
            print("Nenhum ponto para analisar.")
            return
        
        dim_stats = {}
        first_chunk = True
        numeric_dims = []
        text_dims = []  # Comuns em LAS: flags/bitfields tratados como text
        
        for chunk in reader.chunk_iterator(1_000_000):
            if first_chunk:
                # Descobre dimensões numéricas disponíveis no chunk (laspy 2.x style)
                possible_dims = [attr for attr in dir(chunk) 
                               if not attr.startswith('_') and attr != 'point_format' 
                               and hasattr(chunk, attr) and not callable(getattr(chunk, attr))]
                numeric_dims = possible_dims
                # Possíveis text/flag dims (tratadas como text)
                text_dims = ['synthetic_flag', 'keypoint_flag', 'withheld_flag', 
                           'overlap_flag', 'scanner_channel', 'classification_flags',
                           'wave_packet_descriptor_index']  
                text_dims = [d for d in text_dims if d not in numeric_dims]
                first_chunk = False
                print(f"  Atributos numéricos: {len(numeric_dims)} | Text/Flags: {len(text_dims)}")
            
            # Acumula stats para numeric dims
            for name in numeric_dims:
                values = getattr(chunk, name)
                valid = np.isfinite(values) &amp; (values != reader.header.scales[0] * np.inf)  # ignore invalid
                if name not in dim_stats:
                    dim_stats[name] = {'sum': 0.0, 'count': 0, 'type': 'numeric'}
                dim_stats[name]['sum'] += np.nansum(values[valid])
                dim_stats[name]['count'] += np.sum(valid)
            
            # Text dims (0.0, exists=True)
            for name in text_dims:
                if name not in dim_stats:
                    dim_stats[name] = {'type': 'text', 'exists': True}
        
        # Tabela de resultados
        print(f"{'Atributo':<25} {'Média':>15} {'Tipo':<12}")
        print(f"{'-'*25}{'_'*15}{'-'*12}")
        
        for name in sorted(dim_stats):
            stats = dim_stats[name]
            if stats['type'] == 'numeric':
                count = stats['count']
                mean = stats['sum'] / count if count > 0 else 0.0
                type_str = 'numeric'
            else:
                mean = 0.0
                type_str = 'text'
            
            note = ' [existe]' if stats.get('exists', False) and stats['type'] == 'text' else ''
            print(f"{name:<25} {mean:>15.3f} {type_str:<12}{note}")
        
        print(f"{'_'*80}")
        print(f"✓ Análise completa: {len(dim_stats)} atributos.")

def main():
    cwd = '.'
    laz_files = sorted(glob.glob(os.path.join(cwd, '*.laz')))
    
    print(f"🔍 Encontrados {len(laz_files)} arquivos .laz")
    print()
    
    for fp in laz_files:
        try:
            analyze_laz(fp)
        except Exception as e:
            print(f"  ❌ Erro em {os.path.basename(fp)}: {e}")

if __name__ == '__main__':
    main()

