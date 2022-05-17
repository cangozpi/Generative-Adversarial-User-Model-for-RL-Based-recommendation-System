import torch
import torch.nn as nn   
from torch.utils.data import DataLoader
import numpy as np
import pickle
import datetime
import itertools
import os

class Dataset(nn.Module):
    def __init__(self, data_folder, dset, split="train"):
        """
        Inputs:
            data_folder (str): location of the datasset folder.
            dset (str): type of the dataset to be used. Can be "yelp", "rsc", "tb"
            split (str): can be "train", "validation", or "test". Determines the returned dataset split. 
        """
        assert split in ["train", "test", "validation"]
        data_folder = "./dropbox"
        dset = "yelp" # choose rsc, tb, or yelp

        data_filename = os.path.join(data_folder, dset+'.pkl')
        f = open(data_filename, 'rb')
        data_behavior = pickle.load(f)
        item_features = pickle.load(f)
        f.close()
        
        # Load user splits
        filename = os.path.join(data_folder, dset+'-split.pkl')
        pkl_file = open(filename, 'rb')
        train_users = pickle.load(pkl_file)
        val_users = pickle.load(pkl_file)
        test_users = pickle.load(pkl_file)
        pkl_file.close()

        # data_behavior[user][0] is user_id
        # data_behavior[user][1][t] is displayed list at time t
        # data_behavior[user][2][t] is picked id at time t

        num_items = len(item_features[0])

        self.clicked_items_index_per_user = [] # --> [user, num_time_steps]
        self.picked_item_features_per_user = [] # --> [user, num_time_steps, feature_dim]
        self.display_set_features_per_user = [] # --> [user, num_time_steps, num_displayed_items, feature_dim]
        
        users = []
        if split == "train":
            users = train_users
            
        elif split == "validation":
            users = val_users
        else: # test split
            users = test_users

        for u in users:
            # create clicked item history in terms of its index in the display_set
            self.clicked_items_index_per_user.append(data_behavior[u][2])
            
            # create clicked item (real user click) history in terms of its feature representation (dim = feature_dim)
            picked_item_features = [] # --> [num_time_steps, features]
            for picked_item_id in data_behavior[u][2]:
                picked_item_features.append(item_features[picked_item_id])
                self.picked_item_features_per_user.append(picked_item_features)

            # create display_set history
            self.display_set_features_per_user.append(data_behavior[u])

            
        
        

        

    def __getitem__(self, index):
        """
        Returns: tuple of lists (i.e. (list, list, list, list))
            # clicked_items --> [num_time_steps] display set index of the clicked items by the real user (gt user actions)
            # real_click_history --> [num_time_steps, feature_dim]
            # real_click_history_length --> [num_time_steps]
            # display_set --> [num_time_steps, num_displayed_item, feature_dim]
         
        """
        # Note that we index on users
        clicked_items = self.clicked_items_index_per_user[index]

        real_click_history = self.picked_item_features_per_user[index] # --> [num_time_steps, picked_item_features]
        real_click_history_length = len(real_click_history) 
        
        display_set = self.display_set_features_per_user[index]


        return clicked_items, real_click_history, real_click_history_length, display_set  


    def __len__(self):
        return len(self.picked_item_features_per_user) # = user



def custom_collate_fn(data):
    """
        Used to create batches with variable sequence lengths. Output will be compatible with LSTMs.
        --
        Inputs: tuple of lists (i.e. (list, list, list, list))
            # clicked_items --> [num_time_steps] display set index of the clicked items by the real user (gt user actions)
            # real_click_history --> [num_time_steps, feature_dim]
            # real_click_history_length --> [num_time_steps]
            # display_set --> [num_time_steps, num_displayed_item, feature_dim]    

        Returns:  tuple of torch.tensor (i.e. (torch.tensor, torch.tensor, torch.tensor))
            # batched_clicked_items --> [batch_size (#users), max(num_time_steps)] display set index of the clicked items by the real user (gt user actions)
            # batched_real_click_history --> [batch_size (#users), max(num_time_steps), feature_dim]
            # batched_display_set --> [batch_size (#users), max(num_time_steps), num_displayed_item, feature_dim]             
    """
    # Pack Sequences here for LSTM batches with padded dimensions
        # Record the length of every time_step
    lengths_list = []
    for clicked_items, real_click_history, real_click_history_length, display_set in data:
        lengths_list.append(real_click_history_length)
    
    # Longest time_step length. All of the sequences will be padded towards this value
    max_length = max(lengths_list)
    
    # Create the padded vectors
    batch_size = len(data)
    feature_dim = len(data[0][1][0])
    num_displayed_item = len(data[0][3][0])

    # Create a batch from the inputted data
    padded_clicked_items = torch.zeros(batch_size, max_length) # --> [batch_size, max(num_time_steps)]
    padded_real_click_history = torch.zeros(batch_size, max_length, feature_dim) # --> [batch_size, max(num_time_steps), feature_dim]
    padded_display_set = torch.zeros(batch_size, max_length, num_displayed_item, feature_dim) # --> [batch_size, max(num_time_steps), num_displayed_item, feature_dim]
    for i, (clicked_items, real_click_history, real_click_history_length, display_set) in enumerate(data): # index on the batch
        # ************************ Reminder
        # clicked_items --> [num_time_steps] display set index of the clicked items by the real user (gt user actions)
        # real_click_history --> [num_time_steps, feature_dim]
        # real_click_history_length --> [num_time_steps]
        # display_set --> [num_time_steps, num_displayed_item, feature_dim] 
        # ************************
        cur_clicked_items = torch.tensor(clicked_items) # --> [num_time_steps]
        padded_clicked_items[i, real_click_history_length:] = cur_clicked_items

        real_click_history = torch.tensor(real_click_history) # --> [num_time_steps, feature_dim]
        padded_real_click_history[i, :real_click_history_length, :] = real_click_history

        display_set = torch.tensor(display_set) # --> [num_time_steps, num_displayed_item, feature_dim]
        padded_display_set[i, :real_click_history_length, :, :] = display_set

    # Make padded tensors compatible with LSTMs
    batched_clicked_items = torch.nn.utils.rnn.pack_padded_sequence(padded_clicked_items, lengths_list, batch_first=True, enforce_sorted = False) # --> [batch_size (#users), num_time_steps]
    batched_click_history = torch.nn.utils.rnn.pack_padded_sequence(padded_real_click_history, lengths_list, batch_first=True, enforce_sorted = False) # --> [batch_size (#users), num_time_steps, feature_dim]
    batched_display_set = torch.nn.utils.rnn.pack_padded_sequence(padded_display_set, lengths_list, batch_first=True, enforce_sorted = False) # --> [batch_size (#users), num_time_steps, num_displayed_item, feature_dim]

    return batched_clicked_items, batched_click_history, batched_display_set


    # =============================== ERASE BELOW
    # Record the length of every time_step
    lengths_list = []
    for cur_vector, cur_vector_length in data:
        lengths_list.append(cur_vector_length)

    # longest time_step length. All of the sequences will be padded towards this value
    max_length = max(lengths_list)
    
    # Create the padded vectors
    batch_size = len(data)
    feature_dim = len(data[0][0][0])
    
    padded_vectors = torch.zeros(batch_size, max_length, feature_dim) # --> [batch_size, max(num_time_steps), feature_dim]
    for i, (cur_vector, cur_vector_length) in enumerate(data):
        cur_vector = torch.tensor(cur_vector[0])
        padded_vectors[i, :cur_vector_length] = cur_vector

    
    return torch.nn.utils.rnn.pack_padded_sequence(padded_vectors, lengths_list, batch_first=True, enforce_sorted = False) 
    


# ==============================================================
if __name__ == "__main__":
    # data_folder = "./dropbox"
    # dset = "yelp" # choose rsc, tb, or yelp

    # data_filename = os.path.join(data_folder, dset+'.pkl')
    # f = open(data_filename, 'rb')
    # data_behavior = pickle.load(f)
    # item_feature = pickle.load(f)
    # f.close()
    # # data_behavior[user][0] is user_id
    # # data_behavior[user][1][t] is displayed list at time t
    # # data_behavior[user][2][t] is picked id at time t
    # size_item = len(item_feature)
    # size_user = len(data_behavior)
    # f_dim = len(item_feature[0])

    # # Load user splits
    # filename = os.path.join(data_folder, dset+'-split.pkl')
    # pkl_file = open(filename, 'rb')
    # train_user = pickle.load(pkl_file)
    # vali_user = pickle.load(pkl_file)
    # test_user = pickle.load(pkl_file)
    # pkl_file.close()

    # print("=================================================")
    # print("size_item: ", size_item, ", size_user: ", size_user, ",data_behavior: ", np.asarray(data_behavior).shape,\
    #     ",item_feature: ", np.asarray(item_feature).shape, ",f_dim: ", f_dim, \
    #         ",train_user: ", np.asarray(train_user).shape, ", vali_user: ", np.asarray(vali_user).shape, \
    #             ", test_user: ", np.asarray(test_user).shape
    #     )
    # print("=================================================")
    # # print(np.asarray(data_behavior)[14])

    # Test our custom Dataset
    data_folder = "./dropbox"
    available_datasets = ["yelp", "rsc", "tb"]
    dset = available_datasets[0] # choose rsc, tb, or yelp
    
    # Initialize Dataloaders
    train_dataset = Dataset(data_folder, dset, split="train")
    val_dataset = Dataset(data_folder, dset, split="validation")
    test_dataset = Dataset(data_folder, dset, split="test")

    train_dataloader = DataLoader(train_dataset, batch_size=16, shuffle=True, collate_fn=custom_collate_fn, drop_last=True)
    val_dataloader = DataLoader(val_dataset, batch_size=16, collate_fn=custom_collate_fn, drop_last=True)
    test_dataloader = DataLoader(test_dataset, batch_size=16, collate_fn=custom_collate_fn, drop_last=True)

    print("Dataloaders successfully instantiated !")
    
    print("\n=======\nTrain DataLoader: \n\t")
    for x in train_dataloader:
        print(type(x))
        print(x)
        break
    print("\n=======\nValidation DataLoader: \n\t")
    for x in val_dataloader:
        print(type(x))
        print(x)
        break
    print("\n=======\nTest DataLoader: \n\t")
    for x in test_dataloader:
        print(type(x))
        print(x)
        break
        
