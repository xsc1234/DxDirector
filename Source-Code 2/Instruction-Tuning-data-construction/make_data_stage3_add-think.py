import os
import openai
import json
from tqdm import tqdm
import joblib
import time
from prompt import Prompt_gpt_ask_assistant_o1_preview_with_mark_open_end_add_subthink
# url
openai.api_base = 'xxxxxxxxxxxxxxx'
# api
openai.api_key = "xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
data_origin = []
prefix = ''

with open(prefix+'/inst-ft_data_MedQA_ask_assistant_v3_with_mark_open-end.json', "r", encoding="utf-8") as file:
    for line in file:
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        data_origin.append(data)

with open(prefix+'/inst-ft_data_MedQA_ask_assistant_v3_with_mark_open-end-add-sub-think.json', 'a') as f:
    for idx, one_data in tqdm(enumerate(data_origin), total=len(data_origin)):
        if idx < 0:
            continue
        print(idx)
        time.sleep(0.5)
        question = one_data['question']
        doctor = one_data['response']
        description = one_data['description']
        reasoning = doctor.split('[Final Content]')[0]
        final_ans = '[Final Content]:\n' + doctor.split('[Final Content]')[-1]
        doctor = """{think_tag}
{reasoning}
{think_end_tag}
{answer_tag}
{solution}
{answer_end_tag}""".format(
               think_tag="<think>",
               reasoning=reasoning,
               think_end_tag="</think>",
               answer_tag="<answer>",
               solution=final_ans,
               answer_end_tag="</answer>")
        print('before: {}'.format(doctor))
        S = Prompt_gpt_ask_assistant_o1_preview_with_mark_open_end_add_subthink +\
"""### User:
[Description of the patient]: {}
[Question]: {}
[Doctor]:
{}

Please note that you cannot change anything else, you can only add thoughts in <sub-think> to make the logic tighter and smoother!
### Assistant:""".format(description,question,doctor)
        success_flag = 0
        while success_flag == 0:
            try:
                response = openai.ChatCompletion.create(
                    model="o1-preview",
                    temperature=0,
                    messages=[
                    {"role": "user", "content": S}],
                    timeout=50)
                success_flag = 1

                new_text = response["choices"][0]["message"]["content"].split('### Assistant:')[-1]
                dict_temp = one_data
                print(new_text)
                dict_temp['response'] = new_text
                json.dump(dict_temp, f)
                f.write('\n')
                f.flush()
            except:
                print("request fail")
                success_flag = 0
