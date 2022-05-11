import torch
from torch import nn

# Note that User Model is the Generator in this context
class Generator_UserModel(nn.Module):
    def __init__(self, input_size, output_size, n_hidden, hidden_dim):
        super().__init__()
        self.input_size = input_size
        layers = []
        
        layers.extend([torch.nn.Linear(input_size, hidden_dim),torch.nn.ReLU()])
        
        for n in range(n_hidden-1):
            layers.extend([torch.nn.Linear(hidden_dim, hidden_dim),torch.nn.ReLU()])
            
            
        # Classification Layer (outputs score for each display_item)
        layers.extend[[torch.nn.Linear(hidden_dim, output_size), torch.nn.Tanh()]]
         
        self.model = torch.nn.Sequential(*layers) # (inp_0 inp_1 .. inp_k) --> classification(inp_0, inp_1, .. inp_k) 
                                                

    def forward(self, state, displayed_items):
        """
        Input:
            state (torch.Tensor): [batch_size (#users), state_dim]
            displayed_items (torch.Tensor): [batch_size (#users), num_displayed_items, feature_dims]
            TODO: sum(item_features) -->[ 0 0 ... 1 0 0 1 ... 1 ... 1] = 805 dim
        Return:
            action_scores (torch.Tensor): [batch_size (#users), num_displayed_items]
        """
        # Prepare input
        batch_size = state.shape[0]
        # concat zero vector to displayed items to represent user not clicking on any of the displayed items
        not_clicking_feature_vec = torch.zeros((1, displayed_items.shape[-1])) # --> [1, feature_dims]
        displayed_items = torch.cat((displayed_items, not_clicking_feature_vec), -1) # --> [batch_size (#users), (num_displayed_items+1), feature_dims]
        displayed_items_flat = displayed_items.view(batch_size, -1) # --> [batch_size (#users), (num_displayed_items+1)*feature_dims]
        input_features = torch.cat((displayed_items_flat, state), dim=-1) # --> [batch_size (#users), (num_displayed_items*feature_dims) + state_dim]
        
        return self.model(input_features)
        
        
        