import torch
import requests
import warnings
import re
from elasticsearch import Elasticsearch
from flask import Flask, request, jsonify


from openai import OpenAI

openai_api_key = "EMPTY"
openai_api_base = "http://172.22.1.23:8061/v1"

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)

app = Flask(__name__)

es = Elasticsearch(
    ['http://10.200.100.240:9200'],
    http_auth=('elastic', 'elastic')
)


def process_data(text):

    chat = [{
        "role" : "user" , 
        "content" : f"""请对以下文本进行立场判定，并从“支持”、“中立”、“反对”中选择一个答案。请不要输出其他任何信息。

文本：{text}

答案："""}]
    
    return chat

def stance_stability(time_stance):
    # 计算时间序列立场的标准差，标准差越低，立场稳定度越稳定
    # 计算时间序列的自相关性，，用于衡量时间序列中各个时间点的值与前一个时间点值的相关度。自相关系数接近1表示高稳定。
    # 计算时间序列中立场分数的变化率，变化率比较低表示立场稳定
    # 标准差大于0.5则不稳定，标准差小于0.5则稳定
    mean = sum(time_stance) / len(time_stance)
    variance = sum((x - mean) ** 2 for x in time_stance) / len(time_stance)
    std_dev = variance ** 0.5

    return std_dev

@app.route("/user_stance", methods=["POST"])
def event_stance():
    data = request.get_json()
    
    if not data or 'uid' not in data:
        return jsonify({'error': 'Missing required parameters'}), 400

    uid = data['uid']
    # 定义搜索查询
    query = {
        "query": {
            "match": {
                "uid": uid
            }
        }
    }
    # 执行搜索查询
    response = es.search(index="sc_news", body=query)
    user_stances = []
    for hit in response['hits']['hits']:
        text = hit['_source']['content']
        inputs = process_data(text)
        chat_response = client.chat.completions.create(
        model="facebook/opt-125m",
        messages=inputs,
        max_token=3
        )

        stance = chat_response.choices[0].message.content
        user_stances.append(stance)
    
    time_stance = []
    for senti in user_stances:
        if '支持' in senti:
            time_stance.append(1)
        elif '反对' in senti:
            time_stance.append(-1)
        else:
            time_stance.append(0)
    
    if sum(time_stance) > 0:
        event_stance = "支持"
    elif sum(time_stance) == 0:
        event_stance = "中立"
    else:
        event_stance = "反对"

    stability = stance_stability(time_stance)
    
    # 返回处理后的数据
    return jsonify({'user_stance':event_stance, "stance_stability":stability, 'statusCode': 200, 'data': "#115420"})
    

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10007, debug=True)

