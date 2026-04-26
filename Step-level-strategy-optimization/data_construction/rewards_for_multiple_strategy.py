import os
import openai
import json
from tqdm import tqdm
import joblib
import time
import random
openai.api_base = 'xxxxxxxxxxxxxxxxxxxx'
openai.api_key = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
import os
import sys
import json
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

from transformers import (
    AutoModelForCausalLM,
    LlamaForCausalLM,
    SchedulerType,
    GenerationConfig,
)

import deepspeed
IGNORE_INDEX = -100
from prompt import Prompt_gpt_ask_assistant_deepseek_with_mark_open_end_dpo
from openai import OpenAI

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
    parser.add_argument('--disable_dropout',
                        action='store_true',
                        help='Disable the dropout of the model.')
    # deepspeed features
    parser.add_argument('--offload',
                        action='store_true',
                        help='Enable ZeRO Offload techniques.')
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
    ## Tensorboard logging
    parser.add_argument('--enable_tensorboard',
                        action='store_true',
                        help='Enable tensorboard logging')
    parser.add_argument('--tensorboard_path',
                        type=str,
                        default="step1_tensorboard")
    ## Print loss
    parser.add_argument('--print_loss',
                        action='store_true',
                        help='Prints loss at each step.')
    parser = deepspeed.add_config_arguments(parser)
    args = parser.parse_args()

    return args


import re


def split_complex_string(input_str):
    split_result = [part.strip() for part in
                    re.split(r'(<sub-think \d+>)', input_str) if part.strip()]
    res_list = []
    # print('split:')
    # print(split_result)
    if len(split_result) % 2 == 1 and not 'sub-think' in split_result[0]:
        split_result = split_result[1:]
    for idx in range(0, len(split_result), 2):
        res_list.append(split_result[idx] + split_result[idx + 1])

    return res_list

def get_answer(text):
    pattern_1 = r"so the final answer is([^\.]+)"
    matches = re.findall(pattern_1, text.lower())
    return matches

def slm_generate(S,client,ground_truth,client_gpt_4):
    chat_response = client.chat.completions.create(model="medichain",
                                                   messages=[{"role": "user",
                                                              "content": S}])
    output = chat_response.choices[0].message.content.split(S)[-1]
    output = output.split('<think>')[-1]
    qa_pairs = output
    qa_list = output.split('</think>')[0]
    qa_list = split_complex_string(qa_list)

    final_answer = get_answer(output.split('</think>')[-1])
    inst = "[Option]: {} \n [Diagnosis]: {} \n Whether the [Diagnosis] meets the given [Option]? (Only answer Yes or No)".format(ground_truth,final_answer)
    judge = gpt_generate(client_gpt_4,inst)
    reward = 10
    if 'yes' in judge.lower():
        sub_string = '<Physician>'
        reward = 10 / qa_pairs.lower().count(sub_string)
    else:
        reward = 0

    return qa_list,reward


def gpt_generate(client,inst):
    success_flag = 0
    while success_flag == 0:
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                temperature=0,
                messages=[
                    {"role": "user", "content": inst}],
                timeout=50)
            success_flag = 1
            new_text = response.choices[0].message.content
            return new_text
        except:
            print("request fail")
            success_flag = 0


if __name__ == "__main__":
    prompt = """A conversation between User and Assistant. The user asks a question, and the Assistant solves it.
The assistant first thinks about the reasoning process in the mind and then provides the user with the answer.
The reasoning process and answer are enclosed within <think> </think> and <answer> </answer> tags, respectively.
Within <think> </think>, you are an experienced medical professional. Your current role is a doctor who is examining a patient to answer the [Question]. The patient's description is in [Description of the patient].
You should reason about the [Question] step by step. 
For each node of the chain, you should generate a query, starting with [Query number]. You must give the answer for [Query number], starting with [Answer number].
Each node of the chain can be a query and answer to the content about [symptoms, medical history, and test results] of the patient, or a query and answer to related medical knowledge.
Before generating each [Query], you should do some thinking within <sub-think> </sub-think> to clarify your motivation for generating this [Query].
You should mark the queries that ask for the content in [symptoms, medical history, and test results] with [Question to <Physician> ].
You should mark the queries that ask for the related objective medical knowledge with [Question to <LLM>].
Each query should arise naturally as part of the logical flow, ensuring that it aligns with the clinical reasoning process.
There should be strict logical connections between nodes, such as relevant medical knowledge or your medical experience
Emphasize again that you are now simulating a doctor who is consulting a patient. You do not know all the information about [symptoms, medical history, and test results], and you must obtain them through step-by-step reasoning in the form of self-questioning and self-answering in the chain.
Within <answer> </answer>, which means the reasoning is finished, you can generate the final answer for the [Question] by referring to the [Query]-[Answer] pairs, starting with [Final Content] and marking the number for each [Answer].
You must give the final answer by "So the final answer is ". """
    device = torch.device("cuda:1")
    # If passed along, set the training seed now.
    openai_api_key = "EMPTY"

    openai_api_base_clinchain = "http://localhost:29514/v1"
    client_clinchain = OpenAI(api_key=openai_api_key, base_url=openai_api_base_clinchain)


    client_gpt4 = OpenAI(
        api_key="sk-yBjf7xTuaiiT52nkB00a3f3cA71f4b14B514C6553f1d9059",
        base_url='https://api.gptapi.us/v1'
    )

    data_origin = []
    prefix = ''
    with open(prefix + '/inst-ft_data_MedQA_extracted.json', "r",
              encoding="utf-8") as file:
        for line in file:
            data = json.loads(line)
            data_origin.append(data)

    data_origin = data_origin[8000:]

    data_final = []

    with open(prefix + '/slso_data.json', 'w') as f:
        for idx, one_data in tqdm(enumerate(data_origin), total=len(data_origin)):
            try:
                if idx < 0:
                    continue
                print(idx)
                data_temp = {}

                question = one_data['question']
                description = one_data['description']
                bingqing = one_data['bingqing']

                data_temp['question'] = one_data['question']
                data_temp['description'] = one_data['description']
                data_temp['bingqing'] = one_data['bingqing']
                data_temp['options'] = one_data['options']
                data_temp['answer'] = one_data['answer']
                data_temp['answer_idx'] = one_data['answer_idx']
                data_temp['original_question'] = one_data['original_question']
                data_temp['data_point'] = []
                inst = """[Description of the patient]: {}\n[Question]: {}\n""".format(description, question)
                slm_input = prompt + """\n###User: {question} \n### Assistant: {think_tag}""".format(question=inst,think_tag='<think>')
                slm_input_prefix = slm_input

                gpt_input = Prompt_gpt_ask_assistant_deepseek_with_mark_open_end_dpo + """\nUser: [Description of the patient]: {}
[symptoms, medical history, and test results]: {}
[Question]: {}
Assistant: """.format(description,bingqing,question)

                now_idx = 1
                sample_k = 0
                slm_qa_at_each_step = []
                finish_flag = False
                while not finish_flag:
                    max_slm_qa_list = 0
                    while sample_k < 3:
                        random.seed(sample_k)
                        slm_qa_list, reward = slm_generate(S=slm_input, client=client_clinchain, now_idx=now_idx)
                        sample_k += 1
                        print('now idx is {}'.format(now_idx))
                        for s_idx in range(len(slm_qa_list)):
                            if '[Answer {}]'.format(now_idx) in slm_qa_list[s_idx]:
                                if ']' in slm_qa_list[s_idx][:5]:
                                    slm_qa_now = slm_qa_list[s_idx][4:]
                                else:
                                    slm_qa_now = slm_qa_list[s_idx]
                                break
                        if len(slm_qa_list) > max_slm_qa_list:
                            max_slm_qa_list = len(slm_qa_list)
                        slm_q = slm_qa_now.split(' Question {}]'.format(now_idx))[0]
                        slm_qa_at_each_step.append((slm_q, reward, slm_qa_now))

                    if now_idx > 1:
                        slm_qa_at_each_step.sort(key=lambda x: x[1], reverse=True)
                        for pos_i in range(3):
                            for neg_i in range(pos_i+1,3):
                                data_temp['data_point'].append(
                                    {'prefx': slm_input, 'pos': slm_qa_at_each_step[pos_i][0], 'neg': slm_qa_at_each_step[neg_i][0]})

                    slm_input += '\n\n' + slm_qa_now
                    now_idx += 1
                    if now_idx >= max_slm_qa_list:
                        finish_flag = True

                json.dump(data_temp, f)
                f.write('\n') 
                f.flush()  
            except:
                pass