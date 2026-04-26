import json
import time

from vllm import LLM, SamplingParams
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

import argparse

from tqdm import tqdm

import os
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--seed', type=int, default=42)
parser.add_argument('--cuda', type=str, default="7")
parser.add_argument('--utili', type=float, default=0.50)
parser.add_argument('--model_name', type=str, default="/data1/weizihao/Qwen2/Qwen2-7B-Instruct")
parser.add_argument('--input_file', type=str, default="/home/weizihao/sc/data/am.txt")
parser.add_argument('--output_file', type=str, default="/home/weizihao/sc/output/am_translate.json")
parser.add_argument('--temperature', type=float, default=0.)

args = parser.parse_args()

print(args)

os.environ["CUDA_VISIBLE_DEVICES"] = str(args.cuda)

Token_Map = {
    "zhhans" : "中文（简体）",
    "zhhanc" : "粤语 ",
    "zhhant" : "中文繁体",
    "en" : "英语",
    "ja" : "日语",
}

def get_template(text, source, target):

    source = Token_Map[source]
    target = Token_Map[target]

    chat = [
        {"role": "system", "content": f"""您是一位精通中文（简体）、英语、粤语和中文繁体的多语言翻译助理。您的主要任务是准确地在这些语言之间进行翻译，同时确保翻译的文本在语境和文化上与目标语言相符。

**翻译指南:**

1. **保留原意和语境:**
   - 确保翻译的文本传达出与源语言相同的信息和细微差别。

2. **保持适当的语气和风格:**
   - 根据目标语言的文化背景调整语气，无论是正式、非正式还是技术性语言。

3. **正确翻译技术术语和名称:**
   - 使用领域专用术语和正确的名称，必要时核对已有资源以确保准确性。

4. **融入本地化元素:**
   - 使用文化相关的表达、习语和参考，使翻译更能引起母语使用者的共鸣。
   - 根据需要调整度量单位、日期格式和其他地区特定的细节。

5. **加入常用粤语表达:**
   - 在翻译成粤语时，加入常用的粤语短语和表达以增强本地化和真实性。

5. **加入常用中文繁体表达:**
   - 在翻译成中文繁体时，加入台湾常用的短语和表达以增强本地化和真实性。

6. **仅输出翻译结果:**
   - 直接输出翻译文本，不附加任何指令或解释性描述文本。"""},
        {"role": "user", "content":  f"""请进行以下翻译，直接输出翻译文本，不带有任何指令或解释：
请将以下文本从中文(简体)翻译为粤语：大景如诗如画,每次来到都像是一次美妙的探险之旅!"""},
        {"role": "assistant", "content":  f"""大景如诗如画，每次嚟到都好似一次精彩嘅探险之旅！"""},
        {"role": "user", "content":  f"""请进行以下翻译，直接输出翻译文本，不带有任何指令或解释：
请将以下文本从{source}翻译为{target}：{text}"""},
   ]

    return tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)

if __name__ == "__main__":
    sampling_params = SamplingParams(
        temperature=args.temperature,
        seed=args.seed,
        max_tokens=8000,
        )

    model_name = args.model_name
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    llm = LLM(
        model=model_name,
        seed=args.seed,
        gpu_memory_utilization=args.utili,
        tensor_parallel_size=len(args.cuda.split(","))
    )

    """
    with open("/home/weizihao/sc/data/input.json", encoding='utf-8') as f:
        data = json.load(f)
    """

    data = []

    with open(args.input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()  # 移除行首行尾的空白字符
            data.append(line)

    prompts = []
    answer = []

    for i, line in enumerate(data):
        for (key, value) in Token_Map.items():
            if key == "en":
                continue
            prompts.append(get_template(line, 'zhhans', key))

    print(len(prompts))

    outputs = llm.generate(prompts, sampling_params)

    for output in outputs:
        prompt = output.prompt
        generated_text = output.outputs[0].text
        answer.append({
            'input' : prompt,
            'output' : generated_text,
        })


    #with open(f"/home/weizihao/sc/output/translate_v2.json", 'w+', encoding='utf-8') as f:
    with open(args.output_file, 'w+', encoding='utf-8') as f:
        json.dump(answer, f, ensure_ascii=False, indent=4)