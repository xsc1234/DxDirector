import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
grandparent_dir = os.path.dirname(parent_dir)
sys.path.append(grandparent_dir)
import torch
from my_transformers import AutoTokenizer, AutoModel,GPTNeoXModel
from datasets import load_from_disk
from torch import Tensor


def last_token_pool(last_hidden_states: Tensor, attention_mask: Tensor) -> Tensor:
    last_hidden = last_hidden_states.masked_fill(~attention_mask[..., None].bool(), 0.0)
    left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
    if left_padding:
        embedding = last_hidden[:, -1]
    else:
        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = last_hidden.shape[0]
        embedding = last_hidden[torch.arange(batch_size, device=last_hidden.device), sequence_lengths]
    return embedding


if __name__ == '__main__':
    device = torch.device("cuda:4")
    model = GPTNeoXModel.from_pretrained("/Path_to_Retrieval_Model").to(device)
    tokenizer = AutoTokenizer.from_pretrained("/Path_to_Retrieval_Model")

    save_folder = '/medical_rag/faiss_index_text_with_ids'
    print('loading dataset')
    ds_with_embeddings_data = load_from_disk(save_folder)  
    print('loading dataset')
    ds_with_embeddings = load_from_disk(save_folder)  
    print('loading text embeddings')
    ds_with_embeddings.load_faiss_index("text_embeddings", f"{save_folder}/text_embeddings.faiss")
    print('retrieval....')

    ###for example: 
    query = 'How to Treat Leukemia?'
    query_text = "Given a question, retrieve relevant documents that answer the question\n Query: {}".format(query)
    query_inputs = tokenizer(query_text, return_tensors="pt").to(device)

    with torch.no_grad():
        query_outputs = model(**query_inputs)
    query_embedding = last_token_pool(query_outputs.last_hidden_state, query_inputs["attention_mask"]).cpu().numpy()

    results = ds_with_embeddings.get_nearest_examples("text_embeddings", query_embedding, k=5)[1]
    retrieved_text = ''
    for i in range(results['ids'][0],results['ids'][0]+10):
        retrieved_text += (ds_with_embeddings_data[i]['text'].split('Represent this passage\npassage: ')[-1] + ' ')
    print(retrieved_text)
