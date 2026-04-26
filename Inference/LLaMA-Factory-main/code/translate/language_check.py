import nltk
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

import requests
from flask import Flask, request, jsonify

import zhconv

app = Flask(__name__)

"""
中文粤语 zhhanc
中文台湾 zhhant
中文简体 zhhans
日语 ja
英语 en

"""

DetectorFactory.seed = 42

@app.route('/v1/api/text/langdetect', methods=['POST'])
#@app.route('/translate', methods=['POST'])
def translate_text():
    # 获取 JSON 数据
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({'error': 'Missing required parameters'}), 400

    print(data)

    # 获取请求中的数据
    text = data['content']

    try:
        language = detect(text)
        output = language
    except LangDetectException:
        output = "无法检测语言"

    if output == "zh-cn":
        output = "zhhans"
    if output == "zh-tw":
        output = "zhhant"

    # 返回处理后的数据
    return jsonify({'message': output, 'statusCode': 200})

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=8069)