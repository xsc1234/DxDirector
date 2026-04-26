#!/bin/bash

MODEL_PATH=/DxDirector-7B-instruct-FT
OUTPUT=/DxDirector-7B
DATA_PATH=/slso_data.json
mkdir -p $OUTPUT

CUDA_VISIBLE_DEVICES="1,2,3,4" accelerate launch --main_process_port 29504 --config_file=deepspeed_zero3.yaml --num_processes 4 slso_train.py \
    --dataset_name $DATA_PATH \
    --model_name_or_path $MODEL_PATH \
    --learning_rate 5.0e-7 \
    --num_train_epochs 1 \
    --per_device_train_batch_size 1 \
    --gradient_accumulation_steps 4 \
    --gradient_checkpointing \
    --logging_steps 25 \
    --eval_strategy steps \
    --eval_steps 1000 \
    --bf16 True \
    --output_dir $OUTPUT \
    --no_remove_unused_columns