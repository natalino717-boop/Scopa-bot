
import random
import numpy as np
import torch
import torch.optim as optim
import torch.nn.functional as F

from scopa_rl import DQN, ScopaStateEncoder, ReplayBuffer

class ScopaRLAgent:
    """
    Reinforcement Learning Agent for Scopa using Standard DQN.
    Action Space: 40 (Play Card Index 0-39 based on rank/suit ref).
    """
    def __init__(self, state_dim, action_dim=40, lr=1e-4, gamma=0.99, buffer_size=10000):
        # Auto-detect device
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        print(f"RL Agent using device: {self.device}")
        
        self.policy_net = DQN(state_dim, action_dim).to(self.device)
        self.target_net = DQN(state_dim, action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=lr)
        self.memory = ReplayBuffer(buffer_size)
        
        self.state_encoder = ScopaStateEncoder()
        
        # Build Map from Move -> Action Index
        # We use the card_to_idx from encoder
        self.card_to_idx = self.state_encoder.card_to_idx
        
        self.gamma = gamma
        self.steps_done = 0
        
    def select_action(self, state, valid_moves, epsilon, training=True):
        """
        Selects an action using Epsilon-Greedy strategy.
        Returns: (Move, move_index)
        """
        if not valid_moves:
            return None, -1
            
        # Map moves to indices
        move_indices = []
        for m in valid_moves:
            # We map based on the CARD played.
            # Ambiguity: If playing Card X has 2 options (Capture A or Capture B),
            # this architecture conflates them.
            # Strategy: We assume the Agent picks the CARD, and the Environment picks the Best Capture.
            # In training, 'valid_moves' might contain duplicates of cards (different captures).
            # We filter unique cards for RL selection, then pick the best capture for that card.
            c_idx = self.card_to_idx[m.card_played]
            move_indices.append(c_idx)
            
        if training and random.random() < epsilon:
            # Exploration
            chosen_idx = random.choice(move_indices)
        else:
            # Exploitation
            state_vec = self.state_encoder.encode(state, state.current_player).to(self.device)
            with torch.no_grad():
                q_values = self.policy_net(state_vec.unsqueeze(0)) # [1, 40]
            
            # Mask invalid actions
            # Set Q=-inf for actions not in move_indices
            mask = torch.full((40,), float('-inf'), device=self.device)
            mask[move_indices] = 0
            
            masked_q = q_values + mask
            chosen_idx = masked_q.argmax().item()
            
        # Find the move object corresponding to chosen_idx
        # If multiple moves share the same card (different captures), pick the best one heuristically?
        # Or Just validation.
        # Let's pick the first one matching the card for now.
        # Optimization: Pick the capture with highest points? Yes.
        candidate_moves = [m for m in valid_moves if self.card_to_idx[m.card_played] == chosen_idx]
        
        # Heuristic tie-break for multiple captures with same card
        if len(candidate_moves) > 1:
            candidate_moves.sort(key=lambda m: len(m.cards_captured) if m.is_capture else 0, reverse=True)
            
        return candidate_moves[0], chosen_idx

    def store_transition(self, state, action, reward, next_state, done):
        s_vec = self.state_encoder.encode(state, state.current_player).numpy()
        
        if next_state is None:
            ns_vec = np.zeros_like(s_vec)
        else:
            ns_vec = self.state_encoder.encode(next_state, state.current_player).numpy()
            
        self.memory.push(s_vec, action, float(reward), ns_vec, float(done))

    def optimize_model(self, batch_size=64):
        if len(self.memory) < batch_size:
            return None
        
        states, actions, rewards, next_states, dones = self.memory.sample(batch_size)
        
        state_batch = torch.FloatTensor(states).to(self.device)
        action_batch = torch.LongTensor(actions).unsqueeze(1).to(self.device) # [64, 1]
        reward_batch = torch.FloatTensor(rewards).unsqueeze(1).to(self.device)
        next_state_batch = torch.FloatTensor(next_states).to(self.device)
        done_batch = torch.FloatTensor(dones).unsqueeze(1).to(self.device)
        
        # Compute Q(s, a)
        # Gather Q values for specific actions taken
        q_values = self.policy_net(state_batch).gather(1, action_batch)
        
        # Compute V(s') = max_a Q(s', a) from target net
        with torch.no_grad():
            next_q_values = self.target_net(next_state_batch).max(1)[0].unsqueeze(1)
            # Apply Bellman: Q_target = r + gamma * V(s') * (1-done)
            target_q_values = reward_batch + (self.gamma * next_q_values * (1 - done_batch))
            
        loss = F.smooth_l1_loss(q_values, target_q_values)
        
        self.optimizer.zero_grad()
        loss.backward()
        # Gradient clipping
        for param in self.policy_net.parameters():
            param.grad.data.clamp_(-1, 1)
        self.optimizer.step()
        
        return loss.item()

    def update_target_network(self):
        self.target_net.load_state_dict(self.policy_net.state_dict())
        
    def save(self, path):
        torch.save(self.policy_net.state_dict(), path)
        
    def load(self, path):
        self.policy_net.load_state_dict(torch.load(path, map_location=self.device))
