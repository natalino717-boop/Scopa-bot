
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Tuple, Dict
from scopa_core import GameState, Card, Suit

# === CONFIG ===
INPUT_SIZE = 120 + 10  # 40 (Hand) + 40 (Table) + 40 (Unseen/Memory) + 10 (Scalars)
HIDDEN_SIZE = 256
OUTPUT_SIZE = 40  # One Q-value per possible card usage (simplified) 
# Note: Scopa moves are complex (Card -> Capture variants). 
# Simplified Action Space: 
# We need to map (Card Played, Capture Combination) to an index.
# This is hard. 
# Alternative: Evaluator Model. Input (State + Move) -> Score.
# This fits our existing architecture better.
# Let's build a Value Network (State + Move -> Q) instead of Policy Network.

class ScopaStateEncoder:
    """Encodes GameState into a tensor."""
    
    def __init__(self):
        self.deck_ref = [Card(s, v) for s in Suit for v in range(1, 11)]
        self.card_to_idx = {c: i for i, c in enumerate(self.deck_ref)}

    def encode(self, state: GameState, my_player: int) -> torch.Tensor:
        # 1. My Hand (One-Hot) - 40
        hand_vec = np.zeros(40, dtype=np.float32)
        for c in state.players[my_player].hand:
            if c in self.card_to_idx:
                hand_vec[self.card_to_idx[c]] = 1.0
        
        # 2. Table (One-Hot) - 40
        table_vec = np.zeros(40, dtype=np.float32)
        for c in state.table:
            if c in self.card_to_idx:
                table_vec[self.card_to_idx[c]] = 1.0
        
        # 3. Captured (One-Hot) - 40 (My captured cards)
        # Useful to know what I have for primes/settebello
        captured_vec = np.zeros(40, dtype=np.float32)
        for c in state.players[my_player].captured:
            if c in self.card_to_idx:
                captured_vec[self.card_to_idx[c]] = 1.0


        # 4. Scalars
        # [MyScope, OppScope, DeckLen, MyHandLen, OppHandLen, LastCapturerIsMe]
        opp_player = 1 - my_player
        scalars = np.array([
            state.players[my_player].scope / 10.0,
            state.players[opp_player].scope / 10.0,
            len(state.deck) / 40.0,
            len(state.players[my_player].hand) / 3.0,
            len(state.players[opp_player].hand) / 3.0,
            1.0 if state.last_capturer == my_player else 0.0,
        ], dtype=np.float32)
        
        # Concatenate
        features = np.concatenate([hand_vec, table_vec, captured_vec, scalars])
        return torch.FloatTensor(features)

    def feature_dim(self):
        return 40 + 40 + 40 + 6  # 126


class DQN(nn.Module):
    """
    Standard Deep Q-Network.
    Input: State Features
    Output: 40 Q-Values (one for each possible card in deck).
    
    The agent selects the card to play. If the card generates multiple capture options,
    the environment (heuristic) decides the best capture, or we pick greedy.
    For RL Phase 4, we assume 'Targeted Selection' (Agent picks card, Game picks best capture).
    """
    def __init__(self, state_dim, action_dim=40):
        super(DQN, self).__init__()
        self.fc1 = nn.Linear(state_dim, 512)
        self.fc2 = nn.Linear(512, 512)
        self.fc3 = nn.Linear(512, 256)
        self.fc_out = nn.Linear(256, action_dim)  # 40 outputs
        
    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = F.relu(self.fc3(x))
        return self.fc_out(x)


class ReplayBuffer:
    """Experience Replay Buffer."""
    def __init__(self, capacity=10000):
        self.capacity = capacity
        self.buffer = []
        self.position = 0
    
    def push(self, state, action_idx, reward, next_state, done):
        """Action is now a simple main index (0-39)."""
        if len(self.buffer) < self.capacity:
            self.buffer.append(None)
        self.buffer[self.position] = (state, action_idx, reward, next_state, done)
        self.position = (self.position + 1) % self.capacity
    
    def sample(self, batch_size):
        import random
        batch = random.sample(self.buffer, batch_size)
        state, action, reward, next_state, done = map(np.stack, zip(*batch))
        return state, action, reward, next_state, done
    
    def __len__(self):
        return len(self.buffer)


