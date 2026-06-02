#!/usr/bin/env python3
"""
Fix all table name mismatches in workflows and pipelines.
Maps stg_omie_* names to actual database schema names.
"""

import os
import re

# Mapping of workflow table names to actual database table names
TABLE_MAPPINGS = {
    'stg_omie_clientes': 'stg_cad_clientes',
    'stg_omie_conta_pagar': 'stg_fato_contas_pagar',
    'stg_omie_categorias_conta_pagar': 'stg_fato_contas_pagar',  # Store categories in main table
    'stg_omie_distribuicao_contas_pagar': 'stg_fato_contas_pagar',  # Store distribution in main table
    'stg_omie_contas_receber': 'stg_fato_contas_receber',
    'stg_omie_categorias_contas_receber': 'stg_fato_contas_receber_categorias',
    'stg_omie_distribuicao_contas_receber': 'stg_fato_contas_receber_departamentos',
    'stg_omie_lancamentos_cc': 'stg_fato_lancamentos_cc',
    'stg_omie_categorias_lancamentos_cc': 'stg_fato_lancamentos_cc_categorias',
    'stg_omie_distribuicao_lancamentos_cc': 'stg_fato_lancamentos_cc_departamentos',
}

def fix_file(filepath):
    """Fix table names in a single file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Replace table names (handle both in SQL and XML tags)
    for old_name, new_name in TABLE_MAPPINGS.items():
        # In SQL statements
        content = re.sub(
            rf'\b{old_name}\b',
            new_name,
            content,
            flags=re.IGNORECASE
        )

    # Only write if changed
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    base_dir = r'ETL_Omie_Unificado'
    fixed_files = []

    # Find all .hpl and .hwf files
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(('.hpl', '.hwf')):
                filepath = os.path.join(root, file)
                if fix_file(filepath):
                    fixed_files.append(filepath)
                    print(f"[OK] Fixed: {filepath}")

    print(f"\nTotal files fixed: {len(fixed_files)}")
    if fixed_files:
        print("\nTable name mappings applied:")
        for old, new in TABLE_MAPPINGS.items():
            print(f"  {old} -> {new}")

if __name__ == '__main__':
    main()
