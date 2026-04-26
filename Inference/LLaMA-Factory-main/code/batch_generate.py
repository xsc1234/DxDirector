import torch
import time
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

file_path = "/data1/weizihao/nllb-200-3.3B"

# 加载模型和tokenizer
tokenizer = AutoTokenizer.from_pretrained(file_path, src_lang = "zho_Hans", trust_remote_code=True)
model = AutoModelForSeq2SeqLM.from_pretrained(file_path, device_map='cuda:0', torch_dtype=torch.float16, trust_remote_code=True)

# 语言代码映射
Token_Map = {
    "zhhanc" : "yue_Hant",
    "zhhant" : "zho_Hant",
    "zhhans" : "zho_Hans",
    "en" : "eng_Latn",
    "ja" : "jpn_Jpan",
}

# 生成长度为100个token的输入样例
def generate_sample_text(token_length=100):
    # 生成大约100个token的样例文本
    sample_text = "这是一段测试文本。" * (token_length // len(tokenizer.tokenize("这是一段测试文本。")))
    tokens = tokenizer.tokenize(sample_text)
    print(tokens)
    if len(tokens) > token_length:
        tokens = tokens[:token_length]
    sample_text = tokenizer.convert_tokens_to_string(tokens)
    return sample_text

# 翻译函数
def translation(texts, source, target):
    input_ids = tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
    generated_tokens = model.generate(**input_ids.to(model.device), forced_bos_token_id=tokenizer.convert_tokens_to_ids("eng_Latn"))
    output_texts = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
    return output_texts

# 生成100个token长度的测试样例
sample_text = generate_sample_text(token_length=100)

# 批量生成100条文本
batch_texts = [sample_text] * 100

# 设置源语言和目标语言
source_language = Token_Map["zhhans"]
target_language = Token_Map["en"]

# 测量翻译时间
start_time = time.time()
translated_texts = translation(batch_texts, source_language, target_language)
end_time = time.time()

# 输出翻译时间
print(f"Time taken to translate 100 texts: {end_time - start_time} seconds")

# 输出翻译结果的前几个示例
print(f"Sample translated text: {translated_texts[:5]}")