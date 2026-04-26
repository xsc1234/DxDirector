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
from datasets import Dataset
from torch import Tensor
import json,os
from tqdm import tqdm
from my_transformers import AutoModel, AutoTokenizer,GPTNeoXModel


def get_detailed_instruct_query(task_description: str, query: str) -> str:
    return f'{task_description}\nQuery: {query}'

def get_detailed_instruct_passage(passage: str) -> str:
    return f'Represent this passage\npassage: {passage}'

def load_dataset(path_1,path_2,path_3,path_4):
    data_list = []
    ids_list = []
    files = os.listdir(path_1)
    id = 0
    for filename in tqdm(files, desc="Processing files pubmed", unit="file"):
        if filename.endswith('.jsonl'): 
            file_path = os.path.join(path_1, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    item = json.loads(line)
                    data_list.append(get_detailed_instruct_passage(item['contents']))
                    ids_list.append(id)
                    id += 1

    files = os.listdir(path_2)
    for filename in tqdm(files, desc="Processing files stat", unit="file"):
        if filename.endswith('.jsonl'):
            file_path = os.path.join(path_2, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    item = json.loads(line)
                    data_list.append(get_detailed_instruct_passage(item['contents']))
                    ids_list.append(id)
                    id += 1

    files = os.listdir(path_3)
    for filename in tqdm(files, desc="Processing files textbook", unit="file"):
        if filename.endswith('.jsonl'):  
            file_path = os.path.join(path_3, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    item = json.loads(line)
                    data_list.append(get_detailed_instruct_passage(item['contents']))
                    ids_list.append(id)
                    id += 1

    files = os.listdir(path_4)
    for filename in tqdm(files, desc="Processing files wikipedia", unit="file"):
        if filename.endswith('.jsonl'):  
            file_path = os.path.join(path_4, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    item = json.loads(line)
                    data_list.append(get_detailed_instruct_passage(item['contents']))
                    ids_list.append(id)
                    id += 1
    return data_list, ids_list


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

def encode_batch(batch):
    batch_dict = tokenizer(batch["text"], max_length=1024 - 1, padding=True, truncation=True, return_tensors='pt')
    batch_dict['input_ids'] = [torch.cat((input_ids, torch.tensor([tokenizer.eos_token_id]))) for input_ids in batch_dict['input_ids']]
    batch_dict = tokenizer.pad(batch_dict, padding=True, return_attention_mask=True, return_tensors='pt').to(model.device)

    last_column = batch_dict["attention_mask"][:, -1].unsqueeze(1) 
    batch_dict["attention_mask"] = torch.cat((batch_dict["attention_mask"], last_column), dim=1)
    with torch.no_grad():
        outputs = model(**batch_dict)
    embeddings = last_token_pool(outputs.last_hidden_state, batch_dict["attention_mask"])
    return {"text_embeddings": embeddings.detach().cpu().numpy()}


if __name__ == "__main__":
    device = torch.device("cuda:3")
    prefix = ''
    model =GPTNeoXModel.from_pretrained(prefix+"/retriever_model").to(device)
    tokenizer = AutoTokenizer.from_pretrained(prefix+"/retriever_model")
    print('loading dataset..............')
    path_1 = prefix + '/medical_data/pubmed/chunk'
    path_2 = prefix + '/medical_data/statpearls/chunk'
    path_3 = prefix + '/medical_data/textbooks/chunk'
    path_4 = prefix + '/medical_data/wikipedia'
    texts, ids_list = load_dataset(path_1=path_1, path_2=path_2, path_3=path_3, path_4=path_4)
    print('load {} texts'.format(len(texts)))
    dataset = Dataset.from_dict({"text": texts, "ids": ids_list})

    print('building text embeddings........')
    ds_with_embeddings = dataset.map(encode_batch, batched=True, batch_size=128)  

    print('adding faiss index.........')
    ds_with_embeddings.add_faiss_index(column="text_embeddings")

    print('saving...')
    save_folder = prefix + '/medical_rag/faiss_index_text_with_ids'
    ds_with_embeddings.save_faiss_index("text_embeddings", save_folder + "/text_embeddings.faiss")
    ds_with_embeddings.drop_index("text_embeddings")
    save_folder = prefix + '/medical_rag/faiss_index_text_with_ids'
    ds_with_embeddings.save_to_disk(save_folder) 

    print('Index saved successfully!')
