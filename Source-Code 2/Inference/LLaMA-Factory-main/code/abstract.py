from flask import Flask, request, jsonify
from transformers import LlamaTokenizer, LlamaForCausalLM
import torch
import re
from typing import List
from jieba import analyse
import torch
from openai import OpenAI
from transformers import LlamaTokenizer, LlamaForCausalLM
from flask import Flask, request

# tokenizer = LlamaTokenizer.from_pretrained("/home/shared_usrQwen1.5-0.5B", use_fast=False)
# tokenizer.padding_side = 'left'
# model = LlamaForCausalLM.from_pretrained("/home/shared_usrQwen1.5-0.5B", low_cpu_mem_usage=True).half()

openai_api_key = "EMPTY"
openai_api_base = "http://localhost:8061/v1"

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)

NER_TEMPLATE = '''从给定的文本中准确抽取以下类型的实体，包括人名，地点，时间，国家，专有名词等。按照以下要求生成: 以##开头，多个实体之间使用逗号‘,’隔开。如果没有则不填写。文本可能有多种语言构成，你不需要翻译它们。下面是一些例子: 

文本：伦敦 — 中国国家主席习近平在周二（5月7日）晚上结束对法国为期两天的访问时，几乎没有向接待他的法国总统埃马纽埃尔·马克龙（Emmanuel Macron）做出任何让步。在两国关系因贸易争端和北京支持俄罗斯入侵乌克兰而有所恶化后，两国元首都在习近平五年来首次访问欧洲之际寻求修复关系。

##人名: 习近平, 埃马纽埃尔·马克龙
##地点: 伦敦, 法国, 乌克兰
##时间: 5月7日
##国家: 中国, 法国, 俄罗斯
##专有名词: 



文本：新華社通信、ワシントン、4月26日 米国各地の大学での反戦デモはここ1週間で激化し、ガザ地区での恒久的な停戦と米国のイスラエルへの軍事援助の停止を要求している。反戦の波に直面して、バイデン大統領は今週、イスラエルへの軍事援助を増やすため巨額の対外援助充当法案に署名した。米国警察は数百人の抗議参加者を逮捕。

##人名: バイデン大統領
##地名: ワシントン,ガザ地区,米国,イスラエル
##时间: 4月26日,ここ1週間
##国家: 米国,イスラエル
##专用名词: 反戦デモ,ガザ地区,イスラエル,米国警察



文本：倫敦 — 中國國家主席習近平在周二（5月7日）晚上結束對法國為期兩天的訪問時，幾乎沒有向接待他的法國總統馬克宏（Emmanuel Macron）做出任何讓步。在兩國關係因貿易爭端和北京支持俄羅斯入侵烏克蘭而惡化後，兩國元首都在習近平五年來首次訪問歐洲之際尋求修復關係。

##人名: 習近平, 馬克宏
##地点: 倫敦, 法國, 烏克蘭
##时间: 5月7日
##国家: 中國, 法國, 俄羅斯
##专有名词:



文本：倫敦 — 中國國家主席習近平喺星期二（5月7日）晚上結束對法國為期兩日嘅訪問時，幾乎冇向接待佢嘅法國總統埃馬紐埃爾 · 馬克龍（ Emmanuel Macron ）做出任何讓步。喺兩國關係因為貿易爭端同北京支持俄羅斯入侵烏克蘭而有所惡化之後，兩國元首都喺習近平五年來首次訪問歐洲之際尋求修復關係。

##人名: 習近平, 埃馬紐埃爾·馬克龍
##地点: 倫敦, 法國, 烏克蘭
##时间: 5月7日
##国家: 中國, 法國, 俄羅斯
##专有名词:



文本：{content}
'''

# 初始化Flask应用
app = Flask(__name__)

def keywords_extract_tfidf(datas):
    results = []
    for _data in datas:
        keywords_tfidf = analyse.extract_tags(_data , topK = 3, withWeight = False, allowPOS = ('n','ns','vn','v','nz'))
        results.append(keywords_tfidf)
    
    return results

def keywords_extract_textrank(datas):
    results = []
    for _data in datas:
        keywords_tfidf = analyse.textrank(_data , topK = 5, withWeight = False, allowPOS = ('n','ns','vn','v','nz'))
        results.append(keywords_tfidf)
    
    return results


def Ner_template(text):
    messages = [
        {"role": "system", "content": "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."},
        {"role": "user", "content": text}
    ]
    return messages

def Abs_template(text):
    chat = [
        {"role" : "system" , 
        "content" : """You are an AI language model tasked with summarizing text while ensuring that the summary is generated in the same language as the original input text. The input text will be in one of the following languages: English, Simplified Chinese, Traditional Chinese, Cantonese, or Japanese. Your task is to produce a concise and accurate summary that captures the key points and main ideas from the input, while preserving the original meaning, tone, and language.

Guidelines:
1. Generate the summary in the same language as the input.
2. Focus on the key arguments, themes, and main points of the text, avoiding irrelevant or minor details.
3. Ensure that the summary is coherent and consistent with the tone and style of the original text.
4. Adhere to the user's specific requirements regarding the length or focus of the summary.
5. Always maintain consistency in meaning between the original text and the summary."""},
        {"role" : "user" , 
        "content" : f"""{text}"""}
    ]

    return chat

@app.route("/v1/api/get_abstracts", methods=["POST"])
def get_abstractive():
    # data = request.get_json()
    data = request.get_json()
    required_fields = ['content']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    # 使用PROMPT_TEMPLATE构建prompt
    prompts = []

    for i, line in enumerate(data['content']):
        prompts.append(Abs_template(line))


    result_list=[]
    print(prompts)
    # 使用本地Vicuna模型生成文本
    try:
        for index in range(len(prompts)):
            chat_response = client.chat.completions.create(
            model="facebook/opt-125m",
            messages=prompts[index],
            )
            result_list.append(chat_response.choices[0].message.content)
            print(result_list)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"message":None, "statusCode":200, "data":result_list})

    # except Exception as e:
    #     return jsonify({"error": str(e)}), 500

def extract_entities(text):
    entities = {"PER": [], "LOC": [], "TIME": [], "NAT": [], "OTHER": []}
    patterns = {
            "PER": re.compile(r"##人名:([^#]+)"),
            "LOC": re.compile(r"##地名:([^#]+)"),
            "TIME": re.compile(r"##时间:([^#]+)"),
            "NAT": re.compile(r"##国家:([^#]+)"),
            "OTHER": re.compile(r"##专用名词:([^#]+)")
    }
    # entity_matches = entity_pattern.finditer(text)

    # for match in entity_matches:
    for key, pattern in patterns.items():
        match = pattern.search(text)
        if match:
            info_list = [info.strip() for info in match.group(1).split(",")]
            entities[key] = info_list
        # entity_type = match.group(1)
        # entity_list = match.group(2).strip().split("\n")

        # if entity_type == "人名":
        #     entities["PER"] = entity_list
        # elif entity_type == "地名":
        #     entities["LOC"] = entity_list
        # elif entity_type == "时间":
        #     entities["TIME"] = entity_list
        # elif entity_type == "国家":
        #     entities["NAT"] = entity_list
        # elif entity_type == "专用名词":
        #     entities["OTHER"] = entity_list

    return entities

# 输出实体
@app.route("/v1/api/get_entities", methods=["POST"])
def get_ner():

    data = request.get_json()
    required_fields = ['content']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    # 使用PROMPT_TEMPLATE构建prompt
    prompts = [Ner_template(NER_TEMPLATE.format(content=content)) for content in data['content']]


    result_list=[]

    try:
         for index in range(len(prompts)):
            # print(prompts[index])
            chat_response = client.chat.completions.create(
            model="facebook/opt-125m",
            messages=prompts[index],
            # max_token=3
            )
            print(chat_response.choices[0].message.content)
            entities = extract_entities(chat_response.choices[0].message.content)
            result_list.append(entities)
            print(entities)
        # inputs = tokenizer(prompts, return_token_type_ids=False, padding=True, return_tensors="pt", truncation=True).to(device)
        # inputs = {k: torch.tensor(v).to(device) for k, v in inputs.items()}

        # with torch.no_grad():
        #             output_ids = model.generate(
        #                 **inputs,
        #                 do_sample=True,
        #                 temperature=temperature,
        #                 top_k=5,
        #                 num_return_sequences=1)

        # outputs = tokenizer.batch_decode(output_ids, skip_special_tokens=True, spaces_between_special_tokens=False)

        # for index in range(len(outputs)):
        #         print(outputs[index].split("ASSISTANT:")[-1])
        #         result = outputs[index].split("ASSISTANT:")[-1].lstrip("\n")
        #         entities = extract_entities(result)
        #         result_list.append(entities)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"message":None, "statusCode":200, "data":result_list})


@app.route("/v1/api/media/keywords", methods=["POST"])
def get_keywords_tfidf():
    # 从POST请求中获取参数
    data = request.get_json()

    required_fields = ['content']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    try:
        # xx
        results = keywords_extract_tfidf(data['event'])
        print(results)
        return jsonify({"message":None, "statusCode":200, "data":results})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/v1/api/media/keywords", methods=["POST"])
def get_keywords_textrank():
    # 从POST请求中获取参数
    data = request.get_json()

    required_fields = ['content']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    try:
        results = keywords_extract_textrank(data['events'])
        print(results)
        return jsonify({"message":None, "statusCode":200, "data":results})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090, debug=True)
    # content = {"content": ["伦敦 — 中国国家主席习近平在周二（5月7日）晚上结束对法国为期两天的访问时，几乎没有向接待他的法国总统埃马纽埃尔·马克龙（Emmanuel Macron）做出任何让步。在两国关系因贸易争端和北京支持俄罗斯入侵乌克兰而有所恶化后，两国元首都在习近平五年来首次访问欧洲之际寻求修复关系。", "新华社华盛顿4月26日电　美国多地高校反战示威活动在过去一周愈演愈烈，要求加沙地带永久停火、美国停止军援以色列。面对反战浪潮，总统拜登则在本周签署巨额对外援助拨款法案，向以色列提供更多军援。美国警方逮捕数百名抗议者。"]}
    # get_abstractive(content)
    # get_ner(content)
    # datas = {"content":["受众在哪里，媒体就应该在哪里，媒体的体制、内容、技术就应该向哪里转变。", "媒体融合关键是以人为本，即满足大众的信息需求，为受众提供更优质的服zvbnm,", "这就要求媒体在融合发展的过程中，既注重技术创新，又注重用户体验。"]}
    # resutls = keywords_extract_tfidf(datas['content'])
    # print(resutls)

