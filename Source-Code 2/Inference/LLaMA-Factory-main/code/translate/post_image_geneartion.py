import requests
import json
import base64
# 目标 URL
#url = 'http://localhost:12345/v1/api/text/translate'
#url = 'http://172.22.1.23:12345/v1/api/text/image_generation'
url = 'http://10.208.58.21:50011/v1/api/text/image_generation'
#url = 'http://127.0.0.1:50011/v1/api/text/image_generation'
# 要发送的数据
data = {
    'content': 'a book',  # 图像生成指令
}


response = requests.post(url, json=data)

# 检查响应
if response.status_code == 200:
    print("成功接收到响应！")
    response_data = response.json()
    # 检查返回的状态码
    if response_data.get('statusCode') == 200:
        #print("生成成功：", response_data.get('message'))
        print('生成成功')
        with open('1.jpg', 'wb') as file:
            base64_image = response_data.get('message')
            jiema = base64.b64decode(base64_image)  # 解码
            file.write(jiema)
        print("返回的数据ID：", response_data.get('data'))
    else:
        print("生成失败，状态码：", response_data.get('statusCode'))
else:
    print("生成失败，HTTP 状态码：", response.status_code)