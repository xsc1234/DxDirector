import torch
import requests
from flask import Flask, request, jsonify
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

#file_path = "/home/nllb-200-3.3B"
file_path = "/data1/culture/sc_qwen/nllb-200-3.3B"

tokenizer = AutoTokenizer.from_pretrained(file_path, trust_remote_code=True)
model = AutoModelForSeq2SeqLM.from_pretrained(file_path, device_map='cuda:0', torch_dtype=torch.float16, trust_remote_code=True)

app = Flask(__name__)

"""
粤语 zhhanc
台湾 zhhant
简体 zhhans
"""

def translation(text, source, target):
    tokenizer.src_lang = source
    input_ids = tokenizer(text, return_tensors="pt")
    generated_tokens = model.generate(**input_ids.to(model.device), forced_bos_token_id=tokenizer.lang_code_to_id[target])
    output_text = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
    return output_text

@app.route('/v1/api/text/translate', methods=['POST'])
#@app.route('/translate', methods=['POST'])
def translate_text():
    # 获取 JSON 数据
    data = request.get_json()
    
    if not data or 'content' not in data or 'currentLanguage' not in data or 'targetLanguage' not in data:
        return jsonify({'error': 'Missing required parameters'}), 400

    Token_Map = {
        "zhhanc" : "yue_Hant",
        "zhhant" : "zho_Hant",
        "zhhans" : "zho_Hans",
        "en" : "eng_Latn",
        "ja" : "jpn_Jpan",
    }

    # 获取请求中的数据
    text = data['content']
    source_language = Token_Map[data['currentLanguage']]
    target_language = Token_Map[data['targetLanguage']]


    translated_text = translation(text, source_language, target_language)
    translated_text = translated_text[0] 

    print(translated_text)

    # 返回处理后的数据
    return jsonify({'message': translated_text, 'statusCode': 200, 'data': "#115420"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=8066)
