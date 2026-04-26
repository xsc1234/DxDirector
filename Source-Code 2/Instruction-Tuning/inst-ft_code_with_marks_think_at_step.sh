#!/bin/bash
MODEL_PATH=/Path_to_Pretrained_LLama2
OUTPUT=/DxDirector-7B-instruct-FT
SFT_DATA_PATH=/inst-ft_data_MedQA_ask_assistant_v3_with_mark_open-end-deepseek-v3-add-sub-think.json
mkdir -p $OUTPUT

deepspeed --include localhost:3,4 --master_port 29510 inst-ft_code_with_marks_think_at_step.py \
   --sft_path $SFT_DATA_PATH \
   --data_split 2,4,4 \
   --dtype bf16 \
   --model_name_or_path $MODEL_PATH \
   --per_device_train_batch_size 1 \
   --per_device_eval_batch_size 1 \
   --max_seq_len 2048 \
   --learning_rate 9.65e-6 \
   --weight_decay 0. \
   --num_train_epochs 3  \
   --gradient_accumulation_steps 1 \
   --lr_scheduler_type cosine \
   --num_warmup_steps 0 \
   --seed 1234 \
   --gradient_checkpointing \
   --zero_stage 3 \
   --deepspeed \
   --print_loss \
   --output_dir $OUTPUT
