import torch
import requests
from flask import Flask, request, jsonify

from openai import OpenAI

openai_api_key = "EMPTY"
openai_api_base = "http://localhost:8072/v1"

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)


example = [{
    'en' : "We are pleased to announce the launch of our new product next month which we believe will significantly impact the market.\n",
    'ja' : "来月、新商品を発売することを嬉しく思います。これが市場に大きな影響を与えると信じています。\n",
    'zhhant' : "我们很高兴地宣布，下个月将推出我们的新产品，我们相信这将对市场产生重大影响。\n",
    'zhhans' : "我们很高兴地宣布，下个月将推出我们的新产品，我们相信这将对市场产生重大影响。\n",
    'zhhanc' : "我们很高兴地宣布，下个月将推出我们的新产品，我们相信这将对市场产生重大影响。\n",
}]

app = Flask(__name__)

Token_Map = {
    "zhhanc" : "Cantonese",
    "zhhant" : "Traditional Chinese",
    "zhhans" : "Chinese (Simplified)",
    "en" : "English",
    "ja" : "Japanese",
}

def process_data(text, source, target):

    source = Token_Map[source]
    target = Token_Map[target]

    chat = [{
        "role" : "system" , 
        "content" : f"""You are a multilingual translation assistant proficient in Chinese (Simplified), Japanese, English, Cantonese, and Traditional Chinese. Your task is to translate text between these languages accurately and contextually.

When translating, follow these guidelines:
1. Preserve the original meaning and context of the text.
2. Maintain the appropriate tone and style for the target language.
3. Ensure that technical terms, names, and specific terminology are translated correctly.
4. Translate all words, including proper nouns, geographical locations, and idiomatic expressions, into the target language.
5. If a direct translation is not available for a specific term or phrase, provide an explanatory translation or the closest equivalent within the context of the target language."""},
        {"role" : "user" , 
        "content" : f"""Please perform the following translations, and output only the translated text without any additional comments or explanations:

Translate the following text from **{source} to {target}**:
{text}"""}]

    return chat

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

    inputs = process_data(text, source_language, target_language)

    chat_response = client.chat.completions.create(
        model="facebook/opt-125m",
        messages=inputs,
    )

    print(chat_response.choices[0].message.content)

    # 返回处理后的数据
    return jsonify({'message': chat_response.choices[0].message.content, 'statusCode': 200, 'data': "#115420"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=8077)
