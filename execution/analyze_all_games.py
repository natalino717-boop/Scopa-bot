#!/usr/bin/env python3
"""
Scopa Bot - Analizzatore Automatico Partite
v1.0 - Analizza tutte le partite e trova errori logici

Uso: python3 analyze_all_games.py [--last N]
"""

import json
import os
import sys
from datetime import datetime
from collections import defaultdict

DIARY_DIR = os.path.join(os.path.dirname(__file__), 'game_diaries')

# === REGOLE DI SCOPA ===
# 1. Settebello (7d) = 1 punto garantito
# 2. Denari: 6+ = 1 punto
# 3. Carte: 21+ = 1 punto
# 4. Primiera: 7 > 6 > 1 > 5 > 4 > 3 > 2 > figure
# 5. Scopa = 1 punto

def is_denaro(card):
    return card.endswith('d')

def is_seven(card):
    return card.startswith('7')

def is_settebello(card):
    return card == '7d'

def get_value(card):
    """Estrae il valore numerico da una carta (es. '10d' -> 10)"""
    val = card[:-1]
    if val in ['j', 'q', 'k']:
        return {'j': 8, 'q': 9, 'k': 10}[val]
    return int(val)

def analyze_move(move, game_id):
    """Analizza una singola mossa per errori logici"""
    errors = []
    req = move.get('request', {})
    dec = move.get('decision')
    
    if not dec or not req:
        return errors
    
    hand = req.get('hand', [])
    table = req.get('table', [])
    card_played = dec.get('card_played')
    is_capture = dec.get('is_capture', False)
    reasoning = dec.get('reasoning', [])
    
    if not card_played or not hand:
        return errors
    
    # === ERROR CHECKS ===
    
    # 1. SCARTA DENARO con alternative
    if not is_capture and is_denaro(card_played):
        alternatives = [c for c in hand if not is_denaro(c)]
        if alternatives:
            errors.append({
                'type': 'SCARTA_DENARO',
                'severity': 'HIGH',
                'detail': f"Scarta {card_played} invece di {alternatives}"
            })
    
    # 2. SCARTA SETTEBELLO (gravissimo!)
    if not is_capture and is_settebello(card_played):
        alternatives = [c for c in hand if not is_settebello(c)]
        if alternatives:
            errors.append({
                'type': 'SCARTA_SETTEBELLO',
                'severity': 'CRITICAL',
                'detail': f"Scarta 7D (!!) invece di {alternatives}"
            })
    
    # 3. SCARTA 7 con alternative
    if not is_capture and is_seven(card_played) and not is_settebello(card_played):
        alternatives = [c for c in hand if not is_seven(c)]
        if alternatives:
            errors.append({
                'type': 'SCARTA_7',
                'severity': 'MEDIUM',
                'detail': f"Scarta {card_played} invece di {alternatives}"
            })
    
    # 4. CATTURA con NON-denaro quando denaro disponibile
    if is_capture and not is_denaro(card_played):
        played_val = get_value(card_played)
        denari_same = [c for c in hand if is_denaro(c) and get_value(c) == played_val]
        if denari_same:
            errors.append({
                'type': 'CATTURA_NON_DENARO',
                'severity': 'HIGH',
                'detail': f"Usa {card_played} invece di {denari_same[0]}"
            })
    
    # 5. USA SETTEBELLO per catturare quando altro 7 disponibile
    if is_capture and is_settebello(card_played):
        other_sevens = [c for c in hand if is_seven(c) and not is_settebello(c)]
        if other_sevens:
            errors.append({
                'type': 'USA_SETTEBELLO',
                'severity': 'HIGH',
                'detail': f"Usa 7D invece di {other_sevens}"
            })
    
    # 6. NON CATTURA 7 quando possibile
    if not is_capture:
        sevens_on_table = [c for c in table if is_seven(c)]
        sevens_in_hand = [c for c in hand if is_seven(c)]
        if sevens_on_table and sevens_in_hand:
            errors.append({
                'type': 'MANCA_CATTURA_7',
                'severity': 'MEDIUM',
                'detail': f"Non cattura {sevens_on_table} con {sevens_in_hand}"
            })
    
    # 7. NON CATTURA SETTEBELLO quando possibile
    if not is_capture and '7d' in table:
        sevens_in_hand = [c for c in hand if is_seven(c)]
        if sevens_in_hand:
            errors.append({
                'type': 'MANCA_CATTURA_SETTEBELLO',
                'severity': 'CRITICAL',
                'detail': f"Non cattura 7D con {sevens_in_hand}!"
            })
    
    return errors

def analyze_game(filepath):
    """Analizza una singola partita"""
    with open(filepath) as f:
        data = json.load(f)
    
    game_id = data.get('game_id', 'unknown')
    timestamp = data.get('timestamp', 'unknown')
    moves = data.get('moves', [])
    
    if not moves:
        return None
    
    # Punteggio finale dall'ultima mossa
    last_move = moves[-1]
    my_score = last_move['request'].get('my_score_details', {})
    opp_score = last_move['request'].get('opp_score_details', {})
    
    my_total = my_score.get('totale', 0)
    opp_total = opp_score.get('totale', 0)
    
    # Risultato
    if my_total > opp_total:
        result = 'WIN'
    elif my_total < opp_total:
        result = 'LOSS'
    else:
        result = 'DRAW'
    
    # Scope
    my_scope = my_score.get('scope', 0)
    opp_scope = opp_score.get('scope', 0)
    
    # Settebello
    my_settebello = my_score.get('settebello', 0)
    opp_settebello = opp_score.get('settebello', 0)
    
    # Denari
    my_denari = my_score.get('denari', 0)
    opp_denari = opp_score.get('denari', 0)
    
    # Carte
    my_carte = my_score.get('carte', 0)
    opp_carte = opp_score.get('carte', 0)
    
    # Analizza mosse per errori
    all_errors = []
    for move in moves:
        errors = analyze_move(move, game_id)
        for err in errors:
            err['move_number'] = move['move_number']
            err['hand'] = move['request']['hand']
            err['table'] = move['request']['table']
            err['decision'] = move['decision']['description']
            all_errors.append(err)
    
    return {
        'game_id': game_id,
        'timestamp': timestamp,
        'result': result,
        'score': f"{my_total}-{opp_total}",
        'scope': f"{my_scope}-{opp_scope}",
        'settebello': 'ME' if my_settebello else ('OPP' if opp_settebello else 'NONE'),
        'denari': f"{my_denari}-{opp_denari}",
        'carte': f"{my_carte}-{opp_carte}",
        'total_moves': len(moves),
        'errors': all_errors,
        'error_count': len(all_errors)
    }

def generate_report(games, show_errors=True):
    """Genera report completo"""
    print("\n" + "="*70)
    print("📊 REPORT ANALISI PARTITE SCOPA BOT")
    print("="*70)
    print(f"Partite analizzate: {len(games)}")
    print(f"Data report: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Statistiche generali
    wins = sum(1 for g in games if g['result'] == 'WIN')
    losses = sum(1 for g in games if g['result'] == 'LOSS')
    draws = sum(1 for g in games if g['result'] == 'DRAW')
    
    print(f"\n📈 RISULTATI:")
    print(f"   Vittorie: {wins} ({100*wins/len(games):.1f}%)")
    print(f"   Sconfitte: {losses} ({100*losses/len(games):.1f}%)")
    print(f"   Pareggi: {draws} ({100*draws/len(games):.1f}%)")
    
    # Settebello
    my_7d = sum(1 for g in games if g['settebello'] == 'ME')
    opp_7d = sum(1 for g in games if g['settebello'] == 'OPP')
    none_7d = sum(1 for g in games if g['settebello'] == 'NONE')
    
    print(f"\n🎯 SETTEBELLO (7D):")
    print(f"   Bot: {my_7d} | Avversario: {opp_7d} | Nessuno: {none_7d}")
    
    # Scope
    total_my_scope = sum(int(g['scope'].split('-')[0]) for g in games)
    total_opp_scope = sum(int(g['scope'].split('-')[1]) for g in games)
    
    print(f"\n🧹 SCOPE:")
    print(f"   Bot: {total_my_scope} | Avversario: {total_opp_scope}")
    
    # Errori
    total_errors = sum(g['error_count'] for g in games)
    total_moves = sum(g['total_moves'] for g in games)
    
    print(f"\n⚠️ ERRORI LOGICI:")
    print(f"   Totale: {total_errors} su {total_moves} mosse ({100*total_errors/total_moves:.2f}%)")
    
    # Errori per tipo
    error_types = defaultdict(int)
    for g in games:
        for err in g['errors']:
            error_types[err['type']] += 1
    
    if error_types:
        print(f"\n   Per tipo:")
        for err_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"   - {err_type}: {count}")
    
    # Dettaglio errori
    if show_errors:
        all_errors = []
        for g in games:
            for err in g['errors']:
                err['game_id'] = g['game_id']
                all_errors.append(err)
        
        if all_errors:
            print(f"\n📋 DETTAGLIO ERRORI (per severità):")
            
            # Prima i CRITICAL
            critical = [e for e in all_errors if e['severity'] == 'CRITICAL']
            high = [e for e in all_errors if e['severity'] == 'HIGH']
            medium = [e for e in all_errors if e['severity'] == 'MEDIUM']
            
            for err_list, label in [(critical, '🔴 CRITICAL'), (high, '🟠 HIGH'), (medium, '🟡 MEDIUM')]:
                if err_list:
                    print(f"\n   {label}:")
                    for err in err_list[:10]:  # Max 10 per categoria
                        print(f"   Game {err['game_id']} M{err['move_number']}: {err['type']}")
                        print(f"      Mano: {err['hand']}")
                        print(f"      -> {err['detail']}")
    
    # Partite con più errori
    games_with_errors = [(g, g['error_count']) for g in games if g['error_count'] > 0]
    games_with_errors.sort(key=lambda x: -x[1])
    
    if games_with_errors:
        print(f"\n🔍 PARTITE CON PIÙ ERRORI:")
        for g, count in games_with_errors[:5]:
            print(f"   Game {g['game_id']}: {count} errori ({g['result']}, {g['score']})")
    
    print("\n" + "="*70)
    
    return {
        'total_games': len(games),
        'wins': wins,
        'losses': losses,
        'win_rate': wins/len(games) if games else 0,
        'total_errors': total_errors,
        'error_rate': total_errors/total_moves if total_moves else 0,
        'my_scope': total_my_scope,
        'opp_scope': total_opp_scope,
        'my_settebello': my_7d,
        'opp_settebello': opp_7d
    }

def main():
    # Parse args
    last_n = None
    if '--last' in sys.argv:
        idx = sys.argv.index('--last')
        if idx + 1 < len(sys.argv):
            last_n = int(sys.argv[idx + 1])
    
    # Get all game files
    if not os.path.exists(DIARY_DIR):
        print(f"❌ Directory non trovata: {DIARY_DIR}")
        return
    
    files = sorted([f for f in os.listdir(DIARY_DIR) if f.endswith('.json')])
    
    if last_n:
        files = files[-last_n:]
    
    if not files:
        print("❌ Nessuna partita trovata!")
        return
    
    print(f"\n🔍 Analizzando {len(files)} partite...")
    
    games = []
    for fname in files:
        fpath = os.path.join(DIARY_DIR, fname)
        result = analyze_game(fpath)
        if result:
            games.append(result)
    
    if games:
        generate_report(games)
    else:
        print("❌ Nessuna partita valida da analizzare!")

if __name__ == "__main__":
    main()
