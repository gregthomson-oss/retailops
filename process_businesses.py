#!/usr/bin/env python3
"""
Retail Location Validation Pipeline
Processes businesses through a 3-phase funnel to identify
brand-owned retail locations for Shopify POS outreach.
"""

import csv
import json
import os
import re
import sys

INPUT_CSV = '/home/ubuntu/.cursor/projects/workspace/uploads/Retail_Accounts_-_Sheet1__2_.csv'
OUTPUT_CSV = '/workspace/retail_validation_output.csv'
PROGRESS_FILE = '/workspace/processing_progress.json'

PROHIBITED_KEYWORDS = {
    'vape': 'Vaping/e-cigarettes',
    'vapor ': 'Vaping/e-cigarettes',
    'vaping': 'Vaping/e-cigarettes',
    'e-cig': 'E-cigarettes',
    'nicotine pouch': 'Nicotine products',
    'kratom': 'Kratom',
    'cbd ': 'CBD products',
    'cbd.': 'CBD products',
    'cryofreezecbd': 'CBD products',
    'hemp ': 'Hemp/CBD',
    'dragonhemp': 'Hemp/CBD',
    'cannabis': 'Cannabis',
    'firearm': 'Firearms',
    'ammunition': 'Ammunition',
    'smoke shop': 'Tobacco/smoking',
    'smokeshop': 'Tobacco/smoking',
    'calgaryvapor': 'Vaping',
    'wevape': 'Vaping',
    'liftedsmokeshop': 'Tobacco/smoking',
    'dipammo': 'Nicotine pouches',
    'kratomsky': 'Kratom',
}

WHOLESALE_PATTERNS = [
    'wholesale', 'b2b', 'distributor', 'dealers.', 'dealer.', 
    'liquidation', '-wholesale', 'wholesale.', 'reseller.',
]

TEST_PATTERNS = [
    'random-test', '-test.myshopify', '-staging.myshopify', 
    '-dev.myshopify', 'feft-test', 'payment-test', 'twp-test',
    'ibbq-dev', 'vayyar-element.myshopify',
]


def load_and_dedup():
    rows = []
    seen = set()
    with open(INPUT_CSV, 'r') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) < 2:
                continue
            key = (row[0].strip(), row[1].strip())
            if key not in seen and key[0] and key[1]:
                seen.add(key)
                rows.append({'name': key[0], 'domain': key[1]})
    return rows


def phase1_keyword_screen(biz):
    combined = (biz['name'] + ' ' + biz['domain']).lower()
    
    for kw, reason in PROHIBITED_KEYWORDS.items():
        if kw in combined:
            return 'INELIGIBLE', reason
    
    for pat in WHOLESALE_PATTERNS:
        if pat in combined:
            return 'INELIGIBLE', 'Wholesale/B2B-only business'
    
    for pat in TEST_PATTERNS:
        if pat in combined:
            return 'INELIGIBLE', 'Test/sandbox store'
    
    return 'ELIGIBLE', None


def format_csv_row(name, website, num_locations, predicted_revenue, product_type, reasoning):
    fields = [name, website, str(num_locations), predicted_revenue, product_type, reasoning]
    formatted = []
    for f in fields:
        if ',' in str(f) or '"' in str(f) or '\n' in str(f):
            formatted.append('"' + str(f).replace('"', '""') + '"')
        else:
            formatted.append(str(f))
    return ','.join(formatted)


def generate_output():
    businesses = load_and_dedup()
    results = []
    needs_research = []
    
    for biz in businesses:
        status, reason = phase1_keyword_screen(biz)
        if status == 'INELIGIBLE':
            results.append(format_csv_row(
                biz['name'], biz['domain'], 0, '', 
                reason, f"Phase 1: Eliminated - {reason}. No further research needed."
            ))
        else:
            needs_research.append(biz)
    
    print(f"Auto-eliminated: {len(results)}")
    print(f"Need web research: {len(needs_research)}")
    
    with open('/workspace/needs_research.json', 'w') as f:
        json.dump(needs_research, f, indent=2)
    
    with open('/workspace/auto_eliminated.csv', 'w') as f:
        for row in results:
            f.write(row + '\n')
    
    return needs_research, results


if __name__ == '__main__':
    needs_research, auto_results = generate_output()
    print(f"\nGenerated {len(auto_results)} auto-eliminated rows")
    print(f"Saved {len(needs_research)} businesses needing research to needs_research.json")
    
    batch_size = 50
    num_batches = (len(needs_research) + batch_size - 1) // batch_size
    print(f"\nWill need {num_batches} batches of ~{batch_size} businesses each")
    
    for i in range(num_batches):
        start = i * batch_size
        end = min(start + batch_size, len(needs_research))
        batch = needs_research[start:end]
        batch_file = f'/workspace/batch_{i:03d}.json'
        with open(batch_file, 'w') as f:
            json.dump(batch, f, indent=2)
        print(f"Batch {i}: {len(batch)} businesses -> {batch_file}")
