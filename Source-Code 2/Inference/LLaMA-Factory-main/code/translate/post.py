import requests
import json

# 目标 URL
#url = 'http://localhost:12345/v1/api/text/translate'
#url = 'http://172.22.1.23:8069/v1/api/text/translate'
url = 'http://0.0.0.0:8062/v1/api/text/transfer'
#url = 'http://localhost:18862/v1/api/text/translate'
#url = 'http://localhost:28062/v1/api/text/translate'
#url = 'http://localhost:28065/v1/api/get_abstracts'
#url = 'http://0.0.0.0:8067/v1/api/text/transfer'
#url = 'http://0.0.0.0:8077/v1/api/text/transfer'
#url = 'http://localhost:8862/v1/api/text/transfer'
#url = 'http://0.0.0.0:8090/v1/api/get_abstracts'
# url = 'http://0.0.0.0:8090//trymoregpt/v1/api/media/textMedias'
#url = 'http://0.0.0.0:18067/event_stance'

    # content = {"content": }
    # get_abstractive(content)

# 要发送的数据，例如翻译请求的内容
data = {
    #'content': ["伦敦 — 中国国家主席习近平在周二（5月7日）晚上结束对法国为期两天的访问时，几乎没有向接待他的法国总统埃马纽埃尔·马克龙（Emmanuel Macron）做出任何让步。在两国关系因贸易争端和北京支持俄罗斯入侵乌克兰而有所恶化后，两国元首都在习近平五年来首次访问欧洲之际寻求修复关系。", "新华社华盛顿4月26日电　美国多地高校反战示威活动在过去一周愈演愈烈，要求加沙地带永久停火、美国停止军援以色列。面对反战浪潮，总统拜登则在本周签署巨额对外援助拨款法案，向以色列提供更多军援。美国警方逮捕数百名抗议者。"],  # 假设我们要翻译的文本
    'content': "伦敦 — 中国国家主席习近平在周二（5月7日）晚上结束对法国为期两天的访问时，几乎没有向接待他的法国总统埃马纽埃尔·马克龙（Emmanuel Macron）做出任何让步。在两国关系因贸易争端和北京支持俄罗斯入侵乌克兰而有所恶化后，两国元首都在习近平五年来首次访问欧洲之际寻求修复关系。",
    "currentLanguage" : "zhhans",
    "targetLanguage" : "en",
}

#data = {
#     'content': ["伦敦 — 中国国家主席习近平在周二（5月7日）晚上结束对法国为期两天的访问时，几乎没有向接待他的法国总统埃马纽埃尔·马克龙（Emmanuel Macron）做出任何让步。在两国关系因贸易争端和北京支持俄罗斯入侵乌克兰而有所恶化后，两国元首都在习近平五年来首次访问欧洲之际寻求修复关系。", "新华社华盛顿4月26日电　美国多地高校反战示威活动在过去一周愈演愈烈，要求加沙地带永久停火、美国停止军援以色列。面对反战浪潮，总统拜登则在本周签署巨额对外援助拨款法案，向以色列提供更多军援。美国警方逮捕数百名抗议者。"],  # 假设我们要翻译的文本
#}

response = requests.post(url, json=data)

# 检查响应
if response.status_code == 200:
    print("成功接收到响应！")
    response_data = response.json()
    # 检查返回的状态码
    if response_data.get('statusCode') == 200:
        print("翻译成功：", response_data.get('message'))
        print("返回的数据ID：", response_data.get('data'))
    else:
        print("翻译失败，状态码：", response_data.get('statusCode'))
else:
    print("请求失败，HTTP 状态码：", response.status_code)
