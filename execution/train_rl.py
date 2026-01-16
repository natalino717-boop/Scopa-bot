
import os
import torch
import numpy as np
from tqdm import tqdm

from scopa_core import initialize_game, get_valid_moves, apply_move, is_game_over, calculate_scores
from scopa_rl_agent import ScopaRLAgent
from scopa_ai import ScopaBot  # Heuristic Opponent (v9.3)

# CONFIG
EPISODES = 5000
BATCH_SIZE = 64
GAMMA = 0.99
EPS_START = 1.0
EPS_END = 0.1
EPS_DECAY = 2000
TARGET_UPDATE = 100
CHECKPOINT_PATH = "scopa_dqn.pth"

def calculate_reward(state, player_idx, move, prev_scores):
    """
    Shaped Reward Function.
    Returns (reward, done, new_scores)
    """
    scores = calculate_scores(state)
    my_score = scores[player_idx].total
    opp_score = scores[1 - player_idx].total
    
    # Calculate point delta since last turn
    prev_my = prev_scores[player_idx].total
    delta = my_score - prev_my
    
    reward = 0.0
    
    # 1. Immediate Material Reward (Cards captured)
    if move.is_capture:
        reward += 0.1 * len(move.cards_captured)
        if any(c.is_settebello for c in move.cards_captured):
            reward += 1.0
        if move.is_scopa:
            reward += 2.0
            
    # 2. Point Reward (accumulated points)
    reward += delta * 1.0
    
    done = is_game_over(state)
    
    # 3. Game Outcome Reward (Sparse)
    if done:
        if my_score > opp_score:
            reward += 10.0
        elif my_score < opp_score:
            reward -= 10.0
        else:
            reward += 0.0
            
    return reward, done, scores

def train():
    input_dim = 126
    output_dim = 40
    
    agent = ScopaRLAgent(input_dim, output_dim, lr=1e-4, gamma=GAMMA)
    
    # Check if checkpoint exists
    if os.path.exists(CHECKPOINT_PATH):
        print(f"Loading checkpoint: {CHECKPOINT_PATH}")
        try:
            agent.load(CHECKPOINT_PATH)
        except Exception:
            print("Failed to load checkpoint, starting fresh.")
    
    start_eps = agent.steps_done
    opponent = ScopaBot("Heuristic")

    print(f"Starting Training: {EPISODES} episodes vs ScopaBot v9.3")
    
    wins = 0
    pbar = tqdm(range(EPISODES))
    
    for episode in pbar:
        state = initialize_game()
        
        # Randomize start player
        rl_player = episode % 2
        opp_player = 1 - rl_player
        
        # Loop until game over
        # We need to track scores for shaped rewards
        prev_scores = calculate_scores(state)
        
        # If Opponent starts, let them play first move
        if state.current_player == opp_player:
            # Opponent Move
            opp_move = opponent.choose_move(state) # Auto-updates memory inside
            state = apply_move(state, opp_move)
            # Update scores ref
            prev_scores = calculate_scores(state)
            
        done = False
        while not done:
            # === RL TURN ===
            if not state.current.hand:
                # Should not happen inside loop normally unless game over
                break
                
            steps = agent.steps_done
            epsilon = EPS_END + (EPS_START - EPS_END) * \
                      np.exp(-1. * steps / EPS_DECAY)
            agent.steps_done += 1
            
            # Select Action
            valid_moves = get_valid_moves(state)
            move, action_idx = agent.select_action(state, valid_moves, epsilon)
            
            # Apply Action
            next_state = apply_move(state, move)
            
            # Calculate Intermediate Reward (My Move)
            reward, done, new_scores = calculate_reward(next_state, rl_player, move, prev_scores)
            prev_scores = new_scores
            
            # Note: Transition storage depends on Next State.
            # IN CARD GAMES: The true "Next State" for the agent is AFTER the opponent moves.
            # But the reward for MY move is immediate (capture).
            # If we store (s, a, r, s_after_opp), the Agent learns to predict opponent.
            # If we store (s, a, r, s_after_me), the Agent learns immediate effects.
            # Standard approach: Wait for opponent to move before storing?
            # Or store s_after_me?
            # Let's use: Store s_after_me. The value V(s') will account for opponent eventually if trained enough.
            # Simpler: S -> A -> R -> S' (My Turn End).
            
            # Store transition (S, A, R, S')
            # If done, s' is terminal.
            # If not done, s' is state where Opponent is about to move.
            # Agent needs to learn that Opponent moving is part of environment dynamics.
            
            # PROBLEM: agent.optimize uses max Q(s').
            # If Opponent plays perfectly, V(s') might be low for me.
            # This is correct. The environment includes the opponent.
            
            agent.store_transition(state, action_idx, reward, next_state if not done else None, done)
            agent.optimize_model()
            
            state = next_state
            
            if done:
                if reward > 0: wins += 1
                break
                
            # === OPPONENT TURN ===
            if not state.current.hand:
                # Prepare new hand? Handled by apply_move/deal logic inside loop usually
                # scopa_core handles deal? No, apply_move doesn't deal.
                # Simulator handles it. We must handle it here.
                # Check Simulator logic: "if not hands: deal"
                pass 
                
            # Deal if empty hands and deck exists
            if not state.players[0].hand and not state.players[1].hand:
                 from scopa_core import deal_cards
                 if state.deck:
                     state = deal_cards(state, 3)
            
            if not state.current.hand:
                break # Game Over (checked by loop condition but good safety)
                
            # Opponent moves
            opp_moves = get_valid_moves(state)
            if not opp_moves: break # Should not happen
            
            # Opponent chooses
            # We must be careful about memory. ScopaBot inside handles its memory.
            opp_move = opponent.choose_move(state) 
            state = apply_move(state, opp_move)
            
            # Check if game ended by Opponent
            # Opponent reward doesn't matter for RL agent directly, BUT
            # if Opponent wins, RL agent gets negative terminal reward?
            # My reward function handles "Game Outcome" only when *I* finish the game?
            # Or when game finishes regardless?
            # calculate_reward checks is_game_over.
            
            done = is_game_over(state)
            if done:
                # Terminal Reward check
                # We need to give the agent a final reward/penalty if Opponent ended the game
                # How to attribute this?
                # We can store a transition: (S_prev, A_prev, R + Terminal, None)
                # But we already stored S_prev.
                # This is the "Afterstate" problem.
                # Simplified: Reward for RL action includes ONLY immediate + future value.
                # If opponent kills me next turn, V(s') will reflect that (Target Net).
                # So we don't need to manually patch the previous reward.
                # Correct.
                
                # Update stats
                scores = calculate_scores(state)
                # Check win
                if scores[rl_player].total > scores[opp_player].total:
                    wins += 1
        
        # Target Update
        if episode % TARGET_UPDATE == 0:
            agent.update_target_network()
            
        # Logging
        if (episode + 1) % 100 == 0:
            win_rate = wins / 100
            pbar.set_description(f"Ep {episode+1} | WR: {win_rate:.2f} | Eps: {epsilon:.2f}")
            wins = 0
            agent.save(CHECKPOINT_PATH)
            
    print("Training Complete.")
    agent.save(CHECKPOINT_PATH)

if __name__ == "__main__":
    train()
