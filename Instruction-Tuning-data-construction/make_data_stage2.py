import os
import openai
import json
from tqdm import tqdm
import joblib
import time
from prompt import Prompt_gpt_ask_assistant_v3_with_mark_open_end
# URL
openai.api_base = 'xxxxxxxxxxxxxxxxxxxx'
# API
openai.api_key = "xxxxxxxxxxxxxxxxxxxxx"
data_origin = []
prefix = ''

with open(prefix+'/inst-ft_data_MedQA_extracted.json', "r", encoding="utf-8") as file:
    for line in file:
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        data_origin.append(data)

with open(prefix+'/inst-ft_data_MedQA_ask_assistant_v3_with_mark_open-end.json', 'a') as f:
    for idx, one_data in tqdm(enumerate(data_origin), total=len(data_origin)):
        if idx < 0:
            continue
        print(idx)
        time.sleep(0.5)
        question = one_data['question'].split('. ')[-1]
        description = one_data['response'].split('[New description]:')[-1]
        bingqing = one_data['response'].split('[New description]:')[0].split('[Extracted symptoms, medical history, and test results]:')[-1]
        options = one_data['options']
        answer = one_data['answer']
        answer_idx = one_data['answer_idx']

        change_inst = """Please change this sentence into a question instead of asking which option: {}""".format(
            question)
        original_question = question
        success_flag = 0
        change_question = ''
        while success_flag == 0:
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o",
                    temperature=0,
                    messages=[
                        {"role": "user", "content": change_inst}],
                    timeout=50)
                success_flag = 1

                change_question = response["choices"][0]["message"]["content"]
            except:
                print("request fail")
                success_flag = 0
        question = change_question

        S = Prompt_gpt_ask_assistant_v3_with_mark_open_end + """###User: [Description of the patient]: {}
[symptoms, medical history, and test results]: {}
[Question]: {}
### Assistant: """.format(description,bingqing,question)
        success_flag = 0
        while success_flag == 0:
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o",
                    temperature=0,
                    messages=[
                    {"role": "user", "content": S}],
                    timeout=50)
                success_flag = 1

                new_text = response["choices"][0]["message"]["content"].split('### Assistant:')[-1]
                print(new_text)
                dict_temp = {}
                dict_temp['question'] = question
                dict_temp['description'] = description
                dict_temp['bingqing'] = bingqing
                dict_temp['options'] = options
                dict_temp['answer'] = answer
                dict_temp['answer_idx'] = answer_idx
                if not '[Patient\'s Special Query 1]' in new_text and not '[Knowledge Query 1]' in new_text:
                    dict_temp['response'] = '[Patient\'s Special Query 1] ' + new_text
                else:
                    dict_temp['response'] = new_text
                dict_temp['original_question'] = one_data['input_query']
                json.dump(dict_temp, f)
                f.write('\n')
                f.flush()
            except:
                print("request fail")
                success_flag = 0
