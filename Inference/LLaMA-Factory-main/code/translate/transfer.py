import torch
import opencc
import requests
from flask import Flask, request, jsonify
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

import zhconv

#file_path = "/data1/weizihao/gemma/gemma-7b-it"
file_path = "/data1/weizihao/Qwen1.5-7B-Chat"
#file_path = "/data1/weizihao/MiniCPM-2B-sft-bf16"

tokenizer = AutoTokenizer.from_pretrained(file_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(file_path, device_map='cuda:2', torch_dtype=torch.float16, trust_remote_code=True)

example = [{
    'en' : "We are pleased to announce the launch of our new product next month which we believe will significantly impact the market.\n",
    'ja' : "来月、新商品を発売することを嬉しく思います。これが市場に大きな影響を与えると信じています。\n",
    'zhhant' : "我们很高兴地宣布，下个月将推出我们的新产品，我们相信这将对市场产生重大影响。\n",
    'zhhans' : "我们很高兴地宣布，下个月将推出我们的新产品，我们相信这将对市场产生重大影响。\n",
    'zhhanc' : "我们很高兴地宣布，下个月将推出我们的新产品，我们相信这将对市场产生重大影响。\n",
}]

app = Flask(__name__)

def process_data(text, source, target):
    # 在这里调用 Transformer 模型处理数据
    if target == "en": 
        chat = [
            { "role": "system", "content": f"""As an excellent translator, you are required to accurately translate the provided text into English. Ensure the translation meets the following standards:
Accuracy: The translation must remain faithful to the original text, without adding, omitting, or altering the intended meaning.
Fluency: The translation should be smooth and natural, conforming to English linguistic habits.
Cultural Adaptability: For content that includes specific cultural references, make appropriate adjustments to better suit the understanding of English readers."""},
            { "role": "user", "content": f"""Translate the following text into English: {example[0][source]}"""},
            { "role": "assistant", "content": example[0][target]},
            { "role": "user", "content": f"""Translate the following text into English: {text}"""},
        ]

    if target == "ja": 
        chat = [
            { "role": "system", "content": f"""As an excellent translator, you are required to accurately translate the provided text into Japanese. Ensure the translation meets the following standards:
Accuracy: The translation must remain faithful to the original text, without adding, omitting, or altering the intended meaning.
Fluency: The translation should be smooth and natural, conforming to Japanese linguistic habits.
Cultural Adaptability: For content that includes specific cultural references, make appropriate adjustments to better suit the understanding of Japanese readers."""},
            { "role": "user", "content": f"""Translate the following text into Japanese: {example[0][source]}"""},
            { "role": "assistant", "content": example[0][target]},
            { "role": "user", "content": f"""Translate the following text into Japanese: {text}"""},
        ]
        
    if target == "zhhans" or target == "zhhant" or target == "zhhanc": 
        chat = [
            { "role": "system", "content": f"""作为一个优秀的翻译器，你需要将提供的文本准确无误地翻译成中文。请确保翻译符合以下标准：
准确性：翻译内容需完全忠实于原文，不添加、省略或改变原文意思。
流畅性：翻译结果应流畅自然，符合中文语言习惯。
文化适应性：对于包含特定文化背景的内容，应适当调整，使其更符合当地读者的理解。
"""},
            { "role": "user", "content": f"""将接下来这段文本翻译成为中文: {example[0][source]}"""},
            { "role": "assistant", "content": example[0][target]},
            { "role": "user", "content": f"""将接下来这段文本翻译成为中文: {text}"""},
        ]

    prompt = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
    print(f"prompt {prompt}")
    processed_data = tokenizer.encode(prompt, return_tensors="pt")
    return processed_data

Token_Map = {
    "zhhanc" : "Cantonese",
    "zhhant" : "Traditional Chinese",
    "zhhans" : "Chinese (Simplified)",
    "en" : "English",
    "ja" : "Japanese",
}

def process_data_1(text, source, target):

    source = Token_Map[source]
    target = Token_Map[target]

    chat = [{
        "role" : "user" , 
        "content" : f"""You are a multilingual translation assistant proficient in Chinese (Simplified), Japanese, English, Cantonese, and Traditional Chinese. Your task is to translate text between these languages accurately and contextually.

When translating, follow these guidelines:
1. Preserve the original meaning and context of the text.
2. Maintain the appropriate tone and style for the target language.
3. Ensure that technical terms, names, and specific terminology are translated correctly.

Please perform the following translations, and output only the translated text without any additional comments or explanations:

1. Translate the following text from **{source} to {target}**:
{text}"""}]
    
    prompt = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
    print(f"prompt {prompt}")
    processed_data = tokenizer.encode(prompt, return_tensors="pt")
    return processed_data

@app.route('/v1/api/text/transfer', methods=['POST'])
def translate_text():
    # 获取 JSON 数据
    data = request.get_json()
    
    if not data or 'content' not in data or 'currentLanguage' not in data or 'targetLanguage' not in data:
        return jsonify({'error': 'Missing required parameters'}), 400

    # 获取请求中的数据
    text = data['content']
    source_language = data['currentLanguage']
    target_language = data['targetLanguage']

    translated_text = fake_translation(text, source_language, target_language)

    print(translated_text)

    # 返回处理后的数据
    return jsonify({'message': translated_text, 'statusCode': 200, 'data': "#115420"})

def fake_translation(text, source, target):
    inputs = process_data_1(text, source, target)
    outputs_ids = model.generate(input_ids=inputs.to(model.device), temperature = 0.3, max_new_tokens=6000)
    outputs = tokenizer.decode(outputs_ids[0])
    #outputs = outputs.split("<AI>")[-1]
    outputs = outputs.split("assistant")[-1]
    print(outputs)
    #outputs = outputs.split("</s>")[0]
    outputs = outputs.split("<|im_end|>")[0]
    return outputs.strip()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=8067)
