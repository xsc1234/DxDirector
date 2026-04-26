import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
import argparse
import math
from dataclasses import dataclass, field
import torch
from torch.utils.data import DataLoader, RandomSampler, SequentialSampler
from torch.utils.data.distributed import DistributedSampler
IGNORE_INDEX = -100
max_leng = 2048
import json
from transformers import (
    AutoModelForCausalLM,
    LlamaForCausalLM,
    SchedulerType,
    default_data_collator,
    get_scheduler,
)
import transformers
from torch.utils.data import Dataset
import deepspeed
from deepspeed.ops.adam import DeepSpeedCPUAdam, FusedAdam
from deepspeed import get_accelerator
import joblib
from ds_train_llm.dschat.utils.data.data_utils import create_prompt_dataset
from ds_train_llm.dschat.utils.utils import print_rank_0, to_device, save_hf_format, set_random_seed, get_all_reduce_mean, get_optimizer_grouped_parameters, save_zero_three_model, load_hf_tokenizer
from ds_train_llm.dschat.utils.ds_utils import get_train_ds_config
from ds_train_llm.dschat.utils.module.lora import convert_linear_layer_to_lora, convert_lora_to_linear_layer, only_optimize_lora_parameters, make_model_gradient_checkpointing_compatible
from ds_train_llm.dschat.utils.model.model_utils import create_hf_model, causal_lm_model_to_fp32_loss
from ds_train_llm.dschat.utils.perf import print_throughput
from ds_train_llm.dschat.utils import conversation as conversation_lib
from packaging import version
import tokenizers
IS_TOKENIZER_GREATER_THAN_0_14 = version.parse(tokenizers.__version__) >= version.parse('0.14')


def parse_args():
    parser = argparse.ArgumentParser(
        description=
        "Finetune a transformers model on a causal language modeling task")
    parser.add_argument('--data_path',
                        nargs='*',
                        default=['Dahoas/rm-static'],
                        help='Path to the training dataset. Accepted format:'
                        '1) a single data path, 2) multiple datasets in the'
                        'form: dataset1-path dataset2-path ...')
    parser.add_argument('--data_split',
                        type=str,
                        default='2,4,4',
                        help='Comma-separated list of proportions for training'
                        'phase 1, 2, and 3 data. For example the split `6,2,2`'
                        'will use 60%% of data for phase 1, 20%% for phase 2'
                        'and 20%% for phase 3.')
    parser.add_argument(
        '--sft_only_data_path',
        nargs='*',
        default=[],
        help='Path to the dataset for only using in SFT phase.')
    parser.add_argument(
        '--data_output_path',
        type=str,
        default='/tmp/data_files/',
        help=
        'Where to store the data-related files such as shuffle index. This needs to be on a local storage of a node (not on a shared storage)'
    )
    parser.add_argument(
        "--model_name_or_path",
        type=str,
        help=
        "Path to pretrained model or model identifier from huggingface.co/models.",
        required=True,
    )
    parser.add_argument(
        "--nli_path",
        type=str,
        help=
        "Path to pretrained model or model identifier from huggingface.co/models.",
        required=False,
    )
    parser.add_argument(
        "--sft_path",
        type=str,
        help=
        "Path to pretrained model or model identifier from huggingface.co/models.",
        required=False,
    )
    parser.add_argument(
        "--per_device_train_batch_size",
        type=int,
        default=16,
        help="Batch size (per device) for the training dataloader.",
    )
    parser.add_argument(
        "--per_device_eval_batch_size",
        type=int,
        default=16,
        help="Batch size (per device) for the evaluation dataloader.",
    )
    parser.add_argument(
        "--max_seq_len",
        type=int,
        default=512,
        help="The maximum sequence length.",
    )
    parser.add_argument(
        "--learning_rate",
        type=float,
        default=1e-3,
        help=
        "Initial learning rate (after the potential warmup period) to use.",
    )
    parser.add_argument("--weight_decay",
                        type=float,
                        default=0.,
                        help="Weight decay to use.")
    parser.add_argument("--num_train_epochs",
                        type=int,
                        default=1,
                        help="Total number of training epochs to perform.")
    parser.add_argument(
        "--gradient_accumulation_steps",
        type=int,
        default=1,
        help=
        "Number of updates steps to accumulate before performing a backward/update pass.",
    )
    parser.add_argument(
        "--lr_scheduler_type",
        type=SchedulerType,
        default="cosine",
        help="The scheduler type to use.",
        choices=[
            "linear", "cosine", "cosine_with_restarts", "polynomial",
            "constant", "constant_with_warmup"
        ],
    )
    parser.add_argument(
        "--num_warmup_steps",
        type=int,
        default=0,
        help="Number of steps for the warmup in the lr scheduler.")
    parser.add_argument("--output_dir",
                        type=str,
                        default=None,
                        help="Where to store the model.")
    parser.add_argument("--seed",
                        type=int,
                        default=1234,
                        help="A seed for reproducible training.")
    parser.add_argument("--local_rank",
                        type=int,
                        default=-1,
                        help="local_rank for distributed training on gpus")
    parser.add_argument('--gradient_checkpointing',
                        action='store_true',
                        help='Enable HF gradient checkpointing for model.')
    parser.add_argument(
        "--dropout",
        type=float,
        default=None,
        help="If dropout configured, use it. "
        "Otherwise, keep the default dropout configuration of the model.")
    # deepspeed features
    parser.add_argument('--offload',
                        action='store_true',
                        help='Enable ZeRO Offload techniques.')
    parser.add_argument('--dtype',
                        type=str,
                        default='fp16',
                        choices=['fp16', 'bf16'],
                        help='Training data type')
    parser.add_argument(
        '--zero_stage',
        type=int,
        default=0,
        help='ZeRO optimization stage for Actor model (and clones).')
    ## LoRA for efficient training setting
    parser.add_argument("--lora_dim",
                        type=int,
                        default=0,
                        help="If > 0, use LoRA for efficient training.")
    parser.add_argument("--lora_module_name",
                        type=str,
                        default="decoder.layers.",
                        help="The scope of LoRA.")
    parser.add_argument('--only_optimize_lora',
                        action='store_true',
                        help='Only optimize the LoRA parameters.')
    parser.add_argument(
        "--lora_learning_rate",
        type=float,
        default=5e-4,
        help=
        "Initial LoRA learning rate (after the potential warmup period) to use."
    )
    ## low precision
    parser.add_argument(
        '--compute_fp32_loss',
        action='store_true',
        help='Relevant for low precision dtypes (fp16, bf16, etc.). '
        'If specified, loss is calculated in fp32.')
    ## Tensorboard logging
    parser.add_argument('--enable_tensorboard',
                        action='store_true',
                        help='Enable tensorboard logging')
    parser.add_argument('--tensorboard_path',
                        type=str,
                        default="step1_tensorboard")
    ## Tokenizer
    parser.add_argument(
        "--add_eot_token",
        action='store_true',
        help="Add `eot_token` as additional special token to tokenizer")
    parser.add_argument(
        "--eot_token",
        type=str,
        default="<|endoftext|>",
        help="Specify the format of the `eot_token`",
    )
    ## Print loss
    parser.add_argument('--print_loss',
                        action='store_true',
                        help='Prints loss at each step.')
    parser = deepspeed.add_config_arguments(parser)
    args = parser.parse_args()

    return args

class SupervisedDataset(Dataset):
    """Dataset for supervised fine-tuning."""

    def __init__(self,
                 data_list):
        super(SupervisedDataset, self).__init__()
        self.data_list = data_list

    def __len__(self):
        return len(self.data_list)

    def __getitem__(self, i):
        return self.data_list[i]

def preprocess(
    sources,
    tokenizer: transformers.PreTrainedTokenizer,
):
    response = sources['response'].split('[Query 1]')[-1]
    input_text = """A conversation between User and Assistant. The user asks a question, and the Assistant solves it.
The assistant first thinks about the reasoning process in the mind and then provides the user with the answer.
The reasoning process and answer are enclosed within <think> </think> and <answer> </answer> tags, respectively.
Within <think> </think>, you are an experienced medical professional. Your current role is a doctor who is examining a patient to answer the [Question]. The patient's description is in [Description of the patient].
You should reason about the [Question] step by step. 
For each node of the chain, you should generate a query, starting with [Query number]. You must give the answer for [Query number], starting with [Answer number].
Each node of the chain can be a query and answer to the content about [symptoms, medical history, and test results] of the patient, or a query and answer to related medical knowledge.
Before generating each [Query], you should do some thinking within <sub-think> </sub-think> to clarify your motivation for generating this [Query].
You should mark the queries that ask for the content in [symptoms, medical history, and test results] with [Patient's Special Query].
You should mark the queries that ask for the related objective medical knowledge with [Knowledge Query].
Each query should arise naturally as part of the logical flow, ensuring that it aligns with the clinical reasoning process.
There should be strict logical connections between nodes, such as relevant medical knowledge or your medical experience
Emphasize again that you are now simulating a doctor who is consulting a patient. You do not know all the information about [symptoms, medical history, and test results], and you must obtain them through step-by-step reasoning in the form of self-questioning and self-answering in the chain.
Within <answer> </answer>, which means the reasoning is finished, you can generate the final answer for the [Question] by referring to the [Query]-[Answer] pairs, starting with [Final Content] and marking the number for each [Answer].
You must give the final answer by "So the final answer is ". """ + """\n###User: [Description of the patient]: {}
[Question]: {}
### Assistant: """.format(sources['description'],sources['question']) + ' ' + response + ' </s>'
    input_ids = tokenizer(
        input_text,
        return_tensors="pt",
        padding="longest",
        max_length=max_leng,
        truncation=True,
    ).input_ids

    prefix = """A conversation between User and Assistant. The user asks a question, and the Assistant solves it.
The assistant first thinks about the reasoning process in the mind and then provides the user with the answer.
The reasoning process and answer are enclosed within <think> </think> and <answer> </answer> tags, respectively.
Within <think> </think>, you are an experienced medical professional. Your current role is a doctor who is examining a patient to answer the [Question]. The patient's description is in [Description of the patient].
You should reason about the [Question] step by step. 
For each node of the chain, you should generate a query, starting with [Query number]. You must give the answer for [Query number], starting with [Answer number].
Each node of the chain can be a query and answer to the content about [symptoms, medical history, and test results] of the patient, or a query and answer to related medical knowledge.
Before generating each [Query], you should do some thinking within <sub-think> </sub-think> to clarify your motivation for generating this [Query].
You should mark the queries that ask for the content in [symptoms, medical history, and test results] with [Patient's Special Query].
You should mark the queries that ask for the related objective medical knowledge with [Knowledge Query].
Each query should arise naturally as part of the logical flow, ensuring that it aligns with the clinical reasoning process.
There should be strict logical connections between nodes, such as relevant medical knowledge or your medical experience
Emphasize again that you are now simulating a doctor who is consulting a patient. You do not know all the information about [symptoms, medical history, and test results], and you must obtain them through step-by-step reasoning in the form of self-questioning and self-answering in the chain.
Within <answer> </answer>, which means the reasoning is finished, you can generate the final answer for the [Question] by referring to the [Query]-[Answer] pairs, starting with [Final Content] and marking the number for each [Answer].
You must give the final answer by "So the final answer is ". """ + """\n###User: [Description of the patient]: {}
[Question]: {}
### Assistant: """.format(sources['description'],sources['question'])
    prefix_ids = tokenizer(
        prefix,
        return_tensors="pt",
        padding="longest",
        max_length=max_leng,
        truncation=True,
    ).input_ids

    targets = input_ids.clone()

    targets[0][:len(prefix_ids[0])] = IGNORE_INDEX

    # mask掉所有的answer
    target_query = torch.tensor([386]) #query
    target_answer = torch.tensor([22550])  # query
    answer_idx = []
    query_idx = []
    # 查询连续值的起始索引
    # print('response is {}'.format(response))
    # print('ids is {}'.format(tokenizer(
    #     response,
    #     return_tensors="pt",
    #     padding="longest",
    #     max_length=1024,
    #     truncation=True,
    # ).input_ids))
    for i in range(len(prefix_ids[0]), len(targets[0]) - len(target_query) + 1):
        if torch.equal(targets[0][i:i + len(target_query)], target_query):
            try:
                if targets[0][i+1] == 682 and targets[0][i+4] == 29958 and targets[0][i-3] == 29966:
                    query_idx.append(i-4)
            except:
                continue

    for i in range(len(prefix_ids[0]), len(targets[0]) - len(target_answer) + 1):
        if torch.equal(targets[0][i:i + len(target_answer)], target_answer):
            try:
                if targets[0][i + 3] == 29962 or targets[0][i+3] == 5387:
                    answer_idx.append(i+4)
            except:
                continue

    print('len query idx {} len answer idx {}'.format(len(query_idx),len(answer_idx)))
    print('query idx {}'.format(query_idx))
    print('answer idx {}'.format(answer_idx))

    for q_a_idx in range(min(len(query_idx)-1,len(answer_idx)-1)):
        targets[0][answer_idx[q_a_idx]:query_idx[q_a_idx+1]] = IGNORE_INDEX

    return dict(
        input_ids=input_ids,
        labels=targets,
    )

def preprocess_train_answer(
    sources,
    tokenizer: transformers.PreTrainedTokenizer,
):
    response = sources['response'].split('[Query 1]')[-1]
    input_text = """A conversation between User and Assistant. The user asks a question, and the Assistant solves it.
The assistant first thinks about the reasoning process in the mind and then provides the user with the answer.
The reasoning process and answer are enclosed within <think> </think> and <answer> </answer> tags, respectively.
Within <think> </think>, you are an experienced medical professional. Your current role is a doctor who is examining a patient to answer the [Question]. The patient's description is in [Description of the patient].
You should reason about the [Question] step by step. 
For each node of the chain, you should generate a query, starting with [Query number]. You must give the answer for [Query number], starting with [Answer number].
Each node of the chain can be a query and answer to the content about [symptoms, medical history, and test results] of the patient, or a query and answer to related medical knowledge.
Before generating each [Query], you should do some thinking within <sub-think> </sub-think> to clarify your motivation for generating this [Query].
You should mark the queries that ask for the content in [symptoms, medical history, and test results] with [Patient's Special Query].
You should mark the queries that ask for the related objective medical knowledge with [Knowledge Query].
Each query should arise naturally as part of the logical flow, ensuring that it aligns with the clinical reasoning process.
There should be strict logical connections between nodes, such as relevant medical knowledge or your medical experience
Emphasize again that you are now simulating a doctor who is consulting a patient. You do not know all the information about [symptoms, medical history, and test results], and you must obtain them through step-by-step reasoning in the form of self-questioning and self-answering in the chain.
Within <answer> </answer>, which means the reasoning is finished, you can generate the final answer for the [Question] by referring to the [Query]-[Answer] pairs, starting with [Final Content] and marking the number for each [Answer].
You must give the final answer by "So the final answer is ". """ + """\n###User: [Description of the patient]: {}
[Symptoms, Medical History, and Test Results]: {}
[Question]: {}
### Assistant: """.format(sources['description'],sources['bingqing'],sources['question']) + ' ' + response + ' </s>'
    input_ids = tokenizer(
        input_text,
        return_tensors="pt",
        padding="longest",
        max_length=max_leng,
        truncation=True,
    ).input_ids

    prefix = """A conversation between User and Assistant. The user asks a question, and the Assistant solves it.
The assistant first thinks about the reasoning process in the mind and then provides the user with the answer.
The reasoning process and answer are enclosed within <think> </think> and <answer> </answer> tags, respectively.
Within <think> </think>, you are an experienced medical professional. Your current role is a doctor who is examining a patient to answer the [Question]. The patient's description is in [Description of the patient].
You should reason about the [Question] step by step. 
For each node of the chain, you should generate a query, starting with [Query number]. You must give the answer for [Query number], starting with [Answer number].
Each node of the chain can be a query and answer to the content about [symptoms, medical history, and test results] of the patient, or a query and answer to related medical knowledge.
Before generating each [Query], you should do some thinking within <sub-think> </sub-think> to clarify your motivation for generating this [Query].
You should mark the queries that ask for the content in [symptoms, medical history, and test results] with [Patient's Special Query].
You should mark the queries that ask for the related objective medical knowledge with [Knowledge Query].
Each query should arise naturally as part of the logical flow, ensuring that it aligns with the clinical reasoning process.
There should be strict logical connections between nodes, such as relevant medical knowledge or your medical experience
Emphasize again that you are now simulating a doctor who is consulting a patient. You do not know all the information about [symptoms, medical history, and test results], and you must obtain them through step-by-step reasoning in the form of self-questioning and self-answering in the chain.
Within <answer> </answer>, which means the reasoning is finished, you can generate the final answer for the [Question] by referring to the [Query]-[Answer] pairs, starting with [Final Content] and marking the number for each [Answer].
You must give the final answer by "So the final answer is ". """ + """\n###User: [Description of the patient]: {}
[Symptoms, Medical History, and Test Results]: {}
[Question]: {}
### Assistant: """.format(sources['description'],sources['bingqing'],sources['question'])
    prefix_ids = tokenizer(
        prefix,
        return_tensors="pt",
        padding="longest",
        max_length=max_leng,
        truncation=True,
    ).input_ids

    targets = input_ids.clone()

    targets[0][:len(prefix_ids[0])] = IGNORE_INDEX

    # mask掉所有的answer
    target_query = torch.tensor([386]) #query
    target_answer = torch.tensor([22550])  # answer
    answer_idx = []
    query_idx = []
    # 查询连续值的起始索引
    # print('response is {}'.format(response))
    # print('ids is {}'.format(tokenizer(
    #     response,
    #     return_tensors="pt",
    #     padding="longest",
    #     max_length=1024,
    #     truncation=True,
    # ).input_ids))
    for i in range(len(prefix_ids[0]), len(targets[0]) - len(target_query) + 1):
        if torch.equal(targets[0][i:i + len(target_query)], target_query):
            try:
                if targets[0][i+1] == 682 and targets[0][i+4] == 29958 and targets[0][i-3] == 29966:
                    query_idx.append(i+4)
            except:
                continue

    for i in range(len(prefix_ids[0]), len(targets[0]) - len(target_answer) + 1):
        if torch.equal(targets[0][i:i + len(target_answer)], target_answer):
            try:
                if targets[0][i + 3] == 29962 or targets[0][i+3] == 5387:
                    answer_idx.append(i-2)
            except:
                continue

    print('len query idx {} len answer idx {}'.format(len(query_idx),len(answer_idx)))
    print('query idx {}'.format(query_idx))
    print('answer idx {}'.format(answer_idx))

    for q_a_idx in range(min(len(query_idx)-1,len(answer_idx)-1)):
        targets[0][query_idx[q_a_idx]:answer_idx[q_a_idx]] = IGNORE_INDEX

    return dict(
        input_ids=input_ids,
        labels=targets,
    )

class LazySupervisedDataset(Dataset):
    """Dataset for supervised fine-tuning."""

    def __init__(self, data_path: str,
                 tokenizer: transformers.PreTrainedTokenizer,):
        super(LazySupervisedDataset, self).__init__()
        #list_data_dict = joblib.load(data_path)
        list_data_dict = []
        with open(data_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                list_data_dict.append(data)
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.list_data_dict)

    @property
    def lengths(self):
        length_list = []
        for sample in self.list_data_dict:
            img_tokens = 128 if 'image' in sample else 0
            length_list.append(sum(len(conv['value'].split()) for conv in sample['conversations']) + img_tokens)
        return length_list

    @property
    def modality_lengths(self):
        length_list = []
        for sample in self.list_data_dict:
            cur_len = sum(len(conv['value'].split()) for conv in sample['conversations'])
            cur_len = cur_len if 'image' in sample else -cur_len
            length_list.append(cur_len)
        return length_list

    def __getitem__(self, i):
        sources = self.list_data_dict[i]
        if i % 2 == 0:
            data_dict = preprocess(
                sources,
                self.tokenizer)
        else:
            data_dict = preprocess_train_answer(
                sources,
                self.tokenizer)
        #print(data_dict["input_ids"].shape)
        if isinstance(i, int):
            data_dict = dict(input_ids=data_dict["input_ids"][0],
                             labels=data_dict["labels"][0])
        return data_dict

@dataclass
class DataCollatorForSupervisedDataset(object):
    """Collate examples for supervised fine-tuning."""

    tokenizer: transformers.PreTrainedTokenizer

    def __call__(self, instances):
        input_ids, labels = tuple([instance[key] for instance in instances]
                                  for key in ("input_ids", "labels"))
        input_ids = torch.nn.utils.rnn.pad_sequence(
            input_ids,
            batch_first=True,
            padding_value=self.tokenizer.pad_token_id)

        labels = torch.nn.utils.rnn.pad_sequence(labels,
                                                 batch_first=True,
                                                 padding_value=IGNORE_INDEX)
        input_ids = input_ids[:, :self.tokenizer.model_max_length]
        labels = labels[:, :self.tokenizer.model_max_length]

        batch = dict(
            input_ids=input_ids,
            labels=labels,
            attention_mask=input_ids.ne(self.tokenizer.pad_token_id),
        )

        return batch

def main():
    args = parse_args()

    if args.local_rank == -1:
        device = torch.device(get_accelerator().device_name())
    else:
        get_accelerator().set_device(args.local_rank)
        device = torch.device(get_accelerator().device_name(), args.local_rank)
        # Initializes the distributed backend which will take care of sychronizing nodes/GPUs
        # torch.distributed.init_process_group(backend='nccl')
        deepspeed.init_distributed()

    args.global_rank = torch.distributed.get_rank()

    ds_config = get_train_ds_config(offload=args.offload,
                                    dtype=args.dtype,
                                    stage=args.zero_stage,
                                    enable_tensorboard=args.enable_tensorboard,
                                    tb_path=args.tensorboard_path,
                                    tb_name="step1_model")
    ds_config[
        'train_micro_batch_size_per_gpu'] = args.per_device_train_batch_size
    ds_config[
        'train_batch_size'] = args.per_device_train_batch_size * torch.distributed.get_world_size(
        ) * args.gradient_accumulation_steps

    # If passed along, set the training seed now.
    set_random_seed(args.seed)

    torch.distributed.barrier()

    # load_hf_tokenizer will get the correct tokenizer and set padding tokens based on the model family
    additional_special_tokens = args.eot_token if args.add_eot_token else None
    tokenizer = load_hf_tokenizer(args.model_name_or_path,
                                  fast_tokenizer=True,
                                  add_special_tokens=additional_special_tokens)

    model = create_hf_model(LlamaForCausalLM,
                            args.model_name_or_path,
                            tokenizer,
                            ds_config,
                            dropout=args.dropout)

    if args.compute_fp32_loss:
        print_rank_0(
            f"Using model {model.__class__.__name__} with loss in fp32",
            args.global_rank)
        causal_lm_model_to_fp32_loss(model)

    if args.lora_dim > 0:
        model = convert_linear_layer_to_lora(model, args.lora_module_name,
                                             args.lora_dim)
        if args.only_optimize_lora:
            model = only_optimize_lora_parameters(model)
            model = make_model_gradient_checkpointing_compatible(model)

    # Prepare the data
    train_phase = 1
    import joblib
    #data_list = joblib.load(args.nli_path)
    train_dataset = LazySupervisedDataset(data_path=args.sft_path,tokenizer=tokenizer)
    eval_dataset = LazySupervisedDataset(data_path=args.sft_path,tokenizer=tokenizer)
    data_collator = DataCollatorForSupervisedDataset(tokenizer=tokenizer)
    # DataLoaders creation:
    if args.local_rank == -1:
        train_sampler = SequentialSampler(train_dataset)
        print('sequence sampling')
        eval_sampler = SequentialSampler(eval_dataset)
    else:
        train_sampler = DistributedSampler(train_dataset)
        eval_sampler = DistributedSampler(eval_dataset)
    train_dataloader = DataLoader(train_dataset,
                                  collate_fn=data_collator,
                                  sampler=train_sampler,
                                  batch_size=args.per_device_train_batch_size)
    eval_dataloader = DataLoader(eval_dataset,
                                 collate_fn=data_collator,
                                 sampler=eval_sampler,
                                 batch_size=args.per_device_eval_batch_size)

    def evaluation(model, eval_dataloader):
        model.eval()
        losses = 0
        for step, batch in enumerate(eval_dataloader):
            batch = to_device(batch, device)
            with torch.no_grad():
                outputs = model(**batch)

            loss = outputs.loss
            losses += loss.float()
        losses = losses / (step + 1)
        try:
            losses = get_all_reduce_mean(losses)
        except:
            pass
        try:
            perplexity = torch.exp(losses).item()
        except OverflowError:
            perplexity = float("inf")
        return perplexity, losses.item()

    # Split weights in two groups, one with weight decay and the other not.
    optimizer_grouped_parameters = get_optimizer_grouped_parameters(
        model, args.weight_decay, args.lora_learning_rate)

    AdamOptimizer = DeepSpeedCPUAdam if args.offload else FusedAdam
    optimizer = AdamOptimizer(optimizer_grouped_parameters,
                              lr=args.learning_rate,
                              betas=(0.9, 0.95))

    num_update_steps_per_epoch = math.ceil(
        len(train_dataloader) / args.gradient_accumulation_steps)
    lr_scheduler = get_scheduler(
        name=args.lr_scheduler_type,
        optimizer=optimizer,
        num_warmup_steps=args.num_warmup_steps,
        num_training_steps=args.num_train_epochs * num_update_steps_per_epoch,
    )

    model, optimizer, _, lr_scheduler = deepspeed.initialize(
        model=model,
        optimizer=optimizer,
        args=args,
        config=ds_config,
        lr_scheduler=lr_scheduler,
        dist_init_required=True)

    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()

    # Train!
    print_rank_0("***** Running training *****", args.global_rank)
    # print_rank_0(
    #     f"***** Evaluating perplexity, Epoch {0}/{args.num_train_epochs} *****",
    #     args.global_rank)
    # perplexity, eval_loss = evaluation(model, eval_dataloader)
    # print_rank_0(f"ppl: {perplexity}, loss: {eval_loss}", args.global_rank)

    for epoch in range(args.num_train_epochs):
        print_rank_0(
            f"Beginning of Epoch {epoch+1}/{args.num_train_epochs}, Total Micro Batches {len(train_dataloader)}",
            args.global_rank)
        model.train()
        import time
        for step, batch in enumerate(train_dataloader):
            start = time.time()
            batch = to_device(batch, device)
            outputs = model(**batch, use_cache=False)
            loss = outputs.loss
            if args.print_loss:
                print(
                    f"Epoch: {epoch}, Step: {step}, Rank: {torch.distributed.get_rank()}, loss = {loss}"
                )
            model.backward(loss)
            model.step()
            end = time.time()
            if torch.distributed.get_rank() == 0:
                print_throughput(model.model, args, end - start,
                                 args.global_rank)

        model.tput_timer.update_epoch_count()

    if args.output_dir is not None:
        print_rank_0('saving the final model ...', args.global_rank)
        model = convert_lora_to_linear_layer(model)

        if args.global_rank == 0:
            save_hf_format(model, tokenizer, args)

        if args.zero_stage == 3:
            # For zero stage 3, each gpu only has a part of the model, so we need a special save function
            # save_zero_three_model(model,
            #                       args.global_rank,
            #                       args.output_dir,
            #                       zero_stage=args.zero_stage)
            save_zero_three_model(model, global_rank=0, save_dir=args.output_dir, zero_stage=args.zero_stage, max_shard_size=2000 * 1024 * 1024)

if __name__ == "__main__":
    main()
