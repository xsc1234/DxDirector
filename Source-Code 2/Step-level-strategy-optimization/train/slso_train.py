import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
grandparent_dir = os.path.dirname(parent_dir)
sys.path.append(grandparent_dir)

import torch
from datasets import load_dataset
from my_transformers_2 import AutoModelForCausalLM, AutoTokenizer

from trl import (
    DPOConfig,
    DPOTrainer,
    ModelConfig,
    ScriptArguments,
    TrlParser,
    get_kbit_device_map,
    get_peft_config,
    get_quantization_config,
)
from trl.trainer.utils import SIMPLE_CHAT_TEMPLATE

import json
from torch.utils.data import Dataset
from datasets import Dataset as ds

class LazySupervisedDataset(Dataset):
    """Dataset for training."""

    def __init__(self, data_path: str):
        list_data_dict = []
        with open(data_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                for data_point in data['data_point']:
                    dict_temp = {}
                    dict_temp['prompt'] = data_point['prefix']
                    dict_temp['chosen'] = '\n\n' + data_point['pos']
                    dict_temp['rejected'] = '\n\n' + data_point['neg']
                    list_data_dict.append(dict_temp)
        self.list_data_dict = list_data_dict

    def __len__(self):
        return len(self.list_data_dict)

    def __getitem__(self, i):
        return self.list_data_dict[i]

if __name__ == "__main__":
    parser = TrlParser((ScriptArguments, DPOConfig, ModelConfig))
    script_args, training_args, model_config = parser.parse_args_and_config()

    ################
    # Model & Tokenizer
    ###################
    # torch_dtype = (
    #     model_config.torch_dtype
    #     if model_config.torch_dtype in ["auto", None]
    #     else getattr(torch, model_config.torch_dtype)
    # )
    torch_dtype = torch.bfloat16
    quantization_config = get_quantization_config(model_config)
    model_kwargs = dict(
        revision=model_config.model_revision,
        attn_implementation=model_config.attn_implementation,
        torch_dtype=torch_dtype,
        use_cache=False if training_args.gradient_checkpointing else True,
        device_map=get_kbit_device_map() if quantization_config is not None else None,
        quantization_config=quantization_config,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_config.model_name_or_path, trust_remote_code=model_config.trust_remote_code, **model_kwargs
    )
    peft_config = get_peft_config(model_config)
    if peft_config is None:
        ref_model = AutoModelForCausalLM.from_pretrained(
            model_config.model_name_or_path, trust_remote_code=model_config.trust_remote_code, **model_kwargs
        )
    else:
        ref_model = None
    tokenizer = AutoTokenizer.from_pretrained(
        model_config.model_name_or_path, trust_remote_code=model_config.trust_remote_code
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    # if tokenizer.chat_template is None:
    #     tokenizer.chat_template = SIMPLE_CHAT_TEMPLATE
    if script_args.ignore_bias_buffers:
        # torch distributed hack
        model._ddp_params_and_buffers_to_ignore = [
            name for name, buffer in model.named_buffers() if buffer.dtype == torch.bool
        ]

    ################
    # Dataset
    ################
    #dataset = load_dataset(script_args.dataset_name)
    dataset = LazySupervisedDataset(script_args.dataset_name)
    train_dataset = ds.from_dict({
    "prompt": [item["prompt"] for item in dataset.list_data_dict][:12000],
    "chosen": [item["chosen"] for item in dataset.list_data_dict][:12000],
    "rejected": [item["rejected"] for item in dataset.list_data_dict][:12000],
})
    eval_dataset = ds.from_dict({
        "prompt": [item["prompt"] for item in dataset.list_data_dict][12000:],
        "chosen": [item["chosen"] for item in dataset.list_data_dict][12000:],
        "rejected": [item["rejected"] for item in dataset.list_data_dict][12000:],
    })
    ##########
    # Training
    ################
    trainer = DPOTrainer(
        model,
        ref_model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )

    trainer.train()

    if training_args.eval_strategy != "no":
        metrics = trainer.evaluate()
        trainer.log_metrics("eval", metrics)
        trainer.save_metrics("eval", metrics)

    # Save and push to hub
    # trainer.save_model(training_args.output_dir)
    # if training_args.push_to_hub:
    #     trainer.push_to_hub(dataset_name=script_args.dataset_name)