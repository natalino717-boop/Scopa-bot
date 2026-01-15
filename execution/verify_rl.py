
from scopa_core import initialize_game, apply_move, is_game_over, calculate_scores, get_valid_moves
from scopa_opponents import ScopaRLOpponent, RandomBot
from tqdm import tqdm

def run_verification(games=100):
    rl_bot = ScopaRLOpponent()
    random_bot = RandomBot()
    
    if rl_bot.agent is None:
        print("RL Agent failed to load. Aborting.")
        return

    wins = 0
    draws = 0
    
    print(f"Benchmarking RL (v1) vs Random ({games} games)...")
    
    for _ in tqdm(range(games)):
        state = initialize_game()
        # RL is Player 0
        
        while not is_game_over(state):
            # Deal if needed
            if not state.players[0].hand and not state.players[1].hand:
                if state.deck:
                     from scopa_core import deal_cards
                     state = deal_cards(state, 3)
            
            if not state.current.hand: break
            
            if state.current_player == 0:
                # RL Move
                move = rl_bot.choose_move(state)
            else:
                # Random Move
                move = random_bot.choose_move(state)
                
            state = apply_move(state, move)
            
        scores = calculate_scores(state)
        if scores[0].total > scores[1].total:
            wins += 1
        elif scores[0].total == scores[1].total:
            draws += 1
            
    print(f"\nResults vs Random:")
    print(f"Win Rate: {wins/games:.1%}")
    print(f"Wins: {wins}, Draws: {draws}, Losses: {games - wins - draws}")

if __name__ == "__main__":
    run_verification()
