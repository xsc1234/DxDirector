import os
import openai
import json
from tqdm import tqdm
import joblib
import time
# url
openai.api_base = 'xxxxxxxxxxxxxx'
# api
openai.api_key = "xxxxxxxxx"
prefix = ''

data_origin = joblib.load(prefix+'/MedQA_data_list')
with open(prefix+'/inst-ft_data_MedQA_extracted.json', 'a') as f:
    for idx, one_data in tqdm(enumerate(data_origin), total=len(data_origin)):
        if idx < 0:
            continue
        print(idx)
        time.sleep(0.5)
        question = one_data['question']
        options = ''
        for k, v in one_data['options'].items():
            options += k + ": " + v + ' '
        answer = one_data['answer']
        answer_idx = one_data['answer_idx']
        input_query = question
        S = """
Given a patient description [Original description], please accurately extract the content related to symptoms, medical history, and test results from this description [Extracted symptoms, medical history, and test results], and generate a new patient description [New description]. This new description should not contain the extracted symptoms, medical history, and test results, but rather a vague expression of the patient's condition from the perspective of a patient who is currently receiving treatment:
For example:
[Original description]: A 35-year-old male presents to his primary care physician complaining of a one-month history of progressively worsening fatigue. He sought medical attention because this has affected his ability to complete his work as a graduate student. As a child, he was hospitalized for hemolytic uremic syndrome. His past medical history is also notable for diabetes mellitus and obesity. He takes metformin and glyburide. He does not smoke and drinks alcohol occasionally. His family history is notable for chronic lymphocytic leukemia in his paternal uncle and stroke in his father. His temperature is 99.9°F (37.7°C), blood pressure is 100/70 mmHg, pulse is 110/min, and respirations are 18/min. Physical examination reveals diffuse pallor. Hematologic labs are shown below:\n\nHemoglobin: 8.9 g/dL\nHematocrit: 24%\nLeukocyte count: 7,500 cells/mm^3 with normal differential\nPlatelet count: 180,000/mm^3\nMean corpuscular volume: 85 µm^3\nReticulocyte count: 0.4%\n\nHead and neck imaging is negative for neck masses. The pathogen associated with this patient’s condition is also known to cause which of the following?
[Extracted symptoms, medical history, and test results]: Symptoms: One-month history of progressively worsening fatigue; diffuse pallor.
Medical history: Hospitalized as a child for hemolytic uremic syndrome; history of diabetes mellitus and obesity.
Medications: Metformin and glyburide.
Family history: Chronic lymphocytic leukemia in paternal uncle; stroke in father.
Social history: Does not smoke; drinks alcohol occasionally.
Vitals: Temperature 99.9°F (37.7°C); blood pressure 100/70 mmHg; pulse 110/min; respirations 18/min.
Hematologic labs:
Hemoglobin: 8.9 g/dL
Hematocrit: 24%
Leukocyte count: 7,500 cells/mm³ with normal differential
Platelet count: 180,000/mm³
Mean corpuscular volume: 85 µm³
Reticulocyte count: 0.4%
Imaging: Head and neck imaging negative for neck masses.
[New description]: A 35-year-old male has been receiving ongoing care for a condition that has caused fatigue and impacted his daily activities, including his academic responsibilities. He has a history of chronic medical issues and is currently undergoing evaluation and treatment to manage his condition and improve his well-being.
[Original description]: {}""".format(input_query)
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

                new_text = response["choices"][0]["message"]["content"]
                print(new_text)
                dict_temp = {}
                dict_temp['question'] = question
                dict_temp['input_query'] = input_query
                dict_temp['options'] = options
                dict_temp['answer'] = answer
                dict_temp['answer_idx'] = answer_idx
                dict_temp['response'] = new_text
                json.dump(dict_temp, f)
                f.write('\n')
                f.flush()
            except:
                print("request fail")
                success_flag = 0
